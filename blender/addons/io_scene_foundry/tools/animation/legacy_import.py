"""Reach-style skeleton and animation conversion for native legacy imports."""
import bpy
from math import radians
from mathutils import Matrix

from ... import import_transform, utils
from ...animation_aiming import blend_screen_yaw_span
from .automate_pose_overlay import BlendScreen, PoseBuilder, legacy_blend_screen_wrap_events


def prepare_reach_skeleton(armature):
    names = {}
    for bone in armature.data.bones:
        names.setdefault(utils.remove_node_prefix(bone.name).lower(), bone.name)
    required = ('pedestal', 'aim_yaw', 'aim_pitch')
    if not all(name in names for name in required):
        utils.set_object_mode(bpy.context)
        utils.deselect_all_objects()
        armature.select_set(True)
        utils.set_active_object(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bones = armature.data.edit_bones
            roots = [bone for bone in bones if bone.parent is None and bone.use_deform]
            for name in required:
                if name in names:
                    continue
                bone = bones.new(name)
                bone.tail = (0, max(import_transform.scale_factor(), 0.001), 0)
                bone.matrix = import_transform.rotation_matrix()
                names[name] = bone.name
                if name != 'pedestal':
                    bone.parent = bones[names['pedestal']]
            pedestal = bones[names['pedestal']]
            for root in roots:
                if root != pedestal and root.name not in (names['aim_yaw'], names['aim_pitch']):
                    root.use_connect = False
                    root.parent = pedestal
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

    scene_nwo = utils.get_scene_props()
    scene_nwo.node_usage_pedestal = names['pedestal']
    scene_nwo.node_usage_pose_blend_yaw = names['aim_yaw']
    scene_nwo.node_usage_pose_blend_pitch = names['aim_pitch']
    for name in required:
        armature.pose.bones[names[name]].rotation_mode = 'QUATERNION'
    return names


def split_root_movement(moved, unmoved, pedestal_rest):
    """Factor movement onto the pedestal without changing the resulting root pose.

    Both root matrices are in imported armature space. The returned old-root
    matrix is local to the pedestal; their product reproduces the original pose.
    """
    return moved @ unmoved.inverted_safe() @ pedestal_rest, pedestal_rest.inverted_safe() @ unmoved


def blend_screen_duplicate_frames(screen, frame_start=1):
    """Map repeated yaw/pitch samples to their first authored pose.

    Compare the two aim rotations separately: yaw remains meaningful at the
    pitch poles. Wraps distinguish otherwise identical screen coordinates.
    The additive reference is not a blend-screen sample.
    """
    unique = []
    duplicates = {}
    for index, (yaw, pitch, wrap) in enumerate(screen.transforms):
        frame = frame_start + index + 1
        for first_frame, first_yaw, first_pitch, first_wrap in unique:
            if wrap == first_wrap and all(abs(a[row][column] - b[row][column]) <= 1e-6
                   for a, b in ((yaw, first_yaw), (pitch, first_pitch))
                   for row in range(3) for column in range(3)):
                duplicates[frame] = first_frame
                break
        else:
            unique.append((frame, yaw, pitch, wrap))
    return duplicates


def strip_reach_blend_screen_duplicates(armature, animations, duplicate_frames):
    """Compact every action curve and event after native events are imported."""
    from .generate_aim_look_overlays import _armature_track, _fcurve_map

    for animation in animations:
        duplicates = duplicate_frames.get(animation.name, {})
        if not duplicates:
            continue
        track = _armature_track(animation, armature)
        if track is None:
            continue
        retained = [frame for frame in range(animation.frame_start, animation.frame_end + 1)
                    if frame not in duplicates]
        frame_map = {frame: animation.frame_start + index
                     for index, frame in enumerate(retained)}
        frame_map.update({frame: frame_map[first] for frame, first in duplicates.items()})
        _, slot = _fcurve_map(track.action, armature)
        curves = utils.get_fcurves(track.action, slot)
        # Sample before clearing so sparse source curves retain their poses.
        for curve in curves:
            values = [curve.evaluate(frame) for frame in retained]
            curve.keyframe_points.clear()
            curve.keyframe_points.add(len(retained))
            for point, frame, value in zip(curve.keyframe_points, retained, values):
                point.co = (frame_map[frame], value)
                point.interpolation = 'LINEAR'
            curve.update()
        for event in animation.animation_events:
            start = frame_map.get(event.frame_frame, event.frame_frame)
            end = frame_map.get(event.frame_range, event.frame_range)
            event.frame_frame = start
            event.frame_range = max(start, end)
        animation.frame_end = track.action.frame_end = frame_map[retained[-1]]
        animation.source_authoring_data = ''


def convert_blend_screen(armature, animation, action, slot, record, names, *, circular_aiming=None):
    screen = BlendScreen()
    screen.from_record(record)
    if circular_aiming is not None:
        animation.pose_overlay_aiming_source = 'CIRCULAR' if circular_aiming else 'PLANAR'
    animation.pose_overlay_yaw_span = blend_screen_yaw_span(screen)
    wrap_events = legacy_blend_screen_wrap_events(animation.name, animation, screen,
                                                 circular_aiming=circular_aiming)
    screen.compute_transforms(wrap_yaw_limit=90.0 if wrap_events else None)
    armature.animation_data.action = action
    armature.animation_data.action_slot = slot
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    builder = PoseBuilder(
        armature.pose.bones[names['pedestal']],
        armature.pose.bones[names['aim_pitch']],
        armature.pose.bones[names['aim_yaw']],
    )
    animation.pose_overlay = True
    with utils.ArmatureDeformMute():
        animation.frame_end = builder.build_from_blend_screen(
            bpy.context.scene, animation, action, wrap_events, screen, slot)
    action.frame_end = animation.frame_end
    return blend_screen_duplicate_frames(screen, animation.frame_start)


def generate_reach_aim_look_overlays(scene_nwo, armature, imported_animations, *, turns_with_aim_pose=None,
                                   prefer_move=False):
    """Fill missing movement overlays using only sources/bases from this import.

    When turn conversion results are supplied, only use successfully converted
    turns. A missing directional aim sample must not produce a shifted screen.
    """
    from .generate_aim_look_overlays import (
        _is_eligible_animation_mode, _retarget_overlay_state,
        _target_base_animations, generate_aim_look_overlays, _TURN_AIM_YAW_OFFSETS,
    )

    imported_pointers = {animation.as_pointer() for animation in imported_animations}
    imported_indices = [index for index, animation in enumerate(scene_nwo.animations)
                        if animation.as_pointer() in imported_pointers]
    generated = []
    if prefer_move:
        # Movement screens must win over still screens for locomotion leaves.
        imported_indices.sort(key=lambda index: '_move' not in utils.AnimationName(
            scene_nwo.animations[index].name).state)
    for source_index in imported_indices:
        source = scene_nwo.animations[source_index]
        name = utils.AnimationName(source.name)
        if (source.animation_type != 'overlay' or not source.pose_overlay
                or source.frame_end <= source.frame_start
                or not name.valid or name.custom
                or name.type != utils.AnimationStateType.ACTION
                or not _is_eligible_animation_mode(name.mode)
                or _retarget_overlay_state(name.state, 'move_front') is None):
            continue
        base_animations = [scene_nwo.animations[index] for index in imported_indices]
        if turns_with_aim_pose is not None:
            base_animations = [base for base in base_animations
                               if utils.AnimationName(base.name).state not in _TURN_AIM_YAW_OFFSETS
                               or base.name in turns_with_aim_pose]
        target_bases = _target_base_animations(base_animations, armature, name)
        if name.state.startswith(('aim_move', 'look_move')):
            if not prefer_move:
                continue
            target_bases = [(state, base) for state, base in target_bases
                            if state.startswith(('move_', 'walk_'))]
        if not target_bases:
            continue
        try:
            overlays, _skipped, _failed = generate_aim_look_overlays(
                scene_nwo, source, armature, target_bases,
                turns_with_aim_pose=turns_with_aim_pose or ())
            generated.extend(overlays)
        except ValueError as error:
            utils.print_warning(f"Failed to generate overlays for [{source.name}]: {error}")
    return [scene_nwo.animations[name] for name in generated]


def combine_reach_acc_overlays(scene_nwo, armature, imported_animations):
    """Join legacy acceleration screens, keeping one additive reference frame."""
    from .generate_aim_look_overlays import (
        _armature_track, _copy_property_group, _fcurve_map,
        _rest_local_matrix, _sample_local_matrices, _write_generated_transforms,
        _pose_bone_from_usage, _world_matrices,
    )

    states = ('acc_left_right', 'acc_front_back', 'acc_up_down')
    groups = {}
    imported_pointers = {animation.as_pointer() for animation in imported_animations}
    for source_index, animation in enumerate(scene_nwo.animations):
        if animation.as_pointer() not in imported_pointers:
            continue
        name = utils.AnimationName(animation.name)
        if (name.state not in states or animation.animation_type != 'overlay'
                or _armature_track(animation, armature) is None):
            continue
        tokens = animation.name.replace(':', ' ').split()
        tokens[tokens.index(name.state)] = 'acc'
        target_name = ' '.join(tokens)
        # Blender collection additions/removals can invalidate RNA references.
        # Names are not unique. Adjust original positions as sources are removed.
        groups.setdefault(target_name, []).append((states.index(name.state), source_index))

    rest = {bone.name: _rest_local_matrix(bone) for bone in armature.pose.bones}
    pedestal = _pose_bone_from_usage(armature, scene_nwo.node_usage_pedestal, ('pedestal',))
    yaw_bone = _pose_bone_from_usage(armature, scene_nwo.node_usage_pose_blend_yaw, ('aim_yaw',))
    pitch_bone = _pose_bone_from_usage(armature, scene_nwo.node_usage_pose_blend_pitch, ('aim_pitch',))
    if groups and any(bone is None for bone in (pedestal, yaw_bone, pitch_bone)):
        raise ValueError('Acceleration conversion requires pedestal, aim_yaw and aim_pitch bones')
    generated = []
    removed_indices = set()

    def current_index(original_index):
        return original_index - sum(index < original_index for index in removed_indices)

    def source_at(original_index):
        return scene_nwo.animations[current_index(original_index)]

    for target_name, sources in groups.items():
        if any(' '.join(item.name.replace(':', ' ').split()).casefold() == target_name.casefold()
               for item in scene_nwo.animations):
            utils.print_warning(f'Skipping acceleration conversion for [{target_name}]: already exists')
            continue
        sources.sort(key=lambda item: item[0])
        first_index = sources[0][1]
        first = source_at(first_index)
        frames = {}
        events = []
        aim_samples = {}
        for state_index, source_index in sources:
            source = source_at(source_index)
            curves, slot = _fcurve_map(_armature_track(source, armature).action, armature)
            if not frames:
                frames[1] = _sample_local_matrices(armature, curves, source.frame_start, rest)
            frame_map = {source.frame_start: 1} if source.pose_overlay else {}
            start = source.frame_start + int(source.pose_overlay)
            sample_count = source.frame_end - start + 1
            for frame in range(start, source.frame_end + 1):
                # Match Foundry's acceleration preset, with yaw before pitch.
                # The front endpoint uses -1 rather than 0 degrees, as in the
                # preset, to keep it distinct from the neutral aim sample.
                fraction = (frame - start) / max(sample_count - 1, 1)
                yaw, pitch = ((-90 + 180 * fraction, 0) if state_index == 0 else
                              (180 + 179 * fraction, 0) if state_index == 1 else
                              (0, 90 - 180 * fraction))
                yaw_matrix = Matrix.Rotation(radians(yaw), 4, 'Z')
                pitch_matrix = Matrix.Rotation(radians(pitch), 4, 'Y')
                signature = tuple(round(matrix[row][column], 6)
                                  for matrix in (yaw_matrix, pitch_matrix)
                                  for row in range(3) for column in range(3))
                if signature in aim_samples:
                    frame_map[frame] = aim_samples[signature]
                    continue
                target_frame = len(frames) + 1
                pose = _sample_local_matrices(armature, curves, frame, rest)
                world = _world_matrices(armature, pose)
                for bone, rotation in ((yaw_bone, yaw_matrix), (pitch_bone, pitch_matrix)):
                    desired = world[pedestal.name] @ rotation
                    pose[bone.name] = (world[bone.parent.name].inverted_safe() @ desired
                                       if bone.parent else desired)
                frames[target_frame] = pose
                aim_samples[signature] = target_frame
                frame_map[frame] = target_frame
            events.extend((source_index, index, frame_map)
                          for index in range(len(source.animation_events)))

        first_track = _armature_track(first, armature)
        action = first_track.action.copy()
        action.name = target_name
        _, slot = _fcurve_map(action, armature)
        try:
            _write_generated_transforms(action, armature, slot, frames, set(rest), rest)
        except Exception:
            bpy.data.actions.remove(action)
            raise
        target = scene_nwo.animations.add()
        first = source_at(first_index)
        first_track = _armature_track(first, armature)
        _copy_property_group(first, target, skip={
            'name', 'name_old', 'action_tracks', 'animation_renames', 'animation_events',
            'blend_axis_active_index',
        })
        track = target.action_tracks.add()
        _copy_property_group(first_track, track)
        track.action = action
        target.name = target.name_old = target_name
        target.state = 'acc'
        target.pose_overlay = True
        target.pose_overlay_source = 'pose'
        target.blend_screen = ''
        target.source_authoring_data = ''
        target.frame_start = action.frame_start = 1
        target.frame_end = action.frame_end = len(frames)
        for source_index, event_index, frame_map in events:
            source_event = source_at(source_index).animation_events[event_index]
            event = target.animation_events.add()
            _copy_property_group(source_event, event)
            # Capture both endpoints before setters enforce range >= start.
            endpoints = {field: frame_map.get(getattr(source_event, field),
                                             getattr(source_event, field))
                         for field in ('frame_frame', 'frame_range')}
            for field in ('frame_frame', 'frame_range'):
                setattr(event, field, endpoints[field])
        for original_index in sorted({index for _, index in sources}, reverse=True):
            scene_nwo.animations.remove(current_index(original_index))
            removed_indices.add(original_index)
        generated.append(target_name)
    return generated

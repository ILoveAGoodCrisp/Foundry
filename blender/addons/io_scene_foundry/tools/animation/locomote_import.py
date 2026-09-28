"""Build Halo 4 / H2AMP locomotion from imported movement cycles."""
import re

import bpy
from mathutils import Matrix

from ... import import_transform, utils
from ...constants import WU_SCALAR
from .generate_aim_look_overlays import (
    _armature_track, _copy_property_group, _fcurve_map, _is_eligible_animation_mode,
    _lower_body_bone_names, _normalized_name, _pose_bone_from_usage,
    _replace_action_state, _rest_local_matrix, _sample_local_matrices,
    _world_matrices, _write_generated_transforms,
)


ANGLES = {'front': 0, 'frontleft': 45, 'left': 90, 'backleft': 135,
          'back': 180, 'backright': -135, 'right': -90, 'frontright': -45}
DIAGONALS = {'frontleft': ('front', 'left'), 'frontright': ('front', 'right'),
             'backleft': ('back', 'left'), 'backright': ('back', 'right')}
MOVEMENT = re.compile(r'^(?P<aim>aim_|look_)?(?P<gait>move|walk|walkslow)_(?P<direction>front|back|left|right|frontleft|frontright|backleft|backright|inplace)(?P<suffix>_up|_down)?$')
LOCOMOTE = re.compile(r'^locomote_(run|walk|walkslow)_(front|back|left|right|frontleft|frontright|backleft|backright|inplace)$')


def locomote_name(label):
    name = utils.AnimationName(label)
    if not name.valid or name.custom or name.type != utils.AnimationStateType.ACTION:
        return label
    if not _is_eligible_animation_mode(name.mode):
        return label
    match = MOVEMENT.fullmatch(name.state)
    if match is None:
        return label
    gait = 'run' if match['gait'] == 'move' else match['gait']
    state = f"{match['aim'] or ''}locomote_{gait}_{match['direction']}{match['suffix'] or ''}"
    return _replace_action_state(label, state)


def _blend_matrix(first, second):
    a, ar, asc = first.decompose()
    b, br, bsc = second.decompose()
    return Matrix.LocRotScale(a.lerp(b, 0.5), ar.slerp(br, 0.5), asc.lerp(bsc, 0.5))


def _foot_phase(animation):
    for event in animation.animation_events:
        if event.event_type == '_connected_geometry_animation_event_type_frame' and event.frame_name in {'left foot', 'right foot'}:
            return event.frame_name, (event.frame_frame - animation.frame_start) / max(1, animation.frame_end - animation.frame_start)
    return None


def _diagonal(scene_nwo, armature, first_index, second_index, target_name):
    first, second = scene_nwo.animations[first_index], scene_nwo.animations[second_index]
    first_track, second_track = _armature_track(first, armature), _armature_track(second, armature)
    if first_track is None or second_track is None or min(first.frame_end - first.frame_start, second.frame_end - second.frame_start) <= 0:
        return None
    pedestal = _pose_bone_from_usage(armature, scene_nwo.node_usage_pedestal, ('pedestal',))
    if pedestal is None:
        return None
    lower = _lower_body_bone_names(armature, scene_nwo, pedestal)
    roots = {pedestal.name, *(bone.name for bone in pedestal.parent_recursive)}
    if not lower - roots:
        return None
    rest = {bone.name: _rest_local_matrix(bone) for bone in armature.pose.bones}
    curves_a, slot = _fcurve_map(first_track.action, armature)
    curves_b, _ = _fcurve_map(second_track.action, armature)
    if not curves_a or not curves_b:
        return None
    # Keep the first cycle's duration, upper body and events. Resample the other
    # cycle by normalized phase; align a matching footfall when one is available.
    phase_offset = 0.0
    foot = _foot_phase(first)
    if foot:
        for event in second.animation_events:
            if event.event_type == '_connected_geometry_animation_event_type_frame' and event.frame_name == foot[0]:
                phase_offset = (event.frame_frame - second.frame_start) / (second.frame_end - second.frame_start) - foot[1]
                break
    span_a, span_b = first.frame_end - first.frame_start, second.frame_end - second.frame_start
    frames = {}
    for frame in range(first.frame_start, first.frame_end + 1):
        phase = (frame - first.frame_start) / span_a
        pose_a = _sample_local_matrices(armature, curves_a, frame, rest)
        pose_b = _sample_local_matrices(armature, curves_b, second.frame_start + phase * span_b, rest)
        legs_b = (_sample_local_matrices(armature, curves_b,
                  second.frame_start + ((phase + phase_offset) % 1.0) * span_b, rest)
                  if phase_offset else pose_b)
        frames[frame] = {bone: _blend_matrix(pose_a[bone], pose_b[bone] if bone in roots else legs_b[bone])
                         for bone in lower}
    # Averaging perpendicular velocities loses speed. Normalize the pedestal
    # displacement to the mean source speed, accounting for different durations.
    start, end = first.frame_start, first.frame_end
    a0 = _sample_local_matrices(armature, curves_a, start, rest)[pedestal.name].translation
    a1 = _sample_local_matrices(armature, curves_a, end, rest)[pedestal.name].translation
    b0 = _sample_local_matrices(armature, curves_b, second.frame_start, rest)[pedestal.name].translation
    b1 = _sample_local_matrices(armature, curves_b, second.frame_end, rest)[pedestal.name].translation
    velocity_a, velocity_b = (a1 - a0) / span_a, (b1 - b0) / span_b
    direction = velocity_a.to_2d().normalized() + velocity_b.to_2d().normalized()
    if direction.length:
        desired = direction.normalized() * ((velocity_a.to_2d().length + velocity_b.to_2d().length) * 0.5 * span_a)
        actual = (frames[end][pedestal.name].translation - frames[start][pedestal.name].translation).to_2d()
        correction = desired - actual
        for frame, pose in frames.items():
            offset = correction * ((frame - start) / span_a)
            pose[pedestal.name].translation += offset.to_3d()
    action = first_track.action.copy()
    action.name = target_name
    try:
        _write_generated_transforms(action, armature, slot, frames, lower, rest, preserve_other_transforms=True)
    except Exception:
        bpy.data.actions.remove(action)
        raise
    target = scene_nwo.animations.add()
    first = scene_nwo.animations[first_index]
    _copy_property_group(first, target, skip={'name', 'name_old', 'action_tracks', 'animation_renames', 'blend_axis_active_index'})
    # Other-object tracks cannot be meaningfully interpolated here.
    track = target.action_tracks.add()
    _copy_property_group(_armature_track(first, armature), track)
    track.action = action
    target.name = target.name_old = target_name
    target.state = utils.AnimationName(target_name).state
    target.external = False
    target.gr2_path = target.blend_path = ''
    return len(scene_nwo.animations) - 1


def _speed(animation, armature, scene_nwo):
    track = _armature_track(animation, armature)
    pedestal = _pose_bone_from_usage(armature, scene_nwo.node_usage_pedestal, ('pedestal',))
    if track is None or pedestal is None or animation.frame_end <= animation.frame_start:
        return 0.0
    curves, _ = _fcurve_map(track.action, armature)
    rest = {bone.name: _rest_local_matrix(bone) for bone in armature.pose.bones}
    positions = [_world_matrices(armature, _sample_local_matrices(armature, curves, frame, rest))[pedestal.name].translation
                 for frame in (animation.frame_start, animation.frame_end)]
    fps = bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
    return ((positions[1] - positions[0]).to_2d().length * fps / (animation.frame_end - animation.frame_start)
            * 0.03048 * WU_SCALAR / import_transform.scale_factor(scene_nwo))


def _composite(scene_nwo, name, leaves, *, overlay=False):
    if not leaves or any(_normalized_name(item.name) == _normalized_name(name) for item in scene_nwo.animations):
        return None
    composite = scene_nwo.animations.add()
    composite.name = composite.name_old = name
    composite.state = utils.AnimationName(name).state
    composite.animation_type = 'composite'
    composite.pose_overlay = overlay
    composite.timing_source = next((source for source, speed, _ in leaves if speed > 0), leaves[0][0])
    speed = composite.blend_axis.add()
    speed.name = 'movement_speed'
    speed.relationship = 'PARENT'
    speed.animation_source_bounds_manual = speed.runtime_source_bounds_manual = True
    speed.animation_source_bounds = speed.runtime_source_bounds = (0, max(value for _, value, _ in leaves) or 1)
    speed.runtime_source_clamped = True
    angle = composite.blend_axis.add()
    angle.name = 'movement_angles'
    angle.relationship = 'CHILD'
    angle.animation_source_bounds_manual = angle.runtime_source_bounds_manual = True
    angle.animation_source_bounds = angle.runtime_source_bounds = (-180, 180)
    angle.animation_source_limit = 90
    phase = angle.phase_sets.add()
    phase.name = 'locomotion'
    phase.key_left_foot = phase.key_right_foot = not overlay
    for source, value, direction in leaves:
        leaf = phase.leaves.add()
        leaf.animation = source
        leaf.manual_blend_axis_0 = leaf.manual_blend_axis_1 = True
        leaf.blend_axis_0, leaf.blend_axis_1 = value, ANGLES.get(direction, 0)
    return composite.name


def convert_locomotion(scene_nwo, armature, imported_start):
    """Convert only this import, preserving existing authored target animations."""
    imported_end = len(scene_nwo.animations)
    occupied = {_normalized_name(item.name) for item in scene_nwo.animations}
    for index in range(imported_start, imported_end):
        animation = scene_nwo.animations[index]
        renamed = locomote_name(animation.name)
        if renamed != animation.name and _normalized_name(renamed) not in occupied:
            occupied.discard(_normalized_name(animation.name))
            animation.name = animation.name_old = renamed
            animation.state = utils.AnimationName(renamed).state
            occupied.add(_normalized_name(renamed))
        for rename in animation.animation_renames:
            rename.name = locomote_name(rename.name)
    groups = {}
    for index in range(imported_start, imported_end):
        animation = scene_nwo.animations[index]
        name = utils.AnimationName(animation.name)
        match = LOCOMOTE.fullmatch(name.state)
        if (animation.animation_type != 'base' or not match or not name.valid or name.custom
                or name.type != utils.AnimationStateType.ACTION or not _is_eligible_animation_mode(name.mode)):
            continue
        group_name = _replace_action_state(animation.name, 'locomote')
        groups.setdefault(group_name, {}).setdefault(match[1], {})[match[2]] = index
    generated = []
    for group_name, gaits in groups.items():
        base_leaves, aim_leaves = [], []
        idle_name = _replace_action_state(group_name, 'idle')
        idle = next((item for item in scene_nwo.animations[imported_start:]
                     if _normalized_name(item.name) == _normalized_name(idle_name)
                     and item.animation_type == 'base'), None)
        if idle is not None:
            base_leaves.append((idle.name, 0.0, 'front'))
        still_name = _replace_action_state(group_name, 'aim_still_up')
        still = next((item for item in scene_nwo.animations[imported_start:]
                      if _normalized_name(item.name) == _normalized_name(still_name)
                      and item.animation_type == 'overlay' and item.pose_overlay), None)
        still_source = still.name if still is not None else None
        for gait, directions in gaits.items():
            for diagonal, (first, second) in DIAGONALS.items():
                if diagonal in directions or first not in directions or second not in directions:
                    continue
                target_name = _replace_action_state(group_name, f'locomote_{gait}_{diagonal}')
                if _normalized_name(target_name) in occupied:
                    continue
                try:
                    index = _diagonal(scene_nwo, armature, directions[first], directions[second], target_name)
                except (ValueError, RuntimeError) as error:
                    utils.print_warning(f"Skipping diagonal [{target_name}]: {error}")
                    continue
                if index is not None:
                    directions[diagonal] = index
                    occupied.add(_normalized_name(target_name))
                    generated.append(target_name)
            for direction, index in directions.items():
                animation = scene_nwo.animations[index]
                speed = _speed(animation, armature, scene_nwo)
                base_leaves.append((animation.name, speed, direction))
                aim_name = _replace_action_state(animation.name, f'aim_locomote_{gait}_{direction}_up')
                aim = next((item for item in scene_nwo.animations[imported_start:]
                            if _normalized_name(item.name) == _normalized_name(aim_name)
                            and item.animation_type == 'overlay' and item.pose_overlay), None)
                if aim is not None:
                    aim_leaves.append((aim.name, speed, direction))
        if aim_leaves and still_source is not None:
            aim_leaves.append((still_source, 0.0, 'front'))
        for name, leaves, overlay in ((group_name, base_leaves, False),
                                      (_replace_action_state(group_name, 'aim_locomote_up'), aim_leaves, True)):
            result = _composite(scene_nwo, name, leaves, overlay=overlay)
            if result is not None:
                generated.append(result)
    return generated

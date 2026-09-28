"""Build Halo 4 / H2AMP locomotion from imported movement cycles."""
import re
from math import atan2

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
    # A strafe and a forward/backward cycle can have incompatible foot phases
    # and pelvis orientations. Averaging their local poses produces crossed
    # legs and twisted hips even when a foot event happens to line up. Keep
    # the longitudinal cycle intact and redirect its complete lower body.
    span_a, span_b = first.frame_end - first.frame_start, second.frame_end - second.frame_start
    def root_position(curves, frame):
        return _world_matrices(armature, _sample_local_matrices(armature, curves, frame, rest))[pedestal.name].translation

    a0, a1 = root_position(curves_a, first.frame_start), root_position(curves_a, first.frame_end)
    b0, b1 = root_position(curves_b, second.frame_start), root_position(curves_b, second.frame_end)
    velocity_a, velocity_b = (a1 - a0).to_2d() / span_a, (b1 - b0).to_2d() / span_b
    if min(velocity_a.length, velocity_b.length) < 1e-8:
        utils.print_warning(f"Skipping diagonal [{target_name}]: both sources need horizontal pedestal displacement")
        return None
    direction = velocity_a.normalized() + velocity_b.normalized()
    if direction.length < 1e-6:
        utils.print_warning(f"Skipping diagonal [{target_name}]: source movement directions oppose each other")
        return None
    direction.normalize()
    yaw = atan2(direction.y, direction.x) - atan2(velocity_a.y, velocity_a.x)
    redirect = Matrix.Rotation(yaw, 4, 'Z')
    speed_scale = (velocity_a.length + velocity_b.length) * 0.5 / velocity_a.length
    # Counter-rotate the first upper-body bones below the hips. Their positions
    # follow the redirected pelvis, while chest/weapon orientation stays intact.
    boundary = {bone.name for bone in armature.pose.bones
                if bone.name not in lower and bone.parent is not None and bone.parent.name in lower - roots}
    written = lower | boundary
    frames = {}
    for frame in range(first.frame_start, first.frame_end + 1):
        pose_a = _sample_local_matrices(armature, curves_a, frame, rest)
        world = _world_matrices(armature, pose_a)
        old_root = world[pedestal.name].translation
        displacement = redirect.to_3x3() @ (old_root - a0)
        displacement.x *= speed_scale
        displacement.y *= speed_scale
        new_root = a0 + displacement
        transform = Matrix.Translation(new_root) @ redirect @ Matrix.Translation(-old_root)
        target_world = dict(world)
        target_world[pedestal.name] = world[pedestal.name].copy()
        target_world[pedestal.name].translation = new_root
        for name in lower - roots:
            target_world[name] = transform @ world[name]
        for name in boundary:
            bone = armature.pose.bones[name]
            attached = target_world[bone.parent.name] @ pose_a[name]
            _, rotation, scale = world[name].decompose()
            target_world[name] = Matrix.LocRotScale(attached.translation, rotation, scale)
        frames[frame] = {}
        for name in written:
            bone = armature.pose.bones[name]
            frames[frame][name] = (target_world[bone.parent.name].inverted_safe() @ target_world[name]
                                   if bone.parent else target_world[name])
    action = first_track.action.copy()
    action.name = target_name
    try:
        _write_generated_transforms(action, armature, slot, frames, written, rest, preserve_other_transforms=True)
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
    if animation.animation_movement_data not in {'xy', 'xyyaw', 'xyzyaw', 'full', 'world'}:
        return 0.0
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
    directional = len({ANGLES.get(direction, 0) for _, value, direction in leaves if value > 0}) > 1
    # Keep all source actions, but choose one representative for each generated
    # blend coordinate (idle wins over an in-place gait because it comes first).
    unique = {}
    for source, value, direction in leaves:
        key = (round(value, 6), ANGLES.get(direction, 0) if directional else 0)
        if key in unique:
            utils.print_warning(f"Composite [{name}]: [{source}] shares blend coordinates with [{unique[key][0]}]; keeping the first source")
            continue
        unique[key] = (source, value, direction)
    leaves = list(unique.values())
    composite = scene_nwo.animations.add()
    composite.name = composite.name_old = name
    composite.state = utils.AnimationName(name).state
    composite.animation_type = 'composite'
    composite.overlay = overlay
    composite.pose_overlay = overlay
    composite.timing_source = next((source for source, speed, _ in leaves if speed > 0), leaves[0][0])
    if directional:
        angle = composite.blend_axis.add()
        angle.name = 'movement_angles'
        angle.relationship = 'PARENT'
        angle.animation_source_bounds_manual = angle.runtime_source_bounds_manual = True
        angle.animation_source_bounds = angle.runtime_source_bounds = (-180, 180)
        # Sparse converted gaits do not provide the directional stationary rows
        # used by stock composites. A finite angle limit can leave no usable
        # triangles and stall Tool's constrained triangulation.
        angle.animation_source_limit = 0
    speed = composite.blend_axis.add()
    speed.name = 'movement_speed'
    speed.relationship = 'CHILD' if directional else 'PARENT'
    speed.animation_source_bounds_manual = speed.runtime_source_bounds_manual = True
    speed.animation_source_bounds = speed.runtime_source_bounds = (0, 1)
    speed.runtime_source_clamped = True
    # A single population needs no explicit phase set. Keep the leaves directly
    # on the terminal axis, as in retail locomotes.
    for source, value, direction in leaves:
        leaf = speed.leaves.add()
        leaf.animation = source
        leaf.manual_blend_axis_0 = leaf.manual_blend_axis_1 = True
        leaf.blend_axis_0, leaf.blend_axis_1 = (ANGLES.get(direction, 0), value) if directional else (value, 0)
    if len(leaves) == 1:
        # One source is a constant-pose speed blend, not a one-point simplex.
        speed.leaves[0].blend_axis_0 = 0
        leaf = speed.leaves.add()
        leaf.animation = leaves[0][0]
        leaf.manual_blend_axis_0 = leaf.manual_blend_axis_1 = True
        leaf.blend_axis_0 = speed.animation_source_bounds[1]
    return composite.name


def _fill_locomote_aim(scene_nwo, armature, group_name, directions, imported_start):
    """Build missing aim leaves against the final base poses, including diagonals."""
    from .generate_aim_look_overlays import generate_aim_look_overlays
    generated = []
    # Only use screens from this import and this exact mode/weapon/variant.
    for state in ('aim_move_up', 'aim_still_up'):
        source_name = _normalized_name(_replace_action_state(group_name, state))
        source_index = next((index for index in range(imported_start, len(scene_nwo.animations))
                             if _normalized_name(scene_nwo.animations[index].name) == source_name
                             and scene_nwo.animations[index].animation_type == 'overlay'
                             and scene_nwo.animations[index].pose_overlay
                             and scene_nwo.animations[index].frame_end > scene_nwo.animations[index].frame_start), None)
        if source_index is None:
            continue
        bases = [(utils.AnimationName(scene_nwo.animations[index].name).state, scene_nwo.animations[index])
                 for index in directions.values()]
        try:
            names, _, _ = generate_aim_look_overlays(
                scene_nwo, scene_nwo.animations[source_index], armature, bases)
            generated.extend(names)
        except ValueError as error:
            utils.print_warning(f"Skipping missing aim locomotes for [{group_name}]: {error}")
    return generated


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
        sprint = name.mode == 'sprint' and name.state == 'move_front_fast'
        if (animation.animation_type != 'base' or not (match or sprint) or not name.valid or name.custom
                or name.type != utils.AnimationStateType.ACTION or not _is_eligible_animation_mode(name.mode)):
            continue
        group_name = _replace_action_state(animation.name, 'locomote')
        gait, direction = ('sprint', 'front') if sprint else (match[1], match[2])
        groups.setdefault(group_name, {}).setdefault(gait, {})[direction] = index
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
            new_aim = _fill_locomote_aim(scene_nwo, armature, group_name, directions, imported_start)
            generated.extend(new_aim)
            occupied.update(_normalized_name(name) for name in new_aim)
            for direction, index in directions.items():
                animation = scene_nwo.animations[index]
                speed = 0.0 if direction == 'inplace' else {'run': 1.0, 'sprint': 1.0, 'walk': 0.5, 'walkslow': 0.2}[gait]
                base_leaves.append((animation.name, speed, direction))
                aim_name = _replace_action_state(animation.name, f'aim_{utils.AnimationName(animation.name).state}_up')
                aim = next((item for item in scene_nwo.animations[imported_start:]
                            if _normalized_name(item.name) == _normalized_name(aim_name)
                            and item.animation_type == 'overlay' and item.pose_overlay), None)
                if aim is not None:
                    aim_leaves.append((aim.name, speed, direction))
        if aim_leaves and still_source is not None:
            aim_leaves.append((still_source, 0.0, 'front'))
        for name, leaves, overlay in ((group_name, base_leaves, False),
                                      (_replace_action_state(group_name, 'aim_locomote_up'), aim_leaves, True)):
            # Normalized gait rows need stationary support across the angular
            # range. A single idle at angle zero can still stall triangulation,
            # even with unlimited blending. Reuse its action at each column.
            stationary = next((source for source, value, _ in leaves if value == 0), None)
            if stationary is not None:
                moving_directions = {direction for _, value, direction in leaves if value > 0}
                stationary_angles = {ANGLES.get(direction, 0) for _, value, direction in leaves if value == 0}
                if len(moving_directions) > 1:
                    leaves.extend((stationary, 0.0, direction) for direction in sorted(moving_directions)
                                  if ANGLES.get(direction, 0) not in stationary_angles)
            result = _composite(scene_nwo, name, leaves, overlay=overlay)
            if result is not None:
                generated.append(result)
    return generated

"""Rebase legacy turn poses onto their own aim screen without changing movement."""
from ... import utils
from .generate_aim_look_overlays import (
    _apply_turn_aim_delta, _armature_track, _base_candidate_score,
    _evaluated_action_poses, _lower_body_bone_names, _sample_turn_aim_reference,
    _TURN_AIM_YAW_OFFSETS,
    _fcurve_map, _has_bone_transform, _is_eligible_animation_mode, _pose_bone_from_usage,
    _rest_local_matrix, _sample_local_matrices, _write_generated_transforms,
)


_TURN_DIRECTIONS = {
    f"turn_{direction}{suffix}": direction
    for direction in ("left", "right")
    for suffix in ("", "_fast", "_slow")
}


def _matching_aim_overlay(animations, armature, turn_name):
    candidates = []
    for index, animation in enumerate(animations):
        if (animation.animation_type != 'overlay' or not animation.pose_overlay
                or animation.frame_end <= animation.frame_start
                or _armature_track(animation, armature) is None):
            continue
        name = utils.AnimationName(animation.name)
        if (not name.valid or name.custom or name.type != utils.AnimationStateType.ACTION
                or name.state not in {'aim_still_up', 'aim_still'}):
            continue
        score = _base_candidate_score(turn_name, name, index)
        if score is not None:
            # Scope specificity wins, then prefer the up screen and same variant.
            candidates.append(((*score[:4], name.state == 'aim_still_up',
                                name.variant == turn_name.variant, *score[4:]), animation))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _turn_aim_reference(overlay, armature, pedestal, yaw_bone, pitch_bone, direction):
    poses = _evaluated_action_poses(
        _armature_track(overlay, armature).action, armature,
        range(overlay.frame_start, overlay.frame_end + 1),
    )
    return _sample_turn_aim_reference(
        armature, overlay, poses, pedestal.name, yaw_bone.name, pitch_bone.name,
        _TURN_AIM_YAW_OFFSETS[f'turn_{direction}'],
    )


def convert_reach_turn_poses(scene_nwo, armature, imported_animations):
    """Match each imported turn's starting body pose to its directional aim pose.

    Keep pedestal, pelvis and leg curves, duration, events and action identity.
    Transfer upper-body rotations relative to the pedestal onto a sampled
    +/-45 degree aim pose, and smoothly remove their terminal rotation drift.
    Return successfully converted names.
    """
    animations = tuple(imported_animations)
    pedestal = _pose_bone_from_usage(armature, scene_nwo.node_usage_pedestal, ('pedestal',))
    yaw = _pose_bone_from_usage(armature, scene_nwo.node_usage_pose_blend_yaw, ('aim_yaw',))
    pitch = _pose_bone_from_usage(armature, scene_nwo.node_usage_pose_blend_pitch, ('aim_pitch',))
    if any(bone is None for bone in (pedestal, yaw, pitch)):
        return []
    preserved = _lower_body_bone_names(armature, scene_nwo, pedestal)
    preserved.difference_update((yaw.name, pitch.name))
    rest = {bone.name: _rest_local_matrix(bone) for bone in armature.pose.bones}
    converted = []
    reference_cache = {}
    for animation in animations:
        if animation.animation_type != 'base' or animation.frame_end <= animation.frame_start:
            continue
        name = utils.AnimationName(animation.name)
        direction = _TURN_DIRECTIONS.get(name.state)
        if (not direction or not name.valid or name.custom
                or name.type != utils.AnimationStateType.ACTION
                or not _is_eligible_animation_mode(name.mode)):
            continue
        track = _armature_track(animation, armature)
        if track is None:
            continue
        overlay = _matching_aim_overlay(animations, armature, name)
        if overlay is None:
            utils.print_warning(f"Skipping turn pose conversion for [{animation.name}]: no matching aim_still_up/aim_still overlay")
            continue
        key = (overlay.as_pointer(), direction)
        if key not in reference_cache:
            reference_cache[key] = _turn_aim_reference(overlay, armature, pedestal, yaw, pitch, direction)
        aim_reference = reference_cache[key]
        if aim_reference is None:
            utils.print_warning(f"Skipping turn pose conversion for [{animation.name}]: no level {direction} aim coverage at 45 degrees")
            continue
        curves, slot = _fcurve_map(track.action, armature)
        if not curves:
            continue
        aim_curves, _ = _fcurve_map(_armature_track(overlay, armature).action, armature)
        body_names = {bone.name for bone in armature.pose.bones
                      if bone.name not in preserved
                      and (_has_bone_transform(curves, bone) or _has_bone_transform(aim_curves, bone))}
        body_names.update((yaw.name, pitch.name))
        source_reference = _sample_local_matrices(armature, curves, animation.frame_start, rest)
        source_end = _sample_local_matrices(armature, curves, animation.frame_end, rest)
        frames = {}
        for frame in range(animation.frame_start, animation.frame_end + 1):
            pose = _sample_local_matrices(armature, curves, frame, rest)
            # Only rotations are rebased. Local translations/scales and all
            # lower-body curves retain the source turn's placement and motion.
            output = {bone: matrix.copy() for bone, matrix in pose.items()}
            progress = (frame - animation.frame_start) / (animation.frame_end - animation.frame_start)
            tail = max(0.0, (progress - .75) / .25)
            _apply_turn_aim_delta(
                armature, source_reference, pose, aim_reference, output,
                pedestal.name, body_names, source_end=source_end,
                endpoint_weight=tail * tail * (3.0 - 2.0 * tail),
            )
            frames[frame] = output
        _write_generated_transforms(track.action, armature, slot, frames, body_names, rest,
                                    preserve_other_transforms=True)
        animation.source_authoring_data = ''
        converted.append(animation.name)
    return converted

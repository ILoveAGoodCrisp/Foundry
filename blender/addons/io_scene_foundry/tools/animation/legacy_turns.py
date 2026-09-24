"""Rebase legacy turn poses onto their own aim screen without changing movement."""
from math import atan2, radians

from ... import utils
from .generate_aim_look_overlays import (
    _armature_track, _base_candidate_score, _compose_overlay_transform,
    _fcurve_map, _has_bone_transform, _is_eligible_animation_mode, _pose_bone_from_usage,
    _rest_local_matrix, _sample_local_matrices, _world_matrices,
    _write_generated_transforms, _WRAP_EVENT_NAMES, _WRAP_EVENT_TYPE,
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


def _turn_aim_reference(overlay, armature, pedestal, yaw_bone, pitch_bone, direction, rest):
    curves, _ = _fcurve_map(_armature_track(overlay, armature).action, armature)
    if not curves:
        return None
    wrapped_frames = {event.frame_frame for event in overlay.animation_events
                      if event.event_type == _WRAP_EVENT_TYPE and event.import_name in _WRAP_EVENT_NAMES}
    samples = []
    # The first frame is the additive reference, not an aim-screen sample.
    for frame in range(overlay.frame_start + 1, overlay.frame_end + 1):
        if frame in wrapped_frames:
            continue
        pose = _sample_local_matrices(armature, curves, frame, rest)
        world = _world_matrices(armature, pose)
        pedestal_inverse = world[pedestal.name].inverted_safe()
        yaw_matrix = pedestal_inverse @ world[yaw_bone.name]
        pitch_matrix = pedestal_inverse @ world[pitch_bone.name]
        yaw = atan2(yaw_matrix[1][0], yaw_matrix[0][0])
        pitch = abs(pitch_matrix.to_euler('XYZ').y)
        if (yaw > radians(0.1) if direction == 'left' else yaw < -radians(0.1)):
            samples.append((pitch, yaw, pose))
    if not samples:
        return None
    neutral_pitch = min(pitch for pitch, _, _ in samples)
    if neutral_pitch > radians(5):
        return None
    samples = [sample for sample in samples if sample[0] <= neutral_pitch + radians(0.1)]
    return (max if direction == 'left' else min)(samples, key=lambda sample: sample[1])[2]


def convert_reach_turn_poses(scene_nwo, armature, imported_animations):
    """Match each imported turn's starting body pose to its directional aim pose.

    Keep the original pedestal/ancestor curves, duration, events and action
    identity. Apply the turn's local skeletal motion relative to its first frame
    on top of the selected aim reference. Return successfully converted names.
    """
    animations = tuple(imported_animations)
    pedestal = _pose_bone_from_usage(armature, scene_nwo.node_usage_pedestal, ('pedestal',))
    yaw = _pose_bone_from_usage(armature, scene_nwo.node_usage_pose_blend_yaw, ('aim_yaw',))
    pitch = _pose_bone_from_usage(armature, scene_nwo.node_usage_pose_blend_pitch, ('aim_pitch',))
    if any(bone is None for bone in (pedestal, yaw, pitch)):
        return []
    preserved = {pedestal.name, *(bone.name for bone in pedestal.parent_recursive)}
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
            reference_cache[key] = _turn_aim_reference(overlay, armature, pedestal, yaw, pitch, direction, rest)
        aim_reference = reference_cache[key]
        if aim_reference is None:
            utils.print_warning(f"Skipping turn pose conversion for [{animation.name}]: no level {direction} aim sample")
            continue
        curves, slot = _fcurve_map(track.action, armature)
        if not curves:
            continue
        aim_curves, _ = _fcurve_map(_armature_track(overlay, armature).action, armature)
        body_names = {bone.name for bone in armature.pose.bones
                      if bone.name not in preserved
                      and (_has_bone_transform(curves, bone) or _has_bone_transform(aim_curves, bone))}
        source_reference = _sample_local_matrices(armature, curves, animation.frame_start, rest)
        frames = {}
        for frame in range(animation.frame_start, animation.frame_end + 1):
            pose = _sample_local_matrices(armature, curves, frame, rest)
            frames[frame] = {
                bone: _compose_overlay_transform(source_reference[bone], pose[bone], aim_reference[bone])
                for bone in body_names
            }
        _write_generated_transforms(track.action, armature, slot, frames, body_names, rest,
                                    preserve_other_transforms=True)
        converted.append(animation.name)
    return converted

import random
import re
from math import degrees, radians

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from ... import utils


_DIRECTIONS = ("front", "right", "left", "back")
_VALID_BASE_STATES = tuple(
    [f"walk_{direction}" for direction in _DIRECTIONS]
    + [f"move_{direction}" for direction in _DIRECTIONS]
    + ["airborne"]
    + [f"turn_{direction}" for direction in _DIRECTIONS]
)
_BONE_TRANSFORM_PROPERTIES = (
    "location",
    "rotation_quaternion",
    "rotation_euler",
    "rotation_axis_angle",
    "scale",
)
_LOWER_BODY_NAME_TOKENS = (
    "thigh", "leg", "calf", "shin", "knee", "ankle", "foot", "toe", "tarsal",
)
_WRAP_EVENT_TYPE = "_connected_geometry_animation_event_type_import"
_WRAP_EVENT_NAMES = {"Wrapped Left", "Wrapped Right"}
_TURN_AIM_YAW_OFFSETS = {"turn_left": 45.0, "turn_right": -45.0}
_SOURCE_STATE_PATTERN = re.compile(r"^(aim|look)_still(?P<suffix>(?:_.*)?)$")


def _normalized_name(name: str) -> str:
    return " ".join((name or "").replace(":", " ").split()).lower()


def _is_vehicle_animation_mode(mode: str) -> bool:
    """Keep this in sync with AnimationTag._is_vehicle_animation_mode."""
    mode = (mode or "").strip()
    return len(mode) > 2 and mode[-2] == "_" and mode[-1] != "_"


def _is_eligible_animation_mode(mode: str) -> bool:
    mode = (mode or "").strip().lower()
    return bool(mode) and mode != "bunker" and not _is_vehicle_animation_mode(mode)


def _retarget_overlay_state(state: str, base_state: str) -> str | None:
    match = _SOURCE_STATE_PATTERN.fullmatch((state or "").lower())
    if match is None:
        return None
    return f"{match.group(1)}_{base_state}{match.group('suffix')}"


def _replace_action_state(name: str, state: str) -> str:
    parsed = utils.AnimationName(name)
    if not parsed.valid or parsed.custom or parsed.type != utils.AnimationStateType.ACTION:
        return name
    tokens = _normalized_name(name).split()
    variant = tokens.pop() if tokens and tokens[-1].startswith("var") and tokens[-1][3:].isdigit() else ""
    if not tokens:
        return name
    tokens[-1] = state
    if variant:
        tokens.append(variant)
    return " ".join(tokens)


def _retarget_rename(name: str, source_state: str, target_state: str, base_state: str) -> str:
    parsed = utils.AnimationName(name)
    if parsed.valid and not parsed.custom and parsed.type == utils.AnimationStateType.ACTION:
        rename_state = _retarget_overlay_state(parsed.state, base_state) or target_state
        return _replace_action_state(name, rename_state)
    normalized = _normalized_name(name)
    return normalized.replace(source_state, target_state, 1) if source_state in normalized else name


def _copy_property_group(source, target, skip=frozenset()):
    for prop in source.bl_rna.properties:
        identifier = prop.identifier
        if identifier == "rna_type" or identifier in skip:
            continue
        try:
            if prop.type == 'COLLECTION':
                target_collection = getattr(target, identifier)
                target_collection.clear()
                for source_item in getattr(source, identifier):
                    _copy_property_group(source_item, target_collection.add())
            elif not prop.is_readonly:
                setattr(target, identifier, getattr(source, identifier))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass


def _armature_track(animation, armature: bpy.types.Object):
    for track in animation.action_tracks:
        if track.object is None or track.object.type != 'ARMATURE' or track.action is None or track.is_shape_key_action:
            continue
        if track.object == armature:
            return track
    return None


def _slot_identifier(action: bpy.types.Action, ob: bpy.types.Object) -> str:
    slots = getattr(action, "slots", None)
    if not slots:
        return ""
    animation_data = getattr(ob, "animation_data", None)
    identifier = getattr(animation_data, "last_slot_identifier", "") if animation_data else ""
    if identifier and slots.get(identifier) is not None:
        return identifier
    active = getattr(slots, "active", None)
    return active.identifier if active is not None else slots[0].identifier


def _fcurve_map(action: bpy.types.Action, ob: bpy.types.Object) -> tuple[dict, str]:
    slot_identifier = _slot_identifier(action, ob)
    if not slot_identifier:
        return {}, ""
    fcurves = utils.get_fcurves(action, slot_identifier)
    if fcurves is None:
        return {}, slot_identifier
    return {(fcurve.data_path, fcurve.array_index): fcurve for fcurve in fcurves}, slot_identifier


def _curve_values(curves: dict, data_path: str, size: int, defaults, frame: int):
    values = list(defaults)
    found = False
    for index in range(size):
        fcurve = curves.get((data_path, index))
        if fcurve is not None:
            values[index] = fcurve.evaluate(frame)
            found = True
    return values, found


def _sample_basis_matrix(bone: bpy.types.PoseBone, curves: dict, frame: int) -> Matrix:
    location, _ = _curve_values(curves, bone.path_from_id("location"), 3, (0.0, 0.0, 0.0), frame)
    scale, _ = _curve_values(curves, bone.path_from_id("scale"), 3, (1.0, 1.0, 1.0), frame)
    quat, has_quat = _curve_values(
        curves, bone.path_from_id("rotation_quaternion"), 4, (1.0, 0.0, 0.0, 0.0), frame
    )
    euler, has_euler = _curve_values(
        curves, bone.path_from_id("rotation_euler"), 3, (0.0, 0.0, 0.0), frame
    )
    axis_angle, has_axis = _curve_values(
        curves, bone.path_from_id("rotation_axis_angle"), 4, (0.0, 0.0, 1.0, 0.0), frame
    )

    if bone.rotation_mode == 'QUATERNION' and has_quat:
        rotation = Quaternion(quat)
    elif bone.rotation_mode == 'AXIS_ANGLE' and has_axis:
        axis = Vector(axis_angle[1:])
        rotation = Quaternion(axis if axis.length_squared else Vector((0.0, 1.0, 0.0)), axis_angle[0])
    elif bone.rotation_mode not in {'QUATERNION', 'AXIS_ANGLE'} and has_euler:
        rotation = Euler(euler, bone.rotation_mode).to_quaternion()
    elif has_quat:
        rotation = Quaternion(quat)
    elif has_euler:
        mode = bone.rotation_mode if bone.rotation_mode not in {'QUATERNION', 'AXIS_ANGLE'} else 'XYZ'
        rotation = Euler(euler, mode).to_quaternion()
    elif has_axis:
        axis = Vector(axis_angle[1:])
        rotation = Quaternion(axis if axis.length_squared else Vector((0.0, 1.0, 0.0)), axis_angle[0])
    else:
        rotation = Quaternion()
    rotation = rotation.normalized() if rotation.magnitude else Quaternion()
    return Matrix.LocRotScale(Vector(location), rotation, Vector(scale))


def _rest_local_matrix(bone: bpy.types.PoseBone) -> Matrix:
    if bone.parent is None:
        return bone.bone.matrix_local.copy()
    return bone.parent.bone.matrix_local.inverted_safe() @ bone.bone.matrix_local


def _sample_local_matrices(armature: bpy.types.Object, curves: dict, frame: int, rest_matrices: dict) -> dict:
    return {
        bone.name: rest_matrices[bone.name] @ _sample_basis_matrix(bone, curves, frame)
        for bone in armature.pose.bones
    }


def _evaluated_action_poses(
    action: bpy.types.Action,
    armature: bpy.types.Object,
    frames,
) -> dict[int, dict[str, Matrix]]:
    frames = tuple(frames)
    if not frames:
        return {}

    scene = bpy.context.scene
    had_animation_data = armature.animation_data is not None
    animation_data = armature.animation_data_create()
    previous_action = animation_data.action
    previous_slot_identifier = getattr(
        getattr(animation_data, "action_slot", None), "identifier", ""
    )
    previous_use_nla = animation_data.use_nla
    previous_influence = animation_data.action_influence
    previous_frame = scene.frame_current
    previous_subframe = scene.frame_subframe
    poses = {}

    try:
        animation_data.use_nla = False
        animation_data.action_influence = 1.0
        animation_data.action = action
        slots = getattr(action, "slots", None)
        if slots:
            slot_identifier = _slot_identifier(action, armature)
            slot = slots.get(slot_identifier) or slots[0]
            animation_data.action_slot = slot

        for frame in frames:
            scene.frame_set(frame)
            evaluated_armature = armature.evaluated_get(
                bpy.context.evaluated_depsgraph_get()
            )
            frame_pose = {}
            for bone in evaluated_armature.pose.bones:
                frame_pose[bone.name] = (
                    bone.parent.matrix.inverted_safe() @ bone.matrix
                    if bone.parent is not None
                    else bone.matrix.copy()
                )
            poses[frame] = frame_pose
    finally:
        animation_data.action = previous_action
        if previous_action is not None and previous_slot_identifier:
            previous_slots = getattr(previous_action, "slots", None)
            if previous_slots:
                previous_slot = previous_slots.get(previous_slot_identifier)
                if previous_slot is not None:
                    animation_data.action_slot = previous_slot
        animation_data.use_nla = previous_use_nla
        animation_data.action_influence = previous_influence
        scene.frame_set(previous_frame, subframe=previous_subframe)
        if not had_animation_data:
            armature.animation_data_clear()

    return poses


def _component_divide(value: Vector, divisor: Vector) -> Vector:
    return Vector(
        value[index] / divisor[index] if abs(divisor[index]) > 1e-8 else 1.0
        for index in range(3)
    )


def _compose_overlay_transform(source_reference: Matrix, source_pose: Matrix, target_reference: Matrix) -> Matrix:
    reference_location, reference_rotation, reference_scale = source_reference.decompose()
    source_location, source_rotation, source_scale = source_pose.decompose()
    target_location, target_rotation, target_scale = target_reference.decompose()
    reference_rotation.normalize()
    source_rotation.normalize()
    target_rotation.normalize()
    rotation = target_rotation @ (reference_rotation.inverted() @ source_rotation)
    rotation.normalize()
    scale_delta = _component_divide(source_scale, reference_scale)
    return Matrix.LocRotScale(
        target_location + source_location - reference_location,
        rotation,
        Vector(target_scale[index] * scale_delta[index] for index in range(3)),
    )


def _world_matrices(armature: bpy.types.Object, local_matrices: dict) -> dict:
    result = {}

    def resolve(bone: bpy.types.PoseBone):
        matrix = result.get(bone.name)
        if matrix is not None:
            return matrix
        local = local_matrices[bone.name]
        matrix = resolve(bone.parent) @ local if bone.parent is not None else local.copy()
        result[bone.name] = matrix
        return matrix

    for bone in armature.pose.bones:
        resolve(bone)
    return result


def _bone_depth(bone: bpy.types.PoseBone) -> int:
    depth = 0
    while bone.parent is not None:
        depth += 1
        bone = bone.parent
    return depth


def _apply_turn_aim_delta(
    armature: bpy.types.Object,
    source_reference: dict,
    source_pose: dict,
    target_reference: dict,
    target_pose: dict,
    pedestal_name: str,
    aim_bone_names: set[str],
) -> None:
    source_reference_world = _world_matrices(armature, source_reference)
    source_pose_world = _world_matrices(armature, source_pose)
    target_reference_world = _world_matrices(armature, target_reference)
    target_world = _world_matrices(armature, target_pose)

    _location, source_reference_pedestal, _scale = source_reference_world[
        pedestal_name
    ].decompose()
    _location, source_pose_pedestal, _scale = source_pose_world[
        pedestal_name
    ].decompose()
    _location, target_reference_pedestal, _scale = target_reference_world[
        pedestal_name
    ].decompose()
    _location, target_pedestal, _scale = target_world[pedestal_name].decompose()
    for rotation in (
        source_reference_pedestal,
        source_pose_pedestal,
        target_reference_pedestal,
        target_pedestal,
    ):
        rotation.normalize()

    aim_bones = [armature.pose.bones.get(name) for name in aim_bone_names]
    aim_bones = sorted(
        (bone for bone in aim_bones if bone is not None),
        key=_bone_depth,
    )
    for bone in aim_bones:
        _location, source_reference_rotation, _scale = source_reference_world[
            bone.name
        ].decompose()
        _location, source_pose_rotation, _scale = source_pose_world[
            bone.name
        ].decompose()
        _location, target_reference_rotation, _scale = target_reference_world[
            bone.name
        ].decompose()
        for rotation in (
            source_reference_rotation,
            source_pose_rotation,
            target_reference_rotation,
        ):
            rotation.normalize()

        source_reference_relative = (
            source_reference_pedestal.inverted()
            @ source_reference_rotation
        )
        source_pose_relative = (
            source_pose_pedestal.inverted() @ source_pose_rotation
        )
        source_delta = (
            source_reference_relative.inverted() @ source_pose_relative
        )
        target_reference_relative = (
            target_reference_pedestal.inverted()
            @ target_reference_rotation
        )
        desired_world_rotation = target_pedestal @ (
            target_reference_relative @ source_delta
        )
        if bone.parent is None:
            desired_local_rotation = desired_world_rotation
        else:
            _location, parent_rotation, _scale = target_world[
                bone.parent.name
            ].decompose()
            parent_rotation.normalize()
            desired_local_rotation = (
                parent_rotation.inverted() @ desired_world_rotation
            )
        desired_local_rotation.normalize()
        location, _rotation, scale = target_pose[bone.name].decompose()
        target_pose[bone.name] = Matrix.LocRotScale(
            location,
            desired_local_rotation,
            scale,
        )
        target_world = _world_matrices(armature, target_pose)



def _offset_turn_aim_yaw(
    armature: bpy.types.Object,
    target_reference: dict,
    pedestal_name: str,
    aim_bone_names: set[str],
    yaw_degrees: float,
) -> None:
    pedestal = armature.pose.bones.get(pedestal_name)
    if pedestal is None:
        raise RuntimeError("Turn overlays require a valid pedestal bone")

    reference_world = _world_matrices(armature, target_reference)
    target_world = dict(reference_world)
    _location, pedestal_rotation, _scale = reference_world[pedestal_name].decompose()
    pedestal_rotation.normalize()
    yaw_delta = Quaternion((0.0, 0.0, 1.0), radians(yaw_degrees))

    aim_bones = [armature.pose.bones.get(name) for name in aim_bone_names]
    aim_bones = sorted(
        (bone for bone in aim_bones if bone is not None),
        key=_bone_depth,
    )
    for bone in aim_bones:
        _location, reference_rotation, _scale = reference_world[bone.name].decompose()
        reference_rotation.normalize()
        relative_rotation = pedestal_rotation.inverted() @ reference_rotation
        desired_world_rotation = pedestal_rotation @ (yaw_delta @ relative_rotation)
        if bone.parent is None:
            desired_local_rotation = desired_world_rotation
        else:
            _location, parent_rotation, _scale = target_world[
                bone.parent.name
            ].decompose()
            parent_rotation.normalize()
            desired_local_rotation = parent_rotation.inverted() @ desired_world_rotation
        desired_local_rotation.normalize()
        location, _rotation, scale = target_reference[bone.name].decompose()
        target_reference[bone.name] = Matrix.LocRotScale(
            location,
            desired_local_rotation,
            scale,
        )
        target_world = _world_matrices(armature, target_reference)


def _pose_bone_from_usage(armature: bpy.types.Object, usage_name: str, fallback_names=()):
    if usage_name:
        bone = utils.get_pose_bone(armature, usage_name)
        if bone is not None:
            return bone
    fallback_names = {name.lower() for name in fallback_names}
    for bone in armature.pose.bones:
        if utils.remove_node_prefix(bone.name).lower() in fallback_names:
            return bone
    return None


def _descendant_names(bone: bpy.types.PoseBone) -> set[str]:
    names = {bone.name}
    for child in bone.children:
        names.update(_descendant_names(child))
    return names


def _lower_body_bone_names(armature: bpy.types.Object, scene_nwo, pedestal) -> set[str]:
    pelvis = _pose_bone_from_usage(armature, scene_nwo.node_usage_pelvis, ("pelvis", "hips"))
    left_foot = _pose_bone_from_usage(
        armature, scene_nwo.node_usage_left_foot, ("l_foot", "left_foot", "foot_l")
    )
    right_foot = _pose_bone_from_usage(
        armature, scene_nwo.node_usage_right_foot, ("r_foot", "right_foot", "foot_r")
    )
    lower = set()

    bone = pedestal
    while bone is not None:
        lower.add(bone.name)
        bone = bone.parent

    if pelvis is not None:
        lower.add(pelvis.name)
        bone = pelvis.parent
        while bone is not None:
            lower.add(bone.name)
            bone = bone.parent

        branch_roots = set()
        for foot in (left_foot, right_foot):
            bone = foot
            while bone is not None and bone.parent is not pelvis:
                bone = bone.parent
            if bone is not None and bone.parent is pelvis:
                branch_roots.add(bone)

        if not branch_roots:
            for child in pelvis.children:
                branch_names = " ".join(
                    utils.remove_node_prefix(bone.name).lower()
                    for bone in (child, *child.children_recursive)
                )
                if any(token in branch_names for token in _LOWER_BODY_NAME_TOKENS):
                    branch_roots.add(child)

        for branch_root in branch_roots:
            lower.update(_descendant_names(branch_root))

    if pelvis is None or not (left_foot or right_foot):
        for bone in armature.pose.bones:
            name = utils.remove_node_prefix(bone.name).lower()
            if any(token in name for token in _LOWER_BODY_NAME_TOKENS):
                lower.update(_descendant_names(bone))
    return lower


def _aim_bone_names(armature: bpy.types.Object, scene_nwo) -> set[str]:
    pitch = _pose_bone_from_usage(
        armature, scene_nwo.node_usage_pose_blend_pitch, ("aim_pitch",)
    )
    yaw = _pose_bone_from_usage(
        armature, scene_nwo.node_usage_pose_blend_yaw, ("aim_yaw",)
    )
    control = _pose_bone_from_usage(
        armature, armature.nwo.control_aim, ("aim_control",)
    )
    return {bone.name for bone in (pitch, yaw, control) if bone is not None}


def _has_bone_transform(curves: dict, bone: bpy.types.PoseBone) -> bool:
    sizes = {
        "location": 3,
        "rotation_quaternion": 4,
        "rotation_euler": 3,
        "rotation_axis_angle": 4,
        "scale": 3,
    }
    return any(
        (bone.path_from_id(prop), index) in curves
        for prop, size in sizes.items()
        for index in range(size)
    )


def _scope_token_score(source: str, candidate: str) -> int:
    if candidate == source:
        return 3
    if candidate == "any":
        return 2
    return -1


def _base_candidate_score(source_name: utils.AnimationName, candidate_name: utils.AnimationName, index: int):
    if candidate_name.mode == source_name.mode:
        mode_score = 2
    elif candidate_name.mode == "any":
        mode_score = 1
    else:
        return None
    scope_scores = tuple(
        _scope_token_score(getattr(source_name, prop), getattr(candidate_name, prop))
        for prop in ("weapon_class", "weapon_type", "set")
    )
    if -1 in scope_scores:
        return None
    return (mode_score, *scope_scores, int(not candidate_name.variant), -index)


def _target_base_animations(animations, armature: bpy.types.Object, source_name: utils.AnimationName):
    candidates = {state: [] for state in _VALID_BASE_STATES}
    for index, animation in enumerate(animations):
        if animation.animation_type != 'base':
            continue
        name = utils.AnimationName(animation.name)
        if not name.valid or name.custom or name.type != utils.AnimationStateType.ACTION:
            continue
        if name.state not in candidates or not _is_eligible_animation_mode(name.mode):
            continue
        if _armature_track(animation, armature) is None:
            continue
        score = _base_candidate_score(source_name, name, index)
        if score is not None:
            candidates[name.state].append((score, animation))

    result = []
    for state in _VALID_BASE_STATES:
        if candidates[state]:
            result.append((state, max(candidates[state], key=lambda item: item[0])[1]))
    return result


def _write_generated_transforms(
    action: bpy.types.Action,
    armature: bpy.types.Object,
    slot_identifier: str,
    frames: dict[int, dict[str, Matrix]],
    animated_bone_names: set[str],
    rest_matrices: dict,
    *,
    preserve_other_transforms=False,
) -> None:
    fcurves = utils.get_fcurves(action, slot_identifier)
    if fcurves is None:
        raise RuntimeError(f"Action [{action.name}] has no usable action slot")

    transform_paths = {
        bone.path_from_id(prop)
        for bone in armature.pose.bones
        if not preserve_other_transforms or bone.name in animated_bone_names
        for prop in _BONE_TRANSFORM_PROPERTIES
    }
    for fcurve in list(fcurves):
        if (fcurve.data_path in transform_paths
                or (not preserve_other_transforms and fcurve.data_path in _BONE_TRANSFORM_PROPERTIES)):
            fcurves.remove(fcurve)

    previous_rotations = {}
    previous_eulers = {}
    for bone_name in sorted(animated_bone_names):
        bone = armature.pose.bones.get(bone_name)
        if bone is None:
            continue
        location_curves = [
            fcurves.new(data_path=bone.path_from_id("location"), index=index, group_name=bone.name)
            for index in range(3)
        ]
        scale_curves = [
            fcurves.new(data_path=bone.path_from_id("scale"), index=index, group_name=bone.name)
            for index in range(3)
        ]
        if bone.rotation_mode == 'QUATERNION':
            path = bone.path_from_id("rotation_quaternion")
            rotation_curves = [
                fcurves.new(data_path=path, index=index, group_name=bone.name)
                for index in range(4)
            ]
        elif bone.rotation_mode == 'AXIS_ANGLE':
            path = bone.path_from_id("rotation_axis_angle")
            rotation_curves = [
                fcurves.new(data_path=path, index=index, group_name=bone.name)
                for index in range(4)
            ]
        else:
            path = bone.path_from_id("rotation_euler")
            rotation_curves = [
                fcurves.new(data_path=path, index=index, group_name=bone.name)
                for index in range(3)
            ]

        rest_inverse = rest_matrices[bone.name].inverted_safe()
        for frame, local_matrices in frames.items():
            location, rotation, scale = (rest_inverse @ local_matrices[bone.name]).decompose()
            rotation.normalize()
            if bone.rotation_mode == 'QUATERNION':
                previous = previous_rotations.get(bone.name)
                if previous is not None and previous.dot(rotation) < 0.0:
                    rotation.negate()
                previous_rotations[bone.name] = rotation.copy()
                rotation_values = tuple(rotation)
            elif bone.rotation_mode == 'AXIS_ANGLE':
                axis, angle = rotation.to_axis_angle()
                rotation_values = (angle, axis.x, axis.y, axis.z)
            else:
                euler = rotation.to_euler(bone.rotation_mode, previous_eulers.get(bone.name))
                previous_eulers[bone.name] = euler.copy()
                rotation_values = tuple(euler)

            for index, value in enumerate(location):
                location_curves[index].keyframe_points.insert(frame, value, options={'FAST'})
            for index, value in enumerate(rotation_values):
                rotation_curves[index].keyframe_points.insert(frame, value, options={'FAST'})
            for index, value in enumerate(scale):
                scale_curves[index].keyframe_points.insert(frame, value, options={'FAST'})

        for fcurve in (*location_curves, *rotation_curves, *scale_curves):
            for point in fcurve.keyframe_points:
                point.interpolation = 'LINEAR'
            fcurve.update()


def _generated_action(
    source_animation,
    source_track,
    target_base_animation,
    target_base_track,
    target_name: str,
    armature: bpy.types.Object,
    lower_body_names: set[str],
    aim_bone_names: set[str],
    pedestal_name: str,
    *,
    apply_turn_aim_offset=True,
) -> bpy.types.Action:
    source_curves, source_slot_identifier = _fcurve_map(source_track.action, armature)
    target_curves, _target_slot_identifier = _fcurve_map(target_base_track.action, armature)
    if not source_curves:
        raise RuntimeError(f"Source action [{source_track.action.name}] has no transform data")
    if not target_curves:
        raise RuntimeError(f"Base action [{target_base_track.action.name}] has no transform data")

    rest_matrices = {bone.name: _rest_local_matrix(bone) for bone in armature.pose.bones}
    source_frames = range(source_animation.frame_start, source_animation.frame_end + 1)
    source_poses = _evaluated_action_poses(
        source_track.action,
        armature,
        source_frames,
    )
    source_reference = source_poses[source_animation.frame_start]
    base_state = utils.AnimationName(target_base_animation.name).state
    turn_yaw_offset = _TURN_AIM_YAW_OFFSETS.get(base_state)
    is_turn = turn_yaw_offset is not None
    target_reference = _sample_local_matrices(
        armature, target_curves, target_base_animation.frame_start, rest_matrices
    )
    if is_turn and apply_turn_aim_offset:
        _offset_turn_aim_yaw(
            armature,
            target_reference,
            pedestal_name,
            aim_bone_names,
            turn_yaw_offset,
        )
    animated_bone_names = {
        bone.name
        for bone in armature.pose.bones
        if _has_bone_transform(source_curves, bone) or _has_bone_transform(target_curves, bone)
    }
    animated_bone_names.update(aim_bone_names)

    generated_reference = target_reference

    output_frames = {}
    for frame in range(source_animation.frame_start, source_animation.frame_end + 1):
        source_pose = source_poses[frame]
        if frame == source_animation.frame_start:
            target_pose = {
                bone.name: generated_reference[bone.name].copy()
                for bone in armature.pose.bones
            }
        else:
            target_pose = {}
            for bone in armature.pose.bones:
                if bone.name in lower_body_names and bone.name not in aim_bone_names:
                    target_pose[bone.name] = generated_reference[bone.name].copy()
                else:
                    target_pose[bone.name] = _compose_overlay_transform(
                        source_reference[bone.name],
                        source_pose[bone.name],
                        generated_reference[bone.name],
                    )

        if is_turn and frame != source_animation.frame_start:
            # Aim changes are relative to the turn's offset aim-bone reference.
            _apply_turn_aim_delta(
                armature,
                source_reference,
                source_pose,
                generated_reference,
                target_pose,
                pedestal_name,
                aim_bone_names,
            )
        output_frames[frame] = target_pose

    action = source_track.action.copy()
    action.name = target_name
    action.use_frame_range = True
    action.frame_start = source_animation.frame_start
    action.frame_end = source_animation.frame_end
    try:
        _write_generated_transforms(
            action,
            armature,
            source_slot_identifier,
            output_frames,
            animated_bone_names,
            rest_matrices,
        )
    except Exception:
        bpy.data.actions.remove(action)
        raise
    return action


def _rebuild_wrap_events(
    animation,
    action: bpy.types.Action,
    armature: bpy.types.Object,
    pedestal_name: str,
    yaw_name: str | None,
) -> int:
    """Replace copied wrap events using the generated pose-screen transforms."""
    for index in range(len(animation.animation_events) - 1, -1, -1):
        event = animation.animation_events[index]
        if (
            event.event_type == _WRAP_EVENT_TYPE
            and event.import_name in _WRAP_EVENT_NAMES
        ):
            animation.animation_events.remove(index)

    if not yaw_name:
        return 0

    pedestal = armature.pose.bones.get(pedestal_name)
    yaw = armature.pose.bones.get(yaw_name)
    if pedestal is None or yaw is None:
        return 0

    poses = _evaluated_action_poses(
        action,
        armature,
        range(animation.frame_start, animation.frame_end + 1),
    )
    event_ids = {event.event_id for event in animation.animation_events}
    reset = True
    current_name = ""
    added = 0

    for frame in range(animation.frame_start + 1, animation.frame_end + 1):
        local_matrices = poses[frame]
        world_matrices = _world_matrices(armature, local_matrices)
        relative = (
            world_matrices[pedestal.name].inverted_safe()
            @ world_matrices[yaw.name]
        )
        raw_yaw = degrees(relative.to_euler('XYZ').z)

        if abs(raw_yaw) <= 90.0 + 1e-3:
            reset = True
            continue

        if reset:
            current_name = "Wrapped Left" if raw_yaw > 0.0 else "Wrapped Right"
            reset = False

        event_id = random.randint(0, 2147483647)
        while event_id in event_ids:
            event_id = random.randint(0, 2147483647)
        event_ids.add(event_id)

        event = animation.animation_events.add()
        event.event_type = _WRAP_EVENT_TYPE
        event.event_id = event_id
        event.frame_frame = frame
        event.import_name = current_name
        added += 1

    animation.active_animation_event_index = min(
        animation.active_animation_event_index, len(animation.animation_events) - 1
    ) if animation.animation_events else 0
    return added


def _populate_target_animation(
    target,
    source,
    source_track,
    generated_action,
    target_name: str,
    target_state: str,
    base_state: str,
    armature: bpy.types.Object,
) -> None:
    _copy_property_group(
        source,
        target,
        # A pose overlay has no composite axis to activate via its UI callback.
        skip={"name", "name_old", "action_tracks", "animation_renames", "blend_axis_active_index"},
    )
    target.action_tracks.clear()
    target.animation_renames.clear()

    copied_actions = {}
    for source_action_track in source.action_tracks:
        target_track = target.action_tracks.add()
        _copy_property_group(source_action_track, target_track, skip={"action"})
        if source_action_track == source_track:
            target_track.object = armature
            target_track.action = generated_action
        elif source_action_track.action is not None:
            copied_action = copied_actions.get(source_action_track.action)
            if copied_action is None:
                copied_action = source_action_track.action.copy()
                copied_action.name = target_name
                copied_actions[source_action_track.action] = copied_action
            target_track.action = copied_action


    source_state = utils.AnimationName(source.name).state
    for source_rename in source.animation_renames:
        target_rename = target.animation_renames.add()
        _copy_property_group(source_rename, target_rename)
        target_rename.name = _retarget_rename(
            source_rename.name, source_state, target_state, base_state
        )

    target.name = target_name
    target.name_old = target_name
    target.state = target_state
    target.state_type = 'action'
    target.animation_type = 'overlay'
    target.external = False
    target.gr2_path = ""
    target.blend_path = ""
    target.active_action_group_index = min(
        source.active_action_group_index, len(target.action_tracks) - 1
    ) if target.action_tracks else 0
    target.active_animation_event_index = min(
        source.active_animation_event_index, len(target.animation_events) - 1
    ) if target.animation_events else 0
    target.active_animation_node_index = min(
        source.active_animation_node_index, len(target.animation_nodes) - 1
    ) if target.animation_nodes else 0
    target.active_animation_rename_index = min(
        source.active_animation_rename_index, len(target.animation_renames) - 1
    ) if target.animation_renames else 0


def generate_aim_look_overlays(scene_nwo, source, armature, target_bases, *, override_existing=False,
                              turns_with_aim_pose=()):
    """Share overlay generation between the operator and Reach-style tag import.

    The caller supplies a validated aim/look source and matching base states.
    Return generated animation names, the skipped count, and failed names.
    """
    source_name = utils.AnimationName(source.name)
    source_track = _armature_track(source, armature)
    if source_track is None:
        raise ValueError("The source overlay has no armature action track")
    pedestal = _pose_bone_from_usage(
        armature, scene_nwo.node_usage_pedestal, ("pedestal",)
    )
    aim_yaw = _pose_bone_from_usage(
        armature, scene_nwo.node_usage_pose_blend_yaw, ("aim_yaw",)
    )
    aim_bone_names = _aim_bone_names(armature, scene_nwo)
    if pedestal is None:
        raise ValueError("The armature has no valid pedestal bone usage")
    if not aim_bone_names:
        raise ValueError("The armature has no valid aim pitch, aim yaw, or aim control bone")

    lower_body_names = _lower_body_bone_names(armature, scene_nwo, pedestal)
    lower_body_names.difference_update(aim_bone_names)
    # Adding a CollectionProperty item can invalidate existing RNA references.
    # Keep indices across additions and reacquire entries before using them.
    indices = {animation.as_pointer(): index for index, animation in enumerate(scene_nwo.animations)}
    source_index = indices[source.as_pointer()]
    target_bases = [(state, indices[animation.as_pointer()]) for state, animation in target_bases]
    existing_by_name = {
        _normalized_name(animation.name): index
        for index, animation in enumerate(scene_nwo.animations)
    }
    generated = []
    skipped_count = 0
    failed = []

    for base_state, base_index in target_bases:
        source = scene_nwo.animations[source_index]
        source_track = _armature_track(source, armature)
        base_animation = scene_nwo.animations[base_index]
        target_state = _retarget_overlay_state(source_name.state, base_state)
        target_name = _replace_action_state(source.name, target_state)
        normalized_target_name = _normalized_name(target_name)
        existing = existing_by_name.get(normalized_target_name)
        if existing is not None and not override_existing:
            skipped_count += 1
            continue

        base_track = _armature_track(base_animation, armature)
        if base_track is None:
            failed.append(target_name)
            continue
        try:
            action = _generated_action(
                source,
                source_track,
                base_animation,
                base_track,
                target_name,
                armature,
                lower_body_names,
                aim_bone_names,
                pedestal.name,
                apply_turn_aim_offset=base_animation.name not in turns_with_aim_pose,
            )
            if existing is None:
                target = scene_nwo.animations.add()
                target_index = len(scene_nwo.animations) - 1
                source = scene_nwo.animations[source_index]
                source_track = _armature_track(source, armature)
            else:
                target_index = existing
                target = scene_nwo.animations[target_index]
            _populate_target_animation(
                target,
                source,
                source_track,
                action,
                target_name,
                target_state,
                base_state,
                armature,
            )
            _rebuild_wrap_events(
                target,
                action,
                armature,
                pedestal.name,
                aim_yaw.name if aim_yaw is not None else None,
            )
            existing_by_name[normalized_target_name] = target_index
            generated.append(target_name)
        except Exception as error:
            utils.print_warning(f"Failed to generate [{target_name}]: {error}")
            failed.append(target_name)

    return generated, skipped_count, failed


class NWO_OT_GenerateAimLookOverlays(bpy.types.Operator):
    bl_idname = "nwo.generate_aim_look_overlays"
    bl_label = "Generate Aim / Look Overlays"
    bl_description = (
        "Generate movement pose overlays from the active aim_still or look_still pose overlay"
    )
    bl_options = {'REGISTER', 'UNDO'}

    override_existing: bpy.props.BoolProperty(
        name="Override Existing",
        description=(
            "Replace generated animation entries when an animation with the target name "
            "already exists"
        ),
        default=False,
    )

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return bool(scene_nwo.animations and scene_nwo.active_animation_index > -1)

    def draw(self, context):
        layout = self.layout
        scene_nwo = utils.get_scene_props()
        if scene_nwo.animations and scene_nwo.active_animation_index > -1:
            layout.label(
                text=f"Source: {scene_nwo.animations[scene_nwo.active_animation_index].name}"
            )
        layout.label(text="Generate walk, move, airborne, and turn overlays")
        layout.prop(self, "override_existing")

    def invoke(self, context, _event):
        return context.window_manager.invoke_props_dialog(self, width=440)

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        if not scene_nwo.animations or scene_nwo.active_animation_index < 0:
            self.report({'WARNING'}, "No active animation")
            return {'CANCELLED'}

        source = scene_nwo.animations[scene_nwo.active_animation_index]
        source_name = utils.AnimationName(source.name)
        if not source_name.valid or source_name.custom or source_name.type != utils.AnimationStateType.ACTION:
            self.report({'WARNING'}, "The active animation does not have a valid action animation name")
            return {'CANCELLED'}
        if source.animation_type != 'overlay' or not source.pose_overlay:
            self.report({'WARNING'}, "The active animation must be a pose overlay")
            return {'CANCELLED'}
        if _retarget_overlay_state(source_name.state, "move_front") is None:
            self.report(
                {'WARNING'},
                "The active animation state must be aim_still, look_still, or an up/down variant",
            )
            return {'CANCELLED'}
        if not _is_eligible_animation_mode(source_name.mode):
            self.report(
                {'WARNING'},
                f"Animation mode [{source_name.mode}] is not an eligible biped movement mode",
            )
            return {'CANCELLED'}

        armature = utils.get_rig_prioritize_active(context)
        source_track = _armature_track(source, armature) if armature is not None else None
        if source_track is None:
            for track in source.action_tracks:
                if (
                    track.object is not None
                    and track.object.type == 'ARMATURE'
                    and track.action is not None
                    and not track.is_shape_key_action
                ):
                    armature = track.object
                    source_track = track
                    break
        if armature is None or source_track is None:
            self.report({'WARNING'}, "The active overlay has no armature action track")
            return {'CANCELLED'}
        if source.frame_end <= source.frame_start:
            self.report(
                {'WARNING'},
                "The active overlay must contain a base frame and at least one pose frame",
            )
            return {'CANCELLED'}


        target_bases = _target_base_animations(scene_nwo.animations, armature, source_name)
        if not target_bases:
            self.report(
                {'WARNING'},
                "No eligible walk, move, airborne, or turn base animations were found",
            )
            return {'CANCELLED'}

        try:
            generated, skipped_count, failed = generate_aim_look_overlays(
                scene_nwo, source, armature, target_bases,
                override_existing=self.override_existing,
            )
        except ValueError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        generated_count = len(generated)

        if generated_count == 0 and failed:
            self.report(
                {'WARNING'},
                f"Failed to generate {len(failed)} overlay animation(s); "
                "see Foundry Output for details",
            )
            return {'CANCELLED'}

        message = f"Generated {generated_count} aim/look overlay animation(s)"
        if skipped_count:
            message += f"; skipped {skipped_count} existing"
        if failed:
            message += f"; failed {len(failed)}"
        self.report({'INFO'} if generated_count else {'WARNING'}, message)
        return {'FINISHED'}

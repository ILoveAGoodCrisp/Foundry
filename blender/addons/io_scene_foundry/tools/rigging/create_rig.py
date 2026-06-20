import re

import bpy

from ... import utils
from ...tools.rigging import (
    HaloRig,
    aim_control_name,
    eye_track_constraint_name,
    fk_collection_name,
    foundry_armature_constraint_name,
    gun_copy_transforms_constraint_name,
    choose_eye_bone_names,
    find_deform_pose_bone_name_by_suffix,
    find_deform_pose_bone_names_by_suffix,
    get_head_driver_bone_name,
    head_control_name,
    head_track_constraint_name,
    ik_blend_property_name,
    ik_collection_name,
    ik_child_of_constraint_name,
    ik_constraint_name,
    ik_copy_location_constraint_name,
    ik_copy_rotation_constraint_name,
    is_control_bone_name,
    is_finger_ik_chain_source_name,
    is_finger_ik_source_name,
    look_control_name,
    look_child_of_constraint_name,
    misc_control_collection_name,
    neck_assist_constraint_name,
    needs_reach_fp_ik_fix,
    remove_empty_bone_collection,
    root_child_of_constraint_name,
    settings_control_collection_name,
    settings_control_name,
)
from bpy_extras import anim_utils
from math import ceil, floor
from mathutils import Matrix, Vector


def scene_control_scale():
    return 0.03048 if utils.get_scene_props().scale == 'blender' else 1.0


def armature_needs_reach_fp_ik_fix(arm: bpy.types.Object):
    return needs_reach_fp_ik_fix(arm.nwo.node_order_source)


def armature_has_fk_ik_control_rig(arm: bpy.types.Object):
    return any(bone.name.startswith(("FK_", "IK_", "PT_")) for bone in arm.data.bones)


def armature_has_control_rig(arm: bpy.types.Object):
    return armature_has_fk_ik_control_rig(arm) or bool(arm.nwo.control_aim and arm.pose.bones.get(arm.nwo.control_aim))


control_rig_constraint_names = (
    head_track_constraint_name,
    neck_assist_constraint_name,
    eye_track_constraint_name,
    root_child_of_constraint_name,
    look_child_of_constraint_name,
    foundry_armature_constraint_name,
    gun_copy_transforms_constraint_name,
    ik_constraint_name,
    ik_child_of_constraint_name,
    ik_copy_location_constraint_name,
    ik_copy_rotation_constraint_name,
)


def generated_control_bone_names(arm: bpy.types.Object) -> set[str]:
    return {bone.name for bone in arm.data.bones if is_control_bone_name(bone.name)}


def clear_control_rig_constraints(arm: bpy.types.Object, control_bone_names: set[str]):
    for pbone in arm.pose.bones:
        for con in reversed(pbone.constraints):
            con_name = con.name
            subtarget = getattr(con, "subtarget", "")
            target = getattr(con, "target", None)
            name_matches = any(con_name == name or con_name.startswith(f"{name}.") for name in control_rig_constraint_names)
            target_matches_removed_control = target == arm and subtarget in control_bone_names
            if con.type == 'ARMATURE':
                target_matches_removed_control = any(
                    target.target == arm and target.subtarget in control_bone_names
                    for target in con.targets
                )
            owner_is_removed_control = pbone.name in control_bone_names

            if name_matches or target_matches_removed_control or owner_is_removed_control:
                pbone.constraints.remove(con)


def control_bone_remove_order(arm: bpy.types.Object, control_bone_names: set[str]) -> list[str]:
    depths = {}
    for bone in arm.data.bones:
        if bone.name not in control_bone_names:
            continue

        depth = 0
        parent = bone.parent
        while parent is not None:
            depth += 1
            parent = parent.parent
        depths[bone.name] = depth

    return [name for name, _ in sorted(depths.items(), key=lambda item: item[1], reverse=True)]


def remove_control_bone_collections(armature_data: bpy.types.Armature):
    for name in (fk_collection_name, ik_collection_name, settings_control_collection_name, misc_control_collection_name):
        remove_empty_bone_collection(armature_data, name)


def set_control_rig_inverted(context, arm: bpy.types.Object, inverted: bool):
    any_pose_bones = any(b.name for b in arm.pose.bones if b.name.endswith(("_pitch", "_yaw")))
    rig = HaloRig(context, scale=scene_control_scale(), has_pose_bones=any_pose_bones)
    rig.rig_ob = arm
    rig.rig_data = arm.data
    rig.rig_pose = arm.pose

    aim_control_name = arm.nwo.control_aim
    aim_control = utils.get_pose_bone(arm, aim_control_name)

    if aim_control is not None:
        rig.build_and_apply_control_shapes(
            aim_control=aim_control,
            aim_control_only=True,
            reverse_control=inverted,
            constraints_only=True,
        )

    if armature_has_fk_ik_control_rig(arm):
        rig.build_fk_ik_rig(
            reverse_controls=inverted,
            constraints_only=True,
            reach_fp_ik_fix=armature_needs_reach_fp_ik_fix(arm),
        )


def bake_control_rig_actions(context, arm: bpy.types.Object, actions):
    actions = list(dict.fromkeys(action for action in actions if action is not None))
    if not actions or not armature_has_control_rig(arm):
        return 0

    if arm.animation_data is None:
        arm.animation_data_create()

    original_action = arm.animation_data.action
    original_slot_identifier = arm.animation_data.last_slot_identifier
    original_active = context.view_layer.objects.active
    selected_objects = [ob for ob in context.selected_objects]
    selected_pose_bones = {pb.name: pb.select for pb in arm.pose.bones}

    utils.set_object_mode(context)
    utils.deselect_all_objects()
    arm.select_set(True)
    utils.set_active_object(arm)

    control_bone_names = {pb.name for pb in arm.pose.bones if is_control_bone_name(pb.name)}
    for pb in arm.pose.bones:
        pb.select = pb.name in control_bone_names

    arm.select_set(False)
    options = anim_utils.BakeOptions(
        only_selected=True,
        do_pose=True,
        do_object=False,
        do_visual_keying=True,
        do_constraint_clear=False,
        do_parents_clear=False,
        do_clean=False,
        do_location=True,
        do_rotation=True,
        do_scale=True,
        do_bbone=False,
        do_custom_props=False,
    )
    baked_count = 0

    try:
        for action in actions:
            print(f"Baking action: {action.name}")

            start, end = utils.get_frame_start_end_from_keyframes(action, arm)
            if end - start < 1:
                continue

            if len(action.slots):
                slot = action.slots.get(arm.animation_data.last_slot_identifier) or action.slots[0]
                arm.animation_data.last_slot_identifier = slot.identifier
            arm.animation_data.action = action
            anim_utils.bake_action(arm, action=action, frames=range(start, end + 1), bake_options=options)
            baked_count += 1
    finally:
        arm.animation_data.action = original_action
        arm.animation_data.last_slot_identifier = original_slot_identifier
        for pb in arm.pose.bones:
            pb.select = selected_pose_bones.get(pb.name, False)
        utils.deselect_all_objects()
        for ob in selected_objects:
            if ob.name in bpy.data.objects:
                ob.select_set(True)
        if original_active is not None and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active

    return baked_count


def bake_imported_actions_to_control_rig(context, arm: bpy.types.Object, actions):
    if not actions or not armature_has_control_rig(arm):
        return 0

    baked_count = 0
    set_control_rig_inverted(context, arm, True)
    context.view_layer.update()
    try:
        baked_count = bake_control_rig_actions(context, arm, actions)
    finally:
        set_control_rig_inverted(context, arm, False)
        context.view_layer.update()

    if baked_count:
        correct_baked_control_target_actions(context, arm, actions)

    return baked_count


def remove_pose_bone_transform_fcurves(action: bpy.types.Action, arm: bpy.types.Object, bone_name: str):
    fcurves = utils.get_fcurves(action, arm)
    if not fcurves:
        return

    data_paths = set(pose_bone_transform_paths(bone_name))
    for fcurve in list(fcurves):
        if fcurve.data_path in data_paths:
            fcurves.remove(fcurve)


def set_pose_bone_transform_interpolation(action: bpy.types.Action, arm: bpy.types.Object, bone_name: str, interpolation: str):
    fcurves = utils.get_fcurves(action, arm)
    if not fcurves:
        return

    data_paths = set(pose_bone_transform_paths(bone_name))
    for fcurve in fcurves:
        if fcurve.data_path not in data_paths:
            continue

        for keyframe_point in fcurve.keyframe_points:
            keyframe_point.interpolation = interpolation
        fcurve.update()


def average_pose_bone_heads(pose_bones: list[bpy.types.PoseBone]) -> Vector:
    total = Vector((0.0, 0.0, 0.0))
    for pbone in pose_bones:
        total += pbone.head.copy()

    return total / max(len(pose_bones), 1)


def average_pose_bone_axis(pose_bones: list[bpy.types.PoseBone], axis_index: int) -> Vector:
    total = Vector((0.0, 0.0, 0.0))
    for pbone in pose_bones:
        axis = pbone.matrix.to_3x3().col[axis_index].copy()
        if axis.length > 1e-6:
            total += axis.normalized()

    if total.length < 1e-6:
        return Vector((0.0, -1.0, 0.0))

    return total.normalized()


def control_target_rest_distance(control_bone: bpy.types.PoseBone, source_bones: list[bpy.types.PoseBone]) -> float:
    if not source_bones:
        return max(control_bone.bone.length, 0.01)

    control_head = control_bone.bone.head_local.copy()
    source_head = Vector((0.0, 0.0, 0.0))
    for source in source_bones:
        source_head += source.bone.head_local.copy()
    source_head /= len(source_bones)

    return max((control_head - source_head).length, control_bone.bone.length, 0.01)


def control_target_pose_position(source_bones: list[bpy.types.PoseBone], axis_index: int, distance: float) -> Vector:
    return average_pose_bone_heads(source_bones) + average_pose_bone_axis(source_bones, axis_index) * distance


def head_look_target_bake_contexts(arm: bpy.types.Object) -> list[tuple[bpy.types.PoseBone, list[bpy.types.PoseBone], int, float]]:
    contexts = []

    head_control = arm.pose.bones.get(head_control_name)
    if head_control is not None:
        head_deform_name = find_deform_pose_bone_name_by_suffix(arm, "head")
        head_driver_name = get_head_driver_bone_name(arm, head_deform_name, {})
        head_driver = arm.pose.bones.get(head_driver_name) if head_driver_name else None
        if head_driver is not None:
            contexts.append((
                head_control,
                [head_driver],
                2,
                control_target_rest_distance(head_control, [head_driver]),
            ))

    look_control = arm.pose.bones.get(look_control_name)
    if look_control is not None:
        eye_names = choose_eye_bone_names(find_deform_pose_bone_names_by_suffix(arm, "eye"))
        eye_bones = [arm.pose.bones[name] for name in eye_names[:2] if arm.pose.bones.get(name) is not None]
        if eye_bones:
            contexts.append((
                look_control,
                eye_bones,
                0,
                control_target_rest_distance(look_control, eye_bones),
            ))

    return contexts


def mute_constraints_by_name(arm: bpy.types.Object, constraint_names: tuple[str, ...]) -> list[tuple[bpy.types.Constraint, bool]]:
    muted_constraints = []
    for pbone in arm.pose.bones:
        for con in pbone.constraints:
            if any(con.name == name or con.name.startswith(f"{name}.") for name in constraint_names):
                muted_constraints.append((con, con.mute))
                con.mute = True

    return muted_constraints


def correct_baked_control_target_actions(context, arm: bpy.types.Object, actions):
    return (
        correct_baked_ik_target_actions(context, arm, actions)
        + correct_baked_head_look_target_actions(context, arm, actions)
    )


def ik_target_bake_contexts(arm: bpy.types.Object) -> list[tuple[str, bpy.types.PoseBone, bpy.types.PoseBone, bpy.types.PoseBone, list[bpy.types.PoseBone]]]:
    contexts = []
    for fkb in arm.pose.bones:
        if not fkb.name.startswith("FK_"):
            continue

        ikb = arm.pose.bones.get(fkb.name.replace("FK_", "IK_", 1))
        ptb = arm.pose.bones.get(fkb.name.replace("FK_", "PT_", 1))
        if ikb is None or ptb is None:
            continue

        chain = fk_chain_for_end_bone(fkb)
        if len(chain) < 2:
            continue

        contexts.append((ik_blend_property_name(fkb.name), fkb, ikb, ptb, chain))

    return contexts


def remove_settings_prop_fcurve(action: bpy.types.Action, arm: bpy.types.Object, prop_name: str):
    fcurves = utils.get_fcurves(action, arm)
    if not fcurves:
        return

    data_path = settings_prop_data_path(prop_name)
    for fcurve in list(fcurves):
        if fcurve.data_path == data_path:
            fcurves.remove(fcurve)


def correct_baked_ik_target_actions(context, arm: bpy.types.Object, actions):
    settings_bone = arm.pose.bones.get(settings_control_name)
    contexts = ik_target_bake_contexts(arm)
    if settings_bone is None or not contexts:
        return 0

    if arm.animation_data is None:
        return 0

    original_action = arm.animation_data.action
    original_slot_identifier = arm.animation_data.last_slot_identifier
    original_frame = context.scene.frame_current
    original_mode = context.mode
    original_active = context.view_layer.objects.active
    selected_objects = [ob for ob in context.selected_objects]
    prop_names = [prop_name for prop_name, _fkb, _ikb, _ptb, _chain in contexts]
    corrected_count = 0

    utils.set_object_mode(context)
    utils.set_active_object(arm)

    try:
        for action in list(dict.fromkeys(action for action in actions if action is not None)):
            start, end = utils.get_frame_start_end_from_keyframes(action, arm)
            if end < start:
                continue

            if len(action.slots):
                slot = action.slots.get(arm.animation_data.last_slot_identifier) or action.slots[0]
                arm.animation_data.last_slot_identifier = slot.identifier
            arm.animation_data.action = action

            for prop_name, _fkb, ikb, ptb, _chain in contexts:
                remove_settings_prop_fcurve(action, arm, prop_name)
                remove_pose_bone_transform_fcurves(action, arm, ikb.name)
                remove_pose_bone_transform_fcurves(action, arm, ptb.name)

            frames = list(range(floor(start), ceil(end) + 1))
            for frame in frames:
                context.scene.frame_set(frame)
                for prop_name in prop_names:
                    settings_bone[prop_name] = 0.0
                context.view_layer.update()

                for _prop_name, fkb, ikb, ptb, chain in contexts:
                    ikb.matrix = fkb.matrix.copy()
                    pole_position = calculate_pose_pole_position(chain[0], chain[-2], fkb, ptb)
                    set_pose_bone_matrix_translation(ptb, pole_position)
                    keyframe_pose_bone_transform(ikb, frame)
                    keyframe_pose_bone_transform(ptb, frame)

            for prop_name, _fkb, ikb, ptb, _chain in contexts:
                set_pose_bone_transform_interpolation(action, arm, ikb.name, 'LINEAR')
                set_pose_bone_transform_interpolation(action, arm, ptb.name, 'LINEAR')
                settings_bone[prop_name] = 0.0

            corrected_count += 1
    finally:
        for prop_name in prop_names:
            settings_bone[prop_name] = 0.0
        arm.animation_data.action = original_action
        arm.animation_data.last_slot_identifier = original_slot_identifier
        context.scene.frame_set(original_frame)
        utils.deselect_all_objects()
        for ob in selected_objects:
            if ob.name in bpy.data.objects:
                ob.select_set(True)
        if original_active is not None and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active
        utils.restore_mode(original_mode)

    return corrected_count


def correct_baked_head_look_target_actions(context, arm: bpy.types.Object, actions):
    contexts = head_look_target_bake_contexts(arm)
    if not contexts:
        return 0

    if arm.animation_data is None:
        return 0

    original_action = arm.animation_data.action
    original_slot_identifier = arm.animation_data.last_slot_identifier
    original_frame = context.scene.frame_current
    original_mode = context.mode
    original_active = context.view_layer.objects.active
    selected_objects = [ob for ob in context.selected_objects]
    muted_constraints = []
    corrected_count = 0

    utils.set_object_mode(context)
    utils.set_active_object(arm)

    try:
        muted_constraints = mute_constraints_by_name(arm, (head_track_constraint_name, eye_track_constraint_name))
        for action in list(dict.fromkeys(action for action in actions if action is not None)):
            start, end = utils.get_frame_start_end_from_keyframes(action, arm)
            if end < start:
                continue

            if len(action.slots):
                slot = action.slots.get(arm.animation_data.last_slot_identifier) or action.slots[0]
                arm.animation_data.last_slot_identifier = slot.identifier
            arm.animation_data.action = action

            for control_bone, _source_bones, _axis_index, _distance in contexts:
                remove_pose_bone_transform_fcurves(action, arm, control_bone.name)

            for frame in range(floor(start), ceil(end) + 1):
                context.scene.frame_set(frame)
                context.view_layer.update()
                for control_bone, source_bones, axis_index, distance in contexts:
                    target_position = control_target_pose_position(source_bones, axis_index, distance)
                    matrix = control_bone.bone.matrix_local.copy()
                    matrix.translation = target_position
                    control_bone.matrix = matrix
                    keyframe_pose_bone_transform(control_bone, frame)

            for control_bone, _source_bones, _axis_index, _distance in contexts:
                set_pose_bone_transform_interpolation(action, arm, control_bone.name, 'LINEAR')

            corrected_count += 1
    finally:
        for con, muted in muted_constraints:
            con.mute = muted
        arm.animation_data.action = original_action
        arm.animation_data.last_slot_identifier = original_slot_identifier
        context.scene.frame_set(original_frame)
        utils.deselect_all_objects()
        for ob in selected_objects:
            if ob.name in bpy.data.objects:
                ob.select_set(True)
        if original_active is not None and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active
        utils.restore_mode(original_mode)

    return corrected_count


def pole_target_bake_contexts(arm: bpy.types.Object) -> list[tuple[bpy.types.PoseBone, bpy.types.PoseBone, list[bpy.types.PoseBone]]]:
    contexts = []
    for fkb in arm.pose.bones:
        if not fkb.name.startswith("FK_"):
            continue

        ptb = arm.pose.bones.get(fkb.name.replace("FK_", "PT_", 1))
        if ptb is None:
            continue

        chain = fk_chain_for_end_bone(fkb)
        if len(chain) < 2:
            continue

        contexts.append((fkb, ptb, chain))

    return contexts


def correct_baked_pole_target_actions(context, arm: bpy.types.Object, actions):
    contexts = pole_target_bake_contexts(arm)
    if not contexts:
        return 0

    if arm.animation_data is None:
        return 0

    original_action = arm.animation_data.action
    original_slot_identifier = arm.animation_data.last_slot_identifier
    original_frame = context.scene.frame_current
    original_mode = context.mode
    original_active = context.view_layer.objects.active
    selected_objects = [ob for ob in context.selected_objects]
    corrected_count = 0

    utils.set_object_mode(context)
    utils.set_active_object(arm)

    try:
        for action in list(dict.fromkeys(action for action in actions if action is not None)):
            start, end = utils.get_frame_start_end_from_keyframes(action, arm)
            if end < start:
                continue

            if len(action.slots):
                slot = action.slots.get(arm.animation_data.last_slot_identifier) or action.slots[0]
                arm.animation_data.last_slot_identifier = slot.identifier
            arm.animation_data.action = action

            for _fkb, ptb, _chain in contexts:
                remove_pose_bone_transform_fcurves(action, arm, ptb.name)

            for frame in range(floor(start), ceil(end) + 1):
                context.scene.frame_set(frame)
                context.view_layer.update()
                for fkb, ptb, chain in contexts:
                    pole_position = calculate_pose_pole_position(chain[0], chain[-2], fkb, ptb)
                    matrix = ptb.bone.matrix_local.copy()
                    matrix.translation = pole_position
                    ptb.matrix = matrix
                    keyframe_pose_bone_transform(ptb, frame)

            for _fkb, ptb, _chain in contexts:
                set_pose_bone_transform_interpolation(action, arm, ptb.name, 'LINEAR')

            corrected_count += 1
    finally:
        arm.animation_data.action = original_action
        arm.animation_data.last_slot_identifier = original_slot_identifier
        context.scene.frame_set(original_frame)
        utils.deselect_all_objects()
        for ob in selected_objects:
            if ob.name in bpy.data.objects:
                ob.select_set(True)
        if original_active is not None and original_active.name in bpy.data.objects:
            context.view_layer.objects.active = original_active
        utils.restore_mode(original_mode)

    return corrected_count


class NWO_OT_BakeToControl(bpy.types.Operator):
    bl_idname = "nwo.bake_to_control"
    bl_label = "Bake Deform to Control Bones"
    bl_description = "Bakes the position of control, FK, and IK bones"
    bl_options = {"UNDO"}
    
    all_actions: bpy.props.BoolProperty(
        name="All Actions",
        description="Bake all actions in the blend file to the control rig"
    )
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type =='ARMATURE' and context.object.animation_data
    
    def execute(self, context):
        arm = context.object
        if self.all_actions:
            actions = bpy.data.actions
        else:
            actions = [arm.animation_data.action]
            
        if not actions or actions[0] is None:
            return {'CANCELLED'}
        was_inverted = arm.nwo.invert_control_rig
        baked_count = bake_control_rig_actions(context, arm, actions)
        set_control_rig_inverted(context, arm, False)
        if was_inverted and baked_count:
            correct_baked_control_target_actions(context, arm, actions)
        
        return {'FINISHED'}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "all_actions")

class NWO_OT_BakeIKControl(bpy.types.Operator):
    bl_idname = "nwo.bake_ik_control"
    bl_label = "Snap Bones"
    bl_description = "Toggle IK/FK and snap the affected bones so the pose is preserved"
    bl_options = {"UNDO", "REGISTER"}

    prop_name: bpy.props.StringProperty(options={'HIDDEN'})
    direction: bpy.props.EnumProperty(
        options={'HIDDEN'},
        items=[
            ('TOGGLE', "Toggle", "Choose FK to IK or IK to FK from the current IK slider value"),
            ('FK_TO_IK', "FK to IK", "Snap IK controls to the current FK pose and enable IK"),
            ('IK_TO_FK', "IK to FK", "Snap FK controls to the current IK pose and disable IK"),
        ],
        default='TOGGLE',
    )
    do_bake: bpy.props.BoolProperty(name="Bake", default=False)
    frame_start: bpy.props.IntProperty(name="Start Frame")
    frame_end: bpy.props.IntProperty(name="End Frame")
    key_before_start: bpy.props.BoolProperty(
        name="Key Before Start",
        description="Insert keys one frame before the bake range to preserve the previous mode",
        default=False,
    )
    key_after_end: bpy.props.BoolProperty(
        name="Key After End",
        description="Insert keys one frame after the bake range to preserve the following mode",
        default=False,
    )

    @classmethod
    def description(cls, context, properties):
        direction = cls.resolve_direction_from_context(context, properties)
        prop_name = getattr(properties, "prop_name", "")
        arm = context.object if context is not None else None
        is_ik_prop = bool(
            arm is not None
            and getattr(arm, "type", None) == 'ARMATURE'
            and prop_name
            and fk_bones_from_ik_prop(arm, prop_name)
        )
        if not is_ik_prop and prop_name:
            if direction == 'FK_TO_IK':
                return "Enable this pose control and preserve the affected bones"
            elif direction == 'IK_TO_FK':
                return "Disable this pose control and preserve the affected bones"
            return "Toggle this pose control and preserve the affected bones"

        if direction == 'FK_TO_IK':
            return "Snap IK controls to the current FK pose and enable IK"
        elif direction == 'IK_TO_FK':
            return "Snap FK controls to the current IK pose and disable IK"
        return cls.bl_description

    @classmethod
    def poll(cls, context):
        arm = context.object
        return bool(arm and arm.type == 'ARMATURE' and arm.pose.bones.get(settings_control_name))

    @classmethod
    def resolve_direction_from_context(cls, context, properties):
        direction = getattr(properties, "direction", "TOGGLE")
        if direction != 'TOGGLE':
            return direction

        return cls.resolve_auto_direction_from_context(context, getattr(properties, "prop_name", ""))

    @classmethod
    def resolve_auto_direction_from_context(cls, context, prop_name: str):
        arm = context.object
        settings_bone = arm.pose.bones.get(settings_control_name) if arm is not None and arm.type == 'ARMATURE' else None
        if settings_bone is None or prop_name not in settings_bone:
            return 'FK_TO_IK'

        try:
            return 'FK_TO_IK' if float(settings_bone[prop_name]) < 1.0 else 'IK_TO_FK'
        except (TypeError, ValueError):
            return 'FK_TO_IK'

    def invoke(self, context, _event):
        self.frame_start = context.scene.frame_start
        self.frame_end = context.scene.frame_end
        self.do_bake = False
        self.direction = self.resolve_auto_direction_from_context(context, self.prop_name)
        if self._snap_context(context, report=True) is None:
            return {'CANCELLED'}
        return self.execute(context)
        # return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "do_bake")
        if self.do_bake:
            time_row = layout.row(align=True)
            time_row.prop(self, "frame_start")
            time_row.prop(self, "frame_end")
            key_row = layout.row(align=True)
            key_row.prop(self, "key_before_start")
            key_row.prop(self, "key_after_end")

        snap_context = self._snap_context(context)
        if snap_context is None:
            return

        layout.separator()
        layout.label(text="Snapped bones:" if snap_context["type"] == "IK" else "Preserved bones:")
        col = layout.column(align=True)
        if snap_context["type"] == "IK":
            for _fkb, ikb, ptb, chain in snap_context["contexts"]:
                for source_name, target_name in ik_snap_display_rows(snap_context["direction"], chain, ikb, ptb):
                    col.label(text=f"          {source_name} -> {target_name}")
        else:
            for pbone in snap_context["bones"]:
                col.label(text=f"          {pbone.name}")

    def execute(self, context):
        snap_context = self._snap_context(context, report=True)
        if snap_context is None:
            return {'CANCELLED'}

        arm = snap_context["arm"]
        settings_bone = snap_context["settings_bone"]
        direction = snap_context["direction"]
        if self.do_bake and self.frame_end < self.frame_start:
            self.report({'WARNING'}, "End frame must be greater than or equal to start frame")
            return {'CANCELLED'}

        if self.do_bake:
            ensure_armature_action(arm)
        elif arm.animation_data is None:
            arm.animation_data_create()

        original_mode = context.mode
        original_frame = context.scene.frame_current
        utils.set_object_mode(context)
        utils.set_active_object(arm)

        try:
            affected_bones = snap_context_affected_bones(snap_context)
            if self.do_bake:
                frames = list(range(self.frame_start, self.frame_end + 1))
                if self.key_before_start:
                    key_ik_state(context, settings_bone, self.prop_name, affected_bones, self.frame_start - 1)
                if self.key_after_end:
                    key_ik_state(context, settings_bone, self.prop_name, affected_bones, self.frame_end + 1)

                for frame in frames:
                    snap_control_context_frame(context, snap_context, frame, keyframe=True)

                set_settings_prop_key_interpolation(arm, self.prop_name, frames)
                self.report({'INFO'}, f"Baked {'on' if direction == 'FK_TO_IK' else 'off'} for {self.prop_name}")
            else:
                snap_control_context_frame(context, snap_context, original_frame, keyframe=False)
                self.report({'INFO'}, f"Snapped {self.prop_name} {'on' if direction == 'FK_TO_IK' else 'off'}")
        finally:
            if self.do_bake:
                context.scene.frame_set(original_frame)
            else:
                context.view_layer.update()
            utils.restore_mode(original_mode)

        return {'FINISHED'}

    def _snap_context(self, context, report=False):
        ik_context = self._ik_context(context)
        if ik_context is not None:
            return ik_context

        generic_context = self._generic_context(context)
        if generic_context is not None:
            return generic_context

        if report:
            self.report({'WARNING'}, f"Failed to find driven controls for {self.prop_name}")

    def _ik_context(self, context):
        arm = context.object
        settings_bone = arm.pose.bones.get(settings_control_name)
        if settings_bone is None or self.prop_name not in settings_bone:
            return None

        contexts = []
        for fkb in fk_bones_from_ik_prop(arm, self.prop_name):
            ikb = arm.pose.bones.get(fkb.name.replace("FK_", "IK_", 1))
            ptb = arm.pose.bones.get(fkb.name.replace("FK_", "PT_", 1))
            if ikb is None:
                continue

            chain = fk_chain_for_end_bone(fkb)
            if not chain:
                continue
            contexts.append((fkb, ikb, ptb, chain))

        if not contexts:
            return None

        return {
            "type": "IK",
            "arm": arm,
            "settings_bone": settings_bone,
            "prop_name": self.prop_name,
            "contexts": contexts,
            "direction": self.resolve_direction_from_context(context, self),
        }

    def _generic_context(self, context):
        arm = context.object
        settings_bone = arm.pose.bones.get(settings_control_name)
        if settings_bone is None or self.prop_name not in settings_bone:
            return None

        bones = settings_prop_affected_pose_bones(arm, self.prop_name)
        if not bones:
            return None

        return {
            "type": "GENERIC",
            "arm": arm,
            "settings_bone": settings_bone,
            "prop_name": self.prop_name,
            "bones": bones,
            "direction": self.resolve_direction_from_context(context, self),
        }

def ensure_armature_action(arm: bpy.types.Object):
    if arm.animation_data is None:
        arm.animation_data_create()
    if arm.animation_data.action is None:
        arm.animation_data.action = bpy.data.actions.new(f"ACT-{arm.name}")

def snap_context_affected_bones(snap_context) -> list[bpy.types.PoseBone]:
    if snap_context["type"] == "IK":
        affected = []
        for _fkb, ikb, ptb, chain in snap_context["contexts"]:
            affected.extend(ik_affected_bones(snap_context["direction"], chain, ikb, ptb))
        return unique_pose_bones(affected)

    return unique_pose_bones(snap_context["bones"])

def unique_pose_bones(bones) -> list[bpy.types.PoseBone]:
    unique = []
    seen = set()
    for bone in bones:
        if bone is None or bone.name in seen:
            continue
        unique.append(bone)
        seen.add(bone.name)

    return unique

def ik_snap_display_rows(direction: str, chain: list[bpy.types.PoseBone], ikb: bpy.types.PoseBone, ptb: bpy.types.PoseBone | None) -> list[tuple[str, str]]:
    if direction == 'FK_TO_IK':
        rows = [(chain[-1].name, ikb.name)] if chain else []
        if ptb is None:
            return rows
        if len(chain) > 1:
            rows.append((chain[-2].name, ptb.name))
        else:
            rows.append((chain[-1].name if chain else ikb.name, ptb.name))
        return rows

    return [(ikb.name, pbone.name) for pbone in chain]

def ik_affected_bones(direction: str, chain: list[bpy.types.PoseBone], ikb: bpy.types.PoseBone, ptb: bpy.types.PoseBone | None) -> list[bpy.types.PoseBone]:
    if direction == 'FK_TO_IK':
        return [bone for bone in (ikb, ptb) if bone is not None]

    return list(chain)

def key_ik_state(
    context: bpy.types.Context,
    settings_bone: bpy.types.PoseBone,
    prop_name: str,
    affected_bones: list[bpy.types.PoseBone],
    frame: int,
):
    context.scene.frame_set(frame)
    context.view_layer.update()
    keyframe_settings_prop(settings_bone, prop_name, frame)
    for pbone in affected_bones:
        keyframe_pose_bone_transform(pbone, frame)

def snap_control_context_frame(context, snap_context, frame: int, keyframe=False):
    if snap_context["type"] == "IK":
        snap_ik_contexts_frame(
            context,
            snap_context["settings_bone"],
            snap_context["arm"],
            snap_context["prop_name"] if "prop_name" in snap_context else None,
            snap_context["direction"],
            snap_context["contexts"],
            frame,
            keyframe,
        )
        return

    snap_generic_control_frame(
        context,
        snap_context["settings_bone"],
        snap_context["prop_name"] if "prop_name" in snap_context else None,
        snap_context["direction"],
        snap_context["bones"],
        frame,
        keyframe,
    )

def snap_ik_contexts_frame(
    context: bpy.types.Context,
    settings_bone: bpy.types.PoseBone,
    arm: bpy.types.Object,
    prop_name: str | None,
    direction: str,
    contexts: list[tuple[bpy.types.PoseBone, bpy.types.PoseBone, bpy.types.PoseBone | None, list[bpy.types.PoseBone]]],
    frame: int,
    keyframe=False,
):
    if not prop_name:
        return

    context.scene.frame_set(frame)
    if direction == 'FK_TO_IK':
        set_settings_control_prop_value(settings_bone, prop_name, False)
        context.view_layer.update()
        targets = []
        for fkb, _ikb, ptb, chain in contexts:
            ik_matrix = ik_snap_target_matrix(fkb, _ikb)
            pole_position = calculate_pose_pole_position(chain[0], chain[-2], fkb, ptb) if ptb is not None and len(chain) > 1 else None
            targets.append((ik_matrix, pole_position))

        for (_fkb, ikb, ptb, _chain), (ik_matrix, pole_position) in zip(contexts, targets):
            ikb.matrix = ik_matrix
            if ptb is not None and pole_position is not None:
                set_pose_bone_matrix_translation(ptb, pole_position)
        context.view_layer.update()
        set_settings_control_prop_value(settings_bone, prop_name, True)
        context.view_layer.update()

        if keyframe:
            for _fkb, ikb, ptb, _chain in contexts:
                keyframe_pose_bone_transform(ikb, frame)
                if ptb is not None:
                    keyframe_pose_bone_transform(ptb, frame)
            keyframe_settings_prop(settings_bone, prop_name, frame)
        return

    set_settings_control_prop_value(settings_bone, prop_name, True)
    context.view_layer.update()
    visual_matrices = {}
    for _fkb, _ikb, _ptb, chain in contexts:
        visual_matrices.update({pbone.name: pbone.matrix.copy() for pbone in chain})

    set_settings_control_prop_value(settings_bone, prop_name, False)
    context.view_layer.update()
    for _fkb, _ikb, _ptb, chain in contexts:
        restore_pose_bone_matrices(context, chain, visual_matrices)

    if keyframe:
        for _fkb, _ikb, _ptb, chain in contexts:
            for pbone in chain:
                keyframe_pose_bone_transform(pbone, frame)
        keyframe_settings_prop(settings_bone, prop_name, frame)

def ik_snap_target_matrix(fkb: bpy.types.PoseBone, ikb: bpy.types.PoseBone) -> Matrix:
    if is_finger_ik_source_name(fkb.name):
        matrix = ikb.matrix.copy()
        matrix.translation = fkb.tail.copy()
        return matrix

    return fkb.matrix.copy()

def restore_pose_bone_matrices(
    context: bpy.types.Context,
    bones: list[bpy.types.PoseBone],
    matrices: dict[str, Matrix],
):
    for pbone in bones:
        matrix = matrices.get(pbone.name)
        if matrix is None:
            continue
        pbone.matrix = matrix
        context.view_layer.update()

def snap_generic_control_frame(
    context: bpy.types.Context,
    settings_bone: bpy.types.PoseBone,
    prop_name: str | None,
    direction: str,
    affected_bones: list[bpy.types.PoseBone],
    frame: int,
    keyframe=False,
):
    if not prop_name:
        return

    context.scene.frame_set(frame)
    context.view_layer.update()
    visual_matrices = {pbone.name: pbone.matrix.copy() for pbone in affected_bones}
    compensated_bone_names = set()
    if direction == 'FK_TO_IK':
        compensated_bone_names = compensate_armature_follow_target_matrices(
            context,
            settings_bone.id_data,
            prop_name,
            affected_bones,
            visual_matrices,
        )
    set_settings_control_prop_value(settings_bone, prop_name, direction == 'FK_TO_IK')
    context.view_layer.update()
    restore_pose_bone_matrices(
        context,
        [pbone for pbone in affected_bones if pbone.name not in compensated_bone_names],
        visual_matrices,
    )

    if keyframe:
        for pbone in affected_bones:
            keyframe_pose_bone_transform(pbone, frame)
        keyframe_settings_prop(settings_bone, prop_name, frame)

def compensate_armature_follow_target_matrices(
    context: bpy.types.Context,
    arm: bpy.types.Object,
    prop_name: str,
    bones: list[bpy.types.PoseBone],
    visual_matrices: dict[str, Matrix],
) -> set[str]:
    compensated_bone_names = set()
    for pbone in bones:
        matrix = visual_matrices.get(pbone.name)
        if matrix is None:
            continue

        compensated = False
        for target_bone in armature_constraint_targets_driven_by_prop(arm, pbone, prop_name):
            deform = target_bone.matrix @ target_bone.bone.matrix_local.inverted_safe()
            matrix = deform.inverted_safe() @ matrix
            compensated = True

        if compensated:
            pbone.matrix = matrix
            context.view_layer.update()
            compensated_bone_names.add(pbone.name)

    return compensated_bone_names

def armature_constraint_targets_driven_by_prop(
    arm: bpy.types.Object,
    pbone: bpy.types.PoseBone,
    prop_name: str,
) -> list[bpy.types.PoseBone]:
    animation_data = arm.animation_data
    if animation_data is None:
        return []

    prop_path = settings_prop_data_path(prop_name)
    driven_paths = {
        fcurve.data_path
        for fcurve in animation_data.drivers
        if any(
            target.id == arm and target.data_path == prop_path
            for var in fcurve.driver.variables
            for target in var.targets
        )
    }
    if not driven_paths:
        return []

    targets = []
    for con in pbone.constraints:
        if con.type != 'ARMATURE':
            continue

        for index, target in enumerate(con.targets):
            data_path = f'pose.bones["{pbone.name}"].constraints["{con.name}"].targets[{index}].weight'
            if data_path not in driven_paths or target.target != arm:
                continue

            target_bone = arm.pose.bones.get(target.subtarget)
            if target_bone is not None:
                targets.append(target_bone)

    return targets

def set_settings_control_prop_value(settings_bone: bpy.types.PoseBone, prop_name: str, enabled: bool):
    if settings_prop_uses_bool(settings_bone, prop_name):
        settings_bone[prop_name] = bool(enabled)
    else:
        settings_bone[prop_name] = 1.0 if enabled else 0.0
    settings_bone.id_data.update_tag()

def settings_prop_uses_bool(settings_bone: bpy.types.PoseBone, prop_name: str) -> bool:
    if prop_name in settings_bone and isinstance(settings_bone[prop_name], bool):
        return True

    lower_name = prop_name.lower()
    return (
        "follows " in lower_name
        or "follow " in lower_name
        or "ignores " in lower_name
        or "ignore " in lower_name
        or "root_ignore" in lower_name
    )

def snap_ik_control_frame(
    context: bpy.types.Context,
    settings_bone: bpy.types.PoseBone,
    prop_name: str,
    direction: str,
    chain: list[bpy.types.PoseBone],
    fkb: bpy.types.PoseBone,
    ikb: bpy.types.PoseBone,
    ptb: bpy.types.PoseBone,
    frame: int,
    keyframe=False,
):
    context.scene.frame_set(frame)
    if direction == 'FK_TO_IK':
        set_settings_control_prop_value(settings_bone, prop_name, False)
        context.view_layer.update()

        ik_matrix = ik_snap_target_matrix(fkb, ikb)
        pole_position = calculate_pose_pole_position(chain[0], chain[-2], fkb, ptb) if len(chain) > 1 else fkb.head.copy()

        ikb.matrix = ik_matrix
        set_pose_bone_matrix_translation(ptb, pole_position)
        context.view_layer.update()
        set_settings_control_prop_value(settings_bone, prop_name, True)
        context.view_layer.update()

        if keyframe:
            keyframe_pose_bone_transform(ikb, frame)
            keyframe_pose_bone_transform(ptb, frame)
            keyframe_settings_prop(settings_bone, prop_name, frame)
        return

    set_settings_control_prop_value(settings_bone, prop_name, True)
    context.view_layer.update()
    visual_matrices = {pbone.name: pbone.matrix.copy() for pbone in chain}

    set_settings_control_prop_value(settings_bone, prop_name, False)
    context.view_layer.update()
    restore_pose_bone_matrices(context, chain, visual_matrices)

    if keyframe:
        for pbone in chain:
            keyframe_pose_bone_transform(pbone, frame)
        keyframe_settings_prop(settings_bone, prop_name, frame)

class NWO_OT_KeyframeControlRigSettings(bpy.types.Operator):
    bl_idname = "nwo.keyframe_control_rig_settings"
    bl_label = "Keyframe Non-Zero Pose Controls"
    bl_description = "Adds keyframes at the current frame for all non-zero CTRL_settings pose control properties"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        arm = context.object
        return bool(arm and arm.type == 'ARMATURE' and arm.pose.bones.get(settings_control_name))

    def execute(self, context):
        arm = context.object
        settings_bone = context.object.pose.bones.get(settings_control_name)
        frame = context.scene.frame_current
        keyed_count = 0

        for prop_name in sorted(key for key in settings_bone.keys()):
            try:
                value = float(settings_bone[prop_name])
            except (TypeError, ValueError):
                continue

            if abs(value) <= 1e-6 and not settings_prop_has_fcurve(arm, prop_name):
                continue

            keyframe_settings_prop(settings_bone, prop_name, frame)
            keyed_count += 1

        if keyed_count == 0:
            self.report({'INFO'}, f"No non-zero {settings_control_name} properties to key")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Keyframed {keyed_count} {settings_control_name} propert{'y' if keyed_count == 1 else 'ies'}")
        return {'FINISHED'}

def settings_prop_has_fcurve(arm: bpy.types.Object, prop_name: str) -> bool:
    if arm.animation_data is None or arm.animation_data.action is None:
        return False

    fcurves = utils.get_fcurves(arm.animation_data.action, arm)
    if not fcurves:
        return False

    data_path = settings_prop_data_path(prop_name)
    return any(fcurve.data_path == data_path for fcurve in fcurves)

POSE_BONE_DATA_PATH_RE = re.compile(r'pose\.bones\["([^"]+)"\]')

def fk_bones_from_ik_prop(arm: bpy.types.Object, prop_name: str) -> list[bpy.types.PoseBone]:
    bones = []
    for pbone in arm.pose.bones:
        if pbone.name.startswith("FK_") and ik_blend_property_name(pbone.name) == prop_name:
            bones.append(pbone)

    return bones

def fk_bone_from_ik_prop(arm: bpy.types.Object, prop_name: str) -> bpy.types.PoseBone | None:
    bones = fk_bones_from_ik_prop(arm, prop_name)
    return bones[0] if bones else None

def settings_prop_affected_pose_bones(arm: bpy.types.Object, prop_name: str) -> list[bpy.types.PoseBone]:
    animation_data = arm.animation_data
    if animation_data is None:
        return []

    prop_path = settings_prop_data_path(prop_name)
    affected_names = []
    for fcurve in animation_data.drivers:
        driver = fcurve.driver
        if not any(
            target.id == arm and target.data_path == prop_path
            for var in driver.variables
            for target in var.targets
        ):
            continue

        match = POSE_BONE_DATA_PATH_RE.search(fcurve.data_path)
        if match is not None:
            affected_names.append(match.group(1))

    return [
        arm.pose.bones[name]
        for name in dict.fromkeys(affected_names)
        if arm.pose.bones.get(name) is not None
    ]

def fk_chain_for_end_bone(fkb: bpy.types.PoseBone) -> list[bpy.types.PoseBone]:
    chain = []
    pbone = fkb
    while pbone is not None and pbone.name.startswith("FK_"):
        if is_finger_ik_source_name(fkb.name) and not is_finger_ik_chain_source_name(pbone.name):
            break
        chain.append(pbone)
        pbone = pbone.parent

    chain.reverse()
    return chain

def ik_bake_frames(context, arm: bpy.types.Object, action: bpy.types.Action | None, source_bones: list[bpy.types.PoseBone], prop_name: str) -> list[int]:
    if action is None:
        return [context.scene.frame_current]

    fcurves = utils.get_fcurves(action, arm)
    if not fcurves:
        return [context.scene.frame_current]

    source_paths = set()
    for pbone in source_bones:
        source_paths.update(pose_bone_transform_paths(pbone.name))
    source_paths.add(settings_prop_data_path(prop_name))

    frames = fcurve_keyframes(fcurve for fcurve in fcurves if fcurve.data_path in source_paths)
    if not frames:
        frames = fcurve_keyframes(fcurves)
    if not frames:
        return [context.scene.frame_current]

    start = floor(min(frames))
    end = ceil(max(frames))
    if end < start:
        return [context.scene.frame_current]

    return list(range(start, end + 1))

def pose_bone_transform_paths(bone_name: str) -> tuple[str, ...]:
    prefix = f'pose.bones["{bone_name}"].'
    return (
        f"{prefix}location",
        f"{prefix}rotation_euler",
        f"{prefix}rotation_quaternion",
        f"{prefix}rotation_axis_angle",
        f"{prefix}scale",
    )

def settings_prop_data_path(prop_name: str) -> str:
    return f'pose.bones["{settings_control_name}"]["{prop_name}"]'

def fcurve_keyframes(fcurves) -> set[float]:
    frames = set()
    for fcurve in fcurves:
        for keyframe_point in fcurve.keyframe_points:
            frames.add(keyframe_point.co[0])

    return frames

def calculate_pose_pole_position(root_bone: bpy.types.PoseBone, mid_bone: bpy.types.PoseBone, end_bone: bpy.types.PoseBone, pole_target: bpy.types.PoseBone | None = None, distance_scale=1.25) -> Vector:
    a = root_bone.head.copy()
    b = mid_bone.head.copy()
    c = end_bone.head.copy()

    ac = c - a
    if ac.length < 1e-6:
        return b.copy()

    ac_dir = ac.normalized()
    projection = a + ac_dir * ((b - a).dot(ac_dir))
    pole_dir = b - projection

    if pole_dir.length < 1e-6 and pole_target is not None:
        pole_dir = pole_target.matrix.translation - b
        pole_dir -= ac_dir * pole_dir.dot(ac_dir)

    if pole_dir.length < 1e-6:
        pole_dir = mid_bone.matrix.to_3x3().col[0].copy()

    if pole_dir.length < 1e-6:
        pole_dir = Vector((0.0, 0.0, 1.0))

    pole_dir.normalize()
    dist = max((b - a).length, (c - b).length) * distance_scale
    return b + pole_dir * dist

def set_pose_bone_matrix_translation(pbone: bpy.types.PoseBone, translation: Vector):
    matrix = pbone.matrix.copy()
    matrix.translation = translation
    pbone.matrix = matrix

def keyframe_pose_bone_transform(pbone: bpy.types.PoseBone, frame: int):
    pbone.keyframe_insert(data_path="location", frame=frame)
    if pbone.rotation_mode == 'QUATERNION':
        pbone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    elif pbone.rotation_mode == 'AXIS_ANGLE':
        pbone.keyframe_insert(data_path="rotation_axis_angle", frame=frame)
    else:
        pbone.keyframe_insert(data_path="rotation_euler", frame=frame)
    pbone.keyframe_insert(data_path="scale", frame=frame)

def keyframe_settings_prop(settings_bone: bpy.types.PoseBone, prop_name: str, frame: int):
    settings_bone.keyframe_insert(data_path=f'["{prop_name}"]', frame=frame)

def set_settings_prop_key_interpolation(arm: bpy.types.Object, prop_name: str, frames: list[int]):
    if arm.animation_data is None or arm.animation_data.action is None:
        return

    fcurves = utils.get_fcurves(arm.animation_data.action, arm)
    if not fcurves:
        return

    data_path = settings_prop_data_path(prop_name)
    frame_set = set(frames)
    for fcurve in fcurves:
        if fcurve.data_path != data_path:
            continue

        for keyframe_point in fcurve.keyframe_points:
            if round(keyframe_point.co[0]) in frame_set:
                keyframe_point.interpolation = 'CONSTANT'
        fcurve.update()
        break

class NWO_OT_BuildControlRig(bpy.types.Operator):
    bl_idname = "nwo.build_control_rig"
    bl_label = "Build Control Rig"
    bl_description = "Generates an FK & IK control rig for this armature"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'
    
    apply_deform_bone_shape: bpy.props.BoolProperty(
        name="Apply Deform Bone Shape",
        description="Applies a custom bone shape to deform bones before applying the control rig",
        default=True,
    )

    apply_reach_fp_ik_fix: bpy.props.BoolProperty(
        name="Reach FP Arms Fix",
        description="Applies the special IK pole placement fix for Halo Reach Spartan and Elite first person arm rigs",
        default=False,
    )
    
    def execute(self, context):
        arm = context.object
        any_pose_bones = any(b.name for b in arm.pose.bones if b.name.endswith(("_pitch", "_yaw")))
        rig = HaloRig(context, scale=scene_control_scale(), has_pose_bones=any_pose_bones)
        rig.rig_ob = arm
        rig.rig_data = arm.data
        rig.rig_pose = arm.pose

        aim_control = None
        if any_pose_bones:
            aim_control = utils.get_pose_bone(arm, arm.nwo.control_aim) if arm.nwo.control_aim else None
            if aim_control is None:
                aim_control = utils.get_pose_bone(arm, aim_control_name)
            if aim_control is None:
                rig.build_bones()
                rig.rig_pose = arm.pose

        rig.build_and_apply_control_shapes(
            aim_control=aim_control,
            reverse_control=arm.nwo.invert_control_aim,
            constraints_only=False,
        )
        
        if self.apply_deform_bone_shape:
            rig.apply_halo_bone_shape()

        update_existing_rig = armature_has_fk_ik_control_rig(arm)
        rig.build_fk_ik_rig(
            reverse_controls=arm.nwo.invert_control_rig,
            constraints_only=update_existing_rig,
            reach_fp_ik_fix=self.apply_reach_fp_ik_fix,
        )
        rig.generate_bone_collections()
        self.report({'INFO'}, "Updated Control Rig" if update_existing_rig else "Built Control Rig")
        return {'FINISHED'}
    
    def invoke(self, context, _):
        self.apply_reach_fp_ik_fix = armature_needs_reach_fp_ik_fix(context.object)
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "apply_deform_bone_shape")
        self.layout.prop(self, "apply_reach_fp_ik_fix")


class NWO_OT_ClearControlRig(bpy.types.Operator):
    bl_idname = "nwo.clear_control_rig"
    bl_label = "Clear Control Rig"
    bl_description = "Removes generated FK, IK, and control bones from this armature"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        arm = context.object
        return bool(arm and arm.type == 'ARMATURE' and generated_control_bone_names(arm))

    def execute(self, context):
        arm = context.object
        control_bone_names = generated_control_bone_names(arm)
        if not control_bone_names:
            self.report({'INFO'}, "No control rig bones found")
            return {'CANCELLED'}

        original_mode = context.mode
        utils.set_object_mode(context)
        utils.set_active_object(arm)

        try:
            clear_control_rig_constraints(arm, control_bone_names)
            remove_order = control_bone_remove_order(arm, control_bone_names)

            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            edit_bones = arm.data.edit_bones
            removed_count = 0
            for name in remove_order:
                bone = edit_bones.get(name)
                if bone is None:
                    continue

                edit_bones.remove(bone)
                removed_count += 1

            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            arm.nwo.invert_control_rig = False
            if arm.nwo.control_aim in control_bone_names:
                arm.nwo.control_aim = ""
                arm.nwo.invert_control_aim = False

            rig = HaloRig(context, scale=scene_control_scale())
            rig.rig_ob = arm
            rig.rig_data = arm.data
            rig.rig_pose = arm.pose
            rig.generate_bone_collections()
            remove_control_bone_collections(arm.data)

        finally:
            utils.restore_mode(original_mode)

        self.report({'INFO'}, f"Cleared {removed_count} control rig bones")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
    
class NWO_OT_InvertControlRig(bpy.types.Operator):
    bl_idname = "nwo.invert_control_rig"
    bl_label = "Invert Control Rig"
    bl_description = "Inverts the constraint relationship between the control (FK & IK) rig and deform bones"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'
    
    def execute(self, context):
        arm = context.object
        any_pose_bones = any(b.name for b in arm.pose.bones if b.name.endswith(("_pitch", "_yaw")))
        rig = HaloRig(context, scale=scene_control_scale(), has_pose_bones=any_pose_bones)
        rig.rig_ob = arm
        rig.rig_data = arm.data
        rig.rig_pose = arm.pose
        
        rig.build_fk_ik_rig(
            reverse_controls=(not arm.nwo.invert_control_rig),
            constraints_only=True,
            reach_fp_ik_fix=armature_needs_reach_fp_ik_fix(arm),
        )
        self.report({'INFO'}, f"Inverted Control Rig - {'Deform bones in control' if arm.nwo.invert_control_rig else 'Control bones in control'}")
        return {'FINISHED'}

class NWO_OT_InvertAimControl(bpy.types.Operator):
    bl_idname = "nwo.invert_aim_control"
    bl_label = "Invert Aim Control"
    bl_description = "Inverts the constraint relationship between the Aim Control and aim pitch / aim yaw bones. Allows the aim pitch and aim yaw bones to control the aim control bone"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE' and context.object.nwo.control_aim.strip()
    
    def execute(self, context):
        arm = context.object
        aim_control_name = context.object.nwo.control_aim
        aim_control = utils.get_pose_bone(arm, aim_control_name)
        if aim_control is None:
            self.report({'WARNING'}, f"Failed to find aim control bone named {aim_control_name}")
            return {'CANCELLED'}
        
        rig = HaloRig(context, has_pose_bones=True)
        rig.rig_ob = arm
        rig.rig_data = arm.data
        rig.rig_pose = arm.pose
        rig.build_and_apply_control_shapes(aim_control=aim_control, aim_control_only=True, reverse_control=(not arm.nwo.invert_control_aim), constraints_only=True)
        self.report({'INFO'}, f"Aim pitch & yaw now control {aim_control_name}" if arm.nwo.invert_control_aim else f"{aim_control_name} controls aim pitch & yaw")
        return {'FINISHED'}

class NWO_OT_AddRig(bpy.types.Operator):
    bl_idname = "nwo.add_rig"
    bl_label = "Add Halo Rig"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    has_pose_bones: bpy.props.BoolProperty(default=True)
    # wireframe: bpy.props.BoolProperty(name="Wireframe Control Shapes", description="Makes the control shapes wireframe rather than solid", default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        add_rig(context, self.has_pose_bones)
        return {"FINISHED"}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'has_pose_bones', text='Add Aim Bones')
        # layout.prop(self, 'wireframe')
    
class NWO_OT_SelectArmature(bpy.types.Operator):
    bl_label = "Select Armature"
    bl_idname = "nwo.select_armature"
    bl_options = {'UNDO', 'REGISTER'}
    bl_description = "Sets the main scene armature as the active object, optionallu creating one if no armature exists"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    
    has_pose_bones: bpy.props.BoolProperty(default=True)
    # wireframe: bpy.props.BoolProperty(name="Wireframe Control Shapes", description="Makes the control shapes wireframe rather than solid")
    create_arm: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, context):
        if self.create_arm:
            add_rig(context, self.has_pose_bones)
            return {'FINISHED'}
        
        objects = context.view_layer.objects
        scene = context.scene
        scene_nwo = utils.get_scene_props()
        if scene_nwo.main_armature:
            arm = scene_nwo.main_armature
        else:
            rigs = [ob for ob in objects if ob.type == 'ARMATURE']
            if not rigs:
                # self.report({'WARNING'}, "No Armature in Scene")
                self.create_arm = True
                return context.window_manager.invoke_props_dialog(self)
            elif len(rigs) > 1:
                self.report({'WARNING'}, "Multiple Armatures found. Please validate rig under Foundry Tools > Rig Tools")
            arm = rigs[0]
        utils.deselect_all_objects()
        arm.hide_set(False)
        arm.hide_select = False
        arm.select_set(True)
        utils.set_active_object(arm)
        self.report({'INFO'}, F"Selected {arm.name}")

        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.label(text='No Armature in Scene. Press OK to create one')
        layout.prop(self, 'has_pose_bones', text='With Aim Bones')
        
def add_rig(context, has_pose_bones):
    scene_nwo = utils.get_scene_props()
    scale = 1
    rig = HaloRig(context, forward=scene_nwo.forward_direction, has_pose_bones=has_pose_bones, set_scene_rig_props=True)
    rig.build_armature()
    rig.build_bones()
    rig.build_and_apply_control_shapes()

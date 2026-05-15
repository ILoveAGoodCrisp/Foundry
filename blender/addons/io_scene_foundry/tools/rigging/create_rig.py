import bpy

from ... import utils
from ...tools.rigging import (
    HaloRig,
    aim_control_name,
    eye_track_constraint_name,
    fk_collection_name,
    gun_copy_transforms_constraint_name,
    head_track_constraint_name,
    ik_collection_name,
    ik_constraint_name,
    ik_control_property_name,
    ik_copy_rotation_constraint_name,
    is_control_bone_name,
    look_child_of_constraint_name,
    misc_control_collection_name,
    neck_assist_constraint_name,
    needs_reach_fp_ik_fix,
    remove_empty_bone_collection,
    root_child_of_constraint_name,
    settings_control_name,
)
from bpy_extras import anim_utils
from math import ceil, floor
from mathutils import Vector


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
    gun_copy_transforms_constraint_name,
    ik_constraint_name,
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
    for name in (fk_collection_name, ik_collection_name, misc_control_collection_name):
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

    for pb in arm.pose.bones:
        pb.select = pb.name.startswith(("FK_", "CTRL_", "IK_", "PT_"))

    arm.select_set(False)
    options = anim_utils.BakeOptions(True, True, False, True, False, False, False, True, True, True, False, False)
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

    set_control_rig_inverted(context, arm, True)
    context.view_layer.update()
    try:
        return bake_control_rig_actions(context, arm, actions)
    finally:
        set_control_rig_inverted(context, arm, False)
        context.view_layer.update()


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
        bake_control_rig_actions(context, arm, actions)
        set_control_rig_inverted(context, arm, False)
        
        return {'FINISHED'}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "all_actions")

class NWO_OT_BakeIKControl(bpy.types.Operator):
    bl_idname = "nwo.bake_ik_control"
    bl_label = "Bake IK Control"
    bl_description = "Bakes the active action between an FK chain and its IK control"
    bl_options = {"UNDO"}

    prop_name: bpy.props.StringProperty(options={'HIDDEN'})
    direction: bpy.props.EnumProperty(
        options={'HIDDEN'},
        items=[
            ('FK_TO_IK', "FK to IK", "Snap IK controls to the current FK pose and enable IK"),
            ('IK_TO_FK', "IK to FK", "Snap FK controls to the current IK pose and disable IK"),
        ],
        default='FK_TO_IK',
    )

    @classmethod
    def poll(cls, context):
        arm = context.object
        return bool(arm and arm.type == 'ARMATURE' and arm.pose.bones.get(settings_control_name))

    def execute(self, context):
        arm = context.object
        settings_bone = arm.pose.bones.get(settings_control_name)
        if settings_bone is None or self.prop_name not in settings_bone:
            self.report({'WARNING'}, f"Failed to find {settings_control_name}.{self.prop_name}")
            return {'CANCELLED'}

        fkb = fk_bone_from_ik_prop(arm, self.prop_name)
        if fkb is None:
            self.report({'WARNING'}, f"Failed to find FK bone for {self.prop_name}")
            return {'CANCELLED'}

        ikb = arm.pose.bones.get(fkb.name.replace("FK_", "IK_", 1))
        ptb = arm.pose.bones.get(fkb.name.replace("FK_", "PT_", 1))
        if ikb is None or ptb is None:
            self.report({'WARNING'}, f"Failed to find IK controls for {fkb.name}")
            return {'CANCELLED'}

        if arm.animation_data is None:
            arm.animation_data_create()

        original_mode = context.mode
        original_frame = context.scene.frame_current
        utils.set_object_mode(context)
        utils.set_active_object(arm)

        chain = fk_chain_for_end_bone(fkb)
        action = arm.animation_data.action
        source_bones = chain if self.direction == 'FK_TO_IK' else [ikb, ptb, settings_bone]
        frames = ik_bake_frames(context, arm, action, source_bones, self.prop_name)

        try:
            if self.direction == 'FK_TO_IK':
                for frame in frames:
                    context.scene.frame_set(frame)
                    settings_bone[self.prop_name] = 0.0
                    context.view_layer.update()

                    ikb.matrix = fkb.matrix.copy()
                    set_pose_bone_matrix_translation(
                        ptb,
                        calculate_pose_pole_position(chain[0], chain[-2], fkb, ptb) if len(chain) > 1 else fkb.head.copy(),
                    )
                    context.view_layer.update()

                    settings_bone[self.prop_name] = 1.0
                    context.view_layer.update()
                    keyframe_pose_bone_transform(ikb, frame)
                    keyframe_pose_bone_transform(ptb, frame)
                    keyframe_settings_prop(settings_bone, self.prop_name, frame)

                set_settings_prop_key_interpolation(arm, self.prop_name, frames)
                self.report({'INFO'}, f"Baked FK to IK for {fkb.name}")
            else:
                for frame in frames:
                    context.scene.frame_set(frame)
                    settings_bone[self.prop_name] = 1.0
                    context.view_layer.update()

                    visual_matrices = {pbone.name: pbone.matrix.copy() for pbone in chain}
                    settings_bone[self.prop_name] = 0.0
                    context.view_layer.update()

                    for pbone in chain:
                        pbone.matrix = visual_matrices[pbone.name]
                    context.view_layer.update()

                    for pbone in chain:
                        keyframe_pose_bone_transform(pbone, frame)
                    keyframe_settings_prop(settings_bone, self.prop_name, frame)

                set_settings_prop_key_interpolation(arm, self.prop_name, frames)
                self.report({'INFO'}, f"Baked IK to FK for {fkb.name}")
        finally:
            context.scene.frame_set(original_frame)
            utils.restore_mode(original_mode)

        return {'FINISHED'}

def fk_bone_from_ik_prop(arm: bpy.types.Object, prop_name: str) -> bpy.types.PoseBone | None:
    for pbone in arm.pose.bones:
        if pbone.name.startswith("FK_") and ik_control_property_name(pbone.name) == prop_name:
            return pbone

def fk_chain_for_end_bone(fkb: bpy.types.PoseBone) -> list[bpy.types.PoseBone]:
    chain = []
    pbone = fkb
    while pbone is not None and pbone.name.startswith("FK_"):
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

import bpy

from ... import utils
from ...tools.rigging import HaloRig
from bpy_extras import anim_utils

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
        original_action = None
        if self.all_actions:
            actions = bpy.data.actions
            original_action = arm.animation_data.action
        else:
            actions = [arm.animation_data.action]
            
        if not actions or actions[0] is None:
            return

        for pb in arm.pose.bones:
            pb.select = pb.name.startswith(("FK_", "CTRL_", "IK_"))
            
        arm.select_set(False)
        
        options = anim_utils.BakeOptions(True, True, False, True, False, False, False, True, True, True, False, False)
            
        for action in actions:
            print(f"Baking action: {action.name}")
            
            if action.use_frame_range:
                frame_range = range(int(action.frame_start), int(action.frame_end))
            else:
                frame_range = range(utils.get_frame_start_end_from_keyframes(action, arm))

            if self.all_actions:
                arm.animation_data.action = action
            
            anim_utils.bake_action(arm, action=action, frames=frame_range, bake_options=options)
            
        rig = HaloRig(context, has_pose_bones=True)
        rig.rig_ob = arm
        rig.rig_data = arm.data
        rig.rig_pose = arm.pose
        
        aim_control_name = context.object.nwo.control_aim
        aim_control = utils.get_pose_bone(arm, aim_control_name)
        
        if aim_control is not None:
            rig.build_and_apply_control_shapes(aim_control_only=True, reverse_control=False, constraints_only=True)
        rig.build_fk_ik_rig(reverse_controls=False, constraints_only=True)
        
        if self.all_actions:
            arm.animation_data.action = original_action
        
        return {'FINISHED'}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "all_actions")

class NWO_OT_BuildControlRig(bpy.types.Operator):
    bl_idname = "nwo.build_control_rig"
    bl_label = "Build Control Rig"
    bl_description = "Generates an FK (IK TBD) control rig for this armature"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'
    
    apply_deform_bone_shape: bpy.props.BoolProperty(
        name="Apply Deform Bone Shape",
        description="Applies a custom bone shape to deform bones before applying the control rig"
    )
    
    def execute(self, context):
        arm = context.object
        any_pose_bones = any(b.name for b in arm.pose.bones if b.name.endswith(("_pitch", "_yaw")))
        rig = HaloRig(context, has_pose_bones=any_pose_bones)
        rig.rig_ob = arm
        rig.rig_data = arm.data
        rig.rig_pose = arm.pose
        
        rig.apply_halo_bone_shape()
        rig.build_fk_ik_rig(reverse_controls=arm.nwo.invert_control_rig)
        rig.generate_bone_collections()
        self.report({'INFO'}, "Built Control Rig")
        return {'FINISHED'}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, "apply_deform_bone_shape")
    
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
        rig = HaloRig(context, has_pose_bones=any_pose_bones)
        rig.rig_ob = arm
        rig.rig_data = arm.data
        rig.rig_pose = arm.pose
        
        rig.build_fk_ik_rig(reverse_controls=(not arm.nwo.invert_control_rig), constraints_only=True)
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
    wireframe: bpy.props.BoolProperty(name="Wireframe Control Shapes", description="Makes the control shapes wireframe rather than solid", default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        add_rig(context, self.has_pose_bones, self.wireframe)
        return {"FINISHED"}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'has_pose_bones', text='Add Aim Bones')
        layout.prop(self, 'wireframe')
    
class NWO_OT_SelectArmature(bpy.types.Operator):
    bl_label = "Select Armature"
    bl_idname = "nwo.select_armature"
    bl_options = {'UNDO', 'REGISTER'}
    bl_description = "Sets the main scene armature as the active object, optionallu creating one if no armature exists"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    
    has_pose_bones: bpy.props.BoolProperty(default=True)
    wireframe: bpy.props.BoolProperty(name="Wireframe Control Shapes", description="Makes the control shapes wireframe rather than solid")
    create_arm: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, context):
        if self.create_arm:
            add_rig(context, self.has_pose_bones, self.wireframe)
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
        
def add_rig(context, has_pose_bones, wireframe):
    scene_nwo = utils.get_scene_props()
    scale = 1
    rig = HaloRig(context, forward=scene_nwo.forward_direction, has_pose_bones=has_pose_bones, set_scene_rig_props=True)
    rig.build_armature()
    rig.build_bones()
    rig.build_and_apply_control_shapes(wireframe=wireframe)

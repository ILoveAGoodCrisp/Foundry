import bpy
from io_scene_foundry.tools.rigging import HaloRig

class NWO_OT_AddRig(bpy.types.Operator):
    bl_idname = "nwo.add_rig"
    bl_label = "Add Halo Rig"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    has_pose_bones: bpy.props.BoolProperty(default=True)
    has_pedestal_control: bpy.props.BoolProperty(default=True)
    has_aim_control: bpy.props.BoolProperty(default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene_nwo = context.scene.nwo
        scale = 1 if scene_nwo.scale == 'blender' else (1 / 0.03048)
        rig = HaloRig(context, scale, scene_nwo.forward_direction, self.has_pose_bones, self.has_pedestal_control, self.has_aim_control)
        rig.build_armature()
        rig.build_bones()
        rig.build_bone_collections()
        if self.has_pedestal_control or self.has_aim_control:
            rig.build_and_apply_control_shapes()
        
        return {"FINISHED"}
    
    # def invoke(self, context, _):
    #     return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'has_pedestal_control', text='Add Pedestal Control')
        layout.prop(self, 'has_pose_bones', text='Add Aim Bones')
        if self.has_pose_bones:
            layout.prop(self, 'has_aim_control', text='Add Aim Control')

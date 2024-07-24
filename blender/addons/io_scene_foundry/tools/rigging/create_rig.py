import bpy
from io_scene_foundry.tools.rigging import HaloRig

class NWO_OT_AddRig(bpy.types.Operator):
    bl_idname = "nwo.add_rig"
    bl_label = "Add Halo Rig"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    has_pose_bones: bpy.props.BoolProperty(default=True)
    wireframe: bpy.props.BoolProperty(name="Wireframe Control Shapes", description="Makes the control shapes wireframe rather than solid")
    # has_pedestal_control: bpy.props.BoolProperty(default=True)
    # has_aim_control: bpy.props.BoolProperty(default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        add_rig(context, self.has_pose_bones, self.wireframe)
        return {"FINISHED"}
    
    # def invoke(self, context, _):
    #     return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'has_pose_bones', text='Add Aim Bones')
        layout.prop(self, 'wireframe')
            
def add_rig(context, has_pose_bones, wireframe):
    scene_nwo = context.scene.nwo
    scale = 1
    if scene_nwo.scale == 'max':
        scale *= (1 / 0.03048)
    rig = HaloRig(context, scale, scene_nwo.forward_direction, has_pose_bones, True)
    rig.build_armature()
    rig.build_bones()
    rig.build_and_apply_control_shapes(wireframe=wireframe)

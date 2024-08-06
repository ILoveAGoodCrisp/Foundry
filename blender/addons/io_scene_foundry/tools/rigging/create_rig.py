import bpy

from ... import utils
from ...tools.rigging import HaloRig

class NWO_OT_AddRig(bpy.types.Operator):
    bl_idname = "nwo.add_rig"
    bl_label = "Add Halo Rig"
    bl_description = ""
    bl_options = {"REGISTER", "UNDO"}
    
    has_pose_bones: bpy.props.BoolProperty(default=True)
    wireframe: bpy.props.BoolProperty(name="Wireframe Control Shapes", description="Makes the control shapes wireframe rather than solid")

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
        if scene.nwo.main_armature:
            arm = scene.nwo.main_armature
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
    scene_nwo = context.scene.nwo
    scale = 1
    if scene_nwo.scale == 'max':
        scale *= (1 / 0.03048)
    rig = HaloRig(context, scale, scene_nwo.forward_direction, has_pose_bones, True)
    rig.build_armature()
    rig.build_bones()
    rig.build_and_apply_control_shapes(wireframe=wireframe)

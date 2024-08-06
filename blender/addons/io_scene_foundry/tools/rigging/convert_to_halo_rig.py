# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

'''Prepends Foundry's halo armature to an existing armature'''

import bpy
from ...tools.rigging import HaloRig
from ... import utils

class NWO_OT_ConvertToHaloRig(bpy.types.Operator):
    bl_idname = "nwo.convert_to_halo_rig"
    bl_label = "Convert to Halo Rig"
    bl_description = "Converts the active armature object to be compatiable with Halo by prepending required halo bones to the existing rig"
    bl_options = {"REGISTER", "UNDO"}
    
    has_pose_bones: bpy.props.BoolProperty(default=True)
    wireframe: bpy.props.BoolProperty(name="Wireframe Control Shapes", description="Makes the control shapes wireframe rather than solid")
    convert_root_bone: bpy.props.BoolProperty(name="Use Root Bone as Pedestal", description="Convert the existing root bone to the pedestal bone rather than making it the child of the pedestal. This does not ensure that the root bone has Halo compliant transforms. Use rig validation afterwards to ensure correct transforms")

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'

    def execute(self, context):
        scene_nwo = context.scene.nwo
        target_root_bone = utils.rig_root_deform_bone(context.object, True)
        if "pedestal" in target_root_bone or scene_nwo.node_usage_pedestal == target_root_bone:
            self.report({'WARNING'}, f"Armature [{context.object.name}] already has Halo skeleton structure, skipping")
            return {'CANCELLED'}
        scale = 1
        if scene_nwo.scale == 'max':
            scale *= (1 / 0.03048)
        rig = HaloRig(context, scale, scene_nwo.forward_direction, self.has_pose_bones, True)
        rig.rig_ob = context.object
        rig.rig_data = context.object.data
        root_bone = None
        if self.convert_root_bone:
            root_bone = target_root_bone
            if type(root_bone) == list:
                self.report({"WARNING"}, "Found more than one root bone. Creating new pedestal bone")
                root_bone = None
                
        rig.build_bones(root_bone)
        rig.build_and_apply_control_shapes(root_bone, wireframe=self.wireframe)
        if root_bone != target_root_bone:
            rig.make_parent(target_root_bone)
        return {"FINISHED"}
    
    # def invoke(self, context, _):
    #     return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'has_pose_bones', text='Add Aim Bones')
        layout.prop(self, 'wireframe')
        layout.prop(self, 'convert_root_bone')
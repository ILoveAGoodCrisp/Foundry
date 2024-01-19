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
from io_scene_foundry.tools.rigging import HaloRig
from io_scene_foundry.utils import nwo_utils

class NWO_OT_ConvertToHaloRig(bpy.types.Operator):
    bl_idname = "nwo.convert_to_halo_rig"
    bl_label = "Convert to Halo Rig"
    bl_description = "Converts yhe active armature object to be compatiable with Halo by prepending required halo bones to the existing rig"
    bl_options = {"REGISTER", "UNDO"}
    
    has_pedestal_control: bpy.props.BoolProperty(default=True)
    has_pose_bones: bpy.props.BoolProperty(default=True)
    has_aim_control: bpy.props.BoolProperty(default=True)

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE'

    def execute(self, context):
        scene_nwo = context.scene.nwo
        target_root_bone = nwo_utils.rig_root_deform_bone(context.object, True)
        scale = 1 if scene_nwo.scale == 'blender' else (1 / 0.03048)
        rig = HaloRig(context, scale, scene_nwo.forward_direction, self.has_pose_bones, self.has_pedestal_control, self.has_aim_control, True)
        rig.rig_ob = context.object
        rig.rig_data = context.object.data
        rig.build_bones()
        rig.build_bone_collections()
        if self.has_pedestal_control or self.has_aim_control:
            rig.build_and_apply_control_shapes()
        rig.make_parent(target_root_bone)
        return {"FINISHED"}
    
    # def invoke(self, context, _):
    #     return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'has_pedestal_control', text='Add Pedestal Control')
        layout.prop(self, 'has_pose_bones', text='Add Aim Bones')
        if self.has_pose_bones:
            layout.prop(self, 'has_aim_control', text='Add Aim Control')
    
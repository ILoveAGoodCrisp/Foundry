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

import bpy
from io_scene_foundry.utils import nwo_utils

class NWO_ScaleScene(bpy.types.Operator):
    bl_idname = "nwo.scale_scene"
    bl_label = "Scale Scene"
    bl_description = "Scales the blender scene"
    bl_options = {"UNDO"}
    
    scale_factor: bpy.props.FloatProperty(
        default=1,
        description='Scale factor to apply to the scene'
        )
    
    def scale_items(self, context):
        items = []
        items.append(('blender', 'Blender', "For working at a Blender friendly scale. Scene will be appropriately scaled at export to account for Halo's scale", 'BLENDER', 0))
        items.append(('max', '3DS Max', "Scene is exported without scaling. Use this if you're working with imported 3DS Max Files, or legacy assets such as JMS/ASS files which have not been scaled down for Blender", nwo_utils.get_icon_id("3ds_max"), 2))
        return items
    
    def update_scale(self, context):
        scene_scale = context.scene.nwo.scale
        if self.scale == 'blender':
            if scene_scale == 'blender':
                self.scale_factor = 1
            else:
                self.scale_factor = 0.03048
        else:
            if scene_scale == 'blender':
                self.scale_factor = (1 / 0.03048)
            else:
                self.scale_factor = 1
    
    scale: bpy.props.EnumProperty(
        name="Scale",
        options=set(),
        description="Select the scaling for this asset. Scale is applied at export to ensure units displayed in Blender match with in game units",
        items=scale_items,
        update=update_scale,
    )
    
    def execute(self, context):
        old_mode = context.mode
        old_object = context.object
        old_selection = context.selected_objects
        if bpy.ops.nwo.unlink_animation.poll():
            animation_index = context.scene.nwo.active_action_index
            bpy.ops.nwo.unlink_animation()
        nwo_utils.set_object_mode(context)
        nwo_utils.scale_scene(context, self.scale_factor)
        
        context.scene.nwo.scale = self.scale
        if old_object:
            nwo_utils.set_active_object(old_object)
        [ob.select_set(True) for ob in old_selection]
        
        if 'EDIT' in old_mode:
            bpy.ops.object.editmode_toggle()
        if old_mode == 'POSE':
            bpy.ops.object.posemode_toggle()
            
        context.scene.nwo.active_action_index = animation_index
        return {"FINISHED"}
    
    def invoke(self, context: bpy.types.Context, _):
        if context.scene.nwo.scale == 'blender':
            self.scale = 'max'
        else:
            self.scale = 'blender'
            
        return context.window_manager.invoke_props_dialog(self)
            
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'scale', text='New Scale')
        layout.prop(self, 'scale_factor', text='Scale Factor')

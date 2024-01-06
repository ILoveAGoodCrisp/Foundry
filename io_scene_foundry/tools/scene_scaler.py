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
    bl_label = "Transform Scene"
    bl_description = "Scales and rotates the blender scene"
    bl_options = {"REGISTER","UNDO"}
    
    scale_factor: bpy.props.FloatProperty(
        default=1,
        options={'SKIP_SAVE'},
        description='Scale factor to apply to the scene. Change this to override the default set by the Blender/3DS Max Scale'
        )
    
    def scale_items(self, context):
        items = []
        items.append(('none', 'None', "Does not scale the scene", 'MATPLANE', 0))
        items.append(('blender', 'To Blender', "Scales the scene by a factor of roughly 32.8", 'BLENDER', 1))
        items.append(('max', 'To 3DS Max', "Scales the scene by a factor of roughly 0.03", nwo_utils.get_icon_id("3ds_max"), 2))
        items.append(('custom', 'Custom', "Scales the scene by the given factor", 'FULLSCREEN_ENTER', 3))
        return items
    
    scale: bpy.props.EnumProperty(
        name="Scale",
        options={'SKIP_SAVE'},
        description="Select the scaling for this asset. Scale is applied at export to ensure units displayed in Blender match with in game units",
        items=scale_items,
    )
    
    def update_forward(self, context):
        rot = nwo_utils.blender_rotation_diff(self.forward, context.scene.nwo.forward_direction)
        self.rotation = rot
    
    forward: bpy.props.EnumProperty(
        name="Scene Forward",
        options={'SKIP_SAVE'},
        description="Define the forward direction you are using for the scene. By default Halo uses X forward. Whichever option is set as the forward direction in Blender will be oriented to X forward in game i.e. a model facing -Y in Blender will face X in game",
        default="y-",
        items=[
            ("y-", "-Y", "Model is facing Y negative"),
            ("y", "Y", "Model is facing Y positive"),
            ("x-", "-X", "Model is facing X negative"),
            ("x", "X", "Model is facing X positive"),   
        ],
        update=update_forward,
    )
    
    rotation: bpy.props.FloatProperty(
        name='Rotation',
        options={'SKIP_SAVE'},
        subtype='ANGLE',
    )
    
    marker_forward: bpy.props.EnumProperty(
        name="Marker Direction",
        options=set(),
        description="Determines whether the marker X direction or its current forward is used as the in game X axis",
        items=[
            ('keep', "Keep Axis", "Marker direction is kept as is at export. Use this if you want the marker direction in game to match the marker forward in Blender. Good to use on completely custom assets"),
            ('x', "Use X", "Markers are rotated so that the x axis shown in Blender matches visually with the in game x axis. Use this if you're not exporting with X forward but are importing for an existing asset"),
        ]
    )
    
    def execute(self, context):
        if self.scale == 'none':
            self.scale_factor = 1
        elif self.scale == 'blender':
            self.scale_factor = 0.03048
        elif self.scale == 'max':
            self.scale_factor = (1 / 0.03048)
        
        if not (self.scale_factor != 1 or self.rotation):
            self.report({'INFO'}, "No scaling or rotation applied")
            return {'FINISHED'}
            
        nwo_utils.exit_local_view(context)
        old_mode = context.mode
        old_object = context.object
        old_selection = context.selected_objects
        animation_index = None
        context.scene.tool_settings.use_keyframe_insert_auto = False
        if bpy.ops.nwo.unlink_animation.poll():
            animation_index = context.scene.nwo.active_action_index
            bpy.ops.nwo.unlink_animation()
        nwo_utils.set_object_mode(context)
        nwo_utils.deselect_all_objects()
        nwo_utils.transform_scene(context, self.scale_factor, self.rotation, keep_marker_axis=self.marker_forward == 'keep')

        if old_object:
            nwo_utils.set_active_object(old_object)
        [ob.select_set(True) for ob in old_selection]
        
        if 'EDIT' in old_mode:
            bpy.ops.object.editmode_toggle()
        if old_mode == 'POSE':
            bpy.ops.object.posemode_toggle()
        
        if self.scale == 'blender' or self.scale == 'max':
            context.scene.nwo.scale = self.scale
        context.scene.nwo.forward_direction = self.forward
        context.scene.nwo.marker_forward = self.marker_forward
        
        if animation_index:
            context.scene.nwo.active_action_index = animation_index
        return {"FINISHED"}
    
    def invoke(self, context: bpy.types.Context, _):
        self.forward = context.scene.nwo.forward_direction
        self.marker_forward = context.scene.nwo.marker_forward
        return context.window_manager.invoke_props_dialog(self)
            
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'scale', text='New Scale')
        if self.scale == 'custom':
            layout.prop(self, 'scale_factor', text='Scale Factor')
        layout.prop(self, 'forward')
        layout.prop(self, 'rotation')
        layout.prop(self, 'marker_forward')

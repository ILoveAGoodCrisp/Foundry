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
        description='Scale factor to apply to the scene. Change this to override the default set by the Blender/Halo Scale'
        )
    
    def scale_items(self, context):
        items = []
        items.append(('none', 'None', "Does not scale the scene", 'MATPLANE', 0))
        items.append(('blender', 'To Blender', "Scales the scene by a factor of roughly 32.8", 'BLENDER', 1))
        items.append(('max', 'To Halo', "Scales the scene by a factor of roughly 0.03", nwo_utils.get_icon_id("halo_scale"), 2))
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
        description="The forward direction you are using for the scene. By default Halo uses X forward. Whichever option is set as the forward direction in Blender will be oriented to X forward in game i.e. a model facing -Y in Blender will face X in game",
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
    
    maintain_marker_axis: bpy.props.BoolProperty(
        name="Maintain Marker Axis",
        options=set(),
        description="Maintains the forward direction of markers during scene transform. Don't use this if you're re-importing existing assets and rely on marker positions exactly matching",
        default=True,
    )
    
    selected_only: bpy.props.BoolProperty(
        name="Selected Objects Only",
        description="Transforms selected objects only",
        options=set(),
    )
    
    animations: bpy.props.EnumProperty(
        name="Animations",
        description="Animations to include in transform",
        options=set(),
        items=[
            ("all", "All", ""),
            ("active", "Active", ""),
            ("none", "None", ""),
        ]
    )
    
    exclude_scale_models: bpy.props.BoolProperty(
        name="Exclude Scale Models",
        description="Excludes Halo scale models from transform so that size differences can more easily be compared",
        options=set(),
        default=True,
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
        # animation_index = None
        # current_frame = int(context.scene.frame_current)
        context.scene.tool_settings.use_keyframe_insert_auto = False
        # if bpy.ops.nwo.unlink_animation.poll():
        #     animation_index = int(context.scene.nwo.active_action_index)
        #     bpy.ops.nwo.unlink_animation()
        nwo_utils.set_object_mode(context)
        nwo_utils.deselect_all_objects()
        objects_to_transform = old_selection if self.selected_only else None
        actions_to_transform = None
        if self.animations != "all":
            active_action_index = context.scene.nwo.active_action_index
            if self.animations == 'active' and active_action_index >= 0:
                actions_to_transform = [bpy.data.actions[active_action_index]]
            else:
                actions_to_transform = []
                
        nwo_utils.transform_scene(context, self.scale_factor, self.rotation, context.scene.nwo.forward_direction, self.forward, keep_marker_axis=self.maintain_marker_axis, objects=objects_to_transform, actions=actions_to_transform, exclude_scale_models=self.exclude_scale_models)

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
        context.scene.nwo.maintain_marker_axis = self.maintain_marker_axis
        
        # if animation_index:
        #     context.scene.nwo.active_action_index = animation_index
        #     context.scene.frame_current = current_frame
        return {"FINISHED"}
    
    def invoke(self, context: bpy.types.Context, _):
        self.forward = context.scene.nwo.forward_direction
        self.maintain_marker_axis = context.scene.nwo.maintain_marker_axis
        return context.window_manager.invoke_props_dialog(self)
            
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'scale', text='New Scale')
        if self.scale == 'custom':
            layout.prop(self, 'scale_factor', text='Scale Factor')
        layout.prop(self, 'forward')
        layout.prop(self, 'rotation')
        layout.prop(self, 'maintain_marker_axis')
        layout.label(text="Scope")
        layout.prop(self, 'selected_only')
        layout.prop(self, 'animations')
        layout.prop(self, 'exclude_scale_models')

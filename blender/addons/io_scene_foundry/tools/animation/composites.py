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

from pathlib import Path
import bpy

from io_scene_foundry.icons import get_icon_id
from io_scene_foundry.utils import nwo_utils

class NWO_UL_AnimationComposites(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            # row.alignment = 'LEFT'
            layout.prop(item, 'name', emboss=False, text="")
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationCompositeAdd(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_composite_add"
    bl_options = {'UNDO'}
    
    mode: bpy.props.StringProperty(
        name="Mode",
        description="The mode the object must be in to use this animation. Use 'any' for all modes. Other valid inputs inlcude but are not limited to: 'crouch' when a unit is crouching,  'combat' when a unit is in combat. Modes can also refer to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more information refer to existing model_animation_graph tags. Can be empty",
    )

    weapon_class: bpy.props.StringProperty(
        name="Weapon Class",
        description="The weapon class this unit must be holding to use this animation. Weapon class is defined per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty",
    )
    state: bpy.props.EnumProperty(
        name="State",
        items=[
            ("locomote", "locomote", ""),
            ("aim_locomote_up", "aim_locomote_up", ""),
            ("turn_left_composite", "turn_left_composite", ""),
            ("turn_right_composite", "turn_right_composite", ""),
            ("jump", "jump", ""),
        ]
    )
    
    def build_name(self):
        name = ""
        name += self.mode.strip() if self.mode.strip() else "any"
        name += " "
        name += self.weapon_class.strip() if self.weapon_class.strip() else "any"
        name += " "
        name += self.state
        return name

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_composites
        entry = table.add()
        entry.name = self.build_name()
        nwo.animation_composites_active_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text="Animation Name")
        col = layout.column()
        col.use_property_split = True
        col.prop(self, "mode")
        col.prop(self, "weapon_class")
        col.prop(self, "state", text="State")
    
class NWO_OT_AnimationCompositeRemove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_composite_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_composites
        table.remove(nwo.animation_composites_active_index)
        if nwo.animation_composites_active_index > len(table) - 1:
            nwo.animation_composites_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationCompositeMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_composite_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_composites
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = nwo.animation_composites_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        nwo.animation_composites_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
def create_template_composite_xml(name: str, preset: str):
    name = name.split()[-1]
    asset_dir, asset_name = nwo_utils.get_asset_info()
    composite_dir = Path(nwo_utils.get_tags_path(), asset_dir, asset_name, "animations", "composites")
    if not composite_dir.exists():
        composite_dir.mkdir(parents=True, exist_ok=True)
    
    composite_file = Path(composite_dir, name).with_suffix(".composite.xml")
    if not composite_file.exists():
        
        template_composite_file = Path(nwo_utils.addon_root(), "composites", preset).with_suffix(".composite.xml")
        with open(template_composite_file, 'r') as template_file:
            template_data = template_file.read()
            
        with open(composite_file, 'w') as file:
            file.write(template_data)
            
class NWO_UL_AnimationBlendAxis(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            # row.alignment = 'LEFT'
            layout.prop(item, 'name')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationBlendAxisAdd(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_blend_axis_add"
    bl_options = {'UNDO'}
    
    blend_axis: bpy.props.EnumProperty(
        name="Blend Axis",
        items=[
            ("movement_angles", "Movement Angles", ""), # linear_movement_angle get_move_angle
            ("movement_speed", "Movement Speed", ""), # linear_movement_speed get_move_speed
            ("turn_rate", "Turn Rate", ""), # average_angular_rate get_turn_rate
            ("vertical", "Vertical", ""), # translation_offset_z get_destination_vertical
            ("horizontal", "Horizontal", ""), # translation_offset_horizontal get_destination_forward
        ]
    )
    
    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        table = composite.blend_axis
        entry = table.add()
        entry.name = self.blend_axis
        composite.blend_axis_active_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, 'blend_axis')
        
class NWO_OT_AnimationBlendAxisRemove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_blend_axis_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        table = composite.blend_axis
        table.remove(composite.blend_axis_active_index)
        if composite.blend_axis_active_index > len(table) - 1:
            composite.blend_axis_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationBlendAxisMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_blend_axis_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        composite = context.scene.nwo.animation_composites[context.scene.nwo.animation_composites_active_index]
        table = composite.blend_axis
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = composite.blend_axis_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        composite.blend_axis_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
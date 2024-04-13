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
            layout.prop(item, 'name')
            layout.prop(item, 'overlay', icon='CHECKBOX_HLT' if item.overlay else 'CHECKBOX_DEHLT')
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationCompositeAdd(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_composite_add"
    bl_options = {'UNDO'}
    
    def update_presets(self, context):
        if self.presets != 'none':
            self.name = self.presets
    
    preset: bpy.props.EnumProperty(
        name="Preset",
        description="Preset composite animations. Will generate an XML template to use",
        update=update_presets,
        items=[
            ('combat any locomote', 'Locomote', ''),
            ('crouch any locomote', 'Crouch Locomote', ''),
            ('combat any aim_locomote_up', 'Aim Locomote', ''),
            ('crouch any aim_locomote_up', 'Crouch Aim Locomote', ''),
            ('combat rifle locomote', 'Rifle Locomote', ''),
            ('combat turret locomote', 'Turret Locomote', ''),
            ('sprint any locomote', 'Sprint Locomote', ''),
            ('combat any turn_left_composite', 'Turn Left', ''),
            ('combat any turn_right_composite', 'Turn Right', ''),
            ('combat any jump', 'Jump', ''),
            ('none', 'No Preset', '')
        ]
    )
    
    name: bpy.props.StringProperty(
        name="Name",
        description="The name of this animation. Automically updated on choosing a different preset"
    )

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_composites
        entry = table.add()
        entry.name = self.name
        nwo.animation_composites_active_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=800)
    
    def draw(self, context):
        layout = self.layout
        split = layout.split()
        col1 = split.column(heading="Source")
        col3 = split.column(heading="Copy")
        col1.prop(self, "source_mode", text=f"Mode")
        col3.prop(self, "copy_mode", text="")
        col1.prop(self, "source_weapon_class", text="Weapon Class")
        col3.prop(self, "copy_weapon_class", text="")
        col1.prop(self, "source_weapon_type", text="Weapon Type")
        col3.prop(self, "copy_weapon_type", text="")
        col1.prop(self, "source_set", text="Set")
        col3.prop(self, "copy_set", text="")
    
class NWO_OT_AnimationCompositeRemove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_composite_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_copies
        table.remove(nwo.animation_copies_active_index)
        if nwo.animation_copies_active_index > len(table) - 1:
            nwo.animation_copies_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationCompositeMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_composite_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_copies
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = nwo.animation_copies_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        nwo.animation_copies_active_index = to_index
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
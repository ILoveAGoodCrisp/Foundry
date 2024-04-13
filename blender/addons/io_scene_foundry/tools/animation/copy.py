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

from io_scene_foundry.icons import get_icon_id

class NWO_UL_AnimationCopies(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            # row.alignment = 'LEFT'
            layout.label(text=f"{item.source_name} -> {item.name}", icon_value=get_icon_id("animation_copy"))
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_AnimationCopyAdd(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_copy_add"
    bl_options = {'UNDO'}
    
    source_mode: bpy.props.StringProperty(name="Source Mode", default="")
    source_weapon_class: bpy.props.StringProperty(name="Source Weapon Class")
    source_weapon_type: bpy.props.StringProperty(name="Source Weapon Type")
    source_set: bpy.props.StringProperty(name="Source Set")
    
    copy_mode: bpy.props.StringProperty(name="Copy Mode")
    copy_weapon_class: bpy.props.StringProperty(name="Copy Weapon Class")
    copy_weapon_type: bpy.props.StringProperty(name="Copy Weapon Type")
    copy_set: bpy.props.StringProperty(name="Copy Set")
    
    def get_names(self) -> tuple[str, str]:
        source_name = ""
        copy_name = ""
        source_name += self.source_mode.strip() if self.source_mode.strip() else "any"
        source_name += " "
        source_name += self.source_weapon_class.strip() if self.source_weapon_class.strip() else "any"
        source_name += " "
        source_name += self.source_weapon_type.strip() if self.source_weapon_type.strip() else "any"
        source_name += " "
        source_name += self.source_set.strip() if self.source_set.strip() else "any"
        
        copy_name += self.copy_mode.strip() if self.copy_mode.strip() else "any"
        copy_name += " "
        copy_name += self.copy_weapon_class.strip() if self.copy_weapon_class.strip() else "any"
        copy_name += " "
        copy_name += self.copy_weapon_type.strip() if self.copy_weapon_type.strip() else "any"
        copy_name += " "
        copy_name += self.copy_set.strip() if self.copy_set.strip() else "any"
        
        return source_name, copy_name

    def execute(self, context):
        source_name, copy_name = self.get_names()
        if source_name == copy_name:
            self.report({'WARNING'}, "Source name and copy name cannot match")
            return {'CANCELLED'}
        
        nwo = context.scene.nwo
        table = nwo.animation_copies
        entry = table.add()
        entry.name = copy_name
        entry.source_name = source_name
        nwo.animation_copies_active_index = len(table) - 1
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
    
class NWO_OT_AnimationCopyRemove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_copy_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.animation_copies
        table.remove(nwo.animation_copies_active_index)
        if nwo.animation_copies_active_index > len(table) - 1:
            nwo.animation_copies_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_AnimationCopyMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_copy_move"
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
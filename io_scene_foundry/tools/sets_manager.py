# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
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

'''Handles bpy operators and functions for the Sets Manager panel'''

import bpy

# REGIONS
class NWO_RegionAdd(bpy.types.Operator):
    bl_label = "Add Region"
    bl_idname = "nwo.region_add"
    bl_description = "Add a new Region"
    bl_options = {'REGISTER', 'UNDO'}

    set_object_region: bpy.props.BoolProperty()
    name: bpy.props.StringProperty(name="Name")

    def execute(self, context):
        nwo = context.scene.nwo
        region = nwo.regions_table.add()
        region.name = self.name
        nwo.regions_table_active_index = len(nwo.regions_table) - 1
        if self.set_object_region:
            ob = context.object
            if ob:
                ob.nwo.region_name_ui = self.name
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.activate_init = True
        layout.prop(self, "name", text="Name")

class NWO_RegionRemove(bpy.types.Operator):
    bl_label = "Remove Region"
    bl_idname = "nwo.region_remove"
    bl_description = "Removes the active Region"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return len(context.scene.nwo.regions_table) > 1
    
    def execute(self, context):
        nwo = context.scene.nwo
        nwo.regions_table.remove(nwo.regions_table[nwo.regions_table_active_index])
        if nwo.regions_table_active_index > len(nwo.regions_table) - 1:
            nwo.regions_table_active_index += -1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_RegionMove(bpy.types.Operator):
    bl_label = "Move Region"
    bl_idname = "nwo.region_move"
    bl_description = "Moves the active Region"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return len(context.scene.nwo.regions_table) > 1
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        delta = {"down": 1, "up": -1,}[self.direction]
        nwo = context.scene.nwo
        current_index = nwo.regions_table_active_index
        to_index = (current_index + delta) % len(nwo.regions_table)
        nwo.regions_table.move(current_index, to_index)
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_RegionAssignSingle(bpy.types.Operator):
    bl_label = "Assign Region to Object"
    bl_idname = "nwo.region_assign_single"
    bl_description = "Assigns the active Region to the active Object"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.scene.nwo.regions_table and context.object
    
    
    name: bpy.props.StringProperty(
        name="Region",
    )
    
    def execute(self, context):
        nwo = context.object.nwo
        nwo.region_name_ui = self.name
        return {'FINISHED'}
    
class NWO_RegionHide(bpy.types.Operator):
    bl_label = "Hide Region"
    bl_idname = "nwo.region_hide"
    bl_description = "Hides/Unhides the active Region"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.scene.nwo.regions_table
    
    region: bpy.props.StringProperty()
    
    def execute(self, context):
        for r in context.scene.nwo.regions_table:
            if r.name == self.region:
                r.hidden = not r.hidden
                break
        else:
            self.report({'ERROR'}, "Somehow found no matching regions")
            return {'CANCELLED'}
        scene_objects = context.scene.objects
        region_objects = [ob for ob in scene_objects if ob.nwo.region_name_ui == self.region]
        [ob.hide_set(r.hidden) for ob in region_objects]
        return {'FINISHED'}

# PERMUTATIONS
class NWO_UL_Permutations(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            layout.label(text=item.name)
        else:
            layout.label(text="", translate=False, icon_value=icon)

# BSPS
class NWO_UL_BSPs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            layout.label(text=item.name)
        else:
            layout.label(text="", translate=False, icon_value=icon)

# GLOBAL MATERIALS
class NWO_UL_GlobalMaterials(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            layout.label(text=item.name)
        else:
            layout.label(text="", translate=False, icon_value=icon)
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

from io_scene_foundry.utils.nwo_utils import true_permutation, true_region

# Parent Classes
class TableEntryAdd(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}

    set_object_prop: bpy.props.BoolProperty()
    name: bpy.props.StringProperty(name="Name")

    def execute(self, context):
        name = self.name.lower()
        nwo = context.scene.nwo
        table = getattr(nwo, self.table_str)
        all_names = [entry.name for entry in table]

        if not name:
            self.report({'WARNING'}, f"{self.type_str} name cannot be empty")
            return {'CANCELLED'}
        elif len(name) > 128:
            self.report({'WARNING'}, f"{self.type_str} name has a maximum of 128 characters")
            return {'CANCELLED'}
        elif name in all_names:
            self.report({'WARNING'}, f"{self.type_str} name already exists")
            return {'CANCELLED'}
    
        entry = table.add()
        entry.name = name
        setattr(nwo, f"{self.table_str}_active_index", len(table) - 1)
        if self.set_object_prop:
            ob = context.object
            if ob: setattr(ob.nwo, self.ob_prop_str, name)

        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.activate_init = True
        layout.prop(self, "name", text="Name")

class TableEntryRemove(bpy.types.Operator):
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = context.scene.nwo
        table = getattr(nwo, self.table_str)
        table_active_index_str = f"{self.table_str}_active_index"
        table_active_index = getattr(nwo, table_active_index_str)
        entry = table[table_active_index]
        scene_objects = context.scene.objects
        entry_objects = [ob for ob in scene_objects if getattr(ob.nwo, self.ob_prop_str) == entry.name]
        table.remove(table_active_index)
        if table_active_index > len(table) - 1:
            setattr(nwo, table_active_index_str, table_active_index - 1)
        new_entry_name = table[0].name
        for ob in entry_objects:
            setattr(ob.nwo, self.ob_prop_str, new_entry_name)
        context.area.tag_redraw()
        return {'FINISHED'}
    
class TableEntryMove(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        table = getattr(nwo, self.table_str)
        table_active_index_str = f"{self.table_str}_active_index"
        table_active_index = getattr(nwo, table_active_index_str)
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = table_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        setattr(nwo, table_active_index_str, to_index)

        context.area.tag_redraw()
        return {'FINISHED'}

class TableEntryAssignSingle(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    name: bpy.props.StringProperty(
        name="Name",
    )
    
    def execute(self, context):
        nwo = context.object.nwo
        setattr(nwo, self.ob_prop_str, self.name)
        return {'FINISHED'}
    
class TableEntryAssign(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    name: bpy.props.StringProperty(
        name="Name",
    )
    
    def execute(self, context):
        sel_obs = context.selected_objects
        for ob in sel_obs:
            setattr(ob.nwo, self.ob_prop_str, self.name)
        return {'FINISHED'}
    
class TableEntrySelect(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    select: bpy.props.BoolProperty()
    
    def execute(self, context):
        nwo = context.scene.nwo
        table = getattr(context.scene.nwo, self.table_str)
        table_active_index_str = f"{self.table_str}_active_index"
        table_active_index = getattr(nwo, table_active_index_str)
        entry = table[table_active_index]
        available_objects = context.view_layer.objects
        entry_objects = [ob for ob in available_objects if true_table_entry(ob.nwo, self.ob_prop_str) == entry.name]
        [ob.select_set(self.select) for ob in entry_objects]
        return {'FINISHED'}
    
class TableEntryRename(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    
    new_name: bpy.props.StringProperty(
        name="New Name",
    )
    
    def execute(self, context):
        nwo = context.scene.nwo
        new_name = self.new_name.lower()
        table = getattr(nwo, self.table_str)
        table_active_index_str = f"{self.table_str}_active_index"
        table_active_index = getattr(nwo, table_active_index_str)
        all_names = [entry.name for entry in table]

        if not new_name:
            self.report({'WARNING'}, f"{self.type_str} name cannot be empty")
            return {'CANCELLED'}
        elif len(new_name) > 128:
            self.report({'WARNING'}, f"{self.type_str} name has a maximum of 128 characters")
            return {'CANCELLED'}
        elif new_name in all_names:
            self.report({'WARNING'}, f"{self.type_str} name already exists")
            return {'CANCELLED'}
        
        entry = table[table_active_index]
        scene_objects = context.scene.objects
        entry_objects = [ob for ob in scene_objects if getattr(ob.nwo, self.ob_prop_str) == entry.name]
        entry.name = new_name
        for ob in entry_objects:
            setattr(ob.nwo, self.ob_prop_str, new_name)

        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.activate_init = True
        layout.prop(self, "new_name", text="New Name")

class TableEntryHide(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    entry_name: bpy.props.StringProperty()
    
    def execute(self, context):
        nwo = context.scene.nwo
        table = getattr(nwo, self.table_str)
        entry = get_entry(table, self.entry_name)
        should_hide = entry.hidden
        available_objects = context.view_layer.objects
        entry_objects = [ob for ob in available_objects if true_table_entry(ob.nwo, self.ob_prop_str) == entry.name]
        [ob.hide_set(should_hide) for ob in entry_objects]
        return {'FINISHED'}
    
class TableEntryHideSelect(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    entry_name: bpy.props.StringProperty()
    
    def execute(self, context):
        nwo = context.scene.nwo
        table = getattr(nwo, self.table_str)
        entry = get_entry(table, self.entry_name)
        should_hide_select = entry.hide_select
        available_objects = context.view_layer.objects
        entry_objects = [ob for ob in available_objects if true_table_entry(ob.nwo, self.ob_prop_str) == entry.name]
        for ob in entry_objects:
            ob.hide_select = should_hide_select
        return {'FINISHED'}

# REGIONS
class NWO_RegionAdd(TableEntryAdd):
    bl_label = "Add Region"
    bl_idname = "nwo.region_add"
    bl_description = "Add a new Region"

    def __init__(self):
        self.type_str = "Region"
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

class NWO_RegionRemove(TableEntryRemove):
    bl_label = "Remove Region"
    bl_idname = "nwo.region_remove"
    bl_description = "Removes the active Region"

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo.regions_table) > 1

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"
    
class NWO_RegionMove(TableEntryMove):
    bl_label = "Move Region"
    bl_idname = "nwo.region_move"
    bl_description = "Moves the active Region"

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo.regions_table) > 1

    def __init__(self):
        self.table_str = "regions_table"
    
class NWO_RegionAssignSingle(TableEntryAssignSingle):
    bl_label = "Assign Region to Object"
    bl_idname = "nwo.region_assign_single"
    bl_description = "Assigns the active Region to the active Object"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table and context.object

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"
    
class NWO_RegionAssign(TableEntryAssign):
    bl_label = "Assign Region to Selected Objects"
    bl_idname = "nwo.region_assign"
    bl_description = "Assigns the active Region to selected Objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table and context.selected_objects

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"
    
class NWO_RegionSelect(TableEntrySelect):
    bl_label = "Select Region"
    bl_idname = "nwo.region_select"
    bl_description = "Selects/Deselects the active Region"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"
    
class NWO_RegionRename(TableEntryRename):
    bl_label = "Rename Region"
    bl_idname = "nwo.region_rename"
    bl_description = "Renames the active Region and updates scene objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table

    def __init__(self):
        self.type_str = "Region"
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"
    
class NWO_RegionHide(TableEntryHide):
    bl_label = "Hide Region"
    bl_idname = "nwo.region_hide"
    bl_description = "Hides/Unhides the active Region"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

class NWO_RegionHideSelect(TableEntryHideSelect):
    bl_label = "Hide Region Selection"
    bl_idname = "nwo.region_hide_select"
    bl_description = "Disable selection of the active Region objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

# PERMUTATIONS
class NWO_PermutationAdd(TableEntryAdd):
    bl_label = "Add Permutation"
    bl_idname = "nwo.permutation_add"
    bl_description = "Add a new Permutation"

    def __init__(self):
        self.type_str = "Permutation"
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

class NWO_PermutationRemove(TableEntryRemove):
    bl_label = "Remove Permutation"
    bl_idname = "nwo.permutation_remove"
    bl_description = "Removes the active Permutation"

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo.permutations_table) > 1

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"
    
class NWO_PermutationMove(TableEntryMove):
    bl_label = "Move Permutation"
    bl_idname = "nwo.permutation_move"
    bl_description = "Moves the active Permutation"

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo.permutations_table) > 1

    def __init__(self):
        self.table_str = "permutations_table"
    
class NWO_PermutationAssignSingle(TableEntryAssignSingle):
    bl_label = "Assign Permutation to Object"
    bl_idname = "nwo.permutation_assign_single"
    bl_description = "Assigns the active Permutation to the active Object"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table and context.object
    
    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"
    
class NWO_PermutationAssign(TableEntryAssign):
    bl_label = "Assign Permutation to Selected Objects"
    bl_idname = "nwo.permutation_assign"
    bl_description = "Assigns the active Permutation to selected Objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table and context.selected_objects

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"
    
class NWO_PermutationSelect(TableEntrySelect):
    bl_label = "Select Permutation"
    bl_idname = "nwo.permutation_select"
    bl_description = "Selects/Deselects the active Permutation"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"
    
class NWO_PermutationRename(TableEntryRename):
    bl_label = "Permutation Region"
    bl_idname = "nwo.permutation_rename"
    bl_description = "Renames the active Permutation and updates scene objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table

    def __init__(self):
        self.type_str = "Permutation"
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"
    
class NWO_PermutationHide(TableEntryHide):
    bl_label = "Hide Permutation"
    bl_idname = "nwo.permutation_hide"
    bl_description = "Hides/Unhides the active Permutation"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

class NWO_PermutationHideSelect(TableEntryHideSelect):
    bl_label = "Hide Permutation Selection"
    bl_idname = "nwo.permutation_hide_select"
    bl_description = "Disable selection of the active Permutation objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"


# HELPER FUNCTIONS

def get_entry(table, entry_name):
    for entry in table:
        if entry.name == entry_name:
            return entry
        
def true_table_entry(nwo, ob_prop_str):
    if ob_prop_str == "region_name_ui":
        return true_region(nwo)
    elif ob_prop_str == "permutation_name_ui":
        return true_permutation(nwo)

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
        entry.old = name
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
        old_name = getattr(nwo, self.ob_prop_str)
        setattr(nwo, self.ob_prop_str, self.name)
        if self.ob_prop_str == "region_name_ui" and nwo.seam_back_ui == self.name:
            nwo.seam_back_ui = old_name
        return {'FINISHED'}
    
class TableEntryAssign(bpy.types.Operator):
    bl_options = {'UNDO'}
    
    name: bpy.props.StringProperty(
        name="Name",
    )
    
    def execute(self, context):
        sel_obs = context.selected_objects
        for ob in sel_obs:
            old_name = getattr(ob.nwo, self.ob_prop_str)
            setattr(ob.nwo, self.ob_prop_str, self.name)
            if self.ob_prop_str == "region_name_ui" and ob.nwo.seam_back_ui == self.name:
                ob.nwo.seam_back_ui = old_name
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

    index: bpy.props.IntProperty()
    
    def execute(self, context):
        nwo = context.scene.nwo
        new_name = self.new_name.lower()
        table = getattr(nwo, self.table_str)
        table_active_index = self.index
        all_names = [entry.name for entry in table]
        all_names.pop(table_active_index)
        entry = table[table_active_index]

        if not entry.old:
            entry.old = 'default'

        if not new_name:
            self.report({'WARNING'}, f"{self.type_str} name cannot be empty")
            entry.name = entry.old
            return {'CANCELLED'}
        elif len(new_name) > 128:
            self.report({'WARNING'}, f"{self.type_str} name has a maximum of 128 characters")
            entry.name = entry.old
            return {'CANCELLED'}
        elif new_name in all_names:
            self.report({'WARNING'}, f"{self.type_str} name already exists")
            entry.name = entry.old
            return {'CANCELLED'}
        
        scene_objects = context.scene.objects
        entry_objects = [ob for ob in scene_objects if getattr(ob.nwo, self.ob_prop_str) == entry.name]
        old_name = str(entry.old)
        entry.old = new_name
        entry.name = new_name
        for ob in entry_objects:
            setattr(ob.nwo, self.ob_prop_str, new_name)
        scene_collections = bpy.data.collections
        current_type = self.type_str.lower()
        for coll in scene_collections:
            c_parts = coll.name.split('::')
            if not c_parts or len(c_parts) != 2: continue
            if coll.nwo.type != current_type or c_parts[1] != old_name: continue
            coll.name = current_type + '::' + self.new_name

        if hasattr(context.area, 'tag_redraw'):
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
    bl_label = ""
    bl_idname = "nwo.region_add"
    bl_description = "Add a new Region"

    def __init__(self):
        self.type_str = "Region"
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Add a new BSP"
        else:
            return "Add a new Region"

class NWO_RegionRemove(TableEntryRemove):
    bl_label = ""
    bl_idname = "nwo.region_remove"
    bl_description = "Removes the active Region"

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo.regions_table) > 1

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Removes the active BSP"
        else:
            return "Removes the active Region"
    
class NWO_RegionMove(TableEntryMove):
    bl_label = ""
    bl_idname = "nwo.region_move"
    bl_description = "Moves the active Region"

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo.regions_table) > 1

    def __init__(self):
        self.table_str = "regions_table"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Moves the active BSP"
        else:
            return "Moves the active Region"
    
class NWO_RegionAssignSingle(TableEntryAssignSingle):
    bl_label = ""
    bl_idname = "nwo.region_assign_single"
    bl_description = "Assigns the active Region to the active Object"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table and context.object

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Assigns the selected BSP to the active Object"
        else:
            return "Assigns the selected Region to the active Object"
    
class NWO_RegionAssign(TableEntryAssign):
    bl_label = ""
    bl_idname = "nwo.region_assign"
    bl_description = "Assigns the active Region to selected Objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table and context.selected_objects

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Assigns the active BSP to selected Objects"
        else:
            return "Assigns the active Region to selected Objects"
    
class NWO_RegionSelect(TableEntrySelect):
    bl_label = ""
    bl_idname = "nwo.region_select"
    bl_description = "Selects/Deselects the active Region"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            if properties.select:
                return "Selects the active BSP"
            else:
                return "Deselects the active BSP"
        else:
            if properties.select:
                return "Selects the active Region"
            else:
                return "Deselects the active Region"
    
class NWO_RegionRename(TableEntryRename):
    bl_label = ""
    bl_idname = "nwo.region_rename"
    bl_description = "Renames the active Region and updates scene objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table

    def __init__(self):
        self.type_str = "Region"
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Renames the active BSP and updates scene objects"
        else:
            return "Renames the active Region and updates scene objects"
    
class NWO_RegionHide(TableEntryHide):
    bl_label = ""
    bl_idname = "nwo.region_hide"
    bl_description = "Hides/Unhides the active Region"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            if properties.hidden:
                return "Unhides the active BSP"
            else:
                return "Hides the active BSP"
        else:
            if properties.select:
                return "Unhides the active Region"
            else:
                return "Hides the active Region"

class NWO_RegionHideSelect(TableEntryHideSelect):
    bl_label = ""
    bl_idname = "nwo.region_hide_select"
    bl_description = "Disables selection of the active Region objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "region_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            if properties.hide_select:
                return "Enables selection of the active BSP objects"
            else:
                return "Disables selection of the active BSP objects"
        else:
            if properties.select:
                return "Enables selection of the active Region objects"
            else:
                return "Disables selection of the active Region objects"

# PERMUTATIONS
class NWO_PermutationAdd(TableEntryAdd):
    bl_label = ""
    bl_idname = "nwo.permutation_add"
    bl_description = "Add a new Permutation"

    def __init__(self):
        self.type_str = "Permutation"
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Add a new BSP Category"
        else:
            return "Add a new Permutation"

class NWO_PermutationRemove(TableEntryRemove):
    bl_label = ""
    bl_idname = "nwo.permutation_remove"
    bl_description = "Removes the active Permutation"

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo.permutations_table) > 1

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Removes the active BSP Category"
        else:
            return "Removes the active Permutation"
    
class NWO_PermutationMove(TableEntryMove):
    bl_label = ""
    bl_idname = "nwo.permutation_move"
    bl_description = "Moves the active Permutation"

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo.permutations_table) > 1

    def __init__(self):
        self.table_str = "permutations_table"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Moves the active BSP Category"
        else:
            return "Moves the active Permutation"
    
class NWO_PermutationAssignSingle(TableEntryAssignSingle):
    bl_label = ""
    bl_idname = "nwo.permutation_assign_single"
    bl_description = "Assigns the selected Permutation to the active Object"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table and context.object
    
    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Assigns the selected BSP Category to the active Object"
        else:
            return "Assigns the selected Permutation to the active Object"
    
class NWO_PermutationAssign(TableEntryAssign):
    bl_label = ""
    bl_idname = "nwo.permutation_assign"
    bl_description = "Assigns the active Permutation to selected Objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table and context.selected_objects

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Assigns the active BSP Category to selected Objects"
        else:
            return "Assigns the active Permutation to selected Objects"
    
class NWO_PermutationSelect(TableEntrySelect):
    bl_label = ""
    bl_idname = "nwo.permutation_select"
    bl_description = "Selects/Deselects the active Permutation"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            if properties.select:
                return "Selects the active BSP Category"
            else:
                return "Deselects the active BSP Category"
        else:
            if properties.select:
                return "Selects the active Permutation"
            else:
                return "Deselects the active Permutation"
    
class NWO_PermutationRename(TableEntryRename):
    bl_label = ""
    bl_idname = "nwo.permutation_rename"
    bl_description = "Renames the active Permutation and updates scene objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table

    def __init__(self):
        self.type_str = "Permutation"
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            return "Renames the active BSP Category and updates scene objects"
        else:
            return "Renames the active Permutation and updates scene objects"
    
class NWO_PermutationHide(TableEntryHide):
    bl_label = ""
    bl_idname = "nwo.permutation_hide"
    bl_description = "Hides/Unhides the active Permutation"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            if properties.hide_select:
                return "Enables selection of the active BSP Category objects"
            else:
                return "Disables selection of the active BSP Category objects"
        else:
            if properties.select:
                return "Enables selection of the active Permutation objects"
            else:
                return "Disables selection of the active Permutation objects"

class NWO_PermutationHideSelect(TableEntryHideSelect):
    bl_label = ""
    bl_idname = "nwo.permutation_hide_select"
    bl_description = "Disable selection of the active Permutation objects"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.permutations_table

    def __init__(self):
        self.table_str = "permutations_table"
        self.ob_prop_str = "permutation_name_ui"

    @classmethod
    def description(cls, context, properties) -> str:
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        if is_scenario:
            if properties.hide_select:
                return "Enables selection of the active BSP Category objects"
            else:
                return "Disables selection of the active BSP Category objects"
        else:
            if properties.select:
                return "Enables selection of the active Permutation objects"
            else:
                return "Disables selection of the active Permutation objects"


class NWO_SeamAssignSingle(TableEntryAssignSingle):
    bl_label = ""
    bl_idname = "nwo.seam_backface_assign_single"
    bl_description = "Sets the selected BSP as this seam's backfacing BSP reference"

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.regions_table and context.object

    def __init__(self):
        self.table_str = "regions_table"
        self.ob_prop_str = "seam_back_ui"

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

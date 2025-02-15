"""UI for the sets manager"""

import bpy

from ...constants import VALID_MESHES

from ... import utils
from ...icons import get_icon_id

class NWO_OT_SwapMaterial(bpy.types.Operator):
    bl_idname = "nwo.swap_material"
    bl_label = "Swap Material"
    bl_description = "Switches the source and destination material on all objects with the current permutation"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        if not permutation.clones:
            return False
        clone = permutation.clones[permutation.active_clone_index]
        if not clone.material_overrides:
            return False
        
        if not clone.material_overrides:
            return False
        
        override = clone.material_overrides[clone.active_material_override_index]
        
        return override.source_material is not None and override.destination_material is not None

    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        clone = permutation.clones[permutation.active_clone_index]
        override = clone.material_overrides[clone.active_material_override_index]
        
        source = override.source_material
        dest = override.destination_material
        
        pname = permutation.name
        
        for ob in bpy.data.objects:
            if ob.type not in VALID_MESHES:
                continue
            if utils.true_permutation(ob.nwo) == pname:
                for slot in ob.material_slots:
                    if slot.material is source:
                        slot.material = dest
                        
                
        override.source_material = dest
        override.destination_material = source
        
        for other_clone in permutation.clones:
            if other_clone is clone:
                continue
            for other_override in other_clone.material_overrides:
                if other_override.source_material is source:
                    other_override.source_material = dest
        
        return {"FINISHED"}


class NWO_UL_MaterialOverrides(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        source = item.source_material
        destination = item.destination_material
        if source is None or destination is None:
            layout.label(text="INVALID", icon='ERROR')
        else:
            layout.label(text=f"{source.name} --> {destination.name}", icon='MATERIAL')
            layout.prop(item, "enabled", icon='CHECKBOX_HLT' if item.enabled else 'CHECKBOX_DEHLT', text="", emboss=False)
            
class NWO_OT_AddMaterialOverride(bpy.types.Operator):
    bl_label = "Add"
    bl_idname = 'nwo.add_material_override'
    bl_description = "Add a new material override clone"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        clone = permutation.clones[permutation.active_clone_index]
        clone.material_overrides.add()
        clone.active_material_override_index = len(clone.material_overrides) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_RemoveMaterialOverride(bpy.types.Operator):
    bl_idname = "nwo.remove_material_override"
    bl_label = "Remove"
    bl_description = "Remove a material override from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        return permutation.clones and permutation.active_clone_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        clone = permutation.clones[permutation.active_clone_index]
        index = clone.active_material_override_index
        clone.material_overrides.remove(index)
        if clone.active_material_override_index > len(clone.material_overrides) - 1:
            clone.active_material_override_index -= 1
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_MoveMaterialOverride(bpy.types.Operator):
    bl_idname = "nwo.move_material_override"
    bl_label = "Move"
    bl_description = "Moves the material override up/down the list"
    bl_options = {"UNDO"}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        clone = permutation.clones[permutation.active_clone_index]
        overrides = clone.material_overrides
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = permutation.active_clone_index
        to_index = (current_index + delta) % len(overrides)
        overrides.move(current_index, to_index)
        clone.active_material_override_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}

class NWO_UL_PermutationClones(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, "name", text="", emboss=False, icon='COPY_ID')
        layout.prop(item, "enabled", icon='CHECKBOX_HLT' if item.enabled else 'CHECKBOX_DEHLT', text="", emboss=False)
        
class NWO_OT_AddPermutationClone(bpy.types.Operator):
    bl_label = "Add"
    bl_idname = 'nwo.add_permutation_clone'
    bl_description = "Add a new permutation clone"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        clone = permutation.clones.add()
        permutation.active_clone_index = len(permutation.clones) - 1
        clone.name = f"{permutation.name}_clone"
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_RemovePermutationClone(bpy.types.Operator):
    bl_idname = "nwo.remove_permutation_clone"
    bl_label = "Remove"
    bl_description = "Remove a permutation clone from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        return permutation.clones and permutation.active_clone_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        index = permutation.active_clone_index
        permutation.clones.remove(index)
        if permutation.active_clone_index > len(permutation.clones) - 1:
            permutation.active_clone_index -= 1
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_MovePermutationClone(bpy.types.Operator):
    bl_idname = "nwo.move_permutation_clone"
    bl_label = "Move"
    bl_description = "Moves the permutation clone up/down the list"
    bl_options = {"UNDO"}
    
    direction: bpy.props.StringProperty()
    
    @classmethod
    def poll(cls, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        return permutation.clones and permutation.active_clone_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        clones = permutation.clones
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = permutation.active_clone_index
        to_index = (current_index + delta) % len(clones)
        clones.move(current_index, to_index)
        permutation.active_clone_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}

class NWO_RegionsContextMenu(bpy.types.Menu):
    bl_label = "Regions Context Menu"
    bl_idname = "NWO_MT_RegionsContext"

    @classmethod
    def poll(self, context):
        return context.scene.nwo.regions_table
    
    def draw(self, context):
        pass

class NWO_PermutationsContextMenu(bpy.types.Menu):
    bl_label = "Permutations Context Menu"
    bl_idname = "NWO_MT_PermutationsContext"

    @classmethod
    def poll(self, context):
        return context.scene.nwo.permutations_table
    
    def draw(self, context):
        pass

class NWO_UL_Regions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            layout.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("region"))
            layout.prop(item, "hidden", text="", icon='HIDE_ON' if item.hidden else 'HIDE_OFF', emboss=False)
            layout.prop(item, "hide_select", text="", icon='RESTRICT_SELECT_ON' if item.hide_select else 'RESTRICT_SELECT_OFF', emboss=False)
            if data.asset_type in ('model', 'sky'):
                layout.prop(item, "active", text="", icon='CHECKBOX_HLT' if item.active else 'CHECKBOX_DEHLT', emboss=False)
        else:
            layout.label(text="", translate=False, icon_value=icon)

class NWO_UL_Permutations(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            layout.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("permutation"))
            layout.prop(item, "hidden", text="", icon='HIDE_ON' if item.hidden else 'HIDE_OFF', emboss=False)
            layout.prop(item, "hide_select", text="", icon='RESTRICT_SELECT_ON' if item.hide_select else 'RESTRICT_SELECT_OFF', emboss=False)
        else:
            layout.label(text="", translate=False, icon_value=icon)
"""UI for the sets manager"""

import bpy
from ...icons import get_icon_id

class NWO_UL_MaterialOverrides(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        source = item.source_material
        destination = item.destination_material
        if source is None or destination is None:
            layout.label(text="INVALID", icon='ERROR')
        else:
            layout.label(text=f"{source.name} --> {destination.name}", icon='MATERIAL')
            
class NWO_OT_AddMaterialOverride(bpy.types.Operator):
    bl_label = "Add"
    bl_idname = 'nwo.add_material_override'
    bl_description = "Add a new material override clone"
    bl_options = {'UNDO'}
    
    source: bpy.props.PointerProperty(
        name="Source Material",
    )
    destination: bpy.props.PointerProperty(
        name="Destination Material",
    )
    
    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations[nwo.permutations_table_active_index]
        clone = permutation.clones[permutation.active_clone_index]
        override = clone.material_overrides.add()
        override.source_material = self.source
        override.destination_material = self.destination
        clone.active_material_override_index = len(clone.material_overrides) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "soruce")
        layout.prop(self, "destination")
    
class NWO_OT_RemoveMaterialOverride(bpy.types.Operator):
    bl_idname = "nwo.remove_material_override"
    bl_label = "Remove"
    bl_description = "Remove a material override from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations[nwo.permutations_table_active_index]
        return permutation.clones and permutation.active_clone_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations[nwo.permutations_table_active_index]
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
        permutation = nwo.permutations[nwo.permutations_table_active_index]
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
        
class NWO_OT_AddPermutationClone(bpy.types.Operator):
    bl_label = "Add"
    bl_idname = 'nwo.add_permutation_clone'
    bl_description = "Add a new permutation clone"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations[nwo.permutations_table_active_index]
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
        permutation = nwo.permutations[nwo.permutations_table_active_index]
        return permutation.clones and permutation.active_clone_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations[nwo.permutations_table_active_index]
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
        permutation = nwo.permutations[nwo.permutations_table_active_index]
        return permutation.clones and permutation.active_clone_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        permutation = nwo.permutations[nwo.permutations_table_active_index]
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
            row = layout.row()
            row.alignment = 'LEFT'
            # row.operator("nwo.region_rename", text=item.name, emboss=False, icon_value=get_icon_id("region"))
            row.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("region"))
            row = layout.row(align=True)
            row.alignment = 'RIGHT'
            row.prop(item, "hidden", text="", icon='HIDE_ON' if item.hidden else 'HIDE_OFF', emboss=False)
            row.prop(item, "hide_select", text="", icon='RESTRICT_SELECT_ON' if item.hide_select else 'RESTRICT_SELECT_OFF', emboss=False)
            if data.asset_type in ('model', 'sky'):
                row.prop(item, "active", text="", icon='CHECKBOX_HLT' if item.active else 'CHECKBOX_DEHLT', emboss=False)
        else:
            layout.label(text="", translate=False, icon_value=icon)

class NWO_UL_Permutations(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row()
            row.alignment = 'LEFT'
            # row.operator("nwo.permutation_rename", text=item.name, emboss=False, icon_value=get_icon_id("permutation"))
            row.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("permutation"))
            row = layout.row(align=True)
            row.alignment = 'RIGHT'
            row.prop(item, "hidden", text="", icon='HIDE_ON' if item.hidden else 'HIDE_OFF', emboss=False)
            row.prop(item, "hide_select", text="", icon='RESTRICT_SELECT_ON' if item.hide_select else 'RESTRICT_SELECT_OFF', emboss=False)
        else:
            layout.label(text="", translate=False, icon_value=icon)
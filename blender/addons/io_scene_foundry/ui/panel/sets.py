"""UI for the sets manager"""

import bpy
from ...icons import get_icon_id

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
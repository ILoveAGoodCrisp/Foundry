

import bpy

from ...icons import get_icon_id
from ...managed_blam.scenario import ScenarioTag

class NWO_UL_ZoneSets(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if item:
            row = layout.row()
            # row.alignment = 'LEFT'
            row.prop(item, 'name', text='', emboss=False, icon_value=get_icon_id("zone_set"))
        else:
            layout.label(text="", translate=False, icon_value=icon)
            
class NWO_OT_ZoneSetAdd(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.zone_set_add"
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.zone_sets
        entry = table.add()
        entry.name = "zone_set_" + str(len(table))
        nwo.zone_sets_active_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_ZoneSetRemove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.zone_set_remove"
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.zone_sets
        if table[nwo.zone_sets_active_index].name.lower() == "default":
            nwo.user_removed_all_zone_set = True
        table.remove(nwo.zone_sets_active_index)
        if nwo.zone_sets_active_index > len(table) - 1:
            nwo.zone_sets_active_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_ZoneSetMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.zone_set_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        table = nwo.zone_sets
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = nwo.zone_sets_active_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        nwo.zone_sets_active_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
def write_zone_sets_to_scenario(scene_nwo, asset_name):
    foundry_zone_sets = scene_nwo.zone_sets
    foundry_zone_set_names = [zs.name.lower() for zs in foundry_zone_sets]
    missing_zone_sets = [zs for zs in foundry_zone_sets]
    full_bsp_names = [region.name for region in scene_nwo.regions_table if region.name]
    full_sd_names = [f"{region.name}_structure_design" for region in scene_nwo.regions_table if region.name]
    with ScenarioTag() as scenario:
        for element in scenario.block_zone_sets.Elements:
            tag_zs_name = element.SelectField("name").GetStringData()
            bsp_flags = element.SelectField("bsp zone flags")
            sd_flags = element.SelectField("structure design zone flags")

            if tag_zs_name in foundry_zone_set_names:
                zs = foundry_zone_sets[foundry_zone_set_names.index(tag_zs_name)]
                missing_zone_sets.remove(zs)
                
                if tag_zs_name == "default":
                    for item in bsp_flags.Items:
                        item.IsSet = True
                    for item in sd_flags.Items:
                        item.IsSet = True
                        
                    continue
                
                for item in bsp_flags.Items:
                    flag_name = item.FlagName
                    if flag_name not in full_bsp_names:
                        continue
                    foundry_bsp_index = full_bsp_names.index(flag_name)
                    item.IsSet = getattr(zs, f"bsp_{foundry_bsp_index}", 0)
                    
                for item in sd_flags.Items:
                    flag_name = item.FlagName
                    if flag_name not in full_sd_names:
                        continue
                    foundry_bsp_index = full_sd_names.index(flag_name)
                    item.IsSet = getattr(zs, f"bsp_{foundry_bsp_index}", 0)
        
        for zs in missing_zone_sets:
            element = scenario.block_zone_sets.AddElement()
            element.SelectField("name").SetStringData(zs.name.lower())
            bsp_flags = element.SelectField("bsp zone flags")
            sd_flags = element.SelectField("structure design zone flags")
            if zs.name.lower() == "default":
                for item in bsp_flags.Items:
                    item.IsSet = True
                for item in sd_flags.Items:
                    item.IsSet = True
                continue

            for item in bsp_flags.Items:
                flag_name = item.FlagName
                if flag_name not in full_bsp_names:
                    continue
                foundry_bsp_index = full_bsp_names.index(flag_name)
                item.IsSet = getattr(zs, f"bsp_{foundry_bsp_index}", 0)
                
            for item in sd_flags.Items:
                flag_name = item.FlagName
                if flag_name not in full_sd_names:
                    continue
                foundry_bsp_index = full_sd_names.index(flag_name)
                item.IsSet = getattr(zs, f"bsp_{foundry_bsp_index}", 0)
                
        scenario.tag_has_changes = True
        
class NWO_OT_RemoveExistingZoneSets(bpy.types.Operator):
    bl_label = "Cull Scenario Tag Zone Sets"
    bl_description = "Removes zone sets in the scenario tag that are not present in Foundry"
    bl_idname = "nwo.remove_existing_zone_sets"
    bl_options = {'UNDO'}
    
    def execute(self, context):
        removed_count = remove_existing_zone_sets_from_scenario(context.scene.nwo)
        if removed_count:
            self.report({"INFO"}, f"Removed {removed_count} zone set from scenario. Scenario tag synced with Foundry")
        else:
            self.report({"INFO"}, f"No Zone Sets to remove. Scenario tag synced with Foundry")
            
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)
        
def remove_existing_zone_sets_from_scenario(scene_nwo) -> int:
    foundry_zone_sets = scene_nwo.zone_sets
    foundry_zone_set_names = [zs.name.lower() for zs in foundry_zone_sets]
    to_remove = []
    with ScenarioTag() as scenario:
        to_remove = [element.ElementIndex for element in scenario.block_zone_sets.Elements if element.SelectField("name").GetStringData() not in foundry_zone_set_names]
        if not to_remove:
            return 0
        [scenario.block_zone_sets.RemoveElement(i) for i in reversed(to_remove)]
        scenario.tag_has_changes = True
        
    return len(to_remove)
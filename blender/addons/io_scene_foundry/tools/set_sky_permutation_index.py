

from pathlib import Path
import bpy
from .. import utils
from ..tags.scenario import ScenarioMetadataTag

def set_default_sky(context, report, sky_index):
    scene_nwo = utils.get_scene_props()
    active_bsp = scene_nwo.regions_table[scene_nwo.regions_table_active_index].name
    with ScenarioMetadataTag() as scenario:
        if scene_nwo.skies_authored_from_blender:
            scenario.set_skies(item.path for item in scene_nwo.scenario_skies)
        sky_name = scenario.set_bsp_default_sky(active_bsp, sky_index)
        if sky_name is None:
            report({'WARNING'}, f"BSP {active_bsp} not found. Could not set sky")
            return {"CANCELLED"}
        else:
            scenario.save()
        
    report({'INFO'}, f"Set sky for bsp {active_bsp} to {sky_name}")
    return {"FINISHED"}

def new_sky_material(context, report, sky_index, sky_name=None):
    if sky_index > -1:
        mat_name = '+sky' + str(sky_index)
    else:
        mat_name = '+sky'
    mat = bpy.data.materials.get(mat_name, 0)
    if not mat:
        mat = bpy.data.materials.new(mat_name)
    context.object.active_material = mat
    if sky_name is None:
        report({'INFO'}, f"Updated sky permutation index for active material")
    else:
        report({'INFO'}, f"Added new sky to scenario and updated sky permutation index for active material. Name={sky_name}, Index={str(sky_index)}")
    return {"FINISHED"}

class NWO_UL_ScenarioSkies(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=Path(item.path).stem if item.path else "Select Sky Tag", icon='WORLD')


class NWO_ScenarioSkyAdd(bpy.types.Operator):
    bl_idname = 'nwo.scenario_sky_add'
    bl_label = 'Add Sky'
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = utils.get_scene_props()
        nwo.scenario_skies.add()
        nwo.active_scenario_sky_index = len(nwo.scenario_skies) - 1
        return {'FINISHED'}


class NWO_ScenarioSkyRemove(bpy.types.Operator):
    bl_idname = 'nwo.scenario_sky_remove'
    bl_label = 'Remove Sky'
    bl_options = {'UNDO'}

    def execute(self, context):
        nwo = utils.get_scene_props()
        if nwo.scenario_skies:
            nwo.scenario_skies.remove(nwo.active_scenario_sky_index)
            nwo.active_scenario_sky_index = max(0, min(nwo.active_scenario_sky_index, len(nwo.scenario_skies) - 1))
        return {'FINISHED'}


class NWO_ScenarioSkyMove(bpy.types.Operator):
    bl_idname = 'nwo.scenario_sky_move'
    bl_label = 'Move Sky'
    bl_options = {'UNDO'}
    direction: bpy.props.IntProperty()

    def execute(self, context):
        nwo = utils.get_scene_props()
        source = nwo.active_scenario_sky_index
        target = source + self.direction
        if 0 <= source < len(nwo.scenario_skies) and 0 <= target < len(nwo.scenario_skies):
            nwo.scenario_skies.move(source, target)
            nwo.active_scenario_sky_index = target
        return {'FINISHED'}


class NWO_ScenarioSkiesUpdate(bpy.types.Operator):
    bl_idname = 'nwo.scenario_skies_update'
    bl_label = 'Update Scenario Skies'
    bl_description = 'Write the ordered Blender skies list to the scenario tag'

    def execute(self, context):
        tags_root = Path(utils.get_tags_path()).resolve()
        paths = []
        for index, item in enumerate(utils.get_scene_props().scenario_skies):
            path = Path(item.path)
            resolved = (tags_root / path).resolve()
            if (not item.path or path.suffix.lower() not in {'.sky', '.scenery'}
                    or not resolved.is_relative_to(tags_root) or not resolved.is_file()):
                self.report({'ERROR'}, f'Sky {index + 1} must be an existing sky or scenery tag inside the tags folder')
                return {'CANCELLED'}
            paths.append(str(resolved.relative_to(tags_root)))
        try:
            with ScenarioMetadataTag() as scenario:
                scenario.set_skies(paths)
        except Exception as exc:
            self.report({'ERROR'}, f'Could not update scenario skies: {exc}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Updated {len(paths)} scenario skies')
        return {'FINISHED'}

class NWO_SetSky(bpy.types.Operator):
    bl_idname = "nwo.set_sky"
    bl_label = "Set Sky"
    bl_description = "Selects the sky to use for this material"
    bl_options = {"UNDO"}
    
    def skies_items(self, context):
        items = []
        if self.type == 'material':
            items.append(("-1", "Default", "", "", 0))
        else:
            items.append(("-1", "None", "", "", 0))
        scene_nwo = utils.get_scene_props()
        if scene_nwo.skies_authored_from_blender:
            skies = [Path(item.path).stem for item in scene_nwo.scenario_skies]
        else:
            with ScenarioMetadataTag() as scenario:
                skies = scenario.get_skies_mapping()
        for idx, sky in enumerate(skies):
            items.append((str(idx), f'{sky} ({str(idx)})', '', idx + 1))
        
        return items
    
    scenario_skies: bpy.props.EnumProperty(
        name="Sky",
        items=skies_items,
        options={'SKIP_SAVE'}
    )
    
    type: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'}, default='material')

    @classmethod
    def poll(cls, context):
        return utils.poll_ui('scenario') and utils.valid_nwo_asset(context) and context.object and context.object.active_material and context.object.active_material.name.startswith('+sky')

    def execute(self, context):
        sky_index = int(self.scenario_skies)
        return new_sky_material(context, self.report, sky_index)

    def invoke(self, context, _):
        self.sky_names = []
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'scenario_skies', text="Sky")
        
class NWO_SetDefaultSky(NWO_SetSky):
    bl_idname = "nwo.set_default_sky"
    bl_label = "Set BSP Sky"
    bl_description = "Sets the sky for this BSP"
    bl_options = set()
    
    type: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'}, default='bsp')

    @classmethod
    def poll(cls, context):
        return utils.poll_ui('scenario') and utils.valid_nwo_asset(context) and utils.is_corinth(context)
    
    def execute(self, context):
        if self.scenario_skies == 'none':
            sky_index = -1
        else:
            sky_index = int(self.scenario_skies)
        return set_default_sky(context, self.report, sky_index)

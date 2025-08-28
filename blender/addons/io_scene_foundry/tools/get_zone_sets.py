
from pathlib import Path
import bpy
from ..managed_blam.scenario import ScenarioTag

from ..utils import get_tags_path
from .. import utils

class NWO_GetZoneSets(bpy.types.Operator):
    bl_idname = "nwo.get_zone_sets"
    bl_label = "Zone Sets"
    bl_description = "Returns a list of scenario zone sets"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        
        if not utils.current_project_valid():
            return False
        
        if not context.scene.nwo.cinematic_scenario:
            return False
        tag_path = Path(get_tags_path(), context.scene.nwo.cinematic_scenario)
        return tag_path.is_absolute() and tag_path.exists() and tag_path.is_file()
    
    def zone_set_items(self, context):
        with ScenarioTag(path=context.scene.nwo.cinematic_scenario) as scenario:
            if not scenario.block_zone_sets.Elements.Count:
                return [("default", "default", "")]
            items = []
            for element in scenario.block_zone_sets.Elements:
                zs_name = element.Fields[0].GetStringData()
                items.append((zs_name, zs_name, ""))

            return items
        
        return [("default", "default", "")]
    
    zone_set: bpy.props.EnumProperty(
        name="Zone Set",
        items=zone_set_items,
    )
    
    def execute(self, context):
        nwo = context.scene.nwo
        if Path(get_tags_path(), utils.relative_path(nwo.cinematic_scenario)).exists():
            nwo.cinematic_zone_set = self.zone_set
            return {'FINISHED'}
        
        self.report({'ERROR'}, f"Scenario does not exist: {nwo.cinematic_scenario}")
        return {'CANCELLED'}
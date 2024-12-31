from enum import Enum
from pathlib import Path

from ..export.cinematic import CinematicScene

from .scenario import ScenarioTag
from . import Tag

# TODO Handle resources

class ShotType(Enum):
    ALL = 0
    TAG = 1
    CURRENT = 2

class CinematicTag(Tag):
    tag_ext = 'cinematic'
    
    def _read_fields(self):
        self.cinematic_playback = self.tag.SelectField('Custom:custom playback')
        self.scenario = self.tag.SelectField("Struct:scenario and zone set[0]/Reference:scenario")
        self.zone_set = self.tag.SelectField("Struct:scenario and zone set[0]/LongInteger:zone set")
        self.name = self.tag.SelectField("StringId:name")
        self.channel_type = self.tag.SelectField("ShortEnum:channel type")
        self.flags = self.tag.SelectField("Flags:flags")
        self.scenes = self.tag.SelectField("Block:scenes")
    
    def get_play_text(self, loop: bool, shot_type: ShotType) -> str:
        match shot_type:
            case ShotType.ALL:
                return self.cinematic_playback.GetPlayCinematicText(loop)
            case ShotType.TAG:
                return self.cinematic_playback.GetPlayCheckedText(loop)
            case ShotType.CURRENT:
                pass
                # TODO set all shots unchecked apart from current in blender
    
    def get_stop_text(self, loop) -> str:
        return self.cinematic_playback.GetStopCinematicText(loop)
    
    def create(self, name: str, cinematic_scene: CinematicScene, all_scene_paths: list[Path], scenario_path: Path | None = None, zone_set: str = "cinematic"):
        self.tag_has_changes = True
        
        # Add scenes to cinematic
        if all_scene_paths:
            if self.scenes.Elements.Count > 0:
                self.scenes.RemoveAllElements()
            
            for scene_path in all_scene_paths:
                element = self.scenes.AddElement()
                element.Fields[0].Path = self._TagPath_from_string(scene_path)
        
        if scenario_path is not None:
            with ScenarioTag(path=scenario_path) as scenario:
                scenario.tag_has_changes = True
                # Set link to scenario in cinematic tag
                self.name = name
                self.scenario.Path = scenario.tag_path
                # Add cinematic to scenario tag, first checking to see if the reference exists
                block_cinematics = scenario.tag.SelectField("Block:cinematics")
                for element in scenario.tag.SelectField("Block:cinematics").Elements:
                    if element.Fields[1].Path == self.tag_path:
                        scenario_cinematic_index = element.ElementIndex
                        break
                else:
                    element = block_cinematics.AddElement()
                    element.Fields[1].Path = self.tag_path
                    scenario_cinematic_index = element.ElementIndex
                
                zone_set_index = -1
                # Add to given zone set name if this exists
                for element in scenario.block_zone_sets.Elements:
                    if element.Fields[0].GetStringData() == zone_set:
                        zone_set_index = element.ElementIndex
                        for item in element.SelectField("BlockFlags:cinematic zones").Items:
                            if item.FlagBit == scenario_cinematic_index:
                                item.IsSet = True
                                break
                        break
                else:
                    # Create a new zone set if needed
                    element = scenario.block_zone_sets.AddElement()
                    element.Fields[0].SetStringData(zone_set)
                    zone_set_index = element.ElementIndex
                        
                    for item in element.SelectField("BlockFlags:cinematic zones").Items:
                        if item.FlagBit == scenario_cinematic_index:
                            item.IsSet = True
                        break
                    
                    # Enable all zone bsp and design tags for this 
                    for item in element.SelectField("bsp zone flags").Items:
                        item.IsSet = True
                            
                    for item in element.SelectField("structure design zone flags").Items:
                        item.IsSet = True
                
                
                self.zone_set.Data = zone_set_index
                        
                # Add cinematic anchor object to scenario
                if cinematic_scene.anchor is not None:
                    cutscene_flags = scenario.tag.SelectField("Block:cutscene flags")
                    for element in cutscene_flags.Elements:
                        if cinematic_scene.anchor_name == element.Fields[0].GetStringData():
                            element.Fields[1].Data = cinematic_scene.anchor_location
                            element.Fields[2].Data = cinematic_scene.anchor_yaw_pitch
                            break
                                
                    else:
                        element = cutscene_flags.AddElement()
                        element.Fields[0].SetStringData(cinematic_scene.anchor_name)
                        element.Fields[1].Data = cinematic_scene.anchor_location
                        element.Fields[2].Data = cinematic_scene.anchor_yaw_pitch
                        
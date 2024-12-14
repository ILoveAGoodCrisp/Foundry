from enum import Enum
from pathlib import Path

from .scenario import ScenarioTag
from . import Tag

class ShotType(Enum):
    ALL = 0
    TAG = 1
    CURRENT = 2

class CinematicTag(Tag):
    tag_ext = 'cinematic'
    
    def _read_fields(self):
        self.cinematic_playback = self.tag.SelectField('Custom:custom playback')
        self.scenario = self.tag.SelectField("Struct:scenario and zone set[0]/Reference:scenario")
        self.zone_set = self.tag.SelectField("Struct:scenario and zone set[0]/Reference:zone set")
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
    
    def create(self, name: str, scenario_path: Path, zone_set: str, scenes: list[Path]):
        with ScenarioTag(path=scenario) as scenario:
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
                
            bsp_flags = None
            sd_flags = None
            for element in scenario.block_zone_sets.Elements:
                if element.Fields[0] == zone_set:
                    cinematic_zones = element.SelectField("BlockFlags:cinematic zones")
                    for item in cinematic_zones.Items:
                        if item.FlagName == name:
                            item.IsSet = True
                    # element.SelectField("BlockFlags:cinematic zones").SetBit(name, True)
                    
                
            element = scenario.block_zone_sets.AddElement()
            if zone_set:
                element.Fields[0].SetStringData(f"{zone_set}_cinematic")
            else:
                element.Fields[0].SetStringData("cinematic")
            
            if bsp_flags is None:
                for item in element.SelectField("bsp zone flags").Items:
                    item.IsSet = True
            else:
                for item in element.SelectField("bsp zone flags").Items:
                    item.IsSet = bsp_flags.Items[item.FlagIndex].IsSet
                    
            if sd_flags is None:
                for item in element.SelectField("structure design zone flags").Items:
                    item.IsSet = True
            else:
                for item in element.SelectField("structure design zone flags").Items:
                    item.IsSet = sd_flags.Items[item.FlagIndex].IsSet
            
                
        self.scenario.Path = self._TagPath_from_string(scenario)
        
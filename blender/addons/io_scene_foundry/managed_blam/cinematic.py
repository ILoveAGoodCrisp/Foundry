from enum import Enum
from pathlib import Path

from .cinematic_scene import CinematicSceneTag

from .. import utils

from .scenario import ScenarioTag
from . import Tag

# TODO Handle resources

class ShotType(Enum):
    ALL = 0
    TAG = 1
    SCENE = 2
    CURRENT = 3

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
        if self.corinth:
            return f'(cinematic_debug_play "{utils.get_asset_name()}" "" 0 {self.tag.SelectField("Struct:cinematic playback[0]/LongInteger:bsp zone flags").Data})'
        match shot_type:
            case ShotType.ALL:
                if self.corinth:
                    return f'(cinematic_debug_play "{utils.get_asset_name()}" "" 0 {self.cinematic_playback.Elements[0].SelectField("bsp zone flags").Data})'
                return self.cinematic_playback.GetPlayCinematicText(loop)
            case ShotType.TAG:
                return self.cinematic_playback.GetPlayCheckedText(loop)
            case ShotType.SCENE:
                playback_scenes = self.cinematic_playback.Elements[0].SelectField("scenes")
                return self.cinematic_playback.GetPlayCinematicText(loop)
            case ShotType.CURRENT:
                current_shot_index = utils.get_current_shot_index(self.context)
                # TODO set all shots unchecked apart from current in blender
                
        self.tag_has_changes = True
    
    def get_stop_text(self, loop) -> str:
        return self.cinematic_playback.GetStopCinematicText(loop)
    
    def get_pause_text(self) -> str:
        return self.cinematic_playback.GetPauseCinematicText()
    
    def create(self, name: str, cinematic_scene, all_scenes: list[Path], scenario_path: Path | None = None, zone_set: str = "cinematic"):
        self.tag_has_changes = True
        # Add scenes to cinematic
        if all_scenes:
            if self.scenes.Elements.Count > 0:
                self.scenes.RemoveAllElements()
            
            for scene in all_scenes:
                element = self.scenes.AddElement()
                scene_path = Path(Path(self.tag_path.RelativePath).parent, scene)
                element.Fields[0].Path = self._TagPath_from_string(scene_path.with_suffix(".cinematic_scene"))
                if self.corinth:
                    element.Fields[1].Path = self._TagPath_from_string(scene_path.with_suffix(".cinematic_scene_data"))
        
        needs_cinematic_scenario_update = True
        if scenario_path is None:
            tag_path = self.scenario.Path
            if tag_path is not None:
                path = Path(tag_path.Filename)
                if path.exists():
                    scenario_path = path
                    needs_cinematic_scenario_update = False
        
        if scenario_path is not None:
            with ScenarioTag(path=scenario_path) as scenario:
                scenario.tag_has_changes = True
                # Set link to scenario in cinematic tag
                if needs_cinematic_scenario_update:
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
                
                    if zone_set:
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
                cutscene_flags = scenario.tag.SelectField("Block:cutscene flags")
                for element in cutscene_flags.Elements:
                    if cinematic_scene.anchor_name == element.Fields[0].GetStringData():
                        element.Fields[1].Data = cinematic_scene.anchor_location
                        if self.corinth:
                            element.Fields[2].Data = cinematic_scene.anchor_ypr
                        else:
                            # Reach only uses yaw and pitch for cutscene flags
                            element.Fields[2].Data = cinematic_scene.anchor_ypr[:2]
                        break
                            
                else:
                    element = cutscene_flags.AddElement()
                    element.Fields[0].SetStringData(cinematic_scene.anchor_name)
                    element.Fields[1].Data = cinematic_scene.anchor_location
                    element.Fields[2].Data = cinematic_scene.anchor_ypr
                        
                if not self.corinth:
                    scenario.update_cinematic_resource()
                
                    # Delete the autogenerated cinematic script to force a recompile
                    source_files = scenario.tag.SelectField("Block:source files")
                    for element in scenario.tag.SelectField("Block:source files").Elements:
                        if element.Fields[0].GetStringData() == "auto_generated_cinematic_script":
                            source_files.RemoveElement(element.ElementIndex)
                            break
                        
                if scenario.read_scenario_type() == 1:
                    utils.print_warning(f"{scenario.tag_path.RelativePathWithExtension} is set to Multiplayer. Cinematics will crash if you attempt to run them\nSwitch the scenario type to Solo before playing cinematic")
    
    def to_blender(self, film_aperture: float, import_scenario=False):
        scenario_path = None
        zone_set = ""
        
        scene_datas = []
        if import_scenario:
            scenario_tagpath = self.scenario.Path
            if self.path_exists(scenario_tagpath):
                scenario_path = scenario_tagpath.Filename
                zone_set_index = self.zone_set.Data
                
                with ScenarioTag(path=scenario_path) as scenario:
                    if zone_set_index > -1 and zone_set_index < scenario.block_zone_sets.Elements.Count:
                        zone_set = scenario.block_zone_sets.Elements[zone_set_index].Fields[0].GetStringData()
        
        for element in self.scenes.Elements:
            if self.corinth:
                pass
            
            scene_tagpath = element.SelectField("Reference:scene").Path
            if self.path_exists(scene_tagpath):
                with CinematicSceneTag(path=scene_tagpath) as scene:
                    scene_data = SceneData(*scene.to_blender(film_aperture))
                    scene_datas.append(scene_data)
                    
                # until we add support for multiple scenes
                break
        
        return scene_datas, scenario_path, zone_set
    
class SceneData:
    def __init__(self, name, scene, camera_objects, object_animations, anchor_name, actions, shot_frames):
        self.name = name
        self.blender_scene = scene
        self.camera_objects = camera_objects
        self.object_animations = object_animations
        self.anchor_name = anchor_name
        self.actions = actions
        self.shot_frames = shot_frames
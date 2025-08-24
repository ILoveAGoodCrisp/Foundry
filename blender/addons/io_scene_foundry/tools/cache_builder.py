from enum import Enum
from math import degrees, radians
import os
from pathlib import Path
import time
import bpy
import json
from uuid import uuid4

from .scenario.lightmap import run_lightmapper

from ..managed_blam.scenario import ScenarioTag
from .. import utils

mcc_reach_sounds = {
       "english.fsb",
       "english.fsb.info",
       "french.fsb",
       "french.fsb.info",
       "german.fsb",
       "german.fsb.info",
       "italian.fsb",
       "italian.fsb.info",
       "mexican.fsb",
       "mexican.fsb.info"
       "sfx.fsb",
       "sfx.fsb.info",
       "spanish.fsb",
       "spanish.fsb.info"
}

mcc_halo4_sounds = {
    "sfxbank.pck",
    "sfxbank_dlc.pck",
    "sfxstream.pck",
    "sfxstream_dlc.pck",
    "english(us)\\dlc.pck",
    "english(us)\\soundbank.pck",
    "english(us)\\soundstream.pck",
    "french(france)\\dlc.pck",
    "french(france)\\soundbank.pck",
    "french(france)\\soundstream.pck",
    "german\\dlc.pck",
    "german\\soundbank.pck",
    "german\\soundstream.pck",
    "italian\\dlc.pck",
    "italian\\soundbank.pck",
    "italian\\soundstream.pck",
    "spanish(mexico)\\dlc.pck",
    "spanish(mexico)\\soundbank.pck",
    "spanish(mexico)\\soundstream.pck",
    "spanish(spain)\\dlc.pck",
    "spanish(spain)\\soundbank.pck",
    "spanish(spain)\\soundstream.pck",
}

mcc_halo2amp_sounds = {
    "sfxbank.pck",
    "sfxstream.pck",
    "english(us)\\soundbank.pck",
    "english(us)\\soundstream.pck",
}
    
class ScenarioType(Enum):
    CAMPAIGN = 0
    MULTIPLAYER = 1
    FIREFIGHT = 2
    
class CacheBuilder:
    def __init__(self, scenario_path: Path, context: bpy.types.Context, mp_validation: bool, own_asset: bool):
        self.project_dir = utils.get_project_path()
        self.tags_dir = Path(self.project_dir, "tags")
        self.scenario = scenario_path.with_suffix("")
        self.mod_name = self.scenario.name
        self.map = Path(self.project_dir, "maps", f"{self.mod_name}.map")
        self.mcc_mods = Path(self.project_dir, "MCC")
        self.mod_dir = Path(self.mcc_mods, self.mod_name)
        self.game_engine = utils.project_game_for_mcc(context)
        self.scenario_type = ScenarioType.CAMPAIGN
        self.context = context
        self.do_mp_validation = False
        self.zone_sets = None
        self.bsps = None
        self.mp_object_types = None

        if self.game_engine == "HaloReach":
            self.sound_dir = Path(self.project_dir, "fmod", "pc")
        else:
            self.sound_dir = Path(self.project_dir, "sound", "pc")
        
        with ScenarioTag(path=scenario_path) as tag:
            if tag.survival_mode():
                self.scenario_type = ScenarioType.FIREFIGHT
            elif tag.read_scenario_type() == 1:
                self.scenario_type = ScenarioType.MULTIPLAYER
                
            self.do_mp_validation = mp_validation and self.scenario_type != ScenarioType.CAMPAIGN
                
            self.zone_sets = [element.Fields[0].GetStringData() for element in tag.block_zone_sets.Elements]
            
            self.bsps = tag.get_bsp_names()
                
            if self.do_mp_validation and own_asset:
                self._multiplayer_validation(tag)
                
    def _multiplayer_validation(self, tag):
        is_mp = self.scenario_type == ScenarioType.MULTIPLAYER
        type_txt = "multiplayer" if is_mp else "firefight"
        print(f"\n\n{type_txt.capitalize()} Validation")
        print("-----------------------------------------------------------------------\n")
        # Add MP resources
        resource_field = tag.tag.SelectField("Reference:required resources")
        if resource_field.Path is None:
            if is_mp:
                if self.game_engine == "HaloReach":
                    path = r"levels\multi\multiplayer.scenario_required_resource"
                else:
                    path = r"levels\multi\mp_required_resources.scenario_required_resource"
            else:
                path = r"levels\firefight\firefight_required_resources.scenario_required_resource"
                
            if Path(self.tags_dir, path).exists():
                resource_field.Path = tag._TagPath_from_string(path)
                print(f"--- Added reference to {path}")
                tag.tag_has_changes = True
            else:
                return utils.print_warning(f"Failed to find required resources file for {type_txt}. File does not exist at: {path}")
        else:
            print(f"--- Required resources validated: {resource_field.Path.RelativePath}")
            
        if is_mp: # Don't do this for firefight
            initial_spawn_point = r"objects\multi\spawning\initial_spawn_point.scenery"
                
            # Abort if child scenarios
            if tag.corinth and tag.tag.SelectField("Block:child scenarios").Elements.Count > 0:
                return print(f"Scenario has child scenarios, skipping spawn point check. If you do not spawn in MCC, then you will need to set up initial spawn points with the following tag: {initial_spawn_point}")
            
            # Check for initial spawn points tags
            if not Path(self.tags_dir, initial_spawn_point).exists():
                return utils.print_warning(f"Cannot validate MP spawns. Failed to find initial spawn point tag: {initial_spawn_point}")
            
            respawn_point = r"objects\multi\spawning\respawn_point.scenery"
            respawn_point_ref = None
            if Path(self.tags_dir, respawn_point).exists():
                respawn_point_ref = tag._TagPath_from_string(respawn_point)
            
            has_respawn_ref = respawn_point_ref is not None
            initial_spawn_point_ref = tag._TagPath_from_string(initial_spawn_point)
            
            camera = r"objects\multi\generic\mp_cinematic_camera.scenery"
            camera_ref = None
            if Path(self.tags_dir, camera).exists():
                camera_ref = tag._TagPath_from_string(camera)
            
            has_camera_ref = camera_ref is not None
            
            # Search scenery palette for ref
            initial_palette_index = -1
            respawn_palette_index = -1
            camera_palette_index = -1
            scenery_palette = tag.tag.SelectField("Block:scenery palette")
            for element in scenery_palette.Elements:
                if element.Fields[0].Path == initial_spawn_point_ref:
                    initial_palette_index = element.ElementIndex
                elif has_respawn_ref and element.Fields[0].Path == respawn_point_ref:
                    respawn_palette_index = element.ElementIndex
                elif has_camera_ref and element.Fields[0].Path == camera_ref:
                    camera_palette_index = element.ElementIndex
                
                if initial_palette_index != -1 and respawn_palette_index != -1 and camera_palette_index != -1:
                    break
            
            if initial_palette_index == -1:
                element = scenery_palette.AddElement()
                element.Fields[0].Path = initial_spawn_point_ref
                initial_palette_index = element.ElementIndex
                tag.tag_has_changes = True
                print("--- Added reference to initial spawn point tag")
            if has_respawn_ref and respawn_palette_index == -1:
                element = scenery_palette.AddElement()
                element.Fields[0].Path = respawn_point_ref
                respawn_palette_index = element.ElementIndex
                tag.tag_has_changes = True
                print("--- Added reference to respawn point tag")
            if has_camera_ref and camera_palette_index == -1:
                element = scenery_palette.AddElement()
                element.Fields[0].Path = camera_ref
                camera_palette_index = element.ElementIndex
                tag.tag_has_changes = True
                print("--- Added reference to camera tag")

            has_initial_spawns = False
            has_respawns = False
            has_camera = False
            
            scenery = tag.tag.SelectField("Block:scenery")
            
            for element in scenery.Elements:
                if initial_palette_index != -1 and element.Fields[1].Value == initial_palette_index:
                    has_initial_spawns = True
                elif has_respawn_ref and respawn_palette_index != -1 and element.Fields[1].Value == respawn_palette_index:
                    has_respawns = True
                elif has_camera_ref and camera_palette_index != -1 and element.Fields[1].Value == camera_palette_index:
                    has_camera = True
                    
                if has_initial_spawns and has_respawns and has_camera:
                    break
                
            if has_initial_spawns and has_respawns and has_camera:
                print("--- Spawns validated")
            else:
                tag.tag_has_changes = True
                # Get valid positions from player starting points if possible
                # spawn_coordinates = x, y, z, yaw, pitch
                spawn_coordinates = []
                for element in tag.tag.SelectField("Block:player starting locations").Elements:
                    x, y, z = element.Fields[0].Data
                    yaw = element.SelectField("Angle:facing").Data
                    pitch = element.SelectField("Angle:pitch").Data
                    spawn_coordinates.append(tuple((tuple((x, y, z)), tuple((yaw, pitch, 0.0)))))
                    
                if not spawn_coordinates:
                    spawn_coordinates.append(tuple((tuple((0.0, 0.0, 0.0)), tuple((0.0, 0.0, 0.0)))))
                    
                if not has_initial_spawns:
                    for co in spawn_coordinates:
                        element = scenery.AddElement()
                        element.Fields[1].Value = initial_palette_index
                        element.SelectField("Struct:object data[0]/RealPoint3d:position").Data = co[0]
                        element.SelectField("Struct:object data[0]/RealEulerAngles3d:rotation").Data = co[1]
                        element.SelectField("Struct:object data[0]/Struct:object id[0]/LongInteger:unique id").Data = utils.unique_id()
                        element.SelectField("Struct:object data[0]/Struct:object id[0]/CharEnum:type").Value = 6 # Scenery
                        element.SelectField("Struct:multiplayer data[0]/CharEnum:owner team").Value = 8 # Neutral
                    print("--- Added initial spawn points")
                        
                if has_respawn_ref and not has_respawns:
                    for co in spawn_coordinates:
                        element = scenery.AddElement()
                        element.Fields[1].Value = respawn_palette_index
                        element.SelectField("Struct:object data[0]/RealPoint3d:position").Data = co[0]
                        element.SelectField("Struct:object data[0]/RealEulerAngles3d:rotation").Data = co[1]
                        element.SelectField("Struct:object data[0]/Struct:object id[0]/LongInteger:unique id").Data = utils.unique_id()
                        element.SelectField("Struct:object data[0]/Struct:object id[0]/CharEnum:type").Value = 6 # Scenery
                        element.SelectField("Struct:multiplayer data[0]/CharEnum:owner team").Value = 8 # Neutral
                    print("--- Added respawn points")
                    
                if has_camera_ref and not has_camera:
                    # try:
                    blender_cameras = [ob for ob in self.context.view_layer.objects if ob.type == 'CAMERA']
                    if blender_cameras:
                        loc, rot, sca = utils.halo_loc_rot_sca(blender_cameras[0].matrix_world)
                        print(f"--- Added multiplayer camera from blender camera: {blender_cameras[0].name}")
                    else:
                        loc, rot, sca = utils.halo_loc_rot_sca(self.context.space_data.region_3d.view_matrix.inverted_safe())
                        print(f"--- Added multiplayer camera from blender viewport")
                    element = scenery.AddElement()
                    element.Fields[1].Value = camera_palette_index
                    element.SelectField("Struct:object data[0]/RealPoint3d:position").Data = loc
                    element.SelectField("Struct:object data[0]/RealEulerAngles3d:rotation").Data = rot
                    element.SelectField("Struct:object data[0]/Struct:object id[0]/LongInteger:unique id").Data = utils.unique_id()
                    element.SelectField("Struct:object data[0]/Struct:object id[0]/CharEnum:type").Value = 6 # Scenery
                    element.SelectField("Struct:multiplayer data[0]/CharEnum:owner team").Value = 8 # Neutral 
                    # except:
                    #     pass
        
        print(f"--- Scenario validated for {type_txt}")
                
    def texture_analysis(self):
        for zone_set in self.zone_sets:
            utils.run_tool(
                [
                    "faux_perform_texture_analysis",
                    str(self.scenario),
                    zone_set,
                    "true",
                    "false",
                ]
            )
            
    def wetness(self):
        pass
    
    def imposters(self):
        pass
    
    def cubemaps(self):
        pass
        
    def lightmap(self):
        export = self.context.scene.nwo_export
        run_lightmapper(
            self.game_engine != "HaloReach",
            str(self.scenario),
            export.lightmap_quality,
            export.lightmap_quality_h4,
            export.lightmap_all_bsps,
            export.lightmap_specific_bsp,
            export.lightmap_region.name if utils.pointer_ob_valid(export.lightmap_region) else "",
            False,
            export.lightmap_threads,
            self.bsps)
    
    def build_cache(self, event_level=None) -> bool:
        # Get scenario type
        
        # clear existing map file
        if self.map.exists():
            self.map.unlink()
        try:
            utils.run_tool(
                [
                    "build-cache-file",
                    str(self.scenario),
                    "pc",
                ],
                event_level=event_level,
                force_tool=True,
            )
        except:
            return False
        
        return self.map.exists()
    
    def build_mod(self):
        # Create MCC mods folder if needed
        if not self.mcc_mods.exists():
            self.mcc_mods.mkdir()
        
        # Update Mod Manifest if needed
        user_dir = Path(os.getenv('USERPROFILE'))
        if not (user_dir.is_absolute() and user_dir.exists()):
            return "Failed to find user profile directory"
        
        manifest = Path(user_dir, "AppData", "LocalLow", "MCC", "Config", "ModManifest.txt")
        mod_dir_txt = f"{self.mcc_mods}\n"
        if manifest.exists():
            with open(manifest, "r") as file:
                for line in file.readlines():
                    if line == mod_dir_txt:
                        break
                else:
                    with open(manifest, "a") as file:
                        file.write(mod_dir_txt)
            

        else:
            with open(manifest, "x") as file:
                file.write(mod_dir_txt)
                
        # Create mod folder
        if not self.mod_dir.exists():
            self.mod_dir.mkdir()
            
        # copy map file
        mod_maps_dir = Path(self.mod_dir, "maps")
        if not mod_maps_dir.exists():
            mod_maps_dir.mkdir()
        
        try:
            utils.copy_file(self.map, Path(mod_maps_dir, self.map.name))
        except:
            return "Failed to copy compiled .map file to mod folder. This .map file may be open in MCC"
                
        # Create JSON data
        # Mod info JSON
        mod_info = Path(self.mod_dir, "ModInfo.json")
        # Use existing guid if available
        existing_mod_info_guid = None
        steam_guid = None
        if mod_info.exists():
            try:
                with open(mod_info, "r") as file:
                    jfile = json.load(file)
                    existing_mod_info_guid = jfile["ModIdentifier"]["ModGuid"]
                    hosted_mod_ids = jfile["ModIdentifier"].get("HostedModIds")
                    if hosted_mod_ids is not None:
                        steam_guid = hosted_mod_ids.get("SteamWorkshopId")
            except: ...
        
        # Write json data as dict
        mod_info_dict = {
            "ModIdentifier": {
                "ModGuid": existing_mod_info_guid if existing_mod_info_guid is not None else str(uuid4())
            },
            "ModVersion": {
                "Major": 0,
                "Minor": 0,
                "Patch": 0
            },
            "MinAppVersion": {
                "Major": 0,
                "Minor": 0,
                "Patch": 0
            },
            "MaxAppVersion": {
                "Major": 0,
                "Minor": 0,
                "Patch": 0
            },
            "Engine": self.game_engine,
            "Title": {
                "Neutral": self.mod_name.upper()
            },
            "InheritSharedFiles": "FromMCC",
            "ModContents": {
                "HasBackgroundVideos": False,
                "HasNameplates": False
            },
            "GameModContents": {
                "HasSharedFiles": False,
                "HasCampaign": self.scenario_type == ScenarioType.CAMPAIGN,
                "HasSpartanOps": False,
                "HasController": False
            }
        }
        
        if steam_guid is not None:
            mod_info_dict["ModIdentifier"]["HostedModIds"]["SteamWorkshopId"] = steam_guid
        
        match self.scenario_type:
            case ScenarioType.CAMPAIGN:
                campaign_info = Path(self.mod_dir, "CampaignInfo.json")
                
                existing_campaign_info_guid = None
                if campaign_info.exists():
                    try:
                        with open(campaign_info, "r") as file:
                            existing_campaign_info_guid = json.load(file)["CampaignGuid"]
                    except: ...
                    
                campaign_info_dict = {
                    "CampaignGuid": existing_campaign_info_guid if existing_campaign_info_guid is not None else str(uuid4()),
                    "Title": {
                        "Neutral": "test"
                    },
                    "CampaignMaps": [
                        f"campaign/{self.mod_name}.json"
                    ]
                }
                
                with open(campaign_info, "w") as file:
                    json.dump(campaign_info_dict, file, indent=4)
                
                campaign_dir = Path(self.mod_dir, "campaign")
                if not campaign_dir.exists():
                    campaign_dir.mkdir()
                    
                campaign_map_info = Path(campaign_dir, f"{self.mod_name}.json")
                
                existing_campaign_map_info_guid = None
                if campaign_map_info.exists():
                    try:
                        with open(campaign_map_info, "r") as file:
                            existing_campaign_map_info_guid = json.load(file)["MapGuid"]
                    except: ...
                    
                campaign_map_info_dict = {
                    "MapGuid": existing_campaign_map_info_guid if existing_campaign_map_info_guid is not None else str(uuid4()),
                    "ScenarioFile": str(self.scenario),
                    "Title": {
                        "Neutral": self.mod_name.upper()
                    },
                    "Description": {
                        "Neutral": f"Forged in Foundry at {time.strftime('%Y-%m-%d-%H:%M:%S')}"
                    },
                    "Images": {
                        "Large": r"images\large.png",
                        "Thumbnail": r"images\small.png",
                        "LoadingScreen": r"images\loading_screen.png",
                        "TopDown": r"images\top_down.png"
                    },
                    "Flags": [
                        "DisableSavedFilms"
                    ],
                    "InsertionPoints": [
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 0,
                            "Valid": True,
                            "Title": {
                                "Neutral": "ALPHA"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 0"
                            },
                            "ODST": {},
                            "Thumbnail": r"images\rally_point_small.png"
                        },
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 1,
                            "Valid": True,
                            "Title": {
                                "Neutral": "BRAVO"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 1"
                            },
                            "ODST": {},
                            "Thumbnail": r"images\rally_point_small.png"
                        },
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 2,
                            "Valid": True,
                            "Title": {
                                "Neutral": "CHARLIE"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 2"
                            },
                            "ODST": {},
                            "Thumbnail": r"images\rally_point_small.png"
                        },
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 3,
                            "Valid": True,
                            "Title": {
                                "Neutral": "DELTA"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 3"
                            },
                            "ODST": {},
                            "Thumbnail": r"images\rally_point_small.png"
                        },
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 4,
                            "Valid": True,
                            "Title": {
                                "Neutral": "ECHO"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 4"
                            },
                            "ODST": {},
                            "Thumbnail": r"images\rally_point_small.png"
                        }
                    ],
                    "CampaignMapKind": "Default",
                    "CampaignMetagame": {
                        "IsNonScoring": False,
                        "MissionSegmentCount": 0,
                        "ParTimeInSeconds": 0.0,
                        "AverageTimeInSeconds": 0.0,
                        "MaxTimeInSeconds": 0.0
                    }
                }
                
                with open(campaign_map_info, "w") as file:
                    json.dump(campaign_map_info_dict, file, indent=4)
                
            case ScenarioType.MULTIPLAYER:
                mp_dir = Path(self.mod_dir, "multiplayer")
                if not mp_dir.exists():
                    mp_dir.mkdir()
                    
                mp_info = Path(mp_dir, f"{self.mod_name}.json")
                
                existing_mp_info_guid = None
                existing_mp_object_types = None
                if mp_info.exists():
                    try:
                        with open(mp_info, "r") as file:
                            fjson = json.load(file)
                            existing_mp_info_guid = fjson["MapGuid"]
                            existing_mp_object_types = fjson.get("ValidMultiplayerObjectTypes")
                    except: ...
                
                mp_info_dict = {
                        "MapGuid": existing_mp_info_guid if existing_mp_info_guid is not None else str(uuid4()),
                        "ScenarioFile": str(self.scenario),
                        "Title": {
                            "Neutral": self.mod_name.upper()
                        },
                        "Description": {
                            "Neutral": f"Forged in Foundry at {time.strftime('%Y-%m-%d-%H:%M:%S')}"
                        },
                        "Images": {
                            "Large": r"images\large.png",
                            "Thumbnail": r"images\small.png",
                            "LoadingScreen": r"images\loading_screen.png",
                            "TopDown": r"images\top_down.png"
                        },
                        "Flags": [
                            "DisableSavedFilms"
                        ],
                        "InsertionPoints": [],
                        "MaximumTeamsByGameCategory": {},
                    }
                
                if self.mp_object_types is not None:
                    mp_info_dict["ValidMultiplayerObjectTypes"] = self.mp_object_types
                elif existing_mp_object_types is not None:
                    mp_info_dict["ValidMultiplayerObjectTypes"] = existing_mp_object_types
                
                with open(mp_info, "w") as file:
                    json.dump(mp_info_dict, file, indent=4)
                    
                mod_info_dict["GameModContents"]["MultiplayerMaps"] = [str(mp_info.relative_to(self.mod_dir))]
                    
            case ScenarioType.FIREFIGHT:
                ff_dir = Path(self.mod_dir, "firefight")
                if not ff_dir.exists():
                    ff_dir.mkdir()
                    
                ff_info = Path(ff_dir, f"{self.mod_name}.json")
                
                existing_ff_info_guid = None
                if ff_info.exists():
                    try:
                        with open(ff_info, "r") as file:
                            existing_ff_info_guid = json.load(file)["MapGuid"]
                    except: ...
                
                ff_info_dict = {
                        "MapGuid": existing_ff_info_guid if existing_ff_info_guid is not None else str(uuid4()),
                        "ScenarioFile": str(self.scenario),
                        "Title": {
                            "Neutral": self.mod_name.upper()
                        },
                        "Description": {
                            "Neutral": f"Forged in Foundry at {time.strftime('%Y-%m-%d-%H:%M:%S')}"
                        },
                        "Images": {
                            "Large": r"images\large.png",
                            "Thumbnail": r"images\small.png",
                            "LoadingScreen": r"images\loading_screen.png",
                            "TopDown": r"images\top_down.png"
                        },
                        "Flags": [
                            "DisableSavedFilms"
                        ],
                        "InsertionPoints": [],
                    }
                
                with open(ff_info, "w") as file:
                    json.dump(ff_info_dict, file, indent=4)
                    
                mod_info_dict["GameModContents"]["FirefightMaps"] = [str(ff_info.relative_to(self.mod_dir))]
            
        with open(mod_info, "w") as file:
            json.dump(mod_info_dict, file, indent=4)
            
        # Add in MCC images
        images_dir = Path(self.mod_dir, "images")
        if not images_dir.exists():
            images_dir.mkdir()
            
        placeholder_images_dir = Path(utils.addon_root(), "mcc", "images")
        
        placeholder_large = Path(placeholder_images_dir, "large.png")
        placeholder_small = Path(placeholder_images_dir, "small.png")
        placeholder_loading_screen = Path(placeholder_images_dir, "loading_screen.png")
        placeholder_rally_point = Path(placeholder_images_dir, "rally_point_small.png")
        
        mod_large = Path(images_dir, "large.png")
        mod_small = Path(images_dir, "small.png")
        mod_loading_screen = Path(images_dir, "loading_screen.png")
        mod_rally_point = Path(images_dir, "rally_point_small.png")
        
        if placeholder_large.exists() and not mod_large.exists():
            utils.copy_file(placeholder_large, mod_large)
            
        if placeholder_small.exists() and not mod_small.exists():
            utils.copy_file(placeholder_small, mod_small)
            
        if placeholder_loading_screen.exists() and not mod_loading_screen.exists():
            utils.copy_file(placeholder_loading_screen, mod_loading_screen)
            
        if self.scenario_type == ScenarioType.CAMPAIGN and placeholder_rally_point.exists() and not mod_rally_point.exists():
            utils.copy_file(placeholder_rally_point, mod_rally_point)
    
    def generate_multiplayer_object_types(self):
        gestalt = Path(self.project_dir, "reports", self.mod_name, f"{self.mod_name}.cache_file_resource_gestalt")
        if not gestalt.exists():
            utils.print_warning(f"Failed to find cache_file_resource_gestalt at [{gestalt}]. Unable to build multiplayer object types")
            return
        
        tag_gestalt = Path(self.tags_dir, f"{self.scenario}.cache_file_resource_gestalt")
        utils.copy_file(gestalt, tag_gestalt)
        relative_gestalt = tag_gestalt.relative_to(self.tags_dir).with_suffix("")
        output = "multiplayer_object_types.bin"
        bin_path = Path(self.project_dir, output)
        
        # remove .bin if it already exists
        if bin_path.exists():
            bin_path.unlink()
            
        try:
            utils.run_tool(
                [
                    "multiplayer-generate-scenario-object-type-bitvector",
                    str(self.scenario),
                    str(relative_gestalt),
                    output
                ]
                
            )
            print("")
        except:
            return utils.print_warning("Failed to build multiplayer object types")
        
        
        if bin_path.exists():
            with open(bin_path, "r+b") as f:
                binary_data = f.read()
            
            if len(binary_data) != 256:
                return utils.print_warning(f"{output} should be exactly 256 btyes, but was {len(binary_data)} bytes")
            
            valid_indices = []
            for byte_index, byte in enumerate(binary_data):
                for bit in range(8):
                    if (byte >> bit) & 1:
                        valid_indices.append(byte_index * 8 + bit)
                        
            if valid_indices:
                self.mp_object_types = valid_indices
                        
            bin_path.unlink()
            print("--- Successfully read valid multiplayer object types")
            
        else:
            return utils.print_warning("Failed to build multiplayer object types")
            
        
    
    def copy_sounds(self, custom_only: bool):
        match self.game_engine:
            case "HaloReach":
                default_files = mcc_reach_sounds
                game_dir = "haloreach"
            case "Halo4":
                default_files = mcc_halo4_sounds
                game_dir = "halo4"
            case "Halo2A":
                default_files = mcc_halo2amp_sounds
                game_dir = "groundhog"
            case _:
                raise
                
        if self.game_engine == "HaloReach":
            mod_sound_dir = Path(self.mod_dir, game_dir, "fmod", "pc")
        else:
            mod_sound_dir = Path(self.mod_dir, game_dir, "sound", "pc")
        for root, dirs, files in os.walk(self.sound_dir):
            for file in files:
                full = Path(root, file)
                relative = full.relative_to(self.sound_dir)
                
                if not relative.suffix.lower() in {".info", ".fsb", ".pck"}:
                    continue
                
                if custom_only and str(relative).lower() in default_files:
                    continue
                
                mod_full = Path(mod_sound_dir, relative)
                
                if not mod_full.parent.exists():
                    mod_full.parent.mkdir(parents=True, exist_ok=True)
                
                utils.copy_file(full, mod_full)
                print(f"--- Copied {relative}")
    
class NWO_OT_OpenModFolder(bpy.types.Operator):
    bl_idname = "nwo.open_mod_folder"
    bl_label = "Open Mod Folder"
    bl_description = "Opens the mod folder for this asset"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        if not context.scene.nwo.mod_name:
            return False
        path = Path(utils.get_project_path(), "MCC", context.scene.nwo.mod_name)
        return path.exists()
    
    def execute(self, context):
        path = Path(utils.get_project_path(), "MCC", context.scene.nwo.mod_name)
        os.startfile(path)
        return {'FINISHED'}
            
class NWO_OT_LaunchMCC(bpy.types.Operator):
    bl_idname = "nwo.launch_mcc"
    bl_label = "Launch MCC"
    bl_description = "Launches the Steam version of The Masterchief Collection provied you have this installed"
    bl_options = {"UNDO"}
    
    def execute(self, context):
        os.startfile("steam://launch/976730/option2")
        time.sleep(5) # Give MCC a moment to launch to avoid the user double clicking the operator
        return {'FINISHED'}

class NWO_OT_CacheBuild(bpy.types.Operator):
    bl_idname = "nwo.cache_build"
    bl_label = "Build Cache File"
    bl_description = "Generates the cache file needed to load the map in MCC and optionally builds mod files"
    bl_options = {"UNDO"}
    
    filepath: bpy.props.StringProperty(
        name='Scenario Filepath',
        subtype='FILE_PATH',
        description="Path to the scenario tag file to generate a cache file (.map) from",
        options={"HIDDEN"},
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.scenario",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    build_mod: bpy.props.BoolProperty(
        name="Create Mod",
        description="Create an MCC mod for this cache file",
        default=True,
    )
    
    launch_mcc: bpy.props.BoolProperty(
        name="Launch MCC",
        description="Launches MCC once the cache file and optional mod files have been built",
        options={'SKIP_SAVE'}
    )
    
    rexport_scenario: bpy.props.BoolProperty(
        name="Export Scenario",
        description="Exports this scenario using the current export settings. Will run regardless if the scenario doesn't exist in the tags folder",
        default=False,
    )
    
    rebuild_cache: bpy.props.BoolProperty(
        name="Rebuild Cache File",
        description="Rebuilds the compiled .map file even if it already exists. If the map file does not exist inside of your project /maps directory, this operator will create it regardless of whether rebuild_cache is set",
        default=True
    )
    
    event_level: bpy.props.EnumProperty(
        name="Event Level",
        description="Describes the level of error/warning event reporting to be output during exports. ",
        options=set(),
        default='DEFAULT',
        items=[
            ("DEFAULT", "Default Events", ""),
            ("LOG", "Log Events", "Errors & warnings are logged to a separate file instead of being shown in the Blender output. This file will be opened once Tool has finished executing if any warnings or errors were reported"),
            ("VERBOSE", "Verbose Events", ""),
            ("STATUS", "Status Events", ""),
            ("MESSAGE", "Message Events", ""),
            ("WARNING", "Warning Events", ""),
            ("ERROR", "Error Events", ""),
            ("CRITICAL", "Critical Events", ""),
            ("NONE", "No Events", "No errors or warnings are reported"),
        ]
    )
    
    texture_analysis: bpy.props.BoolProperty(
        name="Run Faux Texture Analysis",
        description="Runs the faux_perform_texture_analysis Tool command which is necessary for textures to display correctly in MCC",
        default=True,
    )
    
    cubemap_farm: bpy.props.BoolProperty(
        name="Build Cubemaps",
        description="Runs the cubemap farm tool",
        default=False,
    )
    
    imposter_farm: bpy.props.BoolProperty(
        name="Build Instance Imposters",
        description="Runs the imposter farm tool",
        default=False,
    )
    
    wetness_farm: bpy.props.BoolProperty(
        name="Generate Wetness Data",
        description="Generates wetness data for all BSPs",
        default=False,
    )
    
    lightmap: bpy.props.BoolProperty(
        name="Lightmap",
        description="Lightmaps the scenario prior to building the cache file",
    )
    
    validate_multiplayer: bpy.props.BoolProperty(
        name="Validate Multiplayer",
        description="If this is a multiplayer scenario, ensures scenario tag settings for multiplayer are set up correctly for loading in MCC. This will also regenerate the multiplayer_object_types.bin file",
        default=True,
    )
    
    sounds: bpy.props.EnumProperty(
        name="Sounds",
        description="Sound files to include in mod directory. Sound files (fsb/pck) must exist in the sound folder of your project",
        items=[
            ('NONE', "Don't Copy Sounds", "Sound files are not copied to the mod folder. The mod will use the existing sound files in MCC"),
            ('CUSTOM', "Copy Custom Sounds", "Copies custom sound files to the mod folder. Custom sound files are defined as files whos name do not match any of the existing sound files that come with MCC. For example a MCC .FSB file with new sounds appended to it would not be copied over"),
            ('ALL', "Copy All Sounds", "All sounds files in this project are copied over to the mod folder")
        ]
    )

    @classmethod
    def poll(cls, context):
        return not utils.validate_ek()

    def execute(self, context):
        relative_path = Path(utils.relative_path(self.filepath))
        full_path = Path(utils.get_tags_path(), relative_path)
        force_asset_export = False
        own_asset = relative_path.with_suffix("").name == utils.get_asset_name()
        if not full_path.exists():
            if own_asset:
                force_asset_export = True
                print("--- Asset scenario does not exist, exporting")
            else:
                self.report({'WARNING'}, f"Specified scenario file does not exist: {full_path}")
                return {'CANCELLED'}
        
        scene_nwo_export = context.scene.nwo_export
        os.system("cls")
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()
            scene_nwo_export.show_output = False
        

        start = time.perf_counter()
        title = f"►►► CACHE BUILDER ◄◄◄"
        print(title)
        print("\nIf you did not intend to run this, hold CTRL+C")
        try:
            if force_asset_export or (self.rexport_scenario and own_asset):
                if bpy.ops.nwo.export_scene.poll():
                    bpy.ops.nwo.export_scene(for_cache_build=True)
                else:
                    utils.print_warning("Unable to export scenario")

            if not full_path.exists():
                self.report({'WARNING'}, f"Scenario file does not exist: {full_path}")
                return {'CANCELLED'}
            
            builder = CacheBuilder(relative_path, context, self.validate_multiplayer, own_asset)
            
            if self.wetness_farm:
                builder.wetness()
            
            if self.lightmap:
                if not scene_nwo_export.lightmap_all_bsps and scene_nwo_export.lightmap_specific_bsp not in builder.bsps:
                    utils.print_error(f"Skipping Lightmap. Specified BSP [{scene_nwo_export.lightmap_specific_bsp}] does not exist in the scenario tag: {builder.scenario.with_suffix('.scenario')}")
                else:
                    builder.lightmap()
                    
            if self.imposter_farm:
                builder.imposters()
                
            if self.cubemap_farm:
                builder.cubemaps()
            
            if utils.is_corinth(context) and self.texture_analysis:
                print("\n\nFaux Texture Analysis")
                print("-----------------------------------------------------------------------\n")
                builder.texture_analysis()
                
            if self.rebuild_cache or not builder.map.exists(): 
                print("\n\nBuilding Cache File")
                print("-----------------------------------------------------------------------\n")
                if not builder.build_cache(self.event_level if self.event_level != 'DEFAULT' else None):
                    utils.print_error("\nCache Build Failed")
                    self.report({'WARNING'}, "Failed to build .map file for scenario")
                    return {'CANCELLED'}
            
            if builder.do_mp_validation and builder.map.exists():
                print("\n\nGenerating Multiplayer Object Types")
                print("-----------------------------------------------------------------------\n")
                builder.generate_multiplayer_object_types()
            
            if self.build_mod:
                if builder.game_engine is None:
                    utils.print_error("Failed to determine game engine")
                    self.report({'WARNING'}, "Failed to determine game engine")
                    return {'CANCELLED'}
                
                print("\n\nBuilding MCC Mod Files")
                print("-----------------------------------------------------------------------\n")
                report = builder.build_mod()
                if report is not None:
                    utils.print_error(report)
                    self.report({'WARNING'}, report)
                    return {'CANCELLED'}
                
                print(f"Mod files generated and saved to: {builder.mod_dir}")
                
                context.scene.nwo.mod_name = builder.mod_name
                
            match self.sounds:
                case 'CUSTOM':
                    print("\n\nCopying Custom Sounds")
                    print("-----------------------------------------------------------------------\n")
                    builder.copy_sounds(True)
                case 'ALL':
                    print("\n\nCopying All Sounds")
                    print("-----------------------------------------------------------------------\n")
                    builder.copy_sounds(False)
                
            print("\n-----------------------------------------------------------------------")
            print(f"Cache Build Completed in {utils.human_time(time.perf_counter() - start, True)}")
            print("-----------------------------------------------------------------------\n")
            
            if self.launch_mcc:
                print("Launching MCC...")
                os.startfile("steam://launch/976730/option2")
            
            self.report({'INFO'}, "Cache Build Successful")
        
        except KeyboardInterrupt:
            utils.print_warning("\n\nCANCELLED BY USER")
            
        return {"FINISHED"}
    
    def invoke(self, context, event):
        if not self.filepath.lower().endswith(".scenario"):
            asset_path = utils.get_asset_path_full(True)
            if asset_path:
                path = Path(asset_path, f"{utils.get_asset_name()}.scenario")
                if not path.parent.exists():
                    path.parent.mkdir(parents=True)
                self.filepath = str(path)
            else:
                self.filepath = utils.get_tags_path() + os.sep
        else:
            self.filepath = utils.get_tags_path() + os.sep
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        corinth = utils.is_corinth(context)
        layout = self.layout
        layout.scale_y = 1.5
        layout.prop(self, "event_level", text="")
        layout.prop(self, "sounds", text="")
        layout.prop(self, "rebuild_cache")
        layout.prop(self, "build_mod")
        layout.prop(self, "validate_multiplayer")
        if corinth:
            layout.prop(self, "texture_analysis")
        layout.prop(self, "launch_mcc")
        layout.prop(self, "rexport_scenario")
        layout.prop(self, "lightmap")
        if self.lightmap:
            export = context.scene.nwo_export
            if corinth:
                layout.prop(export, "lightmap_quality_h4")
            else:
                layout.prop(export, "lightmap_quality")
            if not export.lightmap_all_bsps:
                layout.prop(export, "lightmap_specific_bsp")
            layout.prop(export, "lightmap_all_bsps")
            if not corinth:
                layout.prop(export, "lightmap_threads")

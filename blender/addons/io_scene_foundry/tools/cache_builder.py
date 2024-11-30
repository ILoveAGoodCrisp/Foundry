from enum import Enum
import os
from pathlib import Path
import time
import bpy
import json
from uuid import uuid4

from ..managed_blam.scenario import ScenarioTag
from .. import utils

class GameEngine(Enum):
    halo_reach = 6
    halo_4 = 3
    halo_2amp = 4
    
class ScenarioType(Enum):
    CAMPAIGN = 0
    MULTIPLAYER = 1
    FIREFIGHT = 2
    
class CacheBuilder:
    def __init__(self, scenario_path: Path, context: bpy.types.Context):
        project_dir = utils.get_project_path()
        self.scenario = scenario_path.with_suffix("")
        self.mod_name = self.scenario.name
        self.map = Path(project_dir, "maps", f"{self.mod_name}.map")
        self.mcc_mods = Path(project_dir, "MCC")
        self.mod_dir = Path(self.mcc_mods, self.mod_name)
        self.game_engine = utils.project_game_for_mcc(context)
        self.scenario_type = ScenarioType.CAMPAIGN
        with ScenarioTag(path=scenario_path) as tag:
            if tag.survival_mode():
                self.scenario_type = ScenarioType.FIREFIGHT
            elif tag.read_scenario_type() == 1:
                self.scenario_type = ScenarioType.MULTIPLAYER
    
    def build_cache(self, event_level=None) -> bool:
        # Get scenario type
        
        # clear existing map file
        if self.map.exists():
            self.map.unlink()
        utils.run_tool(
            [
                "build-cache-file",
                str(self.scenario)
            ],
            event_level=event_level
        )
        
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
            
        utils.copy_file(self.map, Path(mod_maps_dir, self.map.name))
                
        # Create JSON data
        # Mod info JSON
        mod_info = Path(self.mod_dir, "ModInfo.json")
        # Use existing guid if available
        existing_mod_info_guid = None
        if mod_info.exists():
            try:
                with open(mod_info, "r") as file:
                    existing_mod_info_guid = json.load(file)["ModIdentifier"]["ModGuid"]
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
                "Neutral": self.mod_name
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
                    json.dump(campaign_info_dict, file)
                
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
                        "Neutral": self.mod_name
                    },
                    "Images": {
                        "Large": r"images\large.png",
                        "Thumbnail": r"images\thumbnail.png",
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
                                "Neutral": "Alpha"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 0"
                            },
                            "ODST": {},
                            "Thumbnail": ""
                        },
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 1,
                            "Valid": True,
                            "Title": {
                                "Neutral": "Bravo"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 1"
                            },
                            "ODST": {},
                            "Thumbnail": ""
                        },
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 2,
                            "Valid": True,
                            "Title": {
                                "Neutral": "Charlie"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 2"
                            },
                            "ODST": {},
                            "Thumbnail": ""
                        },
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 3,
                            "Valid": True,
                            "Title": {
                                "Neutral": "Delta"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 3"
                            },
                            "ODST": {},
                            "Thumbnail": ""
                        },
                        {
                            "ZoneSetName": "",
                            "ZoneSetIndex": 4,
                            "Valid": True,
                            "Title": {
                                "Neutral": "Echo"
                            },
                            "Description": {
                                "Neutral": "Loads level with game_insertion_point set to 4"
                            },
                            "ODST": {},
                            "Thumbnail": ""
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
                    json.dump(campaign_map_info_dict, file)
                
            case ScenarioType.MULTIPLAYER:
                mp_dir = Path(self.mod_dir, "multiplayer")
                if not mp_dir.exists():
                    mp_dir.mkdir()
                    
                mp_info = Path(mp_dir, f"{self.mod_name}.json")
                
                existing_mp_info_guid = None
                if mp_info.exists():
                    try:
                        with open(mp_info, "r") as file:
                            existing_mp_info_guid = json.load(file)["MapGuid"]
                    except: ...
                
                mp_info_dict = {
                        "MapGuid": existing_mp_info_guid if existing_mp_info_guid is not None else str(uuid4()),
                        "ScenarioFile": str(self.scenario),
                        "Title": {
                            "Neutral": self.mod_name
                        },
                        "Description": {
                            "Neutral": f"Forged in Foundry at {time.strftime('%Y-%m-%d-%H:%M:%S')}"
                        },
                        "Images": {
                            "Large": r"images\large.png",
                            "Thumbnail": r"images\thumbnail.png",
                            "LoadingScreen": r"images\loading_screen.png",
                            "TopDown": r"images\top_down.png"
                        },
                        "Flags": [
                            "DisableSavedFilms"
                        ],
                        "InsertionPoints": [],
                        "MaximumTeamsByGameCategory": {},
                    }
                
                with open(mp_info, "w") as file:
                    json.dump(mp_info_dict, file)
                    
                mod_info_dict["GameModContents"]["MultiplayerMaps"] = [str(mp_info.relative_to(self.mod_dir))]
                    
            case ScenarioType.FIREFIGHT:
                pass
                # mod_info_dict["GameModContents"]["FirefightMaps"] = [str(ff_info.relative_to(self.mod_dir))]
            
        with open(mod_info, "w") as file:
            json.dump(mod_info_dict, file)

class NWO_OT_CacheBuild(bpy.types.Operator):
    bl_idname = "nwo.cache_build"
    bl_label = "Build Cache File"
    bl_description = "Generates the cache file needed to load the map in MCC and optionally builds mod files"
    bl_options = {"UNDO"}
    
    filepath: bpy.props.StringProperty(
        name='Scenario Filepath',
        subtype='FILE_PATH',
        description="Path to the scenario tag file to generate a cache file (.map) from",
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
        description="Launches MCC once the cache file and optional mod files have been built"
    )
    
    event_level: bpy.props.EnumProperty(
        name="Event Level",
        description="Describes the level of error/warning event reporting to be output during exports. ",
        options=set(),
        default='DEFAULT',
        items=[
            ("DEFAULT", "Default Events", ""),
            ("VERBOSE", "Verbose Events", ""),
            ("STATUS", "Status Events", ""),
            ("MESSAGE", "Message Events", ""),
            ("WARNING", "Warning Events", ""),
            ("ERROR", "Error Events", ""),
            ("CRITICAL", "Critical Events", ""),
            ("NONE", "No Events", "No errors or warnings are reported"),
        ]
    )

    @classmethod
    def poll(cls, context):
        return not utils.validate_ek() and context.scene.nwo.asset_type == 'scenario'

    def execute(self, context):
        relative_path = Path(utils.relative_path(self.filepath))
        full_path = Path(utils.get_tags_path(), relative_path)
        if not full_path.exists():
            self.report({'WARNING'}, f"Specified scenario file does not exist: {full_path}")
            return {'CANCELLED'}
        
        builder = CacheBuilder(relative_path, context)
        
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
            print("\n\nBuilding Cache File\n")
            print("-----------------------------------------------------------------------\n")
            if not builder.build_cache(self.event_level if self.event_level != 'DEFAULT' else None):
                utils.print_error("Cache Build Failed")
                self.report({'WARNING'}, "Failed to build .map file for scenario")
                return {'CANCELLED'}
            
            
            if self.build_mod:
                if builder.game_engine is None:
                    utils.print_error("Failed to determine game engine")
                    self.report({'WARNING'}, "Failed to determine game engine")
                    return {'CANCELLED'}
                
                print("\n\nBuilding MCC Mod Files\n")
                print("-----------------------------------------------------------------------\n")
                report = builder.build_mod()
                if report is not None:
                    utils.print_error(report)
                    self.report({'WARNING'}, report)
                    return {'CANCELLED'}
                
                print(f"Mod files generated and saved to: {builder.mod_dir}")
                
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
            if asset_path is not None:
                self.filepath = str(Path(asset_path, f"{utils.get_asset_name()}.scenario"))
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "event_level", text="")
        layout.prop(self, "build_mod")
        layout.prop(self, "launch_mcc")
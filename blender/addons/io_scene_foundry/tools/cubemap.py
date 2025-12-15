

import ctypes
import bpy
import os
import time
import shutil

from ..managed_blam import Tag
from ..managed_blam.scenario import ScenarioTag
from ..managed_blam.bitmap import BitmapTag
from .. import utils
from pathlib import Path

instructions_given = False

class Cubemap:
    def __init__(self, x, y, z) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.checksum_pair = self._registration_points()
        
    def _registration_points(self):
        rpx = self._calculate_checksum()
        rpy = rpx >> 0x10
        return str(rpx), str(rpy)
    
    def _calculate_checksum(self) -> int:
        x, y, z = int(self.x * 10), int(self.y * 10), int(self.z * 10)
        uVar1 = (y + -456204533) & 0xFFFFFFFF
        uVar4 = ((z + -456204533 ^ uVar1) - (uVar1 >> 0x12 ^ uVar1 * 0x4000)) & 0xFFFFFFFF
        uVar3 = ((-456204533 + x ^ uVar4) - (uVar4 >> 0x15 ^ uVar4 * 0x800)) & 0xFFFFFFFF
        uVar2 = ((uVar1 ^ uVar3) - (uVar3 * 0x2000000 ^ uVar3 >> 7)) & 0xFFFFFFFF
        uVar4 = ((uVar4 ^ uVar2) - (uVar2 >> 0x10 ^ uVar2 * 0x10000)) & 0xFFFFFFFF
        uVar1 = ((uVar4 ^ uVar3) - (uVar4 >> 0x1c ^ uVar4 * 0x10)) & 0xFFFFFFFF
        uVar1 = ((uVar2 ^ uVar1) - (uVar1 >> 0x12 ^ uVar1 * 0x4000)) & 0xFFFFFFFF
        return (uVar4 ^ uVar1) - (uVar1 * 0x1000000 ^ uVar1 >> 8)

class CubemapFarm:
    def __init__(self, scenario_path) -> None:
        self.scenario_path = scenario_path
        self.scenario_path_no_ext = str(Path(scenario_path).with_suffix(""))
        self.project_dir = Path(utils.get_project_path())
        self.cubemaps_dir = Path(self.project_dir, "cubemaps")
        
    def get_tagplay_exe(self):
        for file in self.project_dir.iterdir():
            if str(file).lower().endswith("tag_play.exe"):
                return str(file)
            
    def ensure_cubemap_points(self):
        with ScenarioTag(path=self.scenario_path) as scenario:
            block_cubemaps = scenario.tag.SelectField("Block:cubemaps")
            if block_cubemaps.Elements.Count > 0:
                return
            else:
                print("Scenario has no cubemaps, adding default cubemap at position 0.0,0.0,0.6")
                element = block_cubemaps.AddElement()
                element.SelectField("cubemap position").Data = 0.0, 0.0, 0.6
                scenario.tag_has_changes = True
                resources = scenario.tag.SelectField("Block:scenario resources")
                if resources.Elements.Count > 0:
                    split_resources = resources.SelectField("Block:new split resources")
                    if split_resources.Elements.Count > 0:
                        cubemap_resource = split_resources.SelectField("Reference:cubemap reference resource")
                        path = scenario.get_path_str(cubemap_resource.Path, True)
                        if path and Path(path).exists():
                            with Tag(path=path) as resource:
                                block_cubemaps = resource.tag.SelectField("Block:cubemaps")
                                element = block_cubemaps.AddElement()
                                element.SelectField("cubemap position").Data = 0.0, 0.0, 0.6
                                resource.tag_has_changes = True
    
    def launch_game(self):
        executable = self.get_tagplay_exe()
        try:
            with open(Path(self.project_dir, "bonobo_init.txt"), "w") as init:
                if utils.is_corinth():
                    init.write("prune_globals 1\n")
                else:
                    init.write("prune_global 1\n")
                init.write(f"game_start {self.scenario_path_no_ext}\n")
                init.write("run_game_scripts 0\n")
                init.write('error_geometry_hide_all\n')
                init.write('events_enabled 0\n')
                init.write('ai_hide_actor_errors 1\n')
                # init.write('terminal_render 0\n')
                init.write('console_status_string_render 0\n')
                init.write('events_debug_spam_render 0\n')
                init.write("motion_blur 0\n")
        except:
            print("Unable to replace bonobo_init.txt. It is currently read only")
        
        utils.update_debug_menu(update_type=utils.DebugMenuType.CUBEMAP)
        
        if self.cubemaps_dir.exists():
            utils.clear_directory(self.cubemaps_dir)
                
        print("Loading game...")
        use_instructions = "1. Once the game has loaded press HOME on your keyboard to open the debug menu\n2. Scroll to the bottom of the menu and press enter on the Generate Dynamic Cubemaps command\n3. Wait for the process to complete\n4. Exit the game using SHIFT+ESC\n"
        global instructions_given
        if not instructions_given:
            ctypes.windll.user32.MessageBoxW(
                None,
                use_instructions,
                "Cubemap Generation Instructions",
                0x00000040,
            )
            instructions_given = True
        print("Waiting for the game to close...\n")
        utils.run_ek_cmd([executable])
            
    def write_cubemap_bitmaps(self):
        if not self.cubemaps_dir.exists():
            return f"No cubemap source files found at {str(Path(self.project_dir, 'cubemaps'))}"
        cubemaps: list[Cubemap] = []
        index_map = self._bsp_cubemap_index_map()
        if not index_map or not any(index_map.values()):
            return f"No valid cubemap source files found at {str(Path(self.project_dir, 'cubemaps'))}"
        with ScenarioTag(path=self.scenario_path) as scenario:
            block_cubemaps = scenario.tag.SelectField("Block:cubemaps")
            if block_cubemaps.Elements.Count <= 0:
                return "Scenario has no cubemaps"
            for element in block_cubemaps.Elements:
                position = element.SelectField("cubemap position")
                points = position.Data
                cubemaps.append(Cubemap(points[0], points[1], points[2]))
        
            print("--- Generating cubemap bitmap tag")
            utils.run_tool(["cubemaps", self.scenario_path_no_ext, self.cubemaps_dir])
            print("\n--- Fixing up cubemap bitmap checksums")
                
            for bsp_element in scenario.block_bsps.Elements:
                bsp_tagpath = bsp_element.SelectField("structure bsp").Path
                bsp_name = bsp_tagpath.ShortName
                scenario_name = Path(self.scenario_path_no_ext).name
                cubemap_bitmap_name = f"{scenario_name}_{bsp_name}_cubemaps.bitmap"
                scenario_dir = Path(self.scenario_path_no_ext).parent
                cubemap_bitmap_path = str(Path(scenario_dir, cubemap_bitmap_name))
                if utils.is_corinth():
                    bitmap_tagpath = bsp_element.SelectField("bsp specific cubemap")
                else:
                    bitmap_tagpath = bsp_element.SelectField("cubemap bitmap group reference")
                
                cubemap_bitmap_tagpath = scenario._TagPath_from_string(cubemap_bitmap_path)
                if bitmap_tagpath.Path != cubemap_bitmap_tagpath:
                    bitmap_tagpath.Path = cubemap_bitmap_tagpath
                    scenario.tag_has_changes = True
                
                bitmap_path = Path(bitmap_tagpath.Path.Filename)
                if bitmap_path.exists():   
                    with BitmapTag(path=bitmap_path) as bitmap:
                        bitmap_cubemap_indices = index_map.get(bsp_element.ElementIndex, None)
                        if bitmap_cubemap_indices is None: continue
                        for bitmap_element in bitmap.block_bitmaps.Elements:
                            current_cubemap_index = bitmap_cubemap_indices[bitmap_element.ElementIndex]
                            field_registration_point = bitmap_element.SelectField("registration point")
                            rpx, rpy = cubemaps[current_cubemap_index].checksum_pair
                            field_registration_point.SetStringData([rpx, rpy])
                        
                        bitmap.tag_has_changes = True
                        
        return ""
                
    def _bsp_cubemap_index_map(self) -> dict:
        index_map = {}
        for item in self.cubemaps_dir.iterdir():
            if item.is_dir() and item.name.startswith("bsp"):
                current_bsp_index = int(item.name[3:])
                index_set = set()
                for file in item.iterdir():
                    if file.name.startswith("cubemap_"):
                        cubemap_index = int(file.with_suffix("").name.split("_")[1])
                        index_set.add(cubemap_index)
                        
                index_map[current_bsp_index] = sorted(index_set)
        
        return index_map
                        

class NWO_OT_Cubemap(bpy.types.Operator):
    bl_idname = "nwo.cubemap"
    bl_label = "Cubemap Farm"
    bl_description = "Generates Cubemaps for a scenario"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.current_project_valid()
        
    filepath: bpy.props.StringProperty(
        name='Scenario Filepath',
        subtype='FILE_PATH',
        description="Path to the scenario tag to generate a cubemap bitmap for",
        options={"HIDDEN"},
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.scenario",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    launch_game: bpy.props.BoolProperty(
        name="Generate Cubemap Source files",
        description="Launches Tag Play for dynamic cubemap generation to be ran. Access the debug menu via the home button post launch to execute the command (this should be at the bottom of your debug menu). Close the game when complete to continue the process",
        default=True,
    )

    def execute(self, context):
        scene_nwo_export = utils.get_export_props()
        if not self.filepath or Path(self.filepath).suffix.lower() != ".scenario":
            self.report({"WARNING"}, "No scenario path given. Operation cancelled")
            return {'CANCELLED'}
        farm = CubemapFarm(utils.relative_path(self.filepath))
        os.system("cls")
        if scene_nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            print(f"►►► CUBEMAP FARM ◄◄◄")
        farm.ensure_cubemap_points()
        if self.launch_game:
            farm.launch_game()
        start = time.perf_counter()
        message = farm.write_cubemap_bitmaps()
        if message:
            self.report({'WARNING'}, message)
            utils.print_warning("\n Cubemap farm cancelled")
            return {"CANCELLED"}
        end = time.perf_counter()
        print("\n-----------------------------------------------------------------------")
        print(f"Cubemaps generated in {utils.human_time(end - start, True)}")
        print("-----------------------------------------------------------------------")
        return {"FINISHED"}
    
    def invoke(self, context, event):
        scene_nwo = utils.get_scene_props()
        tags_dir = utils.get_tags_path() + os.sep
        self.filepath = tags_dir
        if utils.valid_nwo_asset() and scene_nwo.asset_type == "scenario":
            asset_path, asset_name = utils.get_asset_info()
            if asset_path and asset_name:
                self.filepath = str(Path(tags_dir, asset_path, asset_name).with_suffix(".scenario"))
                
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        # layout.prop(self, "scenario_path")
        layout.prop(self, "launch_game")
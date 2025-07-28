

import ctypes
import bpy
import os
import time
import shutil
from ..managed_blam.scenario import ScenarioTag
from ..managed_blam.bitmap import BitmapTag
from .. import utils
from pathlib import Path

instructions_given = False

class ImposterFarm:
    def __init__(self, scenario_path) -> None:
        self.scenario_path = scenario_path
        self.scenario_path_no_ext = str(Path(scenario_path).with_suffix(""))
        self.project_dir = Path(utils.get_project_path())
        self.imposter_cache_dir = Path(self.project_dir, "imposter_cache")
        
    def get_tagplay_exe(self):
        for file in self.project_dir.iterdir():
            if str(file).lower().endswith("tag_play.exe"):
                return str(file)
    
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
        
        utils.update_debug_menu(update_type=utils.DebugMenuType.IMPOSTER)
        
        if self.imposter_cache_dir.exists():
            try:
                shutil.rmtree(self.imposter_cache_dir)
            except:
                utils.print_warning(f"Failed to remove existing imposter_cache directory: {self.imposter_cache_dir}")
                
        print("Loading game...")
        use_instructions = "1. Once the game has loaded press HOME on your keyboard to open the debug menu\n2. Scroll to the bottom of the menu and press enter on the Generate Imposter Source Files command\n3. Wait for the process to complete\n4. Exit the game using SHIFT+ESC\n"
        global instructions_given
        if not instructions_given:
            ctypes.windll.user32.MessageBoxW(
                None,
                use_instructions,
                "Imposter Instructions",
                0x00000040,
            )
            instructions_given = True
        print("Waiting for the game to close...\n")
        utils.run_ek_cmd([executable])
            
    def process_imposter(self):
        if not self.imposter_cache_dir.exists():
            return f"No imposter_cache files found at {str(Path(self.project_dir, 'imposter_cache'))}"
        print("--- Processing Imposters")
        utils.run_tool(["process_imposters", ".\\"])
        print("\n--- Building Instance Imposters")
        utils.run_tool(["build-instance-imposter", ".\\"])
        
        return "Done"

class NWO_OT_InstanceImposterGenerate(bpy.types.Operator):
    bl_idname = "nwo.instance_imposter_generate"
    bl_label = "Instance Imposter Farm"
    bl_description = "Generates imposter models for all instance geometry in a level"
    bl_options = {"UNDO"}
        
    filepath: bpy.props.StringProperty(
        name='Scenario Filepath',
        subtype='FILE_PATH',
        description="Path to the scenario tag to generate a imposters for",
        options={"HIDDEN"},
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.scenario",
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    launch_game: bpy.props.BoolProperty(
        name="Generate Cubemap Source files",
        description="Launches Tag Play for dynamic imposter snapshot to be ran. Access the debug menu via the home button post launch to execute the command (this should be at the bottom of your debug menu). Close the game when complete to continue the process",
        default=True,
    )
    
    bsp: bpy.props.EnumProperty(
        name="BSP",
        description="Select the BSP to generate imposters. Defaults to all BSPs"
    )

    def execute(self, context):
        if not self.filepath or Path(self.filepath).suffix.lower() != ".scenario":
            self.report({"WARNING"}, "No scenario path given. Operation cancelled")
            return {'CANCELLED'}
        farm = ImposterFarm(utils.relative_path(self.filepath))
        os.system("cls")
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            print(f"►►► IMPOSTER FARM ◄◄◄")
        if self.launch_game:
            farm.launch_game()
        start = time.perf_counter()
        message = farm.process_imposter()
        if message:
            self.report({'WARNING'}, message)
            utils.print_warning("\n Imposter farm cancelled")
            return {"CANCELLED"}
        end = time.perf_counter()
        print("\n-----------------------------------------------------------------------")
        print(f"Imposters generated in {utils.human_time(end - start, True)}")
        print("-----------------------------------------------------------------------")
        return {"FINISHED"}
    
    def invoke(self, context, event):
        if utils.valid_nwo_asset() and context.scene.nwo.asset_type == "scenario":
            asset_path, asset_name = utils.get_asset_info()
            if asset_path and asset_name:
                self.filepath = str(Path(asset_path, asset_name).with_suffix(".scenario"))
            else:
                self.filepath = utils.get_tags_path() + os.sep
        else:
            self.filepath = utils.get_tags_path() + os.sep
            
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        # layout.prop(self, "scenario_path")
        layout.prop(self, "launch_game")
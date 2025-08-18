

import ctypes
from subprocess import check_call
import bpy
import os
import time
import shutil
from ..managed_blam.scenario import ScenarioTag
from ..managed_blam.bitmap import BitmapTag
from .. import utils
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

instructions_given = False

def process_imposter(file_path):
    utils.run_tool(["process-imposter", file_path], null_output=True)

def move_metadata(src: Path, dst: Path):
    shutil.move(str(src), str(dst))
    
def build_instance_imposter(file_path):
    utils.run_tool(["build-instance-imposter", file_path], null_output=True)
    
spinny = iter(['|', '/', '-', '\\'])

class ImposterFarm:
    def __init__(self, scenario_path) -> None:
        self.scenario_path = scenario_path
        self.scenario_path_no_ext = str(Path(scenario_path).with_suffix(""))
        self.project_dir = Path(utils.get_project_path())
        self.imposter_cache_dir = Path(self.project_dir, "imposter_cache")
        
    def get_tagtest_exe(self):
        for file in self.project_dir.iterdir():
            if str(file).lower().endswith("tag_test.exe"):
                return str(file)
    
    def launch_game(self, clear_imposter_cache=False):
        executable = self.get_tagtest_exe()
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
        
        with ScenarioTag(path=self.scenario_path) as scenario:
            utils.update_debug_menu(update_type=utils.DebugMenuType.IMPOSTER, bsp_names=scenario.get_bsp_names())
        
        if clear_imposter_cache and self.imposter_cache_dir.exists():
            try:
                shutil.rmtree(self.imposter_cache_dir)
            except:
                utils.print_warning(f"Failed to remove existing imposter_cache directory: {self.imposter_cache_dir}")
                
        print("Loading game...")
        use_instructions = "NOTE: This will only work on lightmapped BSPs!\n\n1. Once the game has loaded press HOME on your keyboard to open the debug menu\n2. Scroll to the bottom of the menu and press enter on the Generate Instance Imposters for each BSP you wish to run this on\n3. Wait for the process to complete (Tag Test may appear unresponsive but this is normal)\n4. Exit the game using SHIFT+ESC\n"
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
        
        os.chdir(utils.get_project_path())

        oss_files = []
        
        for root, dirs, files in os.walk(self.imposter_cache_dir):
            for file in files:
                if file.endswith(".oss"):
                    oss_files.append(str(Path(root, file).relative_to(self.imposter_cache_dir).with_suffix('')))
                    
        total = len(oss_files)
        completed = 0
        
        utils.update_job_count("--- Processing Imposters", "", 0, total)
        with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            futures = {executor.submit(process_imposter, f): f for f in oss_files}
            
            for _ in as_completed(futures):
                completed += 1
                utils.update_job_count("--- Processing Imposters", "", completed, total)
        
        move_tasks = []
        bsp_dirs = []

        for dir in self.imposter_cache_dir.iterdir():
            if dir.is_dir():
                # print(f"-- {dir.name}")
                for subdir in dir.iterdir():
                    if subdir.is_dir():
                        for file in subdir.iterdir():
                            if file.is_file() and file.suffix == ".imposter_metadata":
                                target = dir / file.name
                                move_tasks.append((file, target))
                                
                bsp_dirs.append(dir.name)
                
        total = len(move_tasks)
        completed = 0
        
        utils.update_job_count("--- Moving Imposter Metadata", "", 0, total)
        with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            futures = {executor.submit(move_metadata, src, dst): (src, dst) for src, dst in move_tasks}
            
            for _ in as_completed(futures):
                completed += 1
                utils.update_job_count("--- Moving Imposter Metadata", "", completed, total)
                
        total = len(bsp_dirs)
        completed = 0

        utils.update_job_count("--- Building Instance Imposter Definition Tags", "", 0, total)
        with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            futures = {executor.submit(build_instance_imposter, f): f for f in bsp_dirs}
            
            for _ in as_completed(futures):
                completed += 1
                utils.update_job_count("--- Building Instance Imposter Definition Tags", "", completed, total)
            
        return ""

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
        name="Generate Imposter Source Files",
        description="Launches Tag Play for dynamic imposter snapshot to be ran. Access the debug menu via the home button post launch to execute the command (this should be at the bottom of your debug menu). Close the game when complete to continue the process",
        default=True,
    )
    
    clear_imposter_cache: bpy.props.BoolProperty(
        name="Clear Imposter Cache",
        description="Deletes the existing imposter_cache before loading the game",
        default=True,
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
            farm.launch_game(self.clear_imposter_cache)
            
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
        tags_dir = utils.get_tags_path() + os.sep
        self.filepath = tags_dir
        if utils.valid_nwo_asset() and context.scene.nwo.asset_type == "scenario":
            asset_path, asset_name = utils.get_asset_info()
            if asset_path and asset_name:
                self.filepath = str(Path(tags_dir, asset_path, asset_name).with_suffix(".scenario"))
            
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        # layout.prop(self, "scenario_path")
        layout.prop(self, "launch_game")
        if self.launch_game:
            layout.prop(self, "clear_imposter_cache")
import datetime
from contextlib import ExitStack
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
from pathlib import Path
import bpy
from subprocess import CalledProcessError

from ...patches import ToolPatcher

from ...tags.lightmapper_globals import LightmapperGlobalsTag

from ...tags.scenario import ScenarioMetadataTag
from ... import utils, foundry_output
import os

def scenario_exists() -> bool:
    asset_dir, asset_name = utils.get_asset_info()
    scenario_path = Path(utils.get_tags_path(), asset_dir, asset_name).with_suffix('.scenario')
    return scenario_path.exists()

def model_exists() -> bool:
    asset_dir, asset_name = utils.get_asset_info()
    model_path = Path(utils.get_tags_path(), asset_dir, asset_name).with_suffix('.model')
    return model_path.exists()

def ulong_to_long_sub(u):
    if (u > (1 << 32)):
        u = u & 0xFFFFFFFF
    return u - (1 << 32) if u >= (1<<31) else u
        
def calc_job_id(scenario, bsp):
    hash = 0x117
    for char in scenario:
        hash ^= (hash << 11) ^ ord(char)
    for char in bsp:
        hash ^= (hash << 7) ^ ord(char)
    return abs(ulong_to_long_sub(hash))

def tool_error_code(error=None, returncode=None):
    code = returncode if returncode is not None else getattr(error, "returncode", None)
    if code is None:
        return "unknown"
    signed_code = ulong_to_long_sub(code) if isinstance(code, int) else code
    if signed_code != code:
        return f"{signed_code} ({code})"
    return str(code)


def halo1_lightmap_commands(scenario_path, bsps, quality, stop_threshold, noassert=False):
    """Build H1 Tool arguments for a scenario tag path and BSP tag names."""
    if quality not in {'0', '1'}:
        raise ValueError(f"Invalid Halo 1 radiosity quality: {quality}")
    threshold = float(stop_threshold)
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("Halo 1 lightmap stop threshold must be greater than zero")
    if not bsps:
        raise ValueError("No BSPs selected for Halo 1 lightmapping")
    commands = []
    for bsp in bsps:
        if not bsp:
            raise ValueError("Halo 1 lightmapping requires a BSP name")
        command = ['lightmaps', str(scenario_path), bsp, quality, str(threshold)]
        if noassert:
            command.append('-noassert')
        commands.append(command)
    return commands


def run_halo1_lightmapper(scenario_path, bsps, export_settings):
    commands = halo1_lightmap_commands(
            scenario_path, bsps, export_settings.lightmap_quality_h1,
            export_settings.lightmap_stop_threshold_h1,
            export_settings.lightmap_noassert_h1)
    if len(commands) == 1:
        print(f"--- Lightmapping BSP {commands[0][2]}")
        utils.run_tool(commands[0], force_tool=True, console_output=True,
                       event_level=export_settings.event_level)
        return

    # Resolve all Blender state and shared Tool configuration before workers run.
    jobs = [(command[2], utils.prepare_tool(
        command, force_tool=True, console_output=True,
        event_level=export_settings.event_level)) for command in commands]
    workers = min(len(jobs), os.cpu_count() or 1)
    print(f"--- Lightmapping {len(jobs)} BSPs ({workers} concurrent processes)")

    def lightmap_bsp(bsp, run):
        print(f"--- Lightmapping BSP {bsp}")
        run()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(lightmap_bsp, bsp, run): bsp for bsp, run in jobs}
        try:
            for future in as_completed(futures):
                bsp = futures[future]
                try:
                    future.result()
                except CalledProcessError as error:
                    utils.print_error(f"Lightmapping BSP {bsp} failed: Tool.exe exited with code {tool_error_code(error)}")
                    raise
                print(f"--- Finished lightmapping BSP {bsp}")
        except BaseException:
            # Do not start queued BSPs after failure/cancellation. The executor
            # waits for running Tool jobs before returning control to Blender.
            for future in futures:
                future.cancel()
            raise


class NWO_OT_Lightmap(bpy.types.Operator):
    bl_idname = "nwo.lightmap"
    bl_label = "Lightmap"
    bl_options = {"UNDO"}
    bl_description = "Runs lightmap generation on the current asset"

    @classmethod
    def poll(cls, context):
        if not utils.valid_nwo_asset(context):
            return False
        asset_type = utils.get_scene_props().asset_type
        if utils.is_corinth(context):
            if asset_type == 'scenario':
                return scenario_exists()
            elif asset_type in ('model', 'sky'):
                return model_exists()
            else:
                return False
        else:
            return asset_type == 'scenario' and scenario_exists()

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        scene_nwo_export = utils.get_export_props()
        asset_type = scene_nwo.asset_type
        asset_path, asset_name = utils.get_asset_info()
        scenario_path = str(Path(asset_path, asset_name))
        is_corinth = utils.is_corinth(context)
        project = utils.get_project(scene_nwo.scene_project)
        halo1 = bool(project and project.game == 'halo1')
        utils.clear_output()
        if scene_nwo_export.show_output:
            utils.show_output()  # open Foundry Output so users can see progress
            scene_nwo_export.show_output = False

        export_title = f"►►► LIGHTMAPPER ◄◄◄"
        print(export_title)
        with ScenarioMetadataTag() as scenario:
            bsps = scenario.get_bsp_names()
            if not scene_nwo_export.lightmap_all_bsps and scene_nwo_export.lightmap_specific_bsp not in bsps:
                utils.print_error(f"Cancelling Lightmap. Specified BSP [{scene_nwo_export.lightmap_specific_bsp}] does not exist in the scenario tag: {scenario.tag_path.RelativePathWithExtension}")
                self.report({'WARNING'}, f"Specified BSP [{scene_nwo_export.lightmap_specific_bsp}] does not exist in the scenario tag: {scenario.tag_path.RelativePathWithExtension}")
                return {'CANCELLED'}
            
        try:
            if halo1:
                selected_bsps = bsps if scene_nwo_export.lightmap_all_bsps else [scene_nwo_export.lightmap_specific_bsp]
                run_halo1_lightmapper(scenario_path, selected_bsps, scene_nwo_export)
                return {'FINISHED'}
            lightmap_results = run_lightmapper(
                is_corinth,
                scenario_path,
                scene_nwo_export.lightmap_quality,
                scene_nwo_export.lightmap_quality_h4,
                scene_nwo_export.lightmap_all_bsps,
                scene_nwo_export.lightmap_specific_bsp,
                scene_nwo_export.lightmap_region.name if utils.pointer_ob_valid(scene_nwo_export.lightmap_region) else "",
                asset_type in ("model", "sky") and is_corinth,
                scene_nwo_export.lightmap_threads,
                bsps)
        except CalledProcessError as error:
            message = f"Lightmapping aborted because Tool.exe exited with code {tool_error_code(error)}"
            utils.print_error(message)
            self.report({'WARNING'}, message)
            return {'CANCELLED'}
        except ValueError as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        
        if lightmap_results.lightmap_failed:
            self.report({'WARNING'}, lightmap_results.lightmap_message)
            return {'CANCELLED'}

        return {"FINISHED"}
    
def run_lightmapper(
    not_bungie_game,
    scenario_path,
    lightmap_quality="direct_only",
    lightmap_quality_h4="__custom__",
    lightmap_all_bsps=True,
    lightmap_specific_bsp="default",
    lightmap_region="",
    model_lightmap=False,
    cpu_threads=1,
    structure_bsps=[],
):
    lightmap = LightMapper(
        not_bungie_game,
        lightmap_quality,
        lightmap_quality_h4,
        lightmap_all_bsps,
        lightmap_specific_bsp,
        lightmap_region,
        scenario_path,
        model_lightmap,
        cpu_threads,
        structure_bsps,
    )
    
    try:
        if not_bungie_game:
            lightmap_results = lightmap.lightmap_h4()
        else:
            project = utils.get_project(use_external=False)
            if project and project.game == 'halo2':
                lightmap_results = lightmap.lightmap_halo2()
            elif project and project.game in {'halo3', 'halo3odst'}:
                lightmap_results = lightmap.lightmap_halo3()
            else:
                lightmap_results = lightmap.lightmap_reach()
    except CalledProcessError as error:
        lightmap.abort_tool_error("lightmapping", error=error)
        lightmap_results = lightmap
        
    if lightmap_results.lightmap_failed:
        utils.print_error(lightmap_results.lightmap_message)
        proj = utils.get_project_path()
        if proj and lightmap_results.show_crash_report:
            crash_report = Path(proj, "crash_report", "crash_info.txt")
            if crash_report.exists():
                utils.print_warning("Showing last crash report")
                with open(crash_report, "r") as f:
                    utils.print_error(f.read())
    else:
        print(lightmap_results.lightmap_message)

    return lightmap_results


class LightMapper:
    def __init__(
        self,
        not_bungie_game,
        lightmap_quality,
        lightmap_quality_h4,
        lightmap_all_bsps,
        lightmap_specific_bsp,
        lightmap_region,
        scenario_path,
        model_lightmap,
        cpu_threads,
        structure_bsps,
    ):
        self.lightmap_message = "Lightmap Successful"
        self.lightmap_failed = False
        self.show_crash_report = True
        self.model_lightmap = model_lightmap
        self.scenario = scenario_path
        self.bsp = self.bsp_to_lightmap(lightmap_all_bsps, lightmap_specific_bsp)
        self.quality = lightmap_quality_h4 if not_bungie_game else lightmap_quality
        self.light_group = lightmap_region.lower()
        self.thread_count = cpu_threads
        self.bsps = structure_bsps
        self.tool_patches = []

    def bsp_to_lightmap(self, lightmap_all_bsps, lightmap_specific_bsp):
        bsp = "all"
        if not lightmap_all_bsps:
            bsp = lightmap_specific_bsp

        return bsp

    # EXECUTE LIGHTMAP ---------------------------------------------------------------------

    def print_exec_time(self):
        print(datetime.datetime.now() - self.start_time)

    def abort_tool_error(self, stage, error=None, returncode=None, log_filename=""):
        self.lightmap_failed = True
        self.show_crash_report = False
        message = f"Lightmapping aborted during {stage}: Tool.exe exited with code {tool_error_code(error, returncode)}"
        if log_filename:
            message += f". See error log for details: {log_filename}"
            message += "\nIf nothing is written to the above log, it may be that you have minimal space remaining on your disk drive"
        self.lightmap_message = message

    def run_tool_or_abort(self, tool_args, stage, **kwargs):
        if self.tool_patches and "tool_patches" not in kwargs:
            kwargs["tool_patches"] = self.tool_patches
        try:
            utils.run_tool(tool_args, **kwargs)
        except CalledProcessError as error:
            self.abort_tool_error(stage, error=error)
            return False
        return True

    def threads(self, stage, thread_index):
        # Tool runs in the project directory, but Blender's working directory
        # may be elsewhere (and may not be writable).
        log_filename = os.path.join(utils.get_project_path(), self.blob_dir, "logs", stage, f"{thread_index}.txt")
        log_dir = os.path.dirname(log_filename)
        os.makedirs(log_dir, exist_ok=True)
        with open(log_filename, "w") as log:
            p = utils.run_tool(
                    [
                        "faux_farm_" + stage,
                        self.blob_dir,
                        str(thread_index),
                        str(self.thread_count),
                    ],
                    True,
                    log_file=log,
                    force_tool_fast=True,
                    tool_patches=self.tool_patches)
            print(f"--- Spawned Process {thread_index}")
            return (p, log_filename)

    def farm(self, stage):
        # self.print_exec_time()
        processes = [
            self.threads(stage, thread_index)
            for thread_index in range(self.thread_count)
        ]
        print("--- Waiting for processes to complete")
        for idx, (p, log_filename) in enumerate(processes):
            returncode = p.wait()
            if returncode != 0:
                for remaining_process, _remaining_log in processes[idx + 1:]:
                    try:
                        if remaining_process.poll() is None:
                            remaining_process.kill()
                            remaining_process.wait()
                    except Exception:
                        pass
                self.abort_tool_error(stage, returncode=returncode, log_filename=log_filename)
                return False

        if not self.run_tool_or_abort(
            [
                "faux_farm_" + stage + "_merge",
                self.blob_dir,
                str(self.thread_count),
            ],
            "faux_farm_" + stage + "_merge",
            force_tool_fast=True,
        ):
            return False

        return True

    def lightmap_halo2(self):
        """Bake individual H2 BSPs, farming only when multiple workers are requested."""
        qualities = {'checkerboard', 'cuban', 'draft_low', 'draft_medium',
                     'draft_high', 'draft_super', 'direct_only', 'low',
                     'medium', 'high', 'super'}
        if self.quality not in qualities:
            raise ValueError(f'Invalid Halo 2 lightmap quality: {self.quality}')
        if self.thread_count < 1:
            raise ValueError('Halo 2 lightmapping requires at least one worker')
        bsps = list(dict.fromkeys(self.bsps if self.bsp == 'all' else [self.bsp]))
        if not bsps or any(not bsp for bsp in bsps):
            raise ValueError('No BSPs selected for Halo 2 lightmapping')
        self.tool_patches = []
        for bsp in bsps:
            print(f'--- Lightmapping BSP {bsp}')
            if self.thread_count == 1:
                if not self.run_tool_or_abort(
                    ['lightmaps', self.scenario, bsp, self.quality],
                    f'lightmaps ({bsp})', force_tool=True,
                ):
                    return self
            elif not self._halo2_farm(bsp):
                return self
        self.lightmap_message = f'{utils.formalise_string(self.quality)} Quality lightmap complete'
        return self

    def _halo2_farm(self, bsp):
        log_dir = Path(utils.get_project_path(), 'lightmap_logs', 'halo2',
                       str(calc_job_id(self.scenario, bsp)))
        log_dir.mkdir(parents=True, exist_ok=True)
        processes = []
        with ExitStack() as logs:
            try:
                # Worker zero writes shared scenery lighting data. Give all
                # other workers a 30-second head start before launching it.
                for index in [*range(1, self.thread_count), 0]:
                    if index == 0:
                        print('--- Waiting 30 seconds before launching worker 0')
                        deadline = time.monotonic() + 30
                        while time.monotonic() < deadline:
                            foundry_output._raise_if_cancel_requested()
                            for process, log_path in processes:
                                code = process.poll()
                                if code is not None and code != 0:
                                    self.abort_tool_error('lightmaps-farm-worker',
                                                          returncode=code, log_filename=str(log_path))
                                    return False
                            time.sleep(0.25)
                    foundry_output._raise_if_cancel_requested()
                    log_path = log_dir / f'worker_{index}.txt'
                    log = logs.enter_context(log_path.open('w'))
                    process = utils.run_tool(
                        ['lightmaps-farm-worker', self.scenario, bsp, self.quality,
                         str(index), str(self.thread_count)],
                        in_background=True, log_file=log, force_tool=True,
                    )
                    processes.append((process, log_path))
                    print(f'--- Spawned lightmap worker {index}')
                for process, log_path in processes:
                    code = process.wait()
                    if code != 0:
                        self.abort_tool_error('lightmaps-farm-worker', returncode=code,
                                              log_filename=str(log_path))
                        return False
            except CalledProcessError as error:
                self.abort_tool_error('lightmaps-farm-worker', error=error)
                return False
            finally:
                # Also stop workers when launching fails or the user cancels.
                for process, _ in processes:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
        return self.run_tool_or_abort(
            ['lightmaps-farm-merge', self.scenario, bsp, str(self.thread_count)],
            f'lightmaps-farm-merge ({bsp})', force_tool=True,
        )

    def lightmap_reach(self):
        return self._lightmap_farm(reach=True)

    def lightmap_halo3(self):
        """Run the H3/ODST local farm without Reach Tool memory patches."""
        return self._lightmap_farm(reach=False)

    def _lightmap_farm(self, *, reach):
        self.blob_dir_name = str(calc_job_id(self.scenario, self.bsp))
        self.analytical_light = "true"
        self.blob_dir = os.path.join("faux", self.blob_dir_name)
        self.start_time = datetime.datetime.now()
        
        self.tool_patches = []
        if reach:
            tool_path = Path(utils.get_project_path(), "tool_fast.exe")
            patcher = ToolPatcher(tool_path)
            self.tool_patches = patcher.reach_lightmap_color(return_patches=True)

        print("\n\nFaux Data Sync")
        print(
            "-------------------------------------------------------------------------\n"
        )
        # self.print_exec_time()
        if not self.run_tool_or_abort(["faux_data_sync", self.scenario, self.bsp], "faux_data_sync", force_tool_fast=True):
            return self

        print("\nFaux Farm")
        print(
            "-------------------------------------------------------------------------\n"
        )
        # self.print_exec_time()
        begin_args = [
            "faux_farm_begin",
            self.scenario,
            self.bsp,
            self.light_group if reach else (self.light_group or "all"),
            self.quality,
            self.blob_dir_name,
        ]
        if reach:
            begin_args.append(self.analytical_light)
        if not self.run_tool_or_abort(
            begin_args,
            "faux_farm_begin",
            force_tool_fast=True
        ):
            return self

        print("\nDirect Illumination")
        print(
            "-------------------------------------------------------------------------\n"
        )
        if not self.farm("dillum"):
            return self
        print("\nCasting Photons")
        print(
            "-------------------------------------------------------------------------\n"
        )
        if not self.farm("pcast"):
            return self
        print("\nExtended Illumination")
        print(
            "-------------------------------------------------------------------------\n"
        )
        if reach:
            if not self.farm("radest_extillum"):
                return self
        else:
            if not self.farm("radest"):
                return self
            if not self.farm("extillum"):
                return self
        print("\nFinal Gather")
        print(
            "-------------------------------------------------------------------------\n"
        )
        if not self.farm("fgather"):
            return self

        print("\nFaux Farm Process Finalise")
        print(
            "-------------------------------------------------------------------------\n"
        )
        if not self.run_tool_or_abort(["faux_farm_finish", self.blob_dir], "faux_farm_finish", force_tool_fast=True):
            return self

        if not reach:
            for command in (
                "faux-build-linear-textures-with-intensity-from-quadratic",
                "faux-compress-scenario-bitmaps-dxt5",
                "faux-farm-compression-merge",
            ):
                if not self.run_tool_or_abort(
                    [command, self.scenario, self.bsp], command, force_tool_fast=True
                ):
                    return self
            self.lightmap_message = f"{utils.formalise_string(self.quality)} Quality lightmap complete"
            return self

        if not self.run_tool_or_abort(
            [
                "faux-reorganize-mesh-for-analytical-lights",
                self.scenario,
                self.bsp,
            ],
            "faux-reorganize-mesh-for-analytical-lights",
            force_tool_fast=True
        ):
            return self
        if not self.run_tool_or_abort(
            [
                "faux-build-vmf-textures-from-quadratic",
                self.scenario,
                self.bsp,
                "true",
                "true",
            ],
            "faux-build-vmf-textures-from-quadratic",
            force_tool_fast=True
        ):
            return self
        self.lightmap_message = f"{utils.formalise_string(self.quality)} Quality lightmap complete"
        return self

    def lightmap_h4(self):
        self.force_reatlas = "false"
        custom = self.quality == "__custom__"
        using_asset_settings = (custom or self.quality == "__asset__")
        self.suppress_dialog = (
            "false" if custom or self.quality == "" else "true"
        )
        self.settings = str(Path("globals", "lightmapper_settings", self.quality))
        print("\n\nRunning Lightmapper")
        print(
            "-------------------------------------------------------------------------\n"
        )
        scene_nwo = utils.get_scene_props()
        if using_asset_settings:
            asset_path = utils.get_asset_path_full(True)
            asset_name = Path(asset_path).name
            bsps = [r.name for r in scene_nwo.regions_table if r.name.lower() != 'shared']
            lightmapper_globals_paths = [str(Path(asset_path, f'{asset_name}_{b}.lightmapper_globals')) for b in bsps]
            
            # Create defaults
            default_lm_tag = Path(utils.get_tags_path(), r'globals\lightmapper_settings\default_new.lightmapper_globals')
            if default_lm_tag.exists():
                for lg_path in lightmapper_globals_paths:
                    if not Path(lg_path).exists():
                        utils.copy_file(default_lm_tag, lg_path)
                        
            if self.light_group:
                ob = bpy.context.scene.objects.get(self.light_group)
                if ob is not None:
                    print("Writing Lightmapper Bounding Box")
                    for lg_path in lightmapper_globals_paths:
                        min_co, max_co = utils.to_aabb(ob)
                        with LightmapperGlobalsTag(path=lg_path) as lm_globals:
                            lm_globals.restrict_to_region(min_co, max_co)
            else:
                for lg_path in lightmapper_globals_paths:
                    with LightmapperGlobalsTag(path=lg_path) as lm_globals:
                        lm_globals.clear_region_restriction()
                
        try:
            if self.model_lightmap:
                utils.run_tool(
                    [
                        "faux_lightmap_model",
                        self.scenario,
                        self.suppress_dialog,
                        self.force_reatlas,
                    ]
                )
            else:
                if self.bsp == "all":
                    for bsp in self.bsps:
                        if using_asset_settings:
                            utils.run_tool(
                                [
                                    "faux_lightmap",
                                    self.scenario,
                                    bsp,
                                    self.suppress_dialog,
                                    self.force_reatlas,
                                ]
                            )
                        else:
                            utils.run_tool(
                                [
                                    "faux_lightmap_with_settings",
                                    self.scenario,
                                    bsp,
                                    self.suppress_dialog,
                                    self.force_reatlas,
                                    self.settings,
                                ]
                            )
                        # self.suppress_dialog = "true"
                else:
                    if using_asset_settings:
                        utils.run_tool(
                            [
                                "faux_lightmap",
                                self.scenario,
                                self.bsp,
                                self.suppress_dialog,
                                self.force_reatlas,
                            ]
                        )
                    else:
                        utils.run_tool(
                            [
                                "faux_lightmap_with_settings",
                                self.scenario,
                                self.bsp,
                                self.suppress_dialog,
                                self.force_reatlas,
                                self.settings,
                            ]
                        )
        except CalledProcessError as error:
            self.abort_tool_error("faux_lightmap", error=error)
        except Exception:
            self.lightmap_failed = True
            self.show_crash_report = False
            self.lightmap_message = "Lightmapper did not run"
            utils.print_warning(self.lightmap_message)

        return self

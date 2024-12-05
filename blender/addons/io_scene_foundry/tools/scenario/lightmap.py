import datetime
from pathlib import Path
import bpy
from ... import utils
import os

def scenario_exists() -> bool:
    asset_dir, asset_name = utils.get_asset_info()
    scenario_path = Path(utils.get_tags_path(), asset_dir, asset_name).with_suffix('.scenario')
    return scenario_path.exists()

def model_exists() -> bool:
    asset_dir, asset_name = utils.get_asset_info()
    model_path = Path(utils.get_tags_path(), asset_dir, asset_name).with_suffix('.model')
    return model_path.exists()
     

class NWO_OT_Lightmap(bpy.types.Operator):
    bl_idname = "nwo.lightmap"
    bl_label = "Lightmap"
    bl_options = {"UNDO"}
    bl_description = "Runs lightmap generation on the current asset"

    @classmethod
    def poll(cls, context):
        if not utils.valid_nwo_asset(context):
            return False
        asset_type = context.scene.nwo.asset_type
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
        asset_type = context.scene.nwo.asset_type
        asset_path, _ = utils.get_asset_info()
        scenario_path = str(Path(asset_path, asset_path))
        scene_nwo_export = context.scene.nwo_export
        is_corinth = utils.is_corinth(context)
        os.system("cls")
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            context.scene.nwo_export.show_output = False

        export_title = f"►►► LIGHTMAPPER ◄◄◄"
        print(export_title)
        bsps = [region.name for region in context.scene.nwo.regions_table]
        valid_bsps = set()
        for ob in context.scene.objects:
            region = utils.true_region(ob.nwo)
            if region in bsps:
                valid_bsps.add(region)
                
        bsps = [b for b in bsps if b in valid_bsps]
                
        run_lightmapper(
            is_corinth,
            [],
            scenario_path,
            scene_nwo_export.lightmap_quality,
            scene_nwo_export.lightmap_quality_h4,
            scene_nwo_export.lightmap_all_bsps,
            scene_nwo_export.lightmap_specific_bsp,
            scene_nwo_export.lightmap_region,
            asset_type in ("model", "sky") and is_corinth,
            scene_nwo_export.lightmap_threads,
            bsps)
        return {"FINISHED"}
    
def run_lightmapper(
    not_bungie_game,
    misc_halo_objects,
    scenario_path,
    lightmap_quality="direct_only",
    lightmap_quality_h4="__custom__",
    lightmap_all_bsps=True,
    lightmap_specific_bsp="default",
    lightmap_region="all",
    model_lightmap=False,
    cpu_threads=1,
    structure_bsps=[],
):
    lightmap = LightMapper(
        not_bungie_game,
        misc_halo_objects,
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
    if not_bungie_game:
        lightmap_results = lightmap.lightmap_h4()
    else:
        lightmap_results = lightmap.lightmap_reach()

    return lightmap_results


class LightMapper:
    def __init__(
        self,
        not_bungie_game,
        misc_halo_objects,
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
        self.model_lightmap = model_lightmap
        self.scenario = scenario_path
        self.bsp = self.bsp_to_lightmap(lightmap_all_bsps, lightmap_specific_bsp)
        self.quality = lightmap_quality_h4 if not_bungie_game else lightmap_quality
        self.light_group = self.get_light_group(lightmap_region, misc_halo_objects, not_bungie_game)
        self.thread_count = cpu_threads
        self.bsps = structure_bsps

    # HELPERS --------------------------
    def get_light_group(self, lightmap_region, misc_halo_objects, not_bungie_game):
        return "all" # NOTE temp until lightmap regions are figured out
        if not not_bungie_game and lightmap_region != "" and lightmap_region != "all":
            for ob in misc_halo_objects:
                if ob.name == lightmap_region:
                    return lightmap_region
            else:
                print_warning(
                    f"Lightmap region specified but no lightmap region named {lightmap_region} exists in scene"
                )

        return "all"

    def bsp_to_lightmap(self, lightmap_all_bsps, lightmap_specific_bsp):
        bsp = "all"
        if not lightmap_all_bsps:
            bsp = lightmap_specific_bsp

        return bsp

    # EXECUTE LIGHTMAP ---------------------------------------------------------------------

    def print_exec_time(self):
        print(datetime.datetime.now() - self.start_time)

    def threads(self, stage, thread_index):
        log_filename = os.path.join(self.blob_dir, "logs", stage, f"{thread_index}.txt")
        log_dir = os.path.dirname(log_filename)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        with open(log_filename, "w") as log:
            return (
                utils.run_tool(
                    [
                        "faux_farm_" + stage,
                        self.blob_dir,
                        str(thread_index),
                        str(self.thread_count),
                    ],
                    True,
                    log,
                ),
                log_filename,
            )

    def farm(self, stage):
        # self.print_exec_time()
        processes = [
            self.threads(stage, thread_index)
            for thread_index in range(self.thread_count)
        ]
        for p, log_filename in processes:
            if p.wait() != 0:
                self.lightmap_message = f"Lightmapper failed during {stage}. See error log for details: {log_filename}\nIf nothing is written to the above log, it may be that you have minimal space remaining on your disk drive"
                self.lightmap_failed = True
                return False

        utils.run_tool(
            [
                "faux_farm_" + stage + "_merge",
                self.blob_dir,
                str(self.thread_count),
            ]
        )

        return True

    def lightmap_reach(self):
        self.blob_dir_name = "111"
        self.analytical_light = "true"
        self.blob_dir = os.path.join("faux", self.blob_dir_name)
        self.start_time = datetime.datetime.now()

        print("\n\nFaux Data Sync")
        print(
            "-------------------------------------------------------------------------\n"
        )
        # self.print_exec_time()
        utils.run_tool(["faux_data_sync", self.scenario, self.bsp])

        print("\nFaux Farm")
        print(
            "-------------------------------------------------------------------------\n"
        )
        # self.print_exec_time()
        utils.run_tool(
            [
                "faux_farm_begin",
                self.scenario,
                self.bsp,
                self.light_group,
                self.quality,
                self.blob_dir_name,
                self.analytical_light,
            ]
        )

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
        if not self.farm("radest_extillum"):
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
        utils.run_tool(["faux_farm_finish", self.blob_dir])

        utils.run_tool(
            [
                "faux-reorganize-mesh-for-analytical-lights",
                self.scenario,
                self.bsp,
            ]
        )
        utils.run_tool(
            [
                "faux-build-vmf-textures-from-quadratic",
                self.scenario,
                self.bsp,
                "true",
                "true",
            ]
        )
        self.lightmap_message = f"{utils.formalise_string(self.quality)} Quality lightmap complete"
        return self

    def lightmap_h4(self):
        self.force_reatlas = "false"
        using_asset_settings = (self.quality == "__custom__" or self.quality == "__asset__")
        self.suppress_dialog = (
            "false" if self.quality == "__custom__" or self.quality == "" else "true"
        )
        self.settings = str(Path("globals", "lightmapper_settings", self.quality))
        print("\n\nRunning Lightmapper")
        print(
            "-------------------------------------------------------------------------\n"
        )
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
        except:
            utils.print_error("Failed to run lightmapper")

        return self


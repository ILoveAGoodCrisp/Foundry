# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

import os
from io_scene_foundry.utils.nwo_utils import (
    formalise_string,
    get_asset_path,
    print_warning,
    run_tool,
)
import datetime
import multiprocessing


def run_lightmapper(
    not_bungie_game,
    misc_halo_objects,
    asset,
    lightmap_quality="DIRECT",
    lightmap_quality_h4="__custom__",
    lightmap_all_bsps=True,
    lightmap_specific_bsp="default",
    lightmap_region="all",
    model_lightmap=False,
):
    lightmap = LightMapper(
        not_bungie_game,
        misc_halo_objects,
        lightmap_quality,
        lightmap_quality_h4,
        lightmap_all_bsps,
        lightmap_specific_bsp,
        lightmap_region,
        asset,
        model_lightmap,
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
        asset,
        model_lightmap,
    ):
        self.asset_name = asset
        self.lightmap_message = "Lightmap Successful"
        self.lightmap_failed = False
        self.model_lightmap = model_lightmap
        self.scenario = os.path.join(get_asset_path(), self.asset_name)
        self.bsp = self.bsp_to_lightmap(lightmap_all_bsps, lightmap_specific_bsp)
        self.quality = self.get_quality(
            lightmap_quality,
            lightmap_quality_h4,
            not_bungie_game,
        )
        self.light_group = self.get_light_group(
            lightmap_region, misc_halo_objects, not_bungie_game
        )

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
            bsp = f"{self.asset_name}_{lightmap_specific_bsp}"

        return bsp

    def get_quality(
        self,
        lightmap_quality,
        lightmap_quality_h4,
        not_bungie_game,
    ):
        if not_bungie_game:
            return lightmap_quality_h4

        match lightmap_quality:
            case "DIRECT":
                return "direct_only"
            case "DRAFT":
                return "draft"
            case "LOW":
                return "low"
            case "MEDIUM":
                return "medium"
            case "HIGH":
                return "high"
            case _:
                return "super_slow"

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
                run_tool(
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

        run_tool(
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
        run_tool(["faux_data_sync", self.scenario, self.bsp])

        print("\nFaux Farm")
        print(
            "-------------------------------------------------------------------------\n"
        )
        # self.print_exec_time()
        run_tool(
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

        self.thread_count = multiprocessing.cpu_count()

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
        run_tool(["faux_farm_finish", self.blob_dir])

        run_tool(
            [
                "faux-reorganize-mesh-for-analytical-lights",
                self.scenario,
                self.bsp,
            ]
        )
        run_tool(
            [
                "faux-build-vmf-textures-from-quadratic",
                self.scenario,
                self.bsp,
                "true",
                "true",
            ]
        )
        self.lightmap_message = f"{formalise_string(self.quality)} Quality lightmap complete"
        return self

    def lightmap_h4(self):
        self.force_reatlas = "false"
        self.suppress_dialog = (
            "false" if self.quality == "__custom__" or self.quality == "" else "true"
        )
        self.settings = os.path.join("globals", "lightmapper_settings", self.quality)
        print("\n\nRunning Lightmapper")
        print(
            "-------------------------------------------------------------------------\n"
        )
        if self.model_lightmap:
            run_tool(
                [
                    "faux_lightmap_model",
                    self.scenario,
                    self.suppress_dialog,
                    self.force_reatlas,
                ]
            )

        elif self.quality == "__custom__" or self.quality == '__asset__':
            run_tool(
                [
                    "faux_lightmap",
                    self.scenario,
                    self.bsp,
                    self.suppress_dialog,
                    self.force_reatlas,
                ]
            )
        else:
            if self.bsp == "all":
                run_tool(
                    [
                        "faux_lightmap_with_settings_for_all",
                        self.scenario,
                        self.bsp,
                        self.suppress_dialog,
                        self.force_reatlas,
                        self.settings,
                    ]
                )
            else:
                run_tool(
                    [
                        "faux_lightmap_with_settings",
                        self.scenario,
                        self.bsp,
                        self.suppress_dialog,
                        self.force_reatlas,
                        self.settings,
                    ]
                )

        return self

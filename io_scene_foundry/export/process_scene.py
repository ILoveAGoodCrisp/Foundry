# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
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

import itertools
import random
import time
import bpy
import os
import json
import multiprocessing
import threading
from io_scene_foundry.export.tag_builder import build_tags
from io_scene_foundry.export.lightmapper import run_lightmapper

from io_scene_foundry.managed_blam.animation import AnimationTag
from io_scene_foundry.managed_blam.camera_track import CameraTrackTag
from io_scene_foundry.managed_blam.render_model import RenderModelTag
from io_scene_foundry.managed_blam.model import ModelTag
from io_scene_foundry.managed_blam.scenario import ScenarioTag
from .format_json import NWOJSON
from ..utils.nwo_utils import (
    data_relative,
    disable_prints,
    enable_prints,
    get_data_path,
    get_tags_path,
    is_corinth,
    jstr,
    mute_armature_mods,
    print_warning,
    reset_to_basis,
    run_tool,
    unmute_armature_mods,
    update_job,
    update_job_count,
)

#####################################################################################
#####################################################################################
# MAIN FUNCTION


class ProcessScene:
    def __init__(self):
        self.gr2_fail = False
        self.lightmap_failed = False
        self.lightmap_message = ""
        self.sidecar_import_failed = False
        self.sidecar_import_error = ""
        self.thread_max = multiprocessing.cpu_count()
        
        self.gr2_processes = 0
        self.delay = 0
        self.running_check = 0
        self.sidecar_paths = {}
        self.export_paths = []
        self.sidecar_paths_design = {}
        self.asset_has_animations = False
        
        self.p_queue = []
        self.max_export = 0.5
        self.first_gr2 = True
        self.skeleton_only = False
        
        
    
    def process_scene(self, context, sidecar_path, sidecar_path_full, asset, asset_path, asset_type, nwo_scene, scene_nwo_export, scene_nwo):
        reports = []
        gr2_count = 0
        h4 = is_corinth(context)
        muted_armature_deforms = []
        if asset_type == 'camera_track_set':
            return build_camera_tracks(context, nwo_scene.camera, asset_path)
        if scene_nwo_export.export_gr2_files:
            # make necessary directories
            models_dir = os.path.join(asset_path, "models")
            export_dir = os.path.join(asset_path, "export", "models")
            os.makedirs(models_dir, exist_ok=True)
            os.makedirs(export_dir, exist_ok=True)
            if asset_type in ("MODEL", "FP ANIMATION"):
                if nwo_scene.model_armature and bpy.data.actions:
                    if scene_nwo_export.export_animations != "NONE":
                        timeline = context.scene
                        print("\n\nStarting Animations Export")
                        print(
                            "-----------------------------------------------------------------------\n"
                        )

                    # Handle swapping out armature
                    muted_armature_deforms = mute_armature_mods()
                    for action in bpy.data.actions:
                        # make animation dirs
                        animations_dir = os.path.join(asset_path, "animations")
                        export_animations_dir = os.path.join(
                            asset_path, "export", "animations"
                        )
                        os.makedirs(animations_dir, exist_ok=True)
                        os.makedirs(export_animations_dir, exist_ok=True)
                        action_nwo = action.nwo
                        # only export animations that have manual frame range
                        if action.use_frame_range:
                            self.asset_has_animations = True
                            animation_name = action.nwo.name_override
                            fbx_path, json_path, gr2_path = self.get_path(
                                asset_path,
                                asset,
                                "animations",
                                None,
                                None,
                                animation_name,
                            )
                            if scene_nwo_export.export_animations != "NONE":
                                if (
                                    scene_nwo_export.export_animations == "ALL"
                                    or nwo_scene.current_action == action
                                ):
                                    job = f"--- {animation_name}"
                                    update_job(job, 0)
                                    
                                    arm = nwo_scene.model_armature

                                    for ob in bpy.data.objects:
                                        if ob.animation_data:
                                            ob.animation_data.action = action
                                            
                                    timeline.frame_start = int(action.frame_start)
                                    timeline.frame_end = int(action.frame_end)

                                    context.scene.frame_set(int(action.frame_start))

                                    export_obs = self.create_event_nodes(
                                        context,
                                        action_nwo.animation_events,
                                        arm,
                                        list(nwo_scene.skeleton_bones.keys())[1],
                                        timeline.frame_start,
                                        timeline.frame_end,
                                    )

                                    override = context.copy()
                                    area = [
                                        area
                                        for area in context.screen.areas
                                        if area.type == "VIEW_3D"
                                    ][0]
                                    override["area"] = area
                                    override["region"] = area.regions[-1]
                                    override["space_data"] = area.spaces.active
                                    override["selected_objects"] = export_obs

                                    with context.temp_override(**override):
                                        if self.export_fbx(
                                            True,
                                            fbx_path,
                                        ):
                                            if self.export_json(
                                                json_path,
                                                export_obs,
                                                asset_type,
                                                asset,
                                                nwo_scene,
                                            ):
                                                self.export_gr2(
                                                    fbx_path,
                                                    json_path,
                                                    gr2_path,
                                                )
                                            else:
                                                return f"Failed to export skeleton JSON: {json_path}"
                                        else:
                                            return f"Failed to export skeleton FBX: {fbx_path}"

                                    update_job(job, 1)

                            if "animation" in self.sidecar_paths.keys():
                                self.sidecar_paths["animation"].append(
                                    [
                                        data_relative(fbx_path),
                                        data_relative(json_path),
                                        data_relative(gr2_path),
                                        animation_name,
                                        action_nwo.animation_type,
                                        action_nwo.animation_movement_data,
                                        action_nwo.animation_space,
                                        action_nwo.animation_is_pose,
                                        action_nwo.compression,
                                    ]
                                )
                            else:
                                self.sidecar_paths["animation"] = [
                                    [
                                        data_relative(fbx_path),
                                        data_relative(json_path),
                                        data_relative(gr2_path),
                                        animation_name,
                                        action_nwo.animation_type,
                                        action_nwo.animation_movement_data,
                                        action_nwo.animation_space,
                                        action_nwo.animation_is_pose,
                                        action_nwo.compression,
                                    ]
                                ]
            print("\n\nStarting Models Export")
            print(
                "-----------------------------------------------------------------------\n"
            )
            clear_constraints()
            reset_to_basis()
            if muted_armature_deforms:
                unmute_armature_mods(muted_armature_deforms)
            if asset_type in ("MODEL", "FP ANIMATION"):

                if nwo_scene.render:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "render",
                        nwo_scene.render,
                        nwo_scene.render_perms,
                        nwo_scene.selected_perms,
                        nwo_scene.model_armature,
                        asset_type,
                        nwo_scene,
                        scene_nwo_export.export_render,
                    )
                if asset_type == "MODEL":
                    if nwo_scene.collision:
                        self.export_model(
                            context,
                            asset_path,
                            asset,
                            "collision",
                            nwo_scene.collision,
                            nwo_scene.collision_perms,
                            nwo_scene.selected_perms,
                            nwo_scene.model_armature,
                            asset_type,
                            nwo_scene,
                            scene_nwo_export.export_collision,
                        )

                    if nwo_scene.physics:
                        self.export_model(
                            context,
                            asset_path,
                            asset,
                            "physics",
                            nwo_scene.physics,
                            nwo_scene.physics_perms,
                            nwo_scene.selected_perms,
                            nwo_scene.model_armature,
                            asset_type,
                            nwo_scene,
                            scene_nwo_export.export_physics,
                        )

                    if nwo_scene.markers:
                        self.export_model(
                            context,
                            asset_path,
                            asset,
                            "markers",
                            nwo_scene.markers,
                            None,
                            None,
                            nwo_scene.model_armature,
                            asset_type,
                            nwo_scene,
                            scene_nwo_export.export_markers,
                        )
                    if nwo_scene.lighting:
                        self.export_model(
                            context,
                            asset_path,
                            asset,
                            "lighting",
                            nwo_scene.lighting,
                            None,
                            None,
                            nwo_scene.model_armature,
                            asset_type,
                            nwo_scene,
                            True,
                        )
                    

                fbx_path, json_path, gr2_path = self.get_path(
                    asset_path, asset, "skeleton", None, None, None
                )

                if nwo_scene.model_armature and scene_nwo_export.export_skeleton:
                    export_obs = [nwo_scene.model_armature]

                    override = context.copy()
                    area = [
                        area
                        for area in context.screen.areas
                        if area.type == "VIEW_3D"
                    ][0]
                    override["area"] = area
                    override["region"] = area.regions[-1]
                    override["space_data"] = area.spaces.active
                    override["selected_objects"] = export_obs
                    with context.temp_override(**override):
                        job = "--- skeleton"
                        update_job(job, 0)
                        if self.export_fbx(
                            False,
                            fbx_path,
                        ):
                            if self.export_json(
                                json_path,
                                export_obs,
                                asset_type,
                                asset,
                                nwo_scene,
                            ):
                                self.export_gr2(fbx_path, json_path, gr2_path)
                            else:
                                return (
                                    f"Failed to export skeleton JSON: {json_path}"
                                )
                        else:
                            return f"Failed to export skeleton FBX: {fbx_path}"

                        update_job(job, 1)

                if "skeleton" in self.sidecar_paths.keys():
                    self.sidecar_paths["skeleton"].append(
                        [
                            data_relative(fbx_path),
                            data_relative(json_path),
                            data_relative(gr2_path),
                        ]
                    )
                else:
                    self.sidecar_paths["skeleton"] = [
                        [
                            data_relative(fbx_path),
                            data_relative(json_path),
                            data_relative(gr2_path),
                        ]
                    ]

            elif asset_type == "SCENARIO":
                if nwo_scene.structure:
                    self.export_bsp(
                        context,
                        asset_path,
                        asset,
                        False,
                        nwo_scene.structure,
                        nwo_scene.selected_perms,
                        nwo_scene.selected_bsps,
                        asset_type,
                        nwo_scene,
                        nwo_scene.structure_bsps,
                        nwo_scene.structure_perms,
                        scene_nwo_export.export_structure,
                    )

                if nwo_scene.design:
                    self.export_bsp(
                        context,
                        asset_path,
                        asset,
                        True,
                        nwo_scene.design,
                        nwo_scene.selected_perms,
                        nwo_scene.selected_bsps,
                        asset_type,
                        nwo_scene,
                        nwo_scene.design_bsps,
                        nwo_scene.design_perms,
                        scene_nwo_export.export_design,
                    )

            elif asset_type == "SKY":
                if nwo_scene.render:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "sky",
                        nwo_scene.render,
                        None,
                        None,
                        nwo_scene.model_armature,
                        asset_type,
                        nwo_scene,
                        scene_nwo_export.export_render,
                    )
                if nwo_scene.lighting:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "lighting",
                        nwo_scene.lighting,
                        None,
                        None,
                        nwo_scene.model_armature,
                        asset_type,
                        nwo_scene,
                        True,
                    )

            elif asset_type == "DECORATOR SET":
                if nwo_scene.render:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "decorator",
                        nwo_scene.render,
                        None,
                        None,
                        None,
                        asset_type,
                        nwo_scene,
                        scene_nwo_export.export_render,
                    )

            elif asset_type == "PREFAB":
                if nwo_scene.structure:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "prefab",
                        nwo_scene.structure,
                        None,
                        None,
                        None,
                        asset_type,
                        nwo_scene,
                        True,
                    )

            else:  # for particles
                if nwo_scene.render:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "particle_model",
                        nwo_scene.render,
                        None,
                        None,
                        None,
                        asset_type,
                        nwo_scene,
                        scene_nwo_export.export_render,
                    )

            from .build_sidecar import Sidecar
            
            sidecar = Sidecar(asset_path, asset, asset_type)
            sidecar.build(context, sidecar_path, sidecar_path_full, nwo_scene, self.sidecar_paths, self.sidecar_paths_design, scene_nwo)

            # make another sidecar to generate model lighting files
            if nwo_scene.lighting:
                lighting_sidecar = Sidecar(asset_path, asset, "MODEL SCENARIO")
                lighting_sidecar.build(context, sidecar_path, sidecar_path_full, nwo_scene, self.sidecar_paths, self.sidecar_paths_design, scene_nwo, True)

            reports.append(sidecar.message)
            print("\n\nBuilding Intermediary Files")
            print(
                "-----------------------------------------------------------------------\n"
            )

            total_p = self.gr2_processes

            job = "--- Running GR2 Conversion"
            spinner = itertools.cycle(["|", "/", "—", "\\"])
            while self.running_check:
                update_job_count(
                    job, next(spinner), total_p - self.running_check, total_p
                )
                time.sleep(0.1)

            update_job_count(job, "", total_p, total_p)

            # check that gr2 files exist (since fbx-to-gr2 doesn't return a non zero code on faiL!)
            job = "--- Validating GR2 Files"
            update_job(job, 0)
            for path_set in self.export_paths:
                gr2_file = path_set[2]
                if (
                    not os.path.exists(gr2_file)
                    or os.stat(gr2_file).st_size == 0
                ):
                    #print(f"\n\nFailed to build GR2: {gr2_file}")
                    #print(f"Retrying export...")
                    fbx_file = path_set[0]
                    json_file = path_set[1]
                    self.export_gr2_sync(fbx_file, json_file, gr2_file)
                    if (
                        os.path.exists(gr2_file)
                        and os.stat(gr2_file).st_size > 0
                    ):
                        pass
                        # print("Success!")
                    else:
                        print_warning(
                            f"\nFailed to build GR2 File: {gr2_file}"
                        )
                        print_warning("Retrying...")
                        self.export_gr2_sync(fbx_file, json_file, gr2_file, False)
                        time.sleep(2)
                        if (
                            os.path.exists(gr2_file)
                            and os.stat(gr2_file).st_size > 0
                        ):
                            print("Success!!")
                        else:
                            self.gr2_fail = True
                            return "Failed to build GR2 File, Giving Up"

                # If Reach, apply GR2 patch. This prevents the importer from breaking object directions
                if not h4 and os.path.exists(gr2_file):
                    patch_granny(gr2_file)

            update_job(job, 1)

            reports.append("Exported " + str(gr2_count) + " GR2 Files")

            tag_folder_path = asset_path.replace(get_data_path(), get_tags_path())
            scenery_path = os.path.join(tag_folder_path, f"{asset}.scenery")
            no_top_level_tag = hasattr(sidecar, "no_top_level_tag") and not os.path.exists(scenery_path)

            if scene_nwo_export.export_gr2_files and os.path.exists(sidecar_path_full):
                self.managed_blam_pre_import_tasks(nwo_scene, scene_nwo_export.export_animations, context.scene.nwo)
                set_better_lm_res = False
                if asset_type == 'SCENARIO':
                    scenario_path = os.path.join(tag_folder_path, f"{asset}.scenario")
                    if not os.path.exists(scenario_path):
                        set_better_lm_res = True
                export_failed, error = build_tags(asset_type, sidecar_path, asset_path, asset, scene_nwo_export, scene_nwo, bool(nwo_scene.lighting), nwo_scene.selected_bsps)
                if export_failed:
                    self.sidecar_import_failed = True
                    self.sidecar_import_error = error
                    reports.append("Tag Export Failed")
                else:
                    reports.append("Tag Export Complete")
                    self.managed_blam_post_import_tasks(context, nwo_scene, asset_type, asset_path.replace(get_data_path(), ""), asset, sidecar.reach_world_animations, set_better_lm_res)
            else:
                reports.append("Skipped tag export, asset sidecar does not exist")


            if no_top_level_tag:
                if os.path.exists(scenery_path):
                    os.remove(scenery_path)

        should_lightmap = scene_nwo_export.lightmap_structure and (
            asset_type == "SCENARIO" or (h4 and asset_type in ("MODEL", "SKY"))
        )

        if should_lightmap:
            lightmap_results = run_lightmapper(
                h4,
                nwo_scene.structure,
                asset,
                scene_nwo_export.lightmap_quality,
                scene_nwo_export.lightmap_quality_h4,
                scene_nwo_export.lightmap_all_bsps,
                scene_nwo_export.lightmap_specific_bsp,
                scene_nwo_export.lightmap_region,
                asset_type in ("MODEL", "SKY") and h4)

            self.lightmap_message = lightmap_results.lightmap_message

            if lightmap_results.lightmap_failed:
                self.lightmap_failed = True

    def export_model(
        self,
        context,
        asset_path,
        asset,
        type,
        objects,
        obs_perms,
        sel_perms,
        model_armature,
        asset_type,
        nwo_scene,
        export_check,
    ):
        if obs_perms:
            perms = obs_perms
        else:
            perms = ["default"]

        for perm in perms:
            fbx_path, json_path, gr2_path = self.get_path(asset_path, asset, type, perm, None, None)
            sidecar_data =  [data_relative(fbx_path), data_relative(json_path), data_relative(gr2_path), perm]
            if type in self.sidecar_paths.keys():
                self.sidecar_paths[type].append(sidecar_data)
            else:
                self.sidecar_paths[type] = [sidecar_data]
                
            if not sel_perms or perm in sel_perms:
                if model_armature:
                    if obs_perms:
                        export_obs = [ob for ob in objects if ob.nwo.permutation_name == perm]
                        export_obs.append(model_armature)
                    else:
                        export_obs = [ob for ob in objects]
                        export_obs.append(model_armature)
                else:
                    if obs_perms:
                        export_obs = [ob for ob in objects if ob.nwo.permutation_name == perm]
                    else:
                        export_obs = [ob for ob in objects]

                if type == "prefab":
                    print_text = f"prefab"
                elif type == "particle_model":
                    print_text = f"particle Model"
                elif type == "decorator":
                    print_text = f"decorator"
                elif type == "sky":
                    print_text = f"sky"
                elif type == "markers":
                    print_text = f"markers"
                elif type == "lighting":
                    print_text = f"lighting"
                elif perm == "default":
                    print_text = f"{type} model"
                else:
                    print_text = f"{perm} {type} model"

                if export_check:
                    override = context.copy()
                    area = [
                        area for area in context.screen.areas if area.type == "VIEW_3D"
                    ][0]
                    override["area"] = area
                    override["region"] = area.regions[-1]
                    override["space_data"] = area.spaces.active
                    override["selected_objects"] = export_obs

                    with context.temp_override(**override):
                        job = f"--- {print_text}"
                        update_job(job, 0)
                        if self.export_fbx(
                            False,
                            fbx_path,
                        ):
                            if self.export_json(
                                json_path, export_obs, asset_type, asset, nwo_scene
                            ):
                                self.export_gr2(fbx_path, json_path, gr2_path)
                            else:
                                return f"Failed to export {perm} {type} model JSON: {json_path}"
                        else:
                            return f"Failed to export {perm} {type} model FBX: {fbx_path}"

                        update_job(job, 1)

    def export_bsp(
        self,
        context,
        asset_path,
        asset,
        is_design,
        objects,
        sel_perms,
        sel_bsps,
        asset_type,
        nwo_scene,
        bsps,
        layers,
        export_check,
    ):
        type_name = 'design' if is_design else 'bsp'
        for bsp in bsps:
            for perm in layers:
                export_obs = [ob for ob in objects if ob.nwo.permutation_name == perm and (ob.nwo.region_name == bsp)]
                if not export_obs: continue
                fbx_path, json_path, gr2_path = self.get_path(asset_path, asset, type_name, perm, bsp, None)
                sidecar_data =  [data_relative(fbx_path), data_relative(json_path), data_relative(gr2_path), perm]
                if is_design:
                    if bsp in self.sidecar_paths_design.keys():
                        self.sidecar_paths_design[bsp].append(sidecar_data)
                    else:
                        self.sidecar_paths_design[bsp] = [sidecar_data]
                else:
                    if bsp in self.sidecar_paths.keys():
                        self.sidecar_paths[bsp].append(sidecar_data)
                    else:
                        self.sidecar_paths[bsp] = [sidecar_data]
                        
                if (not sel_bsps or bsp in sel_bsps) and (not sel_perms or perm in sel_perms):
                    if export_check and export_obs:
                        override = context.copy()
                        area = [
                            area for area in context.screen.areas if area.type == "VIEW_3D"
                        ][0]
                        override["area"] = area
                        override["region"] = area.regions[-1]
                        override["space_data"] = area.spaces.active
                        override["selected_objects"] = export_obs

                        with context.temp_override(**override):
                            if perm == "default":
                                print_text = f"{bsp} {type_name}"
                            else:
                                print_text = f"{bsp} {perm} {type_name}"

                            job = f"--- {print_text}"
                            update_job(job, 0)
                            if self.export_fbx(
                                False,
                                fbx_path,
                            ):
                                if self.export_json(
                                    json_path,
                                    export_obs,
                                    asset_type,
                                    asset,
                                    nwo_scene,
                                ):
                                    self.export_gr2(fbx_path, json_path, gr2_path)
                                else:
                                    return f"Failed to export {perm} {type_name} model JSON: {json_path}"
                            else:
                                return (
                                    f"Failed to export {perm} {type_name} model FBX: {fbx_path}"
                                )

                            update_job(job, 1)

    def get_path(self, asset_path, asset_name, tag_type, perm="", bsp="", animation=""):
        """Gets an appropriate new path for the exported fbx file"""
        if bsp:
            if tag_type == "design":
                if perm == "default":
                    path = (
                        f'{os.path.join(asset_path, "models", asset_name)}_{bsp}_design'
                    )
                    path_gr2 = f'{os.path.join(asset_path, "export", "models", asset_name)}_{bsp}_design'
                else:
                    path = f'{os.path.join(asset_path, "models", asset_name)}_{bsp}_{perm}_design'
                    path_gr2 = f'{os.path.join(asset_path, "export", "models", asset_name)}_{bsp}_{perm}_design'
            else:
                if perm == "default":
                    path = f'{os.path.join(asset_path, "models", asset_name)}_{bsp}'
                    path_gr2 = f'{os.path.join(asset_path, "export", "models", asset_name)}_{bsp}'
                else:
                    path = (
                        f'{os.path.join(asset_path, "models", asset_name)}_{bsp}_{perm}'
                    )
                    path_gr2 = f'{os.path.join(asset_path, "export", "models", asset_name)}_{bsp}_{perm}'
        else:
            if tag_type == "animations":
                path = os.path.join(asset_path, "animations", animation)
                path_gr2 = os.path.join(
                    asset_path,
                    "export",
                    "animations",
                    animation,
                )

            elif tag_type in (
                "render",
                "collision",
                "physics",
                "markers",
                "lighting",
                "skeleton",
                "sky",
                "decorator",
            ):
                if perm == "default" or tag_type in ("markers", "skeleton", "lighting"):
                    path = (
                        f'{os.path.join(asset_path, "models", asset_name)}_{tag_type}'
                    )
                    path_gr2 = f'{os.path.join(asset_path, "export", "models", asset_name)}_{tag_type}'
                else:
                    path = f'{os.path.join(asset_path, "models", asset_name)}_{perm}_{tag_type}'
                    path_gr2 = f'{os.path.join(asset_path, "export", "models", asset_name)}_{perm}_{tag_type}'

            else:
                path = os.path.join(asset_path, "models", asset_name)
                path_gr2 = os.path.join(asset_path, "export", "models", asset_name)

        return f"{path}.fbx", f"{path}.json", f"{path_gr2}.gr2"

    #####################################################################################
    #####################################################################################
    # MANAGEDBLAM

    def managed_blam_pre_import_tasks(self, nwo_scene, export_animations, scene_nwo):
        node_usage_set = self.asset_has_animations and export_animations and self.any_node_usage_override(scene_nwo)
        mb_justified = node_usage_set or scene_nwo.ik_chains
        if not mb_justified:
            return
        print("\nTags Pre-Process")
        print(
            "-----------------------------------------------------------------------\n"
        )
        # Update/ set up Node Usage block of the model_animation_graph
        if node_usage_set:
            with AnimationTag(hide_prints=False) as animation:
                animation.set_node_usages(nwo_scene.skeleton_bones)
            print("--- Updated Animation Node Usages")
        if scene_nwo.ik_chains:
            with AnimationTag(hide_prints=False) as animation:
                animation.write_ik_chains(scene_nwo.ik_chains, nwo_scene.skeleton_bones)
            print("--- Updated Animation IK Chains")

    def managed_blam_post_import_tasks(self, context, nwo_scene, asset_type, asset_path, asset_name, reach_world_animations, set_better_lm_res):
        nwo = context.scene.nwo
        model_sky = asset_type in ('MODEL', 'SKY')
        model = asset_type == 'MODEL'
        h4_model_lighting = (nwo_scene.lighting and is_corinth(context) and model_sky)
        model_override = (
            (nwo.render_model_path and model)
            or (nwo.collision_model_path and model)
            or (nwo.physics_model_path and model)
            or (nwo.animation_graph_path and model)
        )
        mb_justified =  (
            h4_model_lighting
            or model_override
            or reach_world_animations
            or set_better_lm_res
        )
        if not mb_justified:
            return
        
        print("\nTags Post-Process")
        print(
            "-----------------------------------------------------------------------\n"
        )
        
        # If this model has lighting, add a reference to the structure_meta tag in the render_model
        if h4_model_lighting:
            meta_path = os.path.join(asset_path, asset_name + '.structure_meta')
            with RenderModelTag(hide_prints=False) as render_model:
                render_model.set_structure_meta_ref(meta_path)
            print("--- Added Structure Meta Reference to Render Model")

        # Apply model overrides if any
        if model_override:
            with ModelTag(hide_prints=True) as model:
                model.set_model_overrides(nwo.render_model_path, nwo.collision_model_path, nwo.animation_graph_path, nwo.physics_model_path)
            print("--- Applied Model Overrides")
            
        if reach_world_animations:
            with AnimationTag(hide_prints=True) as animation:
                animation.set_world_animations(reach_world_animations)
            print("--- Setup World Animations")
            
        if set_better_lm_res:
            lm_value = 6 if is_corinth(context) else 3
            with ScenarioTag(hide_prints=True) as scenario:
                for bsp in nwo_scene.structure_bsps:
                    scenario.set_bsp_lightmap_res(bsp, lm_value, 0)
            print("--- Set Lightmapper size class to 1k")
            

    def any_node_usage_override(self, nwo):
        return (nwo.node_usage_physics_control
                or nwo.node_usage_camera_control
                or nwo.node_usage_origin_marker
                or nwo.node_usage_left_clavicle
                or nwo.node_usage_left_upperarm
                or nwo.node_usage_pose_blend_pitch
                or nwo.node_usage_pose_blend_yaw
                or nwo.node_usage_pedestal
                or nwo.node_usage_pelvis
                or nwo.node_usage_left_foot
                or nwo.node_usage_right_foot
                or nwo.node_usage_damage_root_gut
                or nwo.node_usage_damage_root_chest
                or nwo.node_usage_damage_root_head
                or nwo.node_usage_damage_root_left_shoulder
                or nwo.node_usage_damage_root_left_arm
                or nwo.node_usage_damage_root_left_leg
                or nwo.node_usage_damage_root_left_foot
                or nwo.node_usage_damage_root_right_shoulder
                or nwo.node_usage_damage_root_right_arm
                or nwo.node_usage_damage_root_right_leg
                or nwo.node_usage_damage_root_right_foot
                or nwo.node_usage_left_hand
                or nwo.node_usage_right_hand
                or nwo.node_usage_weapon_ik
                )


    #####################################################################################
    #####################################################################################
    # ANIMATION EVENTS

    def create_event_nodes(
        self, context, events, model_armature, root_bone_name, frame_start, frame_end
    ):
        animation_events = [model_armature]
        scene_coll = context.scene.collection.objects
        for event in events:
            # create the event node to store event info
            event_ob = bpy.data.objects.new('event_export_node_' + event.event_type[41:] + '_' + str(event.event_id), None)
            nwo = event_ob.nwo
            # Set this node to be an animation event
            nwo.object_type = "_connected_geometry_object_type_animation_event"
            # Set up the event node with the action start and end frame and id
            # add the user defined properties from the action
            nwo.event_id = abs(event.event_id)
            nwo.event_type = event.event_type
            nwo.wrinkle_map_face_region = event.wrinkle_map_face_region
            nwo.wrinkle_map_effect = jstr(event.wrinkle_map_effect)
            nwo.ik_chain = event.ik_chain
            nwo.ik_target_marker = event.ik_target_marker.name if event.ik_target_marker else ''
            nwo.ik_target_usage = event.ik_target_usage
            nwo.object_function_name = event.object_function_name
            nwo.object_function_effect = jstr(event.object_function_effect)
            nwo.import_frame = str(event.import_frame)
            nwo.import_name = event.import_name
            # add it to the list
            scene_coll.link(event_ob)
            animation_events.append(event_ob)
            # duplicate for frame range
            if nwo.event_type == '_connected_geometry_animation_event_type_frame':
                nwo.frame_frame = event.frame_frame
                nwo.frame_name = event.frame_name
                if event.multi_frame == "range" and event.frame_range > 1:
                    for _ in range(
                        min(event.frame_range - 1, frame_end - event.frame_frame)
                    ):
                        event_ob_copy = event_ob.copy()
                        copy_nwo = event_ob_copy.nwo
                        copy_nwo.event_id += 1
                        copy_nwo.frame_frame += 1
                        event_ob_copy.name = 'event_export_node_frame_' + str(copy_nwo.event_id)
                        scene_coll.link(event_ob_copy)
                        animation_events.append(event_ob_copy)
                        event_ob = event_ob_copy
                    
            elif nwo.event_type.startswith('_connected_geometry_animation_event_type_ik'):
                # Create animation controls
                proxy_target = bpy.data.objects.new('proxy_target_export_node_'+ nwo.ik_target_usage + '_' + nwo.ik_target_marker, None)
                proxy_target.parent = model_armature
                proxy_target.parent_type = 'BONE'
                proxy_target.parent_bone = root_bone_name
                rnd = random.Random()
                rnd.seed(proxy_target.name)
                proxy_target_id = str(rnd.randint(0, 2147483647))
                nwo.ik_proxy_target_id = proxy_target_id
                proxy_target_nwo = proxy_target.nwo
                proxy_target_nwo.object_type = '_connected_geometry_object_type_animation_control'
                proxy_target_nwo.animation_control_id = proxy_target_id
                proxy_target_nwo.animation_control_type = '_connected_geometry_animation_control_type_target_proxy'
                proxy_target_nwo.animation_control_proxy_target_usage = nwo.ik_target_usage
                proxy_target_nwo.animation_control_proxy_target_marker = nwo.ik_target_marker
                scene_coll.link(proxy_target)
                proxy_target.matrix_local = bpy.data.objects.get(nwo.ik_target_marker).matrix_local
                animation_events.append(proxy_target)
                
                effector = bpy.data.objects.new('ik_effector_export_node_'+ nwo.ik_chain + '_' + nwo.event_type[44:], None)
                effector.parent = model_armature
                effector.parent_type = 'BONE'
                effector.parent_bone = root_bone_name
                rnd = random.Random()
                rnd.seed(effector.name)
                effector_id = str(rnd.randint(0, 2147483647))
                nwo.ik_effector_id = effector_id
                effector_nwo = effector.nwo
                effector_nwo.object_type = '_connected_geometry_object_type_animation_control'
                effector_nwo.animation_control_id = effector_id
                effector_nwo.animation_control_type = '_connected_geometry_animation_control_type_ik_effector'
                effector_nwo.animation_control_ik_chain = nwo.ik_chain
                effector_nwo.animation_control_ik_effect = jstr(event.ik_influence)
                scene_coll.link(effector)
                effector.matrix_local = proxy_target.matrix_local
                animation_events.append(effector)
                
                rnd = random.Random()
                rnd.seed(event_ob.name + '117')
                nwo.ik_pole_vector_id = str(rnd.randint(0, 2147483647))
                
            else:
                nwo.frame_start = str(event.frame_frame)
                nwo.frame_end = str(event.frame_frame + event.frame_range)
                
        return animation_events

    #####################################################################################
    #####################################################################################
    # FBX

    def export_fbx(
        self,
        export_anim,
        fbx_filepath,
    ):  
        disable_prints()

        bpy.ops.export_scene.fbx(
            filepath=fbx_filepath,
            check_existing=False,
            use_selection=True,
            use_visible=True,
            apply_scale_options="FBX_SCALE_UNITS",
            use_mesh_modifiers=True,
            mesh_smooth_type="OFF",
            use_triangles=False,
            add_leaf_bones=False,
            use_armature_deform_only=True,
            bake_anim_use_all_bones=False,
            bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False,
            bake_anim_force_startend_keying=False,
            bake_anim_simplify_factor=0,
            axis_forward="X",
            axis_up="Z",
            bake_anim=export_anim,
        )

        enable_prints()
        return os.path.exists(fbx_filepath)

    #####################################################################################
    #####################################################################################
    # JSON

    def export_json(self, json_path, export_obs, asset_type, asset_name, nwo_scene):
        """Exports a json file by passing the currently selected objects to the NWOJSON class, and then writing the resulting dictionary to a .json file"""
        json_props = NWOJSON(
            export_obs,
            asset_type,
            nwo_scene.model_armature,
            None,
            asset_name,
            nwo_scene.skeleton_bones,
            nwo_scene.regions,
            nwo_scene.global_materials_dict,
            nwo_scene.skylights,
        )
        with open(json_path, "w") as j:
            json.dump(json_props.json_dict, j, indent=4)

        return os.path.exists(json_path)

    #####################################################################################
    #####################################################################################
    # GR2

    def export_gr2_sync(self, fbx_path, json_path, gr2_path, hide_output=True):
        run_tool(
            [
                "fbx-to-gr2",
                data_relative(fbx_path),
                data_relative(json_path),
                data_relative(gr2_path),
            ],
            False,
            hide_output,
        )

    def export_gr2(self, fbx_path, json_path, gr2_path):
        self.export_paths.append([fbx_path, json_path, gr2_path])
        # clear existing gr2, so we can test if export failed
        if os.path.exists(gr2_path):
            os.remove(gr2_path)

        while self.running_check > self.thread_max * 2:
            time.sleep(0.1)

        thread = threading.Thread(target=self.gr2, args=(fbx_path, json_path, gr2_path))
        thread.start()
        self.first_gr2 = False

    def gr2(self, fbx_path, json_path, gr2_path):
        self.running_check += 1
        self.gr2_processes += 1
        time.sleep(self.running_check / 10)
        run_tool(
            [
                "fbx-to-gr2",
                data_relative(fbx_path),
                data_relative(json_path),
                data_relative(gr2_path),
            ],
            False,
            True,
        )
        self.running_check -= 1


def patch_granny(gr2):
    replacement_data = b'H'
    header_size = 0x94
    with open(gr2, 'r+b') as file:
        file_data = bytearray(file.read())
        pointer_offset = 0x7C
        offset_bytes = file_data[pointer_offset:pointer_offset + 4]
        offset_value = int.from_bytes(offset_bytes, byteorder='little') + header_size  # Assuming little-endian byte order
        data_structure_offset = offset_value
        file_data[data_structure_offset:data_structure_offset + len(replacement_data)] = replacement_data
        file.seek(0)
        file.write(file_data)
        
def clear_constraints():
    for ob in bpy.data.objects:
        # ob.constraints.clear()
        if ob.type == 'ARMATURE':
            for pose_bone in ob.pose.bones:
                for con in pose_bone.constraints:
                    pose_bone.constraints.remove(con)
                    
def build_camera_tracks(context, camera, asset_folder_path):
    camera_track_actions = [action for action in bpy.data.actions if action.use_frame_range]
    print('')
    if not camera_track_actions:
        print_warning("No valid camera animations found")
        return
    
    print("Exporting Camera Tracks")
    print(
        "-----------------------------------------------------------------------\n"
    )
    for action in camera_track_actions:
        tag_path = os.path.join(asset_folder_path, action.name + '.camera_track')
        print(f"--- {action.name}")
        with CameraTrackTag(path=tag_path) as camera_track:
            camera_track.to_tag(context, action, camera)
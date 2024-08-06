import itertools
from pathlib import Path
import random
import time
import bpy
import os
import json
import multiprocessing
import threading
from ..managed_blam.scenario_structure_lighting_info import ScenarioStructureLightingInfoTag
from ..managed_blam import Tag
from ..tools.scenario.zone_sets import write_zone_sets_to_scenario
from ..export.tag_builder import build_tags
from ..tools.scenario.lightmap import run_lightmapper
from ..managed_blam.animation import AnimationTag
from ..managed_blam.camera_track import CameraTrackTag
from ..managed_blam.model import ModelTag
from ..managed_blam.scenario import ScenarioTag
from .format_json import NWOJSON
from ..utils import (
    disable_prints,
    enable_prints,
    get_animated_objects,
    get_data_path,
    get_tags_path,
    is_corinth,
    jstr,
    mute_armature_mods,
    print_warning,
    relative_path,
    reset_to_basis,
    run_tool,
    set_active_object,
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
        
        self.models_export_started = False
    
    def process_scene(self, context, sidecar_path, sidecar_path_full, asset, asset_path, asset_type, export_scene, scene_nwo_export, scene_nwo):
        reports = []
        gr2_count = 0
        h4 = is_corinth(context)
        muted_armature_deforms = []
        exported_actions = []
        if asset_type == 'camera_track_set':
            return build_camera_tracks(context, export_scene.camera, asset_path)
        if scene_nwo_export.export_gr2_files:
            self.slow_gr2 = scene_nwo_export.slow_gr2
            # make necessary directories
            models_dir = os.path.join(asset_path, "models")
            export_dir = os.path.join(asset_path, "export", "models")
            os.makedirs(models_dir, exist_ok=True)
            os.makedirs(export_dir, exist_ok=True)
            if asset_type in ("model", "animation"):
                if export_scene.model_armature and bpy.data.actions:
                    if scene_nwo_export.export_animations != "NONE":
                        timeline = context.scene
                        print("\n\nStarting Animations Export")
                        print(
                            "-----------------------------------------------------------------------\n"
                        )

                    # Handle swapping out armature
                    muted_armature_deforms = mute_armature_mods()
                    animated_objects = get_animated_objects(context)
                    
                    for ob in animated_objects:
                        if ob.type == 'ARMATURE' and ob.data.pose_position == 'REST':
                            ob.data.pose_position = 'POSE'
                            
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
                                    or export_scene.current_action == action
                                ):
                                    job = f"--- {animation_name}"
                                    update_job(job, 0)
                                    
                                    arm = export_scene.model_armature

                                    for ob in animated_objects: ob.animation_data.action = action
                                            
                                    timeline.frame_start = int(action.frame_start)
                                    timeline.frame_end = int(action.frame_end)

                                    context.scene.frame_set(int(action.frame_start))

                                    export_obs = self.create_event_nodes(
                                        context,
                                        action_nwo.animation_events,
                                        arm,
                                        export_scene.root_bone_name,
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
                                                export_scene,
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

                                    exported_actions.append(action)
                                    update_job(job, 1)

                            if "animation" in self.sidecar_paths.keys():
                                self.sidecar_paths["animation"].append(
                                    [
                                        relative_path(fbx_path),
                                        relative_path(json_path),
                                        relative_path(gr2_path),
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
                                        relative_path(fbx_path),
                                        relative_path(json_path),
                                        relative_path(gr2_path),
                                        animation_name,
                                        action_nwo.animation_type,
                                        action_nwo.animation_movement_data,
                                        action_nwo.animation_space,
                                        action_nwo.animation_is_pose,
                                        action_nwo.compression,
                                    ]
                                ]
                                
            clear_constraints()
            reset_to_basis(context)
            if muted_armature_deforms:
                unmute_armature_mods(muted_armature_deforms)
            if asset_type in ("model", "animation"):
                self.export_model(
                    context,
                    asset_path,
                    asset,
                    "render",
                    export_scene.render,
                    export_scene.render_perms,
                    export_scene.selected_perms,
                    export_scene.model_armature,
                    asset_type,
                    export_scene,
                    scene_nwo_export.export_render,
                )
                if asset_type == "model":
                    if export_scene.collision:
                        self.export_model(
                            context,
                            asset_path,
                            asset,
                            "collision",
                            export_scene.collision,
                            export_scene.collision_perms,
                            export_scene.selected_perms,
                            export_scene.model_armature,
                            asset_type,
                            export_scene,
                            scene_nwo_export.export_collision,
                        )

                    if export_scene.physics:
                        self.export_model(
                            context,
                            asset_path,
                            asset,
                            "physics",
                            export_scene.physics,
                            export_scene.physics_perms,
                            export_scene.selected_perms,
                            export_scene.model_armature,
                            asset_type,
                            export_scene,
                            scene_nwo_export.export_physics,
                        )

                    if export_scene.markers:
                        self.export_model(
                            context,
                            asset_path,
                            asset,
                            "markers",
                            export_scene.markers,
                            None,
                            None,
                            export_scene.model_armature,
                            asset_type,
                            export_scene,
                            scene_nwo_export.export_markers,
                        )

                fbx_path, json_path, gr2_path = self.get_path(
                    asset_path, asset, "skeleton", None, None, None
                )

                if export_scene.model_armature and scene_nwo_export.export_skeleton:
                    export_obs = [export_scene.model_armature]

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
                                export_scene,
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
                            relative_path(fbx_path),
                            relative_path(json_path),
                            relative_path(gr2_path),
                        ]
                    )
                else:
                    self.sidecar_paths["skeleton"] = [
                        [
                            relative_path(fbx_path),
                            relative_path(json_path),
                            relative_path(gr2_path),
                        ]
                    ]

            elif asset_type == "scenario":
                if export_scene.structure:
                    self.export_bsp(
                        context,
                        asset_path,
                        asset,
                        False,
                        export_scene.structure,
                        export_scene.selected_perms,
                        export_scene.selected_bsps,
                        asset_type,
                        export_scene,
                        export_scene.structure_bsps,
                        export_scene.structure_perms,
                        scene_nwo_export.export_structure,
                    )

                if export_scene.design:
                    self.export_bsp(
                        context,
                        asset_path,
                        asset,
                        True,
                        export_scene.design,
                        export_scene.selected_perms,
                        export_scene.selected_bsps,
                        asset_type,
                        export_scene,
                        export_scene.design_bsps,
                        export_scene.design_perms,
                        scene_nwo_export.export_design,
                    )

            elif asset_type == "sky":
                if export_scene.render:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "sky",
                        export_scene.render,
                        None,
                        None,
                        export_scene.model_armature,
                        asset_type,
                        export_scene,
                        scene_nwo_export.export_render,
                    )
                if export_scene.markers:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "markers",
                        export_scene.markers,
                        None,
                        None,
                        export_scene.model_armature,
                        asset_type,
                        export_scene,
                        scene_nwo_export.export_markers,
                    )

            elif asset_type == "decorator_set":
                if export_scene.render:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "decorator",
                        export_scene.render,
                        None,
                        None,
                        None,
                        asset_type,
                        export_scene,
                        scene_nwo_export.export_render,
                    )

            elif asset_type == "prefab":
                if export_scene.structure:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "prefab",
                        export_scene.structure,
                        None,
                        None,
                        None,
                        asset_type,
                        export_scene,
                        True,
                    )

            else:  # for particles
                if export_scene.render:
                    self.export_model(
                        context,
                        asset_path,
                        asset,
                        "particle_model",
                        export_scene.render,
                        None,
                        None,
                        None,
                        asset_type,
                        export_scene,
                        scene_nwo_export.export_render,
                    )

            from .build_sidecar import Sidecar
            
            sidecar = Sidecar(asset_path, asset, asset_type, context)
            sidecar.build(context, sidecar_path, sidecar_path_full, export_scene, self.sidecar_paths, self.sidecar_paths_design, scene_nwo)

            reports.append(sidecar.message)
            print("\n\nCreating Intermediary Files")
            print(
                "-----------------------------------------------------------------------\n"
            )

            total_p = self.gr2_processes

            job = "--- FBX & JSON -> GR2"
            spinner = itertools.cycle(["|", "/", "—", "\\"])
            while self.running_check:
                update_job_count(job, next(spinner), total_p - self.running_check, total_p)
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
            relative_asset_path = relative_path(asset_path)
            tag_folder_path = str(Path(get_tags_path(), relative_asset_path))
            scenery_path = str(Path(tag_folder_path, f"{asset}.scenery"))
            no_top_level_tag = hasattr(sidecar, "no_top_level_tag") and not os.path.exists(scenery_path)
            
            setup_scenario = False
            if asset_type == 'scenario':
                scenario_path = Path(tag_folder_path, f"{asset}.scenario")
                if not scenario_path.exists():
                    setup_scenario = True

            if scene_nwo_export.export_gr2_files and os.path.exists(sidecar_path_full):
                print("\n\nBuilding Tags")
                print("-----------------------------------------------------------------------\n")
                self.managed_blam_pre_import_tasks(export_scene, scene_nwo_export.export_animations, context.scene.nwo, exported_actions, setup_scenario, relative_asset_path, asset, asset_type, h4)
                export_failed, error = build_tags(asset_type, sidecar_path, asset_path, asset, scene_nwo_export, scene_nwo, export_scene.selected_bsps, export_scene.structure_bsps)
                if export_failed:
                    self.sidecar_import_failed = True
                    self.sidecar_import_error = error
                    reports.append("Tag Export Failed")
                else:
                    reports.append("Tag Export Complete")
                    self.managed_blam_post_import_tasks(context, context.scene.nwo, export_scene, asset_type, asset_path.replace(get_data_path(), ""), asset, sidecar.reach_world_animations, sidecar.pose_overlays, setup_scenario)
            else:
                reports.append("Skipped tag export, asset sidecar does not exist")


            if no_top_level_tag:
                if os.path.exists(scenery_path):
                    os.remove(scenery_path)

        should_lightmap = scene_nwo_export.lightmap_structure and (
            asset_type == "scenario" or (h4 and asset_type in ("model", "sky"))
        )

        if should_lightmap:
            lightmap_results = run_lightmapper(
                h4,
                export_scene.structure,
                asset,
                scene_nwo_export.lightmap_quality,
                scene_nwo_export.lightmap_quality_h4,
                scene_nwo_export.lightmap_all_bsps,
                scene_nwo_export.lightmap_specific_bsp,
                scene_nwo_export.lightmap_region,
                asset_type in ("model", "sky") and h4,
                scene_nwo_export.lightmap_threads,
                export_scene.structure_bsps)

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
        export_scene,
        export_check,
    ):      
        if obs_perms:
            perms = obs_perms
        else:
            perms = ["default"]

        for perm in perms:
            fbx_path, json_path, gr2_path = self.get_path(asset_path, asset, type, perm, None, None)
            sidecar_data =  [relative_path(fbx_path), relative_path(json_path), relative_path(gr2_path), perm]
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
                    if not self.models_export_started:
                        self.models_export_started = True
                        print("\n\nStarting Models Export")
                        print(
                            "-----------------------------------------------------------------------\n"
                        )
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
                                json_path, export_obs, asset_type, asset, export_scene
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
        export_scene,
        bsps,
        layers,
        export_check,
    ):
        type_name = 'design' if is_design else 'bsp'
        for bsp in bsps:
            for perm in layers:
                export_obs = [ob for ob in objects if (ob.nwo.permutation_name == perm) and (ob.nwo.region_name == bsp)]
                if not export_obs: continue
                fbx_path, json_path, gr2_path = self.get_path(asset_path, asset, type_name, perm, bsp, None)
                sidecar_data = [relative_path(fbx_path), relative_path(json_path), relative_path(gr2_path), perm]
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
                        if not self.models_export_started:
                            self.models_export_started = True
                            print("\n\nStarting Models Export")
                            print(
                                "-----------------------------------------------------------------------\n"
                            )
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
                                    export_scene,
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

    def managed_blam_pre_import_tasks(self, export_scene, export_animations, scene_nwo, exported_actions, setup_scenario, relative_asset_path, asset_name, asset_type, corinth):
        node_usage_set = self.asset_has_animations and export_animations and self.any_node_usage_override(scene_nwo, asset_type, corinth)
        # print("\n--- Foundry Tags Pre-Process\n")
        if node_usage_set or scene_nwo.ik_chains or exported_actions:
            with AnimationTag(hide_prints=False) as animation:
                if scene_nwo.parent_animation_graph:
                    animation.set_parent_graph(scene_nwo.parent_animation_graph)
                    # print("--- Set Parent Animation Graph")
                if exported_actions:
                    animation.validate_compression(exported_actions, scene_nwo.default_animation_compression)
                    # print("--- Validated Animation Compression")
                if node_usage_set:
                    animation.set_node_usages(export_scene.skeleton_bones)
                    #print("--- Updated Animation Node Usages")
                if scene_nwo.ik_chains:
                    animation.write_ik_chains(scene_nwo.ik_chains, export_scene.skeleton_bones)
                    # print("--- Updated Animation IK Chains")
                    
                if animation.tag_has_changes and (node_usage_set or scene_nwo.ik_chains):
                    # Graph should be data driven if ik chains or overlay groups in use.
                    # Node usages are a sign the user intends to create overlays group
                    animation.tag.SelectField("Struct:definitions[0]/ByteFlags:private flags").SetBit('uses data driven animation', True)
                    
        if setup_scenario and scene_nwo.scenario_type != 'solo':
            with ScenarioTag(hide_prints=True) as scenario:
                scenario.tag.SelectField('type').SetValue(scene_nwo.scenario_type)
                
        if scene_nwo.asset_type == 'particle_model' and scene_nwo.particle_uses_custom_points:
            emitter_path = str(Path(relative_asset_path, asset_name).with_suffix(".particle_emitter_custom_points"))
            if not Path(get_tags_path(), emitter_path).exists():
                with Tag(path=emitter_path) as _: pass

    def managed_blam_post_import_tasks(self, context, scene_nwo, export_scene, asset_type, asset_path, asset_name, reach_world_animations, pose_overlays, setup_scenario):
        nwo = context.scene.nwo
        model = asset_type == 'model'
        scenario = asset_type == 'scenario'
        # h4_model_lighting = (export_scene.lighting and is_corinth(context) and model_sky)
        model_override = (
            (nwo.template_render_model and model)
            or (nwo.template_collision_model and model)
            or (nwo.template_physics_model and model)
            or (nwo.template_model_animation_graph and model)
        )
        # print("\n--- Foundry Tags Post-Process")
        # If this model has lighting, add a reference to the structure_meta tag in the render_model
        # if h4_model_lighting:
        #     meta_path = os.path.join(asset_path, asset_name + '.structure_meta')
        #     with RenderModelTag(hide_prints=True) as render_model:
        #         render_model.set_structure_meta_ref(meta_path)
            # print("--- Added Structure Meta Reference to Render Model")

        # Apply model overrides if any
        if model and model_override:
            with ModelTag(hide_prints=False) as model:
                model.set_model_overrides(nwo.template_render_model, nwo.template_collision_model, nwo.template_model_animation_graph, nwo.template_physics_model)
            # print("--- Applied Model Overrides")
            
        if reach_world_animations or pose_overlays:
            with AnimationTag(hide_prints=False) as animation:
                if reach_world_animations:
                    animation.set_world_animations(reach_world_animations)
                if pose_overlays:
                    animation.setup_blend_screens(pose_overlays)
            # print("--- Setup World Animations")
            
        if scenario and setup_scenario:
            lm_value = 6 if is_corinth(context) else 3
            with ScenarioTag(hide_prints=True) as scenario:
                for bsp in export_scene.structure_bsps:
                    scenario.set_bsp_lightmap_res(bsp, lm_value, 0)
            # print("--- Set Lightmapper size class to 1k")
            
        if scenario and scene_nwo.zone_sets:
            write_zone_sets_to_scenario(scene_nwo, asset_name)
            
        for task in export_scene.lighting_tasks:
            if len(task) == 1:
                with ScenarioStructureLightingInfoTag(path=task[0]) as tag: tag.clear_lights()
            elif task[0].endswith('.model'):
                with ModelTag(path=task[0]) as tag: tag.assign_lighting_info_tag(task[1])
            else:
                with ScenarioStructureLightingInfoTag(path=task[0]) as tag: tag.build_tag(task[1], task[2])
            
    def any_node_usage_override(self, nwo, asset_type, corinth):
        if not corinth and asset_type == 'animation' and nwo.asset_animation_type == 'first_person':
            return False # Don't want to set node usages for reach fp animations, it breaks them
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
        self, context, events, model_armature, root_bone_name
    ):
        animation_events = [model_armature]
        scene_coll = context.scene.collection.objects
        for event in events:
            if event.event_type.startswith('_connected_geometry_animation_event_type_ik') and event.ik_chain == 'none': continue
            # create the event node to store event info
            event_ob = bpy.data.objects.new('event_export_node_' + event.event_type[41:] + '_' + str(event.event_id), None)
            # Set this node to be an animation event
            event_ob["bungie_object_type"] = "_connected_geometry_object_type_animation_event"
            # Set up the event node with the action start and end frame and id
            # add the user defined properties from the action
            event_ob["bungie_animation_event_id"] = str(abs(event.event_id))
            event_ob["bungie_animation_event_type"] = event.event_type
            if event.event_type == '_connected_geometry_animation_event_type_wrinkle_map':
                event_ob["bungie_animation_event_wrinkle_map_face_region"] = event.wrinkle_map_face_region
                event_ob["bungie_animation_event_wrinkle_map_effect"] = jstr(event.wrinkle_map_effect)
            elif event.event_type in ("_connected_geometry_animation_event_type_ik_active", "_connected_geometry_animation_event_type_ik_passive"):
                event_ob["bungie_animation_event_ik_chain"] = event.ik_chain
                event_ob["bungie_animation_event_ik_target_marker"] = event.ik_target_marker.name if event.ik_target_marker else ''
                event_ob["bungie_animation_event_ik_target_usage"] = event.ik_target_usage
            # add it to the list
            scene_coll.link(event_ob)
            animation_events.append(event_ob)
            # duplicate for frame range
            if event.event_type == '_connected_geometry_animation_event_type_frame':
                event_ob["bungie_animation_event_frame_frame"] = str(event.frame_frame)
                event_ob["bungie_animation_event_frame_name"] = event.frame_name
                if event.multi_frame == "range" and event.frame_range > event.frame_frame:
                    for i in range(event.frame_range - event.frame_frame):
                        event_ob_copy = event_ob.copy()
                        event_ob_copy["bungie_animation_event_id"] = str(abs(event.event_id) + i)
                        event_ob_copy["bungie_animation_event_frame_frame"] = str(event.frame_frame + i)
                        event_ob_copy.name = 'event_export_node_frame_' + event_ob_copy["bungie_animation_event_id"]
                        scene_coll.link(event_ob_copy)
                        animation_events.append(event_ob_copy)
                        event_ob = event_ob_copy
                    
            elif event.event_type.startswith('_connected_geometry_animation_event_type_ik'):
                # Create animation controls
                proxy_target = bpy.data.objects.new('proxy_target_export_node_'+ event.ik_target_usage + '_' + event_ob["bungie_animation_event_ik_target_marker"], None)
                proxy_target.parent = model_armature
                proxy_target.parent_type = 'BONE'
                proxy_target.parent_bone = root_bone_name
                rnd = random.Random()
                rnd.seed(proxy_target.name)
                proxy_target_id = str(rnd.randint(0, 2147483647))
                proxy_target["bungie_animation_event_ik_proxy_target_id"] = proxy_target_id
                proxy_target["bungie_object_type"] = '_connected_geometry_object_type_animation_control'
                proxy_target["bungie_animation_control_id"] = proxy_target_id
                proxy_target["bungie_animation_control_type"] = '_connected_geometry_animation_control_type_target_proxy'
                proxy_target["bungie_animation_control_proxy_target_usage"] = event_ob["bungie_animation_event_ik_target_usage"]
                proxy_target["bungie_animation_control_proxy_target_marker"] = event_ob["bungie_animation_event_ik_target_marker"]
                scene_coll.link(proxy_target)
                if event.ik_target_marker:
                    proxy_target.matrix_local = event.ik_target_marker.matrix_local
                animation_events.append(proxy_target)
                
                effector = bpy.data.objects.new('ik_effector_export_node_'+ event.ik_chain + '_' + event.event_type[44:], None)
                effector.parent = model_armature
                effector.parent_type = 'BONE'
                effector.parent_bone = root_bone_name
                rnd = random.Random()
                rnd.seed(effector.name)
                effector_id = str(rnd.randint(0, 2147483647))
                event_ob["bungie_animation_event_ik_effector_id"] = effector_id
                effector["bungie_object_type"] = '_connected_geometry_object_type_animation_control'
                effector["bungie_animation_control_id"] = effector_id
                effector["bungie_animation_control_type"] = '_connected_geometry_animation_control_type_ik_effector'
                effector["bungie_animation_control_ik_chain"] = event.ik_chain
                effector["bungie_animation_control_ik_effect"] = jstr(event.ik_influence)
                scene_coll.link(effector)
                effector.matrix_local = proxy_target.matrix_local
                animation_events.append(effector)
                
                rnd = random.Random()
                rnd.seed(event_ob.name + '117')
                event_ob["bungie_animation_event_ik_pole_vector_id"] = str(rnd.randint(0, 2147483647))
                
            else:
                event_ob["bungie_animation_event_start"] = str(event.frame_frame)
                event_ob["bungie_animation_event_end"] = str(event.frame_frame + event.frame_range)
                
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
            use_custom_props=True,
        )

        enable_prints()
        return os.path.exists(fbx_filepath)

    #####################################################################################
    #####################################################################################
    # JSON

    def export_json(self, json_path, export_obs, asset_type, asset_name, export_scene):
        """Exports a json file by passing the currently selected objects to the NWOJSON class, and then writing the resulting dictionary to a .json file"""
        json_props = NWOJSON(
            export_obs,
            asset_type,
            export_scene.model_armature,
            None,
            asset_name,
            export_scene.skeleton_bones,
            export_scene.validated_regions,
            export_scene.validated_permutations,
            export_scene.global_materials_dict,
            export_scene.skylights,
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
                relative_path(fbx_path),
                relative_path(json_path),
                relative_path(gr2_path),
            ],
            False,
            hide_output,
        )

    def export_gr2(self, fbx_path, json_path, gr2_path):
        self.export_paths.append([fbx_path, json_path, gr2_path])
        # clear existing gr2, so we can test if export failed
        if os.path.exists(gr2_path):
            os.remove(gr2_path)
            
            
        if self.slow_gr2:
            self.gr2_processes += 1
            return self.export_gr2_sync(fbx_path, json_path, gr2_path)

        while self.running_check > self.thread_max * 2:
            time.sleep(0.1)

        thread = threading.Thread(target=self.gr2, args=(fbx_path, json_path, gr2_path))
        thread.start()
        self.first_gr2 = False

    def gr2(self, fbx_path, json_path, gr2_path):
        self.gr2_processes += 1
        self.running_check += 1
        time.sleep(self.running_check / 10)
        run_tool(
            [
                "fbx-to-gr2",
                relative_path(fbx_path),
                relative_path(json_path),
                relative_path(gr2_path),
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
    set_active_object(camera)
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
        camera.animation_data.action = action
        tag_path = os.path.join(asset_folder_path, action.name + '.camera_track')
        print(f"--- {action.name}")
        with CameraTrackTag(path=tag_path) as camera_track:
            camera_track.to_tag(context, action, camera)
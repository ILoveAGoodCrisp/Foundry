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
from pathlib import Path
import bpy
import glob
from io_scene_foundry.managed_blam.scenario import ScenarioTag
from io_scene_foundry.utils.nwo_utils import (
    get_data_path,
    get_exe,
    get_prefs,
    get_project_path,
    get_tags_path,
    is_corinth,
    nwo_asset_type,
    relative_path,
    run_ek_cmd,
    update_debug_menu,
    valid_nwo_asset,
)

class NWO_OpenFoundationTag(bpy.types.Operator):
    bl_idname = "nwo.open_foundation_tag"
    bl_label = "Open in Tag Editor"
    bl_description = "Opens the specified tag in Foundation"

    tag_path : bpy.props.StringProperty()

    def execute(self, context):
        full_tag_path = Path(get_tags_path(), self.tag_path)
        if full_tag_path.exists():
            run_ek_cmd(["foundation", "/dontloadlastopenedwindows", full_tag_path], True)
        else:
            self.report({"WARNING"}, "Tag does not exist")
        return {"FINISHED"}
        

def get_tag_if_exists(asset_path, asset_name, type, extra=""):
    tag = Path(get_tags_path(), asset_path, f"{asset_name}.{type}")
    if tag.exists():
        return str(tag)
    else:
        return ""

def launch_foundation(settings, context):
    scene_nwo = context.scene.nwo
    launch_args = ["Foundation.exe"]
    # set the launch args
    if settings.foundation_default == "asset" and valid_nwo_asset(context):
        launch_args.append("/dontloadlastopenedwindows")
        asset_path = scene_nwo.asset_directory
        asset_path_full = Path(get_tags_path(), asset_path)
        asset_name = scene_nwo.asset_name
        if nwo_asset_type() == "model":
            if settings.open_model:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "model"))
            if settings.open_render_model:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "render_model")
                )
            if settings.open_collision_model:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "collision_model")
                )
            if settings.open_physics_model:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "physics_model")
                )
            if settings.open_model_animation_graph and len(bpy.data.actions) > 0:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "model_animation_graph")
                )
            if settings.open_frame_event_list and len(bpy.data.actions) > 0:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "frame_event_list")
                )

            if settings.open_biped and scene_nwo.output_biped:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "biped"))
            if settings.open_crate and scene_nwo.output_crate:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "crate"))
            if settings.open_creature and scene_nwo.output_creature:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "creature")
                )
            if settings.open_device_control and scene_nwo.output_device_control:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "device_control")
                )
            if (
                settings.open_device_dispenser
                and scene_nwo.output_device_dispenser
                and is_corinth()
            ):
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "device_dispenser")
                )
            if settings.open_device_machine and scene_nwo.output_device_machine:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "device_machine")
                )
            if settings.open_device_terminal and scene_nwo.output_device_terminal:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "device_terminal")
                )
            if settings.open_effect_scenery and scene_nwo.output_effect_scenery:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "effect_scenery")
                )
            if settings.open_equipment and scene_nwo.output_equipment:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "equipment")
                )
            if settings.open_giant and scene_nwo.output_giant:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "giant"))
            if settings.open_scenery and scene_nwo.output_scenery:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "scenery"))
            if settings.open_vehicle and scene_nwo.output_vehicle:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "vehicle"))
            if settings.open_weapon and scene_nwo.output_weapon:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "weapon"))

        elif nwo_asset_type() == "scenario":
            if settings.open_scenario:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "scenario")
                )
            if settings.open_scenario_structure_bsp:
                if settings.bsp_name == "":
                    for file in asset_path_full.glob("*.scenario_structure_bsp"):
                        launch_args.append(str(file))
                else:
                    # get all bsps given by user and add asset name
                    bsps = settings.bsp_name.replace(" ", "")
                    bsps = bsps.split(",")
                    bsps = [asset_name + "_" + bsp for bsp in bsps]
                    bsps = tuple(bsps)
                    # added each to launch args
                    for file in asset_path_full.glob("*.scenario_structure_bsp"):
                        launch_args.append(str(file))

            if settings.open_scenario_lightmap_bsp_data:
                if settings.bsp_name == "":
                    for file in asset_path_full.glob("*.scenario_lightmap_bsp_data"):
                        launch_args.append(str(file))
                else:
                    # get all bsps given by user and add asset name
                    bsps = settings.bsp_name.replace(" ", "")
                    bsps = bsps.split(",")
                    bsps = [asset_name + "_" + bsp for bsp in bsps]
                    bsps = tuple(bsps)
                    # added each to launch args
                    for file in asset_path_full.glob("*.scenario_lightmap_bsp_data"):
                        launch_args.append(str(file))
                        
            if settings.open_scenario_structure_lighting_info:
                if settings.bsp_name == "":
                    for file in asset_path_full.glob("*.scenario_structure_lighting_info"):
                        launch_args.append(str(file))
                else:
                    # get all bsps given by user and add asset name
                    bsps = settings.bsp_name.replace(" ", "")
                    bsps = bsps.split(",")
                    bsps = [asset_name + "_" + bsp for bsp in bsps]
                    bsps = tuple(bsps)
                    # added each to launch args
                    for file in asset_path_full.glob("*.scenario_structure_lighting_info"):
                        launch_args.append(str(file))

        elif nwo_asset_type() == "sky":
            if settings.open_model:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "model"))
            if settings.open_render_model:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "render_model")
                )
            if settings.open_scenery:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "scenery"))

        elif nwo_asset_type() == "decorator_set":
            if settings.open_decorator_set:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "decorator_set")
                )

        elif nwo_asset_type() == "particle_model":
            if settings.open_particle_model:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "particle_model")
                )

        elif nwo_asset_type() == "prefab":
            if settings.open_prefab:
                launch_args.append(get_tag_if_exists(asset_path, asset_name, "prefab"))
            if settings.open_scenario_structure_bsp:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "scenario_structure_bsp")
                )
            if settings.open_scenario_structure_lighting_info:
                launch_args.append(
                    get_tag_if_exists(
                        asset_path,
                        asset_name,
                        "scenario_structure_lighting_info",
                    )
                )

        elif nwo_asset_type() == "animation":
            if settings.open_model_animation_graph:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "model_animation_graph")
                )
            if settings.open_frame_event_list:
                launch_args.append(
                    get_tag_if_exists(asset_path, asset_name, "frame_event_list")
                )
                
        elif nwo_asset_type() == "camera_track_set":
            if settings.camera_track_name:
                launch_args.append(
                    get_tag_if_exists(asset_path, settings.camera_track_name, "camera_track")
                )

    # first, get and set the project so we can avoid the Foundation prompt
    run_ek_cmd(launch_args, True)
    run_ek_cmd([os.path.join("bin", "tools", "bonobo", "TagWatcher.exe")], True)

    return {"FINISHED"}

def launch_game(is_sapien, settings, filepath, scene_nwo, ignore_play=False):
    asset_path = scene_nwo.asset_directory
    asset_name = scene_nwo.asset_name
    using_filepath = filepath.endswith(".scenario")
    if scene_nwo.asset_type == 'model' and get_prefs().debug_menu_on_launch:
        update_debug_menu(asset_path, asset_name)
    # get the program to launch
    if is_sapien:
        if not ignore_play and settings.use_play:
            args = [get_exe("sapien_play")]
        else:
            args = [get_exe("sapien")]
        # Sapien needs the scenario in the launch args so adding this here
        if nwo_asset_type() == "scenario" and settings.game_default == "asset":
            filepath = get_tag_if_exists(asset_path, asset_name, "scenario")
        
        args.append(filepath)
        
    else:
        if not ignore_play and settings.use_play:
            args = [get_exe("tag_play")]
        else:
            args = [get_exe("tag_test")]

    os.chdir(get_project_path())
    # Write the init file
    init = ""
    if os.path.exists("bonobo_init.txt"):
        try:
            if os.path.exists("bonobo_init_old.txt"):
                os.remove("bonobo_init_old.txt")
            os.rename("bonobo_init.txt", "bonobo_init_old.txt")
            init = "bonobo_init.txt"
        except:
            print("Unable to replace bonobo_init.txt. It is currently read only")
    else:
        init = "bonobo_init.txt"

    if init != "":
        h4_plus = is_corinth()
        with open(init, "w") as file:
            if settings.prune_globals:
                if h4_plus:
                    file.write("prune_globals 1\n")
                else:
                    file.write("prune_global 1\n")

            if settings.prune_globals_keep_playable:
                if h4_plus:
                    file.write("prune_globals_keep_playable 1\n")
                else:
                    file.write("prune_global_keep_playable 1\n")
            if settings.prune_scenario_for_environment_editing:
                file.write("prune_scenario_for_environment_editing 1\n")
                if settings.prune_scenario_for_environment_editing:
                    if settings.prune_scenario_for_environment_editing_keep_cinematics:
                        file.write(
                            "prune_scenario_for_environment_editing_keep_cinematics 1\n"
                        )
                    if settings.prune_scenario_for_environment_editing_keep_scenery:
                        file.write(
                            "prune_scenario_for_environment_editing_keep_scenery 1\n"
                        )
                    if settings.prune_scenario_for_environment_editing_keep_decals:
                        file.write(
                            "prune_scenario_for_environment_editing_keep_decals 1\n"
                        )
                    if settings.prune_scenario_for_environment_editing_keep_crates:
                        file.write(
                            "prune_scenario_for_environment_editing_keep_crates 1\n"
                        )
                    if settings.prune_scenario_for_environment_editing_keep_creatures:
                        file.write(
                            "prune_scenario_for_environment_editing_keep_creatures 1\n"
                        )
                    if settings.prune_scenario_for_environment_editing_keep_pathfinding:
                        if h4_plus:
                            file.write(
                                "prune_scenario_for_environment_editing_keep_pathfinding 1\n"
                            )
                        else:
                            file.write("prune_scenario_for_environment_pathfinding 1\n")

                    if (
                        settings.prune_scenario_for_environment_editing_keep_new_decorator_block
                    ):
                        file.write(
                            "prune_scenario_for_environmnet_editing_keep_new_decorator_block 1\n"
                        )
            if settings.prune_scenario_all_lightmaps:
                if h4_plus:
                    file.write("prune_scenario_all_lightmaps 1\n")
                else:
                    file.write("prune_scenario_lightmaps 1\n")

            if settings.prune_all_materials_use_gray_shader:
                if h4_plus:
                    file.write("prune_all_materials_use_gray_shader 1\n")
                else:
                    file.write("prune_scenario_use_gray_shader 1\n")
            if settings.prune_all_material_effects:
                if h4_plus:
                    file.write("prune_all_material_effects 1\n")
                else:
                    file.write("prune_global_material_effects 1\n")

            if settings.prune_all_dialog_sounds:
                if h4_plus:
                    file.write("prune_all_dialog_sounds 1\n")
                else:
                    file.write("prune_global_dialog_sounds 1\n")

            if settings.prune_all_error_geometry:
                if h4_plus:
                    file.write("prune_all_error_geometry 1\n")
                else:
                    file.write("prune_error_geometry 1\n")
            # H4+ only
            if h4_plus:
                if settings.prune_globals_use_empty:
                    file.write("prune_globals_use_empty 1\n")
                if settings.prune_models_enable_alternate_render_models:
                    file.write("prune_models_enable_alternate_render_models 1\n")
                if settings.prune_scenario_keep_scriptable_objects:
                    file.write("prune_scenario_keep_scriptable_objects 1\n")
                if settings.prune_all_materials_use_default_textures:
                    file.write("prune_all_materials_use_default_textures 1\n")
                if settings.prune_all_materials_use_default_textures_fx_textures:
                    file.write(
                        "prune_all_materials_use_default_textures_keep_fx_textures 1\n"
                    )
                if settings.prune_facial_animations:
                    file.write("prune_facial_animations 1\n")
                if settings.prune_first_person_animations:
                    file.write("prune_first_person_animations 1\n")
                if settings.prune_low_quality_animations:
                    file.write("prune_low_quality_animations 1\n")
                if settings.prune_use_imposters:
                    file.write("prune_use_imposters 1\n")
                if settings.prune_cinematic_effects:
                    file.write("prune_cinematic_effects 1\n")
            # Reach Only
            else:
                if settings.prune_scenario_force_solo_mode:
                    file.write("prune_scenario_force_solo_mode 1\n")
                if settings.prune_scenario_for_environment_editing:
                    if settings.prune_scenario_for_environment_finishing:
                        file.write("prune_scenario_for_environment_finishing 1\n")
                if settings.prune_scenario_force_single_bsp_zone_set:
                    file.write("prune_scenario_force_single_bsp_zone_set 1\n")
                if settings.prune_scenario_force_single_bsp_zones:
                    file.write("prune_scenario_add_single_bsp_zones 1\n")
                if settings.prune_keep_scripts:
                    file.write("pruning_keep_scripts 1\n")
                    
            
            if not is_sapien:
                if scenario_is_multiplayer(filepath):
                    if settings.forge:
                        file.write('game_multiplayer sandbox\n')
                    else:
                        file.write('game_multiplayer megalo\n')
                    if settings.megalo_variant:
                        file.write(f'game_set_variant {settings.megalo_variant}\n')
                elif scenario_is_firefight(filepath):
                    file.write('game_multiplayer survival\n')
                    if settings.megalo_variant:
                        file.write(f'game_set_variant {settings.megalo_variant}\n')
                
                file.write(
                    f'run_game_scripts {"1" if settings.run_game_scripts else "0"}\n'
                )
                
            if not settings.show_debugging:
                file.write('error_geometry_hide_all\n')
                file.write('events_enabled 0\n')
                file.write('ai_hide_actor_errors 1\n')
                file.write('terminal_render 0\n')
                file.write('console_status_string_render 0\n')
                file.write('events_debug_spam_render 0\n')

            if settings.initial_zone_set != "":
                file.write(f"game_initial_zone_set {settings.initial_zone_set}\n")
            elif settings.initial_bsp != "" and h4_plus:
                file.write(f"game_initial_BSP {settings.initial_bsp}\n")

            if settings.insertion_point_index > -1:
                file.write(
                    f"game_insertion_point_set {settings.insertion_point_index}\n"
                )

            if settings.enable_firefight and h4_plus:
                file.write(f"game_firefight {settings.enable_firefight}\n")
                if settings.firefight_mission == "":
                    file.write(f'game_set_variant "midnight_firefight_firefight"\n')
                else:
                    file.write(f'game_set_variant "{settings.firefight_mission}"\n')

            if settings.custom_functions != "":
                try:
                    for line in bpy.data.texts[settings.custom_functions].lines:
                        file.write(f"{line.body}\n")
                except:
                    if os.path.exists(f"{settings.custom_functions}.txt"):
                        with open(
                            f"{settings.custom_functions}.txt", "r"
                        ) as custom_init:
                            new_lines = custom_init.readlines()

                        for line in new_lines:
                            file.write(f"{line}\n")
                    else:
                        file.write(f"{settings.custom_functions}\n")
                        
                        
            if not is_sapien:
                if using_filepath:
                    file.write(
                        f'game_start "{str(Path(relative_path(filepath)).with_suffix(""))}"\n'
                    )
                else:
                    file.write(
                        f'game_start "{str(Path(relative_path(get_tag_if_exists(asset_path, asset_name, "scenario"))).with_suffix(""))}"\n'
                    )

    run_ek_cmd(args, True)

    return {"FINISHED"}

def open_file_explorer_default(is_tags, tags_dir, data_dir):
    if is_tags:
        os.startfile(tags_dir)
    else:
        os.startfile(data_dir)

    return {"FINISHED"}

def open_file_explorer(type, is_tags, scene_nwo):
    tags_dir = get_tags_path()
    data_dir = get_data_path()
    if type == "asset":
        asset_path = scene_nwo.asset_directory
        if valid_nwo_asset():
            if is_tags:
                if Path(tags_dir, asset_path).exists():
                    os.startfile(Path(tags_dir, asset_path))
                    return {"FINISHED"}
            else:
                os.startfile(Path(data_dir, asset_path))
                return {"FINISHED"}

    if type == "asset" or type == "blend":
        blend_folder = os.path.dirname(bpy.data.filepath)
        if not blend_folder.startswith(data_dir):
            return open_file_explorer_default(is_tags, tags_dir, data_dir)
        
        relative = blend_folder.replace(data_dir, "")
        if is_tags:
            folder_path = str(Path(tags_dir, relative))
            folder_path2 = os.path.dirname(folder_path)
            folder_path3 = os.path.dirname(folder_path2)
            if os.path.exists(folder_path):
                os.startfile(folder_path)
                return {"FINISHED"}
            elif os.path.exists(folder_path2):
                os.startfile(folder_path2)
                return {"FINISHED"}
            elif os.path.exists(folder_path3):
                os.startfile(folder_path3)
                return {"FINISHED"}
            else:
                return open_file_explorer_default(is_tags, tags_dir, data_dir)
        
        elif Path(data_dir, relative).exists():
            os.startfile(Path(data_dir, relative))
            return {"FINISHED"}
        
    return open_file_explorer_default(is_tags, tags_dir, data_dir)


class NWO_MaterialGirl(bpy.types.Operator):
    bl_label = "Material Viewer"
    bl_idname = "nwo.open_matman"

    def execute(self, context):
        launch_args = [os.path.join(get_project_path(), "Foundation.exe")]
        launch_args.append("/pluginset:matman")
        run_ek_cmd(launch_args, True)
        run_ek_cmd(["bin\\tools\\bonobo\\TagWatcher.exe"], True)
        return {'FINISHED'}

def scenario_is_multiplayer(scenario_path):
    with ScenarioTag(path=scenario_path) as scenario:
        scenario_type = scenario.read_scenario_type()
        
    return scenario_type == 1

def scenario_is_firefight(scenario_path):
    with ScenarioTag(path=scenario_path) as scenario:
        return scenario.survival_mode()
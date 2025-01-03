

import os
from pathlib import Path
import bpy

from ..ui.bar import draw_game_launcher_pruning, draw_game_launcher_settings
from ..managed_blam.scenario import ScenarioTag
from ..utils import (
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
                    bsp = Path(asset_path_full, f"{settings.bsp_name}.scenario_structure_bsp")
                    if bsp.exists():
                        launch_args.append(str(bsp))

            if settings.open_scenario_lightmap_bsp_data:
                if settings.bsp_name == "":
                    for file in asset_path_full.glob("*.scenario_lightmap_bsp_data"):
                        launch_args.append(str(file))
                else:
                    bsp = Path(asset_path_full, f"{settings.bsp_name}.scenario_lightmap_bsp_data")
                    if bsp.exists():
                        launch_args.append(str(bsp))
                        
            if settings.open_scenario_structure_lighting_info:
                if settings.bsp_name == "":
                    for file in asset_path_full.glob("*.scenario_structure_lighting_info"):
                        launch_args.append(str(file))
                else:
                    bsp = Path(asset_path_full, f"{settings.bsp_name}.scenario_structure_lighting_info")
                    if bsp.exists():
                        launch_args.append(str(bsp))

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
    if scene_nwo.asset_type == 'model' and get_prefs().debug_menu_on_launch:
        update_debug_menu(asset_path, asset_name)
    # get the program to launch
    
    asset_type = scene_nwo.asset_type
    if asset_type in {"scenario", "cinematic"} and settings.game_default == "asset":
        if asset_type == "scenario":
            filepath = get_tag_if_exists(asset_path, asset_name, "scenario")
        else:
            cin_scen_path = Path(get_tags_path(), relative_path(scene_nwo.cinematic_scenario))
            if cin_scen_path.exists() and cin_scen_path.is_file() and cin_scen_path.is_absolute():
                filepath = str(cin_scen_path)
    
    if is_sapien:
        if not ignore_play and settings.use_play:
            args = [get_exe("sapien_play")]
        else:
            args = [get_exe("sapien")]
        # Sapien needs the scenario in the launch args so adding this here
        
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
                file.write(
                    f'game_start "{str(Path(relative_path(filepath)).with_suffix(""))}"\n'
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
    
class NWO_HaloLauncher_Foundation(bpy.types.Operator):
    """Launches Foundation"""

    bl_idname = "nwo.launch_foundation"
    bl_label = "Foundation"

    def execute(self, context):
        from .halo_launcher import launch_foundation

        return launch_foundation(context.scene.nwo_halo_launcher, context)


class NWO_HaloLauncher_Data(bpy.types.Operator):
    """Opens the Data Folder"""

    bl_idname = "nwo.launch_data"
    bl_label = "Data"

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        return open_file_explorer(
            scene_nwo_halo_launcher.explorer_default,
            False,
            scene.nwo
        )


class NWO_HaloLauncher_Tags(bpy.types.Operator):
    """Opens the Tags Folder"""

    bl_idname = "nwo.launch_tags"
    bl_label = "Tags"

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        return open_file_explorer(
            scene_nwo_halo_launcher.explorer_default,
            True,
            scene.nwo
        )


class NWO_HaloLauncher_Sapien(bpy.types.Operator):
    """Opens Sapien"""

    bl_idname = "nwo.launch_sapien"
    bl_label = "Sapien"

    filter_glob: bpy.props.StringProperty(
        default="*.scenario",
        options={"HIDDEN"},
    )

    filepath: bpy.props.StringProperty(
        name="filepath",
        description="Set path for the scenario",
        subtype="FILE_PATH",
    )
    
    ignore_play: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        return launch_game(True, scene_nwo_halo_launcher, self.filepath.lower(), scene.nwo, self.ignore_play)

    def invoke(self, context, event):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        if (
            scene_nwo_halo_launcher.game_default == "default"
            or not scene.nwo.is_valid_asset
            or scene.nwo.asset_type not in {'cinematic', 'scenario'}
        ):
            self.filepath = get_tags_path() + os.sep
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = ""
            return self.execute(context)
        
    def draw(self, context):
        layout = self.layout
        scene_nwo_launcher = context.scene.nwo_halo_launcher
        draw_game_launcher_settings(scene_nwo_launcher, layout)
        box = layout.box()
        box.label(text="Pruning")
        draw_game_launcher_pruning(scene_nwo_launcher, box)
        

class NWO_HaloLauncher_TagTest(bpy.types.Operator):
    """Opens Tag Test"""

    bl_idname = "nwo.launch_tagtest"
    bl_label = "Tag Test"

    filter_glob: bpy.props.StringProperty(
        default="*.scenario",
        options={"HIDDEN"},
    )

    filepath: bpy.props.StringProperty(
        name="filepath",
        description="Set path for the scenario",
        subtype="FILE_PATH",
    )
    
    ignore_play: bpy.props.BoolProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        return launch_game(False, scene_nwo_halo_launcher, self.filepath.lower(), scene.nwo, self.ignore_play)

    def invoke(self, context, event):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        if (
            scene_nwo_halo_launcher.game_default == "default"
            or not scene.nwo.is_valid_asset
            or scene.nwo.asset_type not in {'cinematic', 'scenario'}
        ):
            self.filepath = get_tags_path() + os.sep
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = ""
            return self.execute(context)
        
    def draw(self, context):
        layout = self.layout
        scene_nwo_launcher = context.scene.nwo_halo_launcher
        draw_game_launcher_settings(scene_nwo_launcher, layout)
        box = layout.box()
        box.label(text="Pruning")
        draw_game_launcher_pruning(scene_nwo_launcher, box)


class NWO_HaloLauncherPropertiesGroup(bpy.types.PropertyGroup):
    explorer_default: bpy.props.EnumProperty(
        name="Folder",
        description="Select whether to open the root data / tags folder, the blend folder, or the one for your asset. When no asset is found, defaults to root",
        default="asset",
        options=set(),
        items=[("default", "Root", ""), ("asset", "Asset", ""), ("blend", "Blend", "")],
    )

    foundation_default: bpy.props.EnumProperty(
        name="Tags",
        description="Select whether Foundation should open with the last opended windows, or open to the selected asset tags",
        default="asset",
        options=set(),
        items=[
            ("last", "Default", ""),
            ("asset", "Asset", ""),
        ],
    )

    game_default: bpy.props.EnumProperty(
        name="Scenario",
        description="Select whether to open Sapien / Tag Test and select a scenario, or open the current scenario asset if it exists",
        default="asset",
        options=set(),
        items=[("default", "Browse", ""), ("asset", "Asset", "")],
    )

    open_model: bpy.props.BoolProperty(
        name="Model",
        default=True,
        options=set(),
    )

    open_render_model: bpy.props.BoolProperty(options=set(), name="Render Model")

    open_collision_model: bpy.props.BoolProperty(options=set(), name="Collision Model")

    open_physics_model: bpy.props.BoolProperty(options=set(), name="Physics Model")

    open_model_animation_graph: bpy.props.BoolProperty(
        options=set(), name="Model Animation Graph"
    )

    open_frame_event_list: bpy.props.BoolProperty(options=set(), name="Frame Event List")

    open_biped: bpy.props.BoolProperty(options=set(), name="Biped")

    open_crate: bpy.props.BoolProperty(options=set(), name="Crate")

    open_creature: bpy.props.BoolProperty(options=set(), name="Creature")

    open_device_control: bpy.props.BoolProperty(options=set(), name="Device Control")

    open_device_dispenser: bpy.props.BoolProperty(options=set(), name="Device Dispenser")

    open_device_machine: bpy.props.BoolProperty(options=set(), name="Device Machine")

    open_device_terminal: bpy.props.BoolProperty(options=set(), name="Device Terminal")

    open_effect_scenery: bpy.props.BoolProperty(options=set(), name="Effect Scenery")

    open_equipment: bpy.props.BoolProperty(options=set(), name="Equipment")

    open_giant: bpy.props.BoolProperty(options=set(), name="Giant")

    open_scenery: bpy.props.BoolProperty(options=set(), name="Scenery")

    open_vehicle: bpy.props.BoolProperty(options=set(), name="Vehicle")

    open_weapon: bpy.props.BoolProperty(options=set(), name="Weapon")

    open_scenario: bpy.props.BoolProperty(options=set(), name="Scenario", default=True)

    open_prefab: bpy.props.BoolProperty(options=set(), name="Prefab", default=True)

    open_particle_model: bpy.props.BoolProperty(
        options=set(), name="Particle Model", default=True
    )

    open_decorator_set: bpy.props.BoolProperty(options=set(), name="Decorator Set", default=True)
    
    def camera_track_items(self, context):
        items = []
        actions = [a for a in bpy.data.actions if a.use_frame_range]
        for a in actions:
            items.append((a.name, a.name, ''))
            
        return items
    
    camera_track_name: bpy.props.EnumProperty(
        options=set(),
        name="Camera Track",
        description="The camera track tag to open",
        items=camera_track_items, 
    )
    
    def bsp_name_items(self, context):
        items = []
        bsps = [b.name for b in context.scene.nwo.regions_table if b.name.lower() != "shared"]
        for b in bsps:
            items.append((b, b, ''))
            
        return items

    bsp_name: bpy.props.EnumProperty(
        options=set(),
        name="BSP",
        description="The BSP tag to open",
        items=bsp_name_items,
    )

    open_scenario_structure_bsp: bpy.props.BoolProperty(
        options=set(),
        name="BSP",
    )

    open_scenario_lightmap_bsp_data: bpy.props.BoolProperty(
        options=set(),
        name="Lightmap Data",
    )

    open_scenario_structure_lighting_info: bpy.props.BoolProperty(
        options=set(),
        name="Lightmap Info",
    )

    ##### game launch #####

    use_play : bpy.props.BoolProperty(
        name="Use Play Variant",
        description="Launches sapien_play / tag_play instead. These versions have less debug information and should load faster",
    )

    run_game_scripts: bpy.props.BoolProperty(
        options=set(),
        description="Runs all startup, dormant, and continuous scripts on map load",
        name="TagTest Run Scripts",
        default=True,
    )
    
    forge: bpy.props.BoolProperty(
        name="TagTest Load Forge",
        description="Open the scenario with the Forge gametype loaded if the scenario type is set to multiplayer"
    )
    
    megalo_variant: bpy.props.StringProperty(
        name="Megalo Variant",
        description="Name of the megalo variant to load",
    )
    
    show_debugging: bpy.props.BoolProperty(
        name="Show Debugging/Errors",
        description="If disabled, will turn off debugging text spew and error geometry",
        default=True,
    )

    prune_globals: bpy.props.BoolProperty(
        options=set(),
        description="Strips all player information, global materials, grenades and powerups from the globals tag, as well as interface global tags. Don't use this if you need the game to be playable",
        name="Globals",
    )

    prune_globals_keep_playable: bpy.props.BoolProperty(
        options=set(),
        description="Strips player information (keeping one single player element), global materials, grenades and powerups. Keeps the game playable.",
        name="Globals (Keep Playable)",
    )

    prune_globals_use_empty: bpy.props.BoolProperty(
        options=set(),
        description="Uses global_empty.globals instead of globals.globals",
        name="Globals Use Empty",
    )

    prune_models_enable_alternate_render_models: bpy.props.BoolProperty(
        options=set(),
        description="Allows tag build to use alternative render models specified in the .model",
        name="Allow Alternate Render Models",
    )

    prune_scenario_keep_scriptable_objects: bpy.props.BoolProperty(
        options=set(),
        description="Attempts to run scripts while pruning",
        name="Keep Scriptable Objects",
    )

    prune_scenario_for_environment_editing: bpy.props.BoolProperty(
        options=set(),
        description="Removes everything but the environment: Weapons, vehicles, bipeds, equipment, cinematics, AI, etc",
        name="Prune for Environment Editing",
    )

    prune_scenario_for_environment_editing_keep_cinematics: bpy.props.BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of cutscene flags and cinematics",
        name="Keep Cinematics",
    )

    prune_scenario_for_environment_editing_keep_scenery: bpy.props.BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of scenery",
        name="Keep Scenery",
    )

    prune_scenario_for_environment_editing_keep_decals: bpy.props.BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decals",
        name="Keep Decals",
    )

    prune_scenario_for_environment_editing_keep_crates: bpy.props.BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of crates",
        name="Keep Crates",
    )

    prune_scenario_for_environment_editing_keep_creatures: bpy.props.BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of creatures",
        name="Keep Creatures",
    )

    prune_scenario_for_environment_editing_keep_pathfinding: bpy.props.BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of pathfinding",
        name="Keep Pathfinding",
    )

    prune_scenario_for_environment_editing_keep_new_decorator_block: bpy.props.BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decorators",
        name="Keep Decorators",
    )

    prune_scenario_all_lightmaps: bpy.props.BoolProperty(
        options=set(),
        description="Loads the scenario without lightmaps",
        name="Prune Lightmaps",
    )

    prune_all_materials_use_gray_shader: bpy.props.BoolProperty(
        options=set(),
        description="Replaces all shaders in the scene with a gray shader, allowing designers to load larger zone sets (the game looks gray, but without artifacts)",
        name="Use Gray Shader",
    )

    prune_all_materials_use_default_textures: bpy.props.BoolProperty(
        options=set(),
        description="Replaces all material textures in the scene with the material shader's default, allowing designers to load larger zone sets",
        name="Use Default Textures",
    )

    prune_all_materials_use_default_textures_fx_textures: bpy.props.BoolProperty(
        options=set(),
        description="Loads only material textures related to FX, all other material textures will show up as the shader's default",
        name="Include FX materials",
    )

    prune_all_material_effects: bpy.props.BoolProperty(
        options=set(),
        description="Loads the scenario without material effects",
        name="Prune Material Effects",
    )

    prune_all_dialog_sounds: bpy.props.BoolProperty(
        options=set(),
        description="Removes all dialog sounds referenced in the globals tag",
        name="Prune Material Effects",
    )

    prune_all_error_geometry: bpy.props.BoolProperty(
        options=set(),
        description="If you're working on geometry and don't need to see the (40+ MB of) data that gets loaded in tags then you should enable this command",
        name="Prune Error Geometry",
    )

    prune_facial_animations: bpy.props.BoolProperty(
        options=set(),
        description="Skips loading the PCA data for facial animations",
        name="Prune Facial Animations",
    )

    prune_first_person_animations: bpy.props.BoolProperty(
        options=set(),
        description="Skips laoding the first-person animations",
        name="Prune First Person Animations",
    )

    prune_low_quality_animations: bpy.props.BoolProperty(
        options=set(),
        description="Use low-quality animations if they are available",
        name="Use Low Quality Animations",
    )

    prune_use_imposters: bpy.props.BoolProperty(
        options=set(),
        description="Uses imposters if they available",
        name="Use Imposters only",
    )

    prune_cinematic_effects: bpy.props.BoolProperty(
        options=set(),
        description="Skips loading and player cinematic effects",
        name="Prune Cinematic Effects",
    )
    # REACH Only prunes
    prune_scenario_force_solo_mode: bpy.props.BoolProperty(
        options=set(),
        description="Forces the map to be loaded in solo mode even if it is a multiplayer map. The game will look for a solo map spawn point",
        name="Force Solo Mode",
    )

    prune_scenario_for_environment_finishing: bpy.props.BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decals, scenery, crates and decorators",
        name="Prune Finishing",
    )

    prune_scenario_force_single_bsp_zone_set: bpy.props.BoolProperty(
        options=set(),
        description="Removes all but the first BSP from the initial zone set. Ensures that the initial zone set will not crash on load due to low memory",
        name="Prune Zone Sets",
    )

    prune_scenario_force_single_bsp_zones: bpy.props.BoolProperty(
        options=set(),
        description="Add single bsp zone sets (for each BSP) to the debug menu",
        name="Single BSP zone sets",
    )

    prune_keep_scripts: bpy.props.BoolProperty(
        options=set(),
        description="Attempts to run scripts while pruning",
        name="Keep Scripts",
    )
    # Other
    enable_firefight: bpy.props.BoolProperty(options=set(), name="Enable Spartan Ops")

    firefight_mission: bpy.props.StringProperty(
        options=set(),
        name="Spartan Ops Mission",
        description="Set the string that matches the spartan ops mission that should be loaded",
        default="",
    )

    insertion_point_index: bpy.props.IntProperty(
        options=set(),
        name="Insertion Point",
        default=-1,
        min=-1,
        soft_max=4,
    )

    initial_zone_set: bpy.props.StringProperty(
        options=set(),
        name="Zone Set",
        description="Opens the scenario to the zone set specified. This should match a zone set defined in the .scenario tag",
    )

    initial_bsp: bpy.props.StringProperty(
        options=set(),
        name="BSP",
        description="Opens the scenario to the bsp specified. This should match a bsp name in your blender scene",
    )

    custom_functions: bpy.props.StringProperty(
        options=set(),
        name="Custom",
        description="Name of Blender blender text editor file to get custom init lines from. If no such text exists, instead looks in the root editing kit for an init.txt with this name. If this doesn't exist, then the actual text is used instead",
        default="",
    )
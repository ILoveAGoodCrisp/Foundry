bl_info = {
    "name": "Halo Tag Export",
    "author": "Crisp",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "File > Export",
    "category": "Export",
    "description": "Asset Exporter and Toolset for Halo Reach, Halo 4, and Halo 2 Anniversary Multiplayer",
}

from pathlib import Path
import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from os.path import exists as file_exists
from os import path
import time
import os
import ctypes
import traceback
import logging

from bpy_extras.io_utils import ExportHelper

from ..tools.refresh_cinematic_controls import add_controls_to_debug_menu

from ..tools.asset_types import AssetType

from ..tools.camera_track_sync import export_current_action_as_camera_track

from .process import ExportScene

from ..icons import get_icon_id, get_icon_id_in_directory
from ..ui.bar import NWO_MT_ProjectChooserMenuDisallowNew

from ..utils import (
    check_path,
    get_data_path,
    get_asset_info,
    get_prefs,
    get_project_path,
    get_tool_path,
    human_time,
    is_corinth,
    print_error,
    print_warning,
    update_debug_menu,
    validate_ek,
)
from .. import managed_blam
from .. import utils

# export keywords
process = {}

# lightmapper_run_once = False
sidecar_read = False

sidecar_path = ""

def menu_func_export(self, context):
    self.layout.operator(NWO_ExportScene.bl_idname, text="Halo Foundry Export")

class NWO_ExportScene(Operator, ExportHelper):
    bl_idname = "nwo.export_scene"
    bl_label = "Export Asset"
    bl_options = {"PRESET", "UNDO"}
    bl_description = "Exports Tags for use with a Reach/H4/H2AMP Halo Editing Kit"
    
    filename_ext = ".asset"

    filter_glob: StringProperty(
        default="*.asset",
        options={"HIDDEN"},
        maxlen=1024,
    )
    
    for_cache_build: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})
    
    @classmethod
    def poll(cls, context):
        return not validate_ek() and not context.scene.nwo.storage_only and context.scene.nwo.asset_type != 'resource'
    
    @classmethod
    def description(cls, context, properties):
        d = validate_ek()
        if d is not None:
            return "Export Unavaliable: " + d
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # SETUP #
        scene = bpy.context.scene
        data_dir = get_data_path()
        self.game_path_not_set = False

        if Path(get_tool_path()).with_suffix(".exe").exists():
            # get sidecar path from users EK data path + internal path
            sidecar_filepath = str(Path(data_dir, scene.nwo.sidecar_path))
            if not sidecar_filepath.endswith(".sidecar.xml"):
                sidecar_filepath = ""
            if sidecar_filepath and file_exists(sidecar_filepath):
                self.filepath = utils.dot_partition(sidecar_filepath)
            elif bpy.data.is_saved:
                try:
                    filepath_list = bpy.data.filepath.split(os.sep)
                    del filepath_list[-1]
                    if filepath_list[-1] == "work" and filepath_list[-2] in (
                        "models",
                        "animations",
                    ):
                        del filepath_list[-1]
                        del filepath_list[-1]
                    elif filepath_list[-1] in ("models", "animations"):
                        del filepath_list[-1]
                    drive = filepath_list[0]
                    del filepath_list[0]
                    self.filepath = path.join(drive, path.sep, *filepath_list, "halo")
                except:
                    if data_dir != "":
                        self.filepath = path.join(get_data_path(), "halo")

            elif data_dir != "":
                self.filepath = path.join(get_data_path(), "halo")

        else:
            self.game_path_not_set = True
            
    def export_invalid(self):
        if (
            not check_path(self.filepath)
            or not file_exists(f"{get_tool_path()}.exe")
            or self.asset_path.lower() + os.sep == get_data_path().lower()
        ):  # check the user is saving the file to a location in their editing kit data directory AND tool exists. AND prevent exports to root data dir
            game = bpy.context.scene.nwo.scene_project
            if get_project_path() is None or get_project_path() == "":
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"No {game} Editing Kit path found. Please check your {game} editing kit path in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset] and ensure this points to your {game} editing kit directory.",
                    f"Invalid {game} Project Path",
                    0,
                )
            elif not file_exists(f"{get_tool_path()}.exe"):
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"{game} Tool not found. Could not find {game} tool or tool_fast. Please check your {game} editing kit path in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset] and ensure this points to your {game} editing kit directory.",
                    f"Invalid {game} Tool Path",
                    0,
                )
            elif self.asset_path.lower() + path.sep == get_data_path().lower():
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f'You cannot export directly to your root {game} editing kit data directory. Please create a valid asset directory such as "data\my_asset" and direct your export to this folder',
                    f"Root Data Folder Export",
                    0,
                )
            else:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"The selected export folder is outside of your {game} editing kit data directory, please ensure you are exporting to a directory within your {game} editing kit data folder.",
                    f"Invalid {game} Export Path",
                    0,
                )

            return True

        return False

    def execute(self, context):
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        scene_nwo = scene.nwo
        
        scene_nwo.export_in_progress = True
        if self.game_path_not_set:
            self.report(
                {"WARNING"},
                f"Unable to export. Your {context.scene.nwo.scene_project} path must be set in preferences",
            )
            return {"CANCELLED"}
        
        global process
        process = self.as_keywords()

        start = time.perf_counter()
        # get the asset name and path to the asset folder
        self.asset_path, self.asset_name = get_asset_info(self.filepath)

        sidecar_path_full = str(Path(self.asset_path, self.asset_name).with_suffix(".sidecar.xml"))
        global sidecar_path
        sidecar_path = str(Path(sidecar_path_full).relative_to(get_data_path()))
        
        scene_nwo.sidecar_path = sidecar_path
        
        # Check that we can export
        if self.export_invalid():
            scene_nwo_export.export_quick = False
            self.report({"WARNING"}, "Export aborted")
            return {"CANCELLED"}
        
        if not self.for_cache_build:
            # toggle the console
            os.system("cls")
            if context.scene.nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                scene_nwo_export.show_output = False

            export_title = f"►►► {scene_nwo.asset_type.replace('_', ' ').upper()} EXPORT ◄◄◄"

            print(export_title)

            print("\nIf you did not intend to export, hold CTRL+C")

        self.failed = False
        self.fail_explanation = ""
        
        if scene_nwo.asset_type == 'camera_track_set':
            scene_nwo.export_gr2s = False
            
        try:
            try:
                process_results = None
                export_asset(context, sidecar_path_full, sidecar_path, self.asset_name, self.asset_path, scene_nwo, scene_nwo_export, is_corinth(context))
            
            except Exception as e:
                if isinstance(e, RuntimeError):
                    # logging.error(traceback.format_exc())
                    self.fail_explanation = traceback.format_exception_only(e)[0][14:]
                else:
                    print_error("\n\nException hit. Please include in report\n")
                    logging.error(traceback.format_exc())
                    self.failed = True

            # validate that a sidecar file exists
            if not Path(sidecar_path_full).exists:
                context.scene.nwo.sidecar_path = ""

            end = time.perf_counter()

            if self.failed:
                print_warning(
                    "\ Export crashed and burned. Please let the developer know: https://github.com/ILoveAGoodCrisp/Foundry/issues\n"
                )
                print_error(
                    "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                )
                
            elif self.fail_explanation:
                    print_warning("\n\nEXPORT CANCELLED\n")
                    print_error(self.fail_explanation)

            elif process_results and process_results.sidecar_import_failed:
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print_error("FAILED TO CREATE TAGS\n")
                if process_results.sidecar_import_error:
                    # print("Explanation of error:")
                    print(process_results.sidecar_import_error)

                print("\nFor further details, please review the Tool output above")

                print(
                    "-----------------------------------------------------------------------\n"
                )
            elif process_results and process_results.lightmap_failed:
                
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print_error(process_results.lightmap_message)

                print(
                    "-----------------------------------------------------------------------\n"
                )
            else:
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print(f"Export Completed in {human_time(end - start, True)}")

                print(
                    "-----------------------------------------------------------------------\n"
                )
                if get_prefs().debug_menu_on_export:
                    if scene_nwo.asset_type == 'model':
                        update_debug_menu(self.asset_path, self.asset_name)
                    elif scene_nwo.asset_type == 'cinematic':
                        asset_path = utils.get_asset_path()
                        asset_name = Path(asset_path).name
                        scene_index = 0
                        shot_index = utils.current_shot_index(context)
                        add_controls_to_debug_menu(context, utils.is_corinth(context), Path(asset_path, asset_name).with_suffix(".cinematic"), scene_index, shot_index)

        except KeyboardInterrupt:
            print_warning("\n\nEXPORT CANCELLED BY USER")

        context.scene.nwo.export_in_progress = False
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        # PROJECT
        row = layout.row()
        if managed_blam.mb_active:
            row.enabled = False
        projects = get_prefs().projects
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        scene_nwo = scene.nwo
        scenario = scene_nwo.asset_type == "scenario"
        prefab = scene_nwo.asset_type == "prefab"
        for p in projects:
            if p.name == scene_nwo.scene_project:
                thumbnail = os.path.join(p.project_path, p.image_path)
                if os.path.exists(thumbnail):
                    icon_id = get_icon_id_in_directory(thumbnail)
                elif p.remote_server_name == "bngtoolsql":
                    icon_id = get_icon_id("halo_reach")
                elif p.remote_server_name == "metawins":
                    icon_id = get_icon_id("halo_4")
                elif p.remote_server_name == "episql.343i.selfhost.corp.microsoft.com":
                    icon_id = get_icon_id("halo_2amp")
                else:
                    icon_id = get_icon_id("tag_test")
                row.menu(NWO_MT_ProjectChooserMenuDisallowNew.bl_idname, text=scene_nwo.scene_project, icon_value=icon_id)
                break
        else:
            if projects:
                row.menu(NWO_MT_ProjectChooserMenuDisallowNew.bl_idname, text="Choose Project", icon_value=get_icon_id("tag_test"))
        # SETTINGS #
        box = layout.box()
        box.label(text="Settings")

        h4 = is_corinth(context)

        col = box.column()
        row = col.row()
        col.prop(scene_nwo, "asset_type", text="Asset Type")
        col.prop(scene_nwo_export, "export_quick", text="Quick Export")
        col.prop(scene_nwo_export, "show_output", text="Toggle Output")
        col.separator()
        col.use_property_split = False
        if not scene_nwo.is_child_asset:
            col.prop(scene_nwo_export, "export_mode", text="")
            col.prop(scene_nwo_export, "event_level", text="")
        if scene_nwo.asset_type == 'camera_track_set':
            return
        scenario = scene_nwo.asset_type == "scenario"
        render = utils.poll_ui(("model", "sky"))
        scenario_lightmap = (h4 and render) or scenario
        if render or scenario:
            if scenario:
                lighting_name = "Light Scenario"
            elif scenario_lightmap:
                lighting_name = "Light Model"
            else:
                lighting_name = "Light Model (PRT)"
            
            if scenario_lightmap:
                col.prop(scene_nwo_export, "update_lighting_info")
            col.prop(scene_nwo_export, "lightmap_structure", text=lighting_name)
            if scene_nwo_export.lightmap_structure and scenario_lightmap:
                if scene_nwo.asset_type == "scenario":
                    if h4:
                        col.prop(scene_nwo_export, "lightmap_quality_h4")
                    else:
                        col.prop(scene_nwo_export, "lightmap_quality")
                    if not scene_nwo_export.lightmap_all_bsps:
                        col.prop(scene_nwo_export, "lightmap_specific_bsp")
                    col.prop(scene_nwo_export, "lightmap_all_bsps")
                    if not h4:
                        col.prop(scene_nwo_export, "lightmap_threads")
                        
        box = layout.box()
        box.label(text="Scope")
        col = box.column()
                        
        if scene_nwo.asset_type == "model":
            col.prop(scene_nwo_export, "export_render", text="Render")
            col.prop(scene_nwo_export, "export_collision", text="Collision")
            col.prop(scene_nwo_export, "export_physics", text="Physics")
            col.prop(scene_nwo_export, "export_markers")
            col.prop(scene_nwo_export, "export_skeleton")
        elif scene_nwo.asset_type == "animation":
            col.prop(scene_nwo_export, "export_skeleton")
        elif scene_nwo.asset_type == "scenario":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_structure")
            col.prop(scene_nwo_export, "export_design", text="Design")
        elif scene_nwo.asset_type != "prefab":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")

        col = layout.column()
        col.use_property_split = False
        col.separator()
        if scene_nwo.asset_type == "scenario":
            col.prop(scene_nwo_export, "export_all_bsps", expand=True, text=" ")
            col.separator()
        col.prop(scene_nwo_export, "export_all_perms", expand=True, text=" ")
        col.separator()
        if scene_nwo.asset_type in {'animation', 'model'}:
            col.prop(scene_nwo_export, "export_animations", expand=True)
            
        box = layout.box()
        box.label(text="Coordinate System")
        col = box.column()
            
        col.prop(scene_nwo, 'scale', text='Scale')
        col.prop(scene_nwo, "forward_direction", text="Scene Forward")
        col.prop(scene_nwo, "maintain_marker_axis")
        col.prop(scene_nwo_export, "granny_mirror")
        
        box = layout.box()
        box.label(text="Triangulation")
        col = box.column()
        
        col.prop(scene_nwo_export, 'triangulate_quad_method', text="Quad Method")
        col.prop(scene_nwo_export, 'triangulate_ngon_method', text="N-gon Method")
        
        box = layout.box()
        box.label(text="Import Flags")
        col = box.column()
        
        flow = col.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(scene_nwo_export, "force_imposter_policy_never")
        col.prop(scene_nwo_export, "import_force", text="Force full export")
        if h4:
            if scenario or prefab:
                if scenario:
                    col.prop(
                        scene_nwo_export,
                        "import_seam_debug",
                        text="Show more seam debugging info",
                    )
                    col.prop(
                        scene_nwo_export,
                        "import_skip_instances",
                        text="Skip importing instances",
                    )
                col.prop(
                    scene_nwo_export,
                    "import_meta_only",
                    text="Only import structure_meta tag",
                )
                col.prop(
                    scene_nwo_export,
                    "import_lighting",
                    text="Only reimport lighting information",
                )
                col.prop(
                    scene_nwo_export,
                    "import_disable_hulls",
                    text="Skip instance convex hull decomp",
                )
                col.prop(
                    scene_nwo_export,
                    "import_disable_collision",
                    text="Don't generate complex collision",
                )
            else:
                col.prop(
                    scene_nwo_export, "import_no_pca", text="Skip PCA calculations"
                )
                col.prop(
                    scene_nwo_export,
                    "import_force_animations",
                    text="Force import error animations",
                )
        else:
            # col.prop(scene_nwo_export, "import_verbose", text="Verbose Output")
            col.prop(
                scene_nwo_export,
                "import_suppress_errors",
                text="Don't write errors to VRML",
            )
            if scenario:
                col.prop(
                    scene_nwo_export,
                    "import_seam_debug",
                    text="Show more seam debugging info",
                )
                col.prop(
                    scene_nwo_export,
                    "import_skip_instances",
                    text="Skip importing instances",
                )
                col.prop(
                    scene_nwo_export,
                    "import_decompose_instances",
                    text="Run convex physics decomposition",
                )
            # else:
            #     col.prop(scene_nwo_export, "import_draft", text="Skip PRT generation")
                
        flow = col.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        
        if utils.has_gr2_viewer():
            box = layout.box()
            box.label(text="GR2 Debug Settings")
            col = box.column()
            col.prop(scene_nwo_export, 'granny_open')
            col.prop(scene_nwo_export, 'granny_textures')
            if utils.poll_ui(('animation',)):
                col.prop(scene_nwo_export, 'granny_animations_mesh')

def register():
    bpy.utils.register_class(NWO_ExportScene)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(NWO_ExportScene)

def export_asset(context, sidecar_path_full, sidecar_path, asset_name, asset_path, scene_settings, export_settings, corinth):
    is_child_asset = scene_settings.is_child_asset
    asset_type = scene_settings.asset_type
    if asset_type == 'camera_track_set':
        return export_current_action_as_camera_track(context,asset_path) # Return early if this is a camera track export
    export_scene = ExportScene(context, sidecar_path_full, sidecar_path, asset_type, asset_name, asset_path, corinth, export_settings, scene_settings)
    try:
        if is_child_asset or export_settings.export_mode in {'FULL', 'GRANNY'}:
            print("\n\nProcessing Scene")
            print("-----------------------------------------------------------------------\n")
            export_scene.ready_scene()
            export_scene.get_initial_export_objects()
            export_scene.map_halo_properties()
            export_scene.set_template_node_order()
            export_scene.create_virtual_tree()
            if export_scene.asset_type == AssetType.CINEMATIC:
                export_scene.sample_shots()
            else:
                export_scene.sample_animations()
            export_scene.report_warnings()
            export_scene.export_files()
            export_scene.write_sidecar()
            
        if not is_child_asset and export_settings.export_mode in {'FULL', 'TAGS'}:
            if export_settings.export_mode == 'TAGS' and (export_scene.limit_perms_to_selection or export_scene.limit_bsps_to_selection):
                # Need to figure out what perms/bsps are selected in this case
                print("\n\nQuick Scene Process")
                print("-----------------------------------------------------------------------\n")
                export_scene.ready_scene()
                export_scene.get_initial_export_objects()
                export_scene.map_halo_properties()
                
            export_scene.preprocess_tags()
            if not (export_scene.asset_type == AssetType.CINEMATIC and (export_settings.cinematic_scope == 'CAMERA' or not export_scene.cinematic_actors)):
                # No need to invoke tool if we're only writing cinematic frame data
                print("\n\nWriting Tags")
                print("-----------------------------------------------------------------------\n")
                export_scene.invoke_tool_import()
                
            export_scene.postprocess_tags()
            export_scene.lightmap()
    finally:
        export_scene.restore_scene()
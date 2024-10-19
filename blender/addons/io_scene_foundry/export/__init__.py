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

# export keywords
process = {}

# lightmapper_run_once = False
sidecar_read = False

sidecar_path = ""

def toggle_output():
    bpy.context.scene.nwo_export.show_output = False

def menu_func_export(self, context):
    self.layout.operator(NWO_ExportScene.bl_idname, text="Halo Foundry Export")

class NWO_ExportScene(Operator):
    bl_idname = "export_scene.nwo"
    bl_label = "Export Asset"
    bl_options = {"PRESET", "UNDO"}
    bl_description = "Exports Tags for use with a Reach/H4/H2AMP Halo Editing Kit"
    
    filename_ext = ".xml"

    filter_glob: StringProperty(
        default="*.xml",
        options={"HIDDEN"},
        maxlen=1024,
    )
    
    @classmethod
    def poll(cls, context):
        return not validate_ek() and not context.scene.nwo.storage_only and context.scene.nwo.is_valid_asset and context.scene.nwo.asset_type != 'resource'
    
    @classmethod
    def description(cls, context, properties):
        d = validate_ek()
        if d is not None:
            return "Export Unavaliable: " + d

    def __init__(self):
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
                self.filepath = sidecar_filepath
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
                    self.filepath = path.join(
                        drive, path.sep, *filepath_list, "halo_export"
                    )
                except:
                    if data_dir != "":
                        self.filepath = path.join(get_data_path(), "halo_export")

            elif data_dir != "":
                self.filepath = path.join(get_data_path(), "halo_export")

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
        
        # toggle the console
        os.system("cls")
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            bpy.app.timers.register(toggle_output)

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
                    self.fail_explanation = traceback.format_exc()
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
                    "\ Export crashed and burned. Please let the developer know: https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit/issues\n"
                )
                print_error(
                    "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                )
                
            elif self.fail_explanation:
                    print_warning("\nEXPORT CANCELLED")
                    print(self.fail_explanation)

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
                
                if scene_nwo.asset_type == 'model' and get_prefs().debug_menu_on_export:
                    update_debug_menu(self.asset_path, self.asset_name)

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
        scenario = scene_nwo.asset_type == "scenario"

        col = box.column()
        row = col.row()
        col.prop(scene_nwo, "asset_type", text="Asset Type")
        col.prop(scene_nwo_export, "show_output", text="Toggle Output")
        # NWO SETTINGS #
        box = layout.box()
        box.label(text="Export Scope")
        col = box.column()
        col.prop(scene_nwo_export, "export_gr2s", text="Export Tags")
        if scene_nwo.asset_type == 'camera_track_set':
            return
        if scene_nwo_export.export_gr2s and scene_nwo.asset_type in ('model', 'scenario', 'prefab', 'animation'):
            col.separator()
            sub = col.column(heading="Export")
            # sub.prop(self, "export_hidden")
            if scene_nwo.asset_type == "model":
                sub.prop(scene_nwo_export, "export_render")
                sub.prop(scene_nwo_export, "export_collision")
                sub.prop(scene_nwo_export, "export_physics")
                sub.prop(scene_nwo_export, "export_markers")
                sub.prop(scene_nwo_export, "export_skeleton")
                sub.prop(scene_nwo_export, "export_animations", expand=True)
            elif scene_nwo.asset_type == "animation":
                sub.prop(scene_nwo_export, "export_skeleton")
                sub.prop(scene_nwo_export, "export_animations", expand=True)
            elif scene_nwo.asset_type == "scenario":
                sub.prop(scene_nwo_export, "export_structure")
                sub.prop(scene_nwo_export, "export_design")
                sub.prop(scene_nwo_export, "export_all_bsps", expand=True)
            elif scene_nwo.asset_type != "prefab":
                sub.prop(scene_nwo_export, "export_render")
            if scene_nwo.asset_type in (
                "model",
                "sky",
            ):
                sub.prop(scene_nwo_export, "export_all_perms", expand=True, text='Permutations')
            elif scene_nwo.asset_type in ("scenario", "prefab"):
                sub.prop(scene_nwo_export, "export_all_perms", expand=True, text='Layers')
        # SIDECAR SETTINGS #
        if scene_nwo.asset_type == "model" and scene_nwo_export.export_gr2s:
            box = layout.box()
            box.label(text="Model Settings")
            col = box.column()
            # col.prop(self, "export_sidecar_xml")
            # if self.export_sidecar_xml:
            sub = box.column(heading="Output Tags")
            if scene_nwo.asset_type == "model":
                sub.prop(scene_nwo, "output_biped")
                sub.prop(scene_nwo, "output_crate")
                sub.prop(scene_nwo, "output_creature")
                sub.prop(scene_nwo, "output_device_control")
                if h4:
                    sub.prop(scene_nwo, "output_device_dispenser")
                sub.prop(scene_nwo, "output_device_machine")
                sub.prop(scene_nwo, "output_device_terminal")
                sub.prop(scene_nwo, "output_effect_scenery")
                sub.prop(scene_nwo, "output_equipment")
                sub.prop(scene_nwo, "output_giant")
                sub.prop(scene_nwo, "output_scenery")
                sub.prop(scene_nwo, "output_vehicle")
                sub.prop(scene_nwo, "output_weapon")

        # IMPORT SETTINGS #
        if scene_nwo_export.export_gr2s:
            box = layout.box()
            sub = box.column(heading="Export Flags")
            if h4:
                sub.prop(scene_nwo_export, "import_force", text="Force full export")
                if scenario:
                    sub.prop(
                        scene_nwo_export, "import_seam_debug", text="Show more seam debugging info"
                    )
                    sub.prop(
                        scene_nwo_export, "import_skip_instances", text="Skip importing instances"
                    )
                    sub.prop(
                        scene_nwo_export, "import_meta_only", text="Only import structure_meta tag"
                    )
                    sub.prop(
                        scene_nwo_export,
                        "import_lighting",
                        text="Only reimport lighting information",
                    )
                    sub.prop(
                        scene_nwo_export,
                        "import_disable_hulls",
                        text="Skip instance convex hull decomp",
                    )
                    sub.prop(
                        scene_nwo_export,
                        "import_disable_collision",
                        text="Don't generate complex collision",
                    )
                else:
                    sub.prop(scene_nwo_export, "import_no_pca", text="Skip PCA calculations")
                    sub.prop(
                        scene_nwo_export,
                        "import_force_animations",
                        text="Force import error animations",
                    )
            else:
                sub.prop(scene_nwo_export, "import_force", text="Force full export")
                # sub.prop(self, "import_verbose", text="Verbose Output")
                sub.prop(
                    scene_nwo_export, "import_suppress_errors", text="Don't write errors to VRML"
                )
                if scenario:
                    sub.prop(
                        scene_nwo_export, "import_seam_debug", text="Show more seam debugging info"
                    )
                    sub.prop(
                        scene_nwo_export, "import_skip_instances", text="Skip importing instances"
                    )
                    sub.prop(
                        scene_nwo_export,
                        "import_decompose_instances",
                        text="Run convex physics decomposition",
                    )
                else:
                    sub.prop(scene_nwo_export, "import_draft", text="Skip PRT generation")

        # LIGHTMAP SETTINGS #
        render = scene_nwo.asset_type in ("model", "sky")
        if (h4 and render) or scenario:
            box = layout.box()
            box.label(text="Lightmap Settings")
            col = box.column()
            if scenario:
                lighting_name = "Light Scenario"
            else:
                lighting_name = "Light Model"

            col.prop(scene_nwo_export, "lightmap_structure", text=lighting_name)
            if scene_nwo_export.lightmap_structure:
                if scenario:
                    if h4:
                        col.prop(scene_nwo_export, "lightmap_quality_h4")
                    else:
                        col.prop(scene_nwo_export, "lightmap_quality")
                    if not scene_nwo_export.lightmap_all_bsps:
                        col.prop(scene_nwo_export, "lightmap_specific_bsp")
                    col.prop(scene_nwo_export, "lightmap_all_bsps")
                    if not h4:
                        col.prop(scene_nwo_export, "lightmap_threads")

def register():
    bpy.utils.register_class(NWO_ExportScene)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(NWO_ExportScene)

def export_asset(context, sidecar_path_full, sidecar_path, asset_name, asset_path, scene_settings, export_settings, corinth):
    asset_type = scene_settings.asset_type
    export_scene = ExportScene(context, sidecar_path_full, sidecar_path, asset_type, asset_name, asset_path, corinth, export_settings, scene_settings)
    try:
        if export_settings.export_mode in {'FULL', 'GRANNY'}:
            print("\n\nProcessing Scene")
            print("-----------------------------------------------------------------------\n")
            export_scene.ready_scene()
            export_scene.get_initial_export_objects()
            export_scene.map_halo_properties()
            export_scene.set_template_node_order()
            export_scene.create_virtual_tree()
            export_scene.sample_animations()
            export_scene.report_warnings()
            export_scene.export_files()
            export_scene.write_sidecar()
            
        if export_settings.export_mode in {'FULL', 'TAGS'}:
            export_scene.preprocess_tags()
            print("\n\nWriting Tags")
            print("-----------------------------------------------------------------------\n")
            export_scene.invoke_tool_import()
            export_scene.postprocess_tags()
            export_scene.lightmap()
    finally:
        export_scene.restore_scene()
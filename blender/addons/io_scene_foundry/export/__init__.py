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


####################
bl_info = {
    "name": "Halo Tag Export",
    "author": "Crisp",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "File > Export",
    "category": "Export",
    "description": "Asset Exporter and Toolset for Halo Reach, Halo 4, and Halo 2 Anniversary Multiplayer",
}

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty
from bpy.types import Operator
from os.path import exists as file_exists
from os import path
import time
import os
import ctypes
import traceback
import logging
from io_scene_foundry.icons import get_icon_id, get_icon_id_in_directory
from io_scene_foundry.managed_blam.camera_track import CameraTrackTag
from io_scene_foundry.tools import NWO_ProjectChooserMenuDisallowNew

from .prepare_scene import PrepareScene
from .process_scene import ProcessScene

from io_scene_foundry.utils.nwo_utils import (
    MutePrints,
    check_path,
    get_camera_track_camera,
    get_data_path,
    get_asset_info,
    get_prefs,
    get_project_path,
    get_tool_path,
    human_time,
    is_corinth,
    managed_blam_active,
    print_error,
    print_warning,
    update_debug_menu,
    validate_ek,
)

# export keywords
export_settings = {}

# lightmapper_run_once = False
sidecar_read = False

sidecar_path = ""

def call_export():
    bpy.ops.nwo.export(**export_settings)

def toggle_output():
    bpy.context.scene.nwo_export.show_output = False
    
def save_sidecar_path():
    bpy.context.scene.nwo_halo_launcher.sidecar_path = sidecar_path

class NWO_Export_Scene(Operator, ExportHelper):
    bl_idname = "export_scene.nwo"
    bl_label = "Export Asset"
    bl_options = {"PRESET", "UNDO"}
    bl_description = "Exports Tags for use with a Reach/H4/H2AMP Halo Editing Kit"

    @classmethod
    def poll(cls, context):
        return not validate_ek() and not context.scene.nwo.storage_only
    
    @classmethod
    def description(cls, context, properties):
        d = validate_ek()
        if d is not None:
            return "Export Unavaliable: " + d

    filename_ext = ".xml"

    filter_glob: StringProperty(
        default="*.xml",
        options={"HIDDEN"},
        maxlen=1024,
    )

    def __init__(self):
        # SETUP #
        scene = bpy.context.scene
        data_dir = get_data_path()
        self.game_path_not_set = False

        if os.path.exists(get_tool_path() + ".exe"):
            # get sidecar path from users EK data path + internal path
            sidecar_filepath = path.join(
                data_dir, scene.nwo_halo_launcher.sidecar_path
            )
            if not sidecar_filepath.endswith(".sidecar.xml"):
                sidecar_filepath = ""
            if sidecar_filepath and file_exists(sidecar_filepath):
                # export_settings = ExportSettingsFromSidecar(sidecar_filepath)
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

    def execute(self, context):
        context.scene.nwo.export_in_progress = True
        if self.game_path_not_set:
            self.report(
                {"WARNING"},
                f"Unable to export. Your {context.scene.nwo.scene_project} path must be set in preferences",
            )
            return {"CANCELLED"}

        # Save the scene
        # bpy.ops.wm.save_mainfile()
        # save settings to global
        global export_settings
        export_settings = self.as_keywords()
        bpy.ops.ed.undo_push()
        # start the actual export operator
        bpy.app.timers.register(call_export)

        return {'FINISHED'}

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

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        # PROJECT
        row = layout.row()
        if managed_blam_active():
            row.enabled = False
        projects = get_prefs().projects
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        scene_nwo = scene.nwo
        for p in projects:
            if p.name == scene_nwo.scene_project:
                thumbnail = os.path.join(p.project_path, p.project_image_path)
                if os.path.exists(thumbnail):
                    icon_id = get_icon_id_in_directory(thumbnail)
                elif p.project_remote_server_name == "bngtoolsql":
                    icon_id = get_icon_id("halo_reach")
                elif p.project_remote_server_name == "metawins":
                    icon_id = get_icon_id("halo_4")
                elif p.project_remote_server_name == "episql.343i.selfhost.corp.microsoft.com":
                    icon_id = get_icon_id("halo_2amp")
                else:
                    icon_id = get_icon_id("tag_test")
                row.menu(NWO_ProjectChooserMenuDisallowNew.bl_idname, text=scene_nwo.scene_project, icon_value=icon_id)
                break
        else:
            if projects:
                row.menu(NWO_ProjectChooserMenuDisallowNew.bl_idname, text="Choose Project", icon_value=get_icon_id("tag_test"))
        # SETTINGS #
        box = layout.box()
        box.label(text="Settings")

        h4 = is_corinth(context)
        scenario = scene_nwo.asset_type == "SCENARIO"

        col = box.column()
        row = col.row()
        col.prop(scene_nwo, "asset_type", text="Asset Type")
        col.prop(scene_nwo_export, "show_output", text="Toggle Output")
        # NWO SETTINGS #
        box = layout.box()
        box.label(text="Export Scope")
        col = box.column()
        col.prop(scene_nwo_export, "export_gr2_files", text="Export Tags")
        if scene_nwo.asset_type == 'camera_track_set':
            return
        if scene_nwo_export.export_gr2_files and scene_nwo.asset_type in ('MODEL', 'SCENARIO', 'PREFAB', 'FP ANIMATION'):
            col.separator()
            sub = col.column(heading="Export")
            # sub.prop(self, "export_hidden")
            if scene_nwo.asset_type == "MODEL":
                sub.prop(scene_nwo_export, "export_render")
                sub.prop(scene_nwo_export, "export_collision")
                sub.prop(scene_nwo_export, "export_physics")
                sub.prop(scene_nwo_export, "export_markers")
                sub.prop(scene_nwo_export, "export_skeleton")
                sub.prop(scene_nwo_export, "export_animations", expand=True)
            elif scene_nwo.asset_type == "FP ANIMATION":
                sub.prop(scene_nwo_export, "export_skeleton")
                sub.prop(scene_nwo_export, "export_animations", expand=True)
            elif scene_nwo.asset_type == "SCENARIO":
                sub.prop(scene_nwo_export, "export_structure")
                sub.prop(scene_nwo_export, "export_design")
                sub.prop(scene_nwo_export, "export_all_bsps", expand=True)
            elif scene_nwo.asset_type != "PREFAB":
                sub.prop(scene_nwo_export, "export_render")
            if scene_nwo.asset_type in (
                "MODEL",
                "SKY",
            ):
                sub.prop(scene_nwo_export, "export_all_perms", expand=True, text='Permutations')
            elif scene_nwo.asset_type in ("SCENARIO", "PREFAB"):
                sub.prop(scene_nwo_export, "export_all_perms", expand=True, text='Layers')
        # SIDECAR SETTINGS #
        if scene_nwo.asset_type == "MODEL" and scene_nwo_export.export_gr2_files:
            box = layout.box()
            box.label(text="Model Settings")
            col = box.column()
            # col.prop(self, "export_sidecar_xml")
            # if self.export_sidecar_xml:
            sub = box.column(heading="Output Tags")
            if scene_nwo.asset_type == "MODEL":
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
        if scene_nwo_export.export_gr2_files:
            box = layout.box()
            sub = box.column(heading="Export Flags")
            sub.prop(scene_nwo_export, 'triangulate', text="Triangulate")
            # if scene_nwo.asset_type in (('MODEL', 'SKY', 'FP ANIMATION')):
            #     # col.prop(scene_nwo_export, "fix_bone_rotations", text="Fix Bone Rotations") # NOTE To restore when this works correctly
            #     col.prop(scene_nwo_export, "fast_animation_export", text="Fast Animation Export")
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
        render = scene_nwo.asset_type in ("MODEL", "SKY")
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
                    # if not h4:
                    #     col.prop(self, "lightmap_region")

        # # SCENE SETTINGS #
        # box = layout.box()
        # box.label(text="Scene Settings")
        # col = box.column()
        # col.prop(self, "use_mesh_modifiers")
        # col.prop(self, "use_armature_deform_only")
        # if fbx_exporter() == "better":
        #     col.prop(self, "mesh_smooth_type_better")
        # else:
        #     col.prop(self, "mesh_smooth_type")
        # col.separator()
        # # col.prop(self, "global_scale")


def menu_func_export(self, context):
    self.layout.operator(NWO_Export_Scene.bl_idname, text="Halo Foundry Export", icon_value=get_icon_id('quick_export'))

class NWO_Export(NWO_Export_Scene):
    bl_idname = "nwo.export"
    bl_label = "Export Asset (INTERNAL ONLY)"
    bl_options = {"INTERNAL"}

    def __init__(self):
        pass

    def execute(self, context):
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        scene_nwo = scene.nwo
        start = time.perf_counter()
        # get the asset name and path to the asset folder
        self.asset_path, self.asset = get_asset_info(self.filepath)

        sidecar_path_full = os.path.join(self.asset_path, self.asset + ".sidecar.xml")
        global sidecar_path
        sidecar_path = sidecar_path_full.replace(get_data_path(), "")
        
        bpy.app.timers.register(save_sidecar_path)
        
        # Check that we can export
        if self.export_invalid():
            scene_nwo_export.export_quick = False
            self.report({"WARNING"}, "Export aborted")
            return {"CANCELLED"}
        
        # Pretty much always need ManagedBlam now, so launch it at export
        if not managed_blam_active():
            bpy.ops.managed_blam.init()
        
        # toggle the console
        os.system("cls")
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            bpy.app.timers.register(toggle_output)

        export_title = f"►►► {scene_nwo.asset_type.replace('_', ' ').upper()} EXPORT ◄◄◄"

        print(export_title)

        print("\nIf you did not intend to export, hold CTRL+C")

        self.failed = False
        self.known_fail = False
        
        if scene_nwo.asset_type == 'camera_track_set':
            scene_nwo.export_gr2_files = False
        
        try:
            try:
                nwo_scene = PrepareScene()
                nwo_scene.prepare_scene(context, self.asset, scene_nwo.asset_type, scene_nwo_export)
                if not nwo_scene.too_many_root_bones and not nwo_scene.no_export_objects:
                    export_process = ProcessScene()
                    export_process.process_scene(context, sidecar_path, sidecar_path_full, self.asset, self.asset_path, scene_nwo.asset_type, nwo_scene, scene_nwo_export, scene_nwo)
            
            except Exception as e:
                if type(e) == RuntimeError:
                    # logging.error(traceback.format_exc())
                    self.known_fail = True
                else:
                    print_error("\n\nException hit. Please include in report\n")
                    logging.error(traceback.format_exc())
                    self.failed = True

            # validate that a sidecar file exists
            if not file_exists(sidecar_path_full):
                context.scene.nwo_halo_launcher.sidecar_path = ""

            # write scene settings generated during export to temp file

            end = time.perf_counter()

            if self.failed:
                print_warning(
                    "\ Export crashed and burned. Please let the developer know: https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit/issues\n"
                )
                print_error(
                    "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                )
            
            elif self.known_fail:
                    print_warning(
                    "\nEXPORT ABORTED. Please see above for details"
                )
            elif nwo_scene.too_many_root_bones:
                print_warning('EXPORT CANCELLED')
                print("Export cancelled because the main armature has multiple deform root bones.")
            elif nwo_scene.no_export_objects:
                print_warning('EXPORT CANCELLED')
                print("Export cancelled because there are no Halo objects in the scene. Ensure at least one object is valid and has the export flag enabled")
            elif export_process.gr2_fail:
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print_error("Failed to export a GR2 File. Export cancelled\n")
                print("GR2 conversion can crash due to Tool failing to parse exported FBX data. To fix, narrow down the problem object and adjust the geometry. Splitting meshes into seperate parts can help.")

                print(
                    "-----------------------------------------------------------------------\n"
                )

            elif export_process.sidecar_import_failed:
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print_error("FAILED TO CREATE TAGS\n")
                if export_process.sidecar_import_error:
                    # print("Explanation of error:")
                    print(export_process.sidecar_import_error)

                print("\nFor further details, please review the Tool output above")

                print(
                    "-----------------------------------------------------------------------\n"
                )
            elif export_process.lightmap_failed:
                
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print_error(export_process.lightmap_message)

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
                
                if scene_nwo.asset_type == 'MODEL':
                    update_debug_menu(self.asset_path, self.asset)

        except KeyboardInterrupt:
            print_warning("\n\nEXPORT CANCELLED BY USER")

        bpy.ops.ed.undo_push()
        bpy.ops.ed.undo()
        context.scene.nwo.export_in_progress = False
        return {"FINISHED"}

def ExportSettingsFromSidecar(sidecar_filepath):
    settings = []
    import xml.etree.ElementTree as ET

    tree = ET.parse(sidecar_filepath)
    metadata = tree.getroot()
    # get the type of sidecar this is
    asset = metadata.find("Asset")
    if asset.get("Sky") == "true":
        asset_type = "sky"
    else:
        asset_type = asset.get("Type")
    # append the type to the settings list
    settings.append(asset_type)
    # if asset type is a model, we need to grab some additional info
    output_tags = []
    if settings[0] == "model":
        output_collection = asset.find("OutputTagCollection")
        for tag in output_collection.findall("OutputTag"):
            if (
                tag.get("Type") != "model"
            ):  # don't collect the model output_tag, we don't need this
                output_tags.append(tag.get("Type"))

        settings.append(output_tags)

    return settings

def register():
    bpy.utils.register_class(NWO_Export)
    bpy.utils.register_class(NWO_Export_Scene)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(NWO_Export_Scene)
    bpy.utils.unregister_class(NWO_Export)

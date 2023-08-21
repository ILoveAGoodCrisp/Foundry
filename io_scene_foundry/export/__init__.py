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


####################
bl_info = {
    "name": "Halo Tag Export",
    "author": "Crisp",
    "version": (1, 0, 0),
    "blender": (3, 6, 1),
    "location": "File > Export",
    "category": "Export",
    "description": "Asset Exporter and Toolset for Halo Reach, Halo 4, and Halo 2 Anniversary Multiplayer",
}

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator
from os.path import exists as file_exists
from os import path
import time
import os
import ctypes
import traceback
import logging

from io_scene_foundry.utils import nwo_globals

from .prepare_scene import PrepareScene
from .process_scene import ProcessScene

from io_scene_foundry.utils.nwo_utils import (
    check_path,
    bpy_enum,
    dot_partition,
    formalise_game_version,
    get_data_path,
    get_asset_info,
    get_ek_path,
    get_tags_path,
    get_tool_path,
    managed_blam_active,
    print_error,
    print_warning,
    validate_ek,
)

# lightmapper_run_once = False
sidecar_read = False

class NWO_Export_Scene(Operator, ExportHelper):
    bl_idname = "export_scene.nwo"
    bl_label = "Export Asset"
    bl_options = {"UNDO", "PRESET"}
    bl_description = "Exports Tags for use with a Reach/H4/H2AMP Halo Editing Kit"

    @classmethod
    def poll(cls, context):
        return not validate_ek(context.scene.nwo.game_version)
    
    @classmethod
    def description(cls, context, properties):
        d = validate_ek(context.scene.nwo.game_version)
        if d is not None:
            return "Export Unavaliable: " + d

    filename_ext = ".fbx"

    filter_glob: StringProperty(
        default="*.fbx",
        options={"HIDDEN"},
        maxlen=1024,
    )

    fast_animation_export : BoolProperty(
        name="Fast Animation Export",
        description="Speeds up exports by ignoring everything but the armature during animation exports. Do not use if your animation relies on helper objects",
        default=False,
    )

    game_version: EnumProperty(
        name="Game Version",
        description="The game to export this asset for",
        default="reach",
        items=[
            ("reach", "Halo Reach", "Export an asset intended for Halo Reach"),
            ("h4", "Halo 4", "Export an asset intended for Halo 4"),
            ("h2a", "Halo 2A MP", "Export an asset intended for Halo 2A MP"),
        ],
    )
    # keep_fbx: BoolProperty(
    #     name="FBX",
    #     description="Keep the source FBX file after GR2 conversion",
    #     default=True,
    # )
    # keep_json: BoolProperty(
    #     name="JSON",
    #     description="Keep the source JSON file after GR2 conversion",
    #     default=True,
    # )
    # export_sidecar_xml: BoolProperty(
    #     name="Build Sidecar",
    #     description="",
    #     default=True,
    # )
    sidecar_type: EnumProperty(
        name="Asset Type",
        description="",
        default="MODEL",
        items=[
            ("MODEL", "Model", ""),
            ("SCENARIO", "Scenario", ""),
            ("SKY", "Sky", ""),
            ("DECORATOR SET", "Decorator Set", ""),
            ("PARTICLE MODEL", "Particle Model", ""),
            ("PREFAB", "Prefab", ""),
            ("FP ANIMATION", "First Person Animation", ""),
        ],
    )
    export_animations: EnumProperty(
        name="Animations",
        description="",
        default="ALL",
        items=[
            ("ALL", "All", ""),
            ("ACTIVE", "Active", ""),
            ("NONE", "None", ""),
        ],
    )
    export_skeleton: BoolProperty(
        name="Skeleton",
        description="",
        default=True,
    )
    export_render: BoolProperty(
        name="Render Models",
        description="",
        default=True,
    )
    export_collision: BoolProperty(
        name="Collision Models",
        description="",
        default=True,
    )
    export_physics: BoolProperty(
        name="Physics Models",
        description="",
        default=True,
    )
    export_markers: BoolProperty(
        name="Markers",
        description="",
        default=True,
    )
    export_structure: BoolProperty(
        name="Structure",
        description="",
        default=True,
    )
    export_design: BoolProperty(
        name="Structure Design",
        description="",
        default=True,
    )
    export_all_bsps: EnumProperty(
        name="BSPs",
        description="Specify whether to export all BSPs, or just those selected",
        default="all",
        items=[("all", "All", ""), ("selected", "Selected", "")],
    )
    export_all_perms: EnumProperty(
        name="Permutations",
        description="Specify whether to export all permutations, or just those selected",
        default="all",
        items=[("all", "All", ""), ("selected", "Selected", "")],
    )
    output_biped: BoolProperty(
        name="Biped",
        description="",
        default=False,
    )
    output_crate: BoolProperty(
        name="Crate",
        description="",
        default=False,
    )
    output_creature: BoolProperty(
        name="Creature",
        description="",
        default=False,
    )
    output_device_control: BoolProperty(
        name="Device Control",
        description="",
        default=False,
    )
    output_device_dispenser: BoolProperty(
        name="Device Dispenser",
        description="",
        default=False,
    )
    output_device_machine: BoolProperty(
        name="Device Machine",
        description="",
        default=False,
    )
    output_device_terminal: BoolProperty(
        name="Device Terminal",
        description="",
        default=False,
    )
    output_effect_scenery: BoolProperty(
        name="Effect Scenery",
        description="",
        default=False,
    )
    output_equipment: BoolProperty(
        name="Equipment",
        description="",
        default=False,
    )
    output_giant: BoolProperty(
        name="Giant",
        description="",
        default=False,
    )
    output_scenery: BoolProperty(
        name="Scenery",
        description="",
        default=False,
    )
    output_vehicle: BoolProperty(
        name="Vehicle",
        description="",
        default=False,
    )
    output_weapon: BoolProperty(
        name="Weapon",
        description="",
        default=False,
    )
    import_to_game: BoolProperty(
        name="Create Tags",
        description="",
        default=True,
    )
    show_output: BoolProperty(name="Show Output", description="", default=True)
    import_check: BoolProperty(
        name="Check",
        description="Run the import process but produce no output files",
        default=False,
    )
    import_force: BoolProperty(
        name="Force",
        description="Force all files to import even if they haven't changed",
        default=False,
    )
    # import_verbose: BoolProperty(
    #     name="Verbose",
    #     description="Write additional import progress information to the console",
    #     default=False,
    # )
    import_draft: BoolProperty(
        name="Draft",
        description="Skip generating PRT data. Faster speed, lower quality",
        default=False,
    )
    import_seam_debug: BoolProperty(
        name="Seam Debug",
        description="Write extra seam debugging information to the console",
        default=False,
    )
    import_skip_instances: BoolProperty(
        name="Skip Instances",
        description="Skip importing all instanced geometry",
        default=False,
    )
    import_decompose_instances: BoolProperty(
        name="Decompose Instances",
        description="Run convex decomposition for instanced geometry physics (very slow)",
        default=False,
    )
    import_suppress_errors: BoolProperty(
        name="Surpress Errors",
        description="Do not write errors to vrml files",
        default=False,
    )
    import_lighting: BoolProperty(
        name="Lighting Info Only",
        description="Only build the scenario_structure_lighting_info tag",
        default=False,
    )
    import_meta_only: BoolProperty(
        name="Meta Only",
        description="Import only the structure_meta tag",
        default=False,
    )
    import_disable_hulls: BoolProperty(
        name="Disable Hulls",
        description="Disables the contruction of conves hulls for instance physics and collision",
        default=False,
    )
    import_disable_collision: BoolProperty(
        name="Disable Collision",
        description="Do not generate complex collision",
        default=False,
    )
    import_no_pca: BoolProperty(
        name="No PCA",
        description="Skips PCA calculations",
        default=False,
    )
    import_force_animations: BoolProperty(
        name="Force Animations",
        description="Force import of all animations that had errors during the last import",
        default=False,
    )
    # use_selection: BoolProperty(
    #     name="selection",
    #     description="",
    #     default=True,
    # )
    bake_anim: BoolProperty(name="", description="", default=True)
    # use_mesh_modifiers: BoolProperty(
    #     name="Apply Modifiers",
    #     description="",
    #     default=True,
    # )
    # global_scale: FloatProperty(name="Scale", description="", default=1.0)
    # use_armature_deform_only: BoolProperty(
    #     name="Deform Bones Only",
    #     description="Only export bones with the deform property ticked",
    #     default=True,
    # )

    # meshes_to_empties: BoolProperty(
    #     name="Markers as Empties",
    #     description="Export all mesh Halo markers as empties. Helps save on export / import time and file size",
    #     default=True,
    # )

    # export_hidden: BoolProperty(
    #     name="Hidden",
    #     description="Export visible objects only",
    #     default=True,
    # )
    # import_in_background: BoolProperty(
    #     name="Run In Background",
    #     description="If enabled does not pause use of blender during the import process",
    #     default=False,
    # )
    lightmap_structure: BoolProperty(
        name="Run Lightmapper",
        default=False,
    )
    lightmap_quality: EnumProperty(
        name="Quality",
        items=(
            ("DIRECT", "Direct", ""),
            ("DRAFT", "Draft", ""),
            ("LOW", "Low", ""),
            ("MEDIUM", "Medium", ""),
            ("HIGH", "High", ""),
            ("SUPER", "Super (very slow)", ""),
        ),
        default="DIRECT",
        description="Define the lightmap quality you wish to use",
    )

    def item_lightmap_quality_h4(self, context):
        items = []
        items.append(
            (
                "asset",
                "Asset",
                "The user defined lightmap settings. Opens a settings dialog",
                0,
            )
        )
        lightmapper_globals_dir = path.join(
            get_tags_path(), "globals", "lightmapper_settings"
        )
        if path.exists(lightmapper_globals_dir):
            from os import listdir

            index = 1
            for file in listdir(lightmapper_globals_dir):
                if file.endswith(".lightmapper_globals"):
                    file_no_ext = dot_partition(file)
                    items.append(bpy_enum(file_no_ext, index))
                    index += 1

        return items

    lightmap_quality_h4: EnumProperty(
        name="Quality",
        items=item_lightmap_quality_h4,
        description="Define the lightmap quality you wish to use",
    )
    lightmap_all_bsps: BoolProperty(
        name="All BSPs",
        default=True,
    )
    lightmap_specific_bsp: StringProperty(
        name="Specific BSP",
        default="",
    )

    lightmap_region: StringProperty(
        name="Region",
        description="Lightmap region to use for lightmapping",
    )

    # mesh_smooth_type_better: EnumProperty(
    #     name="Smoothing",
    #     items=(
    #         ("None", "None", "Do not generate smoothing groups"),
    #         ("Blender", "By Hard edges", ""),
    #         ("FBXSDK", "By FBX SDK", ""),
    #     ),
    #     description="Determine how smoothing groups should be generated",
    #     default="FBXSDK",
    # )
    # mesh_smooth_type: EnumProperty(
    #     name="Smoothing",
    #     items=(
    #         (
    #             "OFF",
    #             "Normals Only",
    #             "Export only normals instead of writing edge or face smoothing data",
    #         ),
    #         ("FACE", "Face", "Write face smoothing"),
    #         ("EDGE", "Edge", "Write edge smoothing"),
    #     ),
    #     description="Export smoothing information "
    #     "(prefer 'Normals Only' option if your target importer understand split normals)",
    #     default="OFF",
    # )
    quick_export: BoolProperty(
        name="",
        default=False,
    )
    export_gr2_files: BoolProperty(
        name="Export GR2 Files",
        default=True,
    )
    fix_bone_rotations: BoolProperty(
        name="Fix Bone Rotations",
        description="Sets the rotation of the following bones to match Halo conventions: pedestal, aim_pitch, aim_yaw, gun",
        default=True,
    )
    # use_tspace: BoolProperty(
    #     name="use tspace",
    #     default=False,
    # )

    def __init__(self):
        # SETUP #
        scene = bpy.context.scene

        self.game_version = scene.nwo.game_version
        self.game_path_not_set = False

        if os.path.exists(get_tool_path() + ".exe"):
            # QUICK EXPORT SETTINGS #
            scene_nwo_export = scene.nwo_export
            self.export_gr2_files = scene_nwo_export.export_gr2_files
            self.export_all_bsps = scene_nwo_export.export_all_bsps
            self.export_all_perms = scene_nwo_export.export_all_perms
            self.import_to_game = scene_nwo_export.import_to_game
            self.import_draft = scene_nwo_export.import_draft
            self.lightmap_structure = scene_nwo_export.lightmap_structure
            self.lightmap_quality_h4 = scene_nwo_export.lightmap_quality_h4
            self.lightmap_quality = scene_nwo_export.lightmap_quality
            self.lightmap_quality = scene_nwo_export.lightmap_quality
            self.lightmap_all_bsps = scene_nwo_export.lightmap_all_bsps

            self.export_animations = scene_nwo_export.export_animations
            self.export_skeleton = scene_nwo_export.export_skeleton
            self.export_render = scene_nwo_export.export_render
            self.export_collision = scene_nwo_export.export_collision
            self.export_physics = scene_nwo_export.export_physics
            self.export_markers = scene_nwo_export.export_markers
            self.export_structure = scene_nwo_export.export_structure
            self.export_design = scene_nwo_export.export_design

            self.show_output = scene_nwo_export.show_output

            self.import_force = scene_nwo_export.import_force
            # self.import_verbose = scene_nwo_export.import_verbose
            self.import_draft = scene_nwo_export.import_draft
            self.import_seam_debug = scene_nwo_export.import_seam_debug
            self.import_skip_instances = scene_nwo_export.import_skip_instances
            self.import_decompose_instances = (
                scene_nwo_export.import_decompose_instances
            )
            self.import_suppress_errors = scene_nwo_export.import_suppress_errors
            self.import_lighting = scene_nwo_export.import_lighting
            self.import_meta_only = scene_nwo_export.import_meta_only
            self.import_disable_hulls = scene_nwo_export.import_disable_hulls
            self.import_disable_collision = scene_nwo_export.import_disable_collision
            self.import_no_pca = scene_nwo_export.import_no_pca
            self.import_force_animations = scene_nwo_export.import_force_animations
            self.fast_animation_export = scene_nwo_export.fast_animation_export
            self.fix_bone_rotations = scene_nwo_export.fix_bone_rotations

            # SIDECAR SETTINGS #
            scene_nwo = bpy.context.scene.nwo

            self.sidecar_type = scene_nwo.asset_type

            self.output_biped = scene_nwo.output_biped
            self.output_crate = scene_nwo.output_crate
            self.output_creature = scene_nwo.output_creature
            self.output_device_control = scene_nwo.output_device_control
            self.output_device_dispenser = scene_nwo.output_device_dispenser
            self.output_device_machine = scene_nwo.output_device_machine
            self.output_device_terminal = scene_nwo.output_device_terminal
            self.output_effect_scenery = scene_nwo.output_effect_scenery
            self.output_equipment = scene_nwo.output_equipment
            self.output_giant = scene_nwo.output_giant
            self.output_scenery = scene_nwo.output_scenery
            self.output_vehicle = scene_nwo.output_vehicle
            self.output_weapon = scene_nwo.output_weapon
            # get sidecar path from users EK data path + internal path
            sidecar_filepath = path.join(
                get_data_path(), scene.nwo_halo_launcher.sidecar_path
            )
            if not sidecar_filepath.endswith(".sidecar.xml"):
                sidecar_filepath = ""
            if sidecar_filepath != "" and file_exists(sidecar_filepath):
                # export_settings = ExportSettingsFromSidecar(sidecar_filepath)
                self.filepath = path.join(
                    sidecar_filepath.rpartition("\\")[0], "halo_export.fbx"
                )
            elif bpy.data.is_saved:
                try:
                    filepath_list = bpy.path.abspath("//").split("\\")
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
                        drive, path.sep, *filepath_list, "halo_export.fbx"
                    )
                except:
                    if get_data_path() != "":
                        self.filepath = path.join(get_data_path(), "halo_export.fbx")

            elif get_data_path() != "":
                self.filepath = path.join(get_data_path(), "halo_export.fbx")

        else:
            self.game_path_not_set = True

    def execute(self, context):
        if self.game_path_not_set:
            self.report(
                {"WARNING"},
                f"Unable to export. Your {formalise_game_version(self.game_version)} Editing Kit path must be set in preferences",
            )
            return {"CANCELLED"}

        start = time.perf_counter()

        # get the asset name and path to the asset folder
        self.asset_path, self.asset = get_asset_info(self.filepath)

        self.set_scene_props(context)

        sidecar_path_full = os.path.join(self.asset_path, self.asset + ".sidecar.xml")

        sidecar_path = sidecar_path_full.replace(get_data_path(), "")
        
        # Check that we can export
        if self.export_invalid():
            self.report({"WARNING"}, "Export aborted")
            return {"CANCELLED"}

        # Save the scene
        # bpy.ops.wm.save_mainfile()

        os.system("cls")

        if self.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            context.scene.nwo_export.show_output = False

        export_title = "►►► HALO TAG EXPORT ◄◄◄"

        print(export_title)

        print("\nIf you did not intend to export, hold CTRL+C")

        self.failed = False

        try:
            try:
                nwo_scene = PrepareScene(
                    context,
                    self.asset,
                    self.sidecar_type,
                    self.game_version,
                    self.export_animations,
                    self.export_gr2_files,
                    self.export_all_perms,
                    self.export_all_bsps,
                    self.fix_bone_rotations,
                )

                export = ProcessScene(
                    context,
                    self.report,
                    sidecar_path,
                    sidecar_path_full,
                    self.asset,
                    self.asset_path,
                    fbx_exporter(),
                    nwo_scene,
                    self.sidecar_type,
                    self.output_biped,
                    self.output_crate,
                    self.output_creature,
                    self.output_device_control,
                    self.output_device_machine,
                    self.output_device_terminal,
                    self.output_device_dispenser,
                    self.output_effect_scenery,
                    self.output_equipment,
                    self.output_giant,
                    self.output_scenery,
                    self.output_vehicle,
                    self.output_weapon,
                    self.export_skeleton,
                    self.export_render,
                    self.export_collision,
                    self.export_physics,
                    self.export_markers,
                    self.export_animations,
                    self.export_structure,
                    self.export_design,
                    self.lightmap_structure,
                    self.import_to_game,
                    self.export_gr2_files,
                    self.game_version,
                    self.import_check,
                    self.import_force,
                    # self.import_verbose,
                    self.import_draft,
                    self.import_seam_debug,
                    self.import_skip_instances,
                    self.import_decompose_instances,
                    self.import_suppress_errors,
                    self.import_lighting,
                    self.import_meta_only,
                    self.import_disable_hulls,
                    self.import_disable_collision,
                    self.import_no_pca,
                    self.import_force_animations,
                    self.lightmap_quality,
                    self.lightmap_quality_h4,
                    self.lightmap_all_bsps,
                    self.lightmap_specific_bsp,
                    self.lightmap_region,
                    self.fast_animation_export,
                )

            except Exception as e:
                print_error("\n\nException hit. Please include in report\n")
                logging.error(traceback.format_exc())
                self.failed = True

            # validate that a sidecar file exists
            if not file_exists(sidecar_path_full):
                context.scene.nwo_halo_launcher.sidecar_path = ""

            # write scene settings generated during export to temp file

            end = time.perf_counter()

            final_report = ""
            report_type = "INFO"

            if self.failed:
                final_report = "Export Failed"
                report_type = "ERROR"
                print_warning(
                    "\nTag Export crashed and burned. Please let the developer know: https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit/issues\n"
                )
                print_error(
                    "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                )

            elif export.gr2_fail:
                final_report = "GR2 Conversion Failed. Export Aborted"
                report_type = "ERROR"
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print_error("Failed to export a GR2 File. Export cancelled")

                print(
                    "-----------------------------------------------------------------------\n"
                )

            elif export.sidecar_import_failed:
                final_report = "Failed to Create Tags"
                report_type = "ERROR"
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print_error("FAILED TO CREATE TAGS\n")
                if export.sidecar_import_error:
                    # print("Explanation of error:")
                    print(export.sidecar_import_error)

                print("\nFor further details, please review the Tool output above")

                print(
                    "-----------------------------------------------------------------------\n"
                )
            else:
                final_report = "Export Complete"
                report_type = "INFO"
                print(
                    "\n-----------------------------------------------------------------------"
                )
                print(f"Export Completed in {round(end - start, 3)} seconds")

                print(
                    "-----------------------------------------------------------------------\n"
                )

            self.write_temp_settings(context, sidecar_path, final_report, report_type)

        except KeyboardInterrupt:
            print_warning("\n\nEXPORT CANCELLED BY USER")
            self.write_temp_settings(context, sidecar_path)

        # restore scene back to its pre export state
        bpy.ops.ed.undo_push()
        bpy.ops.ed.undo()

        return {"FINISHED"}

    def set_scene_props(self, context):
        scene_nwo = context.scene.nwo

        # set Halo scene version to match game_version (we do this do ensure the code is checking the right toolset)
        scene_nwo.game_version = self.game_version

        # Set the UI asset type to the export type
        scene_nwo.asset_type = self.sidecar_type

        # Set the model outpug tag types in the UI to match export settings
        scene_nwo.output_biped = self.output_biped
        scene_nwo.output_crate = self.output_crate
        scene_nwo.output_creature = self.output_creature
        scene_nwo.output_device_control = self.output_device_control
        scene_nwo.output_device_dispenser = self.output_device_dispenser
        scene_nwo.output_device_machine = self.output_device_machine
        scene_nwo.output_device_terminal = self.output_device_terminal
        scene_nwo.output_effect_scenery = self.output_effect_scenery
        scene_nwo.output_equipment = self.output_equipment
        scene_nwo.output_giant = self.output_giant
        scene_nwo.output_scenery = self.output_scenery
        scene_nwo.output_vehicle = self.output_vehicle
        scene_nwo.output_weapon = self.output_weapon

    def export_invalid(self):
        if (
            not check_path(self.filepath)
            or not file_exists(f"{get_tool_path()}.exe")
            or self.asset_path.lower() + os.sep == get_data_path().lower()
        ):  # check the user is saving the file to a location in their editing kit data directory AND tool exists. AND prevent exports to root data dir
            game = formalise_game_version(self.game_version)
            if get_ek_path() is None or get_ek_path() == "":
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"No {game} Editing Kit path found. Please check your {game} editing kit path in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset] and ensure this points to your {game} editing kit directory.",
                    f"INVALID {game} EK PATH",
                    0,
                )
            elif not file_exists(f"{get_tool_path()}.exe"):
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"{game} Tool not found. Could not find {game} tool or tool_fast. Please check your {game} editing kit path in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset] and ensure this points to your {game} editing kit directory.",
                    f"INVALID {game} TOOL PATH",
                    0,
                )
            elif self.asset_path.lower() + path.sep == get_data_path().lower():
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f'You cannot export directly to your root {game} editing kit data directory. Please create a valid asset directory such as "data\my_asset" and direct your export to this folder',
                    f"ROOT DATA FOLDER EXPORT",
                    0,
                )
            else:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"The selected export folder is outside of your {game} editing kit data directory, please ensure you are exporting to a directory within your {game} editing kit data folder.",
                    f"INVALID {game} EXPORT PATH",
                    0,
                )

            return True

        return False

    def write_temp_settings(
        self, context, sidecar_path, report_text="", report_type=""
    ):
        settings = nwo_globals.nwo_scene_settings
        settings["sidecar_path"] = sidecar_path
        settings["game_version"] = self.game_version
        settings["asset_type"] = self.sidecar_type
        settings["sidecar_type"] = self.sidecar_type
        settings["output_biped"] = self.output_biped
        settings["output_crate"] = self.output_crate
        settings["output_creature"] = self.output_creature
        settings["output_device_control"] = self.output_device_control
        settings["output_device_dispenser"] = self.output_device_dispenser
        settings["output_device_machine"] = self.output_device_machine
        settings["output_device_machine"] = self.output_device_machine
        settings["output_device_terminal"] = self.output_device_terminal
        settings["output_effect_scenery"] = self.output_effect_scenery
        settings["output_equipment"] = self.output_equipment
        settings["output_giant"] = self.output_giant
        settings["output_scenery"] = self.output_scenery
        settings["output_vehicle"] = self.output_vehicle
        settings["output_weapon"] = self.output_weapon
        settings["show_output"] = context.scene.nwo_export.show_output
        settings["lightmap_all_bsps"] = self.lightmap_all_bsps
        settings["lightmap_quality"] = self.lightmap_quality
        settings["lightmap_quality_h4"] = self.lightmap_quality_h4
        settings["lightmap_region"] = self.lightmap_region
        settings["lightmap_specific_bsp"] = self.lightmap_specific_bsp
        settings["lightmap_structure"] = self.lightmap_structure
        settings["import_force"] = self.import_force
        settings["import_draft"] = self.import_draft
        settings["import_seam_debug"] = self.import_seam_debug
        settings["import_skip_instances"] = self.import_skip_instances
        settings["import_decompose_instances"] = self.import_decompose_instances
        settings["import_suppress_errors"] = self.import_suppress_errors
        settings["import_lighting"] = self.import_lighting
        settings["import_meta_only"] = self.import_meta_only
        settings["import_disable_hulls"] = self.import_disable_hulls
        settings["import_disable_collision"] = self.import_disable_collision
        settings["import_no_pca"] = self.import_no_pca
        settings["import_force_animations"] = self.import_force_animations
        settings["fast_animation_export"] = self.fast_animation_export
        settings["fix_bone_rotations"] = self.fix_bone_rotations

        if self.quick_export and report_text and report_type:
            nwo_globals.export_report["report_text"] = report_text
            nwo_globals.export_report["report_type"] = report_type
        elif report_text and report_type:
            self.report({report_type}, report_text)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        box = layout.box()
        h4 = self.game_version in ("h4", "h2a")

        # SETTINGS #
        box.label(text="Settings")

        h4 = self.game_version != "reach"
        scenario = self.sidecar_type == "SCENARIO"

        col = box.column()
        row = col.row()
        if managed_blam_active():
            row.enabled = False
        row.prop(self, "game_version", text="Game")
        row = col.row()
        col.prop(self, "sidecar_type", text="Asset Type")
        col.prop(self, "show_output", text="Toggle Output")
        # NWO SETTINGS #
        box = layout.box()
        box.label(text="Export Scope")
        col = box.column()
        col.prop(self, "export_gr2_files", text="Export Tags")
        if self.export_gr2_files:
            col.separator()
            sub = col.column(heading="Export")
            # sub.prop(self, "export_hidden")
            if self.sidecar_type == "MODEL":
                sub.prop(self, "export_render")
                sub.prop(self, "export_collision")
                sub.prop(self, "export_physics")
                sub.prop(self, "export_markers")
                sub.prop(self, "export_skeleton")
                sub.prop(self, "export_animations", expand=True)
            elif self.sidecar_type == "FP ANIMATION":
                sub.prop(self, "export_skeleton")
                sub.prop(self, "export_animations", expand=True)
            elif self.sidecar_type == "SCENARIO":
                sub.prop(self, "export_structure")
                sub.prop(self, "export_design")
                sub.prop(self, "export_all_bsps", expand=True)
            elif self.sidecar_type != "PREFAB":
                sub.prop(self, "export_render")
            if self.sidecar_type not in (
                "DECORATOR SET",
                "PARTICLE MODEL",
                "PREFAB",
            ):
                sub.prop(self, "export_all_perms", expand=True)
        # SIDECAR SETTINGS #
        if self.sidecar_type == "MODEL" and self.export_gr2_files:
            box = layout.box()
            box.label(text="Model Settings")
            col = box.column()
            # col.prop(self, "export_sidecar_xml")
            # if self.export_sidecar_xml:
            sub = box.column(heading="Output Tags")
            if self.sidecar_type == "MODEL":
                sub.prop(self, "output_biped")
                sub.prop(self, "output_crate")
                sub.prop(self, "output_creature")
                sub.prop(self, "output_device_control")
                if h4:
                    sub.prop(self, "output_device_dispenser")
                sub.prop(self, "output_device_machine")
                sub.prop(self, "output_device_terminal")
                sub.prop(self, "output_effect_scenery")
                sub.prop(self, "output_equipment")
                sub.prop(self, "output_giant")
                sub.prop(self, "output_scenery")
                sub.prop(self, "output_vehicle")
                sub.prop(self, "output_weapon")

        # IMPORT SETTINGS #
        if self.export_gr2_files:
            box = layout.box()
            sub = box.column(heading="Export Flags")
            if self.sidecar_type in (('MODEL', 'SKY', 'FP ANIMATION')):
                col.prop(self, "fix_bone_rotations", text="Fix Bone Rotations")
                col.prop(self, "fast_animation_export", text="Fast Animation Export")
            if h4:
                sub.prop(self, "import_force", text="Force full export")
                if scenario:
                    sub.prop(
                        self, "import_seam_debug", text="Show more seam debugging info"
                    )
                    sub.prop(
                        self, "import_skip_instances", text="Skip importing instances"
                    )
                    sub.prop(
                        self, "import_meta_only", text="Only import structure_meta tag"
                    )
                    sub.prop(
                        self,
                        "import_lighting",
                        text="Only reimport lighting information",
                    )
                    sub.prop(
                        self,
                        "import_disable_hulls",
                        text="Skip instance convex hull decomp",
                    )
                    sub.prop(
                        self,
                        "import_disable_collision",
                        text="Don't generate complex collision",
                    )
                else:
                    sub.prop(self, "import_no_pca", text="Skip PCA calculations")
                    sub.prop(
                        self,
                        "import_force_animations",
                        text="Force import error animations",
                    )
            else:
                sub.prop(self, "import_force", text="Force full export")
                # sub.prop(self, "import_verbose", text="Verbose Output")
                sub.prop(
                    self, "import_suppress_errors", text="Don't write errors to VRML"
                )
                if scenario:
                    sub.prop(
                        self, "import_seam_debug", text="Show more seam debugging info"
                    )
                    sub.prop(
                        self, "import_skip_instances", text="Skip importing instances"
                    )
                    sub.prop(
                        self,
                        "import_decompose_instances",
                        text="Run convex physics decomposition",
                    )
                else:
                    sub.prop(self, "import_draft", text="Skip PRT generation")

        # LIGHTMAP SETTINGS #
        render = self.sidecar_type in ("MODEL", "SKY")
        if (h4 and render) or scenario:
            box = layout.box()
            box.label(text="Lightmap Settings")
            col = box.column()
            if scenario:
                lighting_name = "Light Scenario"
            else:
                lighting_name = "Light Model"

            col.prop(self, "lightmap_structure", text=lighting_name)
            if self.lightmap_structure:
                if scenario:
                    if h4:
                        col.prop(self, "lightmap_quality_h4")
                    else:
                        col.prop(self, "lightmap_quality")
                    if not self.lightmap_all_bsps:
                        col.prop(self, "lightmap_specific_bsp")
                    col.prop(self, "lightmap_all_bsps")
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
    self.layout.operator(NWO_Export_Scene.bl_idname, text="Halo Tag")


def fbx_exporter():
    exporter = "default"
    # addon_default, addon_state = check("better_fbx")

    # if addon_default or addon_state:
    #     from sys import modules

    #     if module_bl_info(modules.get("better_fbx")).get("version") in (
    #         (5, 1, 5),
    #         (5, 2, 10),
    #     ):
    #         exporter = "better"
    #     else:
    #         print(
    #             "Only BetterFBX versions [5.1.5] & [5.2.10] are supported. Using Blender's default fbx exporter"
    #         )

    return exporter


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
    bpy.utils.register_class(NWO_Export_Scene)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.utils.unregister_class(NWO_Export_Scene)

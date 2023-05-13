# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2022 Generalkidd & Crisp
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
# TODO Add proper exception handling for when frame id tool anim graph path invalid or empty
# TODO Stop structure design bsps being added to the connected_geometry_bsp_table
# TODO get / setter for halo light colour
# TODO Animation name tool
# TODO Face map properties
# TODO Strip prefixes on export and apply maya namespace prefixes (h4/h2a)

bl_info = {
    'name': 'Halo NWO Export',
    'author': 'Crisp',
    'version': (1, 0, 0),
    'blender': (3, 5, 0),
    'location': 'File > Export',
    'category': 'Export',
    'description': 'Asset Exporter and Toolset for Halo Reach, Halo 4, and Halo 2 Aniversary Multiplayer'
    }

import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, CollectionProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList
from addon_utils import check, module_bl_info
from os.path import exists as file_exists
from os import path
from os import remove as os_remove
import ctypes
from io_scene_foundry.icons import get_icon_id


from io_scene_foundry.utils.nwo_utils import CheckPath, bpy_enum, dot_partition, get_data_path, get_asset_info, get_ek_path, get_tags_path, get_tool_path, managed_blam_active

# lightmapper_run_once = False
sidecar_read = False

class NWO_Export_Scene(Operator, ExportHelper):
    """Exports a Reach+ Asset for use in your Halo Editing Kit"""
    bl_idname = 'export_scene.nwo'
    bl_label = 'Export Asset'
    bl_options = {'UNDO', 'PRESET'}

    filename_ext = ".fbx"

    filter_glob: StringProperty(
        default='*.fbx',
        options={'HIDDEN'},
        maxlen=1024,
    )
    game_version:EnumProperty(
        name="Game Version",
        description="The game to export this asset for",
        default='reach',
        items=[('reach', "Halo Reach", "Export an asset intended for Halo Reach"), ('h4', "Halo 4", "Export an asset intended for Halo 4"), ('h2a', "Halo 2A MP", "Export an asset intended for Halo 2A MP")]
    )
    keep_fbx: BoolProperty(
        name="FBX",
        description="Keep the source FBX file after GR2 conversion",
        default=True,
    )
    keep_json: BoolProperty(
        name="JSON",
        description="Keep the source JSON file after GR2 conversion",
        default=True,
    )
    export_sidecar_xml: BoolProperty(
        name="Build Sidecar",
        description="",
        default=True,
    )
    sidecar_type: EnumProperty(
        name='Asset Type',
        description='',
        default='MODEL',
        items=[ ('MODEL', "Model", ""), ('SCENARIO', "Scenario", ""), ('SKY', 'Sky', ''), ('DECORATOR SET', 'Decorator Set', ''), ('PARTICLE MODEL', 'Particle Model', ''), ('PREFAB', 'Prefab', ''), ('FP ANIMATION', 'First Person Animation', '')]
    )
    export_animations: EnumProperty(
        name='Animations',
        description='',
        default='ACTIVE',
        items=[ ('ALL', "All", ""), ('ACTIVE', "Active", ""), ('NONE', 'None', '')]
    )
    export_skeleton: BoolProperty(
        name='Skeleton',
        description='',
        default=True,
    )
    export_render: BoolProperty(
        name='Render Models',
        description='',
        default=True,
    )
    export_collision: BoolProperty(
        name='Collision Models',
        description='',
        default=True,
    )
    export_physics: BoolProperty(
        name='Physics Models',
        description='',
        default=True,
    )
    export_markers: BoolProperty(
        name='Markers',
        description='',
        default=True,
    )
    export_structure: BoolProperty(
        name='Structure',
        description='',
        default=True,
    )
    export_design: BoolProperty(
        name='Structure Design',
        description='',
        default=True,
    )
    export_all_bsps: EnumProperty(
        name='BSPs',
        description='Specify whether to export all BSPs, or just those selected',
        default='all',
        items=[('all', 'All', ''), ('selected', 'Selected', '')]
    )
    export_all_perms: EnumProperty(
        name='Permutations',
        description='Specify whether to export all permutations, or just those selected',
        default='all',
        items=[('all', 'All', ''), ('selected', 'Selected', '')]
    )
    output_biped: BoolProperty(
        name='Biped',
        description='',
        default=False,
    )
    output_crate: BoolProperty(
        name='Crate',
        description='',
        default=False,
    )
    output_creature: BoolProperty(
        name='Creature',
        description='',
        default=False,
    )
    output_device_control: BoolProperty(
        name='Device Control',
        description='',
        default=False,
    )
    output_device_dispenser: BoolProperty(
        name='Device Dispenser',
        description='',
        default=False,
    )
    output_device_machine: BoolProperty(
        name='Device Machine',
        description='',
        default=False,
    )
    output_device_terminal: BoolProperty(
        name='Device Terminal',
        description='',
        default=False,
    )
    output_effect_scenery: BoolProperty(
        name='Effect Scenery',
        description='',
        default=False,
    )
    output_equipment: BoolProperty(
        name='Equipment',
        description='',
        default=False,
    )
    output_giant: BoolProperty(
        name='Giant',
        description='',
        default=False,
    )
    output_scenery: BoolProperty(
        name='Scenery',
        description='',
        default=False,
    )
    output_vehicle: BoolProperty(
        name='Vehicle',
        description='',
        default=False,
    )
    output_weapon: BoolProperty(
        name='Weapon',
        description='',
        default=False,
    )
    import_to_game: BoolProperty(
        name='Create Tags',
        description='',
        default=True,
    )
    show_output: BoolProperty(
        name='Show Output',
        description='',
        default=True
    )
    import_check: BoolProperty(
        name='Check',
        description='Run the import process but produce no output files',
        default=False,
    )
    import_force: BoolProperty(
        name='Force',
        description="Force all files to import even if they haven't changed",
        default=False,
    )
    import_verbose: BoolProperty(
        name='Verbose',
        description="Write additional import progress information to the console",
        default=False,
    )
    import_draft: BoolProperty(
        name='Draft',
        description="Skip generating PRT data. Faster speed, lower quality",
        default=False,
    )
    import_seam_debug: BoolProperty(
        name='Seam Debug',
        description="Write extra seam debugging information to the console",
        default=False,
    )
    import_skip_instances: BoolProperty(
        name='Skip Instances',
        description="Skip importing all instanced geometry",
        default=False,
    )
    import_decompose_instances: BoolProperty(
        name='Decompose Instances',
        description="Run convex decomposition for instanced geometry physics (very slow)",
        default=False,
    )
    import_surpress_errors: BoolProperty(
        name='Surpress Errors',
        description="Do not write errors to vrml files",
        default=False,
    )
    use_selection: BoolProperty(
        name="selection",
        description="",
        default=True,
    )
    bake_anim: BoolProperty(
        name='',
        description='',
        default=True
    )
    use_mesh_modifiers: BoolProperty(
        name='Apply Modifiers',
        description='',
        default=True,
    )
    use_triangles: BoolProperty(
        name='Triangulate',
        description='',
        default=True,
    )
    global_scale: FloatProperty(
        name='Scale',
        description='',
        default=1.0
    )
    use_armature_deform_only: BoolProperty(
        name='Deform Bones Only',
        description='Only export bones with the deform property ticked',
        default=True,
    )

    meshes_to_empties: BoolProperty(
        name='Markers as Empties',
        description='Export all mesh Halo markers as empties. Helps save on export / import time and file size',
        default=True,
    )

    export_hidden: BoolProperty(
        name="Hidden",
        description="Export visible objects only",
        default=True,
    )
    import_in_background: BoolProperty(
        name='Run In Background',
        description="If enabled does not pause use of blender during the import process",
        default=False
    )
    lightmap_structure: BoolProperty(
        name='Run Lightmapper',
        default=False,
    )
    lightmap_quality: EnumProperty(
        name='Quality',
        items=(('DIRECT', "Direct", ""),
                ('DRAFT', "Draft", ""),
                ('LOW', "Low", ""),
                ('MEDIUM', "Medium", ""),
                ('HIGH', "High", ""),
                ('SUPER', "Super (very slow)", ""),
                ),
        default='DIRECT',
        description="Define the lightmap quality you wish to use",
    )

    def item_lightmap_quality_h4(self, context):
        items = []
        items.append(('asset', 'Asset', 'The user defined lightmap settings. Opens a settings dialog', 0))
        lightmapper_globals_dir = path.join(get_tags_path(), 'globals', 'lightmapper_settings')
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
        name='Quality',
        items=item_lightmap_quality_h4,
        description="Define the lightmap quality you wish to use",
    )
    lightmap_all_bsps: BoolProperty(
        name='All BSPs',
        default=True,
    )
    lightmap_specific_bsp: StringProperty(
        name='Specific BSP',
        default='',
    )

    lightmap_region: StringProperty(
        name='Region',
        description="Lightmap region to use for lightmapping",
    )

    mesh_smooth_type_better: EnumProperty(
            name="Smoothing",
            items=(('None', "None", "Do not generate smoothing groups"),
                   ('Blender', "By Hard edges", ""),
                   ('FBXSDK', "By FBX SDK", ""),
                   ),
            description="Determine how smoothing groups should be generated",
            default='FBXSDK',
            )
    mesh_smooth_type: EnumProperty(
            name="Smoothing",
            items=(('OFF', "Normals Only", "Export only normals instead of writing edge or face smoothing data"),
                   ('FACE', "Face", "Write face smoothing"),
                   ('EDGE', "Edge", "Write edge smoothing"),
                   ),
            description="Export smoothing information "
                        "(prefer 'Normals Only' option if your target importer understand split normals)",
            default='OFF',
            )
    quick_export: BoolProperty(
        name='',
        default=False,
    )
    export_gr2_files: BoolProperty(
        name='Export GR2 Files',
        default=True,
    )
    use_tspace: BoolProperty( 
        name='use tspace',
        default=False,
    )

    def __init__(self):
        # SETUP #
        scene = bpy.context.scene

        if scene.nwo_global.game_version in (('reach','h4','h2a')):
            self.game_version = scene.nwo_global.game_version

        # QUICK EXPORT SETTINGS #

        scene_nwo_export = scene.nwo_export
        self.export_gr2_files = scene_nwo_export.export_gr2_files
        self.export_hidden = scene_nwo_export.export_hidden
        self.export_all_bsps = scene_nwo_export.export_all_bsps
        self.export_all_perms = scene_nwo_export.export_all_perms
        self.export_sidecar_xml = scene_nwo_export.export_sidecar_xml
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
        self.export_poops = scene_nwo_export.export_design

        self.use_mesh_modifiers = scene_nwo_export.use_mesh_modifiers
        self.use_triangles = scene_nwo_export.use_triangles
        self.global_scale = scene_nwo_export.global_scale
        self.use_armature_deform_only = scene_nwo_export.use_armature_deform_only
        self.meshes_to_empties = scene_nwo_export.meshes_to_empties

        self.show_output = scene_nwo_export.show_output
        self.keep_fbx = scene_nwo_export.keep_fbx
        self.keep_json = scene_nwo_export.keep_json

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
        sidecar_filepath = path.join(get_data_path(), scene.nwo_halo_launcher.sidecar_path)
        if not sidecar_filepath.endswith('.sidecar.xml'):
            sidecar_filepath = ''
        if sidecar_filepath != '' and file_exists(sidecar_filepath):
            # export_settings = ExportSettingsFromSidecar(sidecar_filepath)
            self.filepath = path.join(sidecar_filepath.rpartition('\\')[0], 'halo_export.fbx')
        elif bpy.data.is_saved:
            try:
                filepath_list = bpy.path.abspath("//").split('\\')
                del filepath_list[-1]
                if filepath_list[-1] == 'work' and filepath_list[-2] in ('models', 'animations'):
                    del filepath_list[-1]
                    del filepath_list[-1]
                elif filepath_list[-1] in ('models', 'animations'):
                    del filepath_list[-1]
                drive = filepath_list[0]
                del filepath_list[0]
                self.filepath = path.join(drive, path.sep, *filepath_list, 'halo_export.fbx')
            except:
                if get_data_path() != '':
                    self.filepath = path.join(get_data_path(),  'halo_export.fbx')

        elif get_data_path() != '':
            self.filepath = path.join(get_data_path(),  'halo_export.fbx')

    def execute(self, context):
        # get the asset name and path to the asset folder
        asset_path, asset = get_asset_info(self.filepath)

        scene_nwo = context.scene.nwo

        # set Halo scene version to match game_version (we do this do ensure the code is checking the right toolset)
        context.scene.nwo_global.game_version = self.game_version

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

        # Check that we can export
        if not CheckPath(self.filepath) or not file_exists(f'{get_tool_path()}.exe') or asset_path + path.sep == get_data_path(): # check the user is saving the file to a location in their editing kit data directory AND tool exists. AND prevent exports to root data dir

            if get_ek_path() is None or get_ek_path() == '':
                ctypes.windll.user32.MessageBoxW(0, f"No {self.game_version.upper()} Editing Kit path found. Please check your {self.game_version.upper()} editing kit path in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset] and ensure this points to your {self.game_version.upper()} editing kit directory.", f"INVALID {self.game_version.upper()} EK PATH", 0)
            elif not file_exists(f'{get_tool_path()}.exe'):
                ctypes.windll.user32.MessageBoxW(0, f"{self.game_version.upper()} Tool not found. Could not find {self.game_version.upper()} tool or tool_fast. Please check your {self.game_version.upper()} editing kit path in add-on preferences [Edit > Preferences > Add-ons > Halo Asset Blender Development Toolset] and ensure this points to your {self.game_version.upper()} editing kit directory.", f"INVALID {self.game_version.upper()} TOOL PATH", 0)
            elif asset_path + path.sep == get_data_path():
                ctypes.windll.user32.MessageBoxW(0, f'You cannot export directly to your root {self.game_version.upper()} editing kit data directory. Please create a valid asset directory such as "data\my_asset" and direct your export to this folder', f"ROOT DATA FOLDER EXPORT", 0)
            else:
                ctypes.windll.user32.MessageBoxW(0, f"The selected export folder is outside of your {self.game_version.upper()} editing kit data directory, please ensure you are exporting to a directory within your {self.game_version.upper()} editing kit data folder.", f"INVALID {self.game_version.upper()} EXPORT PATH", 0)
            
        else:
            print('Preparing Scene for Export...')

            keywords = self.as_keywords()
            console = bpy.ops.wm

            if self.show_output:
                console.console_toggle() # toggle the console so users can see progress of export

            context.scene.nwo_export.show_output = False

            from .prepare_scene import prepare_scene
            (model_armature, skeleton_bones, halo_objects, timeline_start, timeline_end, lod_count, selected_perms, selected_bsps, regions_dict, global_materials_dict, current_action
            ) = prepare_scene(context, self.report, asset, **keywords) # prepares the scene for processing and returns information about the scene
            # if self.build_shaders:
            #     shader_builder()
            # try:
            from .process_scene import process_scene
            final_report = process_scene(self, context, keywords, self.report, model_armature, asset_path, asset, skeleton_bones, halo_objects, timeline_start, timeline_end, lod_count, UsingBetterFBX(), selected_perms, selected_bsps, regions_dict, global_materials_dict, current_action, **keywords)
            # except Exception:
            #     from traceback import print_exc
            #     print_exc()
            #     self.report({'ERROR'}, 'ASSERT: Scene processing failed')

            sidecar_path = path.join(asset_path.replace(get_data_path(), ''), f'{asset}.sidecar.xml')

            if not file_exists(path.join(get_data_path(), sidecar_path)):
                sidecar_path = ''

            temp_file_path = path.join(bpy.app.tempdir, 'nwo_scene_settings.txt')
            with open(temp_file_path, 'w') as temp_file:
                temp_file.write(f'{sidecar_path}\n')
                temp_file.write(f'{self.game_version}\n')
                temp_file.write(f'{self.sidecar_type}\n')
                temp_file.write(f'{self.output_biped}\n')
                temp_file.write(f'{self.output_crate}\n')
                temp_file.write(f'{self.output_creature}\n')
                temp_file.write(f'{self.output_device_control}\n')
                temp_file.write(f'{self.output_device_dispenser}\n')
                temp_file.write(f'{self.output_device_machine}\n')
                temp_file.write(f'{self.output_device_terminal}\n')
                temp_file.write(f'{self.output_effect_scenery}\n')
                temp_file.write(f'{self.output_equipment}\n')
                temp_file.write(f'{self.output_giant}\n')
                temp_file.write(f'{self.output_scenery}\n')
                temp_file.write(f'{self.output_vehicle}\n')
                temp_file.write(f'{self.output_weapon}\n')
                temp_file.write(f'{context.scene.nwo_export.show_output}\n')
                if self.quick_export:
                    temp_file.write(f'{final_report}\n')
                else:
                    self.report({'INFO'}, final_report)
                    
        bpy.ops.ed.undo_push()
        bpy.ops.ed.undo()

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        box = layout.box()
        h4 = self.game_version in ('h4', 'h2a')

        # SETTINGS #
        box.label(text="Settings")

        col = box.column()
        row = col.row()
        if managed_blam_active():
            row.enabled = False
        row.prop(self, "game_version", text='Game Version')
        row = col.row()
        col.prop(self, "sidecar_type", text='Asset Type')
        col.prop(self, "show_output", text='Toggle Output')
        # NWO SETTINGS #
        box = layout.box()
        box.label(text="GR2 Settings")
        col = box.column()
        col.prop(self, "export_gr2_files", text='Export GR2 Files')
        if self.export_gr2_files:
            col.separator()
            sub = col.column(heading="Keep")
            sub.prop(self, "keep_fbx")
            sub.prop(self, "keep_json")
            col.separator()
            sub = col.column(heading="Export")
            sub.prop(self, "export_hidden")
            if self.sidecar_type == 'MODEL':
                sub.prop(self, "export_render")
                sub.prop(self, "export_collision")
                sub.prop(self, "export_physics")
                sub.prop(self, "export_markers")
                sub.prop(self, 'export_skeleton')
                sub.prop(self, "export_animations", expand=True)
            elif self.sidecar_type == 'FP ANIMATION':
                sub.prop(self, 'export_skeleton')
                sub.prop(self, "export_animations", expand=True)
            elif self.sidecar_type == 'SCENARIO':
                sub.prop(self, "export_structure")
                sub.prop(self, 'export_design')
                sub.prop(self, 'export_all_bsps', expand=True)
            elif self.sidecar_type != 'PREFAB':
                sub.prop(self, "export_render")
            if (self.sidecar_type not in ('DECORATOR SET', 'PARTICLE MODEL', 'PREFAB')):
                sub.prop(self, 'export_all_perms', expand=True)
        # SIDECAR SETTINGS #
        box = layout.box()
        box.label(text="Sidecar Settings")
        col = box.column()
        col.prop(self, "export_sidecar_xml")
        if self.export_sidecar_xml:
            if self.sidecar_type == 'MODEL' and self.export_sidecar_xml:
                sub = box.column(heading="Output Tags")
            if self.sidecar_type == 'MODEL':
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
        box = layout.box()
        box.label(text="Import Settings")
        col = box.column()
        col.prop(self, "import_to_game")
        if self.import_to_game:
            sub = box.column(heading="Import Flags")
            sub.prop(self, "import_check")
            sub.prop(self, "import_force")
            sub.prop(self, "import_verbose")
            sub.prop(self, "import_surpress_errors")
            if self.sidecar_type == 'SCENARIO':
                sub.prop(self, "import_seam_debug")
                sub.prop(self, "import_skip_instances")
                sub.prop(self, "import_decompose_instances")
            else:
                sub.prop(self, "import_draft")

        # LIGHTMAP SETTINGS #
        if self.sidecar_type == 'SCENARIO':
            box = layout.box()
            box.label(text="Lightmap Settings")
            col = box.column()
            col.prop(self, "lightmap_structure")
            if self.lightmap_structure:
                if h4:
                    col.prop(self, "lightmap_quality_h4") 
                else:
                    col.prop(self, "lightmap_quality")
                if not self.lightmap_all_bsps:
                    col.prop(self, 'lightmap_specific_bsp')
                col.prop(self, 'lightmap_all_bsps')
                if not h4:
                    col.prop(self, "lightmap_region")

        # # BITMAP SETTINGS #
        # box = layout.box()
        # box.label(text="Bitmap Settings")
        # col = box.column()
        # col.prop(self, "import_bitmaps")
        # if self.import_bitmaps:
        #     col.prop(self, "bitmap_type")

        # SCENE SETTINGS #
        box = layout.box()
        box.label(text="Scene Settings")
        col = box.column()
        col.prop(self, "use_mesh_modifiers")
        col.prop(self, "use_triangles")
        col.prop(self, 'use_armature_deform_only') 
        col.prop(self, 'meshes_to_empties')
        if UsingBetterFBX():
            col.prop(self, 'mesh_smooth_type_better')
        else:
            col.prop(self, 'mesh_smooth_type')
        col.separator()
        col.prop(self, "global_scale")

def menu_func_export(self, context):
    self.layout.operator(NWO_Export_Scene.bl_idname, text="Halo Tag Exporter")

def UsingBetterFBX():
    using_better_fbx = False
    addon_default, addon_state = check('better_fbx')

    if (addon_default or addon_state):
        from sys import modules
        if module_bl_info(modules.get('better_fbx')).get('version') in ((5, 1, 5), (5, 2, 10)):
            using_better_fbx = True
        else:
            print("Only BetterFBX versions [5.1.5] & [5.2.10] are supported. Using Blender's default fbx exporter")

    return using_better_fbx

def ExportSettingsFromSidecar(sidecar_filepath):
    settings = []
    import xml.etree.ElementTree as ET
    tree = ET.parse(sidecar_filepath)
    metadata = tree.getroot()
    # get the type of sidecar this is
    asset = metadata.find('Asset')
    if asset.get('Sky') == 'true':
        asset_type = 'sky'
    else:
        asset_type = asset.get('Type')
    # append the type to the settings list
    settings.append(asset_type)
    # if asset type is a model, we need to grab some additional info
    output_tags = []
    if settings[0] == 'model':
        output_collection = asset.find('OutputTagCollection')
        for tag in output_collection.findall('OutputTag'):
            if tag.get('Type') != 'model': # don't collect the model output_tag, we don't need this
                output_tags.append(tag.get('Type'))

        settings.append(output_tags)


    return settings
##############################################
# NWO Scene Settings
##############################################
class NWO_SceneProps(Panel):
    bl_label = "Asset Properties"
    bl_idname = "NWO_PT_GameVersionPanel"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_parent_id = "NWO_PT_ScenePropertiesPanel"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo_global
        return scene_nwo.game_version in ('reach', 'h4', 'h2a')

    def draw(self, context):
        layout = self.layout
        scene_nwo = context.scene.nwo
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        flow.use_property_split = True
        col = flow.column()
        col.prop(scene_nwo, 'asset_type')
        col.separator()
        #col.prop(scene_nwo, 'default_mesh_type_ui')
        if scene_nwo.asset_type in ('MODEL', 'FP ANIMATION'):
            col.prop(scene_nwo, 'forward_direction')
            col.separator()
        # col.prop(scene_nwo, 'filter_ui', text = 'Filter UI')
        if scene_nwo.asset_type == 'MODEL':
            col.label(text="Output Tags")
            row = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=True, align=True)
            # row = layout.row(align=True)
            row.scale_x = 1.3
            row.scale_y = 1.3

            row.prop(scene_nwo, "output_crate", text='',icon_value=get_icon_id('crate'))
            row.prop(scene_nwo, "output_scenery",text='',icon_value=get_icon_id('scenery'))
            row.prop(scene_nwo, "output_effect_scenery",text='',icon_value=get_icon_id('effect_scenery'))

            row.prop(scene_nwo, "output_device_control",text='',icon_value=get_icon_id('device_control'))
            row.prop(scene_nwo, "output_device_machine", text='',icon_value=get_icon_id('device_machine'))
            row.prop(scene_nwo, "output_device_terminal", text='',icon_value=get_icon_id('device_terminal'))
            if context.scene.nwo_global.game_version in ('h4', 'h2a'):
                row.prop(scene_nwo, "output_device_dispenser",text='',icon_value=get_icon_id('device_dispenser'))

            row.prop(scene_nwo, "output_biped", text='', icon_value=get_icon_id('biped'))
            row.prop(scene_nwo, "output_creature",text='',icon_value=get_icon_id('creature'))
            row.prop(scene_nwo, "output_giant", text='', icon_value=get_icon_id('giant'))
            
            row.prop(scene_nwo, "output_vehicle", text='',icon_value=get_icon_id('vehicle'))
            row.prop(scene_nwo, "output_weapon", text='',icon_value=get_icon_id('weapon'))
            row.prop(scene_nwo, "output_equipment",text='',icon_value=get_icon_id('equipment'))



class NWO_UL_SceneProps_SharedAssets(UIList):
    use_name_reverse: bpy.props.BoolProperty(
        name="Reverse Name",
        default=False,
        options=set(),
        description="Reverse name sort order",
    )

    use_order_name: bpy.props.BoolProperty(
        name="Name",
        default=False,
        options=set(),
        description="Sort groups by their name (case-insensitive)",
    )

    filter_string: bpy.props.StringProperty(
        name="filter_string",
        default = "",
        description="Filter string for name"
    )

    filter_invert: bpy.props.BoolProperty(
        name="Invert",
        default = False,
        options=set(),
        description="Invert Filter"
    )


    def filter_items(self, context,
                    data, 
                    property 
        ):


        items = getattr(data, property)
        if not len(items):
            return [], []

        if self.filter_string:
            flt_flags = bpy.types.UI_UL_list.filter_items_by_name(
                    self.filter_string,
                    self.bitflag_filter_item,
                    items, 
                    propname="name",
                    reverse=self.filter_invert)
        else:
            flt_flags = [self.bitflag_filter_item] * len(items)

        if self.use_order_name:
            flt_neworder = bpy.types.UI_UL_list.sort_items_by_name(items, "name")
            if self.use_name_reverse:
                flt_neworder.reverse()
        else:
            flt_neworder = []    


        return flt_flags, flt_neworder        

    def draw_filter(self, context,
                    layout
        ):

        row = layout.row(align=True)
        row.prop(self, "filter_string", text="Filter", icon="VIEWZOOM")
        row.prop(self, "filter_invert", text="", icon="ARROW_LEFTRIGHT")


        row = layout.row(align=True)
        row.label(text="Order by:")
        row.prop(self, "use_order_name", toggle=True)

        icon = 'TRIA_UP' if self.use_name_reverse else 'TRIA_DOWN'
        row.prop(self, "use_name_reverse", text="", icon=icon)

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        scene = context.scene
        scene_nwo = scene.nwo
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if scene:
                layout.label(text=item.shared_asset_name, icon='BOOKMARKS')
            else:
                layout.label(text='')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)    
            
class NWO_SceneProps_SharedAssets(Panel):
    bl_label = "Shared Assets"
    bl_idname = "NWO_PT_GameVersionPanel_SharedAssets"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_parent_id = "NWO_PT_GameVersionPanel"

    @classmethod
    def poll(cls, context):
        return False # hiding this menu until it actually does something

    def draw(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        layout = self.layout

        layout.template_list("NWO_UL_SceneProps_SharedAssets", "", scene_nwo, "shared_assets", scene_nwo, 'shared_assets_index')
        # layout.template_list("NWO_UL_SceneProps_SharedAssets", "compact", scene_nwo, "shared_assets", scene_nwo, "shared_assets_index", type='COMPACT') # not needed

        row = layout.row()
        col = row.column(align=True)
        col.operator("nwo_shared_asset.list_add", text="Add")
        col = row.column(align=True)
        col.operator("nwo_shared_asset.list_remove", text="Remove")
        
        if len(scene_nwo.shared_assets) > 0:
            item = scene_nwo.shared_assets[scene_nwo.shared_assets_index]
            row = layout.row()
            # row.prop(item, "shared_asset_name", text='Asset Name') # debug only
            row.prop(item, "shared_asset_path", text='Path')
            row = layout.row()
            row.prop(item, "shared_asset_type", text='Type')

class NWO_List_Add_Shared_Asset(Operator):
    """ Add an Item to the UIList"""
    bl_idname = "nwo_shared_asset.list_add"
    bl_label = "Add"
    bl_description = "Add a new shared asset (sidecar) to the list."
    filename_ext = ''
    bl_options = {"REGISTER", "UNDO"}

    filter_glob: StringProperty(
        default="*.xml",
        options={'HIDDEN'},
        )

    filepath: StringProperty(
        name="Sidecar",
        description="Set path for the Sidecar file",
        subtype="FILE_PATH"
    )

    @classmethod
    def poll(cls, context):
        return context.scene
    
    def execute(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        scene_nwo.shared_assets.add()
        
        path = self.filepath
        path = path.replace(get_data_path(), '')
        scene_nwo.shared_assets[-1].shared_asset_path = path
        scene_nwo.shared_assets_index = len(scene_nwo.shared_assets) - 1
        context.area.tag_redraw()
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class NWO_List_Remove_Shared_Asset(Operator):
    """ Remove an Item from the UIList"""
    bl_idname = "nwo_shared_asset.list_remove"
    bl_label = "Remove"
    bl_description = "Remove a shared asset (sidecar) from the list."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo
        return context.scene and len(scene_nwo.shared_assets) > 0
    
    def execute(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        index = scene_nwo.shared_assets_index
        scene_nwo.shared_assets.remove(index)
        return {'FINISHED'}

class NWO_Asset_ListItems(PropertyGroup):

    def GetSharedAssetName(self):
        name = self.shared_asset_path
        name = name.rpartition('\\')[2]
        name = name.rpartition('.sidecar.xml')[0]

        return name

    shared_asset_name: StringProperty(
        get=GetSharedAssetName,
    )

    shared_asset_path: StringProperty()

    shared_asset_types = [
            ('BipedAsset', 'Biped', ''),
            ('CrateAsset', 'Crate', ''),
            ('CreatureAsset', 'Creature', ''),
            ('Device_ControlAsset', 'Device Control', ''),
            ('Device_MachineAsset', 'Device Machine', ''),
            ('Device_TerminalAsset', 'Device Terminal', ''),
            ('Effect_SceneryAsset', 'Effect Scenery', ''),
            ('EquipmentAsset', 'Equipment', ''),
            ('GiantAsset', 'Giant', ''),
            ('SceneryAsset', 'Scenery', ''),
            ('VehicleAsset', 'Vehicle', ''),
            ('WeaponAsset', 'Weapon', ''),
            ('ScenarioAsset', 'Scenario', ''),
            ('Decorator_SetAsset', 'Decorator Set', ''),
            ('Particle_ModelAsset', 'Particle Model', ''),
        ]

    shared_asset_type: EnumProperty(
        name='Type',
        default='BipedAsset',
        options=set(),
        items=shared_asset_types
    )

class NWO_ScenePropertiesGroup(PropertyGroup):
    shared_assets: CollectionProperty(
        type=NWO_Asset_ListItems,
    )

    shared_assets_index: IntProperty(
        name='Index for Shared Asset',
        default=0,
        min=0,
    )

    def force_set_mesh_types(self, context):
        """Sets an objects mesh type to it's current mesh type. Gets around the default mesh type get/setter updating existing objects"""
        for ob in context.scene.objects:
            ob.nwo.ObjectMesh_Type_H4 = ob.nwo.ObjectMesh_Type_H4
            ob.nwo.ObjectMesh_Type = ob.nwo.ObjectMesh_Type

        self.default_mesh_type = self.default_mesh_type_ui

    mesh_type_items = [
        ('_connected_geometry_mesh_type_boundary_surface', "Boundary Surface", "Used in structure_design tags for soft_kill, soft_ceiling, and slip_sufaces. Only use when importing to a structure_design tag. Can be forced on with the prefixes: '+soft_ceiling', 'soft_kill', 'slip_surface'"), # 0
        ('_connected_geometry_mesh_type_collision', "Collision", "Sets this mesh to have collision geometry only. Can be forced on with the prefix: '@'"), #1
        ('_connected_geometry_mesh_type_cookie_cutter', "Cookie Cutter", "Defines an area which ai will pathfind around. Can be forced on with the prefix: '+cookie'"), # 2
        ('_connected_geometry_mesh_type_decorator', "Decorator", "Use this when making a decorator. Allows for different LOD levels to be set"), # 3
        ('_connected_geometry_mesh_type_default', "Render / Structure", "By default this mesh type will be treated as render only geometry in models, and render + bsp collision geometry in structures"), #4
        ('_connected_geometry_mesh_type_poop', "Instanced Geometry", "Writes this mesh to a json file as instanced geometry. Can be forced on with the prefix: '%'"), # 5
        ('_connected_geometry_mesh_type_object_instance', "Object Instance", "Writes this mesh to the json as an instanced object. Can be forced on with the prefix: '+flair'"), # 10
        ('_connected_geometry_mesh_type_physics', "Physics", "Sets this mesh to have physics geometry only. Can be forced on with the prefix: '$'"), # 11
        ('_connected_geometry_mesh_type_planar_fog_volume', "Planar Fog Volume", "Defines an area for a fog volume. The same logic as used for portals should be applied to these.  Can be forced on with the prefix: '+fog'"), # 12
        ('_connected_geometry_mesh_type_portal', "Portal", "Cuts up a bsp and defines clusters. Can be forced on with the prefix '+portal'"), # 13
        ('_connected_geometry_mesh_type_seam', "Seam", "Defines where two bsps meet. Its name should match the name of the bsp its in. Can be forced on with the prefix '+seam'"), # 14
        ('_connected_geometry_mesh_type_water_physics_volume', "Water Physics Volume", "Defines an area where water physics should apply. Only use when importing to a structure_design tag. Can be forced on with the prefix: '+water'"), # 15
        ('_connected_geometry_mesh_type_water_surface', "Water Surface", "Defines a mesh as a water surface. Can be forced on with the prefix: '"), # 16
    ]

    default_mesh_type_ui: EnumProperty(
        name="Default Mesh Type",
        options=set(),
        description="Set the default Halo mesh type for new objects",
        default = '_connected_geometry_mesh_type_default',
        update=force_set_mesh_types,
        items=mesh_type_items
        )

    default_mesh_type: EnumProperty(
        name="Default Mesh Type",
        options=set(),
        description="Set the default Halo mesh type for new objects",
        default = '_connected_geometry_mesh_type_default',
        items=mesh_type_items
        )
    
    def apply_props(self, context):
        for ob in context.scene.objects:
            ob_nwo = ob.nwo

            if ob_nwo.mesh_type_ui == '':
                if self.asset_type == 'DECORATOR SET':
                    ob_nwo.mesh_type_ui = '_connected_geometry_mesh_type_decorator'
                elif self.asset_type == 'SCENARIO':
                    ob_nwo.mesh_type_ui = '_connected_geometry_mesh_type_structure'
                elif self.asset_type == 'PREFAB':
                    ob_nwo.mesh_type_ui = '_connected_geometry_mesh_type_poop'
                else:
                    ob_nwo.mesh_type_ui = '_connected_geometry_mesh_type_render'

    asset_type: EnumProperty(
        name="Asset Type",
        options=set(),
        description="Define the type of asset you are creating",
        default = 'MODEL',
        # update=apply_props,
        items=[ ('MODEL', "Model", ""), ('SCENARIO', "Scenario", ""), ('SKY', 'Sky', ''), ('DECORATOR SET', 'Decorator Set', ''), ('PARTICLE MODEL', 'Particle Model', ''), ('PREFAB', 'Prefab', ''), ('FP ANIMATION', 'First Person Animation', '')]
        )
    
    forward_direction: EnumProperty(
        name="Model Forward",
        options=set(),
        description="Define the forward direction you are using for this model. By default Halo uses X forward. If you model is not x positive select the correct forward directiom.",
        default = 'x',
        items=[ ('x', "X Forward", ""), ('x-', "X Backward", ""), ('y', 'Y Forward', ''), ('y-', 'Y Backward', '')]
    )

    # filter_ui: BoolProperty(
    #     name="Filter UI",
    #     options=set(),
    #     description="When True, hides all UI elements that aren't needed for the selected asset type",
    #     default = True,
    #     )

    output_biped: BoolProperty(
        name='Biped',
        description='',
        default=False,
        options=set(),
    )
    output_crate: BoolProperty(
        name='Crate',
        description='',
        default=False,
        options=set(),
    )
    output_creature: BoolProperty(
        name='Creature',
        description='',
        default=False,
        options=set(),
    )
    output_device_control: BoolProperty(
        name='Device Control',
        description='',
        default=False,
        options=set(),
    )
    output_device_dispenser: BoolProperty(
        name='Device Dispenser',
        description='',
        default=False,
        options=set(),
    )
    output_device_machine: BoolProperty(
        name='Device Machine',
        description='',
        default=False,
        options=set(),
    )
    output_device_terminal: BoolProperty(
        name='Device Terminal',
        description='',
        default=False,
        options=set(),
    )
    output_effect_scenery: BoolProperty(
        name='Effect Scenery',
        description='',
        default=False,
        options=set(),
    )
    output_equipment: BoolProperty(
        name='Equipment',
        description='',
        default=False,
        options=set(),
    )
    output_giant: BoolProperty(
        name='Giant',
        description='',
        default=False,
        options=set(),
    )
    output_scenery: BoolProperty(
        name='Scenery',
        description='',
        default=True,
        options=set(),
    )
    output_vehicle: BoolProperty(
        name='Vehicle',
        description='',
        default=False,
        options=set(),
    )
    output_weapon: BoolProperty(
        name='Weapon',
        description='',
        default=False,
        options=set(),
    )

classeshalo = (
    NWO_Export_Scene,
    NWO_Asset_ListItems,
    NWO_List_Add_Shared_Asset,
    NWO_List_Remove_Shared_Asset,
    NWO_ScenePropertiesGroup,
    NWO_SceneProps,
    NWO_UL_SceneProps_SharedAssets,
    NWO_SceneProps_SharedAssets,
)

def register():
    for clshalo in classeshalo:
        bpy.utils.register_class(clshalo)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.Scene.nwo = PointerProperty(type=NWO_ScenePropertiesGroup, name="NWO Scene Properties", description="Set properties for your scene")

def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    del bpy.types.Scene.nwo
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)

if __name__ == "__main__":
    register()
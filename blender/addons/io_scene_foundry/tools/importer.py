

from enum import Enum
import logging
from math import radians
import os
from pathlib import Path
import re
import time
import traceback
from uuid import uuid4
import addon_utils
import bmesh
import bpy
import bpy.props
from mathutils import Color

from bpy_extras import view3d_utils
import numpy as np

from ..managed_blam.frame_event_list import FrameEventListTag

from ..managed_blam.globals import FPARMS, GlobalsTag

from ..managed_blam import start_mb_for_import

from ..legacy.jma import JMA

from ..managed_blam.object import ObjectTag
from ..managed_blam.particle_model import ParticleModelTag
from ..managed_blam.scenario_structure_bsp import ScenarioStructureBspTag
from ..managed_blam.scenario import ScenarioTag
from ..managed_blam.animation import AnimationTag
from ..managed_blam.render_model import RenderModelTag
from ..managed_blam.physics_model import PhysicsTag
from ..managed_blam.model import ChildObject, ModelTag
from ..tools.mesh_to_marker import convert_to_marker
from ..managed_blam.bitmap import BitmapTag, clear_path_cache
from ..managed_blam.camera_track import CameraTrackTag
from ..managed_blam.collision_model import CollisionTag
from ..tools.clear_duplicate_materials import clear_duplicate_materials
from ..tools.property_apply import apply_props_material
from ..tools.shader_finder import find_shaders
from ..tools.shader_reader import tag_to_nodes
from ..constants import IDENTITY_MATRIX, OBJECT_TAG_EXTS, VALID_MESHES
from ..managed_blam.connected_material import GameFunctionType, game_functions
from .. import utils

pose_hints = 'aim', 'look', 'acc', 'steer', 'pain'
legacy_model_formats = '.jms', '.ass'
legacy_animation_formats = '.jmm', '.jma', '.jmt', '.jmz', '.jmv', '.jmw', '.jmo', '.jmr', '.jmrx'
legacy_poop_prefixes = '%', '+', '-', '?', '!', '>', '*', '&', '^', '<', '|',
legacy_frame_prefixes = "frame_", "frame ", "bip_", "bip ", "b_", "b "

global variant_items
last_used_variant = ""

zone_set_items = {"blah": "blah"}

ammo_names = "primary_ammunition", "airstrike_launch_count", "secondary_ammunition"
tether_name = "tether_distance"

### Steps for adding a new file type ###
########################################
# 1. Add the name of the file extension to formats
# 2. Add this to bl_file_extensions under the NWO_FH_Import class
# 3. Add NWO_Import.invoke condition for type and add to the filter glob
# 4. Add elif for type to NWOImporter.group_filetypes
# 5. Add import function to NWOImporter
# 6. Add an if with conditions for handling this import under NWO_Import.execute
# 7. Update scope variable to importer calls in other python files where appropriate

formats = "amf", "jms", "jma", "bitmap", "camera_track", "model", "render_model", "scenario", "scenario_structure_bsp", "particle_model", "object", "animation"

xref_tag_types = (
    ".crate",
    ".scenery",
    ".device_machine"
)

object_tag_types = (
    ".biped",
    ".crate",
    ".creature",
    ".device_control",
    ".device_dispenser",
    ".effect_scenery",
    ".equipment",
    ".giant",
    ".device_machine",
    ".projectile",
    ".scenery",
    ".spawner",
    ".sound_scenery",
    ".device_terminal",
    ".vehicle",
    ".weapon",
)

tag_files_cache = set()

def set_asset(tag_ext: str, ob: bpy.types.Object=None, sky=False):
    scene_nwo = bpy.context.scene.nwo
    
    if tag_ext in object_tag_types:
        tags_dir = utils.get_tags_path()
        scene_nwo.asset_type = 'sky' if sky else 'model'
        if ob.type != 'ARMATURE':
            return utils.print_warning(f"Tried to setup {ob.name} as an asset but it is not an armature")
        render_path = ob.nwo.node_order_source
        if not render_path.strip():
            return utils.print_warning(f"Tried to setup {ob.name} as an asset but it has not render model source path")
        
        path = Path(render_path).with_suffix("")
    
        scene_nwo.main_armature = ob
        if not sky:
            def enable_output_tag(tag_type: str):
                if Path(tags_dir, path).with_suffix(tag_type).exists():
                    tag_type_no_period = tag_type[1:]
                    setattr(scene_nwo, f"output_{tag_type_no_period}", True)
                    setattr(scene_nwo, f"template_{tag_type_no_period}", str(path.with_suffix(tag_type)))
                    
            for tag_type in object_tag_types:
                enable_output_tag(tag_type)
                
        scene_nwo.template_model = str(path.with_suffix(".model"))
        scene_nwo.template_render_model = str(path.with_suffix(".render_model"))
        if Path(tags_dir, path).with_suffix(".collision_model").exists():
            scene_nwo.template_collision_model = str(path.with_suffix(".collision_model"))
        if Path(tags_dir, path).with_suffix(".model_animation_graph").exists():
            scene_nwo.template_model_animation_graph = str(path.with_suffix(".model_animation_graph"))
            with AnimationTag(path=scene_nwo.template_model_animation_graph) as animation:
                skeleton_node_names = animation.get_nodes()
                for element in animation.block_node_usages.Elements:
                    usage = element.Fields[0].Items[element.Fields[0].Value].EnumName.replace(" ", "_")
                    node_index = element.Fields[1].Value
                    if node_index > -1:
                        node = skeleton_node_names[node_index]
                        setattr(scene_nwo, f"node_usage_{usage}", node)
                    
        if Path(tags_dir, path).with_suffix(".physics_model").exists():
            scene_nwo.template_physics_model = str(path.with_suffix(".physics_model"))
             
    else:
        match tag_ext:
            case '.scenario' | '.scenario_structure_bsp':
                scene_nwo.asset_type = 'scenario'
            case '.prefab':
                scene_nwo.asset_type = 'prefab'
            case '.particle_model':
                scene_nwo.asset_type = 'particle_model'
            case '.decorator_set':
                scene_nwo.asset_type = 'decorator_set'
            case '.camera_track':
                scene_nwo.asset_type = 'camera_track_set'

def add_function(scene: bpy.types.Scene, name: str, ob: bpy.types.Object, armature: bpy.types.Object=None) -> bool:
    func = game_functions.get(name)
    ammo = name.startswith(ammo_names)
    tether = name.startswith(tether_name)
    has_armature = armature is not None # because we handle these differently
    needs_id_prop = False
    id = None
    value_comes_from_scene = False
    value_is_bool = False
    
    if ammo or tether:
        ob[name] = 0.0
        ob.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
        return value_is_bool
    
    if func is None:
        if has_armature:
            id = armature
            needs_id_prop = armature.get(name) is None
        if needs_id_prop:
            id[name] = 0.0
            id.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
        ob[name] = 0.0
        ob.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
    else:
        if func.function_type == GameFunctionType.CONSTANT:
            return value_is_bool
        value_is_bool = isinstance(func.default_value, bool)
        value_comes_from_scene = func.attribute_type == 'VIEW_LAYER'
        if value_comes_from_scene:
            id = scene
            needs_id_prop = scene.get(name) is None
        elif has_armature:
            id = armature
            needs_id_prop = armature.get(name) is None
        
        if value_is_bool:
            if needs_id_prop:
                id[name] = func.default_value
            ob[name] = func.default_value
        else:
            if needs_id_prop:
                id[name] = float(func.default_value)
                id.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
            ob[name] = float(func.default_value)
            ob.id_properties_ui(name).update(min=0, max=1, subtype='FACTOR')
    
    if id is not None:
        result = ob.driver_add(f'["{name}"]')
        driver = result.driver
        driver.type = 'SCRIPTED'
        var = driver.variables.new()
        var.name = "var"
        var.type = 'SINGLE_PROP'
        if value_comes_from_scene:
            var.targets[0].id_type = 'SCENE'
        var.targets[0].id = id
        var.targets[0].data_path = f'["{name}"]'
        driver.expression = var.name
        
    return value_is_bool
        

class State(Enum):
    all_states = -1
    default = 0
    minor = 1
    medium = 2
    major = 3
    destroyed = 4

state_items = [
    ("all_states", "All Damage States", "Includes all damage stages"),
    ("default", "Default", "State before any damage has been taken"),
    ("minor", "Minor", "Minor Damage"),
    ("medium", "Medium", "Medium Damage"),
    ("major", "Major", "Major Damage"),
    ("destroyed", "Destroyed", "Object's destroyed state"),
]

class XREF:
    def __init__(self, object_name: str, xref_path: str, xref_name: str):
        self.preferred_type = ".crate"
        self.preferred_dir = None
        if object_name.lower().startswith("?"):
            self.preferred_type = ".device_machine"
        if xref_path:
            relative_path = utils.any_partition(xref_path, "\\data\\", True)
            relative_dir = Path(relative_path).parent
            self.preferred_dir = Path(utils.get_tags_path(), relative_dir)
        
        self.name = xref_name

class NWO_OT_ConvertScene(bpy.types.Operator):
    bl_label = "Convert Scene"
    bl_idname = "nwo.convert_scene"
    bl_description = "Converts the scene from the selected format to Foundry standard"
    
    selected_only: bpy.props.BoolProperty(
        name="Selected Only",
        description="Restrict affected objects to only those selected"
    )
    
    convert_type: bpy.props.EnumProperty(
        name="Current Type",
        description="The type of format objects are currently in",
        items=[
            ('amf', "AMF", ""),
            ('jms', "JMS/ASS", ""),
        ]
    )
    
    jms_type: bpy.props.EnumProperty(
        name="JMS Type",
        description="Whether this is a model or a scenario",
        items=[
            ("model", "Model", ""),
            ("scenario", "Scenario", "")
        ]
    )
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "selected_only")
        layout.prop(self, "convert_type", expand=True)
        if self.convert_type == "jms":
            layout.prop(self, "jms_type", expand=True)
        
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        failed = False
        if self.selected_only:
            objects_in_scope = context.selected_objects[:]
        else:
            objects_in_scope = bpy.data.objects[:]
            
        with utils.ExportManager():
            os.system("cls")
            start = time.perf_counter()
            user_cancelled = False
            if context.scene.nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                context.scene.nwo_export.show_output = False
            try:
                export_title = f"►►► FOUNDRY CONVERTER ◄◄◄"
                print(export_title, '\n')
                converter = NWOImporter(context, [], [], existing_scene=True)
                match self.convert_type:
                    case "amf":
                        converter.amf_marker_objects = []
                        converter.amf_mesh_objects = []
                        converter.amf_other_objects = []
                        converter.process_amf_objects(objects_in_scope, "")
                    case "jms":
                        if not utils.blender_toolset_installed():
                            self.report({'WARNING'}, "Cannot convert scene from JMS/ASS format, Halo Blender Toolset is not installed")
                            return {'CANCELLED'}
                        converter.jms_marker_objects = []
                        converter.jms_mesh_objects = []
                        converter.jms_other_objects = []
                        converter.process_jms_objects(objects_in_scope, "", self.jms_type == 'model')
                
            except KeyboardInterrupt:
                utils.print_warning("\nCANCELLED BY USER")
                user_cancelled = True
                failed = True
            except:
                print("FOUNDRY VERSION: ", utils.get_version_string())
                utils.print_warning(
                    "\ Import failed spectacularly. Please let the developer know: https://github.com/ILoveAGoodCrisp/Foundry/issues\n"
                )
                utils.print_error(
                    "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                )
                failed = True
                
        end = time.perf_counter()
        if user_cancelled:
            self.report({'WARNING'}, "Cancelled by user")
        elif failed:
            self.report({'WARNING'}, "Import failed")
        else:
            print("\n-----------------------------------------------------------------------")
            print(f"Completed in {utils.human_time(end - start, True)}")
            print("-----------------------------------------------------------------------\n")

        if failed:
            bpy.ops.ed.undo_push()
            bpy.ops.ed.undo()
        
        return {'FINISHED'}

class NWO_Import(bpy.types.Operator):
    bl_label = "Foundry Import"
    bl_idname = "nwo.foundry_import"
    bl_description = "Imports a variety of filetypes and sets them up for Foundry. Currently supports: AMF, JMA, JMS, ASS, bitmap tags, camera_track tags, model tags (collision & skeleton only)"
    
    @classmethod
    def poll(cls, context):
        return True
    
    filter_glob: bpy.props.StringProperty(
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    directory: bpy.props.StringProperty(
        name='Directory',
        subtype='DIR_PATH',
        options={"HIDDEN"},
    )
    
    filepath: bpy.props.StringProperty(
        name='Filepath',
        subtype='FILE_PATH',
        options={"HIDDEN"},
    )
    
    # find_shader_paths: bpy.props.BoolProperty(
    #     name="Find Shader Paths",
    #     description="Searches the tags folder after import and tries to find shader/material tags which match the name of importer materials",
    #     default=True,
    # )
    build_blender_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Builds Blender material nodes for materials based off their shader/material tags (if found)",
        default=True,
    )
    
    import_images_to_blender: bpy.props.BoolProperty(
        name="Import to Blend",
        description="Imports images into the blender after extracting bitmaps from the game",
        default=True,
    )
    images_fake_user: bpy.props.BoolProperty(
        name="Set Fake User",
        description="Sets the fake user property on imported images",
        default=True,
    )
    extracted_bitmap_format: bpy.props.EnumProperty(
        name="Image Format",
        description="Sets format to save the extracted bitmap as",
        items=[
            ("tiff", "TIFF", ""),
            ("png", "PNG", ""),
            ("jped", "JPEG", ""),
            ("bmp", "BMP", ""),
        ]
    )
    
    camera_track_animation_scale: bpy.props.FloatProperty(
        name='Animation Scale',
        default=1,
        min=1,
    )
    
    amf_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    legacy_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    scope: bpy.props.StringProperty(
        name="Scope",
        options={"HIDDEN", "SKIP_SAVE"}
    )
    
    reuse_armature: bpy.props.BoolProperty(
        name="Reuse Scene Armature",
        description="Will reuse the main blend scene armature for this model instead of importing a new one",
        default=False,
    )
    tag_render: bpy.props.BoolProperty(
        name="Import Render Geometry",
        default=True,
    )
    tag_markers: bpy.props.BoolProperty(
        name="Import Markers",
        default=True,
    )
    tag_collision: bpy.props.BoolProperty(
        name="Import Collision",
        default=False,
    )
    tag_physics: bpy.props.BoolProperty(
        name="Import Physics",
        default=False,
    )
    tag_animation: bpy.props.BoolProperty(
        name="Import Animation Graph",
        description="Imports animations, renames, and animation events. This importer is work in progress and additional functionaility is still to be added",
        options={'SKIP_SAVE'},
        default=False,
    )
    
    tag_variant: bpy.props.StringProperty(
        name="Variant",
        options={'SKIP_SAVE'},
        description="Optional field to declare a variant to import. If this field is left blank, all variants will be imported (except if this is for a cinematic, in which case the first variant will be used)"
    )
    
    import_variant_children: bpy.props.BoolProperty(
        name="Import Variant Child Objects",
        description="Imports the child objects associated with this model variant",
        options={'SKIP_SAVE'},
    )
    
    tag_state: bpy.props.EnumProperty(
        name="Model State",
        description="The damage state to import. Only valid when a variant is set",
        default=1,
        items=state_items,
    )
    
    setup_as_asset: bpy.props.BoolProperty(
        name="Setup as Asset",
        description="Updates the scene asset settings so that this object can be immediately reimported into the game"
    )
    
    tag_zone_set: bpy.props.StringProperty(
        name="Zone Set",
        options={'SKIP_SAVE'},
        description="Optional field to declare a zone set to import. This will limit the scope of imported BSPs to those within the zone set. If this field is left blank, all BSPs will be imported"
    )
    
    tag_bsp_render_only: bpy.props.BoolProperty(
        name="Render Geometry Only",
        description="Skips importing bsp data like collision and portals. Use this if you aren't importing the BSP back into the game"
    )
    
    tag_animation_filter: bpy.props.StringProperty(
        name="Animation Filter",
        options={'SKIP_SAVE'},
        description="Filter for the animations to import. Animations that don't contain the specified strings (space or colon delimited) will be skipped"
    )
    
    graph_import_animations: bpy.props.BoolProperty(
        name="Import Animations",
        description="Imports animations from the graph. Currently the root movement element of base movement animations is unsupported and overlay rotations do not import correctly"
    )
    graph_generate_renames: bpy.props.BoolProperty(
        name="Generate Animation Renames",
        description="Parses the animation mode n state graph to work out which graph elements were imported as renames and adds these to relevant animations in this blend scene"
    )
    graph_import_events: bpy.props.BoolProperty(
        name="Import Animation Events",
        description="This currently only supports importing of frame events"
    )
    graph_import_ik_chains: bpy.props.BoolProperty(
        name="Import IK Chains",
        description="Sets up the IK chains graph tag block in blender"
    )
    
    import_fp_arms: bpy.props.EnumProperty(
        name="FP Arms",
        description="Imports the First person arms along with the weapon and joins the skeletons",
        items=[
            ('NONE', "None", "Don't import first person arms"),
            ('SPARTAN', "Spartan", "Imports the Spartan first person arms"),
            ('ELITE', "Elite", "Imports the ELITE first person arms")
        ]
    )
    
    legacy_type: bpy.props.EnumProperty(
        name="JMS/ASS Type",
        description="Whether the importer should try to import a JMS/ASS file as a model, or bsp. Auto will determine this based on current asset type and contents of the JMS/ASS file",
        items=[
            ("auto", "Auto", ""),
            ("model", "Model", ""),
            ("bsp", "BSP", ""),
        ]
    )
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always Extract Bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not",
        options=set(),
    )
    
    import_as_instanced_collection: bpy.props.BoolProperty(
        name="Import as Game Marker",
        description="Imports the object as a game marker with an instanced collection",
        default=True
    )
    
    from_vert_normals: bpy.props.BoolProperty(
        name="Store Model Vertex Normals",
        description="Stores a models vertex normals so that it can be reimported in game with the exact same vertex order. This is done automatically for PCA meshes, this option just applies the same to everything. Any edits to meshes with this setting will probably break normals on export"
    )
    
    place_at_mouse : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    mouse_x : bpy.props.FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
    mouse_y : bpy.props.FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    def execute(self, context):
        failed = False
        filepaths = [self.directory + f.name for f in self.files]
        if self.filepath and self.filepath not in filepaths:
            filepaths.append(self.filepath)
        start = time.perf_counter()
        imported_objects = []
        imported_actions = []
        armature = None
        starting_materials = bpy.data.materials[:]
        for_cinematic = context.scene.nwo.asset_type == 'cinematic'
        self.anchor = None
        self.nothing_imported = False
        self.user_cancelled = False
        utils.set_object_mode(context)
        global last_used_variant
        last_used_variant = self.tag_variant
        if self.tag_variant == "all_variants":
            self.tag_variant = ""
        if self.tag_zone_set == "all_zone_sets":
            self.tag_zone_set = ""
            
        if self.always_extract_bitmaps:
            clear_path_cache()
            
        set_animation_index = context.scene.nwo.asset_type in {'model', 'animation'}
            
        with utils.ExportManager():
            os.system("cls")
            if not self.place_at_mouse and context.scene.nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                context.scene.nwo_export.show_output = False
            try:
                export_title = f"►►► FOUNDRY IMPORTER ◄◄◄"
                print(export_title, '\n')
                scope_list = []
                if self.scope:
                    scope_list = self.scope.split(',')
                importer = NWOImporter(context, filepaths, scope_list)
                
                if self.place_at_mouse:
                    tag_path = filepaths[0]
                    marker = bpy.data.objects.new(name=Path(tag_path).with_suffix("").name, object_data=None)
                    marker.nwo.marker_type = '_connected_geometry_marker_type_game_instance'
                    marker.nwo.marker_game_instance_tag_name = utils.relative_path(tag_path)
                    marker.nwo.marker_game_instance_tag_variant_name = self.tag_variant
                    
                    marker.matrix_world = utils.matrix_from_mouse(self.mouse_x, self.mouse_y)
                
                
                if 'amf' in importer.extensions and self.amf_okay:
                    amf_module_name = utils.amf_addon_installed()
                    amf_addon_enabled = addon_utils.check(amf_module_name)[0]
                    if not amf_addon_enabled:
                        addon_utils.enable(amf_module_name)
                    amf_files = importer.sorted_filepaths["amf"]
                    imported_amf_objects = importer.import_amf_files(amf_files, importer.scale_factor)
                    if not amf_addon_enabled:
                        addon_utils.disable(amf_module_name)
                    if imported_amf_objects:
                        imported_objects.extend(imported_amf_objects)
                    
                    if importer.to_x_rot:
                        utils.transform_scene(context, 1, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_amf_objects, actions=[])
                        
                if self.legacy_okay and 'jms'  in importer.extensions:
                    toolset_addon_enabled = addon_utils.check('io_scene_halo')[0]
                    if not toolset_addon_enabled:
                        addon_utils.enable('io_scene_halo')
                    jms_files = importer.sorted_filepaths["jms"]
                    
                    arm = None
                    
                    scene_nwo = context.scene.nwo
                    if scene_nwo.main_armature:
                        arm = scene_nwo.main_armature
                    else:
                        arm = utils.get_rig_prioritize_active(context)
                    
                    if arm is not None:
                        arm.hide_set(False)
                        arm.hide_select = False
                        utils.set_active_object(arm)
                        
                    # Transform Scene so it's ready for JMS files
                    if importer.needs_scaling:
                        if arm is not None:
                            utils.transform_scene(context, (1 / importer.scale_factor), importer.to_x_rot, context.scene.nwo.forward_direction, 'x', objects=[arm], actions=[])
         
                    imported_jms_objects = importer.import_jms_files(jms_files, self.legacy_type)

                    if imported_jms_objects:
                        imported_objects.extend(imported_jms_objects)
                    if not toolset_addon_enabled:
                        addon_utils.disable('io_scene_halo')

                    if importer.needs_scaling:
                        if arm is None:
                            utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_jms_objects, actions=[])
                        else:
                            utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=[arm] + imported_jms_objects, actions=[])
                            
                if 'jma' in importer.extensions:
                    jma_files = importer.sorted_filepaths["jma"]
                    arm = None
                    arm = utils.get_rig_prioritize_active(context)
                        
                    if arm is None:
                        utils.print_warning("No armature in scene, cannot import JMA files")
                    else:
                        if importer.needs_scaling:
                            utils.transform_scene(context, (1 / importer.scale_factor), importer.to_x_rot, context.scene.nwo.forward_direction, 'x', objects=[arm], actions=[])
                        imported_jma_animations = importer.import_jma_files(jma_files, arm)
                        if imported_jma_animations:
                            imported_actions.extend(imported_jma_animations)
                            
                        if importer.needs_scaling:
                            utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=[arm], actions=imported_jma_animations)
                            
                        if imported_jma_animations and set_animation_index:
                            context.scene.nwo.active_animation_index = len(context.scene.nwo.animations) - 1
                        
                if 'model' in importer.extensions:
                    importer.tag_render = self.tag_render
                    importer.tag_markers = self.tag_markers
                    importer.tag_collision = self.tag_collision
                    importer.tag_physics = self.tag_physics
                    importer.tag_animation = self.tag_animation
                    importer.tag_variant = self.tag_variant.lower()
                    importer.tag_state = State[self.tag_state].value
                    importer.tag_animation_filter = self.tag_animation_filter
                    importer.graph_import_animations = self.graph_import_animations
                    importer.graph_generate_renames = self.graph_generate_renames
                    importer.graph_import_events = self.graph_import_events
                    importer.graph_import_ik_chains = self.graph_import_ik_chains
                    importer.import_variant_children = self.import_variant_children
                    importer.setup_as_asset = self.setup_as_asset
                    model_files = importer.sorted_filepaths["model"]
                    existing_armature = None
                    if self.reuse_armature:
                        existing_armature = utils.get_rig_prioritize_active(context)
                        if existing_armature is not None:
                            arm_pose = existing_armature.data.pose_position
                            existing_armature.data.pose_position = 'REST'
                            context.view_layer.update()
                            if importer.needs_scaling:
                                utils.transform_scene(context, (1 / importer.scale_factor), importer.to_x_rot, context.scene.nwo.forward_direction, 'x', objects=[existing_armature], actions=[])
                            
                    imported_model_objects, imported_animations = importer.import_models(model_files, existing_armature)
                    
                    if importer.needs_scaling:
                        utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_model_objects, actions=imported_animations)
                        
                    if existing_armature is not None:
                        existing_armature.data.pose_position = arm_pose
                    
                    if imported_animations and set_animation_index:
                        context.scene.nwo.active_animation_index = len(context.scene.nwo.animations) - 1
                        
                    imported_objects.extend(imported_model_objects)
                    
                    
                elif 'object' in importer.extensions:
                    if self.place_at_mouse:
                        game_object_cache = {(c.nwo.game_object_path, c.nwo.game_object_variant): c for c in utils.get_foundry_storage_scene().collection.children if c.nwo.game_object_path}
                        key = marker.nwo.marker_game_instance_tag_name, marker.nwo.marker_game_instance_tag_variant_name
                        game_object_collection = game_object_cache.get(key)
                        imported_object_objects = []
                        if game_object_collection is None:
                            game_object_collection = importer.import_object(marker, None)
                            merge_collection(game_object_collection)
                            imported_object_objects = game_object_collection.all_objects
                            context.scene.collection.children.unlink(game_object_collection)
                            utils.get_foundry_storage_scene().collection.children.link(game_object_collection)
                            game_object_collection.nwo.game_object_path, game_object_collection.nwo.game_object_variant = key
                            
                        marker.instance_type = 'COLLECTION'
                        marker.instance_collection = game_object_collection
                        marker.nwo.marker_instance = True
                        imported_objects.append(marker)
                        context.collection.objects.link(marker)
                        
                        if imported_object_objects and importer.needs_scaling:
                            utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_object_objects, actions=[])
                            
                        marker.select_set(True)
                        context.view_layer.objects.active = marker
                        
                    else:
                        importer.tag_render = self.tag_render
                        importer.tag_markers = self.tag_markers
                        importer.tag_collision = self.tag_collision
                        importer.tag_physics = self.tag_physics
                        importer.tag_animation = self.tag_animation
                        importer.tag_variant = self.tag_variant.lower()
                        importer.tag_state = State[self.tag_state].value
                        importer.tag_animation_filter = self.tag_animation_filter
                        importer.graph_import_animations = self.graph_import_animations
                        importer.graph_generate_renames = self.graph_generate_renames
                        importer.graph_import_events = self.graph_import_events
                        importer.graph_import_ik_chains = self.graph_import_ik_chains
                        importer.import_variant_children = self.import_variant_children
                        importer.setup_as_asset = self.setup_as_asset
                        importer.import_fp_arms = FPARMS[self.import_fp_arms]
                        importer.from_vert_normals = self.from_vert_normals
                        object_files = importer.sorted_filepaths["object"]
                        existing_armature = None
                        if self.reuse_armature:
                            existing_armature = utils.get_rig_prioritize_active(context)
                            if existing_armature is not None:
                                arm_pose = existing_armature.data.pose_position
                                existing_armature.data.pose_position = 'REST'
                                context.view_layer.update()
                                if importer.needs_scaling:
                                    utils.transform_scene(context, (1 / importer.scale_factor), importer.to_x_rot, context.scene.nwo.forward_direction, 'x', objects=[existing_armature], actions=[])
                        
                        imported_object_objects, imported_animations = importer.import_object(object_files, existing_armature)
                        if importer.needs_scaling:
                            utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_object_objects, actions=imported_animations)
                            
                        if existing_armature is not None:
                            existing_armature.data.pose_position = arm_pose
                            
                        imported_objects.extend(imported_object_objects)
                        
                        if imported_animations and set_animation_index:
                            context.scene.nwo.active_animation_index = len(context.scene.nwo.animations) - 1
                    
                elif 'render_model' in importer.extensions:
                    importer.tag_render = self.tag_render
                    importer.tag_markers = self.tag_markers
                    importer.from_vert_normals = self.from_vert_normals
                    render_model_files = importer.sorted_filepaths["render_model"]
                    existing_armature = None
                    if self.reuse_armature:
                        existing_armature = utils.get_rig_prioritize_active(context)
                        if importer.needs_scaling:
                            utils.transform_scene(context, (1 / importer.scale_factor), importer.to_x_rot, context.scene.nwo.forward_direction, 'x', objects=[existing_armature], actions=[])
                    
                    imported_render_objects = []
                    for file in render_model_files:
                        print(f'Importing Render Model Tag: {Path(file).with_suffix("").name} ')
                        render_model_objects, armature = importer.import_render_model(file, context.scene.collection, existing_armature, set(), skip_print=True)
                        imported_render_objects.extend(render_model_objects)
                        
                    if importer.needs_scaling:
                        utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_render_objects, actions=[])
                        
                    imported_objects.extend(imported_render_objects)
                    
                elif 'animation' in importer.extensions:
                    context.scene.render.fps = 30
                    importer.tag_animation_filter = self.tag_animation_filter
                    importer.graph_import_animations = self.graph_import_animations
                    importer.graph_generate_renames = self.graph_generate_renames
                    importer.graph_import_events = self.graph_import_events
                    importer.graph_import_ik_chains = self.graph_import_ik_chains
                    animation_files = importer.sorted_filepaths['animation']
                    if context.object and context.object.type == 'ARMATURE':
                        existing_armature = context.object
                    else:
                        existing_armature = utils.get_rig_prioritize_active(context)
                    if existing_armature is None:
                        utils.print_warning("No armature found, cannot import animations. Ensure you have the appropriate armature for this animation graph import and selected")
                    else:
                        arm_pose = existing_armature.data.pose_position
                        existing_armature.data.pose_position = 'REST'
                        context.view_layer.update()
                        good_to_go = True
                        render_model = existing_armature.nwo.node_order_source
                        if not render_model.strip():
                            utils.print_warning(f"Armature [{armature.name}] has no render model set. Set this in Foundry object properties")
                            good_to_go = False
                        full_render_path = Path(utils.get_tags_path(), utils.relative_path(render_model))
                        if not full_render_path.exists():
                            utils.print_warning(f"Armature [{existing_armature.name}] has invalid render model set (it does not exist) [{full_render_path}]")
                            good_to_go = False
                        
                        if good_to_go:
                            if importer.needs_scaling:
                                utils.transform_scene(context, (1 / importer.scale_factor), importer.to_x_rot, context.scene.nwo.forward_direction, 'x', objects=[existing_armature], actions=[])
                            
                            imported_animations = []
                            for file in animation_files:
                                print(f'Importing Animation Graph Tag: {Path(file).with_suffix("").name} ')
                                imported_animations.extend(importer.import_animation_graph(file, existing_armature, full_render_path))
                                
                            if importer.needs_scaling:
                                utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=[existing_armature], actions=imported_animations)
                            
                        if imported_animations and set_animation_index:
                            context.scene.nwo.active_animation_index = len(context.scene.nwo.animations) - 1
                                    
                        existing_armature.data.pose_position = arm_pose
                    
                if 'scenario' in importer.extensions:
                    importer.tag_zone_set = self.tag_zone_set
                    importer.tag_bsp_render_only = self.tag_bsp_render_only
                    importer.setup_as_asset = self.setup_as_asset
                    scenario_files = importer.sorted_filepaths["scenario"]
                    imported_scenario_objects = importer.import_scenarios(scenario_files)
                    if importer.needs_scaling:
                        utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_scenario_objects, actions=[])
                        
                    imported_objects.extend(imported_scenario_objects)
                    
                    if for_cinematic:
                        if not context.scene.nwo.cinematic_scenario and scenario_files:
                            context.scene.nwo.cinematic_scenario = scenario_files[0]
                            if self.tag_zone_set:
                                context.scene.nwo.cinematic_zone_set = self.tag_zone_set
                        self.link_anchor(context, imported_scenario_objects)
                    
                elif 'scenario_structure_bsp' in importer.extensions:
                    importer.tag_bsp_render_only = self.tag_bsp_render_only
                    bsp_files = importer.sorted_filepaths["scenario_structure_bsp"]
                    imported_bsp_objects = []
                    for bsp in bsp_files:
                        bsp_objects = importer.import_bsp(bsp)
                        imported_bsp_objects.extend(bsp_objects)
                    if importer.needs_scaling:
                        utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_bsp_objects, actions=[])
                        
                    imported_objects.extend(imported_bsp_objects)
                    
                    if for_cinematic:
                        self.link_anchor(context, imported_bsp_objects)
                    
                if 'particle_model' in importer.extensions:
                    particle_model_files = importer.sorted_filepaths["particle_model"]
                    imported_particle_model_objects = []
                    for file in particle_model_files:
                        particle_objects = importer.import_particle_model(file)
                        imported_particle_model_objects.extend(particle_objects)
                    if importer.needs_scaling:
                        utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_particle_model_objects, actions=[])
                        
                    imported_objects.extend(imported_particle_model_objects)
                    
                # for ob in importer.to_cursor_objects:
                #     ob.matrix_world = context.scene.cursor.matrix
                
                setup_materials(context, importer, starting_materials, imported_objects, self.build_blender_materials, self.always_extract_bitmaps, importer.emissive_meshes)
                        
                if 'bitmap' in importer.extensions:
                    bitmap_files = importer.sorted_filepaths["bitmap"]
                    if not bitmap_files:
                        self.nothing_imported = True
                    else:
                        extracted_bitmaps = importer.extract_bitmaps(bitmap_files, self.extracted_bitmap_format)
                        if self.import_images_to_blender:
                            importer.load_bitmaps(extracted_bitmaps, self.images_fake_user)
                                    
                        self.report({'INFO'}, f"Extracted {'and imported' if self.import_images_to_blender else ''} {len(bitmap_files)} bitmaps")
                        
                if 'camera_track' in importer.extensions:
                    camera_track_files = importer.sorted_filepaths["camera_track"]
                    cameras, actions = importer.import_camera_tracks(camera_track_files, self.camera_track_animation_scale)
                    if importer.needs_scaling:
                        utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=cameras, actions=actions)
                    
                    if context.scene.nwo.animations:
                        context.scene.nwo.active_animation_index = len(context.scene.nwo.animations) - 1
                        
            except KeyboardInterrupt:
                utils.print_warning("\nIMPORT CANCELLED BY USER")
                self.user_cancelled = True
                failed = True
            except Exception as e:
                failed = True
                if isinstance(e, RuntimeError):
                    # logging.error(traceback.format_exc())
                    utils.print_warning(traceback.format_exception_only(e)[0][14:])
                else:
                    utils.print_error("\n\nException hit. Please include in report\n")
                    logging.error(traceback.format_exc())
                    print("FOUNDRY VERSION: ", utils.get_version_string())
                    utils.print_warning(
                        "\ Import failed spectacularly. Please let the developer know: https://github.com/ILoveAGoodCrisp/Foundry/issues\n"
                    )
                    utils.print_error(
                        "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
                    )
                    failed = True

        
        end = time.perf_counter()
        if self.user_cancelled:
            self.report({'WARNING'}, "Import cancelled by user")
        elif failed:
            self.report({'WARNING'}, "Import failed")
        elif self.nothing_imported:
            print("No Folders/Filepaths supplied")
            self.report({'WARNING'}, "Nothing imported. No filepaths/folders supplied")
        else:
            print(
                "\n-----------------------------------------------------------------------"
            )
            print(f"Import Completed in {utils.human_time(end - start)}")

            print(
                "-----------------------------------------------------------------------\n"
            )
        
        if failed:
            bpy.ops.ed.undo_push()
            bpy.ops.ed.undo()
        
        return {'FINISHED'}
    
    def link_anchor(self, context, objects):
        if self.anchor is None:
            if context.scene.nwo.cinematic_anchor is None:
                self.anchor = bpy.data.objects.new(name="Anchor", object_data=None)
                context.scene.collection.objects.link(self.anchor)
                context.scene.nwo.cinematic_anchor = self.anchor
            else:
                self.anchor = context.scene.nwo.cinematic_anchor
        for ob in objects:
            if not ob.parent:
                ob.parent = self.anchor
    
    def invoke(self, context, event):
        # skip_fileselect = False
        # if self.directory or self.files or self.filepath:
        #     skip_fileselect = True
        #     self.filter_glob = "*.bitmap;*.camera_track;*.model;*.scenario;*.scen*_bsp;*.render_model"
        # else:
        if 'bitmap' in self.scope:
            self.directory = utils.get_tags_path()
        elif 'camera_track' in self.scope:
            cameras_dir = Path(utils.get_tags_path(), 'camera')
            if cameras_dir.exists():
                self.directory = str(cameras_dir)
            else:
                self.directory = utils.get_tags_path()
        else:
            self.directory = ''
            self.filepath = ''
            
        self.filename = ''
        if not self.scope:
            self.filter_glob = "*"
        else:
            if 'bitmap' in self.scope:
                self.directory = utils.get_tags_path()
                self.filter_glob += "*.bitmap;"
            if 'camera_track' in self.scope:
                self.filter_glob += '*.camera_track;'
            if 'model' in self.scope:
                self.filter_glob += '*.model;'
            if 'render_model' in self.scope:
                self.filter_glob += '*.render_model;'
            if 'scenario' in self.scope:
                self.filter_glob += '*.scenario;'
            if 'scenario_structure_bsp' in self.scope:
                self.filter_glob += '*.scen*_bsp;'
            if 'particle_model' in self.scope:
                self.filter_glob += '*.particle_model;'
            if 'object' in self.scope:
                self.filter_glob += '*.biped;*.crate;*.creature;*.d*_control;*.d*_dispenser;*.e*_scenery;*.equipment;*.giant;*.d*_machine;*.projectile;*.scenery;*.spawner;*.sound_scenery;*.d*_terminal;*.vehicle;*.weapon;'
            if 'animation' in self.scope:
                self.filter_glob += '*.mod*_*_graph;'
                    
            if utils.amf_addon_installed() and 'amf' in self.scope:
                self.amf_okay = True
                self.filter_glob += "*.amf;"
            if utils.blender_toolset_installed() and 'jms' in self.scope:
                self.legacy_okay = True
                self.filter_glob += '*.jms;*.ass;'
            if 'jma' in self.scope:
                self.legacy_okay = True
                self.filter_glob += '*.jmm;*.jma;*.jmt;*.jmz;*.jmv;*.jmw;*.jmo;*.jmr;*.jmrx;'
            
        # if skip_fileselect:
        #     return self.execute(context)
        
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.25
        
        if not self.scope or ('amf' in self.scope or 'jms' in self.scope or 'model' in self.scope or 'object' in self.scope):
            box = layout.box()
            box.label(text="Model Settings")
            tag_type = 'material' if utils.is_corinth(context) else 'shader'
            # box.prop(self, 'find_shader_paths', text=f"Find {tag_type.capitalize()} Tag Paths")
            box.prop(self, 'build_blender_materials', text=f"Blender Materials from {tag_type.capitalize()} Tags")
            box.prop(self, 'always_extract_bitmaps')
                
        if not self.scope or ('model' in self.scope) or ('object' in self.scope):
            box = layout.box()
            box.label(text='Model Tag Settings')
            box.prop(self, 'reuse_armature')
            box.prop(self, 'tag_render')
            box.prop(self, 'tag_markers')
            box.prop(self, 'tag_collision')
            box.prop(self, 'tag_physics')
            box.prop(self, 'tag_animation')
            box.prop(self, 'tag_variant')
            box.prop(self, 'tag_state')
            if self.tag_variant and self.tag_markers:
                box.prop(self, "import_variant_children")
                
            box.prop(self, "setup_as_asset")
            box.prop(self, "from_vert_normals")
            box.prop(self, "import_fp_arms", text="FP Arms (Weapon Only)")
            
            if self.tag_animation:
                box.prop(self, "tag_animation_filter")
                box.prop(self, "graph_import_animations")
                box.prop(self, "graph_generate_renames")
                box.prop(self, "graph_import_events")
                box.prop(self, "graph_import_ik_chains")
            
        if not self.scope or ('scenario' in self.scope) or ('scenario_structure_bsp' in self.scope):
            box = layout.box()
            tag_type = 'material' if utils.is_corinth(context) else 'shader'
            box.label(text='Scenario Tag Settings')
            box.prop(self, 'tag_zone_set')
            box.prop(self, 'tag_bsp_render_only')
            box.prop(self, 'build_blender_materials', text=f"Blender Materials from {tag_type.capitalize()} Tags")
            box.prop(self, 'always_extract_bitmaps')
            if not self.scope or ('scenario' in self.scope):
                box.prop(self, "setup_as_asset")
        
        if not self.scope or 'jms' in self.scope:
            box = layout.box()
            box.label(text="JMS/ASS Settings")
            box.prop(self, "legacy_type")
        
        if not self.scope or ('bitmap' in self.scope):
            box = layout.box()
            box.label(text="Bitmap Settings")
            box.use_property_split = True
            box.prop(self, 'extracted_bitmap_format')
            box.prop(self, 'import_images_to_blender')
            if self.import_images_to_blender:
                box.prop(self, 'images_fake_user')
                
        if not self.scope or ('camera_track' in self.scope):
            box = layout.box()
            box.label(text='Camera Track Settings')
            box.prop(self, 'camera_track_animation_scale')
            box.prop(self, "setup_as_asset")
            
class JMSMaterialSlot:
    def __init__(self, slot: bpy.types.MaterialSlot):
        self.material = slot.material
        self.index = slot.slot_index
        self.name = slot.material.name
        self._material_props_from_name()
        self._material_props_from_ui()
        
        if self.water_surface:
            self.mesh_type = '_connected_geometry_mesh_type_water_surface'
        else:
            self.mesh_type = self._mesh_type_from_special_name()
        
    def _mesh_type_from_special_name(self):
        name = self.material.name
        if name.startswith('+portal') or self.portal_one_way or self.portal_vis_blocker:
            return 'portal'
        elif name.startswith('+seam') and not name.startswith('+seams'):
            return 'seam'
        elif name.startswith('+soft_ceiling'):
            return 'soft_ceiling'
        elif name.startswith('+soft_kill'):
            return 'soft_kill'
        elif name.startswith('+slip_surface'):
            return 'slip_surface'
        elif self.fog_plane:
            return 'fog'
        elif self.water_surface:
            return 'water_surface'
        
        return 'default'
            
    def _material_props_from_ui(self):
        self.two_sided = self.material.ass_jms.two_sided or self.two_sided
        self.transparent_one_sided = self.material.ass_jms.transparent_1_sided or self.transparent_one_sided
        self.transparent_two_sided = self.material.ass_jms.transparent_2_sided or self.transparent_two_sided
        self.render_only = self.material.ass_jms.render_only or self.render_only
        self.collision_only = self.material.ass_jms.collision_only or self.collision_only
        self.sphere_collision_only = self.material.ass_jms.sphere_collision_only or self.sphere_collision_only
        self.fog_plane = self.material.ass_jms.fog_plane or self.fog_plane
        self.ladder = self.material.ass_jms.ladder or self.ladder
        self.breakable = self.material.ass_jms.breakable or self.breakable
        self.ai_deafening = self.material.ass_jms.ai_deafening or self.ai_deafening
        self.no_shadow = self.material.ass_jms.no_shadow or self.no_shadow
        self.shadow_only = self.material.ass_jms.shadow_only or self.shadow_only
        self.lightmap_only = self.material.ass_jms.lightmap_only or self.lightmap_only
        self.precise = self.material.ass_jms.precise or self.precise
        self.portal_one_way = self.material.ass_jms.portal_1_way or self.portal_one_way
        self.portal_door = self.material.ass_jms.portal_door or self.portal_door
        self.portal_vis_blocker = self.material.ass_jms.portal_vis_blocker or self.portal_vis_blocker
        self.ignored_by_lightmaps = self.material.ass_jms.ignored_by_lightmaps or self.ignored_by_lightmaps
        self.blocks_sound = self.material.ass_jms.blocks_sound or self.blocks_sound
        self.decal_offset = self.material.ass_jms.decal_offset or self.decal_offset
        self.water_surface = self.material.ass_jms.water_surface or self.water_surface
        self.slip_surface = self.material.ass_jms.slip_surface
        # lightmap
        if self.material.ass_jms.lightmap_res != 1:
            self.lightmap_resolution_scale = utils.clamp(int(float(self.material.ass_jms.lightmap_res) * 3), 1, 7)
        if self.material.ass_jms.additive_transparency != Color((0.0, 0.0, 0.0)):
            self.lightmap_additive_transparency = self.material.ass_jms.additive_transparency
        if self.material.ass_jms.two_sided_transparent_tint != Color((0.0, 0.0, 0.0)):
            self.lightmap_translucency_tint_color = self.material.ass_jms.additive_transparency
            
        self.lightmap_transparency_override = self.material.ass_jms.override_lightmap_transparency
            
        # Emissive
        self.emissive_power = None
        self.emissive_color = None
        self.emissive_quality = None
        self.emissive_per_unit = None
        self.emissive_shader_gel = None
        self.emissive_focus = None
        self.emissive_attenuation = None
        self.emissive_attenuation_falloff = None
        self.emissive_attenuation_cutoff = None
        self.emissive_frustum_blend = None
        self.emissive_frustum_falloff = None
        self.emissive_frustum_cutoff = None
        
        if self.material.ass_jms.power > 0:
            self.emissive_power = self.material.ass_jms.power
            self.emissive_color = self.material.ass_jms.color
            self.emissive_quality = self.material.ass_jms.quality
            self.emissive_per_unit = self.material.ass_jms.power_per_unit_area
            self.emissive_shader_gel = self.material.ass_jms.use_shader_gel
            self.emissive_focus = radians(self.material.ass_jms.emissive_focus * 180)
            self.emissive_attenuation = self.material.ass_jms.attenuation_enabled
            if self.emissive_attenuation:
                self.emissive_attenuation_falloff = self.material.ass_jms.falloff_distance
                self.emissive_attenuation_cutoff = self.material.ass_jms.cutoff_distance
            else:
                self.emissive_attenuation_falloff = 0
                self.emissive_attenuation_cutoff = 0
        
    def _material_props_from_name(self):
        name = self.material.name
        self.two_sided = '%' in name
        self.transparent_one_sided = '#' in name
        self.transparent_two_sided = '?' in name
        self.render_only = '!' in name
        self.collision_only = '@' in name
        self.sphere_collision_only = '*' in name
        self.fog_plane = '$' in name
        self.ladder = '^' in name
        self.breakable = '-' in name
        self.ai_deafening = '&' in name
        self.no_shadow = '=' in name
        self.lightmap_only = ';' in name
        self.shadow_only = False
        self.precise = ')' in name
        self.portal_one_way = '<' in name
        self.portal_door = '|' in name
        self.portal_vis_blocker = '~' in name
        self.ignored_by_lightmaps = '{' in name
        self.blocks_sound = '}' in name
        self.decal_offset = '[' in name
        self.water_surface = "'" in name
        self.slip_surface = False
        
        # lighting props
        self.lightmap_resolution_scale = None
        self.lightmap_translucency_tint_color = None
        self.lightmap_additive_transparency = None
        self.lightmap_transparency_override = None
        
        parts = name.split()
        if len(parts) > 1 and (parts[0].startswith(utils.legacy_lightmap_prefixes) or parts[-1].startswith(utils.legacy_lightmap_prefixes)):
            pattern = r'(' + '|'.join(utils.legacy_lightmap_prefixes) + r')(\d+\.?\d*)'
            matches = re.findall(pattern, name)
            for match_groups in matches:
                if len(match_groups) <= 1:
                    continue
                match match_groups[0]:
                    # Only handling lightmap res currently
                    case 'lm:':
                        self.lightmap_resolution_scale = utils.clamp(int(float(match_groups[1]) * 3), 1, 7)
        
    def __eq__(self, __value: 'JMSMaterialSlot') -> bool:
        if not isinstance(__value, self.__class__):
            return False
        if self.two_sided != __value.two_sided:
            return False
        if self.transparent_one_sided != __value.transparent_one_sided:
            return False
        if self.transparent_two_sided != __value.transparent_two_sided:
            return False
        if self.render_only != __value.render_only:
            return False
        if self.collision_only != __value.collision_only:
            return False
        if self.sphere_collision_only != __value.sphere_collision_only:
            return False
        if self.fog_plane != __value.fog_plane:
            return False
        if self.ladder != __value.ladder:
            return False
        if self.breakable != __value.breakable:
            return False
        if self.ai_deafening != __value.ai_deafening:
            return False
        if self.no_shadow != __value.no_shadow:
            return False
        if self.shadow_only != __value.shadow_only:
            return False
        if self.lightmap_only != __value.lightmap_only:
            return False
        if self.precise != __value.precise:
            return False
        if self.portal_one_way != __value.portal_one_way:
            return False
        if self.portal_door != __value.portal_door:
            return False
        if self.portal_vis_blocker != __value.portal_vis_blocker:
            return False
        if self.ignored_by_lightmaps != __value.ignored_by_lightmaps:
            return False
        if self.blocks_sound != __value.blocks_sound:
            return False
        if self.decal_offset != __value.decal_offset:
            return False
        if self.water_surface != __value.water_surface:
            return False
        if self.slip_surface != __value.slip_surface:
            return False
        
        if self.lightmap_resolution_scale != __value.lightmap_resolution_scale: return False
        if self.lightmap_translucency_tint_color != __value.lightmap_translucency_tint_color: return False
        if self.lightmap_additive_transparency != __value.lightmap_additive_transparency: return False
        if self.lightmap_transparency_override != __value.lightmap_transparency_override: return False
        
        if self.emissive_power != __value.emissive_power: return False
        if self.emissive_color != __value.emissive_color: return False
        if self.emissive_quality != __value.emissive_quality: return False
        if self.emissive_per_unit != __value.emissive_per_unit: return False
        if self.emissive_shader_gel != __value.emissive_shader_gel: return False
        if self.emissive_focus != __value.emissive_focus: return False
        if self.emissive_attenuation != __value.emissive_attenuation: return False
        if self.emissive_attenuation_falloff != __value.emissive_attenuation_falloff: return False
        if self.emissive_attenuation_cutoff != __value.emissive_attenuation_cutoff: return False
        if self.emissive_frustum_blend != __value.emissive_frustum_blend: return False
        if self.emissive_frustum_falloff != __value.emissive_frustum_falloff: return False
        if self.emissive_frustum_cutoff != __value.emissive_frustum_cutoff: return False
        
        return True


class NWOImporter:
    def __init__(self, context, filepaths=[], scope=[], existing_scene=False):
        self.filepaths = filepaths
        self.context = context
        self.mesh_objects = []
        self.marker_objects = []
        self.extensions = set()
        self.existing_scene = existing_scene
        self.apply_materials = utils.get_prefs().apply_materials
        self.prefix_setting = utils.get_prefs().apply_prefix
        self.corinth = utils.is_corinth(context)
        self.arm = utils.get_rig_prioritize_active(context)
        self.tag_render = False
        self.tag_markers = False
        self.tag_collision = False
        self.tag_physics = False
        self.tag_animation = False
        self.graph_import_animations = False
        self.graph_generate_renames = False
        self.graph_import_events = False
        self.graph_import_ik_chains = False
        self.import_fp_arms = FPARMS.NONE
        # self.to_cursor_objects = set()
        self.tag_variant = ""
        self.tag_state = -1
        self.tag_zone_set = ""
        self.tag_bsp_render_only = False
        self.tag_animation_filter = ""
        self.import_variant_children = False
        self.setup_as_asset = False
        self.for_cinematic = context.scene.nwo.asset_type == "cinematic"
        self.obs_for_props = {}
        self.fp_arms_imported = False
        if filepaths:
            self.sorted_filepaths = self.group_filetypes(scope)
        else:
            self.sorted_filepaths = []
        
        self.scale_factor = 0.03048 if context.scene.nwo.scale == 'blender' else 1
        self.to_x_rot = utils.rotation_diff_from_forward(context.scene.nwo.forward_direction, 'x')
        self.from_x_rot = utils.rotation_diff_from_forward('x', context.scene.nwo.forward_direction)
        self.needs_scaling = self.scale_factor != 1 or self.to_x_rot
        self.from_vert_normals = False
        
        self.emissive_meshes = set()
    
    def group_filetypes(self, scope):
        if scope:
            filetype_dict = {ext: {} for ext in scope}
        else:
            filetype_dict = {ext: {} for ext in formats}
        # Search for folders first and add their files to filepaths
        folders = [path for path in self.filepaths if os.path.isdir(path)]
        for f in folders:
            for root, _, files in os.walk(f):
                for file in files:
                    self.filepaths.append(os.path.join(root, file))
                    
        valid_exts = filetype_dict.keys()
            
        for path in self.filepaths:
            if 'amf' in valid_exts and path.lower().endswith('.amf'):
                self.extensions.add('amf')
                filetype_dict["amf"][path] = None
            elif 'jms' in valid_exts and path.lower().endswith(legacy_model_formats):
                self.extensions.add('jms')
                filetype_dict["jms"][path] = None
            elif 'jma' in valid_exts and path.lower().endswith(legacy_animation_formats):
                self.extensions.add('jma')
                filetype_dict["jma"][path] = None
            elif 'bitmap' in valid_exts and path.lower().endswith('.bitmap'):
                self.extensions.add('bitmap')
                filetype_dict["bitmap"][path] = None
            elif 'camera_track' in valid_exts and path.lower().endswith('.camera_track'):
                self.extensions.add('camera_track')
                filetype_dict["camera_track"][path] = None
            elif 'model' in valid_exts and path.lower().endswith('.model'):
                self.extensions.add('model')
                filetype_dict["model"][path] = None
            elif 'render_model' in valid_exts and path.lower().endswith('.render_model'):
                self.extensions.add('render_model')
                filetype_dict["render_model"][path] = None
            elif 'scenario' in valid_exts and path.lower().endswith('.scenario'):
                self.extensions.add('scenario')
                filetype_dict["scenario"][path] = None
            elif 'scenario_structure_bsp' in valid_exts and path.lower().endswith('.scenario_structure_bsp'):
                self.extensions.add('scenario_structure_bsp')
                filetype_dict["scenario_structure_bsp"][path] = None
            elif 'particle_model' in valid_exts and path.lower().endswith('.particle_model'):
                self.extensions.add('particle_model')
                filetype_dict["particle_model"][path] = None
            elif 'object' in valid_exts and path.lower().endswith(object_tag_types):
                self.extensions.add('object')
                filetype_dict["object"][path] = None
            elif 'animation' in valid_exts and path.lower().endswith(".model_animation_graph"):
                self.extensions.add('animation')
                filetype_dict["animation"][path] = None
            
        # First stored as dict then converted to list. Avoids duplicate files
        for k, v in filetype_dict.items():
            filetype_dict[k] = list(v)
                
        return filetype_dict
        
    # Utility functions
    
    def set_region(self, ob, region):
        regions_table = self.context.scene.nwo.regions_table
        entry = regions_table.get(region, 0)
        if not entry:
            # Create the entry
            regions_table.add()
            entry = regions_table[-1]
            entry.old = region
            entry.name = region
            
        ob.nwo.region_name = region

    def set_permutation(self, ob, permutation):
        permutations_table = self.context.scene.nwo.permutations_table
        entry = permutations_table.get(permutation, 0)
        if not entry:
            # Create the entry
            permutations_table.add()
            entry = permutations_table[-1]
            entry.old = permutation
            entry.name = permutation
            
        ob.nwo.permutation_name = permutation
        
    # Camera track import
    def import_camera_tracks(self, paths, animation_scale):
        cameras = []
        actions = []
        for file in paths:
            camera, action = self.import_camera_track(file, animation_scale)
            cameras.append(camera)
            actions.append(action)
        
        return cameras, actions
            
    def import_camera_track(self, file, animation_scale):
        start_mb_for_import(file)
        with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
            with CameraTrackTag(path=mover.tag_path) as camera_track:
                camera, action = camera_track.to_blender_animation(self.context, animation_scale)
            
        return camera, action
    
    # Model Import
    
    def import_models(self, paths, existing_armature):
        imported_objects = []
        imported_animations = []
        for file in paths:
            print(f'Importing Model Tag: {Path(file).with_suffix("").name} ')
            start_mb_for_import(file)
            with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
                with ModelTag(path=mover.tag_path, raise_on_error=False) as model:
                    if not model.valid: continue
                    if mover.needs_to_move:
                        source_tag_root = mover.potential_source_tag_dir
                    else:
                        source_tag_root = utils.get_project(self.context.scene.nwo.scene_project).tags_directory
                        
                    render, collision, animation, physics = model.get_model_paths(optional_tag_root=source_tag_root)
                    
                    allowed_region_permutations = model.get_variant_regions_and_permutations(self.tag_variant, self.tag_state)
                    model_collection = bpy.data.collections.new(model.tag_path.ShortName)
                    self.context.scene.collection.children.link(model_collection)
                    if render:
                        render_objects, armature = self.import_render_model(render, model_collection, existing_armature, allowed_region_permutations)
                        imported_objects.extend(render_objects)
                    if collision and self.tag_collision:
                        imported_objects.extend(self.import_collision_model(collision, armature, model_collection, allowed_region_permutations))
                    if physics and self.tag_physics:
                        imported_objects.extend(self.import_physics_model(physics, armature, model_collection, allowed_region_permutations))
                    if animation and self.tag_animation:
                        print("Importing Animations")
                        imported_animations.extend(self.import_animation_graph(animation, armature, render))
                        
                    if self.setup_as_asset:
                        set_asset(Path(file).suffix, armature)
        
        return imported_objects, imported_animations
    
    def import_object(self, paths, existing_armature) -> tuple[list[bpy.types.Object], list] | bpy.types.Collection:
        imported_objects = []
        imported_animations = []
        is_game_object = isinstance(paths, bpy.types.Object)
        if is_game_object:
            paths = [paths]
            self.tag_render = True
            self.tag_markers = True
            self.tag_state = 0
            self.import_variant_children = True
        for file in paths:
            if is_game_object:
                game_object = file
                file = str(Path(utils.get_tags_path(), game_object.nwo.marker_game_instance_tag_name))
            start_mb_for_import(file)
            print(f'Importing Object Tag: {Path(file).name} ')
            with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
                with ObjectTag(path=mover.tag_path, raise_on_error=False) as obj:
                    if is_game_object:
                        if game_object.nwo.marker_game_instance_tag_variant_name.strip():
                            self.tag_variant = game_object.nwo.marker_game_instance_tag_variant_name
                        elif obj.default_variant.GetStringData():
                            self.tag_variant = obj.default_variant.GetStringData()
                        else:
                            self.tag_variant = ""
                    model_path = obj.get_model_tag_path_full()
                    change_colors = obj.get_change_colors(self.tag_variant)
                    magazine_size = obj.get_magazine_size()
                    has_ammo = magazine_size > 0
                    if has_ammo:
                        print(f"--- Weapon has magazine size: {magazine_size}")
                    uses_tether = obj.get_uses_tether()
                    functions = obj.functions_to_blender()
                    if functions:
                        print(f"--- Created Blender node groups for {len(functions)} object functions")
                    prop_names = []
                    with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, model_path) as model_mover:
                        with ModelTag(path=model_mover.tag_path, raise_on_error=False) as model:
                            if not model.valid: continue
                            if model_mover.needs_to_move:
                                source_tag_root = mover.potential_source_tag_dir
                            else:
                                source_tag_root = utils.get_project(self.context.scene.nwo.scene_project).tags_directory
                                
                            render, collision, animation, physics = model.get_model_paths(optional_tag_root=source_tag_root)
                            
                            temp_variant = self.tag_variant
                            
                            if not temp_variant and (is_game_object or self.context.scene.nwo.asset_type == 'cinematic'):
                                if model.block_variants.Elements.Count:
                                    temp_variant = model.block_variants.Elements[0].Fields[0].GetStringData()
                            
                            allowed_region_permutations = model.get_variant_regions_and_permutations(temp_variant, self.tag_state)
                            model_collection = bpy.data.collections.new(model.tag_path.ShortName)
                            self.context.scene.collection.children.link(model_collection)
                                
                            # possible compass driver = abs(var/pi / (2*pi))
                            if render:
                                render_objects, armature = self.import_render_model(render, model_collection, existing_armature, allowed_region_permutations)
                                
                                # FP Stuff
                                if not is_game_object and self.import_fp_arms.value and not self.fp_arms_imported and obj.tag_path.Extension == "weapon":
                                    # get fp arms path from globals
                                    globals_path = Path(utils.get_tags_path(), "globals\\globals.globals")
                                    if globals_path.exists():
                                        with GlobalsTag(path=globals_path) as globals:
                                            result = globals.get_fp_arms_path(self.import_fp_arms)
                                            if result is None:
                                                print("Failed to get FP arms reference")
                                            else:
                                                fp_arms_path, tp_unit_path, allowed_fp_region_permutations = result
                                                if Path(tp_unit_path).exists():
                                                    with ObjectTag(path=tp_unit_path) as unit:
                                                        fp_change_colors = unit.get_change_colors()
                                                        if fp_change_colors is not None:
                                                            change_colors = fp_change_colors
                                            
                                                if Path(fp_arms_path).exists():
                                                    fp_collection = bpy.data.collections.new(f"FP Arms - {self.import_fp_arms.name.title()}")
                                                    self.context.scene.collection.children.link(fp_collection)
                                                    with RenderModelTag(path=fp_arms_path) as render_model:
                                                        fp_objects, fp_armature = render_model.to_blend_objects(fp_collection, True, self.tag_markers, self.context.scene.collection, None, allowed_fp_region_permutations)
                                                        fp_objects.remove(fp_armature)
                                                        render_objects.extend(fp_objects)
                                                        
                                                        fp_arm_name = fp_armature.name
                                                        root_gun_bone = armature.pose.bones[0].name
                                                        
                                                        utils.deselect_all_objects()
                                                        armature.select_set(True)
                                                        fp_armature.select_set(True)
                                                        utils.set_active_object(armature)
                                                        bpy.ops.object.join()
                                                        armature.name = fp_arm_name
                                                        utils.unlink(armature)
                                                        fp_collection.objects.link(armature)
                                                        # Load fp graph to work out skeleton
                                                        block_fp = obj.tag.SelectField("Struct:player interface[0]/Block:first person")
                                                        fp_anim_tag = None
                                                        if self.import_fp_arms == FPARMS.SPARTAN:
                                                            if block_fp.Elements.Count > 0:
                                                                fp_anim_tag = block_fp.Elements[0].SelectField("Reference:first person animations").Path.Filename
                                                        elif self.import_fp_arms == FPARMS.ELITE:
                                                            if block_fp.Elements.Count > 1:
                                                                fp_anim_tag = block_fp.Elements[1].SelectField("Reference:first person animations").Path.Filename
                                                                
                                                        if fp_anim_tag is not None and Path(fp_anim_tag).exists():
                                                            with AnimationTag(path=fp_anim_tag) as fp_graph:
                                                                node_names = fp_graph.get_nodes()
                                                                for idx, name in enumerate(node_names):
                                                                    if utils.remove_node_prefix(name) == utils.remove_node_prefix(root_gun_bone):
                                                                        fp_root_node_element = fp_graph.block_skeleton_nodes.Elements[idx]
                                                                        parent_index = fp_root_node_element.SelectField("ShortBlockIndex:parent node index").Value
                                                                        parent_node = node_names[parent_index]
                                                        
                                                        bpy.ops.object.editmode_toggle()
                                                        root_gun_edit_bone = armature.data.edit_bones.get(root_gun_bone)
                                                        if root_gun_edit_bone is not None:
                                                            for bone in armature.data.edit_bones:
                                                                if utils.remove_node_prefix(bone.name) == utils.remove_node_prefix(parent_node):
                                                                    root_gun_edit_bone.parent = bone
                                                                    break
                                                                
                                                        bpy.ops.object.editmode_toggle()
                                                        
                                                        for ob in fp_objects:
                                                            if ob.type == 'MESH':
                                                                for mod in ob.modifiers:
                                                                    if mod.type == 'ARMATURE':
                                                                        mod.object = armature
                                    else:
                                        print(f"Couldn't find globals tag [{globals_path}], cannot import fp arms")
                                    
                                    self.fp_arms_imported = True
                                
                                imported_objects.extend(render_objects)
                                
                                has_change_colors = change_colors is not None
                                
                                if has_change_colors:
                                    prop_names.extend(["Primary Color", "Secondary Color", "Tertiary Color", "Quaternary Color"])
                                
                                for ob in render_objects:
                                    if ob.type != 'EMPTY':
                                        if has_change_colors:
                                            ob["Primary Color"] = change_colors[0]
                                            ob["Secondary Color"] = change_colors[1]
                                            ob["Tertiary Color"] = change_colors[2]
                                            ob["Quaternary Color"] = change_colors[3]
                                            ob.id_properties_ui("Primary Color").update(subtype="COLOR", min=0, max=1)
                                            ob.id_properties_ui("Secondary Color").update(subtype="COLOR", min=0, max=1)
                                            ob.id_properties_ui("Tertiary Color").update(subtype="COLOR", min=0, max=1)
                                            ob.id_properties_ui("Quaternary Color").update(subtype="COLOR", min=0, max=1)

                                        if ob.type == 'MESH':
                                            self.obs_for_props[ob] = functions
                                    
                                    if not is_game_object:    
                                        if ob.type == 'ARMATURE':
                                            # self.to_cursor_objects.add(ob)
                                            ob.nwo.cinematic_object = obj.tag_path.RelativePathWithExtension
                                            if temp_variant == self.tag_variant:
                                                ob.nwo.cinematic_variant = temp_variant
                                                
                                            if has_ammo:
                                                ob["Ammo"] = magazine_size
                                                ob.id_properties_ui("Ammo").update(min=0, max=int('9' * len(str(magazine_size))))
                                            if uses_tether:
                                                ob["Tether Distance"] = 0
                                                ob.id_properties_ui("Tether Distance").update(min=0, max=999)
                                                
                                        elif ob.type == 'MESH':
                                            for prop in prop_names:
                                                # Add driver
                                                result = ob.driver_add(f'["{prop}"]')
                                                if isinstance(result, list):
                                                    for idx, fcurve in enumerate(result):
                                                        driver = fcurve.driver
                                                        driver.type = 'SCRIPTED'
                                                        # Add variable
                                                        var = driver.variables.new()
                                                        var.name = "var"
                                                        var.type = 'SINGLE_PROP'
                                                        var.targets[0].id = armature
                                                        var.targets[0].data_path = f'["{prop}"][{idx}]'
                                                        driver.expression = var.name
                                                else:
                                                    driver = result.driver
                                                    driver.type = 'SCRIPTED'
                                                    var = driver.variables.new()
                                                    var.name = "var"
                                                    var.type = 'SINGLE_PROP'
                                                    var.targets[0].id = armature
                                                    var.targets[0].data_path = f'["{prop}"]'
                                                    driver.expression = var.name
                                                
                                                                                
                            if not is_game_object and collision and self.tag_collision:
                                imported_objects.extend(self.import_collision_model(collision, armature, model_collection, allowed_region_permutations))
                            if not is_game_object and physics and self.tag_physics:
                                imported_objects.extend(self.import_physics_model(physics, armature, model_collection, allowed_region_permutations))
                            if not is_game_object and animation and self.tag_animation:
                                print("Importing Animation Graph")
                                imported_animations.extend(self.import_animation_graph(animation, armature, render))
                                
                            if self.import_variant_children and temp_variant:
                                child_collection = bpy.data.collections.new(name=f"{model.tag_path.ShortName}_child_objects")
                                model_collection.children.link(child_collection)
                                child_objects = model.get_variant_children(temp_variant)
                                if child_objects:
                                    print("Import Child Objects")
                                    for child in model.get_variant_children(temp_variant):
                                        if child.child_object is None:
                                            continue
                                        print(f"--- {child.child_object.ShortNameWithExtension}")
                                        imported_objects.extend(self.import_child_object(child, armature, {ob: ob.nwo.marker_model_group for ob in render_objects if ob.type == 'EMPTY'}, child_collection, is_game_object))
                                    self.context.view_layer.update()
                                    
                            if not is_game_object and self.setup_as_asset:
                                set_asset(Path(file).suffix, armature)

        if is_game_object:
            return model_collection
        else:
            return imported_objects, imported_animations
    
    def import_child_object(self, child_object: ChildObject, parent_armature: bpy.types.Object, markers: dict[bpy.types.Object: str], child_collection, is_game_object):
        imported_objects = []
        if child_object.child_object is None:
            return
        with ObjectTag(path=child_object.child_object, raise_on_error=False) as obj:
            model_path = obj.get_model_tag_path_full()
            change_colors = obj.get_change_colors(self.tag_variant)
            has_change_colors = change_colors is not None
            magazine_size = obj.get_magazine_size()
            has_ammo = magazine_size > 0
            if has_ammo:
                print(f"--- Weapon has magazine size: {magazine_size}")
            uses_tether = obj.get_uses_tether()
            functions = obj.functions_to_blender()
            if functions:
                print(f"--- Created Blender node groups for {len(functions)} object functions")
            default_variant = obj.default_variant.GetStringData()
            prop_names = []
            with ModelTag(path=model_path, raise_on_error=False) as model:
                if not model.valid: return
                    
                render, collision, animation, physics = model.get_model_paths()
                temp_variant = child_object.child_variant_name

                if not temp_variant:
                    if default_variant:
                        temp_variant = default_variant
                    elif model.block_variants.Elements.Count:
                        temp_variant = model.block_variants.Elements[0].Fields[0].GetStringData()
                
                allowed_region_permutations = model.get_variant_regions_and_permutations(temp_variant, self.tag_state)
                model_collection = bpy.data.collections.new(model.tag_path.ShortName)
                child_collection.children.link(model_collection)

                if has_change_colors:
                    prop_names.extend(["Primary Color", "Secondary Color", "Tertiary Color", "Quaternary Color"])
                
                if render:
                    render_objects, armature = self.import_render_model(render, model_collection, None, allowed_region_permutations)
                    imported_objects.extend(render_objects)
                    for ob in render_objects:
                        if ob.type != 'EMPTY':
                            if has_change_colors:
                                ob["Primary Color"] = change_colors[0]
                                ob["Secondary Color"] = change_colors[1]
                                ob["Tertiary Color"] = change_colors[2]
                                ob["Quaternary Color"] = change_colors[3]
                                ob.id_properties_ui("Primary Color").update(subtype="COLOR", min=0, max=1)
                                ob.id_properties_ui("Secondary Color").update(subtype="COLOR", min=0, max=1)
                                ob.id_properties_ui("Tertiary Color").update(subtype="COLOR", min=0, max=1)
                                ob.id_properties_ui("Quaternary Color").update(subtype="COLOR", min=0, max=1)

                            if ob.type == 'MESH':
                                self.obs_for_props[ob] = functions
                                
                        if ob.type == 'ARMATURE':
                            ob.nwo.export_this = False
                            ob.nwo.cinematic_object = obj.tag_path.RelativePathWithExtension
                            if temp_variant == self.tag_variant:
                                ob.nwo.cinematic_variant = temp_variant
                                
                            if has_ammo:
                                ob["Ammo"] = magazine_size
                                ob.id_properties_ui("Ammo").update(min=0, max=int('9' * len(str(magazine_size))))
                            if uses_tether:
                                ob["Tether Distance"] = 0
                                ob.id_properties_ui("Tether Distance").update(min=0, max=999)
                                
                        elif ob.type == 'MESH':
                            for prop in prop_names:
                                # Add driver
                                result = ob.driver_add(f'["{prop}"]')
                                if isinstance(result, list):
                                    for idx, fcurve in enumerate(result):
                                        driver = fcurve.driver
                                        driver.type = 'SCRIPTED'
                                        # Add variable
                                        var = driver.variables.new()
                                        var.name = "var"
                                        var.type = 'SINGLE_PROP'
                                        var.targets[0].id = armature
                                        var.targets[0].data_path = f'["{prop}"][{idx}]'
                                        driver.expression = var.name
                                else:
                                    driver = result.driver
                                    driver.type = 'SCRIPTED'
                                    var = driver.variables.new()
                                    var.name = "var"
                                    var.type = 'SINGLE_PROP'
                                    var.targets[0].id = armature
                                    var.targets[0].data_path = f'["{prop}"]'
                                    driver.expression = var.name
                                    
                    if not is_game_object and collision and self.tag_collision:
                        imported_objects.extend(self.import_collision_model(collision, armature, model_collection, allowed_region_permutations))
                    if not is_game_object and physics and self.tag_physics:
                        imported_objects.extend(self.import_physics_model(physics, armature, model_collection, allowed_region_permutations))
                        
                    marker_children = []
                        
                    if child_object.child_marker:
                        for marker_ob, group_name in {ob: ob.nwo.marker_model_group for ob in render_objects if ob.type == 'EMPTY'}.items():
                            if group_name == child_object.child_marker:
                                marker_children.append(marker_ob)
                                
                    if marker_children:
                        # Where there is a child marker, the child armature should be given the transforms of the child marker
                        # However, we must also unwind the transformation we did to make the marker relative to a bone head instead of tail
                        marker_ob = marker_children[0]
                        armature.matrix_world = marker_ob.matrix_world
                        
                    marker_parents = []
                    
                    if child_object.parent_marker:
                        for marker_ob, group_name in markers.items():
                            if group_name == child_object.parent_marker:
                                marker_parents.append(marker_ob)
                    
                    # con = armature.constraints.new('CHILD_OF')
                    # con.set_inverse_pending = False
                    if marker_parents:
                        armature.parent = marker_parents[0]
                        # con.target = marker_parents[0]
                    else:
                        armature.parent = parent_armature
                        # con.target = parent_armature
                        
                    # con.inverse_matrix = IDENTITY_MATRIX
                        
        return imported_objects
            
    def import_render_model(self, file, model_collection, existing_armature, allowed_region_permutations, skip_print=False):
        start_mb_for_import(file)
        if not skip_print:
            print("Importing Render Model")
        render_model_objects = []
        armature = None
        collection = bpy.data.collections.new(str(Path(file).with_suffix("").name) + "_render")
        model_collection.children.link(collection)
        with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
            with RenderModelTag(path=mover.tag_path) as render_model:
                render_model_objects, armature = render_model.to_blend_objects(collection, self.tag_render, self.tag_markers, model_collection, existing_armature, allowed_region_permutations, self.from_vert_normals)
            
        return render_model_objects, armature
    
    def import_collision_model(self, file, armature, model_collection,allowed_region_permutations):
        start_mb_for_import(file)
        print("Importing Collision Model")
        collision_model_objects = []
        collection = bpy.data.collections.new(str(Path(file).with_suffix("").name) + "_collision")
        model_collection.children.link(collection)
        with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
            with CollisionTag(path=mover.tag_path) as collision_model:
                collision_model_objects = collision_model.to_blend_objects(collection, armature, allowed_region_permutations)
            
        return collision_model_objects
    
    def import_physics_model(self, file, armature, model_collection, allowed_region_permutations):
        start_mb_for_import(file)
        print("Importing Physics Model")
        physics_model_objects = []
        collection = bpy.data.collections.new(str(Path(file).with_suffix("").name) + "_physics")
        model_collection.children.link(collection)
        with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
            with PhysicsTag(path=mover.tag_path) as physics_model:
                physics_model_objects = physics_model.to_blend_objects(collection, armature, allowed_region_permutations)
            
        return physics_model_objects
    
    def import_animation_graph(self, file, armature, render):
        start_mb_for_import(file)
        actions = []
        filter = self.tag_animation_filter.replace(" ", ":")
        with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
            with AnimationTag(path=mover.tag_path) as graph:
                if self.graph_import_animations:
                    print("Importing Animations")
                    actions = graph.to_blender(render, armature, filter)
                if self.graph_generate_renames:
                    print("Generating Animation Renames")
                    graph.generate_renames(filter)
                if self.graph_import_events:
                    print("Importing Animation Events")
                    count = graph.events_to_blender()
                    print(f"Imported {count} frame events")
                            
                if self.graph_import_ik_chains:
                    print("Importing IK Chains")
                    graph.ik_chains_to_blender(armature)

        return actions
    
    def import_scenarios(self, paths):
        imported_objects = []
        for file in paths:
            start_mb_for_import(file)
            print(f'Importing Scenario Tag: {Path(file).with_suffix("").name} ')
            with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
                with ScenarioTag(path=mover.tag_path, raise_on_error=False) as scenario:
                    if not scenario.valid: continue
                    bsps = scenario.get_bsp_paths(self.tag_zone_set)
                    scenario_name = scenario.tag_path.ShortName
                    scenario_collection = bpy.data.collections.new(scenario_name)
                    self.context.scene.collection.children.link(scenario_collection)
                    for bsp in bsps:
                        bsp_objects = self.import_bsp(bsp, scenario_collection)
                        imported_objects.extend(bsp_objects)
                    
                    # if seams:
                    #     seams_tag = scenario.get_seams_path()
                        
            # if seams_tag is not None:
            #     seams_collection = bpy.data.collections.new(f"seams_{scenario_name}")
            #     scenario_collection.children.link(seams_collection)
            #     with utils.TagImportMover(utils.get_project(context.scene.nwo.scene_project).tags_directory, seams_tag) as mover:
            #         with StructureSeamsTag(path=mover.tag_path, raise_on_error=False) as structure_seams:
            #             imported_objects.extend(structure_seams.to_blend_objects(seams, seams_collection))
            
                    if self.setup_as_asset:
                        set_asset(Path(file).suffix)
        
        return imported_objects
    
    def import_bsp(self, file, scenario_collection=None):
        
        bsp_name = Path(file).with_suffix("").name
        print(f"Importing BSP {bsp_name}")
        bsp_objects = []
        collection = bpy.data.collections.new(bsp_name)
        if scenario_collection is None:
            self.context.scene.collection.children.link(collection)
        else:
            scenario_collection.children.link(collection)
        with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
            with ScenarioStructureBspTag(path=mover.tag_path) as bsp:
                bsp_objects, game_objects = bsp.to_blend_objects(collection, self.tag_bsp_render_only)
                
                meshes = {ob.data for ob in bsp_objects if ob.type == 'MESH'}
                self.emissive_meshes.update({me for me in meshes if any(p.type == 'emissive' for p in me.nwo.face_props)})
                
                if game_objects:
                    print("Importing Game Object Geometry")
                    game_object_cache = {(c.nwo.game_object_path, c.nwo.game_object_variant): c for c in utils.get_foundry_storage_scene().collection.children if c.nwo.game_object_path}
                    for ob in game_objects:
                        
                        key = ob.nwo.marker_game_instance_tag_name, ob.nwo.marker_game_instance_tag_variant_name
                        game_object_collection = game_object_cache.get(key)
                        
                        if game_object_collection is None:
                            game_object_collection = self.import_object(ob, None)
                            merge_collection(game_object_collection)
                            bsp_objects.extend(game_object_collection.all_objects)
                            self.context.scene.collection.children.unlink(game_object_collection)
                            utils.get_foundry_storage_scene().collection.children.link(game_object_collection)
                            game_object_collection.nwo.game_object_path, game_object_collection.nwo.game_object_variant = key
                            game_object_cache[key] = game_object_collection
                            
                        ob.instance_type = 'COLLECTION'
                        ob.instance_collection = game_object_collection
                        ob.nwo.marker_instance = True
                # seams = bsp.get_seams(bsp_name, seams)
        
        bsp_name = utils.add_region(bsp_name)
        collection.name = "bsp::" + bsp_name
        collection.nwo.type = "region"
        collection.nwo.region = bsp_name
        
        return bsp_objects
    
    def import_particle_model(self, file):
        start_mb_for_import(file)
        filename = Path(file).with_suffix("").name
        print(f"Importing Particle Model: {filename}")
        particle_model_objects = []
        collection = bpy.data.collections.new(f"{filename}_particle")
        self.context.scene.collection.children.link(collection)
        with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, file) as mover:
            with ParticleModelTag(path=mover.tag_path) as particle_model:
                particle_model_objects = particle_model.to_blend_objects(collection, filename)
            
        return particle_model_objects
        
    # Bitmap Import
    def extract_bitmaps(self, bitmap_files, image_format):
        print("\nExtracting Bitmaps")
        print(
            "-----------------------------------------------------------------------\n"
        )
        extracted_bitmaps = {}
        job = "Progress"
        bitmap_count = len(bitmap_files)
        for idx, fp in enumerate(bitmap_files):
            start_mb_for_import(fp)
            utils.update_progress(job, idx / bitmap_count)
            bitmap_name = utils.dot_partition(os.path.basename(fp))
            if 'lp_array' in bitmap_name or 'global_render_texture' in bitmap_name: continue # Filter out the bitmaps that crash ManagedBlam
            with utils.TagImportMover(utils.get_project(self.context.scene.nwo.scene_project).tags_directory, fp) as mover:
                with BitmapTag(path=mover.tag_path) as bitmap:
                    if not bitmap.has_bitmap_data(): continue
                    is_non_color = bitmap.is_linear()
                    image_path = bitmap.save_to_tiff(blue_channel_fix=bitmap.used_as_normal_map(), format=image_format)
                    if image_path:
                        # print(f"--- Extracted {os.path.basename(fp)} to {relative_path(image_path)}")
                        extracted_bitmaps[image_path] = is_non_color
        utils.update_progress(job, 1)
        print(f"\nExtracted {len(extracted_bitmaps)} bitmaps")
        
        return extracted_bitmaps
    
    def load_bitmaps(self, image_paths, fake_user):
        print("\nLoading Bitmaps")
        print(
            "-----------------------------------------------------------------------\n"
        )
        images = []
        job = "Progress"
        image_paths_count = len(image_paths)
        for idx, (path, is_non_color) in enumerate(image_paths.items()):
            utils.update_progress(job, idx / image_paths_count)
            if Path(path).exists():
                image = bpy.data.images.load(filepath=path, check_existing=True)
                images.append(image)
                image.use_fake_user = fake_user
                image.nwo.filepath = utils.relative_path(path)
                if is_non_color:
                    image.colorspace_settings.name = 'Non-Color'
                else:
                    image.alpha_mode = 'CHANNEL_PACKED'
            else:
                utils.print_warning(f"Failed to extract bitmap: {path}")
            
        utils.update_progress(job, 1)
        
        return images
    
    # AMF Importer
    def import_amf_files(self, amf_files, scale_factor):
        """Imports all amf files supplied"""
        self.amf_marker_objects = []
        self.amf_mesh_objects = []
        self.amf_other_objects = []
        import_size = 'MAX' if scale_factor == 1 else 'METERS'
        for path in amf_files:
            self.import_amf_file(path, import_size)
            
        return self.amf_mesh_objects + self.amf_marker_objects + self.amf_other_objects

    def import_amf_file(self, path, import_size):
        # get all objects that exist prior to import
        path = Path(path)
        pre_import_objects = bpy.data.objects[:]
        file_name = utils.dot_partition(os.path.basename(path))
        print(f"Importing AMF: {file_name}")
        with utils.MutePrints():
            bpy.ops.import_scene.amf(files=[{'name': path.name}], directory=str(path.parent), import_units=import_size, marker_prefix='')
        new_objects = [ob for ob in bpy.data.objects if ob not in pre_import_objects]
        self.process_amf_objects(new_objects, file_name)
        
    def process_amf_objects(self, objects, file_name):
        is_model = bool([ob for ob in objects if ob.type == 'ARMATURE'])
        possible_bsp = file_name
        if possible_bsp.lower() == 'shared': possible_bsp = "default_shared"
        # Add all objects to a collection
        if not self.existing_scene:
            new_coll = bpy.data.collections.get(file_name, 0)
            if not new_coll:
                new_coll = bpy.data.collections.new(file_name)
                self.context.scene.collection.children.link(new_coll)
            if not is_model and possible_bsp:
                new_coll.name = 'bsp::' + possible_bsp
                regions_table = self.context.scene.nwo.regions_table
                entry = regions_table.get(possible_bsp, 0)
                if not entry:
                    regions_table.add()
                    entry = regions_table[-1]
                    entry.old = possible_bsp
                    entry.name = possible_bsp
                    
                new_coll.nwo.type = 'region'
                new_coll.nwo.region = possible_bsp
            
        self.amf_poops = []
        print("Setting object properties")
        self.amf_object_instances = []
        self.amf_file_mesh_objects = []
        self.amf_file_marker_objects = []
        for ob in objects:
            if file_name:
                utils.unlink(ob)
                new_coll.objects.link(ob)
            if ob.type == 'MESH':
                self.setup_amf_mesh(ob, is_model)
            elif ob.type == 'EMPTY':
                self.setup_amf_marker(ob, is_model)
            else:
                self.amf_other_objects.append(ob)
                
        if self.amf_poops:
            print("Fixing scale")
            utils.stomp_scale_multi_user(self.amf_poops)
        
        if self.amf_object_instances:
            unsolved_instances = self.solve_amf_object_instances()
            if unsolved_instances:
                utils.print_warning("\nUnable to determine object instance regions and/or permutations for:")
                [utils.print_warning(f"- {ob.name}") for ob in unsolved_instances]
                print("Review the source render_model tag (if available) to determine correct region/permutations\n")
        
        if not self.existing_scene:
            utils.add_to_collection(self.amf_file_marker_objects, True, new_coll, name="markers")
            utils.add_to_collection(self.amf_file_mesh_objects, True, new_coll, name="meshes")
            
        self.amf_marker_objects.extend(self.amf_file_marker_objects)
        self.amf_mesh_objects.extend(self.amf_file_mesh_objects)
        
    def solve_amf_object_instances(self):
        unsolved_instances = [ob for ob in self.amf_object_instances]
        for ob in self.amf_object_instances:
            solved_region = False
            solved_permutation = False
            part_we_care_about = ob.name.split(":")[1]
            region_part, permutation_part = part_we_care_about.split("(")
            for region in self.context.scene.nwo.regions_table:
                if region_part.startswith(region.name):
                    self.set_region(ob, region.name)
                    ob.nwo.region_name = region.name
                    ob.nwo.marker_uses_regions = True
                    solved_region = True
                    
            permutation_part: str
            permutation_part = permutation_part.strip(")").partition("_")[2]
            for permutation in self.context.scene.nwo.permutations_table:
                if permutation_part.startswith(permutation.name):
                    self.set_permutation(ob, permutation.name)
                    ob.nwo.permutation_name = permutation.name
                    ob.nwo.marker_permutations.add().name = permutation.name
                    ob.nwo.marker_permutation_type = 'include'
                    solved_permutation = True
                    
            if solved_region and solved_permutation:
                unsolved_instances.remove(ob)
                
        return unsolved_instances
                    
    
    def setup_amf_mesh(self, ob, is_model):
        name = utils.dot_partition(ob.name)
        if is_model:
            if name.startswith('Instances:'):
                ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_object_instance'
                self.amf_object_instances.append(ob)
            else:
                parts = name.split(':')
                if len(parts) > 1:
                    region, permutation = parts[0], parts[1]
                    self.set_region(ob, utils.dot_partition(region))
                    self.set_permutation(ob, utils.dot_partition(permutation))
        else:
            if name.startswith('Clusters'):
                ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_structure'
            else:
                self.amf_poops.append(ob)
                    
        self.amf_file_mesh_objects.append(ob)
        
    def setup_amf_marker(self, ob, is_model):
        name = utils.dot_partition(ob.name)
        nwo = ob.nwo
        if is_model:
            if name.startswith('fx'):
                nwo.marker_type = '_connected_geometry_marker_type_effects'
            elif name.startswith('target'):
                nwo.marker_type = '_connected_geometry_marker_type_target'
            elif name.startswith('garbage'):
                nwo.marker_type = '_connected_geometry_marker_type_garbage'
            elif name.startswith('hint'):
                nwo.marker_type = '_connected_geometry_marker_type_hint'
                            
        self.amf_file_marker_objects.append(ob)
        
# JMS/ASS importer
######################################################################

    def import_jms_files(self, jms_files, legacy_type):
        """Imports all JMS/ASS files supplied"""
        if not jms_files:
            return []
        self.jms_marker_objects = []
        self.jms_mesh_objects = []
        self.jms_frame_objects = []
        self.jms_light_objects = []
        for path in jms_files:
            self.import_jms_file(path, legacy_type)
            
        meshes = {ob.data for ob in self.jms_mesh_objects}
        
        for me in meshes:
            utils.consolidate_face_attributes(me)

        return self.jms_marker_objects + self.jms_mesh_objects + self.jms_frame_objects + self.jms_light_objects
    
    def import_jms_file(self, path, legacy_type):
        # get all objects that exist prior to import
        pre_import_objects = set(bpy.data.objects)
        path = Path(path)
        file_name = path.with_suffix("").name
        ext = path.suffix.strip('.').upper()
        print(f"Importing {ext}: {file_name}")
        with utils.MutePrints():
            if ext == 'JMS':
                bpy.ops.import_scene.jms(files=[{'name': path.name}], directory=str(path.parent), reuse_armature=True, empty_markers=True)
            else:
                bpy.ops.import_scene.ass(filepath=str(path))
                
        new_objects = [ob for ob in bpy.data.objects if ob not in pre_import_objects]
        if self.arm and self.arm not in new_objects:
            new_objects.append(self.arm)
            
        self.jms_file_marker_objects = []
        self.jms_file_mesh_objects = []
        self.jms_file_frame_objects = []
        self.jms_file_light_objects = []
        
        match legacy_type:
            case "auto":
                is_model =  utils.nwo_asset_type() not in ("scenario", "prefab") and bool([ob for ob in new_objects if ob.type == 'ARMATURE'])
            case "model":
                is_model = True
            case "bsp":
                is_model = False
        
        self.process_jms_objects(new_objects, file_name, is_model)
        
        self.jms_marker_objects.extend(self.jms_file_marker_objects)
        self.jms_mesh_objects.extend(self.jms_file_mesh_objects)
        self.jms_frame_objects.extend(self.jms_file_frame_objects)
        self.jms_light_objects.extend(self.jms_file_light_objects)
        
    def process_jms_objects(self, objects: list[bpy.types.Object], file_name, is_model):
        self.light_data = set()
        # Add all objects to a collection
        if not self.existing_scene:
            new_coll = bpy.data.collections.get(file_name, 0)
            if not new_coll:
                new_coll = bpy.data.collections.new(file_name)
                self.context.scene.collection.children.link(new_coll)
        if not is_model and not self.existing_scene:
            possible_bsp = file_name
            if possible_bsp.lower() == 'shared': possible_bsp = "default_shared"
            new_coll.name = 'bsp::' + possible_bsp
            regions_table = self.context.scene.nwo.regions_table
            entry = regions_table.get(possible_bsp, 0)
            if not entry:
                regions_table.add()
                entry = regions_table[-1]
                entry.old = possible_bsp
                entry.name = possible_bsp
                
            new_coll.nwo.type = 'region'
            new_coll.nwo.region = possible_bsp
        
        print("Setting object properties")
        
        self.processed_meshes = []
        if file_name:
            self.new_coll = new_coll
        else:
            self.new_coll = self.context.scene.collection
            
        for ob in objects:
            if file_name:
                utils.unlink(ob)
                new_coll.objects.link(ob)
                
            if ob.type == 'MESH' and ob.data.ass_jms.XREF_name:
                xref = XREF(ob.name, ob.data.ass_jms.XREF_path, ob.data.ass_jms.XREF_name)
                ob = convert_to_marker(ob, maintain_mesh=True)
                self.setup_jms_marker(ob, is_model, xref)
                
            elif ob.name.lower().startswith(legacy_frame_prefixes) or utils.is_frame(ob):
                ob = self.setup_jms_frame(ob)
                if not ob.parent and ob.type == 'EMPTY' and not ob.name.lower().startswith(legacy_frame_prefixes):
                    ob.nwo.export_this = False
            elif ob.name.startswith('#') or (is_model and ob.type =='EMPTY' and ob.name.startswith('$')):
                self.setup_jms_marker(ob, is_model)
            elif ob.type == 'MESH':
                self.setup_jms_mesh(ob, is_model)
            elif ob.type == 'LIGHT':
                self.light_data.add(ob.data)
                self.jms_file_light_objects.append(ob)
        
        if not self.existing_scene:
            utils.add_to_collection(self.jms_file_marker_objects, True, new_coll, name="markers")
            utils.add_to_collection(self.jms_file_mesh_objects, True, new_coll, name="meshes")
            utils.add_to_collection(self.jms_file_frame_objects, True, new_coll, name="frames")
            utils.add_to_collection(self.jms_file_light_objects, True, new_coll, name="lights")
            
        for data in self.light_data:
            data.nwo.light_intensity = data.energy * (1 / 0.03048)
            if data.halo_light.light_cone_shape == 'RECTANGLE':
                data.nwo.light_shape = '_connected_geometry_light_shape_rectangle'
            else:
                data.nwo.light_shape = '_connected_geometry_light_shape_circle'
                
            if data.type == 'SPOT':
                data.spot_size = data.halo_light.spot_size
                data.spot_blend = data.halo_light.spot_blend
            
            if data.halo_light.use_near_atten:
                data.nwo.light_near_attenuation_start = data.halo_light.near_atten_start
                data.nwo.light_near_attenuation_end = data.halo_light.near_atten_end
            
            if data.halo_light.use_far_atten:
                data.nwo.light_far_attenuation_start = data.halo_light.far_atten_start
                data.nwo.light_far_attenuation_end = data.halo_light.far_atten_end
                
    def setup_jms_frame(self, ob):
        # ob.nwo.frame_override = True
        if ob.type == 'MESH':
            marker = convert_to_marker(ob)
            if self.existing_scene:
                for coll in ob.users_collection: coll.objects.link(marker)
            bpy.data.objects.remove(ob)
            self.jms_file_frame_objects.append(marker)
            return marker
        else:
            self.jms_file_frame_objects.append(ob)
            return ob
            
    def setup_jms_marker(self, ob, is_model, xref: XREF = None):
        perm, region = None, None
        constraint = is_model and ob.name.startswith('$')
        name = ob.name[1:]
        if ')' in name:
            perm_region, name = name.split(')')
            perm, region = perm_region[1:].split(' ')
        
        if ob.type == 'EMPTY':
            marker = ob
            marker.name = name
        else:
            original_matrix = ob.matrix_world.copy()
            original_parent = ob.parent
            original_parent_type = ob.parent_type
            original_parent_bone = ob.parent_bone
            radius = max(ob.dimensions.x, ob.dimensions.y, ob.dimensions.z) / 2
            scale = ob.scale.copy()
            marker = bpy.data.objects.new(name, None)
            if self.existing_scene:
                for coll in ob.users_collection: coll.objects.link(marker)
            bpy.data.objects.remove(ob)
            marker.parent = original_parent
            marker.parent_type = original_parent_type
            marker.parent_bone = original_parent_bone
            marker.matrix_world = original_matrix
            marker.scale = scale
            marker.empty_display_size = radius
            marker.empty_display_type = 'ARROWS'
            
        if is_model and region is not None:
            if region not in [region.name for region in self.context.scene.nwo.regions_table]:
                region_entry = self.context.scene.nwo.regions_table.add()
                region_entry.name = region
                region_entry.old = region
            marker.nwo.region_name = region
            marker.nwo.marker_uses_regions = True
            
            if is_model and perm is not None:
                if perm not in [perm.name for perm in self.context.scene.nwo.permutations_table]:
                    perm_entry = self.context.scene.nwo.permutations_table.add()
                    perm_entry.name = perm
                    perm_entry.old = perm
                marker.nwo.marker_permutations.add().name = perm
                marker.nwo.marker_permutation_type = 'include'
                
        if xref is not None:
            marker.nwo.marker_type = "_connected_geometry_marker_type_game_instance"
            tag_path = ""
            fallback_tag_path = ""
            if xref.preferred_dir is not None:
                path = Path(xref.preferred_dir, xref.name, f"{xref.name}{xref.preferred_type}")
                fallback_tag_path = str(path)
                if path.exists():
                    tag_path = utils.relative_path(path)
                elif xref.preferred_dir.exists():
                    for xtype in xref_tag_types:
                        path = Path(xref.preferred_dir, xref.name, f"{xref.name}{xtype}")
                        if path.exists():
                            tag_path = utils.relative_path(path)
                            break
                        
            if not tag_path:
                if not tag_files_cache:
                    for root, _, files in os.walk(utils.get_tags_path()):
                        for file in files:
                            tag_files_cache.add(Path(root, file).with_suffix(""))
                
                for path_no_ext in tag_files_cache:
                    if path_no_ext.name == xref.name:
                        path = path_no_ext.with_suffix(xref.preferred_type)
                        if path.exists():
                            tag_path = utils.relative_path(path)
                        else:
                            for xtype in xref_tag_types:
                                path = path_no_ext.with_suffix(xtype)
                                if path.exists():
                                    tag_path = utils.relative_path(path)
                                    break
                            
            if tag_path:
                marker.nwo.marker_game_instance_tag_name = tag_path
            elif fallback_tag_path:
                marker.nwo.marker_game_instance_tag_name = fallback_tag_path

        elif constraint:
            marker.nwo.marker_type = '_connected_geometry_marker_type_physics_constraint'
            marker.nwo.physics_constraint_parent = marker.rigid_body_constraint.object1
            marker.nwo.physics_constraint_child = marker.rigid_body_constraint.object2
            if marker.rigid_body_constraint.type == 'HINGE':
                marker.nwo.physics_constraint_type = '_connected_geometry_marker_type_physics_hinge_constraint'
                if marker.rigid_body_constraint.use_limit_ang_z:
                    marker.nwo.physics_constraint_uses_limits = True
                    marker.nwo.hinge_constraint_minimum = marker.rigid_body_constraint.limit_ang_z_lower
                    marker.nwo.hinge_constraint_maximum = marker.rigid_body_constraint.limit_ang_z_upper
            elif marker.rigid_body_constraint.type == 'GENERIC':
                marker.nwo.physics_constraint_type = '_connected_geometry_marker_type_physics_socket_constraint'
                if marker.rigid_body_constraint.use_limit_ang_x or marker.rigid_body_constraint.use_limit_ang_y or marker.rigid_body_constraint.use_limit_ang_z:
                    marker.nwo.physics_constraint_uses_limits = True
                    if marker.rigid_body_constraint.use_limit_ang_x:
                        marker.nwo.twist_constraint_start = marker.rigid_body_constraint.limit_ang_x_lower
                        marker.nwo.twist_constraint_end = marker.rigid_body_constraint.limit_ang_x_upper
                    if marker.rigid_body_constraint.use_limit_ang_y:
                        marker.nwo.cone_angle = marker.rigid_body_constraint.limit_ang_y_upper
                    if marker.rigid_body_constraint.use_limit_ang_z:
                        marker.nwo.plane_constraint_minimum = marker.rigid_body_constraint.limit_ang_z_lower
                        marker.nwo.plane_constraint_maximum = marker.rigid_body_constraint.limit_ang_z_upper

        elif name.startswith('fx'):
            marker.nwo.marker_type = '_connected_geometry_marker_type_effects'
        elif name.startswith('target'):
            marker.nwo.marker_type = '_connected_geometry_marker_type_target'
            marker.empty_display_type = 'SPHERE'
        elif name.startswith('garbage'):
            marker.nwo.marker_type = '_connected_geometry_marker_type_garbage'
        elif name.startswith('hint'):
            marker.nwo.marker_type = '_connected_geometry_marker_type_hint'
                
        self.jms_file_marker_objects.append(marker)
        
    def setup_jms_mesh(self, original_ob, is_model):
        new_objects = self.convert_material_props(original_ob)
        for ob in new_objects:
            mesh = ob.data
            mesh_type_legacy = self.get_mesh_type(ob, is_model)
            ob.nwo.mesh_type_temp = ''
            if ob.name.startswith('%'):
                self.set_poop_policies(ob)
            if mesh_type_legacy:
                mesh_type, material = self.mesh_and_material(mesh_type_legacy, is_model)
                ob.data.nwo.mesh_type = mesh_type
                        
                if self.corinth and utils.test_face_prop_all(mesh, 'Render Only'):
                    ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_default'
                    
                if self.corinth and ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_structure' and utils.test_face_prop_all(mesh, 'Slip Surface'):
                    ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_default'
                    ob.nwo.export_this = False
                    
                if self.corinth and ob.data.nwo.mesh_type == '_connected_geometry_mesh_type_structure' and utils.test_face_prop_any(mesh, "Two-Sided"):
                    ob.data.nwo.mesh_type = '_connected_geometry_mesh_type_default'

                if mesh_type_legacy in ('collision', 'physics') and is_model:
                    self.setup_collision_materials(ob, mesh_type_legacy)
                    if mesh_type_legacy == 'physics':
                        match ob.data.ass_jms.Object_Type:
                            case "CAPSULES":
                                ob.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_pill"
                            case "SPHERE":
                                ob.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_sphere"
                            case "BOX":
                                ob.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_box"
                            case _:
                                ob.nwo.mesh_primitive_type = "_connected_geometry_primitive_type_none"
                                
                elif ob.parent and mesh_type_legacy == 'collision' and (ob.parent.name[0] == "%" and ob.parent.type == 'MESH'):
                    # setup poop proxy
                    ob.nwo.proxy_parent = ob.parent.data
                    ob.nwo.proxy_type = "collision"
                    ob.parent.data.nwo.proxy_collision = ob
                    utils.get_foundry_storage_scene().objects.link(ob)
                    self.jms_other_objects.append(ob)
                    return
                    
                if self.apply_materials:
                    apply_props_material(ob, material)
                
            if is_model:
                if ob.region_list:
                    reg_perm = ob.region_list[0].name
                    parts = reg_perm.split()
                    if len(parts) == 1:
                        self.set_region(ob, parts[0])
                    elif len(parts) >= 2:
                        self.set_region(ob, parts[-1])
                        self.set_permutation(ob, parts[-2])
                        
                    if mesh_type_legacy == 'io':
                        ob.nwo.marker_uses_regions = True
                        ob.nwo.marker_permutation_type = 'include'
                        ob.nwo.marker_permutations.add().name = ob.nwo.permutation_name
                    
            if ob.nwo.mesh_type == '_connected_geometry_mesh_type_structure':
                ob.nwo.proxy_instance = True
            elif ob.nwo.mesh_type == '_connected_geometry_mesh_type_seam':
                ob.nwo.seam_back_manual = True
            
            self.jms_file_mesh_objects.append(ob)
            
    def set_poop_policies(self, ob):
        for char in ob.name[1:]:
            match char:
                case '+':
                    ob.nwo.poop_pathfinding = 'static'
                case '-':
                    ob.nwo.poop_pathfinding = 'none'
                case '?':
                    ob.nwo.poop_lighting = 'per_vertex'
                case '!':
                    ob.nwo.poop_lighting = 'per_pixel'
                case '>':
                    ob.nwo.poop_lighting = 'single_probe'
                case '*':
                    ob.nwo.poop_render_only = True
                # case '&':
                #     ob.nwo.poop_chops_portals = True
                case '^':
                    ob.nwo.poop_does_not_block_aoe = True
                case '<':
                    ob.nwo.poop_excluded_from_lightprobe = True
                case '|':
                    ob.nwo.poop_decal_spacing = True
                case _:
                    return
        
    def convert_material_props(self, ob: bpy.types.Object):
        if ob.name.startswith('$'):
            return [ob]
        
        if ob.data in self.processed_meshes:
            ob.nwo.mesh_type_temp = 'skip'
            return [ob]

        objects_to_setup = [ob]
        self.processed_meshes.append(ob.data)
        jms_materials: list[JMSMaterialSlot] = []
        for slot in ob.material_slots:
            if not slot.material:
                continue
            jms_materials.append(JMSMaterialSlot(slot))
        
        if len(jms_materials) == 1:
            jms_mat = jms_materials[0]
            ob.nwo.mesh_type_temp = jms_mat.mesh_type
            nwo = ob.data.nwo
            mesh = ob.data
            if jms_mat.two_sided or jms_mat.transparent_two_sided:
                utils.add_face_prop(mesh, "face_sides")
            
            if jms_mat.transparent_one_sided or jms_mat.transparent_two_sided:
                utils.add_face_prop(mesh, "transparent")
            if jms_mat.render_only and not ob.data.nwo.proxy_collision:
                utils.add_face_prop(mesh, "face_mode").face_mode = 'render_only'
            if jms_mat.collision_only:
                utils.add_face_prop(mesh, "face_mode").face_mode = 'collision_only'
            if jms_mat.sphere_collision_only:
                utils.add_face_prop(mesh, "face_mode").face_mode = 'sphere_collision_only'
            
            if jms_mat.ladder:
                utils.add_face_prop(mesh, "ladder")
            if jms_mat.breakable:
                utils.add_face_prop(mesh, "face_mode").face_mode = 'breakable'
                
            nwo.portal_ai_deafening = jms_mat.ai_deafening
            
            if jms_mat.no_shadow:
                utils.add_face_prop(mesh, "no_shadow")
                
            if jms_mat.lightmap_only:
                utils.add_face_prop(mesh, "face_mode").face_mode = 'lightmap_only'
            if jms_mat.shadow_only:
                utils.add_face_prop(mesh, "face_mode").face_mode = 'shadow_only'
            if jms_mat.precise:
                utils.add_face_prop(mesh, "precise_position")

            if jms_mat.portal_one_way:
                nwo.portal_type = '_connected_geometry_portal_type_one_way'
            nwo.portal_is_door = jms_mat.portal_door
            if jms_mat.portal_vis_blocker:
                nwo.portal_type = '_connected_geometry_portal_type_no_way'
            if jms_mat.ignored_by_lightmaps:
                utils.add_face_prop(mesh, "no_lightmap")
            nwo.portal_blocks_sounds = jms_mat.blocks_sound
            
            if jms_mat.decal_offset:
                utils.add_face_prop(mesh, "decal_offset")
            
            if jms_mat.slip_surface:
                utils.add_face_prop(mesh, "slip_surface")
            # Lightmap
            if jms_mat.lightmap_resolution_scale:
                utils.add_face_prop(mesh, "lightmap_resolution_scale").lightmap_resolution_scale = str(jms_mat.lightmap_resolution_scale)
            if jms_mat.lightmap_additive_transparency:
                utils.add_face_prop(mesh, "lightmap_additive_transparency").lightmap_additive_transparency = jms_mat.lightmap_additive_transparency
            if jms_mat.lightmap_translucency_tint_color:
                utils.add_face_prop(mesh, "lightmap_translucency_tint_color").lightmap_translucency_tint_color = jms_mat.lightmap_translucency_tint_color
            if jms_mat.lightmap_transparency_override:
                utils.add_face_prop(mesh, "lightmap_transparency_override")
            # Emissive
            if jms_mat.emissive_power:
                prop = utils.add_face_prop(mesh, "emissive")
                prop.light_intensity = jms_mat.emissive_power
                prop.material_lighting_emissive_color = jms_mat.emissive_color
                prop.material_lighting_emissive_quality = jms_mat.emissive_quality
                prop.material_lighting_emissive_per_unit = jms_mat.emissive_per_unit
                prop.material_lighting_use_shader_gel = jms_mat.emissive_shader_gel
                prop.material_lighting_emissive_focus = jms_mat.emissive_focus
                prop.material_lighting_attenuation_falloff = jms_mat.emissive_attenuation_falloff
                prop.material_lighting_attenuation_cutoff = jms_mat.emissive_attenuation_cutoff

        mesh_types = list(set([m.mesh_type for m in jms_materials if m.mesh_type]))
        if len(mesh_types) == 1:
            ob.nwo.mesh_type_temp = mesh_types[0]
        elif len(mesh_types) > 1:
            linked_objects = [o for o in bpy.data.objects if o != ob and o.data == ob.data]
            bm_original = bmesh.new()
            bm_original.from_mesh(ob.data)
            utils.save_loop_normals(bm_original, ob.data)
            for jms_mat in jms_materials:
                if jms_mat.mesh_type == 'default':
                    continue
                new_ob = ob.copy()
                if self.existing_scene:
                    for coll in ob.users_collection: coll.objects.link(new_ob)
                new_ob.data = ob.data.copy()
                bm = bm_original.copy()
                faces_to_remove = [face for face in bm.faces if face.material_index != jms_mat.index]
                faces_to_remove_original = [face for face in bm_original.faces if face.material_index == jms_mat.index]
                bmesh.ops.delete(bm, geom=faces_to_remove, context='FACES')
                bmesh.ops.delete(bm_original, geom=faces_to_remove_original, context='FACES')
                bm.to_mesh(new_ob.data)
                bm.free()
                utils.apply_loop_normals(new_ob.data)
                utils.loop_normal_magic(new_ob.data)
                utils.clean_materials(new_ob)
                if new_ob.data.polygons:
                    new_ob.nwo.mesh_type_temp = jms_mat.mesh_type
                    objects_to_setup.append(new_ob)
                    self.new_coll.objects.link(new_ob)
                    for obj in linked_objects:
                        new_ob_copy = new_ob.copy()
                        new_ob_copy.parent = obj.parent
                        new_ob_copy.parent_type = obj.parent_type
                        new_ob_copy.parent_bone = obj.parent_bone
                        new_ob_copy.matrix_world = obj.matrix_world
                else:
                    bpy.data.objects.remove(new_ob)
                
            bm_original.to_mesh(ob.data)
            bm_original.free()
            if not ob.data.polygons:
                objects_to_setup.remove(ob)
                bpy.data.objects.remove(ob)
            else:
                utils.apply_loop_normals(ob.data)
                utils.loop_normal_magic(ob.data)
                utils.clean_materials(ob)
            
        for ob in objects_to_setup:
            mesh = ob.data
            nwo = ob.nwo
            if len(ob.data.materials) == 1 or self.matching_material_properties(ob.data.materials, jms_materials):
                jms_mats = [mat for mat in jms_materials if mat.name == ob.data.materials[0].name]
                if jms_mats:
                    jms_mat = jms_mats[0]
                    ob.nwo.mesh_type_temp = jms_mat.mesh_type
                    if jms_mat.two_sided or jms_mat.transparent_two_sided:
                        utils.add_face_prop(mesh, "face_sides")
                    
                    if jms_mat.transparent_one_sided or jms_mat.transparent_two_sided:
                        utils.add_face_prop(mesh, "transparent")
                    if jms_mat.render_only and not ob.data.nwo.proxy_collision:
                        utils.add_face_prop(mesh, "face_mode").face_mode = 'render_only'
                    if jms_mat.collision_only:
                        utils.add_face_prop(mesh, "face_mode").face_mode = 'collision_only'
                    if jms_mat.sphere_collision_only:
                        utils.add_face_prop(mesh, "face_mode").face_mode = 'sphere_collision_only'
                    
                    if jms_mat.ladder:
                        utils.add_face_prop(mesh, "ladder")
                    if jms_mat.breakable:
                        utils.add_face_prop(mesh, "face_mode").face_mode = 'breakable'
                        
                    nwo.portal_ai_deafening = jms_mat.ai_deafening
                    
                    if jms_mat.no_shadow:
                        utils.add_face_prop(mesh, "no_shadow")
                        
                    if jms_mat.lightmap_only:
                        utils.add_face_prop(mesh, "face_mode").face_mode = 'lightmap_only'
                    if jms_mat.shadow_only:
                        utils.add_face_prop(mesh, "face_mode").face_mode = 'shadow_only'
                    if jms_mat.precise:
                        utils.add_face_prop(mesh, "precise_position")

                    if jms_mat.portal_one_way:
                        nwo.portal_type = '_connected_geometry_portal_type_one_way'
                    nwo.portal_is_door = jms_mat.portal_door
                    if jms_mat.portal_vis_blocker:
                        nwo.portal_type = '_connected_geometry_portal_type_no_way'
                    if jms_mat.ignored_by_lightmaps:
                        utils.add_face_prop(mesh, "no_lightmap")
                    nwo.portal_blocks_sounds = jms_mat.blocks_sound
                    
                    if jms_mat.decal_offset:
                        utils.add_face_prop(mesh, "decal_offset")
                    
                    if jms_mat.slip_surface:
                        utils.add_face_prop(mesh, "slip_surface")
                    # Lightmap
                    if jms_mat.lightmap_resolution_scale:
                        utils.add_face_prop(mesh, "lightmap_resolution_scale").lightmap_resolution_scale = str(jms_mat.lightmap_resolution_scale)
                    if jms_mat.lightmap_additive_transparency:
                        utils.add_face_prop(mesh, "lightmap_additive_transparency").lightmap_additive_transparency = jms_mat.lightmap_additive_transparency
                    if jms_mat.lightmap_translucency_tint_color:
                        utils.add_face_prop(mesh, "lightmap_translucency_tint_color").lightmap_translucency_tint_color = jms_mat.lightmap_translucency_tint_color
                    if jms_mat.lightmap_transparency_override:
                        utils.add_face_prop(mesh, "lightmap_transparency_override")
                    # Emissive
                    if jms_mat.emissive_power:
                        prop = utils.add_face_prop(mesh, "emissive")
                        prop.light_intensity = jms_mat.emissive_power
                        prop.material_lighting_emissive_color = jms_mat.emissive_color
                        prop.material_lighting_emissive_quality = jms_mat.emissive_quality
                        prop.material_lighting_emissive_per_unit = jms_mat.emissive_per_unit
                        prop.material_lighting_use_shader_gel = jms_mat.emissive_shader_gel
                        prop.material_lighting_emissive_focus = jms_mat.emissive_focus
                        prop.material_lighting_attenuation_falloff = jms_mat.emissive_attenuation_falloff
                        prop.material_lighting_attenuation_cutoff = jms_mat.emissive_attenuation_cutoff
                    
            elif len(ob.data.materials) > 1:
                material_face_indices = np.empty(len(mesh.polygons), dtype=np.int32)
                mesh.polygons.foreach_get("material_index", material_face_indices)
                for idx, material in enumerate(ob.data.materials):
                    jms_mats = [mat for mat in jms_materials if mat.name == material.name]
                    if jms_mats:
                        jms_mat = jms_mats[0]
                        
                        indices = material_face_indices == idx
                        
                        if jms_mat.two_sided or jms_mat.transparent_two_sided:
                            utils.add_face_prop(mesh, 'face_sides', indices)
                                
                        if jms_mat.transparent_one_sided or jms_mat.transparent_two_sided:
                            utils.add_face_prop(mesh, 'transparent', indices)
                                
                        if jms_mat.render_only:
                            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'render_only'
                        if jms_mat.collision_only:
                            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'collision_only'
                        if jms_mat.sphere_collision_only:
                            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'sphere_collision_only'
                        
                        if jms_mat.ladder:
                            utils.add_face_prop(mesh, "ladder", indices)
                        if jms_mat.breakable:
                            utils.add_face_prop(mesh, "face_mode, indices").face_mode = 'breakable'
                        
                        if jms_mat.no_shadow:
                            utils.add_face_prop(mesh, "no_shadow", indices)
                            
                        if jms_mat.lightmap_only:
                            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'lightmap_only'
                        if jms_mat.shadow_only:
                            utils.add_face_prop(mesh, "face_mode", indices).face_mode = 'shadow_only'
                        if jms_mat.precise:
                            utils.add_face_prop(mesh, "precise_position", indices)

                        if jms_mat.ignored_by_lightmaps:
                            utils.add_face_prop(mesh, "no_lightmap", indices)
                        
                        if jms_mat.decal_offset:
                            utils.add_face_prop(mesh, "decal_offset", indices)
                        
                        if jms_mat.slip_surface:
                            utils.add_face_prop(mesh, "slip_surface", indices)
                        # Lightmap
                        if jms_mat.lightmap_resolution_scale:
                            utils.add_face_prop(mesh, "lightmap_resolution_scale", indices).lightmap_resolution_scale = str(jms_mat.lightmap_resolution_scale)
                        if jms_mat.lightmap_additive_transparency:
                            utils.add_face_prop(mesh, "lightmap_additive_transparency", indices).lightmap_additive_transparency = jms_mat.lightmap_additive_transparency
                        if jms_mat.lightmap_translucency_tint_color:
                            utils.add_face_prop(mesh, "lightmap_translucency_tint_color", indices).lightmap_translucency_tint_color = jms_mat.lightmap_translucency_tint_color
                        if jms_mat.lightmap_transparency_override:
                            utils.add_face_prop(mesh, "lightmap_transparency_override", indices)
                        # Emissive
                        if jms_mat.emissive_power:
                            prop = utils.add_face_prop(mesh, "emissive", indices)
                            prop.light_intensity = jms_mat.emissive_power
                            prop.material_lighting_emissive_color = jms_mat.emissive_color
                            prop.material_lighting_emissive_quality = jms_mat.emissive_quality
                            prop.material_lighting_emissive_per_unit = jms_mat.emissive_per_unit
                            prop.material_lighting_use_shader_gel = jms_mat.emissive_shader_gel
                            prop.material_lighting_emissive_focus = jms_mat.emissive_focus
                            prop.material_lighting_attenuation_falloff = jms_mat.emissive_attenuation_falloff
                            prop.material_lighting_attenuation_cutoff = jms_mat.emissive_attenuation_cutoff
        
        return objects_to_setup
    
    def matching_material_properties(self, materials: list[bpy.types.Material], scoped_jms_materials: list[JMSMaterialSlot]):
        '''Checks if all jms materials have matching properties'''
        if len(materials) <= 1:
            return True
        material_names = [m.name for m in materials]
        jms_materials = [jms_mat for jms_mat in scoped_jms_materials if jms_mat.name in material_names]
        first_mat = jms_materials[0]
        for mat in jms_materials[1:]:
            if mat != first_mat:
                return False
            
        return True
        
    def setup_collision_materials(self, ob: bpy.types.Object, mesh_type_legacy: str):
        if not ob.material_slots:
            return
        if mesh_type_legacy == 'physics' or len(ob.material_slots) == 1:
            if ob.material_slots[0].material:
                ob.data.nwo.face_global_material = ob.material_slots[0].material.name
                
        elif mesh_type_legacy == 'collision':
            face_props = ob.data.nwo.face_props
            for slot in ob.material_slots:
                if not slot.material:
                    continue
                layer = face_props.add()
                layer.name = slot.material.name
                layer.layer_name = 'face_global_material'
                layer.face_global_material = slot.material.name
                layer.face_global_material_override = True
                material_index = slot.slot_index
                layer.layer_name, layer.face_count = self.add_collision_face_attribute(ob.data, material_index, layer.layer_name)
                layer.color = utils.random_color()
                
    def add_collision_face_attribute(self, mesh, material_index, prefix):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        face_attribute = bm.faces.layers.int.new(f"{prefix}_{str(uuid4())}")
        for face in bm.faces:
            if face.material_index == material_index:
                face[face_attribute] = 1
        
        bm.to_mesh(mesh)
                
        return face_attribute.name, utils.layer_face_count(bm, face_attribute)
        
    def get_mesh_type(self, ob: bpy.types.Object, is_model):
        if ob.nwo.mesh_type_temp == 'skip':
            return ''
        name = ob.name
        if name.startswith('@'):
            return 'collision'
        elif name.startswith('$'):
            return 'physics'
        elif name.startswith('~') and not is_model:
            return 'water_physics'
        elif name.startswith('%'):
            if is_model:
                return 'io'
            elif ob.nwo.mesh_type_temp and ob.nwo.mesh_type_temp != 'default':
                return ob.nwo.mesh_type_temp
            else:
                return 'instance'
            
        elif ob.nwo.mesh_type_temp:
            return ob.nwo.mesh_type_temp
        
        return 'default'
    
    def mesh_and_material(self, mesh_type, is_model):
        material = ""
        match mesh_type:
            case "collision":
                if is_model:
                    mesh_type = "_connected_geometry_mesh_type_collision"
                    material = "Collision"
                else:
                    mesh_type = "_connected_geometry_mesh_type_structure"
            case "physics":
                mesh_type = "_connected_geometry_mesh_type_physics"
                material = "Physics"
            case "default":
                if is_model:
                    mesh_type = "_connected_geometry_mesh_type_default"
                else:
                    mesh_type = "_connected_geometry_mesh_type_structure"
            case "io":
                mesh_type = "_connected_geometry_mesh_type_object_instance"
            case "instance":
                mesh_type = "_connected_geometry_mesh_type_default"
            case "seam":
                mesh_type = "_connected_geometry_mesh_type_seam"
                material = "Seam"
            case "portal":
                mesh_type = "_connected_geometry_mesh_type_portal"
                material = "Portal"
            case "water_surface":
                mesh_type = "_connected_geometry_mesh_type_water_surface"
            case "rain_sheet":
                mesh_type = "_connected_geometry_mesh_type_poop_vertical_rain_sheet"
                material = "RainSheet"
            case "fog":
                mesh_type = "_connected_geometry_mesh_type_planar_fog_volume"
                material = "Fog"
            case "soft_ceiling":
                mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                material = "SoftCeiling"
            case "soft_kill":
                mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                material = "SoftKill"
            case "slip_surface":
                mesh_type = "_connected_geometry_mesh_type_boundary_surface"
                material = "SlipSurface"
            case "water_physics":
                mesh_type = "_connected_geometry_mesh_type_water_surface"
                material = "WaterVolume"
            case "cookie_cutter":
                mesh_type = "_connected_geometry_mesh_type_cookie_cutter"
                material = "CookieCutter"
            case "rain_blocker":
                mesh_type = "_connected_geometry_mesh_type_poop_rain_blocker"
                material = "RainBlocker"
            case "decorator":
                mesh_type = "_connected_geometry_mesh_type_decorator"
                
        return mesh_type, material
            

# Legacy Animation importer
######################################################################
    def import_jma_files(self, jma_files, arm):
        """Imports all legacy animation files supplied"""
        if not jma_files:
            return []
        self.actions = []
        self.objects = []
        if jma_files:
            muted_armature_deforms = utils.mute_armature_mods()
            print("Importing Animations")
            print(
                "-----------------------------------------------------------------------\n"
            )
            try:
                for bone in arm.pose.bones:
                    bone.matrix_basis = IDENTITY_MATRIX
                self.context.view_layer.update()
                for path in jma_files:
                    self.import_legacy_animation(path, arm)
            finally:
                utils.unmute_armature_mods(muted_armature_deforms)
                
            if self.context.scene.nwo.asset_type in {'model', 'animation'}:
                self.context.scene.nwo.active_animation_index = len(self.context.scene.nwo.animations) - 1
            
            return self.actions
            
    def import_legacy_animation(self, path, arm):
        path = Path(path)
        # existing_animations = bpy.data.actions[:]
        extension = path.suffix.strip('.')
        anim_name = path.with_suffix("").name
        print(f"--- {anim_name}")
        jma = JMA()
        jma.from_file(path)
        action = jma.to_armature_action(arm)
        # with utils.MutePrints():
        #     bpy.ops.import_scene.jma(filepath=str(path))
        if action is not None:
            self.actions.append(action)
            animation = self.context.scene.nwo.animations.add()
            animation.name = anim_name
            action.use_fake_user = True
            action.use_frame_range = True
            animation.frame_start = 1
            animation.frame_end = jma.frame_count
            track = animation.action_tracks.add()
            track.object = arm
            track.action = action
            match extension.lower():
                case 'jmm':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'none'
                case 'jma':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'xy'
                case 'jmt':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'xyyaw'
                case 'jmz':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'xyzyaw'
                case 'jmv':
                    animation.animation_type = 'base'
                    animation.animation_movement_data = 'full'
                case 'jmw':
                    animation.animation_type = 'world'
                case 'jmo':
                    animation.animation_type = 'overlay'
                    # animation.animation_is_pose = any(hint in anim_name.lower() for hint in pose_hints)
                    # if animation.animation_is_pose:
                    #     pass
                case 'jmr':
                    animation.animation_type = 'replacement'
                case 'jmrx':
                    animation.animation_type = 'replacement'
                    animation.animation_space = 'local'
                        
class NWO_OT_ImportFromDrop(bpy.types.Operator):
    bl_idname = "nwo.import_from_drop"
    bl_label = "Foundry Importer"
    bl_description = "Imports from drag n drop"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    # filename: bpy.props.StringProperty(options={'SKIP_SAVE'})
    # filter_glob: bpy.props.StringProperty(
    #     default=".jms;.amf;.ass;.bitmap;.model;.render_model;.scenario;.scenario_structure_bsp;.jmm;.jma;.jmt;.jmz;.jmv;.jmw;.jmo;.jmr;.jmrx;.camera_track;.particle_model;.scenery;.biped;.model_animation_graph",
    #     options={"HIDDEN"},
    # )
    
    # find_shader_paths: bpy.props.BoolProperty(
    #     name="Find Shader Paths",
    #     description="Searches the tags folder after import and tries to find shader/material tags which match the name of importer materials",
    #     default=True,
    # )
    build_blender_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Builds Blender material nodes for materials based off their shader/material tags (if found)",
        default=True,
    )
    
    import_images_to_blender: bpy.props.BoolProperty(
        name="Import to Blend",
        description="Imports images into the blender after extracting bitmaps from the game",
        default=True,
    )
    images_fake_user: bpy.props.BoolProperty(
        name="Set Fake User",
        description="Sets the fake user property on imported images",
        default=True,
    )
    extracted_bitmap_format: bpy.props.EnumProperty(
        name="Image Format",
        description="Sets format to save the extracted bitmap as",
        items=[
            ("tiff", "TIFF", ""),
            ("png", "PNG", ""),
            ("jped", "JPEG", ""),
            ("bmp", "BMP", ""),
        ]
    )
    
    camera_track_animation_scale: bpy.props.FloatProperty(
        name='Animation Scale',
        default=1,
        min=1,
    )
    
    reuse_armature: bpy.props.BoolProperty(
        name="Reuse Scene Armature",
        description="Will reuse the main blend scene armature for this model instead of importing a new one",
        default=False,
    )
    tag_render: bpy.props.BoolProperty(
        name="Import Render Geometry",
        default=True,
    )
    tag_markers: bpy.props.BoolProperty(
        name="Import Markers",
        default=True,
    )
    tag_collision: bpy.props.BoolProperty(
        name="Import Collision",
        default=False,
    )
    tag_physics: bpy.props.BoolProperty(
        name="Import Physics",
        default=False,
    )
    tag_animation: bpy.props.BoolProperty(
        name="Import Animation Graph",
        description="Imports animations, renames, and animation events. This importer is work in progress and additional functionaility is still to be added",
        options={'SKIP_SAVE'},
        default=False,
    )
    
    def items_tag_variant(self, context):
        var_match = False
        if context.scene.nwo.asset_type in {"cinematic", "scenario"}:
            items = []
        else:
            items = [("all_variants", "All Variants", "Includes the full model geometry")]
        for var in variant_items:
            if var == last_used_variant:
                var_match = True
            else:
                items.append((var, var, ""))
                
        if var_match:
            items.insert(0, (last_used_variant, last_used_variant, ""))
            
        return items
        
    
    tag_variant: bpy.props.EnumProperty(
        name="Variant",
        options={'SKIP_SAVE'},
        description="Model variant to import, or all",
        items=items_tag_variant,
    )
    
    setup_as_asset: bpy.props.BoolProperty(
        name="Setup as Asset",
        description="Updates the scene asset settings so that this object can be immediately reimported into the game"
    )
    
    def items_tag_zone_set(self, context):
        items = [("all_zone_sets", "All Zone Sets", "All scenario bsps will be imported")]
        for zs, bsps in zone_set_items.items():
            bsps_str = "\n".join(bsps)
            items.append((zs, zs, f"Includes BSPs:\n{bsps_str}"))
            
        return items
    
    tag_zone_set: bpy.props.EnumProperty(
        name="Zone Set",
        options={'SKIP_SAVE'},
        description="Limits the bsps to import to those present in the specified zoneset",
        items=items_tag_zone_set,
    )
    
    tag_bsp_render_only: bpy.props.BoolProperty(
        name="Render Geometry Only",
        description="Skips importing bsp data like collision and portals. Use this if you aren't importing the BSP back into the game",
    )
    
    tag_animation_filter: bpy.props.StringProperty(
        name="Animation Filter",
        description="Filter for the animations to import. Animation names that do not contain the specified string will be skipped"
    )
    
    tag_state: bpy.props.EnumProperty(
        name="Model State",
        description="The damage state to import. Only valid when a variant is set",
        default=1,
        items=state_items,
    )
    
    graph_import_animations: bpy.props.BoolProperty(
        name="Import Animations"
    )
    graph_generate_renames: bpy.props.BoolProperty(
        name="Generate Renames",
        description="Parses the animation mode n state graph to work out what animations were imported as renames"
    )
    graph_import_events: bpy.props.BoolProperty(
        name="Import Animation Events",
        description="This currently only supports importing of frame events"
    )
    graph_import_ik_chains: bpy.props.BoolProperty(
        name="Import IK Chains",
        description="Sets up the IK chains graph tag block in blender"
    )
    
    import_fp_arms: bpy.props.EnumProperty(
        name="FP Arms",
        description="Imports the First person arms along with the weapon and joins the skeletons",
        items=[
            ('NONE', "None", "Don't import first person arms"),
            ('SPARTAN', "Spartan", "Imports the Spartan first person arms"),
            ('ELITE', "Elite", "Imports the ELITE first person arms")
        ]
    )
    
    legacy_type: bpy.props.EnumProperty(
        name="JMS/ASS Type",
        description="Whether the importer should try to import a JMS/ASS file as a model, or bsp. Auto will determine this based on current asset type and contents of the JMS/ASS file",
        items=[
            ("auto", "Auto", ""),
            ("model", "Model", ""),
            ("bsp", "BSP", ""),
        ]
    )
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always Extract Bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not",
        options=set(),
    )
    
    import_variant_children: bpy.props.BoolProperty(
        name="Import Child Objects",
        description="Imports the child objects associated with this model variant",
        default=True,
        options={'SKIP_SAVE'},
    )
    
    amf_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    legacy_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    place_at_mouse : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    import_as_instanced_collection: bpy.props.BoolProperty(
        name="Import as Game Marker",
        description="Imports the object as a game marker with an instanced collection",
        default=True
    )
    
    from_vert_normals: bpy.props.BoolProperty(
        name="Store Model Vertex Normals",
        description="Stores a models vertex normals so that it can be reimported in game with the exact same vertex order. This is done automatically for PCA meshes, this option just applies the same to everything. Any edits to meshes with this setting will probably break normals on export"
    )
    
    mouse_x : bpy.props.FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
    mouse_y : bpy.props.FloatProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    def execute(self, context):
        bpy.ops.nwo.foundry_import(**self.as_keywords())
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y
        suffix = Path(self.filepath).suffix.lower()
        self.place_at_mouse = context.scene.nwo.asset_type == 'scenario' and (suffix == '.prefab' or suffix in OBJECT_TAG_EXTS)
        self.has_variants = False
        self.has_zone_sets = False
        self.import_type = Path(self.filepath).suffix[1:].lower()
        if context.scene.nwo.asset_type == "cinematic":
            self.tag_bsp_render_only = True
            self.tag_collision = False
            self.tag_physics = False
            # self.tag_animation = False
            self.tag_state = "default"
            
        if self.import_type == "amf":
            if utils.amf_addon_installed():
                self.amf_okay = True
            else:
                 self.report({'WARNING'}, "AMF Toolset not installed, cannot import AMF")
                 return {'CANCELLED'}
        elif self.import_type in {"jms", "ass", "jmm", "jma", "jmt", "jmz", "jmv", "jmw", "jmo", "jmr", "jmrx"}:
            if utils.blender_toolset_installed():
                self.legacy_okay = True
            else:
                self.report({'WARNING'}, "Blender Toolset not installed, cannot import JMS/ASS/JMA")
                return {'CANCELLED'}
            
        if self.import_type in {"camera_track", "jms", "ass", "model", "render_model", "scenario", "scenario_structure_bsp", "model_animation_graph", "biped", "crate", "creature", "device_control", "device_dispenser", "effect_scenery", "equipment", "giant", "device_machine", "projectile", "scenery", "spawner", "sound_scenery", "device_terminal", "vehicle", "weapon"}:
            if self.import_type == "scenario":
                global zone_set_items
                with ScenarioTag(path=self.filepath) as scenario:
                    zone_set_items = scenario.get_zone_sets_dict()
                    if zone_set_items:
                        self.has_zone_sets = True
            elif self.import_type in {"model", "biped", "crate", "creature", "device_control", "device_dispenser", "effect_scenery", "equipment", "giant", "device_machine", "projectile", "scenery", "spawner", "sound_scenery", "device_terminal", "vehicle", "weapon"}:
                global variant_items
                if self.import_type == "model":
                    with ModelTag(path=self.filepath) as model:
                        variant_items = model.get_model_variants()
                else:
                    with ObjectTag(path=self.filepath) as object_tag:
                        variant_items = object_tag.get_variants()
                if variant_items:
                    self.has_variants = True
            if self.place_at_mouse:
                return self.execute(context)
            else:
                return context.window_manager.invoke_props_dialog(self)
        else:
            return self.execute(context)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.label(text=f"Importing: {Path(self.filepath).name}")
        match self.import_type:
            case "model" | "biped" | "crate" | "creature" | "device_control" | "device_dispenser" | "effect_scenery" | "equipment" | "giant" | "device_machine" | "projectile" | "scenery" | "spawner" | "sound_scenery" | "device_terminal" | "vehicle" | "weapon":
                if self.has_variants:
                    layout.prop(self, "tag_variant")
                    if self.tag_variant != "all_variants":
                        layout.prop(self, "tag_state")
                        if self.tag_markers:
                            layout.prop(self, "import_variant_children")
                if not self.place_at_mouse:
                    layout.prop(self, "reuse_armature")
                    layout.prop(self, "tag_render")
                    layout.prop(self, "tag_markers")
                    layout.prop(self, "tag_collision")
                    layout.prop(self, "tag_physics")
                    layout.prop(self, "tag_animation")
                    layout.prop(self, "setup_as_asset")
                    layout.prop(self, "from_vert_normals")
                    if self.import_type == "weapon":
                        layout.prop(self, "import_fp_arms")
                    if self.tag_animation:
                        layout.prop(self, "tag_animation_filter")
                        layout.prop(self, "graph_import_animations")
                        layout.prop(self, "graph_generate_renames")
                        layout.prop(self, "graph_import_events")
                        layout.prop(self, "graph_import_ik_chains")
                layout.prop(self, "build_blender_materials")
                layout.prop(self, "always_extract_bitmaps")
            case "render_model":
                if self.has_variants:
                    layout.prop(self, "tag_variant")
                layout.prop(self, "tag_markers")
                layout.prop(self, "from_vert_normals")
                layout.prop(self, "build_blender_materials")
                layout.prop(self, "always_extract_bitmaps")
            case "scenario":
                layout.prop(self, "tag_zone_set")
                layout.prop(self, "tag_bsp_render_only")
                layout.prop(self, "setup_as_asset")
                layout.prop(self, "build_blender_materials")
                layout.prop(self, "always_extract_bitmaps")
            case "scenario_structure_bsp":
                layout.prop(self, "tag_bsp_render_only")
                layout.prop(self, "setup_as_asset")
                layout.prop(self, "build_blender_materials")
                layout.prop(self, "always_extract_bitmaps")
            case "model_animation_graph":
                layout.prop(self, "tag_animation_filter")
                layout.prop(self, "graph_import_animations")
                layout.prop(self, "graph_generate_renames")
                layout.prop(self, "graph_import_events")
                layout.prop(self, "graph_import_ik_chains")
            case "camera_track":
                layout.prop(self, "camera_track_animation_scale")
                layout.prop(self, "setup_as_asset")
            case "ass" | "jms":
                layout.prop(self, "legacy_type", expand=True)
            

class NWO_FH_Import(bpy.types.FileHandler):
    bl_idname = "NWO_FH_Import"
    bl_label = "File handler Foundry Importer"
    bl_import_operator = "nwo.import_from_drop"
    bl_file_extensions = ".jms;.amf;.ass;.bitmap;.model;.render_model;.scenario;.scenario_structure_bsp;.jmm;.jma;.jmt;.jmz;.jmv;.jmw;.jmo;.jmr;.jmrx;.camera_track;.particle_model;.biped;.crate;.creature;.device_control;.device_dispenser;.effect_scenery;.equipment;.giant;.device_machine;.projectile;.scenery;.spawner;.sound_scenery;.device_terminal;.vehicle;.weapon;.model_animation_graph"

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')
    
class NWO_OT_ImportBitmap(bpy.types.Operator):
    bl_idname = "nwo.import_bitmap"
    bl_label = "Bitmap Importer"
    bl_description = "Imports an image and loads it as the active image in the image editor or as a texture node depending on area context"
    bl_options = {"UNDO"}
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filename: bpy.props.StringProperty(options={'SKIP_SAVE'})
    filter_glob: bpy.props.StringProperty(
        default="*.bitmap",
        options={"HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        if Path(self.filepath).suffix != '.bitmap':
            return {'CANCELLED'}
        
        clear_path_cache()
        importer = NWOImporter(context, [self.filepath], ['bitmap'])
        extracted_bitmaps = importer.extract_bitmaps([self.filepath], 'tiff')
        images = importer.load_bitmaps(extracted_bitmaps, False)
        if images:
            if context.area.type == 'IMAGE_EDITOR':
                context.area.spaces.active.image = images[0]
            elif context.area.type == 'NODE_EDITOR' and context.material and context.material.use_nodes:
                tree = context.material.node_tree
                node = tree.nodes.new("ShaderNodeTexImage")
                node.image = images[0]
                for n in tree.nodes: n.select = False
                node.select = True
                node.location = context.region.view2d.region_to_view(self.mouse_x, self.mouse_y)
                    
        return {"FINISHED"}
    
    def invoke(self, context, event):
        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y
        return self.execute(context)
    
class NWO_FH_ImportBitmapAsImage(bpy.types.FileHandler):
    bl_idname = "NWO_FH_ImportBitmapAsImage"
    bl_label = "File handler Foundry Bitmap Importer"
    bl_import_operator = "nwo.import_bitmap"
    bl_file_extensions = ".bitmap"
    
    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'IMAGE_EDITOR')

    
class NWO_FH_ImportBitmapAsNode(bpy.types.FileHandler):
    bl_idname = "NWO_FH_ImportBitmapAsNode"
    bl_label = "File handler Foundry Bitmap Importer"
    bl_import_operator = "nwo.import_bitmap"
    bl_file_extensions = ".bitmap"
    
    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'NODE_EDITOR')
    
class NWO_OT_ImportShader(bpy.types.Operator):
    bl_idname = "nwo.import_shader"
    bl_label = "Shader Importer"
    bl_description = "Imports a shader/material tag"
    bl_options = {"UNDO"}
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE'})
    filename: bpy.props.StringProperty(options={'SKIP_SAVE'})
    filter_glob: bpy.props.StringProperty(
        default="*.shader;*.shader_decal;*.shader_terrain;",
        options={"HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        if Path(self.filepath).suffix not in utils.shader_exts:
            return {'CANCELLED'}
        
        mat = bpy.data.materials.new(str(Path(self.filepath).with_suffix("").name))
        shader_path = utils.relative_path(self.filepath)
        mat.nwo.shader_path = shader_path
        tag_to_nodes(utils.is_corinth(context), mat, shader_path)
        
        match self.area:
            case 'VIEW_3D':
                hit, face_location, face_normal, face_index, face_object, face_matrix = utils.ray_cast_mouse(context, (self.mouse_x, self.mouse_y))
                if hit and face_object.type in VALID_MESHES:
                    mesh = face_object.data
                    if mesh.materials and face_object.type == 'MESH':
                        mat_index = mesh.polygons[face_index].material_index
                        mesh.materials[mat_index] = mat
                    else:
                        mesh.materials.append(mat)
            case 'PROPERTIES' | 'NODE_EDITOR':
                if context.object and context.object.type in VALID_MESHES:
                    mesh = context.object.data
                    if context.material:
                        mat_index = mesh.materials.find(context.material.name)
                        mesh.materials[mat_index] = mat
                    else:
                        mesh.materials.append(mat)
                        
        
        self.report({'INFO'}, f"Imported {mat.name}")
                    
        return {"FINISHED"}
    
    def invoke(self, context, event):
        self.mouse_x = event.mouse_region_x
        self.mouse_y = event.mouse_region_y
        self.area = context.area.type
        return self.execute(context)
    
class NWO_FH_ImportShaderAsMaterial(bpy.types.FileHandler):
    bl_idname = "NWO_FH_ImportShaderAsMaterial"
    bl_label = "File handler Foundry Bitmap Importer"
    bl_import_operator = "nwo.import_shader"
    bl_file_extensions = ".shader;.shader_cortana;.shader_custom;.shader_decal;.shader_foliage;.shader_fur;.shader_fur_stencil;.shader_glass;.shader_halogram;.shader_mux;.shader_mux_material;.shader_screen;.shader_skin;.shader_terrain;.shader_water;.material"
    
    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type in {'NODE_EDITOR', 'VIEW_3D', 'PROPERTIES'})
    
def merge_collection(collection: bpy.types.Collection):
    """Reduces a collection down to just the meshes. Clearing markers and armatures"""
    utils.deselect_all_objects()
    mesh_found = False
    to_remove_objects = []
    for ob in collection.all_objects:
        if ob.type == 'MESH':
            ob.select_set(True)
            if not mesh_found:
                mesh_found = True
                bpy.context.view_layer.objects.active = ob
        else:
            to_remove_objects.append(ob)
            
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    
    for ob in to_remove_objects:
        bpy.data.objects.remove(ob)
        
    # bpy.ops.object.join()
    
    for ob in collection.all_objects:
        utils.unlink(ob)
        collection.objects.link(ob)
    
    for child in collection.children_recursive:
        bpy.data.collections.remove(child)
        
def setup_materials(context: bpy.types.Context, importer: NWOImporter, starting_materials: list[bpy.types.Material], imported_objects: list[bpy.types.Object], build_materials: bool, always_extract_bitmaps=False, emissive_meshes=set()):
    new_materials = [mat for mat in bpy.data.materials if mat not in starting_materials]
    # Clear duplicate materials
    missing_some_shader_paths = False
    if new_materials:
        new_materials = clear_duplicate_materials(True, new_materials)
        for m in new_materials:
            if not m.nwo.shader_path and utils.has_shader_path(m):
                missing_some_shader_paths = True
                break
    
    if missing_some_shader_paths:
        if utils.is_corinth(context):
            print('Updating material tag paths for imported objects')
        else:
            print('Updating shader tag paths for imported objects')
        imported_meshes: list[bpy.types.Mesh] = set([ob.data for ob in imported_objects if ob.type in VALID_MESHES])
        if imported_meshes:
            find_shaders(new_materials)
                
    if build_materials and new_materials:
        validated_funcs = set()
        sequence_drivers = {}
        if utils.is_corinth(context):
            print('Building Blender materials from material tags')
        else:
            print('Building Blender materials from shader tags')

        processed_shader_paths = {}
        
        for mat in new_materials:
            if not mat.users:
                bpy.data.materials.remove(mat)
                continue
            shader_path = mat.nwo.shader_path
            if shader_path:
                existing_mat = processed_shader_paths.get(shader_path)
                if existing_mat is None:
                    result = tag_to_nodes(importer.corinth, mat, shader_path, always_extract_bitmaps)
                    processed_shader_paths[shader_path] = mat
                    if result is not None:
                        sequence_drivers.update(result)
                else:
                    utils.copy_material_nodes(existing_mat, mat)
                    
                # TODO Add emissive node
                
        for ob in imported_objects:
            for slot in ob.material_slots:
                if slot.material:
                    functions = slot.material.nwo.game_functions.split(",") if slot.material.nwo.game_functions.strip(" ,") else []
                    if slot.material.nwo.object_functions.strip(" ,"):
                        validated_funcs.update(slot.material.nwo.object_functions.split(","))
                    if functions:
                        for func in functions:
                            bool_prop = add_function(context.scene, func, ob, ob.parent)
                            key = sequence_drivers.get(func)
                            if key is not None:
                                driver, sequence_length = key
                                driver: bpy.types.Driver
                                driver.variables[0].targets[0].id = ob
                                if not bool_prop:
                                    ob.id_properties_ui(func).update(min=0, max=sequence_length - 1)
                                ammo = func.startswith(ammo_names)
                                tether = func.startswith(tether_name)
                                if ammo or tether:
                                    result = ob.driver_add(f'["{func}"]')
                                    driver = result.driver
                                    driver.type = 'SCRIPTED'
                                    var = driver.variables.new()
                                    var.name = "var"
                                    var.type = 'SINGLE_PROP'
                                    var.targets[0].id = ob.parent
                                    var.targets[0].data_path = '["Tether Distance"]' if tether else '["Ammo"]'
                                    match func.rpartition("_")[2]:
                                        case "ones":
                                            driver.expression = f"({var.name} - floor({var.name} / 10) * 10) / {sequence_length}"
                                        case "tens":
                                            driver.expression = f"(floor({var.name} / 10) - floor({var.name} / 100) * 10) / {sequence_length}"
                                        case "hundreds":
                                            driver.expression = f"(floor({var.name} / 100) - floor({var.name} / 1000) * 10) / {sequence_length}"
                            
        for ob, func_dict in importer.obs_for_props.items():
            for export_name, funcs in func_dict.items():
                if export_name in validated_funcs:
                    for func in funcs:
                        add_function(context.scene, func, ob, ob.parent)
                        
                        
        # Apply emissives
        if emissive_meshes:
            print("Setting up emissive materials")
            for mesh in emissive_meshes:
                utils.setup_emissive_attributes(mesh)


class NWO_ImportGameInstanceTag(bpy.types.Operator):
    bl_idname = "nwo.import_game_instance_tag"
    bl_label = "Import Game Tag"
    bl_description = "Imports the tag referenced by this game instance marker and sets as the visual representation for the marker"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob is None or ob.type != 'EMPTY':
            return False
        
        if not ob.nwo.marker_game_instance_tag_name.strip():
            return False
        
        suffix = Path(ob.nwo.marker_game_instance_tag_name).suffix.lower()
        
        return suffix == ".prefab" or suffix in OBJECT_TAG_EXTS
    
    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always Extract Bitmaps",
        description="By default existing tiff files will be used for shaders. Checking this option means the bitmaps will always be re-extracted regardless if they exist or not",
        options=set(),
    )
    
    build_blender_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Builds Blender material nodes for materials based off their shader/material tags (if found)",
        default=True,
    )

    def execute(self, context):
        ob = context.object
        tag_path = ob.nwo.marker_game_instance_tag_name
        variant = ob.nwo.marker_game_instance_tag_variant_name.lower()
        
        tag_path_rel = utils.relative_path(tag_path)
        tag_path_full = Path(utils.get_tags_path(), tag_path_rel)
        
        if not tag_path_full.exists():
            self.report({'WARNING'}, f"Tag does not exist: {tag_path_full}")
            return {'CANCELLED'}
        
        game_object_collections = {(c.nwo.game_object_path, c.nwo.game_object_variant): c for c in utils.get_foundry_storage_scene().collection.children if c.nwo.game_object_path}
        
        collection = game_object_collections.get((tag_path_rel, variant))
        if collection is None:
            importer = NWOImporter(context)
            starting_materials = bpy.data.materials[:]
            
            if tag_path_full.suffix.lower() == ".prefab":
                collection = importer.import_prefab(ob)
            else:
                collection = importer.import_object(ob, None)
            if importer.needs_scaling:
                utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', context.scene.nwo.forward_direction, objects=collection.all_objects, actions=[])
                
            merge_collection(collection)
            context.scene.collection.children.unlink(collection)
            utils.get_foundry_storage_scene().collection.children.link(collection)
            collection.nwo.game_object_path = tag_path_rel
            collection.nwo.game_object_variant = variant
            
            setup_materials(context, importer, starting_materials, collection.all_objects, self.build_blender_materials, self.always_extract_bitmaps)
            
        ob.instance_type = 'COLLECTION'
        ob.instance_collection = collection
        ob.nwo.marker_instance = True
        
        ob.select_set(True)
        context.view_layer.objects.active = ob
        
        return {"FINISHED"}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "build_blender_materials")
        layout.prop(self, "always_extract_bitmaps")
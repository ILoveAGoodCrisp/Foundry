from collections import defaultdict
import datetime
import getpass
from pathlib import Path
import socket
import bmesh
import bpy
import csv
from math import degrees, radians
from mathutils import Matrix, Vector
from numpy import sign

from .export_info import ExportInfo
from ..tools.light_exporter import BlamLightDefinition, BlamLightInstance
from ..managed_blam.render_model import RenderModelTag
from ..managed_blam.animation import AnimationTag
from ..tools.materials import special_materials
from ..constants import VALID_MESHES, VALID_OBJECTS
from .. import utils

render_mesh_types = {
    "_connected_geometry_mesh_type_poop",
    "_connected_geometry_mesh_type_water_surface",
    "_connected_geometry_mesh_type_decorator",
    "_connected_geometry_mesh_type_object_instance",
    "_connected_geometry_mesh_type_poop_rain_blocker",
    "_connected_geometry_mesh_type_poop_vertical_rain_sheet"}

# Bone matrix constants

# PEDESTAL_MATRIX_X_POSITIVE = Matrix(((1.0, 0.0, 0.0, 0.0),
#                                 (0.0, 1.0, 0.0, 0.0),
#                                 (0.0, 0.0, 1.0, 0.0),
#                                 (0.0, 0.0, 0.0, 1.0)))

# PEDESTAL_MATRIX_Y_NEGATIVE = Matrix(((0.0, 1.0, 0.0, 0.0),
#                                     (-1.0, 0.0, 0.0, 0.0),
#                                     (0.0, 0.0, 1.0, 0.0),
#                                     (0.0, 0.0, 0.0, 1.0)))

# PEDESTAL_MATRIX_Y_POSITIVE = Matrix(((0.0, -1.0, 0.0, 0.0),
#                                     (1.0, 0.0, 0.0, 0.0),
#                                     (0.0, 0.0, 1.0, 0.0),
#                                     (0.0, 0.0, 0.0, 1.0)))

# PEDESTAL_MATRIX_X_NEGATIVE = Matrix(((-1.0, 0.0, 0.0, 0.0),
#                                     (0.0, -1.0, 0.0, 0.0),
#                                     (0.0, 0.0, 1.0, 0.0),
#                                     (0.0, 0.0, 0.0, 1.0)))

halo_light_rot = Matrix.Rotation(radians(90), 4, 'X') @ Matrix.Rotation(radians(180), 4, 'Z')

invalid_path = r"shaders\invalid"

#####################################################################################
#####################################################################################
# MAIN CLASS
class PrepareScene:
    '''
    Class for converting the blend scene to a state ready for export\n
    Handles converting the various halo properties to strings to be handled later by the json dumper\n
    Does lots of fixup to the objects to make sure they are ready for processing by Halo\n
    '''
    def __init__(self, context, asset_type, corinth, scene_settings, export_settings, asset_name):
        self.context = context
        self.asset_type = asset_type
        self.asset_name = asset_name
        self.corinth = corinth
        self.game_version = 'corinth' if corinth else 'reach'
        self.scene_settings = scene_settings
        self.export_settings = export_settings
        self.tags_dir = Path(utils.get_tags_path())
        self.data_dir = Path(utils.get_data_path())
        self.warning_hit = False
        self.bsps_with_structure = set()
        self.pedestal = None
        self.aim_pitch = None
        self.aim_yaw = None
        self.gun = None
        self.arm_name = ""
        self.prefs = utils.get_prefs()
        self.project = utils.get_project(scene_settings.scene_project)
        self.verbose_warnings = False
        self.no_export_objects = False
        self.too_many_root_bones = False
        self.scale_factor = 1
        self.objects_selection = set()
        self.scene_collection = context.scene.collection.objects
        self.area, self.area_region, self.area_space = utils.get_area_info(context)
        self.supports_regions_and_perms = asset_type in ('model', 'sky', 'scenario', 'prefab')
        self.validated_regions = set()
        self.validated_permutations = set()
        self.lods = set()
        self.skylights = {}
        self.physics_prims = set()
        self.default_shader_type = 'material' if corinth else 'shader'
        self.export_info = None
        
        if self.supports_regions_and_perms:
            self.regions = [entry.name for entry in context.scene.nwo.regions_table]
            self.permutations = [entry.name for entry in context.scene.nwo.permutations_table]
        else:
            self.regions = ['default']
            self.permutations = ['default']
            self.validated_regions.add('default')
            self.validated_permutations.add('default')
            
        self.default_region = self.regions[0]
        self.default_permutation = self.permutations[0]
        
        self.reg_name = 'BSP' if asset_type in ('scenario', 'prefab') else 'region'
        self.perm_name = 'layer' if asset_type in ('scenario', 'prefab') else 'permutation'
        
        self.emissive_factor = 0.328084 if scene_settings.scale == 'max' else 1
        
        self.has_global_mats = asset_type in ("model", "scenario", "prefab")

        self.global_materials = {"default"}
        self.seams = set()
        self.reach_sky_lights = set()
        self.lights = []
        
        self.lighting_tasks = []
        
        global render_mesh_types
        if not corinth or asset_type in ('model', 'sky'):
            render_mesh_types.add('_connected_geometry_mesh_type_default')
            
        self.model_armature = None
        self.root_bone_name = ''
        self.skeleton_bones = {}
        self.protected_names = set()
        self.used_materials = set()
        
        self.selected_perms = set()
        self.selected_bsps = set()
        
        self.null_path_materials = set()
        self.invalid_path_materials = set()
        
        self.timeline_start, self.timeline_end = self._set_timeline_range(context)
        self.current_action = None
        if bpy.data.actions:
            self.current_action = bpy.data.actions[scene_settings.active_action_index]
            context.scene.tool_settings.use_keyframe_insert_auto = False
        
    def ready_scene(self):
        '''
        Makes the scene ready to be parsed by ensuring object visibility and that
        a good blender unrestricted context is active
        '''
        print("\nPreparing Export Scene")
        print(f"{'-'*70}\n")
        # Exit local view. Must do this otherwise fbx export will fail.
        utils.exit_local_view(self.context)
        # Ensure context in object mode
        self.context.view_layer.update()
        utils.set_object_mode(self.context)
        # Save the currently selected objects. Used later to determine currently selected bsps/perms/layers
        self.objects_selection = self.context.selected_objects[:]
        utils.deselect_all_objects()
        utils.disable_excluded_collections(self.context)
        # Unhide collections. Hidden collections will stop objects in the collection being exported. We only want this functionality if the collection is disabled
        utils.unhide_collections(self.context)
        
    def make_real(self):
        '''
        Makes linked data real so it can be processed
        '''
        # Disabling prints for this to hide blender output
        utils.disable_prints()
        # Remove all marker instancing, we want to keep markers as empties
        markers = {ob for ob in self.context.view_layer.objects if ob.type == 'EMTPY' and not utils.library_instanced_collection(ob)}
        for ob in markers: ob.instance_type = 'NONE'
        # Save a list of curve & font objects
        curves = {ob for ob in bpy.data.objects if ob.type in ('FONT', 'CURVE')}
        instanced_objects = {ob for ob in bpy.data.objects if utils.library_instanced_collection(ob)}
        # Make instanced objects real
        if instanced_objects:
            with self.context.temp_override(selected_editable_objects=instanced_objects):
                bpy.ops.object.duplicates_make_real()
        # Remove new curves erroneously create during ops.object.duplicates_make_real()
        new_curves = {ob for ob in bpy.data.objects if ob.type in ('FONT', 'CURVE') and ob not in curves}
        for ob in new_curves: bpy.data.objects.remove(ob)
        # Make all library linked objects local to the blend file
        with self.context.temp_override(selected_editable_objects=bpy.data.objects):
            bpy.ops.object.make_local(type="ALL")
        # Purge orphaned objects
        # bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        utils.update_view_layer(self.context)
        utils.enable_prints()
        
    def clear_export_props(self):
        '''Clears custom properties beginning with bungie_'''
        for attr in dir(bpy.data):
            if "bpy_prop_collection" in str(type(getattr(bpy.data, attr))):
                for obj in getattr(bpy.data, attr):
                    for prop_name in list(obj.keys()):
                        if prop_name.startswith("bungie_"):
                            del obj[prop_name]
        
    def get_track_camera(self):
        '''
        Finds the camera to be used for a camera track set export
        '''
        self.camera = utils.get_camera_track_camera(self.context)
        if not self.camera:
            utils.print_warning('No Camera in scene, cannot export camera track')
            raise RuntimeError
        
    def unlink_non_export_objects(self):
        '''
        Unlinks non-exported objects from the scene so we avoid processing them\n
        '''
        # Unlinking objects is preferable to removing them as we don't want to break any object parentage/modifier reliance on non-export objects
        if self.asset_type == "animation":
            non_export_obs = {ob for ob in self.context.view_layer.objects if ob.type != "ARMATURE"}
        else:
            non_export_obs = {ob for ob in self.context.view_layer.objects if not ob.nwo.export_this or ob.type not in VALID_OBJECTS or (ob.type == 'EMTPY' and ob.empty_display_type == "IMAGE")}
        for ob in non_export_obs: utils.unlink(ob)
        utils.update_view_layer(self.context)
        
    def setup_skeleton(self):
        self.model_armature = utils.get_rig(self.context)
        if not self.model_armature: return
        if self.asset_type != "animation" and not self.model_armature.nwo.exportable:
            raise RuntimeError(f"Scene Armature [{self.model_armature.name}] is set to not export")
    
        if self.asset_type in ('model', 'animation') and self.scene_settings.main_armature and any((self.scene_settings.support_armature_a, self.scene_settings.support_armature_b, self.scene_settings.support_armature_c)):
            self._consolidate_rig()

        self.skeleton_bones = self._get_bone_list()
        utils.remove_relative_parenting(self.model_armature)
        self._fix_parenting()
        
        self.model_armature["bungie_frame_ID1"] = "8078"
        self.model_armature["bungie_frame_ID2"] = "378163771"
        if self.corinth:
            self.model_armature["bungie_frame_world"] = "1"
                
        if self.asset_type != "animation":
            for ob in self.context.view_layer.objects:
                if ob is not self.model_armature and not ob.parent:
                    old_matrix = ob.matrix_world.copy()
                    ob.parent = self.model_armature
                    ob.parent_type = "BONE"
                    ob.parent_bone = self.root_bone_name
                    ob.matrix_world = old_matrix
                    
    def add_structure_instance_proxies(self):
        '''
        Sets up copies of structure objects that have the instance flagged tickem
        These copies are setup as instances so that they are renderable and collidable
        '''
        proxy_owners = {ob for ob in self.context.view_layer.objects if utils.is_mesh(ob) and ob.nwo.mesh_type == '_connected_geometry_mesh_type_structure' and ob.nwo.proxy_instance}
        proxy_owner_data = {ob.data for ob in proxy_owners}
        
        proxy_owner_data_copies = {}
        for data in proxy_owner_data:
            data_copy = data.copy()
            
            data_copy.nwo.mesh_type = '_connected_geometry_mesh_type_default'
            proxy_owner_data_copies[data] = data_copy

        for ob in proxy_owners:
            proxy_instance = ob.copy()
            proxy_instance.data = proxy_owner_data_copies[ob.data]
            proxy_instance.name = f"{ob.name}(instance)"
            for collection in ob.users_collection:
                collection.objects.link(proxy_instance)
                
        utils.update_view_layer(self.context)
                
    def add_special_materials(self):
        '''
        Adds special materials to the blend file for use later
        '''
        materials = bpy.data.materials
        # create fixup materials
        for sm in special_materials:
            m = materials.get(sm.name)
            if not m:
                m = materials.new(sm.name)
            m["bungie_shader_path"] = sm.shader_path
            if self.corinth:
                m["bungie_shader_type"] = "material" # No support for material face props in H4, so always a material tag reference
            else:
                m["bungie_shader_type"] = 'override' if sm.is_face_property else 'shader' 
            match sm.name:
                case '+invisible':
                    self.invisible_mat = m
                case '+invalid':
                    self.invalid_mat = m
                case '+seamsealer':
                    self.seamsealer_mat = m
                case '+sky':
                    self.sky_mat = m
                case '+collision':
                    self.collision_mat = m
                case '+sphere_collision':
                    self.sphere_collision_mat = m
        
        self.default_mat = materials.get("+default")
        if self.default_mat is None:
            self.default_mat = materials.new("+default")
        
        default_shader = utils.relative_path(self.project.default_material)
        if Path(self.tags_dir, default_shader).exists():
            self._set_shader_props(self.default_mat, default_shader)
        else:
            utils.print_warning(f"Default shader/material tag does not exist: {default_shader}")
            self._set_shader_props(self.default_mat, invalid_path)
        
        # Not avaliable to user, but creating this to ensure water renders
        self.water_surface_mat = materials.get("+water")
        if self.water_surface_mat is None:
            self.water_surface_mat = materials.new("+water")
        
        default_water_shader = utils.relative_path(self.project.default_water)
        if Path(self.tags_dir, default_water_shader).exists():
            self.water_surface_mat["bungie_shader_path"] = str(Path(default_water_shader).with_suffix(''))
            self._set_shader_props(self.water_surface_mat, default_water_shader)
        else:
            utils.print_warning(f"Default water tag does not exist: {default_water_shader}")
            self._set_shader_props(self.water_surface_mat, invalid_path)
        
    def convert_area_lights(self):
        ''''
        Converts Area lights to emissive planes
        '''
        area_lights = {ob for ob in self.context.view_layer.objects if ob.type == 'LIGHT' and ob.data.type == 'AREA'}
        for light_ob in area_lights:
            collections = light_ob.users_collection
            plane_ob = utils.area_light_to_emissive(light_ob)
            for collection in collections:
                collection.objects.link(plane_ob)
            utils.unlink(light_ob)
        
        utils.update_view_layer(self.context)
        
    def setup_objects(self):
        '''
        Loops through export objects and completes a number of tasks:\n
        - Sets up export properties
        - Adjusts light transforms if Reach
        - Fixes missing materials
        '''
        
        process = "--- Object Validation"
        export_obs = self.context.view_layer.objects
        len_export_obs = len(export_obs)
        with utils.Spinner():
            utils.update_job_count(process, "", 0, len_export_obs)
            scenario_or_prefab = self.asset_type in ("scenario", "prefab")
            for idx, ob in enumerate(export_obs):
                nwo = ob.nwo
                ob_type = ob.type
                is_light = ob_type == 'LIGHT'
                
                is_mesh_loose = ob_type in VALID_MESHES

                # export objects must be visible and selectable
                ob.hide_set(False)
                ob.hide_select = False

                if is_light:
                    if not self.corinth and self.asset_type == 'sky':
                        self.reach_sky_lights.add(ob)
                        utils.unlink(ob)
                        continue

                self._strip_prefix(ob)
                
                object_type = utils.get_object_type(ob)
                ob["bungie_object_type"] = object_type

                if self.asset_type in ('model', 'sky', 'scenario', 'prefab'):
                    nwo.permutation_name = self.default_region if not nwo.permutation_name else nwo.permutation_name
                    nwo.region_name = self.default_permutation if not nwo.region_name else nwo.region_name
                    
                    # cast ui props to export props
                    if self.supports_regions_and_perms:
                        mesh_not_io = (object_type == '_connected_geometry_object_type_mesh' and nwo.mesh_type != '_connected_geometry_mesh_type_object_instance')
                        if is_light or scenario_or_prefab or mesh_not_io or nwo.marker_uses_regions:
                            reg = utils.true_region(nwo)
                            if reg in self.regions:
                                self.validated_regions.add(reg)
                                nwo.region_name = utils.true_region(nwo)
                            else:
                                self.warning_hit = True
                                utils.print_warning(f"Object [{ob.name}] has {self.reg_name} [{reg}] which is not presented in the {self.reg_name}s table. Setting {self.reg_name} to: {self.default_region}")
                                nwo.permutation_name = self.default_permutation
                            
                            if is_light or scenario_or_prefab or mesh_not_io:
                                perm = utils.true_permutation(nwo)
                                if perm in self.permutations:
                                    self.validated_permutations.add(perm)
                                    nwo.permutation_name = utils.true_permutation(nwo)
                                else:
                                    self.warning_hit = True
                                    utils.print_warning(f"Object [{ob.name}] has {self.perm_name} [{perm}] which is not presented in the {self.perm_name}s table. Setting {self.perm_name} to: {self.default_permutation}")
                                    nwo.permutation_name = self.default_permutation
                                    
                            elif nwo.marker_uses_regions and nwo.marker_permutation_type == 'include' and nwo.marker_permutations:
                                nwo.permutation_name = 'default'
                                marker_perms = [item.name for item in nwo.marker_permutations]
                                for perm in marker_perms:
                                    if perm in self.permutations:
                                        self.validated_permutations.add(perm)
                                    else:
                                        self.warning_hit = True
                                        utils.print_warning(f"Object [{ob.name}] has {self.perm_name} [{perm}] in its include list which is not presented in the {self.perm_name}s table. Ignoring {self.perm_name}")
                                    
                            else:
                                nwo.permutation_name = 'default'
                    else:
                        nwo.region_name = 'default'
                        nwo.permutation_name = 'default'
                
                if object_type == '_connected_geometry_object_type_none':
                    utils.unlink(ob)
                    continue
                
                elif is_light:
                    self.lights.append(ob)
                    utils.unlink(ob)
                
                elif object_type == '_connected_geometry_object_type_mesh':
                    if nwo.mesh_type == '':
                        nwo.mesh_type = '_connected_geometry_mesh_type_default'
                    if utils.type_valid(nwo.mesh_type, self.asset_type, self.game_version):
                        if not self._setup_mesh_properties(ob, scenario_or_prefab):
                            utils.unlink(ob)
                            continue
                        
                    else:
                        self.warning_hit = True
                        utils.print_warning(f"{ob.name} has invalid mesh type [{nwo.mesh_type}] for asset [{self.asset_type}]. Skipped")
                        utils.unlink(ob)
                        continue
                    
                elif object_type == '_connected_geometry_object_type_marker':
                    if nwo.marker_type == '':
                        nwo.marker_type = '_connected_geometry_marker_type_model'
                    if utils.type_valid(nwo.marker_type, self.asset_type, self.game_version):
                        self._setup_marker_properties(ob)
                    else:
                        self.warning_hit = True
                        utils.print_warning(f"{ob.name} has invalid marker type [{nwo.mesh_type}] for asset [{self.asset_type}]. Skipped")
                        utils.unlink(ob)
                        continue

                is_halo_render = is_mesh_loose and object_type == '_connected_geometry_object_type_mesh' and ob.get("bungie_mesh_type") in render_mesh_types

                # add region/global_mat to sets
                uses_global_mat = self.has_global_mats and (ob.get("bungie_mesh_type") in ("_connected_geometry_mesh_type_collision", "_connected_geometry_mesh_type_physics", "_connected_geometry_mesh_type_poop", "_connected_geometry_mesh_type_poop_collision") or self.asset_type == 'scenario' and not self.corinth and ob.get("bungie_mesh_type") == "_connected_geometry_mesh_type_default")
                if uses_global_mat:
                    self.global_materials.add(ob.get("bungie_face_global_material"))

                if self.export_settings.export_gr2s:
                    if is_mesh_loose:
                        # Add materials to all objects without one. No materials = unhappy Tool.exe
                        does_not_support_sky = ob.get("bungie_mesh_type") != '_connected_geometry_mesh_type_default' or self.asset_type != 'scenario'
                        self._fix_materials(ob, is_halo_render, does_not_support_sky)
                
                utils.update_job_count(process, "", idx, len_export_obs)

            utils.update_job_count(process, "", len_export_obs, len_export_obs)
    
    def write_lights_data(self):
        asset_path = utils.get_asset_path()
        lights = [BlamLightInstance(ob, ob.nwo.region_name) for ob in self.lights]
        if self.asset_type == 'scenario':
            bsps = [r.name for r in bpy.context.scene.nwo.regions_table if r.name.lower() != 'shared']
            lighting_info_paths = [str(Path(asset_path, f'{self.asset_name}_{b}.scenario_structure_lighting_info')) for b in bsps]
            for idx, info_path in enumerate(lighting_info_paths):
                b = bsps[idx]
                lights_list = [light for light in lights if light.bsp == b]
                if not lights_list:
                    if Path(self.tags_dir, utils.relative_path(info_path)).exists():
                        self.lighting_tasks.append([info_path])
                else:
                    light_instances = [light for light in lights_list]
                    light_data = {bpy.data.lights.get(light.data_name) for light in lights_list}
                    light_definitions = [BlamLightDefinition(data) for data in light_data]
                    self.lighting_tasks.append([info_path, light_instances, light_definitions])
                    
        elif self.corinth and self.asset_type in ('model', 'sky', 'prefab'):
            info_path = str(Path(asset_path, f'{self.asset_name}.scenario_structure_lighting_info'))
            if not lights:
                self.lighting_tasks.append([info_path])
            else:
                light_instances = [light for light in lights]
                light_data = {bpy.data.lights.get(light.data_name) for light in lights}
                light_definitions = [BlamLightDefinition(data) for data in light_data]
                self.lighting_tasks.append([info_path, light_instances, light_definitions])
                if self.asset_type in ('model', 'sky'):
                    self.lighting_tasks.append([str(Path(asset_path, f'{self.asset_name}.model')), info_path])
    
    def get_selected_sets(self):
        '''
        Get selected bsps/permutations from the objects selected at export
        '''
        sel_perms = self.export_settings.export_all_perms == "selected"
        sel_bsps = self.export_settings.export_all_bsps == "selected"
        current_selection = {ob for ob in self.context.view_layer.objects if ob in self.objects_selection}
        if sel_perms or sel_bsps:
            for ob in current_selection:
                nwo = ob.nwo
                if sel_perms: self.selected_perms.add(nwo.permutation_name)
                if sel_bsps: self.selected_bsps.add(nwo.region_name)
                
    def validate_shader_paths(self):
        '''
        Validates that shader paths point to existing tags\n
        Reports missing/invalid shader paths to user
        Sets the bungie_ props for materials
        '''
        
        for mat in self.used_materials:
            mat_nwo = mat.nwo
            if utils.has_shader_path(mat):
                shader = utils.relative_path(mat_nwo.shader_path)
                if not mat_nwo.shader_path.strip():
                    self.null_path_materials.add(mat)
                    self.warning_hit = True
                    self._set_shader_props(mat, invalid_path)
                        
                elif not Path(self.tags_dir, shader).exists():
                    self.invalid_path_materials.add(mat)
                    self.warning_hit = True
                    self._set_shader_props(mat, invalid_path)
                
                else:
                    self._set_shader_props(mat, shader)
                
        if self.null_path_materials:
            if self.corinth:
                utils.print_warning("\nFound blender materials with empty material tag paths:")
            else:
                utils.print_warning("\nFound blender materials with empty shader tag paths:")
                
            for m in self.null_path_materials:
                utils.print_warning(f'  {m.name}')
                
            print("")
                
        if self.invalid_path_materials:
            if self.corinth:
                utils.print_warning("\nFound blender materials with invalid material tag paths:")
            else:
                utils.print_warning("\nFound blender materials with invalid shader tag paths:")
                
            for m in self.invalid_path_materials:
                utils.print_warning(f'  {m.name}')
                
    def water_physics_from_surfaces(self):
        '''
        Creates water physics volumes from water surfaces
        '''
        water_surfaces = {ob for ob in self.context.view_layer.objects if ob.get("bungie_mesh_type") == '_connected_geometry_mesh_type_water_surface'}
        for ob_surf in water_surfaces: self._setup_water_physics(ob_surf)
        
        utils.update_view_layer(self.context)
        
    def build_seams(self):
        '''
        Adds matching backside seams necessary for Tool to correctly generate a structure_seams tag
        '''
        if not self.seams or len([r for r in self.regions if r.lower().strip() != 'shared']) < 2: return
        # if len(self.regions) < 2:
        #     self.warning_hit = True
        #     utils.print_warning("Only single BSP in scene, seam objects ignored from export")
        #     for seam in self.seams: utils.unlink(seam)
        #     utils.update_view_layer(self.context)
        #     return

        skip_seams = set()
        for seam in self.seams:
            if seam in skip_seams or seam.nwo.seam_back_manual: continue
            
            # add_triangle_mod(seam)
            seam_nwo = seam.nwo
            back_seam = seam.copy()
            back_seam.data = seam.data.copy()
            back_me = back_seam.data
            back_nwo = back_seam.nwo
            back_me.flip_normals()

            # apply new bsp association
            back_ui = seam_nwo.seam_back
            if (
                back_ui == ""
                or back_ui == seam_nwo.region_name
                or back_ui not in self.regions
            ):
                # this attempts to fix a bad back facing bsp ref
                self.warning_hit = True
                utils.print_warning(
                    f"{seam.name} has bad back facing bsp reference. Replacing with nearest adjacent bsp"
                )
                closest_bsp = utils.closest_bsp_object(self.context, seam, [ob for ob in self.context.view_layer.objects if ob in VALID_MESHES])
                if closest_bsp is None:
                    utils.print_warning(
                        f"Failed to automatically set back facing bsp reference for {seam.name}. Removing Seam from export"
                    )
                    utils.unlink(seam)
                else:
                    back_nwo.region_name = closest_bsp.nwo.region_name
            else:
                back_nwo.region_name = seam_nwo.seam_back

            back_seam.name = f"seam({back_nwo.region_name}:{seam_nwo.region_name})"
            back_seam["bungie_mesh_seam_associated_bsp"] = (f"{self.asset_name}_{back_nwo.region_name}")
            self.scene_collection.link(back_seam)
            
        utils.update_view_layer(self.context)
        
    def clean_poop_materials(self):
        '''
        Ensures no poops have a +sky face
        For Reach these are replaced with seamsealer, in h4+ the faces are deleted
        Also ensures poop_collision doesn't use seamsealer
        Removes invisible faces from render only poops
        '''
        to_cleanup = set()
        if self.corinth:
            poop_obs = {ob for ob in self.context.view_layer.objects if ob.get("bungie_mesh_type") == '_connected_geometry_mesh_type_poop'}
            poop_meshes = {ob.data for ob in poop_obs}
            poop_mesh_objects_dict = {data: [ob for ob in poop_obs if ob.data == data] for data in poop_meshes}
            poop_mesh_objects_dict = {data: objects_list for data, objects_list in poop_mesh_objects_dict.items() if objects_list}
            for data in poop_mesh_objects_dict.keys():
                material_names = [m.name for m in data.materials]
                sky_mat_indexes = set()
                for idx, name in enumerate(material_names):
                    if name.lower().startswith((self.sky_mat.name, self.seamsealer_mat.name)):
                        sky_mat_indexes.add(idx)
                        
                if sky_mat_indexes:
                    bm = bmesh.new()
                    bm.from_mesh(data)
                    sky_faces = [f for f in bm.faces if f.material_index in sky_mat_indexes]
                    bmesh.ops.delete(bm, geom=sky_faces, context='FACES')
                    bm.to_mesh(data)
                    bm.free()
                    for ob in poop_mesh_objects_dict[data]:
                        to_cleanup.add(ob)
        else:
            poop_objects = {ob for ob in self.context.view_layer.objects if ob.get("bungie_mesh_type") == '_connected_geometry_mesh_type_poop'}
            for ob in poop_objects:
                sky_slots = {slot for slot in ob.material_slots if slot.material and slot.material.name.lower().startswith(self.sky_mat.name)}
                if len(sky_slots) > 1: to_cleanup.add(ob)
                for slot in ob.material_slots:
                    if slot in sky_slots:
                        slot.material = self.seamsealer_mat
                        
        poop_collision_meshes = {ob for ob in self.context.view_layer.objects if ob.get("bungie_mesh_type") == '_connected_geometry_mesh_type_poop_collision'}
        for ob in poop_collision_meshes:
            to_replace = []
            for idx, mat in enumerate(ob.data.materials):
                if mat.name == self.seamsealer_mat.name:
                    to_replace.append(idx)
                    
            for idx in to_replace:
                ob.material_slots[idx].material = self.invalid_mat
                
        poop_render_obs = {ob: ob.data for ob in self.context.view_layer.objects if ob.get("bungie_mesh_type") == '_connected_geometry_mesh_type_poop' and ob.get("bungie_face_mode") == '_connected_geometry_face_mode_render_only'}
        poop_render_meshes = {ob.data for ob in poop_render_obs}
        poop_render_mesh_objects_dict = {data: [ob for ob in poop_render_obs if ob.data == data] for data in poop_render_meshes}
        poop_render_mesh_objects_dict = {data: objects_list for data, objects_list in poop_render_mesh_objects_dict.items() if objects_list}
        
        for data in poop_render_mesh_objects_dict.keys():
            material_names = [m.name for m in data.materials]
            invis_mat_indexes = set()
            for idx, name in enumerate(material_names):
                if name.lower().startswith((self.seamsealer_mat.name, self.invisible_mat.name)):
                    invis_mat_indexes.add(idx)
                    
            if invis_mat_indexes:
                bm = bmesh.new()
                bm.from_mesh(data)
                invis_faces = [f for f in bm.faces if f.material_index in invis_mat_indexes]
                bmesh.ops.delete(bm, geom=invis_faces, context='FACES')
                bm.to_mesh(data)
                bm.free()
                for ob in poop_render_mesh_objects_dict[data]:
                    to_cleanup.add(ob)
                    
        for ob in to_cleanup:
            utils.clean_materials(ob)
                
    def process_face_properties_and_proxies(self):
        '''
        Loops through all objects with face properties and recursively splits them into seperate meshes, storing face level properties at mesh level
        This function also handles applying instance proxies
        '''
        export_obs = self.context.view_layer.objects
        valid_mesh_types = (
            "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_poop",
            "_connected_geometry_mesh_type_default",
        )

        valid_for_face_properties_objects = {ob for ob in export_obs if ob.type == 'MESH' and ob.get("bungie_mesh_type") in valid_mesh_types and not ob.get("bungie_face_mode") == '_connected_geometry_face_mode_lightmap_only' and not (self.corinth and self.asset_type == 'scenario' and ob.get("bungie_mesh_type") == "_connected_geometry_mesh_type_default")}
        meshes = {ob.data for ob in valid_for_face_properties_objects}
        if not meshes: return
        
        mesh_objects_dict = {data: [ob for ob in valid_for_face_properties_objects if ob.data == data] for data in meshes}
        mesh_objects_dict = {data: objects_list for data, objects_list in mesh_objects_dict.items() if objects_list}

        process = "--- Processing Meshes"
        len_mesh_objects_dict = len(mesh_objects_dict)
        with utils.Spinner():
            utils.update_job_count(process, "", 0, len_mesh_objects_dict)
            for idx, (data, objects_list) in enumerate(mesh_objects_dict.items()):
                ob = objects_list[0]
                # Running instance proxy stuff here
                data_nwo = data.nwo
                ob_nwo = ob.nwo
                
                if ob.get("bungie_mesh_type") == '_connected_geometry_mesh_type_poop' and not ob_nwo.reach_poop_collision and not data_nwo.render_only:
                    self._setup_instance_proxies(data, objects_list)

                if self.export_settings.granny_export: continue # Skip this if we're debugging granny exports
                
                face_properties = data_nwo.face_props

                if face_properties:
                    bm = bmesh.new(use_operators=True)
                    bm.from_mesh(data)
                    # must ensure all faces are visible
                    for face in bm.faces: face.hide_set(False)

                    split_objects = self._split_to_layers(ob, ob_nwo, data, face_properties, bm, False)
                    # Can skip the below for loop if objects_list has a length of 1
                    if len(objects_list) > 1:
                        # copy all new face split objects to all linked objects
                        objects_list.remove(ob)
                        for linked_ob in objects_list:
                            for split_ob in split_objects:
                                new_ob = linked_ob
                                if linked_ob.data == split_ob.data:
                                    new_ob.name = split_ob.name
                                    for face_props in new_ob.data.nwo.face_props:
                                        self._face_prop_to_mesh_prop(face_props, new_ob)
                                else:
                                    new_ob = split_ob.copy()
                                    for collection in linked_ob.users_collection: collection.objects.link(new_ob)
                                    new_ob.matrix_world = linked_ob.matrix_world
                                    # linked objects might have different group assignments, ensure their split objects match this
                                    new_ob.nwo.region_name = linked_ob.nwo.region_name
                                    new_ob.nwo.permutation_name = linked_ob.nwo.permutation_name

                                if split_ob.children and not new_ob.children:
                                    new_ob["bungie_face_mode"] = "_connected_geometry_face_mode_render_only"
                                    for child in split_ob.children:
                                        if not child.nwo.proxy_parent:
                                            new_child = child.copy()
                                            for collection in new_ob.users_collection: collection.objects.link(new_child)
                                            new_child.parent = new_ob
                                            new_child.matrix_world = new_ob.matrix_world
                                            new_child.nwo.region_name = new_ob.nwo.region_name
                                            new_child.nwo.permutation_name = new_ob.nwo.permutation_name
                                            new_child.nwo.region_name = new_ob.nwo.region_name
                
                utils.update_job_count(process, "", idx, len_mesh_objects_dict)
                
            utils.update_job_count(process, "", len_mesh_objects_dict, len_mesh_objects_dict)
        
        utils.update_view_layer(self.context)
        
    def scene_transformation(self):
        '''
        Ensures all objects are unaffected by animation transforms\n
        Converts all relevant objects to meshes with their modifiers applied\n
        Transforms the scene ready, setting the scene to match x forward and 3ds Max scale
        '''
        export_obs = self.context.view_layer.objects
        utils.reset_to_basis(self.context)
        # Convert all mesh like objects to meshes and apply modifiers
        to_mesh(self.context, export_obs)
        # remove meshes with zero faces
        [utils.unlink(ob) for ob in export_obs if ob.type == "MESH" and not ob.data.polygons]
        # Transform the scene if needed to Halo Scale and forward
        self.scale_factor = transform_export_scene(self.context, self.scene_settings, self.export_settings.granny_export)
        utils.update_view_layer(self.context)
        # for ob in export_obs:
        #     if ob.type == 'MESH':
        #         # utils.set_origin_to_floor(ob) TODO Consider
        #         if ob.get("bungie_mesh_type") in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_collision"):
        #             while len(ob.data.polygons > 10000):
        #                 bm = bmesh.new()
        #                 bm.from_mesh(ob.data)
        #                 # TODO
                        
                
        update_physics_prims(self.physics_prims)
        
    def fixup_uv_names(self):
        '''
        Fix meshes with missing UV maps and align UV map names
        '''
        for data in {ob.data for ob in self.context.view_layer.objects if ob.type == 'MESH'}:
            uv_layers = data.uv_layers
            if uv_layers:
                for idx, uv_map in enumerate(uv_layers):
                    if uv_map.name != 'lighting' and uv_map.name != 'vertex_id':
                        uv_map.name = f"UVMap{idx}"
            else:
                uv_layers.new(name="UVMap0")
                
    def validate_scale(self):
        '''
        Validates object scales, applying them where needed\n
        Handles instance scale, applying non-uniform scales and fixing flipped normals where needed
        '''
        print("--- Validating Object Scales")
        good_scale = Vector.Fill(3, 1)
        # Validate armature scale. Allowing for uniform positive scale
        if self.model_armature and self.model_armature.scale != good_scale:
            arm_scale = self.model_armature.scale
            if arm_scale.x < 0 or arm_scale.y < 0 or arm_scale.z < 0:
                utils.print_warning("Armature has negative scale. Model & animations will look incorrect in game")
            elif not (arm_scale.x == arm_scale.y == arm_scale.z):
                utils.print_warning("Armature has non-uniform scale. Model & animations will look incorrect in game")
                
            utils.apply_armature_scale(self.context, self.model_armature)
            
        # Group objects by their meshes, spitting by instanced/non-instanced
        mesh_objects = {ob for ob in self.context.view_layer.objects if utils.is_mesh(ob)}
        uniform_io_objects = {ob for ob in mesh_objects if ob.get("bungie_mesh_type") in ('_connected_geometry_mesh_type_object_instance', '_connected_geometry_mesh_type_poop') and round(ob.scale.x, 4) == round(ob.scale.y, 4) == round(ob.scale.z, 4)}
        other_objects = {ob for ob in mesh_objects if ob not in uniform_io_objects}
        meshes = {ob.data for ob in mesh_objects}
        mesh_io_dict = {data: [ob for ob in uniform_io_objects if ob.data == data] for data in meshes}
        mesh_io_dict = {data: objects_list for data, objects_list in mesh_io_dict.items() if objects_list}
        mesh_other_dict = {data: [ob for ob in other_objects if ob.data == data] for data in meshes if data not in mesh_io_dict.keys()}
        mesh_other_dict = {data: objects_list for data, objects_list in mesh_other_dict.items() if objects_list}
        
        # Handle instances with uniform scaling. This is allowed but can be optimised to avoid extreme scale values
        for data, objects_list in mesh_io_dict.items():
            scales = {abs(ob.scale.x) for ob in objects_list}
            maximum_scale = max(scales)
            if maximum_scale > 10:
                scale_vector = Vector.Fill(3, maximum_scale / 10)
                for vert in data.vertices: vert.co *= scale_vector
                for ob in objects_list:
                    child_worlds = {child: child.matrix_world.copy() for child in ob.children}
                    ob.scale.x /= scale_vector.x
                    ob.scale.y /= scale_vector.y
                    ob.scale.z /= scale_vector.z
                    for child_ob, world in child_worlds.items():
                        child_ob.matrix_world = world
        
        # Must do this recursively since children are scaled during the process
        # This doesn't matter for instances as they should never have instance children
        self._recursive_scale_check(mesh_other_dict, good_scale)
                    
    def _recursive_scale_check(self, objects_dict: dict, good_scale: Vector):
        continue_checking_scale = False
        for data, objects_list in objects_dict.items():
            # group objects by whether their scale matches
            object_scale_dict = {ob.scale.copy().freeze(): [o for o in objects_list if o.scale == ob.scale] for ob in objects_list if ob.scale != good_scale}
            if object_scale_dict:
                continue_checking_scale = True
                for scale, objects in object_scale_dict.items():
                    if objects:
                        new_data = data.copy()
                        for vert in new_data.vertices: vert.co *= scale
                        # check if mesh was mirrored via scaling
                        if (sign(scale.x) * sign(scale.y) * sign(scale.z)) <= 0:
                            new_data.flip_normals()
                        for ob in objects:
                            child_worlds = {child: child.matrix_world.copy() for child in ob.children}
                            ob.data = new_data
                            ob.scale = good_scale
                            for child_ob, world in child_worlds.items():
                                child_ob.matrix_world = world
        if continue_checking_scale:
            self._recursive_scale_check(objects_dict, good_scale)
                
    def categorise_objects(self):
        # Establish a dictionary of scene global materials. Used later in export_gr2 and build_sidecar
        global_materials = ["default"]
        for glob_mat in self.global_materials:
            if glob_mat != "default" and glob_mat:
                global_materials.append(glob_mat)

        self.global_materials_dict = {global_material: str(idx) for idx, global_material in enumerate(global_materials) if global_material}

        # get all objects that we plan to export later
        self._halo_objects_init()
        self._halo_objects()

        utils.update_view_layer(self.context)
                
    def animation_fixup(self):
        if self.export_settings.export_gr2s and self.model_armature:
            self._force_fcurves_to_start_at_zero()

        if self.model_armature:
            self._set_animation_overrides()
    
    def get_decorator_lods(self):
        if self.asset_type == 'decorator_set':
            for ob in self.render: self.lods.add(self._decorator_int(ob))
        
    def validate_sets(self):
        null_regions = {r for r in self.regions if r not in self.validated_regions}
        if null_regions:
            
            print('')
            for r in null_regions:
                if self.asset_type == 'scenario' and r.lower() == 'shared': continue
                self.warning_hit = True
                utils.print_warning(f'No export object has {self.reg_name}: {r}')
                
            self.regions = [r for r in self.regions if r not in null_regions]
            
        null_permutations = {p for p in self.permutations if p not in self.validated_permutations}
        if null_permutations:
            self.warning_hit = True
            print('')
            for p in null_permutations:
                utils.print_warning(f'No export object has {self.perm_name}: {p}')
                
            self.permutations = [p for p in self.permutations if p not in null_permutations]
            
        # Order these to match regions/perms table
        if len(self.structure_bsps) > 1:
            self.structure_bsps = [b for b in self.regions if b in self.structure_bsps]
        if len(self.structure_perms) > 1:
            self.structure_perms = [l for l in self.permutations if l in self.structure_perms]
        if len(self.design_bsps) > 1:
            self.design_bsps = [b for b in self.regions if b in self.design_bsps]
        if len(self.design_perms) > 1:
            self.design_perms = [l for l in self.permutations if l in self.design_perms]
            
        if self.asset_type in ('model', 'sky'):
            for ob in self.context.view_layer.objects:
                if ob.type == 'MESH':
                    ob["bungie_face_region"] = ob.nwo.region_name
            
    def generate_structure(self):
        bsps_in_need = {bsp for bsp in self.structure_bsps if bsp not in self.bsps_with_structure}
        if not bsps_in_need: return
        default_bsp_part = self.default_permutation
        for bsp in bsps_in_need:
            bsp_obs = {ob for ob in self.context.view_layer.objects if ob.nwo.region_name == bsp}
            structure = self._wrap_bounding_box(bsp_obs, 0 if self.corinth else 0.01)
            structure_mesh = structure.data
            nwo = structure.nwo
            if self.corinth:
                structure_mesh.materials.append(self.invalid_mat)
                structure["bungie_face_type"] = '_connected_geometry_face_type_sky'
            else:
                structure_mesh.materials.append(self.sky_mat)
            nwo.region_name = bsp
            nwo.permutation_name = default_bsp_part
            self.structure.add(structure)
            
        utils.update_view_layer(self.context)
    
    def add_null_render_if_needed(self):
        if self.render: return
        self.render = {self._add_null_render()}
        utils.update_view_layer(self.context)
        
    def setup_skylights(self):
        if not self.reach_sky_lights: return
        if self.scale_factor != 1:
            light_scale = 0.03048 ** 2
            sun_scale = 0.03048
        else:
            light_scale = 1
            sun_scale = 1
        sun = None
        lightGen_colors = []
        lightGen_directions = []
        lightGen_solid_angles = []
        for ob in self.reach_sky_lights:
            if (ob.data.energy * light_scale) < 0.01:
                sun = ob
            down = Vector((0, 0, -1))
            down.rotate(ob.rotation_euler)
            lightGen_colors.append(utils.color_3p_str(ob.data.color))
            lightGen_directions.append(f'{utils.jstr(down[0])} {utils.jstr(down[1])} {utils.jstr(down[2])}')
            lightGen_solid_angles.append(utils.jstr(ob.data.energy * light_scale))
            
        self.skylights['lightGen_colors'] = ' '.join(lightGen_colors)
        self.skylights['lightGen_directions'] = ' '.join(lightGen_directions)
        self.skylights['lightGen_solid_angles'] = ' '.join(lightGen_solid_angles)
        self.skylights['lightGen_samples'] = str(len(self.reach_sky_lights) - 1)
        
        if sun is not None:
            if sun.data.color.v > 1:
                sun.data.color.v = 1
            self.skylights['sun_size'] = utils.jstr((max(sun.scale.x, sun.scale.y, sun.scale.z) * sun_scale))
            self.skylights['sun_intensity'] = utils.jstr(sun.data.energy * 10000 * light_scale)
            self.skylights['sun_color'] = utils.color_3p_str(sun.data.color)
            
    def finalize(self):
        # Create BungieExportInfo
        self.global_materials = [i for i in self.global_materials if i is not None]
        self.export_info = ExportInfo(self.regions, self.global_materials).create_info()
        
        # self.apply_shading()
        
        if self.warning_hit:
            utils.print_warning(
                "\nScene has issues that should be resolved for subsequent exports"
            )
            utils.print_warning("Please see above output for details")
            
    def apply_shading(self):
        meshes = set()
        for ob in self.context.view_layer.objects:
            if ob.type == 'MESH': meshes.add(ob.data)
            
        for mesh in meshes:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            if mesh.has_custom_normals:
                bm.normal_update()  # Update normals to ensure they reflect any changes
                custom_loop_normals = [loop.normal for loop in mesh.loops]
            edges_to_split = set()
            for face in bm.faces:
                if not face.smooth:
                    edges_to_split.update(face.edges)
                    
            for edge in bm.edges:
                if edge.smooth == False:
                    edges_to_split.add(edge)
            
            result = bmesh.ops.split_edges(bm, edges=list(edges_to_split))
            
            if mesh.has_custom_normals:
                # Map the old loops to the new loops after the split
                old_loops = [elem for elem in result["geom_split"] if isinstance(elem, bmesh.types.BMLoop)]
                
                for old_loop, new_loop in zip(old_loops, result['geom_split']):
                    if isinstance(new_loop, bmesh.types.BMLoop):
                        # Assign the custom normal to the new loop
                        new_loop.normal = custom_loop_normals[old_loop.index]
            
            bmesh.ops.triangulate(bm, faces=bm.faces)
            bm.to_mesh(mesh)
            bm.free()
            
            
########################################################################################################################################
# HELPER FUNCTIONS
########################################################################################################################################

    def _justify_face_split(self, face_sequences, poly_count):
        """Checked whether we actually need to split this mesh up"""
        # check if face layers cover the whole mesh, if they do, we don't need to split the mesh
        for face_seq in face_sequences:
            if not face_seq:continue
            face_count = len(face_seq)
            if not face_count: continue
            if poly_count != face_count:
                return True

        return False
            
    def _strip_nocoll_only_faces(self, prop_faces_dict, bm):
        """Removes faces from a mesh that shouldn't be used to build proxy collision"""
        for prop, face_seq in prop_faces_dict.items():
            if prop.render_only_override or prop.sphere_collision_only_override or prop.breakable_override:
                bmesh.ops.delete(bm, geom=face_seq, context="FACES")

        return len(bm.faces)
    
    def _get_collision_only_face_indexes(self, prop_faces_dict):
        face_indexes = set()
        for prop, face_seq in prop_faces_dict.items():
            if prop.collision_only_override:
                face_indexes.update(face_seq)
                
        return face_indexes

    
    def _coll_proxy_two_sided(self, ob, bm: bmesh.types.BMesh):
        for props in ob.data.nwo.face_props:
            if props.face_two_sided_override:
                if utils.layer_face_count(bm, bm.faces.layers.int.get(props.layer_name)):
                    return True
            
        return False

    def _split_to_layers(self, ob: bpy.types.Object, ob_nwo, data, face_properties, bm, is_proxy):
        poly_count = len(bm.faces)
        face_layers = bm.faces.layers.int
        prop_faces_dict = {prop: utils.layer_face_indexes(bm, face_layers.get(prop.layer_name)) for prop in face_properties}
        face_sequences = list(prop_faces_dict.values())
        collision_ob = None
        justified = self._justify_face_split(face_sequences, poly_count)
        bm.to_mesh(data)

        if justified:
            save_normals = ob.get("bungie_mesh_type") in render_mesh_types
            if save_normals:
                utils.save_loop_normals(bm, data)

            is_poop = ob.get("bungie_mesh_type") == "_connected_geometry_mesh_type_poop"
            if is_poop and not self.corinth:
                ob["bungie_face_mode"] = "_connected_geometry_face_mode_render_only"
                has_coll_child = any(child["bungie_mesh_type"] == '_connected_geometry_mesh_type_poop_collision' for child in ob.children)

                if not has_coll_child:
                    collision_face_indexes = self._get_collision_only_face_indexes(prop_faces_dict)
                    if len(collision_face_indexes) == len(ob.data.polygons):
                        ob["bungie_face_mode"] = "_connected_geometry_face_mode_collision_only"
                        return [ob]

                    collision_ob = ob.copy()
                    collision_ob.pop("bungie_face_mode", None)
                    collision_ob.data = data.copy()
                    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index in collision_face_indexes], context='FACES')
                    for collection in ob.users_collection:
                        collection.objects.link(collision_ob)

                    coll_bm = bmesh.new()
                    coll_bm.from_mesh(collision_ob.data)
                    coll_layer_faces_dict = {layer: utils.layer_faces(coll_bm, coll_bm.faces.layers.int.get(layer.layer_name)) for layer in face_properties}
                    self._strip_nocoll_only_faces(coll_layer_faces_dict, coll_bm)

                    coll_bm.to_mesh(collision_ob.data)
                    collision_ob.name = f"{ob.name}(collision)"
                    if self._coll_proxy_two_sided(collision_ob, coll_bm):
                        collision_ob["bungie_face_sides"] = "_connected_geometry_face_sides_two_sided"
                    coll_bm.free()
                    collision_ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_poop_collision"
                    collision_ob.matrix_world = ob.matrix_world.copy()

            remaining_faces = {f.index for f in bm.faces if all(f.index not in fseq for fseq in face_sequences)}
            prop_faces_dict["|~~no_face_props~~|"] = remaining_faces

            layers = [face_layers.get(prop.layer_name) for prop in face_properties]
            polygons = [tuple(face[l] for l in layers) for face in bm.faces]
            
            property_groups = defaultdict(list)
            for index, polygon in enumerate(polygons):
                property_groups[polygon].append(index)

            indices_list = list(property_groups.values())
            split_objects = [ob]

            for indices in indices_list[1:]:
                new_ob = ob.copy()
                new_me = ob.data.copy()
                new_ob.data = new_me
                new_bm = bm.copy()
                new_bm.faces.ensure_lookup_table()
                keep_faces = {new_bm.faces[i] for i in indices}
                bmesh.ops.delete(new_bm, geom=[f for f in new_bm.faces if f not in keep_faces], context='FACES')
                new_bm.to_mesh(new_ob.data)
                new_bm.free()
                split_objects.append(new_ob)
                if not is_proxy:
                    for collection in ob.users_collection:
                        collection.objects.link(new_ob)

            bm.faces.ensure_lookup_table()
            keep_faces = {bm.faces[i] for i in indices_list[0]}
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in keep_faces], context='FACES')
            bm.to_mesh(ob.data)
            bm.free()

            ori_ob_name = str(ob.name)
            for nrm_ob in split_objects:
                if save_normals:
                    utils.apply_loop_normals(nrm_ob.data)
                utils.clean_materials(nrm_ob)

            for split_ob in split_objects:
                obj_bm = bmesh.new()
                obj_bm.from_mesh(split_ob.data)
                obj_name_suffix = ""
                more_than_one_prop = False
                for layer in split_ob.data.nwo.face_props:
                    if utils.layer_face_count(obj_bm, obj_bm.faces.layers.int.get(layer.layer_name)):
                        self._face_prop_to_mesh_prop(layer, split_ob)
                        if more_than_one_prop:
                            obj_name_suffix += ", "
                        else:
                            more_than_one_prop = True
                        obj_name_suffix += layer.name
                obj_bm.free()
                split_ob.name = f"{ori_ob_name}({obj_name_suffix})" if obj_name_suffix else ori_ob_name

            if is_poop:
                parent_ob = None
                if collision_ob:
                    for split_ob in reversed(split_objects):
                        if split_ob.get("bungie_face_mode") not in ("_connected_geometry_face_mode_collision_only", "_connected_geometry_face_mode_sphere_collision_only", "_connected_geometry_face_mode_breakable"):
                            parent_ob = split_ob
                            break
                    else:
                        collision_ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_poop"
                        collision_ob["bungie_face_mode"] = "_connected_geometry_face_mode_collision_only"

                    if parent_ob:
                        collision_ob.parent = parent_ob
                        collision_ob.matrix_world = ob.matrix_world.copy()

                    coll_only_objects = {split_ob for split_ob in split_objects if split_ob.get("bungie_face_mode") == "_connected_geometry_face_mode_collision_only"}
                    for coll_obj in coll_only_objects:
                        utils.unlink(coll_obj)
                    split_objects = [obj for obj in split_objects if obj not in coll_only_objects]

            return split_objects
        else:
            for face_props in face_properties:
                self._face_prop_to_mesh_prop(face_props, ob)
            return [ob]
        
            
    def _face_prop_to_mesh_prop(self, face_props, ob):
        is_poop = ob.get("bungie_mesh_type") == "_connected_geometry_mesh_type_poop"
        if face_props.render_only_override:
            if self.corinth:
                ob["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_none"
            else:
                ob["bungie_face_mode"] = "_connected_geometry_face_mode_render_only"
        elif face_props.collision_only_override:
            if self.corinth:
                ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_poop_collision"
                ob["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_default"
            else:
                ob["bungie_face_mode"] = "_connected_geometry_face_mode_collision_only"
        elif face_props.sphere_collision_only_override:
            if self.corinth:
                ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_poop_collision'
                ob["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_invisible_wall"
            else:
                ob["bungie_face_mode"] = "_connected_geometry_face_mode_sphere_collision_only"
        elif self.corinth and face_props.player_collision_only_override:
            ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_poop_collision'
            ob["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_play_collision"
        elif self.corinth and face_props.bullet_collision_only_override:
            ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_poop_collision'
            ob["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_bullet_collision"
            
        if not self.corinth and face_props.breakable_override:
            ob["bungie_face_mode"] = '_connected_geometry_face_mode_breakable'
            
        if self.asset_type in ('model', 'sky') and ob["bungie_mesh_type"] in render_mesh_types and face_props.face_draw_distance_override:
            ob["bungie_face_draw_distance"] = face_props.face_draw_distance
            
        if face_props.mesh_tessellation_density_override and face_props.mesh_tessellation_density != "_connected_geometry_mesh_tessellation_density_none":
                ob["bungie_mesh_tessellation_density"] = face_props.mesh_tessellation_density

        # Handle face sides, game wants an enum but Foundry uses flags
        face_sides_value = "_connected_geometry_face_sides_"
        has_transparency = face_props.face_transparent_override and ob["bungie_mesh_type"] in render_mesh_types
        if face_props.face_two_sided_override:
            # Only h4+ support properties for the backside face
            if self.corinth and ob["bungie_mesh_type"] in render_mesh_types:
                face_sides_value += face_props.face_two_sided_type
            else:
                face_sides_value += "two_sided"
            # Add transparency if set
            if has_transparency:
                face_sides_value += "_transparent"
            ob["bungie_face_sides"] = face_sides_value
            
        elif has_transparency:
            face_sides_value += "one_sided_transparent"
            ob["bungie_face_sides"] = face_sides_value

        if face_props.region_name_override:
            reg = face_props.region_name
            
            if reg in self.regions:
                self.validated_regions.add(reg)
                ob.nwo.region_name = reg
            else:
                self.warning_hit = True
                utils.print_warning(f"Object [{ob.name}] has {self.reg_name} face property [{reg}] which is not present in the {self.reg_name}s table. Setting {self.reg_name} to: {self.default_region}")
                ob.nwo.region_name = self.default_region

        if face_props.face_global_material_override:
            glob_mat = face_props.face_global_material.strip().replace(' ', "_")
            self._set_global_material_prop(ob, global_material=glob_mat)
            self.global_materials.add(glob_mat)

        if face_props.ladder_override:
            ob["bungie_ladder"] = "1"

        if face_props.slip_surface_override:
            ob["bungie_slip_surface"] = "1"

        if face_props.decal_offset_override:
            ob["bungie_decal_offset"] = "1"
            if is_poop:
                ob["bungie_mesh_poop_decal_spacing"] = "1"

        if face_props.no_shadow_override:
            ob["bungie_no_shadow"] = "1"

        if face_props.precise_position_override:
            ob["bungie_precise_position"] = "1"
            # ob["bungie_mesh_additional_compression"] = "_connected_geometry_mesh_additional_compression_force_off"
            if is_poop:
                ob["bungie_mesh_poop_precise_geometry"] = "1"

        if face_props.no_lightmap_override:
            ob["bungie_no_lightmap"] = "1"

        if face_props.no_pvs_override:
            ob["bungie_invisible_to_pvs"] = "1"

        # lightmap props
        if face_props.lightmap_additive_transparency_override:
            ob["bungie_lightmap_transparency_override"] = "1"
            ob["bungie_lightmap_additive_transparency"] = utils.color_4p_str(face_props.lightmap_additive_transparency)

        if face_props.lightmap_resolution_scale_override:
            ob["bungie_lightmap_resolution_scale"] = utils.jstr(face_props.lightmap_resolution_scale)
        if face_props.lightmap_type_override:
            ob["bungie_lightmap_type"] = face_props.lightmap_type
            
        if face_props.lightmap_translucency_tint_color_override:
            ob["bungie_lightmap_translucency_tint_color"] = utils.color_4p_str(face_props.lightmap_translucency_tint_color)
        if face_props.lightmap_lighting_from_both_sides_override:
            ob["bungie_lightmap_lighting_from_both_sides"] = "1"
            
        # emissive props
        if face_props.emissive_override:
            if self.corinth:
                ob["bungie_lighting_emissive_power"] = utils.jstr(face_props.material_lighting_emissive_power / 30)
            else:
                ob["bungie_lighting_emissive_power"] = utils.jstr(face_props.material_lighting_emissive_power)
                
            if face_props.material_lighting_attenuation_falloff or face_props.material_lighting_attenuation_cutoff:
                ob["bungie_lighting_attenuation_enabled"] = "1"
                ob["bungie_lighting_attenuation_falloff"] = utils.jstr(face_props.material_lighting_attenuation_falloff * 100 * 0.03048 * self.emissive_factor)
                ob["bungie_lighting_attenuation_cutoff"] = utils.jstr(face_props.material_lighting_attenuation_cutoff * 100 * 0.03048 * self.emissive_factor)
            else:
                ob["bungie_lighting_attenuation_enabled"] = "0"

            ob["bungie_lighting_emissive_focus"] = utils.jstr(degrees(face_props.material_lighting_emissive_focus) / 180)
            ob["bungie_lighting_emissive_color"] = utils.color_4p_str(face_props.material_lighting_emissive_color)
            ob["bungie_lighting_emissive_per_unit"] =  utils.bool_str(face_props.material_lighting_emissive_per_unit)
            ob["material_lighting_emissive_quality"] =  utils.jstr(face_props.material_lighting_emissive_quality)
            ob["material_lighting_use_shader_gel"] =  utils.bool_str(face_props.material_lighting_use_shader_gel)
            ob["bungie_lighting_bounce_ratio"] = utils.jstr(face_props.material_lighting_bounce_ratio)

        # added two sided property to avoid open edges if collision prop
        if not self.corinth:
            is_poop = ob.get("bungie_mesh_type") == "_connected_geometry_mesh_type_poop"
            if is_poop and (ob.get("bungie_ladder") or ob.get("bungie_slip_surface")):
                special_ob = ob.copy()
                for collection in ob.users_collection: collection.objects.link(special_ob)
                if ob.get("bungie_ladder"):
                    del ob["bungie_ladder"]
                if ob.get("bungie_slip_surface"):
                    del ob["bungie_slip_surface"]
                special_ob["bungie_face_sides"] = "_connected_geometry_face_sides_two_sided"
                special_ob["bungie_face_mode"] = "_connected_geometry_face_mode_sphere_collision_only"
    
    def _set_shader_props(self, material, shader="", ext=""):
        '''
        Writes shader path and type to a materials custom properties
        If no shader path is passed, this is taken from the materials nwo.shader_path property
        The shader path extension can be overwritten if an ext argument is passed
        '''
        if not shader:
            shader = material.nwo.shader_path
        shader_path = Path(shader)
        if ext:
            if ext[0] != '.': ext = '.' + ext
            shader_path = shader_path.with_suffix(ext)
            
        if len(shader_path.suffix) < 2:
            shader_path = shader_path.with_suffix(f'.{self.default_shader_type}')
        
        material["bungie_shader_path"] = str(shader_path.with_suffix(""))
        material["bungie_shader_type"] = shader_path.suffix[1:]
    
    def _setup_water_physics(self, ob_surface):
        collections = ob_surface.users_collection
        if ob_surface.nwo.water_volume_depth:
            ob_physics = ob_surface.copy()
            for collection in collections: collection.objects.link(ob_physics)
            nwo = ob_physics.nwo
            if ob_physics.get("mesh_tessellation_density"):
                del ob_physics["mesh_tessellation_density"]
                
            ob_physics["bungie_mesh_type"] = "_connected_geometry_mesh_type_water_physics_volume"
            ob_physics["bungie_mesh_water_volume_depth"] = utils.jstr(nwo.water_volume_depth)
            ob_physics["bungie_mesh_water_volume_flow_direction"] = utils.jstr(degrees(nwo.water_volume_flow_direction))
            ob_physics["bungie_mesh_water_volume_flow_velocity"] = utils.jstr(nwo.water_volume_flow_velocity)
            ob_physics["bungie_mesh_water_volume_fog_murkiness"] = utils.jstr(nwo.water_volume_fog_murkiness)
            if self.corinth:
                ob_physics["bungie_mesh_water_volume_fog_color"] = utils.color_rgba_str(nwo.water_volume_fog_color)
            else:
                ob_physics["bungie_mesh_water_volume_fog_color"] = utils.color_argb_str(nwo.water_volume_fog_color)

    def _setup_instance_proxies(self, data, linked_objects):
        if self.asset_type in ("scenario", "prefab"):
            proxy_physics = None #data.nwo.proxy_physics # NOTE temp whilst new pipeline is built
            proxy_collision = data.nwo.proxy_collision
            proxy_cookie_cutter = data.nwo.proxy_cookie_cutter
            
            coll = proxy_collision is not None
            phys = proxy_physics is not None
            cookie = proxy_cookie_cutter is not None and not self.corinth
            
            if phys:
                proxy_physics["bungie_object_type"] = "_connected_geometry_object_type_mesh"
                # glob_mat_phys = proxy_physics.data.nwo.face_global_material.strip().replace(" ", "_")
                # if glob_mat_phys:
                #     self._set_global_material_prop(proxy_physics, global_material=glob_mat_phys)
                #     self.global_materials.add(glob_mat_phys)

                if self.corinth:
                    proxy_physics["bungie_mesh_type"] = "_connected_geometry_mesh_type_poop_collision"
                    proxy_physics["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_play_collision"
                    # split_physics = self._proxy_face_split(proxy_physics)
                else:
                    # Physics gets split by parts
                    proxy_physics["bungie_mesh_type"] = "_connected_geometry_mesh_type_poop_physics"
                    bpy.context.scene.collection.objects.link(proxy_physics)
                    proxy_physics.select_set(True)
                    utils.set_active_object(proxy_physics)
                    bpy.ops.object.editmode_toggle()
                    for v in proxy_physics.data.vertices: v.select = True
                    bpy.ops.mesh.separate(type="LOOSE")
                    for v in proxy_physics.data.vertices: v.select = False
                    bpy.ops.object.editmode_toggle()
                    split_physics = bpy.context.selected_objects
                    utils.deselect_all_objects()

            if coll:
                proxy_collision["bungie_object_type"] = "_connected_geometry_object_type_mesh"
                proxy_collision["bungie_mesh_type"] = "_connected_geometry_mesh_type_poop_collision"
                glob_mat_coll = proxy_collision.data.nwo.face_global_material
                if glob_mat_coll:
                    self._set_global_material_prop(proxy_collision, global_material=glob_mat_coll)
                    self.global_materials.add(glob_mat_coll)
                if self.corinth:
                    if phys:
                        proxy_collision["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_bullet_collision"
                    else:
                        proxy_collision["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_default"

                    # split_collision = self._proxy_face_split(proxy_collision)
                else:
                    self._set_proxy_collision_props(proxy_collision)

            
            if cookie:
                proxy_cookie_cutter["bungie_object_type"] = "_connected_geometry_object_type_mesh"
                proxy_cookie_cutter["bungie_mesh_type"] = "_connected_geometry_mesh_type_cookie_cutter"

            if phys or coll or cookie:
                poops = {o for o in linked_objects if o["bungie_mesh_type"] == "_connected_geometry_mesh_type_poop"}
                for ig in poops:
                    if coll:
                        if self.corinth:
                            o_collision = proxy_collision.copy()
                            for collection in ig.users_collection: collection.objects.link(o_collision)
                            o_collision.parent = ig
                            o_collision.matrix_world = ig.matrix_world
                            o_collision.nwo.region_name = ig.nwo.region_name
                            o_collision.nwo.permutation_name = ig.nwo.permutation_name
                        else:
                            ig["bungie_face_mode"] = "_connected_geometry_face_mode_render_only"
                            o_collision = proxy_collision.copy()
                            for collection in ig.users_collection: collection.objects.link(o_collision)
                            o_collision.parent = ig
                            o_collision.matrix_world = ig.matrix_world
                            o_collision.nwo.region_name = ig.nwo.region_name
                            o_collision.nwo.permutation_name = ig.nwo.permutation_name

                    if phys:
                        for s_ob in split_physics:
                            o_physics = s_ob.copy()
                            for collection in ig.users_collection: collection.objects.link(o_physics)
                            o_physics.parent = ig
                            o_physics.matrix_world = ig.matrix_world
                            o_physics.nwo.region_name = ig.nwo.region_name
                            o_physics.nwo.permutation_name = ig.nwo.permutation_name

                    if cookie:
                        o_cookie_cutter = proxy_cookie_cutter.copy()
                        for collection in ig.users_collection: collection.objects.link(o_cookie_cutter)
                        o_cookie_cutter.parent = ig
                        o_cookie_cutter.matrix_world = ig.matrix_world
                        o_cookie_cutter.nwo.region_name = ig.nwo.region_name
                        o_cookie_cutter.nwo.permutation_name = ig.nwo.permutation_name
                        
                        
                    # Correctly setup original coll type for poop if h4
                    if self.corinth:
                        if coll:
                            ig["bungie_mesh_poop_collision_type"] = '_connected_geometry_poop_collision_type_none'
                        elif phys:
                            ig["bungie_mesh_poop_collision_type"] = '_connected_geometry_poop_collision_type_bullet_collision'

    def _force_fcurves_to_start_at_zero(self):
        if self.export_settings.export_animations != "NONE" and bpy.data.actions:
            # Force the keyframes to start at frame 0
            for animation in bpy.data.actions:
                frames_from_zero = int(animation.frame_start)
                if frames_from_zero == 0: continue
                for fcurve in animation.fcurves:
                    for kfp in fcurve.keyframe_points:
                        kfp.co_ui[0] -= frames_from_zero
                    fcurve.keyframe_points.handles_recalc()
                    
                animation.frame_start = 0
                animation.frame_end -= frames_from_zero
                
    def _set_proxy_collision_props(self, ob):
        mesh = ob.data
        # Not supporting proxy face props currently, so just shove them into mesh props
        for prop in mesh.nwo.face_props:
            if prop.face_two_sided:
                mesh.nwo.face_two_sided = True
            if prop.sphere_collision_only:
                mesh.nwo.sphere_collision_only = True
            if prop.ladder:
                mesh.nwo.ladder = True
            if prop.slip_surface:
                mesh.nwo.slip_surface = True
                
        if mesh.nwo.face_two_sided:
            ob["bungie_face_sides"] = "_connected_geometry_face_sides_two_sided"
            
        if mesh.nwo.sphere_collision_only:
            ob["bungie_face_mode"] = "_connected_geometry_face_mode_sphere_collision_only"
            
        if mesh.nwo.ladder:
            ob["bungie_ladder"] = "1"
            
        if mesh.nwo.slip_surface:
            ob["bungie_slip_surface"] = "1"
            
    def _setup_poop_props(self, ob):
        nwo = ob.nwo
        nwo_data = ob.data.nwo
        ob["bungie_mesh_poop_lighting"] = nwo.poop_lighting
        ob["bungie_mesh_poop_pathfinding"] = nwo.poop_pathfinding
        ob["bungie_mesh_poop_imposter_policy"] = nwo.poop_imposter_policy
        if (
            nwo.poop_imposter_policy
            != "_connected_poop_instance_imposter_policy_never"
        ):
            if not nwo.poop_imposter_transition_distance_auto:
                ob["bungie_mesh_poop_imposter_transition_distance"] = utils.jstr(nwo.poop_imposter_transition_distance)
            if self.corinth:
                nwo["bungie_mesh_poop_imposter_brightness"] = utils.jstr(nwo.poop_imposter_brightness)
        if nwo_data.render_only:
            ob["bungie_face_mode"] = '_connected_geometry_face_mode_render_only'
            if self.corinth:
                ob["bungie_mesh_poop_collision_type"] = '_connected_geometry_poop_collision_type_none'
            else:
                ob["bungie_mesh_poop_is_render_only"] = "1"
        elif nwo.poop_render_only:
            if self.corinth:
                ob["bungie_mesh_poop_collision_type"] = '_connected_geometry_poop_collision_type_none'
            else:
                ob["bungie_mesh_poop_is_render_only"] = "1"
                
        elif not self.corinth and nwo_data.sphere_collision_only:
            ob["bungie_face_mode"] = '_connected_geometry_face_mode_sphere_collision_only'
        elif self.corinth:
            ob["bungie_mesh_poop_collision_type"] = nwo_data.poop_collision_type
        # if nwo.poop_chops_portals:
        #     ob["bungie_mesh_poop_chops_portals"] = "1"
        if nwo.poop_does_not_block_aoe:
            ob["bungie_mesh_poop_does_not_block_aoe"] = "1"
        if nwo.poop_excluded_from_lightprobe:
            ob["bungie_mesh_poop_excluded_from_lightprobe"] = "1"
            
        if nwo_data.decal_offset:
            ob["bungie_mesh_poop_decal_spacing"] = "1" 
        if nwo_data.precise_position:
            ob["bungie_mesh_poop_precise_geometry"] = "1"

        if self.corinth:
            ob["bungie_mesh_poop_lightmap_resolution_scale"] = str(nwo.poop_lightmap_resolution_scale)
            ob["bungie_mesh_poop_streamingpriority"] = nwo.poop_streaming_priority
            ob["bungie_mesh_poop_cinema_only"] = utils.bool_str(nwo.poop_cinematic_properties == '_connected_geometry_poop_cinema_only')
            ob["bungie_mesh_poop_exclude_from_cinema"] = utils.bool_str(nwo.poop_cinematic_properties == '_connected_geometry_poop_cinema_exclude')
            if nwo.poop_remove_from_shadow_geometry:
                ob["bungie_mesh_poop_remove_from_shadow_geometry"] = "1"
            if nwo.poop_disallow_lighting_samples:
                ob["bungie_mesh_poop_disallow_object_lighting_samples"] = "1"
                
        for child in ob.children:
            if child.type in VALID_MESHES and child.data.nwo.mesh_type == '_connected_geometry_mesh_type_collision':
                ob["bungie_face_mode"] = '_connected_geometry_face_mode_render_only'
                break
            
    def _setup_mesh_properties(self, ob: bpy.types.Object, is_map):
        nwo = ob.nwo
        mesh_type = str(ob.data.nwo.mesh_type)
        if is_map:
            # The ol switcheroo
            if mesh_type == '_connected_geometry_mesh_type_default':
                mesh_type = '_connected_geometry_mesh_type_poop'
            elif mesh_type == '_connected_geometry_mesh_type_structure':
                self.bsps_with_structure.add(nwo.region_name)
                mesh_type = '_connected_geometry_mesh_type_default'
                if not self.corinth:
                    if ob.data.nwo.render_only:
                        ob["bungie_face_mode"] = '_connected_geometry_face_mode_render_only'
                    elif ob.data.nwo.sphere_collision_only:
                        ob["bungie_face_mode"] = '_connected_geometry_face_mode_sphere_collision_only'
                    elif ob.data.nwo.collision_only:
                        ob["bungie_face_mode"] = '_connected_geometry_face_mode_collision_only'
            
        ob["bungie_mesh_type"] = mesh_type
        nwo_data = ob.data.nwo
        if mesh_type == "_connected_geometry_mesh_type_physics":
            prim_type = nwo.mesh_primitive_type
            ob["bungie_mesh_primitive_type"] = prim_type
            if prim_type != '_connected_geometry_primitive_type_none':
                self.physics_prims.add(ob)
            elif self.corinth and nwo.mopp_physics:
                ob["bungie_mesh_primitive_type"] = "_connected_geometry_primitive_type_mopp"
                ob["bungie_havok_isshape"] = "1"
                
        elif mesh_type == '_connected_geometry_mesh_type_object_instance':
            ob["bungie_marker_all_regions"] = utils.bool_str(not nwo.marker_uses_regions)
            if nwo.marker_uses_regions:
                ob["bungie_marker_region"] = ob.nwo.region_name
                nwo.region_name = utils.true_region(nwo)
                self.validated_regions.add(nwo.region_name)
                m_perms = nwo.marker_permutations
                if m_perms:
                    m_perm_set = set()
                    for perm in m_perms:
                        self.validated_permutations.add(perm.name)
                        m_perm_set.add(perm.name)
                    m_perm_json_value = f'''#({', '.join('"' + p + '"' for p in m_perm_set)})'''
                    if nwo.marker_permutation_type == "exclude":
                        ob["bungie_marker_exclude_from_permutations"] = m_perm_json_value
                    else:
                        ob["bungie_marker_include_in_permutations"] = m_perm_json_value
                    
                
        elif mesh_type == '_connected_geometry_mesh_type_poop':
            self._setup_poop_props(ob)
            
        elif mesh_type == '_connected_geometry_mesh_type_default' and self.corinth and self.asset_type == 'scenario':
            ob["bungie_face_type"] = '_connected_geometry_face_type_sky'
                    
        elif mesh_type == "_connected_geometry_mesh_type_seam":
            ob["bungie_mesh_seam_associated_bsp"] = (f"{self.asset_name}_{nwo.region_name}")
            self.seams.add(ob)
            
        elif mesh_type == "_connected_geometry_mesh_type_portal":
            ob["bungie_mesh_portal_type"] = nwo.portal_type
            if nwo.portal_ai_deafening:
                ob["bungie_mesh_portal_ai_deafening"] = "1"
            if nwo.portal_blocks_sounds:
                ob["bungie_mesh_portal_blocks_sound"] = "1"
            if nwo.portal_is_door:
                ob["bungie_mesh_portal_is_door"] = "1"
                
            
        elif mesh_type == "_connected_geometry_mesh_type_water_physics_volume":
            # ob["bungie_mesh_tessellation_density"] = nwo.mesh_tessellation_density
            ob["bungie_mesh_water_volume_depth"] = utils.jstr(nwo.water_volume_depth)
            ob["bungie_mesh_water_volume_flow_direction"] = utils.jstr(degrees(nwo.water_volume_flow_direction))
            ob["bungie_mesh_water_volume_flow_velocity"] = utils.jstr(nwo.water_volume_flow_velocity)
            ob["bungie_mesh_water_volume_fog_murkiness"] = utils.jstr(nwo.water_volume_fog_murkiness)
            if self.corinth:
                ob["bungie_mesh_water_volume_fog_color"] = utils.color_rgba_str(nwo.water_volume_fog_color)
            else:
                ob["bungie_mesh_water_volume_fog_color"] = utils.color_argb_str(nwo.water_volume_fog_color)
            
        elif mesh_type in ("_connected_geometry_mesh_type_poop_vertical_rain_sheet", "_connected_geometry_mesh_type_poop_rain_blocker"):
            ob["bungie_face_mode"] = '_connected_geometry_face_mode_render_only'
            
        elif mesh_type == "_connected_geometry_mesh_type_planar_fog_volume":
            ob["bungie_mesh_fog_appearance_tag"] = utils.relative_path(nwo.fog_appearance_tag)
            ob["bungie_mesh_fog_volume_depth"] = utils.jstr(nwo.fog_volume_depth)
            
        elif mesh_type == "_connected_geometry_mesh_type_soft_ceiling":
            ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_boundary_surface"
            ob["bungie_mesh_boundary_surface_type"] = '_connected_geometry_boundary_surface_type_soft_ceiling'
            ob["bungie_mesh_boundary_surface_name"] = utils.dot_partition(ob.name)
            
        elif mesh_type == "_connected_geometry_mesh_type_soft_kill":
            ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_boundary_surface"
            ob["bungie_mesh_boundary_surface_type"] = '_connected_geometry_boundary_surface_type_soft_kill'
            ob["bungie_mesh_boundary_surface_name"] = utils.dot_partition(ob.name)
            
        elif mesh_type == "_connected_geometry_mesh_type_slip_surface":
            ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_boundary_surface"
            ob["bungie_mesh_boundary_surface_type"] = '_connected_geometry_boundary_surface_type_slip_surface'
            ob["bungie_mesh_boundary_surface_name"] = utils.dot_partition(ob.name)
            
        elif mesh_type == "_connected_geometry_mesh_type_lightmap_only":
            nwo.lightmap_resolution_scale_active = False
            ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_poop"
            self._setup_poop_props(ob)
            if nwo_data.no_shadow:
                ob["bungie_face_mode"] = '_connected_geometry_face_mode_render_only'
            else:
                ob["bungie_face_mode"] = '_connected_geometry_face_mode_lightmap_only'
            ob["bungie_mesh_poop_lighting"] = "_connected_geometry_poop_lighting_single_probe"
            ob["bungie_mesh_poop_pathfinding"] = "_connected_poop_instance_pathfinding_policy_none"
            if ob.data.materials != [self.invisible_mat]:
                ob.data.materials.clear()
                ob.data.materials.append(self.invisible_mat)
                
        elif mesh_type == "_connected_geometry_mesh_type_lightmap_exclude":
            ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_obb_volume"
            ob["bungie_mesh_obb_type"] = "_connected_geometry_mesh_obb_volume_type_lightmapexclusionvolume"
            
        elif mesh_type == "_connected_geometry_mesh_type_streaming":
            ob["bungie_mesh_type"] = "_connected_geometry_mesh_type_obb_volume"
            ob["bungie_mesh_obb_type"] = "_connected_geometry_mesh_obb_volume_type_streamingvolume"
            
        elif mesh_type == '_connected_geometry_mesh_type_collision' and self.asset_type in ('scenario', 'prefab'):
            if self.corinth:
                ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_poop_collision'
                ob["bungie_mesh_poop_collision_type"] = nwo_data.poop_collision_type
            elif ob.parent and ob.parent.type in VALID_MESHES and ob.parent.data.nwo.mesh_type == '_connected_geometry_mesh_type_default':
                ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_poop_collision'
            else:
                ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_poop'
                ob["bungie_mesh_poop_lighting"] = "_connected_geometry_poop_lighting_single_probe"
                ob["bungie_mesh_poop_pathfinding"] = "_connected_poop_instance_pathfinding_policy_cutout"
                ob["bungie_mesh_poop_imposter_policy"] = "_connected_poop_instance_imposter_policy_never"
                nwo.reach_poop_collision = True
                if nwo_data.sphere_collision_only:
                    ob["bungie_face_mode"] = '_connected_geometry_face_mode_sphere_collision_only'
                else:
                    ob["bungie_face_mode"] = '_connected_geometry_face_mode_collision_only'
        
        elif self.asset_type == 'prefab':
            ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_poop'
            self._setup_poop_props(ob)
            
        elif self.asset_type == 'decorator_set':
            ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_decorator'
            ob["bungie_mesh_decorator_lod"] = str(self._decorator_int(ob))
        
        # MESH LEVEL PROPERTIES
        current_mesh_type = ob.get("bungie_mesh_type")
        if current_mesh_type in (
            "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_physics",
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_object_instance",
            "_connected_geometry_mesh_type_poop",
            "_connected_geometry_mesh_type_poop_collision",
            "_connected_geometry_mesh_type_water_surface",
        ):
            if self.asset_type in ("scenario", "prefab") or current_mesh_type in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
            ) and not (not self.corinth and current_mesh_type in "_connected_geometry_mesh_type_poop"):
                self._set_global_material_prop(ob)
                if current_mesh_type != "_connected_geometry_mesh_type_physics" and not self.corinth:
                    if nwo_data.ladder:
                        ob["bungie_ladder"] = "1"
                    if nwo_data.slip_surface:
                        ob['bungie_slip_surface'] = "1"
                        
            if self.asset_type in ("model", "sky") and current_mesh_type in render_mesh_types and nwo_data.face_draw_distance != '_connected_geometry_face_draw_distance_normal':
                ob["bungie_face_draw_distance"] = nwo_data.face_draw_distance
                        
            if current_mesh_type != "_connected_geometry_mesh_type_physics":
                # Handle face sides, game wants an enum but Foundry uses flags
                face_sides_value = "_connected_geometry_face_sides_"
                has_transparency = nwo_data.face_transparent and current_mesh_type in render_mesh_types
                if nwo_data.face_two_sided:
                    # Only h4+ support properties for the backside face
                    if not self.corinth or current_mesh_type not in render_mesh_types:
                        face_sides_value += "two_sided"
                    else:
                        face_sides_value += nwo_data.face_two_sided_type
                    # Add transparency if set
                    if has_transparency:
                        face_sides_value += "_transparent"
                    ob["bungie_face_sides"] = face_sides_value
                    
                elif has_transparency:
                    face_sides_value += "one_sided_transparent"
                    ob["bungie_face_sides"] = face_sides_value

            if current_mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop'):
                if nwo_data.precise_position and not (self.asset_type == 'scenario' and current_mesh_type == '_connected_geometry_mesh_type_default'):
                    ob["bungie_precise_position"] = "1"
                    #ob["bungie_mesh_additional_compression"] = "_connected_geometry_mesh_additional_compression_force_off"
                if nwo_data.decal_offset:
                    ob["bungie_decal_offset"] = "1"
                if nwo_data.mesh_tessellation_density != "_connected_geometry_mesh_tessellation_density_none":
                    ob["bungie_mesh_tessellation_density"] = nwo_data.mesh_tessellation_density
            if self.asset_type in ("scenario", "prefab"):   
                if nwo_data.no_shadow:
                    ob["bungie_no_shadow"] = "1"
                if self.corinth:
                    if nwo_data.no_lightmap:
                        ob["bungie_no_lightmap"] = "1"
                    if nwo_data.no_pvs:
                        ob["bungie_invisible_to_pvs"] = "1"
                if nwo_data.mesh_type != "_connected_geometry_mesh_type_lightmap_only":
                    if nwo_data.lightmap_additive_transparency_active:
                        ob["bungie_lightmap_transparency_override"] = "1"
                        ob["bungie_lightmap_additive_transparency"] = utils.color_4p_str(nwo_data.lightmap_additive_transparency)
                    if nwo_data.lightmap_resolution_scale_active:
                        ob["bungie_lightmap_resolution_scale"] = utils.jstr(nwo_data.lightmap_resolution_scale)
                    if nwo_data.lightmap_type_active:
                        ob["bungie_lightmap_type"] = nwo_data.lightmap_type
                    if nwo_data.lightmap_translucency_tint_color_active:
                        ob["bungie_lightmap_translucency_tint_color"] = utils.color_4p_str(nwo_data.lightmap_translucency_tint_color)
                    if nwo_data.lightmap_lighting_from_both_sides_active and nwo_data.lightmap_lighting_from_both_sides:
                        ob["bungie_lightmap_lighting_from_both_sides"] = "1"
                if nwo_data.emissive_active:
                    if self.corinth:
                        ob["bungie_lighting_emissive_power"] = utils.jstr(nwo_data.material_lighting_emissive_power / 30)
                    else:
                        ob["bungie_lighting_emissive_power"] = utils.jstr(nwo_data.material_lighting_emissive_power)
                        
                    if nwo_data.material_lighting_attenuation_falloff or nwo_data.material_lighting_attenuation_cutoff:
                        ob["bungie_lighting_attenuation_enabled"] = "1"
                        ob["bungie_lighting_attenuation_falloff"] = utils.jstr(nwo_data.material_lighting_attenuation_falloff * 100 * 0.03048 * self.emissive_factor)
                        ob["bungie_lighting_attenuation_cutoff"] = utils.jstr(nwo_data.material_lighting_attenuation_cutoff * 100 * 0.03048 * self.emissive_factor)
                    else:
                        ob["bungie_lighting_attenuation_enabled"] = "0"

                    ob["bungie_lighting_emissive_focus"] = utils.jstr(degrees(nwo_data.material_lighting_emissive_focus) / 180)
                    ob["bungie_lighting_emissive_color"] = utils.color_4p_str(nwo_data.material_lighting_emissive_color)
                    ob["bungie_lighting_emissive_per_unit"] =  utils.bool_str(nwo_data.material_lighting_emissive_per_unit)
                    ob["material_lighting_emissive_quality"] =  utils.jstr(nwo_data.material_lighting_emissive_quality)
                    ob["material_lighting_use_shader_gel"] =  utils.bool_str(nwo_data.material_lighting_use_shader_gel)
                    ob["bungie_lighting_bounce_ratio"] = utils.jstr(nwo_data.material_lighting_bounce_ratio)
                    
        return True

    
    def _setup_marker_properties(self, ob):
        nwo = ob.nwo
        marker_type = nwo.marker_type
        ob["bungie_marker_type"] = marker_type
        ob["bungie_marker_model_group"] = nwo.marker_model_group
        if self.asset_type in ('model', 'sky'):
            ob["bungie_marker_all_regions"] = utils.bool_str(not nwo.marker_uses_regions)
            if nwo.marker_uses_regions:
                self.validated_regions.add(ob.nwo.region_name)
                ob["bungie_marker_region"] = ob.nwo.region_name
                m_perms = nwo.marker_permutations
                if m_perms:
                    m_perm_set = set()
                    for perm in m_perms:
                        self.validated_permutations.add(perm.name)
                        m_perm_set.add(perm.name)
                    m_perm_json_value = f'''#({', '.join('"' + p + '"' for p in m_perm_set)})'''
                    if nwo.marker_permutation_type == "exclude":
                        ob["bungie_marker_exclude_from_permutations"] = m_perm_json_value
                    else:
                        ob["bungie_marker_include_in_permutations"] = m_perm_json_value
                        
            if marker_type == "_connected_geometry_marker_type_hint":
                if self.corinth:
                    scale = ob.matrix_world.to_scale()
                    max_abs_scale = max(abs(scale.x), abs(scale.y), abs(scale.z))
                    ob["bungie_marker_hint_length"] = utils.jstr(ob.empty_display_size * 2 * max_abs_scale)

                ob.name = "hint_"
                if nwo.marker_hint_type == "bunker":
                    ob.name += "bunker"
                elif nwo.marker_hint_type == "corner":
                    ob.name += "corner_"
                    if nwo.marker_hint_side == "right":
                        ob.name += "right"
                    else:
                        ob.name += "left"

                else:
                    if nwo.marker_hint_type == "vault":
                        ob.name += "vault_"
                    elif nwo.marker_hint_type == "mount":
                        ob.name += "mount_"
                    else:
                        ob.name += "hoist_"

                    if nwo.marker_hint_height == "step":
                        ob.name += "step"
                    elif nwo.marker_hint_height == "crouch":
                        ob.name += "crouch"
                    else:
                        ob.name += "stand"
                        
            elif marker_type == "_connected_geometry_marker_type_pathfinding_sphere":
                set_marker_sphere_size(ob, nwo)
                ob["bungie_marker_pathfinding_sphere_vehicle_only"] = utils.bool_str(nwo.marker_pathfinding_sphere_vehicle)
                ob["bungie_marker_pathfinding_sphere_remains_when_open"] = utils.bool_str(nwo.pathfinding_sphere_remains_when_open)
                ob["bungie_marker_pathfinding_sphere_with_sectors"] = utils.bool_str(nwo.pathfinding_sphere_with_sectors)
                
            elif marker_type == "_connected_geometry_marker_type_physics_constraint":
                ob["bungie_marker_type"] = nwo.physics_constraint_type
                parent = nwo.physics_constraint_parent
                if (
                    parent is not None
                    and parent.type == "ARMATURE"
                    and nwo.physics_constraint_parent_bone != ""
                ):
                    ob["bungie_physics_constraint_parent"] = (
                        nwo.physics_constraint_parent_bone
                    )

                elif parent is not None:
                    ob["bungie_physics_constraint_parent"] = str(
                        nwo.physics_constraint_parent.parent_bone
                    )
                child = nwo.physics_constraint_child
                if (
                    child is not None
                    and child.type == "ARMATURE"
                    and nwo.physics_constraint_child_bone != ""
                ):
                    ob["bungie_physics_constraint_child"] = (
                        nwo.physics_constraint_child_bone
                    )

                elif child is not None:
                    ob["bungie_physics_constraint_child"] = str(
                        nwo.physics_constraint_child.parent_bone
                    )
                ob["bungie_physics_constraint_use_limits"] = utils.bool_str(
                    nwo.physics_constraint_uses_limits
                )
                if nwo.physics_constraint_uses_limits:
                    if nwo.physics_constraint_type == "_connected_geometry_marker_type_physics_hinge_constraint":
                        ob["bungie_physics_constraint_hinge_min"] = utils.jstr(degrees(nwo.hinge_constraint_minimum))
                        ob["bungie_physics_constraint_hinge_max"] = utils.jstr(degrees(nwo.hinge_constraint_maximum))
                    else:
                        ob["bungie_physics_constraint_cone_angle"] = utils.jstr(degrees(nwo.cone_angle))
                        ob["bungie_physics_constraint_plane_min"] = utils.jstr(degrees(nwo.plane_constraint_minimum))
                        ob["bungie_physics_constraint_plane_max"] = utils.jstr(degrees(nwo.plane_constraint_maximum))
                        ob["bungie_physics_constraint_twist_start"] = utils.jstr(degrees(nwo.twist_constraint_start))
                        ob["bungie_physics_constraint_twist_end"] = utils.jstr(degrees(nwo.twist_constraint_end))
                
            elif marker_type == "_connected_geometry_marker_type_target":
                set_marker_sphere_size(ob, nwo)
                
            elif marker_type == "_connected_geometry_marker_type_effects":
                ob["bungie_marker_type"] = "_connected_geometry_marker_type_model"
                if not ob.name.startswith("fx_"):
                    ob.name = "fx_" + ob.name
                    
            elif marker_type == "_connected_geometry_marker_type_garbage":
                if not self.corinth:
                    ob["bungie_marker_type"] = "_connected_geometry_marker_type_model"
                ob["bungie_marker_velocity"] = utils.vector_str(nwo.marker_velocity)
        
        elif self.asset_type in ("scenario", "prefab"):
            if marker_type == "_connected_geometry_marker_type_game_instance":
                tag_name = nwo.marker_game_instance_tag_name.lower()
                ob["bungie_marker_game_instance_tag_name"] = tag_name
                if self.corinth and tag_name.endswith(
                    ".prefab"
                ):
                    ob["bungie_marker_type"] = "_connected_geometry_marker_type_prefab"
                    if nwo.prefab_pathfinding != "no_override":
                        ob["bungie_mesh_poop_pathfinding"] = nwo.prefab_pathfinding
                    if nwo.prefab_lightmap_res > 0:
                        ob["bungie_mesh_poop_lightmap_resolution_scale"] = str(nwo.prefab_lightmap_res)
                    if nwo.prefab_lighting != "no_override":
                        ob["bungie_mesh_poop_lighting"] = nwo.prefab_lighting
                    if nwo.prefab_imposter_policy != "no_override":
                        ob["bungie_mesh_poop_imposter_policy"] = nwo.prefab_imposter_policy
                        if nwo.prefab_imposter_policy != "_connected_poop_instance_imposter_policy_never":
                            if nwo.prefab_imposter_brightness > 0:
                                ob["bungie_mesh_poop_imposter_brightness"] = utils.jstr(nwo.prefab_imposter_brightness)
                            if not nwo.prefab_imposter_transition_distance_auto:
                                ob["bungie_mesh_poop_imposter_transition_distance"] = utils.jstr(nwo.prefab_imposter_transition_distance_auto)
                                
                    if nwo.prefab_streaming_priority != "no_override":
                        ob["bungie_mesh_poop_streamingpriority"] = nwo.prefab_streaming_priority
                    
                    if nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_only':
                        ob["bungie_mesh_poop_cinema_only"] = "1"
                    elif nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_exclude':
                        ob["bungie_mesh_poop_exclude_from_cinema"] = "1"
                        
                    if nwo.prefab_render_only:
                        ob["bungie_mesh_poop_is_render_only"] = "1"
                    if nwo.prefab_does_not_block_aoe:
                        ob["bungie_mesh_poop_does_not_block_aoe"] = "1"
                    if nwo.prefab_excluded_from_lightprobe:
                        ob["bungie_mesh_poop_excluded_from_lightprobe"] = "1"
                    if nwo.prefab_decal_spacing:
                        ob["bungie_mesh_poop_decal_spacing"] = "1"
                    if nwo.prefab_remove_from_shadow_geometry:
                        ob["bungie_mesh_poop_remove_from_shadow_geometry"] = "1"
                    if nwo.prefab_disallow_lighting_samples:
                        ob["bungie_mesh_poop_disallow_object_lighting_samples"] = "1"       
                        
                elif (
                    self.corinth
                    and tag_name.endswith(
                        ".cheap_light"
                    )
                ):
                    ob["bungie_marker_type"] = "_connected_geometry_marker_type_cheap_light"
                elif (
                    self.corinth
                    and tag_name.endswith(".light")
                ):
                    ob["bungie_marker_type"] = "_connected_geometry_marker_type_light"
                elif (
                    self.corinth
                    and tag_name.endswith(".leaf")
                ):
                    ob["bungie_marker_type"] = "_connected_geometry_marker_type_falling_leaf"
                else:
                    ob["bungie_marker_game_instance_variant_name"] = nwo.marker_game_instance_tag_variant_name
                    if self.corinth:
                        ob["bungie_marker_always_run_scripts"] = utils.bool_str(nwo.marker_always_run_scripts)
            
            elif marker_type == "_connected_geometry_marker_type_envfx":
                ob["bungie_marker_looping_effect"] = nwo.marker_looping_effect
                
            elif marker_type == "_connected_geometry_marker_type_lightCone":
                ob["bungie_marker_light_tag"] = nwo.marker_light_cone_tag
                ob["bungie_marker_light_color"] = utils.color_3p_str(nwo.marker_light_cone_color)
                ob["bungie_marker_light_cone_width"] = utils.jstr(nwo.marker_light_cone_alpha)
                ob["bungie_marker_light_cone_length"] = utils.jstr(nwo.marker_light_cone_width)
                ob["bungie_marker_light_color_alpha"] = utils.jstr(nwo.marker_light_cone_length)
                ob["bungie_marker_light_cone_intensity"] = utils.jstr(nwo.marker_light_cone_intensity)
                ob["bungie_marker_light_cone_curve"] = nwo.marker_light_cone_curve

    def _strip_prefix(self, ob):
        name = ob.name.lower()
        keep_stripping = True
        while keep_stripping:
            if name.startswith(("frame ", "frame_")):
                name = name[6:]
            elif name.startswith(("bone ", "bone_")):
                name = name[5:]
            elif name.startswith(("bip ", "bip_")):
                name = name[4:]
            elif name.startswith(("b ", "b_")):
                name = name[2:]
            elif name.startswith(("#", "?", "@", "$", "'")):
                name = name[1:]
            elif name.startswith(("%")):
                name = name[1:]
                if name.startswith(("?", "!", "+", "-", ">", "*")):
                    name = name[1:]
                    if name.startswith(("?", "!", "+", "-", ">", "*")):
                        name = name[1:]
                        if name.startswith(("?", "!", "+", "-", ">", "*")):
                            name = name[1:]

            else:
                keep_stripping = False

        ob.name = name.strip(" _")
        while ob.name in self.protected_names:
            if not ob.name.rpartition(".")[0]:
                ob.name += "."
            ob.name += "padding"

    def _set_animation_overrides(self):
        for action in bpy.data.actions:
            action.name = utils.dot_partition(action.name).lower().strip(" :_,-")
            nwo = action.nwo
            if not nwo.name_override: nwo.name_override = action.name
            if self.scene_settings.default_animation_compression != "Automatic" and nwo.compression == "Default":
                nwo.compression = self.scene_settings.default_animation_compression

    def _set_timeline_range(self, context):
        scene = context.scene
        timeline_start = scene.frame_start
        timeline_end = scene.frame_end

        scene.frame_current = 0
        scene.frame_start = 0
        scene.frame_end = 0

        return timeline_start, timeline_end
    
    def _decorator_int(self, ob):
        match ob.nwo.decorator_lod:
            case "high":
                return 1
            case "medium":
                return 2
            case "low":
                return 3
            case _:
                return 4

    #####################################################################################
    #####################################################################################
    # ARMATURE FUNCTIONS

    def _fix_parenting(self):
        bones = self.model_armature.data.bones
        valid_bone_names = {b.name for b in bones if b.use_deform}
        objects_in_scope = [ob for ob in self.context.view_layer.objects if ob.parent == self.model_armature]
        for ob in objects_in_scope:
            marker = utils.is_marker(ob)
            physics = utils.is_mesh(ob) and ob.data.nwo.mesh_type == "_connected_geometry_mesh_type_physics"
            io = utils.is_mesh(ob) and ob.data.nwo.mesh_type == "_connected_geometry_mesh_type_object_instance"
            if ob.parent_type != "BONE":
                if marker or physics or io:
                    world = ob.matrix_world.copy()
                    ob.parent_type = "BONE"
                    if ob.type == 'MESH':
                        major_vertex_group = utils.get_major_vertex_group(ob)
                        if major_vertex_group in valid_bone_names:
                            ob.parent_bone = major_vertex_group
                        else:
                            ob.parent_bone = self.root_bone_name
                    else:
                        ob.parent_bone = self.root_bone_name
                    if not ob.parent_bone in valid_bone_names:
                        self.warning_hit = True
                        utils.print_warning(f'{ob.name} is parented to bone {ob.parent_bone} but this bone is either non-deform or does not exist. Parenting object to {self.root_bone_name}')
                        ob.parent_bone = self.root_bone_name
                    
                    ob.matrix_world = world
                    
                elif ob.type == "MESH":
                    # check if has armature mod
                    modifiers = ob.modifiers
                    for mod in modifiers:
                        if mod.type == "ARMATURE":
                            if mod.object != self.model_armature:
                                mod.object = self.model_armature
                            break
                    else:
                        arm_mod = ob.modifiers.new("Armature", "ARMATURE")
                        arm_mod.object = self.model_armature

            else:
                # Ensure parent inverse matrix set
                # If we don't do this, object can be offset in game
                if not ob.parent_bone in valid_bone_names:
                    world = ob.matrix_world.copy()
                    self.warning_hit = True
                    utils.print_warning(f'{ob.name} is parented to bone {ob.parent_bone} but this bone is either non-deform or does not exist. Parenting object to {self.root_bone_name}')
                    ob.parent_bone = self.root_bone_name
                    ob.matrix_world = world

            if ob.parent_type == "BONE":
                if ob.modifiers:
                    for mod in ob.modifiers:
                        if mod.type == "ARMATURE":
                            ob.modifiers.remove(mod)

    #####################################################################################
    #####################################################################################
    # BONE FUNCTIONS

    def _get_bone_list(self):
        boneslist = {}
        nodes_order = {}
        nodes_order_gun = {}
        nodes_order_fp = {}
        nodes = None
        bone_list = [bone for bone in self.model_armature.data.bones if bone.use_deform]
        if len(bone_list) > 256:
            raise RuntimeError(f"Armature [{self.model_armature.name}] exceeds maximum deform bone count for exporting. {len(bone_list)} > 256")
        
        root_bone = utils.rig_root_deform_bone(self.model_armature)
        
        if not root_bone:
            raise RuntimeError(f"Armature [{self.model_armature.name}] does not have a root deform bone")
        elif type(root_bone) == list:
            raise RuntimeError(f"Armature [{self.model_armature.name}] has multiple root deform bones")
        
        self.root_bone_name = root_bone.name
        
        # sort list
        def sorting_key(value):
            return nodes_order.get(value.name, len(nodes))
        
        if self.scene_settings.template_render_model:
            node_order_source = self.scene_settings.template_render_model
            node_order_source_is_model = True
        else:
            node_order_source = self.scene_settings.template_model_animation_graph
            node_order_source_is_model = False
            
        fp_model = self.scene_settings.fp_model_path
        gun_model = self.scene_settings.gun_model_path
        render_model_path = self.scene_settings.render_model_path
        if self.asset_type == 'model' and node_order_source:
            if Path(self.tags_dir, node_order_source).exists():
                if node_order_source_is_model:
                    with RenderModelTag(path=node_order_source, hide_prints=True) as render_model:
                        nodes = render_model.get_nodes()
                else:
                    with AnimationTag(path=node_order_source, hide_prints=True) as animation:
                        nodes = animation.get_nodes()
                
                if nodes is not None:
                    nodes_order = {v: i for i, v in enumerate(nodes)}
                    bone_list = sorted(bone_list, key=sorting_key)
            else:
                if node_order_source_is_model:
                    utils.print_warning("Render Model path supplied but file does not exist")
                else:
                    utils.print_warning("Model Animation Graph path supplied but file does not exist")  
                    
                self.warning_hit = True
        
        elif self.asset_type == 'animation':
            if self.scene_settings.asset_animation_type == 'first_person':
                if gun_model:
                    if Path(self.tags_dir, gun_model).exists():
                        with RenderModelTag(path=gun_model, hide_prints=True) as render_model:
                            nodes = render_model.get_nodes()
                        # add a 1000 to each index to ensure gun bones sorted last
                        nodes_order_gun = {v: i + 1000 for i, v in enumerate(nodes)}
                    else:
                        utils.print_warning("Gun Render Model supplied but tag path does not exist")
                        self.warning_hit = True
                if fp_model:
                    if Path(self.tags_dir, fp_model).exists():
                        with RenderModelTag(path=fp_model, hide_prints=True) as render_model:
                            nodes = render_model.get_nodes()
                        nodes_order_fp = {v: i for i, v in enumerate(nodes)}
                    else:
                        utils.print_warning("FP Render Model supplied but tag path does not exist")
                        self.warning_hit = True
                        
                if nodes is not None:
                    nodes_order.update(nodes_order_fp)
                    nodes_order.update(nodes_order_gun)
                    bone_list = sorted(bone_list, key=sorting_key)
                    
            else:
                if render_model_path:
                    with RenderModelTag(path=render_model_path, hide_prints=False) as render_model:
                        nodes = render_model.get_nodes()
                        
                if nodes is not None:
                    nodes_order = {v: i for i, v in enumerate(nodes)}
                    bone_list = sorted(bone_list, key=sorting_key)
            
        if nodes is None:
            # Fine, I'll order it myself
            bones_ordered = []
            bones_ordered.append(root_bone)
            idx = 0
            while idx < len(bone_list):
                for b in bone_list:
                    if idx < len(bones_ordered) and b.parent and b.parent == bones_ordered[idx]:
                        bones_ordered.append(b)
                idx += 1
                
            bone_list = bones_ordered
            
        frameIDs = self._read_frame_id_list()
        for idx, b in enumerate(bone_list):
            name = b.name
            self.protected_names.add(name)
            FrameID1, FrameID2 = frameIDs[idx]
            boneslist.update(
                {
                    name: self._get_bone_properties(
                        FrameID1,
                        FrameID2,
                        b.nwo.object_space_node,
                        b.nwo.replacement_correction_node,
                        b.nwo.fik_anchor_node,
                        b,
                    )
                }
            )

        return boneslist

    def _get_armature_props(self):
        node_props = {}

        node_props.update(
            {"bungie_object_type": "_connected_geometry_object_type_frame"}
        ),
        node_props.update({"bungie_frame_ID1": "8078"}),
        node_props.update({"bungie_frame_ID2": "378163771"}),
        if self.corinth:
            node_props.update({"bungie_frame_world": "1"}),

        return node_props

    def _get_bone_properties(
        self,
        FrameID1,
        FrameID2,
        object_space_node,
        replacement_correction_node,
        fik_anchor_node,
        bone,
    ):
        node_props = {}
        bone["bungie_object_type"] = '_connected_geometry_object_type_frame'
        bone["bungie_frame_ID1"] = FrameID1
        bone["bungie_frame_ID2"] = FrameID2
        node_props["bungie_object_type"] = '_connected_geometry_object_type_frame'
        node_props["bungie_frame_ID1"] = FrameID1
        node_props["bungie_frame_ID2"] = FrameID2

        if object_space_node:
            node_props["bungie_is_object_space_offset_node"] = "1"
            bone["bungie_is_object_space_offset_node"] = "1"
        if replacement_correction_node:
            node_props["bungie_is_replacement_correction_node"] = "1"
            bone["bungie_is_replacement_correction_node"] = "1"
        if fik_anchor_node:
            node_props["bungie_is_fik_anchor_node"] = "1"
            bone["bungie_is_fik_anchor_node"] = "1"

        node_props["bungie_object_animates"] = '1'
        bone["bungie_object_animates"] = "1"

        return node_props

    def _read_frame_id_list(self):
        filepath = Path(utils.addon_root(), "export", "frameidlist.csv")
        frameIDList = []
        with filepath.open(mode="r") as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=",")
            for row in csv_reader:
                frameIDList.append(row)

        return frameIDList

    def _fix_materials(self, ob, is_halo_render, does_not_support_sky):
        # fix multi user materials
        nwo = ob.nwo
        data = ob.data
        data_nwo = data.nwo
        # if data_nwo.face_global_material and nwo.reach_poop_collision:
        #     self._set_reach_coll_materials(data, True)
        # else:
        self._loop_and_fix_slots(ob, data, nwo, does_not_support_sky, is_halo_render)

    def _set_reach_coll_materials(self, data, mesh_level=False):
        # UNUSED
        # handle reach poop collision material assignment
        data_nwo = data.nwo
        mesh_global_mat = data_nwo.face_global_material.strip()
        if mesh_global_mat:
            data.materials.clear()
            new_mat_name = f"global_material_{mesh_global_mat}"
            if new_mat_name not in bpy.data.materials:
                coll_mat = bpy.data.materials.new(new_mat_name)
            else:
                coll_mat = bpy.data.materials.get(new_mat_name)
            
            tag_path = f"levels\\reference\\sound\\shaders\\bsp_{mesh_global_mat}.shader"
            full_tag_path = Path(self.tags_dir, tag_path)
            if full_tag_path.exists():
                coll_mat.nwo.shader_path = tag_path
            else:
                self.warning_hit = True
                utils.print_warning(f"Couldn't find collision material shader in 'tags\\levels\\reference\\sound\\shaders'. Please ensure a shader tag exists for {mesh_global_mat} prefixed with 'bsp_'")

            data.materials.append(coll_mat)
            
        if mesh_level or not data.nwo.face_props: return
        # set up the materials by face props
        bm = bmesh.new()
        bm.from_mesh(data)
        layers = data_nwo.face_props
        for l in layers:
            if not l.face_global_material or l.face_global_material == data_nwo.face_global_material:
                continue
            faces = utils.layer_faces(bm, bm.faces.layers.int.get(l.layer_name))
            if not faces:
                continue
            new_mat_face_name = f"global_material_{l.face_global_material}"
            if new_mat_face_name not in bpy.data.materials:
                coll_face_mat = bpy.data.materials.new(new_mat_face_name)
            else:
                coll_face_mat = bpy.data.materials.get(new_mat_face_name)

            tag_path = f"levels\\reference\\sound\\shaders\\bsp_{l.face_global_material}.shader"
            full_tag_path = Path(self.tags_dir, tag_path)
            if full_tag_path.exists():
                coll_face_mat.nwo.shader_path = tag_path
                data.materials.append(coll_face_mat)
                mat_dict = {mat: i for i, mat in enumerate(data.materials)}
                for f in faces: f.material_index = mat_dict[coll_face_mat]

            else:
                self.warning_hit = True
                utils.print_warning(f"Couldn't find collision material shader in 'tags\\levels\\reference\\sound\\shaders'. Please ensure a shader tag exists for {l.face_global_material} prefixed with 'bsp_'")

        bm.to_mesh(data)
        bm.free()

    def _loop_and_fix_slots(self, ob, data, nwo, does_not_support_sky, is_halo_render):
        is_true_mesh = ob.type == 'MESH'
        slots = utils.clean_materials(ob)
        for slot in slots:
            if slot.material.name in utils.special_material_names:
                if self.corinth and slot.material.name not in (self.invisible_mat.name, self.invalid_mat.name):
                    if not slot.material.name.lower().startswith(self.sky_mat.name):
                        slot.material = self.invisible_mat
                elif not self.corinth and slot.material.name.startswith(self.sky_mat.name) and does_not_support_sky:
                    slot.material = self.seamsealer_mat
            elif slot.material.name in utils.convention_material_names:
                slot.material = self.invisible_mat
            elif is_halo_render and not slot.material.get("bungie_shader_path"):
                self.used_materials.add(slot.material)

        if not slots:
            # append the new material to the object
            if ob.get("bungie_mesh_type") == "_connected_geometry_mesh_type_water_surface":
                data.materials.append(self.water_surface_mat)
            elif ob.get("bungie_mesh_type") in render_mesh_types:
                data.materials.append(self.default_mat)
            else:
                data.materials.append(self.invalid_mat)
        elif not self.corinth:
            sky_slots = [s for s in ob.material_slots if s.material.name.startswith('+sky')]
            # Loop through slots with sky material, if a permutation is given we need to make a new mesh
            if not sky_slots: return
            # If there's only one sky material can skip face split code below
            if len(sky_slots) == 1 or not is_true_mesh:
                sky_index = utils.get_sky_perm(sky_slots[0].material)
                if sky_index > -1 and sky_index < 32:
                    nwo.sky_permutation_index = str(sky_index)
                sky_slots[0].material = self.sky_mat
                return
            
            collections = ob.users_collections
            original_bm = bmesh.new()
            original_bm.from_mesh(data)
            for s in sky_slots:
                sky_index = utils.get_sky_perm(s.material)
                if sky_index > -1 and sky_index < 32:
                    original_bm.faces.ensure_lookup_table()
                    mat_faces = [f for f in original_bm.faces if f.material_index == s.slot_index]
                    # Exit early here if all faces are assigned to one sky perm
                    if len(mat_faces) == len(original_bm.faces):
                        nwo.sky_permutation_index = str(sky_index)
                        break
                    
                    face_indexes = [f.index for f in original_bm.faces if f in mat_faces]
                    new_bm = original_bm.copy()
                    bmesh.ops.delete(original_bm, geom=[f for f in original_bm.faces if f.index in face_indexes], context="FACES")
                    bmesh.ops.delete(new_bm, geom=[f for f in new_bm.faces if not f.index in face_indexes], context="FACES")
                    new_sky_data = data.copy()
                    new_bm.to_mesh(new_sky_data)
                    new_bm.free()
                    original_bm.to_mesh(data)
                    original_bm.free()
                    new_sky_ob = ob.copy()
                    new_sky_ob.name = ob.name + f'(sky_perm_{str(sky_index)})'
                    new_sky_ob.data = new_sky_data
                    for collection in collections: collection.objects.link(new_sky_ob)
                    new_sky_ob.nwo.sky_permutation_index = str(sky_index)
                    utils.clean_materials(ob)
                    utils.clean_materials(new_sky_ob)
                
                s.material = self.sky_mat

    def _wrap_bounding_box(self, objects, padding):
        min_x, min_y, min_z, max_x, max_y, max_z = -5, -5, 0, 5, 5, 300
        for ob in objects:
            if ob.type == 'MESH':
                bbox = ob.bound_box
                for co in bbox:
                    bounds = ob.matrix_world @ Vector((co[0], co[1], co[2]))
                    min_x = min(min_x, bounds.x - padding)
                    min_y = min(min_y, bounds.y - padding)
                    min_z = min(min_z, bounds.z - padding)
                    max_x = max(max_x, bounds.x + padding)
                    max_y = max(max_y, bounds.y + padding)
                    max_z = max(max_z, bounds.z + padding)
            else:
                bounds = ob.location
                min_x = min(min_x, bounds.x - padding)
                min_y = min(min_y, bounds.y - padding)
                min_z = min(min_z, bounds.z - padding)
                max_x = max(max_x, bounds.x + padding)
                max_y = max(max_y, bounds.y + padding)
                max_z = max(max_z, bounds.z + padding)
    
        # Create the box with bmesh
        bm = bmesh.new()
        xyz = bm.verts.new(Vector((min_x, min_y, min_z)))
        xyz = bm.verts.new(Vector((min_x, min_y, min_z)))
        xYz = bm.verts.new(Vector((min_x, max_y, min_z)))
        xYZ = bm.verts.new(Vector((min_x, max_y, max_z)))
        xyZ = bm.verts.new(Vector((min_x, min_y, max_z)))
        
        Xyz = bm.verts.new(Vector((max_x, min_y, min_z)))
        XYz = bm.verts.new(Vector((max_x, max_y, min_z)))
        XYZ = bm.verts.new(Vector((max_x, max_y, max_z)))
        XyZ = bm.verts.new(Vector((max_x, min_y, max_z)))
        
        bm.faces.new([xyz, xYz, xYZ, xyZ]) # Create the minimum x face
        bm.faces.new([Xyz, XYz, XYZ, XyZ]) # Create the maximum x face
        
        bm.faces.new([xyz, Xyz, XyZ, xyZ]) # Create the minimum y face
        bm.faces.new([xYz, xYZ, XYZ, XYz]) # Create the maximum y face
        
        bm.faces.new([xyz, xYz, XYz, Xyz]) # Create the minimum z face
        bm.faces.new([xyZ, xYZ, XYZ, XyZ]) # Create the maximum z face
        
        # Calculate consistent faces
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        # Flip em since bmesh by default calculates outside normals
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        
        # Create the mesh and object
        structure_mesh = bpy.data.meshes.new('autogenerated_structure')
        bm.to_mesh(structure_mesh)
        structure = bpy.data.objects.new('autogenerated_structure', structure_mesh)
        self.scene_collection.link(structure)
        structure["bungie_object_type"] = '_connected_geometry_object_type_mesh'
        structure["bungie_mesh_type"] = '_connected_geometry_mesh_type_default'
        
        return structure

    #####################################################################################
    #####################################################################################
    # HALO CLASS

    def _halo_objects_init(self):
        self.frames = set()
        self.markers = set()

        self.render = set()
        self.render_perms = set()

        self.collision = set()
        self.collision_perms = set()

        self.physics = set()
        self.physics_perms = set()

        self.design = set()
        self.design_bsps = set()
        self.design_perms = set()

        self.structure = set()
        self.structure_bsps = set()
        self.structure_perms = set()

    def _halo_objects(self):
        render_asset = self.asset_type in ("model", "sky", "decorator_set", "particle_model")
        for ob in self.context.view_layer.objects:
            nwo = ob.nwo
            object_type = ob.get("bungie_object_type")
            mesh_type = ob.get("bungie_mesh_type")
            permutation = nwo.permutation_name
            region = nwo.region_name

            if render_asset:
                default = mesh_type in (
                    "_connected_geometry_mesh_type_default",
                    "_connected_geometry_mesh_type_decorator",
                )
            else:
                design = mesh_type in (
                    "_connected_geometry_mesh_type_planar_fog_volume",
                    "_connected_geometry_mesh_type_boundary_surface",
                    "_connected_geometry_mesh_type_water_physics_volume",
                    "_connected_geometry_mesh_type_poop_rain_blocker",
                    "_connected_geometry_mesh_type_poop_vertical_rain_sheet",
                )

            if (
                object_type == "_connected_geometry_object_type_frame"
                and ob.type != "LIGHT"
            ):
                self.frames.add(ob)

            elif render_asset:
                io_with_single_perm = mesh_type == "_connected_geometry_mesh_type_object_instance" and nwo.marker_uses_regions and nwo.marker_permutation_type == "include" and len(nwo.marker_permutations) == 1
                if default or io_with_single_perm:
                    if io_with_single_perm:
                        permutation = nwo.marker_permutations[0].name
                        nwo.permutation_name = permutation
                    self.render.add(ob)
                    self.render_perms.add(permutation)
                elif mesh_type == "_connected_geometry_mesh_type_collision":
                    self.collision.add(ob)
                    self.collision_perms.add(permutation)
                elif mesh_type == "_connected_geometry_mesh_type_physics":
                    self.physics.add(ob)
                    self.physics_perms.add(permutation)
                elif object_type == "_connected_geometry_object_type_marker" or (object_type == '_connected_geometry_object_type_mesh' and mesh_type == "_connected_geometry_mesh_type_object_instance"):
                    self.markers.add(ob)
                else:
                    utils.unlink(ob)

            else:
                if design:
                    self.design.add(ob)
                    self.design_bsps.add(region)
                    self.design_perms.add(permutation)
                else:
                    self.structure.add(ob)
                    self.structure_bsps.add(region)
                    self.structure_perms.add(permutation)
    
    def _consolidate_rig(self):
        context = self.context
        scene_nwo = context.scene.nwo
        if scene_nwo.support_armature_a and context.scene.objects.get(scene_nwo.support_armature_a.name):
            child_bone = utils.rig_root_deform_bone(scene_nwo.support_armature_a, True)
            if child_bone and scene_nwo.support_armature_a_parent_bone:
                self._join_armatures(context, scene_nwo.main_armature, scene_nwo.support_armature_a, scene_nwo.support_armature_a_parent_bone, child_bone)
            else:
                utils.unlink(scene_nwo.support_armature_a)
                if not scene_nwo.support_armature_a_parent_bone:
                    self.warning_hit = True
                    utils.print_warning(f"No parent bone specified in Asset Editor panel for {scene_nwo.support_armature_a_parent_bone}. Ignoring support armature")
                    
                if not child_bone:
                    self.warning_hit = True
                    utils.print_warning(f"{scene_nwo.support_armature_a.name} has multiple root bones, could not join to {scene_nwo.main_armature.name}. Ignoring support armature")
                    
        if scene_nwo.support_armature_b and context.scene.objects.get(scene_nwo.support_armature_b.name):
            child_bone = utils.rig_root_deform_bone(scene_nwo.support_armature_b, True)
            if child_bone and scene_nwo.support_armature_b_parent_bone:
                self._join_armatures(context, scene_nwo.main_armature, scene_nwo.support_armature_b, scene_nwo.support_armature_b_parent_bone, child_bone)
            else:
                utils.unlink(scene_nwo.support_armature_b)
                if not scene_nwo.support_armature_b_parent_bone:
                    self.warning_hit = True
                    utils.print_warning(f"No parent bone specified in Asset Editor panel for {scene_nwo.support_armature_b_parent_bone}. Ignoring support armature")
                    
                if not child_bone:
                    self.warning_hit = True
                    utils.print_warning(f"{scene_nwo.support_armature_b.name} has multiple root bones, could not join to {scene_nwo.main_armature.name}. Ignoring support armature")
                    
        if scene_nwo.support_armature_c and context.scene.objects.get(scene_nwo.support_armature_c.name):
            child_bone = utils.rig_root_deform_bone(scene_nwo.support_armature_c, True)
            if child_bone and scene_nwo.support_armature_c_parent_bone:
                self._join_armatures(context, scene_nwo.main_armature, scene_nwo.support_armature_c, scene_nwo.support_armature_c_parent_bone, child_bone)
            else:
                utils.unlink(scene_nwo.support_armature_c)
                if not scene_nwo.support_armature_c_parent_bone:
                    self.warning_hit = True
                    utils.print_warning(f"No parent bone specified in Asset Editor panel for {scene_nwo.support_armature_c_parent_bone}. Ignoring support armature")
                    
                if not child_bone:
                    self.warning_hit = True
                    utils.print_warning(f"{scene_nwo.support_armature_c.name} has multiple root bones, could not join to {scene_nwo.main_armature.name}. Ignoring support armature")
                    
    def _join_armatures(self, context: bpy.types.Context, parent, child, parent_bone, child_bone):
        with context.temp_override(selected_editable_objects=[parent, child], active_object=parent):
            bpy.ops.object.join()
        # Couldn't get context override working for accessing edit_bones
        context.view_layer.objects.active = parent
        bpy.ops.object.editmode_toggle()
        edit_child = parent.data.edit_bones.get(child_bone, 0)
        edit_parent = parent.data.edit_bones.get(parent_bone, 0)
        if edit_child and edit_parent:
            edit_child.parent = edit_parent
        else:
            self.warning_hit = True
            utils.print_warning(f"Failed to join bones {parent_bone} and {child_bone} for {parent.name}")
            
        bpy.ops.object.editmode_toggle()
        
        context.view_layer.objects.active = None
    
    def _add_null_render(self):
        verts = [Vector((-32, -32, 0.0)), Vector((32, -32, 0.0)), Vector((-32, 32, 0.0))]
        faces = [[0, 1, 2]]
        me = bpy.data.meshes.new('null')
        me.from_pydata(verts, [], faces)
        me.materials.append(self.invisible_mat)
        ob = bpy.data.objects.new('null', me)
        self.scene_collection.link(ob)
        if self.model_armature:
            ob.parent = self.model_armature
            ob.parent_type = 'BONE'
            ob.parent_bone = [b.name for b in self.model_armature.data.bones if b.use_deform][0]
        ob["bungie_object_type"] = '_connected_geometry_object_type_mesh'
        ob["bungie_mesh_type"] = '_connected_geometry_mesh_type_default'
        ob.nwo.region_name  = self.default_region
        ob.nwo.permutation_name  = self.default_permutation
        return ob
    
    def _set_global_material_prop(self, ob, mesh_type="", global_material=""):
        if not mesh_type:
            if ob.get("bungie_mesh_type"):
                mesh_type = ob["bungie_mesh_type"]
            else:
                raise ValueError(f"No mesh type for setting global material on {ob.name}")
        
        if not global_material:
            global_material = ob.data.nwo.face_global_material.strip().replace(' ', "_")
        if global_material:
            if self.corinth and mesh_type in ('_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_poop_collision'):
                ob["bungie_mesh_global_material"] = global_material
                ob["bungie_mesh_poop_collision_override_global_material"] = "1"
            else:
                ob["bungie_face_global_material"] = global_material     

#####################################################################################
#####################################################################################
# VARIOUS FUNCTIONS

def set_marker_sphere_size(ob, nwo):
    scale = ob.matrix_world.to_scale()
    max_abs_scale = max(abs(scale.x), abs(scale.y), abs(scale.z))
    ob["bungie_mesh_primitive_sphere_radius"] = utils.jstr(ob.empty_display_size * max_abs_scale)

def add_triangle_mod(ob: bpy.types.Object):
    mods = ob.modifiers
    for m in mods:
        if m.type == 'TRIANGULATE': return
        
    tri_mod = mods.new('Triangulate', 'TRIANGULATE')
    tri_mod.quad_method = 'FIXED'
    
def transform_export_scene(context, scene_nwo, granny_export) -> float:
    scale_factor = (1 / 0.03048) if scene_nwo.scale == 'blender' else 1
    rotation = utils.blender_halo_rotation_diff(scene_nwo.forward_direction)
    if not granny_export and (scale_factor != 1 or rotation):
        job = "--- Transforming Scene"
        if scale_factor != 1:
            job += " [Blender Scale -> Halo Scale]"
        if rotation:
            match scene_nwo.forward_direction:
                case "y":
                    job += " [Y Forward -> X Forward]"
                case "y-":
                    job += " [-Y Forward -> X Forward]"
                case "x-":
                    job += " [-X Forward -> X Forward]"
        print(job)
        utils.transform_scene(context, scale_factor, rotation, scene_nwo.forward_direction, 'x')
    return scale_factor

def update_physics_prims(prims):
    for ob in prims:
        prim_type = ob['bungie_mesh_primitive_type']
        if prim_type in ('_connected_geometry_primitive_type_box', '_connected_geometry_primitive_type_pill'):
            utils.set_origin_to_floor(ob)
            if prim_type == '_connected_geometry_primitive_type_box':
                ob["bungie_mesh_primitive_box_width"] =  utils.jstr(ob.dimensions.x)
                ob["bungie_mesh_primitive_box_length"] = utils.jstr(ob.dimensions.y)
                ob["bungie_mesh_primitive_box_height"] = utils.jstr(ob.dimensions.z)
            else:
                ob["bungie_mesh_primitive_pill_radius"] = utils.radius_str(ob, True)
                ob["bungie_mesh_primitive_pill_height"] = utils.jstr(ob.dimensions.z)
        else:
            utils.set_origin_to_centre(ob)
            ob["bungie_mesh_primitive_sphere_radius"] = utils.radius_str(ob)

class ArmatureMod:
    object: bpy.types.Object
    vertex_group: bpy.types.VertexGroup
    use_deform_preserve_volume: bool
    use_multi_modifier: bool
    use_vertex_groups: bool
    use_bone_envelopes: bool
    
    def __init__(self, name):
        self.name = name

def to_mesh(context, objects: list[bpy.types.Object]):
    objects_to_convert = [ob for ob in objects if ob.type in ("CURVE", "SURFACE", "META", "FONT") or (ob.type == 'MESH' and ob.modifiers)]
    armature_mod_dict = {}
    for ob in objects_to_convert:
        if not ob.modifiers: continue
        armature_mod_dict[ob] = []
        for mod in ob.modifiers:
            if mod.type == 'ARMATURE':
                arm_mod = ArmatureMod(mod.name)
                arm_mod.object = mod.object
                arm_mod.vertex_group = mod.vertex_group
                arm_mod.use_deform_preserve_volume = mod.use_deform_preserve_volume
                arm_mod.use_multi_modifier = mod.use_multi_modifier
                arm_mod.use_vertex_groups = mod.use_vertex_groups
                arm_mod.use_bone_envelopes = mod.use_bone_envelopes
                armature_mod_dict[ob].append(arm_mod)
                
    if objects_to_convert:
        for ob in objects_to_convert: ob.select_set(True)
        context.view_layer.objects.active = objects_to_convert[0]
        bpy.ops.object.convert(target='MESH')
        for ob in objects_to_convert: ob.select_set(False)
        context.view_layer.objects.active = None
        for ob, arm_mods in armature_mod_dict.items():
            for arm_mod in arm_mods:
                mod = ob.modifiers.new(name=arm_mod.name, type="ARMATURE")
                mod.object = arm_mod.object
                mod.vertex_group = arm_mod.vertex_group
                mod.use_deform_preserve_volume = arm_mod.use_deform_preserve_volume
                mod.use_multi_modifier = arm_mod.use_multi_modifier
                mod.use_vertex_groups = arm_mod.use_vertex_groups
                mod.use_bone_envelopes = arm_mod.use_bone_envelopes
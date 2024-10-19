from collections import defaultdict
from enum import Enum
from math import degrees
import os
from pathlib import Path
import random
import bpy
from mathutils import Vector

from ..props.animation import NWO_ActionPropertiesGroup, NWO_Animation_ListItems

from ..tools.scenario.lightmap import run_lightmapper

from ..tools.light_exporter import export_lights

from ..tools.scenario.zone_sets import write_zone_sets_to_scenario

from ..managed_blam import Tag
from ..managed_blam.scenario import ScenarioTag

from ..managed_blam.render_model import RenderModelTag
from ..managed_blam.animation import AnimationTag
from ..managed_blam.model import ModelTag
from .import_sidecar import SidecarImport
from .build_sidecar import Sidecar
from .export_info import ExportInfo, FaceDrawDistance, FaceMode, FaceSides, FaceType, LightmapType, MeshTessellationDensity, MeshType, ObjectType
from ..props.mesh import NWO_MeshPropertiesGroup
from ..props.object import NWO_ObjectPropertiesGroup
from .virtual_geometry import AnimatedBone, VirtualAnimation, VirtualNode, VirtualScene
from ..granny import Granny
from .. import utils
from ..constants import VALID_MESHES, VALID_OBJECTS
from ..tools.asset_types import AssetType

class ObjectCopy(Enum):
    NONE = 0
    SEAM = 1
    INSTANCE = 2
    WATER_PHYSICS = 3

face_prop_defaults = {
    "bungie_face_region": "default",
    "bungie_face_global_material": "default",
    "bungie_face_type": 0,
    "bungie_face_mode": 0,
    "bungie_face_sides": 0,
    "bungie_face_draw_distance": 0,
    "bungie_ladder": 0,
    "bungie_slip_surface": 0,
    "bungie_decal_offset": 0,
    "bungie_no_shadow": 0,
    "bungie_invisible_to_pvs": 0,
    "bungie_no_lightmap": 0,
    "bungie_precise_position": 0,
    "bungie_mesh_tessellation_density": 0,
    "bungie_lightmap_additive_transparency": (0.0, 0.0, 0.0, 0.0),
    "bungie_lightmap_resolution_scale": 3,
    "bungie_lightmap_type": 0,
    "bungie_lightmap_translucency_tint_color": (0.0, 0.0, 0.0, 0.0),
    "bungie_lightmap_lighting_from_both_sides": 0,
    "bungie_lighting_emissive_power": 0.0,
    "bungie_lighting_emissive_color": 0.0,
    "bungie_lighting_emissive_per_unit": 0,
    "bungie_lighting_emissive_quality": 0.0,
    "bungie_lighting_use_shader_gel": 0,
    "bungie_lighting_bounce_ratio": 0.0,
    "bungie_lighting_attenuation_enabled": 0,
    "bungie_lighting_attenuation_cutoff": 0.0,
    "bungie_lighting_attenuation_falloff": 0.0,
    "bungie_lighting_emissive_focus": 0.0,
}

class ExportTagType(Enum):
    RENDER = 0
    COLLISION = 1
    PHYSICS = 2
    MARKERS = 3
    SKELETON = 4
    ANIMATION = 5
    SKY = 6
    DECORATOR = 7
    STRUCTURE = 8
    STRUCTURE_DESIGN = 9
        
class ExportScene:
    '''Scene to hold all the export objects'''
    def __init__(self, context: bpy.types.Context, sidecar_path_full, sidecar_path, asset_type, asset_name, asset_path, corinth, export_settings, scene_settings):
        self.context = context
        self.asset_type = AssetType[asset_type.upper()]
        self.supports_bsp = self.asset_type.supports_bsp
        self.asset_name = asset_name
        self.asset_path = asset_path
        self.sidecar_path = sidecar_path
        self.corinth = corinth
        self.tags_dir = Path(utils.get_tags_path())
        self.data_dir = Path(utils.get_data_path())
        self.depsgraph: bpy.types.Depsgraph = None
        self.virtual_scene: VirtualScene = None
        self.no_parent_objects = []
        self.objects_with_children = set()
        self.default_region: str = context.scene.nwo.regions_table[0].name
        self.default_permutation: str = context.scene.nwo.permutations_table[0].name
        
        self.models_export_dir = Path(asset_path, "export", "models")
        self.animations_export_dir = Path(asset_path, "export", "animations")
        
        self.regions = [i.name for i in context.scene.nwo.regions_table]
        self.permutations = [i.name for i in context.scene.nwo.permutations_table]
        self.global_materials = set()
        self.global_materials_list = []
        
        self.reg_name = 'BSP' if self.asset_type.supports_bsp else 'region'
        self.perm_name = 'layer' if self.asset_type.supports_bsp else 'permutation'
        
        self.processed_meshes = {}
        self.processed_poop_meshes = set()

        self.game_version = 'corinth' if corinth else 'reach'
        self.export_settings = export_settings
        self.scene_settings = scene_settings
        self.sidecar = Sidecar(sidecar_path_full, sidecar_path, asset_path, asset_name, self.asset_type, scene_settings, corinth, context)
        
        self.selected_permutations = set()
        self.selected_bsps = set()
        self.limit_perms_to_selection = export_settings.export_all_perms == 'selected'
        self.limit_bsps_to_selection = export_settings.export_all_bsps == 'selected'
        
        self.project_root = self.tags_dir.parent
        self.warnings = []
        os.chdir(self.project_root)
        self.granny = Granny(Path(self.project_root, "granny2_x64.dll"), self.corinth)
        
        self.forward = scene_settings.forward_direction
        self.scale = 1 if scene_settings.scale == 'max' else 0.03048
        self.inverse_scale = 1 if scene_settings.scale == 'blender' else 1 / 0.03048
        self.mirror = export_settings.granny_mirror
        self.has_animations = False
        self.exported_actions = []
        self.setup_scenario = False
        self.lights = []
        self.temp_objects = {}
        self.sky_lights = []
        
        self.is_model = self.asset_type in {AssetType.MODEL, AssetType.SKY}
        self.export_tag_types = self._get_export_tag_types()
        
        self.pre_title_printed = False
        self.post_title_printed = False
        gr2_debug = utils.has_gr2_viewer()
        self.granny_textures = gr2_debug and export_settings.granny_textures
        self.granny_open = gr2_debug and export_settings.granny_open
        self.granny_animations_mesh = gr2_debug and export_settings.granny_animations_mesh
        
    def _get_export_tag_types(self):
        tag_types = set()
        match self.asset_type:
            case AssetType.MODEL:
                if self.export_settings.export_render:
                    tag_types.add('render')
                if self.export_settings.export_collision:
                    tag_types.add('collision')
                if self.export_settings.export_physics:
                    tag_types.add('physics')
                if self.export_settings.export_markers:
                    tag_types.add('markers')
                if self.export_settings.export_skeleton:
                    tag_types.add('skeleton')
                tag_types.add('animation')
            case AssetType.ANIMATION:
                tag_types.add('render')
                tag_types.add('animation')
            case AssetType.SCENARIO:
                if self.export_settings.export_structure:
                    tag_types.add('structure')
                if self.export_settings.export_design:
                    tag_types.add('design')
            case AssetType.PREFAB:
                if self.export_settings.export_structure:
                    tag_types.add('structure')
            case AssetType.SKY | AssetType.DECORATOR_SET | AssetType.PARTICLE_MODEL:
                tag_types.add('render')
                
        return tag_types
        
    def ready_scene(self):
        utils.exit_local_view(self.context)
        self.context.view_layer.update()
        utils.set_object_mode(self.context)
        self.disabled_collections = utils.disable_excluded_collections(self.context)
        self.current_frame = self.context.scene.frame_current
        self.current_action = None
        self.animated_objects = {}
        if self.asset_type in {AssetType.MODEL, AssetType.ANIMATION}:
            action_index = self.context.scene.nwo.active_action_index
            if action_index > -1:
                self.current_action = bpy.data.actions[action_index]
            self.animated_objects = utils.reset_to_basis(self.context, record_current_action=True)
        
    def get_initial_export_objects(self):
        self.temp_objects = set()
        self.main_armature = self.context.scene.nwo.main_armature
        self.support_armatures = {}
        self.export_objects = []
        
        instancers = [ob for ob in self.context.view_layer.objects if ob.is_instancer and ob.instance_collection and ob.instance_collection.all_objects and not ob.nwo.marker_instance]
            
        skip_obs = set()
        if instancers:
            self.instanced_collections = set()
            self.collections_to_hide = set()
            for ob in instancers:
                self.instanced_collections.add(ob.instance_collection)

            for ob in instancers:
                ob: bpy.types.Object
                skip_obs.add(ob)
                lookup_dict = {}
                users_collection = ob.users_collection
                for source_ob in ob.instance_collection.all_objects:
                    source_ob: bpy.types.Object
                    temp_ob = source_ob.copy()
                    lookup_dict[source_ob] = temp_ob
                    for collection in users_collection:
                        collection.objects.link(temp_ob)
                        
                    self.temp_objects.add(temp_ob)
                
                for value in lookup_dict.values():
                    if value.parent:
                        new_parent = lookup_dict.get(value.parent)
                        if new_parent is None:
                            value.matrix_world = ob.matrix_world @ value.matrix_world
                        else:
                            old_local = value.matrix_local.copy()
                            value.parent = new_parent
                            value.matrix_local = old_local
                    else:
                        value.matrix_world = ob.matrix_world @ value.matrix_world
            
        if self.main_armature:
            self.support_armatures = {self.context.scene.nwo.support_armature_a, self.context.scene.nwo.support_armature_b, self.context.scene.nwo.support_armature_c}
            
        self.depsgraph = self.context.evaluated_depsgraph_get()
        
        if self.asset_type == AssetType.ANIMATION and not self.granny_animations_mesh:
            self.export_objects = [ob.evaluated_get(self.depsgraph) for ob in self.context.view_layer.objects if ob.nwo.export_this and (ob.type == "ARMATURE" and ob not in self.support_armatures) and ob not in skip_obs]
        else:    
            self.export_objects = [ob.evaluated_get(self.depsgraph) for ob in self.context.view_layer.objects if ob.nwo.export_this and ob.type in VALID_OBJECTS and ob not in self.support_armatures and ob not in skip_obs]
        
        self.virtual_scene = VirtualScene(self.asset_type, self.depsgraph, self.corinth, self.tags_dir, self.granny, self.export_settings, self.context.scene.render.fps, self.scene_settings.default_animation_compression, utils.blender_halo_rotation_diff(self.forward), self.scene_settings.maintain_marker_axis, self.granny_textures)
        
    def create_instance_proxies(self, ob: bpy.types.Object, ob_halo_data: dict, region: str, permutation: str):
        self.processed_poop_meshes.add(ob.data)
        data_nwo = ob.original.data.nwo
        proxy_physics_list = [getattr(data_nwo, f"proxy_physics{i}", None) for i in range(10) if getattr(data_nwo, f"proxy_physics{i}") is not None]
        proxy_collision = data_nwo.proxy_collision
        proxy_cookie_cutter = data_nwo.proxy_cookie_cutter
        
        has_coll = proxy_collision is not None
        has_phys = bool(proxy_physics_list)
        has_cookie = proxy_cookie_cutter is not None and not self.corinth
        
        proxies = []
        
        if has_coll:
            proxy_collision = proxy_collision.evaluated_get(self.depsgraph)
            coll_props = {}
            coll_props["bungie_object_type"] = ObjectType.mesh.value
            coll_props["bungie_mesh_type"] = MeshType.poop_collision.value
            if self.corinth:
                if has_phys:
                    coll_props["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_bullet_collision"
                else:
                    coll_props["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_default"
                    
            fp_defaults, mesh_props = self.processed_meshes.get(proxy_collision.data, (None, None))
            if mesh_props is None:
                fp_defaults, mesh_props = self._setup_mesh_level_props(proxy_collision, "default", {})
                # Collision proxies must not be breakable, else tool will crash
                if mesh_props.get("bungie_face_mode") == FaceMode.breakable.value:
                    mesh_props["bungie_face_mode"] = FaceMode.normal.value
                if fp_defaults.get("bungie_face_mode") == FaceMode.breakable.value:
                    fp_defaults["bungie_face_mode"] = FaceMode.normal.value
                self.processed_meshes[proxy_collision.data] = (fp_defaults, mesh_props)
            
            coll_props.update(mesh_props)
            ob_halo_data[proxy_collision] = (coll_props, region, permutation, fp_defaults, tuple())
            proxies.append(proxy_collision)
            
        if has_phys:
            for proxy_physics in proxy_physics_list:
                proxy_physics = proxy_physics.evaluated_get(self.depsgraph)
                phys_props = {}
                phys_props["bungie_object_type"] = ObjectType.mesh.value
                if self.corinth:
                    phys_props["bungie_mesh_type"] = MeshType.poop_collision.value
                    phys_props["bungie_mesh_poop_collision_type"] = "_connected_geometry_poop_collision_type_play_collision"
                else:
                    phys_props["bungie_mesh_type"] = MeshType.poop_physics.value
                        
                fp_defaults, mesh_props = self.processed_meshes.get(proxy_physics.data, (None, None))
                if mesh_props is None:
                    fp_defaults, mesh_props = self._setup_mesh_level_props(proxy_physics, "default", {})
                    self.processed_meshes[proxy_physics.data] = (fp_defaults, mesh_props)
                
                phys_props.update(mesh_props)
                ob_halo_data[proxy_physics] = (phys_props, region, permutation, fp_defaults, tuple())
                proxies.append(proxy_physics)
            
        if has_cookie:
            proxy_cookie_cutter = proxy_cookie_cutter.evaluated_get(self.depsgraph)
            cookie_props = {}
            cookie_props["bungie_object_type"] = ObjectType.mesh.value
            cookie_props["bungie_mesh_type"] = MeshType.cookie_cutter.value
            fp_defaults, mesh_props = self.processed_meshes.get(proxy_cookie_cutter.data, (None, None))
            if mesh_props is None:
                fp_defaults, mesh_props = self._setup_mesh_level_props(proxy_cookie_cutter, "default", {})
                self.processed_meshes[proxy_cookie_cutter.data] = (fp_defaults, mesh_props)
            
            cookie_props.update(mesh_props)
            ob_halo_data[proxy_cookie_cutter] = (cookie_props, region, permutation, fp_defaults, tuple())
            proxies.append(proxy_cookie_cutter)
        
        return ob_halo_data, proxies, has_coll
    
    def map_halo_properties(self):
        process = "--- Mapping Halo Properties"
        self.ob_halo_data = {}
        num_export_objects = len(self.export_objects)
        self.collection_map = create_parent_mapping(self.depsgraph)
        self.forced_render_only = {}
        self.armature_poses = {}
        object_parent_dict = {}
        evaluated_support_armatures = set()
        for ob in self.support_armatures:
            if ob is not None:
                evaluated_support_armatures.add(ob.evaluated_get(self.depsgraph))
        
        armature = None
        if self.asset_type in {AssetType.MODEL, AssetType.ANIMATION}:
            armature = utils.get_rig(self.context)
        
        for ob in bpy.data.objects:
            if ob.parent:
                self.objects_with_children.add(ob.parent)
                
        
        with utils.Spinner():
            utils.update_job_count(process, "", 0, num_export_objects)
            for idx, ob in enumerate(self.export_objects):
                ob: bpy.types.Object
                if ob.type == 'ARMATURE':
                    self.armature_poses[ob.original.data] = ob.original.data.pose_position
                    ob.original.data.pose_position = 'REST'
                elif ob.type == 'LIGHT':
                    if ob.data.type != 'AREA':
                        self.lights.append(ob)
                    if not self.corinth and self.asset_type == AssetType.SKY:
                        self.sky_lights.append(ob)
                    continue

                result = self.get_halo_props(ob)
                if result is None:
                    continue
                props, region, permutation, fp_defaults, mesh_props, copy = result
                
                if self.limit_perms_to_selection and ob.original.select_get():
                    self.selected_permutations.add(permutation)
                if self.limit_bsps_to_selection and ob.original.select_get():
                    self.selected_bsps.add(region)
                
                parent = ob.parent
                proxies = tuple()
                # Write object as if it has no parent if this is not a model and it is parented to an empty/armature. It solves an issue where instancing fails
                if (parent or (armature and ob.type != "ARMATURE")) and (parent and ob.parent.type not in {'EMPTY', 'ARMATURE'} or self.is_model):
                    if parent in evaluated_support_armatures:
                        object_parent_dict[ob] = self.main_armature.evaluated_get(self.depsgraph)
                    elif not parent:
                        object_parent_dict[ob] = armature.evaluated_get(self.depsgraph)
                    else:
                        object_parent_dict[ob] = parent.evaluated_get(self.depsgraph)
                else:
                    self.no_parent_objects.append(ob)
                    
                if self.supports_bsp and props.get("bungie_mesh_type") == MeshType.poop.value and ob.data not in self.processed_poop_meshes:
                    self.ob_halo_data, proxies, has_collision_proxy = self.create_instance_proxies(ob, self.ob_halo_data, region, permutation)
                    if has_collision_proxy:
                        current_face_mode = mesh_props.get("bungie_face_mode")
                        if not current_face_mode or current_face_mode not in {FaceMode.render_only.value, FaceMode.lightmap_only.value, FaceMode.shadow_only.value}:
                            mesh_props["bungie_face_mode"] = FaceMode.render_only.value
                
                props.update(mesh_props)
                
                if copy is not None:
                    copy_props = props.copy()
                    copy_ob = ob.copy()
                    self.temp_objects.add(copy_ob)
                    copy_region = region
                    match copy:
                        case ObjectCopy.SEAM:
                            copy_ob.nwo.invert_topology = True
                            back_ui = ob.nwo.seam_back
                            if (not back_ui or back_ui == region or back_ui not in self.regions):
                                self.warnings.append(f"{ob.name} has bad back facing bsp reference. Removing Seam from export")
                                continue
                            
                            copy_region = back_ui
                            copy_props["bungie_mesh_seam_associated_bsp"] = f"{self.asset_name}_{copy_region}"
                            
                        case ObjectCopy.INSTANCE:
                            copy_props["bungie_mesh_type"] = MeshType.poop.value
                            if copy_props.get("bungie_face_type") == FaceType.sky.value:
                                copy_props.pop("bungie_face_type")
                            copy_props, copy_mesh_props = self._setup_poop_props(copy_ob, ob.nwo, ob.data.nwo, copy_props, mesh_props)
                            copy_props.update(copy_mesh_props)
                            
                        case ObjectCopy.WATER_PHYSICS:
                            copy_props["bungie_mesh_type"] = MeshType.water_physics_volume.value
                            copy_props = self._setup_water_physics_props(copy_ob.nwo, copy_props)
                    
                    self.ob_halo_data[copy_ob] = [copy_props, copy_region, permutation, fp_defaults, proxies]
                    self.no_parent_objects.append(copy_ob)
                    
                self.ob_halo_data[ob] = [props, region, permutation, fp_defaults, proxies]
                    
                utils.update_job_count(process, "", idx, num_export_objects)
            utils.update_job_count(process, "", num_export_objects, num_export_objects)
            
        self.global_materials_list = list(self.global_materials - {'default'})
        self.global_materials_list.insert(0, 'default')
        self.export_info = ExportInfo(self.regions if self.asset_type.supports_regions else None, self.global_materials_list if self.asset_type.supports_global_materials else None).create_info()
        self.virtual_scene.regions = self.regions
        self.virtual_scene.regions_set = set(self.regions)
        self.virtual_scene.global_materials = self.global_materials_list
        self.virtual_scene.global_materials_set = set(self.global_materials_list)
        self.virtual_scene.object_parent_dict = object_parent_dict
        self.virtual_scene.object_halo_data = self.ob_halo_data
        self.virtual_scene.export_tag_types = self.export_tag_types
        self.context.view_layer.update()
        
    def _get_object_type(self, ob) -> ObjectType:
        if ob.type in VALID_MESHES:
            return ObjectType.mesh
        elif ob.type == 'EMPTY' and ob.empty_display_type != "IMAGE":
            if ob in self.objects_with_children:
                return ObjectType.frame
            else:
                return ObjectType.marker
        elif ob.type == 'ARMATURE':
            return ObjectType.frame
                
        return ObjectType.none
            
    def get_halo_props(self, ob: bpy.types.Object):
        props = {}
        mesh_props = {}
        copy = None
        region = self.default_region
        permutation = self.default_permutation
        fp_defaults = {}
        nwo = ob.original.nwo
        object_type = self._get_object_type(ob.original)
        # Frames go unused in non-model exports
        if object_type == ObjectType.none or (not self.is_model and object_type == ObjectType.frame):
            return 
        
        props["bungie_object_type"] = object_type.value
        # props["bungie_object_type"] = object_type
        is_mesh = object_type == ObjectType.mesh
        instanced_object = (is_mesh and nwo.mesh_type == '_connected_geometry_mesh_type_object_instance')
        tmp_region, tmp_permutation = nwo.region_name, nwo.permutation_name
        collection = bpy.data.collections.get(ob.nwo.export_collection)
        if collection and collection != self.context.scene.collection:
            export_coll = self.collection_map[collection]
            coll_region, coll_permutation = export_coll.region, export_coll.permutation
            if coll_region:
                tmp_region = coll_region
            if coll_permutation:
                tmp_region = coll_permutation
                
        if self.asset_type.supports_permutations:
            if not instanced_object and (is_mesh or self.asset_type.supports_bsp or nwo.marker_uses_regions):
                if tmp_region in self.regions:
                    region = tmp_region
                else:
                    self.warnings.append(f"Object [{ob.name}] has {self.reg_name} [{tmp_region}] which is not present in the {self.reg_name}s table. Setting {self.reg_name} to: {self.default_region}")
                    
            if self.asset_type.supports_permutations and not instanced_object:
                if tmp_permutation in self.permutations:
                    permutation = tmp_permutation
                else:
                    self.warnings.append(f"Object [{ob.name}] has {self.perm_name} [{tmp_permutation}] which is not present in the {self.perm_name}s table. Setting {self.perm_name} to: {self.default_permutation}")
                    
            elif nwo.marker_uses_regions and nwo.marker_permutation_type == 'include' and nwo.marker_permutations:
                marker_perms = [item.name for item in nwo.marker_permutations]
                for perm in marker_perms:
                    if perm not in self.permutations:
                        self.warnings.append(f"Object [{ob.name}] has {self.perm_name} [{perm}] in its include list which is not present in the {self.perm_name}s table. Ignoring {self.perm_name}")
            
        if object_type == ObjectType.mesh:
            if nwo.mesh_type == '':
                nwo.mesh_type = '_connected_geometry_mesh_type_default'
            if utils.type_valid(nwo.mesh_type, self.asset_type.name.lower(), self.game_version):
                props, fp_defaults, mesh_props, copy = self._setup_mesh_properties(ob, ob.nwo, self.asset_type.supports_bsp, props, region, mesh_props, copy)
                if props is None:
                    return
                
            else:
                return self.warnings.append(f"{ob.name} has invalid mesh type [{nwo.mesh_type}] for asset [{self.asset_type}]. Skipped")
                
        elif object_type == ObjectType.marker:
            if nwo.marker_type == '':
                nwo.marker_type = '_connected_geometry_marker_type_model'
            if utils.type_valid(nwo.marker_type, self.asset_type.name.lower(), self.game_version):
                props = self._setup_marker_properties(ob, ob.nwo, props, region)
                if props is None:
                    return
            else:
                return self.warnings.append(f"{ob.name} has invalid marker type [{nwo.mesh_type}] for asset [{self.asset_type}]. Skipped")

        return props, region, permutation, fp_defaults, mesh_props, copy
    
    def _setup_mesh_properties(self, ob: bpy.types.Object, nwo: NWO_ObjectPropertiesGroup, supports_bsp: bool, props: dict, region: str, mesh_props: dict, copy):
        mesh_type = ob.original.data.nwo.mesh_type
        mesh = ob.original.data
        data_nwo: NWO_MeshPropertiesGroup = mesh.nwo
        
        if supports_bsp:
            # Foundry stores instances as the default mesh type, so switch them back to poops and structure to default
            match mesh_type:
                case '_connected_geometry_mesh_type_default':
                    mesh_type = '_connected_geometry_mesh_type_poop'
                case '_connected_geometry_mesh_type_structure':
                    mesh_type = '_connected_geometry_mesh_type_default'
        
        if mesh_type == "_connected_geometry_mesh_type_physics":
            props = self._setup_physics_props(ob, nwo, props)
        elif mesh_type == '_connected_geometry_mesh_type_object_instance':
            props = self._setup_instanced_object_props(nwo, props, region)
        elif mesh_type == '_connected_geometry_mesh_type_poop':
            props, mesh_props = self._setup_poop_props(ob, nwo, data_nwo, props, mesh_props)
        elif mesh_type == '_connected_geometry_mesh_type_default' and self.corinth and self.asset_type == AssetType.SCENARIO:
            props["bungie_face_type"] = FaceType.sky.value
            if nwo.proxy_instance:
                copy = ObjectCopy.INSTANCE
        elif mesh_type == '_connected_geometry_mesh_type_seam':
            props["bungie_mesh_seam_associated_bsp"] = f"{self.asset_name}_{region}"
            if not nwo.seam_back_manual:
                copy = ObjectCopy.SEAM
        elif mesh_type == "_connected_geometry_mesh_type_portal":
            props["bungie_mesh_portal_type"] = nwo.portal_type
            if nwo.portal_ai_deafening:
                props["bungie_mesh_portal_ai_deafening"] = 1
            if nwo.portal_blocks_sounds:
                props["bungie_mesh_portal_blocks_sound"] = 1
            if nwo.portal_is_door:
                props["bungie_mesh_portal_is_door"] = 1
        elif mesh_type == "_connected_geometry_mesh_type_water_physics_volume":
            props = self._setup_water_physics_props(nwo, props)
        elif mesh_type == "_connected_geometry_mesh_type_water_surface":
            if nwo.water_volume_depth > 0:
                copy = ObjectCopy.WATER_PHYSICS
        elif mesh_type in ("_connected_geometry_mesh_type_poop_vertical_rain_sheet", "_connected_geometry_mesh_type_poop_rain_blocker"):
            mesh_props["bungie_face_mode"] = FaceMode.render_only.value
            
        elif mesh_type == "_connected_geometry_mesh_type_planar_fog_volume":
            props["bungie_mesh_fog_appearance_tag"] = utils.relative_path(nwo.fog_appearance_tag)
            props["bungie_mesh_fog_volume_depth"] = nwo.fog_volume_depth
            
        elif mesh_type == "_connected_geometry_mesh_type_soft_ceiling":
            mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            props["bungie_mesh_boundary_surface_type"] = '_connected_geometry_boundary_surface_type_soft_ceiling'
            props["bungie_mesh_boundary_surface_name"] = utils.dot_partition(ob.name)
            
        elif mesh_type == "_connected_geometry_mesh_type_soft_kill":
            mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            props["bungie_mesh_boundary_surface_type"] = '_connected_geometry_boundary_surface_type_soft_kill'
            props["bungie_mesh_boundary_surface_name"] = utils.dot_partition(ob.name)
            
        elif mesh_type == "_connected_geometry_mesh_type_slip_surface":
            mesh_type = "_connected_geometry_mesh_type_boundary_surface"
            props["bungie_mesh_boundary_surface_type"] = '_connected_geometry_boundary_surface_type_slip_surface'
            props["bungie_mesh_boundary_surface_name"] = utils.dot_partition(ob.name)
            
        elif mesh_type == "_connected_geometry_mesh_type_lightmap_only":
            nwo.lightmap_resolution_scale_active = False
            mesh_type = "_connected_geometry_mesh_type_poop"
            props, mesh_props = self._setup_poop_props(ob, nwo, data_nwo, props, mesh_props)
            if data_nwo.no_shadow:
                mesh_props["bungie_face_mode"] = FaceMode.render_only.value
            else:
                mesh_props["bungie_face_mode"] = FaceMode.lightmap_only.value
            props["bungie_mesh_poop_lighting"] = "_connected_geometry_poop_lighting_single_probe"
            props["bungie_mesh_poop_pathfinding"] = "_connected_poop_instance_pathfinding_policy_none"
            
        elif mesh_type == "_connected_geometry_mesh_type_lightmap_exclude":
            mesh_type = "_connected_geometry_mesh_type_obb_volume"
            props["bungie_mesh_obb_type"] = "_connected_geometry_mesh_obb_volume_type_lightmapexclusionvolume"
            
        elif mesh_type == "_connected_geometry_mesh_type_streaming":
            mesh_type = "_connected_geometry_mesh_type_obb_volume"
            props["bungie_mesh_obb_type"] = "_connected_geometry_mesh_obb_volume_type_streamingvolume"
            
        elif mesh_type == '_connected_geometry_mesh_type_collision' and self.asset_type in {AssetType.SCENARIO, AssetType.PREFAB}:
            if self.corinth:
                mesh_type = '_connected_geometry_mesh_type_poop_collision'
                props["bungie_mesh_poop_collision_type"] = data_nwo.poop_collision_type
            elif ob.parent and ob.parent.type in VALID_MESHES and ob.parent.data.nwo.mesh_type == '_connected_geometry_mesh_type_default':
                mesh_type = '_connected_geometry_mesh_type_poop_collision'
                props["bungie_poop_parent"] = '_connected_geometry_mesh_type_poop_collision'
                parent_halo_data = self.ob_halo_data.get(ob.parent)
                if parent_halo_data:
                    # if parent_halo_data[0].get("bungie_face_mode") not in 
                    parent_halo_data[0]["bungie_face_mode"] = FaceMode.render_only.value
                else:
                    self.forced_render_only[ob.parent] = None
            else:
                mesh_type = '_connected_geometry_mesh_type_poop'
                props["bungie_mesh_poop_lighting"] = "_connected_geometry_poop_lighting_single_probe"
                props["bungie_mesh_poop_pathfinding"] = "_connected_poop_instance_pathfinding_policy_cutout"
                props["bungie_mesh_poop_imposter_policy"] = "_connected_poop_instance_imposter_policy_never"
                # nwo.reach_poop_collision = True
                if data_nwo.sphere_collision_only:
                    mesh_props["bungie_face_mode"] = FaceMode.sphere_collision_only.value
                else:
                    mesh_props["bungie_face_mode"] = FaceMode.collision_only.value
        
        elif self.asset_type == AssetType.PREFAB:
            mesh_type = '_connected_geometry_mesh_type_poop'
            self._setup_poop_props(ob, nwo, data_nwo, props)
            
        elif self.asset_type == AssetType.DECORATOR_SET:
            mesh_type = '_connected_geometry_mesh_type_decorator'
            lod = decorator_int(ob)
            self.sidecar.lods.add(lod)
            props["bungie_mesh_decorator_lod"] = lod
        
        props["bungie_mesh_type"] = MeshType[mesh_type[30:]].value
        
        fp_defaults, tmp_mesh_props = self.processed_meshes.get(ob.data, (None, None))
        if tmp_mesh_props is None:
            fp_defaults, mesh_props = self._setup_mesh_level_props(ob, region, mesh_props)
            self.processed_meshes[ob.data] = (fp_defaults, mesh_props)
        else:
            mesh_props.update(tmp_mesh_props)

        return props, fp_defaults, mesh_props, copy
        
    def _setup_physics_props(self, ob: bpy.types.Object, nwo: NWO_ObjectPropertiesGroup, props: dict):
        prim_type = nwo.mesh_primitive_type
        props["bungie_mesh_primitive_type"] = prim_type
        if prim_type != '_connected_geometry_primitive_type_none':
            props = self._set_primitive_props(ob, prim_type, props)
        elif self.corinth and nwo.mopp_physics:
            props["bungie_mesh_primitive_type"] = "_connected_geometry_primitive_type_mopp"
            props["bungie_havok_isshape"] = 1
            
        return props
    
    def _setup_water_physics_props(self, nwo: NWO_ObjectPropertiesGroup, props: dict):
        props["bungie_mesh_water_volume_depth"] = nwo.water_volume_depth
        props["bungie_mesh_water_volume_flow_direction"] = degrees(nwo.water_volume_flow_direction)
        props["bungie_mesh_water_volume_flow_velocity"] = nwo.water_volume_flow_velocity
        props["bungie_mesh_water_volume_fog_murkiness"] = nwo.water_volume_fog_murkiness
        if self.corinth:
            props["bungie_mesh_water_volume_fog_color"] = utils.color_rgba(nwo.water_volume_fog_color)
        else:
            props["bungie_mesh_water_volume_fog_color"] = utils.color_argb(nwo.water_volume_fog_color)
            
        return props
    
    def _setup_instanced_object_props(self, nwo: NWO_ObjectPropertiesGroup, props: dict, region: str):
        props["bungie_marker_all_regions"] = int(not nwo.marker_uses_regions)
        if nwo.marker_uses_regions:
            props["bungie_marker_region"] = region
            m_perms = nwo.marker_permutations
            if m_perms:
                m_perm_set = set()
                for perm in m_perms:
                    m_perm_set.add(perm.name)
                m_perm_json_value = f'''#({', '.join('"' + p + '"' for p in m_perm_set)})'''
                if nwo.marker_permutation_type == "exclude":
                    props["bungie_marker_exclude_from_permutations"] = m_perm_json_value
                else:
                    props["bungie_marker_include_in_permutations"] = m_perm_json_value
                
        return props
    
    def _setup_poop_props(self, ob: bpy.types.Object, nwo: NWO_ObjectPropertiesGroup, data_nwo: NWO_MeshPropertiesGroup, props: dict, mesh_props: dict):
        props["bungie_mesh_poop_lighting"] = nwo.poop_lighting
        props["bungie_mesh_poop_pathfinding"] = nwo.poop_pathfinding
        props["bungie_mesh_poop_imposter_policy"] = nwo.poop_imposter_policy
        if (
            nwo.poop_imposter_policy
            != "_connected_poop_instance_imposter_policy_never"
        ):
            if not nwo.poop_imposter_transition_distance_auto:
                props["bungie_mesh_poop_imposter_transition_distance"] = nwo.poop_imposter_transition_distance
            if self.corinth:
                nwo["bungie_mesh_poop_imposter_brightness"] = nwo.poop_imposter_brightness

        if nwo.poop_render_only:
            if self.corinth:
                props["bungie_mesh_poop_collision_type"] = '_connected_geometry_poop_collision_type_none'
            else:
                props["bungie_mesh_poop_is_render_only"] = 1
                
        elif self.corinth:
            props["bungie_mesh_poop_collision_type"] = data_nwo.poop_collision_type
        if nwo.poop_does_not_block_aoe:
            props["bungie_mesh_poop_does_not_block_aoe"] = 1
        if nwo.poop_excluded_from_lightprobe:
            props["bungie_mesh_poop_excluded_from_lightprobe"] = 1
            
        if data_nwo.decal_offset:
            props["bungie_mesh_poop_decal_spacing"] = 1 
        if data_nwo.precise_position:
            props["bungie_mesh_poop_precise_geometry"] = 1

        if self.corinth:
            props["bungie_mesh_poop_lightmap_resolution_scale"] = nwo.poop_lightmap_resolution_scale
            props["bungie_mesh_poop_streamingpriority"] = nwo.poop_streaming_priority
            props["bungie_mesh_poop_cinema_only"] = int(nwo.poop_cinematic_properties == '_connected_geometry_poop_cinema_only')
            props["bungie_mesh_poop_exclude_from_cinema"] = int(nwo.poop_cinematic_properties == '_connected_geometry_poop_cinema_exclude')
            if nwo.poop_remove_from_shadow_geometry:
                props["bungie_mesh_poop_remove_from_shadow_geometry"] = 1
            if nwo.poop_disallow_lighting_samples:
                props["bungie_mesh_poop_disallow_object_lighting_samples"] = 1
        
        if self.forced_render_only.get(ob):
            props["bungie_face_mode"] = FaceMode.render_only.value

        return props, mesh_props
        
    def _setup_marker_properties(self, ob: bpy.types.Object, nwo: NWO_ObjectPropertiesGroup, props: dict, region: str):
        marker_type = nwo.marker_type
        props["bungie_marker_type"] = marker_type
        props["bungie_marker_model_group"] = nwo.marker_model_group
        if self.is_model:
            props["bungie_marker_all_regions"] = int(not nwo.marker_uses_regions)
            if nwo.marker_uses_regions:
                props["bungie_marker_region"] = region
                m_perms = nwo.marker_permutations
                if m_perms:
                    m_perm_set = set()
                    for perm in m_perms:
                        m_perm_set.add(perm.name)
                    m_perm_json_value = f'''#({', '.join('"' + p + '"' for p in m_perm_set)})'''
                    if nwo.marker_permutation_type == "exclude":
                        props["bungie_marker_exclude_from_permutations"] = m_perm_json_value
                    else:
                        props["bungie_marker_include_in_permutations"] = m_perm_json_value
                        
            if marker_type == "_connected_geometry_marker_type_hint":
                if self.corinth:
                    scale = ob.matrix_world.to_scale()
                    max_abs_scale = max(abs(scale.x), abs(scale.y), abs(scale.z))
                    props["bungie_marker_hint_length"] = ob.empty_display_size * 2 * max_abs_scale

                # TODO Move all this code to update the name while editing in Blender
                # ob.name = "hint_"
                # if nwo.marker_hint_type == "bunker":
                #     ob.name += "bunker"
                # elif nwo.marker_hint_type == "corner":
                #     ob.name += "corner_"
                #     if nwo.marker_hint_side == "right":
                #         ob.name += "right"
                #     else:
                #         ob.name += "left"

                # else:
                #     if nwo.marker_hint_type == "vault":
                #         ob.name += "vault_"
                #     elif nwo.marker_hint_type == "mount":
                #         ob.name += "mount_"
                #     else:
                #         ob.name += "hoist_"

                #     if nwo.marker_hint_height == "step":
                #         ob.name += "step"
                #     elif nwo.marker_hint_height == "crouch":
                #         ob.name += "crouch"
                #     else:
                #         ob.name += "stand"
                        
            elif marker_type == "_connected_geometry_marker_type_pathfinding_sphere":
                props["bungie_mesh_primitive_sphere_radius"] = self.get_marker_sphere_size(ob)
                props["bungie_marker_pathfinding_sphere_vehicle_only"] = int(nwo.marker_pathfinding_sphere_vehicle)
                props["bungie_marker_pathfinding_sphere_remains_when_open"] = int(nwo.pathfinding_sphere_remains_when_open)
                props["bungie_marker_pathfinding_sphere_with_sectors"] = int(nwo.pathfinding_sphere_with_sectors)
                
            elif marker_type == "_connected_geometry_marker_type_physics_constraint":
                props["bungie_marker_type"] = nwo.physics_constraint_type
                parent = nwo.physics_constraint_parent
                if (
                    parent is not None
                    and parent.type == "ARMATURE"
                    and nwo.physics_constraint_parent_bone != ""
                ):
                    props["bungie_physics_constraint_parent"] = (
                        nwo.physics_constraint_parent_bone
                    )

                elif parent is not None:
                    props["bungie_physics_constraint_parent"] = str(
                        nwo.physics_constraint_parent.parent_bone
                    )
                child = nwo.physics_constraint_child
                if (
                    child is not None
                    and child.type == "ARMATURE"
                    and nwo.physics_constraint_child_bone != ""
                ):
                    props["bungie_physics_constraint_child"] = (
                        nwo.physics_constraint_child_bone
                    )

                elif child is not None:
                    props["bungie_physics_constraint_child"] = str(
                        nwo.physics_constraint_child.parent_bone
                    )
                props["bungie_physics_constraint_use_limits"] = int(
                    nwo.physics_constraint_uses_limits
                )
                if nwo.physics_constraint_uses_limits:
                    if nwo.physics_constraint_type == "_connected_geometry_marker_type_physics_hinge_constraint":
                        props["bungie_physics_constraint_hinge_min"] = degrees(nwo.hinge_constraint_minimum)
                        props["bungie_physics_constraint_hinge_max"] = degrees(nwo.hinge_constraint_maximum)
                    else:
                        props["bungie_physics_constraint_cone_angle"] = degrees(nwo.cone_angle)
                        props["bungie_physics_constraint_plane_min"] = degrees(nwo.plane_constraint_minimum)
                        props["bungie_physics_constraint_plane_max"] = degrees(nwo.plane_constraint_maximum)
                        props["bungie_physics_constraint_twist_start"] = degrees(nwo.twist_constraint_start)
                        props["bungie_physics_constraint_twist_end"] = degrees(nwo.twist_constraint_end)
                
            elif marker_type == "_connected_geometry_marker_type_target":
                props["bungie_mesh_primitive_sphere_radius"] = self.get_marker_sphere_size(ob)
                
            elif marker_type == "_connected_geometry_marker_type_effects":
                props["bungie_marker_type"] = "_connected_geometry_marker_type_model"
                if not ob.name.startswith("fx_"):
                    ob.name = "fx_" + ob.name
                    
            elif marker_type == "_connected_geometry_marker_type_garbage":
                if not self.corinth:
                    props["bungie_marker_type"] = "_connected_geometry_marker_type_model"
                props["bungie_marker_velocity"] = utils.vector(nwo.marker_velocity)
        
        elif self.asset_type in {AssetType.SCENARIO, AssetType.PREFAB}:
            if marker_type == "_connected_geometry_marker_type_game_instance":
                props["bungie_object_ID"] = str(nwo.ObjectID)
                tag_name = nwo.marker_game_instance_tag_name.lower()
                props["bungie_marker_game_instance_tag_name"] = tag_name
                if self.corinth and tag_name.endswith(
                    ".prefab"
                ):
                    props["bungie_marker_type"] = "_connected_geometry_marker_type_prefab"
                    if nwo.prefab_pathfinding != "no_override":
                        props["bungie_mesh_poop_pathfinding"] = nwo.prefab_pathfinding
                    if nwo.prefab_lightmap_res > 0:
                        props["bungie_mesh_poop_lightmap_resolution_scale"] = nwo.prefab_lightmap_res
                    if nwo.prefab_lighting != "no_override":
                        props["bungie_mesh_poop_lighting"] = nwo.prefab_lighting
                    if nwo.prefab_imposter_policy != "no_override":
                        props["bungie_mesh_poop_imposter_policy"] = nwo.prefab_imposter_policy
                        if nwo.prefab_imposter_policy != "_connected_poop_instance_imposter_policy_never":
                            if nwo.prefab_imposter_brightness > 0:
                                props["bungie_mesh_poop_imposter_brightness"] = nwo.prefab_imposter_brightness
                            if not nwo.prefab_imposter_transition_distance_auto:
                                props["bungie_mesh_poop_imposter_transition_distance"] = nwo.prefab_imposter_transition_distance_auto
                                
                    if nwo.prefab_streaming_priority != "no_override":
                        props["bungie_mesh_poop_streamingpriority"] = nwo.prefab_streaming_priority
                    
                    if nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_only':
                        props["bungie_mesh_poop_cinema_only"] = 1
                    elif nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_exclude':
                        props["bungie_mesh_poop_exclude_from_cinema"] = 1
                        
                    if nwo.prefab_render_only:
                        props["bungie_mesh_poop_is_render_only"] = 1
                    if nwo.prefab_does_not_block_aoe:
                        props["bungie_mesh_poop_does_not_block_aoe"] = 1
                    if nwo.prefab_excluded_from_lightprobe:
                        props["bungie_mesh_poop_excluded_from_lightprobe"] = 1
                    if nwo.prefab_decal_spacing:
                        props["bungie_mesh_poop_decal_spacing"] = 1
                    if nwo.prefab_remove_from_shadow_geometry:
                        props["bungie_mesh_poop_remove_from_shadow_geometry"] = 1
                    if nwo.prefab_disallow_lighting_samples:
                        props["bungie_mesh_poop_disallow_object_lighting_samples"] = 1       
                        
                elif (
                    self.corinth
                    and tag_name.endswith(
                        ".cheap_light"
                    )
                ):
                    props["bungie_marker_type"] = "_connected_geometry_marker_type_cheap_light"
                elif (
                    self.corinth
                    and tag_name.endswith(".light")
                ):
                    props["bungie_marker_type"] = "_connected_geometry_marker_type_light"
                elif (
                    self.corinth
                    and tag_name.endswith(".leaf")
                ):
                    props["bungie_marker_type"] = "_connected_geometry_marker_type_falling_leaf"
                else:
                    props["bungie_marker_game_instance_variant_name"] = nwo.marker_game_instance_tag_variant_name
                    if self.corinth:
                        props["bungie_marker_always_run_scripts"] = int(nwo.marker_always_run_scripts)
            
            elif marker_type == "_connected_geometry_marker_type_envfx":
                props["bungie_marker_looping_effect"] = nwo.marker_looping_effect
                
            elif marker_type == "_connected_geometry_marker_type_lightCone":
                props["bungie_marker_light_tag"] = nwo.marker_light_cone_tag
                props["bungie_marker_light_color"] = utils.color_3p(nwo.marker_light_cone_color)
                props["bungie_marker_light_cone_width"] = nwo.marker_light_cone_alpha
                props["bungie_marker_light_cone_length"] = nwo.marker_light_cone_width
                props["bungie_marker_light_color_alpha"] = nwo.marker_light_cone_length
                props["bungie_marker_light_cone_intensity"] = nwo.marker_light_cone_intensity
                props["bungie_marker_light_cone_curve"] = nwo.marker_light_cone_curve
                
        return props
    
    def _setup_mesh_level_props(self, ob: bpy.types.Object, region: str, mesh_props: dict):
        data_nwo: NWO_MeshPropertiesGroup = ob.data.nwo
        face_props = data_nwo.face_props
        fp_defaults = face_prop_defaults.copy()
        if self.asset_type.supports_global_materials:
            global_material = ob.data.nwo.face_global_material.strip().replace(' ', "_")
            if global_material:
                if self.corinth and mesh_props.get("bungie_mesh_type") in {MeshType.poop.value, MeshType.poop_collision.value}:
                    mesh_props["bungie_mesh_global_material"] = global_material
                    mesh_props["bungie_mesh_poop_collision_override_global_material"] = 1
                self.global_materials.add(global_material)
                if test_face_prop(face_props, "face_global_material_override"):
                    fp_defaults["bungie_face_global_material"] = global_material
                else:
                    mesh_props["bungie_face_global_material"] = global_material
        
        if self.asset_type.supports_regions:
            if test_face_prop(face_props, "region_name_override"):
                fp_defaults["bungie_face_region"] = region
            else:
                mesh_props["bungie_face_region"] = region
            
        for idx, face_prop in enumerate(data_nwo.face_props):
            if face_prop.region_name_override:
                region = face_prop.region_name
                if region not in self.regions:
                    self.warnings.append(f"Object [{ob.name}] has {self.reg_name} [{region}] on face property index {idx} which is not present in the {self.reg_name}s table. Setting {self.reg_name} to: {self.default_region}")
            if self.asset_type.supports_global_materials and face_prop.face_global_material_override:
                mat = face_prop.face_global_material.strip().replace(' ', "_")
                if mat:
                    self.global_materials.add(mat)
        
        two_sided, transparent = data_nwo.face_two_sided, data_nwo.face_transparent
        
        if two_sided or transparent:
            face_two_sided = test_face_prop(face_props, "face_two_sided_override")
            face_transparent = test_face_prop(face_props, "face_transparent_override")
            if face_two_sided or face_transparent:
                if two_sided and transparent:
                    if self.corinth:
                        match data_nwo.face_two_sided_type:
                            case 'mirror':
                                fp_defaults["bungie_face_sides"] = FaceSides.mirror_transparent.value
                            case 'keep':
                                fp_defaults["bungie_face_sides"] = FaceSides.keep_transparent.value
                            case _:
                                fp_defaults["bungie_face_sides"] = FaceSides.two_sided_transparent.value
                    else:
                        fp_defaults["bungie_face_sides"] = FaceSides.two_sided_transparent.value
                    
                elif two_sided:
                    if self.corinth:
                        match data_nwo.face_two_sided_type:
                            case 'mirror':
                                fp_defaults["bungie_face_sides"] = FaceSides.mirror.value
                            case 'keep':
                                fp_defaults["bungie_face_sides"] = FaceSides.keep.value
                            case _:
                                fp_defaults["bungie_face_sides"] = FaceSides.two_sided.value
                    else:
                        fp_defaults["bungie_face_sides"] = FaceSides.two_sided.value
                        
                else:
                    fp_defaults["bungie_face_sides"] = FaceSides.one_sided_transparent.value
                        
            else:
                face_sides_value = "_connected_geometry_face_sides_"
                if data_nwo.face_two_sided:
                    if not self.corinth:
                        face_sides_value += "two_sided"
                    else:
                        face_sides_value += data_nwo.face_two_sided_type
                        
                    if transparent:
                        face_sides_value += "_transparent"
                    mesh_props["bungie_face_sides"] = face_sides_value
                    
                elif transparent:
                    face_sides_value += "one_sided_transparent"
                    mesh_props["bungie_face_sides"] = face_sides_value
                    
        
        if data_nwo.render_only:
            if test_face_prop(face_props, "render_only_override"):
                fp_defaults["bungie_face_mode"] = FaceMode.render_only.value
            else:
                mesh_props["bungie_face_mode"] = FaceMode.render_only.value
        elif data_nwo.collision_only:
            if test_face_prop(face_props, "collision_only_override"):
                fp_defaults["bungie_face_mode"] = FaceMode.collision_only.value
            else:
                mesh_props["bungie_face_mode"] = FaceMode.collision_only.value
        elif data_nwo.sphere_collision_only:
            if test_face_prop(face_props, "sphere_collision_only_override"):
                fp_defaults["bungie_face_mode"] = FaceMode.sphere_collision_only.value
            else:
                mesh_props["bungie_face_mode"] = FaceMode.sphere_collision_only.value
        elif data_nwo.breakable:
            if test_face_prop(face_props, "breakable_override"):
                fp_defaults["bungie_face_mode"] = FaceMode.breakable.value
            else:
                mesh_props["bungie_face_mode"] = FaceMode.breakable.value
                
        if data_nwo.face_draw_distance != "_connected_geometry_face_draw_distance_normal":
            if test_face_prop(face_props, "face_draw_distance_override"):
                match data_nwo.face_draw_distance:
                    case '_connected_geometry_face_draw_distance_detail_mid':
                        fp_defaults["bungie_face_draw_distance"] = FaceDrawDistance.detail_mid.value
                    case '_connected_geometry_face_draw_distance_detail_close':
                        fp_defaults["bungie_face_draw_distance"] = FaceDrawDistance.detail_close.value
            else:
                mesh_props["bungie_face_draw_distance"] = data_nwo.face_draw_distance
            
        if data_nwo.ladder:
            if test_face_prop(face_props, "ladder_override"):
                fp_defaults["bungie_ladder"] = 1
            else:
                mesh_props["bungie_ladder"] = 1
        if data_nwo.slip_surface:
            if test_face_prop(face_props, "slip_surface_override"):
                fp_defaults["bungie_slip_surface"] = 1
            else:
                mesh_props["bungie_slip_surface"] = 1
        if data_nwo.decal_offset:
            if test_face_prop(face_props, "decal_offset_override"):
                fp_defaults["bungie_decal_offset"] = 1
            else:
                mesh_props["bungie_decal_offset"] = 1
        if data_nwo.no_shadow:
            if test_face_prop(face_props, "no_shadow_override"):
                fp_defaults["bungie_no_shadow"] = 1
            else:
                mesh_props["bungie_no_shadow"] = 1
        if data_nwo.no_pvs:
            if test_face_prop(face_props, "no_pvs_override"):
                fp_defaults["bungie_invisible_to_pvs"] = 1
            else:
                mesh_props["bungie_invisible_to_pvs"] = 1
        if data_nwo.no_lightmap:
            if test_face_prop(face_props, "no_lightmap_override"):
                fp_defaults["bungie_no_lightmap"] = 1
            else:
                mesh_props["bungie_no_lightmap"] = 1
        if data_nwo.precise_position:
            if test_face_prop(face_props, "precise_position_override"):
                fp_defaults["bungie_precise_position"] = 1
            else:
                mesh_props["bungie_precise_position"] = 1
        if data_nwo.mesh_tessellation_density != "_connected_geometry_mesh_tessellation_density_none":
            if test_face_prop(face_props, "mesh_tessellation_density_override"):
                match data_nwo.mesh_tessellation_density:
                    case '_connected_geometry_mesh_tessellation_density_4x':
                        fp_defaults["bungie_mesh_tessellation_density"] = MeshTessellationDensity._4x.value
                    case '_connected_geometry_mesh_tessellation_density_9x':
                        fp_defaults["bungie_mesh_tessellation_density"] = MeshTessellationDensity._9x.value
                    case '_connected_geometry_mesh_tessellation_density_36x':
                        fp_defaults["bungie_mesh_tessellation_density"] = MeshTessellationDensity._36x.value
            else:
                mesh_props["bungie_mesh_tessellation_density"] = data_nwo.mesh_tessellation_density
                
        if data_nwo.lightmap_additive_transparency_active:
            if test_face_prop(face_props, "lightmap_additive_transparency_override"):
                fp_defaults["bungie_lightmap_additive_transparency"] = utils.color_4p(data_nwo.lightmap_additive_transparency)
            else:
                mesh_props["bungie_lightmap_additive_transparency"] = utils.color_4p(data_nwo.lightmap_additive_transparency)
                
        if data_nwo.lightmap_resolution_scale_active:
            if test_face_prop(face_props, "lightmap_resolution_scale_override"):
                fp_defaults["bungie_lightmap_resolution_scale"] = data_nwo.lightmap_resolution_scale
            else:
                mesh_props["bungie_lightmap_resolution_scale"] = str(data_nwo.lightmap_resolution_scale)
                
        if data_nwo.lightmap_type_active:
            if test_face_prop(face_props, "lightmap_resolution_scale_override"):
                if data_nwo.lightmap_type == '_connected_geometry_lightmap_type_per_vertex':
                    fp_defaults["bungie_lightmap_type"] = LightmapType.per_vertex.value
                else:
                    fp_defaults["bungie_lightmap_type"] = LightmapType.per_pixel.value
            else:
                mesh_props["bungie_lightmap_type"] = data_nwo.lightmap_type
                
        if data_nwo.lightmap_translucency_tint_color_active:
            if test_face_prop(face_props, "lightmap_translucency_tint_color_override"):
                fp_defaults["bungie_lightmap_translucency_tint_color"] = utils.color_4p(data_nwo.lightmap_translucency_tint_color)
            else:
                mesh_props["bungie_lightmap_translucency_tint_color"] = utils.color_4p(data_nwo.lightmap_translucency_tint_color)
                
        if data_nwo.lightmap_lighting_from_both_sides_active:
            if test_face_prop(face_props, "lightmap_lighting_from_both_sides_override"):
                fp_defaults["bungie_lightmap_lighting_from_both_sides"] = 1
            else:
                mesh_props["bungie_lightmap_lighting_from_both_sides"] = 1
                
        if data_nwo.emissive_active:
            if test_face_prop(face_props, "emissive_override"):
                fp_defaults["bungie_lighting_emissive_power"] = data_nwo.material_lighting_emissive_power
                fp_defaults["bungie_lighting_emissive_color"] = utils.color_4p(data_nwo.material_lighting_emissive_color)
                fp_defaults["bungie_lighting_emissive_per_unit"] = int(data_nwo.material_lighting_emissive_per_unit)
                fp_defaults["bungie_lighting_emissive_quality"] = data_nwo.material_lighting_emissive_quality
                fp_defaults["bungie_lighting_use_shader_gel"] = int(data_nwo.material_lighting_use_shader_gel)
                fp_defaults["bungie_lighting_bounce_ratio"] = data_nwo.material_lighting_bounce_ratio
                fp_defaults["bungie_lighting_attenuation_enabled"] = int(data_nwo.material_lighting_attenuation_cutoff > 0)
                fp_defaults["bungie_lighting_attenuation_cutoff"] = data_nwo.material_lighting_attenuation_cutoff
                fp_defaults["bungie_lighting_attenuation_falloff"] = data_nwo.material_lighting_attenuation_falloff
                fp_defaults["bungie_lighting_emissive_focus"] = degrees(data_nwo.material_lighting_emissive_focus) / 180
            else:
                mesh_props["bungie_lighting_emissive_power"] = data_nwo.material_lighting_emissive_power
                mesh_props["bungie_lighting_emissive_color"] = utils.color_4p(data_nwo.material_lighting_emissive_color)
                mesh_props["bungie_lighting_emissive_per_unit"] = int(data_nwo.material_lighting_emissive_per_unit)
                mesh_props["bungie_lighting_emissive_quality"] = data_nwo.material_lighting_emissive_quality
                mesh_props["bungie_lighting_use_shader_gel"] = int(data_nwo.material_lighting_use_shader_gel)
                mesh_props["bungie_lighting_bounce_ratio"] = data_nwo.material_lighting_bounce_ratio
                mesh_props["bungie_lighting_attenuation_enabled"] = int(data_nwo.material_lighting_attenuation_cutoff > 0)
                mesh_props["bungie_lighting_attenuation_cutoff"] = data_nwo.material_lighting_attenuation_cutoff
                mesh_props["bungie_lighting_attenuation_falloff"] = data_nwo.material_lighting_attenuation_falloff
                mesh_props["bungie_lighting_emissive_focus"] = degrees(data_nwo.material_lighting_emissive_focus) / 180
                
        return fp_defaults, mesh_props
         
    def set_template_node_order(self):
        nodes = []
        if self.asset_type not in {AssetType.MODEL, AssetType.ANIMATION}:
            return
        if self.asset_type == AssetType.MODEL:
            if self.scene_settings.template_model_animation_graph and Path(self.tags_dir, utils.relative_path(self.scene_settings.template_model_animation_graph)).exists():
                with AnimationTag(path=self.scene_settings.template_model_animation_graph) as animation:
                    nodes = animation.get_nodes()
            elif self.scene_settings.template_render_model and Path(self.tags_dir, utils.relative_path(self.scene_settings.template_render_model)).exists():
                with RenderModelTag(path=self.scene_settings.template_render_model) as render_model:
                    nodes = render_model.get_nodes()
        else:
            if self.scene_settings.asset_animation_type == 'first_person':
                if self.scene_settings.fp_model_path and Path(self.tags_dir, utils.relative_path(self.scene_settings.fp_model_path)).exists():
                    with RenderModelTag(path=self.scene_settings.fp_model_path) as render_model:
                        nodes = render_model.get_nodes()
                if self.scene_settings.gun_model_path and Path(self.tags_dir, utils.relative_path(self.scene_settings.gun_model_path)).exists():
                    with RenderModelTag(path=self.scene_settings.gun_model_path) as render_model:
                        nodes.extend(render_model.get_nodes())
                        
            elif self.scene_settings.render_model_path and Path(self.tags_dir, utils.relative_path(self.scene_settings.render_model_path)).exists():
                with RenderModelTag(path=self.scene_settings.render_model_path) as render_model:
                    nodes = render_model.get_nodes()
                    
        if nodes:
            self.virtual_scene.template_node_order = {v: i for i, v in enumerate(nodes)}
                    
                    
    def create_virtual_tree(self):
        '''Creates a tree of object relations'''
        process = "--- Building Models"
        num_no_parents = len(self.no_parent_objects)
        # Only need to transform scene for armatures
        # if self.scene_settings.forward_direction != 'x' and self.armature_poses:
        #     utils.transform_scene(self.context, 1, utils.blender_halo_rotation_diff(self.scene_settings.forward_direction), self.scene_settings.forward_direction, 'x', skip_data=True)
        #     self.forward = 'x'
        
        if self.sky_lights:
            for ob in self.ob_halo_data.keys():
                if ob.type == 'MESH':
                    props = self.ob_halo_data[ob][0]
                    self.ob_halo_data[ob][0] = self._setup_skylights(props)
            
        with utils.Spinner():
            utils.update_job_count(process, "", 0, num_no_parents)
            for idx, ob in enumerate(self.no_parent_objects):
                self.virtual_scene.add_model(ob)
                utils.update_job_count(process, "", idx, num_no_parents)
            utils.update_job_count(process, "", num_no_parents, num_no_parents)

        if self.asset_type == AssetType.SCENARIO:
            self.virtual_scene.add_automatic_structure(self.default_permutation, self.inverse_scale)
            
    def sample_animations(self):
        if self.asset_type not in {AssetType.MODEL, AssetType.ANIMATION}:
            return
        valid_actions = [action for action in bpy.data.actions if action.use_frame_range]
        if not valid_actions:
            return
        process = "--- Sampling Animations"
        num_animations = len(valid_actions)
        for armature in self.armature_poses.keys():
            armature.pose_position = 'POSE'
        self.context.view_layer.update()
        self.has_animations = True
        if self.export_settings.export_animations == 'ALL':
            with utils.Spinner():
                utils.update_job_count(process, "", 0, num_animations)
                for idx, action in enumerate(valid_actions):
                    for ob in self.animated_objects.keys():
                        ob.animation_data.action = action
                    controls = self.create_event_objects(action)
                    self.virtual_scene.add_animation(action, controls=controls)
                    self.exported_actions.append(action)
                    utils.update_job_count(process, "", idx, num_animations)
                utils.update_job_count(process, "", num_animations, num_animations)
        else:
            active_only = self.export_settings.export_animations == 'ACTIVE'
            for action in valid_actions:
                if active_only and action == self.current_action:
                    for ob in self.animated_objects.keys():
                        ob.animation_data.action = action
                    print("--- Sampling Active Animation ", end="")
                    with utils.Spinner():
                        controls = self.create_event_objects(action)
                        self.virtual_scene.add_animation(action, controls=controls)
                    print(" ", end="")
                else:
                    self.virtual_scene.add_animation(action, sample=False)
                    
                self.exported_actions.append(action)
                
            
    def create_event_objects(self, action: bpy.types.Action):
        nwo = action.nwo
        nwo: NWO_ActionPropertiesGroup
        name = nwo.name_override.strip() if nwo.name_override.strip() else action.name
        event_ob_props = {}
        for event in nwo.animation_events:
            event: NWO_Animation_ListItems
            props = {}
            event_type = event.event_type
            if event_type.startswith('_connected_geometry_animation_event_type_ik') and event.ik_chain == 'none':
                self.warnings.append(f"Animation event [{event.name}] has no ik chain defined. Skipping")
                continue
            event_name = 'event_export_node_' + event_type[41:] + '_' + str(event.event_id)
            ob = bpy.data.objects.new(event_name, None)
            event_ob_props[ob] = props
            props["bungie_object_type"] = ObjectType.animation_event.value
            props["bungie_animation_event_id"] = abs(event.event_id)
            props["bungie_animation_event_type"] = event_type
            props["bungie_animation_event_start"] = 0
            props["bungie_animation_event_end"] = int(action.frame_end) - int(action.frame_start)
            
            match event_type:
                case '_connected_geometry_animation_event_type_frame':
                    props["bungie_animation_event_frame_frame"] = event.frame_frame
                    props["bungie_animation_event_frame_name"] = event.frame_name
                    if event.multi_frame == "range" and event.frame_range > event.frame_frame:
                        for i in range(event.frame_range - event.frame_frame):
                            copy_ob = ob.copy()
                            copy_props = props.copy()
                            copy_id = abs(event.event_id) + i
                            copy_props["bungie_animation_event_id"] = copy_id
                            copy_props["bungie_animation_event_frame_frame"] = event.frame_frame + i
                            copy_props.name = f'event_export_node_frame_{str(copy_id)}'
                            event_ob_props[copy_ob] = copy_props
                            
                case '_connected_geometry_animation_event_type_wrinkle_map':
                    props["bungie_animation_event_wrinkle_map_face_region"] = event.wrinkle_map_face_region
                    props["bungie_animation_event_wrinkle_map_effect"] = event.wrinkle_map_effect
                    
                case '_connected_geometry_animation_event_type_ik_active' | '_connected_geometry_animation_event_type_ik_passive':
                    props["bungie_animation_event_ik_chain"] = event.ik_chain
                    target_marker = event.ik_target_marker.name if event.ik_target_marker else ''
                    props["bungie_animation_event_ik_target_marker"] = target_marker
                    props["bungie_animation_event_ik_target_usage"] = event.ik_target_usage
                    
                    proxy_target = bpy.data.objects.new(f'proxy_target_export_node_{event.ik_target_usage}_{target_marker}', None)
                    proxy_target.parent = self.virtual_scene.skeleton_object
                    proxy_target_props = {}
                    rnd = random.Random()
                    rnd.seed(proxy_target.name)
                    proxy_target_id = rnd.randint(0, 2147483647)
                    props["bungie_animation_event_ik_proxy_target_id"] = proxy_target_id
                    proxy_target_props["bungie_object_type"] = ObjectType.animation_control.value
                    proxy_target_props["bungie_animation_control_id"] = proxy_target_id
                    proxy_target_props["bungie_animation_control_type"] = '_connected_geometry_animation_control_type_target_proxy'
                    proxy_target_props["bungie_animation_control_proxy_target_usage"] = props["bungie_animation_event_ik_target_usage"]
                    proxy_target_props["bungie_animation_control_proxy_target_marker"] = props["bungie_animation_event_ik_target_marker"]
                    if event.ik_target_marker:
                        # if event.ik_target_marker.parent_type == "BONE" and event.ik_target_marker.parent_bone:
                        #     proxy_target.parent_type = 'BONE'
                        #     proxy_target.parent_bone = event.ik_target_marker.parent_bone
                            
                        proxy_target.matrix_world = event.ik_target_marker.matrix_world
                        
                    event_ob_props[proxy_target] = proxy_target_props
                    
                    effector = bpy.data.objects.new(f'ik_effector_export_node_{event.ik_chain}_{event.event_type[44:]}', None)
                    effector.parent = self.virtual_scene.skeleton_object
                    effector_props = {}
                    rnd = random.Random()
                    rnd.seed(effector.name)
                    effector_id = str(rnd.randint(0, 2147483647))
                    props["bungie_animation_event_ik_effector_id"] = effector_id
                    effector_props["bungie_object_type"] = ObjectType.animation_control.value
                    effector_props["bungie_animation_control_id"] = effector_id
                    effector_props["bungie_animation_control_type"] = '_connected_geometry_animation_control_type_ik_effector'
                    effector_props["bungie_animation_control_ik_chain"] = event.ik_chain
                    effector_props["bungie_animation_control_ik_effect"] = event.ik_influence
                    effector.parent_type = proxy_target.parent_type
                    effector.parent_bone = proxy_target.parent_bone
                    effector.matrix_world = proxy_target.matrix_world
                    
                    event_ob_props[effector] = effector_props
                    
                    rnd = random.Random()
                    rnd.seed(ob.name + '117')
                    props["bungie_animation_event_ik_pole_vector_id"] = rnd.randint(0, 2147483647)
        
        controls = []
        
        for ob, props in event_ob_props.items():
            self.temp_objects.add(ob)
            if ob.parent:
                bone_parent = self.virtual_scene.root_bone
                node = self.virtual_scene.add(ob, props, animation_owner=name)
                # if ob.parent_type == 'BONE':
                #     pbone = self.virtual_scene.skeleton_model.skeleton.pbones.get(ob.parent_bone)
                #     if pbone is not None:
                #         bone_parent = pbone
                        
                self.virtual_scene.skeleton_model.skeleton.append_animation_control(ob, node, self.virtual_scene)
                controls.append(AnimatedBone(ob, parent_override=bone_parent))
            else:
                self.virtual_scene.add_model_for_animation(ob, props, animation_owner=name)
                
        return controls
                    
            
    def report_warnings(self):
        if not (self.virtual_scene.warnings or self.warnings):
            return
        
        print("\n\nError Log")
        print("-----------------------------------------------------------------------")
        
        if self.warnings:
            print("\n--- Object Property Errors")
            for warning in self.warnings:
                utils.print_warning(warning)
                
        if self.virtual_scene.warnings:
            print("\n--- Geometry Errors")
            for warning in self.virtual_scene.warnings:
                utils.print_warning(warning)     
    
    def export_files(self):
        self._create_export_groups()
        self._export_models()
        self._export_animations()
                
    def _export_animations(self):
        if self.virtual_scene.skeleton_node and self.virtual_scene.animations:
            exported_something = False
            export = self.export_settings.export_animations != 'NONE'
            active_only = export and self.export_settings.export_animations == 'ACTIVE'
            if export:
                print("\n\nExporting Active Animation" if active_only else "\n\nExporting Animations")
                print("-----------------------------------------------------------------------\n")
            for animation in self.virtual_scene.animations:
                granny_path = self._get_export_path(animation.name, True)
                self.sidecar.add_animation_file_data(granny_path, bpy.data.filepath, animation.name, animation.compression, animation.animation_type, animation.movement, animation.space, animation.pose_overlay)
                if export and (not active_only or (self.current_action is not None and animation.action == self.current_action)):
                    job = f"--- {animation.name}"
                    utils.update_job(job, 0)
                    nodes = self.animation_groups.get(animation.name, [])
                    nodes_dict = {node.name: node for node in nodes + [self.virtual_scene.skeleton_node]}
                    self._export_granny_file(granny_path, nodes_dict, animation)
                    utils.update_job(job, 1)
                    exported_something = True
                
            if not exported_something:
                print("--- No animations to export")
    
    def _create_export_groups(self):
        self.animation_groups = defaultdict(list)
        self.model_groups = defaultdict(list)
        for node in self.virtual_scene.nodes.values():
            if node.for_animation:
                self.animation_groups[node.group].append(node)
            else:
                self.model_groups[node.group].append(node)
    
    def _export_models(self):
        if not self.model_groups: return
        exported_something = False
        print("\n\nExporting Geometry")
        print("-----------------------------------------------------------------------\n")
        for name, nodes in self.model_groups.items():
            granny_path = self._get_export_path(name)
            perm = nodes[0].permutation
            region = nodes[0].region
            tag_type = nodes[0].tag_type
            self.sidecar.add_file_data(tag_type, perm, region, granny_path, bpy.data.filepath)
            in_permutation_selection = self.asset_type not in {AssetType.MODEL, AssetType.SCENARIO, AssetType.SKY, AssetType.PREFAB} or not self.limit_perms_to_selection or perm in self.selected_permutations or tag_type in {'markers', 'skeleton'}
            in_bsp_selection = self.asset_type != AssetType.SCENARIO or not self.limit_bsps_to_selection or region in self.selected_bsps
            if in_permutation_selection and in_bsp_selection and tag_type in self.export_tag_types:
                job = f"--- {name}"
                utils.update_job(job, 0)
                if self.virtual_scene.skeleton_node:
                    nodes_dict = {node.name: node for node in nodes + [self.virtual_scene.skeleton_node]}
                else:
                    nodes_dict = {node.name: node for node in nodes}
                self._export_granny_file(granny_path, nodes_dict)
                utils.update_job(job, 1)
                exported_something = True
        
        if not exported_something:
            print("--- No geometry to export")
        
    def _export_granny_file(self, filepath: Path, virtual_objects: list[VirtualNode], animation: VirtualAnimation = None):
        self.granny.new(filepath, self.forward, self.scale, self.mirror)
        self.granny.from_tree(self.virtual_scene, virtual_objects)
        
        animation_export = animation is not None
        
        if not animation_export:
            if self.granny_textures:
                self.granny.write_textures()
            self.granny.write_materials()
            self.granny.write_vertex_data()
            self.granny.write_tri_topologies()
            self.granny.write_meshes()
            
        self.granny.write_skeletons(export_info=self.export_info)
        self.granny.write_models()
        
        if animation_export:
            self.granny.write_track_groups(animation.granny_track_group)
            self.granny.write_animations(animation.granny_animation)
            
        self.granny.transform()
        self.granny.save()
        
        if self.granny_open and not animation_export and filepath.exists():
            os.startfile(Path(self.project_root, "gr2_viewer.exe"), arguments=str(filepath))
            
    def _get_export_path(self, name: str, animation=False):
        """Gets the path to save a particular file to"""
        if animation:
            return Path(self.animations_export_dir, f"{name}.gr2")
        else:
            return Path(self.models_export_dir, f"{self.asset_name}_{name}.gr2")
        
    def write_sidecar(self):
        self.sidecar.has_armature = bool(self.virtual_scene.skeleton_node)
        self.sidecar.regions = self.regions
        self.sidecar.global_materials = self.global_materials_list
        self.sidecar.structure = self.virtual_scene.structure
        self.sidecar.design = self.virtual_scene.design
        self.sidecar.build()
        
    def restore_scene(self):
        for ob in self.temp_objects:
            bpy.data.objects.remove(ob)
        
        for armature, pose in self.armature_poses.items():
            armature.pose_position = pose
            
        for collection in self.disabled_collections:
            collection.exclude = False
            
        for ob, action in self.animated_objects.items():
            ob.animation_data.action = action
            
        self.context.scene.frame_set(self.current_frame)
            
        self.context.view_layer.update()
        
    def preprocess_tags(self):
        """ManagedBlam tasks to run before tool import is called"""
        node_usage_set = self.has_animations and self.any_node_usage_override()
        # print("\n--- Foundry Tags Pre-Process\n")
        if node_usage_set or self.scene_settings.ik_chains or self.has_animations:
            with AnimationTag() as animation:
                if self.scene_settings.parent_animation_graph:
                    self.print_pre("--- Setting parent animation graph")
                    animation.set_parent_graph(self.scene_settings.parent_animation_graph)
                    # print("--- Set Parent Animation Graph")
                if self.virtual_scene.animations:
                    self.print_pre(f"--- Validating animation compression for {len(self.exported_actions)} animations: Default Compression = {self.scene_settings.default_animation_compression}")
                    animation.validate_compression(self.exported_actions, self.scene_settings.default_animation_compression)
                    # print("--- Validated Animation Compression")
                if node_usage_set:
                    self.print_pre("--- Setting node usages")
                    animation.set_node_usages(self.virtual_scene.animated_bones, True)
                    #print("--- Updated Animation Node Usages")
                if self.scene_settings.ik_chains:
                    self.print_pre("--- Writing IK chains")
                    animation.write_ik_chains(self.scene_settings.ik_chains, self.virtual_scene.animated_bones, True)
                    # print("--- Updated Animation IK Chains")
                    
                if animation.tag_has_changes and (node_usage_set or self.scene_settings.ik_chains):
                    # Graph should be data driven if ik chains or overlay groups in use.
                    # Node usages are a sign the user intends to create overlays group
                    animation.tag.SelectField("Struct:definitions[0]/ByteFlags:private flags").SetBit('uses data driven animation', True)

        if self.asset_type == AssetType.SCENARIO:
            scenario_path = Path(self.tags_dir, utils.relative_path(self.asset_path), f"{self.asset_name}.scenario")
            if not scenario_path.exists():
                self.setup_scenario = True
                    
        if self.setup_scenario:
            with ScenarioTag() as scenario:
                self.print_pre(f"--- Setting up new scenario: Creating default starting profile & setting scenario type to {self.scene_settings.scenario_type}")
                scenario.create_default_profile()
                if self.scene_settings.scenario_type != 'solo':
                    scenario.tag.SelectField('type').SetValue(self.scene_settings.scenario_type)
                
        if self.asset_type == AssetType.PARTICLE_MODEL and self.scene_settings.particle_uses_custom_points:
            self.print_pre("--- Adding particle emitter custom points")
            emitter_path = Path(self.asset_path, self.asset_name).with_suffix(".particle_emitter_custom_points")
            if not emitter_path.exists():
                with Tag(path=str(emitter_path)) as _: pass

    def any_node_usage_override(self):
        if not self.corinth and self.asset_type == AssetType.ANIMATION and self.scene_settings.asset_animation_type == 'first_person':
            return False # Don't want to set node usages for reach fp animations, it breaks them
        return (self.scene_settings.node_usage_physics_control
                or self.scene_settings.node_usage_camera_control
                or self.scene_settings.node_usage_origin_marker
                or self.scene_settings.node_usage_left_clavicle
                or self.scene_settings.node_usage_left_upperarm
                or self.scene_settings.node_usage_pose_blend_pitch
                or self.scene_settings.node_usage_pose_blend_yaw
                or self.scene_settings.node_usage_pedestal
                or self.scene_settings.node_usage_pelvis
                or self.scene_settings.node_usage_left_foot
                or self.scene_settings.node_usage_right_foot
                or self.scene_settings.node_usage_damage_root_gut
                or self.scene_settings.node_usage_damage_root_chest
                or self.scene_settings.node_usage_damage_root_head
                or self.scene_settings.node_usage_damage_root_left_shoulder
                or self.scene_settings.node_usage_damage_root_left_arm
                or self.scene_settings.node_usage_damage_root_left_leg
                or self.scene_settings.node_usage_damage_root_left_foot
                or self.scene_settings.node_usage_damage_root_right_shoulder
                or self.scene_settings.node_usage_damage_root_right_arm
                or self.scene_settings.node_usage_damage_root_right_leg
                or self.scene_settings.node_usage_damage_root_right_foot
                or self.scene_settings.node_usage_left_hand
                or self.scene_settings.node_usage_right_hand
                or self.scene_settings.node_usage_weapon_ik
                )
    
    def invoke_tool_import(self):
        if self.virtual_scene is None:
            structure = [region.name for region in self.context.scene.nwo.regions_table]
        else:
            structure = self.virtual_scene.structure
        sidecar_importer = SidecarImport(self.asset_path, self.asset_name, self.asset_type, self.sidecar_path, self.scene_settings, self.export_settings, self.selected_bsps, self.corinth, structure, self.tags_dir)
        if self.asset_type in {AssetType.SCENARIO, AssetType.PREFAB}:
            sidecar_importer.save_lighting_infos()
        sidecar_importer.setup_templates()
        sidecar_importer.run()
        if sidecar_importer.lighting_infos:
            sidecar_importer.restore_lighting_infos()
        if self.asset_type == AssetType.ANIMATION:
            sidecar_importer.cull_unused_tags()
            
    def print_pre(self, txt):
        if not self.pre_title_printed:
            print("\n\nTags Pre-Process")
            print("-----------------------------------------------------------------------\n")
            self.pre_title_printed = True
            
        print(txt)
        
    def print_post(self, txt):
        if not self.post_title_printed:
            print("\n\nTags Post-Process")
            print("-----------------------------------------------------------------------\n")
            self.post_title_printed = True
            
        print(txt)
            
    def postprocess_tags(self):
        """ManagedBlam tasks to run after tool import is called"""
        self._setup_model_overrides()
        if self.sidecar.reach_world_animations or self.sidecar.pose_overlays:
            with AnimationTag() as animation:
                if self.sidecar.reach_world_animations:
                    self.print_post(f"--- Setting up {len(self.sidecar.reach_world_animations)} world relative animation{'s' if len(self.sidecar.reach_world_animations) > 1 else ''}")
                    animation.set_world_animations(self.sidecar.reach_world_animations)
                if self.sidecar.pose_overlays:
                    self.print_post(f"--- Updating animation blend screens for {len(self.sidecar.pose_overlays)} pose overlay animation{'s' if len(self.sidecar.pose_overlays) > 1 else ''}")
                    animation.setup_blend_screens(self.sidecar.pose_overlays)
            # print("--- Setup World Animations")
            
        if self.asset_type == AssetType.SCENARIO and self.setup_scenario:
            lm_value = 6 if self.corinth else 3
            with ScenarioTag() as scenario:
                for bsp in self.virtual_scene.structure:
                    res = scenario.set_bsp_lightmap_res(bsp, lm_value, 0)
                    self.print_post(f"--- Setting scenario lightmap resolution to {res}")
            
        if self.asset_type == AssetType.SCENARIO and self.scene_settings.zone_sets:
            self.print_post(f"--- Updating scenario zone sets: {[zs.name for zs in self.scene_settings.zone_sets]}")
            write_zone_sets_to_scenario(self.scene_settings, self.asset_name)

        if self.lights:
            self.print_post(f"--- Writing scenario lighting data from {len(self.lights)} light{'s' if len(self.lights) > 1 else ''}")
            export_lights(self.lights)
        
    def _setup_model_overrides(self):
        model_override = self.asset_type == AssetType.MODEL and any((
            self.scene_settings.template_render_model,
            self.scene_settings.template_collision_model,
            self.scene_settings.template_physics_model,
            self.scene_settings.template_model_animation_graph
            ))
        if model_override:
            with ModelTag() as model:
                self.print_post(f"--- Writing model tag paths to {model.tag_path.RelativePathWithExtension}")
                model.set_model_overrides(self.scene_settings.template_render_model,
                                          self.scene_settings.template_collision_model,
                                          self.scene_settings.template_model_animation_graph,
                                          self.scene_settings.template_physics_model)
                
    def lightmap(self):
        if self.export_settings.lightmap_structure and (self.asset_type == AssetType.SCENARIO or (self.corinth and self.is_model)):
            run_lightmapper(
                self.corinth,
                [],
                self.asset_name,
                self.export_settings.lightmap_quality,
                self.export_settings.lightmap_quality_h4,
                self.export_settings.lightmap_all_bsps,
                self.export_settings.lightmap_specific_bsp,
                self.export_settings.lightmap_region,
                self.is_model and self.corinth,
                self.export_settings.lightmap_threads,
                self.virtual_scene.structure)
    
    def get_marker_sphere_size(self, ob):
        scale = ob.matrix_world.to_scale()
        max_abs_scale = max(abs(scale.x), abs(scale.y), abs(scale.z))
        return ob.empty_display_size * max_abs_scale * (1 / self.scale)
    
    def _set_primitive_props(self, ob, prim_type, props):
        match prim_type:
            case '_connected_geometry_primitive_type_sphere':
                props["bungie_mesh_primitive_sphere_radius"] = utils.radius(ob, scale=1/self.scale)
            case '_connected_geometry_primitive_type_pill':
                props["bungie_mesh_primitive_pill_radius"] = utils.radius(ob, True, scale=1/self.scale)
                props["bungie_mesh_primitive_pill_height"] = ob.dimensions.z * (1 / self.scale)
            case '_connected_geometry_primitive_type_box':
                props["bungie_mesh_primitive_box_width"] =  ob.dimensions.x * (1 / self.scale)
                props["bungie_mesh_primitive_box_length"] = ob.dimensions.y * (1 / self.scale)
                props["bungie_mesh_primitive_box_height"] = ob.dimensions.z * (1 / self.scale)
                
        return props
    
    def _setup_skylights(self, props):
        if not self.sky_lights: return
        light_scale = 1
        sun_scale = 1
        sun = None
        lightGen_colors = []
        lightGen_directions = []
        lightGen_solid_angles = []
        for ob in self.sky_lights:
            if (ob.data.energy * light_scale) < 0.01:
                sun = ob
            down = Vector((0, 0, -1))
            down.rotate(ob.rotation_euler)
            lightGen_colors.append(utils.color_3p(ob.data.color))
            lightGen_directions.append(down.to_tuple())
            lightGen_solid_angles.append(ob.data.energy * light_scale)
        
        props['lightGen_colors'] = lightGen_colors
        props['lightGen_directions'] = lightGen_directions
        props['lightGen_solid_angles'] = lightGen_solid_angles
        props['lightGen_samples'] = len(self.sky_lights) - 1
        
        if sun is not None:
            if sun.data.color.v > 1:
                sun.data.color.v = 1
            props['sun_size'] = max(sun.scale.x, sun.scale.y, sun.scale.z) * sun_scale
            props['sun_intensity'] = sun.data.energy * 10000 * light_scale
            props['sun_color'] = utils.color_3p(sun.data.color)
            
        return props

def decorator_int(ob):
    match ob.nwo.decorator_lod:
        case "high":
            return 1
        case "medium":
            return 2
        case "low":
            return 3
        case _:
            return 4
        
class ExportCollection:
    def __init__(self, collection: bpy.types.Collection, depsgraph: bpy.types.Depsgraph):
        self.region, self.permutation = coll_region_perm(collection)
        for ob in collection.objects:
            eval_ob = ob.evaluated_get(depsgraph)
            eval_ob.nwo.export_collection = collection.name
        
def coll_region_perm(coll) -> tuple[str, str]:
    r, p = '', ''
    colltype = coll.nwo.type
    match colltype:
        case 'region':
            r = coll.nwo.region
        case 'permutation':
            p = coll.nwo.permutation
            
    return r, p

def create_parent_mapping(depsgraph: bpy.types.Depsgraph):
    collection_map: dict[bpy.types.Collection: ExportCollection] = {}
    for collection in bpy.data.collections:
        export_coll = ExportCollection(collection, depsgraph)
        collection_map[collection] = export_coll
        for child in collection.children_recursive:
            export_child = collection_map.get(child)
            if not export_child:
                export_child = ExportCollection(child, depsgraph)
                collection_map[collection] = export_child
                
            parent_region, parent_permutation = export_coll.region, export_coll.permutation
            if parent_region:
                export_child.region = parent_region
            if parent_permutation:
                export_child.permutation = parent_permutation
            
    return collection_map

def test_face_prop(face_props: NWO_MeshPropertiesGroup, attribute: str):
    for item in face_props:
        if getattr(item, attribute):
            return True
        
    return False
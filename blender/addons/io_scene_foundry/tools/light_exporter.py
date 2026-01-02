

from math import degrees
import math
from pathlib import Path
import time
import bpy

from ..managed_blam.model import ModelTag
from ..managed_blam.scenario_structure_lighting_info import ScenarioStructureLightingInfoTag
from ..constants import VALID_MESHES, WU_SCALAR
from .. import utils

def calc_attenuation(power: float, intensity_threshold=0.5, cutoff_intensity=0.1, spot_angle=None) -> tuple[float, float]:
    power = abs(power)
    falloff = math.sqrt(power / (4 * math.pi * intensity_threshold))
    cutoff = math.sqrt(power / (4 * math.pi * cutoff_intensity))
    return falloff, cutoff

class BlamLightInstance:
    def __init__(self, ob, bsp=None, scale=None, rotation=None) -> None:
        # self.data = ob.data
        data = ob.data
        self.data_name = ob.data.name
        self.bsp = bsp
        unit_factor = utils.get_unit_conversion_factor(bpy.context)
        matrix = utils.halo_transforms(ob, scale, rotation)
        self.origin = matrix.translation.to_tuple()
        matrix_3x3 = matrix.to_3x3().normalized()
        self.forward = matrix_3x3.col[0]
        self.up = matrix_3x3.col[2]
        ob_nwo = ob.nwo
        self.game_type = 0
        match ob_nwo.light_game_type:
            case '_connected_geometry_bungie_light_type_uber':
                self.game_type = 1
            case '_connected_geometry_bungie_light_type_inlined':
                self.game_type = 2
            case '_connected_geometry_bungie_light_type_screen_space':
                self.game_type = 3
            case '_connected_geometry_bungie_light_type_rerender':
                self.game_type = 4
        
        self.volume_distance = ob_nwo.light_volume_distance
        self.volume_intensity = ob_nwo.light_volume_intensity
        
        self.bounce_ratio = ob_nwo.light_bounce_ratio
        self.screen_space_specular = ob_nwo.light_screenspace_has_specular
        
        self.light_tag = ob_nwo.light_tag_override
        self.shader = ob_nwo.light_shader_reference
        self.gel = ob_nwo.light_gel_reference
        self.lens_flare = ob_nwo.light_lens_flare_reference
        
        self.light_mode = 0
        if ob_nwo.light_mode == '_connected_geometry_light_mode_static':
            self.light_mode = 1
        elif ob_nwo.light_mode == '_connected_geometry_light_mode_analytic':
            self.light_mode = 2
        
        # Fade
        self.fade_out_distance = ob_nwo.light_fade_end_distance * 100 * WU_SCALAR * unit_factor
        self.fade_start_distance = ob_nwo.light_fade_start_distance * 100 * WU_SCALAR * unit_factor
        
class BlamLightDefinition:
    def __init__(self, data):
        # export_scale = utils.get_export_scale(bpy.context)
        unit_factor = utils.get_unit_conversion_factor(bpy.context)
        if utils.is_corinth():
            atten_scalar = 1
        else:
            atten_scalar = 100
        nwo = data.nwo
        self.data_name = data.name
        self.id = utils.id_from_string(self.data_name)
        self.type = 0
        match data.type:
            case 'SPOT':
                self.type = 1
            case 'SUN':
                self.type = 2
                
        self.shape = 0
        if nwo.light_shape == '_connected_geometry_light_shape_circle':
            self.shape = 1
            
        self.is_sun = nwo.is_sun
            
        self.color = [utils.linear_to_srgb(data.color[0]), utils.linear_to_srgb(data.color[1]), utils.linear_to_srgb(data.color[2])]
        self.intensity = nwo.light_intensity
        self.hotspot_size = 0
        self.hotspot_cutoff = 0
        if data.type == 'SPOT':
            self.hotspot_cutoff = min(degrees(data.spot_size), 160)
            self.hotspot_size = self.hotspot_cutoff * (1 - data.spot_blend)
            
        self.hotspot_falloff = nwo.light_falloff_shape
        
        self.near_attenuation_start = data.shadow_soft_size * atten_scalar * WU_SCALAR * unit_factor
        self.near_attenuation_end = self.near_attenuation_start
        if nwo.light_far_attenuation_end:
            self.far_attenuation_start = nwo.light_far_attenuation_start * atten_scalar * WU_SCALAR * unit_factor
            self.far_attenuation_end = nwo.light_far_attenuation_end * atten_scalar * WU_SCALAR * unit_factor
        else:
            falloff, cutoff = calc_attenuation(data.energy * unit_factor ** 2, spot_angle=data.spot_size if data.type == 'SPOT' else None)
            self.far_attenuation_start = falloff * atten_scalar * WU_SCALAR
            self.far_attenuation_end = cutoff * atten_scalar * WU_SCALAR
            
        self.aspect = nwo.light_aspect
        
        self.cone_shape = 0 if nwo.light_cone_projection_shape == '_connected_geometry_cone_projection_shape_cone' else 1
        self.lighting_mode = 0 if nwo.light_physically_correct else 1
        
        # Dynamic only props
        self.shadow_near_clip = nwo.light_shadow_near_clipplane
        self.shadow_far_clip = nwo.light_shadow_far_clipplane
        self.shadow_bias = nwo.light_shadow_bias_offset
        self.shadow_quality = 0 if nwo.light_dynamic_shadow_quality == '_connected_geometry_dynamic_shadow_quality_normal' else 1
        self.shadows = 1 if nwo.light_shadows else 0
        self.screen_space = 1 if nwo.light_screenspace else 0
        self.ignore_dynamic_objects = 1 if nwo.light_ignore_dynamic_objects else 0
        self.cinema_objects_only = 1 if nwo.light_cinema_objects_only else 0
        self.cinema_only = 1 if nwo.light_cinema == '_connected_geometry_lighting_cinema_only' else 0
        self.cinema_exclude = 1 if nwo.light_cinema == '_connected_geometry_lighting_cinema_exclude' else 0
        self.specular_contribution = 1 if nwo.light_specular_contribution else 0
        self.diffuse_contribution = 1 if nwo.light_diffuse_contribution else 0
        
        # Static only props
        self.indirect_amp = nwo.light_amplification_factor
        self.jitter_sphere = nwo.light_jitter_sphere_radius
        self.jitter_angle = degrees(nwo.light_jitter_angle)
        self.jitter_quality = 0
        if nwo.light_jitter_quality == '_connected_geometry_light_jitter_quality_medium':
            self.jitter_quality = 1
        elif nwo.light_jitter_quality == '_connected_geometry_light_jitter_quality_high':
            self.jitter_quality = 2
            
        self.indirect_only = 1 if nwo.light_indirect_only else 0
        self.static_analytic = 1 if nwo.light_static_analytic else 0

class NWO_OT_ExportLights(bpy.types.Operator):
    bl_idname = "nwo.export_lights"
    bl_label = "Export Lights"
    bl_description = "Exports all blender lights (and lightmap regions if Reach) to their respective lighting info tags"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context)

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        if scene_nwo.is_child_asset:
            parent = scene_nwo.parent_asset
            if not parent.strip():
                self.report({'WARNING'}, "Parent asset not specified, cannot export lights")
                return {"CANCELLED"}
            parent_path = Path(parent)
            parent_sidecar = Path(utils.get_tags_path(), parent, f"{parent.name}.sidecar.xml")
            if parent_sidecar.exists():
                export_lights(parent_path, parent_path.name)
            else:
                self.report({'WARNING'}, "Parent asset invalid, cannot export lights")
                return {"CANCELLED"}
        else:
            asset_path, asset_name = utils.get_asset_info()
            export_lights(asset_path, asset_name)
        return {"FINISHED"}
    
def gather_lights(context, collection_map):
    print("--- Start light gather")
    start = time.perf_counter()
    
    collection_map = utils.create_parent_mapping(context)
    proxies = {}
    with utils.DepsgraphRead():
        depsgraph = context.evaluated_depsgraph_get()

        for inst in depsgraph.object_instances:
            obj = inst.object
            original = obj.original
            nwo = original.nwo
            parent = original
            
            if inst.is_instance:
                obj = inst.instance_object
                original = obj.original
                nwo = original.nwo
                parent = inst.parent
            
            if original.type != 'LIGHT' or original.data.type == 'AREA':
                continue
            
            if utils.ignore_for_export_fast(original, collection_map, parent):
                continue
            
            export_collection = parent.nwo.export_collection
            has_export_collection = bool(parent.nwo.export_collection)
            if has_export_collection:
                collection = collection_map[export_collection]
            
            proxy = utils.ExportObject()
            proxy.name = original.name
            proxy.data = original.data
            proxy.type = 'LIGHT'
            proxy.nwo = nwo
            proxy.matrix_world = inst.matrix_world.copy()
            if has_export_collection:
                proxies[proxy] = collection.region
            else:
                proxies[proxy] = nwo.region_name

    print(len(proxies), "lights found")
    print("--- Gathered lights in: {:.3f}s".format(time.perf_counter() - start))
        
    return proxies

def gather_lightmap_regions(context, collection_map):
    print("--- Start lightmap regions gather")
    start = time.perf_counter()
    
    collection_map = utils.create_parent_mapping(context)
    proxies = {}
    with utils.DepsgraphRead():
        depsgraph = context.evaluated_depsgraph_get()

        for inst in depsgraph.object_instances:
            obj = inst.object
            original = obj.original
            nwo = original.nwo
            parent = original
            
            if inst.is_instance:
                obj = inst.instance_object
                original = obj.original
                nwo = original.nwo
                parent = inst.parent
            
            if original.type not in VALID_MESHES or original.data.nwo.mesh_type != '_connected_geometry_mesh_type_lightmap_region':
                continue
            
            if utils.ignore_for_export_fast(original, collection_map, parent):
                continue
            
            export_collection = parent.nwo.export_collection
            has_export_collection = bool(parent.nwo.export_collection)
            if has_export_collection:
                collection = collection_map[export_collection]

            proxy = utils.ExportObject()
            proxy.name = original.name
            proxy.ob = original
            proxy.data = original.data
            proxy.type = original.type
            proxy.nwo = nwo
            proxy.matrix_world = inst.matrix_world.copy()
            if has_export_collection:
                proxies[proxy] = collection.region
            else:
                proxies[proxy] = nwo.region_name

    print(len(proxies), "lightmap regions found")
    print("--- Gathered lightmap regions in: {:.3f}s".format(time.perf_counter() - start))
        
    return proxies

def export_lights(asset_path, asset_name, light_objects = None, bsps = None, lightmap_regions=None):
    tags_dir = utils.get_tags_path()
    context = bpy.context
    corinth = utils.is_corinth(bpy.context)
    scene_nwo = utils.get_scene_props()
    asset_type = scene_nwo.asset_type
    if light_objects is None or lightmap_regions is None:
        collection_map = utils.create_parent_mapping(context)
    
    if light_objects is None:
        light_objects = gather_lights(context, collection_map)
                
    lights = [BlamLightInstance(ob, region) for ob, region in light_objects.items()]
    if asset_type == 'scenario':
        if bsps is None:
            bsps = [r.name for r in scene_nwo.regions_table if r.name.lower() != 'shared']
        lighting_info_paths = [str(Path(asset_path, f'{b}.scenario_structure_lighting_info')) for b in bsps]
        for idx, info_path in enumerate(lighting_info_paths):
            b = bsps[idx]
            lights_list = [light for light in lights if light.bsp == b]
            if not lights_list:
                if Path(tags_dir, utils.relative_path(info_path)).exists():
                    with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.clear_lights()
            else:
                light_instances = [light for light in lights_list]
                light_data = {bpy.data.lights.get(light.data_name) for light in lights_list}
                light_definitions = [BlamLightDefinition(data) for data in light_data]
                with ScenarioStructureLightingInfoTag(path=info_path) as tag:tag.build_tag(light_instances, light_definitions)
                
            if lightmap_regions is None:
                lightmap_regions = gather_lightmap_regions(context, collection_map)
            
            if not corinth:
                for idx, info_path in enumerate(lighting_info_paths):
                    b = bsps[idx]
                    lm_regions_list = {lm_region for lm_region, region in lightmap_regions.items() if region == b}
                    with ScenarioStructureLightingInfoTag(path=info_path) as tag:
                        tag.lightmap_regions_from_blender(lm_regions_list)

    elif corinth and asset_type in ('model', 'sky', 'prefab'):
        info_path = str(Path(asset_path, f'{asset_name}.scenario_structure_lighting_info'))
        if not lights:
            if Path(tags_dir, utils.relative_path(info_path)).exists():
                with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.clear_lights()
        else:
            light_instances = [light for light in lights]
            light_data = {bpy.data.lights.get(light.data_name) for light in lights}
            light_definitions = [BlamLightDefinition(data) for data in light_data]
            with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.build_tag(light_instances, light_definitions)
            if asset_type in ('model', 'sky'):
                with ModelTag(path=str(Path(asset_path, f'{asset_name}.model'))) as tag: tag.assign_lighting_info_tag(info_path)
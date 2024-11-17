

from math import degrees
import math
from pathlib import Path
import bpy
from ..managed_blam.model import ModelTag
from ..managed_blam.scenario_structure_lighting_info import ScenarioStructureLightingInfoTag
from ..constants import WU_SCALAR
from .. import utils

def calc_attenutation(power: float, intensity_threshold=0.5, cutoff_intensity=0.1) -> tuple[float, float]:
    falloff = math.sqrt(power / (4 * math.pi * intensity_threshold))
    cutoff = math.sqrt(power / (4 * math.pi * cutoff_intensity))
    return falloff, cutoff

class BlamLightInstance:
    def __init__(self, ob, bsp=None, scale=None, rotation=None) -> None:
        # self.data = ob.data
        data = ob.data
        nwo = data.nwo
        self.data_name = ob.data.name
        self.bsp = bsp
        matrix = utils.halo_transforms(ob, scale, rotation)
        self.origin = matrix.translation.to_tuple()
        matrix_3x3 = matrix.to_3x3().normalized()
        self.forward = matrix_3x3.col[1]
        self.up = matrix_3x3.col[2]
        
        self.game_type = 0
        match nwo.light_game_type:
            case '_connected_geometry_bungie_light_type_uber':
                self.game_type = 1
            case '_connected_geometry_bungie_light_type_inlined':
                self.game_type = 2
            case '_connected_geometry_bungie_light_type_screen_space':
                self.game_type = 3
            case '_connected_geometry_bungie_light_type_rerender':
                self.game_type = 4
        
        self.volume_distance = nwo.light_volume_distance
        self.volume_intensity = nwo.light_volume_intensity
        
        self.bounce_ratio = nwo.light_bounce_ratio
        self.screen_space_specular = nwo.light_screenspace_has_specular
        
        self.light_tag = nwo.light_tag_override
        self.shader = nwo.light_shader_reference
        self.gel = nwo.light_gel_reference
        self.lens_flare = nwo.light_lens_flare_reference
        
        self.light_mode = 0
        if nwo.light_mode == '_connected_geometry_light_mode_static':
            self.light_mode = 1
        elif nwo.light_mode == '_connected_geometry_light_mode_analytic':
            self.light_mode = 2
        
class BlamLightDefinition:
    def __init__(self, data):
        export_scale = utils.get_export_scale(bpy.context)
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
            
        self.color = [utils.linear_to_srgb(data.color[0]), utils.linear_to_srgb(data.color[1]), utils.linear_to_srgb(data.color[2])]
        self.intensity = max(utils.calc_light_intensity(data, export_scale ** 2), 0.0001)
        self.hotspot_size = 0
        self.hotspot_cutoff = 0
        if data.type == 'SPOT':
            self.hotspot_size = min(degrees(data.spot_size), 160)
            self.hotspot_cutoff = self.hotspot_size * abs(1 - data.spot_blend)
            
        self.hotspot_falloff = nwo.light_falloff_shape
        
        self.near_attenuation_start = nwo.light_near_attenuation_start * atten_scalar * WU_SCALAR * unit_factor
        self.near_attenuation_end = nwo.light_near_attenuation_end * atten_scalar * WU_SCALAR * unit_factor
        if nwo.light_far_attenuation_end:
            self.far_attenuation_start = nwo.light_far_attenuation_start * atten_scalar * WU_SCALAR * unit_factor
            self.far_attenuation_end = nwo.light_far_attenuation_end * atten_scalar * WU_SCALAR * unit_factor
        else:
            falloff, cutoff = calc_attenutation(data.energy * unit_factor ** 2)
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
          
# class NWO_OT_LightSync(bpy.types.Operator):
#     bl_idname = "nwo.light_sync"
#     bl_label = "Light Sync"
#     bl_description = "Updates lighting info tags from Blender in realtime"
#     bl_options = {'REGISTER'}
    
#     cancel_sync: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

#     @classmethod
#     def poll(cls, context):
#         return utils.valid_nwo_asset(context)
    
#     def execute(self, context):
#         if self.cancel_sync:
#             context.scene.nwo.light_sync_active = False
#             return {'CANCELLED'}
#         context.scene.nwo.light_sync_active = True
#         wm = context.window_manager
#         self.timer = wm.event_timer_add(context.scene.nwo.light_sync_rate, window=context.window)
#         wm.modal_handler_add(self)
#         return {'RUNNING_MODAL'}

#     def modal(self, context, event):
#         nwo = context.scene.nwo
#         if not nwo.light_sync_active:
#             return self.cancel(context)
#         if event.type == 'TIMER':
#             for area in context.screen.areas:
#                 if area.type in ('VIEW_3D', "PROPERTIES", "OUTLINER") and utils.mouse_in_object_editor_region(context, event.mouse_x, event.mouse_y):
#                     # blam(export_lights_tasks())
#                     return {'PASS_THROUGH'}
                
#         return {'PASS_THROUGH'}
    
#     def cancel(self, context):
#         wm = context.window_manager
#         wm.event_timer_remove(self.timer)

class NWO_OT_ExportLights(bpy.types.Operator):
    bl_idname = "nwo.export_lights"
    bl_label = "Export Lights"
    bl_description = "Exports all blender lights to their respective lighting info tags"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset(context)

    def execute(self, context):
        export_lights()
        return {"FINISHED"}
    
def gather_lights(context):
    return [ob for ob in context.scene.objects if ob.type == 'LIGHT' and ob.data.type != 'AREA' and ob.nwo.exportable]

def export_lights(light_objects = None, bsps = None):
    context = bpy.context
    asset_path, asset_name = utils.get_asset_info()
    asset_type = context.scene.nwo.asset_type
    if light_objects is None:
        light_objects = gather_lights(context)
    lights = [BlamLightInstance(ob, utils.true_region(ob.nwo)) for ob in light_objects]
    if asset_type == 'scenario':
        if bsps is None:
            bsps = [r.name for r in context.scene.nwo.regions_table if r.name.lower() != 'shared']
        lighting_info_paths = [str(Path(asset_path, f'{b}.scenario_structure_lighting_info')) for b in bsps]
        for idx, info_path in enumerate(lighting_info_paths):
            b = bsps[idx]
            lights_list = [light for light in lights if light.bsp == b]
            if not lights_list:
                if Path(utils.get_tags_path(), utils.relative_path(info_path)).exists():
                    with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.clear_lights()
            else:
                light_instances = [light for light in lights_list]
                light_data = {bpy.data.lights.get(light.data_name) for light in lights_list}
                light_definitions = [BlamLightDefinition(data) for data in light_data]
                with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.build_tag(light_instances, light_definitions)
    
    elif utils.is_corinth(context) and asset_type in ('model', 'sky', 'prefab'):
        info_path = str(Path(asset_path, f'{asset_name}.scenario_structure_lighting_info'))
        if not lights:
            with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.clear_lights()
        else:
            light_instances = [light for light in lights]
            light_data = {bpy.data.lights.get(light.data_name) for light in lights}
            light_definitions = [BlamLightDefinition(data) for data in light_data]
            with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.build_tag(light_instances, light_definitions)
            if asset_type in ('model', 'sky'):
                with ModelTag(path=str(Path(asset_path, f'{asset_name}.model'))) as tag: tag.assign_lighting_info_tag(info_path)
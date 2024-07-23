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

from math import degrees
from pathlib import Path
import bpy
from io_scene_foundry.managed_blam.model import ModelTag
from io_scene_foundry.managed_blam.scenario_structure_lighting_info import ScenarioStructureLightingInfoTag
from io_scene_foundry.utils.nwo_constants import WU_SCALAR
from io_scene_foundry.utils import nwo_utils

class BlamLightInstance:
    def __init__(self, ob, bsp=None, scale=None, rotation=None) -> None:
        # self.data = ob.data
        data = ob.data
        nwo = data.nwo
        self.data_name = ob.data.name
        self.bsp = bsp
        matrix = nwo_utils.halo_transforms(ob, scale, rotation)
        self.origin = [str(n) for n in matrix.translation]
        matrix_3x3 = matrix.to_3x3().normalized()
        self.forward = [str(n) for n in matrix_3x3.col[1]]
        self.up = [str(n) for n in matrix_3x3.col[2]]
        
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
        
        self.volume_distance = str(nwo.light_volume_distance)
        self.volume_intensity = str(nwo.light_volume_intensity)
        
        self.bounce_ratio = str(nwo.light_bounce_ratio)
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
        if nwo_utils.is_corinth():
            atten_scalar = 1
        else:
            atten_scalar = 100
        nwo = data.nwo
        self.data_name = data.name
        self.id = nwo_utils.id_from_string(self.data_name)
        self.type = 0
        match data.type:
            case 'SPOT':
                self.type = 1
            case 'SUN':
                self.type = 2
                
        self.shape = 0
        if nwo.light_shape == '_connected_geometry_light_shape_circle':
            self.shape = 1
            
        self.color = str(nwo_utils.linear_to_srgb(data.color[0])), str(nwo_utils.linear_to_srgb(data.color[1])), str(nwo_utils.linear_to_srgb(data.color[2]))
        self.intensity = max(nwo_utils.calc_light_intensity(data, nwo_utils.get_export_scale(bpy.context) ** 2), 0.0001)
        self.hotspot_size = "0"
        self.hotspot_cutoff = "0"
        if data.type == 'SPOT':
            self.hotspot_size = min(degrees(data.spot_size), 160)
            self.hotspot_cutoff = str(self.hotspot_size * abs(1 - data.spot_blend))
            
        self.hotspot_falloff = str(nwo.light_falloff_shape)
        
        self.near_attenuation_start = str(nwo.light_near_attenuation_start * atten_scalar * WU_SCALAR)
        self.near_attenuation_end = str(nwo.light_near_attenuation_end * atten_scalar * WU_SCALAR)
        if nwo.light_far_attenuation_end:
            self.far_attenuation_start = nwo.light_far_attenuation_start * atten_scalar * WU_SCALAR
            self.far_attenuation_end = nwo.light_far_attenuation_end * atten_scalar * WU_SCALAR
        else:
            self.far_attenuation_start = 9 * atten_scalar
            self.far_attenuation_end = 40 * atten_scalar
            
        self.aspect = str(nwo.light_aspect)
        
        self.cone_shape = 0 if nwo.light_cone_projection_shape == '_connected_geometry_cone_projection_shape_cone' else 1
        self.lighting_mode = 0 if nwo.light_physically_correct else 1
        
        # Dynamic only props
        self.shadow_near_clip = str(nwo.light_shadow_near_clipplane)
        self.shadow_far_clip = str(nwo.light_shadow_far_clipplane)
        self.shadow_bias = str(nwo.light_shadow_bias_offset)
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
        self.indirect_amp = str(nwo.light_amplification_factor)
        self.jitter_sphere = str(nwo.light_jitter_sphere_radius)
        self.jitter_angle = str(degrees(nwo.light_jitter_angle))
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
#         return nwo_utils.valid_nwo_asset(context)
    
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
#                 if area.type in ('VIEW_3D', "PROPERTIES", "OUTLINER") and nwo_utils.mouse_in_object_editor_region(context, event.mouse_x, event.mouse_y):
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
        return nwo_utils.valid_nwo_asset(context)

    def execute(self, context):
        export_lights()
        return {"FINISHED"}
    
def gather_lights(context):
    return [ob for ob in context.scene.objects if ob.type == 'LIGHT' and ob.data.type != 'AREA' and ob.nwo.exportable]

def export_lights():
    context = bpy.context
    asset_path, asset_name = nwo_utils.get_asset_info()
    asset_type = context.scene.nwo.asset_type
    light_objects = gather_lights(context)
    lights = [BlamLightInstance(ob, nwo_utils.true_region(ob.nwo)) for ob in light_objects]
    if asset_type == 'scenario':
        bsps = [r.name for r in context.scene.nwo.regions_table if r.name.lower() != 'shared']
        lighting_info_paths = [str(Path(asset_path, f'{asset_name}_{b}.scenario_structure_lighting_info')) for b in bsps]
        for idx, info_path in enumerate(lighting_info_paths):
            b = bsps[idx]
            lights_list = [light for light in lights if light.bsp == b]
            if not lights_list:
                if Path(nwo_utils.get_tags_path(), nwo_utils.relative_path(info_path)).exists():
                    with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.clear_lights()
            else:
                light_instances = [light for light in lights_list]
                light_data = {bpy.data.lights.get(light.data_name) for light in lights_list}
                light_definitions = [BlamLightDefinition(data) for data in light_data]
                with ScenarioStructureLightingInfoTag(path=info_path) as tag: tag.build_tag(light_instances, light_definitions)
    
    elif nwo_utils.is_corinth(context) and asset_type in ('model', 'sky', 'prefab'):
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
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

import uuid
import random
from math import degrees

from ..utils.nwo_utils import(
    CheckType,
    not_bungie_game,
    mesh_type,
    marker_type,
    object_type,
    color_3p_str,
    color_4p_str,
    bool_str,
    jstr,
    vector_str,
    radius_str,
    true_bsp,
    clean_tag_path,
    shader_exts,

)

# OBJECT LEVEL
class NWOObject:
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        # Set variables passed to this class
        self.ob = ob
        self.data = ob.data
        self.name = ob.name
        self.halo = ob.nwo
        self.sidecar_type = sidecar_type
        self.not_bungie_game = not_bungie_game()
        self.model_armature = model_armature
        self.world_frame = world_frame
        self.asset_name = asset_name
        self.bungie_object_type = self.object_type()
        if self.bungie_object_type not in ('_connected_geometry_object_type_animation_control', '_connected_geometry_object_type_animation_event'):
            self.bungie_object_ID = self.object_ID()
        # self.halo_export = '1'
        if self.bungie_object_type == '_connected_geometry_object_type_frame':
            self.bungie_object_animates = self.object_animates()

    def cleanup(self):
        del self.ob
        del self.data
        del self.name
        del self.halo
        del self.sidecar_type
        del self.not_bungie_game
        del self.model_armature
        del self.world_frame
        del self.asset_name

    def object_type(self):
            return self.halo.object_type
        
    def object_ID(self):
        # Generate a seeded GUID based off object name. This way objects can retain their IDs and as blender objects must be unique, a unique ID is guaranteed.
        rnd = random.Random()
        rnd.seed(self.name)
        obj_id = str(uuid.UUID(int=rnd.getrandbits(128)))

        return obj_id

    def object_animates(self):
        return bool_str(self.sidecar_type == 'MODEL')

    def frame_pca(self):
        return self.halo.is_pca and not_bungie_game() and self.frame()

    def frame(self):
        return object_type(self.ob, ('_connected_geometry_object_type_frame'))

    def marker(self):
        return object_type(self.ob, ('_connected_geometry_object_type_marker'))

    def mesh(self):
        return self.ob.type == 'MESH' and self.ob.nwo.object_type_all in '_connected_geometry_object_type_mesh'

    def light(self):
        return self.ob.type == 'LIGHT'

    def animation_camera(self):
        return self.ob.type == 'CAMERA'

    def animation_control(self):
        return False # temporary until a system for setting these is created

    def animation_event(self):
        return self.halo.is_animation_event 

# ANIMATION CONTROL
#####################
class NWOAnimationControl(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        self.bungie_animation_control_type = None
        self.bungie_animation_control_id = None
        self.bungie_animation_control_ik_chain = None
        self.bungie_animation_control_ik_effect = None
        self.bungie_animation_control_constraint_effect = None
        self.bungie_animation_control_proxy_target_marker = None
        self.bungie_animation_control_proxy_target_tag = None
        self.bungie_animation_control_proxy_target_usage = None

        self.cleanup()

# ANIMATION EVENT
#####################
class NWOAnimationEvent(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        self.bungie_animation_event_type = self.animation_event_type()
        self.bungie_animation_event_start = self.animation_event_start()
        self.bungie_animation_event_end = self.animation_event_end()
        self.bungie_animation_event_id = self.animation_event_id()
        self.bungie_animation_event_frame_frame = self.animation_event_frame_frame()
        self.bungie_animation_event_frame_name = self.animation_event_frame_name()
        if self.bungie_animation_event_type == '_connected_geometry_animation_event_type_wrinkle_map':
            self.bungie_animation_event_wrinkle_map_face_region = self.animation_event_wrinkle_map_face_region()
            self.bungie_animation_event_wrinkle_map_effect = self.animation_event_wrinkle_map_effect()
        elif self.bungie_animation_event_type == '_connected_geometry_animation_event_type_footstep':
            self.bungie_animation_event_footstep_type = self.animation_event_footstep_type()
            self.bungie_animation_event_footstep_effect = self.animation_event_footstep_effect()
        elif self.bungie_animation_event_type in ('_connected_geometry_animation_event_type_ik_active', '_connected_geometry_animation_event_type_ik_passive'):
            self.bungie_animation_event_ik_chain = self.animation_event_ik_chain()
            self.bungie_animation_event_ik_active_tag = self.animation_event_ik_active_tag()
            self.bungie_animation_event_ik_target_tag = self.animation_event_ik_target_tag()
            self.bungie_animation_event_ik_target_marker = self.animation_event_ik_target_marker()
            self.bungie_animation_event_ik_target_usage = self.animation_event_ik_target_usage()
            self.bungie_animation_event_ik_proxy_target_id = self.animation_event_ik_proxy_target_id()
            self.bungie_animation_event_ik_pole_vector_id = self.animation_event_ik_pole_vector_id()
            self.bungie_animation_event_ik_effector_id = self.animation_event_ik_effector_id()
        elif self.bungie_animation_event_type == '_connected_geometry_animation_event_type_cinematic_effect':   
            self.bungie_animation_event_cinematic_effect_tag = self.animation_event_cinematic_effect_tag()
            self.bungie_animation_event_cinematic_effect_effect = self.animation_event_cinematic_effect_effect()
            self.bungie_animation_event_cinematic_effect_marker = self.animation_event_cinematic_effect_marker()
        elif self.bungie_animation_event_type == '_connected_geometry_animation_event_type_object_function':
            self.bungie_animation_event_object_function_name = self.animation_event_object_function_name()
            self.bungie_animation_event_object_function_effect = self.animation_event_object_function_effect()
        elif self.bungie_animation_event_type == '_connected_geometry_animation_event_type_frame':
            self.bungie_animation_event_frame_trigger = self.animation_event_frame_trigger()
        elif self.bungie_animation_event_type == '_connected_geometry_animation_event_type_import':
            self.bungie_animation_event_import_frame = self.animation_event_import_frame()
            self.bungie_animation_event_import_name = self.animation_event_import_name()
        elif self.bungie_animation_event_type == '_connected_geometry_animation_event_type_text':
            self.bungie_animation_event_text = self.animation_event_text()

        self.cleanup()

    def animation_event_type(self):
        return self.halo.event_type

    def animation_event_start(self):
        return jstr(self.halo.frame_start)
    
    def animation_event_end(self):
        return jstr(self.halo.frame_end)
    
    def animation_event_id(self):
        return str(self.halo.event_id)
    
    def animation_event_frame_frame(self):
        return str(self.halo.frame_frame)
    
    def animation_event_frame_name(self):
        return self.halo.frame_name

    def animation_event_wrinkle_map_face_region(self):
        return self.halo.wrinkle_map_face_region
    
    def animation_event_wrinkle_map_effect(self):
        return str(self.halo.wrinkle_map_effect)

    def animation_event_footstep_type(self):
        return self.halo.footstep_type
    
    def animation_event_footstep_effect(self):
        return str(self.halo.footstep_effect)
    
    def animation_event_ik_chain(self):
        return self.halo.ik_chain
    
    def animation_event_ik_active_tag(self):
        return self.halo.ik_active_tag
    
    def animation_event_ik_target_tag(self):
        return self.halo.ik_target_tag
    
    def animation_event_ik_target_marker(self):
        return self.halo.ik_target_marker
    
    def animation_event_ik_target_usage(self):
        return self.halo.ik_target_usage
    
    def animation_event_ik_proxy_target_id(self):
        return str(self.halo.ik_proxy_target_id)
    
    def animation_event_ik_pole_vector_id(self):
        return str(self.halo.ik_pole_vector_id)
    
    def animation_event_ik_effector_id(self):
        return str(self.halo.ik_effector_id)
    
    def animation_event_cinematic_effect_tag(self):
        return self.halo.cinematic_effect_tag

    def animation_event_cinematic_effect_effect(self):
        return str(self.halo.cinematic_effect_effect)

    def animation_event_cinematic_effect_marker(self):
        return self.halo.cinematic_effect_marker

    def animation_event_object_function_name(self):
        return self.halo.object_function_name

    def animation_event_object_function_effect(self):
        return str(self.halo.object_function_effect)

    def animation_event_frame_trigger(self):
        return bool_str(self.halo.frame_trigger)

    def animation_event_import_frame(self):
        return str(self.halo.import_frame)

    def animation_event_import_name(self):
        return self.halo.import_name

    def animation_event_text(self):
        return self.halo.text



# ANIMATION CAMERA
#####################

class NWOAnimationCamera(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)

        self.cleanup()

# LIGHT
#####################
class NWOLight(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        # SHARED
        self.bungie_light_type =  self.light_type()
        self.bungie_light_color = self.light_color()
        self.bungie_light_intensity = self.light_intensity()

        if self.not_bungie_game:
            # H4 ONLY
            self.bungie_light_mode = self.light_mode()
            self.bungie_lighting_mode = self.lighting_mode()
            self.bungie_light_near_attenuation_start = self.light_near_attenuation_start()
            self.bungie_light_near_attenuation_end = self.light_near_attenuation_end()
            self.bungie_light_fade_start_distance = self.light_fade_start_distance()
            self.bungie_light_fade_out_distance = self.light_fade_out_distance()
            self.bungie_light_far_attenuation_start = self.light_far_attenuation_start()
            self.bungie_light_far_attenuation_end = self.light_far_attenuation_end()
            # self.bungie_light_is_uber_light = self.is_uber_light()
            # self.bungie_light_indirect_only = self.light_indirect_only()
            # self.bungie_light_attenuation_near_radius = self.light_attenuation_near_radius()
            # self.bungie_light_attenuation_far_radius = self.light_attenuation_far_radius()
            # self.bungie_light_attenuation_power = self.light_attenuation_power()
            self.bungie_inner_cone_angle = self.inner_cone_angle()
            self.bungie_outer_cone_angle = self.outer_cone_angle()
            self.bungie_cone_projection_shape = self.cone_projection_shape()
            self.bungie_screenspace_light = self.screenspace_light()
            self.bungie_shadow_near_clipplane = self.shadow_near_clipplane()
            self.bungie_shadow_far_clipplane = self.shadow_far_clipplane()
            self.bungie_shadow_bias_offset = self.shadow_bias_offset()
            self.bungie_shadow_color = self.shadow_color()
            self.bungie_dynamic_shadow_quality = self.dynamic_shadow_quality()
            self.bungie_shadows = self.shadows()
            self.bungie_ignore_dynamic_objects = self.ignore_dynamic_objects()
            self.bungie_cinema_objects_only = self.cinema_objects_only()
            self.bungie_cinema_only = self.cinema_only()
            self.bungie_cinema_exclude = self.cinema_exclude()
            self.bungie_specular_contribution = self.specular_contribution()
            self.bungie_diffuse_contribution = self.diffuse_contribution()
            self.bungie_destroy_light_after = self.destroy_light_after()
            self.bungie_specular_power = self.specular_power()
            self.bungie_specular_intensity = self.specular_intensity()
            self.bungie_indirect_amplification_factor = self.indirect_amplification_factor()
            self.bungie_light_jitter_quality = self.light_jitter_quality()
            self.bungie_light_jitter_sphere_radius = self.light_jitter_sphere_radius()
            self.bungie_light_jitter_angle = self.light_jitter_angle()
            self.bungie_is_sun = self.is_sun()
            self.bungie_is_indirect_only = self.is_indirect_only()
            self.bungie_is_static_analytic = self.is_static_analytic()
                # self.bungie_light_indirect_amplification_factor = self.light_indirect_amplification_factor()
            
            # self.bungie_light_tag_name = self.light_tag_name()
        else:
            # REACH ONLY
            self.bungie_light_type_version = '1'
            self.bungie_light_game_type = self.light_game_type()
            self.bungie_light_shape = self.light_shape()
            self.bungie_light_near_attenuation_start = self.light_near_attenuation_start()
            self.bungie_light_near_attenuation_end = self.light_near_attenuation_end()
            self.bungie_light_fade_start_distance = self.light_fade_start_distance()
            self.bungie_light_fade_out_distance = self.light_fade_out_distance()
            self.bungie_light_far_attenuation_start = self.light_far_attenuation_start()
            self.bungie_light_far_attenuation_end = self.light_far_attenuation_end()
            # self.bungie_light_use_near_attenuation = "1" # self.light_use_near_attenuation()
            # self.bungie_light_use_far_attenuation = "1" #self.light_use_far_attenuation()
            self.bungie_light_ignore_bsp_visibility = self.light_ignore_bsp_visibility()
            # self.bungie_light_clipping_size_x_pos = None # not setting these currently
            # self.bungie_light_clipping_size_y_pos = None
            # self.bungie_light_clipping_size_z_pos = None
            # self.bungie_light_clipping_size_x_neg = None
            # self.bungie_light_clipping_size_y_neg = None
            # self.bungie_light_clipping_size_z_neg = None
            # self.bungie_light_use_clipping = None
            self.bungie_light_hotspot_size = self.light_hotspot_size()
            self.bungie_light_hotspot_falloff = self.light_hotspot_falloff()
            self.bungie_light_aspect = self.light_aspect()
            self.bungie_light_falloff_shape = self.light_falloff_shape()
            self.bungie_light_frustum_width = self.light_frustum_width()
            self.bungie_light_frustum_height = self.light_frustum_height()
            self.bungie_light_bounce_light_ratio = self.light_bounce_light_ratio()
            self.bungie_light_dynamic_light_has_bounce = self.light_dynamic_light_has_bounce()
            # self.bungie_light_screenspace_light_has_specular = self.light_screenspace_light_has_specular()
            self.bungie_light_light_tag_override = self.light_light_tag_override()
            self.bungie_light_shader_reference = self.light_shader_reference()
            self.bungie_light_gel_reference = self.light_gel_reference()
            self.bungie_light_lens_flare_reference = self.light_lens_flare_reference()
            self.bungie_light_volume_distance = self.light_volume_distance()
            self.bungie_light_volume_intensity_scalar = self.light_volume_intensity_scala()

        self.cleanup()

# --------------------------------

    def light_type(self):
        if self.not_bungie_game:
            light_type = self.data.type
            if light_type == 'SUN':
                return '_connected_geometry_light_type_directional'
            elif light_type == 'POINT':
                return '_connected_geometry_light_type_point'
            else:
                return '_connected_geometry_light_type_spot'
        else:
            return self.data.nwo.light_type_override
            
    def is_uber_light(self):
        return bool_str(self.data.nwo.light_sub_type == '_connected_geometry_lighting_sub_type_uber')

    def light_fade_start_distance(self):
        return jstr(self.data.nwo.light_fade_start_distance)

    def light_fade_out_distance(self):
        return jstr(self.data.nwo.light_fade_end_distance)

    def light_color(self):
        if self.not_bungie_game:
            return color_3p_str(self.ob.data.color)
        else:
            return color_4p_str(self.ob.data.color)

    def light_intensity(self):
        if self.not_bungie_game:
            return jstr((self.ob.data.energy / 0.03048 ** -2) / 10 if self.ob.data.type != 'SUN' else self.ob.data.energy)
        else:
            return jstr(self.data.nwo.light_intensity)

    def light_far_attenuation_start(self):
        if self.not_bungie_game:
            return jstr(self.data.nwo.light_far_attenuation_starth4)
        else:
            return jstr(self.data.nwo.light_far_attenuation_start)

    def light_far_attenuation_end(self):
        if self.not_bungie_game:
            return jstr(self.data.nwo.light_far_attenuation_endh4)
        else:
            return jstr(self.data.nwo.light_far_attenuation_end)

    def light_near_attenuation_start(self):
        if self.not_bungie_game:
            return jstr(self.data.nwo.light_near_attenuation_starth4)
        else:
            return jstr(self.data.nwo.light_near_attenuation_start)

    def light_near_attenuation_end(self):
        if self.not_bungie_game:
            return jstr(self.data.nwo.light_near_attenuation_endh4)
        else:
            return jstr(self.data.nwo.light_near_attenuation_end)

    def light_mode(self):
        return self.data.nwo.light_mode

    def light_jitter_quality(self):
        return self.data.nwo.light_jitter_quality

    def light_jitter_sphere_radius(self):
        return jstr(self.data.nwo.light_jitter_sphere_radius)

    def light_jitter_angle(self):
        return jstr(self.data.nwo.light_jitter_angle)

    def light_indirect_only(self):
        return bool_str(self.data.nwo.light_indirect_only)

    def light_indirect_amplification_factor(self):
        return jstr(self.data.nwo.light_amplification_factor)

    def light_attenuation_near_radius(self):
        return jstr(self.data.nwo.light_attenuation_near_radius)

    def light_attenuation_far_radius(self):
        return jstr(self.data.nwo.light_attenuation_far_radius)

    def light_attenuation_power(self):
        return jstr(self.data.nwo.light_attenuation_power)

    def lighting_mode(self):
        return self.data.nwo.light_lighting_mode

    def specular_power(self):
        return jstr(self.data.nwo.light_specular_power)

    def specular_intensity(self):
        return jstr(self.data.nwo.light_specular_intensity)

    def inner_cone_angle(self):
        if self.data.type == 'SPOT':
            return jstr(min(160, degrees(self.data.spot_size) * abs(1 - self.data.spot_blend)))
        else:
            return jstr(20)

    def outer_cone_angle(self):
        if self.data.type == 'SPOT':
            return jstr(min(160, degrees(self.data.spot_size)))
        else:
            return jstr(60)

    def cone_projection_shape(self):
        return self.data.nwo.light_cone_projection_shape

    def shadow_near_clipplane(self):
        return jstr(self.data.nwo.light_shadow_near_clipplane)

    def shadow_far_clipplane(self):
        return jstr(self.data.nwo.light_shadow_far_clipplane)

    def shadow_bias_offset(self):
        return jstr(self.data.nwo.light_shadow_bias_offset)

    def shadow_color(self):
        return color_3p_str(self.data.nwo.light_shadow_color)

    def dynamic_shadow_quality(self):
        return self.data.nwo.light_dynamic_shadow_quality

    def shadows(self):
        return bool_str(self.data.nwo.light_shadows)

    def screenspace_light(self):
        return bool_str(self.data.nwo.light_sub_type == '_connected_geometry_lighting_sub_type_screenspace')

    def ignore_dynamic_objects(self):
        return bool_str(self.data.nwo.light_ignore_dynamic_objects)

    def cinema_objects_only(self):
        return bool_str(self.data.nwo.light_cinema_objects_only) # NEED TO ADD TO UI

    def cinema_only(self):
        return bool_str(self.data.nwo.light_cinema == '_connected_geometry_lighting_cinema_only')

    def cinema_exclude(self):
        return bool_str(self.data.nwo.light_cinema == '_connected_geometry_lighting_cinema_exclude')

    def specular_contribution(self):
        return bool_str(self.data.nwo.light_specular_contribution)

    def diffuse_contribution(self):
        return bool_str(self.data.nwo.light_diffuse_contribution)

    def destroy_light_after(self):
        return jstr(self.data.nwo.light_destroy_after)

    def indirect_amplification_factor(self):
        return jstr(self.data.nwo.light_amplification_factor)

    def is_sun(self):
        return bool_str(self.data.type == 'SUN')

    def is_indirect_only(self):
        return bool_str(self.data.nwo.light_indirect_only)

    def is_static_analytic(self):
        return bool_str(self.data.nwo.light_static_analytic)

    def light_tag_name(self):
        return clean_tag_path(self.data.nwo.light_tag_name)

    def light_game_type(self):
        return self.data.nwo.light_game_type

    def light_shape(self):
        return self.data.nwo.light_shape

    def light_ignore_bsp_visibility(self):
        return bool_str(self.data.nwo.light_ignore_bsp_visibility)

    def light_hotspot_size(self):
        return jstr(self.data.nwo.light_hotspot_size)

    def light_hotspot_falloff(self):
        return jstr(self.data.nwo.light_hotspot_falloff)

    def light_aspect(self):
        return jstr(self.data.nwo.light_aspect)

    def light_falloff_shape(self):
        return jstr(self.data.nwo.light_falloff_shape)

    def light_frustum_width(self):
        return jstr(self.data.nwo.light_frustum_width)

    def light_frustum_height(self):
        return jstr(self.data.nwo.light_frustum_height)

    def light_bounce_light_ratio(self):
        return jstr(self.data.nwo.light_bounce_ratio)

    def light_dynamic_light_has_bounce(self):
        return bool_str(self.data.nwo.light_dynamic_has_bounce)

    def light_dynamic_light_has_bounce(self):
        return bool_str(self.data.nwo.light_screenspace_has_specular)

    def light_light_tag_override(self):
        return clean_tag_path(self.data.nwo.light_tag_override)

    def light_shader_reference(self):
        return clean_tag_path(self.data.nwo.light_shader_reference)

    def light_gel_reference(self):
        return clean_tag_path(self.data.nwo.light_gel_reference)

    def light_lens_flare_reference(self):
        return clean_tag_path(self.data.nwo.light_lens_flare_reference, 'lens_flare')

    def light_volume_distance(self):
        return jstr(self.data.nwo.light_volume_distance)

    def light_volume_intensity_scala(self):
        return jstr(self.data.nwo.light_volume_intensity)

# --------------------------------


# FRAME PCA
#####################
class NWOFramePCA(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        self.bungie_mesh_ispca =  self.mesh_ispca()
        
        self.cleanup()

    def mesh_ispca(self):
        return bool_str(self.ob.type == 'MESH')

# FRAME
#####################
class NWOFrame(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        self.bungie_frame_ID1 = self.frame_ID1()
        self.bungie_frame_ID2 = self.frame_ID2()

        if self.not_bungie_game:
            self.bungie_frame_world = self.frame_world()

        self.cleanup()

    def frame_ID1(self):
        return '8078'

    def frame_ID2(self):
        return '378163771'

    def frame_world(self):
        if self.ob == self.model_armature or self.ob == self.world_frame:
            return '1'
        else:
            return '0'


# MARKER
#####################
class NWOMarker(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        # SHARED
        self.bungie_marker_type = self.marker_type()
        if self.sidecar_type in ('MODEL', 'SKY') and not self.bungie_marker_type in (('_connected_geometry_marker_type_pathfinding_sphere', '_connected_geometry_marker_type_physics_hinge_constraint', '_connected_geometry_marker_type_physics_socket_constraint')):
            self.bungie_marker_all_regions = self.marker_all_regions()
            self.bungie_marker_region = self.marker_region()
        if self.bungie_marker_type in ('_connected_geometry_marker_type_model', '_connected_geometry_marker_type_hint', '_connected_geometry_marker_type_target'):
            self.bungie_marker_model_group = self.marker_model_group()
            if self.halo.marker_type == '_connected_geometry_marker_type_garbage' and vector_str(self.halo.marker_velocity) != "0.0 0.0 0.0":
                self.bungie_marker_velocity = self.marker_velocity()
        elif self.bungie_marker_type in ('_connected_geometry_marker_type_prefab', '_connected_geometry_marker_type_cheap_light', '_connected_geometry_marker_type_light', '_connected_geometry_marker_type_falling_leaf', '_connected_geometry_marker_type_game_instance'):
            self.bungie_marker_game_instance_tag_name = self.marker_game_instance_tag_name()
            self.bungie_marker_game_instance_variant_name = self.marker_game_instance_variant_name()
        elif self.bungie_marker_type in ('_connected_geometry_marker_type_pathfinding_sphere', '_connected_geometry_marker_type_target'): 
            self.bungie_mesh_primitive_sphere_radius = self.marker_sphere_radius() # mesh properties in my node properties... Pathfinding spheres need this or they don't get written to the collision model
            if self.bungie_marker_type == '_connected_geometry_marker_type_pathfinding_sphere':
                self.bungie_marker_pathfinding_sphere_vehicle_only = self.marker_pathfinding_sphere_vehicle_only()
                self.bungie_marker_pathfinding_sphere_remains_when_open = self.marker_pathfinding_sphere_remains_when_open()
                self.bungie_marker_pathfinding_sphere_with_sectors = self.marker_pathfinding_sphere_with_sectors()
        elif self.bungie_marker_type in ('_connected_geometry_marker_type_physics_hinge_constraint', '_connected_geometry_marker_type_physics_socket_constraint'):
            self.bungie_physics_constraint_parent = self.physics_constraint_parent()
            self.bungie_physics_constraint_child = self.physics_constraint_child()
            self.bungie_physics_constraint_use_limits = self.physics_constraint_use_limits()
            if self.bungie_physics_constraint_use_limits == '1':
                if self.bungie_marker_type == '_connected_geometry_marker_type_physics_hinge_constraint':
                    self.bungie_physics_constraint_hinge_min = self.physics_constraint_hinge_min()
                    self.bungie_physics_constraint_hinge_max = self.physics_constraint_hinge_max()
                elif self.bungie_marker_type == '_connected_geometry_marker_type_physics_socket_constraint':
                    self.bungie_physics_constraint_cone_angle = self.physics_constraint_cone_angle()
                    self.bungie_physics_constraint_plane_min = self.physics_constraint_plane_min()
                    self.bungie_physics_constraint_plane_max = self.physics_constraint_plane_max()
                    self.bungie_physics_constraint_twist_start = self.physics_constraint_twist_start()
                    self.bungie_physics_constraint_twist_end = self.physics_constraint_twist_end()
        # H4
        if self.not_bungie_game:
            if self.bungie_marker_type in ('_connected_geometry_marker_type_cheap_light', '_connected_geometry_marker_type_light', '_connected_geometry_marker_type_falling_leaf', '_connected_geometry_marker_type_game_instance'):
                self.bungie_marker_always_run_scripts = self.marker_always_run_scripts()
                if self.bungie_marker_type == '_connected_geometry_marker_type_cheap_light':
                    self.bungie_marker_cheap_light_tag_name = self.marker_cheap_light_tag_name()
                elif self.bungie_marker_type == '_connected_geometry_marker_type_light':
                    self.bungie_marker_light_tag_name = self.marker_light_tag_name()
                elif self.bungie_marker_type == '_connected_geometry_marker_type_falling_leaf':
                    self.bungie_marker_falling_leaf_tag_name = self.marker_falling_leaf_tag_name()
            elif self.bungie_marker_type == '_connected_geometry_marker_type_hint':
                self.bungie_marker_hint_length = self.marker_hint_length()
            elif self.bungie_marker_type == '_connected_geometry_marker_type_envfx':
                self.bungie_marker_looping_effect = self.marker_looping_effect()
            elif self.bungie_marker_type == '_connected_geometry_marker_type_airprobe':
                self.bungie_marker_airprobe = self.marker_airprobe()
            elif self.bungie_marker_type == '_connected_geometry_marker_type_lightCone':
                self.bungie_marker_light_tag = self.marker_light_tag()
                self.bungie_marker_light_color = self.marker_light_color()
                self.bungie_marker_light_cone_width = self.marker_light_cone_width()
                self.bungie_marker_light_cone_length = self.marker_light_cone_length()
                self.bungie_marker_light_color_alpha = self.marker_light_color_alpha()
                self.bungie_marker_light_cone_intensity = self.marker_light_cone_intensity()
                self.bungie_marker_light_cone_curve = self.marker_light_cone_curve()

        self.cleanup()

    def marker_type(self):
        # need to cast marker type to model if using Blender only marker types:
        if self.halo.marker_type in ('_connected_geometry_marker_type_effects', '_connected_geometry_marker_type_garbage'):
            return '_connected_geometry_marker_type_model'
        return self.halo.marker_type

    def marker_model_group(self):
        return self.halo.marker_group_name

    def marker_all_regions(self):
        return bool_str(self.halo.marker_all_regions)

    def marker_region(self): 
        return self.halo.region_name

    def marker_game_instance_tag_name(self):
        return clean_tag_path(self.halo.marker_game_instance_tag_name)

    def marker_game_instance_variant_name(self):
        return clean_tag_path(self.halo.marker_game_instance_tag_variant_name)

    def marker_velocity(self):
        return vector_str(self.halo.marker_velocity)

    def marker_pathfinding_sphere_vehicle_only(self):
        return bool_str(self.halo.marker_pathfinding_sphere_vehicle)

    def marker_pathfinding_sphere_remains_when_open(self):
        return bool_str(self.halo.pathfinding_sphere_remains_when_open)

    def marker_pathfinding_sphere_with_sectors(self):
        return bool_str(self.halo.pathfinding_sphere_with_sectors)
    
    def marker_sphere_radius(self):
        return radius_str(self.ob) if self.ob.type == 'MESH' else jstr(self.halo.marker_sphere_radius)

    def physics_constraint_parent(self):
        return self.halo.physics_constraint_parent

    def physics_constraint_child(self):
        return self.halo.physics_constraint_child

    def physics_constraint_use_limits(self):
        return bool_str(self.halo.physics_constraint_uses_limits) 

    def physics_constraint_hinge_min(self):
        return jstr(self.halo.hinge_constraint_minimum)

    def physics_constraint_hinge_max(self):
        return jstr(self.halo.hinge_constraint_maximum)

    def physics_constraint_cone_angle(self):
        return jstr(self.halo.cone_angle)

    def physics_constraint_plane_min(self):
        return jstr(self.halo.plane_constraint_minimum)

    def physics_constraint_plane_max(self):
        return jstr(self.halo.plane_constraint_maximum)

    def physics_constraint_twist_start(self):
        return jstr(self.halo.twist_constraint_start)

    def physics_constraint_twist_end(self):
        return jstr(self.halo.twist_constraint_end)

    def marker_always_run_scripts(self):
        return bool_str(self.halo.marker_game_instance_run_scripts)

    def marker_cheap_light_tag_name(self):
        return clean_tag_path(self.halo.marker_game_instance_tag_name, 'cheap_light')

    def marker_light_tag_name(self):
        return clean_tag_path(self.halo.marker_game_instance_tag_name, 'light')

    def marker_falling_leaf_tag_name(self):
        return clean_tag_path(self.halo.marker_game_instance_tag_name)

    def marker_hint_length(self):
        # return jstr(self.halo.marker_hint_length)
        return jstr(max(self.ob.scale.x, self.ob.scale.y, self.ob.scale.z))

    def marker_looping_effect(self):
        return clean_tag_path(self.halo.marker_looping_effect, 'effect')

    def marker_airprobe(self):
        return self.halo.marker_group_name

    def marker_light_tag(self):
        return clean_tag_path(self.halo.marker_light_cone_tag, 'light')

    def marker_light_color(self):
        return color_3p_str(self.halo.marker_light_cone_color)

    def marker_light_cone_width(self):
        return jstr(self.halo.marker_light_cone_width)

    def marker_light_cone_length(self):
        return jstr(self.halo.marker_light_cone_length)

    def marker_light_color_alpha(self):
        return jstr(self.halo.marker_light_cone_alpha)

    def marker_light_cone_intensity(self):
        return jstr(self.halo.marker_light_cone_intensity)     

    def marker_light_cone_curve(self):
        return clean_tag_path(self.halo.marker_light_cone_curve, 'curve_scalar')

    def model(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_model'))

    def effects(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_effects'))

    def game_instance(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_game_instance'))

    def garbage(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_garbage'))

    def hint(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_hint'))

    def pathfinding_sphere(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_pathfinding_sphere'))

    def physics_constraint(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_physics_constraint'))

    def target(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_target'))

    def water_volume_flow(self):
        return marker_type(self.ob, ('_connected_geometry_marker_type_water_volume_flow'))

    def airprobe(self): # h4+ only
        return marker_type(self.ob, ('_connected_geometry_marker_type_airprobe'))

    def envfx(self): # h4+ only
        return marker_type(self.ob, ('_connected_geometry_marker_type_envfx'))

    def lightcone(self): # h4+ only
        return marker_type(self.ob, ('_connected_geometry_marker_type_lightcone'))

    def prefab(self): # h4+ only
        return self.game_instance() and self.not_bungie_game and self.halo.marker_game_instance_tag_name.lower().endswith('.prefab')

    def cheap_light(self): # h4+ only
        return self.game_instance() and self.not_bungie_game and self.halo.marker_game_instance_tag_name.lower().endswith('.cheap_light')

    def marker_light(self): # h4+ only
        return self.game_instance() and self.not_bungie_game and self.halo.marker_game_instance_tag_name.lower().endswith('.light')

    def falling_leaf(self):  # h4+ only
        return self.game_instance() and self.not_bungie_game and self.halo.marker_game_instance_tag_name.lower().endswith('.leaf')
        
# MESH
#####################
class NWOMesh(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        # SHARED
        self.bungie_mesh_type = self.mesh_type()
        if self.sidecar_type in ('MODEL', 'SKY') and self.bungie_mesh_type in ('_connected_geometry_mesh_type_physics', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_default'):
            self.bungie_face_region = self.face_region()
        # PROPS FOR MESH TYPES WHICH HAVE RENDERED FACES
        if self.bungie_mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_decorator', '_connected_geometry_mesh_type_object_instance', '_connected_geometry_mesh_type_water_surface'):
            self.bungie_face_type = self.face_type()
            self.bungie_face_mode = self.face_mode()
            self.bungie_face_sides = self.face_sides()
            self.bungie_face_draw_distance = self.face_draw_distance()
            self.bungie_texcoord_usage = self.texcoord_usage()
            self.bungie_conveyor = self.conveyor()
            self.bungie_ladder = self.ladder()
            self.bungie_slip_surface = self.slip_surface()
            self.bungie_decal_offset = self.decal_offset()
            self.bungie_group_transparents_by_plane = self.group_transparents_by_plane()
            self.bungie_no_shadow = self.no_shadow()
            self.bungie_precise_position = self.precise_position()
            self.bungie_mesh_tessellation_density = self.mesh_tessellation_density()
            self.bungie_mesh_additional_compression = self.mesh_additional_compression()
            if self.not_bungie_game:
                self.bungie_invisible_to_pvs = self.invisible_to_pvs()
                self.bungie_no_lightmap = self.no_lightmap()
                self.bungie_uvmirror_across_entire_model = self.uvmirror_across_entire_model()
                
            if self.bungie_face_type == '_connected_geometry_face_type_sky':
                self.bungie_sky_permutation_index = self.sky_permutation_index()

        if self.halo.precise_position:
            self.bungie_mesh_use_uncompressed_verts = self.mesh_use_uncompressed_verts()

        if self.bungie_mesh_type in ('_connected_geometry_mesh_type_physics', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_water_surface'):
            if self.halo.face_global_material != '':
                self.bungie_face_global_material = self.face_global_material()
        
        # SPECIFIC MESH TYPE PROPS
        if self.bungie_mesh_type == '_connected_geometry_mesh_type_boundary_surface':
            self.bungie_mesh_boundary_surface_type = self.mesh_boundary_surface_type()
            self.bungie_mesh_boundary_surface_name = self.mesh_boundary_surface_name()

        elif self.bungie_mesh_type in ('_connected_geometry_mesh_type_poop_collision',  '_connected_geometry_mesh_type_poop'):
            if self.not_bungie_game:
                self.bungie_mesh_poop_collision_type = self.mesh_poop_collision_type()
                self.bungie_mesh_poop_collision_override_global_material = self.mesh_poop_collision_override_global_material()
                if self.bungie_mesh_poop_collision_override_global_material == '1':
                    self.bungie_mesh_global_material = self.mesh_global_material()
            if self.bungie_mesh_type == '_connected_geometry_mesh_type_poop':
                self.bungie_mesh_poop_lighting = self.mesh_poop_lighting()
                if self.halo.lightmap_resolution_scale_active:
                    self.bungie_mesh_poop_lightmap_resolution_scale = self.mesh_poop_lightmap_resolution_scale()
                self.bungie_mesh_poop_pathfinding = self.mesh_poop_pathfinding()
                self.bungie_mesh_poop_imposter_policy = self.mesh_poop_imposter_policy()
                self.bungie_mesh_poop_imposter_transition_distance = self.mesh_poop_imposter_brightness()
                # self.bungie_mesh_poop_fade_range_start = self.mesh_poop_fade_range_start()
                # self.bungie_mesh_poop_fade_range_end = self.mesh_poop_fade_range_end()
                # This needs to be Reach only otherwise tool complains. However, the flag is still in use in the UI as it is instead used to set instanced collision type to none
                if not self.not_bungie_game:
                    self.bungie_mesh_poop_is_render_only = self.mesh_poop_is_render_only()

                self.bungie_mesh_poop_chops_portals = self.mesh_poop_chops_portals()
                self.bungie_mesh_poop_does_not_block_aoe = self.mesh_poop_does_not_block_aoe()
                self.bungie_mesh_poop_excluded_from_lightprobe = self.mesh_poop_excluded_from_lightprobe()
                self.bungie_mesh_poop_decal_spacing = self.mesh_poop_decal_spacing()
                self.bungie_mesh_poop_precise_geometry = self.mesh_poop_precise_geometry()
                # self.bungie_mesh_poop_predominant_shader_name = self.mesh_poop_predominant_shader_name()
                # self.bungie_mesh_poop_light_channel_flags = self.mesh_poop_light_channel_flags()
                # H4 only
                if self.not_bungie_game:
                    self.bungie_mesh_poop_imposter_brightness = self.mesh_poop_imposter_brightness()
                    self.bungie_mesh_poop_streamingpriority = self.mesh_poop_streamingpriority()
                    self.bungie_mesh_poop_remove_from_shadow_geometry = self.mesh_poop_remove_from_shadow_geometry()
                    self.bungie_mesh_poop_cinema_only = self.mesh_poop_cinema_only()
                    self.bungie_mesh_poop_exclude_from_cinema = self.mesh_poop_exclude_from_cinema()
                    self.bungie_mesh_poop_disallow_object_lighting_samples = self.mesh_poop_disallow_object_lighting_samples()
                    self.bungie_mesh_poop_is_rain_occluder = self.mesh_poop_is_rain_occluder()

        elif self.bungie_mesh_type == '_connected_geometry_mesh_type_physics':
            self.bungie_mesh_primitive_type = self.mesh_primitive_type()
            if self.bungie_mesh_primitive_type == '_connected_geometry_primitive_type_box':
                self.bungie_mesh_primitive_box_length = self.mesh_primitive_box_length()
                self.bungie_mesh_primitive_box_width = self.mesh_primitive_box_width()
                self.bungie_mesh_primitive_box_height = self.mesh_primitive_box_height()
            elif self.bungie_mesh_primitive_type == '_connected_geometry_primitive_type_pill':
                self.bungie_mesh_primitive_pill_radius = self.mesh_primitive_pill_radius()
                self.bungie_mesh_primitive_pill_height = self.mesh_primitive_pill_height()
            elif self.bungie_mesh_primitive_type == '_connected_geometry_primitive_type_sphere':
                self.bungie_mesh_primitive_sphere_radius = self.mesh_primitive_sphere_radius()

        elif self.bungie_mesh_type == '_connected_geometry_mesh_type_portal':
            self.bungie_mesh_portal_type = self.mesh_portal_type()
            self.bungie_mesh_portal_ai_deafening = self.mesh_portal_ai_deafening()
            self.bungie_mesh_portal_blocks_sound = self.mesh_portal_blocks_sound()
            self.bungie_mesh_portal_is_door = self.mesh_portal_is_door()

        elif self.bungie_mesh_type == '_connected_geometry_mesh_type_decorator':
            self.bungie_mesh_decorator_lod = self.mesh_decorator_lod()
            self.bungie_mesh_decorator_name = self.mesh_decorator_name()

        elif self.bungie_mesh_type == '_connected_geometry_mesh_type_seam':
            self.bungie_mesh_seam_associated_bsp = self.mesh_seam_associated_bsp()
            # self.bungie_mesh_seam_front_bsp = self.mesh_seam_front_bsp()
            # self.bungie_mesh_seam_back_bsp = self.mesh_seam_back_bsp()

        elif self.bungie_mesh_type == '_connected_geometry_mesh_type_water_physics_volume':
            self.bungie_mesh_water_volume_depth = self.mesh_water_volume_depth()
            self.bungie_mesh_water_volume_flow_direction = self.mesh_water_volume_flow_direction()
            self.bungie_mesh_water_volume_flow_velocity = self.mesh_water_volume_flow_velocity()
            self.bungie_mesh_water_volume_fog_color = self.mesh_water_volume_fog_color()
            self.bungie_mesh_water_volume_fog_murkiness = self.mesh_water_volume_fog_murkiness()

        elif self.bungie_mesh_type == '_connected_geometry_mesh_type_planar_fog_volume':
            self.bungie_mesh_fog_name = self.mesh_fog_name()
            self.bungie_mesh_fog_appearance_tag = self.mesh_fog_appearance_tag()
            self.bungie_mesh_fog_volume_depth = self.mesh_fog_volume_depth()

        elif self.bungie_mesh_type == '_connected_geometry_mesh_type_obb_volume':
            self.bungie_mesh_obb_type = self.mesh_obb_type()

        # LIGHTMAP PROPERTIES
        if self.halo.lightmap_additive_transparency_active:
            self.bungie_lightmap_transparency_override = self.lightmap_transparency_override()
            self.bungie_lightmap_additive_transparency = self.lightmap_additive_transparency()
        if self.halo.lightmap_resolution_scale_active:
            self.bungie_lightmap_ignore_default_resolution_scale = self.lightmap_ignore_default_resolution_scale()
            self.bungie_lightmap_resolution_scale = self.lightmap_resolution_scale()
        # self.bungie_lightmap_chart_group = self.lightmap_chart_group()
        # self.bungie_lightmap_photon_fidelity = self.lightmap_photon_fidelity()
        if self.halo.lightmap_type_active:
            self.bungie_lightmap_type = self.lightmap_type()
        # if self.halo.lightmap_analytical_bounce_modifier_active:
        #     self.bungie_lightmap_analytical_bounce_modifier = self.lightmap_analytical_bounce_modifier()
        # if self.halo.lightmap_general_bounce_modifier_active:
        #     self.bungie_lightmap_general_bounce_modifier = self.lightmap_general_bounce_modifier()
        # self.bungie_lightmap_analytical_absorb_ratio = self.lightmap_analytical_absorb_ratio()
        if self.halo.lightmap_translucency_tint_color_active:
            self.bungie_lightmap_translucency_tint_color = self.lightmap_translucency_tint_color()
        if self.halo.lightmap_lighting_from_both_sides_active:
            self.bungie_lightmap_lighting_from_both_sides = self.lightmap_lighting_from_both_sides()
            # if self.not_bungie_game:
            #     self.bungie_mesh_per_vertex_lighting = self.mesh_per_vertex_lighting()
        # EMMISSIVE PROPERTIES
        if self.halo.material_lighting_attenuation_active:
            # if not_bungie_game():
            #     self.bungie_lighting_attenuation_enabled = self.lighting_attenuation_enabled()
                # self.bungie_lighting_frustum_blend = self.lighting_frustum_blend()
                # self.bungie_lighting_frustum_cutoff = self.lighting_frustum_cutoff()
                # self.bungie_lighting_frustum_falloff = self.lighting_frustum_falloff()
            self.bungie_lighting_attenuation_cutoff = self.lighting_attenuation_cutoff()
            self.bungie_lighting_attenuation_falloff = self.lighting_attenuation_falloff()
        if self.halo.material_lighting_emissive_focus_active:
            self.bungie_lighting_emissive_focus = self.lighting_emissive_focus()
        if self.halo.material_lighting_emissive_color_active:
            self.bungie_lighting_emissive_color = self.lighting_emissive_color()
        if self.halo.material_lighting_emissive_per_unit_active:
            self.bungie_lighting_emissive_per_unit = self.lighting_emissive_per_unit()
        if self.halo.material_lighting_emissive_power_active:
            self.bungie_lighting_emissive_power = self.lighting_emissive_power()
        if self.halo.material_lighting_emissive_quality_active:
            self.bungie_lighting_emissive_quality = self.lighting_emissive_quality()
        if self.halo.material_lighting_use_shader_gel_active:
            self.bungie_lighting_use_shader_gel = self.lighting_use_shader_gel()
        if self.halo.material_lighting_bounce_ratio_active:
            self.bungie_lighting_bounce_ratio = self.lighting_bounce_ratio()

        self.cleanup()

    def mesh_type(self):
        return self.halo.mesh_type

    def mesh_global_material(self):
        return self.halo.face_global_material

    def mesh_primitive_type(self):
        return self.halo.mesh_primitive_type

    def mesh_primitive_box_length(self):
        return jstr(self.ob.dimensions.y)

    def mesh_primitive_box_width(self):
        return jstr(self.ob.dimensions.x)

    def mesh_primitive_box_height(self):
        return jstr(self.ob.dimensions.z)

    def mesh_primitive_pill_radius(self):
        return radius_str(self.ob)

    def mesh_primitive_pill_height(self):
        return jstr(self.ob.dimensions.z)

    def mesh_primitive_sphere_radius(self):
        return radius_str(self.ob)

    def mesh_boundary_surface_type(self):
        if self.ob.name.startswith('+soft_ceiling'):
            return '_connected_geometry_boundary_surface_type_soft_ceiling'
        elif self.ob.name.startswith('+soft_kill'):
            return '_connected_geometry_boundary_surface_type_soft_kill'
        elif self.ob.name.startswith('+slip_surface'):
            return '_connected_geometry_boundary_surface_type_slip_surface'
        else:
            return self.halo.boundary_surface_type

    def mesh_boundary_surface_name(self):
        return self.halo.boundary_surface_name

    def mesh_poop_lighting(self):
        return self.halo.poop_lighting_override

    def mesh_poop_lightmap_resolution_scale(self):
        return jstr(self.halo.lightmap_resolution_scale) #jstr(self.halo.poop_lightmap_resolution_scale)

    def mesh_poop_pathfinding(self):
        return self.halo.poop_pathfinding_override

    def mesh_poop_imposter_policy(self):
        return self.halo.poop_imposter_policy

    def mesh_poop_imposter_brightness(self):
        return jstr(self.halo.poop_imposter_brightness)

    # def mesh_poop_fade_range_start(self):
    #     return jstr(self.halo.Poop_Imposter_Fade_Range_Start)

    # def mesh_poop_fade_range_end(self):
    #     return jstr(self.halo.Poop_Imposter_Fade_Range_End)

    def mesh_poop_is_render_only(self):
        return bool_str(self.halo.poop_render_only)

    def mesh_poop_chops_portals(self):
        return bool_str(self.halo.poop_chops_portals)

    def mesh_poop_does_not_block_aoe(self):
        return bool_str(self.halo.poop_does_not_block_aoe)

    def mesh_poop_excluded_from_lightprobe(self):
        return bool_str(self.halo.poop_excluded_from_lightprobe)

    def mesh_poop_streamingpriority(self):
        return self.halo.poop_streaming_priority

    def mesh_poop_decal_spacing(self):
        return bool_str(self.halo.poop_decal_spacing)

    def mesh_poop_precise_geometry(self):
        return bool_str(self.halo.poop_precise_geometry)

    def mesh_poop_remove_from_shadow_geometry(self):
        return bool_str(self.halo.poop_remove_from_shadow_geometry)

    def mesh_poop_cinema_only(self):
        return bool_str(self.halo.poop_cinematic_properties == 'bungie_mesh_poop_cinema_only')

    def mesh_poop_exclude_from_cinema(self):
        return bool_str(self.halo.poop_cinematic_properties == 'bungie_mesh_poop_exclude_from_cinema')

    def mesh_poop_disallow_object_lighting_samples(self):
        return bool_str(self.halo.poop_disallow_lighting_samples)

    def mesh_poop_is_rain_occluder(self):
        return bool_str(self.halo.poop_rain_occluder)

    def mesh_tessellation_density(self):
        return self.halo.mesh_tessellation_density

    def mesh_additional_compression(self):
        return self.halo.mesh_compression

    def mesh_use_uncompressed_verts(self):
        if self.bungie_mesh_type in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_poop', '_connected_geometry_mesh_type_object_instance'):
            if '_connected_geometry_mesh_type_default' and self.sidecar_type == 'SCENARIO':
                return bool_str(False)
            else:
                return bool_str(not self.halo.compress_verts)
        else:
            return bool_str(False)

    def uvmirror_across_entire_model(self):
        return bool_str(self.halo.uvmirror_across_entire_model)

    def mesh_per_vertex_lighting(self):
        return bool_str(self.halo.lightmap_type == '_connected_material_lightmap_type_per_vertex')

    def mesh_poop_collision_type(self):
        if self.halo.poop_render_only:
            return '_connected_geometry_poop_collision_type_none'
        else:
            return self.halo.poop_collision_type

    def mesh_poop_collision_override_global_material(self):
        return bool_str(self.halo.face_global_material != '')

    def mesh_portal_type(self):
        return self.halo.portal_type

    def mesh_portal_ai_deafening(self):
        return bool_str(self.halo.portal_ai_deafening)

    def mesh_portal_blocks_sound(self):
        return bool_str(self.halo.portal_blocks_sounds)

    def mesh_portal_is_door(self):
        return bool_str(self.halo.portal_is_door)

    def mesh_decorator_lod(self):
        return str(self.halo.decorator_lod)

    def mesh_decorator_name(self):
        return self.halo.decorator_name

    def mesh_seam_associated_bsp(self):
        return f'{self.asset_name}_{self.halo.bsp_name}'

    def mesh_water_volume_depth(self):
        return jstr(self.halo.water_volume_depth)

    def mesh_water_volume_flow_direction(self):
        return jstr(self.halo.water_volume_flow_direction)

    def mesh_water_volume_flow_velocity(self):
        return jstr(self.halo.water_volume_flow_velocity)

    def mesh_water_volume_fog_color(self):
        if self.not_bungie_game:
            return color_3p_str(self.halo.water_volume_fog_color)
        else:
            return color_4p_str(self.halo.water_volume_fog_color)

    def mesh_water_volume_fog_murkiness(self):
        return jstr(self.halo.water_volume_fog_murkiness)

    def mesh_fog_name(self):
        return self.halo.Fog_Name

    def mesh_fog_appearance_tag(self):
        return clean_tag_path(self.halo.fog_appearance_tag)

    def mesh_fog_volume_depth(self):
        return jstr(self.halo.fog_volume_depth)

    def mesh_obb_type(self):
        return self.halo.obb_volume_type

    def face_type(self):
        if self.not_bungie_game and self.bungie_mesh_type == '_connected_geometry_mesh_type_default':
            return '_connected_geometry_face_type_sky'
        else:
            return self.halo.face_type

    def face_mode(self):
        if not self.not_bungie_game and len(self.ob.children) > 0 and self.bungie_mesh_type == '_connected_geometry_mesh_type_poop':
            for child in self.ob.children:
                if CheckType.poop_collision(child):
                    return '_connected_geometry_face_mode_render_only'
            else:
                return self.halo.face_mode
        else:
            return self.halo.face_mode


    def face_sides(self):
        return self.halo.face_sides

    def face_draw_distance(self):
        return self.halo.face_draw_distance

    def face_global_material(self):
        return self.halo.face_global_material

    def face_region(self):
        return self.halo.region_name

    def texcoord_usage(self): # NEEDS ENTRY IN UI
        return self.halo.texcoord_usage

    def conveyor(self):
        return bool_str(self.halo.conveyor)

    def ladder(self):
        return bool_str(self.halo.ladder)

    def slip_surface(self):
        return bool_str(self.halo.slip_surface)

    def decal_offset(self):
        return bool_str(self.halo.decal_offset)

    def group_transparents_by_plane(self):
        return bool_str(self.halo.group_transparents_by_plane)

    def no_shadow(self):
        return bool_str(self.halo.no_shadow)

    def invisible_to_pvs(self):
        return bool_str(self.halo.no_pvs)

    def no_lightmap(self):
        return bool_str(self.halo.no_lightmap)

    def precise_position(self):
        return bool_str(self.halo.precise_position)

    def sky_permutation_index(self):
        return str(self.halo.sky_permutation_index)

    def lightmap_additive_transparency(self):
        return color_4p_str(self.halo.lightmap_additive_transparency)

    def lightmap_ignore_default_resolution_scale(self):
        return bool_str(True)

    def lightmap_resolution_scale(self):
        return jstr(self.halo.lightmap_resolution_scale)

    def lightmap_photon_fidelity(self):
        return self.halo.lightmap_photon_fidelity

    def lightmap_type(self):
        return self.halo.lightmap_type
    
    def lightmap_analytical_bounce_modifier(self):
        return jstr(self.halo.lightmap_analytical_bounce_modifier)
    
    def lightmap_general_bounce_modifier(self):
        return jstr(self.halo.lightmap_general_bounce_modifier)

    def lightmap_transparency_override(self):
        return bool_str(True)

    def lightmap_translucency_tint_color(self):
        if self.not_bungie_game:
            return color_3p_str(self.halo.lightmap_translucency_tint_color)
        else:
            return color_4p_str(self.halo.lightmap_translucency_tint_color)

    def lightmap_lighting_from_both_sides(self):
        return bool_str(self.halo.lightmap_lighting_from_both_sides)

    def lighting_attenuation_enabled(self): # NEEDS ENTRY IN UI
        return bool_str(self.halo.lighting_attenuation_enabled)

    def lighting_attenuation_cutoff(self):
        return jstr(self.halo.material_lighting_attenuation_cutoff)

    def lighting_attenuation_falloff(self):
        return jstr(self.halo.material_lighting_attenuation_falloff)

    def lighting_emissive_focus(self):
        return jstr(self.halo.material_lighting_emissive_focus)

    def lighting_emissive_color(self):
        return color_4p_str(self.halo.material_lighting_emissive_color)

    def lighting_emissive_per_unit(self):
        return bool_str(self.halo.material_lighting_emissive_per_unit)

    def lighting_emissive_power(self):
        return jstr(self.halo.material_lighting_emissive_power)

    def lighting_emissive_quality(self):
        return jstr(self.halo.material_lighting_emissive_quality)

    def lighting_frustum_blend(self): # NEEDS ENTRY IN UI
        return jstr(self.halo.lighting_frustum_blend)

    def lighting_frustum_cutoff(self): # NEEDS ENTRY IN UI
        return jstr(self.halo.lighting_frustum_cutoff)

    def lighting_frustum_falloff(self): # NEEDS ENTRY IN UI
        return jstr(self.halo.lighting_frustum_falloff)

    def lighting_use_shader_gel(self):
        return bool_str(self.halo.material_lighting_use_shader_gel)

    def lighting_bounce_ratio(self):
        return jstr(self.halo.material_lighting_bounce_ratio)

    def boundary_surface(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_boundary_surface'))

    def collision(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_collision'))

    def cookie_cutter(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_cookie_cutter'))

    def decorator(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_decorator'))
    
    def default(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_default'))

    def poop(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_poop'))

    def poop_marker(self): # REACH ONLY
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_poop_marker'))

    def poop_rain_blocker(self): # REACH ONLY
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_poop_rain_blocker'))

    def poop_vertical_rain_sheet(self): # REACH ONLY
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_poop_vertical_rain_sheet'))

    def lightmap_region(self): # REACH ONLY
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_lightmap_region'))

    def object_instance(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_object_instance'))

    def physics(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_physics'))

    def planar_fog_volume(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_planar_fog_volume'))

    def portal(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_portal'))

    def seam(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_seam'))

    def water_physics_volume(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_water_physics_volume'))

    def water_surface(self):
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_water_surface'))

    def obb_volume(self): # H4+ ONLY
        return mesh_type(self.ob, ('_connected_geometry_mesh_type_obb_volume')) 

class NWOMaterial:
    def __init__(self, material):
        self.material = material
        self.material_name = material.name
        self.halo = material.nwo
        self.bungie_shader_path = self.shader_path()
        self.bungie_shader_type = self.shader_type()

        del self.material
        del self.material_name
        del self.halo

    def shader_path(self):
        if self.halo.shader_path == '':
            return 'override'
        else:
            return clean_tag_path(self.halo.shader_path, '')

    def shader_type(self):
        if self.halo.shader_path == '':
            return 'override'
        elif not_bungie_game():
            return 'material'
        else:
            shader_type = self.halo.shader_path.rpartition('.')[2]
            if '.' + shader_type in shader_exts:
                return shader_type
            return 'shader'

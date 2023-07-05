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

from ..utils.nwo_utils import (
    dot_partition,
    not_bungie_game,
    color_3p_str,
    color_4p_str,
    bool_str,
    jstr,
    radius_str,
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
        if self.bungie_object_type not in (
            "_connected_geometry_object_type_animation_control",
            "_connected_geometry_object_type_animation_event",
        ):
            self.bungie_object_ID = self.object_ID()
        # self.halo_export = '1'
        if self.bungie_object_type == "_connected_geometry_object_type_frame":
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
        return bool_str(self.sidecar_type == "MODEL")


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
        self.bungie_animation_event_type = self.halo.event_type
        self.bungie_animation_event_start = self.halo.frame_start
        self.bungie_animation_event_end = self.halo.frame_end
        self.bungie_animation_event_id = self.halo.event_id
        self.bungie_animation_event_frame_frame = self.halo.frame_frame
        self.bungie_animation_event_frame_name = self.halo.frame_name
        if (
            self.bungie_animation_event_type
            == "_connected_geometry_animation_event_type_wrinkle_map"
        ):
            self.bungie_animation_event_wrinkle_map_face_region = (
                self.halo.wrinkle_map_face_region
            )
            self.bungie_animation_event_wrinkle_map_effect = (
                self.halo.wrinkle_map_effect
            )
        elif (
            self.bungie_animation_event_type
            == "_connected_geometry_animation_event_type_footstep"
        ):
            self.bungie_animation_event_footstep_type = self.halo.footstep_type
            self.bungie_animation_event_footstep_effect = self.halo.footstep_effect
        elif self.bungie_animation_event_type in (
            "_connected_geometry_animation_event_type_ik_active",
            "_connected_geometry_animation_event_type_ik_passive",
        ):
            self.bungie_animation_event_ik_chain = self.halo.ik_chain
            self.bungie_animation_event_ik_active_tag = self.halo.ik_active_tag
            self.bungie_animation_event_ik_target_tag = self.halo.ik_target_tag
            self.bungie_animation_event_ik_target_marker = self.halo.ik_target_marker
            self.bungie_animation_event_ik_target_usage = self.halo.ik_target_usage
            self.bungie_animation_event_ik_proxy_target_id = (
                self.halo.ik_proxy_target_id
            )
            self.bungie_animation_event_ik_pole_vector_id = self.halo.ik_pole_vector_id
            self.bungie_animation_event_ik_effector_id = self.halo.ik_effector_id
        elif (
            self.bungie_animation_event_type
            == "_connected_geometry_animation_event_type_cinematic_effect"
        ):
            self.bungie_animation_event_cinematic_effect_tag = (
                self.halo.cinematic_effect_tag
            )
            self.bungie_animation_event_cinematic_effect_effect = (
                self.halo.cinematic_effect_effect
            )
            self.bungie_animation_event_cinematic_effect_marker = (
                self.halo.cinematic_effect_marker
            )
        elif (
            self.bungie_animation_event_type
            == "_connected_geometry_animation_event_type_object_function"
        ):
            self.bungie_animation_event_object_function_name = (
                self.halo.object_function_name
            )
            self.bungie_animation_event_object_function_effect = (
                self.halo.object_function_effect
            )
        elif (
            self.bungie_animation_event_type
            == "_connected_geometry_animation_event_type_frame"
        ):
            self.bungie_animation_event_frame_trigger = self.halo.frame_trigger
        elif (
            self.bungie_animation_event_type
            == "_connected_geometry_animation_event_type_import"
        ):
            self.bungie_animation_event_import_frame = self.halo.import_frame
            self.bungie_animation_event_import_name = self.halo.import_name
        elif (
            self.bungie_animation_event_type
            == "_connected_geometry_animation_event_type_text"
        ):
            self.bungie_animation_event_text = self.halo.text

        self.cleanup()


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
        self.bungie_light_type = self.light_type()
        self.bungie_light_color = self.light_color()
        self.bungie_light_intensity = self.light_intensity()

        if self.not_bungie_game:
            # H4 ONLY
            self.bungie_light_mode = self.light_mode()
            self.bungie_lighting_mode = self.lighting_mode()
            self.bungie_light_near_attenuation_start = (
                self.light_near_attenuation_start()
            )
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
            self.bungie_indirect_amplification_factor = (
                self.indirect_amplification_factor()
            )
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
            self.bungie_light_type_version = "1"
            self.bungie_light_game_type = self.light_game_type()
            self.bungie_light_shape = self.light_shape()
            self.bungie_light_near_attenuation_start = (
                self.light_near_attenuation_start()
            )
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
            self.bungie_light_dynamic_light_has_bounce = (
                self.light_dynamic_light_has_bounce()
            )
            # self.bungie_light_screenspace_light_has_specular = self.light_screenspace_light_has_specular()
            self.bungie_light_light_tag_override = self.light_light_tag_override()
            self.bungie_light_shader_reference = self.light_shader_reference()
            self.bungie_light_gel_reference = self.light_gel_reference()
            self.bungie_light_lens_flare_reference = self.light_lens_flare_reference()
            self.bungie_light_volume_distance = self.light_volume_distance()
            self.bungie_light_volume_intensity_scalar = (
                self.light_volume_intensity_scala()
            )

        self.cleanup()

    # --------------------------------

    def light_type(self):
        light_type = self.data.type
        if light_type == "SUN":
            return "_connected_geometry_light_type_directional"
        elif light_type == "POINT":
            if self.not_bungie_game:
                return "_connected_geometry_light_type_point"
            else:
                return "_connected_geometry_light_type_omni"
        else:
            return "_connected_geometry_light_type_spot"

    def is_uber_light(self):
        return bool_str(
            self.data.nwo.light_sub_type == "_connected_geometry_lighting_sub_type_uber"
        )

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
            div = 10
        else:
            div = 300

        return jstr(
            (self.ob.data.energy / 0.03048**-2) / div
            if self.ob.data.type != "SUN"
            else self.ob.data.energy
        )

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
        if self.data.type == "SPOT":
            return jstr(
                min(
                    160,
                    degrees(self.data.spot_size) * abs(1 - self.data.spot_blend),
                )
            )
        else:
            return jstr(20)

    def outer_cone_angle(self):
        if self.data.type == "SPOT":
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
        return bool_str(
            self.data.nwo.light_sub_type
            == "_connected_geometry_lighting_sub_type_screenspace"
        )

    def ignore_dynamic_objects(self):
        return bool_str(self.data.nwo.light_ignore_dynamic_objects)

    def cinema_objects_only(self):
        return bool_str(self.data.nwo.light_cinema_objects_only)  # NEED TO ADD TO UI

    def cinema_only(self):
        return bool_str(
            self.data.nwo.light_cinema == "_connected_geometry_lighting_cinema_only"
        )

    def cinema_exclude(self):
        return bool_str(
            self.data.nwo.light_cinema == "_connected_geometry_lighting_cinema_exclude"
        )

    def specular_contribution(self):
        return bool_str(self.data.nwo.light_specular_contribution)

    def diffuse_contribution(self):
        return bool_str(self.data.nwo.light_diffuse_contribution)

    def destroy_light_after(self):
        return jstr(self.data.nwo.light_destroy_after)

    def indirect_amplification_factor(self):
        return jstr(self.data.nwo.light_amplification_factor)

    def is_sun(self):
        return bool_str(self.data.type == "SUN")

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
        return clean_tag_path(self.data.nwo.light_lens_flare_reference, "lens_flare")

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
        self.bungie_mesh_ispca = self.mesh_ispca()

        self.cleanup()

    def mesh_ispca(self):
        return bool_str(self.ob.type == "MESH")


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
        return "8078"

    def frame_ID2(self):
        return "378163771"

    def frame_world(self):
        if self.ob == self.model_armature or self.ob == self.world_frame:
            return "1"
        else:
            return "0"


# MARKER
#####################
class NWOMarker(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        # SHARED
        self.bungie_marker_type = self.halo.marker_type
        self.bungie_marker_model_group = self.marker_model_group()
        # properties for model/sky assets only
        if self.sidecar_type in ("MODEL", "SKY"):
            if self.halo.marker_all_regions:
                self.bungie_marker_all_regions = self.halo.marker_all_regions
                if self.bungie_marker_all_regions == "0":
                    self.bungie_marker_region = self.halo.region_name

        # garbage has velocity
        if self.halo.marker_type == "_connected_geometry_marker_type_garbage":
            self.bungie_marker_velocity = self.halo.marker_velocity

        # game tag stuff
        elif self.halo.marker_game_instance_tag_name:
            self.bungie_marker_game_instance_tag_name = (
                self.halo.marker_game_instance_tag_name
            )
            if self.halo.marker_game_instance_tag_variant_name:
                self.bungie_marker_game_instance_variant_name = (
                    self.halo.marker_game_instance_tag_variant_name
                )
            if self.not_bungie_game and self.halo.marker_game_instance_run_scripts:
                self.bungie_marker_game_instance_run_scripts = (
                    self.halo.marker_game_instance_run_scripts
                )

        # rest of the pathfinding sphere props
        elif (
            self.bungie_marker_type
            == "_connected_geometry_marker_type_pathfinding_sphere"
        ):
            # sphere radius is pulled from a mesh marker. In the case of an empty marker, this value is user defined
            self.bungie_mesh_primitive_sphere_radius = (
                self.halo.marker_sphere_radius
            )  # mesh properties in my node properties... Pathfinding spheres need this or they don't get written to the collision model
            self.bungie_marker_pathfinding_sphere_vehicle_only = (
                self.halo.marker_pathfinding_sphere_vehicle
            )
            self.bungie_marker_pathfinding_sphere_remains_when_open = (
                self.halo.pathfinding_sphere_remains_when_open
            )
            self.bungie_marker_pathfinding_sphere_with_sectors = (
                self.halo.pathfinding_sphere_with_sectors
            )
        elif self.bungie_marker_type == "_connected_geometry_marker_type_target":
            self.bungie_mesh_primitive_sphere_radius = self.halo.marker_sphere_radius

        # contraints props
        elif self.bungie_marker_type in (
            "_connected_geometry_marker_type_physics_hinge_constraint",
            "_connected_geometry_marker_type_physics_socket_constraint",
        ):
            if self.halo.physics_constraint_parent:
                self.bungie_physics_constraint_parent = (
                    self.halo.physics_constraint_parent
                )
            if self.halo.physics_constraint_child:
                self.bungie_physics_constraint_child = (
                    self.halo.physics_constraint_child
                )
            self.bungie_physics_constraint_use_limits = (
                self.halo.physics_constraint_uses_limits
            )
            if self.bungie_physics_constraint_use_limits == "1":
                if (
                    self.bungie_marker_type
                    == "_connected_geometry_marker_type_physics_hinge_constraint"
                ):
                    self.bungie_physics_constraint_hinge_min = (
                        self.halo.hinge_constraint_minimum
                    )

                    self.bungie_physics_constraint_hinge_max = (
                        self.halo.hinge_constraint_maximum
                    )

                elif (
                    self.bungie_marker_type
                    == "_connected_geometry_marker_type_physics_socket_constraint"
                ):
                    self.bungie_physics_constraint_cone_angle = self.halo.cone_angle
                    self.bungie_physics_constraint_plane_min = (
                        self.halo.plane_constraint_minimum
                    )
                    self.bungie_physics_constraint_plane_max = (
                        self.halo.plane_constraint_maximum
                    )
                    self.bungie_physics_constraint_twist_start = (
                        self.halo.twist_constraint_start
                    )
                    self.bungie_physics_constraint_twist_end = (
                        self.halo.twist_constraint_end
                    )

        # H4 only props
        if self.not_bungie_game:
            # special game instance types
            if self.bungie_marker_type == "_connected_geometry_marker_type_cheap_light":
                self.bungie_marker_cheap_light_tag_name = (
                    self.halo.marker_game_instance_tag_name
                )
            elif self.bungie_marker_type == "_connected_geometry_marker_type_light":
                self.bungie_marker_light_tag_name = (
                    self.halo.marker_game_instance_tag_name
                )
            elif (
                self.bungie_marker_type
                == "_connected_geometry_marker_type_falling_leaf"
            ):
                self.bungie_marker_falling_leaf_tag_name = (
                    self.halo.marker_game_instance_tag_name
                )

            # h4 has hint length
            elif self.bungie_marker_type == "_connected_geometry_marker_type_hint":
                if self.not_bungie_game and self.halo.marker_hint_length:
                    self.bungie_marker_hint_length = self.halo.marker_hint_length

            # scenario place fx
            elif self.bungie_marker_type == "_connected_geometry_marker_type_envfx":
                self.bungie_marker_looping_effect = self.marker_looping_effect()

            # airprobes
            elif self.bungie_marker_type == "_connected_geometry_marker_type_airprobe":
                self.bungie_marker_airprobe = self.marker_model_group()

            # light cone props
            elif self.bungie_marker_type == "_connected_geometry_marker_type_lightCone":
                self.bungie_marker_light_tag = self.halo.marker_light_tag
                self.bungie_marker_light_color = self.halo.marker_light_color
                self.bungie_marker_light_cone_width = self.halo.marker_light_cone_width
                self.bungie_marker_light_cone_length = (
                    self.halo.marker_light_cone_length
                )
                self.bungie_marker_light_color_alpha = (
                    self.halo.marker_light_color_alpha
                )
                self.bungie_marker_light_cone_intensity = (
                    self.halo.marker_light_cone_intensity
                )
                self.bungie_marker_light_cone_curve = self.halo.marker_light_cone_curve

        self.cleanup()

    def marker_model_group(self):
        return dot_partition(self.name).strip("#_?$-")


# MESH
#####################
class NWOMesh(NWOObject):
    def __init__(self, ob, sidecar_type, model_armature, world_frame, asset_name):
        super().__init__(ob, sidecar_type, model_armature, world_frame, asset_name)
        # SHARED
        self.bungie_mesh_type = self.halo.mesh_type
        if self.sidecar_type in ("MODEL", "SKY"):
            self.bungie_face_region = self.halo.region_name

        # PROPS FOR MESH TYPES WHICH HAVE RENDERED FACES:
        if self.halo.face_type:
            self.bungie_face_type = self.halo.face_type
            if self.bungie_face_type == "_connected_geometry_face_type_sky":
                self.bungie_sky_permutation_index = self.halo.sky_permutation_index

        if self.halo.face_mode:
            self.bungie_face_mode = self.halo.face_mode
        if self.halo.face_sides:
            self.bungie_face_sides = self.halo.face_sides
        if self.halo.face_draw_distance:
            self.bungie_face_draw_distance = self.halo.face_draw_distance
        if self.halo.texcoord_usage:
            self.bungie_texcoord_usage = self.halo.texcoord_usage

        if self.halo.ladder:
            self.bungie_ladder = self.halo.ladder
        if self.halo.slip_surface:
            self.bungie_slip_surface = self.halo.slip_surface
        if self.halo.decal_offset:
            self.bungie_decal_offset = self.halo.decal_offset
        if self.halo.group_transparents_by_plane:
            self.bungie_group_transparents_by_plane = (
                self.halo.group_transparents_by_plane
            )
        if self.halo.no_shadow:
            self.bungie_no_shadow = self.halo.no_shadow
        if self.halo.precise_position:
            self.bungie_precise_position = self.halo.precise_position
            if self.bungie_mesh_type == "_connected_geometry_mesh_type_poop":
                self.bungie_mesh_poop_precise_geometry = "1"
        if self.halo.mesh_tessellation_density:
            self.bungie_mesh_tessellation_density = self.halo.mesh_tessellation_density
        if self.halo.mesh_compression:
            self.bungie_mesh_additional_compression = self.halo.mesh_compression
        if self.not_bungie_game:
            if self.halo.no_pvs:
                self.bungie_invisible_to_pvs = self.halo.no_pvs
            if self.halo.no_lightmap:
                self.bungie_no_lightmap = self.halo.no_lightmap
            if self.halo.uvmirror_across_entire_model:
                self.bungie_uvmirror_across_entire_model = (
                    self.halo.uvmirror_across_entire_model
                )

            if self.halo.precise_position:
                self.bungie_mesh_use_uncompressed_verts = (
                    self.mesh_use_uncompressed_verts()
                )

        if self.halo.face_global_material:
            self.bungie_face_global_material = self.halo.face_global_material

        # SPECIFIC MESH TYPE PROPS
        if self.bungie_mesh_type == "_connected_geometry_mesh_type_boundary_surface":
            self.bungie_mesh_boundary_surface_type = self.halo.boundary_surface_type
            self.bungie_mesh_boundary_surface_name = dot_partition(self.name)

        elif self.bungie_mesh_type in (
            "_connected_geometry_mesh_type_poop_collision",
            "_connected_geometry_mesh_type_poop",
        ):
            if (
                self.not_bungie_game
                and self.bungie_mesh_type == "_connected_geometry_mesh_type_poop"
                and self.halo.poop_rain_occluder == "1"
            ):
                self.bungie_mesh_poop_is_rain_occluder = "1"
            else:
                if self.not_bungie_game:
                    self.bungie_mesh_poop_collision_type = (
                        self.mesh_poop_collision_type()
                    )
                    if (
                        self.bungie_mesh_poop_collision_type
                        != "_connected_geometry_poop_collision_type_none"
                    ):
                        self.bungie_mesh_poop_collision_override_global_material = (
                            bool_str(self.halo.face_global_material)
                        )
                        if (
                            self.bungie_mesh_poop_collision_override_global_material
                            == "1"
                        ):
                            self.bungie_mesh_global_material = (
                                self.halo.face_global_material
                            )

                if self.bungie_mesh_type == "_connected_geometry_mesh_type_poop":
                    self.bungie_mesh_poop_lighting = self.halo.poop_lighting
                    if self.halo.lightmap_resolution_scale:
                        self.bungie_mesh_poop_lightmap_resolution_scale = (
                            self.halo.lightmap_resolution_scale
                        )
                    self.bungie_mesh_poop_pathfinding = self.halo.poop_pathfinding
                    self.bungie_mesh_poop_imposter_policy = (
                        self.halo.poop_imposter_policy
                    )
                    if (
                        self.bungie_mesh_poop_imposter_policy
                        != "_connected_poop_instance_imposter_policy_never"
                        and not self.halo.poop_imposter_transition_distance_auto
                    ):
                        self.bungie_mesh_poop_imposter_transition_distance = (
                            self.halo.poop_imposter_transition_distance
                        )
                    # self.bungie_mesh_poop_fade_range_start = self.mesh_poop_fade_range_start()
                    # self.bungie_mesh_poop_fade_range_end = self.mesh_poop_fade_range_end()

                    # This needs to be Reach only otherwise tool complains. However, the flag is still in use in the UI as it is instead used to set instanced collision type to none
                    if (
                        not self.not_bungie_game
                        and self.halo.face_mode
                        == "_connected_geometry_face_mode_render_only"
                    ):
                        self.bungie_mesh_poop_is_render_only = "1"

                    if self.halo.poop_chops_portals:
                        self.bungie_mesh_poop_chops_portals = (
                            self.halo.poop_chops_portals
                        )
                    if self.halo.poop_does_not_block_aoe:
                        self.bungie_mesh_poop_does_not_block_aoe = (
                            self.halo.poop_does_not_block_aoe
                        )
                    if self.halo.poop_excluded_from_lightprobe:
                        self.bungie_mesh_poop_excluded_from_lightprobe = (
                            self.halo.poop_excluded_from_lightprobe
                        )
                    if self.halo.poop_decal_spacing:
                        self.bungie_mesh_poop_decal_spacing = (
                            self.halo.poop_decal_spacing
                        )

                    # self.bungie_mesh_poop_predominant_shader_name = self.mesh_poop_predominant_shader_name()
                    # self.bungie_mesh_poop_light_channel_flags = self.mesh_poop_light_channel_flags()
                    # H4 only
                    if self.not_bungie_game:
                        if (
                            self.bungie_mesh_poop_imposter_policy
                            != "_connected_poop_instance_imposter_policy_never"
                        ):
                            self.bungie_mesh_poop_imposter_brightness = (
                                self.halo.poop_imposter_brightness
                            )
                            self.bungie_mesh_poop_streamingpriority = (
                                self.halo.poop_streaming_priority
                            )

                            self.bungie_mesh_poop_cinema_only = (
                                self.mesh_poop_cinema_only()
                            )
                            self.bungie_mesh_poop_exclude_from_cinema = (
                                self.mesh_poop_exclude_from_cinema()
                            )

                            if self.halo.poop_remove_from_shadow_geometry:
                                self.bungie_mesh_poop_remove_from_shadow_geometry = (
                                    self.halo.poop_remove_from_shadow_geometry
                                )

                            if self.halo.poop_disallow_lighting_samples:
                                self.bungie_mesh_poop_disallow_object_lighting_samples = (
                                    self.halo.poop_disallow_lighting_samples
                                )

        elif self.bungie_mesh_type == "_connected_geometry_mesh_type_physics":
            if (
                self.halo.mesh_primitive_type
                != "_connected_geometry_primitive_type_none"
            ):
                self.bungie_mesh_primitive_type = self.halo.mesh_primitive_type
                if (
                    self.bungie_mesh_primitive_type
                    == "_connected_geometry_primitive_type_box"
                ):
                    self.bungie_mesh_primitive_box_length = (
                        self.mesh_primitive_box_length()
                    )
                    self.bungie_mesh_primitive_box_width = (
                        self.mesh_primitive_box_width()
                    )
                    self.bungie_mesh_primitive_box_height = (
                        self.mesh_primitive_box_height()
                    )
                elif (
                    self.bungie_mesh_primitive_type
                    == "_connected_geometry_primitive_type_pill"
                ):
                    self.bungie_mesh_primitive_pill_radius = (
                        self.mesh_primitive_pill_radius()
                    )
                    self.bungie_mesh_primitive_pill_height = (
                        self.mesh_primitive_pill_height()
                    )
                elif (
                    self.bungie_mesh_primitive_type
                    == "_connected_geometry_primitive_type_sphere"
                ):
                    self.bungie_mesh_primitive_sphere_radius = (
                        self.mesh_primitive_sphere_radius()
                    )

        elif self.bungie_mesh_type == "_connected_geometry_mesh_type_portal":
            self.bungie_mesh_portal_type = self.halo.portal_type
            if self.halo.portal_ai_deafening:
                self.bungie_mesh_portal_ai_deafening = self.halo.portal_ai_deafening
            if self.halo.portal_blocks_sounds:
                self.bungie_mesh_portal_blocks_sound = self.halo.portal_blocks_sounds
            if self.halo.portal_is_door:
                self.bungie_mesh_portal_is_door = self.halo.portal_is_door

        elif self.bungie_mesh_type == "_connected_geometry_mesh_type_decorator":
            self.bungie_mesh_decorator_lod = self.halo.decorator_lod
            self.bungie_mesh_decorator_name = dot_partition(self.name)

        elif self.bungie_mesh_type == "_connected_geometry_mesh_type_seam":
            self.bungie_mesh_seam_associated_bsp = (
                f"{self.asset_name}_{self.halo.bsp_name}"
            )

        elif (
            self.bungie_mesh_type
            == "_connected_geometry_mesh_type_water_physics_volume"
        ):
            self.bungie_mesh_water_volume_depth = self.halo.water_volume_depth
            self.bungie_mesh_water_volume_flow_direction = (
                self.halo.water_volume_flow_direction
            )
            self.bungie_mesh_water_volume_flow_velocity = (
                self.halo.water_volume_flow_velocity
            )
            self.bungie_mesh_water_volume_fog_color = self.halo.water_volume_fog_color
            self.bungie_mesh_water_volume_fog_murkiness = (
                self.halo.water_volume_fog_murkiness
            )

        elif self.bungie_mesh_type == "_connected_geometry_mesh_type_planar_fog_volume":
            self.bungie_mesh_fog_name = dot_partition(self.name)
            self.bungie_mesh_fog_appearance_tag = self.halo.fog_appearance_tag
            self.bungie_mesh_fog_volume_depth = self.halo.fog_volume_depth

        elif self.bungie_mesh_type == "_connected_geometry_mesh_type_obb_volume":
            self.bungie_mesh_obb_type = self.halo.obb_volume_type

        # LIGHTMAP PROPERTIES
        if self.halo.lightmap_additive_transparency_active:
            self.bungie_lightmap_transparency_override = "1"
            self.bungie_lightmap_additive_transparency = (
                self.halo.lightmap_additive_transparency
            )
        if self.halo.lightmap_resolution_scale_active:
            self.bungie_lightmap_ignore_default_resolution_scale = "1"
            self.bungie_lightmap_resolution_scale = self.halo.lightmap_resolution_scale
        # self.bungie_lightmap_chart_group = self.lightmap_chart_group()
        # if self.not_bungie_game:
        #     self.bungie_lightmap_photon_fidelity = self.halo.lightmap_photon_fidelity
        if self.halo.lightmap_type_active:
            self.bungie_lightmap_type = self.halo.lightmap_type
        # if self.halo.lightmap_analytical_bounce_modifier_active:
        #     self.bungie_lightmap_analytical_bounce_modifier = self.lightmap_analytical_bounce_modifier()
        # if self.halo.lightmap_general_bounce_modifier_active:
        #     self.bungie_lightmap_general_bounce_modifier = self.lightmap_general_bounce_modifier()
        # self.bungie_lightmap_analytical_absorb_ratio = self.lightmap_analytical_absorb_ratio()
        if self.halo.lightmap_translucency_tint_color_active:
            self.bungie_lightmap_translucency_tint_color = (
                self.halo.lightmap_translucency_tint_color
            )
        if self.halo.lightmap_lighting_from_both_sides_active:
            self.bungie_lightmap_lighting_from_both_sides = "1"
            # if self.not_bungie_game:
            #     self.bungie_mesh_per_vertex_lighting = self.mesh_per_vertex_lighting()
        # EMMISSIVE PROPERTIES
        if self.halo.material_lighting_emissive_power:
            self.bungie_lighting_emissive_power = (
                self.halo.material_lighting_emissive_power
            )
            if self.halo.material_lighting_attenuation_cutoff:
                self.bungie_lighting_attenuation_cutoff = (
                    self.halo.material_lighting_attenuation_cutoff
                )
                self.bungie_lighting_attenuation_enabled = "1"
            if self.halo.material_lighting_attenuation_falloff:
                self.bungie_lighting_attenuation_falloff = (
                    self.halo.material_lighting_attenuation_falloff
                )
                self.bungie_lighting_attenuation_enabled = "1"
            if self.halo.material_lighting_emissive_focus:
                self.bungie_lighting_emissive_focus = (
                    self.halo.material_lighting_emissive_focus
                )
            if self.halo.material_lighting_emissive_color:
                self.bungie_lighting_emissive_color = (
                    self.halo.material_lighting_emissive_color
                )
            if self.halo.material_lighting_emissive_per_unit:
                self.bungie_lighting_emissive_per_unit = (
                    self.halo.material_lighting_emissive_per_unit
                )
            if self.halo.material_lighting_emissive_quality:
                self.bungie_lighting_emissive_quality = (
                    self.halo.material_lighting_emissive_quality
                )
            if self.halo.material_lighting_use_shader_gel:
                self.bungie_lighting_use_shader_gel = (
                    self.halo.material_lighting_use_shader_gel
                )
            if self.halo.material_lighting_bounce_ratio:
                self.bungie_lighting_bounce_ratio = (
                    self.halo.material_lighting_bounce_ratio
                )

        self.cleanup()

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

    def mesh_poop_cinema_only(self):
        return bool_str(
            self.halo.poop_cinematic_properties == "bungie_mesh_poop_cinema_only"
        )

    def mesh_poop_exclude_from_cinema(self):
        return bool_str(
            self.halo.poop_cinematic_properties
            == "bungie_mesh_poop_exclude_from_cinema"
        )

    def mesh_use_uncompressed_verts(self):
        if self.bungie_mesh_type in (
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_poop",
            "_connected_geometry_mesh_type_object_instance",
        ):
            if (
                "_connected_geometry_mesh_type_default"
                and self.sidecar_type == "SCENARIO"
            ):
                return "0"
            else:
                return "1"
        else:
            return "0"

    def mesh_per_vertex_lighting(self):
        return bool_str(
            self.halo.lightmap_type == "_connected_material_lightmap_type_per_vertex"
        )

    def mesh_poop_collision_type(self):
        if self.halo.face_mode == "_connected_geometry_face_mode_render_only":
            return "_connected_geometry_poop_collision_type_none"
        elif (
            self.halo.face_mode == "_connected_geometry_face_mode_sphere_collision_only"
        ):
            return "_connected_geometry_poop_collision_type_play_collision"
        elif self.halo.mesh_type == "_connected_geometry_mesh_type_poop_collision":
            return self.halo.poop_collision_type
        else:
            return "_connected_geometry_poop_collision_type_default"

    def lightmap_photon_fidelity(self):
        return self.halo.lightmap_photon_fidelity

    def lightmap_analytical_bounce_modifier(self):
        return jstr(self.halo.lightmap_analytical_bounce_modifier)

    def lightmap_general_bounce_modifier(self):
        return jstr(self.halo.lightmap_general_bounce_modifier)

    def lightmap_lighting_from_both_sides(self):
        return bool_str(self.halo.lightmap_lighting_from_both_sides)


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
        if self.halo.shader_path == "":
            return "override"
        else:
            return clean_tag_path(self.halo.shader_path, "")

    def shader_type(self):
        if self.halo.shader_path == "":
            return "override"
        elif not_bungie_game():
            return "material"
        else:
            shader_type = self.halo.shader_path.rpartition(".")[2]
            if "." + shader_type in shader_exts:
                return shader_type
            return "shader"

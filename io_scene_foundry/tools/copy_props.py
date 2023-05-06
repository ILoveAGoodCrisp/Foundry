# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2022 Crisp
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

from io_scene_foundry.utils.nwo_utils import all_prefixes

def CopyProps(report, template, targets):
    # Apply prefixes from template object
    template_name = template.name
    template_prefix = ''
    for prefix in all_prefixes:
        if template_name.startswith(prefix):
            template_prefix = prefix
    for ob in targets:
        if ob != template:
            target_name = ob.name
            for prefix in all_prefixes:
                target_name = target_name.replace(prefix, '')
        
            target_name = template_prefix + target_name
            ob.name = target_name

    # Apply halo properties to target objects
    template_props = template.nwo
    target_count = 0
    for ob in targets:
        if ob != template:
            target_count += 1
            target_props = ob.nwo

            target_props.object_type_items_all = template_props.object_type_items_all
            target_props.object_type_items_no_mesh = template_props.object_type_items_no_mesh
            target_props.object_type_all = template_props.object_type_all
            target_props.object_type_no_mesh = template_props.object_type_no_mesh
            target_props.bsp_name = template_props.bsp_name
            target_props.bsp_shared = template_props.bsp_shared
            target_props.objectmesh_type = template_props.objectmesh_type
            target_props.mesh_primitive_type = template_props.mesh_primitive_type
            target_props.mesh_tesselation_density = template_props.mesh_tesselation_density
            target_props.mesh_compression = template_props.mesh_compression
            target_props.face_type = template_props.face_type
            target_props.face_mode = template_props.face_mode
            target_props.face_sides = template_props.face_sides
            target_props.face_draw_distance = template_props.face_draw_distance
            target_props.region_name = template_props.region_name
            target_props.permutation_name = template_props.permutation_name
            target_props.face_global_material = template_props.face_global_material
            target_props.sky_permutation_index = template_props.sky_permutation_index
            target_props.conveyor = template_props.conveyor
            target_props.ladder = template_props.ladder
            target_props.slip_surface = template_props.slip_surface
            target_props.decal_offset = template_props.decal_offset
            target_props.group_transparents_by_plane = template_props.group_transparents_by_plane
            target_props.no_shadow = template_props.no_shadow
            target_props.precise_position = template_props.precise_position
            target_props.boundary_surface_name = template_props.boundary_surface_name
            target_props.boundary_surface_type = template_props.boundary_surface_type
            target_props.poop_lighting_override = template_props.poop_lighting_override
            target_props.poop_pathfinding_override = template_props.poop_pathfinding_override
            target_props.poop_imposter_policy = template_props.poop_imposter_policy
            target_props.poop_imposter_transition_distance = template_props.poop_imposter_transition_distance
            target_props.poop_imposter_transition_distance_auto = template_props.poop_imposter_transition_distance_auto
            target_props.poop_render_only = template_props.poop_render_only
            target_props.poop_chops_portals = template_props.poop_chops_portals
            target_props.poop_does_not_block_aoe = template_props.poop_does_not_block_aoe
            target_props.poop_excluded_from_lightprobe = template_props.poop_excluded_from_lightprobe
            target_props.poop_decal_spacing = template_props.poop_decal_spacing
            target_props.poop_precise_geometry = template_props.poop_precise_geometry
            target_props.poop_collision_type = template_props.poop_collision_type
            target_props.portal_type = template_props.portal_type
            target_props.portal_ai_deafening = template_props.portal_ai_deafening
            target_props.portal_blocks_sounds = template_props.portal_blocks_sounds
            target_props.portal_is_door = template_props.portal_is_door
            target_props.decorator_name = template_props.decorator_name
            target_props.decorator_lod = template_props.decorator_lod
            target_props.water_volume_depth = template_props.water_volume_depth
            target_props.water_volume_flow_direction = template_props.water_volume_flow_direction
            target_props.water_volume_flow_velocity = template_props.water_volume_flow_velocity
            target_props.water_volume_fog_color = template_props.water_volume_fog_color
            target_props.water_volume_fog_murkiness = template_props.water_volume_fog_murkiness
            target_props.fog_name = template_props.fog_name
            target_props.fog_appearance_tag = template_props.fog_appearance_tag
            target_props.fog_volume_depth = template_props.fog_volume_depth
            target_props.lightmap_settings_enabled = template_props.lightmap_settings_enabled
            target_props.lightmap_additive_transparency = template_props.lightmap_additive_transparency
            target_props.lightmap_ignore_default_resolution_scale = template_props.lightmap_ignore_default_resolution_scale
            target_props.lightmap_resolution_scale = template_props.lightmap_resolution_scale
            target_props.lightmap_type = template_props.lightmap_type
            target_props.lightmap_transparency_override = template_props.lightmap_transparency_override
            target_props.lightmap_analytical_bounce_modifier = template_props.lightmap_analytical_bounce_modifier
            target_props.lightmap_general_bounce_modifier = template_props.lightmap_general_bounce_modifier
            target_props.lightmap_translucency_tint_color = template_props.lightmap_translucency_tint_color
            target_props.lightmap_lighting_from_both_sides = template_props.lightmap_lighting_from_both_sides
            target_props.material_lighting_enabled = template_props.material_lighting_enabled
            target_props.material_lighting_attenuation_cutoff = template_props.material_lighting_attenuation_cutoff
            target_props.material_lighting_attenuation_falloff = template_props.material_lighting_attenuation_falloff
            target_props.material_lighting_emissive_focus = template_props.material_lighting_emissive_focus
            target_props.material_lighting_emissive_color = template_props.material_lighting_emissive_color
            target_props.material_lighting_emissive_per_unit = template_props.material_lighting_emissive_per_unit
            target_props.material_lighting_emissive_power = template_props.material_lighting_emissive_power
            target_props.material_lighting_emissive_quality = template_props.material_lighting_emissive_quality
            target_props.material_lighting_use_shader_gel = template_props.material_lighting_use_shader_gel
            target_props.material_lighting_bounce_ratio = template_props.material_lighting_bounce_ratio
            target_props.objectmarker_type = template_props.objectmarker_type
            target_props.marker_region = template_props.marker_region
            target_props.marker_all_regions = template_props.marker_all_regions
            target_props.marker_game_instance_tag_name = template_props.marker_game_instance_tag_name
            target_props.marker_game_instance_tag_variant_name = template_props.marker_game_instance_tag_variant_name
            target_props.marker_velocity = template_props.marker_velocity
            target_props.marker_pathfinding_sphere_vehicle = template_props.marker_pathfinding_sphere_vehicle
            target_props.pathfinding_sphere_remains_when_open = template_props.pathfinding_sphere_remains_when_open
            target_props.pathfinding_sphere_with_sectors = template_props.pathfinding_sphere_with_sectors
            target_props.physics_constraint_parent = template_props.physics_constraint_parent
            target_props.physics_constraint_child = template_props.physics_constraint_child
            target_props.physics_constraint_type = template_props.physics_constraint_type
            target_props.physics_constraint_uses_limits = template_props.physics_constraint_uses_limits
            target_props.hinge_constraint_minimum = template_props.hinge_constraint_minimum
            target_props.hinge_constraint_maximum = template_props.hinge_constraint_maximum
            target_props.cone_angle = template_props.cone_angle
            target_props.plane_constraint_minimum = template_props.plane_constraint_minimum
            target_props.plane_constraint_maximum = template_props.plane_constraint_maximum
            target_props.twist_constraint_start = template_props.twist_constraint_start
            target_props.twist_constraint_end = template_props.twist_constraint_end
            target_props.light_type_override = template_props.light_type_override
            target_props.light_game_type = template_props.light_game_type
            target_props.light_shape = template_props.light_shape
            target_props.light_near_attenuation = template_props.light_near_attenuation
            target_props.light_far_attenuation = template_props.light_far_attenuation
            target_props.light_near_attenuation_start = template_props.light_near_attenuation_start
            target_props.light_near_attenuation_end = template_props.light_near_attenuation_end
            target_props.light_far_attenuation_start = template_props.light_far_attenuation_start
            target_props.light_far_attenuation_end = template_props.light_far_attenuation_end
            target_props.light_volume_distance = template_props.light_volume_distance
            target_props.light_volume_intensity = template_props.light_volume_intensity
            target_props.light_fade_start_distance = template_props.light_fade_start_distance
            target_props.light_fade_end_distance = template_props.light_fade_end_distance
            target_props.light_ignore_bsp_visibility = template_props.light_ignore_bsp_visibility
            target_props.light_color = template_props.light_color
            target_props.light_intensity = template_props.light_intensity
            target_props.light_use_clipping = template_props.light_use_clipping
            target_props.light_clipping_size_x_pos = template_props.light_clipping_size_x_pos
            target_props.light_clipping_size_y_pos = template_props.light_clipping_size_y_pos
            target_props.light_clipping_size_z_pos = template_props.light_clipping_size_z_pos
            target_props.light_clipping_size_x_neg = template_props.light_clipping_size_x_neg
            target_props.light_clipping_size_y_neg = template_props.light_clipping_size_y_neg
            target_props.light_clipping_size_z_neg = template_props.light_clipping_size_z_neg
            target_props.light_hotspot_size = template_props.light_hotspot_size
            target_props.light_hotspot_falloff = template_props.light_hotspot_falloff
            target_props.light_falloff_shape = template_props.light_falloff_shape
            target_props.light_aspect = template_props.light_aspect
            target_props.light_frustum_width = template_props.light_frustum_width
            target_props.light_frustum_height = template_props.light_frustum_height
            target_props.light_bounce_ratio = template_props.light_bounce_ratio
            target_props.light_dynamic_has_bounce = template_props.light_dynamic_has_bounce
            target_props.light_screenspace_has_specular = template_props.light_screenspace_has_specular
            target_props.light_tag_override = template_props.light_tag_override
            target_props.light_shader_reference = template_props.light_shader_reference
            target_props.light_gel_reference = template_props.light_gel_reference
            target_props.light_lens_flare_reference = template_props.light_lens_flare_reference


    report({'INFO'}, f"Copied properties from {template_name} to {target_count} target objects")
    return {'FINISHED'}

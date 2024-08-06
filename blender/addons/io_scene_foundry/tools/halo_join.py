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

import bpy


class NWO_JoinHalo(bpy.types.Operator):
    bl_idname = "nwo.join_halo"
    bl_label = "Join two or more halo mesh objects"
    bl_description = "Joins objects and face layer properties"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def update_layer_props(self, new_layer, old_layer):
        new_layer.name = old_layer.name
        new_layer.layer_name = old_layer.layer_name
        new_layer.face_count = old_layer.face_count
        new_layer.layer_color = old_layer.layer_color
        new_layer.face_type_override = old_layer.face_type_override
        new_layer.face_mode_override = old_layer.face_mode_override
        new_layer.face_two_sided_override = old_layer.face_two_sided_override
        new_layer.face_draw_distance_override = old_layer.face_draw_distance_override
        new_layer.texcoord_usage_override = old_layer.texcoord_usage_override
        new_layer.region_name_override = old_layer.region_name_override
        new_layer.is_pca_override = old_layer.is_pca_override
        new_layer.face_global_material_override = (
            old_layer.face_global_material_override
        )
        new_layer.sky_permutation_index_override = (
            old_layer.sky_permutation_index_override
        )
        new_layer.ladder_override = old_layer.ladder_override
        new_layer.slip_surface_override = old_layer.slip_surface_override
        new_layer.decal_offset_override = old_layer.decal_offset_override
        new_layer.group_transparents_by_plane_override = (
            old_layer.group_transparents_by_plane_override
        )
        new_layer.no_shadow_override = old_layer.no_shadow_override
        new_layer.precise_position_override = old_layer.precise_position_override
        new_layer.no_lightmap_override = old_layer.no_lightmap_override
        new_layer.no_pvs_override = old_layer.no_pvs_override
        new_layer.lightmap_additive_transparency_override = (
            old_layer.lightmap_additive_transparency_override
        )
        new_layer.lightmap_resolution_scale_override = (
            old_layer.lightmap_resolution_scale_override
        )
        new_layer.lightmap_type_override = old_layer.lightmap_type_override
        new_layer.lightmap_analytical_bounce_modifier_override = (
            old_layer.lightmap_analytical_bounce_modifier_override
        )
        new_layer.lightmap_general_bounce_modifier_override = (
            old_layer.lightmap_general_bounce_modifier_override
        )
        new_layer.lightmap_translucency_tint_color_override = (
            old_layer.lightmap_translucency_tint_color_override
        )
        new_layer.lightmap_lighting_from_both_sides_override = (
            old_layer.lightmap_lighting_from_both_sides_override
        )
        new_layer.emissive_override = old_layer.emissive_override
        new_layer.face_type_ui = old_layer.face_type_ui
        new_layer.face_mode_ui = old_layer.face_mode_ui
        new_layer.face_sides_ui = old_layer.face_sides_ui
        new_layer.face_two_sided = old_layer.face_two_sided
        new_layer.face_draw_distance = old_layer.face_draw_distance
        new_layer.texcoord_usage_ui = old_layer.texcoord_usage_ui
        new_layer.region_name = old_layer.region_name
        new_layer.face_global_material = old_layer.face_global_material
        new_layer.sky_permutation_index_ui = old_layer.sky_permutation_index_ui
        new_layer.ladder = old_layer.ladder
        new_layer.slip_surface = old_layer.slip_surface
        new_layer.decal_offset = old_layer.decal_offset
        new_layer.group_transparents_by_plane_ui = (
            old_layer.group_transparents_by_plane_ui
        )
        new_layer.no_shadow = old_layer.no_shadow
        new_layer.precise_position = old_layer.precise_position
        new_layer.no_lightmap = old_layer.no_lightmap
        new_layer.no_pvs = old_layer.no_pvs
        new_layer.lightmap_additive_transparency = (
            old_layer.lightmap_additive_transparency
        )
        new_layer.lightmap_resolution_scale = old_layer.lightmap_resolution_scale
        new_layer.lightmap_photon_fidelity = old_layer.lightmap_photon_fidelity
        new_layer.lightmap_type = old_layer.lightmap_type
        new_layer.lightmap_analytical_bounce_modifier = (
            old_layer.lightmap_analytical_bounce_modifier
        )
        new_layer.lightmap_general_bounce_modifier = (
            old_layer.lightmap_general_bounce_modifier
        )
        new_layer.lightmap_translucency_tint_color = (
            old_layer.lightmap_translucency_tint_color
        )
        new_layer.lightmap_lighting_from_both_sides = (
            old_layer.lightmap_lighting_from_both_sides
        )
        new_layer.material_lighting_attenuation_cutoff = (
            old_layer.material_lighting_attenuation_cutoff
        )
        new_layer.material_lighting_attenuation_falloff = (
            old_layer.material_lighting_attenuation_falloff
        )
        new_layer.material_lighting_emissive_focus = (
            old_layer.material_lighting_emissive_focus
        )
        new_layer.material_lighting_emissive_color = (
            old_layer.material_lighting_emissive_color
        )
        new_layer.material_lighting_emissive_per_unit = (
            old_layer.material_lighting_emissive_per_unit
        )
        new_layer.material_lighting_emissive_power = (
            old_layer.material_lighting_emissive_power
        )
        new_layer.material_lighting_emissive_quality = (
            old_layer.material_lighting_emissive_quality
        )
        new_layer.material_lighting_use_shader_gel = (
            old_layer.material_lighting_use_shader_gel
        )
        new_layer.material_lighting_bounce_ratio = (
            old_layer.material_lighting_bounce_ratio
        )

    def execute(self, context):
        active_ob = context.view_layer.objects.active
        active_nwo = active_ob.data.nwo
        active_face_props = active_nwo.face_props

        face_layers = []
        non_active_objects = [ob for ob in context.selected_objects if ob != active_ob]
        for ob in non_active_objects:
            for layer in ob.data.nwo.face_props:
                if layer not in face_layers:
                    face_layers.append(layer)

        # active_face_props.clear()
        for old_layer in face_layers:
            bpy.ops.uilist.entry_add(
                list_path="object.data.nwo.face_props",
                active_index_path="object.data.nwo.face_props_active_index",
            )
            new_layer = active_face_props[active_nwo.face_props_active_index]
            self.update_layer_props(new_layer, old_layer)

        bpy.ops.object.join()

        return {"FINISHED"}

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

from .templates import NWO_Op, NWO_Op_Path, NWO_PropPanel, poll_ui
from ..utils.nwo_utils import (
    bpy_enum_list,
    export_objects,
    export_objects_no_arm,
    is_linked,
    not_bungie_game,
    sort_alphanum,
    true_bsp,
    true_permutation,
    true_region,
)
import bpy
from bpy.types import Menu, UIList
from bpy.props import EnumProperty, StringProperty


# FACE LEVEL FACE PROPS


class NWO_UL_FaceMapProps(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            if item:
                layout.prop(
                    item, "name", text="", emboss=False, icon_value=495
                )
            else:
                layout.label(text="", translate=False, icon_value=icon)
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)


class NWO_MeshFaceProps(NWO_PropPanel):
    bl_label = "Mesh Properties"
    bl_idname = "NWO_PT_MeshFaceDetailsPanel"
    bl_parent_id = "NWO_PT_ObjectDetailsPanel"

    @classmethod
    def poll(cls, context):
        ob = context.object
        valid_mesh_types = (
            "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_physics",
            "_connected_geometry_mesh_type_structure",
            "_connected_geometry_mesh_type_render",
            "_connected_geometry_mesh_type_poop",
        )
        return (
            ob
            and ob.nwo.export_this
            and ob.nwo.object_type_ui == "_connected_geometry_object_type_mesh"
            and ob.nwo.mesh_type_ui in valid_mesh_types
        )

    def draw_header(self, context):
        self.layout.label(text="")

    def draw(self, context):
        layout = self.layout
        ob = context.object
        ob_nwo = ob.nwo
        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        # Master Instance button since facemaps aren't stored in mesh data
        if is_linked(ob):
            row = layout.row()
            if ob.data.nwo.master_instance == ob:
                row.label(
                    text=f"Object is the Master Instance for mesh: {ob.data.name}"
                )
            else:
                row.operator("nwo.master_instance")
                row = layout.row()
                row.label(
                    text=f"Object is Child Instance for mesh: {ob.data.name}"
                )

        # if is_poop:
        #     flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        #     col = flow.column()
        #     op_bullet_collision = True
        #     op_player_collision = True
        #     op_cookie_cutter = True
        #     for item in ob_nwo.face_props:
        #         if item.instanced_collision_override:
        #             op_bullet_collision = False
        #             break
        #     for item in ob_nwo.face_props:
        #         if item.instanced_physics_override:
        #             op_player_collision = False
        #             break
        #     for item in ob_nwo.face_props:
        #         if item.cookie_cutter_override:
        #             op_cookie_cutter = False
        #             break

        #     row = col.grid_flow()
        #     if op_bullet_collision:
        #         row.operator("nwo.add_face_property_new", text="Collision", icon='ADD').options = "instanced_collision"
        #     if op_player_collision:
        #         row.operator("nwo.add_face_property_new", text="Physics", icon='ADD').options = "instanced_physics"
        #     if op_cookie_cutter:
        #         row.operator("nwo.add_face_property_new", text="Cookie Cutter", icon='ADD').options = "cookie_cutter"

        # MESH LEVEL PROPERTIES
        # --------------------------------
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        row = col.row()
        if poll_ui(("MODEL", "SKY", "DECORATOR SET")):
            if ob_nwo.region_name_locked_ui != "":
                col.prop(ob_nwo, "region_name_locked_ui", text="Region")
            else:
                row = col.row(align=True)
                row.prop(ob_nwo, "region_name_ui", text="Region")
                row.operator_menu_enum(
                    "nwo.region_list", "region", text="", icon="DOWNARROW_HLT"
                )
                # if ob.nwo.face_props and ob_nwo.mesh_type_ui in ('_connected_geometry_mesh_type_object_render', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics'):
                #     for prop in ob.nwo.face_props:
                #         if prop.region_name_override:
                #             row.label(text='*')
                #             break
        if poll_ui(("MODEL", "SCENARIO", "PREFAB")):
            if ob_nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_poop_collision",
                "_connected_geometry_mesh_type_structure",
            ):
                row = col.row()
                row.prop(
                    ob_nwo,
                    "face_global_material_ui",
                    text="Collision Material",
                )
                row.menu(
                    NWO_GlobalMaterialMenu.bl_idname,
                    text="",
                    icon="DOWNARROW_HLT",
                )
                # if ob.nwo.face_props and ob_nwo.mesh_type_ui in ('_connected_geometry_mesh_type_object_poop', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_object_structure'):
                #     for prop in ob.nwo.face_props:
                #         if prop.face_global_material_override:
                #             row.label(text='*')
                #             break

        if poll_ui(("MODEL", "SCENARIO", "PREFAB")):
            if ob_nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_render",
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_structure",
            ):
                col2 = col.column()
                flow2 = col2.grid_flow()
                flow2.prop(ob_nwo, "precise_position_ui", text="Uncompressed")

        if ob_nwo.mesh_type_ui in (
            "_connected_geometry_mesh_type_render",
            "_connected_geometry_mesh_type_poop",
            "_connected_geometry_mesh_type_poop_collision",
            "_connected_geometry_mesh_type_collision",
        ):
            col3 = col.column()
            flow3 = col3.grid_flow()
            flow3.prop(ob_nwo, "face_two_sided_ui")

        if poll_ui(("SCENARIO", "PREFAB")):
            if ob_nwo.face_mode_active:
                row = col.row()
                row.prop(ob_nwo, "face_mode_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "face_mode"
            if ob_nwo.face_sides_active:
                row = col.row()
                row.prop(ob_nwo, "face_sides_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "face_sides"
            if ob_nwo.face_draw_distance_active:
                row = col.row()
                row.prop(ob_nwo, "face_draw_distance_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "face_draw_distance"
            if ob_nwo.texcoord_usage_active:
                row = col.row()
                row.prop(ob_nwo, "texcoord_usage_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "texcoord_usage"
            if ob_nwo.ladder_active:
                row = col.row()
                row.prop(ob_nwo, "ladder_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "ladder"
            if ob_nwo.slip_surface_active:
                row = col.row()
                row.prop(ob_nwo, "slip_surface_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "slip_surface"
            if ob_nwo.decal_offset_active:
                row = col.row()
                row.prop(ob_nwo, "decal_offset_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "decal_offset"
            if ob_nwo.group_transparents_by_plane_active:
                row = col.row()
                row.prop(ob_nwo, "group_transparents_by_plane_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "group_transparents_by_plane"
            if ob_nwo.no_shadow_active:
                row = col.row()
                row.prop(ob_nwo, "no_shadow_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "no_shadow"
            if ob_nwo.precise_position_active:
                row = col.row()
                row.prop(ob_nwo, "precise_position_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "precise_position"
            if ob_nwo.no_lightmap_active:
                row = col.row()
                row.prop(ob_nwo, "no_lightmap_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "no_lightmap"
            if ob_nwo.no_pvs_active:
                row = col.row()
                row.prop(ob_nwo, "no_pvs_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "no_pvs"
            # lightmap
            if ob_nwo.lightmap_additive_transparency_active:
                row = col.row()
                row.prop(
                    ob_nwo,
                    "lightmap_additive_transparency_ui",
                    text="Lightmap Additive Transparency",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_additive_transparency"
            if ob_nwo.lightmap_resolution_scale_active:
                row = col.row()
                row.prop(
                    ob_nwo,
                    "lightmap_resolution_scale_ui",
                    text="Lightmap Resolution Scale",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_resolution_scale"
            if ob_nwo.lightmap_type_active:
                row = col.row()
                row.prop(ob_nwo, "lightmap_type_ui", text="Lightmap Type")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_type"
            if ob_nwo.lightmap_analytical_bounce_modifier_active:
                row = col.row()
                row.prop(
                    ob_nwo,
                    "lightmap_analytical_bounce_modifier_ui",
                    text="Analytical Bounce Modifier",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_analytical_bounce_modifier"
            if ob_nwo.lightmap_general_bounce_modifier_active:
                row = col.row()
                row.prop(
                    ob_nwo,
                    "lightmap_general_bounce_modifier_ui",
                    text="General Bounce Modifier",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_general_bounce_modifier"
            if ob_nwo.lightmap_translucency_tint_color_active:
                row = col.row()
                row.prop(
                    ob_nwo,
                    "lightmap_translucency_tint_color_ui",
                    text="Translucency Tint Color",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_translucency_tint_color"
            if ob_nwo.lightmap_lighting_from_both_sides_active:
                row = col.row()
                row.prop(
                    ob_nwo,
                    "lightmap_lighting_from_both_sides_ui",
                    text="Lighting From Both Sides",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_lighting_from_both_sides"

            if ob_nwo.face_type_active:
                if ob_nwo.face_type_ui == "_connected_geometry_face_type_sky":
                    col.separator()
                    box = col.box()
                    row = box.row()
                    row.label(text="Face Type Settings")
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "face_type"
                    row = box.row()
                    row.prop(ob_nwo, "face_type_ui")
                    row = box.row()
                    row.prop(ob_nwo, "sky_permutation_index_ui")
                else:
                    row = col.row()
                    row.prop(ob_nwo, "face_type_ui")
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "face_type"
            # material lighting
            if ob_nwo.emissive_active:
                col.separator()
                box = col.box()
                row = box.row()
                row.label(text="Emissive Settings")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "emissive"
                row = box.row()
                row.prop(
                    ob_nwo, "material_lighting_emissive_color_ui", text="Color"
                )
                row = box.row()
                row.prop(
                    ob_nwo, "material_lighting_emissive_power_ui", text="Power"
                )
                row = box.row()
                row.prop(
                    ob_nwo,
                    "material_lighting_emissive_quality_ui",
                    text="Quality",
                )
                row = box.row()
                row.prop(
                    ob_nwo, "material_lighting_emissive_focus_ui", text="Focus"
                )
                row = box.row()
                row.prop(
                    ob_nwo,
                    "material_lighting_attenuation_falloff_ui",
                    text="Attenutation Falloff",
                )
                row = box.row()
                row.prop(
                    ob_nwo,
                    "material_lighting_attenuation_cutoff_ui",
                    text="Attenutation Cutoff",
                )
                row = box.row()
                row.prop(
                    ob_nwo,
                    "material_lighting_bounce_ratio_ui",
                    text="Bounce Ratio",
                )
                row = box.row()
                row.prop(
                    ob_nwo,
                    "material_lighting_use_shader_gel_ui",
                    text="Shader Gel",
                )
                row = box.row()
                row.prop(
                    ob_nwo,
                    "material_lighting_emissive_per_unit_ui",
                    text="Emissive Per Unit",
                )

            col.menu(NWO_MeshPropAddMenu.bl_idname, text="", icon="PLUS")

        # FACE LEVEL PROPERTIES
        # --------------------------------


def toggle_override(context, option, bool_var):
    ob = context.object
    me = ob.data
    ob_nwo = me.nwo
    try:
        item = ob_nwo.face_props[ob.face_maps.active.name]
    except:
        item = ob_nwo.face_props[ob.face_maps.active_index]

    match option:
        case "seam":
            item.seam_override = bool_var
        case "region":
            item.region_name_override = bool_var
        case "face_type":
            item.face_type_override = bool_var
        case "face_mode":
            item.face_mode_override = bool_var
        case "face_sides":
            item.face_sides_override = bool_var
        case "_connected_geometry_face_type_sky":
            item.face_type_override = bool_var
            item.face_type = "_connected_geometry_face_type_sky"
        case "_connected_geometry_face_type_seam_sealer":
            item.face_type_override = bool_var
            item.face_type = "_connected_geometry_face_type_seam_sealer"
        case "_connected_geometry_face_mode_render_only":
            item.face_mode_override = bool_var
            item.face_mode = "_connected_geometry_face_mode_render_only"
        case "_connected_geometry_face_mode_collision_only":
            item.face_mode_override = bool_var
            item.face_mode = "_connected_geometry_face_mode_collision_only"
        case "_connected_geometry_face_mode_sphere_collision_only":
            item.face_mode_override = bool_var
            item.face_mode = (
                "_connected_geometry_face_mode_sphere_collision_only"
            )
        case "_connected_geometry_face_mode_shadow_only":
            item.face_mode_override = bool_var
            item.face_mode = "_connected_geometry_face_mode_shadow_only"
        case "_connected_geometry_face_mode_lightmap_only":
            item.face_mode_override = bool_var
            item.face_mode = "_connected_geometry_face_mode_lightmap_only"
        case "_connected_geometry_face_mode_breakable":
            item.face_mode_override = bool_var
            item.face_mode = "_connected_geometry_face_mode_breakable"
        case "_connected_geometry_face_sides_one_sided_transparent":
            item.face_sides_override = bool_var
            item.face_sides = (
                "_connected_geometry_face_sides_one_sided_transparent"
            )
        case "_connected_geometry_face_sides_two_sided":
            item.face_sides_override = bool_var
            item.face_sides = "_connected_geometry_face_sides_two_sided"
        case "_connected_geometry_face_sides_two_sided_transparent":
            item.face_sides_override = bool_var
            item.face_sides = (
                "_connected_geometry_face_sides_two_sided_transparent"
            )
        case "_connected_geometry_face_sides_mirror":
            item.face_sides_override = bool_var
            item.face_sides = "_connected_geometry_face_sides_mirror"
        case "_connected_geometry_face_sides_mirror_transparent":
            item.face_sides_override = bool_var
            item.face_sides = (
                "_connected_geometry_face_sides_mirror_transparent"
            )
        case "_connected_geometry_face_sides_keep":
            item.face_sides_override = bool_var
            item.face_sides = "_connected_geometry_face_sides_keep"
        case "_connected_geometry_face_sides_keep_transparent":
            item.face_sides_override = bool_var
            item.face_sides = "_connected_geometry_face_sides_keep_transparent"
        case "face_draw_distance":
            item.face_draw_distance_override = bool_var
        case "texcoord_usage":
            item.texcoord_usage_override = bool_var
        case "face_global_material":
            item.face_global_material_override = bool_var
        case "ladder":
            item.ladder_override = bool_var
        case "slip_surface":
            item.slip_surface_override = bool_var
        case "decal_offset":
            item.decal_offset_override = bool_var
        case "group_transparents_by_plane":
            item.group_transparents_by_plane_override = bool_var
        case "no_shadow":
            item.no_shadow_override = bool_var
        case "precise_position":
            item.precise_position_override = bool_var
        case "no_lightmap":
            item.no_lightmap_override = bool_var
        case "no_pvs":
            item.no_pvs_override = bool_var
        # instances
        case "instanced_collision":
            item.instanced_collision_override = bool_var
        case "instanced_physics":
            item.instanced_physics_override = bool_var
        case "cookie_cutter":
            item.cookie_cutter_override = bool_var
        # lightmap
        case "lightmap_additive_transparency":
            item.lightmap_additive_transparency_override = bool_var
        case "lightmap_resolution_scale":
            item.lightmap_resolution_scale_override = bool_var
        case "lightmap_type":
            item.lightmap_type_override = bool_var
        case "lightmap_analytical_bounce_modifier":
            item.lightmap_analytical_bounce_modifier_override = bool_var
        case "lightmap_general_bounce_modifier":
            item.lightmap_general_bounce_modifier_override = bool_var
        case "lightmap_translucency_tint_color":
            item.lightmap_translucency_tint_color_override = bool_var
        case "lightmap_lighting_from_both_sides":
            item.lightmap_lighting_from_both_sides_override = bool_var
        # material lighting
        case "emissive":
            item.emissive_active = bool_var


class NWO_FaceDefaultsToggle(NWO_Op):
    bl_idname = "nwo.toggle_defaults"
    bl_label = "Toggle Defaults"
    bl_description = "Toggles the default Face Properties display"

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "MESH"
            and context.object.mode in ("OBJECT", "EDIT")
        )

    def execute(self, context):
        context.object.nwo.toggle_face_defaults = (
            not context.object.nwo.toggle_face_defaults
        )

        return {"FINISHED"}


# MESH LEVEL FACE PROPS


def toggle_active(context, option, bool_var):
    ob = context.object
    ob_nwo = ob.nwo

    match option:
        case "face_type":
            ob_nwo.face_type_active = bool_var
        case "face_mode":
            ob_nwo.face_mode_active = bool_var
        case "face_sides":
            ob_nwo.face_sides_active = bool_var
        case "_connected_geometry_face_type_sky":
            ob_nwo.face_type_active = bool_var
            ob_nwo.face_type_ui = "_connected_geometry_face_type_sky"
        case "_connected_geometry_face_type_seam_sealer":
            ob_nwo.face_type_active = bool_var
            ob_nwo.face_type_ui = "_connected_geometry_face_type_seam_sealer"
        case "_connected_geometry_face_mode_render_only":
            ob_nwo.face_mode_active = bool_var
            ob_nwo.face_mode_ui = "_connected_geometry_face_mode_render_only"
        case "_connected_geometry_face_mode_collision_only":
            ob_nwo.face_mode_active = bool_var
            ob_nwo.face_mode_ui = (
                "_connected_geometry_face_mode_collision_only"
            )
        case "_connected_geometry_face_mode_sphere_collision_only":
            ob_nwo.face_mode_active = bool_var
            ob_nwo.face_mode_ui = (
                "_connected_geometry_face_mode_sphere_collision_only"
            )
        case "_connected_geometry_face_mode_shadow_only":
            ob_nwo.face_mode_active = bool_var
            ob_nwo.face_mode_ui = "_connected_geometry_face_mode_shadow_only"
        case "_connected_geometry_face_mode_lightmap_only":
            ob_nwo.face_mode_active = bool_var
            ob_nwo.face_mode_ui = "_connected_geometry_face_mode_lightmap_only"
        case "_connected_geometry_face_mode_breakable":
            ob_nwo.face_mode_active = bool_var
            ob_nwo.face_mode_ui = "_connected_geometry_face_mode_breakable"
        case "_connected_geometry_face_sides_one_sided_transparent":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = (
                "_connected_geometry_face_sides_one_sided_transparent"
            )
        case "_connected_geometry_face_sides_two_sided":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = "_connected_geometry_face_sides_two_sided"
        case "_connected_geometry_face_sides_two_sided_transparent":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = (
                "_connected_geometry_face_sides_two_sided_transparent"
            )
        case "_connected_geometry_face_sides_mirror":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = "_connected_geometry_face_sides_mirror"
        case "_connected_geometry_face_sides_mirror_transparent":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = (
                "_connected_geometry_face_sides_mirror_transparent"
            )
        case "_connected_geometry_face_sides_keep":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = "_connected_geometry_face_sides_keep"
        case "_connected_geometry_face_sides_keep_transparent":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = (
                "_connected_geometry_face_sides_keep_transparent"
            )
        case "face_draw_distance":
            ob_nwo.face_draw_distance_active = bool_var
        case "texcoord_usage":
            ob_nwo.texcoord_usage_active = bool_var
        case "ladder":
            ob_nwo.ladder_active = bool_var
        case "slip_surface":
            ob_nwo.slip_surface_active = bool_var
        case "decal_offset":
            ob_nwo.decal_offset_active = bool_var
        case "group_transparents_by_plane":
            ob_nwo.group_transparents_by_plane_active = bool_var
        case "no_shadow":
            ob_nwo.no_shadow_active = bool_var
        case "precise_position":
            ob_nwo.precise_position_active = bool_var
        case "no_lightmap":
            ob_nwo.no_lightmap_active = bool_var
        case "no_pvs":
            ob_nwo.no_pvs_active = bool_var
        # lightmap
        case "lightmap_additive_transparency":
            ob_nwo.lightmap_additive_transparency_active = bool_var
        case "lightmap_resolution_scale":
            ob_nwo.lightmap_resolution_scale_active = bool_var
        case "lightmap_type":
            ob_nwo.lightmap_type_active = bool_var
        case "lightmap_analytical_bounce_modifier":
            ob_nwo.lightmap_analytical_bounce_modifier_active = bool_var
        case "lightmap_general_bounce_modifier":
            ob_nwo.lightmap_general_bounce_modifier_active = bool_var
        case "lightmap_translucency_tint_color":
            ob_nwo.lightmap_translucency_tint_color_active = bool_var
        case "lightmap_lighting_from_both_sides":
            ob_nwo.lightmap_lighting_from_both_sides_active = bool_var
        # material lighting
        case "emissive":
            ob_nwo.emissive_active = bool_var


class NWO_MeshPropAddMenu(Menu):
    bl_label = "Add Mesh Property"
    bl_idname = "NWO_MT_MeshPropAdd"

    def draw(self, context):
        layout = self.layout
        # if poll_ui(('MODEL', 'SKY', 'DECORATOR SET')):
        #     # layout.operator_menu_enum("nwo.add_mesh_property_face_sides", property="options", text="Sides")
        #     layout.operator_menu_enum("nwo.add_mesh_property_misc", property="options", text="Other")

        if poll_ui(("SCENARIO", "PREFAB")):
            # layout.operator_menu_enum("nwo.add_mesh_property_face_sides", property="options", text="Sides")
            layout.operator(
                "nwo.add_mesh_property", text="Sky"
            ).options = "_connected_geometry_face_type_sky"
            layout.operator(
                "nwo.add_mesh_property", text="Seam Sealer"
            ).options = "_connected_geometry_face_type_seam_sealer"
            layout.operator(
                "nwo.add_mesh_property", text="Emissive"
            ).options = "emissive"
            layout.operator_menu_enum(
                "nwo.add_mesh_property_face_mode",
                property="options",
                text="Mode",
            )
            layout.operator_menu_enum(
                "nwo.add_mesh_property_flags", property="options", text="Flags"
            )
            layout.operator_menu_enum(
                "nwo.add_mesh_property_lightmap",
                property="options",
                text="Lightmap",
            )


class NWO_MeshPropAdd(NWO_Op):
    """Adds a face property that will override face properties set in the mesh"""

    bl_idname = "nwo.add_mesh_property"
    bl_label = "Add"

    @classmethod
    def poll(cls, context):
        return context.object

    options: EnumProperty(
        items=[
            ("emissive", "Emissive", ""),
            ("_connected_geometry_face_type_sky", "Sky", ""),
            ("_connected_geometry_face_type_seam_sealer", "Seam Sealer", ""),
        ]
    )

    def execute(self, context):
        toggle_active(context, self.options, True)
        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_MeshPropRemove(NWO_Op):
    """Removes a mesh property"""

    bl_idname = "nwo.remove_mesh_property"
    bl_label = "Remove"

    options: EnumProperty(
        default="face_type",
        items=[
            ("face_type", "Face Type", ""),
            ("face_mode", "Face Mode", ""),
            ("face_sides", "Face Sides", ""),
            ("face_draw_distance", "Draw Distance", ""),
            ("texcoord_usage", "Texcord Usage", ""),
            ("ladder", "Ladder", ""),
            ("slip_surface", "Slip Surface", ""),
            ("decal_offset", "Decal Offset", ""),
            ("group_transparents_by_plane", "Group Transparents by Plane", ""),
            ("no_shadow", "No Shadow", ""),
            ("precise_position", "Precise Position", ""),
            ("no_lightmap", "No Lightmap", ""),
            ("no_pvs", "No PVS", ""),
            ("lightmap_additive_transparency", "Transparency", ""),
            ("lightmap_resolution_scale", "Resolution Scale", ""),
            ("lightmap_type", "Lightmap Type", ""),
            (
                "lightmap_analytical_bounce_modifier",
                "Analytical Light Bounce Modifier",
                "",
            ),
            (
                "lightmap_general_bounce_modifier",
                "General Light Bounce Modifier",
                "",
            ),
            (
                "lightmap_translucency_tint_color",
                "Translucency Tint Colour",
                "",
            ),
            (
                "lightmap_lighting_from_both_sides",
                "Lighting from Both Sides",
                "",
            ),
            ("emissive", "Emissive", ""),
        ],
    )

    def execute(self, context):
        toggle_active(context, self.options, False)
        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_MeshPropAddFaceMode(NWO_MeshPropAdd):
    bl_idname = "nwo.add_mesh_property_face_mode"
    bl_label = "Add"

    options: EnumProperty(
        items=[
            ("_connected_geometry_face_mode_render_only", "Render Only", ""),
            (
                "_connected_geometry_face_mode_collision_only",
                "Collision Only",
                "",
            ),
            (
                "_connected_geometry_face_mode_sphere_collision_only",
                "Sphere Collision Only",
                "",
            ),
            ("_connected_geometry_face_mode_shadow_only", "Shadow Only", ""),
            (
                "_connected_geometry_face_mode_lightmap_only",
                "Lightmap Only",
                "",
            ),
            ("_connected_geometry_face_mode_breakable", "Breakable", ""),
        ]
    )


class NWO_MeshPropAddFaceSides(NWO_MeshPropAdd):
    bl_idname = "nwo.add_mesh_property_face_sides"
    bl_label = "Add"

    options: EnumProperty(
        items=[
            (
                "_connected_geometry_face_sides_one_sided_transparent",
                "Transparent",
                "",
            ),
            ("_connected_geometry_face_sides_two_sided", "Two Side", ""),
            (
                "_connected_geometry_face_sides_two_sided_transparent",
                "Two Side Transparent",
                "",
            ),
            ("_connected_geometry_face_sides_mirror", "Mirror", ""),
            (
                "_connected_geometry_face_sides_mirror_transparent",
                "Mirror Transparent",
                "",
            ),
            ("_connected_geometry_face_sides_keep", "Keep", ""),
            (
                "_connected_geometry_face_sides_keep_transparent",
                "Keep Transparent",
                "",
            ),
        ]
    )


class NWO_MeshPropAddFlags(NWO_MeshPropAdd):
    bl_idname = "nwo.add_mesh_property_flags"
    bl_label = "Add"

    options: EnumProperty(
        items=[
            ("ladder", "Ladder", ""),
            ("slip_surface", "Slip Surface", ""),
            ("decal_offset", "Decal Offset", ""),
            ("group_transparents_by_plane", "Group Transparents by Plane", ""),
            ("no_shadow", "No Shadow", ""),
            ("no_lightmap", "No Lightmap", ""),
            ("no_pvs", "No PVS", ""),
        ]
    )


class NWO_MeshPropAddLightmap(NWO_MeshPropAdd):
    bl_idname = "nwo.add_mesh_property_lightmap"
    bl_label = "Add"

    options: EnumProperty(
        items=[
            ("lightmap_additive_transparency", "Transparency", ""),
            ("lightmap_resolution_scale", "Resolution Scale", ""),
            ("lightmap_type", "Lightmap Type", ""),
            # ('lightmap_analytical_bounce_modifier', 'Analytical Light Bounce Modifier', ''),
            # ('lightmap_general_bounce_modifier', 'General Light Bounce Modifier', ''),
            (
                "lightmap_translucency_tint_color",
                "Translucency Tint Colour",
                "",
            ),
            (
                "lightmap_lighting_from_both_sides",
                "Lighting from Both Sides",
                "",
            ),
        ]
    )


class NWO_MeshPropAddMaterialLighting(NWO_MeshPropAdd):
    bl_idname = "nwo.add_mesh_property_material_lighting"
    bl_label = "Add"

    options: EnumProperty(
        items=[
            ("material_lighting_attenuation", "Attenuation", ""),
            ("material_lighting_emissive_focus", "Focus", ""),
            ("material_lighting_emissive_color", "Colour", ""),
            ("material_lighting_emissive_per_unit", "Emissive per Unit", ""),
            ("material_lighting_emissive_power", "Power", ""),
            ("material_lighting_emissive_quality", "Quality", ""),
            ("material_lighting_use_shader_gel", "Use Shader Gel", ""),
            ("material_lighting_bounce_ratio", "Lighting Bounce Ratio", ""),
        ]
    )


class NWO_MeshPropAddMisc(NWO_MeshPropAdd):
    bl_idname = "nwo.add_mesh_property_misc"
    bl_label = "Add"

    options: EnumProperty(
        items=[
            ("face_draw_distance", "Draw Distance", ""),
            # ('texcoord_usage', 'Texcord Usage', ''),
        ]
    )


# Object Properties Panels
# ------------------------------------------


class NWO_ObjectProps(NWO_PropPanel):
    bl_label = "Halo Object Properties"
    bl_idname = "NWO_PT_ObjectDetailsPanel"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        ob = context.object
        return (
            ob
            and ob.type
            not in ("ARMATURE", "LATTICE", "LIGHT_PROBE", "SPEAKER", "CAMERA")
            and not (ob.type == "EMPTY" and ob.empty_display_type == "IMAGE")
            and poll_ui(
                (
                    "MODEL",
                    "SCENARIO",
                    "SKY",
                    "DECORATOR SET",
                    "PARTICLE MODEL",
                    "PREFAB",
                )
            )
        )

    def draw_header(self, context):
        self.layout.prop(context.object.nwo, "export_this", text="")

    def draw(self, context):
        layout = self.layout
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        ob = context.object
        ob_nwo = ob.nwo
        h4 = not_bungie_game()

        if not ob_nwo.export_this:
            layout.label(text="Object is excluded from export")
            layout.active = False
        else:
            col = flow.column()
            row = layout.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=True,
            )
            row.scale_x = 1.3
            row.scale_y = 1.3
            row.prop(ob_nwo, "object_type_ui", text="", expand=True)
            # if CheckType.frame(ob) and h4:
            #     col.prop(ob_nwo, 'is_pca')

            if (
                ob_nwo.object_type_ui
                == "_connected_geometry_object_type_light"
            ):
                flow = layout.grid_flow(
                    row_major=True,
                    columns=0,
                    even_columns=True,
                    even_rows=False,
                    align=False,
                )
                col = flow.column()
                col.use_property_split = True
                if poll_ui("SCENARIO"):
                    row = col.row()
                    if ob_nwo.permutation_name_locked_ui != "":
                        row.prop(
                            ob_nwo,
                            "permutation_name_locked_ui",
                            text="Permutation",
                        )
                    else:
                        row.prop(
                            ob_nwo, "permutation_name_ui", text="Permutation"
                        )
                        row.operator_menu_enum(
                            "nwo.permutation_list",
                            "permutation",
                            text="",
                            icon="DOWNARROW_HLT",
                        )

                    row = col.row()
                    if ob_nwo.bsp_name_locked_ui != "":
                        row.prop(ob_nwo, "bsp_name_locked_ui", text="BSP")
                    else:
                        row.prop(ob_nwo, "bsp_name_ui", text="BSP")
                        row.operator_menu_enum(
                            "nwo.bsp_list",
                            "bsp",
                            text="",
                            icon="DOWNARROW_HLT",
                        )

                    col.separator()

                col.label(
                    text="See the Object Data Properties panel for Halo Light Properties"
                )

            elif (
                ob_nwo.object_type_ui == "_connected_geometry_object_type_mesh"
            ):
                # SPECIFIC MESH PROPS
                flow = layout.grid_flow(
                    row_major=True,
                    columns=0,
                    even_columns=True,
                    even_rows=False,
                    align=False,
                )

                col = flow.column()
                row = col.row()
                row.scale_y = 1.25
                row.emboss = "NORMAL"
                row.prop(ob_nwo, "mesh_type_ui", text="")
                # row.menu(NWO_MeshMenu.bl_idname, text=mesh_type_name, icon_value=get_icon_id(mesh_type_icon))

                col.separator()
                flow = layout.grid_flow(
                    row_major=True,
                    columns=0,
                    even_columns=True,
                    even_rows=False,
                    align=False,
                )
                col = flow.column()
                col.use_property_split = True

                if poll_ui(("MODEL", "SCENARIO")):
                    row = col.row()
                    if (
                        poll_ui("MODEL")
                        and ob_nwo.mesh_type_ui
                        == "_connected_geometry_mesh_type_object_instance"
                    ):
                        pass
                    elif ob_nwo.permutation_name_locked_ui != "":
                        row.prop(
                            ob_nwo,
                            "permutation_name_locked_ui",
                            text="Permutation",
                        )
                    else:
                        row.prop(
                            ob_nwo, "permutation_name_ui", text="Permutation"
                        )
                        row.operator_menu_enum(
                            "nwo.permutation_list",
                            "permutation",
                            text="",
                            icon="DOWNARROW_HLT",
                        )

                if poll_ui("SCENARIO"):
                    is_seam = ob_nwo.mesh_type_ui == "_connected_geometry_mesh_type_seam"
                    row = col.row()
                    if ob_nwo.bsp_name_locked_ui != "":
                        if is_seam:
                            row.prop(ob_nwo, "bsp_name_locked_ui", text="Front Facing BSP")
                        else:
                            row.prop(ob_nwo, "bsp_name_locked_ui", text="BSP")
                    else:
                        if is_seam:
                            row.prop(ob_nwo, "bsp_name_ui", text="Front Facing BSP")
                        else:
                            row.prop(ob_nwo, "bsp_name_ui", text="BSP")
                        row.operator_menu_enum(
                            "nwo.bsp_list",
                            "bsp",
                            text="",
                            icon="DOWNARROW_HLT",
                        )

                    if is_seam:
                        row = col.row()
                        row.prop(ob_nwo, "seam_back_ui", text="Back Facing BSP")
                        row.operator_menu_enum(
                            "nwo.bsp_list_seam",
                            "bsp",
                            text="",
                            icon="DOWNARROW_HLT",
                        )
                        # Seams guide
                        col.separator()
                        row = col.row()
                        row.label(text="Seam normals should face towards the specified front facing BSP")

                # col.separator()

                if (
                    ob_nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_decorator"
                ):
                    col.prop(ob_nwo, "decorator_lod_ui")

                elif (
                    ob_nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_physics"
                ):
                    col.prop(
                        ob_nwo, "mesh_primitive_type_ui", text="Primitive Type"
                    )

                elif (
                    ob_nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_plane"
                ):
                    row = col.row()
                    row.scale_y = 1.25
                    row.prop(ob_nwo, "plane_type_ui")

                    if (
                        ob_nwo.plane_type_ui
                        == "_connected_geometry_plane_type_portal"
                    ):
                        row = col.row()
                        row.prop(
                            ob_nwo,
                            "portal_type_ui",
                            text="Portal Type",
                            expand=True,
                        )

                        col.separator()

                        col = col.column(heading="Flags")

                        col.prop(
                            ob_nwo,
                            "portal_ai_deafening_ui",
                            text="AI Deafening",
                        )
                        col.prop(
                            ob_nwo,
                            "portal_blocks_sounds_ui",
                            text="Blocks Sounds",
                        )
                        col.prop(ob_nwo, "portal_is_door_ui", text="Is Door")

                    elif (
                        ob_nwo.plane_type_ui
                        == "_connected_geometry_plane_type_planar_fog_volume"
                    ):
                        row = col.row()
                        row.prop(
                            ob_nwo,
                            "fog_appearance_tag_ui",
                            text="Fog Appearance Tag",
                        )
                        row.operator(
                            "nwo.fog_path", icon="FILE_FOLDER", text=""
                        )
                        col.prop(
                            ob_nwo,
                            "fog_volume_depth_ui",
                            text="Fog Volume Depth",
                        )

                    elif (
                        ob_nwo.plane_type_ui
                        == "_connected_geometry_plane_type_water_surface"
                    ):
                        col.prop(ob_nwo, "mesh_tessellation_density_ui")

                elif (
                    ob_nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_volume"
                ):
                    row = col.row()
                    row.scale_y = 1.25
                    row.prop(ob_nwo, "volume_type_ui")

                    if (
                        ob_nwo.volume_type_ui
                        == "_connected_geometry_volume_type_water_physics"
                    ):
                        col.separator()
                        col.prop(
                            ob_nwo,
                            "water_volume_depth_ui",
                            text="Water Volume Depth",
                        )
                        col.prop(
                            ob_nwo,
                            "water_volume_flow_direction_ui",
                            text="Flow Direction",
                        )
                        col.prop(
                            ob_nwo,
                            "water_volume_flow_velocity_ui",
                            text="Flow Velocity",
                        )
                        col.prop(
                            ob_nwo,
                            "water_volume_fog_color_ui",
                            text="Underwater Fog Color",
                        )
                        col.prop(
                            ob_nwo,
                            "water_volume_fog_murkiness_ui",
                            text="Underwater Fog Murkiness",
                        )

                elif (
                    ob_nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_poop_collision"
                ):
                    col.prop(ob_nwo, "poop_collision_type_ui")

                elif ob_nwo.mesh_type_ui in (
                    "_connected_geometry_mesh_type_poop",
                    "_connected_geometry_mesh_type_structure",
                ):
                    if (
                        h4
                        and ob_nwo.mesh_type_ui
                        == "_connected_geometry_mesh_type_structure"
                    ):
                        col.prop(ob_nwo, "proxy_instance")
                    if (
                        ob_nwo.mesh_type_ui
                        == "_connected_geometry_mesh_type_poop"
                        or (
                            ob_nwo.mesh_type_ui
                            == "_connected_geometry_mesh_type_structure"
                            and h4
                            and ob_nwo.proxy_instance
                        )
                    ):
                        col.prop(
                            ob_nwo, "poop_lighting_ui", text="Lighting Policy"
                        )

                        # if h4:
                        #     col.prop(ob_nwo, "poop_lightmap_resolution_scale_ui")

                        col.prop(
                            ob_nwo,
                            "poop_pathfinding_ui",
                            text="Pathfinding Policy",
                        )

                        col.prop(
                            ob_nwo,
                            "poop_imposter_policy_ui",
                            text="Imposter Policy",
                        )
                        if (
                            ob_nwo.poop_imposter_policy_ui
                            != "_connected_poop_instance_imposter_policy_never"
                        ):
                            sub = col.row(heading="Imposter Transition")
                            sub.prop(
                                ob_nwo,
                                "poop_imposter_transition_distance_auto",
                                text="Automatic",
                            )
                            if (
                                not ob_nwo.poop_imposter_transition_distance_auto
                            ):
                                sub.prop(
                                    ob_nwo,
                                    "poop_imposter_transition_distance_ui",
                                    text="Distance",
                                )
                            if h4:
                                col.prop(ob_nwo, "poop_imposter_brightness_ui")

                        if h4:
                            col.prop(ob_nwo, "poop_streaming_priority_ui")
                            col.prop(ob_nwo, "poop_cinematic_properties_ui")

                        col.separator()

                        col = col.column(heading="Flags")

                        # col.prop(ob_nwo, "poop_render_only_ui", text='Render Only')

                        col.prop(
                            ob_nwo,
                            "poop_chops_portals_ui",
                            text="Chops Portals",
                        )
                        col.prop(
                            ob_nwo,
                            "poop_does_not_block_aoe_ui",
                            text="Does Not Block AOE",
                        )
                        col.prop(
                            ob_nwo,
                            "poop_excluded_from_lightprobe_ui",
                            text="Excluded From Lightprobe",
                        )
                        # col.prop(ob_nwo, "poop_decal_spacing_ui", text='Decal Spacing')
                        if h4:
                            # col.prop(ob_nwo, "poop_remove_from_shadow_geometry_ui")
                            col.prop(
                                ob_nwo, "poop_disallow_lighting_samples_ui"
                            )
                            # col.prop(ob_nwo, "poop_rain_occluder")

                # MESH LEVEL / FACE LEVEL PROPERTIES

            elif (
                ob_nwo.object_type_ui
                == "_connected_geometry_object_type_marker"
                and poll_ui(("MODEL", "SCENARIO", "SKY"))
            ):
                # MARKER PROPERTIES
                flow = layout.grid_flow(
                    row_major=True,
                    columns=0,
                    even_columns=False,
                    even_rows=False,
                    align=False,
                )
                flow.use_property_split = False
                col = flow.column()
                row = col.row()
                row.scale_y = 1.25
                row.emboss = "NORMAL"
                row.prop(ob_nwo, "marker_type_ui", text="")

                col.separator()

                flow = layout.grid_flow(
                    row_major=True,
                    columns=0,
                    even_columns=False,
                    even_rows=False,
                    align=False,
                )
                flow.use_property_split = True
                col = flow.column()

                if poll_ui("SCENARIO"):
                    row = col.row()
                    if ob_nwo.permutation_name_locked_ui != "":
                        row.prop(
                            ob_nwo,
                            "permutation_name_locked_ui",
                            text="Permutation",
                        )
                    else:
                        row.prop(
                            ob_nwo, "permutation_name_ui", text="Permutation"
                        )
                        row.operator_menu_enum(
                            "nwo.permutation_list",
                            "permutation",
                            text="",
                            icon="DOWNARROW_HLT",
                        )

                    row = col.row()
                    if ob_nwo.bsp_name_locked_ui != "":
                        row.prop(ob_nwo, "bsp_name_locked_ui", text="BSP")
                    else:
                        row.prop(ob_nwo, "bsp_name_ui", text="BSP")
                        row.operator_menu_enum(
                            "nwo.bsp_list",
                            "bsp",
                            text="",
                            icon="DOWNARROW_HLT",
                        )

                    col.separator()

                if (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_model"
                ):
                    if poll_ui(("MODEL", "SKY")):
                        row = col.row()
                        sub = col.row(align=True)
                        if not ob_nwo.marker_all_regions_ui:
                            if ob_nwo.region_name_locked_ui != "":
                                col.prop(
                                    ob_nwo,
                                    "region_name_locked_ui",
                                    text="Region",
                                )
                            else:
                                col.prop(
                                    ob_nwo, "region_name_ui", text="Region"
                                )
                        sub.prop(
                            ob_nwo, "marker_all_regions_ui", text="All Regions"
                        )

                elif (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_game_instance"
                ):
                    row = col.row()
                    row.prop(
                        ob_nwo,
                        "marker_game_instance_tag_name_ui",
                        text="Tag Path",
                    )
                    row.operator(
                        "nwo.game_instance_path", icon="FILE_FOLDER", text=""
                    )
                    if not ob_nwo.marker_game_instance_tag_name_ui.endswith(
                        (".prefab", ".cheap_light", ".light", ".leaf")
                    ):
                        col.prop(
                            ob_nwo,
                            "marker_game_instance_tag_variant_name_ui",
                            text="Tag Variant",
                        )
                        if h4:
                            col.prop(
                                ob_nwo, "marker_game_instance_run_scripts_ui"
                            )

                elif (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_hint"
                ):
                    row = col.row(align=True)
                    row.prop(ob_nwo, "marker_hint_type")
                    if ob_nwo.marker_hint_type == "corner":
                        row = col.row(align=True)
                        row.prop(ob_nwo, "marker_hint_side", expand=True)
                    elif ob_nwo.marker_hint_type in (
                        "vault",
                        "mount",
                        "hoist",
                    ):
                        row = col.row(align=True)
                        row.prop(ob_nwo, "marker_hint_height", expand=True)
                    if h4:
                        col.prop(ob_nwo, "marker_hint_length_ui")

                elif (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_garbage"
                ):
                    col.prop(
                        ob_nwo, "marker_velocity_ui", text="Marker Velocity"
                    )

                elif (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_pathfinding_sphere"
                ):
                    col = col.column(heading="Flags")
                    col.prop(
                        ob_nwo,
                        "marker_pathfinding_sphere_vehicle_ui",
                        text="Vehicle Only",
                    )
                    col.prop(
                        ob_nwo,
                        "pathfinding_sphere_remains_when_open_ui",
                        text="Remains When Open",
                    )
                    col.prop(
                        ob_nwo,
                        "pathfinding_sphere_with_sectors_ui",
                        text="With Sectors",
                    )
                    if ob.type != "MESH":
                        col.prop(ob_nwo, "marker_sphere_radius_ui")

                elif (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_physics_constraint"
                ):
                    col.prop(
                        ob_nwo,
                        "physics_constraint_parent_ui",
                        text="Constraint Parent",
                    )
                    col.prop(
                        ob_nwo,
                        "physics_constraint_child_ui",
                        text="Constraint Child",
                    )
                    row = col.row()
                    row.prop(
                        ob_nwo,
                        "physics_constraint_type_ui",
                        text="Constraint Type",
                        expand=True,
                    )
                    col.prop(
                        ob_nwo,
                        "physics_constraint_uses_limits_ui",
                        text="Uses Limits",
                    )

                    if ob_nwo.physics_constraint_uses_limits:
                        if (
                            ob_nwo.physics_constraint_type
                            == "_connected_geometry_marker_type_physics_hinge_constraint"
                        ):
                            col.prop(
                                ob_nwo,
                                "hinge_constraint_minimum_ui",
                                text="Minimum",
                            )
                            col.prop(
                                ob_nwo,
                                "hinge_constraint_maximum_ui",
                                text="Maximum",
                            )

                        elif (
                            ob_nwo.physics_constraint_type
                            == "_connected_geometry_marker_type_physics_socket_constraint"
                        ):
                            col.prop(ob_nwo, "cone_angle", text="Cone Angle")

                            col.prop(
                                ob_nwo,
                                "plane_constraint_minimum_ui",
                                text="Plane Minimum",
                            )
                            col.prop(
                                ob_nwo,
                                "plane_constraint_maximum_ui",
                                text="Plane Maximum",
                            )

                            col.prop(
                                ob_nwo,
                                "twist_constraint_start_ui",
                                text="Twist Start",
                            )
                            col.prop(
                                ob_nwo,
                                "twist_constraint_end_ui",
                                text="Twist End",
                            )

                elif (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_target"
                ):
                    if ob.type != "MESH":
                        col.prop(ob_nwo, "marker_sphere_radius_ui")

                elif (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_envfx"
                    and h4
                ):
                    row = col.row()
                    row.prop(ob_nwo, "marker_looping_effect_ui")
                    row.operator("nwo.effect_path")

                elif (
                    ob_nwo.marker_type_ui
                    == "_connected_geometry_marker_type_lightCone"
                    and h4
                ):
                    row = col.row()
                    row.prop(ob_nwo, "marker_light_cone_tag_ui")
                    row.operator(
                        "nwo.light_cone_path", icon="FILE_FOLDER", text=""
                    )
                    col.prop(ob_nwo, "marker_light_cone_color_ui")
                    col.prop(ob_nwo, "marker_light_cone_alpha_ui")
                    col.prop(ob_nwo, "marker_light_cone_intensity_ui")
                    col.prop(ob_nwo, "marker_light_cone_width_ui")
                    col.prop(ob_nwo, "marker_light_cone_length_ui")
                    row = col.row()
                    row.prop(ob_nwo, "marker_light_cone_curve_ui")
                    row.operator(
                        "nwo.light_cone_curve_path",
                        icon="FILE_FOLDER",
                        text="",
                    )


# Tag Path Operators
# ------------------------------------------
class NWO_GameInstancePath(NWO_Op_Path):
    bl_idname = "nwo.game_instance_path"
    bl_description = "Return the path to a game tag"

    filter_glob: StringProperty(
        default="*.biped;*.crate;*.creature;*.device_*;*.effect_*;*.equipment;*.giant;*.scenery;*.vehicle;*.weapon;*.prefab;*.cheap_l*;*.light",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.marker_game_instance_tag_name_ui = self.filepath
        return {"FINISHED"}


class NWO_FogPath(NWO_Op_Path):
    bl_idname = "nwo.fog_path"
    bl_description = "Return the path to a fog tag"

    filter_glob: StringProperty(
        default="*.atmosphere_",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.fog_appearance_tag_ui = self.filepath
        return {"FINISHED"}


class NWO_EffectPath(NWO_Op_Path):
    bl_idname = "nwo.effect_path"
    bl_description = "Set the path to an effect tag"

    filter_glob: StringProperty(
        default="*.effect",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.marker_looping_effect_ui = self.filepath
        return {"FINISHED"}


class NWO_LightConePath(NWO_Op_Path):
    bl_idname = "nwo.light_cone_path"
    bl_description = "Set the path to a light cone tag"

    filter_glob: StringProperty(
        default="*.light_",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.marker_light_cone_tag_ui = self.filepath
        return {"FINISHED"}


class NWO_LightConeCurvePath(NWO_Op_Path):
    bl_idname = "nwo.light_cone_curve_path"
    bl_description = "Set the path to a light cone curve tag"

    filter_glob: StringProperty(
        default="*.curve_",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.marker_light_cone_curve_ui = self.filepath
        return {"FINISHED"}


class NWO_LightTagPath(NWO_Op_Path):
    bl_idname = "nwo.light_tag_path"
    bl_description = "Set the path to a light tag"

    filter_glob: StringProperty(
        default="*.light",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.light_tag_override_ui = self.filepath
        return {"FINISHED"}


class NWO_LightShaderPath(NWO_Op_Path):
    bl_idname = "nwo.light_shader_path"
    bl_description = "Set the path to a light shader tag"

    filter_glob: StringProperty(
        default="*.render_",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.light_shader_reference = self.filepath
        return {"FINISHED"}


class NWO_LightGelPath(NWO_Op_Path):
    bl_idname = "nwo.light_gel_path"
    bl_description = "Set the path to a gel bitmap"

    filter_glob: StringProperty(
        default="*.bitmap",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.light_gel_reference = self.filepath
        return {"FINISHED"}


class NWO_LensFlarePath(NWO_Op_Path):
    bl_idname = "nwo.lens_flare_path"
    bl_description = "Set the path to a lens flare bitmap"

    filter_glob: StringProperty(
        default="*.lens_",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.object.nwo.light_lens_flare_reference = self.filepath
        return {"FINISHED"}


# LIST SYSTEMS
# ------------------------------------------------


class NWO_GlobalMaterialMenu(Menu):
    bl_label = "Add Collision Material"
    bl_idname = "NWO_MT_AddGlobalMaterial"

    def draw(self, context):
        layout = self.layout
        ob = context.object
        global_materials = ["default"]
        for ob in export_objects_no_arm():
            global_material = ob.nwo.face_global_material_ui
            if global_material not in global_materials:
                global_materials.append(global_material)
            # also need to loop through face props
            for face_prop in ob.data.nwo.face_props:
                if (
                    face_prop.face_global_material_override
                    and face_prop.face_global_material not in global_materials
                ):
                    global_materials.append(face_prop.face_global_material)

        for g_mat in global_materials:
            layout.operator(
                "nwo.global_material_list", text=g_mat
            ).global_material = g_mat

        if poll_ui(("MODEL", "SKY")):
            layout.operator_menu_enum(
                "nwo.global_material_regions_list",
                property="region",
                text="From Region",
            )


class NWO_RegionList(NWO_Op):
    bl_idname = "nwo.region_list"
    bl_label = "Region List"
    bl_description = "Applies a region to the selected object"

    def regions_items(self, context):
        # get scene regions
        regions = ["default"]
        for ob in export_objects_no_arm():
            region = true_region(ob.nwo)
            if region not in regions:
                regions.append(region)
            # also need to loop through face props
            for face_prop in ob.data.nwo.face_props:
                if (
                    face_prop.region_name_override
                    and face_prop.region_name_ui not in regions
                ):
                    regions.append(face_prop.region_name_ui)

        regions = sort_alphanum(regions)
        items = []
        for index, region in enumerate(regions):
            items.append(bpy_enum_list(region, index))

        return items

    region: EnumProperty(
        name="Region",
        items=regions_items,
    )

    def execute(self, context):
        context.object.nwo.region_name_ui = self.region
        return {"FINISHED"}


class NWO_GlobalMaterialRegionList(NWO_RegionList):
    bl_idname = "nwo.global_material_regions_list"
    bl_label = "Collision Material List"
    bl_description = "Applies a global material to the selected object"

    def execute(self, context):
        context.object.nwo.face_global_material_ui = self.region
        return {"FINISHED"}


class NWO_GlobalMaterialList(NWO_Op):
    bl_idname = "nwo.global_material_list"
    bl_label = "Collision Material List"
    bl_description = "Applies a Collision Material to the selected object"

    def global_material_items(self, context):
        # get scene regions
        global_materials = ["default"]
        for ob in export_objects_no_arm():
            global_material = ob.nwo.face_global_material_ui
            if global_material not in global_materials and global_material:
                global_materials.append(global_material)
            # also need to loop through face props
            for face_prop in ob.data.nwo.face_props:
                if (
                    face_prop.face_global_material_override
                    and face_prop.face_global_material_ui
                    not in global_materials
                ):
                    global_materials.append(face_prop.face_global_materia_ui)

        global_materials = sort_alphanum(global_materials)
        items = []
        for index, global_material in enumerate(global_materials):
            items.append(bpy_enum_list(global_material, index))

        return items

    global_material: EnumProperty(
        name="Collision Material",
        items=global_material_items,
    )

    def execute(self, context):
        context.object.nwo.face_global_material_ui = self.global_material
        return {"FINISHED"}


class NWO_PermutationList(NWO_Op):
    bl_idname = "nwo.permutation_list"
    bl_label = "Permutation List"
    bl_description = "Applies a permutation to the selected object"

    def permutations_items(self, context):
        # get scene perms
        permutations = ["default"]
        for ob in export_objects_no_arm():
            permutation = true_permutation(ob.nwo)
            if permutation not in permutations:
                permutations.append(permutation)

        permutations = sort_alphanum(permutations)
        items = []
        for index, permutation in enumerate(permutations):
            items.append(bpy_enum_list(permutation, index))

        return items

    permutation: EnumProperty(
        name="Permutation",
        items=permutations_items,
    )

    def execute(self, context):
        context.object.nwo.permutation_name_ui = self.permutation
        return {"FINISHED"}


class NWO_BSPList(NWO_Op):
    bl_idname = "nwo.bsp_list"
    bl_label = "BSP List"
    bl_description = "Applies a BSP to the selected object"

    def bsp_items(self, context):
        # get scene perms
        bsps = ["default"]
        for ob in export_objects_no_arm():
            bsp = true_bsp(ob.nwo)
            if bsp not in bsps:
                bsps.append(bsp)

        bsps = sort_alphanum(bsps)
        items = []
        for index, bsp in enumerate(bsps):
            items.append(bpy_enum_list(bsp, index))

        return items

    bsp: EnumProperty(
        name="bsp",
        items=bsp_items,
    )

    def execute(self, context):
        context.object.nwo.bsp_name_ui = self.bsp
        return {"FINISHED"}


class NWO_BSPListSeam(NWO_BSPList):
    bl_idname = "nwo.bsp_list_seam"

    def bsp_items(self, context):
        # get scene perms
        self_bsp = true_bsp(context.object.nwo)
        bsps = []
        for ob in export_objects_no_arm():
            bsp = true_bsp(ob.nwo)
            if bsp != self_bsp and bsp not in bsps:
                bsps.append(bsp)

        bsps = sort_alphanum(bsps)
        items = []
        for index, bsp in enumerate(bsps):
            items.append(bpy_enum_list(bsp, index))

        return items

    bsp: EnumProperty(
        name="bsp",
        items=bsp_items,
    )

    def execute(self, context):
        context.object.nwo.seam_back_ui = self.bsp
        return {"FINISHED"}


class NWO_MasterInstance(NWO_Op):
    bl_idname = "nwo.master_instance"
    bl_label = "Set Master Instance"
    bl_description = "Sets the current object as the master instance for all linked objects. Linked objects will use this objects face properties"

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "MESH"
            and context.object.mode in ("OBJECT", "EDIT")
            and is_linked(context.object)
        )

    def execute(self, context):
        ob = context.object

        # Set this object to the master instance
        ob.data.nwo.master_instance = ob

        return {"FINISHED"}


# BONE PANEL
class NWO_BoneProps(NWO_PropPanel):
    bl_label = "Halo Bone Properties"
    bl_idname = "NWO_PT_BoneDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        scene_nwo = scene.nwo
        return (
            scene_nwo.game_version in ("reach", "h4", "h2a") and context.bone
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        bone = context.bone
        bone_nwo = bone.nwo
        scene = context.scene

        # layout.enabled = scene_nwo.expert_mode

        col = flow.column()
        col.prop(bone_nwo, "name_override")

        col.separator()

        col.prop(bone_nwo, "frame_id1", text="Frame ID 1")
        col.prop(bone_nwo, "frame_id2", text="Frame ID 2")

        col.separator()

        col.prop(
            bone_nwo, "object_space_node", text="Object Space Offset Node"
        )
        col.prop(
            bone_nwo,
            "replacement_correction_node",
            text="Replacement Correction Node",
        )
        col.prop(bone_nwo, "fik_anchor_node", text="Forward IK Anchor Node")


# LIGHT PANEL
class NWO_LightProps(NWO_PropPanel):
    bl_label = "Halo Light Properties"
    bl_idname = "NWO_PT_LightPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"
    bl_parent_id = "DATA_PT_EEVEE_light"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        data = context.object.data
        ob_nwo = data.nwo

        col = flow.column()

        scene = context.scene
        scene_nwo = scene.nwo

        if scene_nwo.game_version in ("h4", "h2a"):
            # col.prop(ob_nwo, 'Light_Color', text='Color')
            row = col.row()
            row.prop(ob_nwo, "light_mode", expand=True)
            row = col.row()
            row.prop(ob_nwo, "light_lighting_mode", expand=True)
            # col.prop(ob_nwo, 'light_type_h4')
            if data.type == "SPOT":
                col.separator()
                row = col.row()
                row.prop(ob_nwo, "light_cone_projection_shape", expand=True)
                # col.prop(ob_nwo, 'light_inner_cone_angle')
                # col.prop(ob_nwo, 'light_outer_cone_angle')

            col.separator()
            # col.prop(ob_nwo, 'Light_IntensityH4')
            if (
                ob_nwo.light_lighting_mode
                == "_connected_geometry_lighting_mode_artistic"
            ):
                col.prop(ob_nwo, "light_near_attenuation_starth4")
                col.prop(ob_nwo, "light_near_attenuation_endh4")

            col.separator()

            if ob_nwo.light_mode == "_connected_geometry_light_mode_dynamic":
                col.prop(ob_nwo, "light_far_attenuation_starth4")
                col.prop(ob_nwo, "light_far_attenuation_endh4")

                col.separator()

                row = col.row()
                row.prop(ob_nwo, "light_cinema", expand=True)
                col.prop(ob_nwo, "light_destroy_after")

                col.separator()

                col.prop(ob_nwo, "light_shadows")
                if ob_nwo.light_shadows:
                    col.prop(ob_nwo, "light_shadow_color")
                    row = col.row()
                    row.prop(
                        ob_nwo, "light_dynamic_shadow_quality", expand=True
                    )
                    col.prop(ob_nwo, "light_shadow_near_clipplane")
                    col.prop(ob_nwo, "light_shadow_far_clipplane")
                    col.prop(ob_nwo, "light_shadow_bias_offset")
                col.prop(ob_nwo, "light_cinema_objects_only")
                col.prop(ob_nwo, "light_specular_contribution")
                col.prop(ob_nwo, "light_diffuse_contribution")
                col.prop(ob_nwo, "light_ignore_dynamic_objects")
                col.prop(ob_nwo, "light_screenspace")
                if ob_nwo.light_screenspace:
                    col.prop(ob_nwo, "light_specular_power")
                    col.prop(ob_nwo, "light_specular_intensity")

                # col = layout.column(heading="Flags")
                # sub = col.column(align=True)
            else:
                row = col.row()
                row.prop(ob_nwo, "light_jitter_quality", expand=True)
                col.prop(ob_nwo, "light_jitter_angle")
                col.prop(ob_nwo, "light_jitter_sphere_radius")

                col.separator()

                col.prop(ob_nwo, "light_amplification_factor")

                col.separator()
                # col.prop(ob_nwo, 'light_attenuation_near_radius')
                # col.prop(ob_nwo, 'light_attenuation_far_radius')
                # col.prop(ob_nwo, 'light_attenuation_power')
                # col.prop(ob_nwo, 'light_tag_name')
                col.prop(ob_nwo, "light_indirect_only")
                col.prop(ob_nwo, "light_static_analytic")

            # col.prop(ob_nwo, 'light_intensity_off', text='Light Intensity Set Via Tag')
            # if ob_nwo.light_lighting_mode == '_connected_geometry_lighting_mode_artistic':
            #     col.prop(ob_nwo, 'near_attenuation_end_off', text='Near Attenuation Set Via Tag')
            # if ob_nwo.light_type_h4 == '_connected_geometry_light_type_spot':
            #     col.prop(ob_nwo, 'outer_cone_angle_off', text='Outer Cone Angle Set Via Tag')

            # col.prop(ob_nwo, 'Light_Fade_Start_Distance')
            # col.prop(ob_nwo, 'Light_Fade_End_Distance')

        else:
            col.prop(ob_nwo, "light_type_override", text="Type")

            col.prop(ob_nwo, "light_game_type", text="Game Type")
            col.prop(ob_nwo, "light_shape", text="Shape")
            # col.prop(ob_nwo, 'Light_Color', text='Color')
            col.prop(ob_nwo, "light_intensity", text="Intensity")

            col.separator()

            col.prop(
                ob_nwo,
                "light_fade_start_distance",
                text="Fade Out Start Distance",
            )
            col.prop(
                ob_nwo, "light_fade_end_distance", text="Fade Out End Distance"
            )

            col.separator()

            col.prop(ob_nwo, "light_hotspot_size", text="Hotspot Size")
            col.prop(ob_nwo, "light_hotspot_falloff", text="Hotspot Falloff")
            col.prop(ob_nwo, "light_falloff_shape", text="Falloff Shape")
            col.prop(ob_nwo, "light_aspect", text="Light Aspect")

            col.separator()

            col.prop(ob_nwo, "light_frustum_width", text="Frustum Width")
            col.prop(ob_nwo, "light_frustum_height", text="Frustum Height")

            col.separator()

            col.prop(
                ob_nwo, "light_volume_distance", text="Light Volume Distance"
            )
            col.prop(
                ob_nwo, "light_volume_intensity", text="Light Volume Intensity"
            )

            col.separator()

            col.prop(ob_nwo, "light_bounce_ratio", text="Light Bounce Ratio")

            col.separator()

            col = layout.column(heading="Flags")
            sub = col.column(align=True)

            sub.prop(
                ob_nwo,
                "light_ignore_bsp_visibility",
                text="Ignore BSP Visibility",
            )
            sub.prop(
                ob_nwo,
                "light_dynamic_has_bounce",
                text="Light Has Dynamic Bounce",
            )
            if (
                ob_nwo.light_sub_type
                == "_connected_geometry_lighting_sub_type_screenspace"
            ):
                sub.prop(
                    ob_nwo,
                    "light_screenspace_has_specular",
                    text="Screenspace Light Has Specular",
                )

            col = flow.column()

            col.prop(
                ob_nwo,
                "light_near_attenuation_start",
                text="Near Attenuation Start",
            )
            col.prop(
                ob_nwo,
                "light_near_attenuation_end",
                text="Near Attenuation End",
            )

            col.separator()

            col.prop(
                ob_nwo,
                "light_far_attenuation_start",
                text="Far Attenuation Start",
            )
            col.prop(
                ob_nwo, "light_far_attenuation_end", text="Far Attenuation End"
            )

            col.separator()
            row = col.row()
            row.prop(ob_nwo, "light_tag_override", text="Light Tag Override")
            row.operator("nwo.light_tag_path")
            row = col.row()
            row.prop(
                ob_nwo, "light_shader_reference", text="Shader Tag Reference"
            )
            row.operator("nwo.light_shader_path")
            row = col.row()
            row.prop(ob_nwo, "light_gel_reference", text="Gel Tag Reference")
            row.operator("nwo.light_gel_path")
            row = col.row()
            row.prop(
                ob_nwo,
                "light_lens_flare_reference",
                text="Lens Flare Tag Reference",
            )
            row.operator("nwo.lens_flare_path")

            # col.separator() # commenting out light clipping for now.

            # col.prop(ob_nwo, 'Light_Clipping_Size_X_Pos', text='Clipping Size X Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Y_Pos', text='Clipping Size Y Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Z_Pos', text='Clipping Size Z Forward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_X_Neg', text='Clipping Size X Backward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Y_Neg', text='Clipping Size Y Backward')
            # col.prop(ob_nwo, 'Light_Clipping_Size_Z_Neg', text='Clipping Size Z Backward')


class NWO_LightPropsCycles(NWO_LightProps):
    bl_idname = "NWO_PT_LightPanel_Cycles"
    bl_parent_id = "CYCLES_LIGHT_PT_light"

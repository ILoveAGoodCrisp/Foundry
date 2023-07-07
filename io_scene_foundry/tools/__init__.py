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

import bpy
from os.path import exists as file_exists
from os.path import join as path_join
import os
import webbrowser

from bpy.types import Context, OperatorProperties, Panel, Operator, PropertyGroup

from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
)
from io_scene_foundry.icons import get_icon_id
from io_scene_foundry.ui.face_ui import NWO_FaceLayerAddMenu, NWO_FacePropAddMenu
from io_scene_foundry.ui.object_ui import NWO_GlobalMaterialMenu, NWO_MeshPropAddMenu

from io_scene_foundry.utils.nwo_utils import (
    bpy_enum,
    clean_tag_path,
    deselect_all_objects,
    dot_partition,
    foundry_update_check,
    get_halo_material_count,
    get_tags_path,
    has_face_props,
    has_mesh_props,
    is_halo_object,
    managed_blam_active,
    not_bungie_game,
    nwo_asset_type,
    protected_material_name,
    set_active_object,
    valid_nwo_asset,
    poll_ui,
    validate_ek,
)
from bpy_extras.object_utils import AddObjectHelper

is_blender_startup = True

FOUNDRY_DOCS = r"https://c20.reclaimers.net/general/tools/foundry"
FOUNDRY_GITHUB = r"https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit"

BLENDER_TOOLSET = r"https://github.com/General-101/Halo-Asset-Blender-Development-Toolset/releases"
AMF_ADDON = r"https://www.mediafire.com/file/zh55pb2p3yc4e7v/Blender_AMF2.py/file"
RECLAIMER = r"https://www.mediafire.com/file/bwnfg09iy0tbm09/Reclaimer.Setup-v1.7.309.msi/file"
ANIMATION_REPO = r"https://github.com/77Mynameislol77/HaloAnimationRepository"

CURRENT_VERSION = "0.9.1"

update_str, update_needed = foundry_update_check(CURRENT_VERSION)

HOTKEYS = [
    ("apply_mesh_type", "SHIFT+F"),
    ("apply_marker_type", "CTRL+F"),
    ("halo_join", "ALT+J"),
    ("move_to_halo_collection", "ALT+M"),
]

PANELS_PROPS = [
    "scene_properties",
    "asset_editor",
    "object_properties",
    "material_properties",
    "animation_properties",
    "tools",
    "help",
    "settings"
]

PANELS_TOOLS = ["sets_viewer"]

#######################################
# NEW TOOL UI


class NWO_FoundryPanelProps(Panel):
    bl_label = "Foundry Panel"
    bl_idname = "NWO_PT_FoundryPanelProps"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    #######################################
    # ADD MENU TOOLS

    def draw(self, context):
        self.context = context
        layout = self.layout
        self.h4 = not_bungie_game()
        self.scene = context.scene
        nwo = self.scene.nwo
        row = layout.row(align=True)
        col1 = row.column(align=True)
        col2 = row.column(align=True)

        box = col1.box()
        for p in PANELS_PROPS:
            if p == "help":
                box = col1.box()
            elif p == "animation_properties":
                if nwo.asset_type not in ('MODEL', 'FP ANIMATION'):
                    continue
            
            row_icon = box.row(align=True)
            panel_active = getattr(nwo, f"{p}_active")
            panel_pinned = getattr(nwo, f"{p}_pinned")
            row_icon.scale_x = 1.2
            row_icon.scale_y = 1.2
            row_icon.operator(
                "nwo.panel_set",
                text="",
                icon_value=get_icon_id(f"category_{p}_pinned") if panel_pinned else get_icon_id(f"category_{p}"),
                emboss=panel_active,
                depress=panel_pinned,
            ).panel_str = p

            if panel_active:
                panel_display_name = f"{p.replace('_', ' ').title()}"
                panel_expanded = getattr(nwo, f"{p}_expanded")
                self.box = col2.box()
                row_header = self.box.row(align=True)
                row_header.operator(
                    "nwo.panel_expand",
                    text=panel_display_name,
                    icon="TRIA_DOWN" if panel_expanded else "TRIA_RIGHT",
                    emboss=False,
                ).panel_str = p
                row_header.operator(
                    "nwo.panel_unpin",
                    text="",
                    icon="PINNED" if panel_pinned else "UNPINNED",
                    emboss=False,
                ).panel_str = p

                if panel_expanded:
                    draw_panel = getattr(self, f"draw_{p}")
                    draw_panel()

    def draw_scene_properties(self):
        box = self.box.box()
        mb_active = managed_blam_active()
        nwo = self.scene.nwo
        scene = self.scene

        col = box.column()
        if mb_active:
            col.enabled = False
        row = col.row()
        row.scale_y = 1.5
        row.prop(nwo, "game_version", text="")
        col = box.column()
        col.use_property_split = True
        if nwo.asset_type in ("MODEL", "SCENARIO", "PREFAB"):
            col.prop(nwo, "default_mesh_type_ui", text="Default Mesh Type")
        if nwo.asset_type in ("MODEL", "FP ANIMATION"):
            col.prop(nwo, "forward_direction", text="Model Forward")

        col.separator()
        row = col.row()

        if mb_active or nwo.mb_startup:
            row = col.row()
            col1 = row.column()
            col2 = row.column()
            col1.use_property_split = False
            col2.use_property_split = False
            col1.alignment = 'LEFT'
            col2.alignment = 'RIGHT'
            col1.label(icon_value=get_icon_id("managed_blam_on"), text="ManagedBlam Active")
            col2.prop(nwo, "mb_startup", text="Run on startup")
        elif os.path.exists(os.path.join(bpy.app.tempdir, "blam_new.txt")):
            row.label(text="Blender Restart Required for ManagedBlam")
        else:
            row.operator("managed_blam.init", text="Initialize ManagedBlam", icon_value=get_icon_id("managed_blam_off"))

        row = col.row()
        row.scale_y = 1.1

        unit_scale = scene.unit_settings.scale_length

        if unit_scale == 1.0:
            row.operator("nwo.set_unit_scale", text="Set Halo Scale", icon_value=get_icon_id("halo_scale")).scale = 0.03048
        else:
            row.operator("nwo.set_unit_scale", text="Set Default Scale", icon="BLENDER").scale = 1.0

    def draw_asset_editor(self):
        box = self.box.box()
        nwo = self.scene.nwo
        context = self.context
        scene = self.scene
        h4 = self.h4
        col = box.column()
        row = col.row()
        row.scale_y = 1.5
        row.prop(nwo, "asset_type", text="")
        col.separator()
        asset_name = scene.nwo_halo_launcher.sidecar_path.rpartition("\\")[2].replace(
            ".sidecar.xml", ""
        )
        
        row = col.row()
        if asset_name:
            row.label(text=f"Asset Name: {asset_name}")
            row.operator("nwo.make_asset", text="Copy Asset", icon_value=get_icon_id("halo_asset")) 
            
        else:
            row.scale_y = 1.5
            row.operator("nwo.make_asset", text="New Asset", icon_value=get_icon_id("halo_asset"))

        col.separator()
        if nwo.asset_type == "MODEL":
            col.label(text="Output Tags")
            row = col.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=True,
                align=True,
            )
            row.scale_x = 0.65
            row.scale_y = 1.3

            row.prop(
                nwo,
                "output_crate",
                # text="",
                icon_value=get_icon_id("crate"),
            )
            row.prop(
                nwo,
                "output_scenery",
                # text="",
                icon_value=get_icon_id("scenery"),
            )
            row.prop(
                nwo,
                "output_effect_scenery",
                text="Effect",
                icon_value=get_icon_id("effect_scenery"),
            )

            row.prop(
                nwo,
                "output_device_control",
                text="Control",
                icon_value=get_icon_id("device_control"),
            )
            row.prop(
                nwo,
                "output_device_machine",
                text="Machine",
                icon_value=get_icon_id("device_machine"),
            )
            row.prop(
                nwo,
                "output_device_terminal",
                text="Terminal",
                icon_value=get_icon_id("device_terminal"),
            )
            if context.scene.nwo.game_version in ("h4", "h2a"):
                row.prop(
                    nwo,
                    "output_device_dispenser",
                    text="Dispenser",
                    icon_value=get_icon_id("device_dispenser"),
                )

            row.prop(
                nwo,
                "output_biped",
                # text="",
                icon_value=get_icon_id("biped"),
            )
            row.prop(
                nwo,
                "output_creature",
                # text="",
                icon_value=get_icon_id("creature"),
            )
            row.prop(
                nwo,
                "output_giant",
                # text="",
                icon_value=get_icon_id("giant"),
            )

            row.prop(
                nwo,
                "output_vehicle",
                # text="",
                icon_value=get_icon_id("vehicle"),
            )
            row.prop(
                nwo,
                "output_weapon",
                # text="",
                icon_value=get_icon_id("weapon"),
            )
            row.prop(
                nwo,
                "output_equipment",
                # text="",
                icon_value=get_icon_id("equipment"),
            )

            box = box.box()
            box.label(text="Model Tag Reference Overrides")
            col = box.column()
            row = col.row(align=True)
            row.prop(nwo, "render_model_path", text="Render", icon_value=get_icon_id("tags"))
            row.operator("nwo.render_path", text="", icon="FILE_FOLDER")
            row = col.row(align=True)
            row.prop(nwo, "collision_model_path", text="Collision", icon_value=get_icon_id("tags"))
            row.operator("nwo.collision_path", text="", icon="FILE_FOLDER")
            row = col.row(align=True)
            row.prop(nwo, "animation_graph_path", text="Animation", icon_value=get_icon_id("tags"))
            row.operator("nwo.animation_path", text="", icon="FILE_FOLDER")
            row = col.row(align=True)
            row.prop(nwo, "physics_model_path", text="Physics", icon_value=get_icon_id("tags"))
            row.operator("nwo.physics_path", text="", icon="FILE_FOLDER")


    def draw_object_properties(self):
        box = self.box.box()
        row = box.row()
        context = self.context
        ob = context.object
        h4 = self.h4
        if not ob:
            row.label(text="No Active Object")
            return
        elif not is_halo_object(ob):
            row.label(text="Not a Halo Object")
            return

        nwo = ob.nwo
        col1 = row.column()
        col1.template_ID(context.view_layer.objects, "active", filter="AVAILABLE")
        col2 = row.column()
        col2.alignment = "RIGHT"
        col2.prop(nwo, "export_this", text="Export")

        if not nwo.export_this:
            box.label(text="Object is excluded from export")
            return

        elif ob.type == "ARMATURE":
            box.label(text="This object contains the skeleton for this asset")
            return

        row = box.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=True,
        )
        row.scale_x = 0.5
        row.scale_y = 1.3
        data = ob.data

        halo_light = nwo.object_type_ui == "_connected_geometry_object_type_light"

        if halo_light:
            row.prop(data, "type", expand=True)
        else:
            row.prop(nwo, "object_type_ui", expand=True)

        if halo_light:
            col = box.column()
            col.use_property_split = True
            if poll_ui("SCENARIO"):
                row = col.row()
                if nwo.permutation_name_locked_ui != "":
                    row.prop(
                        nwo,
                        "permutation_name_locked_ui",
                        text="Subgroup",
                    )
                else:
                    row.prop(nwo, "permutation_name_ui", text="Subgroup")
                    row.operator_menu_enum(
                        "nwo.permutation_list",
                        "permutation",
                        text="",
                        icon="DOWNARROW_HLT",
                    )

                row = col.row()
                if nwo.bsp_name_locked_ui != "":
                    row.prop(nwo, "bsp_name_locked_ui", text="BSP")
                else:
                    row.prop(nwo, "bsp_name_ui", text="BSP")
                    row.operator_menu_enum(
                        "nwo.bsp_list",
                        "bsp",
                        text="",
                        icon="DOWNARROW_HLT",
                    )

                col.separator()

            flow = col.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )

            scene = context.scene
            scene_nwo = scene.nwo
            nwo = data.nwo
            col = flow.column()

            col.prop(data, "color")
            col.prop(data, "energy")

            if data.type == 'SPOT' and h4:
                col.separator()
                col.prop(data, "spot_size", text="Cone Size")
                col.prop(data, "spot_blend", text="Cone Blend", slider=True)
                col.prop(data, "show_cone")
            elif data.type == 'AREA':
                col.label(text="Area lights not currently supported", icon="ERROR")
                return

            col.separator()
            if scene_nwo.game_version in ("h4", "h2a"):
                # col.prop(ob_nwo, 'Light_Color', text='Color')
                row = col.row()
                row.prop(nwo, "light_mode", expand=True)
                row = col.row()
                row.prop(nwo, "light_lighting_mode", expand=True)
                # col.prop(nwo, 'light_type_h4')
                if data.type == "SPOT":
                    col.separator()
                    row = col.row()
                    row.prop(nwo, "light_cone_projection_shape", expand=True)
                    # col.prop(nwo, 'light_inner_cone_angle')
                    # col.prop(nwo, 'light_outer_cone_angle')

                col.separator()
                # col.prop(nwo, 'Light_IntensityH4')
                if (
                    nwo.light_lighting_mode
                    == "_connected_geometry_lighting_mode_artistic"
                ):
                    col.prop(nwo, "light_near_attenuation_starth4")
                    col.prop(nwo, "light_near_attenuation_endh4")

                col.separator()

                if nwo.light_mode == "_connected_geometry_light_mode_dynamic":
                    col.prop(nwo, "light_far_attenuation_starth4")
                    col.prop(nwo, "light_far_attenuation_endh4")

                    col.separator()

                    row = col.row()
                    row.prop(nwo, "light_cinema", expand=True)
                    col.prop(nwo, "light_destroy_after")

                    col.separator()

                    col.prop(nwo, "light_shadows")
                    if nwo.light_shadows:
                        col.prop(nwo, "light_shadow_color")
                        row = col.row()
                        row.prop(nwo, "light_dynamic_shadow_quality", expand=True)
                        col.prop(nwo, "light_shadow_near_clipplane")
                        col.prop(nwo, "light_shadow_far_clipplane")
                        col.prop(nwo, "light_shadow_bias_offset")
                    col.prop(nwo, "light_cinema_objects_only")
                    col.prop(nwo, "light_specular_contribution")
                    col.prop(nwo, "light_diffuse_contribution")
                    col.prop(nwo, "light_ignore_dynamic_objects")
                    col.prop(nwo, "light_screenspace")
                    if nwo.light_screenspace:
                        col.prop(nwo, "light_specular_power")
                        col.prop(nwo, "light_specular_intensity")

                    # col = layout.column(heading="Flags")
                    # sub = col.column(align=True)
                else:
                    row = col.row()
                    row.prop(nwo, "light_jitter_quality", expand=True)
                    col.prop(nwo, "light_jitter_angle")
                    col.prop(nwo, "light_jitter_sphere_radius")

                    col.separator()

                    col.prop(nwo, "light_amplification_factor")

                    col.separator()
                    # col.prop(nwo, 'light_attenuation_near_radius')
                    # col.prop(nwo, 'light_attenuation_far_radius')
                    # col.prop(nwo, 'light_attenuation_power')
                    # col.prop(nwo, 'light_tag_name')
                    col.prop(nwo, "light_indirect_only")
                    col.prop(nwo, "light_static_analytic")

                # col.prop(nwo, 'light_intensity_off', text='Light Intensity Set Via Tag')
                # if nwo.light_lighting_mode == '_connected_geometry_lighting_mode_artistic':
                #     col.prop(nwo, 'near_attenuation_end_off', text='Near Attenuation Set Via Tag')
                # if nwo.light_type_h4 == '_connected_geometry_light_type_spot':
                #     col.prop(nwo, 'outer_cone_angle_off', text='Outer Cone Angle Set Via Tag')

                # col.prop(nwo, 'Light_Fade_Start_Distance')
                # col.prop(nwo, 'Light_Fade_End_Distance')
                

            else:
                # col.prop(nwo, "light_type_override", text="Type")

                col.prop(nwo, "light_game_type", text="Game Type")
                col.prop(nwo, "light_shape", text="Shape")
                # col.prop(nwo, 'Light_Color', text='Color')
                # col.prop(nwo, "light_intensity", text="Intensity")

                col.separator()

                col.prop(
                    nwo,
                    "light_fade_start_distance",
                    text="Fade Out Start Distance",
                )
                col.prop(nwo, "light_fade_end_distance", text="Fade Out End Distance")

                col.separator()

                col.prop(nwo, "light_hotspot_size", text="Hotspot Size")
                col.prop(nwo, "light_hotspot_falloff", text="Hotspot Falloff")
                col.prop(nwo, "light_falloff_shape", text="Falloff Shape")
                col.prop(nwo, "light_aspect", text="Light Aspect")

                col.separator()

                col.prop(nwo, "light_frustum_width", text="Frustum Width")
                col.prop(nwo, "light_frustum_height", text="Frustum Height")

                col.separator()

                col.prop(nwo, "light_volume_distance", text="Light Volume Distance")
                col.prop(nwo, "light_volume_intensity", text="Light Volume Intensity")

                col.separator()

                col.prop(nwo, "light_bounce_ratio", text="Light Bounce Ratio")

                col.separator()

                col = col.column(heading="Flags")
                sub = col.column(align=True)

                sub.prop(
                    nwo,
                    "light_ignore_bsp_visibility",
                    text="Ignore BSP Visibility",
                )
                sub.prop(
                    nwo,
                    "light_dynamic_has_bounce",
                    text="Light Has Dynamic Bounce",
                )
                if (
                    nwo.light_sub_type
                    == "_connected_geometry_lighting_sub_type_screenspace"
                ):
                    sub.prop(
                        nwo,
                        "light_screenspace_has_specular",
                        text="Screenspace Light Has Specular",
                    )

                col = flow.column()

                col.prop(
                    nwo,
                    "light_near_attenuation_start",
                    text="Near Attenuation Start",
                )
                col.prop(
                    nwo,
                    "light_near_attenuation_end",
                    text="Near Attenuation End",
                )

                col.separator()

                col.prop(
                    nwo,
                    "light_far_attenuation_start",
                    text="Far Attenuation Start",
                )
                col.prop(nwo, "light_far_attenuation_end", text="Far Attenuation End")

                col.separator()
                row = col.row()
                row.prop(nwo, "light_tag_override", text="Light Tag Override")
                row.operator("nwo.light_tag_path")
                row = col.row()
                row.prop(nwo, "light_shader_reference", text="Shader Tag Reference")
                row.operator("nwo.light_shader_path")
                row = col.row()
                row.prop(nwo, "light_gel_reference", text="Gel Tag Reference")
                row.operator("nwo.light_gel_path")
                row = col.row()
                row.prop(
                    nwo,
                    "light_lens_flare_reference",
                    text="Lens Flare Tag Reference",
                )
                row.operator("nwo.lens_flare_path")

                # col.separator() # commenting out light clipping for now.

                # col.prop(nwo, 'Light_Clipping_Size_X_Pos', text='Clipping Size X Forward')
                # col.prop(nwo, 'Light_Clipping_Size_Y_Pos', text='Clipping Size Y Forward')
                # col.prop(nwo, 'Light_Clipping_Size_Z_Pos', text='Clipping Size Z Forward')
                # col.prop(nwo, 'Light_Clipping_Size_X_Neg', text='Clipping Size X Backward')
                # col.prop(nwo, 'Light_Clipping_Size_Y_Neg', text='Clipping Size Y Backward')
                # col.prop(nwo, 'Light_Clipping_Size_Z_Neg', text='Clipping Size Z Backward')

            

        elif nwo.object_type_ui == "_connected_geometry_object_type_mesh":
            # SPECIFIC MESH PROPS
            flow = box.grid_flow(
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
            row.prop(nwo, "mesh_type_ui", text="")
            # row.menu(NWO_MeshMenu.bl_idname, text=mesh_type_name, icon_value=get_icon_id(mesh_type_icon))

            col.separator()
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            col.use_property_split = True

            if poll_ui(("MODEL", "SCENARIO")):
                perm_name = "Permutation"
                if poll_ui("SCENARIO"):
                    perm_name = "Subgroup"

                row = col.row()
                if (
                    poll_ui("MODEL")
                    and nwo.mesh_type_ui
                    == "_connected_geometry_mesh_type_object_instance"
                ):
                    pass
                elif nwo.permutation_name_locked_ui != "":
                    row.prop(
                        nwo,
                        "permutation_name_locked_ui",
                        text=perm_name,
                    )
                else:
                    row.prop(nwo, "permutation_name_ui", text=perm_name)
                    row.operator_menu_enum(
                        "nwo.permutation_list",
                        "permutation",
                        text="",
                        icon="DOWNARROW_HLT",
                    )

            if poll_ui("SCENARIO"):
                is_seam = nwo.mesh_type_ui == "_connected_geometry_mesh_type_seam"
                row = col.row()
                if nwo.bsp_name_locked_ui != "":
                    if is_seam:
                        row.prop(nwo, "bsp_name_locked_ui", text="Front Facing BSP")
                    else:
                        row.prop(nwo, "bsp_name_locked_ui", text="BSP")
                else:
                    if is_seam:
                        row.prop(nwo, "bsp_name_ui", text="Front Facing BSP")
                    else:
                        row.prop(nwo, "bsp_name_ui", text="BSP")
                    row.operator_menu_enum(
                        "nwo.bsp_list",
                        "bsp",
                        text="",
                        icon="DOWNARROW_HLT",
                    )

                if is_seam:
                    row = col.row()
                    row.prop(nwo, "seam_back_ui", text="Back Facing BSP")
                    row.operator_menu_enum(
                        "nwo.bsp_list_seam",
                        "bsp",
                        text="",
                        icon="DOWNARROW_HLT",
                    )
                    # Seams guide
                    col.separator()
                    row = col.row()
                    row.label(
                        text="Seam normals should face towards the specified front facing BSP"
                    )

            # col.separator()

            if nwo.mesh_type_ui == "_connected_geometry_mesh_type_decorator":
                col.prop(nwo, "decorator_lod_ui", text="Level of Detail")

            elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_physics":
                col.prop(nwo, "mesh_primitive_type_ui", text="Primitive Type")

            elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_plane":
                row = col.row()
                row.scale_y = 1.25
                row.prop(nwo, "plane_type_ui")

                if nwo.plane_type_ui == "_connected_geometry_plane_type_portal":
                    row = col.row()
                    row.prop(
                        nwo,
                        "portal_type_ui",
                        text="Portal Type",
                        expand=True,
                    )

                    col.separator()

                    col = col.column(heading="Flags")

                    col.prop(
                        nwo,
                        "portal_ai_deafening_ui",
                        text="AI Deafening",
                    )
                    col.prop(
                        nwo,
                        "portal_blocks_sounds_ui",
                        text="Blocks Sounds",
                    )
                    col.prop(nwo, "portal_is_door_ui", text="Is Door")

                elif (
                    nwo.plane_type_ui
                    == "_connected_geometry_plane_type_planar_fog_volume"
                ):
                    row = col.row()
                    row.prop(
                        nwo,
                        "fog_appearance_tag_ui",
                        text="Fog Appearance Tag",
                    )
                    row.operator("nwo.fog_path", icon="FILE_FOLDER", text="")
                    col.prop(
                        nwo,
                        "fog_volume_depth_ui",
                        text="Fog Volume Depth",
                    )

                elif (
                    nwo.plane_type_ui == "_connected_geometry_plane_type_water_surface"
                ):
                    col.prop(nwo, "mesh_tessellation_density_ui")

            elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_volume":
                row = col.row()
                row.scale_y = 1.25
                row.prop(nwo, "volume_type_ui")

                if (
                    nwo.volume_type_ui
                    == "_connected_geometry_volume_type_water_physics_volume"
                ):
                    col.separator()
                    col.prop(
                        nwo,
                        "water_volume_depth_ui",
                        text="Water Volume Depth",
                    )
                    col.prop(
                        nwo,
                        "water_volume_flow_direction_ui",
                        text="Flow Direction",
                    )
                    col.prop(
                        nwo,
                        "water_volume_flow_velocity_ui",
                        text="Flow Velocity",
                    )
                    col.prop(
                        nwo,
                        "water_volume_fog_color_ui",
                        text="Underwater Fog Color",
                    )
                    col.prop(
                        nwo,
                        "water_volume_fog_murkiness_ui",
                        text="Underwater Fog Murkiness",
                    )

            elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_poop_collision":
                col.prop(nwo, "poop_collision_type_ui")

            elif nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_structure",
            ):
                if h4 and nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure":
                    col.prop(nwo, "proxy_instance")
                if nwo.mesh_type_ui == "_connected_geometry_mesh_type_poop" or (
                    nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure"
                    and h4
                    and nwo.proxy_instance
                ):
                    col.prop(nwo, "poop_lighting_ui", text="Lighting Policy")

                    # if h4:
                    #     col.prop(nwo, "poop_lightmap_resolution_scale_ui")

                    col.prop(
                        nwo,
                        "poop_pathfinding_ui",
                        text="Pathfinding Policy",
                    )

                    col.prop(
                        nwo,
                        "poop_imposter_policy_ui",
                        text="Imposter Policy",
                    )
                    if (
                        nwo.poop_imposter_policy_ui
                        != "_connected_poop_instance_imposter_policy_never"
                    ):
                        sub = col.row(heading="Imposter Transition")
                        sub.prop(
                            nwo,
                            "poop_imposter_transition_distance_auto",
                            text="Automatic",
                        )
                        if not nwo.poop_imposter_transition_distance_auto:
                            sub.prop(
                                nwo,
                                "poop_imposter_transition_distance_ui",
                                text="Distance",
                            )
                        if h4:
                            col.prop(nwo, "poop_imposter_brightness_ui")

                    if h4:
                        col.prop(nwo, "poop_streaming_priority_ui")
                        col.prop(nwo, "poop_cinematic_properties_ui")

                    col.separator()

                    col = col.column(heading="Flags")

                    # col.prop(nwo, "poop_render_only_ui", text='Render Only')

                    col.prop(
                        nwo,
                        "poop_chops_portals_ui",
                        text="Chops Portals",
                    )
                    col.prop(
                        nwo,
                        "poop_does_not_block_aoe_ui",
                        text="Does Not Block AOE",
                    )
                    col.prop(
                        nwo,
                        "poop_excluded_from_lightprobe_ui",
                        text="Excluded From Lightprobe",
                    )
                    # col.prop(nwo, "poop_decal_spacing_ui", text='Decal Spacing')
                    if h4:
                        # col.prop(nwo, "poop_remove_from_shadow_geometry_ui")
                        col.prop(nwo, "poop_disallow_lighting_samples_ui")
                        # col.prop(nwo, "poop_rain_occluder")

            # MESH LEVEL / FACE LEVEL PROPERTIES

        elif nwo.object_type_ui == "_connected_geometry_object_type_marker" and poll_ui(
            ("MODEL", "SCENARIO", "SKY")
        ):
            # MARKER PROPERTIES
            flow = box.grid_flow(
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
            row.prop(nwo, "marker_type_ui", text="")

            col.separator()

            flow = box.grid_flow(
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
                if nwo.permutation_name_locked_ui != "":
                    row.prop(
                        nwo,
                        "permutation_name_locked_ui",
                        text="Permutation",
                    )
                else:
                    row.prop(nwo, "permutation_name_ui", text="Permutation")
                    row.operator_menu_enum(
                        "nwo.permutation_list",
                        "permutation",
                        text="",
                        icon="DOWNARROW_HLT",
                    )

                row = col.row()
                if nwo.bsp_name_locked_ui != "":
                    row.prop(nwo, "bsp_name_locked_ui", text="BSP")
                else:
                    row.prop(nwo, "bsp_name_ui", text="BSP")
                    row.operator_menu_enum(
                        "nwo.bsp_list",
                        "bsp",
                        text="",
                        icon="DOWNARROW_HLT",
                    )

                col.separator()

            if nwo.marker_type_ui in (
                "_connected_geometry_marker_type_model",
                "_connected_geometry_marker_type_garbage",
                "_connected_geometry_marker_type_effects",
                "_connected_geometry_marker_type_target",
                "_connected_geometry_marker_type_hint",
                "_connected_geometry_marker_type_pathfinding_sphere",
            ):
                if poll_ui(("MODEL", "SKY")):
                    row = col.row()
                    sub = col.row(align=True)
                    if not nwo.marker_all_regions_ui:
                        if nwo.region_name_locked_ui != "":
                            col.prop(
                                nwo,
                                "region_name_locked_ui",
                                text="Region",
                            )
                        else:
                            col.prop(nwo, "region_name_ui", text="Region")
                    sub.prop(nwo, "marker_all_regions_ui", text="All Regions")

            elif nwo.marker_type_ui == "_connected_geometry_marker_type_game_instance":
                row = col.row()
                row.prop(
                    nwo,
                    "marker_game_instance_tag_name_ui",
                    text="Tag Path",
                )
                row.operator("nwo.game_instance_path", icon="FILE_FOLDER", text="")
                if not nwo.marker_game_instance_tag_name_ui.endswith(
                    (".prefab", ".cheap_light", ".light", ".leaf")
                ):
                    col.prop(
                        nwo,
                        "marker_game_instance_tag_variant_name_ui",
                        text="Tag Variant",
                    )
                    if h4:
                        col.prop(nwo, "marker_game_instance_run_scripts_ui")

            if nwo.marker_type_ui == "_connected_geometry_marker_type_hint":
                print("Here")
                row = col.row(align=True)
                row.prop(nwo, "marker_hint_type")
                if nwo.marker_hint_type == "corner":
                    row = col.row(align=True)
                    row.prop(nwo, "marker_hint_side", expand=True)
                elif nwo.marker_hint_type in (
                    "vault",
                    "mount",
                    "hoist",
                ):
                    row = col.row(align=True)
                    row.prop(nwo, "marker_hint_height", expand=True)
                # if h4:
                #     col.prop(nwo, "marker_hint_length_ui")

            elif nwo.marker_type_ui == "_connected_geometry_marker_type_garbage":
                col.prop(nwo, "marker_velocity_ui", text="Marker Velocity")

            elif (
                nwo.marker_type_ui
                == "_connected_geometry_marker_type_pathfinding_sphere"
            ):
                col = col.column(heading="Flags")
                col.prop(
                    nwo,
                    "marker_pathfinding_sphere_vehicle_ui",
                    text="Vehicle Only",
                )
                col.prop(
                    nwo,
                    "pathfinding_sphere_remains_when_open_ui",
                    text="Remains When Open",
                )
                col.prop(
                    nwo,
                    "pathfinding_sphere_with_sectors_ui",
                    text="With Sectors",
                )
                # if ob.type != "MESH":
                #     col.prop(nwo, "marker_sphere_radius_ui")

            elif (
                nwo.marker_type_ui
                == "_connected_geometry_marker_type_physics_constraint"
            ):
                col.prop(
                    nwo,
                    "physics_constraint_parent_ui",
                    text="Constraint Parent",
                )
                parent = nwo.physics_constraint_parent_ui
                if parent is not None and parent.type == "ARMATURE":
                    col.prop_search(
                        nwo,
                        "physics_constraint_parent_bone_ui",
                        parent.data,
                        "bones",
                        text="Bone",
                    )
                col.prop(
                    nwo,
                    "physics_constraint_child_ui",
                    text="Constraint Child",
                )
                child = nwo.physics_constraint_child_ui
                if child is not None and child.type == "ARMATURE":
                    col.prop_search(
                        nwo,
                        "physics_constraint_child_bone_ui",
                        child.data,
                        "bones",
                        text="Bone",
                    )
                row = col.row()
                row.prop(
                    nwo,
                    "physics_constraint_type_ui",
                    text="Constraint Type",
                    expand=True,
                )
                col.prop(
                    nwo,
                    "physics_constraint_uses_limits_ui",
                    text="Uses Limits",
                )

                if nwo.physics_constraint_uses_limits_ui:
                    if (
                        nwo.physics_constraint_type_ui
                        == "_connected_geometry_marker_type_physics_hinge_constraint"
                    ):
                        col.prop(
                            nwo,
                            "hinge_constraint_minimum_ui",
                            text="Minimum",
                        )
                        col.prop(
                            nwo,
                            "hinge_constraint_maximum_ui",
                            text="Maximum",
                        )

                    elif (
                        nwo.physics_constraint_type_ui
                        == "_connected_geometry_marker_type_physics_socket_constraint"
                    ):
                        col.prop(nwo, "cone_angle_ui", text="Cone Angle")

                        col.prop(
                            nwo,
                            "plane_constraint_minimum_ui",
                            text="Plane Minimum",
                        )
                        col.prop(
                            nwo,
                            "plane_constraint_maximum_ui",
                            text="Plane Maximum",
                        )

                        col.prop(
                            nwo,
                            "twist_constraint_start_ui",
                            text="Twist Start",
                        )
                        col.prop(
                            nwo,
                            "twist_constraint_end_ui",
                            text="Twist End",
                        )

            # elif (
            #     nwo.marker_type_ui
            #     == "_connected_geometry_marker_type_target"
            # ):
            #     # if ob.type != "MESH":
            #     #     col.prop(nwo, "marker_sphere_radius_ui")

            elif nwo.marker_type_ui == "_connected_geometry_marker_type_envfx" and h4:
                row = col.row()
                row.prop(nwo, "marker_looping_effect_ui")
                row.operator("nwo.effect_path")

            elif (
                nwo.marker_type_ui == "_connected_geometry_marker_type_lightCone" and h4
            ):
                row = col.row()
                row.prop(nwo, "marker_light_cone_tag_ui")
                row.operator("nwo.light_cone_path", icon="FILE_FOLDER", text="")
                col.prop(nwo, "marker_light_cone_color_ui")
                col.prop(nwo, "marker_light_cone_alpha_ui")
                col.prop(nwo, "marker_light_cone_intensity_ui")
                col.prop(nwo, "marker_light_cone_width_ui")
                col.prop(nwo, "marker_light_cone_length_ui")
                row = col.row()
                row.prop(nwo, "marker_light_cone_curve_ui")
                row.operator(
                    "nwo.light_cone_curve_path",
                    icon="FILE_FOLDER",
                    text="",
                )

        if not has_mesh_props(ob):
            return

        flow = box.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        flow.use_property_split = True

        col = flow.column()
        row = col.row()
        if poll_ui(("MODEL", "SKY", "DECORATOR SET")):
            if nwo.region_name_locked_ui != "":
                col.prop(nwo, "region_name_locked_ui", text="Region")
            else:
                row = col.row(align=True)
                row.prop(nwo, "region_name_ui", text="Region")
                row.operator_menu_enum(
                    "nwo.region_list", "region", text="", icon="DOWNARROW_HLT"
                )
                # if ob.nwo.face_props and nwo.mesh_type_ui in ('_connected_geometry_mesh_type_object_render', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_physics'):
                #     for prop in ob.nwo.face_props:
                #         if prop.region_name_override:
                #             row.label(text='*')
                #             break
        if poll_ui(("MODEL", "SCENARIO", "PREFAB")):
            if (nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_poop_collision",
                "_connected_geometry_mesh_type_structure",
            ) and (not h4 or nwo.proxy_instance or nwo.mesh_type_ui != "_connected_geometry_mesh_type_structure")):
                row = col.row()
                row.prop(
                    nwo,
                    "face_global_material_ui",
                    text="Collision Material",
                )
                row.menu(
                    NWO_GlobalMaterialMenu.bl_idname,
                    text="",
                    icon="DOWNARROW_HLT",
                )
                # if ob.nwo.face_props and nwo.mesh_type_ui in ('_connected_geometry_mesh_type_object_poop', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_object_structure'):
                #     for prop in ob.nwo.face_props:
                #         if prop.face_global_material_override:
                #             row.label(text='*')
                #             break

        if poll_ui(("MODEL", "SCENARIO", "PREFAB")):
            if (nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_render",
                "_connected_geometry_mesh_type_poop",
                "_connected_geometry_mesh_type_structure",
                )
                and (not h4 or nwo.proxy_instance or nwo.mesh_type_ui != "_connected_geometry_mesh_type_structure")
            ):
                col2 = col.column()
                flow2 = col2.grid_flow()
                flow2.prop(nwo, "precise_position_ui", text="Uncompressed")
                col3 = col.column()
                flow3 = col3.grid_flow()
                flow3.prop(nwo, "decal_offset_ui")

        if nwo.mesh_type_ui in (
            "_connected_geometry_mesh_type_render",
            "_connected_geometry_mesh_type_poop",
            "_connected_geometry_mesh_type_poop_collision",
            "_connected_geometry_mesh_type_collision",
        ):
            col4 = col.column()
            flow4 = col4.grid_flow()
            flow4.prop(nwo, "face_two_sided_ui")

        if poll_ui(("SCENARIO", "PREFAB")) and (not h4 or nwo.proxy_instance or nwo.mesh_type_ui != "_connected_geometry_mesh_type_structure"):
            if nwo.face_mode_active:
                row = col.row()
                row.prop(nwo, "face_mode_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "face_mode"
            if nwo.face_sides_active:
                row = col.row()
                row.prop(nwo, "face_sides_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "face_sides"
            if nwo.face_draw_distance_active:
                row = col.row()
                row.prop(nwo, "face_draw_distance_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "face_draw_distance"
            if nwo.texcoord_usage_active:
                row = col.row()
                row.prop(nwo, "texcoord_usage_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "texcoord_usage"
            if nwo.ladder_active:
                row = col.row()
                row.prop(nwo, "ladder_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "ladder"
            if nwo.slip_surface_active:
                row = col.row()
                row.prop(nwo, "slip_surface_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "slip_surface"
            if nwo.group_transparents_by_plane_active:
                row = col.row()
                row.prop(nwo, "group_transparents_by_plane_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "group_transparents_by_plane"
            if nwo.no_shadow_active:
                row = col.row()
                row.prop(nwo, "no_shadow_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "no_shadow"
            if nwo.no_lightmap_active:
                row = col.row()
                row.prop(nwo, "no_lightmap_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "no_lightmap"
            if nwo.no_pvs_active:
                row = col.row()
                row.prop(nwo, "no_pvs_ui")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "no_pvs"
            # lightmap
            if nwo.lightmap_additive_transparency_active:
                row = col.row()
                row.prop(
                    nwo,
                    "lightmap_additive_transparency_ui",
                    text="Lightmap Additive Transparency",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_additive_transparency"
            if nwo.lightmap_resolution_scale_active:
                row = col.row()
                row.prop(
                    nwo,
                    "lightmap_resolution_scale_ui",
                    text="Lightmap Resolution Scale",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_resolution_scale"
            if nwo.lightmap_type_active:
                row = col.row()
                row.prop(nwo, "lightmap_type_ui", text="Lightmap Type")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_type"
            if nwo.lightmap_analytical_bounce_modifier_active:
                row = col.row()
                row.prop(
                    nwo,
                    "lightmap_analytical_bounce_modifier_ui",
                    text="Analytical Bounce Modifier",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_analytical_bounce_modifier"
            if nwo.lightmap_general_bounce_modifier_active:
                row = col.row()
                row.prop(
                    nwo,
                    "lightmap_general_bounce_modifier_ui",
                    text="General Bounce Modifier",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_general_bounce_modifier"
            if nwo.lightmap_translucency_tint_color_active:
                row = col.row()
                row.prop(
                    nwo,
                    "lightmap_translucency_tint_color_ui",
                    text="Translucency Tint Color",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_translucency_tint_color"
            if nwo.lightmap_lighting_from_both_sides_active:
                row = col.row()
                row.prop(
                    nwo,
                    "lightmap_lighting_from_both_sides_ui",
                    text="Lighting From Both Sides",
                )
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "lightmap_lighting_from_both_sides"

            if nwo.face_type_active:
                if nwo.face_type_ui == "_connected_geometry_face_type_sky":
                    col.separator()
                    box = col.box()
                    row = box.row()
                    row.label(text="Face Type Settings")
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "face_type"
                    row = box.row()
                    row.prop(nwo, "face_type_ui")
                    row = box.row()
                    row.prop(nwo, "sky_permutation_index_ui")
                else:
                    row = col.row()
                    row.prop(nwo, "face_type_ui")
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "face_type"
            # material lighting
            if nwo.emissive_active:
                col.separator()
                box = col.box()
                row = box.row()
                row.label(text="Emissive Settings")
                row.operator(
                    "nwo.remove_mesh_property", text="", icon="X"
                ).options = "emissive"
                row = box.row()
                row.prop(nwo, "material_lighting_emissive_color_ui", text="Color")
                row = box.row()
                row.prop(nwo, "material_lighting_emissive_power_ui", text="Power")
                row = box.row()
                row.prop(
                    nwo,
                    "material_lighting_emissive_quality_ui",
                    text="Quality",
                )
                row = box.row()
                row.prop(nwo, "material_lighting_emissive_focus_ui", text="Focus")
                row = box.row()
                row.prop(
                    nwo,
                    "material_lighting_attenuation_falloff_ui",
                    text="Attenutation Falloff",
                )
                row = box.row()
                row.prop(
                    nwo,
                    "material_lighting_attenuation_cutoff_ui",
                    text="Attenutation Cutoff",
                )
                row = box.row()
                row.prop(
                    nwo,
                    "material_lighting_bounce_ratio_ui",
                    text="Bounce Ratio",
                )
                row = box.row()
                row.prop(
                    nwo,
                    "material_lighting_use_shader_gel_ui",
                    text="Shader Gel",
                )
                row = box.row()
                row.prop(
                    nwo,
                    "material_lighting_emissive_per_unit_ui",
                    text="Emissive Per Unit",
                )

            col.menu(NWO_MeshPropAddMenu.bl_idname, text="", icon="PLUS")

        if not has_face_props(ob) or not (not h4 or nwo.proxy_instance or nwo.mesh_type_ui != "_connected_geometry_mesh_type_structure"):
            return

        flow = box.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        flow.use_property_split = True

        nwo = ob.data.nwo

        box.label(text="Face Properties")

        if len(nwo.face_props) <= 0 and context.mode != "EDIT_MESH":
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            col.scale_y = 1.3
            col.operator(
                "nwo.edit_face_layers",
                text="Use Edit Mode to Add Face Properties",
                icon="EDITMODE_HLT",
            )
        else:
            rows = 5
            row = box.row()
            row.template_list(
                "NWO_UL_FacePropList",
                "",
                nwo,
                "face_props",
                nwo,
                "face_props_index",
                rows=rows,
            )

            if context.mode == "EDIT_MESH":
                col = row.column(align=True)
                col.menu(NWO_FaceLayerAddMenu.bl_idname, text="", icon="ADD")
                col.operator("nwo.face_layer_remove", icon="REMOVE", text="")
                col.separator()
                col.operator(
                    "nwo.face_layer_color_all",
                    text="",
                    icon="SHADING_RENDERED",
                    depress=nwo.highlight,
                ).enable_highlight = not nwo.highlight
                col.separator()
                col.operator(
                    "nwo.face_layer_move", icon="TRIA_UP", text=""
                ).direction = "UP"
                col.operator(
                    "nwo.face_layer_move", icon="TRIA_DOWN", text=""
                ).direction = "DOWN"

                row = box.row()

                if nwo.face_props:
                    sub = row.row(align=True)
                    sub.operator("nwo.face_layer_assign", text="Assign").assign = True
                    sub.operator("nwo.face_layer_assign", text="Remove").assign = False
                    sub = row.row(align=True)
                    sub.operator("nwo.face_layer_select", text="Select").select = True
                    sub.operator(
                        "nwo.face_layer_select", text="Deselect"
                    ).select = False

            else:
                box.operator(
                    "nwo.edit_face_layers",
                    text="Edit Mode",
                    icon="EDITMODE_HLT",
                )

            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            row = col.row()
            col.use_property_split = True
            if nwo.face_props:
                item = nwo.face_props[nwo.face_props_index]

                if item.region_name_override:
                    row = col.row()
                    row.prop(item, "region_name_ui")
                    row.operator_menu_enum(
                        "nwo.face_region_list",
                        "region",
                        text="",
                        icon="DOWNARROW_HLT",
                    )
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "region"

                if item.face_type_override:
                    if item.face_type_ui == "_connected_geometry_face_type_sky":
                        col.separator()
                        box = col.box()
                        row = box.row()
                        row.label(text="Face Type Settings")
                        row.operator(
                            "nwo.face_prop_remove", text="", icon="X"
                        ).options = "face_type"
                        row = box.row()
                        row.prop(item, "face_type_ui")
                        row = box.row()
                        row.prop(item, "sky_permutation_index_ui")
                    else:
                        row = col.row()
                        row.prop(item, "face_type_ui")
                        row.operator(
                            "nwo.face_prop_remove", text="", icon="X"
                        ).options = "face_type"

                if item.face_mode_override:
                    row = col.row()
                    row.prop(item, "face_mode_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "face_mode"
                if item.face_two_sided_override:
                    row = col.row()
                    row.prop(item, "face_two_sided_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "two_sided"
                if item.face_global_material_override:
                    row = col.row()
                    row.prop(item, "face_global_material_ui")
                    row.operator_menu_enum(
                        "nwo.face_global_material_list",
                        "global_material",
                        text="",
                        icon="DOWNARROW_HLT",
                    )
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "face_global_material"
                if item.ladder_override:
                    row = col.row()
                    row.prop(item, "ladder_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "ladder"
                if item.slip_surface_override:
                    row = col.row()
                    row.prop(item, "slip_surface_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "slip_surface"
                if item.decal_offset_override:
                    row = col.row()
                    row.prop(item, "decal_offset_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "decal_offset"
                if item.group_transparents_by_plane_override:
                    row = col.row()
                    row.prop(item, "group_transparents_by_plane_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "group_transparents_by_plane"
                if item.no_shadow_override:
                    row = col.row()
                    row.prop(item, "no_shadow_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "no_shadow"
                if item.no_lightmap_override:
                    row = col.row()
                    row.prop(item, "no_lightmap_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "no_lightmap"
                if item.no_pvs_override:
                    row = col.row()
                    row.prop(item, "no_pvs_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "no_pvs"
                # lightmap
                if item.lightmap_additive_transparency_override:
                    row = col.row()
                    row.prop(item, "lightmap_additive_transparency_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "lightmap_additive_transparency"
                if item.lightmap_resolution_scale_override:
                    row = col.row()
                    row.prop(item, "lightmap_resolution_scale_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "lightmap_resolution_scale"
                if item.lightmap_type_override:
                    row = col.row()
                    row.prop(item, "lightmap_type_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "lightmap_type"
                if item.lightmap_analytical_bounce_modifier_override:
                    row = col.row()
                    row.prop(item, "lightmap_analytical_bounce_modifier_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "lightmap_analytical_bounce_modifier"
                if item.lightmap_general_bounce_modifier_override:
                    row = col.row()
                    row.prop(item, "lightmap_general_bounce_modifier_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "lightmap_general_bounce_modifier"
                if item.lightmap_translucency_tint_color_override:
                    row = col.row()
                    row.prop(item, "lightmap_translucency_tint_color_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "lightmap_translucency_tint_color"
                if item.lightmap_lighting_from_both_sides_override:
                    row = col.row()
                    row.prop(item, "lightmap_lighting_from_both_sides_ui")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "lightmap_lighting_from_both_sides"
                # material lighting
                if item.emissive_override:
                    col.separator()
                    box = col.box()
                    row = box.row()
                    row.label(text="Emissive Settings")
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "emissive"
                    # row.operator("nwo.remove_mesh_property", text='', icon='X').options = 'emissive'
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_color_ui",
                        text="Color",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_power_ui",
                        text="Power",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_quality_ui",
                        text="Quality",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_focus_ui",
                        text="Focus",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_attenuation_falloff_ui",
                        text="Attenutation Falloff",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_attenuation_cutoff_ui",
                        text="Attenutation Cutoff",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_bounce_ratio_ui",
                        text="Bounce Ratio",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_use_shader_gel_ui",
                        text="Shader Gel",
                    )
                    row = box.row()
                    row.prop(
                        item,
                        "material_lighting_emissive_per_unit_ui",
                        text="Emissive Per Unit",
                    )

                col.menu(NWO_FacePropAddMenu.bl_idname, text="", icon="PLUS")

    def draw_material_properties(self):
        box = self.box.box()
        row = box.row()
        context = self.context
        ob = context.object
        h4 = self.h4
        if not ob:
            row.label(text="No active object")
            return
        ob_type = ob.type
        if ob_type not in ("MESH", "CURVE", "SURFACE", "META", "FONT"):
            row.label(text="Active object does not support materials")
            return

        mat = ob.active_material
        col1 = row.column()
        col1.template_ID(ob, "active_material", new="material.new")
        if mat:
            txt = "Halo Material" if h4 else "Halo Shader"
            nwo = mat.nwo
            col2 = row.column()
            col2.alignment = "RIGHT"
            col2.prop(nwo, "rendered", text="Export")

        is_sortable = len(ob.material_slots) > 1
        rows = 3
        if is_sortable:
            rows = 5

        row = box.row()

        row.template_list(
            "MATERIAL_UL_matslots",
            "",
            ob,
            "material_slots",
            ob,
            "active_material_index",
            rows=rows,
        )

        col = row.column(align=True)
        col.operator("object.material_slot_add", icon="ADD", text="")
        col.operator("object.material_slot_remove", icon="REMOVE", text="")

        col.separator()

        col.menu("MATERIAL_MT_context_menu", icon="DOWNARROW_HLT", text="")

        if is_sortable:
            col.separator()

            col.operator(
                "object.material_slot_move", icon="TRIA_UP", text=""
            ).direction = "UP"
            col.operator(
                "object.material_slot_move", icon="TRIA_DOWN", text=""
            ).direction = "DOWN"

        row = box.row()

        if ob.mode == "EDIT":
            row = box.row(align=True)
            row.operator("object.material_slot_assign", text="Assign")
            row.operator("object.material_slot_select", text="Select")
            row.operator("object.material_slot_deselect", text="Deselect")
        if mat:
            row = box.row()
            if nwo.rendered:
                row.label(text=f"{txt} Path")
                row = box.row(align=True)
                row.prop(nwo, "shader_path", text="", icon_value=get_icon_id("tags"))
                row.operator("nwo.shader_finder_single", icon_value=get_icon_id("material_finder"), text="")
                row.operator("nwo.shader_path", icon="FILE_FOLDER", text="")
                ext = nwo.shader_path.rpartition(".")[2]
                if ext != nwo.shader_path and (ext == "material" or "shader" in ext):
                    row = box.row()
                    # row.scale_y = 1.5
                    row.operator(
                        "nwo.open_halo_material",
                        icon_value=get_icon_id("foundation"),
                    )
                else:
                    row = box.row()
                    tag_type = "Material" if h4 else "Shader"
                    row.operator("nwo.build_shader_single", text=f"Generate {tag_type} Tag", icon_value=get_icon_id("material_exporter"))

            else:
                if self.bl_idname == "NWO_PT_MaterialPanel":
                    row.label(text=f"Not a {txt}")
                else:
                    row.label(text=f"Not a {txt}")

    def draw_animation_properties(self):
        box = self.box.box()
        row = box.row()
        context = self.context
        ob = context.object
        if not ob or ob.type != "ARMATURE":
            if ob:
                row.label(text="Halo Animations are only supported for Armatures")
            else:
                row.label(text="No active object")

            row = box.row()
            row.operator("nwo.select_armature", text="Select Armature", icon='OUTLINER_OB_ARMATURE')
            return

        animation_data = ob.animation_data

        if not animation_data:
            ob.animation_data_create()
            return

        col1 = row.column(align=True)
        col1.template_ID(
            animation_data,
            "action",
            new="nwo.new_animation",
            unlink="nwo.delete_animation",
        )
        action = animation_data.action
        if action:
            nwo = action.nwo
            col2 = row.column()
            col2.alignment = "RIGHT"
            col2.prop(action, "use_frame_range", text="Export")

            if action.use_frame_range:
                row = box.row()
                row.use_property_split = True
                row.prop(action, "frame_start")
                row = box.row()
                row.use_property_split = True
                row.prop(action, "frame_end")
                row = box.row()
                row.use_property_split = True
                row.prop(nwo, "animation_type")
                row = box.row()
                row.use_property_split = True
                row.prop(nwo, "name_override")

                # ANIMATION RENAMES
                row = box.row()
                row.label(text="Animation Renames")
                row = box.row()
                rows = 2
                row.template_list(
                    "NWO_UL_AnimationRename",
                    "",
                    nwo,
                    "animation_renames",
                    nwo,
                    "animation_renames_index",
                    rows=rows,
                )
                col = row.column(align=True)
                col.operator("nwo.animation_rename_add", text="", icon="ADD")
                col.operator("nwo.animation_rename_remove", icon="REMOVE", text="")
                # col.separator()
                # col.operator(
                #     "nwo.face_layer_move", icon="TRIA_UP", text=""
                # ).direction = "UP"
                # col.operator(
                #     "nwo.face_layer_move", icon="TRIA_DOWN", text=""
                # ).direction = "DOWN"

                # ANIMATION EVENTS
                row = box.row()
                row.label(text="Animation Events")
                row = box.row()
                rows = 3
                row.template_list(
                    "NWO_UL_AnimProps_Events",
                    "",
                    nwo,
                    "animation_events",
                    nwo,
                    "animation_events_index",
                    rows=rows,
                )

                col = row.column(align=True)
                col.operator("animation_event.list_add", icon="ADD", text="")
                col.operator("animation_event.list_remove", icon="REMOVE", text="")

                if len(nwo.animation_events) > 0:
                    item = nwo.animation_events[nwo.animation_events_index]
                    # row = layout.row()
                    # row.prop(item, "name") # debug only
                    flow = box.grid_flow(
                        row_major=True,
                        columns=0,
                        even_columns=True,
                        even_rows=False,
                        align=False,
                    )
                    col = flow.column()
                    col.use_property_split = True
                    row = col.row()
                    row.prop(item, "multi_frame", expand=True)
                    col.prop(item, "frame_frame")
                    if item.multi_frame == "range":
                        col.prop(item, "frame_range")
                    col.prop(item, "frame_name")
                    col.prop(item, "event_type")
                    if (
                        item.event_type
                        == "_connected_geometry_animation_event_type_wrinkle_map"
                    ):
                        col.prop(item, "wrinkle_map_face_region")
                        col.prop(item, "wrinkle_map_effect")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_footstep"
                    ):
                        col.prop(item, "footstep_type")
                        col.prop(item, "footstep_effect")
                    elif item.event_type in (
                        "_connected_geometry_animation_event_type_ik_active",
                        "_connected_geometry_animation_event_type_ik_passive",
                    ):
                        col.prop(item, "ik_chain")
                        col.prop(item, "ik_active_tag")
                        col.prop(item, "ik_target_tag")
                        col.prop(item, "ik_target_marker")
                        col.prop(item, "ik_target_usage")
                        col.prop(item, "ik_proxy_target_id")
                        col.prop(item, "ik_pole_vector_id")
                        col.prop(item, "ik_effector_id")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_cinematic_effect"
                    ):
                        col.prop(item, "cinematic_effect_tag")
                        col.prop(item, "cinematic_effect_effect")
                        col.prop(item, "cinematic_effect_marker")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_object_function"
                    ):
                        col.prop(item, "object_function_name")
                        col.prop(item, "object_function_effect")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_frame"
                    ):
                        col.prop(item, "frame_trigger")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_import"
                    ):
                        col.prop(item, "import_frame")
                        col.prop(item, "import_name")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_text"
                    ):
                        col.prop(item, "text")

    def draw_tools(self):
        box = self.box.box()
        h4 = self.h4
        count, total = get_halo_material_count()
        shader_type = "Material" if h4 else "Shader"
        # if total:
        row = box.row()
        col = row.column()
        col.label(text=f"Asset {shader_type}s")
        # col.separator()
        col.label(
            text=f"{count} tag paths found out of {total} materials",
            icon='CHECKMARK' if total == count else 'ERROR'
        )
        row = col.row(align=True)
        col1 = row.column(align=True)
        col2 = row.column(align=True)
        col2.alignment = "RIGHT"
        col1.operator(
            "nwo.shader_finder",
            text=f"Find Missing {shader_type}s",
            icon_value=get_icon_id("material_finder"),
        )
        col2.popover(panel=NWO_ShaderFinder.bl_idname, text="")


    def draw_help(self):
        box_websites = self.box.box()
        box_websites.label(text="Foundry Documentation")
        col = box_websites.column()
        col.operator("nwo.open_url", text="Getting Started", icon_value=get_icon_id("c20_reclaimers")).url = FOUNDRY_DOCS
        col.operator("nwo.open_url", text="Github", icon_value=get_icon_id("github")).url = FOUNDRY_GITHUB

        box_hotkeys = self.box.box()
        box_hotkeys.label(text="Keyboard Shortcuts")
        col = box_hotkeys.column()
        col.direction
        for shortcut in HOTKEYS:
            col.operator("nwo.describe_hotkey", emboss=False, text=shortcut[0].replace("_", " ").title() + " : " + shortcut[1]).hotkey = shortcut[0]

        box_downloads = self.box.box()
        box_downloads.label(text="Other Resources")
        col = box_downloads.column()
        col.operator("nwo.open_url", text="Halo Blender Toolset", icon="BLENDER").url = BLENDER_TOOLSET
        col.operator("nwo.open_url", text="AMF Importer", icon_value=get_icon_id("amf")).url = AMF_ADDON
        col.operator("nwo.open_url", text="Reclaimer", icon_value=get_icon_id("marathon")).url = RECLAIMER
        col.operator("nwo.open_url", text="Animation Repository", icon_value=get_icon_id("github")).url = ANIMATION_REPO

    def draw_settings(self):
        nwo = self.scene.nwo
        box = self.box.box()
        box.label(text=update_str, icon_value=get_icon_id("foundry"))
        if update_needed:
            box.operator("nwo.open_url", text="Get Latest", icon_value=get_icon_id("github")).url = FOUNDRY_GITHUB
        box = self.box.box()
        col = box.column()
        col.prop(nwo, "toolbar_icons_only", text="Foundry Toolbar Icons Only")


class NWO_HotkeyDescription(Operator):
    bl_label = "Keyboard Shortcut Description"
    bl_idname = "nwo.describe_hotkey"
    bl_description = "Provides a description of this keyboard shortcut"

    hotkey : StringProperty()

    def execute(self, context: Context):
        return {'FINISHED'}
    
    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str:
        match properties.hotkey:
            case "apply_mesh_type":
                return "Opens a pie menu with a set of possible mesh types to apply to selected mesh objects. Applying a type through this menu will apply special materials if the type selected is not one that supports textures in game"
            case "apply_marker_type":
                return "Opens a pie menu with a set of possible marker types to apply to selected mesh and empty objects"
            case "halo_join":
                return "Joins two or more mesh objects and merges Halo Face Properties"
            case "move_to_halo_collection":
                return "Opens a dialog to specify a new halo collection to create, and then moves the selected objects into this collection"
                

    @staticmethod
    def hotkey_info(self, context):
        layout = self.layout
        layout.label(text=NWO_HotkeyDescription.description(context, self.hotkey))

class NWO_OpenURL(Operator):
    bl_label = "Open URL"
    bl_idname = "nwo.open_url"
    bl_description = "Opens a URL"

    url : StringProperty()

    def execute(self, context):
        webbrowser.open_new_tab(self.url)
        return {'FINISHED'}
    
    @classmethod
    def description(cls, context, properties) -> str:
        if properties.url == FOUNDRY_DOCS:
            return "Opens documentation for Foundry on the c20 Reclaimers site in a new tab"
        elif properties.url == FOUNDRY_GITHUB:
            return "Opens the github page for Foundry in a new tab"
        elif properties.url == BLENDER_TOOLSET:
            return "Opens the github releases page for the Halo Blender Development Toolset, a blender addon supporting H1/H2/H3/ODST. Opens in a new tab"
        elif properties.url == AMF_ADDON:
            return "Opens the download page for the AMF importer blender addon. This addon allows blender to import AMF files extracted from the Halo Tool - Reclaimer."
        elif properties.url == RECLAIMER:
            return "Opens the download page for Reclaimer, a tool for extracting render models, BSPs, and textures for Halo games"
        elif properties.url == ANIMATION_REPO:
            return "Opens the github page for a repository containing a collection of Halo animations stored in the legacy Halo animation format"
        
class NWO_SelectArmature(Operator):
    bl_label = "Select Armature"
    bl_idname = "nwo.select_armature"
    bl_options = {'UNDO'}
    bl_description = "Sets the first armature encountered as the active object"

    def execute(self, context):
        objects = context.view_layer.objects
        for ob in objects:
            if ob.type == 'ARMATURE':
                deselect_all_objects()
                ob.hide_set(False)
                ob.hide_select = False
                ob.select_set(True)
                set_active_object(ob)
                self.report({'INFO'}, F"Selected {ob.name}")
                break
        else:
            self.report({'WARNING'}, "No Armature Found")

        return {'FINISHED'}



class NWO_FoundryPanelSetsViewer(Panel):
    bl_label = "Halo Sets Viewer"
    bl_idname = "NWO_PT_FoundryPanelSetsViewer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    def draw(self, context):
        self.context = context
        layout = self.layout
        self.h4 = not_bungie_game()
        self.scene = context.scene
        nwo = self.scene.nwo
        row = layout.row(align=True)
        col1 = row.column(align=True)
        col2 = row.column(align=True)

        for p in PANELS_TOOLS:
            col1.separator()
            row_icon = col1.row(align=True)
            panel_active = getattr(nwo, f"{p}_active")
            panel_pinned = getattr(nwo, f"{p}_pinned")
            row_icon.scale_x = 1.2
            row_icon.scale_y = 1.2
            row_icon.operator(
                "nwo.panel_set",
                text="",
                icon_value=get_icon_id(f"category_{p}"),
                emboss=panel_active,
                depress=panel_pinned,
            ).panel_str = p

            if panel_active:
                panel_display_name = f"Halo {p.replace('_', ' ').title()}"
                panel_expanded = getattr(nwo, f"{p}_expanded")
                self.box = col2.box()
                row_header = self.box.row(align=True)
                row_header.alignment = "EXPAND"
                row_header.operator(
                    "nwo.panel_expand",
                    text=panel_display_name,
                    icon="TRIA_DOWN" if panel_expanded else "TRIA_RIGHT",
                    emboss=False,
                ).panel_str = p

                if panel_expanded:
                    draw_panel = getattr(self, f"draw_{p}")
                    draw_panel()

    def draw_object_tools(self):
        collection_manager = self.scene.nwo_collection_manager
        frame_id_tool = self.scene.nwo_frame_ids
        box = self.box.box()
        box.label(
            text="Collection Creator", icon_value=get_icon_id("collection_creator")
        )
        row = box.row()
        row.prop(collection_manager, "collection_name", text="Name")
        row = box.row()
        row.prop(collection_manager, "collection_type", text="Type")
        row = box.row()
        row.scale_y = 1.5
        row.operator("nwo.collection_create", text="New Collection")
        box = box.box()
        box.label(text="Frame ID Helper", icon_value=get_icon_id("frame_id"))
        row = box.row()
        row.label(text="Animation Graph Path")
        row = box.row()
        row.prop(frame_id_tool, "anim_tag_path", text="")
        row.scale_x = 0.25
        row.operator("nwo.graph_path", text="Find", icon="FILE_FOLDER")
        row = box.row()
        row.scale_y = 1.5
        row.operator("nwo.set_frame_ids", text="Set Frame IDs")
        row = box.row()
        row.scale_y = 1.5
        row.operator("nwo.reset_frame_ids", text="Reset Frame IDs")

    def draw_material_tools(self):
        shader_finder = self.scene.nwo_shader_finder
        box = self.box.box()
        box.label(text="Shader Finder", icon_value=get_icon_id("material_finder"))
        row = box.row()
        row.label(text="Limit Search To:")
        row = box.row()
        row.prop(shader_finder, "shaders_dir", text="", icon="FILE_FOLDER")
        row = box.row()
        row.prop(shader_finder, "overwrite_existing", text="Overwrite Existing Paths")
        row = box.row()
        row.scale_y = 1.5
        row.operator("nwo.shader_finder")

    def draw_animation_tools(self, box, scene):
        rig_creator = self.scene.nwo_armature_creator
        box = self.box.box()
        box.label(text="Rig Creator", icon_value=get_icon_id("rig_creator"))
        row = box.row()
        row.prop(rig_creator, "armature_type", text="Type", expand=True)
        row = box.row()
        row.scale_y = 1.5
        row.operator("nwo.armature_create", text="Create Rig")

class NWO_OT_PanelUnpin(Operator):
    bl_idname = "nwo.panel_unpin"
    bl_label = ""

    bl_options = {"UNDO"}

    panel_str : StringProperty()

    def execute(self, context: Context):
        nwo = context.scene.nwo
        prop_pin = f"{self.panel_str}_pinned"
        setattr(nwo, prop_pin, not getattr(nwo, prop_pin))

        return {"FINISHED"}



class NWO_OT_PanelSet(Operator):
    """Toggles a Foundry panel on/off"""

    bl_idname = "nwo.panel_set"
    bl_label = ""
    bl_options = {"UNDO"}

    panel_str : StringProperty()
    keep_enabled : BoolProperty()
    pin : BoolProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        prop = f"{self.panel_str}_active"
        prop_pin = f"{self.panel_str}_pinned"
        pinned = getattr(nwo, prop_pin)
        if self.pin and not pinned:
            setattr(nwo, prop_pin, True)
            setattr(nwo, prop, True)
        elif self.pin and pinned:
            setattr(nwo, prop_pin, False)
            setattr(nwo, prop, False)
        else:
            setattr(nwo, prop, True)

        # toggle all others off
        if not self.keep_enabled:
            for p in PANELS_PROPS:
                p_name = f"{p}_active"
                if p_name != prop and not getattr(nwo, f"{p}_pinned"):
                    setattr(nwo, p_name, False)

        return {"FINISHED"}
    
    def invoke(self, context, event):
        self.keep_enabled = event.shift or event.ctrl
        self.pin = event.ctrl
        return self.execute(context)
        
    
    @classmethod
    def description(cls, context, properties):
        name = properties.panel_str.title().replace("_", " ")
        descr = "Shift+Click to select multiple\nCtrl+Click to pin"
        full_descr = f'{name}\n\n{descr}'
        return full_descr


class NWO_OT_PanelExpand(Operator):
    """Expands or contracts Foundry panel on/off"""

    bl_idname = "nwo.panel_expand"
    bl_label = ""
    bl_options = {"UNDO"}
    bl_description = "Expand a panel"

    panel_str: StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        prop = f"{self.panel_str}_expanded"
        setattr(nwo, prop, not getattr(nwo, prop))
        self.report({"INFO"}, f"Expanded: {prop}")
        return {"FINISHED"}


class NWO_ScaleModels_Add(Operator, AddObjectHelper):
    bl_idname = "mesh.add_halo_scale_model"
    bl_label = "Halo Scale Model"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Create a new Halo Scale Model Object"

    game: EnumProperty(
        default="reach",
        name="Game",
        items=[
            ("reach", "Halo Reach", ""),
            ("h4", "Halo 4", ""),
            #("h2a", "Halo 2AMP", ""),
        ],
    )

    unit: EnumProperty(
        default="biped",
        name="Type",
        items=[
            ("biped", "Biped", ""),
            ("vehicle", "Vehicle", ""),
        ],
    )

    biped_model_reach: EnumProperty(
        default="scale_model_spartan",
        name="",
        items=[
            ("scale_model_brute", "Brute", ""),
            ("scale_model_civilian_female", "Civilian Female", ""),
            ("scale_model_civilian_male", "Civilian Male", ""),
            ("scale_model_cortana", "Cortana", ""),
            ("scale_model_bugger", "Drone", ""),
            ("scale_model_elite", "Elite", ""),
            ("scale_model_engineer", "Engineer", ""),
            ("scale_model_grunt", "Grunt", ""),
            ("scale_model_halsey", "Halsey", ""),
            ("scale_model_hunter", "Hunter", ""),
            ("scale_model_jackal", "Jackal", ""),
            ("scale_model_keyes", "Keyes", ""),
            ("scale_model_marine", "Marine", ""),
            ("scale_model_marine_female", "Marine Female", ""),
            ("scale_model_moa", "Moa", ""),
            ("scale_model_monitor", "Monitor", ""),
            ("scale_model_marine_odst", "ODST", ""),
            ("scale_model_rat", "Rat", ""),
            ("scale_model_skirmisher", "Skirmisher", ""),
            ("scale_model_spartan", "Spartan", ""),
        ],
    )

    biped_model_h4: EnumProperty(
        default="scale_model_chiefsolo",
        name="",
        items=[
            ("scale_model_chiefsolo", "Masterchief", ""),
            ("scale_model_chiefmp", "Spartan", ""),
        ],
    )

    biped_model_h2a: EnumProperty(
        default="scale_model_masterchief",
        name="",
        items=[
            ("scale_model_elite", "Elite", ""),
            ("scale_model_masterchief", "Spartan", ""),
            ("scale_model_monitor", "Monitor", ""),
        ],
    )

    vehicle_model_reach: EnumProperty(
        default="scale_model_warthog",
        name="",
        items=[
            ("scale_model_banshee", "Banshee", ""),
            ("scale_model_corvette", "Corvette", ""),
            ("scale_model_cruiser", "Cruiser", ""),
            ("scale_model_cart_electric", "Electric Cart", ""),
            ("scale_model_falcon", "Falcon", ""),
            ("scale_model_forklift", "Forklift", ""),
            ("scale_model_frigate", "Frigate", ""),
            ("scale_model_ghost", "Ghost", ""),
            ("scale_model_lnos", "Long Night of Solace", ""),
            ("scale_model_mongoose", "Mongoose", ""),
            ("scale_model_oni_van", "Oni Van", ""),
            ("scale_model_pelican", "Pelican", ""),
            ("scale_model_phantom", "Phantom", ""),
            ("scale_model_pickup", "Pickup Truck", ""),
            ("scale_model_poa", "Pillar of Autumn", ""),
            ("scale_model_revenant", "Revenant", ""),
            ("scale_model_sabre", "Sabre", ""),
            ("scale_model_scarab", "Scarab", ""),
            ("scale_model_scorpion", "Scorpion", ""),
            ("scale_model_seraph", "Seraph", ""),
            ("scale_model_spirit", "Spirit", ""),
            ("scale_model_super_carrier", "Super Carrier", ""),
            ("scale_model_warthog", "Warthog", ""),
            ("scale_model_wraith", "Wraith", ""),
        ],
    )

    vehicle_model_h4: EnumProperty(
        default="scale_model_mongoose",
        name="",
        items=[
            ("scale_model_banshee", "Banshee", ""),
            ("scale_model_broadsword", "Broadsword", ""),
            ("scale_model_ghost", "Ghost", ""),
            ("scale_model_mantis", "Mantis", ""),
            ("scale_model_mongoose", "Mongoose", ""),
        ],
    )

    vehicle_model_h2a: EnumProperty(
        default="scale_model_banshee",
        name="",
        items=[
            ("scale_model_banshee", "Banshee", ""),
        ],
    )

    def execute(self, context):
        from .scale_models import add_scale_model

        add_scale_model(self, context)
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        row = col.row(align=True)
        row.prop(self, "game", expand=True)
        row = col.row(align=True)
        row = col.row(align=True)
        row.prop(self, "unit", expand=True)
        row = col.row(align=True)
        row = col.row(align=True)
        if self.unit == "biped":
            if self.game == "reach":
                col.prop(self, "biped_model_reach")
            elif self.game == "h4":
                col.prop(self, "biped_model_h4")
            # else:
            #     col.prop(self, "biped_model_h2a")
        else:
            if self.game == "reach":
                col.prop(self, "vehicle_model_reach")
            elif self.game == "h4":
                col.prop(self, "vehicle_model_h4")
            # else:
            #     col.prop(self, "vehicle_model_h2a")


def add_halo_scale_model_button(self, context):
    self.layout.operator(
        NWO_ScaleModels_Add.bl_idname,
        text="Halo Scale Model",
        icon_value=get_icon_id("biped"),
    )

def add_halo_armature_buttons(self, context):
    self.layout.operator(
        "nwo.armature_create",
        text="Halo Pedestal",
        icon_value=get_icon_id("rig_creator"),
    ).rig = "PEDESTAL"

    self.layout.operator(
        "nwo.armature_create",
        text="Halo Unit",
        icon_value=get_icon_id("rig_creator"),
    ).rig = "UNIT"


def create_halo_collection(self, context):
    self.layout.operator("nwo.collection_create" , text="", icon_value=get_icon_id("collection_creator"))

from .halo_join import NWO_JoinHalo

def add_halo_join(self, context):
    self.layout.operator(NWO_JoinHalo.bl_idname, text="Halo Join")


#######################################
# FRAME IDS TOOL
class NWO_SetFrameIDs(Panel):
    bl_label = "Set Frame IDs"
    bl_idname = "NWO_PT_SetFrameIDs"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("frame_id"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_frame_ids = scene.nwo_frame_ids

        row = layout.row()
        row.label(text="Animation Graph Path")
        row = layout.row()
        row.prop(scene_nwo_frame_ids, "anim_tag_path", text="")
        row.scale_x = 0.25
        row.operator("nwo.graph_path")
        row = layout.row()
        row.scale_y = 1.5
        row.operator("nwo.set_frame_ids", text="Set Frame IDs")
        row = layout.row()
        row.scale_y = 1.5
        row.operator("nwo.reset_frame_ids", text="Reset Frame IDs")


class NWO_GraphPath(Operator):
    """Set the path to a model animation graph tag"""

    bl_idname = "nwo.graph_path"
    bl_label = "Find"

    filter_glob: StringProperty(
        default="*.model_*",
        options={"HIDDEN"},
    )

    filepath: StringProperty(
        name="graph_path",
        description="Set the path to the tag",
        subtype="FILE_PATH",
    )

    def execute(self, context):
        context.scene.nwo_frame_ids.anim_tag_path = self.filepath

        return {"FINISHED"}

    def invoke(self, context, event):
        self.filepath = get_tags_path()
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class NWO_SetFrameIDsOp(Operator):
    """Set frame IDs using the specified animation graph path"""

    bl_idname = "nwo.set_frame_ids"
    bl_label = "Set Frame IDs"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return len(context.scene.nwo_frame_ids.anim_tag_path) > 0

    def execute(self, context):
        from .set_frame_ids import set_frame_ids

        return set_frame_ids(context, self.report)


class NWO_ResetFrameIDsOp(Operator):
    """Resets the frame IDs to null values"""

    bl_idname = "nwo.reset_frame_ids"
    bl_label = "Reset Frame IDs"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from .set_frame_ids import reset_frame_ids

        return reset_frame_ids(context, self.report)


class NWO_SetFrameIDsPropertiesGroup(PropertyGroup):
    def graph_clean_tag_path(self, context):
        self["anim_tag_path"] = clean_tag_path(self["anim_tag_path"]).strip('"')

    anim_tag_path: StringProperty(
        name="Path to Animation Tag",
        description="Specify the full or relative path to a model animation graph",
        default="",
        update=graph_clean_tag_path,
    )


#######################################
# HALO MANAGER TOOL


class NWO_HaloLauncherExplorerSettings(Panel):
    bl_label = "Explorer Settings"
    bl_idname = "NWO_PT_HaloLauncherExplorerSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    # @classmethod
    # def poll(cls, context):
    #     return valid_nwo_asset(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        col = flow.column()
        row = col.row()
        row.prop(scene_nwo_halo_launcher, "explorer_default", expand=True)


class NWO_HaloLauncherGameSettings(Panel):
    bl_label = "Game Settings"
    bl_idname = "NWO_PT_HaloLauncherGameSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        col = flow.column()
        row = col.row()
        row.prop(scene_nwo_halo_launcher, "game_default", expand=True)
        col.separator()
        col.prop(scene_nwo_halo_launcher, "insertion_point_index")
        col.prop(scene_nwo_halo_launcher, "initial_zone_set")
        if not_bungie_game():
            col.prop(scene_nwo_halo_launcher, "initial_bsp")
        col.prop(scene_nwo_halo_launcher, "custom_functions")

        col.prop(scene_nwo_halo_launcher, "run_game_scripts")
        if not_bungie_game():
            col.prop(scene_nwo_halo_launcher, "enable_firefight")
            if scene_nwo_halo_launcher.enable_firefight:
                col.prop(scene_nwo_halo_launcher, "firefight_mission")


class NWO_HaloLauncherGamePruneSettings(Panel):
    bl_label = "Pruning"
    bl_idname = "NWO_PT_HaloLauncherGamePruneSettings"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "NWO_PT_HaloLauncherGameSettings"
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        col = flow.column()
        col.prop(scene_nwo_halo_launcher, "prune_globals")
        col.prop(scene_nwo_halo_launcher, "prune_globals_keep_playable")
        if not_bungie_game():
            col.prop(scene_nwo_halo_launcher, "prune_globals_use_empty")
            col.prop(
                scene_nwo_halo_launcher,
                "prune_models_enable_alternate_render_models",
            )
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_keep_scriptable_objects",
            )
        col.prop(scene_nwo_halo_launcher, "prune_scenario_all_lightmaps")
        col.prop(scene_nwo_halo_launcher, "prune_all_materials_use_gray_shader")
        if not_bungie_game():
            col.prop(
                scene_nwo_halo_launcher,
                "prune_all_materials_use_default_textures",
            )
            col.prop(
                scene_nwo_halo_launcher,
                "prune_all_materials_use_default_textures_fx_textures",
            )
        col.prop(scene_nwo_halo_launcher, "prune_all_material_effects")
        col.prop(scene_nwo_halo_launcher, "prune_all_dialog_sounds")
        col.prop(scene_nwo_halo_launcher, "prune_all_error_geometry")
        if not_bungie_game():
            col.prop(scene_nwo_halo_launcher, "prune_facial_animations")
            col.prop(scene_nwo_halo_launcher, "prune_first_person_animations")
            col.prop(scene_nwo_halo_launcher, "prune_low_quality_animations")
            col.prop(scene_nwo_halo_launcher, "prune_use_imposters")
            col.prop(scene_nwo_halo_launcher, "prune_cinematic_effects")
        else:
            col.prop(scene_nwo_halo_launcher, "prune_scenario_force_solo_mode")
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_force_single_bsp_zone_set",
            )
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_force_single_bsp_zones",
            )
            col.prop(scene_nwo_halo_launcher, "prune_keep_scripts")
        col.prop(scene_nwo_halo_launcher, "prune_scenario_for_environment_editing")
        if scene_nwo_halo_launcher.prune_scenario_for_environment_editing:
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_for_environment_editing_keep_cinematics",
            )
            col.prop(
                scene_nwo_halo_launcher,
                "prune_scenario_for_environment_editing_keep_scenery",
            )
            if not_bungie_game():
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_decals",
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_crates",
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_creatures",
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_pathfinding",
                )
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_editing_keep_new_decorator_block",
                )
            else:
                col.prop(
                    scene_nwo_halo_launcher,
                    "prune_scenario_for_environment_finishing",
                )


class NWO_HaloLauncherFoundationSettings(Panel):
    bl_label = "Foundation Settings"
    bl_idname = "NWO_PT_HaloLauncherFoundationSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    # @classmethod
    # def poll(cls, context):
    #     return valid_nwo_asset(context)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        col = flow.column()
        row = col.row()
        row.prop(scene_nwo_halo_launcher, "foundation_default", expand=True)
        col = layout.column(heading="Open")
        if scene_nwo_halo_launcher.foundation_default == "asset":
            if nwo_asset_type() == "MODEL":
                col.prop(scene_nwo_halo_launcher, "open_model")
                col.prop(scene_nwo_halo_launcher, "open_render_model")
                col.prop(scene_nwo_halo_launcher, "open_collision_model")
                col.prop(scene_nwo_halo_launcher, "open_physics_model")
                if len(bpy.data.actions) > 0:
                    col.prop(scene_nwo_halo_launcher, "open_model_animation_graph")
                    col.prop(scene_nwo_halo_launcher, "open_frame_event_list")
                col.separator()
                if scene.nwo.output_biped:
                    col.prop(scene_nwo_halo_launcher, "open_biped")
                if scene.nwo.output_crate:
                    col.prop(scene_nwo_halo_launcher, "open_crate")
                if scene.nwo.output_creature:
                    col.prop(scene_nwo_halo_launcher, "open_creature")
                if scene.nwo.output_device_control:
                    col.prop(scene_nwo_halo_launcher, "open_device_control")
                if scene.nwo.output_device_dispenser:
                    col.prop(scene_nwo_halo_launcher, "open_device_dispenser")
                if scene.nwo.output_device_machine:
                    col.prop(scene_nwo_halo_launcher, "open_device_machine")
                if scene.nwo.output_device_terminal:
                    col.prop(scene_nwo_halo_launcher, "open_device_terminal")
                if scene.nwo.output_effect_scenery:
                    col.prop(scene_nwo_halo_launcher, "open_effect_scenery")
                if scene.nwo.output_equipment:
                    col.prop(scene_nwo_halo_launcher, "open_equipment")
                if scene.nwo.output_giant:
                    col.prop(scene_nwo_halo_launcher, "open_giant")
                if scene.nwo.output_scenery:
                    col.prop(scene_nwo_halo_launcher, "open_scenery")
                if scene.nwo.output_vehicle:
                    col.prop(scene_nwo_halo_launcher, "open_vehicle")
                if scene.nwo.output_weapon:
                    col.prop(scene_nwo_halo_launcher, "open_weapon")
            elif nwo_asset_type() == "SCENARIO":
                col.prop(scene_nwo_halo_launcher, "open_scenario")
                col.prop(scene_nwo_halo_launcher, "open_scenario_structure_bsp")
                col.prop(scene_nwo_halo_launcher, "open_scenario_lightmap_bsp_data")
                col.prop(
                    scene_nwo_halo_launcher,
                    "open_scenario_structure_lighting_info",
                )
                if any(
                    [
                        scene_nwo_halo_launcher.open_scenario_structure_bsp,
                        scene_nwo_halo_launcher.open_scenario_lightmap_bsp_data,
                        scene_nwo_halo_launcher.open_scenario_structure_lighting_info,
                    ]
                ):
                    col.prop(scene_nwo_halo_launcher, "bsp_name")
            elif nwo_asset_type() == "SKY":
                col.prop(scene_nwo_halo_launcher, "open_model")
                col.prop(scene_nwo_halo_launcher, "open_render_model")
                col.prop(scene_nwo_halo_launcher, "open_scenery")
            elif nwo_asset_type() == "DECORATOR SET":
                col.prop(scene_nwo_halo_launcher, "open_decorator_set")
            elif nwo_asset_type() == "PARTICLE MODEL":
                col.prop(scene_nwo_halo_launcher, "open_particle_model")
            elif nwo_asset_type() == "PREFAB":
                col.prop(scene_nwo_halo_launcher, "open_prefab")
                col.prop(scene_nwo_halo_launcher, "open_scenario_structure_bsp")
                col.prop(
                    scene_nwo_halo_launcher,
                    "open_scenario_structure_lighting_info",
                )
            elif nwo_asset_type() == "FP ANIMATION":
                col.prop(scene_nwo_halo_launcher, "open_model_animation_graph")
                col.prop(scene_nwo_halo_launcher, "open_frame_event_list")


class NWO_HaloLauncher_Foundation(Operator):
    """Launches Foundation"""

    bl_idname = "nwo.launch_foundation"
    bl_label = "Foundation"

    def execute(self, context):
        from .halo_launcher import LaunchFoundation

        return LaunchFoundation(context.scene.nwo_halo_launcher, context)


class NWO_HaloLauncher_Data(Operator):
    """Opens the Data Folder"""

    bl_idname = "nwo.launch_data"
    bl_label = "Data"

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        from .halo_launcher import open_file_explorer

        return open_file_explorer(
            scene_nwo_halo_launcher.sidecar_path,
            scene_nwo_halo_launcher.explorer_default == "asset"
            and valid_nwo_asset(context),
            False,
        )


class NWO_HaloLauncher_Tags(Operator):
    """Opens the Tags Folder"""

    bl_idname = "nwo.launch_tags"
    bl_label = "Tags"

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        from .halo_launcher import open_file_explorer

        return open_file_explorer(
            scene_nwo_halo_launcher.sidecar_path,
            scene_nwo_halo_launcher.explorer_default == "asset"
            and valid_nwo_asset(context),
            True,
        )


class NWO_HaloLauncher_Sapien(Operator):
    """Opens Sapien"""

    bl_idname = "nwo.launch_sapien"
    bl_label = "Sapien"

    filter_glob: StringProperty(
        default="*.scenario",
        options={"HIDDEN"},
    )

    filepath: StringProperty(
        name="filepath",
        description="Set path for the scenario",
        subtype="FILE_PATH",
    )

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        from .halo_launcher import launch_game

        return launch_game(True, scene_nwo_halo_launcher, self.filepath)

    def invoke(self, context, event):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        if (
            scene_nwo_halo_launcher.game_default == "default"
            or not valid_nwo_asset(context)
            or nwo_asset_type() != "SCENARIO"
        ):
            self.filepath = get_tags_path()
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = ""
            return self.execute(context)


class NWO_HaloLauncher_TagTest(Operator):
    """Opens Tag Test"""

    bl_idname = "nwo.launch_tagtest"
    bl_label = "Tag Test"

    filter_glob: StringProperty(
        default="*.scenario",
        options={"HIDDEN"},
    )

    filepath: StringProperty(
        name="filepath",
        description="Set path for the scenario",
        subtype="FILE_PATH",
    )

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        from .halo_launcher import launch_game

        return launch_game(False, scene_nwo_halo_launcher, self.filepath)

    def invoke(self, context, event):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        if (
            scene_nwo_halo_launcher.game_default == "default"
            or not valid_nwo_asset(context)
            or nwo_asset_type() != "SCENARIO"
        ):
            self.filepath = get_tags_path()
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = ""
            return self.execute(context)


class NWO_HaloLauncherPropertiesGroup(PropertyGroup):
    sidecar_path: StringProperty(
        name="",
        description="",
        default="",
    )
    asset_name: StringProperty(
        name="",
        description="",
        default="",
    )

    explorer_default: EnumProperty(
        name="Folder",
        description="Select whether to open the root data / tags folder or the one for your asset. When no asset is found, defaults to root",
        default="asset",
        options=set(),
        items=[("default", "Root", ""), ("asset", "Asset", "")],
    )

    foundation_default: EnumProperty(
        name="Tags",
        description="Select whether Foundation should open with the last opended windows, or open to the selected asset tags",
        default="asset",
        options=set(),
        items=[
            ("last", "Default", ""),
            ("asset", "Asset", ""),
            ("material", "Materials", ""),
        ],
    )

    game_default: EnumProperty(
        name="Scenario",
        description="Select whether to open Sapien / Tag Test and select a scenario, or open the current scenario asset if it exists",
        default="asset",
        options=set(),
        items=[("default", "Browse", ""), ("asset", "Asset", "")],
    )

    open_model: BoolProperty(
        name="Model",
        default=True,
        options=set(),
    )

    open_render_model: BoolProperty(options=set(), name="Render Model")

    open_collision_model: BoolProperty(options=set(), name="Collision Model")

    open_physics_model: BoolProperty(options=set(), name="Physics Model")

    open_model_animation_graph: BoolProperty(
        options=set(), name="Model Animation Graph"
    )

    open_frame_event_list: BoolProperty(options=set(), name="Frame Event List")

    open_biped: BoolProperty(options=set(), name="Biped")

    open_crate: BoolProperty(options=set(), name="Crate")

    open_creature: BoolProperty(options=set(), name="Creature")

    open_device_control: BoolProperty(options=set(), name="Device Control")

    open_device_dispenser: BoolProperty(options=set(), name="Device Dispenser")

    open_device_machine: BoolProperty(options=set(), name="Device Machine")

    open_device_terminal: BoolProperty(options=set(), name="Device Terminal")

    open_effect_scenery: BoolProperty(options=set(), name="Effect Scenery")

    open_equipment: BoolProperty(options=set(), name="Equipment")

    open_giant: BoolProperty(options=set(), name="Giant")

    open_scenery: BoolProperty(options=set(), name="Scenery")

    open_vehicle: BoolProperty(options=set(), name="Vehicle")

    open_weapon: BoolProperty(options=set(), name="Weapon")

    open_scenario: BoolProperty(options=set(), name="Scenario", default=True)

    open_prefab: BoolProperty(options=set(), name="Prefab", default=True)

    open_particle_model: BoolProperty(
        options=set(), name="Particle Model", default=True
    )

    open_decorator_set: BoolProperty(options=set(), name="Decorator Set", default=True)

    bsp_name: StringProperty(
        options=set(),
        name="BSP Name(s)",
        description="Input the bsps to open. Comma delimited for multiple bsps. Leave blank to open all bsps",
        default="",
    )

    open_scenario_structure_bsp: BoolProperty(
        options=set(),
        name="BSP",
    )

    open_scenario_lightmap_bsp_data: BoolProperty(
        options=set(),
        name="Lightmap Data",
    )

    open_scenario_structure_lighting_info: BoolProperty(
        options=set(),
        name="Lightmap Info",
    )

    ##### game launch #####

    run_game_scripts: BoolProperty(
        options=set(),
        description="Runs all startup & continuous scripts on map load",
        name="Run Game Scripts",
    )

    prune_globals: BoolProperty(
        options=set(),
        description="Strips all player information, global materials, grenades and powerups from the globals tag, as well as interface global tags. Don't use this if you need the game to be playable",
        name="Globals",
    )

    prune_globals_keep_playable: BoolProperty(
        options=set(),
        description="Strips player information (keeping one single player element), global materials, grenades and powerups. Keeps the game playable.",
        name="Globals (Keep Playable)",
    )

    prune_globals_use_empty: BoolProperty(
        options=set(),
        description="Uses global_empty.globals instead of globals.globals",
        name="Globals Use Empty",
    )

    prune_models_enable_alternate_render_models: BoolProperty(
        options=set(),
        description="Allows tag build to use alternative render models specified in the .model",
        name="Allow Alternate Render Models",
    )

    prune_scenario_keep_scriptable_objects: BoolProperty(
        options=set(),
        description="Attempts to run scripts while pruning",
        name="Keep Scriptable Objects",
    )

    prune_scenario_for_environment_editing: BoolProperty(
        options=set(),
        description="Removes everything but the environment: Weapons, vehicles, bipeds, equipment, cinematics, AI, etc",
        name="Prune for Environment Editing",
    )

    prune_scenario_for_environment_editing_keep_cinematics: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of cutscene flags and cinematics",
        name="Keep Cinematics",
    )

    prune_scenario_for_environment_editing_keep_scenery: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of scenery",
        name="Keep Scenery",
    )

    prune_scenario_for_environment_editing_keep_decals: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decals",
        name="Keep Decals",
    )

    prune_scenario_for_environment_editing_keep_crates: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of crates",
        name="Keep Crates",
    )

    prune_scenario_for_environment_editing_keep_creatures: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of creatures",
        name="Keep Creatures",
    )

    prune_scenario_for_environment_editing_keep_pathfinding: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of pathfinding",
        name="Keep Pathfinding",
    )

    prune_scenario_for_environment_editing_keep_new_decorator_block: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decorators",
        name="Keep Decorators",
    )

    prune_scenario_all_lightmaps: BoolProperty(
        options=set(),
        description="Loads the scenario without lightmaps",
        name="Prune Lightmaps",
    )

    prune_all_materials_use_gray_shader: BoolProperty(
        options=set(),
        description="Replaces all shaders in the scene with a gray shader, allowing designers to load larger zone sets (the game looks gray, but without artifacts)",
        name="Use Gray Shader",
    )

    prune_all_materials_use_default_textures: BoolProperty(
        options=set(),
        description="Replaces all material textures in the scene with the material shader's default, allowing designers to load larger zone sets",
        name="Use Default Textures",
    )

    prune_all_materials_use_default_textures_fx_textures: BoolProperty(
        options=set(),
        description="Loads only material textures related to FX, all other material textures will show up as the shader's default",
        name="Include FX materials",
    )

    prune_all_material_effects: BoolProperty(
        options=set(),
        description="Loads the scenario without material effects",
        name="Prune Material Effects",
    )

    prune_all_dialog_sounds: BoolProperty(
        options=set(),
        description="Removes all dialog sounds referenced in the globals tag",
        name="Prune Material Effects",
    )

    prune_all_error_geometry: BoolProperty(
        options=set(),
        description="If you're working on geometry and don't need to see the (40+ MB of) data that gets loaded in tags then you should enable this command",
        name="Prune Error Geometry",
    )

    prune_facial_animations: BoolProperty(
        options=set(),
        description="Skips loading the PCA data for facial animations",
        name="Prune Facial Animations",
    )

    prune_first_person_animations: BoolProperty(
        options=set(),
        description="Skips laoding the first-person animations",
        name="Prune First Person Animations",
    )

    prune_low_quality_animations: BoolProperty(
        options=set(),
        description="Use low-quality animations if they are available",
        name="Use Low Quality Animations",
    )

    prune_use_imposters: BoolProperty(
        options=set(),
        description="Uses imposters if they available",
        name="Use Imposters only",
    )

    prune_cinematic_effects: BoolProperty(
        options=set(),
        description="Skips loading and player cinematic effects",
        name="Prune Cinematic Effects",
    )
    # REACH Only prunes
    prune_scenario_force_solo_mode: BoolProperty(
        options=set(),
        description="Forces the map to be loaded in solo mode even if it is a multiplayer map. The game will look for a solo map spawn point",
        name="Force Solo Mode",
    )

    prune_scenario_for_environment_finishing: BoolProperty(
        options=set(),
        description="Supersedes prune_scenario_for_environment_editing, with the inclusion of decals, scenery, crates and decorators",
        name="Prune Finishing",
    )

    prune_scenario_force_single_bsp_zone_set: BoolProperty(
        options=set(),
        description="Removes all but the first BSP from the initial zone set. Ensures that the initial zone set will not crash on load due to low memory",
        name="Prune Zone Sets",
    )

    prune_scenario_force_single_bsp_zones: BoolProperty(
        options=set(),
        description="Add single bsp zone sets (for each BSP) to the debug menu",
        name="Single BSP zone sets",
    )

    prune_keep_scripts: BoolProperty(
        options=set(),
        description="Attempts to run scripts while pruning",
        name="Keep Scripts",
    )
    # Other
    enable_firefight: BoolProperty(options=set(), name="Enable Spartan Ops")

    firefight_mission: StringProperty(
        options=set(),
        name="Spartan Ops Mission",
        description="Set the string that matches the spartan ops mission that should be loaded",
        default="",
    )

    insertion_point_index: IntProperty(
        options=set(),
        name="Insertion Point Index",
        default=-1,
        min=-1,
        soft_max=4,
    )

    initial_zone_set: StringProperty(
        options=set(),
        name="Initial Zone Set",
        description="Opens the scenario to the zone set specified. This should match a zone set defined in the .scenario tag",
    )

    initial_bsp: StringProperty(
        options=set(),
        name="Initial BSP",
        description="Opens the scenario to the bsp specified. This should match a bsp name in your blender scene",
    )

    custom_functions: StringProperty(
        options=set(),
        name="Custom",
        description="Name of Blender blender text editor file to get custom init lines from. If no such text exists, instead looks in the root editing kit for an init.txt with this name. If this doesn't exist, then the actual text is used instead",
        default="",
    )


#######################################
# SHADER FINDER TOOL


class NWO_ShaderFinder(Panel):
    bl_label = "Shader Finder"
    bl_idname = "NWO_PT_ShaderFinder"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"INSTANCED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_shader_finder = scene.nwo_shader_finder

        col = layout.column(heading="Shaders Directory (Optional)")
        col.prop(scene_nwo_shader_finder, "shaders_dir", text="")
        col.prop(
            scene_nwo_shader_finder,
            "overwrite_existing",
            text="Overwrite Existing Paths",
        )
        col.prop(
            scene_nwo_shader_finder,
            "set_non_export",
            text="Disable export if no tag path found",
        )



class NWO_ShaderFinder_Find(Operator):
    """Searches the tags folder for shaders (or the specified directory) and applies all that match blender material names"""

    bl_idname = "nwo.shader_finder"
    bl_label = ""
    bl_options = {"UNDO"}

    def execute(self, context):
        scene = context.scene
        scene_nwo_shader_finder = scene.nwo_shader_finder
        from .shader_finder import find_shaders

        return find_shaders(
            bpy.data.materials,
            not_bungie_game(),
            self.report,
            scene_nwo_shader_finder.shaders_dir,
            scene_nwo_shader_finder.overwrite_existing,
            scene_nwo_shader_finder.set_non_export,
        )

    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str:
        if not_bungie_game():
            return "Update Halo Material path"
        else:
            return "Update Halo Shader Path"

class NWO_ShaderFinder_FindSingle(NWO_ShaderFinder_Find):
    bl_idname = "nwo.shader_finder_single"

    def execute(self, context):
        scene = context.scene
        scene_nwo_shader_finder = scene.nwo_shader_finder
        from .shader_finder import find_shaders

        return find_shaders(
            [context.object.active_material],
            not_bungie_game(),
            self.report,
            scene_nwo_shader_finder.shaders_dir,
            True,
            False,
        )

class NWO_HaloShaderFinderPropertiesGroup(PropertyGroup):
    shaders_dir: StringProperty(
        name="Shaders Directory",
        description="Leave blank to search the entire tags folder for shaders or input a directory path to specify the folder (and sub-folders) to search for shaders",
        default="",
    )
    overwrite_existing: BoolProperty(
        name="Overwrite Shader Paths",
        options=set(),
        description="Overwrite material shader paths even if they're not blank",
        default=False,
    )
    set_non_export: BoolProperty(
        name="Set Non Export",
        options=set(),
        description="Disables the export property for materials that Foundry could not find a tag path for",
        default=False,
    )


#######################################
# HALO EXPORT TOOL


class NWO_HaloExportSettings(Panel):
    bl_label = "Quick Export Settings"
    bl_idname = "NWO_PT_HaloExportSettings"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        h4 = scene.nwo.game_version in ("h4", "h2a")
        asset_type = scene.nwo.asset_type
        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(scene_nwo_export, "export_quick", text="Quick Export")
        col.prop(scene_nwo_export, "show_output", text="Toggle Output")
        col.prop(scene_nwo_export, "export_gr2_files", text="Export Tags")
        scenario = asset_type == "SCENARIO"
        render = asset_type in ("MODEL", "SKY")
        if (h4 and render) or scenario:
            if scenario:
                lighting_name = "Light Scenario"
            else:
                lighting_name = "Light Model"

            col.prop(scene_nwo_export, "lightmap_structure", text=lighting_name)
            if scene_nwo_export.lightmap_structure:
                if asset_type == "SCENARIO":
                    if h4:
                        col.prop(scene_nwo_export, "lightmap_quality_h4")
                    else:
                        col.prop(scene_nwo_export, "lightmap_quality")
                    if not scene_nwo_export.lightmap_all_bsps:
                        col.prop(scene_nwo_export, "lightmap_specific_bsp")
                    col.prop(scene_nwo_export, "lightmap_all_bsps")
                    if not h4:
                        col.prop(scene_nwo_export, "lightmap_region")


class NWO_HaloExportSettingsScope(Panel):
    bl_label = "Scope"
    bl_idname = "NWO_PT_HaloExportSettingsScope"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "NWO_PT_HaloExportSettings"
    bl_region_type = "HEADER"

    @classmethod
    def poll(self, context):
        return context.scene.nwo_export.export_gr2_files

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_export = scene.nwo_export
        scene_nwo = scene.nwo

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col = layout.column(heading="Include")

        if scene_nwo.asset_type == "MODEL":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")
            col.prop(scene_nwo_export, "export_collision")
            col.prop(scene_nwo_export, "export_physics")
            col.prop(scene_nwo_export, "export_markers")
            col.prop(scene_nwo_export, "export_skeleton")
            col.prop(scene_nwo_export, "export_animations", expand=True)
        elif scene_nwo.asset_type == "FP ANIMATION":
            col.prop(scene_nwo_export, "export_skeleton")
            col.prop(scene_nwo_export, "export_animations", expand=True)
        elif scene_nwo.asset_type == "SCENARIO":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_structure")
            col.prop(scene_nwo_export, "export_design", text="Design")
        elif scene_nwo.asset_type != "PREFAB":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")

        if scene_nwo.asset_type == "SCENARIO":
            col.prop(scene_nwo_export, "export_all_bsps", expand=True)
        if scene_nwo.asset_type in (("MODEL", "SCENARIO", "PREFAB")):
            if scene_nwo.asset_type == "MODEL":
                txt = "Permutations"
            else:
                txt = "Subgroup"
            col.prop(scene_nwo_export, "export_all_perms", expand=True, text=txt)


class NWO_HaloExportSettingsFlags(Panel):
    bl_label = "Flags"
    bl_idname = "NWO_PT_HaloExportSettingsFlags"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "NWO_PT_HaloExportSettings"
    bl_region_type = "HEADER"

    @classmethod
    def poll(self, context):
        return context.scene.nwo_export.export_gr2_files

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo = scene.nwo
        scene_nwo_export = scene.nwo_export
        h4 = scene_nwo.game_version != "reach"
        scenario = scene_nwo.asset_type == "SCENARIO"
        prefab = scene_nwo.asset_type == "PREFAB"

        layout.use_property_split = False
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        if h4:
            col.prop(scene_nwo_export, "import_force", text="Force full export")
            if scenario or prefab:
                if scenario:
                    col.prop(
                        scene_nwo_export,
                        "import_seam_debug",
                        text="Show more seam debugging info",
                    )
                    col.prop(
                        scene_nwo_export,
                        "import_skip_instances",
                        text="Skip importing instances",
                    )
                col.prop(
                    scene_nwo_export,
                    "import_meta_only",
                    text="Only import structure_meta tag",
                )
                col.prop(
                    scene_nwo_export,
                    "import_lighting",
                    text="Only reimport lighting information",
                )
                col.prop(
                    scene_nwo_export,
                    "import_disable_hulls",
                    text="Skip instance convex hull decomp",
                )
                col.prop(
                    scene_nwo_export,
                    "import_disable_collision",
                    text="Don't generate complex collision",
                )
            else:
                col.prop(
                    scene_nwo_export, "import_no_pca", text="Skip PCA calculations"
                )
                col.prop(
                    scene_nwo_export,
                    "import_force_animations",
                    text="Force import error animations",
                )
        else:
            col.prop(scene_nwo_export, "import_force", text="Force full export")
            col.prop(scene_nwo_export, "import_verbose", text="Verbose Output")
            col.prop(
                scene_nwo_export,
                "import_surpress_errors",
                text="Don't write errors to VRML",
            )
            if scenario:
                col.prop(
                    scene_nwo_export,
                    "import_seam_debug",
                    text="Show more seam debugging info",
                )
                col.prop(
                    scene_nwo_export,
                    "import_skip_instances",
                    text="Skip importing instances",
                )
                col.prop(
                    scene_nwo_export,
                    "import_decompose_instances",
                    text="Run convex physics decomposition",
                )
            else:
                col.prop(scene_nwo_export, "import_draft", text="Skip PRT generation")


class NWO_HaloExport(Operator):
    bl_idname = "nwo.export_quick"
    bl_label = "Quick Export"
    bl_options = {"UNDO"}
    bl_description = "Exports the current Halo asset and creates tags"

    def execute(self, context):
        from .halo_export import export_quick, export

        scene = context.scene
        scene_nwo_export = scene.nwo_export
        if scene_nwo_export.export_quick and valid_nwo_asset(context):
            return export_quick(
                bpy.ops.export_scene.nwo,
                self.report,
                scene_nwo_export.export_gr2_files,
                scene_nwo_export.export_all_bsps,
                scene_nwo_export.export_all_perms,
                scene_nwo_export.import_to_game,
                scene_nwo_export.import_draft,
                scene_nwo_export.lightmap_structure,
                scene_nwo_export.lightmap_quality_h4,
                scene_nwo_export.lightmap_region,
                scene_nwo_export.lightmap_quality,
                scene_nwo_export.lightmap_specific_bsp,
                scene_nwo_export.lightmap_all_bsps,
                scene_nwo_export.export_animations,
                scene_nwo_export.export_skeleton,
                scene_nwo_export.export_render,
                scene_nwo_export.export_collision,
                scene_nwo_export.export_physics,
                scene_nwo_export.export_markers,
                scene_nwo_export.export_structure,
                scene_nwo_export.export_design,
            )
        else:
            return export(bpy.ops.export_scene.nwo)


class NWO_HaloExportPropertiesGroup(PropertyGroup):
    export_gr2_files: BoolProperty(
        name="Export GR2 Files",
        default=True,
        options=set(),
    )
    # export_hidden: BoolProperty(
    #     name="Hidden",
    #     description="Export visible objects only",
    #     default=True,
    #     options=set(),
    # )
    export_all_bsps: EnumProperty(
        name="BSPs",
        description="Specify whether to export all BSPs, or just those selected",
        default="all",
        items=[("all", "All", ""), ("selected", "Selected", "")],
        options=set(),
    )
    export_all_perms: EnumProperty(
        name="Perms",
        description="Specify whether to export all permutations, or just those selected",
        default="all",
        items=[("all", "All", ""), ("selected", "Selected", "")],
        options=set(),
    )
    # export_sidecar_xml: BoolProperty(
    #     name="Build Sidecar",
    #     description="",
    #     default=True,
    #     options=set(),
    # )
    import_to_game: BoolProperty(
        name="Import to Game",
        description="",
        default=True,
        options=set(),
    )
    export_quick: BoolProperty(
        name="Quick Export",
        description="Exports the scene without a file dialog, provided this scene is a Halo asset",
        default=True,
        options=set(),
    )
    import_draft: BoolProperty(
        name="Draft",
        description="Skip generating PRT data. Faster speed, lower quality",
        default=False,
        options=set(),
    )
    lightmap_structure: BoolProperty(
        name="Burn Lighting",
        default=False,
        options=set(),
    )

    def item_lightmap_quality_h4(self, context):
        items = []
        items.append(
            (
                "asset",
                "Asset",
                "The user defined lightmap settings. Opens a settings dialog",
                0,
            )
        )
        lightmapper_globals_dir = path_join(
            get_tags_path(), "globals", "lightmapper_settings"
        )
        if file_exists(lightmapper_globals_dir):
            from os import listdir

            index = 1
            for file in listdir(lightmapper_globals_dir):
                if file.endswith(".lightmapper_globals"):
                    file_no_ext = dot_partition(file)
                    items.append(bpy_enum(file_no_ext, index))
                    index += 1
        return items

    lightmap_quality_h4: EnumProperty(
        name="Quality",
        options=set(),
        items=item_lightmap_quality_h4,
        description="Define the lightmap quality you wish to use",
    )

    lightmap_region: StringProperty(
        name="Region",
        description="Lightmap region to use for lightmapping",
    )

    lightmap_quality: EnumProperty(
        name="Quality",
        items=(
            ("DIRECT", "Direct", ""),
            ("DRAFT", "Draft", ""),
            ("LOW", "Low", ""),
            ("MEDIUM", "Medium", ""),
            ("HIGH", "High", ""),
            ("SUPER", "Super (very slow)", ""),
        ),
        default="DIRECT",
        options=set(),
        description="Define the lightmap quality you wish to use",
    )
    lightmap_all_bsps: BoolProperty(
        name="All BSPs",
        default=True,
        options=set(),
    )
    lightmap_specific_bsp: StringProperty(
        name="Specific BSP",
        default="",
        options=set(),
    )
    ################################
    # Detailed settings
    ###############################
    export_animations: EnumProperty(
        name="Animations",
        description="",
        default="ALL",
        items=[
            ("ALL", "All", ""),
            ("ACTIVE", "Active", ""),
            ("NONE", "None", ""),
        ],
        options=set(),
    )
    export_skeleton: BoolProperty(
        name="Skeleton",
        description="",
        default=True,
        options=set(),
    )
    export_render: BoolProperty(
        name="Render Models",
        description="",
        default=True,
        options=set(),
    )
    export_collision: BoolProperty(
        name="Collision Models",
        description="",
        default=True,
        options=set(),
    )
    export_physics: BoolProperty(
        name="Physics Models",
        description="",
        default=True,
        options=set(),
    )
    export_markers: BoolProperty(
        name="Markers",
        description="",
        default=True,
        options=set(),
    )
    export_structure: BoolProperty(
        name="Structure",
        description="",
        default=True,
        options=set(),
    )
    export_design: BoolProperty(
        name="Structure Design",
        description="",
        default=True,
        options=set(),
    )
    # use_mesh_modifiers: BoolProperty(
    #     name="Apply Modifiers",
    #     description="",
    #     default=True,
    #     options=set(),
    # )
    # global_scale: FloatProperty(
    #     name="Scale",
    #     description="",
    #     default=1.0,
    #     options=set(),
    # )
    # use_armature_deform_only: BoolProperty(
    #     name="Deform Bones Only",
    #     description="Only export bones with the deform property ticked",
    #     default=True,
    #     options=set(),
    # )
    # meshes_to_empties: BoolProperty(
    #     name="Markers as Empties",
    #     description="Export all mesh Halo markers as empties. Helps save on export / import time and file size",
    #     default=True,
    #     options=set(),
    # )

    # def get_show_output(self):
    #     global is_blender_startup
    #     if is_blender_startup:
    #         print("Startup check")
    #         is_blender_startup = False
    #         file_path = os.path.join(bpy.app.tempdir, "foundry_output.txt")
    #         if file_exists(file_path):
    #             with open(file_path, "r") as f:
    #                 state = f.read()

    #             if state == "True":
    #                 return True
    #             else:
    #                 return False

    #     return self.get("show_output", False)

    # def set_show_output(self, value):
    #     self["show_output"] = value

    def update_show_output(self, context):
        file_path = os.path.join(bpy.app.tempdir, "foundry_output.txt")
        if file_exists(file_path):
            with open(file_path, "w") as f:
                f.write(str(self.show_output))

    show_output: BoolProperty(
        name="Toggle Output",
        description="Select whether or not the output console should toggle at export",
        options=set(),
        # get=get_show_output,
        # set=set_show_output,
        update=update_show_output,
    )

    # keep_fbx: BoolProperty(
    #     name="FBX",
    #     description="Keep the source FBX file after GR2 conversion",
    #     default=False,
    #     options=set(),
    # )
    # keep_json: BoolProperty(
    #     name="JSON",
    #     description="Keep the source JSON file after GR2 conversion",
    #     default=False,
    #     options=set(),
    # )

    import_force: BoolProperty(
        name="Force",
        description="Force all files to import even if they haven't changed",
        default=False,
    )
    import_verbose: BoolProperty(
        name="Verbose",
        description="Write additional import progress information to the console",
        default=False,
    )
    import_draft: BoolProperty(
        name="Draft",
        description="Skip generating PRT data. Faster speed, lower quality",
        default=False,
    )
    import_seam_debug: BoolProperty(
        name="Seam Debug",
        description="Write extra seam debugging information to the console",
        default=False,
    )
    import_skip_instances: BoolProperty(
        name="Skip Instances",
        description="Skip importing all instanced geometry",
        default=False,
    )
    import_decompose_instances: BoolProperty(
        name="Decompose Instances",
        description="Run convex decomposition for instanced geometry physics (very slow)",
        default=False,
    )
    import_surpress_errors: BoolProperty(
        name="Surpress Errors",
        description="Do not write errors to vrml files",
        default=False,
    )
    import_lighting: BoolProperty(
        name="Lighting Info Only",
        description="Only the scenario_structure_lighting_info tag will be reimported",
        default=False,
    )
    import_meta_only: BoolProperty(
        name="Meta Only",
        description="Import only the structure_meta tag",
        default=False,
    )
    import_disable_hulls: BoolProperty(
        name="Disable Hulls",
        description="Disables the contruction of convex hulls for instance physics and collision",
        default=False,
    )
    import_disable_collision: BoolProperty(
        name="Disable Collision",
        description="Do not generate complex collision",
        default=False,
    )
    import_no_pca: BoolProperty(
        name="No PCA",
        description="Skips PCA calculations",
        default=False,
    )
    import_force_animations: BoolProperty(
        name="Force Animations",
        description="Force import of all animations that had errors during the last import",
        default=False,
    )


#######################################
# PROPERTIES MANAGER TOOL


class NWO_PropertiesManager(Panel):
    bl_label = "Halo Object Tools"
    bl_idname = "NWO_PT_PropertiesManager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    def draw(self, context):
        layout = self.layout

        # if context.scene.nwo.asset_type == 'SCENARIO':
        #     layout.operator("nwo.auto_seam", icon_value=get_icon_id("seam"))


class NWO_CollectionManager(Panel):
    bl_label = "Collection Creator"
    bl_idname = "NWO_PT_CollectionManager"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("collection_creator"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_collection_manager = scene.nwo_collection_manager

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(scene_nwo_collection_manager, "collection_name", text="Name")
        col.prop(scene_nwo_collection_manager, "collection_type", text="Type")
        col = col.row()
        col.scale_y = 1.5
        col.operator("nwo.collection_create")


class NWO_CollectionManager_Create(Operator):
    bl_idname = "nwo.collection_create"
    bl_label = "New Halo Collection"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Creates a Halo collection with the specified name and type"

    def collection_type_items(self, context):
        items = []
        asset_type = context.scene.nwo.asset_type
        if asset_type in ("SCENARIO", "PREFAB"):
            items.append(("PERMUTATION", "Subgroup", ""))
            if asset_type == "SCENARIO":
                items.insert(0, ("BSP", "BSP", ""))
        elif asset_type in ("MODEL", "SKY"):
            items.append(("REGION", "Region", ""))
            if asset_type == "MODEL":
                items.insert(0, ("PERMUTATION", "Permutation", ""))

        items.append(("EXCLUDE", "Exclude", ""))

        return items

    type : EnumProperty(items=collection_type_items)
    name : StringProperty()

    def execute(self, context):
        from .collection_manager import create_collections

        return create_collections(
            context,
            bpy.ops,
            bpy.data,
            self.type,
            self.name,
            False
        )
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "type", text="Type", expand=True)
        row = layout.row()
        row.activate_init = True
        row.prop(self, "name", text="Name")
        
class NWO_CollectionManager_CreateMove(NWO_CollectionManager_Create):
    bl_idname = "nwo.collection_create_move"
    bl_label = "Move to Halo Collection"
    bl_description = "Creates a Halo collection with the specified name and type. Adds all currently selected objects to it"

    def execute(self, context):
        from .collection_manager import create_collections

        return create_collections(
            context,
            bpy.ops,
            bpy.data,
            self.type,
            self.name,
            True,
        )

class NWO_MT_CollectionManager(Operator):
    def draw(self, context):
        pass

class NWO_ArmatureCreator(Panel):
    bl_label = "Rig Creator"
    bl_idname = "NWO_PT_ArmatureCreator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_AnimationTools"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("rig_creator"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_armature_creator = scene.nwo_armature_creator

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.prop(
            scene_nwo_armature_creator,
            "armature_type",
            text="Type",
            expand=True,
        )
        col = layout.column(heading="Include")
        sub = col.column(align=True)
        sub.prop(scene_nwo_armature_creator, "control_rig", text="Control Rig")
        col = col.row()
        col.scale_y = 1.5
        col.operator("nwo.armature_create")


class NWO_ArmatureCreator_Create(Operator):
    """Creates the specified armature"""

    bl_idname = "nwo.armature_create"
    bl_label = "Create Armature"
    bl_options = {"REGISTER", "UNDO"}

    rig : StringProperty()

    def execute(self, context):
        scene = context.scene
        from .armature_creator import armature_create

        return armature_create(
            context,
            self.rig,
        )
    
    @classmethod
    def description(cls, context, properties):
        if properties.rig == 'PEDESTAL':
            return "Creates a Halo rig with a pedestal deform and control bone"
        elif properties.rig == 'UNIT':
            return ("Creates a Halo rig requried for a unit (biped / vehicle / giant). "
            "Includes a pedestal bone, and pitch and yaw bones (with a controller) necessary "
            "for pose overlay animations (e.g. aiming / steering)"
            )


class NWO_ArmatureCreatorPropertiesGroup(PropertyGroup):
    armature_type: EnumProperty(
        name="Armature Type",
        options=set(),
        description="Creates a Halo armature of the specified type",
        default="PEDESTAL",
        items=[
            ("PEDESTAL", "Pedestal", "Creates a single bone Halo armature"),
            (
                "UNIT",
                "Unit",
                "Creates a rig consisting of a pedestal bone, and a pitch and yaw bone. For bipeds and vehicles",
            ),
        ],
    )
    control_rig: BoolProperty(
        name="Use Control Rig",
        description="If True, adds a control rig to the specified armature",
        default=True,
        options=set(),
    )


class NWO_CopyHaloProps(Panel):
    bl_label = "Copy Halo Properties"
    bl_idname = "NWO_PT_CopyHaloProps"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.scale_y = 1.5
        col.operator("nwo.props_copy")


class NWO_CopyHaloProps_Copy(Operator):
    """Copies all halo properties from the active object to selected objects"""

    bl_idname = "nwo.props_copy"
    bl_label = "Copy Properties"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Copy Halo Properties from the active object to selected objects"

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 1

    def execute(self, context):
        from .copy_props import CopyProps

        return CopyProps(
            self.report,
            context.view_layer.objects.active,
            context.selected_objects,
        )


class NWO_AMFHelper(Panel):
    bl_label = "Object Importer"
    bl_idname = "NWO_PT_AMFHelper"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("import_helper"))

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
        col = flow.column()
        col.operator("nwo.amf_assign")


class NWO_AMFHelper_Assign(Operator):
    """Sets regions and permutations for all scene objects which use the AMF naming convention [region:permutation]"""

    bl_idname = "nwo.amf_assign"
    bl_label = "Set Regions/Perms"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Sets regions and permutations for all scene objects which use the AMF naming convention [region:permutation]"

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def execute(self, context):
        from .amf_helper import amf_assign

        return amf_assign(context, self.report)


class NWO_JMSHelper(Panel):
    bl_label = "JMS Helper"
    bl_idname = "NWO_PT_JMSHelper"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    @classmethod
    def poll(cls, context):
        return False

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
        col = flow.column()
        game_version = context.scene.nwo.game_version
        if game_version == "reach":
            col.operator("nwo.jms_assign", text="JMS -> Reach Asset")
        elif game_version == "h4":
            col.operator("nwo.jms_assign", text="JMS -> H4 Asset")
        else:
            col.operator("nwo.jms_assign", text="JMS -> H2AMP Asset")


class NWO_JMSHelper_Assign(Operator):
    """Splits the active object into it's face maps and assigns a new name for each new object to match the AMF naming convention, as well as setting the proper region & permutation. Collision and physics prefixes are retained"""

    bl_idname = "nwo.jms_assign"
    bl_label = "JMS -> NWO Asset"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Splits the active object into it's face maps and assigns a new name for each new object to match the AMF naming convention, as well as setting the proper region & permutation. Collision and physics prefixes are retained"

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def execute(self, context):
        from .jms_helper import jms_assign

        return jms_assign(context, self.report)


class NWO_AMFHelper(Panel):
    bl_label = "Object Importer"
    bl_idname = "NWO_PT_AMFHelper"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_PropertiesManager"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("import_helper"))

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
        col = flow.column()
        col.operator("nwo.amf_assign")


class NWO_AutoSeam(Operator):
    bl_idname = "nwo.auto_seam"
    bl_label = "Auto Seam"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Automatically adds bsp seams to the blend scene"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        from .auto_seam import auto_seam

        return auto_seam(context)


class NWO_AnimationTools(Panel):
    bl_label = "Halo Animation Tools"
    bl_idname = "NWO_PT_AnimationTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    def draw(self, context):
        layout = self.layout


class NWO_GunRigMaker(Panel):
    bl_label = "Rig gun to FP Arms"
    bl_idname = "NWO_PT_GunRigMaker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_AnimationTools"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.operator("nwo.build_rig")


class NWO_GunRigMaker_Start(Operator):
    """Joins a gun armature to an first person armature and builds an appropriate rig. Ensure both the FP and Gun rigs are selected before use"""

    bl_idname = "nwo.build_rig"
    bl_label = "Rig Gun to FP"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Joins a gun armature to an first person armature and builds an appropriate rig. Ensure both the FP and Gun rigs are selected before use"

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.object.type == "ARMATURE"
            and context.object.mode == "OBJECT"
            and len(context.selected_objects) > 1
        )

    def execute(self, context):
        from .rig_gun_to_fp import build_rig

        return build_rig(self.report, context.selected_objects)


class NWO_MaterialsManager(Panel):
    bl_label = "Halo Material Tools"
    bl_idname = "NWO_PT_MaterialTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    # bl_options = {'DEFAULT_CLOSED'}
    bl_category = "Foundry"

    def draw(self, context):
        layout = self.layout


class NWO_BitmapExport(Panel):
    bl_label = "Bitmap Exporter"
    bl_idname = "NWO_PT_BitmapExport"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_MaterialTools"

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("texture_export"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo_bitmap_export = scene.nwo_bitmap_export

        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.scale_y = 1.5
        col.operator("nwo.export_bitmaps")
        col.separator()
        col = flow.column(heading="Overwrite")
        col.prop(scene_nwo_bitmap_export, "overwrite", text="Existing")
        row = col.row()
        row.prop(scene_nwo_bitmap_export, "bitmaps_selection", expand=True)
        col.prop(scene_nwo_bitmap_export, "export_type")


class NWO_BitmapExport_Export(Operator):
    """Exports TIFFs for the active material and imports them into the game as bitmaps"""

    bl_idname = "nwo.export_bitmaps"
    bl_label = "Export Bitmaps"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Exports TIFFs for the active material and imports them into the game as bitmaps"

    @classmethod
    def poll(cls, context):
        return managed_blam_active() and (
            context.object.active_material
            or context.scene.nwo_bitmap_export.bitmaps_selection == "all"
        )

    def execute(self, context):
        scene = context.scene
        scene_nwo_bitmap_export = scene.nwo_bitmap_export
        from .export_bitmaps import export_bitmaps

        return export_bitmaps(
            self.report,
            context,
            context.object.active_material,
            context.scene.nwo_halo_launcher.sidecar_path,
            scene_nwo_bitmap_export.overwrite,
            scene_nwo_bitmap_export.export_type,
            scene_nwo_bitmap_export.bitmaps_selection,
        )


class NWO_BitmapExportPropertiesGroup(PropertyGroup):
    overwrite: BoolProperty(
        name="Overwrite TIFFs",
        description="Enable to overwrite tiff files already saved to your asset bitmaps directory",
        options=set(),
    )
    export_type: EnumProperty(
        name="Actions",
        default="both",
        description="Choose whether to just export material image textures as tiffs, or just import the existing ones to the game, or both",
        options=set(),
        items=[
            ("both", "Both", ""),
            (
                "export",
                "Export TIFF",
                "Export blender image textures to tiff only",
            ),
            (
                "import",
                "Make Tags",
                "Import the tiff to the game as a bitmap tag only",
            ),
        ],
    )
    bitmaps_selection: EnumProperty(
        name="Selection",
        default="active",
        description="Choose whether to only export textures attached to the active material, or all scene textures",
        options=set(),
        items=[
            ("active", "Active", "Export the active material only"),
            ("all", "All", "Export all blender textures"),
        ],  # ('bake', 'Bake', 'Bakes textures for the currently selected objects and exports the results')]
    )


class NWO_Shader(Panel):
    bl_label = "Shader Exporter"
    bl_idname = "NWO_PT_Shader"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = "NWO_PT_MaterialTools"

    @classmethod
    def poll(cls, context):
        return not not_bungie_game()

    def draw_header(self, context):
        self.layout.label(text="", icon_value=get_icon_id("material_exporter"))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nwo_shader_build = scene.nwo_shader_build
        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )
        col = flow.column()
        col.scale_y = 1.5
        if not_bungie_game():
            col.operator("nwo.build_shader", text="Build Materials")
        else:
            col.operator("nwo.build_shader", text="Build Shaders")
        col.separator()
        col = flow.column(heading="Update")
        col.prop(nwo_shader_build, "update", text="Existing")
        row = col.row()
        row.prop(nwo_shader_build, "material_selection", expand=True)


class NWO_Material(NWO_Shader):
    bl_label = "Material Exporter"
    bl_idname = "NWO_PT_Material"

    @classmethod
    def poll(cls, context):
        return not_bungie_game()

class NWO_Shader_BuildSingle(Operator):
    bl_idname = "nwo.build_shader_single"
    bl_label = ""
    bl_options = {"UNDO"}
    bl_description = ""

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and not protected_material_name(context.object.active_material.name)
    
    def execute(self, context):
        from .shader_builder import build_shaders

        return build_shaders(context,
            context.object.active_material,
            self.report,
            True,
        )
    
    @classmethod
    def description(cls, context, properties) -> str:
        if context.scene.nwo.game_version == 'reach':
            return "Creates an empty shader tag for this material"
        else:
            return "Creates an empty material tag for this material"


class NWO_Shader_Build(Operator):
    """Makes a shader"""

    bl_idname = "nwo.build_shader"
    bl_label = "Build Shader"
    bl_options = {"UNDO"}
    bl_description = "Builds empty shader tags for blender materials. Requires ManagedBlam to be active"

    @classmethod
    def poll(cls, context):
        scene = context.scene
        nwo_shader_build = scene.nwo_shader_build
        return (
            context.object
            and context.object.type == "MESH"
            and managed_blam_active()
            and (
                nwo_shader_build.material_selection == "all"
                or context.active_object.active_material
            )
        )

    def execute(self, context):
        scene = context.scene
        nwo_shader_build = scene.nwo_shader_build
        from .shader_builder import build_shaders

        return build_shaders(
            context,
            nwo_shader_build.material_selection,
            self.report,
            nwo_shader_build.update,
        )


class NWO_ShaderPropertiesGroup(PropertyGroup):
    update: BoolProperty(
        name="Update",
        description="Enable to overwrite already existing asset shaders",
        options=set(),
    )
    material_selection: EnumProperty(
        name="Selection",
        default="active",
        description="Choose whether to build a shader for the active material, or build shaders for all appropriate materials",
        options=set(),
        items=[
            (
                "active",
                "Active",
                "Build a shader for the active material only",
            ),
            ("all", "All", "Builds shaders for all appropriate materials"),
        ],
    )

def draw_foundry_toolbar(self, context):
    #if context.region.alignment == 'RIGHT':
    foundry_toolbar(self.layout, context)

def foundry_toolbar(layout, context):
    #layout.label(text=" ")
    row = layout.row()
    nwo_scene = context.scene.nwo
    icons_only = nwo_scene.toolbar_icons_only
    row.scale_x = 1
    box = row.box()
    box.scale_x = 0.3
    box.label(text="")
    if not nwo_scene.toolbar_expanded:
        sub_foundry = row.row(align=True)
        sub_foundry.prop(nwo_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
    if nwo_scene.toolbar_expanded:
        error = validate_ek(context.scene.nwo.game_version)
        if error is not None:
            sub_error = row.row()
            sub_error.label(text=error, icon="ERROR")
            sub_foundry = row.row(align=True)
            sub_foundry.prop(nwo_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
            return

        sub0 = row.row(align=True)
        sub0.operator(
            "nwo.export_quick",
            text="" if icons_only else "Tag Export",
            icon_value=get_icon_id("quick_export"),
        )
        sub0.popover(panel="NWO_PT_HaloExportSettings", text="")
        sub1 = row.row(align=True)
        sub1.operator(
            "nwo.launch_sapien",
            text="" if icons_only else "Sapien",
            icon_value=get_icon_id("sapien"),
        )
        sub1.operator(
            "nwo.launch_tagtest",
            text="" if icons_only else "Tag Test",
            icon_value=get_icon_id("tag_test"),
        )
        sub1.popover(panel="NWO_PT_HaloLauncherGameSettings", text="")
        sub2 = row.row(align=True)
        sub2.operator(
            "nwo.launch_foundation",
            text="" if icons_only else "Tag Editor",
            icon_value=get_icon_id("foundation"),
        )
        sub2.popover(panel="NWO_PT_HaloLauncherFoundationSettings", text="")
        sub3 = row.row(align=True)
        sub3.operator(
            "nwo.launch_data",
            text="" if icons_only else "Data",
            icon_value=get_icon_id("data"),
        )
        sub3.operator(
            "nwo.launch_tags",
            text="" if icons_only else "Tags",
            icon_value=get_icon_id("tags"),
        )
        sub3.popover(panel="NWO_PT_HaloLauncherExplorerSettings", text="")

        sub_foundry = row.row(align=True)
        sub_foundry.prop(nwo_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))



classeshalo = (
    NWO_SelectArmature,
    NWO_HotkeyDescription,
    NWO_OpenURL,
    NWO_OT_PanelExpand,
    NWO_OT_PanelSet,
    NWO_OT_PanelUnpin,
    NWO_FoundryPanelProps,
    # NWO_FoundryPanelSetsViewer,
    NWO_HaloExport,
    NWO_HaloExportSettings,
    NWO_HaloExportSettingsScope,
    NWO_HaloExportSettingsFlags,
    NWO_HaloExportPropertiesGroup,
    NWO_HaloLauncherExplorerSettings,
    NWO_HaloLauncherGameSettings,
    NWO_HaloLauncherGamePruneSettings,
    NWO_HaloLauncherFoundationSettings,
    NWO_HaloLauncher_Foundation,
    NWO_HaloLauncher_Data,
    NWO_HaloLauncher_Tags,
    NWO_HaloLauncher_Sapien,
    NWO_HaloLauncher_TagTest,
    NWO_HaloLauncherPropertiesGroup,
    # NWO_PropertiesManager,
    # NWO_CollectionManager,
    NWO_CollectionManager_CreateMove,
    NWO_CollectionManager_Create,
    # NWO_CopyHaloProps,
    # NWO_CopyHaloProps_Copy, #unregistered until this operator is fixed
    NWO_AutoSeam,
    # NWO_MaterialsManager,
    # NWO_MaterialFinder,
    NWO_ShaderFinder,
    NWO_ShaderFinder_FindSingle,
    NWO_ShaderFinder_Find,
    NWO_HaloShaderFinderPropertiesGroup,
    NWO_GraphPath,
    # NWO_SetFrameIDs,
    NWO_SetFrameIDsOp,
    NWO_ResetFrameIDsOp,
    NWO_SetFrameIDsPropertiesGroup,
    # NWO_AMFHelper,
    NWO_AMFHelper_Assign,
    # NWO_JMSHelper,
    NWO_JMSHelper_Assign,
    # NWO_AnimationTools,
    # NWO_ArmatureCreator,
    NWO_ArmatureCreator_Create,
    NWO_ArmatureCreatorPropertiesGroup,
    # NWO_BitmapExport,
    NWO_BitmapExport_Export,
    NWO_BitmapExportPropertiesGroup,
    # NWO_Material,
    # NWO_Shader,
    NWO_Shader_Build,
    NWO_Shader_BuildSingle,
    NWO_ShaderPropertiesGroup,
    NWO_ScaleModels_Add,
    NWO_JoinHalo,
    # NWO_GunRigMaker,
    # NWO_GunRigMaker_Start,
)


def register():
    for clshalo in classeshalo:
        bpy.utils.register_class(clshalo)

    bpy.types.VIEW3D_HT_tool_header.append(draw_foundry_toolbar)
    bpy.types.VIEW3D_MT_mesh_add.append(add_halo_scale_model_button)
    bpy.types.VIEW3D_MT_armature_add.append(add_halo_armature_buttons)
    bpy.types.OUTLINER_HT_header.append(create_halo_collection)
    bpy.types.VIEW3D_MT_object.append(add_halo_join)
    bpy.types.Scene.nwo_frame_ids = PointerProperty(
        type=NWO_SetFrameIDsPropertiesGroup,
        name="Halo Frame ID Getter",
        description="Gets Frame IDs",
    )
    bpy.types.Scene.nwo_halo_launcher = PointerProperty(
        type=NWO_HaloLauncherPropertiesGroup,
        name="Halo Launcher",
        description="Launches stuff",
    )
    bpy.types.Scene.nwo_shader_finder = PointerProperty(
        type=NWO_HaloShaderFinderPropertiesGroup,
        name="Shader Finder",
        description="Find Shaders",
    )
    bpy.types.Scene.nwo_export = PointerProperty(
        type=NWO_HaloExportPropertiesGroup, name="Halo Export", description=""
    )
    bpy.types.Scene.nwo_armature_creator = PointerProperty(
        type=NWO_ArmatureCreatorPropertiesGroup,
        name="Halo Armature",
        description="",
    )
    bpy.types.Scene.nwo_bitmap_export = PointerProperty(
        type=NWO_BitmapExportPropertiesGroup,
        name="Halo Bitmap Export",
        description="",
    )
    bpy.types.Scene.nwo_shader_build = PointerProperty(
        type=NWO_ShaderPropertiesGroup,
        name="Halo Shader Export",
        description="",
    )


def unregister():
    bpy.types.VIEW3D_HT_tool_header.remove(draw_foundry_toolbar)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_halo_scale_model_button)
    bpy.types.VIEW3D_MT_armature_add.remove(add_halo_armature_buttons)
    bpy.types.VIEW3D_MT_object.remove(add_halo_join)
    bpy.types.OUTLINER_HT_header.remove(create_halo_collection)
    del bpy.types.Scene.nwo_frame_ids
    del bpy.types.Scene.nwo_halo_launcher
    del bpy.types.Scene.nwo_shader_finder
    del bpy.types.Scene.nwo_export
    del bpy.types.Scene.nwo_armature_creator
    del bpy.types.Scene.nwo_bitmap_export
    del bpy.types.Scene.nwo_shader_build
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)


if __name__ == "__main__":
    register()

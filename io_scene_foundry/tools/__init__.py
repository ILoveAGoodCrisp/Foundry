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

from math import radians
import os
import random
import bpy
from os.path import exists as file_exists
from os.path import join as path_join
import webbrowser

from bpy.types import Context, OperatorProperties, Panel, Operator, PropertyGroup

from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
)
from mathutils import Matrix
from io_scene_foundry.icons import get_icon_id, get_icon_id_in_directory
from io_scene_foundry.tools.auto_seam import NWO_AutoSeam
from io_scene_foundry.tools.clear_duplicate_materials import NWO_StompMaterials
from io_scene_foundry.tools.export_bitmaps import NWO_ExportBitmapsSingle
from io_scene_foundry.tools.importer import NWO_Import
from io_scene_foundry.tools.material_sync import NWO_MaterialSyncEnd, NWO_MaterialSyncStart
from io_scene_foundry.tools.mesh_to_marker import NWO_MeshToMarker
from io_scene_foundry.tools.set_sky_permutation_index import NWO_NewSky, NWO_SetDefaultSky, NWO_SetSky
from io_scene_foundry.tools.sets_manager import NWO_BSPContextMenu, NWO_BSPInfo, NWO_BSPSetLightmapRes, NWO_FaceRegionAdd, NWO_FaceRegionAssignSingle, NWO_PermutationAdd, NWO_PermutationAssign, NWO_PermutationAssignSingle, NWO_PermutationHide, NWO_PermutationHideSelect, NWO_PermutationMove, NWO_PermutationRemove, NWO_PermutationRename, NWO_PermutationSelect, NWO_RegionAdd, NWO_RegionAssign, NWO_RegionAssignSingle, NWO_RegionHide, NWO_RegionHideSelect, NWO_RegionMove, NWO_RegionRemove, NWO_RegionRename, NWO_RegionSelect, NWO_SeamAssignSingle
from io_scene_foundry.tools.shader_farm import NWO_FarmShaders, NWO_ShaderFarmPopover
from io_scene_foundry.tools.shader_reader import NWO_ShaderToNodes
from io_scene_foundry.ui.face_ui import NWO_FaceLayerAddMenu
from io_scene_foundry.ui.object_ui import NWO_GlobalMaterialMenu
from io_scene_foundry.tools.get_model_variants import NWO_GetModelVariants
from io_scene_foundry.tools.get_tag_list import NWO_GetTagsList, NWO_TagExplore
from io_scene_foundry.tools.halo_launcher import NWO_OpenFoundationTag
from io_scene_foundry.utils.nwo_constants import RENDER_MESH_TYPES, TWO_SIDED_MESH_TYPES
from .shader_builder import NWO_ListMaterialShaders, build_shader

from io_scene_foundry.utils import nwo_globals

from .halo_launcher import NWO_MaterialGirl, open_file_explorer

from io_scene_foundry.utils.nwo_utils import (
    ExportManager,
    addon_root,
    amf_addon_installed,
    blender_toolset_installed,
    bpy_enum,
    clean_tag_path,
    deselect_all_objects,
    dot_partition,
    export_objects,
    extract_from_resources,
    foundry_update_check,
    get_arm_count,
    get_data_path,
    get_halo_material_count,
    get_marker_display,
    get_mesh_display,
    get_prefs,
    get_rig,
    get_sky_perm,
    get_special_mat,
    get_tags_path,
    has_collision_type,
    has_face_props,
    has_mesh_props,
    import_gltf,
    is_frame,
    is_halo_object,
    is_instance_or_structure_proxy,
    is_marker,
    is_mesh,
    library_instanced_collection,
    managed_blam_active,
    is_corinth,
    material_read_only,
    nwo_asset_type,
    os_sep_partition,
    protected_material_name,
    recursive_image_search,
    set_active_object,
    set_object_mode,
    true_permutation,
    true_region,
    type_valid,
    unlink,
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

update_str, update_needed = foundry_update_check(nwo_globals.version)

HOTKEYS = [
    ("show_foundry_panel", "SHIFT+F"),
    ("apply_mesh_type", "CTRL+F"),
    ("apply_marker_type", "ALT+F"),
    ("halo_join", "ALT+J"),
    ("move_to_halo_collection", "ALT+M"),
]

PANELS_PROPS = [
    "scene_properties",
    "asset_editor",
    "sets_manager",
    "object_properties",
    "material_properties",
    "animation_properties",
    "tools",
    "help",
    "settings"
]

PANELS_TOOLS = ["sets_viewer"]

# import Tool Operators
from .instance_proxies import NWO_ProxyInstanceNew, NWO_ProxyInstanceCancel, NWO_ProxyInstanceEdit, NWO_ProxyInstanceDelete

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
    
    @classmethod
    def poll(cls, context):
        return not context.scene.nwo.storage_only

    def draw(self, context):
        self.context = context
        layout = self.layout
        self.h4 = is_corinth(context)
        self.scene = context.scene
        nwo = self.scene.nwo
        self.asset_type = nwo.asset_type
        if context.scene.nwo.instance_proxy_running:    
            box = layout.box()
            ob = context.object
            if ob:
                row = box.row()
                row.label(text=f"Editing: {ob.name}")
                row = box.row()
                row.use_property_split = True
                row.prop(
                    ob.data.nwo,
                    "face_global_material_ui",
                    text="Collision Material",
                )
                row.operator(
                    "nwo.global_material_globals",
                    text="",
                    icon="VIEWZOOM",
                )
                # proxy face props
                self.draw_face_props(box, ob, context, True)

            row = box.row()
            row.scale_y = 2
            row.operator("nwo.proxy_instance_cancel", text="Exit Proxy Edit Mode")
            return
        
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
            elif p in ("object_properties", "material_properties"):
                if nwo.asset_type == 'FP ANIMATION':
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
                    if callable(draw_panel):
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
        prefs = get_prefs()
        projects = prefs.projects
        for p in projects:
            if p.name == nwo.scene_project:
                thumbnail = os.path.join(p.project_path, p.project_image_path)
                if os.path.exists(thumbnail):
                    icon_id = get_icon_id_in_directory(thumbnail)
                elif p.project_remote_server_name == "bngtoolsql":
                    icon_id = get_icon_id("halo_reach")
                elif p.project_remote_server_name == "metawins":
                    icon_id = get_icon_id("halo_4")
                elif p.project_remote_server_name == "episql.343i.selfhost.corp.microsoft.com":
                    icon_id = get_icon_id("halo_2amp")
                else:
                    icon_id = get_icon_id("tag_test")
                row.menu(NWO_ProjectChooserMenu.bl_idname, text=nwo.scene_project, icon_value=icon_id)
                break
        else:
            if projects:
                row.menu(NWO_ProjectChooserMenu.bl_idname, text="Choose Project", icon_value=get_icon_id("tag_test"))
            else:
                row.operator("nwo.project_add", text="Choose Project", icon_value=get_icon_id("tag_test")).set_scene_project = True
        col = box.column()
        col.use_property_split = True
        # if nwo.asset_type in ("MODEL", "SCENARIO", "PREFAB"):
        #     col.prop(nwo, "default_mesh_type_ui", text="Default Mesh Type")

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
        elif nwo_globals.mb_active:
            row.label(text="Blender Restart Required for ManagedBlam")
        else:
            row.operator("managed_blam.init", text="Initialize ManagedBlam", icon_value=get_icon_id("managed_blam_off"))
        col.separator()
        row = col.row()
        row.scale_y = 1.1

        unit_scale = scene.unit_settings.scale_length

        # if unit_scale == 1.0:
        #     row.operator("nwo.set_unit_scale", text="Set Halo Scale", icon_value=get_icon_id("halo_scale")).scale = 0.03048
        # else:
        #     row.operator("nwo.set_unit_scale", text="Set Default Scale", icon="BLENDER").scale = 1.0
        row.prop(scene.nwo, 'scale', text='Scale', expand=True)
        if nwo.asset_type in ("MODEL", "FP ANIMATION"):
            row = col.row()
            row.prop(nwo, "forward_direction", text="Model Forward", expand=True)

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
            row.label(text=asset_name)
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
            if is_corinth(context):
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
            
            col.separator()
            
            row = col.row(align=True)
            row.prop(nwo, 'template_model', icon_value=get_icon_id('model'))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_model"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_model'
            if nwo.output_biped:
                row = col.row(align=True)
                row.prop(nwo, 'template_biped', icon_value=get_icon_id('biped'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_biped"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_biped'
            if nwo.output_crate:
                row = col.row(align=True)
                row.prop(nwo, 'template_crate', icon_value=get_icon_id('crate'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_crate"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_crate'
            if nwo.output_creature:
                row = col.row(align=True)
                row.prop(nwo, 'template_creature', icon_value=get_icon_id('creature'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_creature"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_creature'
            if nwo.output_device_control:
                row = col.row(align=True)
                row.prop(nwo, 'template_device_control', icon_value=get_icon_id('device_control'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_device_control"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_device_control'
            if nwo.output_device_dispenser:
                row = col.row(align=True)
                row.prop(nwo, 'template_device_dispenser', icon_value=get_icon_id('device_dispenser'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_device_dispenser"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_device_dispenser'
            if nwo.output_device_machine:
                row = col.row(align=True)
                row.prop(nwo, 'template_device_machine', icon_value=get_icon_id('device_machine'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_device_machine"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_device_machine'
            if nwo.output_device_terminal:
                row = col.row(align=True)
                row.prop(nwo, 'template_device_terminal', icon_value=get_icon_id('device_terminal'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_device_terminal"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_device_terminal'
            if nwo.output_effect_scenery:
                row = col.row(align=True)
                row.prop(nwo, 'template_effect_scenery', icon_value=get_icon_id('effect_scenery'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_effect_scenery"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_effect_scenery'
            if nwo.output_equipment:
                row = col.row(align=True)
                row.prop(nwo, 'template_equipment', icon_value=get_icon_id('equipment'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_equipment"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_equipment'
            if nwo.output_giant:
                row = col.row(align=True)
                row.prop(nwo, 'template_giant', icon_value=get_icon_id('giant'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_giant"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_giant'
            if nwo.output_scenery:
                row = col.row(align=True)
                row.prop(nwo, 'template_scenery', icon_value=get_icon_id('scenery'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_scenery"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_scenery'
            if nwo.output_vehicle:
                row = col.row(align=True)
                row.prop(nwo, 'template_vehicle', icon_value=get_icon_id('vehicle'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_vehicle"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_vehicle'
            if nwo.output_weapon:
                row = col.row(align=True)
                row.prop(nwo, 'template_weapon', icon_value=get_icon_id('weapon'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_weapon"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_weapon'

            box = self.box.box()
            box.label(text="Model Overrides")
            col = box.column()
            row = col.row(align=True)
            row.prop(nwo, "render_model_path", text="Render", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "render_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'render_model_path'
            row = col.row(align=True)
            row.prop(nwo, "collision_model_path", text="Collision", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "collision_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'collision_model_path'
            row = col.row(align=True)
            row.prop(nwo, "animation_graph_path", text="Animation", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "animation_graph_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'animation_graph_path'
            row = col.row(align=True)
            row.prop(nwo, "physics_model_path", text="Physics", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "physics_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'physics_model_path'
            if nwo.render_model_path and nwo.collision_model_path and nwo.animation_graph_path and nwo.physics_model_path:
                row = col.row(align=True)
                row.label(text='All overrides specified', icon='ERROR')
                row = col.row(align=True)
                row.label(text='Everything exported from this scene will be overwritten')
            
            self.draw_rig_ui(context, nwo)    

        elif nwo.asset_type == "FP ANIMATION":
            box = self.box.box()
            box.label(text="Tag References")
            col = box.column()
            row = col.row(align=True)
            row.prop(nwo, "fp_model_path", text="FP Render Model", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "fp_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'fp_model_path'
            row = col.row(align=True)
            row.prop(nwo, "gun_model_path", text="Gun Render Model", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "gun_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'gun_model_path'
            
            self.draw_rig_ui(context, nwo) 
            
    def draw_rig_ui(self, context, nwo):
        box = self.box.box()
        box.label(text="Model Rig")
        col = box.column()
        col.use_property_split = True
        col.prop(nwo, 'main_armature', icon='OUTLINER_OB_ARMATURE')
        if not nwo.main_armature: return
        col.separator()
        arm_count = get_arm_count(context)
        if arm_count > 1 or nwo.support_armature_a:
            col.prop(nwo, 'support_armature_a', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_a:
                col.prop_search(nwo, 'support_armature_a_parent_bone', nwo.main_armature.data, 'bones')
                col.prop_search(nwo, 'support_armature_a_child_bone', nwo.support_armature_a.data, 'bones')
                col.separator()
        if arm_count > 2 or nwo.support_armature_b:
            col.prop(nwo, 'support_armature_b', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_b:
                col.prop_search(nwo, 'support_armature_b_parent_bone', nwo.main_armature.data, 'bones')
                col.prop_search(nwo, 'support_armature_b_child_bone', nwo.support_armature_b.data, 'bones')
                col.separator()
        if arm_count > 3 or nwo.support_armature_c:
            col.prop(nwo, 'support_armature_c', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_c:
                col.prop_search(nwo, 'support_armature_c_parent_bone', nwo.main_armature.data, 'bones')
                col.prop_search(nwo, 'support_armature_c_child_bone', nwo.support_armature_c.data, 'bones')
        
        col.separator()
        # Bone Controls
        box_controls = box.box()
        box_controls.label(text='Rig Controls')
        box_controls.use_property_split = True
        row = box_controls.row(align=True)
        row.prop_search(nwo, 'control_pedestal', nwo.main_armature.data, 'bones')
        if not nwo.control_pedestal:
            row.operator('nwo.add_pedestal_control', text='', icon='ADD')
        row = box_controls.row(align=True)
        row.prop_search(nwo, 'control_aim', nwo.main_armature.data, 'bones')
        if not nwo.control_aim:
            row.operator('nwo.add_pose_bones', text='', icon='ADD').skip_invoke = True
        # Node Usages
        box_usages = box.box()
        box_usages.label(text='Rig Node Usages')
        box_usages.use_property_split = True
        col = box_usages.column()
        col.prop_search(nwo, "node_usage_pedestal", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_pose_blend_pitch", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_pose_blend_yaw", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_physics_control", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_camera_control", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_origin_marker", nwo.main_armature.data, "bones")
        if self.h4:
            col.prop_search(nwo, "node_usage_weapon_ik", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_pelvis", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_left_clavicle", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_left_upperarm", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_left_foot", nwo.main_armature.data, "bones")
        if self.h4:
            col.prop_search(nwo, "node_usage_left_hand", nwo.main_armature.data, "bones")
            col.prop_search(nwo, "node_usage_right_foot", nwo.main_armature.data, "bones")
            col.prop_search(nwo, "node_usage_right_hand", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_gut", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_chest", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_head", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_left_shoulder", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_left_arm", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_left_leg", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_left_foot", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_right_shoulder", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_right_arm", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_right_leg", nwo.main_armature.data, "bones")
        col.prop_search(nwo, "node_usage_damage_root_right_foot", nwo.main_armature.data, "bones")

    def draw_sets_manager(self):
        box = self.box.box()
        nwo = self.scene.nwo
        context = self.context
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        row = box.row()
        row.label(text="BSPs" if is_scenario else "Regions")
        row = box.row()
        if not nwo.regions_table:
            return
        region = nwo.regions_table[nwo.regions_table_active_index]
        rows = 4
        row.template_list(
            "NWO_UL_Regions",
            "",
            nwo,
            "regions_table",
            nwo,
            "regions_table_active_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.region_add", text="", icon="ADD").set_object_prop = False
        col.operator("nwo.region_remove", icon="REMOVE", text="")
        if self.asset_type == 'SCENARIO':
            col.separator()
            col.menu('NWO_MT_BSPContextMenu', text="", icon='DOWNARROW_HLT')
        col.separator()
        col.operator("nwo.region_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.region_move", icon="TRIA_DOWN", text="").direction = 'down'

        row = box.row()

        sub = row.row(align=True)
        sub.operator("nwo.region_assign", text="Assign").name = region.name

        sub = row.row(align=True)
        sub.operator("nwo.region_select", text="Select").select = True
        sub.operator("nwo.region_select", text="Deselect").select = False  

        # Permutations
        box = self.box.box()
        row = box.row()
        row.label(text="Layers" if is_scenario else "Permutations")
        row = box.row()
        permutation = nwo.permutations_table[nwo.permutations_table_active_index]
        rows = 4
        row.template_list(
            "NWO_UL_Permutations",
            "",
            nwo,
            "permutations_table",
            nwo,
            "permutations_table_active_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.permutation_add", text="", icon="ADD").set_object_prop = False
        col.operator("nwo.permutation_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.permutation_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.permutation_move", icon="TRIA_DOWN", text="").direction = 'down'

        row = box.row()

        sub = row.row(align=True)
        sub.operator("nwo.permutation_assign", text="Assign").name = permutation.name

        sub = row.row(align=True)
        sub.operator("nwo.permutation_select", text="Select").select = True
        sub.operator("nwo.permutation_select", text="Deselect").select = False

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
            box.label(text='Frame')
            return

        row = box.row(align=True)
        row.scale_x = 0.5
        row.scale_y = 1.3
        data = ob.data

        halo_light = ob.type == 'LIGHT'
        has_mesh_types = is_mesh(ob) and poll_ui(('MODEL', 'SCENARIO', 'PREFAB'))
        has_marker_types = is_marker(ob) and poll_ui(('MODEL', 'SKY', 'SCENARIO', 'PREFAB'))

        # Check if this is a linked collection
        if library_instanced_collection(ob):
            row.label(text='Instanced Collection', icon='OUTLINER_OB_GROUP_INSTANCE')
            row = box.row()
            row.label(text=f'{ob.name} will be unpacked at export')
            return

        elif halo_light:
            row.prop(data, "type", expand=True)
            col = box.column()
            col.use_property_split = True
            self.draw_table_menus(col, nwo, ob)
            flow = col.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )

            nwo = data.nwo
            col = flow.column()
            if data.type == 'AREA':
                col.label(text="Area lights not currently supported", icon="ERROR")
                return

            col.prop(data, "color")
            col.prop(nwo, 'light_intensity', text="Intensity")
            if data.energy < 11 and data.type != 'SUN':
                # Warn user about low light power. Need the light scaled to Halo proportions
                col.label(text="Light itensity is very low", icon='ERROR')
                col.label(text="For best results match the power of the light in")
                col.label(text="Cycles to how you'd like it to appear in game")

            if data.type == 'SPOT' and h4:
                col.separator()
                col.prop(data, "spot_size", text="Cone Size")
                col.prop(data, "spot_blend", text="Cone Blend", slider=True)
                col.prop(data, "show_cone")

            col.separator()
            if is_corinth(context):
                row = col.row()
                row.prop(nwo, "light_mode", expand=True)
                if data.type == "SPOT":
                    col.separator()
                    row = col.row()
                    row.prop(nwo, "light_cone_projection_shape", expand=True)

                col.separator()
                
                col.prop(nwo, "light_far_attenuation_start", text='Light Falloff Start')
                col.prop(nwo, "light_far_attenuation_end", text='Light Falloff End')
                
                col.separator()

                if nwo.light_mode == "_connected_geometry_light_mode_dynamic":
                    col.prop(nwo, "light_camera_fade_start", text='Camera Fade Start')
                    col.prop(nwo, "light_camera_fade_end", text='Camera Fade End')

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

                else:
                    row = col.row()
                    row.prop(nwo, "light_jitter_quality", expand=True)
                    col.prop(nwo, "light_jitter_angle")
                    col.prop(nwo, "light_jitter_sphere_radius")

                    col.separator()

                    col.prop(nwo, "light_amplification_factor")

                    col.separator()
                    col.prop(nwo, "light_indirect_only")
                    col.prop(nwo, "light_static_analytic")

                

            else:

                col.prop(nwo, "light_game_type", text="Game Type")
                col.prop(nwo, "light_shape", text="Shape")

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
                    text="Light Activation Start",
                )
                col.prop(
                    nwo,
                    "light_near_attenuation_end",
                    text="Light Activation End",
                )

                col.separator()

                col.prop(
                    nwo,
                    "light_far_attenuation_start",
                    text="Light Falloff Start",
                )
                col.prop(nwo, "light_far_attenuation_end", text="Light Falloff End")

                col.separator()
                row = col.row()
                row.prop(nwo, "light_tag_override", text="Light Tag Override", icon_value=get_icon_id("tags"))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "light_tag_override"
                row.operator("nwo.tag_explore", text="", icon='FILE_FOLDER').prop = 'light_tag_override'
                row = col.row()
                row.prop(nwo, "light_shader_reference", text="Shader Tag Reference", icon_value=get_icon_id("tags"))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "light_shader_reference"
                row.operator("nwo.tag_explore", text="", icon='FILE_FOLDER').prop = 'light_shader_reference'
                row = col.row()
                row.prop(nwo, "light_gel_reference", text="Gel Tag Reference", icon_value=get_icon_id("tags"))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "light_gel_reference"
                row.operator("nwo.tag_explore", text="", icon='FILE_FOLDER').prop = 'light_gel_reference'
                row = col.row()
                row.prop(
                    nwo,
                    "light_lens_flare_reference",
                    text="Lens Flare Tag Reference",
                    icon_value=get_icon_id("tags")
                )
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "light_lens_flare_reference"
                row.operator("nwo.tag_explore", text="", icon='FILE_FOLDER').prop = 'light_lens_flare_reference'

                # col.separator() # commenting out light clipping for now.

                # col.prop(nwo, 'Light_Clipping_Size_X_Pos', text='Clipping Size X Forward')
                # col.prop(nwo, 'Light_Clipping_Size_Y_Pos', text='Clipping Size Y Forward')
                # col.prop(nwo, 'Light_Clipping_Size_Z_Pos', text='Clipping Size Z Forward')
                # col.prop(nwo, 'Light_Clipping_Size_X_Neg', text='Clipping Size X Backward')
                # col.prop(nwo, 'Light_Clipping_Size_Y_Neg', text='Clipping Size Y Backward')
                # col.prop(nwo, 'Light_Clipping_Size_Z_Neg', text='Clipping Size Z Backward')

        elif is_mesh(ob):
            if has_mesh_types:
                display_name, icon_id = get_mesh_display(nwo.mesh_type_ui)
                row.menu('NWO_MT_MeshTypes', text=display_name, icon_value=icon_id)
                
            # SPECIFIC MESH PROPS
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            mesh_nwo = ob.data.nwo
            col = flow.column()
            row = col.row()
            row.scale_y = 1.25
            row.emboss = "NORMAL"
            # row.menu(NWO_MeshMenu.bl_idname, text=mesh_type_name, icon_value=get_icon_id(mesh_type_icon))
            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            col.use_property_split = True
            if self.asset_type == 'DECORATOR SET':
                col.label(text="Decorator")
                col.prop(nwo, "decorator_lod_ui", text="Level of Detail", expand=True)
                return
            elif self.asset_type == 'PARTICLE MODEL':
                col.label(text="Particle Model")
                return
            
            self.draw_table_menus(col, nwo, ob)

            if nwo.mesh_type_ui == "_connected_geometry_mesh_type_physics":
                col.prop(nwo, "mesh_primitive_type_ui", text="Primitive Type")

            elif nwo.mesh_type_ui == "_connected_geometry_mesh_type_portal":
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
                nwo.mesh_type_ui
                == "_connected_geometry_mesh_type_planar_fog_volume"
            ):
                row = col.row()
                row.prop(
                    nwo,
                    "fog_appearance_tag_ui",
                    text="Fog Appearance Tag",
                    icon_value=get_icon_id('tags')
                )
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "fog_appearance_tag_ui"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'fog_appearance_tag_ui'
                col.prop(
                    nwo,
                    "fog_volume_depth_ui",
                    text="Fog Volume Depth",
                )

            elif (
                nwo.mesh_type_ui == "_connected_geometry_mesh_type_water_surface"
            ):
                col.prop(nwo, "mesh_tessellation_density_ui", text="Tessellation Density")

            elif (
                nwo.mesh_type_ui
                == "_connected_geometry_mesh_type_water_physics_volume"
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

            elif nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_default",
                "_connected_geometry_mesh_type_structure",
            ) and poll_ui(('SCENARIO', 'PREFAB')):
                if h4 and nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure" and poll_ui('SCENARIO'):
                    col.prop(nwo, "proxy_instance")
                if nwo.mesh_type_ui == "_connected_geometry_mesh_type_default" or (
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

                    col = col.column(heading="Instance Flags")
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

        elif is_marker(ob) and poll_ui(
            ("MODEL", "SCENARIO", "SKY", "PREFAB")
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
            display_name, icon_id = get_marker_display(nwo.marker_type_ui)
            row.menu('NWO_MT_MarkerTypes', text=display_name, icon_value=icon_id)

            col.separator()

            flow = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=False,
                even_rows=False,
                align=False,
            )
            flow.use_property_split = False
            col = flow.column()

            if poll_ui("SCENARIO"):
                col.use_property_split = True
                self.draw_table_menus(col, nwo, ob)

            if nwo.marker_type_ui in (
                "_connected_geometry_marker_type_model",
                "_connected_geometry_marker_type_garbage",
                "_connected_geometry_marker_type_effects",
                "_connected_geometry_marker_type_target",
                "_connected_geometry_marker_type_hint",
                "_connected_geometry_marker_type_pathfinding_sphere",
            ):
                if poll_ui(("MODEL", "SKY")):
                    if nwo.marker_type_ui in ('_connected_geometry_marker_type_model', '_connected_geometry_marker_type_garbage', '_connected_geometry_marker_type_effects'):
                        col.prop(nwo, 'marker_model_group', text="Marker Group")
                    row = col.row()
                    sub = col.row(align=True)
                    if not nwo.marker_all_regions_ui:
                        col.label(text='Region', icon_value=get_icon_id("collection_creator") if nwo.region_name_locked_ui else 0)
                        col.menu("NWO_MT_Regions", text=true_region(nwo), icon_value=get_icon_id("region"))
                    
                    sub.prop(nwo, "marker_all_regions_ui", text="All Regions")
                    # marker perm ui
                    if not nwo.marker_all_regions_ui:
                        col.separator()
                        rows = 3
                        row = col.row(heading='Marker Permutations')
                        row.use_property_split = False
                        # row.label(text="Marker Permutations")
                        row.prop(nwo, "marker_permutation_type", text=" ", expand=True)
                        row = col.row()
                        row.template_list(
                            "NWO_UL_MarkerPermutations",
                            "",
                            nwo,
                            "marker_permutations",
                            nwo,
                            "marker_permutations_index",
                            rows=rows,
                        )
                        col_perm = row.column(align=True)
                        col_perm.menu("NWO_MT_MarkerPermutations", text="", icon="ADD")
                        col_perm.operator("nwo.marker_perm_remove", icon="REMOVE", text="")
                        if nwo.marker_permutation_type == "include" and not nwo.marker_permutations:
                            row = col.row()
                            row.label(text="No permutations in include list", icon="ERROR")


            elif nwo.marker_type_ui == "_connected_geometry_marker_type_game_instance":
                row = col.row(align=True)
                row.prop(
                    nwo,
                    "marker_game_instance_tag_name_ui",
                    text="Tag Path",
                    icon_value=get_icon_id('tags')
                )
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "marker_game_instance_tag_name_ui"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'marker_game_instance_tag_name_ui'
                tag_name = nwo.marker_game_instance_tag_name_ui
                if tag_name.endswith("decorator_set"):
                    col.prop(
                        nwo,
                        "marker_game_instance_tag_variant_name_ui",
                        text="Decorator Type",
                    )
                elif not tag_name.endswith(
                    (".prefab", ".cheap_light", ".light", ".leaf")
                ):
                    row = col.row(align=True)
                    row.prop(
                        nwo,
                        "marker_game_instance_tag_variant_name_ui",
                        text="Tag Variant",
                    )
                    row.operator_menu_enum("nwo.get_model_variants", "variant", icon="DOWNARROW_HLT", text="")
                    if h4:
                        col.prop(nwo, "marker_game_instance_run_scripts_ui")

            if nwo.marker_type_ui == "_connected_geometry_marker_type_hint":
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
                row.prop(nwo, "marker_looping_effect_ui", icon_value=get_icon_id('tags'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "marker_looping_effect_ui"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'marker_looping_effect_ui'

            elif (
                nwo.marker_type_ui == "_connected_geometry_marker_type_lightCone" and h4
            ):
                row = col.row()
                row.prop(nwo, "marker_light_cone_tag_ui", text='Cone Tag Path', icon_value=get_icon_id('tags'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "marker_light_cone_tag_ui"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'marker_light_cone_tag_ui'
                col.prop(nwo, "marker_light_cone_color_ui", text='Color')
                col.prop(nwo, "marker_light_cone_alpha_ui", text='Alpha')
                col.prop(nwo, "marker_light_cone_intensity_ui", text='Intensity')
                col.prop(nwo, "marker_light_cone_width_ui", text='Width')
                col.prop(nwo, "marker_light_cone_length_ui", text='Length')
                row = col.row()
                row.prop(nwo, "marker_light_cone_curve_ui", text='Curve Tag Path', icon_value=get_icon_id('tags'))
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "marker_light_cone_curve_ui"
                row.operator("nwo.tag_explore", icon="FILE_FOLDER", text="").prop = 'marker_light_cone_curve_ui'
                
        elif is_frame(ob) and poll_ui(
            ("MODEL", "SCENARIO", "SKY")):
            col = box.column()
            col.label(text='Frame', icon_value=get_icon_id('frame'))
            # TODO Add button that selects child objects
            return
                

        if not has_mesh_props(ob) or (h4 and not nwo.proxy_instance and poll_ui('SCENARIO') and nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure"):
            return

        box = self.box.box()
        box.label(text="Mesh Properties", icon='MESH_DATA')
        has_collision = has_collision_type(ob)
        if poll_ui(("MODEL", "SKY", "SCENARIO", "PREFAB")) and nwo.mesh_type_ui != '_connected_geometry_mesh_type_physics':
            if h4 and (not nwo.proxy_instance and nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure" and poll_ui('SCENARIO')):
                return
            row = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=True,
                align=True,
            )
            row.scale_x = 0.8
            if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_lightmap_only"):
                row.prop(mesh_nwo, "precise_position_ui", text="Uncompressed")
            if nwo.mesh_type_ui in TWO_SIDED_MESH_TYPES:
                row.prop(mesh_nwo, "face_two_sided_ui", text="Two Sided")
                if nwo.mesh_type_ui in RENDER_MESH_TYPES:
                    row.prop(mesh_nwo, "face_transparent_ui", text="Transparent")
                    # if h4 and poll_ui(('MODEL', 'SKY')):
                    #     row.prop(mesh_nwo, "uvmirror_across_entire_model_ui", text="Mirror UVs")
            if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure"):
                row.prop(mesh_nwo, "decal_offset_ui", text="Decal Offset") 
            if poll_ui(("SCENARIO", "PREFAB")):
                if not h4:
                    if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure"):
                        row.prop(mesh_nwo, "no_shadow_ui", text="No Shadow")
                else:
                    # row.prop(mesh_nwo, "group_transparents_by_plane_ui", text="Transparents by Plane")
                    if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure"):
                        row.prop(mesh_nwo, "no_shadow_ui", text="No Shadow")
                        if h4:
                            row.prop(mesh_nwo, "no_lightmap_ui", text="No Lightmap")
                            row.prop(mesh_nwo, "no_pvs_ui", text="No Visibility Culling")
                            
            if not h4 and poll_ui('SCENARIO') and nwo.mesh_type_ui in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_structure'):
                row.prop(mesh_nwo, 'render_only_ui', text='Render Only')
                if not mesh_nwo.render_only_ui:
                    row.prop(mesh_nwo, "ladder_ui", text="Ladder")
                    row.prop(mesh_nwo, "slip_surface_ui", text="Slip Surface")
                    row.prop(mesh_nwo, 'breakable_ui', text='Breakable')
                
            elif not h4 and nwo.mesh_type_ui == '_connected_geometry_mesh_type_collision':
                if poll_ui('SCENARIO'):
                    row.prop(mesh_nwo, 'sphere_collision_only_ui', text='Sphere Collision Only')
                elif poll_ui('MODEL'):
                    row.prop(mesh_nwo, "ladder_ui", text="Ladder")
                    row.prop(mesh_nwo, "slip_surface_ui", text="Slip Surface")
                    
                
            elif h4 and has_collision and nwo.mesh_type_ui != '_connected_geometry_mesh_type_collision':
                row.prop(mesh_nwo, 'render_only_ui', text='Render Only')

            if h4 and nwo.mesh_type_ui in RENDER_MESH_TYPES and mesh_nwo.face_two_sided_ui:
                row = box.row()
                row.use_property_split = True
                row.prop(mesh_nwo, "face_two_sided_type_ui", text="Backside Normals")
                
        if poll_ui(("MODEL", "SCENARIO", "PREFAB")):
            if has_collision and not (mesh_nwo.render_only_ui and is_instance_or_structure_proxy(ob)):
                row = box.row()
                row.use_property_split = True
                if h4:
                    row.prop(mesh_nwo, 'poop_collision_type_ui', text='Collision Type')
                        
            if (h4 and (nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                "_connected_geometry_mesh_type_structure",
                "_connected_geometry_mesh_type_default",
                )
                and (nwo.proxy_instance or nwo.mesh_type_ui != "_connected_geometry_mesh_type_structure"))) or (not h4 and nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                )):
                    if not (nwo.mesh_type_ui in ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default") and mesh_nwo.render_only_ui):
                        row = box.row()
                        row.use_property_split = True
                        coll_mat_text = 'Collision Material'
                        if ob.data.nwo.face_props and nwo.mesh_type_ui in ('_connected_geometry_mesh_type_structure', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_default'):
                            for prop in ob.data.nwo.face_props:
                                if prop.face_global_material_override:
                                    coll_mat_text += '*'
                                    break
                        row.prop(
                            mesh_nwo,
                            "face_global_material_ui",
                            text=coll_mat_text,
                        )
                        if poll_ui(('SCENARIO', 'PREFAB')):
                            row.operator(
                                "nwo.global_material_globals",
                                text="",
                                icon="VIEWZOOM",
                            )
                        else:
                            row.menu(
                                NWO_GlobalMaterialMenu.bl_idname,
                                text="",
                                icon="DOWNARROW_HLT",
                        )

        if nwo.mesh_type_ui in (
            "_connected_geometry_mesh_type_structure",
            # "_connected_geometry_mesh_type_collision",
            "_connected_geometry_mesh_type_default",
            "_connected_geometry_mesh_type_lightmap_only",
        ):
            if poll_ui(("SCENARIO", "PREFAB")) and (not h4 or nwo.proxy_instance or nwo.mesh_type_ui != "_connected_geometry_mesh_type_structure"):
                # col.separator()
                col_ob = box.column()
                col_ob.use_property_split = True
                # lightmap
                if mesh_nwo.lightmap_additive_transparency_active:
                    row = col_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "lightmap_additive_transparency_ui",
                        text="Additive Transparency",
                    )
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "lightmap_additive_transparency"
                if mesh_nwo.lightmap_resolution_scale_active:
                    row = col_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "lightmap_resolution_scale_ui",
                        text="Resolution Scale",
                    )
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "lightmap_resolution_scale"
                if mesh_nwo.lightmap_type_active:
                    row = col_ob.row(align=True)
                    row.prop(mesh_nwo, "lightmap_type_ui", text="Lightmap Type")
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "lightmap_type"
                if mesh_nwo.lightmap_analytical_bounce_modifier_active:
                    row = col_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "lightmap_analytical_bounce_modifier_ui",
                        text="Analytical Bounce Modifier",
                    )
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "lightmap_analytical_bounce_modifier"
                if mesh_nwo.lightmap_general_bounce_modifier_active:
                    row = col_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "lightmap_general_bounce_modifier_ui",
                        text="General Bounce Modifier",
                    )
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "lightmap_general_bounce_modifier"
                if mesh_nwo.lightmap_translucency_tint_color_active:
                    row = col_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "lightmap_translucency_tint_color_ui",
                        text="Translucency Tint Color",
                    )
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "lightmap_translucency_tint_color"
                if mesh_nwo.lightmap_lighting_from_both_sides_active:
                    row = col_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "lightmap_lighting_from_both_sides_ui",
                        text="Lighting From Both Sides",
                    )
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "lightmap_lighting_from_both_sides"
                if mesh_nwo.emissive_active:
                    col_ob.separator()
                    box_ob = col_ob.box()
                    row = box_ob.row(align=True)
                    row.label(text="Emissive Settings", icon='LIGHT_DATA')
                    row.operator(
                        "nwo.remove_mesh_property", text="", icon="X"
                    ).options = "emissive"
                    row = box_ob.row(align=True)
                    row.prop(mesh_nwo, "material_lighting_emissive_color_ui", text="Color")
                    row = box_ob.row(align=True)
                    row.prop(mesh_nwo, "material_lighting_emissive_power_ui", text="Power")
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_emissive_quality_ui",
                        text="Quality",
                    )
                    row = box_ob.row(align=True)
                    row.prop(mesh_nwo, "material_lighting_emissive_focus_ui", text="Focus")
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_attenuation_falloff_ui",
                        text="Attenutation Falloff",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_attenuation_cutoff_ui",
                        text="Attenutation Cutoff",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_bounce_ratio_ui",
                        text="Bounce Ratio",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_use_shader_gel_ui",
                        text="Shader Gel",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_emissive_per_unit_ui",
                        text="Emissive Per Unit",
                    )

                col_ob.separator()
                row_add_prop = col_ob.row()
                if not mesh_nwo.emissive_active:
                    row_add_prop.operator("nwo.add_mesh_property", text="Emissive", icon='LIGHT_DATA').options = "emissive"
                
                row_add_prop.operator_menu_enum("nwo.add_mesh_property_lightmap", property="options", text="Lightmap Settings", icon='OUTLINER_DATA_LIGHTPROBE')

        if has_face_props(ob):
            self.draw_face_props(self.box, ob, context)
  
        nwo = ob.data.nwo
        # Instance Proxy Operators
        if ob.type != 'MESH' or ob.nwo.mesh_type_ui != "_connected_geometry_mesh_type_default" or not poll_ui(('SCENARIO', 'PREFAB')) or mesh_nwo.render_only_ui:
            return
        
        col.separator()
        box = self.box.box()
        box.label(text="Instance Proxies", icon='CUBE')
        collision = nwo.proxy_collision
        physics = nwo.proxy_physics
        cookie_cutter = nwo.proxy_cookie_cutter

        if collision:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Collision", icon_value=get_icon_id("collider")).proxy = collision.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = collision.name

        if physics:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Physics", icon_value=get_icon_id("physics")).proxy = physics.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = physics.name

        if not h4 and cookie_cutter:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Cookie Cutter", icon_value=get_icon_id("cookie_cutter")).proxy = cookie_cutter.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = cookie_cutter.name

        if not (collision and physics and (h4 or cookie_cutter)):
            row = box.row()
            row.scale_y = 1.3
            row.operator("nwo.proxy_instance_new", text="New Instance Proxy", icon="ADD")
            col.separator()

    def draw_face_props(self, box, ob, context, is_proxy=False):
        box = box.box()
        flow = box.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        flow.use_property_split = True

        nwo = ob.data.nwo

        box.label(text="Face Properties", icon='FACE_MAPS')

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
                text="Add Face Properties",
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
                if is_proxy or (ob.nwo.mesh_type_ui == "_connected_geometry_mesh_type_collision" and poll_ui(('SCENARIO', 'PREFAB'))):
                    col.operator("nwo.face_layer_add", text="", icon="ADD").options = "face_global_material"
                else:
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
                    box = col.box()
                    row = box.row()
                    row.label(text='Region')
                    row = box.row()
                    row.menu("NWO_MT_FaceRegions", text=item.region_name_ui, icon_value=get_icon_id("region"))
                    row.operator(
                        "nwo.face_prop_remove", text="", icon="X"
                    ).options = "region"
                if item.face_two_sided_override:
                    if is_corinth(context):
                        col.separator()
                        box = col.box()
                        row = box.row()
                        row.label(text="Two Sided")
                        row = box.row()
                        row.prop(item, "face_two_sided_type_ui", text="Backside Normals")
                    else:
                        row = col.row()
                        row.label(text="Two Sided")
                if item.render_only_override:
                    row = col.row()
                    row.label(text='Render Only')
                    
                if item.collision_only_override:
                    row = col.row()
                    row.label(text='Collision Only')
                    
                if item.sphere_collision_only_override:
                    row = col.row()
                    row.label(text='Sphere Collision Only')
                    
                if item.player_collision_only_override:
                    row = col.row()
                    row.label(text='Player Collision Only')
                    
                if item.bullet_collision_only_override:
                    row = col.row()
                    row.label(text='Bullet Collision Only')

                if item.face_transparent_override:
                    row = col.row()
                    row.label(text="Transparent Faces")
                if item.face_global_material_override:
                    row = col.row()
                    row.prop(item, "face_global_material_ui")
                    if poll_ui(('SCENARIO', 'PREFAB')):
                        row.operator(
                            "nwo.global_material_globals",
                            text="",
                            icon="VIEWZOOM",
                        ).face_level = True
                    else:
                        row.menu(
                            "NWO_MT_AddGlobalMaterialFace",
                            text="",
                            icon="DOWNARROW_HLT",
                        )
                if item.precise_position_override:
                    row = col.row()
                    row.label(text='Uncompressed')
                if item.ladder_override:
                    row = col.row()
                    row.label(text='Ladder')
                if item.slip_surface_override:
                    row = col.row()
                    row.label(text='Slip Surface')
                if item.breakable_override:
                    row = col.row()
                    row.label(text='Breakable')
                if item.decal_offset_override:
                    row = col.row()
                    row.label(text='Decal Offset')
                if item.no_shadow_override:
                    row = col.row()
                    row.label(text='No Shadow')
                if item.no_lightmap_override:
                    row = col.row()
                    row.label(text="No Lightmap")
                if item.no_pvs_override:
                    row = col.row()
                    row.label(text="No Visibility Culling")
                # lightmap
                if item.lightmap_additive_transparency_override:
                    row = col.row()
                    row.prop(item, "lightmap_additive_transparency_ui", text="Additive Transparency")
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
                    row.label(text="Lightmap Lighting From Both Sides")
                # material lighting
                if item.emissive_override:
                    col.separator()
                    box = col.box()
                    row = box.row()
                    row.label(text="Emissive Settings")
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
                # if not (is_proxy or ob.nwo.mesh_type_ui == "_connected_geometry_mesh_type_collision"):
                #     col.separator()
                #     col.menu(NWO_FacePropAddMenu.bl_idname, text="Add Face Layer Property", icon="PLUS")            

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
        col1.template_ID(ob, "active_material", new="nwo.duplicate_material")
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
            tag_type = "Material" if h4 else "Shader"
            col = box.column()
            special_type = get_special_mat(mat)
            if special_type:
                if special_type == 'invisible':
                    col.label(text=f'Invisible {tag_type} applied')
                elif special_type == 'seamsealer':
                    col.label(text=f'SeamSealer Material applied')
                elif special_type == 'invalid':
                    col.label(text=f'Default Invalid {tag_type} applied')
                elif special_type == 'sky':
                    col.label(text=f'Sky Material applied')
                    sky_perm = get_sky_perm(mat)
                    if sky_perm > -1:
                        if sky_perm > 31:
                            col.label(text='Maximum Sky Permutation Index is 31', icon='ERROR')
                        else:
                            col.label(text=f"Sky Permutation {str(sky_perm)}")
                    col.operator("nwo.set_sky", text="Set Sky Permutation")
            elif nwo.rendered:
                col.label(text=f"{txt} Path")
                row = col.row(align=True)
                row.prop(nwo, "shader_path", text="", icon_value=get_icon_id("tags"))
                row.operator("nwo.shader_finder_single", icon_value=get_icon_id("material_finder"), text="")
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "shader_path"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'shader_path'
                has_valid_path = nwo.shader_path and os.path.exists(get_tags_path() + nwo.shader_path)
                if has_valid_path:
                    col.separator()
                    # row.scale_y = 1.5
                    col.operator(
                        "nwo.open_halo_material",
                        icon_value=get_icon_id("foundation"),
                        text="Open in Tag Editor"
                    )
                    shader_path = mat.nwo.shader_path
                    full_path = get_tags_path() + shader_path
                    if os.path.exists(full_path) and shader_path.endswith(('.shader', '.material')):
                        col.operator('nwo.shader_to_nodes', text=f"Convert {txt} to Blender Material", icon='NODE_MATERIAL').mat_name = mat.name
                    col.separator()
                    if material_read_only(nwo.shader_path):
                        col.label(text=f"{txt} is read only")
                        return
                    col.label(text=f'{txt} Export Tools')
                    col.prop(nwo, "uses_blender_nodes", text=f"Link Tag to Nodes", icon='NODETREE')
                    if nwo.uses_blender_nodes:
                        col.operator("nwo.build_shader_single", text=f"Update {tag_type} Tag", icon_value=get_icon_id("material_exporter")).linked_to_blender = True
                        col.separator()
                        if h4:
                            row = col.row(align=True)
                            row.prop(nwo, "material_shader", text="Default Shader")
                            row.operator("nwo.get_material_shaders", icon="VIEWZOOM", text="")
                        else:
                            col.prop(nwo, "shader_type", text="Shader Type")

                else:
                    if nwo.shader_path:
                        col.label(text="Shader Tag Not Found", icon="ERROR")
                    else:
                        col.separator()
                        col.label(text=f'{txt} Export Tools')
                        row = col.row()
                        row.operator("nwo.build_shader_single", text=f"New Empty {tag_type} Tag", icon_value=get_icon_id("material_exporter")).linked_to_blender = False
                        row.operator("nwo.build_shader_single", text=f"New Linked {tag_type} Tag", icon_value=get_icon_id("material_exporter")).linked_to_blender = True
                        col.separator()
                        col_props = col.column()
                        col_props.use_property_split = True
                        col_props.prop(nwo, "shader_dir", text=f"{tag_type} Directory")
                        if h4:
                            row = col_props.row(align=True)
                            row.prop(nwo, "material_shader", text="Default Shader")
                            row.operator("nwo.get_material_shaders", icon="VIEWZOOM", text="")
                        else:
                            col_props.prop(nwo, "shader_type", text="Shader Type")

            else:
                if self.bl_idname == "NWO_PT_MaterialPanel":
                    col.label(text=f"Not a {txt}")
                else:
                    col.label(text=f"Not a {txt}")

            # TEXTURE PROPS
            # First validate if Material has images
            if not mat.node_tree:
                return
            if not recursive_image_search(mat):
                return

            box = self.box.box()
            box.use_property_split = False
            box.label(text="Image Properties")
            col = box.column()
            image = nwo.active_image
            col.template_ID_preview(nwo, "active_image")
            if not image:
                return
            bitmap = image.nwo
            editor = context.preferences.filepaths.image_editor
            if editor and image.filepath and os.path.exists(image.filepath_from_user()):
                col.separator()
                end_part = os_sep_partition(editor.lower(), True).strip("\"'")
                if "photoshop" in end_part:
                    editor_name = "Photoshop"
                    editor_icon = "photoshop"
                elif "gimp" in end_part:
                    editor_name = "Gimp"
                    editor_icon = "paint" # gimp
                elif "paint" in end_part:
                    editor_name = "Paint"
                    editor_icon = "paint"
                elif "affinity" in end_part:
                    editor_name = "Affinity"
                    editor_icon = "affinity"
                else:
                    editor_name = "Image Editor"
                    editor_icon = ""
                col.operator("nwo.open_image_editor", text=f"Open in {editor_name}", icon_value=get_icon_id(editor_icon))

            tags_dir = get_tags_path()
            data_dir = get_data_path()
            bitmap_path = dot_partition(bitmap.filepath) + '.bitmap'
            if not os.path.exists(tags_dir + bitmap_path):
                bitmap_path = dot_partition(image.filepath_from_user().lower().replace(data_dir, "")) + '.bitmap'
            if not os.path.exists(tags_dir + bitmap_path):
                col.separator()
                col.label(text='Bitmap Export Tools')
                col.operator("nwo.export_bitmaps_single", text="Export Bitmap", icon_value=get_icon_id("texture_export"))
                col.separator()
                col_props = col.column()
                col_props.use_property_split = True
                col_props.prop(bitmap, "bitmap_dir", text="Tiff Directory")
                col_props.prop(bitmap, "bitmap_type", text="Type")
                return
            col.separator()
            col.operator("nwo.open_foundation_tag", text="Open in Tag Editor", icon_value=get_icon_id("foundation")).tag_path = bitmap_path
            col.separator()
            col.label(text='Bitmap Export Tools')
            col.prop(bitmap, "export", text="Link Bitmap to Blender Image", icon="TEXTURE")
            if bitmap.export:
                col.operator("nwo.export_bitmaps_single", text="Update Bitmap", icon_value=get_icon_id("texture_export"))
                col.separator()
                col_props = col.column()
                col_props.use_property_split = True
                col_props.prop(bitmap, "bitmap_type", text="Type")
                col_props.prop(bitmap, "reexport_tiff", text="Always Export TIFF")
                


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
            unlink="nwo.unlink_animation"
        )
        action = animation_data.action
        if action:
            nwo = action.nwo
            col2 = row.column()
            col2.alignment = "RIGHT"
            col2.prop(action, "use_frame_range", text="Export")

            if action.use_frame_range:
                col = box.column()
                row = col.row()
                col.separator()
                row.operator("nwo.set_timeline", text="Sync Timeline", icon='TIME')
                row = col.row()
                row.use_property_split = True
                row.prop(action, "frame_start", text='Start Frame')
                row = col.row()
                row.use_property_split = True
                row.prop(action, "frame_end", text='End Frame')
                col.separator()
                row = col.row()
                row.use_property_split = True
                row.prop(nwo, "animation_type")
                scene_nwo = context.scene.nwo
                if nwo.animation_type != 'world':
                    row = col.row()
                    row.use_property_split = True
                    if nwo.animation_type == 'base':
                        row.prop(nwo, 'animation_movement_data')
                    elif nwo.animation_type == 'overlay':
                        row.prop(nwo, 'animation_is_pose')
                        if nwo.animation_is_pose:
                            no_aim_pitch = not scene_nwo.node_usage_pose_blend_pitch
                            no_aim_yaw = not scene_nwo.node_usage_pose_blend_yaw
                            no_pedestal = not scene_nwo.node_usage_pedestal
                            if no_aim_pitch or no_aim_yaw or no_pedestal:
                                col.label(text='Pose Overlay needs Node Usages defined for:', icon='ERROR')
                                missing = []
                                if no_pedestal:
                                    missing.append('Pedestal')
                                if no_aim_pitch:
                                    missing.append('Pose Blend Pitch')
                                if no_aim_yaw:
                                    missing.append('Pose Blend Yaw')
                                
                                col.label(text=', '.join(missing))
                                col.operator('nwo.add_pose_bones', text='Setup Rig for Pose Overlays', icon='SHADERFX')
                                col.separator()
                            else:
                                col.operator('nwo.add_aim_animation', text='Add/Change Aim Bones Animation', icon='ANIM')
                                    
                    elif nwo.animation_type == 'replacement':
                        row.prop(nwo, 'animation_space', expand=True)
                col.separator()
                row = col.row()
                row.use_property_split = True
                row.prop(nwo, "compression", text="Compression")
                col.separator()
                row = col.row()
                row.use_property_split = True
                row.prop(nwo, "name_override")
                col.separator()
                row = col.row()
                # ANIMATION RENAMES
                if not nwo.animation_renames:
                    row.operator("nwo.animation_rename_add", text="New Animation Rename", icon_value=get_icon_id('animation_rename'))
                else:
                    row = col.row()
                    row.label(text="Animation Renames")
                    row = col.row()
                    rows = 3
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
                if not nwo.animation_events:
                    if nwo.animation_renames:
                        row = box.row()
                    row.operator("animation_event.list_add", text="New Animation Event", icon_value=get_icon_id('animation_event'))
                else:
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
            col = box.column()
            col.separator()
            col.operator("nwo.delete_animation", text="DELETE ANIMATION", icon="CANCEL")

    def draw_tools(self):
        box = self.box.box()
        self.draw_asset_shaders(box)
        box = self.box.box()
        self.draw_importer(box)
        if poll_ui(('MODEL', 'FP ANIMATION', 'SKY')):
            box = self.box.box()
            self.draw_rig_tools(box)
        elif poll_ui('SCENARIO'):
            box = self.box.box()
            self.draw_bsp_tools(box)
            
    def draw_bsp_tools(self, box):
        row = box.row()
        col = row.column()
        col.label(text=f"BSP Tools")
        col.operator('nwo.auto_seam', text='Auto-Seam', icon_value=get_icon_id('seam'))
        
    def draw_importer(self, box):
        row = box.row()
        col = row.column()
        col.label(text=f"Importer")
        amf_installed = amf_addon_installed()
        toolset_installed = blender_toolset_installed()
        # if poll_ui('MODEL'):
        #     if blender_toolset_installed():
        #         col.operator('nwo.import_legacy_animation', text="Import Legacy Animations", icon='ANIM')
        #     else:
        #         col.label(text="Halo Blender Toolset required for legacy animations")
        #         col.operator("nwo.open_url", text="Download", icon="BLENDER").url = BLENDER_TOOLSET
        if amf_installed or toolset_installed:
            col.operator('nwo.import', text="Import", icon='IMPORT')
        if not toolset_installed:
            col.label(text="Halo Blender Toolset required for import of legacy model and animation files")
            col.operator("nwo.open_url", text="Download", icon="BLENDER").url = BLENDER_TOOLSET
        if not amf_installed:
            col.label(text="AMF Importer required to import amf files")
            col.operator("nwo.open_url", text="Download", icon_value=get_icon_id("amf")).url = AMF_ADDON
        
    def draw_rig_tools(self, box):
        row = box.row()
        col = row.column()
        nwo = self.scene.nwo
        col.label(text=f"Rig Tools")
        col.use_property_split = True
        col.operator('nwo.validate_rig', text='Validate Rig', icon='ARMATURE_DATA')
        if nwo.multiple_root_bones:
            col.label(text='Multiple Root Bones', icon='ERROR')
        if nwo.armature_has_parent:
            col.label(text='Armature is parented', icon='ERROR')
        if nwo.armature_bad_transforms:
            col.label(text='Armature has bad transforms', icon='ERROR')
            col.operator('nwo.fix_armature_transforms', text='Fix Armature Transforms', icon='SHADERFX')
        if nwo.invalid_root_bone:
            col.label(text='Root Bone has non-standard transforms', icon='QUESTION')
            col.operator('nwo.fix_root_bone', text='Fix Root Bone', icon='SHADERFX')
        if nwo.needs_pose_bones:
            col.label(text='Rig not setup for pose overlay animations', icon='ERROR')
            col.operator('nwo.add_pose_bones', text='Fix for Pose Overlays', icon='SHADERFX')
        if nwo.pose_bones_bad_transforms:
            col.label(text='Pose bones have bad transforms', icon='ERROR')
            col.operator('nwo.fix_pose_bones', text='Fix Pose Bones', icon='SHADERFX')
        if nwo.too_many_bones:
            col.label(text='Rig exceeds the maxmimum number of bones', icon='ERROR')
        if nwo.bone_names_too_long:
            col.label(text='Rig has bone names that exceed 31 characters', icon='ERROR')
            

    def draw_asset_shaders(self, box):
        h4 = self.h4
        count, total = get_halo_material_count()
        shader_type = "Material" if h4 else "Shader"
        # if total:
        row = box.row()
        col = row.column()
        col.label(text=f"Asset {shader_type}s")
        col.use_property_split = True
        # col.separator()
        col.label(
            text=f"{count}/{total} {shader_type} tag paths found",
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
        col1.separator()
        col2.separator()
        col1.operator("nwo.shader_farm", text=f"Batch Build {shader_type}s", icon_value=get_icon_id("material_exporter"))
        col2.popover(panel=NWO_ShaderFarmPopover.bl_idname, text="")
        col1.separator()
        col.operator("nwo.stomp_materials", text=f"Remove Duplicate Materials", icon='X')
        if h4:
            col.separator()
            col.operator("nwo.open_matman", text="Open Material Tag Viewer", icon_value=get_icon_id("foundation"))


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
        prefs = get_prefs()
        box = self.box.box()
        context = self.context
        box.label(text=update_str, icon_value=get_icon_id("foundry"))
        if update_needed:
            box.operator("nwo.open_url", text="Get Latest", icon_value=get_icon_id("github")).url = FOUNDRY_GITHUB

        if not nwo_globals.clr_installed:
            box = self.box.box()
            box.label(text="Install required to use Halo Tag API (ManagedBlam)")
            row = box.row(align=True)
            row.scale_y = 1.5
            row.operator("managed_blam.init", text="Install ManagedBlam Dependency", icon='IMPORT').install_only = True
        
        box = self.box.box()
        row = box.row()
        row.label(text="Projects")
        row = box.row()
        rows = 3
        row.template_list(
            "NWO_UL_Projects",
            "",
            prefs,
            "projects",
            prefs,
            "current_project_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.project_add", text="", icon="ADD")
        col.operator("nwo.project_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.project_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.project_move", icon="TRIA_DOWN", text="").direction = 'down'
        row = box.row(align=True, heading="Tool Version")
        row.prop(prefs, "tool_type", expand=True)
        row = box.row(align=True)
        row.prop(prefs, "apply_prefix")
        row = box.row(align=True)
        row.prop(prefs, "apply_materials", text="Apply Types Operator Updates Materials")
        row = box.row(align=True)
        row.prop(prefs, "apply_empty_display")
        # row = box.row(align=True)
        # row.prop(prefs, "poop_default")
        row = box.row(align=True)
        row.prop(prefs, "toolbar_icons_only", text="Foundry Toolbar Icons Only")
        row = box.row(align=True)
        row.prop(prefs, "protect_materials")
        row = box.row(align=True)
        row.prop(prefs, "update_materials_on_shader_path")
        blend_prefs = context.preferences
        if blend_prefs.use_preferences_save and (not bpy.app.use_userpref_skip_save_on_exit):
            return
        row = box.row()
        row.operator("wm.save_userpref", text=("Save Foundry Settings") + (" *" if blend_prefs.is_dirty else ""))


    def draw_table_menus(self, col, nwo, ob):
        perm_name = "Permutation"
        region_name = "Region"
        ob_is_mesh = is_mesh(ob)
        is_seam = nwo.mesh_type_ui == "_connected_geometry_mesh_type_seam" and ob_is_mesh
        if poll_ui("SCENARIO"):
            perm_name = "Layer"
            if is_seam:
                region_name = "Frontfacing BSP"
            else:
                region_name = "BSP"
        elif poll_ui('MODEL') and ob_is_mesh:
            if ob.data.nwo.face_props and nwo.mesh_type_ui in ('_connected_geometry_mesh_type_object_structure', '_connected_geometry_mesh_type_collision', '_connected_geometry_mesh_type_default'):
                for prop in ob.data.nwo.face_props:
                    if prop.region_name_override:
                        region_name += '*'
                        break

        row = col.row()
        split = row.split()
        col1 = split.column()
        col2 = split.column()
        if is_seam:
            col3 = split.column()
        col1.enabled = not nwo.region_name_locked_ui
        if is_seam:
            col3.enabled = not nwo.permutation_name_locked_ui
        else:
            col2.enabled = not nwo.permutation_name_locked_ui
        col1.label(text=region_name, icon_value=get_icon_id("collection_creator") if nwo.region_name_locked_ui else 0)
        if is_seam:
            col2.label(text="Backfacing BSP", icon_value=get_icon_id("collection_creator") if nwo.permutation_name_locked_ui else 0)
            col3.label(text=perm_name, icon_value=get_icon_id("collection_creator") if nwo.permutation_name_locked_ui else 0)
        else:
            col2.label(text=perm_name, icon_value=get_icon_id("collection_creator") if nwo.permutation_name_locked_ui else 0)
        col1.menu("NWO_MT_Regions", text=true_region(nwo), icon_value=get_icon_id("region"))
        if is_seam:
            if true_region(nwo) == nwo.seam_back_ui:
                col2.menu("NWO_MT_SeamBackface", text="", icon='ERROR')
            else:
                col2.menu("NWO_MT_SeamBackface", text=nwo.seam_back_ui, icon_value=get_icon_id("region"))
            col3.menu("NWO_MT_Permutations", text=true_permutation(nwo), icon_value=get_icon_id("permutation"))
        else:
            col2.menu("NWO_MT_Permutations", text=true_permutation(nwo), icon_value=get_icon_id("permutation"))
        col.separator()

class NWO_FoundryPanelPopover(Operator, NWO_FoundryPanelProps):
    bl_label = "Foundry Panel"
    bl_idname = "nwo.show_foundry_panel"
    bl_description = "Loads the Foundry Panel at the position of the mouse cursor"
    bl_icon = 'MESH'
    
    def execute(self, context):
        return context.window_manager.invoke_popup(self, width=450)

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
            case "show_foundry_panel":
                return "Opens the Foundry Panel at the current mouse cursor position"
                

    @staticmethod
    def hotkey_info(self, context):
        layout = self.layout
        layout.label(text=NWO_HotkeyDescription.description(context, self.hotkey))


class NWO_ProjectChooserMenu(bpy.types.Menu):
    bl_label = "Choose Project"
    bl_idname = "NWO_MT_ProjectChooser"

    @classmethod
    def poll(self, context):
        prefs = get_prefs()
        return prefs.projects

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs()
        projects = prefs.projects
        for p in projects:
            name = p.name
            thumbnail = os.path.join(p.project_path, p.project_image_path)
            if os.path.exists(thumbnail):
                icon_id = get_icon_id_in_directory(thumbnail)
            elif p.project_remote_server_name == "bngtoolsql":
                icon_id = get_icon_id("halo_reach")
            elif p.project_remote_server_name == "metawins":
                icon_id = get_icon_id("halo_4")
            elif p.project_remote_server_name == "episql.343i.selfhost.corp.microsoft.com":
                icon_id = get_icon_id("halo_2amp")
            else:
                icon_id = get_icon_id("tag_test")
            layout.operator("nwo.project_select", text=name, icon_value=icon_id).project_name = name

        if self.bl_idname == "NWO_MT_ProjectChooser":
            layout.operator("nwo.project_add", text="New Project", icon="ADD").set_scene_project = True

class NWO_ProjectChooserMenuDisallowNew(NWO_ProjectChooserMenu):
    bl_idname = "NWO_MT_ProjectChooserDisallowNew"

class NWO_ProjectChooser(Operator):
    bl_label = "Select Project"
    bl_idname = "nwo.project_select"
    bl_description = "Select the project to use for this asset"
    bl_property = "project_name"

    @classmethod
    def poll(self, context):
        prefs = get_prefs()
        return prefs.projects

    project_name : StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        nwo.scene_project = self.project_name
        return {'FINISHED'}

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
        set_object_mode(context)
        objects = context.view_layer.objects
        scene = context.scene
        if scene.nwo.main_armature:
            arm = scene.nwo.main_armature
        else:
            rigs = [ob for ob in objects if ob.type == 'ARMATURE']
            if not rigs:
                self.report({'WARNING'}, "No Armature in Scene")
                return {'CANCELLED'}
            elif len(rigs) > 1:
                if scene.nwo.parent_rig and scene.nwo.parent_rig.type == 'ARMATURE':
                    arm = scene.nwo.parent_rig
                else:
                    self.report({'WARNING'}, "Multiple Armatures found. Please validate rig under Foundry Tools > Rig Tools")
                    return {'CANCELLED'}
            arm = rigs[0]
        deselect_all_objects()
        arm.hide_set(False)
        arm.hide_select = False
        arm.select_set(True)
        set_active_object(arm)
        self.report({'INFO'}, F"Selected {arm.name}")

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
        self.h4 = is_corinth()
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
        elif self.multi and getattr(nwo, prop):
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
        self.multi = event.shift
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
    
class NWO_DuplicateMaterial(Operator):
    bl_idname = 'nwo.duplicate_material'
    bl_label = 'Duplicate Material'
    bl_description = 'Duplicates the active material'
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object
    
    def execute(self, context):
        ob = context.object
        if ob.active_material:
            new_mat = ob.active_material.copy()
        else:
            new_mat = bpy.data.materials.new(name='Material')
        ob.active_material = new_mat
        return {'FINISHED'}

class NWO_ScaleModels_Add(Operator, AddObjectHelper):
    bl_idname = "mesh.add_halo_scale_model"
    bl_label = "Halo Scale Model"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Create a new Halo Scale Model Object"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

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
    
def add_halo_light_button(self, context):
    self.layout.operator(
        'nwo.add_halo_light',
        text="Halo Light",
        icon='LIGHT',
    )

def add_halo_armature_buttons(self, context):
    self.layout.operator("nwo.armature_create", text="Halo Skeleton", icon_value=get_icon_id("rig_creator"))

def create_halo_collection(self, context):
    self.layout.operator("nwo.collection_create" , text="", icon_value=get_icon_id("collection_creator"))

from .halo_join import NWO_JoinHalo

def add_halo_join(self, context):
    self.layout.operator(NWO_JoinHalo.bl_idname, text="Halo Join")

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
        row = col.row()
        row.prop(scene_nwo_halo_launcher, "use_play")
        col.separator()
        col.prop(scene_nwo_halo_launcher, "insertion_point_index")
        col.prop(scene_nwo_halo_launcher, "initial_zone_set")
        if is_corinth():
            col.prop(scene_nwo_halo_launcher, "initial_bsp")
        col.prop(scene_nwo_halo_launcher, "custom_functions")

        col.prop(scene_nwo_halo_launcher, "run_game_scripts")
        if is_corinth():
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
        if is_corinth():
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
        if is_corinth():
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
        if is_corinth():
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
            if is_corinth():
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

        return open_file_explorer(
            scene_nwo_halo_launcher.explorer_default,
            False,
        )


class NWO_HaloLauncher_Tags(Operator):
    """Opens the Tags Folder"""

    bl_idname = "nwo.launch_tags"
    bl_label = "Tags"

    def execute(self, context):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher

        return open_file_explorer(
            scene_nwo_halo_launcher.explorer_default,
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
    
    def update_sidecar_path(self, context):
        self["sidecar_path"] = clean_tag_path(self["sidecar_path"]).strip('"')
    
    sidecar_path: StringProperty(
        name="",
        description="",
        default="",
        update=update_sidecar_path,
    )
    asset_name: StringProperty(
        name="",
        description="",
        default="",
    )

    explorer_default: EnumProperty(
        name="Folder",
        description="Select whether to open the root data / tags folder, the blend folder, or the one for your asset. When no asset is found, defaults to root",
        default="asset",
        options=set(),
        items=[("default", "Root", ""), ("asset", "Asset", ""), ("blend", "Blend", "")],
    )

    foundation_default: EnumProperty(
        name="Tags",
        description="Select whether Foundation should open with the last opended windows, or open to the selected asset tags",
        default="asset",
        options=set(),
        items=[
            ("last", "Default", ""),
            ("asset", "Asset", ""),
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

    use_play : BoolProperty(
        name="Use Play Variant",
        description="Launches sapien_play / tag_play instead. These versions have less debug information and should load faster",
    )

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
    bl_idname = "nwo.shader_finder"
    bl_label = ""
    bl_description = 'Searches the tags folder for shaders (or the specified directory) and applies all that match blender material names'
    bl_options = {"UNDO"}

    def execute(self, context):
        scene = context.scene
        scene_nwo_shader_finder = scene.nwo_shader_finder
        from .shader_finder import find_shaders

        return find_shaders(
            bpy.data.materials,
            is_corinth(),
            self.report,
            scene_nwo_shader_finder.shaders_dir,
            scene_nwo_shader_finder.overwrite_existing,
            scene_nwo_shader_finder.set_non_export,
        )

    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str:
        if is_corinth():
            return "Searches the tags folder for Materials (or only the specified directory) and applies all that match blender material names"
        else:
            return "Searches the tags folder for Shaders (or only the specified directory) and applies all that match blender material names"

class NWO_ShaderFinder_FindSingle(NWO_ShaderFinder_Find):
    bl_idname = "nwo.shader_finder_single"
    bl_description = ''

    def execute(self, context):
        scene = context.scene
        scene_nwo_shader_finder = scene.nwo_shader_finder
        from .shader_finder import find_shaders

        return find_shaders(
            [context.object.active_material],
            is_corinth(),
            self.report,
            scene_nwo_shader_finder.shaders_dir,
            True,
            False,
        )
    
    @classmethod
    def description(cls, context: Context, properties: OperatorProperties) -> str:
        if is_corinth():
            return "Returns the path of the first Material tag which matches the name of the active Blender material"
        else:
            return "Returns the path of the first Shader tag which matches the name of the active Blender material"

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
        h4 = is_corinth(context)
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
                    # if not h4:
                    # NOTE light map regions don't appear to work
                    #     col.prop(scene_nwo_export, "lightmap_region")


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
        h4 = is_corinth(context)
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
        col.prop(scene_nwo_export, 'triangulate', text="Triangulate")
        if scene_nwo.asset_type in ('MODEL', 'SKY', 'FP ANIMATION'):
            # col.prop(scene_nwo_export, "fix_bone_rotations", text="Fix Bone Rotations") # NOTE To restore when this works correctly
            col.prop(scene_nwo_export, "fast_animation_export", text="Fast Animation Export")
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
            # col.prop(scene_nwo_export, "import_verbose", text="Verbose Output")
            col.prop(
                scene_nwo_export,
                "import_suppress_errors",
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
    bl_description = "Exports the current Halo asset and creates tags"

    def execute(self, context):
        from .halo_export import export_quick, export

        scene = context.scene
        scene_nwo_export = scene.nwo_export
        if scene_nwo_export.export_quick and valid_nwo_asset(context):
            return export_quick(bpy.ops.export_scene.nwo)
        else:
            return export(bpy.ops.export_scene.nwo)


class NWO_HaloExportPropertiesGroup(PropertyGroup):
    triangulate: BoolProperty(
        name="Triangulate",
        description="Applies a triangulation modifier to all objects at export if they do not already have one",
        default=False,
        options=set(),
    )
    fast_animation_export : BoolProperty(
        name="Fast Animation Export",
        description="Speeds up exports by ignoring everything but the armature during animation exports. Do not use if your animation relies on helper objects. You should ensure animations begin at frame 0 if using this option",
        default=False,
        options=set(),
    )
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
                "__custom__",
                "Custom",
                "Opens a lightmap settings dialog",
                0,
            )
        )
        items.append(
            (
                "__asset__",
                "Asset",
                "Uses the asset defined lightmap settings",
                1,
            )
        )
        lightmapper_globals_dir = path_join(
            get_tags_path(), "globals", "lightmapper_settings"
        )
        if file_exists(lightmapper_globals_dir):
            from os import listdir

            index = 2
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
        options=set(),
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
        nwo_globals.foundry_output_state = self.show_output

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
        options=set(),
    )

    import_draft: BoolProperty(
        name="Draft",
        description="Skip generating PRT data. Faster speed, lower quality",
        default=False,
        options=set(),
    )
    import_seam_debug: BoolProperty(
        name="Seam Debug",
        description="Write extra seam debugging information to the console",
        default=False,
        options=set(),
    )
    import_skip_instances: BoolProperty(
        name="Skip Instances",
        description="Skip importing all instanced geometry",
        default=False,
        options=set(),
    )
    import_decompose_instances: BoolProperty(
        name="Decompose Instances",
        description="Run convex decomposition for instanced geometry physics (very slow)",
        default=False,
        options=set(),
    )
    import_suppress_errors: BoolProperty(
        name="Surpress Errors",
        description="Do not write errors to vrml files",
        default=False,
        options=set(),
    )
    import_lighting: BoolProperty(
        name="Lighting Info Only",
        description="Only the scenario_structure_lighting_info tag will be reimported",
        default=False,
        options=set(),
    )
    import_meta_only: BoolProperty(
        name="Meta Only",
        description="Import only the structure_meta tag",
        default=False,
        options=set(),
    )
    import_disable_hulls: BoolProperty(
        name="Disable Hulls",
        description="Disables the contruction of convex hulls for instance physics and collision",
        default=False,
        options=set(),
    )
    import_disable_collision: BoolProperty(
        name="Disable Collision",
        description="Do not generate complex collision",
        default=False,
        options=set(),
    )
    import_no_pca: BoolProperty(
        name="No PCA",
        description="Skips PCA calculations",
        default=False,
        options=set(),
    )
    import_force_animations: BoolProperty(
        name="Force Animations",
        description="Force import of all animations that had errors during the last import",
        default=False,
        options=set(),
    )
    fix_bone_rotations: BoolProperty(
        name="Fix Bone Rotations",
        description="Sets the rotation of the following bones to match Halo conventions: pedestal, aim_pitch, aim_yaw, gun",
        default=True,
        options=set(),
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

    def type_items(self, context):
        items = []
        r_name = "Region"
        p_name = "Permutation"
        if context.scene.nwo.asset_type == "SCENARIO":
            r_name = "BSP"
            p_name = "Layer"

        items.append(("region", r_name, ""))
        items.append(("permutation", p_name, ""))
        items.append(("exclude", "Exclude", ""))

        return items

    type: bpy.props.EnumProperty(
        name="Collection Type",
        items=type_items,
        )
    
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
    bl_idname = "nwo.armature_create"
    bl_label = "Create Armature"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Creates a Halo rig with a pedestal bone, and optionally pose and control bones"
    
    has_pedestal_control: BoolProperty()
    has_pose_bones: BoolProperty()
    has_aim_control: BoolProperty()
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        scene = context.scene
        asset_name = scene.nwo_halo_launcher.sidecar_path.rpartition("\\")[2].replace(
            ".sidecar.xml", ""
        )
        if asset_name:
            data = bpy.data.armatures.new(f'{asset_name}_world')
        else:
            data = bpy.data.armatures.new('Armature')
        
        arm = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(arm)
        context.scene.nwo.main_armature = arm
        arm.select_set(True)
        set_active_object(arm)
        
        bpy.ops.object.editmode_toggle()
        
        pedestal = data.edit_bones.new('b_pedestal')
        pedestal.head = [0, 0, 0]
        pedestal.tail = [0, 1, 0]
        
        bpy.ops.object.editmode_toggle()
        if self.has_pedestal_control:
            bpy.ops.nwo.add_pedestal_control()
        if self.has_pose_bones:
            if self.has_aim_control:
                bpy.ops.nwo.add_pose_bones(add_control_bone=True)
            else:
                bpy.ops.nwo.add_pose_bones()
        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'has_pedestal_control', text='Add Pedestal Control')
        layout.prop(self, 'has_pose_bones', text='Add Aim Bones')
        if self.has_pose_bones:
            layout.prop(self, 'has_aim_control', text='Add Aim Control')
        

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

class NWO_Shader_BuildSingle(Operator):
    bl_idname = "nwo.build_shader_single"
    bl_label = ""
    bl_options = {"UNDO"}
    bl_description = ""

    linked_to_blender : BoolProperty()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and not protected_material_name(context.object.active_material.name)
    
    def execute(self, context):
        with ExportManager():
            nwo = context.object.active_material.nwo
            nwo.uses_blender_nodes = self.linked_to_blender
            return build_shader(
                context.object.active_material,
                is_corinth(context),
                report=self.report,
            )
    
    @classmethod
    def description(cls, context, properties) -> str:
        tag_type = 'material' if is_corinth(context) else 'shader'
        if properties.linked_to_blender:
            return f"Creates an linked {tag_type} tag for this material. The tag will populate using Blender Material Nodes"
        else:
            return f"Creates an empty {tag_type} tag for this material"


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
    
class NWO_AddPoseBones(Operator):
    bl_idname = 'nwo.add_pose_bones'
    bl_label = 'Add Aim Bones'
    bl_description = 'Adds aim bones to the armature if missing, optionally with a control bone. Assigns node usage bones'
    bl_options = {'REGISTER', 'UNDO'}
    
    add_control_bone: BoolProperty()
    has_control_bone: BoolProperty()
    skip_invoke: BoolProperty()
    
    # @classmethod
    # def poll(cls, context):
    #     return context.scene.nwo.main_armature
    
    def new_bone(self, arm, parent_name, bone_name):
        parent_edit = arm.data.edit_bones.get(parent_name)
        new_edit = arm.data.edit_bones.new(bone_name)
        new_edit.parent = parent_edit
        new_edit.head = parent_edit.head
        new_edit.tail = parent_edit.tail
        new_edit.matrix = parent_edit.matrix
        
        return new_edit.name
    
    def new_control_bone(self, arm, parent_name, bone_name, pitch_name, yaw_name, shape_ob):
        parent_edit = arm.data.edit_bones.get(parent_name)
        new_edit = arm.data.edit_bones.new(bone_name)
        new_edit.parent = parent_edit
        new_edit.tail[1] = 1
        name = new_edit.name
        bpy.ops.object.mode_set(mode="POSE", toggle=False)
        new_bone = arm.data.bones.get(name)
        new_pose = arm.pose.bones.get(name)
        new_bone.use_deform = False
        new_pose.custom_shape = shape_ob
        
        # Constraints for the control bone
        cons = new_pose.constraints
        
        limit_scale = cons.new('LIMIT_SCALE')
        limit_scale.use_min_x = True
        limit_scale.use_min_y = True
        limit_scale.use_min_z = True
        limit_scale.use_max_x = True
        limit_scale.use_max_y = True
        limit_scale.use_max_z = True
        limit_scale.min_x = 1
        limit_scale.min_y = 1
        limit_scale.min_z = 1
        limit_scale.max_x = 1
        limit_scale.max_y = 1
        limit_scale.max_z = 1
        limit_scale.use_transform_limit = True
        limit_scale.owner_space = 'LOCAL'
        
        # limit_rotation = cons.new('LIMIT_ROTATION')
        # limit_rotation.use_limit_x = True
        # limit_rotation.use_limit_y = True
        # limit_rotation.use_limit_z = True
        # limit_rotation.min_y = radians(-90)
        # limit_rotation.max_y = radians(90)
        # limit_rotation.min_z = radians(-90)
        # limit_rotation.max_z = radians(90)
        # limit_rotation.use_transform_limit = True
        # limit_rotation.owner_space = 'LOCAL'
        
        limit_location = cons.new('LIMIT_LOCATION')
        limit_location.use_min_x = True
        limit_location.use_min_y = True
        limit_location.use_min_z = True
        limit_location.use_max_x = True
        limit_location.use_max_y = True
        limit_location.use_max_z = True
        limit_location.use_transform_limit = True
        limit_location.owner_space = 'LOCAL'
        
        # Constraints for the pitch bone
        pose_pitch = arm.pose.bones.get(pitch_name)
        cons = pose_pitch.constraints
        copy_rotation = cons.new('COPY_ROTATION')
        copy_rotation.target = arm
        copy_rotation.subtarget = name
        copy_rotation.use_x = False
        copy_rotation.use_z = False
        copy_rotation.target_space = 'LOCAL_OWNER_ORIENT'
        copy_rotation.owner_space = 'LOCAL'
        
        # Constraints for the yaw bone
        pose_yaw = arm.pose.bones.get(yaw_name)
        cons = pose_yaw.constraints
        copy_rotation = cons.new('COPY_ROTATION')
        copy_rotation.target = arm
        copy_rotation.subtarget = name
        copy_rotation.use_x = False
        copy_rotation.use_y = False
        copy_rotation.target_space = 'LOCAL_OWNER_ORIENT'
        copy_rotation.owner_space = 'LOCAL'
        
        return name
        
    def execute(self, context):
        scene_nwo = context.scene.nwo
        arm = get_rig(context)
        bones = arm.data.bones
        for b in bones:
            if b.use_deform and not b.parent:
                scene_nwo.node_usage_pedestal = b.name
                parent_bone = b
                parent_bone_name = parent_bone.name
                break
        else:
            self.report({'WARNING'}, 'Failed to assign pedestal node usage')
            return {'FINISHED'}
        
        for b in bones:
            if not scene_nwo.node_usage_pose_blend_pitch and b.use_deform and b.parent == parent_bone and 'pitch' in b.name:
                scene_nwo.node_usage_pose_blend_pitch = b.name
            elif not scene_nwo.node_usage_pose_blend_yaw and b.use_deform and b.parent == parent_bone and 'yaw' in b.name:
                scene_nwo.node_usage_pose_blend_yaw = b.name
                
        # Get missing node usages
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        if scene_nwo.node_usage_pose_blend_pitch:
            pitch_name = scene_nwo.node_usage_pose_blend_pitch
        else:
            pitch_name = self.new_bone(arm, parent_bone_name, 'b_aim_pitch')
            scene_nwo.node_usage_pose_blend_pitch = pitch_name
        if scene_nwo.node_usage_pose_blend_yaw:
            yaw_name = scene_nwo.node_usage_pose_blend_yaw
        else:
            yaw_name = self.new_bone(arm, parent_bone_name, 'b_aim_yaw')
            scene_nwo.node_usage_pose_blend_yaw = yaw_name
            
        if self.add_control_bone and not self.has_control_bone:
            bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
            existing_obs = context.view_layer.objects[:]
            resources_zip = os.path.join(addon_root(), "resources.zip")
            control_bone_path = os.path.join('rigs', 'shape_aim_control.glb')
            full_path = os.path.join(addon_root(), 'resources', control_bone_path)
            if os.path.exists(full_path):
                import_gltf(full_path)
            elif os.path.exists(resources_zip):
                file = extract_from_resources(control_bone_path)
                if os.path.exists(file):
                    import_gltf(file)
                    os.remove(file)
            else:
                self.report({'ERROR'}, 'Failed to extract control shape')
                return {'FINISHED'}
                
            bone_shape = [ob for ob in context.view_layer.objects if ob not in existing_obs][0]
            bone_shape.select_set(False)
            bone_shape.nwo.export_this = False
            arm.select_set(True)
            set_active_object(arm)
            bpy.ops.object.mode_set(mode="EDIT", toggle=False)
            scene_nwo.control_aim = self.new_control_bone(arm, parent_bone_name, 'c_aim', pitch_name, yaw_name, bone_shape)
            unlink(bone_shape)
            
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        context.scene.nwo.needs_pose_bones = False
        return {'FINISHED'}
    
    def invoke(self, context, event):
        scene_nwo = context.scene.nwo
        if scene_nwo.control_aim:
            self.report({'INFO'}, "Aim Control bone already set")
            self.has_control_bone = True
            return self.execute(context)
        else:
            self.has_control_bone = False
            if self.skip_invoke:
                self.add_control_bone = True
                return self.execute(context)
            wm = context.window_manager
            return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        self.layout.prop(self, 'add_control_bone', text='Add Aim Control Bone')
        
class NWO_ValidateRig(Operator):
    bl_idname = 'nwo.validate_rig'
    bl_label = 'Validate Rig'
    bl_description = 'Runs a number of checks on the model armature, highlighting issues and providing fixes'
    
    def get_root_bone(self, rig, scene):
        root_bones = [b for b in rig.data.bones if b.use_deform and not b.parent]
        if len(root_bones) > 1:
            scene.nwo.multiple_root_bones = True
            return
        return root_bones[0].name
    
    def validate_root_rot(self, rig, root_bone_name, scene):
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        # Valid rotation depends on model forward direction
        # Given false tuples hightlight whether tail values should be zero = (x, y, z)
        # x_postive = (0, 1, 0)
        # y_postive = (-1, 0, 0)
        # x_negative = (0, -1, 0)
        # y_postive = (1, 0, 0)
        edit_root = rig.data.edit_bones.get(root_bone_name)
        match scene.nwo.forward_direction:
            case 'x':
                tail_okay = (
                edit_root.tail[0] == 0 and
                edit_root.tail[1] > 0 and
                edit_root.tail[0] == 0)
            case 'x-':
                tail_okay = (
                edit_root.tail[0] == 0 and
                edit_root.tail[1] < 0 and
                edit_root.tail[0] == 0)
            case 'y':
                tail_okay = (
                edit_root.tail[0] < 0 and
                edit_root.tail[1] == 0 and
                edit_root.tail[0] == 0)
            case 'y-':
                tail_okay = (
                edit_root.tail[0] > 0 and
                edit_root.tail[1] == 0 and
                edit_root.tail[0] == 0)
                
        head_okay = edit_root.head[0] == 0 and edit_root.head[1] == 0 and edit_root.head[2] == 0
        roll_okay = edit_root.roll == 0
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        
        return tail_okay and head_okay and roll_okay
    
    def validate_pose_bones_transforms(self, scene_nwo):
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        edit_bones = self.rig.data.edit_bones
        pedestal: bpy.types.EditBone = edit_bones.get(scene_nwo.node_usage_pedestal)
        aim_yaw: bpy.types.EditBone = edit_bones.get(scene_nwo.node_usage_pose_blend_pitch)
        aim_pitch: bpy.types.EditBone = edit_bones.get(scene_nwo.node_usage_pose_blend_yaw)
        validated = aim_pitch.matrix == pedestal.matrix and aim_yaw.matrix == pedestal.matrix
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        return validated
    
    def needs_pose_bones(self, scene_nwo):
        usage_set =  scene_nwo.node_usage_pedestal and scene_nwo.node_usage_pose_blend_pitch and scene_nwo.node_usage_pose_blend_yaw
        if usage_set:
            return False
        for action in bpy.data.actions:
            if action.frame_range:
                if action.nwo.animation_type == 'overlay' and action.nwo.animation_is_pose:
                    return True
                
        return False
    
    def armature_transforms_valid(self, rig):
        return rig.matrix_world == Matrix(((1.0, 0.0, 0.0, 0.0),
                                    (0.0, 1.0, 0.0, 0.0),
                                    (0.0, 0.0, 1.0, 0.0),
                                    (0.0, 0.0, 0.0, 1.0)))
            
    def complete_validation(self):
        if self.rig_was_unselectable:
            self.rig.hide_select = True
        if self.rig_was_hidden:
            self.rig.hide_set(True)
        if self.old_active:
            set_active_object(self.old_active)
        if self.old_mode:
            if self.old_mode == 'POSE':
                bpy.ops.object.mode_set(mode='POSE', toggle=False)
            elif self.old_mode.startswith('EDIT'):
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
                
        return {'FINISHED'}
    
    def valid_message(self):
        options = [
            "Rig valid!",
            "Rig validated",
            "Rig is good",
            "Rig is ready for export",
            "Tool is gonna love this rig",
            "You are valid and your rig is valid",
        ]
        return random.choice(options)
    
    def too_many_bones(self, rig):
        bones = rig.data.bones
        return len(bones) > 253
    
    def bone_names_too_long(self):
        bones = self.rig.data.bones
        bones_with_long_names = [b.name for b in bones if len(b.name) > 31]
        for b in bones_with_long_names:
            self.report({'WARNING'}, b)
        return bool(bones_with_long_names)
        
    
    def strip_null_rig_refs(self, scene_nwo, rig):
        bone_names = [b.name for b in rig.data.bones]
        if scene_nwo.control_pedestal and scene_nwo.control_pedestal not in bone_names:
            scene_nwo.control_pedestal = ""
        if scene_nwo.control_aim and scene_nwo.control_aim not in bone_names:
            scene_nwo.control_aim = ""
        if scene_nwo.node_usage_pedestal and scene_nwo.node_usage_pedestal not in bone_names:
            scene_nwo.node_usage_pedestal = ""
        if scene_nwo.node_usage_pose_blend_pitch and scene_nwo.node_usage_pose_blend_pitch not in bone_names:
            scene_nwo.node_usage_pose_blend_pitch = ""
        if scene_nwo.node_usage_pose_blend_yaw and scene_nwo.node_usage_pose_blend_yaw not in bone_names:
            scene_nwo.node_usage_pose_blend_yaw = ""
        if scene_nwo.node_usage_physics_control and scene_nwo.node_usage_physics_control not in bone_names:
            scene_nwo.node_usage_physics_control = ""
        if scene_nwo.node_usage_camera_control and scene_nwo.node_usage_camera_control not in bone_names:
            scene_nwo.node_usage_camera_control = ""
        if scene_nwo.node_usage_origin_marker and scene_nwo.node_usage_origin_marker not in bone_names:
            scene_nwo.node_usage_origin_marker = ""
        if scene_nwo.node_usage_weapon_ik and scene_nwo.node_usage_weapon_ik not in bone_names:
            scene_nwo.node_usage_weapon_ik = ""
        if scene_nwo.node_usage_pelvis and scene_nwo.node_usage_pelvis not in bone_names:
            scene_nwo.node_usage_pelvis = ""
        if scene_nwo.node_usage_left_clavicle and scene_nwo.node_usage_left_clavicle not in bone_names:
            scene_nwo.node_usage_left_clavicle = ""
        if scene_nwo.node_usage_left_clavicle and scene_nwo.node_usage_left_clavicle not in bone_names:
            scene_nwo.node_usage_left_clavicle = ""
        if scene_nwo.node_usage_left_upperarm and scene_nwo.node_usage_left_upperarm not in bone_names:
            scene_nwo.node_usage_left_upperarm = ""
        if scene_nwo.node_usage_left_foot and scene_nwo.node_usage_left_foot not in bone_names:
            scene_nwo.node_usage_left_foot = ""
        if scene_nwo.node_usage_left_hand and scene_nwo.node_usage_left_hand not in bone_names:
            scene_nwo.node_usage_left_hand = ""
        if scene_nwo.node_usage_right_foot and scene_nwo.node_usage_right_foot not in bone_names:
            scene_nwo.node_usage_right_foot = ""
        if scene_nwo.node_usage_right_hand and scene_nwo.node_usage_right_hand not in bone_names:
            scene_nwo.node_usage_right_hand = ""
        if scene_nwo.node_usage_damage_root_gut and scene_nwo.node_usage_damage_root_gut not in bone_names:
            scene_nwo.node_usage_damage_root_gut = ""
        if scene_nwo.node_usage_damage_root_chest and scene_nwo.node_usage_damage_root_chest not in bone_names:
            scene_nwo.node_usage_damage_root_chest = ""
        if scene_nwo.node_usage_damage_root_head and scene_nwo.node_usage_damage_root_head not in bone_names:
            scene_nwo.node_usage_damage_root_head = ""
        if scene_nwo.node_usage_damage_root_left_shoulder and scene_nwo.node_usage_damage_root_left_shoulder not in bone_names:
            scene_nwo.node_usage_damage_root_left_shoulder = ""
        if scene_nwo.node_usage_damage_root_left_arm and scene_nwo.node_usage_damage_root_left_arm not in bone_names:
            scene_nwo.node_usage_damage_root_left_arm = ""
        if scene_nwo.node_usage_damage_root_left_leg and scene_nwo.node_usage_damage_root_left_leg not in bone_names:
            scene_nwo.node_usage_damage_root_left_leg = ""
        if scene_nwo.node_usage_damage_root_left_foot and scene_nwo.node_usage_damage_root_left_foot not in bone_names:
            scene_nwo.node_usage_damage_root_left_foot = ""
        if scene_nwo.node_usage_damage_root_right_shoulder and scene_nwo.node_usage_damage_root_right_shoulder not in bone_names:
            scene_nwo.node_usage_damage_root_right_shoulder = ""
        if scene_nwo.node_usage_damage_root_right_arm and scene_nwo.node_usage_damage_root_right_arm not in bone_names:
            scene_nwo.node_usage_damage_root_right_arm = ""
        if scene_nwo.node_usage_damage_root_right_leg and scene_nwo.node_usage_damage_root_right_leg not in bone_names:
            scene_nwo.node_usage_damage_root_right_leg = ""
        if scene_nwo.node_usage_damage_root_right_foot and scene_nwo.node_usage_damage_root_right_foot not in bone_names:
            scene_nwo.node_usage_damage_root_right_foot = ""
            
    def execute(self, context):
        self.old_mode = context.mode
        self.old_active = context.object
        self.rig_was_unselectable = False
        self.rig_was_hidden = False
        set_object_mode(context)
        scene = context.scene
        scene_nwo = scene.nwo
        self.rig = get_rig(context, True)
        multi_rigs = type(self.rig) == list
        no_rig = self.rig is None
        if no_rig or multi_rigs:
            if multi_rigs:
                self.report({'WARNING'}, 'Multiple armatures in scene. Please declare the main armature in the Asset Editor')
            else:
                self.report({'INFO'}, "No Armature in scene. Armature only required if you want this model to animate")
                scene_nwo.multiple_root_bones = False
                scene_nwo.invalid_root_bone = False
                scene_nwo.needs_pose_bones = False
                scene_nwo.armature_bad_transforms = False
                scene_nwo.armature_has_parent = False
                scene_nwo.too_many_bones = False
                scene_nwo.bone_names_too_long = False
                scene_nwo.pose_bones_bad_transforms = False
                
            return self.complete_validation()
        
        self.strip_null_rig_refs(scene_nwo, self.rig)
        
        if self.rig.parent:
            scene_nwo.armature_has_parent = True
            self.report({'WARNING'}, 'Armature is parented')
        else:
            scene_nwo.armature_has_parent = False
        
        if self.armature_transforms_valid(self.rig):
            scene_nwo.armature_bad_transforms = False
        else:
            scene_nwo.armature_bad_transforms = True
            self.report({'WARNING'}, 'Rig has bad transforms')
        
        self.rig_was_unselectable = self.rig.hide_select
        self.rig_was_hidden = self.rig.hide_get()
        set_active_object(self.rig)
        
        if self.rig.data.library:
            self.report({'INFO'}, f"{self.rig} is linked from another scene, further validation cancelled")
            return self.complete_validation()
        
        root_bone_name = self.get_root_bone(self.rig, scene)
        if root_bone_name is None:
            self.report({'WARNING'}, 'Multiple root bones in armature. Export will fail. Ensure only one bone in the armature has no parent (or set additional root bones as non-deform bones)')
            scene_nwo.multiple_root_bones = True
            return self.complete_validation()
        else:
            scene_nwo.multiple_root_bones = False
        
        if self.validate_root_rot(self.rig, root_bone_name, scene):
            scene_nwo.invalid_root_bone = False
        else:
            self.report({'WARNING'}, f'Root bone [{root_bone_name}] has non-standard transforms. This may cause issues at export')
            scene_nwo.invalid_root_bone = True
            
        if self.needs_pose_bones(scene_nwo):
            scene_nwo.needs_pose_bones = True
            self.report({'WARNING'}, 'Found pose overlay animations, but this rig has no aim bones')
        else:
            scene_nwo.needs_pose_bones = False
            
        if scene_nwo.node_usage_pedestal and scene_nwo.node_usage_pose_blend_pitch and scene_nwo.node_usage_pose_blend_yaw:
            if self.validate_pose_bones_transforms(scene_nwo):
                scene_nwo.pose_bones_bad_transforms = False
            else:
                self.report({'WARNING'}, f"{scene_nwo.node_usage_pose_blend_pitch} & {scene_nwo.node_usage_pose_blend_yaw} bones have bad transforms. Pose overlays will not export correctly")
                scene_nwo.pose_bones_bad_transforms = True
            
        if self.too_many_bones(self.rig):
            scene_nwo.too_many_bones = True
            self.report({'WARNING'}, "Rig has more than 253 bones")
        else:
            scene_nwo.too_many_bones = False
            
        if self.bone_names_too_long():
            scene_nwo.bone_names_too_long = True
            self.report({'WARNING'}, "Rig has bone names that exceed 31 characters. These names will be cut to 31 chars at export")
        else:
            scene_nwo.bone_names_too_long = False
            
        if not (scene_nwo.multiple_root_bones or
                scene_nwo.invalid_root_bone or
                scene_nwo.needs_pose_bones or
                scene_nwo.armature_bad_transforms or
                scene_nwo.armature_has_parent or
                scene_nwo.too_many_bones or
                scene_nwo.bone_names_too_long or
                scene_nwo.pose_bones_bad_transforms):
            self.report({'INFO'}, self.valid_message())
        
        return self.complete_validation()

class NWO_FixPoseBones(Operator):
    bl_idname = 'nwo.fix_pose_bones'
    bl_label = ''
    bl_description = 'Fixes the pose bone transform by making them match the pedestal bone'
    bl_options = {'UNDO'}
    
    def execute(self, context):
        rig = get_rig(context)
        self.old_mode = context.mode
        self.old_active = context.object
        set_object_mode(context)
        set_active_object(rig)
        scene_nwo = context.scene.nwo
        if not scene_nwo.node_usage_pedestal:
            self.report({'WARNING'}, "Cannot fix as pedestal bone is not set in the Asset Editor panel")
            return {'CANCELLED'}
        if not scene_nwo.node_usage_pose_blend_pitch:
            self.report({'WARNING'}, "Cannot fix as pitch bone is not set in the Asset Editor panel")
            return {'CANCELLED'}
        if not scene_nwo.node_usage_pose_blend_yaw:
            self.report({'WARNING'}, "Cannot fix as yaw bone is not set in the Asset Editor panel")
            return {'CANCELLED'} 
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        edit_bones = rig.data.edit_bones
        edit_pedestal_matrix = edit_bones.get(scene_nwo.node_usage_pedestal).matrix
        edit_bones.get(scene_nwo.node_usage_pose_blend_pitch).matrix = edit_pedestal_matrix
        edit_bones.get(scene_nwo.node_usage_pose_blend_yaw).matrix = edit_pedestal_matrix
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        if self.old_active:
            set_active_object(self.old_active)
        if self.old_mode:
            if self.old_mode == 'POSE':
                bpy.ops.object.mode_set(mode='POSE', toggle=False)
            elif self.old_mode.startswith('EDIT'):
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        scene_nwo.pose_bones_bad_transforms = False
        return {'FINISHED'} 
        
        

class NWO_FixRootBone(Operator):
    bl_idname = 'nwo.fix_root_bone'
    bl_label = ''
    bl_description = 'Sets the root bone to have transforms expected by Halo'
    bl_options = {'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        arm = get_rig(context)
        root_bones = [b for b in arm.data.bones if b.use_deform and not b.parent]
        if len(root_bones) > 1:
            return {'CANCELLED'}
        root_bone_name = root_bones[0].name
        self.old_mode = context.mode
        self.old_active = context.object
        set_object_mode(context)
        set_active_object(arm)
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        edit_root = arm.data.edit_bones.get(root_bone_name)
        match scene.nwo.forward_direction:
            case 'x':
                edit_root.tail[0] = 0
                edit_root.tail[1] = 1
                edit_root.tail[2] = 0
            case 'x-':
                edit_root.tail[0] = 0
                edit_root.tail[1] = -1
                edit_root.tail[2] = 0
            case 'y':
                edit_root.tail[0] = -1
                edit_root.tail[1] = 0
                edit_root.tail[2] = 0
            case 'y-':
                edit_root.tail[0] = 1
                edit_root.tail[1] = 0
                edit_root.tail[2] = 0
                
        edit_root.head[0] = 0
        edit_root.head[1] = 0
        edit_root.head[2] = 0
        edit_root.roll = 0
        
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
        if self.old_active:
            set_active_object(self.old_active)
        if self.old_mode:
            if self.old_mode == 'POSE':
                bpy.ops.object.mode_set(mode='POSE', toggle=False)
            elif self.old_mode.startswith('EDIT'):
                bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        scene.nwo.invalid_root_bone = False
        return {'FINISHED'}
    
class NWO_FixArmatureTransforms(Operator):
    bl_idname = 'nwo.fix_armature_transforms'
    bl_label = ''
    bl_description = 'Sets the model armature to a location, scale, and rotation of 0,0,0'
    bl_options = {'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        obs = export_objects()
        rigs = [ob for ob in obs if ob.type == 'ARMATURE']
        if not rigs:
            return {'CANCELLED'}
        elif len(rigs) > 1:
            if scene.nwo.parent_rig and scene.nwo.parent_rig.type == 'ARMATURE':
                arm = scene.nwo.parent_rig
            else:
                return {'CANCELLED'}
        arm = rigs[0]
        
        arm.matrix_world = Matrix(((1.0, 0.0, 0.0, 0.0),
                                    (0.0, 1.0, 0.0, 0.0),
                                    (0.0, 0.0, 1.0, 0.0),
                                    (0.0, 0.0, 0.0, 1.0)))
        scene.nwo.armature_bad_transforms = False
        return {'FINISHED'}
    
class NWO_AddPedestalControl(Operator):
    bl_label = "Add Pedestal Control"
    bl_idname = "nwo.add_pedestal_control"
    bl_description = "Adds a control bone and custom shape to the armature pedestal bone"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.main_armature
    
    def new_control_bone(self, arm, pedestal_name, bone_name, shape_ob):
        new_edit = arm.data.edit_bones.new(bone_name)
        new_edit.tail[1] = 1
        name = new_edit.name
        bpy.ops.object.mode_set(mode="POSE", toggle=False)
        new_bone = arm.data.bones.get(name)
        new_pose = arm.pose.bones.get(name)
        new_bone.use_deform = False
        new_pose.custom_shape = shape_ob
        
        # Constraints for the pedestal bone
        pose_control = arm.pose.bones.get(pedestal_name)
        cons = pose_control.constraints
        copy_rotation = cons.new('COPY_TRANSFORMS')
        copy_rotation.target = arm
        copy_rotation.subtarget = name
        copy_rotation.target_space = 'LOCAL_OWNER_ORIENT'
        copy_rotation.owner_space = 'LOCAL'
        
        return name
    
    def execute(self, context):
        scene_nwo = context.scene.nwo
        arm = scene_nwo.main_armature
        bones = arm.data.bones
        for b in bones:
            if b.use_deform and not b.parent:
                pedestal_bone_name = b.name
                break
        else:
            self.report({'WARNING'}, 'No root bone found')
            return {'FINISHED'}
            
        if scene_nwo.control_pedestal:
            self.report({'INFO'}, "Pedestal control already in place")
            return {'CANCELLED'}
        else:
            bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
            existing_obs = context.view_layer.objects[:]
            resources_zip = os.path.join(addon_root(), "resources.zip")
            control_bone_path = os.path.join('rigs', 'shape_pedestal_control.glb')
            full_path = os.path.join(addon_root(), 'resources', control_bone_path)
            if os.path.exists(full_path):
                import_gltf(full_path)
            elif os.path.exists(resources_zip):
                file = extract_from_resources(control_bone_path)
                if os.path.exists(file):
                    import_gltf(file)
                    os.remove(file)
            else:
                self.report({'ERROR'}, 'Failed to extract control shape')
                return {'FINISHED'}
                
            bone_shape = [ob for ob in context.view_layer.objects if ob not in existing_obs][0]
            bone_shape.select_set(False)
            bone_shape.nwo.export_this = False
            arm.select_set(True)
            set_active_object(arm)
            bpy.ops.object.mode_set(mode="EDIT", toggle=False)
            scene_nwo.control_pedestal = self.new_control_bone(arm, pedestal_bone_name, 'c_pedestal', bone_shape)
            unlink(bone_shape)
            
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)
        return {'FINISHED'}
    
class NWO_AddAimAnimation(Operator):
    bl_idname = 'nwo.add_aim_animation'
    bl_label = 'Aim Animation'
    bl_description = 'Animates the aim bones (or aim control if it exists) based on the chosen option'
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = context.scene.nwo
        arm = scene_nwo.main_armature
        if not arm: return False
        return context.object and context.object == arm and scene_nwo.node_usage_pose_blend_yaw and scene_nwo.node_usage_pose_blend_pitch
    
    aim_animation: EnumProperty(
        name='Animation',
        items=[
            ("steering_yaw", "Steering (Yaw only)", "Uses the yaw bone only. Steers left and right\nFrames:\nrest\nleft\nmiddle\nright"),
            ("steering_full", "Steering (Yaw & Pitch)", "Animates the yaw and pitch bones from left to right\nFrames:\nrest\nleft up\nleft\left down\nmiddle up\nmiddle\nmiddle down\nright up\nright\nright down"),
            ("aiming_360", "Aiming (360)", "Aiming for a turret that can rotate 360 degrees. Uses the yaw bone initially, then the pitch (90 degrees down then up)\nFrames:\nrest\nyaw anti-clockwise 360 for 7 frames\nrest\npitch down\npitch up"),
            ]
        )
    
    max_yaw: bpy.props.FloatProperty(
        name='Max Steering Yaw',
        subtype='ANGLE',
        default=radians(45),
        min=radians(1),
        max=radians(90),
    )
    
    max_pitch: bpy.props.FloatProperty(
        name='Max Steering Pitch',
        subtype='ANGLE',
        default=radians(45),
        min=radians(1),
        max=radians(90),
    )
    
    def setup_steering_yaw(self, yaw, aim, start):
        if aim is None:
            yaw.matrix_basis = Matrix()
            yaw.rotation_mode = 'XYZ'
            yaw.keyframe_insert(data_path='rotation_euler', frame=start)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            yaw.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 3)
        else:
            aim.matrix_basis = Matrix()
            aim.rotation_mode = 'XYZ'
            aim.keyframe_insert(data_path='rotation_euler', frame=start)
            aim.rotation_euler = [0, 0, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            aim.rotation_euler = [0, 0, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            aim.rotation_euler = [0, 0, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            
        return start + 3
        
    def setup_steering_full(self, yaw, pitch, aim, start):
        if aim is None:
            yaw.matrix_basis = Matrix()
            pitch.matrix_basis = Matrix()
            yaw.rotation_mode = 'XYZ'
            pitch.rotation_mode = 'XYZ'
            yaw.keyframe_insert(data_path='rotation_euler', frame=start)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 9)
        else:
            aim.matrix_basis = Matrix()
            aim.rotation_mode = 'XYZ'
            aim.keyframe_insert(data_path='rotation_euler', frame=start)
            aim.rotation_euler = [0, -self.max_pitch, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            aim.rotation_euler = [0, 0, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            aim.rotation_euler = [0, self.max_pitch, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            aim.rotation_euler = [0, -self.max_pitch, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            aim.rotation_euler = [0, 0, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            aim.rotation_euler = [0, self.max_pitch, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            aim.rotation_euler = [0, -self.max_pitch, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            aim.rotation_euler = [0, 0, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            aim.rotation_euler = [0, self.max_pitch, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 9)
        return start + 9
    
    def setup_aiming_360(self, yaw, pitch, aim, start):
        if aim is None:
            yaw.matrix_basis = Matrix()
            pitch.matrix_basis = Matrix()
            yaw.rotation_mode = 'XYZ'
            pitch.rotation_mode = 'XYZ'
            yaw.keyframe_insert(data_path='rotation_euler', frame=start)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start)
            yaw.rotation_euler = [0, 0, radians(45)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            yaw.rotation_euler = [0, 0, radians(90)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            yaw.rotation_euler = [0, 0, radians(135)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            yaw.rotation_euler = [0, 0, radians(180)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            yaw.rotation_euler = [0, 0, radians(225)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            yaw.rotation_euler = [0, 0, radians(270)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            yaw.rotation_euler = [0, 0, radians(315)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            yaw.rotation_euler = [0, 0, radians(360)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            yaw.rotation_euler = [0, 0, radians(360)]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            yaw.rotation_euler = [0, 0, radians(360)]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 10)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 10)
        else:
            aim.matrix_basis = Matrix()
            aim.rotation_mode = 'XYZ'
            aim.keyframe_insert(data_path='rotation_euler', frame=start)
            aim.rotation_euler = [0, 0, radians(45)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            aim.rotation_euler = [0, 0, radians(90)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            aim.rotation_euler = [0, 0, radians(135)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            aim.rotation_euler = [0, 0, radians(180)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            aim.rotation_euler = [0, 0, radians(225)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            aim.rotation_euler = [0, 0, radians(270)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            aim.rotation_euler = [0, 0, radians(315)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            aim.rotation_euler = [0, 0, radians(360)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            aim.rotation_euler = [0, self.max_pitch, radians(360)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            aim.rotation_euler = [0, -self.max_pitch, radians(360)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 10)
            
        return start + 10
    
    def execute(self, context):
        scene_nwo = context.scene.nwo
        arm = scene_nwo.main_armature
        yaw_name = scene_nwo.node_usage_pose_blend_yaw
        pitch_name = scene_nwo.node_usage_pose_blend_pitch
        aim_name = scene_nwo.control_aim
        yaw = arm.pose.bones.get(yaw_name)
        pitch = arm.pose.bones.get(pitch_name)
        if aim_name:
            aim = arm.pose.bones.get(aim_name)
        else:
            aim = None
        start = int(arm.animation_data.action.frame_start)
        scene = context.scene
        current = int(scene.frame_current)
        already_in_pose_mode = False
        if context.mode == 'POSE':
            already_in_pose_mode = True
        else:
            bpy.ops.object.posemode_toggle()
            
        scene.frame_current = start
        action = arm.animation_data.action
        fcurves_for_destruction = set()
        for fc in action.fcurves:
            if fc.data_path.startswith(f'pose.bones["{pitch_name}"].') or fc.data_path.startswith(f'pose.bones["{yaw_name}"].') or fc.data_path.startswith(f'pose.bones["{aim_name}"].'):
                fcurves_for_destruction.add(fc)
        [action.fcurves.remove(fc) for fc in fcurves_for_destruction]
        
        if self.aim_animation == 'steering_yaw':
            action.frame_end = self.setup_steering_yaw(yaw, aim, start)
        elif self.aim_animation == 'steering_full':
            action.frame_end = self.setup_steering_full(yaw, pitch, aim, start)
        elif self.aim_animation == 'aiming_360':
            action.frame_end = self.setup_aiming_360(yaw, pitch, aim, start)
        if not already_in_pose_mode:
            bpy.ops.object.posemode_toggle()
            
        scene.frame_current = current
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'aim_animation', text='Animation')
        if self.aim_animation.startswith('steering'):
            layout.prop(self, 'max_yaw', text='Max Yaw Angle')
        if self.aim_animation == 'steering_full' or self.aim_animation == 'aiming_360':
            layout.prop(self, 'max_pitch', text='Max Pitch Angle')
        

class NWO_ImportLegacyAnimation(Operator):
    bl_label = "Import"
    bl_idname = "nwo.import_legacy_animation"
    bl_description = "Imports legacy Halo animations. Will import all animations selected. Supported file extensions: JMM, JMA, JMT, JMZ, JMV, JMW, JMO, JMR, JMRX"
    
    @classmethod
    def poll(cls, context):
        return blender_toolset_installed()
    
    filter_glob: StringProperty(
        default="*.jmm;*.jma;*.jmt;*.jmz;*.jmv;*.jmw;*.jmo;*.jmr;*.jmrx",
        options={"HIDDEN"},
    )

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    directory: StringProperty(
        name='Directory',
        subtype='DIR_PATH'
    )
    
    def execute(self, context):
        old_active = None
        if context.object:
            old_active = context.object
        scene_nwo = context.scene.nwo
        if scene_nwo.main_armature:
            arm = scene_nwo.main_armature
        else:
            arms = [ob for ob in bpy.context.view_layer.objects if ob.type == 'ARMATURE']
            if arms:
                arm = arms[0]
            else:
                arm_data = bpy.data.armatures.new('Armature')
                arm = bpy.data.objects.new('Armature', arm_data)
                context.scene.collection.objects.link(arm)
            
        arm.hide_set(False)
        arm.hide_select = False
        set_active_object(arm)
        from io_scene_foundry.tools.importer import import_legacy_animations
        filepaths = [self.directory + f.name for f in self.files]
        import_legacy_animations(context, filepaths, self.report)
        if old_active is not None:
            set_active_object(old_active)
            
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

class NWO_OpenImageEditor(Operator):
    bl_label = "Open in Image Editor"
    bl_idname = "nwo.open_image_editor"
    bl_description = "Opens the current image in the image editor specified in Blender Preferences"

    @classmethod
    def poll(self, context):
        ob = context.object
        if not ob:
            return
        mat = ob.active_material
        if not mat:
            return
        image = mat.nwo.active_image
        if not image:
            return
        path = image.filepath
        if not path:
            return
        return os.path.exists(image.filepath_from_user())

    def execute(self, context):
        try:
            bpy.ops.image.external_edit(filepath=context.object.active_material.nwo.active_image.filepath_from_user())
        except:
            self.report({'ERROR'}, 'Image editor could not be launched, ensure that the path in User Preferences > File is valid, and Blender has rights to launch it')
            return {'CANCELLED'}
        return {'FINISHED'}

def draw_foundry_nodes_toolbar(self, context):
    #if context.region.alignment == 'RIGHT':
    foundry_nodes_toolbar(self.layout, context)

def foundry_nodes_toolbar(layout, context):
    #layout.label(text=" ")
    row = layout.row()
    nwo_scene = context.scene.nwo
    icons_only = context.preferences.addons["io_scene_foundry"].preferences.toolbar_icons_only
    row.scale_x = 1
    box = row.box()
    box.scale_x = 0.3
    box.label(text="")
    if not nwo_scene.toolbar_expanded:
        sub_foundry = row.row(align=True)
        sub_foundry.prop(nwo_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
    if nwo_scene.toolbar_expanded:
        error = validate_ek()
        if error is not None:
            sub_error = row.row()
            sub_error.label(text=error, icon="ERROR")
            sub_foundry = row.row(align=True)
            sub_foundry.prop(nwo_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
            return

        sub0 = row.row(align=True)
        if context.scene.nwo.shader_sync_active:
            sub0.enabled = False
        else:
            sub0.enabled = True
        sub0.prop(nwo_scene, "material_sync_rate", text="Sync Rate")
        sub1 = row.row(align=True)
        if context.scene.nwo.shader_sync_active:
            sub1.operator("nwo.material_sync_end", text="Halo Material Sync", icon="PAUSE", depress=True)
        else:
            sub1.operator("nwo.material_sync_start", text="Halo Material Sync", icon="PLAY")
        # sub0.prop(nwo_scene, "shader_sync_active", text="" if icons_only else "Halo Material Sync", icon_value=get_icon_id("material_exporter"))

def draw_foundry_toolbar(self, context):
    #if context.region.alignment == 'RIGHT':
    foundry_toolbar(self.layout, context)

def foundry_toolbar(layout, context):
    #layout.label(text=" ")
    row = layout.row()
    nwo_scene = context.scene.nwo
    if nwo_scene.storage_only:
        row.label(text='Scene is used by Foundry for object storage', icon_value=get_icon_id('foundry'))
        return
    icons_only = context.preferences.addons["io_scene_foundry"].preferences.toolbar_icons_only
    row.scale_x = 1
    box = row.box()
    box.scale_x = 0.3
    box.label(text="")
    if not nwo_scene.toolbar_expanded:
        sub_foundry = row.row(align=True)
        sub_foundry.prop(nwo_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
    if nwo_scene.toolbar_expanded:
        error = validate_ek()
        if error is not None:
            sub_error = row.row()
            sub_error.label(text=error, icon="ERROR")
            sub_foundry = row.row(align=True)
            sub_foundry.prop(nwo_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
            return

        sub0 = row.row(align=True)
        sub0.operator(
            "nwo.export_quick",
            text="" if icons_only else "Export",
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
    NWO_RegionAdd,
    NWO_FaceRegionAdd,
    NWO_RegionRemove,
    NWO_RegionMove,
    NWO_RegionAssignSingle,
    NWO_FaceRegionAssignSingle,
    NWO_RegionAssign,
    NWO_RegionSelect,
    NWO_RegionRename,
    NWO_RegionHide,
    NWO_RegionHideSelect,
    NWO_PermutationAdd,
    NWO_PermutationRemove,
    NWO_PermutationMove,
    NWO_PermutationAssignSingle,
    NWO_PermutationAssign,
    NWO_PermutationSelect,
    NWO_PermutationRename,
    NWO_PermutationHide,
    NWO_PermutationHideSelect,
    NWO_SeamAssignSingle,
    NWO_ImportLegacyAnimation,
    NWO_OpenImageEditor,
    NWO_MaterialGirl,
    NWO_OpenFoundationTag,
    NWO_ExportBitmapsSingle,
    NWO_GetModelVariants,
    NWO_GetTagsList,
    NWO_TagExplore,
    NWO_ProxyInstanceCancel,
    NWO_ProxyInstanceDelete,
    NWO_ProxyInstanceEdit,
    NWO_ProxyInstanceNew,
    NWO_SelectArmature,
    NWO_HotkeyDescription,
    NWO_OpenURL,
    NWO_OT_PanelExpand,
    NWO_OT_PanelSet,
    NWO_OT_PanelUnpin,
    NWO_FoundryPanelProps,
    NWO_FoundryPanelPopover,
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
    NWO_CollectionManager_CreateMove,
    NWO_CollectionManager_Create,
    NWO_AutoSeam,
    NWO_ShaderFinder,
    NWO_ShaderFinder_FindSingle,
    NWO_ShaderFinder_Find,
    NWO_HaloShaderFinderPropertiesGroup,
    NWO_ArmatureCreator_Create,
    NWO_ListMaterialShaders,
    NWO_Shader_BuildSingle,
    NWO_ShaderPropertiesGroup,
    NWO_ScaleModels_Add,
    NWO_JoinHalo,
    NWO_ShaderFarmPopover,
    NWO_FarmShaders,
    NWO_MaterialSyncStart,
    NWO_MaterialSyncEnd,
    NWO_ProjectChooser,
    NWO_ProjectChooserMenuDisallowNew,
    NWO_ProjectChooserMenu,
    NWO_DuplicateMaterial,
    NWO_AddPoseBones,
    NWO_ValidateRig,
    NWO_FixRootBone,
    NWO_FixPoseBones,
    NWO_FixArmatureTransforms,
    NWO_AddPedestalControl,
    NWO_AddAimAnimation,
    NWO_MeshToMarker,
    NWO_StompMaterials,
    NWO_Import,
    NWO_SetDefaultSky,
    NWO_SetSky,
    NWO_NewSky,
    NWO_BSPContextMenu,
    NWO_BSPInfo,
    NWO_BSPSetLightmapRes,
    NWO_ShaderToNodes,
)

def register():
    for clshalo in classeshalo:
        bpy.utils.register_class(clshalo)

    bpy.types.VIEW3D_HT_tool_header.append(draw_foundry_toolbar)
    bpy.types.NODE_HT_header.append(draw_foundry_nodes_toolbar)
    bpy.types.VIEW3D_MT_mesh_add.append(add_halo_scale_model_button)
    bpy.types.VIEW3D_MT_light_add.append(add_halo_light_button)
    bpy.types.VIEW3D_MT_armature_add.append(add_halo_armature_buttons)
    bpy.types.OUTLINER_HT_header.append(create_halo_collection)
    bpy.types.VIEW3D_MT_object.append(add_halo_join)
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
    bpy.types.Scene.nwo_shader_build = PointerProperty(
        type=NWO_ShaderPropertiesGroup,
        name="Halo Shader Export",
        description="",
    )

def unregister():
    bpy.types.VIEW3D_HT_tool_header.remove(draw_foundry_toolbar)
    bpy.types.NODE_HT_header.remove(draw_foundry_nodes_toolbar)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_halo_scale_model_button)
    bpy.types.VIEW3D_MT_light_add.remove(add_halo_light_button)
    bpy.types.VIEW3D_MT_armature_add.remove(add_halo_armature_buttons)
    bpy.types.VIEW3D_MT_object.remove(add_halo_join)
    bpy.types.OUTLINER_HT_header.remove(create_halo_collection)
    del bpy.types.Scene.nwo_halo_launcher
    del bpy.types.Scene.nwo_shader_finder
    del bpy.types.Scene.nwo_export
    del bpy.types.Scene.nwo_shader_build
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)


if __name__ == "__main__":
    register()

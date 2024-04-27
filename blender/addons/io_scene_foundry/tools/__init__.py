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

import os
from pathlib import Path
import bpy
import webbrowser
import multiprocessing

from bpy.types import Context, OperatorProperties, Panel, Operator, PropertyGroup

from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    EnumProperty,
    PointerProperty,
)
from io_scene_foundry.tools.asset_creator import NWO_OT_NewAsset
from io_scene_foundry.tools.animation.rename_importer import NWO_OT_RenameImporter
from io_scene_foundry.tools.animation.fcurve_transfer import NWO_OT_FcurveTransfer
from io_scene_foundry.tools.animation.composites import NWO_OT_AnimationBlendAxisAdd, NWO_OT_AnimationBlendAxisMove, NWO_OT_AnimationBlendAxisRemove, NWO_OT_AnimationCompositeAdd, NWO_OT_AnimationCompositeMove, NWO_OT_AnimationCompositeRemove, NWO_OT_AnimationDeadZoneAdd, NWO_OT_AnimationDeadZoneMove, NWO_OT_AnimationDeadZoneRemove, NWO_OT_AnimationLeafAdd, NWO_OT_AnimationLeafMove, NWO_OT_AnimationLeafRemove, NWO_OT_AnimationPhaseSetAdd, NWO_OT_AnimationPhaseSetMove, NWO_OT_AnimationPhaseSetRemove, NWO_UL_AnimationBlendAxis, NWO_UL_AnimationComposites, NWO_UL_AnimationDeadZone, NWO_UL_AnimationLeaf, NWO_UL_AnimationPhaseSet
from io_scene_foundry.tools.animation.copy import NWO_OT_AnimationCopyAdd, NWO_OT_AnimationCopyMove, NWO_OT_AnimationCopyRemove, NWO_UL_AnimationCopies
from io_scene_foundry.tools.scenario.lightmap import NWO_OT_Lightmap
from io_scene_foundry.tools.scenario.zone_sets import NWO_OT_RemoveExistingZoneSets
from io_scene_foundry.tools.tag_templates import NWO_OT_LoadTemplate
from io_scene_foundry.tools.cubemap import NWO_OT_Cubemap
from io_scene_foundry.managed_blam import Tag
from io_scene_foundry.tools.scale_models import NWO_OT_AddScaleModel
from io_scene_foundry.tools.animation.automate_pose_overlay import NWO_AddAimAnimation
from io_scene_foundry.tools.rigging.convert_to_halo_rig import NWO_OT_ConvertToHaloRig
from io_scene_foundry.tools.rigging.create_rig import NWO_OT_AddRig
from io_scene_foundry.tools.rigging.validation import NWO_AddPedestalControl, NWO_AddPoseBones, NWO_FixArmatureTransforms, NWO_FixPoseBones, NWO_FixRootBone, NWO_ValidateRig
from io_scene_foundry.tools.scene_scaler import NWO_ScaleScene
from io_scene_foundry.utils.nwo_materials import special_materials, convention_materials
from io_scene_foundry.icons import get_icon_id, get_icon_id_in_directory
from io_scene_foundry.tools.append_foundry_materials import NWO_AppendFoundryMaterials
from io_scene_foundry.tools.auto_seam import NWO_AutoSeam
from io_scene_foundry.tools.clear_duplicate_materials import NWO_ClearShaderPaths, NWO_StompMaterials
from io_scene_foundry.tools.export_bitmaps import NWO_ExportBitmapsSingle
from io_scene_foundry.tools.importer import NWO_Import, NWO_OT_ConvertScene
from io_scene_foundry.tools.material_sync import NWO_MaterialSyncEnd, NWO_MaterialSyncStart
from io_scene_foundry.tools.mesh_to_marker import NWO_MeshToMarker
from io_scene_foundry.tools.set_sky_permutation_index import NWO_NewSky, NWO_SetDefaultSky, NWO_SetSky
from io_scene_foundry.tools.sets_manager import NWO_BSPContextMenu, NWO_BSPInfo, NWO_BSPSetLightmapRes, NWO_FaceRegionAdd, NWO_FaceRegionAssignSingle, NWO_OT_HideObjectType, NWO_PermutationAdd, NWO_PermutationAssign, NWO_PermutationAssignSingle, NWO_PermutationHide, NWO_PermutationHideSelect, NWO_PermutationMove, NWO_PermutationRemove, NWO_PermutationRename, NWO_PermutationSelect, NWO_RegionAdd, NWO_RegionAssign, NWO_RegionAssignSingle, NWO_RegionHide, NWO_RegionHideSelect, NWO_RegionMove, NWO_RegionRemove, NWO_RegionRename, NWO_RegionSelect, NWO_SeamAssignSingle, NWO_UpdateSets
from io_scene_foundry.tools.shader_farm import NWO_FarmShaders
from io_scene_foundry.tools.shader_finder import NWO_ShaderFinder_Find, NWO_ShaderFinder_FindSingle
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
    amf_addon_installed,
    blender_toolset_installed,
    clean_tag_path,
    deselect_all_objects,
    dot_partition,
    foundry_update_check,
    get_arm_count,
    get_asset_animation_graph,
    get_asset_collision_model,
    get_asset_info,
    get_asset_physics_model,
    get_asset_render_model,
    get_asset_tag,
    get_asset_tags,
    get_data_path,
    get_export_scale,
    get_halo_material_count,
    get_marker_display,
    get_mesh_display,
    get_prefs,
    get_sky_perm,
    get_tags_path,
    has_collision_type,
    has_face_props,
    has_mesh_props,
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
    project_game_icon,
    project_icon,
    protected_material_name,
    recursive_image_search,
    relative_path,
    set_active_object,
    true_permutation,
    true_region,
    valid_nwo_asset,
    poll_ui,
    validate_ek,
)
from bpy_extras.object_utils import AddObjectHelper

is_blender_startup = True

FOUNDRY_DOCS = r"https://c20.reclaimers.net/general/community-tools/foundry"
FOUNDRY_GITHUB = r"https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit"

BLENDER_TOOLSET = r"https://github.com/General-101/Halo-Asset-Blender-Development-Toolset/releases"
AMF_ADDON = r"https://github.com/Gravemind2401/Reclaimer/blob/master/Reclaimer.Blam/Resources/Blender%20AMF2.py"
RECLAIMER = r"https://github.com/Gravemind2401/Reclaimer/releases"
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
    "animation_manager",
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
    bl_label = "Foundry"
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
                self.draw_expandable_box(box.box(), context.scene.nwo, "face_properties", ob=ob)

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
            elif p == "animation_manager":
                if not nwo.is_valid_asset or not poll_ui(('model', 'animation', 'camera_track_set')):
                    continue
            elif p in ("object_properties", "material_properties", 'sets_manager'):
                if not nwo.is_valid_asset or nwo.asset_type in ('animation', 'camera_track_set'):
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
        box = self.box
        mb_active = managed_blam_active()
        nwo = self.scene.nwo
        scene = self.scene

        col = box.column()
        row = col.row()
        col.scale_y = 1.5

        if not nwo_globals.clr_installed:
            col.operator("managed_blam.init", text="Install Tag API")
            col.separator()
        col.operator('nwo.scale_scene', text='Transform Scene', icon='MOD_LENGTH')
        col = box.column()
        col.scale_y = 1.25
        col.separator()
        row = col.row()
        row.scale_y = 1.1
        row.prop(scene.nwo, 'scale', text='Scale', expand=True)
        row = col.row()
        row.scale_y = 1.1
        row.prop(scene.nwo, 'scale_display', text='Scale Display', expand=True)
        if scene.nwo.scale_display == 'halo' and scene.unit_settings.length_unit != 'METERS':
            row = col.row()
            row.label(text='World Units only accurate when Unit Length is Meters', icon='ERROR')
        row = col.row()
        row.prop(nwo, "forward_direction", text="Scene Forward", expand=True)
        row = col.row()
        row.prop(nwo, "rotate_markers")

    def draw_asset_editor(self):
        box = self.box
        nwo = self.scene.nwo
        col = box.column()
        row = col.row()
        row.scale_y = 1.5
        row.prop(nwo, "asset_type", text="")
        col.separator()
        asset_name = nwo.asset_name
        
        row = col.row()
        row.scale_y = 1.5
        if asset_name:
            row.operator("nwo.new_asset", text=f"Copy {asset_name}", icon_value=get_icon_id("halo_asset")) 
            row.operator("nwo.clear_asset", text="", icon='X')
            
        else:
            row.scale_y = 1.5
            row.operator("nwo.new_asset", text="New Asset", icon_value=get_icon_id("halo_asset"))
            return
        
        if nwo.asset_type == 'model':
            self.draw_expandable_box(self.box.box(), nwo, 'output_tags')
            self.draw_expandable_box(self.box.box(), nwo, 'model')
            # self.draw_expandable_box(self.box.box(), nwo, 'model_overrides')
            self.draw_rig_ui(self.context, nwo)
            
        if self.h4 and poll_ui(('model', 'sky')):
            self.draw_expandable_box(self.box.box(), nwo, 'lighting')
        
        if nwo.asset_type == "animation":
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
            self.draw_rig_ui(self.context, nwo)
            
        elif nwo.asset_type == "scenario":
            self.draw_expandable_box(self.box.box(), nwo, 'scenario')
            self.draw_expandable_box(self.box.box(), nwo, 'zone_sets')
            self.draw_expandable_box(self.box.box(), nwo, 'lighting')
            
        elif nwo.asset_type == 'camera_track_set':
            box = self.box.box()
            col = box.column()
            col.operator('nwo.import', text="Import Camera Track", icon='IMPORT').scope = 'camera_track'
            col.prop(nwo, 'camera_track_camera', text="Camera")
    
    def draw_expandable_box(self, box: bpy.types.UILayout, nwo, name, panel_display_name='', ob=None, material=None):
        if not panel_display_name:
            panel_display_name = f"{name.replace('_', ' ').title()}"
        panel_expanded = getattr(nwo, f"{name}_expanded")
        row_header = box.row(align=True)
        row_header.alignment = 'LEFT'
        row_header.operator(
            "nwo.panel_expand",
            text=panel_display_name,
            icon="TRIA_DOWN" if panel_expanded else "TRIA_RIGHT",
            emboss=False,
        ).panel_str = name

        if panel_expanded:
            draw_panel = getattr(self, f"draw_{name}")
            if callable(draw_panel):
                if ob:
                    draw_panel(box, ob)
                elif material:
                    draw_panel(box, material)
                else:
                    draw_panel(box, nwo)
                    
                return panel_expanded
            
        return False
    
    def draw_scenario(self, box: bpy.types.UILayout, nwo):
        tag_path = get_asset_tag(".scenario")
        if tag_path:
            box.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Scenario Tag").tag_path = tag_path
        col = box.column()
        col.use_property_split = True
        col.prop(nwo, "scenario_type")
        col.separator()
        col.operator("nwo.new_sky", text="Add New Sky to Scenario", icon_value=get_icon_id('sky'))
        
    def draw_lighting(self, box: bpy.types.UILayout, nwo):
        box.use_property_split = True
        scene_nwo_export = self.scene.nwo_export
        _, asset_name = get_asset_info()
        if self.asset_type == 'scenario':
            lighting_name = "Light Scenario"
        else:
            lighting_name = "Light Model"
        if self.asset_type == "scenario":
            if self.h4:
                box.prop(scene_nwo_export, "lightmap_quality_h4")
            else:
                box.prop(scene_nwo_export, "lightmap_quality")
            if not scene_nwo_export.lightmap_all_bsps:
                box.prop(scene_nwo_export, "lightmap_specific_bsp")
            box.prop(scene_nwo_export, "lightmap_all_bsps")
            if not self.h4:
                box.prop(scene_nwo_export, "lightmap_threads")
                    
        box.operator('nwo.lightmap', text=lighting_name, icon='LIGHT_SUN')
        if self.asset_type == 'scenario':
            tag_paths = get_asset_tags(".scenario_structure_lighting_info")
            if tag_paths:
                for path in tag_paths:
                    name = path.with_suffix("").name
                    if name.startswith(asset_name):
                        name = name[len(asset_name) + 1:]
                    box.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text=f"Open {name} Lighting Tag").tag_path = str(path)
        else:
            tag_path = get_asset_tag(".scenario_structure_lighting_info")
            if tag_path:
                box.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text=f"Open Lighting Tag").tag_path = tag_path
        
    def draw_zone_sets(self, box: bpy.types.UILayout, nwo):
        row = box.row()
        rows = 4
        row.template_list(
            "NWO_UL_ZoneSets",
            "",
            nwo,
            "zone_sets",
            nwo,
            "zone_sets_active_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.zone_set_add", text="", icon="ADD")
        col.operator("nwo.zone_set_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.remove_existing_zone_sets", icon="X", text="")
        col.separator()
        col.operator("nwo.zone_set_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.zone_set_move", icon="TRIA_DOWN", text="").direction = 'down'
        if not nwo.zone_sets:
            return
        zone_set = nwo.zone_sets[nwo.zone_sets_active_index]
        box.label(text=f"Zone Set BSPs")
        if zone_set.name.lower() == "all":
            return box.label(text="All BSPs included in Zone Set")
        grid = box.grid_flow()
        grid.scale_x = 0.8
        max_index = 31 if self.h4 else 15
        bsps = [region.name for region in nwo.regions_table]
        for index, bsp in enumerate(bsps):
            if index >= max_index:
                break
            if bsp.lower() != "shared":
                grid.prop(zone_set, f"bsp_{index}", text=bsp)
        
    
    def draw_output_tags(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        if nwo.asset_type == "model":
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
            if is_corinth(self.context):
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
            if nwo.output_crate:
                self.draw_expandable_box(col.box(), nwo, 'crate')
            if nwo.output_scenery:
                self.draw_expandable_box(col.box(), nwo, 'scenery')
            if nwo.output_effect_scenery:
                self.draw_expandable_box(col.box(), nwo, 'effect_scenery')
            if nwo.output_device_control:
                self.draw_expandable_box(col.box(), nwo, 'device_control')
            if nwo.output_device_machine:
                self.draw_expandable_box(col.box(), nwo, 'device_machine')
            if nwo.output_device_terminal:
                self.draw_expandable_box(col.box(), nwo, 'device_terminal')
            if is_corinth(self.context) and nwo.output_device_dispenser:
                self.draw_expandable_box(col.box(), nwo, 'device_dispenser')
            if nwo.output_biped:
                self.draw_expandable_box(col.box(), nwo, 'biped')
            if nwo.output_creature:
                self.draw_expandable_box(col.box(), nwo, 'creature')
            if nwo.output_giant:
                self.draw_expandable_box(col.box(), nwo, 'giant')
            if nwo.output_vehicle:
                self.draw_expandable_box(col.box(), nwo, 'vehicle')
            if nwo.output_weapon:
                self.draw_expandable_box(col.box(), nwo, 'weapon')
            if nwo.output_equipment:
                self.draw_expandable_box(col.box(), nwo, 'equipment')
        
    def draw_output_tag(self, box: bpy.types.UILayout, nwo, tag_type: str):
        row = box.row(align=True)
        row.prop(nwo, f'template_{tag_type}', icon_value=get_icon_id(tag_type), text="Template")
        row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = f"template_{tag_type}"
        row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = f'template_{tag_type}'
        if valid_nwo_asset(self.context) and getattr(nwo, f'template_{tag_type}'):
            box.operator('nwo.load_template', icon='DUPLICATE').tag_type = tag_type
        tag_path = get_asset_tag(tag_type)
        if tag_path:
            box.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text=f"Open {tag_type.capitalize()} Tag").tag_path = tag_path
        
    def draw_crate(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'crate')
        
    def draw_scenery(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'scenery')
        
    def draw_crate(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'crate')
        
    def draw_effect_scenery(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag( box, nwo,'effect_scenery')
        
    def draw_device_control(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'device_control')
        
    def draw_device_machine(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'device_machine')
        
    def draw_device_terminal(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'device_terminal')
        
    def draw_device_dispenser(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'device_dispenser')
        
    def draw_biped(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'biped')
        
    def draw_creature(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'creature')
        
    def draw_giant(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'giant')
        
    def draw_vehicle(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'vehicle')
        
    def draw_weapon(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'weapon')
        
    def draw_equipment(self, box: bpy.types.UILayout, nwo):
        self.draw_output_tag(box, nwo,'equipment')
                
    def draw_model(self, box: bpy.types.UILayout, nwo):
        row = box.row(align=True)
        row.prop(nwo, 'template_model', icon_value=get_icon_id("model"), text="Template")
        row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "template_model"
        row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'template_model'
        if valid_nwo_asset(self.context) and getattr(nwo, 'template_model'):
            box.operator('nwo.load_template', icon='DUPLICATE').tag_type = 'model'
        tag_path = get_asset_tag(".model")
        if tag_path:
            row = box.row(align=True)
            row.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Model Tag").tag_path = tag_path
        self.draw_expandable_box(box.box(), nwo, 'render_model')
        self.draw_expandable_box(box.box(), nwo, 'collision_model')
        self.draw_expandable_box(box.box(), nwo, 'animation_graph')
        self.draw_expandable_box(box.box(), nwo, 'physics_model')
    
    def draw_render_model(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.prop(nwo, "render_model_from_blend")
        if nwo.render_model_from_blend:
            tag_path = get_asset_render_model()
            if tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Render Model Tag").tag_path = tag_path
        else:
            row = col.row(align=True)
            row.prop(nwo, "render_model_path", text="Render", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "render_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'render_model_path'
    
    def draw_collision_model(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.prop(nwo, "collision_model_from_blend")
        if nwo.collision_model_from_blend:
            tag_path = get_asset_collision_model()
            if tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Collision Model Tag").tag_path = tag_path
        else:
            row = col.row(align=True)
            row.prop(nwo, "collision_model_path", text="Collision", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "collision_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'collision_model_path'
    
    def draw_animation_graph(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.prop(nwo, "animation_graph_from_blend")
        if nwo.animation_graph_from_blend:
            row = col.row(align=True)
            row.use_property_split = True
            row.prop(nwo, "parent_animation_graph", text="Parent Animation Graph")
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "parent_animation_graph"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'parent_animation_graph'
            row = col.row()
            row.use_property_split = True
            row.prop(nwo, "default_animation_compression", text="Default Animation Compression")
            tag_path = get_asset_animation_graph()
            if tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Animation Graph Tag").tag_path = tag_path
            frame_events_tag_path = get_asset_tag(".frame_events_list")
            if frame_events_tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Frame Events List Tag").tag_path = frame_events_tag_path
            self.draw_expandable_box(box.box(), nwo, 'rig_usages', 'Node Usages')
            self.draw_expandable_box(box.box(), nwo, 'ik_chains', panel_display_name='IK Chains')
            self.draw_expandable_box(box.box(), nwo, 'animation_copies')
            if self.h4:
                self.draw_expandable_box(box.box(), nwo, 'animation_composites')
        else:
            row = col.row(align=True)
            row.prop(nwo, "animation_graph_path", text="Animation", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "animation_graph_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'animation_graph_path'
    
    def draw_physics_model(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.prop(nwo, "physics_model_from_blend")
        if nwo.physics_model_from_blend:
            tag_path = get_asset_physics_model()
            if tag_path:
                col.operator('nwo.open_foundation_tag', icon_value=get_icon_id('foundation'), text="Open Physics Model Tag").tag_path = tag_path
        else:
            row = col.row(align=True)
            row.prop(nwo, "physics_model_path", text="Physics", icon_value=get_icon_id("tags"))
            row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "physics_model_path"
            row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'physics_model_path'
    
    def draw_model_overrides(self, box: bpy.types.UILayout, nwo):
        asset_dir, asset_name = get_asset_info()
        self_path = str(Path(asset_dir, asset_name))
        everything_overidden = nwo.render_model_path and nwo.collision_model_path and nwo.animation_graph_path and nwo.physics_model_path
        if everything_overidden:
            box.alert = True
        col = box.column()
        row = col.row(align=True)
        if nwo.render_model_path and dot_partition(nwo.render_model_path) == self_path:
            row.alert = True
            row.label(icon='ERROR')
            
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
        if everything_overidden:
            row = col.row(align=True)
            row.label(text='All overrides specified', icon='ERROR')
            row = col.row(align=True)
            row.label(text='Everything exported from this scene will be overwritten')
            
    def draw_model_rig(self, box: bpy.types.UILayout, nwo):
        col = box.column()
        col.use_property_split = True
        col.prop(nwo, 'main_armature', icon='OUTLINER_OB_ARMATURE')
        if not nwo.main_armature: return
        col.separator()
        arm_count = get_arm_count(self.context)
        if arm_count > 1 or nwo.support_armature_a:
            col.prop(nwo, 'support_armature_a', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_a:
                col.prop_search(nwo, 'support_armature_a_parent_bone', nwo.main_armature.data, 'bones')
                col.separator()
        if arm_count > 2 or nwo.support_armature_b:
            col.prop(nwo, 'support_armature_b', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_b:
                col.prop_search(nwo, 'support_armature_b_parent_bone', nwo.main_armature.data, 'bones')
                col.separator()
        if arm_count > 3 or nwo.support_armature_c:
            col.prop(nwo, 'support_armature_c', icon='OUTLINER_OB_ARMATURE')
            if nwo.support_armature_c:
                col.prop_search(nwo, 'support_armature_c_parent_bone', nwo.main_armature.data, 'bones')
                
        #col.separator()
                
    def draw_rig_controls(self, box, nwo):
        box.use_property_split = True
        row = box.row(align=True)
        row.prop_search(nwo, 'control_pedestal', nwo.main_armature.data, 'bones')
        if not nwo.control_pedestal:
            row.operator('nwo.add_pedestal_control', text='', icon='ADD')
        row = box.row(align=True)
        row.prop_search(nwo, 'control_aim', nwo.main_armature.data, 'bones')
        if not nwo.control_aim:
            row.operator('nwo.add_pose_bones', text='', icon='ADD').skip_invoke = True
            
    def draw_rig_object_controls(self, box: bpy.types.UILayout, nwo):
        box.use_property_split = True
        row = box.row()
        row.template_list(
            "NWO_UL_ObjectControls",
            "",
            nwo,
            "object_controls",
            nwo,
            "object_controls_active_index",
        )
        row = box.row(align=True)
        row.operator('nwo.batch_add_object_controls', text='Add')
        row.operator('nwo.batch_remove_object_controls', text='Remove')
        row.operator('nwo.select_object_control', text='Select').select = True
        row.operator('nwo.select_object_control', text='Deselect').select = False
    
    def draw_rig_usages(self, box, nwo):
        box.use_property_split = True
        col = box.column()
        if not nwo.main_armature:
            return col.label(text="Set Main Armature to use")
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
        
    def draw_ik_chains(self, box, nwo):
        if not nwo.ik_chains:
            box.operator("nwo.add_ik_chain", text="Add Game IK Chain", icon="CON_SPLINEIK")
            return
        row = box.row()
        row.template_list(
            "NWO_UL_IKChain",
            "",
            nwo,
            "ik_chains",
            nwo,
            "ik_chains_active_index",
        )
        col = row.column(align=True)
        col.operator("nwo.add_ik_chain", text="", icon="ADD")
        col.operator("nwo.remove_ik_chain", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.move_ik_chain", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.move_ik_chain", icon="TRIA_DOWN", text="").direction = 'down'
        if nwo.ik_chains and nwo.ik_chains_active_index > -1:
            chain = nwo.ik_chains[nwo.ik_chains_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop_search(chain, 'start_node', nwo.main_armature.data, 'bones', text='Start Bone')
            col.prop_search(chain, 'effector_node', nwo.main_armature.data, 'bones', text='Effector Bone')
            
    def draw_animation_copies(self, box, nwo):
        if not nwo.animation_copies:
            box.operator("nwo.animation_copy_add", text="New Animation Copy", icon_value=get_icon_id("animation_copy"))
            return
        row = box.row()
        row.template_list(
            "NWO_UL_AnimationCopies",
            "",
            nwo,
            "animation_copies",
            nwo,
            "animation_copies_active_index",
        )
        col = row.column(align=True)
        col.operator("nwo.animation_copy_add", text="", icon="ADD")
        col.operator("nwo.animation_copy_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.animation_copy_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.animation_copy_move", icon="TRIA_DOWN", text="").direction = 'down'
        if nwo.animation_copies and nwo.animation_copies_active_index > -1:
            item = nwo.animation_copies[nwo.animation_copies_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop(item, "source_name")
            col.prop(item, "name")
            
    def draw_animation_composites(self, box: bpy.types.UILayout, nwo):
        if not nwo.animation_composites:
            box.operator("nwo.animation_composite_add", text="New Composite Animation", icon_value=get_icon_id("animation_composite"))
            return
        row = box.row()
        row.template_list(
            "NWO_UL_AnimationComposites",
            "",
            nwo,
            "animation_composites",
            nwo,
            "animation_composites_active_index",
        )
        col = row.column(align=True)
        col.operator("nwo.animation_composite_add", text="", icon="ADD")
        col.operator("nwo.animation_composite_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.animation_composite_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.animation_composite_move", icon="TRIA_DOWN", text="").direction = 'down'
        if nwo.animation_composites and nwo.animation_composites_active_index > -1:
            item = nwo.animation_composites[nwo.animation_composites_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop(item, "overlay")
            col.prop(item, "timing_source")
            box = col.box()
            box.label(text="Blend Axes")
            row = box.row()
            row.template_list(
                "NWO_UL_AnimationBlendAxis",
                "",
                item,
                "blend_axis",
                item,
                "blend_axis_active_index",
            )
            col = row.column(align=True)
            col.operator("nwo.animation_blend_axis_add", text="", icon="ADD")
            col.operator("nwo.animation_blend_axis_remove", icon="REMOVE", text="")
            col.separator()
            col.operator("nwo.animation_blend_axis_move", text="", icon="TRIA_UP").direction = 'up'
            col.operator("nwo.animation_blend_axis_move", icon="TRIA_DOWN", text="").direction = 'down'
            
            if not item.blend_axis or item.blend_axis_active_index <= -1:
                return
            
            blend_axis = item.blend_axis[item.blend_axis_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop(blend_axis, "animation_source_bounds")
            col.prop(blend_axis, "animation_source_limit")
            col.prop(blend_axis, "runtime_source_bounds")
            col.prop(blend_axis, "runtime_source_clamped")
            col.prop(blend_axis, "adjusted")
            if not blend_axis.dead_zones:
                col.operator("nwo.animation_dead_zone_add", text="Add Dead Zone", icon='CON_OBJECTSOLVER')
            else:
                box = col.box()
                box.label(text="Dead Zones")
                row = box.row()
                row.template_list(
                    "NWO_UL_AnimationDeadZone",
                    "",
                    blend_axis,
                    "dead_zones",
                    blend_axis,
                    "dead_zones_active_index",
                )
                col = row.column(align=True)
                col.operator("nwo.animation_dead_zone_add", text="", icon="ADD")
                col.operator("nwo.animation_dead_zone_remove", icon="REMOVE", text="")
                col.separator()
                col.operator("nwo.animation_dead_zone_move", text="", icon="TRIA_UP").direction = 'up'
                col.operator("nwo.animation_dead_zone_move", icon="TRIA_DOWN", text="").direction = 'down'
                if blend_axis.dead_zones and blend_axis.dead_zones_active_index > -1:
                    dead_zone = blend_axis.dead_zones[blend_axis.dead_zones_active_index]
                    col = box.column()
                    col.use_property_split = True
                    col.prop(dead_zone, "bounds")
                    col.prop(dead_zone, "rate")
                
            self.draw_animation_leaves(col, blend_axis, False)
            if not blend_axis.phase_sets:
                col.operator("nwo.animation_phase_set_add", text="Add Animation Set", icon='PRESET')
            else:
                box = col.box()
                box.label(text="Sets")
                row = box.row()
                row.template_list(
                    "NWO_UL_AnimationPhaseSet",
                    "",
                    blend_axis,
                    "phase_sets",
                    blend_axis,
                    "phase_sets_active_index",
                )
                col = row.column(align=True)
                col.operator("nwo.animation_phase_set_add", text="", icon="ADD")
                col.operator("nwo.animation_phase_set_remove", icon="REMOVE", text="")
                col.separator()
                col.operator("nwo.animation_phase_set_move", text="", icon="TRIA_UP").direction = 'up'
                col.operator("nwo.animation_phase_set_move", icon="TRIA_DOWN", text="").direction = 'down'
                if blend_axis.phase_sets and blend_axis.phase_sets_active_index > -1:
                    phase_set = blend_axis.phase_sets[blend_axis.phase_sets_active_index]
                    col = box.column()
                    col.use_property_split = True
                    col.prop(phase_set, "name")
                    col.prop(phase_set, "priority")
                    col.label(text="Keys")
                    grid = col.grid_flow()
                    grid.prop(phase_set, 'key_primary_keyframe')
                    grid.prop(phase_set, 'key_secondary_keyframe')
                    grid.prop(phase_set, 'key_tertiary_keyframe')
                    grid.prop(phase_set, 'key_left_foot')
                    grid.prop(phase_set, 'key_right_foot')
                    grid.prop(phase_set, 'key_body_impact')
                    grid.prop(phase_set, 'key_left_foot_lock')
                    grid.prop(phase_set, 'key_left_foot_unlock')
                    grid.prop(phase_set, 'key_right_foot_lock')
                    grid.prop(phase_set, 'key_right_foot_unlock')
                    grid.prop(phase_set, 'key_blend_range_marker')
                    grid.prop(phase_set, 'key_stride_expansion')
                    grid.prop(phase_set, 'key_stride_contraction')
                    grid.prop(phase_set, 'key_ragdoll_keyframe')
                    grid.prop(phase_set, 'key_drop_weapon_keyframe')
                    grid.prop(phase_set, 'key_match_a')
                    grid.prop(phase_set, 'key_match_b')
                    grid.prop(phase_set, 'key_match_c')
                    grid.prop(phase_set, 'key_match_d')
                    grid.prop(phase_set, 'key_jetpack_closed')
                    grid.prop(phase_set, 'key_jetpack_open')
                    grid.prop(phase_set, 'key_sound_event')
                    grid.prop(phase_set, 'key_effect_event')
                    
                    self.draw_animation_leaves(col, phase_set, True)
            
            
    def draw_animation_leaves(self,col: bpy.types.UILayout, parent, in_set):
        box = col.box()
        name = "Set Animations" if in_set else "Blend Axis Animations"
        box.label(text=name)
        row = box.row()
        row.template_list(
            "NWO_UL_AnimationLeaf",
            "",
            parent,
            "leaves",
            parent,
            "leaves_active_index",
        )
        col = row.column(align=True)
        col.operator("nwo.animation_leaf_add", text="", icon="ADD").phase_set = in_set
        col.operator("nwo.animation_leaf_remove", icon="REMOVE", text="").phase_set = in_set
        col.separator()
        move_up = col.operator("nwo.animation_leaf_move", text="", icon="TRIA_UP")
        move_up.direction = 'up'
        move_up.phase_set = in_set
        move_down = col.operator("nwo.animation_leaf_move", icon="TRIA_DOWN", text="")
        move_down.direction = 'down'
        move_down.phase_set = in_set
        if parent.leaves and parent.leaves_active_index > -1:
            leaf = parent.leaves[parent.leaves_active_index]
            col = box.column()
            col.use_property_split = True
            col.prop(leaf, "animation")
            col.prop(leaf, "uses_move_speed")
            if leaf.uses_move_speed:
                col.prop(leaf, "move_speed")
            col.prop(leaf, "uses_move_angle")
            if leaf.uses_move_angle:
                col.prop(leaf, "move_angle")
    
    def draw_rig_ui(self, context, nwo):
        box = self.box.box()
        if self.draw_expandable_box(box, nwo, 'model_rig') and nwo.main_armature:
            self.draw_expandable_box(box.box(), nwo, 'rig_controls', 'Bone Controls')
            self.draw_expandable_box(box.box(), nwo, 'rig_object_controls', 'Object Controls')

    def draw_sets_manager(self):
        self.box.operator('nwo.update_sets', icon='FILE_REFRESH')
        box = self.box
        nwo = self.scene.nwo
        if not nwo.regions_table:
            return
        is_scenario = nwo.asset_type == 'scenario'
        self.draw_object_visibility(box.box(), nwo)
        self.draw_expandable_box(box.box(), nwo, "regions_table", "BSPs" if is_scenario else "Regions")
        self.draw_expandable_box(box.box(), nwo, "permutations_table", "Layers" if is_scenario else "Permutations")
        
    def draw_object_visibility(self, box: bpy.types.UILayout, nwo):
        asset_type = nwo.asset_type
        # box.label(text="Mesh")
        grid = box.grid_flow(align=True, even_columns=True)
        default_icon_name = "render_geometry"
        default_icon_off_name = "render_geometry_off"
        if poll_ui(('scenario', 'prefab')):
            default_icon_name = "instance"
            default_icon_off_name = "instance_off"
        elif asset_type == 'decorator_set':
            default_icon_name = "decorator"
            default_icon_off_name = "decorator_off"
            
        grid.prop(nwo, "connected_geometry_mesh_type_default_visible", text="", icon_value=get_icon_id(default_icon_name) if nwo.connected_geometry_mesh_type_default_visible else get_icon_id(default_icon_off_name), emboss=False)
        if poll_ui(('scenario', 'model', 'prefab')):
            grid.prop(nwo, "connected_geometry_mesh_type_collision_visible", text="", icon_value=get_icon_id("collider") if nwo.connected_geometry_mesh_type_collision_visible else get_icon_id("collider_off"), emboss=False)
        if asset_type == 'model':
            grid.prop(nwo, "connected_geometry_mesh_type_physics_visible", text="", icon_value=get_icon_id("physics") if nwo.connected_geometry_mesh_type_physics_visible else get_icon_id("physics_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_object_instance_visible", text="", icon_value=get_icon_id("instance") if nwo.connected_geometry_mesh_type_object_instance_visible else get_icon_id("instance_off"), emboss=False)
        if asset_type == 'scenario':
            grid.prop(nwo, "connected_geometry_mesh_type_structure_visible", text="", icon_value=get_icon_id("structure") if nwo.connected_geometry_mesh_type_structure_visible else get_icon_id("structure_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_seam_visible", text="", icon_value=get_icon_id("seam") if nwo.connected_geometry_mesh_type_seam_visible else get_icon_id("seam_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_portal_visible", text="", icon_value=get_icon_id("portal") if nwo.connected_geometry_mesh_type_portal_visible else get_icon_id("portal_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_lightmap_only_visible", text="", icon_value=get_icon_id("lightmap") if nwo.connected_geometry_mesh_type_lightmap_only_visible else get_icon_id("lightmap_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_water_surface_visible", text="", icon_value=get_icon_id("water") if nwo.connected_geometry_mesh_type_water_surface_visible else get_icon_id("water_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_planar_fog_volume_visible", text="", icon_value=get_icon_id("fog") if nwo.connected_geometry_mesh_type_planar_fog_volume_visible else get_icon_id("fog_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_soft_ceiling_visible", text="", icon_value=get_icon_id("soft_ceiling") if nwo.connected_geometry_mesh_type_soft_ceiling_visible else get_icon_id("soft_ceiling_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_soft_kill_visible", text="", icon_value=get_icon_id("soft_kill") if nwo.connected_geometry_mesh_type_soft_kill_visible else get_icon_id("soft_kill_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_mesh_type_slip_surface_visible", text="", icon_value=get_icon_id("slip_surface") if nwo.connected_geometry_mesh_type_slip_surface_visible else get_icon_id("slip_surface_off"), emboss=False)
            if self.h4:
                grid.prop(nwo, "connected_geometry_mesh_type_streaming_visible", text="", icon_value=get_icon_id("streaming") if nwo.connected_geometry_mesh_type_streaming_visible else get_icon_id("streaming_off"), emboss=False)
                grid.prop(nwo, "connected_geometry_mesh_type_lightmap_exclude_visible", text="", icon_value=get_icon_id("lightmap_exclude") if nwo.connected_geometry_mesh_type_lightmap_exclude_visible else get_icon_id("lightmap_exclude_off"), emboss=False)
            else:
                grid.prop(nwo, "connected_geometry_mesh_type_cookie_cutter_visible", text="", icon_value=get_icon_id("cookie_cutter") if nwo.connected_geometry_mesh_type_cookie_cutter_visible else get_icon_id("cookie_cutter_off"), emboss=False)
                grid.prop(nwo, "connected_geometry_mesh_type_poop_vertical_rain_sheet_visible", text="", icon_value=get_icon_id("rain_sheet") if nwo.connected_geometry_mesh_type_poop_vertical_rain_sheet_visible else get_icon_id("rain_sheet_off"), emboss=False)
                grid.prop(nwo, "connected_geometry_mesh_type_poop_rain_blocker_visible", text="", icon_value=get_icon_id("rain_blocker") if nwo.connected_geometry_mesh_type_poop_rain_blocker_visible else get_icon_id("rain_blocker_off"), emboss=False)

        grid.prop(nwo, "connected_geometry_marker_type_model_visible", text="", icon_value=get_icon_id("marker") if nwo.connected_geometry_marker_type_model_visible else get_icon_id("marker_off"), emboss=False)
        if poll_ui(('model', 'sky')):
            grid.prop(nwo, "connected_geometry_marker_type_effects_visible", text="", icon_value=get_icon_id("effects") if nwo.connected_geometry_marker_type_effects_visible else get_icon_id("effects_off"), emboss=False)
        if asset_type == 'model':
            grid.prop(nwo, "connected_geometry_marker_type_garbage_visible", text="", icon_value=get_icon_id("garbage") if nwo.connected_geometry_marker_type_garbage_visible else get_icon_id("garbage_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_marker_type_hint_visible", text="", icon_value=get_icon_id("hint") if nwo.connected_geometry_marker_type_hint_visible else get_icon_id("hint_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_marker_type_pathfinding_sphere_visible", text="", icon_value=get_icon_id("pathfinding_sphere") if nwo.connected_geometry_marker_type_pathfinding_sphere_visible else get_icon_id("pathfinding_sphere_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_marker_type_physics_constraint_visible", text="", icon_value=get_icon_id("physics_constraint") if nwo.connected_geometry_marker_type_physics_constraint_visible else get_icon_id("physics_constraint_off"), emboss=False)
            grid.prop(nwo, "connected_geometry_marker_type_target_visible", text="", icon_value=get_icon_id("target") if nwo.connected_geometry_marker_type_target_visible else get_icon_id("target_off"), emboss=False)
                
        if poll_ui(('model', 'scenario')) and self.h4:
            grid.prop(nwo, "connected_geometry_marker_type_airprobe_visible", text="", icon_value=get_icon_id("airprobe") if nwo.connected_geometry_marker_type_airprobe_visible else get_icon_id("airprobe_off"), emboss=False)
        if asset_type == 'scenario':
            grid.prop(nwo, "connected_geometry_marker_type_game_instance_visible", text="", icon_value=get_icon_id("game_object") if nwo.connected_geometry_marker_type_game_instance_visible else get_icon_id("game_object_off"), emboss=False)
            if self.h4:
                grid.prop(nwo, "connected_geometry_marker_type_envfx_visible", text="", icon_value=get_icon_id("environment_effect") if nwo.connected_geometry_marker_type_envfx_visible else get_icon_id("environment_effect_off"), emboss=False)
                grid.prop(nwo, "connected_geometry_marker_type_lightCone_visible", text="", icon_value=get_icon_id("light_cone") if nwo.connected_geometry_marker_type_lightCone_visible else get_icon_id("light_cone_off"), emboss=False)
        # box.label(text="Other")
        # grid = box.grid_flow(align=False, even_columns=True)
        grid.prop(nwo, "connected_geometry_object_type_frame_visible", text="", icon_value=get_icon_id("frame") if nwo.connected_geometry_object_type_frame_visible else get_icon_id("frame_off"), emboss=False)
        grid.prop(nwo, "connected_geometry_object_type_light_visible", text="", icon_value=get_icon_id("light") if nwo.connected_geometry_object_type_light_visible else get_icon_id("light_off"), emboss=False)
        
    def draw_regions_table(self, box, nwo):
        row = box.row()
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
        if self.asset_type == 'scenario':
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
    
    def draw_permutations_table(self, box, nwo):
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
        box = self.box
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
        has_mesh_types = is_mesh(ob) and poll_ui(('model', 'scenario', 'prefab'))
        has_marker_types = is_marker(ob) and poll_ui(('model', 'sky', 'scenario', 'prefab'))

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
            col.prop(data, "color")
            col.prop(data, "energy")
            # col.prop(nwo, 'light_intensity', text="Intensity")
            scaled_energy = data.energy * get_export_scale(context)
            if scaled_energy < 11 and data.type != 'SUN':
                # Warn user about low light power. Need the light scaled to Halo proportions
                col.label(text="Light itensity is very low", icon='ERROR')
                col.label(text="For best results match the power of the light in")
                col.label(text="Cycles to how you'd like it to appear in game")
                
            if data.type == 'AREA':
                # Area lights use emissive settings, as they will be converted to lightmap only emissive planes at export
                col.separator()
                col.prop(data, "shape")
                if data.shape in {'SQUARE', 'DISK'}:
                    col.prop(data, "size")
                elif data.shape in {'RECTANGLE', 'ELLIPSE'}:
                    col.prop(data, "size", text="Size X")
                    col.prop(data, "size_y", text="Y")
                col.separator()
                col.prop(nwo, "light_quality")
                col.prop(nwo, "light_focus")
                col.prop(nwo, "light_bounce_ratio")
                col.separator()
                col.prop(nwo, "light_far_attenuation_start", text="Light Falloff")
                col.prop(nwo, "light_far_attenuation_end", text="Light Cutoff")
                col.separator()
                col.prop(nwo, "light_use_shader_gel")
                col.prop(nwo, "light_per_unit")
                return

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
                
                col.prop(nwo, "light_far_attenuation_start", text='Light Falloff')
                col.prop(nwo, "light_far_attenuation_end", text='Light Cutoff')
                
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

                col.prop(nwo, "light_far_attenuation_start", text="Light Falloff")
                col.prop(nwo, "light_far_attenuation_end", text="Light Cutoff")

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
            if self.asset_type == 'decorator_set':
                col.label(text="Decorator")
                col.prop(nwo, "decorator_lod_ui", text="Level of Detail", expand=True)
                return
            elif self.asset_type == 'particle_model':
                col.label(text="Particle Model")
                return
            
            if nwo.mesh_type_ui == '_connected_geometry_mesh_type_object_instance':
                row = col.row()
                row.use_property_split = False
                row.prop(nwo, "marker_uses_regions", text='Region', icon_value=get_icon_id("collection_creator") if nwo.region_name_locked_ui else 0)
                if nwo.marker_uses_regions:
                    col.menu("NWO_MT_Regions", text=true_region(nwo), icon_value=get_icon_id("region"))
                    col.separator()
                    rows = 3
                    row = col.row(heading='Permutations')
                    row.use_property_split = False
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
            else:
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
                nwo.mesh_type_ui
                == "_connected_geometry_mesh_type_water_physics_volume"
            ):
                col.prop(
                    nwo,
                    "water_volume_depth_ui",
                    text="Water Depth",
                )
                col.prop(
                    nwo,
                    "water_volume_flow_direction_ui",
                    text="Water Flow Direction",
                )
                col.prop(
                    nwo,
                    "water_volume_flow_velocity_ui",
                    text="Water Flow Velocity",
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

            elif (
                nwo.mesh_type_ui == "_connected_geometry_mesh_type_water_surface"
            ):
                col.prop(nwo, "mesh_tessellation_density_ui", text="Tessellation Density")
                col.prop(
                    nwo,
                    "water_volume_depth_ui",
                    text="Water Depth",
                )
                if nwo.water_volume_depth_ui:
                    col.prop(
                        nwo,
                        "water_volume_flow_direction_ui",
                        text="Water Flow Direction",
                    )
                    col.prop(
                        nwo,
                        "water_volume_flow_velocity_ui",
                        text="Water Flow Velocity",
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
            ) and poll_ui(('scenario', 'prefab')):
                if h4 and nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure" and poll_ui(('scenario',)):
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
                        col.prop(nwo, "poop_remove_from_shadow_geometry_ui")
                        col.prop(nwo, "poop_disallow_lighting_samples_ui")
                        # col.prop(nwo, "poop_rain_occluder")

            # MESH LEVEL / FACE LEVEL PROPERTIES

        elif is_marker(ob) and poll_ui(
            ("model", "scenario", "sky", "prefab")
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
            
            col.prop(nwo, "frame_override")

            if poll_ui("scenario"):
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
                if poll_ui(("model", "sky")):
                    if nwo.marker_type_ui in ('_connected_geometry_marker_type_model', '_connected_geometry_marker_type_garbage', '_connected_geometry_marker_type_effects'):
                        col.prop(nwo, 'marker_model_group', text="Marker Group")
                    row = col.row()
                    row.use_property_split = False
                    row.prop(nwo, "marker_uses_regions", text='Region', icon_value=get_icon_id("collection_creator") if nwo.region_name_locked_ui else 0)
                    if nwo.marker_uses_regions:
                        col.menu("NWO_MT_Regions", text=true_region(nwo), icon_value=get_icon_id("region"))
                    
                    # marker perm ui
                    if nwo.marker_uses_regions:
                        col.separator()
                        rows = 3
                        row = col.row(heading='Permutations')
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
                        col.prop(nwo, "marker_always_run_scripts_ui")

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
                        col.separator()
                        col.prop(nwo, "cone_angle_ui", text="Cone Angle")
                        col.separator()
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
            ("model", "scenario", "sky")):
            col = box.column()
            col.label(text='Frame', icon_value=get_icon_id('frame'))
            if not ob.children:
                col.prop(nwo, "frame_override")
            # TODO Add button that selects child objects
            return
                

        if not has_mesh_props(ob) or (h4 and not nwo.proxy_instance and poll_ui(('scenario',)) and nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure"):
            return

        self.draw_expandable_box(self.box.box(), context.scene.nwo, "mesh_properties", ob=ob)
        if has_face_props(ob):
            self.draw_expandable_box(self.box.box(), context.scene.nwo, "face_properties", ob=ob)
  
        nwo = ob.data.nwo
        # Instance Proxy Operators
        if ob.type != 'MESH' or ob.nwo.mesh_type_ui != "_connected_geometry_mesh_type_default" or not poll_ui(('scenario', 'prefab')) or mesh_nwo.render_only_ui:
            return
        
        col.separator()
        self.draw_expandable_box(self.box.box(), context.scene.nwo, "instance_proxies", ob=ob)

    def draw_face_properties(self, box, ob):
        context = self.context
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
        if nwo.face_props:
            box.operator('nwo.update_layers_face_count', text="Refresh Face Counts", icon='FILE_REFRESH')
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

            col = row.column(align=True)
            edit_mode = context.mode == 'EDIT_MESH'
            if edit_mode:
                if context.scene.nwo.instance_proxy_running or (ob.nwo.mesh_type_ui == "_connected_geometry_mesh_type_collision" and poll_ui(('scenario', 'prefab'))):
                    col.operator("nwo.face_layer_add", text="", icon="ADD").options = "face_global_material"
                else:
                    col.menu(NWO_FaceLayerAddMenu.bl_idname, text="", icon="ADD")
                
            col.operator("nwo.face_layer_remove", icon="REMOVE", text="")
            col.separator()
            if edit_mode:
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

            if nwo.face_props and edit_mode:
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
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "region"
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
                if item.face_draw_distance_override:
                    row = col.row()
                    row.prop(item, "face_draw_distance_ui")
                if item.face_global_material_override:
                    row = col.row()
                    row.prop(item, "face_global_material_ui")
                    if poll_ui(('scenario', 'prefab')):
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
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_additive_transparency"
                if item.lightmap_resolution_scale_override:
                    row = col.row()
                    row.prop(item, "lightmap_resolution_scale_ui")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_resolution_scale"
                if item.lightmap_type_override:
                    row = col.row()
                    row.prop(item, "lightmap_type_ui")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_type"
                if item.lightmap_analytical_bounce_modifier_override:
                    row = col.row()
                    row.prop(item, "lightmap_analytical_bounce_modifier_ui")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_analytical_bounce_modifier"
                if item.lightmap_general_bounce_modifier_override:
                    row = col.row()
                    row.prop(item, "lightmap_general_bounce_modifier_ui")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_general_bounce_modifier"
                if item.lightmap_translucency_tint_color_override:
                    row = col.row()
                    row.prop(item, "lightmap_translucency_tint_color_ui")
                    # row.operator(
                    #     "nwo.face_prop_remove", text="", icon="X"
                    # ).options = "lightmap_translucency_tint_color"
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

    def draw_mesh_properties(self, box, ob):
        nwo = ob.nwo
        mesh = ob.data
        mesh_nwo = mesh.nwo
        has_collision = has_collision_type(ob)
        if poll_ui(("model", "sky", "scenario", "prefab")) and nwo.mesh_type_ui != '_connected_geometry_mesh_type_physics':
            if self.h4 and (not nwo.proxy_instance and nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure" and poll_ui(('scenario',))):
                return
            row = box.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=True,
                align=True,
            )
            row.scale_x = 0.8
            if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_lightmap_only", '_connected_geometry_mesh_type_object_instance'):
                row.prop(mesh_nwo, "precise_position_ui", text="Uncompressed")
            if nwo.mesh_type_ui in TWO_SIDED_MESH_TYPES:
                row.prop(mesh_nwo, "face_two_sided_ui", text="Two Sided")
                if nwo.mesh_type_ui in RENDER_MESH_TYPES:
                    row.prop(mesh_nwo, "face_transparent_ui", text="Transparent")
                    # if h4 and poll_ui(('model', 'sky')):
                    #     row.prop(mesh_nwo, "uvmirror_across_entire_model_ui", text="Mirror UVs")
            if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure", '_connected_geometry_mesh_type_object_instance', "_connected_geometry_mesh_type_lightmap_only"):
                row.prop(mesh_nwo, "decal_offset_ui", text="Decal Offset") 
            if poll_ui(("scenario", "prefab")):
                if not self.h4:
                    if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_lightmap_only"):
                        row.prop(mesh_nwo, "no_shadow_ui", text="No Shadow")
                else:
                    # row.prop(mesh_nwo, "group_transparents_by_plane_ui", text="Transparents by Plane")
                    if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_lightmap_only"):
                        row.prop(mesh_nwo, "no_shadow_ui", text="No Shadow")
                        if self.h4 and nwo.mesh_type_ui != "_connected_geometry_mesh_type_lightmap_only":
                            row.prop(mesh_nwo, "no_lightmap_ui", text="No Lightmap")
                            row.prop(mesh_nwo, "no_pvs_ui", text="No Visibility Culling")
                            
            if not self.h4 and poll_ui(('scenario',)) and nwo.mesh_type_ui in ('_connected_geometry_mesh_type_default', '_connected_geometry_mesh_type_structure'):
                row.prop(mesh_nwo, 'render_only_ui', text='Render Only')
                if not mesh_nwo.render_only_ui:
                    row.prop(mesh_nwo, "ladder_ui", text="Ladder")
                    row.prop(mesh_nwo, "slip_surface_ui", text="Slip Surface")
                    row.prop(mesh_nwo, 'breakable_ui', text='Breakable')
                
            elif not self.h4 and nwo.mesh_type_ui == '_connected_geometry_mesh_type_collision':
                if poll_ui(('scenario', 'model')):
                    row.prop(mesh_nwo, 'sphere_collision_only_ui', text='Sphere Collision Only')
                    row.prop(mesh_nwo, "ladder_ui", text="Ladder")
                    row.prop(mesh_nwo, "slip_surface_ui", text="Slip Surface")
                
            elif self.h4 and has_collision and nwo.mesh_type_ui != '_connected_geometry_mesh_type_collision':
                row.prop(mesh_nwo, 'render_only_ui', text='Render Only')

            if self.h4 and nwo.mesh_type_ui in RENDER_MESH_TYPES and mesh_nwo.face_two_sided_ui:
                row = box.row()
                row.use_property_split = True
                row.prop(mesh_nwo, "face_two_sided_type_ui", text="Backside Normals")
                
        if nwo.mesh_type_ui in RENDER_MESH_TYPES:
            row = box.row()
            row.use_property_split = True
            row.prop(mesh_nwo, "face_draw_distance_ui")
                
        if poll_ui(("model", "scenario", "prefab")):
            if has_collision and poll_ui(("scenario", "prefab")) and not (mesh_nwo.render_only_ui and is_instance_or_structure_proxy(ob)):
                row = box.row()
                row.use_property_split = True
                if self.h4:
                    row.prop(mesh_nwo, 'poop_collision_type_ui', text='Collision Type')
                        
            if (self.h4 and (nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                "_connected_geometry_mesh_type_structure",
                "_connected_geometry_mesh_type_default",
                )
                and (nwo.proxy_instance or nwo.mesh_type_ui != "_connected_geometry_mesh_type_structure"))) or (not self.h4 and nwo.mesh_type_ui in (
                "_connected_geometry_mesh_type_collision",
                "_connected_geometry_mesh_type_physics",
                )):
                    if not (nwo.mesh_type_ui in ("_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_default") and mesh_nwo.render_only_ui):
                        if not (self.asset_type == 'model' and nwo.mesh_type_ui == '_connected_geometry_mesh_type_default'):
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
                            if poll_ui(('scenario', 'prefab')):
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
            if poll_ui(("scenario", "prefab")) and (not self.h4 or nwo.proxy_instance or nwo.mesh_type_ui != "_connected_geometry_mesh_type_structure"):
                # col.separator()
                col_ob = box.column()
                col_ob.use_property_split = True
                # lightmap
                has_lightmap_props = mesh_nwo.mesh_type_ui != "_connected_geometry_mesh_type_lightmap_only"
                if has_lightmap_props:
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
                        "material_lighting_bounce_ratio_ui",
                        text="Bounce Ratio",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_attenuation_falloff_ui",
                        text="Light Falloff",
                    )
                    row = box_ob.row(align=True)
                    row.prop(
                        mesh_nwo,
                        "material_lighting_attenuation_cutoff_ui",
                        text="Light Cutoff",
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
                
                if has_lightmap_props:
                    row_add_prop.operator_menu_enum("nwo.add_mesh_property_lightmap", property="options", text="Lightmap Settings", icon='OUTLINER_DATA_LIGHTPROBE')
    
    def draw_instance_proxies(self, box, ob):
        nwo = ob.data.nwo
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

        if not self.h4 and cookie_cutter:
            row = box.row(align=True)
            row.operator("nwo.proxy_instance_edit", text="Edit Proxy Cookie Cutter", icon_value=get_icon_id("cookie_cutter")).proxy = cookie_cutter.name
            row.operator("nwo.proxy_instance_delete", text="", icon="X").proxy = cookie_cutter.name

        if not (collision and physics and (self.h4 or cookie_cutter)):
            row = box.row()
            row.scale_y = 1.3
            row.operator("nwo.proxy_instance_new", text="New Instance Proxy", icon="ADD")
    
    def draw_material_properties(self):
        box = self.box
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
            if nwo.SpecialMaterial:
                if mat.name == '+invisible':
                    col.label(text=f'Invisible {tag_type} applied')
                elif mat.name == '+invalid':
                    col.label(text=f'Default Invalid {tag_type} applied')
                elif mat.name == '+missing':
                    col.label(text=f'Default Missing {tag_type} applied')
                elif mat.name == '+seamsealer':
                    col.label(text=f'SeamSealer Material applied')
                elif mat.name == '+collision':
                    col.label(text=f'Collision Material applied')
                elif mat.name == '+sphere_collision':
                    col.label(text=f'Sphere Collision Material applied')
                else:
                    col.label(text=f'Sky Material applied')
                    sky_perm = get_sky_perm(mat)
                    if sky_perm > -1:
                        if sky_perm > 31:
                            col.label(text='Maximum Sky Permutation Index is 31', icon='ERROR')
                        else:
                            col.label(text=f"Sky Permutation {str(sky_perm)}")
                    col.operator("nwo.set_sky", text="Set Sky Permutation")
                return
            elif nwo.ConventionMaterial:
                return col.label(text=f'Non-Rendered {tag_type} applied')
            else:
                col.label(text=f"{txt} Path")
                row = col.row(align=True)
                row.prop(nwo, "shader_path", text="", icon_value=get_icon_id("tags"))
                row.operator("nwo.shader_finder_single", icon_value=get_icon_id("material_finder"), text="")
                row.operator("nwo.get_tags_list", icon="VIEWZOOM", text="").list_type = "shader_path"
                row.operator("nwo.tag_explore", text="", icon="FILE_FOLDER").prop = 'shader_path'
                has_valid_path = nwo.shader_path and Path(get_tags_path(), relative_path(nwo.shader_path)).exists()
                if has_valid_path:
                    col.separator()
                    # row.scale_y = 1.5
                    col.operator(
                        "nwo.open_halo_material",
                        icon_value=get_icon_id("foundation"),
                        text="Open in Tag Editor"
                    )
                    shader_path = mat.nwo.shader_path
                    full_path = str(Path(get_tags_path(), shader_path))
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
                            row.operator("nwo.get_material_shaders", icon="VIEWZOOM", text="").batch_panel = False
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

            # TEXTURE PROPS
            # First validate if Material has images
            if not mat.node_tree:
                return
            if not recursive_image_search(mat):
                return
            
            self.draw_expandable_box(self.box.box(), context.scene.nwo, "image_properties", material=mat)

                
    def draw_image_properties(self, box, mat):
        box.use_property_split = False
        nwo = mat.nwo
        col = box.column()
        image = nwo.active_image
        col.template_ID_preview(nwo, "active_image")
        if not image:
            return
        bitmap = image.nwo
        editor = self.context.preferences.filepaths.image_editor
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
        col.operator("nwo.open_foundation_tag", text="Open Bitmap Tag", icon_value=get_icon_id("foundation")).tag_path = bitmap_path
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

    def draw_animation_manager(self):
        box = self.box.box()
        row = box.row()
        context = self.context
        ob = context.object
        scene_nwo = context.scene.nwo
            
        if not bpy.data.actions:
            box.operator("nwo.new_animation", icon="ANIM", text="New Animation")
            box.operator("nwo.select_armature", text="Select Armature", icon='OUTLINER_OB_ARMATURE')
            return

        row.template_list(
            "NWO_UL_AnimationList",
            "",
            bpy.data,
            "actions",
            scene_nwo,
            "active_action_index",
        )
        
        col = row.column(align=True)
        col.operator("nwo.new_animation", icon="ADD", text="")
        col.operator("nwo.delete_animation", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.unlink_animation", icon="X", text="")
        col.separator()
        col.operator("nwo.set_timeline", text="", icon='TIME')
        if not ob or ob.type != "ARMATURE":
            col.separator()
            col.operator("nwo.select_armature", text="", icon='OUTLINER_OB_ARMATURE')
        
        col = box.column()
        row = col.row()
        
        
        if scene_nwo.active_action_index < 0:
            col.label(text="No Animation Selected")
            return
        
        action = bpy.data.actions[scene_nwo.active_action_index]
        
        if not action.use_frame_range:
            col.label(text="Animation excluded from export", icon='ERROR')
            col.separator()
            
        if not action.use_fake_user:
            col.label(text="Fake User Not Set, Animation may be lost on Blender close", icon='ERROR')
            col.prop(action, 'use_fake_user', text="Enable Fake User", icon='FAKE_USER_OFF')
            col.separator()
        
        nwo = action.nwo
        col.separator()
        col.operator("nwo.animation_frames_sync_to_keyframes", text="Sync Frame Range to Keyframes", icon='FILE_REFRESH', depress=scene_nwo.keyframe_sync_active)
        col.separator()
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
                col.separator()
                col.operator("nwo.animation_rename_move", text="", icon="TRIA_UP").direction = 'up'
                col.operator("nwo.animation_rename_move", icon="TRIA_DOWN", text="").direction = 'down'

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
                col.separator()
                col.operator("nwo.animation_event_move", text="", icon="TRIA_UP").direction = 'up'
                col.operator("nwo.animation_event_move", icon="TRIA_DOWN", text="").direction = 'down'

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
                    col.prop(item, "event_type")
                    if item.event_type == '_connected_geometry_animation_event_type_frame':
                        row = col.row()
                        row.prop(item, "multi_frame", expand=True)
                        if item.multi_frame == "range":
                            row = col.row(align=True)
                            row.prop(item, "frame_frame", text="Event Frame Start")
                            row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                            row = col.row(align=True)
                            row.prop(item, "frame_range", text="Event Frame End")
                            row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_range"
                        else:
                            row = col.row(align=True)
                            row.prop(item, "frame_frame")
                            row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"

                        col.prop(item, "frame_name")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_wrinkle_map"
                    ):
                        row = col.row(align=True)
                        row.prop(item, "frame_frame", text="Event Frame Start")
                        row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_frame"
                        row = col.row(align=True)
                        row.prop(item, "frame_range", text="Event Frame End")
                        row.operator("nwo.animation_event_set_frame", text="", icon="KEYFRAME_HLT").prop_to_set = "frame_range"
                        col.prop(item, "wrinkle_map_face_region")
                        col.prop(item, "wrinkle_map_effect")
                    elif item.event_type.startswith('_connected_geometry_animation_event_type_ik'):
                        valid_ik_chains = [chain for chain in scene_nwo.ik_chains if chain.start_node and chain.effector_node]
                        if not valid_ik_chains:
                            col.label(text='Add IK Chains in the Asset Editor tab', icon='ERROR')
                            return
                        col.prop(item, "ik_chain")
                        # col.prop(item, "ik_active_tag")
                        # col.prop(item, "ik_target_tag")
                        col.prop(item, "ik_target_marker", icon_value=get_icon_id('marker'))
                        col.prop(item, "ik_target_usage")
                        col.prop(item, 'ik_influence')
                        # col.prop(item, "ik_proxy_target_id")
                        # col.prop(item, "ik_pole_vector_id")
                        # col.prop(item, "ik_effector_id")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_object_function"
                    ):
                        col.prop(item, "frame_frame")
                        col.prop(item, "frame_range")
                        col.prop(item, "object_function_name")
                        col.prop(item, "object_function_effect")
                    elif (
                        item.event_type
                        == "_connected_geometry_animation_event_type_import"
                    ):
                        col.prop(item, "import_frame")
                        col.prop(item, "import_name")
            col = box.column()

    def draw_tools(self):
        nwo = self.scene.nwo
        shader_type = "Material" if self.h4 else "Shader"
        self.draw_expandable_box(self.box.box(), nwo, "asset_shaders", f"Asset {shader_type}s")
        self.draw_expandable_box(self.box.box(), nwo, "importer")
        if poll_ui(('model', 'animation', 'sky', 'resource')):
            self.draw_expandable_box(self.box.box(), nwo, "rig_tools")
        if poll_ui(('scenario', 'resource')):
            self.draw_expandable_box(self.box.box(), nwo, "bsp_tools", "BSP Tools")
            
    def draw_bsp_tools(self, box, nwo):
        row = box.row()
        col = row.column()
        col.operator('nwo.auto_seam', text='Auto-Seam', icon_value=get_icon_id('seam'))
        col.operator('nwo.cubemap', text='Cubemap Farm', icon_value=get_icon_id("cubemap"))
        
    def draw_importer(self, box, nwo):
        row = box.row()
        col = row.column()
        amf_installed = amf_addon_installed()
        toolset_installed = blender_toolset_installed()
        if amf_installed or toolset_installed:
            col.operator('nwo.import', text="Import Models & Animations", icon='IMPORT').scope = 'amf,jma,jms,collision_model'
        if not toolset_installed:
            col.label(text="Halo Blender Toolset required for import of legacy model and animation files")
            col.operator("nwo.open_url", text="Download", icon="BLENDER").url = BLENDER_TOOLSET
        if not amf_installed:
            col.label(text="AMF Importer required to import amf files")
            col.operator("nwo.open_url", text="Download", icon_value=get_icon_id("amf")).url = AMF_ADDON
            
        col.operator('nwo.import', text="Import Bitmaps", icon='IMAGE_DATA').scope = 'bitmap'
        col.operator('nwo.rename_import', text="Import Animation Renames & Copies", icon_value=get_icon_id("animation_rename"))
        col.operator("nwo.convert_scene", text="Convert Scene", icon='RIGHTARROW')
        
    def draw_rig_tools(self, box, nwo):
        row = box.row()
        col = row.column()
        nwo = self.scene.nwo
        col.use_property_split = True
        col.operator("nwo.fcurve_transfer", icon='GRAPH')
        col.operator('nwo.convert_to_halo_rig', text='Convert to Halo Rig', icon='OUTLINER_OB_ARMATURE')
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
            

    def draw_asset_shaders(self, box, nwo):
        h4 = self.h4
        count, total = get_halo_material_count()
        shader_type = "Material" if h4 else "Shader"
        # if total:
        row = box.row()
        col = row.column()
        col.use_property_split = True
        # col.separator()
        col.label(
            text=f"{count}/{total} {shader_type} tag paths found",
            icon='CHECKMARK' if total == count else 'ERROR'
        )
        row = col.row(align=True)
        col.operator("nwo.shader_finder", text=f"Find Missing {shader_type}s", icon_value=get_icon_id("material_finder"))
        col.operator("nwo.shader_farm", text=f"Batch Build {shader_type}s", icon_value=get_icon_id("material_exporter"))
        col.separator()
        col.operator("nwo.stomp_materials", text=f"Remove Duplicate Materials", icon='X')
        col.operator("nwo.clear_shader_paths", text=f"Clear {shader_type} paths", icon='X')
        col.separator()
        col.operator("nwo.append_foundry_materials", text="Append Special Materials", icon='ADD')
        if h4:
            col.separator()
            col.operator("nwo.open_matman", text="Open Material Tag Viewer", icon_value=get_icon_id("foundation"))


    def draw_help(self):
        box_websites = self.box.box()
        box_websites.label(text="Foundry Documentation")
        col = box_websites.column()
        col.operator("nwo.open_url", text="Documentation", icon_value=get_icon_id("c20_reclaimers")).url = FOUNDRY_DOCS
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
        self.box.operator('nwo.register_icons', icon='FILE_REFRESH')

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
            row.operator("managed_blam.init", text="Install Tag API Dependency", icon='IMPORT').install_only = True
        
        box = self.box.box()
        row = box.row()
        row.label(text="Projects")
        row = box.row()
        rows = 5
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
        col.operator("nwo.project_edit", icon="SETTINGS", text="")
        col.separator()
        col.operator("nwo.project_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.project_move", icon="TRIA_DOWN", text="").direction = 'down'
        row = box.row(align=True, heading="Tool Version")
        row.prop(prefs, "tool_type", expand=True)
        row = box.row(align=True, heading="Default Scene Matrix")
        row.prop(prefs, "scene_matrix", expand=True)
        row = box.row(align=True, heading="Default Object Prefixes")
        row.prop(prefs, "apply_prefix", expand=True)
        row = box.row(align=True)
        row.prop(prefs, "apply_materials", text="Apply Types Operator Updates Materials")
        row = box.row(align=True)
        row.prop(prefs, "apply_empty_display")
        row = box.row(align=True)
        row.prop(prefs, "toolbar_icons_only", text="Foundry Toolbar Icons Only")
        row = box.row(align=True)
        row.prop(prefs, "protect_materials")
        row = box.row(align=True)
        row.prop(prefs, "update_materials_on_shader_path")
        row = box.row(align=True)
        row.prop(prefs, "sync_timeline_range")
        row = box.row(align=True)
        row.prop(prefs, "debug_menu_on_export")
        row = box.row(align=True)
        row.prop(prefs, "debug_menu_on_launch")
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
        if poll_ui("scenario"):
            perm_name = "Layer"
            if is_seam:
                region_name = "Frontfacing BSP"
            else:
                region_name = "BSP"
        elif poll_ui(('model',)) and ob_is_mesh:
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
    bl_label = "Foundry"
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
            thumbnail = os.path.join(p.project_path, p.image_path)
            if os.path.exists(thumbnail):
                icon_id = get_icon_id_in_directory(thumbnail)
            elif p.remote_server_name == "bngtoolsql":
                icon_id = get_icon_id("halo_reach")
            elif p.remote_server_name == "metawins":
                icon_id = get_icon_id("halo_4")
            elif p.remote_server_name == "episql.343i.selfhost.corp.microsoft.com":
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
    bl_description = "Sets the main scene armature as the active object"
    
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'
    
    has_pedestal_control: BoolProperty()
    has_pose_bones: BoolProperty()
    has_aim_control: BoolProperty()
    create_arm: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def execute(self, context):
        if self.create_arm:
            bpy.ops.nwo.add_rig('INVOKE_DEFAULT')
            return {'FINISHED'}
        
        objects = context.view_layer.objects
        scene = context.scene
        if scene.nwo.main_armature:
            arm = scene.nwo.main_armature
        else:
            rigs = [ob for ob in objects if ob.type == 'ARMATURE']
            if not rigs:
                # self.report({'WARNING'}, "No Armature in Scene")
                self.create_arm = True
                return context.window_manager.invoke_props_dialog(self)
            elif len(rigs) > 1:
                self.report({'WARNING'}, "Multiple Armatures found. Please validate rig under Foundry Tools > Rig Tools")
            arm = rigs[0]
        deselect_all_objects()
        arm.hide_set(False)
        arm.hide_select = False
        arm.select_set(True)
        set_active_object(arm)
        self.report({'INFO'}, F"Selected {arm.name}")

        return {'FINISHED'}
    
    def draw(self, context):
        layout = self.layout
        layout.label(text='No Armature in Scene. Press OK to create one')
        layout.prop(self, 'has_pedestal_control', text='With Pedestal Control Bone')
        layout.prop(self, 'has_pose_bones', text='With Aim Bones')
        if self.has_pose_bones:
            layout.prop(self, 'has_aim_control', text='With Aim Control Bone')

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
    bl_options = set()
    bl_description = "Expand a panel"

    panel_str: StringProperty()

    def execute(self, context):
        nwo = context.scene.nwo
        prop = f"{self.panel_str}_expanded"
        setattr(nwo, prop, not getattr(nwo, prop))
        # self.report({"INFO"}, f"Expanded: {prop}")
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

def add_halo_scale_model_button(self, context):
    self.layout.operator(
        NWO_OT_AddScaleModel.bl_idname,
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
    self.layout.operator("nwo.add_rig", text="Halo Armature", icon_value=get_icon_id("rig_creator"))

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
        draw_game_launcher_settings(scene_nwo_halo_launcher, col)

def draw_game_launcher_settings(scene_nwo_halo_launcher, col):
    row = col.row()
    row.prop(scene_nwo_halo_launcher, "use_play")
    col.separator()
    col.prop(scene_nwo_halo_launcher, "insertion_point_index")
    col.prop(scene_nwo_halo_launcher, "initial_zone_set")
    if is_corinth():
        col.prop(scene_nwo_halo_launcher, "initial_bsp")
    col.prop(scene_nwo_halo_launcher, "custom_functions")
    
    col.separator()
    col.prop(scene_nwo_halo_launcher, "show_debugging")
    col.separator()

    col.prop(scene_nwo_halo_launcher, "run_game_scripts")
    col.prop(scene_nwo_halo_launcher, "forge")
    col.prop(scene_nwo_halo_launcher, "megalo_variant")
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
        draw_game_launcher_pruning(scene_nwo_halo_launcher, col)
                
def draw_game_launcher_pruning(scene_nwo_halo_launcher, col):
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
            if nwo_asset_type() == "model":
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
            elif nwo_asset_type() == "scenario":
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
            elif nwo_asset_type() == "sky":
                col.prop(scene_nwo_halo_launcher, "open_model")
                col.prop(scene_nwo_halo_launcher, "open_render_model")
                col.prop(scene_nwo_halo_launcher, "open_scenery")
            elif nwo_asset_type() == "decorator_set":
                col.prop(scene_nwo_halo_launcher, "open_decorator_set")
            elif nwo_asset_type() == "particle_model":
                col.prop(scene_nwo_halo_launcher, "open_particle_model")
            elif nwo_asset_type() == "prefab":
                col.prop(scene_nwo_halo_launcher, "open_prefab")
                col.prop(scene_nwo_halo_launcher, "open_scenario_structure_bsp")
                col.prop(
                    scene_nwo_halo_launcher,
                    "open_scenario_structure_lighting_info",
                )
            elif nwo_asset_type() == "animation":
                col.prop(scene_nwo_halo_launcher, "open_model_animation_graph")
                col.prop(scene_nwo_halo_launcher, "open_frame_event_list")
            elif nwo_asset_type() == "camera_track_set" and scene_nwo_halo_launcher.camera_track_name:
                col.use_property_split = True
                col.prop(scene_nwo_halo_launcher, "camera_track_name", text='Track')


class NWO_HaloLauncher_Foundation(Operator):
    """Launches Foundation"""

    bl_idname = "nwo.launch_foundation"
    bl_label = "Foundation"

    def execute(self, context):
        from .halo_launcher import launch_foundation

        return launch_foundation(context.scene.nwo_halo_launcher, context)


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
            scene.nwo
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
            scene.nwo
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

        return launch_game(True, scene_nwo_halo_launcher, self.filepath.lower(), scene.nwo)

    def invoke(self, context, event):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        if (
            scene_nwo_halo_launcher.game_default == "default"
            or not scene.nwo.is_valid_asset
            or scene.nwo.asset_type != "scenario"
        ):
            self.filepath = get_tags_path()
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = ""
            return self.execute(context)
        
    def draw(self, context):
        layout = self.layout
        scene_nwo_launcher = context.scene.nwo_halo_launcher
        draw_game_launcher_settings(scene_nwo_launcher, layout)
        box = layout.box()
        box.label(text="Pruning")
        draw_game_launcher_pruning(scene_nwo_launcher, box)
        

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

        return launch_game(False, scene_nwo_halo_launcher, self.filepath.lower(), scene.nwo)

    def invoke(self, context, event):
        scene = context.scene
        scene_nwo_halo_launcher = scene.nwo_halo_launcher
        if (
            scene_nwo_halo_launcher.game_default == "default"
            or not scene.nwo.is_valid_asset
            or scene.nwo.asset_type != "scenario"
        ):
            self.filepath = get_tags_path()
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            self.filepath = ""
            return self.execute(context)
        
    def draw(self, context):
        layout = self.layout
        scene_nwo_launcher = context.scene.nwo_halo_launcher
        draw_game_launcher_settings(scene_nwo_launcher, layout)
        box = layout.box()
        box.label(text="Pruning")
        draw_game_launcher_pruning(scene_nwo_launcher, box)


class NWO_HaloLauncherPropertiesGroup(PropertyGroup):
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
    
    def camera_track_items(self, context):
        items = []
        actions = [a for a in bpy.data.actions if a.use_frame_range]
        for a in actions:
            items.append((a.name, a.name, ''))
            
        return items
    
    camera_track_name: EnumProperty(
        options=set(),
        name="Camera Track",
        description="The camera track tag to open",
        items=camera_track_items, 
    )
    
    def bsp_name_items(self, context):
        items = []
        bsps = [b.name for b in context.scene.nwo.regions_table]
        for b in bsps:
            items.append((b, b, ''))
            
        return items

    bsp_name: EnumProperty(
        options=set(),
        name="BSP",
        description="The BSP tag to open",
        items=bsp_name_items,
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
        description="Runs all startup, dormant, and continuous scripts on map load",
        name="TagTest Run Scripts",
        default=True,
    )
    
    forge: BoolProperty(
        name="TagTest Load Forge",
        description="Open the scenario with the Forge gametype loaded if the scenario type is set to multiplayer"
    )
    
    megalo_variant: StringProperty(
        name="Megalo Variant",
        description="Name of the megalo variant to load",
    )
    
    show_debugging: BoolProperty(
        name="Show Debugging/Errors",
        description="If disabled, will turn off debugging text spew and error geometry",
        default=True,
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
        name="Insertion Point",
        default=-1,
        min=-1,
        soft_max=4,
    )

    initial_zone_set: StringProperty(
        options=set(),
        name="Zone Set",
        description="Opens the scenario to the zone set specified. This should match a zone set defined in the .scenario tag",
    )

    initial_bsp: StringProperty(
        options=set(),
        name="BSP",
        description="Opens the scenario to the bsp specified. This should match a bsp name in your blender scene",
    )

    custom_functions: StringProperty(
        options=set(),
        name="Custom",
        description="Name of Blender blender text editor file to get custom init lines from. If no such text exists, instead looks in the root editing kit for an init.txt with this name. If this doesn't exist, then the actual text is used instead",
        default="",
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
        if asset_type == 'camera_track_set':
            return
        scenario = asset_type == "scenario"
        render = poll_ui("model", "sky")
        if (h4 and render) or scenario:
            if scenario:
                lighting_name = "Light Scenario"
            else:
                lighting_name = "Light Model"

            col.prop(scene_nwo_export, "lightmap_structure", text=lighting_name)
            if scene_nwo_export.lightmap_structure:
                if asset_type == "scenario":
                    if h4:
                        col.prop(scene_nwo_export, "lightmap_quality_h4")
                    else:
                        col.prop(scene_nwo_export, "lightmap_quality")
                    if not scene_nwo_export.lightmap_all_bsps:
                        col.prop(scene_nwo_export, "lightmap_specific_bsp")
                    col.prop(scene_nwo_export, "lightmap_all_bsps")
                    if not h4:
                        col.prop(scene_nwo_export, "lightmap_threads")
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
        return context.scene.nwo_export.export_gr2_files and poll_ui(('model', 'scenario', 'prefab', 'animation'))

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

        if scene_nwo.asset_type == "model":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")
            col.prop(scene_nwo_export, "export_collision")
            col.prop(scene_nwo_export, "export_physics")
            col.prop(scene_nwo_export, "export_markers")
            col.prop(scene_nwo_export, "export_skeleton")
            col.prop(scene_nwo_export, "export_animations", expand=True)
        elif scene_nwo.asset_type == "animation":
            col.prop(scene_nwo_export, "export_skeleton")
            col.prop(scene_nwo_export, "export_animations", expand=True)
        elif scene_nwo.asset_type == "scenario":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_structure")
            col.prop(scene_nwo_export, "export_design", text="Design")
        elif scene_nwo.asset_type != "prefab":
            # col.prop(scene_nwo_export, "export_hidden", text="Hidden")
            col.prop(scene_nwo_export, "export_render")

        if scene_nwo.asset_type == "scenario":
            col.prop(scene_nwo_export, "export_all_bsps", expand=True)
        if poll_ui(("model", "scenario", "prefab")):
            if scene_nwo.asset_type == "model":
                txt = "Permutations"
            else:
                txt = "Layers"
            col.prop(scene_nwo_export, "export_all_perms", expand=True, text=txt)


class NWO_HaloExportSettingsFlags(Panel):
    bl_label = "Flags"
    bl_idname = "NWO_PT_HaloExportSettingsFlags"
    bl_space_type = "VIEW_3D"
    bl_parent_id = "NWO_PT_HaloExportSettings"
    bl_region_type = "HEADER"

    @classmethod
    def poll(self, context):
        return context.scene.nwo_export.export_gr2_files and poll_ui(('model', 'scenario', 'prefab', 'sky', 'particle_model', 'decorator_set', 'animation'))

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        scene_nwo = scene.nwo
        scene_nwo_export = scene.nwo_export
        h4 = is_corinth(context)
        scenario = scene_nwo.asset_type == "scenario"
        prefab = scene_nwo.asset_type == "prefab"

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
    # fast_animation_export : BoolProperty(
    #     name="Fast Animation Export",
    #     description="Speeds up exports by ignoring everything but the armature during animation exports. Do not use if your animation relies on helper objects. You should ensure animations begin at frame 0 if using this option",
    #     default=False,
    #     options=set(),
    # )
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
            )
        )
        items.append(
            (
                "__asset__",
                "Asset",
                "Uses the asset defined lightmap settings",
            )
        )
        lightmapper_globals_dir = Path(get_tags_path(), "globals", "lightmapper_settings")
        if lightmapper_globals_dir.exists():
            for file in lightmapper_globals_dir.iterdir():
                if file.suffix == ".lightmapper_globals":
                    name = file.with_suffix('').name
                    items.append((name, name.replace('_', ' ').capitalize(), ''))
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
    
    def lightmap_quality_items(self, context: bpy.types.Context) -> list[bpy.types.EnumProperty]:
        items = []
        lightmapper_globals_tag_path = Path(get_tags_path(), r"globals\lightmapper_globals.lightmapper_globals")
        if not lightmapper_globals_tag_path.exists() or not nwo_globals.mb_active:
            return [("direct_only", "Direct Only", ""),
                    ("draft", "Draft", ""),
                    ("low", "Low", ""),
                    ("medium", "Medium", ""),
                    ("high", "High", ""),
                    ("super_slow", "Super Slow", ""),
                    ("checkerboard", "Checkboard", ""),
                    ("special_v1", "Special V1", ""),
                    ("special_weekend", "Special Weekend", ""),
                    ]
        
        with Tag(path=lightmapper_globals_tag_path) as lightmapper_globals:
            block_quality_settings = lightmapper_globals.tag.SelectField("Block:quality settings")
            for element in block_quality_settings.Elements:
                name: str = element.Fields[0].GetStringData()
                items.append((name, name.replace('_', ' ').capitalize(), ''))
                
        return items

    lightmap_quality: EnumProperty(
        name="Quality",
        items=lightmap_quality_items,
        options=set(),
        description="The lightmap quality you wish to use. You can change and add to this list by editing your lightmapper globals tag found here:\n\ntags\globals\lightmapper_globals.lightmapper_globals",
    )
    lightmap_all_bsps: BoolProperty(
        name="All BSPs",
        default=True,
        options=set(),
    )
    
    def bsp_items(self, context):
        items = []
        bsps = [region.name for region in context.scene.nwo.regions_table]
        for bsp in bsps:
            items.append((bsp, bsp, ''))
        
        return items
    
    lightmap_specific_bsp: EnumProperty(
        name="Specific BSP",
        options=set(),
        items=bsp_items,
    )
    
    def get_lightmap_threads(self):
        cpu_count = multiprocessing.cpu_count()
        if self.get("lightmap_threads", 0):
            if self.lightmap_threads < cpu_count:
                return self['lightmap_threads']
        return multiprocessing.cpu_count()

    def set_lightmap_threads(self, value):
        self['lightmap_threads'] = value
    
    lightmap_threads: IntProperty(
        name="Thread Count",
        description="The number of CPU threads to use when lightmapping",
        get=get_lightmap_threads,
        set=set_lightmap_threads,
        min=1,
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

        # if context.scene.nwo.asset_type == 'scenario':
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
        if context.scene.nwo.asset_type == "scenario":
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
    export_scene = context.scene.nwo
    icons_only = context.preferences.addons["io_scene_foundry"].preferences.toolbar_icons_only
    row.scale_x = 1
    box = row.box()
    box.scale_x = 0.3
    box.label(text="")
    if not export_scene.toolbar_expanded:
        sub_foundry = row.row(align=True)
        sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
    if export_scene.toolbar_expanded:
        error = validate_ek()
        if error is not None:
            sub_error = row.row()
            sub_error.label(text=error, icon="ERROR")
            sub_foundry = row.row(align=True)
            sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
            return

        sub0 = row.row(align=True)
        if context.scene.nwo.shader_sync_active:
            sub0.enabled = False
        else:
            sub0.enabled = True
        sub0.prop(export_scene, "material_sync_rate", text="Sync Rate")
        sub1 = row.row(align=True)
        if context.scene.nwo.shader_sync_active:
            sub1.operator("nwo.material_sync_end", text="Halo Material Sync", icon="PAUSE", depress=True)
        else:
            sub1.operator("nwo.material_sync_start", text="Halo Material Sync", icon="PLAY")
        # sub0.prop(export_scene, "shader_sync_active", text="" if icons_only else "Halo Material Sync", icon_value=get_icon_id("material_exporter"))

def draw_foundry_toolbar(self, context):
    #if context.region.alignment == 'RIGHT':
    foundry_toolbar(self.layout, context)

def foundry_toolbar(layout, context):
    #layout.label(text=" ")
    row = layout.row()
    export_scene = context.scene.nwo
    if export_scene.storage_only:
        row.label(text='Scene is used by Foundry for object storage', icon_value=get_icon_id('foundry'))
        return
    icons_only = get_prefs().toolbar_icons_only
    row.scale_x = 1
    box = row.box()
    box.scale_x = 0.3
    box.label(text="")
    if not export_scene.toolbar_expanded:
        sub_foundry = row.row(align=True)
        sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
    if export_scene.toolbar_expanded:
        sub_project = row.row(align=True)
        if nwo_globals.mb_active:
            sub_project.enabled = False
        sub_project.menu(NWO_ProjectChooserMenu.bl_idname, text="", icon_value=project_icon(context))
        error = validate_ek()
        if error is not None:
            sub_error = row.row()
            sub_error.label(text=error, icon="ERROR")
            sub_foundry = row.row(align=True)
            if error.startswith("Tag API"):
                sub_foundry.operator("managed_blam.init", text="Install Tag API")
            sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
            return
        
        # sub_game_version = row.row(align=True)
        # sub_game_version.label(text="", icon_value=project_game_icon(context))

        sub0 = row.row(align=True)
        if export_scene.is_valid_asset and export_scene.asset_type != 'resource':
            sub0.operator(
                "nwo.export_quick",
                text="" if icons_only else "Export",
                icon_value=get_icon_id("quick_export"),
            )
            sub0.popover(panel="NWO_PT_HaloExportSettings", text="")
        elif export_scene.sidecar_path:
            sub0.operator(
                "nwo.new_asset",
                text=f"Copy {export_scene.asset_name}",
                icon_value=get_icon_id("halo_asset"),
            ) 
        else:
            sub0.operator(
                "nwo.new_asset",
                text=f"New Asset",
                icon_value=get_icon_id("halo_asset"),
            ) 
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
        sub_foundry.prop(export_scene, "toolbar_expanded", text="", icon_value=get_icon_id("foundry"))
        
def menu_func_import(self, context):
    self.layout.operator(NWO_Import.bl_idname, text="Halo Foundry Import")

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
    NWO_OT_HideObjectType,
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
    NWO_ShaderFinder_FindSingle,
    NWO_ShaderFinder_Find,
    NWO_OT_AddRig,
    NWO_ListMaterialShaders,
    NWO_Shader_BuildSingle,
    NWO_ShaderPropertiesGroup,
    NWO_OT_AddScaleModel,
    NWO_JoinHalo,
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
    NWO_OT_ConvertScene,
    NWO_SetDefaultSky,
    NWO_SetSky,
    NWO_NewSky,
    NWO_BSPContextMenu,
    NWO_BSPInfo,
    NWO_BSPSetLightmapRes,
    NWO_ShaderToNodes,
    NWO_AppendFoundryMaterials,
    NWO_ClearShaderPaths,
    NWO_UpdateSets,
    NWO_ScaleScene,
    NWO_OT_ConvertToHaloRig,
    NWO_OT_Cubemap,
    NWO_OT_LoadTemplate,
    NWO_OT_RemoveExistingZoneSets,
    NWO_OT_Lightmap,
    NWO_UL_AnimationCopies,
    NWO_OT_AnimationCopyAdd,
    NWO_OT_AnimationCopyRemove,
    NWO_OT_AnimationCopyMove,
    NWO_UL_AnimationBlendAxis,
    NWO_OT_AnimationBlendAxisAdd,
    NWO_OT_AnimationBlendAxisRemove,
    NWO_OT_AnimationBlendAxisMove,
    NWO_UL_AnimationComposites,
    NWO_OT_AnimationCompositeAdd,
    NWO_OT_AnimationCompositeRemove,
    NWO_OT_AnimationCompositeMove,
    NWO_UL_AnimationDeadZone,
    NWO_OT_AnimationDeadZoneAdd,
    NWO_OT_AnimationDeadZoneRemove,
    NWO_OT_AnimationDeadZoneMove,
    NWO_UL_AnimationPhaseSet,
    NWO_OT_AnimationPhaseSetAdd,
    NWO_OT_AnimationPhaseSetRemove,
    NWO_OT_AnimationPhaseSetMove,
    NWO_UL_AnimationLeaf,
    NWO_OT_AnimationLeafAdd,
    NWO_OT_AnimationLeafRemove,
    NWO_OT_AnimationLeafMove,
    NWO_OT_FcurveTransfer,
    NWO_OT_RenameImporter,
    NWO_OT_NewAsset,
)

def register():
    for clshalo in classeshalo:
        bpy.utils.register_class(clshalo)

    bpy.types.VIEW3D_HT_tool_header.append(draw_foundry_toolbar)
    bpy.types.NODE_HT_header.append(draw_foundry_nodes_toolbar)
    bpy.types.VIEW3D_MT_mesh_add.append(add_halo_scale_model_button)
    # bpy.types.VIEW3D_MT_light_add.append(add_halo_light_button)
    bpy.types.VIEW3D_MT_armature_add.append(add_halo_armature_buttons)
    bpy.types.OUTLINER_HT_header.append(create_halo_collection)
    bpy.types.VIEW3D_MT_object.append(add_halo_join)
    bpy.types.Scene.nwo_halo_launcher = PointerProperty(
        type=NWO_HaloLauncherPropertiesGroup,
        name="Halo Launcher",
        description="Launches stuff",
    )
    bpy.types.Scene.nwo_export = PointerProperty(
        type=NWO_HaloExportPropertiesGroup, name="Halo Export", description=""
    )
    bpy.types.Scene.nwo_shader_build = PointerProperty(
        type=NWO_ShaderPropertiesGroup,
        name="Halo Shader Export",
        description="",
    )
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.VIEW3D_HT_tool_header.remove(draw_foundry_toolbar)
    bpy.types.NODE_HT_header.remove(draw_foundry_nodes_toolbar)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_halo_scale_model_button)
    # bpy.types.VIEW3D_MT_light_add.remove(add_halo_light_button)
    bpy.types.VIEW3D_MT_armature_add.remove(add_halo_armature_buttons)
    bpy.types.VIEW3D_MT_object.remove(add_halo_join)
    bpy.types.OUTLINER_HT_header.remove(create_halo_collection)
    del bpy.types.Scene.nwo_halo_launcher
    del bpy.types.Scene.nwo_export
    del bpy.types.Scene.nwo_shader_build
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)


if __name__ == "__main__":
    register()

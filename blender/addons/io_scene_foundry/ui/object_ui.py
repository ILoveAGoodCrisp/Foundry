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

import os
from io_scene_foundry.icons import get_icon_id
from io_scene_foundry.managed_blam.globals import GlobalsTag
from .templates import NWO_Op, NWO_PropPanel
from ..utils.nwo_utils import (
    bpy_enum_list,
    export_objects_mesh_only,
    export_objects_no_arm,
    is_linked,
    is_corinth,
    is_marker,
    is_mesh,
    sort_alphanum,
    true_permutation,
    true_region,
    poll_ui,
)

from bpy.types import Context, Menu, UIList, Operator
from bpy.props import EnumProperty, StringProperty
import bpy

global_mats_items = []

# SETS MENUS
class NWO_RegionsMenu(Menu):
    bl_label = "Add Mesh Property"
    bl_idname = "NWO_MT_Regions"

    @classmethod
    def poll(self, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        region_names = [region.name for region in context.scene.nwo.regions_table]
        for r_name in region_names:
            layout.operator("nwo.region_assign_single", text=r_name).name = r_name

        layout.operator("nwo.region_add", text="New BSP" if is_scenario else "New Region", icon='ADD').set_object_prop = True

class NWO_FaceRegionsMenu(Menu):
    bl_label = "Add Mesh Property"
    bl_idname = "NWO_MT_FaceRegions"

    @classmethod
    def poll(self, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        region_names = [region.name for region in context.scene.nwo.regions_table]
        for r_name in region_names:
            layout.operator("nwo.face_region_assign_single", text=r_name).name = r_name

        layout.operator("nwo.face_region_add", text="New Region", icon='ADD').set_object_prop = True

class NWO_SeamBackfaceMenu(NWO_RegionsMenu):
    bl_idname = "NWO_MT_SeamBackface"

    def draw(self, context):
        layout = self.layout
        region_names = [region.name for region in context.scene.nwo.regions_table if region.name != true_region(context.object.nwo)]
        if not region_names:
            layout.label(text="Only one BSP in scene. At least two required to use seams", icon="ERROR")
        for r_name in region_names:
            layout.operator("nwo.seam_backface_assign_single", text=r_name).name = r_name

class NWO_PermutationsMenu(Menu):
    bl_label = "Add Mesh Property"
    bl_idname = "NWO_MT_Permutations"

    @classmethod
    def poll(self, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        is_scenario = context.scene.nwo.asset_type == 'SCENARIO'
        permutation_names = [permutation.name for permutation in context.scene.nwo.permutations_table]
        for p_name in permutation_names:
            layout.operator("nwo.permutation_assign_single", text=p_name).name = p_name

        layout.operator("nwo.permutation_add", text="New BSP Layer" if is_scenario else "New Permutation", icon='ADD').set_object_prop = True

class NWO_MarkerPermutationsMenu(Menu):
    bl_label = "Add Mesh Property"
    bl_idname = "NWO_MT_MarkerPermutations"

    @classmethod
    def poll(self, context):
        return context.object

    def draw(self, context):
        layout = self.layout
        permutation_names = [permutation.name for permutation in context.scene.nwo.permutations_table]
        for p_name in permutation_names:
            layout.operator("nwo.marker_perm_add", text=p_name).name = p_name

# Object Type Menu
class NWO_MeshTypes(Menu):
    bl_label = "Mesh Type"
    bl_idname = "NWO_MT_MeshTypes"
    bl_description = "Mesh Type"
    
    @classmethod
    def poll(cls, context):
        return context.object and is_mesh(context.object)
    
    def draw(self, context):
        layout = self.layout
        h4 = is_corinth(context)
        if poll_ui("MODEL"):
            layout.operator('nwo.apply_type_mesh_single', text='Render', icon_value=get_icon_id('model')).m_type = 'render'
            layout.operator('nwo.apply_type_mesh_single', text='Collision', icon_value=get_icon_id('collider')).m_type = 'collision'
            layout.operator('nwo.apply_type_mesh_single', text='Physics', icon_value=get_icon_id('physics')).m_type = 'physics'
            layout.operator('nwo.apply_type_mesh_single', text='Instanced Object', icon_value=get_icon_id('instance')).m_type = 'io'
        elif poll_ui("SCENARIO"):
            layout.operator('nwo.apply_type_mesh_single', text='Instanced Geometry', icon_value=get_icon_id('instance')).m_type = 'instance'
            layout.operator('nwo.apply_type_mesh_single', text='Structure', icon_value=get_icon_id('structure')).m_type = 'structure'
            layout.operator('nwo.apply_type_mesh_single', text='Collision', icon_value=get_icon_id('collider')).m_type = 'collision'
            layout.operator('nwo.apply_type_mesh_single', text='Seam', icon_value=get_icon_id('seam')).m_type = 'seam'
            layout.operator('nwo.apply_type_mesh_single', text='Portal', icon_value=get_icon_id('portal')).m_type = 'portal'
            layout.operator('nwo.apply_type_mesh_single', text='Lightmap Only', icon_value=get_icon_id('lightmap')).m_type = 'lightmap_only'
            layout.operator('nwo.apply_type_mesh_single', text='Water Surface', icon_value=get_icon_id('water')).m_type = 'water_surface'
            layout.operator('nwo.apply_type_mesh_single', text='Water Physics Volume', icon_value=get_icon_id('water_physics')).m_type = 'water_physics'
            layout.operator('nwo.apply_type_mesh_single', text='Soft Ceiling Volume', icon_value=get_icon_id('soft_ceiling')).m_type = 'soft_ceiling'
            layout.operator('nwo.apply_type_mesh_single', text='Soft Kill Volume', icon_value=get_icon_id('soft_kill')).m_type = 'soft_kill'
            layout.operator('nwo.apply_type_mesh_single', text='Slip Surface Volume', icon_value=get_icon_id('slip_surface')).m_type = 'slip_surface'
            if h4:
                layout.operator('nwo.apply_type_mesh_single', text='Lightmap Exclusion Volume', icon_value=get_icon_id('lightmap_exclude')).m_type = 'lightmap'
                layout.operator('nwo.apply_type_mesh_single', text='Texture Streaming Volume', icon_value=get_icon_id('streaming')).m_type = 'streaming'
            else:
                layout.operator('nwo.apply_type_mesh_single', text='Rain Blocker', icon_value=get_icon_id('rain_blocker')).m_type = 'rain_blocker'
                layout.operator('nwo.apply_type_mesh_single', text='Rain Sheet', icon_value=get_icon_id('rain_sheet')).m_type = 'rain_sheet'
                layout.operator('nwo.apply_type_mesh_single', text='Pathfinding Cutout Volume', icon_value=get_icon_id('cookie_cutter')).m_type = 'cookie_cutter'
                layout.operator('nwo.apply_type_mesh_single', text='Fog Sheet', icon_value=get_icon_id('fog')).m_type = 'fog'
        elif poll_ui("PREFAB"):
            layout.operator('nwo.apply_type_mesh_single', text='Instanced Geometry', icon_value=get_icon_id('instance')).m_type = 'instance'
            layout.operator('nwo.apply_type_mesh_single', text='Collision', icon_value=get_icon_id('collider')).m_type = 'collision'
            layout.operator('nwo.apply_type_mesh_single', text='Lightmap Only', icon_value=get_icon_id('lightmap')).m_type = 'lightmap_only'
            
class NWO_MarkerTypes(Menu):
    bl_label = "Marker Type"
    bl_idname = "NWO_MT_MarkerTypes"
    
    @classmethod
    def poll(self, context):
        return context.object and is_marker(context.object)
    
    def draw(self, context):
        layout = self.layout
        h4 = is_corinth(context)
        if poll_ui(("MODEL", "SKY")):
            layout.operator('nwo.apply_type_marker_single', text='Model Marker', icon_value=get_icon_id('marker')).m_type = 'model'
            layout.operator('nwo.apply_type_marker_single', text='Effects', icon_value=get_icon_id('effects')).m_type = 'effects'
            if poll_ui("MODEL"):
                layout.operator('nwo.apply_type_marker_single', text='Garbage', icon_value=get_icon_id('garbage')).m_type = 'garbage'
                layout.operator('nwo.apply_type_marker_single', text='Hint', icon_value=get_icon_id('hint')).m_type = 'hint'
                layout.operator('nwo.apply_type_marker_single', text='Pathfinding Sphere', icon_value=get_icon_id('pathfinding_sphere')).m_type = 'pathfinding_sphere'
                layout.operator('nwo.apply_type_marker_single', text='Physics Constraint', icon_value=get_icon_id('physics_constraint')).m_type = 'physics_constraint'
                layout.operator('nwo.apply_type_marker_single', text='Target', icon_value=get_icon_id('target')).m_type = 'target'
                if h4:
                    layout.operator('nwo.apply_type_marker_single', text='Airprobe', icon_value=get_icon_id('airprobe')).m_type = 'airprobe'
        elif poll_ui(("SCENARIO", "PREFAB")):
            layout.operator('nwo.apply_type_marker_single', text='Structure Marker', icon_value=get_icon_id('marker')).m_type = 'model'
            layout.operator('nwo.apply_type_marker_single', text='Game Object', icon_value=get_icon_id('game_object')).m_type = 'game_instance'
            if h4:
                layout.operator('nwo.apply_type_marker_single', text='Airprobe', icon_value=get_icon_id('airprobe')).m_type = 'airprobe'
                layout.operator('nwo.apply_type_marker_single', text='Light Cone', icon_value=get_icon_id('light_cone')).m_type = 'lightcone'

# FACE LEVEL FACE PROPS

class NWO_UL_FaceMapProps(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            if item:
                layout.prop(item, "name", text="", emboss=False, icon_value=495)
            else:
                layout.label(text="", translate=False, icon_value=icon)
        elif self.layout_type == "GRID":
            layout.alignment = "CENTER"
            layout.label(text="", icon_value=icon)

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
    ob_nwo = ob.data.nwo

    match option:
        case "_connected_geometry_face_sides_one_sided_transparent":
            ob_nwo.face_sides_active = bool_var
            ob_nwo.face_sides_ui = (
                "_connected_geometry_face_sides_one_sided_transparent"
            )
        case "ladder":
            ob_nwo.ladder_active = bool_var
        case "slip_surface":
            ob_nwo.slip_surface_active = bool_var
        case "decal_offset":
            ob_nwo.decal_offset_active = bool_var
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
    
    @classmethod
    def poll(cls, context):
        return context.object and is_mesh(context.object)

    def draw(self, context):
        layout = self.layout
        nwo = context.object.nwo
        if poll_ui(("SCENARIO", "PREFAB")):
            # if nwo.mesh_type_ui == "_connected_geometry_mesh_type_structure":
            #     layout.operator(
            #         "nwo.add_mesh_property", text="Sky"
            #     ).options = "_connected_geometry_face_type_sky"
            # if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure"):
            #     layout.operator(
            #         "nwo.add_mesh_property", text="Seam Sealer"
            #     ).options = "_connected_geometry_face_type_seam_sealer"
            if nwo.mesh_type_ui in ("_connected_geometry_mesh_type_default", "_connected_geometry_mesh_type_structure", "_connected_geometry_mesh_type_lightmap_only"):
                layout.operator(
                    "nwo.add_mesh_property", text="Emissive"
                ).options = "emissive"
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
        return context.object and is_mesh(context.object)

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


class NWO_MeshPropRemove(Operator):
    """Removes a mesh property"""

    bl_idname = "nwo.remove_mesh_property"
    bl_label = "Remove"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object

    options: EnumProperty(
        items=[
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
            ("lightmap_translucency_tint_color", "Translucency Tint Color", ""),
            ("lightmap_lighting_from_both_sides", "Lighting from Both Sides", ""),
            ("emissive", "Emissive", ""),
        ]
    )

    def execute(self, context):
        toggle_active(context, self.options, False)
        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_MeshPropAddLightmap(NWO_MeshPropAdd):
    bl_idname = "nwo.add_mesh_property_lightmap"
    bl_label = "Add"

    options: EnumProperty(
        items=[
            ("lightmap_additive_transparency", "Transparency", ""),
            ("lightmap_resolution_scale", "Resolution Scale", ""),
            ("lightmap_type", "Lightmap Type", ""),
            (
                "lightmap_translucency_tint_color",
                "Translucency Tint Color",
                "",
            ),
            (
                "lightmap_lighting_from_both_sides",
                "Lighting from Both Sides",
                "",
            ),
        ]
    )

# LIST SYSTEMS
# ------------------------------------------------


class NWO_GlobalMaterialMenu(Menu):
    bl_label = "Add Collision Material"
    bl_idname = "NWO_MT_AddGlobalMaterial"

    def draw(self, context):
        layout = self.layout
        if poll_ui(("MODEL", "SKY")):
            layout.operator_menu_enum(
                "nwo.global_material_regions_list",
                property="region",
                text="From Region",
            )

        if poll_ui(("SCENARIO", "PREFAB", "MODEL")):
            layout.operator(
                "nwo.global_material_globals",
                text="From Globals",
                icon="VIEWZOOM",
            )


class NWO_RegionList(NWO_Op):
    bl_idname = "nwo.region_list"
    bl_label = "Region List"
    bl_description = "Applies a region to the selected object"

    def regions_items(self, context):
        # get scene regions
        items = []
        for r in context.scene.nwo.regions_table:
            items.append((r.name, r.name, ''))
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
        context.object.data.nwo.face_global_material_ui = self.region
        return {"FINISHED"}
    
class NWO_GlobalMaterialGlobals(NWO_RegionList):
    bl_idname = "nwo.global_material_globals"
    bl_label = "Collision Material List"
    bl_description = "Applies a global material to the selected object"
    bl_property = "material"
    
    face_level: bpy.props.BoolProperty()

    def get_materials(self, context):
        global global_mats_items
        if global_mats_items:
            return global_mats_items
        global_mats_items = []
        with GlobalsTag(path=os.path.join('globals', 'globals.globals'), tag_must_exist=True) as globals:
            global_materials = globals.get_global_materials()

        global_materials.sort()
        for mat in global_materials:
            global_mats_items.append((mat, mat, ""))

        return global_mats_items
            
    material : EnumProperty(
        items=get_materials,
    )

    def execute(self, context):
        nwo = context.object.data.nwo
        if self.face_level:
            nwo.face_props[nwo.face_props_index].face_global_material_ui = self.material
        else:
            nwo.face_global_material_ui = self.material
        context.area.tag_redraw()
        return {"FINISHED"}
    
    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}

    def draw(self, context: Context):
        layout = self.layout
        layout.prop(self, 'material', text="Collision Material")

class NWO_GlobalMaterialList(NWO_Op):
    bl_idname = "nwo.global_material_list"
    bl_label = "Collision Material List"
    bl_description = "Applies a Collision Material to the selected object"

    def global_material_items(self, context):
        # get scene regions
        global_materials = ["default"]
        for ob in export_objects_mesh_only():
            global_material = ob.data.nwo.face_global_material_ui
            if (
                global_material != ""
                and global_material not in global_materials
                and global_material
            ):
                global_materials.append(global_material)
            # also need to loop through face props
            if ob.type == "MESH":
                for face_prop in ob.data.nwo.face_props:
                    if (
                        face_prop.face_global_material_ui != ""
                        and face_prop.face_global_material_override
                        and face_prop.face_global_material_ui not in global_materials
                    ):
                        global_materials.append(face_prop.face_global_material_ui)

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
        context.object.data.nwo.face_global_material_ui = self.global_material
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
            bsp = true_region(ob.nwo)
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
        self_bsp = true_region(context.object.nwo)
        bsps = []
        for ob in export_objects_no_arm():
            bsp = true_region(ob.nwo)
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
    bl_label = "Foundry Bone Properties"
    bl_idname = "NWO_PT_BoneDetailsPanel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "bone"

    @classmethod
    def poll(cls, context):
        return context.bone

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
        # col.prop(bone_nwo, "name_override")

        # col.separator()

        # col.prop(bone_nwo, "frame_id1", text="Frame ID 1")
        # col.prop(bone_nwo, "frame_id2", text="Frame ID 2")

        # col.separator()

        col.prop(bone_nwo, "object_space_node", text="Object Space Offset Node")
        col.prop(
            bone_nwo,
            "replacement_correction_node",
            text="Replacement Correction Node",
        )
        col.prop(bone_nwo, "fik_anchor_node", text="Forward IK Anchor Node")

## MARKER PERM UI LIST
class NWO_UL_MarkerPermutations(UIList):
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        layout.label(text=item.name, icon_value=get_icon_id("permutation"))

class NWO_List_Add_MarkerPermutation(Operator):
    bl_idname = "nwo.marker_perm_add"
    bl_label = "Add"
    bl_description = "Add a new permutation"
    bl_options = {"UNDO"}

    name: StringProperty()

    def execute(self, context):
        ob = context.object
        nwo = ob.nwo
        for perm in nwo.marker_permutations:
            if perm.name == self.name:
                return {"CANCELLED"}
            
        bpy.ops.uilist.entry_add(
            list_path="object.nwo.marker_permutations",
            active_index_path="object.nwo.marker_permutations_index",
        )

        nwo.marker_permutations[nwo.marker_permutations_index].name = self.name
        context.area.tag_redraw()

        return {"FINISHED"}


class NWO_List_Remove_MarkerPermutation(Operator):
    bl_idname = "nwo.marker_perm_remove"
    bl_label = "Remove"
    bl_description = "Remove a permutation from the list."
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        ob = context.object
        return ob and ob.nwo.marker_permutations

    def execute(self, context):
        ob = context.object
        nwo = ob.nwo
        nwo.marker_permutations.remove(nwo.marker_permutations_index)
        if nwo.marker_permutations_index > len(nwo.marker_permutations) - 1:
            nwo.marker_permutations_index += -1
        return {"FINISHED"}
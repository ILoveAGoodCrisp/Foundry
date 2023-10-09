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
import bpy
from io_scene_foundry.icons import get_icon_id
from io_scene_foundry.tools.collection_apply import NWO_ApplyCollectionMenu, NWO_ApplyCollectionType, NWO_PermutationListCollection, NWO_RegionListCollection

from io_scene_foundry.ui.collection_properties import NWO_CollectionPropertiesGroup
from io_scene_foundry.utils.nwo_constants import VALID_MARKERS, VALID_MESHES

# from bpy.types import ASSET_OT_open_containing_blend_file as op_blend_file
from .templates import NWO_Op
from bpy.props import (
    PointerProperty,
)

# import classes from other files

from .face_ui import (
    NWO_FaceLayerAddMenu,
    NWO_FacePropAddMenu,
    NWO_UL_FacePropList,
    NWO_EditMode,
    NWO_FaceLayerAdd,
    NWO_FaceLayerRemove,
    NWO_FaceLayerAssign,
    NWO_FaceLayerSelect,
    NWO_FaceLayerMove,
    NWO_FaceLayerAddFaceMode,
    NWO_FaceLayerAddFlags,
    NWO_FaceLayerAddLightmap,
    NWO_FacePropRemove,
    NWO_FacePropAdd,
    NWO_FacePropAddFaceMode,
    NWO_FacePropAddFlags,
    NWO_FacePropAddLightmap,
    NWO_FaceLayerColorAll,
    NWO_FaceLayerColor,
    NWO_RegionListFace,
    NWO_GlobalMaterialRegionListFace,
    NWO_GlobalMaterialListFace,
    NWO_GlobalMaterialMenuFace,
)

from .face_properties import NWO_FaceProperties_ListItems

from .object_properties import (
    NWO_MarkerPermutationItems,
    NWO_MeshPropertiesGroup,
    NWO_ObjectPropertiesGroup,
    NWO_LightPropertiesGroup,
    NWO_BonePropertiesGroup,
)

from .object_ui import (
    NWO_FaceRegionsMenu,
    NWO_GlobalMaterialGlobals,
    NWO_MarkerPermutationsMenu,
    NWO_PermutationsMenu,
    NWO_RegionsMenu,
    NWO_SeamBackfaceMenu,
    NWO_UL_MarkerPermutations,
    NWO_List_Add_MarkerPermutation,
    NWO_List_Remove_MarkerPermutation,
    NWO_UL_FaceMapProps,
    NWO_FaceDefaultsToggle,
    NWO_MeshPropAddMenu,
    NWO_MeshPropAdd,
    NWO_MeshPropRemove,
    NWO_MeshPropAddFaceMode,
    NWO_MeshPropAddFaceSides,
    NWO_MeshPropAddFlags,
    NWO_MeshPropAddLightmap,
    NWO_MeshPropAddMaterialLighting,
    NWO_MeshPropAddMisc,
    NWO_GlobalMaterialMenu,
    NWO_RegionList,
    NWO_GlobalMaterialRegionList,
    NWO_GlobalMaterialList,
    NWO_PermutationList,
    NWO_BSPList,
    NWO_BSPListSeam,
    NWO_MasterInstance,
    NWO_BoneProps,
    # NWO_LightProps,
    # NWO_LightPropsCycles,
)

from .materials_ui import NWO_MaterialOpenTag

from .materials_properties import NWO_MaterialPropertiesGroup

from .animation_properties import (
    NWO_UL_AnimProps_Events,
    NWO_List_Add_Animation_Event,
    NWO_List_Remove_Animation_Event,
    NWO_Animation_ListItems,
    NWO_AnimationRenamesItems,
    NWO_ActionPropertiesGroup,
    NWO_List_Remove_Animation_Event,
    NWO_AnimationRenamesItems,
)

from .animation_ui import (
    NWO_NewAnimation,
    NWO_DeleteAnimation,
    NWO_UnlinkAnimation,
    NWO_List_Add_Animation_Rename,
    NWO_UL_AnimationRename,
    NWO_List_Remove_Animation_Rename,
)

from .scene_properties import NWO_Asset_ListItems, NWO_BSP_ListItems, NWO_GlobalMaterial_ListItems, NWO_Permutations_ListItems, NWO_Regions_ListItems, NWO_ScenePropertiesGroup

from .scene_ui import NWO_SetUnitScale, NWO_AssetMaker, NWO_UL_Permutations, NWO_UL_Regions

from .viewport_ui import (
    NWO_ApplyTypeMesh,
    NWO_MT_PIE_ApplyTypeMesh,
    NWO_PIE_ApplyTypeMesh,
    NWO_ApplyTypeMarker,
    NWO_MT_PIE_ApplyTypeMarker,
    NWO_PIE_ApplyTypeMarker,
)

from .preferences_ui import (
    H2AMPEKLocationPath,
    H4EKLocationPath,
    HREKLocationPath,
    NWO_Project_ListItems,
    NWO_ProjectAdd,
    NWO_ProjectEditDisplayName,
    NWO_ProjectMove,
    NWO_ProjectRemove,
    NWO_UL_Projects,
    ToolkitLocationPreferences,
)

from .image_properties import NWO_ImagePropertiesGroup

mesh_type_items = [
    (
        "_connected_geometry_mesh_type_boundary_surface",
        "Boundary Surface",
        "Used in structure_design tags for soft_kill, soft_ceiling, and slip_sufaces. Only use when importing to a structure_design tag. Can be forced on with the prefixes: '+soft_ceiling', 'soft_kill', 'slip_surface'",
    ),  # 0
    (
        "_connected_geometry_mesh_type_collision",
        "Collision",
        "Sets this mesh to have collision geometry only. Can be forced on with the prefix: '@'",
    ),  # 1
    (
        "_connected_geometry_mesh_type_cookie_cutter",
        "Cookie Cutter",
        "Defines an area which ai will pathfind around. Can be forced on with the prefix: '+cookie'",
    ),  # 2
    (
        "_connected_geometry_mesh_type_decorator",
        "Decorator",
        "Use this when making a decorator. Allows for different LOD levels to be set",
    ),  # 3
    (
        "_connected_geometry_mesh_type_default",
        "Default",
        "By default this mesh type will be treated as render only geometry in models, and render + bsp collision geometry in structures",
    ),  # 4
    (
        "_connected_geometry_mesh_type_poop",
        "Instanced Geometry",
        "Writes this mesh to a json file as instanced geometry. Can be forced on with the prefix: '%'",
    ),  # 5
    ("_connected_geometry_mesh_type_poop_marker", "Instanced Marker", ""),  # 6
    (
        "_connected_geometry_mesh_type_poop_rain_blocker",
        "Rain Occluder",
        "Rain is not rendered in the the volume this mesh occupies.",
    ),  # 7
    (
        "_connected_geometry_mesh_type_poop_vertical_rain_sheet",
        "Vertical Rain Sheet",
        "",
    ),  # 8
    (
        "_connected_geometry_mesh_type_lightmap_region",
        "Lightmap Region",
        "Defines an area of a structure which should be lightmapped. Can be referenced when lightmapping",
    ),  # 9
    (
        "_connected_geometry_mesh_type_object_instance",
        "Object Instance",
        "Writes this mesh to the json as an instanced object. Can be forced on with the prefix: '+flair'",
    ),  # 10
    (
        "_connected_geometry_mesh_type_physics",
        "Physics",
        "Sets this mesh to have physics geometry only. Can be forced on with the prefix: '$'",
    ),  # 11
    (
        "_connected_geometry_mesh_type_planar_fog_volume",
        "Planar Fog Volume",
        "Defines an area for a fog volume. The same logic as used for portals should be applied to these.  Can be forced on with the prefix: '+fog'",
    ),  # 12
    (
        "_connected_geometry_mesh_type_portal",
        "Portal",
        "Cuts up a bsp and defines clusters. Can be forced on with the prefix '+portal'",
    ),  # 13
    (
        "_connected_geometry_mesh_type_seam",
        "Seam",
        "Defines where two bsps meet. Its name should match the name of the bsp its in. Can be forced on with the prefix '+seam'",
    ),  # 14
    (
        "_connected_geometry_mesh_type_water_physics_volume",
        "Water Physics Volume",
        "Defines an area where water physics should apply. Only use when importing to a structure_design tag. Can be forced on with the prefix: '+water'",
    ),  # 15
    (
        "_connected_geometry_mesh_type_water_surface",
        "Water Surface",
        "Defines a mesh as a water surface. Can be forced on with the prefix: '",
    ),  # 16
    ("_connected_geometry_mesh_type_obb_volume", "OBB Volume", ""),  # 17
    ("_connected_geometry_mesh_type_volume", "Volume", ""),
    # These go unused in menus, and are instead set at export
    ("_connected_geometry_mesh_type_poop_collision", "Poop Collision", ""),
    ("_connected_geometry_mesh_type_poop_physics", "Poop Physics", ""),
    ("_connected_geometry_mesh_type_render", "Render", ""),
    ("_connected_geometry_mesh_type_structure", "Structure", ""),
    ("_connected_geometry_mesh_type_default", "Default", ""),
]

volume_type_items = [
    ("_connected_geometry_volume_type_soft_ceiling", "Soft Celing", ""),
    ("_connected_geometry_volume_type_soft_kill", "Soft Kill", ""),
    ("_connected_geometry_volume_type_slip_surface", "Slip Surface", ""),
    ("_connected_geometry_volume_type_water_physics", "Water Physics", ""),
    (
        "_connected_geometry_volume_type_lightmap_exclude",
        "Lightmap Exclusion",
        "",
    ),
    ("_connected_geometry_volume_type_lightmap_region", "Lightmap Region", ""),
    ("_connected_geometry_volume_type_streaming", "Streaming", ""),
]

marker_type_items = [
    (
        "_connected_geometry_marker_type_model",
        "Model",
        "Default marker type. Defines render_model markers for models, and structure markers for bsps",
    ),
    (
        "_connected_geometry_marker_type_effects",
        "Effects",
        "Marker for effects only.",
    ),
    (
        "_connected_geometry_marker_type_game_instance",
        "Game Object",
        "Game Instance marker. Used to create an instance of a tag in the bsp. Can be set with the prefix: ?",
    ),
    (
        "_connected_geometry_marker_type_garbage",
        "Garbage",
        "marker to define position that garbage pieces should be created",
    ),
    ("_connected_geometry_marker_type_hint", "Hint", "Used for ai hints"),
    (
        "_connected_geometry_marker_type_pathfinding_sphere",
        "Pathfinding Sphere",
        "Used to create ai pathfinding spheres",
    ),
    (
        "_connected_geometry_marker_type_physics_constraint",
        "Physics Constraint",
        "Used to define various types of physics constraints",
    ),
    (
        "_connected_geometry_marker_type_physics_hinge_constraint",
        "Hinge Constraint",
        "Used to define various types of physics constraints",
    ),
    (
        "_connected_geometry_marker_type_physics_socket_constraint",
        "Socket Constraint",
        "Used to define various types of physics constraints",
    ),
    (
        "_connected_geometry_marker_type_target",
        "Target",
        "Defines the markers used in a model's targets'",
    ),
    (
        "_connected_geometry_marker_type_water_volume_flow",
        "Water Volume Flow",
        "Used to define water flow for water physics volumes. For structure_design tags only",
    ),
    (
        "_connected_geometry_marker_type_airprobe",
        "Airprobe",
        "Airprobes tell the game how to handle static lighting on dynamic objects",
    ),
    (
        "_connected_geometry_marker_type_envfx",
        "Environment Effect",
        "Plays an effect on this point in the structure",
    ),
    (
        "_connected_geometry_marker_type_lightCone",
        "Light Cone",
        "Creates a light cone with the defined parameters",
    ),
    ("_connected_geometry_marker_type_prefab", "Prefab", ""),
    ("_connected_geometry_marker_type_cheap_light", "Cheap Light", ""),
    ("_connected_geometry_marker_type_light", "Light", ""),
    ("_connected_geometry_marker_type_falling_leaf", "Falling Leaf", ""),
]


def add_asset_open_in_foundry(self, context):
    self.layout.operator(NWO_OpenAssetFoundry.bl_idname, text="Open in Foundry")


class NWO_OpenAssetFoundry(NWO_Op):
    bl_idname = "nwo.open_asset_foundry"
    bl_label = "Open in Foundry"
    bl_options = {"REGISTER"}

    _process = None  # Optional[subprocess.Popen]

    @classmethod
    def poll(cls, context):
        asset_file_handle = getattr(context, "asset_file_handle", None)
        asset_library_ref = getattr(context, "asset_library_ref", None)

        if not asset_library_ref:
            cls.poll_message_set("No asset library selected")
            return False
        if not asset_file_handle:
            cls.poll_message_set("No asset selected")
            return False
        if asset_file_handle.local_id:
            cls.poll_message_set("Selected asset is contained in the current file")
            return False
        return True

    def execute(self, context):
        asset_file_handle = context.asset_file_handle

        if asset_file_handle.local_id:
            self.report({"WARNING"}, "This asset is stored in the current blend file")
            return {"CANCELLED"}

        asset_lib_path = bpy.types.AssetHandle.get_full_library_path(asset_file_handle)
        self.open_in_new_blender(asset_lib_path)

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        if self._process is None:
            self.report({"ERROR"}, "Unable to find any running process")
            self.cancel(context)
            return {"CANCELLED"}

        returncode = self._process.poll()
        if returncode is None:
            # Process is still running.
            return {"RUNNING_MODAL"}

        if bpy.ops.asset.library_refresh.poll():
            bpy.ops.asset.library_refresh()

        self.cancel(context)
        return {"FINISHED"}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)

    def open_in_new_blender(self, filepath):
        import subprocess

        filepath = filepath.replace(os.sep, os.sep * 2)
        cli_args = f"""{bpy.app.binary_path} --python-expr 
                    "import bpy; bpy.ops.wm.read_homefile(app_template='Foundry'); bpy.ops.wm.open_mainfile(filepath='{filepath}')\""""

        self._process = subprocess.Popen(cli_args)



def object_context_apply_types(self, context):
    # self.layout.separator()
    layout = self.layout
    asset_type = context.scene.nwo.asset_type
    markers_valid = context.object.type in VALID_MARKERS and asset_type in ('MODEL', 'SCENARIO', 'SKY')
    meshes_valid = context.object.type in VALID_MESHES and asset_type in ('MODEL', 'SCENARIO')
    if markers_valid:
        layout.separator()
        if meshes_valid:
            layout.operator_menu_enum("nwo.apply_type_mesh", property="m_type", text="Halo Mesh Type")
        layout.operator_menu_enum("nwo.apply_type_marker", property="m_type", text="Halo Marker Type")

def collection_context(self, context):
    layout = self.layout
    coll = context.view_layer.active_layer_collection.collection
    is_scenario = context.scene.nwo.asset_type in ('SCENARIO', 'PREFAB')
    if coll and coll.users:
        layout.separator()
        if coll.nwo.type == 'exclude':
            layout.label(text='Exclude Collection')
        elif coll.nwo.type == 'region':
            first_part = 'BSP Collection : ' if is_scenario else 'Region Collection : '
            layout.label(text=first_part + coll.nwo.region)
        elif coll.nwo.type == 'permutation':
            first_part = 'BSP Category Collection : ' if is_scenario else 'Permutation Collection : '
            layout.label(text=first_part + coll.nwo.permutation)

        layout.menu("NWO_MT_ApplyCollectionMenu", text="Set Halo Collection", icon_value=get_icon_id("collection"))

classes_nwo = (
    NWO_GlobalMaterialGlobals,
    H2AMPEKLocationPath,
    H4EKLocationPath,
    HREKLocationPath,
    NWO_Project_ListItems,
    NWO_Permutations_ListItems,
    NWO_UL_Regions,
    NWO_UL_Permutations,
    NWO_Regions_ListItems,
    NWO_SeamBackfaceMenu,
    NWO_RegionsMenu,
    NWO_FaceRegionsMenu,
    NWO_PermutationsMenu,
    NWO_MarkerPermutationsMenu,
    NWO_BSP_ListItems,
    NWO_GlobalMaterial_ListItems,
    NWO_UL_Projects,
    NWO_ProjectAdd,
    NWO_ProjectRemove,
    NWO_ProjectMove,
    NWO_ProjectEditDisplayName,
    ToolkitLocationPreferences,
    NWO_OpenAssetFoundry,
    NWO_UL_MarkerPermutations,
    NWO_List_Add_MarkerPermutation,
    NWO_List_Remove_MarkerPermutation,
    NWO_List_Add_Animation_Rename,
    NWO_List_Remove_Animation_Rename,
    NWO_NewAnimation,
    NWO_DeleteAnimation,
    NWO_UnlinkAnimation,
    NWO_Asset_ListItems,
    NWO_UL_AnimationRename,
    NWO_ScenePropertiesGroup,
    # NWO_List_Add_Shared_Asset,
    # NWO_List_Remove_Shared_Asset,
    # NWO_UL_SceneProps_SharedAssets,
    # NWO_SceneProps_SharedAssets,
    # NWO_LightPropsCycles,
    # NWO_SceneProps,
    NWO_SetUnitScale,
    NWO_AssetMaker,
    NWO_PermutationListCollection,
    NWO_RegionListCollection,
    NWO_ApplyCollectionType,
    NWO_ApplyCollectionMenu,
    # NWO_ObjectProps,
    NWO_GlobalMaterialRegionListFace,
    NWO_RegionListFace,
    NWO_GlobalMaterialListFace,
    NWO_GlobalMaterialMenuFace,
    NWO_GlobalMaterialRegionList,
    NWO_BSPListSeam,
    NWO_RegionList,
    NWO_PermutationList,
    NWO_BSPList,
    NWO_GlobalMaterialList,
    NWO_GlobalMaterialMenu,
    # NWO_ShaderProps,
    NWO_MaterialOpenTag,
    NWO_UL_FaceMapProps,
    NWO_MarkerPermutationItems,
    NWO_FaceProperties_ListItems,
    NWO_ObjectPropertiesGroup,
    NWO_CollectionPropertiesGroup,
    NWO_LightPropertiesGroup,
    NWO_MaterialPropertiesGroup,
    NWO_MeshPropertiesGroup,
    NWO_ImagePropertiesGroup,
    # NWO_LightProps,
    NWO_BoneProps,
    NWO_BonePropertiesGroup,
    # NWO_ActionProps,
    NWO_UL_AnimProps_Events,
    # NWO_AnimProps_Events,
    NWO_List_Add_Animation_Event,
    NWO_List_Remove_Animation_Event,
    NWO_Animation_ListItems,
    NWO_AnimationRenamesItems,
    NWO_ActionPropertiesGroup,
    NWO_MeshPropAddFaceMode,
    NWO_MeshPropAddFaceSides,
    NWO_MeshPropAddFlags,
    NWO_MeshPropAddMisc,
    NWO_MeshPropAddLightmap,
    NWO_MeshPropAddMaterialLighting,
    NWO_MeshPropAdd,
    NWO_MeshPropRemove,
    NWO_FacePropAddFaceMode,
    NWO_FacePropAddFlags,
    NWO_FacePropAddLightmap,
    NWO_FacePropAdd,
    NWO_FacePropRemove,
    NWO_FaceLayerRemove,
    NWO_FaceLayerAssign,
    NWO_FaceLayerSelect,
    NWO_FaceLayerColor,
    NWO_FaceLayerColorAll,
    NWO_FaceLayerMove,
    NWO_EditMode,
    NWO_MasterInstance,
    NWO_FaceDefaultsToggle,
    # NWO_MeshFaceProps,
    # NWO_FacePropPanel,
    NWO_UL_FacePropList,
    NWO_FaceLayerAddFaceMode,
    NWO_FaceLayerAddFlags,
    NWO_FaceLayerAddLightmap,
    NWO_FaceLayerAdd,
    NWO_MeshPropAddMenu,
    NWO_FacePropAddMenu,
    NWO_FaceLayerAddMenu,
    NWO_MT_PIE_ApplyTypeMesh,
    NWO_ApplyTypeMesh,
    NWO_PIE_ApplyTypeMesh,
    NWO_MT_PIE_ApplyTypeMarker,
    NWO_ApplyTypeMarker,
    NWO_PIE_ApplyTypeMarker,
)

def register():
    for cls_nwo in classes_nwo:
        bpy.utils.register_class(cls_nwo)

    bpy.types.ASSETBROWSER_MT_context_menu.append(add_asset_open_in_foundry)
    bpy.types.VIEW3D_MT_object_context_menu.append(object_context_apply_types)
    bpy.types.OUTLINER_MT_collection.append(collection_context)
    bpy.types.Scene.nwo = PointerProperty(
        type=NWO_ScenePropertiesGroup,
        name="NWO Scene Properties",
        description="Set properties for your scene",
    )
    bpy.types.Object.nwo = PointerProperty(
        type=NWO_ObjectPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Object Properties",
    )
    bpy.types.Collection.nwo = PointerProperty(
        type=NWO_CollectionPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Object Properties",
    )
    bpy.types.Light.nwo = PointerProperty(
        type=NWO_LightPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Object Properties",
    )
    bpy.types.Material.nwo = PointerProperty(
        type=NWO_MaterialPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Material Properties",
    )
    bpy.types.Bone.nwo = PointerProperty(
        type=NWO_BonePropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Bone Properties",
    )
    bpy.types.Action.nwo = PointerProperty(
        type=NWO_ActionPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Animation Properties",
    )
    bpy.types.Mesh.nwo = PointerProperty(
        type=NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.Image.nwo = PointerProperty(
        type=NWO_ImagePropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )

def unregister():
    bpy.types.OUTLINER_MT_collection.remove(collection_context)
    bpy.types.VIEW3D_MT_object_context_menu.remove(object_context_apply_types)
    bpy.types.ASSETBROWSER_MT_context_menu.remove(add_asset_open_in_foundry)
    del bpy.types.Scene.nwo
    del bpy.types.Object.nwo
    del bpy.types.Light.nwo
    del bpy.types.Material.nwo
    del bpy.types.Bone.nwo
    del bpy.types.Action.nwo
    del bpy.types.Mesh.nwo
    for cls_nwo in classes_nwo:
        bpy.utils.unregister_class(cls_nwo)


if __name__ == "__main__":
    register()

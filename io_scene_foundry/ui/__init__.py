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
from io_scene_foundry.ui.nodes_ui import NWO_HaloMaterialNodes, NWO_HaloMaterialTilingNode, node_context_menu
from io_scene_foundry.utils.nwo_utils import get_marker_display, get_mesh_display, get_object_type, is_marker, is_mesh

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
    NWO_FaceLayerAddLightmap,
    NWO_FacePropRemove,
    NWO_FacePropAdd,
    NWO_FacePropAddFaceMode,
    NWO_FacePropAddLightmap,
    NWO_FaceLayerColorAll,
    NWO_FaceLayerColor,
    NWO_RegionListFace,
    NWO_GlobalMaterialRegionListFace,
    NWO_GlobalMaterialMenuFace,
    NWO_UpdateLayersFaceCount,
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
    NWO_MarkerTypes,
    NWO_MeshTypes,
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
    NWO_MeshPropAddLightmap,
    NWO_GlobalMaterialMenu,
    NWO_RegionList,
    NWO_GlobalMaterialRegionList,
    NWO_GlobalMaterialList,
    NWO_PermutationList,
    NWO_BSPList,
    NWO_BSPListSeam,
    NWO_MasterInstance,
    NWO_BoneProps,
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
    NWO_SetTimeline,
    NWO_UL_AnimationList,
    NWO_UnlinkAnimation,
    NWO_List_Add_Animation_Rename,
    NWO_UL_AnimationRename,
    NWO_List_Remove_Animation_Rename,
)

from .scene_properties import NWO_BSP_ListItems, NWO_GlobalMaterial_ListItems, NWO_Permutations_ListItems, NWO_Regions_ListItems, NWO_ScenePropertiesGroup

from .scene_ui import NWO_SetUnitScale, NWO_AssetMaker, NWO_UL_Permutations, NWO_UL_Regions

from .viewport_ui import (
    NWO_AddHaloLight,
    NWO_ApplyTypeMarkerSingle,
    NWO_ApplyTypeMesh,
    NWO_ApplyTypeMeshSingle,
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
    layout = self.layout
    asset_type = context.scene.nwo.asset_type
    layout.separator()
    selection_count = len(context.selected_objects)
    if selection_count > 1:
        layout.label(text=f'{selection_count} Halo Objects Selected', icon_value=get_icon_id('category_object_properties_pinned'))
    else:
        ob = context.object
        object_type = get_object_type(ob, True)
        if object_type in ('Mesh', 'Marker'):
            if object_type == 'Mesh':
                type_name, type_icon = get_mesh_display(ob.nwo.mesh_type_ui)
            elif object_type == 'Marker':
                type_name, type_icon = get_marker_display(ob.nwo.marker_type_ui)
            layout.label(text=f'Halo {object_type} ({type_name})', icon_value=type_icon)
        elif object_type == 'Frame':
            layout.label(text=f'Halo {object_type}', icon_value=get_icon_id('frame'))
        elif object_type == 'Light':
            layout.label(text=f'Halo {object_type}', icon='LIGHT')
        else:
            layout.label(text=f'Halo {object_type}')

    markers_valid = any([is_marker(ob) for ob in context.selected_objects]) and asset_type in ('MODEL', 'SCENARIO', 'SKY', 'PREFAB')
    meshes_valid = any([is_mesh(ob) for ob in context.selected_objects]) and asset_type in ('MODEL', 'SCENARIO', 'PREFAB')
    if markers_valid or meshes_valid:
        if meshes_valid:
            layout.operator_menu_enum("nwo.apply_type_mesh", property="m_type", text="Set Mesh Type", icon='MESH_CUBE')
            layout.operator_menu_enum("nwo.mesh_to_marker", property="marker_type", text="Convert to Marker", icon='EMPTY_AXIS').called_once = False
        elif markers_valid:
            layout.operator_menu_enum("nwo.mesh_to_marker", property="marker_type", text="Set Marker Type", icon='EMPTY_AXIS').called_once = False

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
            first_part = 'Layer Collection : ' if is_scenario else 'Permutation Collection : '
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
    NWO_SetTimeline,
    NWO_NewAnimation,
    NWO_DeleteAnimation,
    NWO_UnlinkAnimation,
    NWO_UL_AnimationRename,
    NWO_ScenePropertiesGroup,
    NWO_SetUnitScale,
    NWO_AssetMaker,
    NWO_PermutationListCollection,
    NWO_RegionListCollection,
    NWO_ApplyCollectionType,
    NWO_ApplyCollectionMenu,
    NWO_GlobalMaterialRegionListFace,
    NWO_RegionListFace,
    NWO_GlobalMaterialMenuFace,
    NWO_GlobalMaterialRegionList,
    NWO_BSPListSeam,
    NWO_RegionList,
    NWO_PermutationList,
    NWO_BSPList,
    NWO_GlobalMaterialList,
    NWO_GlobalMaterialMenu,
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
    NWO_BoneProps,
    NWO_BonePropertiesGroup,
    NWO_UL_AnimProps_Events,
    NWO_List_Add_Animation_Event,
    NWO_List_Remove_Animation_Event,
    NWO_Animation_ListItems,
    NWO_AnimationRenamesItems,
    NWO_ActionPropertiesGroup,
    NWO_MeshPropAddLightmap,
    NWO_MeshPropAdd,
    NWO_MeshPropRemove,
    NWO_FacePropAddFaceMode,
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
    NWO_UL_FacePropList,
    NWO_FaceLayerAddFaceMode,
    NWO_FaceLayerAddLightmap,
    NWO_FaceLayerAdd,
    NWO_MeshPropAddMenu,
    NWO_FacePropAddMenu,
    NWO_FaceLayerAddMenu,
    NWO_MT_PIE_ApplyTypeMesh,
    NWO_ApplyTypeMeshSingle,
    NWO_ApplyTypeMesh,
    NWO_PIE_ApplyTypeMesh,
    NWO_MT_PIE_ApplyTypeMarker,
    NWO_ApplyTypeMarkerSingle,
    NWO_ApplyTypeMarker,
    NWO_PIE_ApplyTypeMarker,
    NWO_HaloMaterialNodes,
    NWO_HaloMaterialTilingNode,
    NWO_MeshTypes,
    NWO_MarkerTypes,
    NWO_AddHaloLight,
    NWO_UpdateLayersFaceCount,
    NWO_UL_AnimationList,
)

def register():
    for cls_nwo in classes_nwo:
        bpy.utils.register_class(cls_nwo)

    # bpy.types.ASSETBROWSER_MT_context_menu.append(add_asset_open_in_foundry)
    bpy.types.VIEW3D_MT_object_context_menu.append(object_context_apply_types)
    bpy.types.OUTLINER_MT_collection.append(collection_context)
    bpy.types.NODE_MT_add.append(node_context_menu)
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
    bpy.types.TextCurve.nwo = PointerProperty(
        type=NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.Curve.nwo = PointerProperty(
        type=NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.SurfaceCurve.nwo = PointerProperty(
        type=NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.MetaBall.nwo = PointerProperty(
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
    bpy.types.NODE_MT_add.remove(node_context_menu)
    bpy.types.OUTLINER_MT_collection.remove(collection_context)
    bpy.types.VIEW3D_MT_object_context_menu.remove(object_context_apply_types)
    # bpy.types.ASSETBROWSER_MT_context_menu.remove(add_asset_open_in_foundry)
    del bpy.types.Scene.nwo
    del bpy.types.Object.nwo
    del bpy.types.Light.nwo
    del bpy.types.Material.nwo
    del bpy.types.Bone.nwo
    del bpy.types.Action.nwo
    del bpy.types.Mesh.nwo
    del bpy.types.TextCurve.nwo
    del bpy.types.Curve.nwo
    del bpy.types.SurfaceCurve.nwo
    del bpy.types.MetaBall.nwo
    del bpy.types.Image.nwo
    for cls_nwo in classes_nwo:
        bpy.utils.unregister_class(cls_nwo)


if __name__ == "__main__":
    register()

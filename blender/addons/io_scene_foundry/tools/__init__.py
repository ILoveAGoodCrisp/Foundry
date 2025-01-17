

import bpy

from .refresh_cinematic_controls import NWO_OT_RefreshCinematicControls

from .cache_builder import NWO_OT_CacheBuild, NWO_OT_LaunchMCC, NWO_OT_OpenModFolder
from .collection_manager import NWO_CollectionManager_Create, NWO_CollectionManager_CreateMove
from .append_grid_materials import NWO_OT_AppendGridMaterials
from .shader_duplicate import NWO_OT_ShaderDuplicate
from .camera_sync import NWO_OT_CameraSync
from .prefab_exporter import NWO_OT_ExportPrefabs
from .light_exporter import NWO_OT_ExportLights
from .asset_creator import NWO_OT_NewAsset, NWO_OT_NewChildAsset
from .animation.rename_importer import NWO_OT_RenameImporter
from .animation.fcurve_transfer import NWO_OT_FcurveTransfer
from .animation.composites import NWO_OT_AnimationBlendAxisAdd, NWO_OT_AnimationBlendAxisMove, NWO_OT_AnimationBlendAxisRemove, NWO_OT_AnimationCompositeAdd, NWO_OT_AnimationCompositeMove, NWO_OT_AnimationCompositeRemove, NWO_OT_AnimationDeadZoneAdd, NWO_OT_AnimationDeadZoneMove, NWO_OT_AnimationDeadZoneRemove, NWO_OT_AnimationLeafAdd, NWO_OT_AnimationLeafMove, NWO_OT_AnimationLeafRemove, NWO_OT_AnimationPhaseSetAdd, NWO_OT_AnimationPhaseSetMove, NWO_OT_AnimationPhaseSetRemove, NWO_UL_AnimationBlendAxis, NWO_UL_AnimationComposites, NWO_UL_AnimationDeadZone, NWO_UL_AnimationLeaf, NWO_UL_AnimationPhaseSet
from .animation.copy import NWO_OT_AnimationCopyAdd, NWO_OT_AnimationCopyMove, NWO_OT_AnimationCopyRemove, NWO_UL_AnimationCopies
from .scenario.lightmap import NWO_OT_Lightmap
from .scenario.zone_sets import NWO_OT_RemoveExistingZoneSets, NWO_OT_ZoneSetAdd, NWO_OT_ZoneSetMove, NWO_OT_ZoneSetRemove, NWO_UL_ZoneSets
from .tag_templates import NWO_OT_LoadTemplate
from .cubemap import NWO_OT_Cubemap
from .scale_models import NWO_OT_AddScaleModel
from .animation.automate_pose_overlay import NWO_AddAimAnimation
from .rigging.convert_to_halo_rig import NWO_OT_ConvertToHaloRig
from .rigging.create_rig import NWO_OT_AddRig, NWO_OT_SelectArmature
from .rigging.validation import NWO_AddPoseBones, NWO_FixArmatureTransforms, NWO_FixPoseBones, NWO_FixRootBone, NWO_ValidateRig
from .scene_scaler import NWO_ScaleScene
from .append_foundry_materials import NWO_AppendFoundryMaterials
from .auto_seam import NWO_AutoSeam
from .clear_duplicate_materials import NWO_ClearShaderPaths, NWO_StompMaterials
from .export_bitmaps import NWO_ExportBitmapsSingle
from .importer import NWO_FH_Import, NWO_FH_ImportBitmapAsImage, NWO_FH_ImportBitmapAsNode, NWO_FH_ImportShaderAsMaterial, NWO_Import, NWO_OT_ConvertScene, NWO_OT_ImportBitmap, NWO_OT_ImportShader
from .mesh_to_marker import NWO_MeshToMarker
from .set_sky_permutation_index import NWO_NewSky, NWO_SetDefaultSky, NWO_SetSky
from .sets_manager import NWO_BSPContextMenu, NWO_BSPInfo, NWO_BSPSetLightmapRes, NWO_FaceRegionAdd, NWO_FaceRegionAssignSingle, NWO_OT_HideObjectType, NWO_PermutationAdd, NWO_PermutationAssign, NWO_PermutationAssignSingle, NWO_PermutationHide, NWO_PermutationHideSelect, NWO_PermutationMove, NWO_PermutationRemove, NWO_PermutationRename, NWO_PermutationSelect, NWO_RegionAdd, NWO_RegionAssign, NWO_RegionAssignSingle, NWO_RegionHide, NWO_RegionHideSelect, NWO_RegionMove, NWO_RegionRemove, NWO_RegionRename, NWO_RegionSelect, NWO_SeamAssignSingle, NWO_UpdateSets
from .shader_farm import NWO_FarmShaders
from .shader_finder import NWO_ShaderFinder_Find, NWO_ShaderFinder_FindSingle
from .shader_reader import NWO_ShaderToNodes
from .get_model_variants import NWO_GetModelVariants
from .get_zone_sets import NWO_GetZoneSets
from .get_tag_list import NWO_GetTagsList, NWO_TagExplore
from .halo_launcher import NWO_HaloLauncher_Data, NWO_HaloLauncher_Foundation, NWO_HaloLauncher_Sapien, NWO_HaloLauncher_TagTest, NWO_HaloLauncher_Tags, NWO_OpenFoundationTag
from .shader_builder import NWO_ListMaterialShaders, NWO_Shader_BuildSingle, NWO_ShaderPropertiesGroup
from .halo_launcher import NWO_HaloLauncherPropertiesGroup, NWO_MaterialGirl

is_blender_startup = True

# import Tool Operators
from .instance_proxies import NWO_ProxyInstanceNew, NWO_ProxyInstanceCancel, NWO_ProxyInstanceEdit, NWO_ProxyInstanceDelete

#######################################
# NEW TOOL UI

from .halo_join import NWO_JoinHalo

#######################################
# HALO MANAGER TOOL


#######################################
# HALO EXPORT TOOL


#######################################
# PROPERTIES MANAGER TOOL

classeshalo = (
    NWO_HaloLauncherPropertiesGroup,
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
    NWO_MaterialGirl,
    NWO_OpenFoundationTag,
    NWO_HaloLauncher_Foundation,
    NWO_HaloLauncher_Data,
    NWO_HaloLauncher_Tags,
    NWO_HaloLauncher_Sapien,
    NWO_HaloLauncher_TagTest,
    NWO_ExportBitmapsSingle,
    NWO_GetModelVariants,
    NWO_GetZoneSets,
    NWO_GetTagsList,
    NWO_TagExplore,
    NWO_ProxyInstanceCancel,
    NWO_ProxyInstanceDelete,
    NWO_ProxyInstanceEdit,
    NWO_ProxyInstanceNew,
    NWO_CollectionManager_CreateMove,
    NWO_CollectionManager_Create,
    NWO_AutoSeam,
    NWO_ShaderFinder_FindSingle,
    NWO_ShaderFinder_Find,
    NWO_OT_AddRig,
    NWO_OT_SelectArmature,
    NWO_ListMaterialShaders,
    NWO_Shader_BuildSingle,
    NWO_ShaderPropertiesGroup,
    NWO_OT_AddScaleModel,
    NWO_JoinHalo,
    NWO_FarmShaders,
    NWO_AddPoseBones,
    NWO_ValidateRig,
    NWO_FixRootBone,
    NWO_FixPoseBones,
    NWO_FixArmatureTransforms,
    NWO_AddAimAnimation,
    NWO_MeshToMarker,
    NWO_StompMaterials,
    NWO_Import,
    NWO_FH_Import,
    NWO_OT_ImportBitmap,
    NWO_FH_ImportBitmapAsImage,
    NWO_FH_ImportBitmapAsNode,
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
    NWO_OT_ZoneSetMove,
    NWO_OT_ZoneSetRemove,
    NWO_OT_ZoneSetAdd,
    NWO_UL_ZoneSets,
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
    NWO_OT_ExportLights,
    NWO_OT_ExportPrefabs,
    NWO_OT_CameraSync,
    NWO_OT_ShaderDuplicate,
    NWO_OT_AppendGridMaterials,
    NWO_OT_CacheBuild,
    NWO_OT_LaunchMCC,
    NWO_OT_OpenModFolder,
    NWO_OT_RefreshCinematicControls,
    NWO_OT_NewChildAsset,
    NWO_OT_ImportShader,
    NWO_FH_ImportShaderAsMaterial,
)

def register():
    for clshalo in classeshalo:
        bpy.utils.register_class(clshalo)
        
    bpy.types.Scene.nwo_shader_build = bpy.props.PointerProperty(
        type=NWO_ShaderPropertiesGroup,
        name="Halo Shader Export",
        description="",
    )
    
    bpy.types.Scene.nwo_halo_launcher = bpy.props.PointerProperty(
        type=NWO_HaloLauncherPropertiesGroup,
        name="Halo Launcher",
        description="Launches stuff",
    )
    
def unregister():
    del bpy.types.Scene.nwo_halo_launcher
    del bpy.types.Scene.nwo_shader_build
    for clshalo in classeshalo:
        bpy.utils.unregister_class(clshalo)
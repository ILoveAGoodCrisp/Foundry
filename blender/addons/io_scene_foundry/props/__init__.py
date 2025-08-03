

import bpy
from . import bone, collection, image, light, material, mesh, object, scene

classes = [
    bone.NWO_BonePropertiesGroup,
    collection.NWO_CollectionPropertiesGroup,
    image.NWO_ImagePropertiesGroup,
    light.NWO_LightPropertiesGroup,
    mesh.NWO_FaceProperties_ListItems,
    mesh.NWO_MeshPropertiesGroup,
    material.NWO_MaterialPropertiesGroup,
    object.NWO_MarkerPermutationItems,
    object.NWO_ActorItems,
    object.NWO_ObjectPropertiesGroup,
    scene.NWO_AnimationCopiesItems,
    scene.NWO_AnimationLeavesItems,
    scene.NWO_AnimationPhaseSetsItems,
    scene.NWO_AnimationDeadZonesItems,
    scene.NWO_AnimationBlendAxisItems,
    scene.NWO_AnimationCompositesItems,
    scene.NWO_ActionGroup,
    scene.NWO_AnimationRenamesItems,
    scene.NWO_AnimationEventData_ListItems,
    scene.NWO_Animation_ListItems,
    scene.NWO_AnimationPropertiesGroup,
    scene.NWO_ZoneSets_ListItems,
    scene.NWO_MaterialOverrides,
    scene.NWO_PermutationClones,
    scene.NWO_Permutations_ListItems,
    scene.NWO_Regions_ListItems,
    scene.NWO_BSP_ListItems,
    scene.NWO_GlobalMaterial_ListItems,
    scene.NWO_IKChain,
    scene.NWO_ControlObjects,
    # scene.NWO_ChildAsset,
    scene.NWO_CinematicEvent,
    scene.NWO_ScenePropertiesGroup,
]

def register():
    for cls in classes: bpy.utils.register_class(cls)
    bpy.types.Scene.nwo = bpy.props.PointerProperty(
        type=scene.NWO_ScenePropertiesGroup,
        name="NWO Scene Properties",
        description="Set properties for your scene",
    )
    bpy.types.Object.nwo = bpy.props.PointerProperty(
        type=object.NWO_ObjectPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Object Properties",
    )
    bpy.types.Bone.nwo = bpy.props.PointerProperty(
        type=bone.NWO_BonePropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Object Properties",
    )
    bpy.types.Collection.nwo = bpy.props.PointerProperty(
        type=collection.NWO_CollectionPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Object Properties",
    )
    bpy.types.Light.nwo = bpy.props.PointerProperty(
        type=light.NWO_LightPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Object Properties",
    )
    bpy.types.Material.nwo = bpy.props.PointerProperty(
        type=material.NWO_MaterialPropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Material Properties",
    )
    bpy.types.Bone.nwo = bpy.props.PointerProperty(
        type=bone.NWO_BonePropertiesGroup,
        name="Halo NWO Properties",
        description="Set Halo Bone Properties",
    )
    bpy.types.Mesh.nwo = bpy.props.PointerProperty(
        type=mesh.NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.TextCurve.nwo = bpy.props.PointerProperty(
        type=mesh.NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.Curve.nwo = bpy.props.PointerProperty(
        type=mesh.NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.SurfaceCurve.nwo = bpy.props.PointerProperty(
        type=mesh.NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.MetaBall.nwo = bpy.props.PointerProperty(
        type=mesh.NWO_MeshPropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    bpy.types.Image.nwo = bpy.props.PointerProperty(
        type=image.NWO_ImagePropertiesGroup,
        name="Halo Mesh Properties",
        description="Set Halo Properties",
    )
    
def unregister():
    del bpy.types.Scene.nwo
    del bpy.types.Object.nwo
    del bpy.types.Bone.nwo
    del bpy.types.Light.nwo
    del bpy.types.Material.nwo
    del bpy.types.Mesh.nwo
    del bpy.types.TextCurve.nwo
    del bpy.types.Curve.nwo
    del bpy.types.SurfaceCurve.nwo
    del bpy.types.MetaBall.nwo
    del bpy.types.Image.nwo
    for cls in reversed(classes): bpy.utils.unregister_class(cls)
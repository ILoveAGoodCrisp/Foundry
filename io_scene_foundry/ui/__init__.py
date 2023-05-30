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
from bpy.app.handlers import persistent
from bpy.props import (
        PointerProperty,
        )

def poll_ui(selected_types):
    scene_nwo = bpy.context.scene.nwo
    asset_type = scene_nwo.asset_type

    return asset_type in selected_types

mesh_type_items = [
    ('_connected_geometry_mesh_type_boundary_surface', "Boundary Surface", "Used in structure_design tags for soft_kill, soft_ceiling, and slip_sufaces. Only use when importing to a structure_design tag. Can be forced on with the prefixes: '+soft_ceiling', 'soft_kill', 'slip_surface'"), # 0
    ('_connected_geometry_mesh_type_collision', "Collision", "Sets this mesh to have collision geometry only. Can be forced on with the prefix: '@'"), #1
    ('_connected_geometry_mesh_type_cookie_cutter', "Cookie Cutter", "Defines an area which ai will pathfind around. Can be forced on with the prefix: '+cookie'"), # 2
    ('_connected_geometry_mesh_type_decorator', "Decorator", "Use this when making a decorator. Allows for different LOD levels to be set"), # 3
    ('_connected_geometry_mesh_type_default', "Default", "By default this mesh type will be treated as render only geometry in models, and render + bsp collision geometry in structures"), #4
    ('_connected_geometry_mesh_type_poop', "Instanced Geometry", "Writes this mesh to a json file as instanced geometry. Can be forced on with the prefix: '%'"), # 5
    ('_connected_geometry_mesh_type_poop_marker', "Instanced Marker", ""), # 6
    ('_connected_geometry_mesh_type_poop_rain_blocker', "Rain Occluder",'Rain is not rendered in the the volume this mesh occupies.'), # 7
    ('_connected_geometry_mesh_type_poop_vertical_rain_sheet', "Vertical Rain Sheet", ''), # 8
    ('_connected_geometry_mesh_type_lightmap_region', "Lightmap Region", "Defines an area of a structure which should be lightmapped. Can be referenced when lightmapping"), # 9
    ('_connected_geometry_mesh_type_object_instance', "Object Instance", "Writes this mesh to the json as an instanced object. Can be forced on with the prefix: '+flair'"), # 10
    ('_connected_geometry_mesh_type_physics', "Physics", "Sets this mesh to have physics geometry only. Can be forced on with the prefix: '$'"), # 11
    ('_connected_geometry_mesh_type_planar_fog_volume', "Planar Fog Volume", "Defines an area for a fog volume. The same logic as used for portals should be applied to these.  Can be forced on with the prefix: '+fog'"), # 12
    ('_connected_geometry_mesh_type_portal', "Portal", "Cuts up a bsp and defines clusters. Can be forced on with the prefix '+portal'"), # 13
    ('_connected_geometry_mesh_type_seam', "Seam", "Defines where two bsps meet. Its name should match the name of the bsp its in. Can be forced on with the prefix '+seam'"), # 14
    ('_connected_geometry_mesh_type_water_physics_volume', "Water Physics Volume", "Defines an area where water physics should apply. Only use when importing to a structure_design tag. Can be forced on with the prefix: '+water'"), # 15
    ('_connected_geometry_mesh_type_water_surface', "Water Surface", "Defines a mesh as a water surface. Can be forced on with the prefix: '"), # 16
    ('_connected_geometry_mesh_type_obb_volume', 'OBB Volume', ''), # 17
    ('_connected_geometry_mesh_type_volume', 'Volume', ''),
    # These go unused in menus, and are instead set at export
    ('_connected_geometry_mesh_type_poop_collision', 'Poop Collision', ''),
    ('_connected_geometry_mesh_type_poop_physics', 'Poop Physics', ''),
    ('_connected_geometry_mesh_type_render', 'Render', ''),
    ('_connected_geometry_mesh_type_structure', 'Structure', ''),
    ('_connected_geometry_mesh_type_default', 'Default', ''),

]

volume_type_items = [
    ('_connected_geometry_volume_type_soft_ceiling', 'Soft Celing', ''),
    ('_connected_geometry_volume_type_soft_kill', 'Soft Kill', ''),
    ('_connected_geometry_volume_type_slip_surface', 'Slip Surface', ''),
    ('_connected_geometry_volume_type_water_physics', 'Water Physics', ''),
    ('_connected_geometry_volume_type_lightmap_exclude', 'Lightmap Exclusion', ''),
    ('_connected_geometry_volume_type_lightmap_region', 'Lightmap Region', ''),
    ('_connected_geometry_volume_type_streaming', 'Streaming', ''),
]

marker_type_items = [ 
            ('_connected_geometry_marker_type_model', "Model", "Default marker type. Defines render_model markers for models, and structure markers for bsps"),
            ('_connected_geometry_marker_type_effects', "Effects", "Marker for effects only."),
            ('_connected_geometry_marker_type_game_instance', "Game Object", "Game Instance marker. Used to create an instance of a tag in the bsp. Can be set with the prefix: ?"),
            ('_connected_geometry_marker_type_garbage', "Garbage", "marker to define position that garbage pieces should be created"),
            ('_connected_geometry_marker_type_hint', "Hint", "Used for ai hints"),
            ('_connected_geometry_marker_type_pathfinding_sphere', "Pathfinding Sphere", "Used to create ai pathfinding spheres"),
            ('_connected_geometry_marker_type_physics_constraint', "Physics Constraint", "Used to define various types of physics constraints"),
            ('_connected_geometry_marker_type_physics_hinge_constraint', "Hinge Constraint", "Used to define various types of physics constraints"),
            ('_connected_geometry_marker_type_physics_socket_constraint', "Socket Constraint", "Used to define various types of physics constraints"),
            ('_connected_geometry_marker_type_target', "Target", "Defines the markers used in a model's targets'"),
            ('_connected_geometry_marker_type_water_volume_flow', "Water Volume Flow", "Used to define water flow for water physics volumes. For structure_design tags only"),
            ('_connected_geometry_marker_type_airprobe', "Airprobe", "Airprobes tell the game how to handle static lighting on dynamic objects"),
            ('_connected_geometry_marker_type_envfx', "Environment Effect", "Plays an effect on this point in the structure"),
            ('_connected_geometry_marker_type_lightCone', "Light Cone", "Creates a light cone with the defined parameters"),
            ('_connected_geometry_marker_type_prefab', "Prefab", ""),
            ('_connected_geometry_marker_type_cheap_light', "Cheap Light", ""),
            ('_connected_geometry_marker_type_light', "Light", ""),
            ('_connected_geometry_marker_type_falling_leaf', "Falling Leaf", ""),
            ]

# FACE LEVEL PROPERTIES

##################################################


###################################################


# import classes from other files

from .object_properties import *
from .object_ui import *
from .materials_ui import *
from .materials_properties import *
from .animation_properties import *
from .animation_ui import *
from .scene_properties import *
from .scene_ui import *
from .face_ui import *

classes_nwo = (
    NWO_Asset_ListItems,
    NWO_ScenePropertiesGroup,
    # NWO_List_Add_Shared_Asset,
    # NWO_List_Remove_Shared_Asset,
    # NWO_UL_SceneProps_SharedAssets,
    # NWO_SceneProps_SharedAssets,
    NWO_LightPropsCycles,
    NWO_SceneProps,
    NWO_SetUnitScale,
    NWO_AssetMaker,
    NWO_GameInstancePath,
    NWO_FogPath,
    NWO_EffectPath,
    NWO_LightConePath,
    NWO_LightConeCurvePath,
    NWO_LightTagPath,
    NWO_LightShaderPath,
    NWO_LightGelPath,
    NWO_LensFlarePath,
    NWO_ShaderPath,
    NWO_ObjectProps,
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
    # NWO_ObjectMeshProps,
    # NWO_ObjectMarkerProps,
    NWO_ShaderProps,
    NWO_MaterialOpenTag,
    NWO_UL_FaceMapProps,
    NWO_FaceProperties_ListItems,
    NWO_ObjectPropertiesGroup,
    NWO_LightPropertiesGroup,
    NWO_MaterialPropertiesGroup,
    NWO_LightProps,
    NWO_BoneProps,
    NWO_BonePropertiesGroup,
    NWO_ActionProps,
    NWO_UL_AnimProps_Events,
    NWO_AnimProps_Events,
    NWO_List_Add_Animation_Event,
    NWO_List_Remove_Animation_Event,
    NWO_Animation_ListItems,
    NWO_ActionPropertiesGroup,
    NWO_MeshPropAddFaceMode,
    NWO_MeshPropAddFaceSides,
    NWO_MeshPropAddFlags,
    NWO_MeshPropAddMisc,
    NWO_MeshPropAddLightmap,
    NWO_MeshPropAddMaterialLighting,
    NWO_MeshPropAdd,
    NWO_MeshPropRemove,
    NWO_FaceLayerAddFaceMode,
    NWO_FaceLayerAddFlags,
    NWO_FaceLayerAddMisc,
    NWO_FaceLayerAddLightmap,
    NWO_FaceLayerAdd,
    NWO_FaceLayerRemove,
    NWO_FaceLayerAssign,
    NWO_FaceLayerSelect,
    NWO_FaceLayerColour,
    NWO_FaceLayerMove,
    NWO_EditMode,
    NWO_MasterInstance,
    NWO_FaceDefaultsToggle,
    NWO_MeshFaceProps,
    NWO_FacePropPanel,
    NWO_UL_FacePropList,
    # NWO_ObjectMeshMaterialLightingProps,
    # NWO_ObjectMeshLightmapProps,
    NWO_MeshPropAddMenu,
    NWO_FacePropAddMenu,
    NWO_MeshPropertiesGroup,
)

def register():
    for cls_nwo in classes_nwo:
        bpy.utils.register_class(cls_nwo)

    bpy.types.Scene.nwo = PointerProperty(type=NWO_ScenePropertiesGroup, name="NWO Scene Properties", description="Set properties for your scene")
    bpy.types.Object.nwo = PointerProperty(type=NWO_ObjectPropertiesGroup, name="Halo NWO Properties", description="Set Halo Object Properties")
    bpy.types.Light.nwo = PointerProperty(type=NWO_LightPropertiesGroup, name="Halo NWO Properties", description="Set Halo Object Properties")
    bpy.types.Material.nwo = PointerProperty(type=NWO_MaterialPropertiesGroup, name="Halo NWO Properties", description="Set Halo Material Properties") 
    bpy.types.Bone.nwo = PointerProperty(type=NWO_BonePropertiesGroup, name="Halo NWO Properties", description="Set Halo Bone Properties")
    bpy.types.Action.nwo = PointerProperty(type=NWO_ActionPropertiesGroup, name="Halo NWO Properties", description="Set Halo Animation Properties")
    bpy.types.Mesh.nwo = PointerProperty(type=NWO_MeshPropertiesGroup, name="Halo Mesh Properties", description="Set Halo Properties")

def unregister():
    del bpy.types.Scene.nwo
    del bpy.types.Object.nwo
    del bpy.types.Light.nwo
    del bpy.types.Material.nwo
    del bpy.types.Bone.nwo
    del bpy.types.Action.nwo
    del bpy.types.Mesh.nwo
    for cls_nwo in classes_nwo:
        bpy.utils.unregister_class(cls_nwo)
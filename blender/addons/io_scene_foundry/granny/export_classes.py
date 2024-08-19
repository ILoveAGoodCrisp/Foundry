from ctypes import Structure, c_char_p, c_float, c_void_p, cast, pointer
from enum import Enum
from typing import Literal
import bpy
from mathutils import Matrix, Quaternion, Vector

from .formats import GrannyDataTypeDefinition, GrannyTransform

from .. import utils
    
class Properties:
    properties: dict
    def __init__(self, id):
        self.properties = utils.get_halo_props_for_granny(id)
        
    def create_properties(self, granny):
        
        if not self.properties: return
        
        ExtendedDataType = (GrannyDataTypeDefinition * (len(self.properties) + 1))()
        
        for i, key in enumerate(self.properties):
            ExtendedDataType[i] = GrannyDataTypeDefinition(
                member_type=8,
                name=key.encode()
            )
        
        ExtendedDataType[-1] = GrannyDataTypeDefinition(member_type=0)
        print(self.properties)
        data = self._extended_data_create()

        granny.extended_data.object = cast(pointer(data), c_void_p)
        granny.extended_data.type = ExtendedDataType
        
    def _extended_data_create(self):
        fields = [(key, c_char_p) for key in self.properties.keys()]

        class ExtendedData(Structure):
            _pack_ = 1
            _fields_ = fields
        
        return ExtendedData(**self.properties)

class Material(Properties):
    name: bytes
    def __init__(self, material: bpy.types.Material):
        super().__init__(material)
        self.name = material.name.encode()
        
class Track:
    name: str
    keyframe_positions: Vector
    keyframe_orientation: Vector
    keyframe_scales: Vector
    position_curve: None
    orientation_curve: None
    scale_curve: None
    
class TrackGroup:
    name: str
    transform_tracks: list[Track]

class Animation:
    name: str
    duration: float
    time_step: float
    oversmapling: float
    track_groups: list[int]
    
class BoneType(Enum):
    NODE = 0
    MARKER = 1
    MESH = 2
    LIGHT = 3
    
class Bone(Properties):
    name: bytes
    parent_index = -1
    local_transform = None
    inverse_transform = None
    lod_error = 0.0
    properties: dict
    bone_type: BoneType
    
    def __init__(self, bone: bpy.types.PoseBone | bpy.types.Object):
        self.name = bone.name.encode()
        
    def set_transform(self, bone: bpy.types.PoseBone | bpy.types.Object):
        if isinstance(bone, bpy.types.Object):
            matrix = bone.matrix_local
        else:
            matrix = bone.matrix
        loc = matrix.to_translation()
        position = (c_float * 3)(loc[0], loc[1], loc[2])
        quaternion = matrix.to_quaternion()
        orientation = (c_float * 4)(quaternion[1], quaternion[2], quaternion[3], quaternion[0])
        scale = matrix.to_scale()
        normalized_matrix = matrix.normalized()
        for i in range(3):
            normalized_matrix[i][0] /= scale[0]
            normalized_matrix[i][1] /= scale[1]
            normalized_matrix[i][2] /= scale[2]
            
        shear = (
            normalized_matrix[1][0],
            normalized_matrix[2][0],
            normalized_matrix[2][1]
        )
        
        scale_shear = scale[0], shear[0], shear[1], 0.0, scale[1], shear[2], 0.0, 0.0, scale[2]
        
        scale_shear = (c_float * 3 * 3)((scale[0], shear[0], shear[1]), (0.0, scale[1], shear[2]), (0.0, 0.0, scale[2]))
        
        self.local_transform = GrannyTransform(flags=7, position=position, orientation=orientation, scale_shear=scale_shear)
        
        inverted_matrix = matrix.inverted()
        self.inverse_transform = (c_float * 4 * 4)(
            (inverted_matrix[0][0], inverted_matrix[0][1], inverted_matrix[0][2], inverted_matrix[0][3]),
            (inverted_matrix[1][0], inverted_matrix[1][1], inverted_matrix[1][2], inverted_matrix[1][3]),
            (inverted_matrix[2][0], inverted_matrix[2][1], inverted_matrix[2][2], inverted_matrix[2][3]),
            (inverted_matrix[3][0], inverted_matrix[3][1], inverted_matrix[3][2], inverted_matrix[3][3]),
        )
        
    
class Skeleton(Properties):
    name: bytes
    lod = 0
    bones: list[Bone]
    
    def __init__(self, ob: bpy.types.Object):
        super().__init__(ob)
        self.name = ob.name.encode()
        self._get_bones(ob)
        
    def _get_bones(self, ob):
        self.bones = []
        if ob.type == 'ARMATURE':
            list_bones =  list(ob.pose.bones)
            for idx, bone in enumerate(ob.pose.bones):
                b = Bone(bone)
                b.set_transform(bone)
                b.properties = utils.get_halo_props_for_granny(ob.data.bones[idx])
                if bone.parent:
                    b.parent_index = list_bones.index(bone.parent)
                self.bones.append(b)
        else:
            self.bones.append(Bone(ob))
    
class Color:
    red: float
    green: float
    blue: float
    
class Vertex:
    position: Vector
    bone_weights: tuple[float, float, float, float]
    bone_indices: tuple[int, int, int, int]
    normal: Vector
    uvs: tuple[Vector]
    lighting_uv: Vector
    vertex_color: Color
    blend_shape: None
    vertex_id1: int
    vertex_id2: int
    
class VertexData:
    vertices: tuple[Vertex]
    
class Group:
    material_index: int
    tri_start: int
    tri_count: int
    
class Triangle:
    material_index: int
    indices: tuple[int, int, int]
    
class Indices:
    group: tuple[Group]
    indices: tuple[int, int, int]
    
class BoneBinding:
    name: str
    ob: bpy.types.Object
    
class Mesh:
    name: str
    primary_vertex_data_index: int
    primary_topology_index: int
    material_bindings: tuple[int]
    bone_bindings: tuple[BoneBinding]
    properties: dict

class Model:
    name: str
    skeleton_index: int
    initial_placement: Quaternion
    mesh_bindings: tuple[int]
    
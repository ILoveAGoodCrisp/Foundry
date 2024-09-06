from ctypes import Structure, c_char_p, c_float, c_int, c_ubyte, c_uint8, c_void_p, cast, pointer
from enum import Enum
from math import pi, radians
from typing import Literal
import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
import numpy as np

from ..export.virtual_geometry import VirtualBone, VirtualMaterial, VirtualMesh, VirtualModel, VirtualNode, VirtualSkeleton

from .formats import GrannyDataTypeDefinition, GrannyTransform

from .. import utils
from ..export.export_info import *

identity_matrix = Matrix.Identity(4)

granny_transform_default = GrannyTransform(flags=7, position=(c_float * 3)(0, 0, 0), orientation=(c_float * 4)(0, 0, 0, 1), scale_shear=(c_float * 3 * 3)((1, 0, 0), (0.0, 1, 0), (0.0, 0.0, 1)))
granny_inverse_transform_default = (c_float * 4 * 4)(
            (1, 0, 0, 0),
            (0, 1, 0, 0),
            (0, 0, 1, 0),
            (0, 0, 0, 1),
        )
granny_inverse_transform_default_mesh = (c_float * 4 * 4)(
            (0, -1, 0, 0),
            (1, 0, 0, 0),
            (0, 0, 1, 0),
            (0, 0, 0, 1),
        )

rotation_matrix = Matrix.Rotation(radians(90), 4, 'Z')
z_up_to_y_up = Matrix.Rotation(-radians(90), 4, 'X')

def granny_transform_parts(matrix_local: Matrix):
    loc = matrix_local.to_translation()
    position = (c_float * 3)(loc[0], loc[1], loc[2])
    quaternion = matrix_local.to_quaternion()
    orientation = (c_float * 4)(quaternion[1], quaternion[2], quaternion[3], quaternion[0])
    scale = matrix_local.to_scale()
    normalized_matrix = matrix_local.normalized()
    for i in range(3):
        normalized_matrix[i][0] /= scale[0]
        normalized_matrix[i][1] /= scale[1]
        normalized_matrix[i][2] /= scale[2]
        
    # shear = (
    #     normalized_matrix[1][0],
    #     normalized_matrix[2][0],
    #     normalized_matrix[2][1]
    # )
    
    # scale_shear = scale[0], shear[0], shear[1], 0.0, scale[1], shear[2], 0.0, 0.0, scale[2]
    
    scale_shear = scale[0], 0.0, 0.0, 0.0, scale[1], 0.0, 0.0, 0.0, 0.0
    
    scale_shear = (c_float * 3 * 3)((scale[0], 0.0, 0.0), (0.0, scale[1], 0.0), (0.0, 0.0, scale[2]))
    
    return position, orientation, scale_shear
    
class Properties:
    properties = {}
    def __init__(self, virtual_id: VirtualNode | VirtualMaterial = None):
        if virtual_id: self.properties = utils.get_halo_props_for_granny(virtual_id.props)
        
    def create_properties(self, granny):
        
        if not self.properties: return
        
        ExtendedDataType = (GrannyDataTypeDefinition * (len(self.properties) + 1))()
        
        for i, key in enumerate(self.properties):
            ExtendedDataType[i] = GrannyDataTypeDefinition(
                member_type=8,
                name=key.encode()
            )
        
        ExtendedDataType[-1] = GrannyDataTypeDefinition(member_type=0)
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
    def __init__(self, material: VirtualMaterial):
        super().__init__(material)
        self.name = material.name.encode()
        self.name_str = material.name
        self.granny = None
        
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
    def __init__(self, bone: VirtualBone):
        # super().__init__(bone)
        self.name = bone.name.encode()
        self.parent_index = bone.parent_index
        self.lod_error = 0.0
        self.local_transform = granny_transform_default
        self.inverse_transform = granny_inverse_transform_default
        self.set_transform(bone.matrix_world, bone.matrix_local)
        
    def set_transform(self, matrix_world: Matrix, matrix_local: Matrix):
        position, orientation, scale_shear = granny_transform_parts(matrix_local)
        self.local_transform = GrannyTransform(flags=0, position=position, orientation=orientation, scale_shear=scale_shear)
        
        inverted_matrix = matrix_world.inverted()
        self.inverse_transform = (c_float * 4 * 4)(
            (inverted_matrix[0][0], inverted_matrix[0][1], inverted_matrix[0][2], inverted_matrix[0][3]),
            (inverted_matrix[1][0], inverted_matrix[1][1], inverted_matrix[1][2], inverted_matrix[1][3]),
            (inverted_matrix[2][0], inverted_matrix[2][1], inverted_matrix[2][2], inverted_matrix[2][3]),
            (inverted_matrix[3][0], inverted_matrix[3][1], inverted_matrix[3][2], inverted_matrix[3][3]),
        )
    
class Skeleton:
    def __init__(self, skeleton: VirtualSkeleton, skeleton_node, all_nodes: dict[VirtualNode]):
        self.granny = None
        self.lod = 0
        self.name = skeleton_node.name.encode()
        self.bones: list[Bone] = []
        self._get_bones(skeleton, all_nodes)
        
    def _get_bones(self, skeleton: VirtualSkeleton, all_nodes):
        # if a virtual bone has no node then it comes from a blender bone. If it does have a node then it came from
        # an object and we need to check its in scope for this export
        self.bones = [Bone(bone) for bone in skeleton.bones if not bone.node or all_nodes.get(bone.name)]
    
class Color:
    red: float
    green: float
    blue: float
    
class Vertex:
    def __init__(self, index: int, mesh: VirtualMesh, transformed_positions: np.ndarray, transformed_normals: np.ndarray):
        self.position = (c_float * 3)(*transformed_positions[index])
        self.normal = (c_float * 3)(*transformed_normals[index])
        
        self.bone_weights = (c_ubyte * 4)(255,0,0,0)
        self.bone_indices = (c_ubyte * 4)(0,0,0,0)
        
        # Bone data, need to limit this to the 4 highest weights and normalise
        # v_groups = [(g.group, g.weight) for g in vert.groups]
        # v_groups.sort(key=lambda x: x[1], reverse=True)
        
        # if len(groups) > 4:
        #     groups = groups[:4]
        
        # UVs
        num_texcoord_layers = len(mesh.texcoords)
        self.uvs0 = (c_float * 3)(0,0,0)
        self.uvs1 = (c_float * 3)(0,0,0)
        self.uvs2 = (c_float * 3)(0,0,0)
        self.uvs3 = (c_float * 3)(0,0,0)
        self.lighting_uv = (c_float * 3)(0,0,0)
        if num_texcoord_layers > 0:
            self.uvs0 = (c_float * 3)(mesh.texcoords[0][index][0],mesh.texcoords[0][index][1],0)
            if num_texcoord_layers > 1:
                self.uvs1 = (c_float * 3)(mesh.texcoords[1][index][0],mesh.texcoords[1][index][1],0)
                if num_texcoord_layers > 2:
                    self.uvs2 = (c_float * 3)(mesh.texcoords[2][index][0],mesh.texcoords[2][index][1],0)
                    if num_texcoord_layers > 3:
                        self.uvs3 = (c_float * 3)(mesh.texcoords[3][index][0],mesh.texcoords[3][index][1],0)
                        
        if mesh.lighting_texcoords is not None:
            self.lighting_uv = (c_float * 3)(mesh.lighting_texcoords[index][0],mesh.lighting_texcoords[index][1],0)

        self.vertex_color0 = (c_float * 3)(0,0,0)
        self.vertex_color1 = (c_float * 3)(0,0,0)
        
        num_vertex_colors = len(mesh.vertex_colors)
        
        if num_vertex_colors > 0:
            self.vertex_color0 = (c_float * 3)(*mesh.vertex_colors[0][index][:2])
            if num_vertex_colors > 1:
                self.vertex_color1 = (c_float * 3)(*mesh.vertex_colors[1][index][:2])
        
        self.blend_shape = (c_float * 3)(0,0,0)
        self.vertex_id = (c_float * 2)(0,0)
        
        # for idx, texcoord in enumerate(mesh.texcoords):
        #     setattr(self, f"uvs{idx}", (c_float * 3)(*texcoord[index] + 0.0))
            
        # if mesh.lighting_texcoords:
        #     self.lighting_uv = (c_float * 3)(*mesh.lighting_texcoords[index])
            
        # vertex_colors = [color_layer for color_layer in mesh.vertex_colors]
        # for idx, layer in enumerate(vertex_colors):
        #     if idx > 1: break
        #     color = layer.data[vert_index].color
        #     setattr(self, f"vertex_color{str(idx)}", (c_float * 3)(color[0], color[1], color[2]))
    
class VertexData:
    vertices: list[Vertex]
    
    def __init__(self, node: VirtualNode):
        self.vertices = []
        mesh = node.mesh
        if node.matrix_world == identity_matrix:
            self.vertices = [Vertex(i, mesh, mesh.positions, mesh.normals) for i in range(mesh.num_vertices)]
        else:
            transformed_positions = mesh.positions @ node.matrix_world.to_3x3()
            transformed_normals = mesh.normals @ node.matrix_world.to_3x3()
            self.vertices = [Vertex(i, mesh, transformed_positions, transformed_normals) for i in range(mesh.num_vertices)]
            
        self.granny = None
    
class Group:
    material_index: int
    tri_start: int
    tri_count: int
    
    def __init__(self, material_index, tri_start, tri_count):
        self.material_index = material_index
        self.tri_start = tri_start
        self.tri_count = tri_count
    
# class Triangle:
#     material_index: int
#     indices: tuple[int, int, int]
    
#     def __init__(self, face: bpy.types.MeshPolygon):
#         self.material_index = face.material_index
#         self.indices = (face.vertices[0], face.vertices[1], face.vertices[2])
        
class TriAnnotationSet:
    def __init__(self, bm: bmesh.types.BMesh, layer: bmesh.types.BMLayerItem, name: str, value: int | float, default: int | float):
        self.name = name.encode()
        num_faces = len(bm.faces)
        annotations = [default] * num_faces
        for idx, face in enumerate(bm.faces):
            if face[layer]:
                annotations[idx] = value
                
        self.tri_annotations = (c_int * num_faces)(*annotations)
    
class TriTopology:
    groups: list
    indices: c_int
    
    def __init__(self, mesh: VirtualMesh):
        self.groups = []
        self.granny = None
        self.indices = (c_int * len(mesh.indices))(*mesh.indices)
        self.groups = [Group(i, tri_start, tri_count) for i, (tri_start, tri_count) in enumerate(mesh.materials.values())]
            
        self._setup_tri_annotations(mesh)
            
    def _setup_tri_annotations(self, mesh):
        self.tri_annotation_sets = []
        # bm = bmesh.new()
        # bm.from_mesh(mesh)
        # for prop in mesh.nwo.face_props:
        #     if prop.face_two_sided:
        #         layer = bm.faces.layers.int.get(prop.layer_name)
        #         if layer:
        #             self.tri_annotation_sets.append(TriAnnotationSet(bm, layer, "bungie_face_sides", FaceSides.two_sided.value, 0))
        
class BoneBinding:
    name: bytes
    def __init__(self, name: str):
        self.name = name.encode()
    
class Mesh(Properties):
    def __init__(self, node: VirtualNode, data_index: int, materials: dict):
        super().__init__(node)
        self.granny = None
        self.name = node.name.encode()
        self.primary_vertex_data_index = data_index
        self.primary_topology_index = data_index
        mesh = node.mesh
        self.material_bindings = [mat.index for mat in mesh.materials]
        self.bone_bindings = []
        # if ob.parent:
        #     if ob.parent_type == 'BONE':
        #         self.bone_bindings = [BoneBinding(ob.parent_bone)]
        #     elif ob.parent.type == 'ARMATURE':
        #         armature = ob.parent
        #         bone_names = [bone.name for bone in armature.data.bones]
        #         vertex_groups = ob.vertex_groups
        #         bones_with_weight = set()
        #         # Loop through all vertices in the mesh
        #         for vertex in ob.data.vertices:
        #             for group in vertex.groups:
        #                 # Get the vertex group name
        #                 group_name = vertex_groups[group.group].name
        #                 # Check if this vertex group corresponds to a bone in the armature
        #                 if group_name in bone_names:
        #                     bones_with_weight.add(group_name)
        #         self.bone_bindings = [BoneBinding(bone) for bone in bones_with_weight]
        #     else:
        #         self.bone_bindings = [BoneBinding(ob.name)]
        # else:
        #     self.bone_bindings = [BoneBinding(ob.name)]

class Model:
    name: str
    skeleton_index: int
    initial_placement: GrannyTransform
    mesh_bindings: tuple[int]
    
    def __init__(self, model: VirtualModel, skeleton_index: int, mesh_binding_indexes: list[int]):
        self.name = model.name.encode()
        node = model.node
        self.skeleton_index = skeleton_index
        position, orientation, scale_shear = granny_transform_parts(node.matrix_local)
        self.initial_placement = GrannyTransform(flags=7, position=position, orientation=orientation, scale_shear=scale_shear)
        self.mesh_bindings = mesh_binding_indexes
        
        
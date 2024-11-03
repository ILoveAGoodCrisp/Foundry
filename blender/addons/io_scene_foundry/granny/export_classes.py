from ctypes import POINTER, Structure, c_char_p, c_float, c_int, c_ubyte, c_uint8, c_void_p, cast, memmove, pointer
from enum import Enum
from math import pi, radians
from typing import Literal
import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
import numpy as np

from .formats import GrannyDataTypeDefinition, GrannyMemberType, GrannyTransform

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

class Material():
    name: bytes
    def __init__(self, material):
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
    
class Bone():
    def __init__(self, bone):
        self.name = bone.name.encode()
        self.parent_index = bone.parent_index
        self.lod_error = 0.0
        self.local_transform = granny_transform_default
        self.inverse_transform = granny_inverse_transform_default
        self.set_transform(bone.matrix_world, bone.matrix_local)
        
    def set_transform(self, matrix_world: Matrix, matrix_local: Matrix):
        position, orientation, scale_shear = granny_transform_parts(matrix_local)
        self.local_transform = GrannyTransform(flags=7, position=position, orientation=orientation, scale_shear=scale_shear)
        
        inverted_matrix = matrix_world.inverted()
        # self.inverse_transform = (c_float * 4 * 4)(
        #     (inverted_matrix[0][0], inverted_matrix[0][1], inverted_matrix[0][2], inverted_matrix[0][3]),
        #     (inverted_matrix[1][0], inverted_matrix[1][1], inverted_matrix[1][2], inverted_matrix[1][3]),
        #     (inverted_matrix[2][0], inverted_matrix[2][1], inverted_matrix[2][2], inverted_matrix[2][3]),
        #     (inverted_matrix[3][0], inverted_matrix[3][1], inverted_matrix[3][2], inverted_matrix[3][3]),
        # )
        self.inverse_transform = (c_float * 4 * 4)(
            (inverted_matrix[0][0], inverted_matrix[1][0], inverted_matrix[2][0], inverted_matrix[3][0]),
            (inverted_matrix[0][1], inverted_matrix[1][1], inverted_matrix[2][1], inverted_matrix[3][1]),
            (inverted_matrix[0][2], inverted_matrix[1][2], inverted_matrix[2][2], inverted_matrix[3][2]),
            (inverted_matrix[0][3], inverted_matrix[1][3], inverted_matrix[2][3], inverted_matrix[3][3]),
        )
    
class Skeleton:
    def __init__(self, skeleton, skeleton_node, all_nodes: dict):
        self.granny = None
        self.lod = 0
        self.name = skeleton_node.name.encode()
        self.bones = []
        self._get_bones(skeleton, all_nodes)
        
    def _get_bones(self, skeleton, all_nodes):
        # if a virtual bone has no node then it comes from a blender bone. If it does have a node then it came from
        # an object and we need to check if its in scope for this export
        self.bones = [bone.granny_bone for bone in skeleton.bones if not bone.node or all_nodes.get(bone.name)]
    
class Color:
    red: float
    green: float
    blue: float
    
class Vertex:
    def __init__(self, index: int, mesh, transformed_positions: np.ndarray, transformed_normals: np.ndarray):
        self.position = (c_float * 3)(*transformed_positions[index])
        self.normal = (c_float * 3)(*transformed_normals[index])
        
        self.bone_weights = (c_ubyte * 4)(255,0,0,0)
        self.bone_indices = (c_ubyte * 4)(0,0,0,0)
        
        if mesh.vertex_weighted:
            self.bone_weights = (c_ubyte * 4)(*mesh.bone_weights[index])
            self.bone_indices = (c_ubyte * 4)(*mesh.bone_indices[index])
        
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
            self.vertex_color0 = (c_float * 3)(*mesh.vertex_colors[0][index])
            if num_vertex_colors > 1:
                self.vertex_color1 = (c_float * 3)(*mesh.vertex_colors[1][index])
        
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
    
    def __init__(self, node):
        self.vertices = []
        mesh = node.mesh
        self.affine3 = (c_float * 3)(0, 0, 0)
        self.linear3x3 = (c_float * 9)(0, 0, 0, 0, 0, 0, 0, 0, 0)
        self.inverse_linear3x3 = (c_float * 9)(0, 0, 0, 0, 0, 0, 0, 0, 0)
        matrix = node.matrix_world
        self.affine3 = (c_float * 3)(matrix[0][3], matrix[1][3], matrix[2][3])
        self.linear3x3 = (c_float * 9)(
            matrix[0][0], matrix[0][1], matrix[0][2],
            matrix[1][0], matrix[1][1], matrix[1][2],
            matrix[2][0], matrix[2][1], matrix[2][2]
        )
        
        # Extracting the 3x3 submatrix
        R = [
            [matrix[0][0], matrix[0][1], matrix[0][2]],
            [matrix[1][0], matrix[1][1], matrix[1][2]],
            [matrix[2][0], matrix[2][1], matrix[2][2]]
        ]

        # Helper function to calculate the determinant of a 3x3 matrix
        def determinant_3x3(m):
            return (
                m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) -
                m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0]) +
                m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
            )

        # Helper function to calculate the adjugate of a 3x3 matrix
        def adjugate_3x3(m):
            return [
                [(m[1][1] * m[2][2] - m[1][2] * m[2][1]), -(m[0][1] * m[2][2] - m[0][2] * m[2][1]), (m[0][1] * m[1][2] - m[0][2] * m[1][1])],
                [-(m[1][0] * m[2][2] - m[1][2] * m[2][0]), (m[0][0] * m[2][2] - m[0][2] * m[2][0]), -(m[0][0] * m[1][2] - m[0][2] * m[1][0])],
                [(m[1][0] * m[2][1] - m[1][1] * m[2][0]), -(m[0][0] * m[2][1] - m[0][1] * m[2][0]), (m[0][0] * m[1][1] - m[0][1] * m[1][0])]
            ]

        # Calculate the inverse if the determinant is not zero
        det = determinant_3x3(R)
        if det != 0:
            adj = adjugate_3x3(R)
            inv_R = [[adj[row][col] / det for col in range(3)] for row in range(3)]
        else:
            inv_R = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]  # Handle singular matrix case

        # Flatten the inverse matrix into a 1D array suitable for c_float * 9
        self.inverse_linear3x3 = (c_float * 9)(
            inv_R[0][0], inv_R[0][1], inv_R[0][2],
            inv_R[1][0], inv_R[1][1], inv_R[1][2],
            inv_R[2][0], inv_R[2][1], inv_R[2][2]
        )

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
    def __init__(self, name: str, array: np.ndarray):
        self.name = name.encode()
        self.type = 0
        c_type = c_int
        if array.dtype == np.single:
            self.type = 1
            c_type = c_float
            if array.shape[1] == 3:
                self.type = 2
        self.tri_annotations = (c_type * len(array))(*array)
    
class TriTopology:
    groups: list
    indices: c_int
    
    def __init__(self, mesh):
        self.groups = []
        self.granny = None
        self.indices = (c_int * len(mesh.indices))(*mesh.indices)
        self.groups = [Group(material_index, tri_start, tri_count) for _, material_index, (tri_start, tri_count) in mesh.materials]
        self.tri_annotation_sets = [TriAnnotationSet(k, v) for k, v in mesh.face_properties.items()]
            
            
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
    
class Mesh():
    def __init__(self, node, valid_siblings):
        self.granny = None
        self.name = node.name.encode()
        self.props = node.props
        mesh = node.mesh
        self.siblings = [s.encode() for s in mesh.siblings if s != node.name and s in valid_siblings]
        self.primary_vertex_data = node.granny_vertex_data
        self.primary_topology = node.mesh.granny_tri_topology
        self.materials = [mat.granny_material for mat in mesh.materials.keys()]
        self.bone_bindings = [BoneBinding(name) for name in node.bone_bindings]

class Model:
    name: str
    skeleton_index: int
    initial_placement: GrannyTransform
    mesh_bindings: tuple[int]
    
    def __init__(self, model, skeleton_index: int, mesh_binding_indices: list[int]):
        self.name = model.name.encode()
        node = model.node
        self.skeleton_index = skeleton_index
        position, orientation, scale_shear = granny_transform_parts(node.matrix_local)
        self.initial_placement = GrannyTransform(flags=7, position=position, orientation=orientation, scale_shear=scale_shear)
        self.mesh_bindings = mesh_binding_indices
from ctypes import Structure, c_char_p, c_float, c_int, c_ubyte, c_uint8, c_void_p, cast, pointer
from enum import Enum
from math import pi, radians
from typing import Literal
import bmesh
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector
import numpy as np

from .formats import GrannyDataTypeDefinition, GrannyTransform

from .. import utils
from ..export.export_info import *

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

def granny_transform_parts(bone: bpy.types.PoseBone | bpy.types.Object, parent: bpy.types.Object):
    if isinstance(bone, bpy.types.Object):
        world_matrix = bone.matrix_world.copy()
        local_matrix = bone.matrix_local.copy()
    else:
        if bone.parent:
            local_matrix = bone.parent.matrix.inverted() @ bone.matrix
        else:
            local_matrix = bone.matrix.copy()

        world_matrix = parent.matrix_world @ bone.matrix
        
    loc = local_matrix.to_translation()
    position = (c_float * 3)(loc[0], loc[1], loc[2])
    quaternion = local_matrix.to_quaternion()
    orientation = (c_float * 4)(quaternion[1], quaternion[2], quaternion[3], quaternion[0])
    scale = local_matrix.to_scale()
    normalized_matrix = local_matrix.normalized()
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
    
    return position, orientation, scale_shear, world_matrix
    
class Properties:
    properties = {}
    def __init__(self, id=None):
        if id: self.properties = utils.get_halo_props_for_granny(id)
        
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
    def __init__(self, material: bpy.types.Material):
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
    def __init__(self, bone: bpy.types.PoseBone | bpy.types.Object):
        # super().__init__(bone)
        self.name = bone.name.encode()
        self.parent_index = -1
        self.lod_error = 0.0
        self.local_transform = granny_transform_default
        self.inverse_transform = granny_inverse_transform_default
        
    def set_transform(self, bone: bpy.types.PoseBone | bpy.types.Object, parent: bpy.types.Object):
        position, orientation, scale_shear, world_matrix = granny_transform_parts(bone, parent)
        self.local_transform = GrannyTransform(flags=0, position=position, orientation=orientation, scale_shear=scale_shear)
        
        inverted_matrix = world_matrix.inverted()
        self.inverse_transform = (c_float * 4 * 4)(
            (inverted_matrix[0][0], inverted_matrix[0][1], inverted_matrix[0][2], inverted_matrix[0][3]),
            (inverted_matrix[1][0], inverted_matrix[1][1], inverted_matrix[1][2], inverted_matrix[1][3]),
            (inverted_matrix[2][0], inverted_matrix[2][1], inverted_matrix[2][2], inverted_matrix[2][3]),
            (inverted_matrix[3][0], inverted_matrix[3][1], inverted_matrix[3][2], inverted_matrix[3][3]),
        )
        # self.local_transform = granny_transform_default
        # self.inverse_transform = granny_inverse_transform_default_mesh
    
class Skeleton:
    name: bytes
    lod = 0
    bones: list[Bone]
    
    def __init__(self, ob: bpy.types.Object, all_objects: list[bpy.types.Object]):
        self.granny = None
        self.name = ob.name.encode()
        self._get_bones(ob, all_objects)
        
    def _get_bones(self, ob, all_objects):
        ob_bone = Bone(ob)
        ob_bone.set_transform(ob, ob)
        if ob.type != 'MESH':
            ob_bone.properties = utils.get_halo_props_for_granny(ob)
            
        self.bones = [ob_bone]
        if ob.type == 'ARMATURE':
            list_bones = [pbone.name for pbone in ob.pose.bones]
            for idx, bone in enumerate(ob.pose.bones):
                b = Bone(bone)
                b.set_transform(bone, ob)
                b.properties = utils.get_halo_props_for_granny(ob.data.bones[idx])
                if bone.parent:
                    # Add one to this since the root is the armature
                    b.parent_index = list_bones.index(bone.parent.name) + 1
                else:
                    b.parent_index = 0
                self.bones.append(b)
                
            child_index = 0
            for child in ob.children:
                if child in all_objects:
                    child_index += 1
                    b = Bone(child)
                    b.set_transform(child, ob)
                    if child.parent_type == 'BONE':
                        b.parent_index = list_bones.index(child.parent_bone) + 1
                    else:
                        b.parent_index = 0
                        
                    if child.type == 'EMPTY' or child.type == 'LIGHT':
                        b.properties = utils.get_halo_props_for_granny(child)
                        
                    self.bones.append(b)
                self.find_children(child, all_objects, child_index)
                    
        else:
            self.find_children(ob, all_objects)
                    
    def find_children(self, ob: bpy.types.Object, all_objects: list[bpy.types.Object], parent_index=0):
        child_index = parent_index
        for child in ob.children:
            if child in all_objects:
                child_index += 1
                b = Bone(child)
                b.set_transform(child, ob)
                b.parent_index = parent_index
                self.bones.append(b)
                self.find_children(child, all_objects, child_index)
    
class Color:
    red: float
    green: float
    blue: float
    
class Vertex:
    def __init__(self, mesh: bpy.types.Mesh, vert_index: int, vertex_uvs, transform_matrix: Matrix):
        # corner_normals = mesh.vertex_normals
        vert = mesh.vertices[vert_index]
        co = transform_matrix @ vert.co
        self.position = (c_float * 3)(*co.to_tuple())
        # normal = corner_normals[vert_index].vector.to_tuple()
        normal = vert.normal.to_tuple()
        self.normal = (c_float * 3)(*normal)
        
        self.bone_weights = (c_ubyte * 4)(255,0,0,0)
        self.bone_indices = (c_ubyte * 4)(0,0,0,0)
        
        # Bone data, need to limit this to the 4 highest weights and normalise
        # v_groups = [(g.group, g.weight) for g in vert.groups]
        # v_groups.sort(key=lambda x: x[1], reverse=True)
        
        # if len(groups) > 4:
        #     groups = groups[:4]
        
        # UVs
        
        self.uvs0 = (c_float * 3)(0,0,0)
        self.uvs1 = (c_float * 3)(0,0,0)
        self.uvs2 = (c_float * 3)(0,0,0)
        self.uvs3 = (c_float * 3)(0,0,0)
        self.lighting_uv = (c_float * 3)(0,0,0)
        self.vertex_color0 = (c_float * 3)(0,0,0)
        self.vertex_color1 = (c_float * 3)(0,0,0)
        self.blend_shape = (c_float * 3)(0,0,0)
        self.vertex_id = (c_float * 2)(0,0)
        
        # lighting_uv_layer = mesh.uv_layers.get("lighting")
        # if lighting_uv_layer:
        #     self.lighting_uv = (c_float * 3)(*lighting_uv_layer.data[vert_index].uv.to_tuple())
        # uv_layers = [uv_layer for uv_layer in mesh.uv_layers if uv_layer != lighting_uv_layer]
        # for idx, layer in enumerate(uv_layers):
        #     if idx > 3: break
        #     for face in mesh.polygons:
        #         for loop_index in face.loop_indices:
        #             if mesh.loops[loop_index].vertex_index == vert_index:
        #                 u, v = layer.data[loop_index].uv.to_tuple()
        #                 setattr(self, f"uvs{str(idx)}", (c_float * 3)(u, v, 0))
        
        if vertex_uvs:
            uv_set = vertex_uvs[vert_index]
            for idx, uv in enumerate(uv_set):
                u, v = uv[0], uv[1]
                setattr(self, f"uvs{str(idx)}", (c_float * 3)(u, v, 0))
            
        vertex_colors = [color_layer for color_layer in mesh.vertex_colors]
        for idx, layer in enumerate(vertex_colors):
            if idx > 1: break
            color = layer.data[vert_index].color
            setattr(self, f"vertex_color{str(idx)}", (c_float * 3)(color[0], color[1], color[2]))
    
class VertexData:
    vertices: list[Vertex]
    
    def __init__(self, ob: bpy.types.Object, vertex_uvs):
        self.vertices = []
        mesh = ob.data
        # mesh.transform(ob.matrix_world)
        for i in range(len(mesh.vertices)):
            self.vertices.append(Vertex(mesh, i, vertex_uvs, ob.matrix_world))
            
        self.granny = None
    
class Group:
    material_index: int
    tri_start: int
    tri_count: int
    
    def __init__(self, material_index, tri_start, tri_count):
        self.material_index = material_index
        self.tri_start = tri_start
        self.tri_count = tri_count
    
class Triangle:
    material_index: int
    indices: tuple[int, int, int]
    
    def __init__(self, face: bpy.types.MeshPolygon):
        self.material_index = face.material_index
        self.indices = (face.vertices[0], face.vertices[1], face.vertices[2])
        
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
    triangles: list
    
    def __init__(self, ob: bpy.types.Object):
        self.groups = []
        self.granny = None
        mesh = ob.data
        num_materials = len(mesh.materials)
        max_material_index = num_materials - 1
        self.triangles = [Triangle(face) for face in mesh.polygons]
        
        if num_materials > 1:
            # self.triangles.sort(key=lambda tri: tri.material_index)
            
            tri_index = 0
            current_material_index = self.triangles[0].material_index
            
            for i, tri in enumerate(self.triangles):
                if current_material_index == max_material_index: break
                elif tri.material_index != current_material_index:
                    self.groups.append(Group(current_material_index, tri_index, i - tri_index))
                    current_material_index = tri.material_index
                    tri_index = i
                    
            self.groups.append(Group(current_material_index, tri_index, len(self.triangles) - tri_index))
                
        else:
            self.groups = [Group(0, 0, len(self.triangles))]
            
        self._setup_tri_annotations(mesh)
            
    def _setup_tri_annotations(self, mesh):
        self.tri_annotation_sets = []
        bm = bmesh.new()
        bm.from_mesh(mesh)
        for prop in mesh.nwo.face_props:
            if prop.face_two_sided:
                layer = bm.faces.layers.int.get(prop.layer_name)
                if layer:
                    self.tri_annotation_sets.append(TriAnnotationSet(bm, layer, "bungie_face_sides", FaceSides.two_sided.value, 0))
        
class BoneBinding:
    name: bytes
    def __init__(self, name: str):
        self.name = name.encode()
    
class Mesh(Properties):
    def __init__(self, ob: bpy.types.Object, data_index: int, material_names: Enum):
        super().__init__(ob)
        self.granny = None
        self.name = ob.name.encode()
        self.primary_vertex_data_index = data_index
        self.primary_topology_index = data_index
        self.material_bindings = []
        for mat in ob.data.materials:
            self.material_bindings.append(material_names[mat.name].value)
        
        if ob.parent:
            if ob.parent_type == 'BONE':
                self.bone_bindings = [BoneBinding(ob.parent_bone)]
            elif ob.parent.type == 'ARMATURE':
                armature = ob.parent
                bone_names = [bone.name for bone in armature.data.bones]
                vertex_groups = ob.vertex_groups
                bones_with_weight = set()
                # Loop through all vertices in the mesh
                for vertex in ob.data.vertices:
                    for group in vertex.groups:
                        # Get the vertex group name
                        group_name = vertex_groups[group.group].name
                        # Check if this vertex group corresponds to a bone in the armature
                        if group_name in bone_names:
                            bones_with_weight.add(group_name)
                self.bone_bindings = [BoneBinding(bone) for bone in bones_with_weight]
            else:
                self.bone_bindings = [BoneBinding(ob.name)]
        else:
            self.bone_bindings = [BoneBinding(ob.name)]

class Model:
    name: str
    skeleton_index: int
    initial_placement: GrannyTransform
    mesh_bindings: tuple[int]
    
    def __init__(self, ob: bpy.types.Object, skeleton_index: int, ob_names: Enum, objects: set):
        self.name = ob.name.encode()
        self.skeleton_index = skeleton_index
        position, orientation, scale_shear, _ = granny_transform_parts(ob, ob)
        self.initial_placement = GrannyTransform(flags=7, position=position, orientation=orientation, scale_shear=scale_shear)
        self.mesh_bindings = []
        if ob.type == 'MESH':
            self.mesh_bindings.append(ob_names[ob.name].value)
        for child in ob.children_recursive:
            if child not in objects: continue
            self.mesh_bindings.append(ob_names[child.name].value)
        
        
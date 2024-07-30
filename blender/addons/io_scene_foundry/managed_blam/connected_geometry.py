"""Classes to help with importing geometry from tags"""

from enum import Enum
from typing import Iterable
import bpy
from mathutils import Matrix, Quaternion, Vector
import numpy as np

from .. import utils
from .Tags import TagFieldBlock, TagFieldBlockElement


class Face:
    index: int
    indices: list[int]
    part: 'MeshPart'
    
    def __init__(self,indices: list[int], part: 'MeshPart', index: int):
        self.indices = indices
        self.part = part
        self.index = index

class Node:
    index: int
    name: str
    translation: Vector
    rotation: Quaternion
    inverse_forward: Vector
    inverse_left: Vector
    inverse_up: Vector
    inverse_position: Vector
    inverse_scale: Vector
    transform_matrix: Matrix
    parent = ""
    bone: bpy.types.EditBone
    def __init__(self, name):
        self.name = name

class Permutation:
    region: 'Region'
    index: int
    name: str
    mesh_index: int
    mesh_count: int
    instances: list[int]
    clone_name: str
    
    def __init__(self, element: TagFieldBlockElement, region: 'Region'):
        self.region = region
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()
        self.mesh_index = int(element.SelectField("mesh index").GetStringData())
        self.mesh_count = int(element.SelectField("mesh count").GetStringData())
        self.clone_name = ""
        if utils.is_corinth():
            self.clone_name = element.SelectField("clone name").GetStringData()
        flags_1 = element.SelectField("instance mask 0-31")
        for i in range(31):
            if flags_1.TestBit(str(i)):
                self.instances.append(i)
        flags_2 = element.SelectField("instance mask 32-63")
        for i in range(31):
            if flags_2.TestBit(str(i)):
                self.instances.append(i)
        flags_3 = element.SelectField("instance mask 64-95")
        for i in range(31):
            if flags_3.TestBit(str(i)):
                self.instances.append(i)
    
class Region:
    index: int
    name: str
    permutations_block: TagFieldBlock
    permutations: list[Permutation]
    
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()
        self.permutations_block = element.SelectField("permutations")
        self.permutations = []
        for element in self.permutations_block.Elements:
            self.permutations.append(Permutation(element, self))
    
class Instances:
    index: int
    name: str
    node_index: int
    scale: float
    forward: list[float, float, float]
    left: list[float, float, float]
    up: list[float, float, float]
    position: list[float, float, float]
    
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()

class RenderArmature():
    def __init__(self, name):
        self.data = bpy.data.armatures.new(name)
        self.ob = bpy.data.objects.new(name, self.data)
        self.bones: Node = []
        
    def create_bone(self, node: Node):
        bone = self.data.edit_bones.new(node.name)
        bone.length = 5
        
        loc = (node.inverse_position)
        rot = Matrix((node.inverse_forward, node.inverse_left, node.inverse_up))
        scale = Vector.Fill(3, node.inverse_scale)
        transform_matrix = Matrix.LocRotScale(loc, rot, scale)
        
        try:
            transform_matrix.invert()
        except:
            transform_matrix.identity()
        
        transform_matrix = Matrix.Translation(node.translation) @ node.rotation.to_matrix().to_4x4()
        node.transform_matrix = transform_matrix
        bone.matrix = transform_matrix
        node.bone = bone
        
    def parent_bone(self, node: Node):
        if node.parent:
            parent = self.data.edit_bones[node.parent]
            node.bone.parent = parent
            transform_matrix = parent.matrix @ node.transform_matrix
            node.bone.matrix = transform_matrix
            
class CompressionBounds:
    co_matrix: Matrix
    u0: float
    v0: float
    u1: float
    v1: float
    
    def __init__(self, element: TagFieldBlockElement):
        first = element.SelectField("position bounds 0").GetStringData()
        second = element.SelectField("position bounds 1").GetStringData()
        
        x0 = float(first[0]) * 100
        x1 = float(first[1]) * 100
        y0 = float(first[2]) * 100
        y1 = float(second[0]) * 100
        z0 = float(second[1]) * 100
        z1 = float(second[2]) * 100
        
        self.co_matrix = Matrix((
            (x1-x0, 0, 0, x0),
            (0, y1-y0, 0, y0),
            (0, 0, z1-z0, z0),
            (0, 0, 0, 1),
        ))
        
        third = element.SelectField("texcoord bounds 0").GetStringData()
        fourth = element.SelectField("texcoord bounds 1").GetStringData()
        
        self.u0 = float(third[0])
        self.u1 = float(third[1])
        self.v0 = float(fourth[0])
        self.v1 = float(fourth[1])

class Material:
    index: int
    name: str
    new: bool
    shader_path: str
    emissive_index: int
    lm_res: int
    lm_transparency: list[float]
    lm_translucency: list[float]
    lm_both_sides: bool
    blender_material: bpy.types.Material
    
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.new = False
        render_method_path = element.SelectField("render method").Path
        self.name = render_method_path.ShortName
        self.shader_path = render_method_path.RelativePathWithExtension
        self.emissive_index = int(element.SelectField("imported material index").GetStringData())
        self.lm_res = int(element.SelectField("imported material index").GetStringData())
        self.blender_material = self._get_blender_material()
        
    def _get_blender_material(self):
        mat = bpy.data.materials.get(self.name)
        if not mat:
            mat = bpy.data.materials.new(self.name)
            mat.nwo.shader_path = self.shader_path
            self.new = True
            
        return mat
    
class IndexLayoutType(Enum):
    DEFAULT = 0
    LINE_LIST = 1
    LINE_STRIP = 2
    TRIANGLE_LIST = 3
    TRIANGLE_FAN = 4
    TRIANGLE_STRIP = 5
    QUAD_LIST = 6
    RECT_LIST = 7
    
class IndexBuffer:
    index_buffer_type: IndexLayoutType
    indices: list[int]

    def __init__(self, index_buffer_type: int, indices: list[int]):
        self.index_layout = IndexLayoutType(index_buffer_type)
        self.indices = indices

    def get_faces(self, mesh: 'Mesh') -> list[Face]:
        faces = []
        idx = 0
        for part in mesh.parts:
            start = part.index_start
            count = part.index_count
            indices = self._get_indices(start, count)
            for i in indices:
                faces.append(Face(indices=i, part=part, index=idx))
                idx += 1

        return faces
    
    def _get_indices(self, start: int, count: int):
        end = len(self.indices) if count < 0 else start + count
        subset = [self.indices[i:i+3] for i in range(start, end, 3)]
        if self.index_layout == IndexLayoutType.TRIANGLE_LIST:
            return subset
        elif self.index_layout == IndexLayoutType.TRIANGLE_STRIP:
            return self._unpack(subset)
        else:
            raise (f"Unsupported Index Layout Type {self.index_layout}")

    def _unpack(self, indices: list[int]) -> list[int]:
        faces = []
        i0, i1, i2 = 0, 0, 0
        for pos, idx in enumerate(indices):
            tri = []
            i0, i1, i2 = i1, i2, idx
            if pos < 2 or i0 == i1 or i0 == i2 or i1 == i2: continue
            tri.append(i0)
            if pos % 2 == 0:
                tri.append(i1)
                tri.append(i2)
            else:
                tri.append(i2)
                tri.append(i1)
                
            faces.append(tri)
            
        return faces

class MeshPart:
    index: int
    material_index: int
    material: Material
    transparent: bool
    index_start: int
    index_count: int
    draw_cull_medium: bool
    draw_cull_close: bool
    tessellation: int
    
    def __init__(self, element: TagFieldBlockElement):
        self.index = element.ElementIndex
        self.material_index = element.SelectField("render method index").Value
        self.transparent = element.SelectField("transparent sorting index").Value > -1
        self.index_start = int(element.SelectField("index start").GetStringData())
        self.index_count = int(element.SelectField("index count").GetStringData())
        
    def create(self, ob: bpy.types.Object, tris: Face):
        mesh = ob.data
        faces = mesh.polygons
        blend_material = self.material.blender_material
        if not mesh.materials.get(blend_material.name):
            mesh.materials.append(blend_material)
        blend_material_index = ob.material_slots.find(blend_material.name)
        faces = mesh.polygons
        for t in tris:
            faces[t.index].material_index = blend_material_index

class Mesh:
    index: int
    permutation: Permutation
    parts: list[MeshPart]
    rigid_node_index: int
    index_buffer_type: int
    bounds: CompressionBounds
    ob: bpy.types.Object
    tris: Iterable[Face]
    
    def __init__(self, element: TagFieldBlockElement, bounds: CompressionBounds, permutation: Permutation):
        self.index = element.ElementIndex
        self.permutation = permutation
        self.rigid_node_index = int(element.SelectField("rigid node index").GetStringData())
        self.index_buffer_type =  int(element.SelectField("index buffer type").Value)
        self.bounds = bounds
        self.parts = []
        for part_element in element.SelectField("parts").Elements:
            self.parts.append(MeshPart(part_element))
            
    def _true_uvs(self, raw_texcoords):
        raw_uvs = [raw_texcoords[n:n+2] for n in range(0, len(raw_texcoords), 2)]
        return [self._interp_uv(raw_uv) for raw_uv in raw_uvs]
    
    def _interp_uv(self, raw_uv):
        u = np.interp(raw_uv[0], (0, 1), (self.bounds.u0, self.bounds.u1))
        v = np.interp(raw_uv[1], (0, 1), (self.bounds.v0, self.bounds.v1))
        
        return Vector((u, 1-v)) # 1-v to correct UV for Blender
        
    def create(self, render_model, temp_meshes: TagFieldBlock, nodes, armature: bpy.types.Object, name):
        mesh = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(mesh.name, mesh)
        self.ob = ob
        temp_mesh = temp_meshes.Elements[self.index]
        raw_vertices = temp_mesh.SelectField("raw vertices")
        raw_indices = temp_mesh.SelectField("raw indices")
        # Vertices & Faces
        raw_positions = [n for n in render_model.GetPositionsFromMesh(temp_meshes, self.index)]
        raw_coords = [raw_positions[n:n+3] for n in range(0, len(raw_positions), 3)]
        indices = [int(element.Fields[0].GetStringData()) for element in raw_indices.Elements]
        buffer = IndexBuffer(self.index_buffer_type, indices)
        self.tris = buffer.get_faces(self)
        mesh.from_pydata(vertices=raw_coords, edges=[], faces=[t.indices for t in self.tris])
        mesh.transform(self.bounds.co_matrix)
        
        # UVs
        raw_texcoords = [n for n in render_model.GetTexCoordsFromMesh(temp_meshes, self.index)]
        uvs = self._true_uvs(raw_texcoords)
        uv_layer = mesh.uv_layers.new(name="UVMap0", do_init=False)
        for face in mesh.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uv_layer.data[loop_idx].uv = uvs[vert_idx]
                
        # Normals
        raw_normals = [n for n in render_model.GetNormalsFromMesh(temp_meshes, self.index)]
        raw_normal_coords = [Vector(raw_normals[n:n+3]).normalized() for n in range(0, len(raw_normals), 3)]
        mesh.normals_split_custom_set_from_vertices(raw_normal_coords)
        
        # Object
        if armature:
            ob.parent = armature
            
        # Weights
        if self.rigid_node_index > -1:
            mat = ob.matrix_world.copy()
            ob.parent_type = "BONE"
            ob.parent_bone = nodes[self.rigid_node_index].name
            ob.matrix_world = mat
            
        else:
            raw_node_indices = [n for n in render_model.GetNodeIndiciesFromMesh(temp_meshes, self.index)]
            raw_node_weights = [n for n in render_model.GetNodeWeightsFromMesh(temp_meshes, self.index)]
            node_indices = [raw_node_indices[n:n+4] for n in range(0, len(raw_node_indices), 4)]
            node_weights = [raw_node_weights[n:n+4] for n in range(0, len(raw_node_weights), 4)]
            
            vgroups = ob.vertex_groups
            
            for idx, (indices, weights) in enumerate(zip(node_indices, node_weights)):
                for i, w in zip(indices, weights):
                    if i < 0 or w <= 0: continue
                    group = vgroups.get(nodes[i].name)
                    if not group:
                        group = vgroups.new(name=nodes[i].name)
                        
                    group.add([idx], w, 'REPLACE')
            
            ob.modifiers.new(name="Armature", type="ARMATURE").object = armature
            
        # Materials
        for part in self.parts:
            relevant_tris = [t for t in self.tris if t.part == part]
            part.create(ob, relevant_tris)
        
        return ob
    
class MarkerType(Enum):
    _connected_geometry_marker_type_model = 0
    _connected_geometry_marker_type_effects = 1
    _connected_geometry_marker_type_garbage = 2
    _connected_geometry_marker_type_hint = 3
    _connected_geometry_marker_type_pathfinding_sphere = 4
    _connected_geometry_marker_type_physics_constraint = 5
    _connected_geometry_marker_type_target = 6

class Marker:
    index: int
    region: Region
    permutation: Permutation
    bone: str
    translation: Vector
    rotation: Quaternion
    scale: float
    direction: list[float, float, float]
    linked_to: list['Marker']
    
    def __init__(self, element: TagFieldBlockElement, nodes: list[Node], regions: list[Region]):
        self.region = ""
        self.permutation = ""
        self.bone = ""
        self.translation = []
        self.rotation = []
        self.scale = 0.01
        self.direction = []
        region_index = int(element.SelectField("region index").GetStringData())
        permutation_index = int(element.SelectField("permutation index").GetStringData())
        node_index = int(element.SelectField("node index").GetStringData())
        if region_index > -1:
            self.region = next(r for r in regions if r.index == region_index)
            if permutation_index > -1:
                self.permutation = next(p for p in self.region.permutations if p.index == permutation_index)
                
        if node_index > -1:
            self.bone = next(n.name for n in nodes if n.index == node_index)
        
        self.translation = [float(n) * 100 for n in element.SelectField("translation").GetStringData()]
        
        self.rotation = utils.ijkw_to_wxyz([float(n) for n in element.SelectField("rotation").GetStringData()])
        self.scale = float(element.SelectField("scale").GetStringData()) * 100
        self.direction = ([float(n) for n in element.SelectField("direction").GetStringData()])
    
class MarkerGroup:
    name: str
    type: MarkerType
    index: int
    markers: list[Marker]
    
    def __init__(self, element: TagFieldBlockElement, nodes: list[Node], regions: list[Region]):
        self.name = element.SelectField("name").GetStringData()
        self.index = element.ElementIndex
        
        self.type = MarkerType._connected_geometry_marker_type_model
        if self.name.startswith("fx_"):
            self.type = MarkerType._connected_geometry_marker_type_effects
        elif self.name.startswith("target_"):
            self.type = MarkerType._connected_geometry_marker_type_target
        elif self.name.startswith("garbage_"):
            self.type = MarkerType._connected_geometry_marker_type_garbage
            
        self.markers = []
        for e in element.SelectField("markers").Elements:
            self.markers.append(Marker(e, nodes, regions))
            
    def to_blender(self, armature: bpy.types.Object, collection: bpy.types.Collection):
        # Find duplicate markers
        objects = []
        skip_markers = []
        for marker in self.markers:
            if marker in skip_markers: continue
            for marker2 in self.markers:
                if marker2 == marker: continue
                if marker.translation == marker2.translation and marker.rotation == marker2.translation:
                    marker.linked_to.append(marker2)
                    skip_markers.append(marker2)
                    
        remaining_markers = [m for m in self.markers if m not in skip_markers]
        
        for marker in remaining_markers:
            ob = bpy.data.objects.new(name=self.name, object_data=None)
            collection.objects.link(ob)
            ob.parent = armature
            ob.parent_type = "BONE"
            ob.parent_bone = marker.bone
            ob.matrix_local = Matrix.LocRotScale(marker.translation, marker.rotation, Vector.Fill(3, marker.scale))
            nwo = ob.nwo
            nwo.marker_type_ui = self.type.name
            objects.append(ob)
            
        return objects
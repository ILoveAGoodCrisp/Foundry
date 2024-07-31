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
    subpart: 'MeshPart'
    
    def __init__(self,indices: list[int], subpart: 'MeshSubpart', index: int):
        self.indices = indices
        self.subpart = subpart
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
    instance_indexes: list[int]
    clone_name: str
    
    def __init__(self, element: TagFieldBlockElement, region: 'Region'):
        self.region = region
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()
        self.mesh_index = int(element.SelectField("mesh index").GetStringData())
        self.mesh_count = int(element.SelectField("mesh count").GetStringData())
        self.clone_name = ""
        self.instance_indexes = []
        if utils.is_corinth():
            self.clone_name = element.SelectField("clone name").GetStringData()
        flags_1 = element.SelectField("instance mask 0-31")
        for i in range(31):
            if flags_1.TestBit(str(i)):
                self.instance_indexes.append(i)
        flags_2 = element.SelectField("instance mask 32-63")
        for i in range(31):
            if flags_2.TestBit(str(i)):
                self.instance_indexes.append(i + 32)
        flags_3 = element.SelectField("instance mask 64-95")
        for i in range(31):
            if flags_3.TestBit(str(i)):
                self.instance_indexes.append(i + 64)
    
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
        
        self.x0 = float(first[0]) * 100
        self.x1 = float(first[1]) * 100
        self.y0 = float(first[2]) * 100
        self.y1 = float(second[0]) * 100
        self.z0 = float(second[1]) * 100
        self.z1 = float(second[2]) * 100
        
        self.co_matrix = Matrix((
            (self.x1-self.x0, 0, 0, self.x0),
            (0, self.y1-self.y0, 0, self.y0),
            (0, 0, self.z1-self.z0, self.z0),
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
        for subpart in mesh.subparts:
            start = subpart.index_start
            count = subpart.index_count
            indices = self._get_indices(start, count)
            for i in indices:
                faces.append(Face(indices=i, subpart=subpart, index=idx))
                idx += 1
        
        return faces
    
    def _get_indices(self, start: int, count: int):
        end = len(self.indices) if count < 0 else start + count
        subset = [self.indices[i] for i in range(start, end)]
        if self.index_layout == IndexLayoutType.TRIANGLE_LIST:
            return [subset[n:n+3] for n in range(0, len(subset), 3)], 
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
    
    def __init__(self, element: TagFieldBlockElement, materials: list[Material]):
        self.index = element.ElementIndex
        self.material_index = element.SelectField("render method index").Value
        self.transparent = element.SelectField("transparent sorting index").Value > -1
        self.index_start = int(element.SelectField("index start").GetStringData())
        self.index_count = int(element.SelectField("index count").GetStringData())
        
        self.material = next(m for m in materials if m.index == self.material_index)
            
class MeshSubpart:
    index: int
    index_start: int
    index_count: int
    part_index: int
    part: MeshPart
    
    def __init__(self, element: TagFieldBlockElement, parts: list[MeshPart]):
        self.index = element.ElementIndex
        self.index_start = int(element.SelectField("index start").GetStringData())
        self.index_count = int(element.SelectField("index count").GetStringData())
        self.part_index = element.SelectField("part index").Value
        self.part = next(p for p in parts if p.index == self.part_index)
        
    def create(self, ob: bpy.types.Object, tris: Face):
        mesh = ob.data
        faces = mesh.polygons
        blend_material = self.part.material.blender_material
        if not mesh.materials.get(blend_material.name):
            mesh.materials.append(blend_material)
        blend_material_index = ob.material_slots.find(blend_material.name)
        faces = mesh.polygons
        indexes = [t.index for t in tris if t.subpart == self]
        for i in indexes:
            faces[i].material_index = blend_material_index
            

class Mesh:
    '''All new Halo 3 render geometry definitions!'''
    index: int
    permutation: Permutation
    parts: list[MeshPart]
    subparts: list[MeshSubpart]
    rigid_node_index: int
    index_buffer_type: int
    bounds: CompressionBounds
    ob: bpy.types.Object
    tris: Iterable[Face]
    raw_positions: list
    raw_texcoords : list
    raw_normals: list
    raw_node_indices: list
    raw_node_weights: list
    
    def __init__(self, element: TagFieldBlockElement, bounds: CompressionBounds, permutation: Permutation, materials: list[Material]):
        self.index = element.ElementIndex
        self.permutation = permutation
        self.rigid_node_index = int(element.SelectField("rigid node index").GetStringData())
        self.index_buffer_type =  int(element.SelectField("index buffer type").Value)
        self.bounds = bounds
        self.parts = []
        self.subparts = []
        
        for part_element in element.SelectField("parts").Elements:
            self.parts.append(MeshPart(part_element, materials))
        for subpart_element in element.SelectField("subparts").Elements:
            self.subparts.append(MeshSubpart(subpart_element, self.parts))
            
        self.raw_positions = []
        self.raw_texcoords = []
        self.raw_normals = []
        self.raw_node_indices = []
        self.raw_node_weights = []
            
    def _true_uvs(self, texcoords):
        return [self._interp_uv(tc) for tc in texcoords]
    
    def _interp_uv(self, texcoord):
        u = np.interp(texcoord[0], (0, 1), (self.bounds.u0, self.bounds.u1))
        v = np.interp(texcoord[1], (0, 1), (self.bounds.v0, self.bounds.v1))
        
        return Vector((u, 1-v)) # 1-v to correct UV for Blender
    
    def create(self, render_model, temp_meshes: TagFieldBlock, nodes, parent: bpy.types.Object | None, instances: list['InstancePlacement'] = []):
        temp_mesh = temp_meshes.Elements[self.index]
        raw_indices = temp_mesh.SelectField("raw indices")
        # Vertices & Faces
        self.raw_positions = [n for n in render_model.GetPositionsFromMesh(temp_meshes, self.index)]
        self.raw_texcoords = [n for n in render_model.GetTexCoordsFromMesh(temp_meshes, self.index)]
        self.raw_normals = [n for n in render_model.GetNormalsFromMesh(temp_meshes, self.index)]
        if not instances and self.rigid_node_index == -1:
            self.raw_node_indices = [n for n in render_model.GetNodeIndiciesFromMesh(temp_meshes, self.index)]
            self.raw_node_weights = [n for n in render_model.GetNodeWeightsFromMesh(temp_meshes, self.index)]

        objects = []
        
        indices = [utils.fix_tag_int(int(element.Fields[0].GetStringData())) for element in raw_indices.Elements]
        buffer = IndexBuffer(self.index_buffer_type, indices)
        self.tris = buffer.get_faces(self)
            
        if instances:
            for instance in instances:
                subpart = self.subparts[instance.index]
                ob = self._create_mesh(instance.name, parent, nodes, subpart, instance.bone, instance.matrix)
                ob.scale = Vector.Fill(3, instance.scale)
                instance.ob = ob
                objects.append(ob)
        else:
            if self.permutation:
                name = f"{self.permutation.region.name}:{self.permutation.name}"
            else:
                name = "blam"
            objects.append(self._create_mesh(name, parent, nodes, None))
            
        return objects
    
    def _create_mesh(self, name, parent, nodes, subpart: MeshSubpart | None, parent_bone=None, local_matrix=None):
        if subpart is None:
            indices = [t.indices for t in self.tris]
        else:
            indices = [t.indices for t in self.tris if t.subpart == subpart]
            
        vertex_indexes = sorted({idx for i in indices for idx in i})
        
        idx_start, idx_end = vertex_indexes[0], vertex_indexes[-1]
            
        mesh = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, mesh)
        
        positions = [self.raw_positions[n:n+3] for idx, n in enumerate(range(0, len(self.raw_positions), 3)) if idx >= idx_start and idx <= idx_end]
        texcoords = [self.raw_texcoords[n:n+2] for idx, n in enumerate(range(0, len(self.raw_texcoords), 2)) if idx >= idx_start and idx <= idx_end]
        normals = [self.raw_normals[n:n+3] for idx, n in enumerate(range(0, len(self.raw_normals), 3)) if idx >= idx_start and idx <= idx_end]
        if idx_start > 0:
            indices = [[i - idx_start for i in tri] for tri in indices]
                    
        mesh.from_pydata(vertices=positions, edges=[], faces=indices)
        mesh.transform(self.bounds.co_matrix)
        
        print(name)
        
        uvs = self._true_uvs(texcoords)
        uv_layer = mesh.uv_layers.new(name="UVMap0", do_init=False)
        for face in mesh.polygons:
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uv_layer.data[loop_idx].uv = uvs[vert_idx]
                
        normalised_normals = [Vector(n).normalized() for n in normals]
        mesh.normals_split_custom_set_from_vertices(normalised_normals)
        
        if parent:
            ob.parent = parent
            if parent.type == 'ARMATURE':
                if self.rigid_node_index > -1:
                    if local_matrix:
                        ob.matrix_basis = local_matrix
                    mat = ob.matrix_world.copy()
                    ob.parent_type = "BONE"
                    if parent_bone:
                        ob.parent_bone = parent_bone
                    else:
                        ob.parent_bone = nodes[self.rigid_node_index].name
                    ob.matrix_world = mat
                else:
                    node_indices = [self.raw_node_indices[n:n+4] for idx, n in enumerate(range(0, len(self.raw_node_indices), 4)) if idx >= idx_start and idx <= idx_end]
                    node_weights = [self.raw_node_weights[n:n+4] for idx, n in enumerate(range(0, len(self.raw_node_weights), 4)) if idx >= idx_start and idx <= idx_end]
                    
                    vgroups = ob.vertex_groups
                    
                    for idx, (ni, nw) in enumerate(zip(node_indices, node_weights)):
                        for i, w in zip(ni, nw):
                            if i < 0 or w <= 0: continue
                            group = vgroups.get(nodes[i].name)
                            if not group:
                                group = vgroups.new(name=nodes[i].name)
                                
                            group.add([idx], w, 'REPLACE')
                    
                    ob.modifiers.new(name="Armature", type="ARMATURE").object = parent
        
        if subpart:
            ob.data.materials.append(subpart.part.material.blender_material)
        else:
            for subpart in self.subparts:
                subpart.create(ob, self.tris)
                    
        return ob
        
class InstancePlacement:
    index: int
    name: str
    node_index: int
    bone: str
    scale: float
    forward: Vector
    left: Vector
    up: Vector
    position: Vector
    matrix: Matrix
    ob: bpy.types.Object
    
    def __init__(self, element: TagFieldBlockElement, nodes: list[Node]):
        self.index = element.ElementIndex
        self.name = element.SelectField("name").GetStringData()
        self.node_index = element.SelectField("node_index").Value
        self.bone = ""
        if self.node_index > -1:
            self.bone = next(n.name for n in nodes if n.index == self.node_index)
        
        self.scale = float(element.SelectField("scale").GetStringData())
        self.forward = Vector([float(n) for n in element.SelectField("forward").GetStringData()])
        self.left = Vector([float(n) for n in element.SelectField("left").GetStringData()])
        self.up = Vector([float(n) for n in element.SelectField("up").GetStringData()])
        self.position = Vector([float(n) for n in element.SelectField("position").GetStringData()]) * 100
        
        self.matrix = Matrix((
            (self.forward[0], self.forward[1], self.forward[2], self.position[0]),
            (self.left[0], self.left[1], self.left[2], self.position[1]),
            (self.up[0], self.up[1], self.up[2], self.position[2]),
            (0, 0, 0, 1),
        ))
        
        self.ob = None
        
        
    
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
        self.linked_to = []
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
        self.scale = float(element.SelectField("scale").GetStringData())
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
        elif self.name.startswith("hint_"):
            self.type = MarkerType._connected_geometry_marker_type_hint
            
        self.markers = []
        for e in element.SelectField("markers").Elements:
            self.markers.append(Marker(e, nodes, regions))
            
    def to_blender(self, edit_armature: utils.EditArmature, collection: bpy.types.Collection, size_factor: float):
        # Find duplicate markers
        objects = []
        skip_markers = []
        for marker in self.markers:
            if marker in skip_markers: continue
            for marker2 in self.markers:
                if marker2 == marker: continue
                if marker.region and marker.region == marker2.region and marker.translation == marker2.translation and marker.rotation == marker2.rotation:
                    marker.linked_to.append(marker2)
                    skip_markers.append(marker2)
                    
        remaining_markers = [m for m in self.markers if m not in skip_markers]
        
        for marker in remaining_markers:
            ob = bpy.data.objects.new(name=self.name, object_data=None)
            collection.objects.link(ob)
            ob.parent = edit_armature.ob
            if marker.bone:
                world = edit_armature.matrices[marker.bone]
                ob.parent_type = "BONE"
                ob.parent_bone = marker.bone
                ob.matrix_world = world
                ob.matrix_local = Matrix.Translation([0, edit_armature.lengths[marker.bone], 0]).inverted() @ Matrix.LocRotScale(marker.translation, marker.rotation, Vector.Fill(3, 1))

            nwo = ob.nwo
            nwo.marker_type_ui = self.type.name
            if marker.region:
                nwo.marker_uses_regions = True
                utils.set_region(ob, marker.region.name)
                # Check if there is a marker for every permutation
                if marker.linked_to and len(marker.linked_to) + 1 != len(marker.region.permutations):
                    # If not pick if this is include or exclude type depending on whichever means less permutation entries need to be added
                    # If a tie prefer exclude
                    include_permutations = [m.permutation.name for m in marker.linked_to if m.permutation]
                    exclude_permutations = [p.name for p in marker.region.permutations if p.name not in include_permutations]
                    if len(include_permutations) < len(exclude_permutations):
                        nwo.marker_permutation_type = "include"
                        utils.set_marker_permutations(ob, include_permutations)
                    else:
                        utils.set_marker_permutations(ob, exclude_permutations)
                    
            
            ob.empty_display_type = "ARROWS"
            ob.empty_display_size *= size_factor
            
            if self.type == MarkerType._connected_geometry_marker_type_target:
                ob.empty_display_size = marker.scale * 100
                ob.empty_display_type = "SPHERE"
            elif self.type == MarkerType._connected_geometry_marker_type_garbage:
                ob.nwo.marker_velocity_ui = marker.direction
            elif self.type == MarkerType._connected_geometry_marker_type_hint:
                hint_parts = self.name.split('_')
                if len(hint_parts) > 1:
                    hint_type = hint_parts[1]
                    nwo.marker_hint_type = hint_type
                    if nwo.marker_hint_type != 'bunker' and len(hint_parts) > 2:
                        hint_subtype = hint_parts[2]
                        if hint_subtype in ('right', 'left'):
                            nwo.marker_hint_side = hint_subtype
                        elif hint_subtype in ('step', 'crouch', 'stand'):
                            nwo.marker_hint_height = hint_subtype
            
            objects.append(ob)
            
        return objects
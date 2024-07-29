# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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

from mathutils import Matrix, Quaternion, Vector
import numpy as np
from typing import List, Iterable, Iterator, overload
from .Tags import *

from .. import utils
from ..managed_blam import Tag
import bpy

class Face:
    index: int
    indices: list[int]
    part: 'MeshPart'
    
    def __init__(self,indices: list[int], part: 'MeshPart'):
        self.indices = indices
        self.part = part

class Node:
    index: int
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
    
class IndexBuffer:
    index_buffer_type: int
    indices: List[int]

    def __init__(self, index_buffer_type: int, indices: List[int]):
        self.index_layout = index_buffer_type
        self.indices = indices

    def get_faces(self, mesh: 'Mesh') -> list[Face]:
        faces = []
        for part in mesh.parts:
            start = part.index_start
            count = part.index_count
            indices = list(self._get_indices(start, count))
            for i in range(0, len(indices), 3):
                faces.append(Face(indices=indices[i:i+3], part=part))
                
        return faces
    
    def _get_indices(self, start: int, count: int) -> list[int]:
        end = len(self.indices) if count < 0 else start + count
        subset = (self.indices[i] for i in range(start, end))
        if self.index_layout == 3:
            return subset
        elif self.index_layout == 4:
            return self._unpack(subset)

    def _unpack(self, indices: Iterable[int]) -> list[int]:
        i0, i1, i2 = 0, 0, 0
        for pos, idx in enumerate(indices):
            i0, i1, i2 = i1, i2, idx
            if pos < 2 or i0 == i1 or i0 == i2 or i1 == i2: continue
            yield i0
            if pos % 2 == 0:
                yield i1
                yield i2
            else:
                yield i2
                yield i1

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
    clone_index: int
    parts: list[MeshPart]
    rigid_node_index: int
    index_buffer_type: int
    bounds: CompressionBounds
    ob: bpy.types.Object
    tris: list[Face]
    
    def __init__(self, element: TagFieldBlockElement, bounds: CompressionBounds, clone_index):
        self.index = element.ElementIndex
        self.clone_index = clone_index
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
            
    def create(self, render_model, temp_meshes: TagFieldBlock, nodes, armature: bpy.types.Object, name, meshes: list['Mesh']):
        if self.clone_index > -1: # is a clone
            hmesh = meshes[self.clone_index]
            ob = hmesh.ob.copy()
            ob.data = ob.data.copy()
            ob.data.materials.clear()
            self.tris = hmesh.tris
            self.ob = ob
        else:
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
            for idx, t in enumerate(self.tris):
                t.index = idx
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
    
class RenderModelTag(Tag):
    tag_ext = 'render_model'
    
    def _read_fields(self):
        self.reference_structure_meta_data = self.tag.SelectField("Reference:structure meta data") if self.corinth else None
        self.block_nodes = self.tag.SelectField("Block:nodes")
        self.struct_render_geometry = self.tag.SelectField("Struct:render geometry")
        self.block_compression_info = self.tag.SelectField("Struct:render geometry[0]/Block:compression info")
        self.block_per_mesh_temporary = self.tag.SelectField("Struct:render geometry[0]/Block:per mesh temporary")
        self.block_regions = self.tag.SelectField("Block:regions")
        self.block_meshes = self.tag.SelectField("Struct:render geometry[0]/Block:meshes")
        self.block_materials = self.tag.SelectField("Block:materials")
        
    def set_structure_meta_ref(self, meta_path):
        if self._tag_exists(meta_path):
            self.reference_structure_meta_data.Path = self._TagPath_from_string(meta_path)
            self.tag_has_changes = True
        else:
            print("Failed to add structure meta reference. Structure meta tag does not exist")
            
    def get_nodes(self):
        return [e.SelectField('name').GetStringData() for e in self.block_nodes.Elements]
    
    def read_render_geometry(self):
        render_geo = self._GameRenderGeometry()
        mesh_info = render_geo.GetMeshInfo(self.struct_render_geometry)
        print("index_bytes", mesh_info.index_bytes)
        print("index_count", mesh_info.index_count)
        print("parts", mesh_info.parts)
        print("subparts", mesh_info.subparts)
        print("triangle_count", mesh_info.triangle_count)
        print("vertex_bytes", mesh_info.vertex_bytes)
        print("vertex_count", mesh_info.vertex_count)
        print("vertex_type", mesh_info.vertex_type)
        
    def read_render_model(self):
        data_block = self.struct_render_geometry.Elements[0].SelectField('per mesh temporary')
        render_model = self._GameRenderModel()
        node_indices = render_model.GetNodeIndiciesFromMesh(data_block, 0)
        node_weights = render_model.GetNodeWeightsFromMesh(data_block, 0)
        normals = render_model.GetNormalsFromMesh(data_block, 0)
        positions = render_model.GetPositionsFromMesh(data_block, 0)
        tex_coords = render_model.GetTexCoordsFromMesh(data_block, 0)
        print("\nnode_indices")
        print("#"*50 + '\n')
        print([i for i in node_indices])
        print("\nnode_weights")
        print("#"*50 + '\n')
        print([i for i in node_weights])
        print("\nnormals")
        print("#"*50 + '\n')
        print([i for i in normals])
        print("\npositions")
        print("#"*50 + '\n')
        print([i for i in positions])
        print("\ntex_coords")
        print("#"*50 + '\n')
        print([i for i in tex_coords])
        
    def to_blend_objects(self, collection):
        self.collection = collection
        objects = []
        self.armature = self._create_armature()
        if self.armature:
            objects.append(self.armature)
            
        objects.extend(self._create_render_geometry())
        
        return objects, self.armature
    
    def _create_armature(self):
        arm = RenderArmature(self.tag.Path.ShortName)
        self.nodes: list[Node] = []
        for element in self.block_nodes.Elements:
            node = Node(element.SelectField("name").GetStringData())
            node.index = element.ElementIndex
            translation = element.SelectField("default translation").GetStringData()
            node.translation = Vector([float(n) for n in translation]) * 100
            rotation = element.SelectField("default rotation").GetStringData()
            node.rotation = Quaternion([float(rotation[3]), float(rotation[0]), float(rotation[1]), float(rotation[2])])
            inverse_forward = element.SelectField("inverse forward").GetStringData()
            node.inverse_forward = Vector([float(n) for n in inverse_forward])
            inverse_left = element.SelectField("inverse left").GetStringData()
            node.inverse_left = Vector([float(n) for n in inverse_left])
            inverse_up = element.SelectField("inverse up").GetStringData()
            node.inverse_up = Vector([float(n) for n in inverse_up])
            inverse_position = element.SelectField("inverse position").GetStringData()
            node.inverse_position = Vector([float(n) for n in inverse_position]) * 100
            inverse_scale = element.SelectField("inverse scale").GetStringData()
            node.inverse_scale = float(inverse_scale)
            
            parent_index = element.SelectField("parent node").Value
            if parent_index > -1:
                node.parent = self.block_nodes.Elements[parent_index].SelectField("name").GetStringData()
                
            self.nodes.append(node)
        
        if arm.ob:
            self.collection.objects.link(arm.ob)
            arm.ob.select_set(True)
            utils.set_active_object(arm.ob)
            bpy.ops.object.editmode_toggle()
            for node in self.nodes: arm.create_bone(node)
            for node in self.nodes: arm.parent_bone(node)
            bpy.ops.object.editmode_toggle()
            return arm.ob
        
        
    def _create_render_geometry(self):
        objects = []
        if not self.block_compression_info.Elements.Count:
            raise RuntimeError("Render Model has no compression info. Cannot import render model mesh")
        self.bounds = CompressionBounds(self.block_compression_info.Elements[0])
        render_model = self._GameRenderModel()
        
        materials = [Material(e) for e in self.block_materials.Elements]
        
        original_meshes = []
        clone_meshes = []
        for element in self.block_regions.Elements:
            region = element.SelectField("name").GetStringData()
            permutations = element.SelectField("permutations")
            for pelement in element.SelectField("permutations").Elements:
                permutation = pelement.SelectField("name").GetStringData()
                mesh_index = int(pelement.SelectField("mesh index").GetStringData())
                if mesh_index < 0: continue
                clone_index = -1
                
                if self.corinth:
                    clone = pelement.SelectField("clone name").GetStringData()
                    if clone:
                        for pe in permutations.Elements:
                            if pe.SelectField("name").GetStringData() == clone:
                                clone_index = int(pe.SelectField("mesh index").GetStringData())
                                break
                                
                mesh_count = int(pelement.SelectField("mesh count").GetStringData())
                for i in range(mesh_count):
                    mesh = Mesh(self.block_meshes.Elements[mesh_index + i], self.bounds, clone_index)
                    for part in mesh.parts:
                        part.material = materials[part.material_index]
                    
                    if clone_index == -1:
                        ob = mesh.create(render_model, self.block_per_mesh_temporary, self.nodes, self.armature, f"{region}:{permutation}", original_meshes)
                        original_meshes.append(mesh)
                        self.collection.objects.link(ob)
                        objects.append(ob)
                    else:
                        clone_meshes.append(mesh)
                        
        
        for clone in clone_meshes:
            ob = clone.create(render_model, self.block_per_mesh_temporary, self.nodes, self.armature, f"{region}:{permutation}", original_meshes)
            self.collection.objects.link(ob)
            objects.append(ob)
            
        for ob in objects:
            region, permutation = utils.dot_partition(ob.name).split(":")
            utils.set_region(ob, region)
            utils.set_permutation(ob, permutation)
        
        return objects
                


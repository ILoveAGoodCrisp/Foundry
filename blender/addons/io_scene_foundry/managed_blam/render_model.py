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

from mathutils import Quaternion, Vector

from .connected_geometry import CompressionBounds, InstancePlacement, MarkerGroup, Material, Mesh, Node, Region, RenderArmature
from .Tags import *

from .. import utils
from ..managed_blam import Tag
import bpy
    
    
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
        self.block_marker_groups = self.tag.SelectField("Block:marker groups")
        
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
        
    def to_blend_objects(self, collection, render: bool, markers: bool, model_collection: bpy.types.Collection):
        self.collection = collection
        self.model_collection = model_collection
        objects = []
        self.armature = self._create_armature()
        objects.append(self.armature)
        
        # Instances
        self.instances = []
        self.instance_mesh_index = self.tag.SelectField("LongBlockIndex:instance mesh index").Value
        if self.instance_mesh_index > -1:
            for element in self.tag.SelectField("Block:instance placements").Elements:
                self.instances.append(InstancePlacement(element, self.nodes))
        
        self.regions: list[Region] = []
        for element in self.block_regions.Elements:
            self.regions.append(Region(element))
        
        if render:
            print("Creating Render Geometry")
            objects.extend(self._create_render_geometry())
        if markers:
            print("Creating Markers")
            objects.extend(self._create_markers())
        
        return objects, self.armature
    
    def _create_armature(self):
        print("Creating Armature")
        arm = RenderArmature(f"{self.tag.Path.ShortName}_world")
        self.nodes: list[Node] = []
        for element in self.block_nodes.Elements:
            node = Node(element.SelectField("name").GetStringData(), )
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
        
        self.model_collection.objects.link(arm.ob)
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
    
        
        original_meshes: list[Mesh] = []
        clone_meshes: list[Mesh] = []
        mesh_node_map = self.tag.SelectField("Struct:render geometry[0]/Block:per mesh node map")
        for region in self.regions:
            for permutation in region.permutations:
                if permutation.mesh_index < 0: continue
                             
                for i in range(permutation.mesh_count):
                    mesh = Mesh(self.block_meshes.Elements[permutation.mesh_index + i], self.bounds, permutation, materials, mesh_node_map)
                    for part in mesh.parts:
                        part.material = materials[part.material_index]
                    
                    if mesh.permutation.clone_name:
                        clone_meshes.append(mesh)
                    else:
                        obs = mesh.create(render_model, self.block_per_mesh_temporary, self.nodes, self.armature)
                        original_meshes.append(mesh)
                        objects.extend(obs)
                        for ob in obs:
                            self.collection.objects.link(ob)
                        
        
        for clone in clone_meshes:
            true_mesh: Mesh
            for tmesh in original_meshes:
                if tmesh.permutation.name == clone.permutation.clone_name:
                    true_mesh = tmesh
                    break
                    
            if true_mesh is None: continue
            # pclone = nwo.permutation_clones.add(clone.permutation.name)
            source_material: bpy.types.Material
            destination_material: bpy.types.Material
            for true_part, clone_part in zip(true_mesh.parts, clone.parts):
                source_material = true_part.material
                destination_material = clone_part.material
                if source_material:
                    pass
                    # pclone.source_material = 
                if destination_material:
                    pass
                    # pclone.destination_material = 
            
        for ob in objects:
            region, permutation = utils.dot_partition(ob.name).split(":")
            utils.set_region(ob, region)
            utils.set_permutation(ob, permutation)
            
        if self.instances:
            instance_mesh = Mesh(self.block_meshes.Elements[self.instance_mesh_index], self.bounds, None, materials, mesh_node_map)
            ios = instance_mesh.create(render_model, self.block_per_mesh_temporary, self.nodes, self.armature, self.instances)
            for ob in ios:
                ob.data.nwo.mesh_type = "_connected_geometry_mesh_type_object_instance"
                self.collection.objects.link(ob)
                
            for instance in self.instances:
                i_permutations = []
                ob = instance.ob
                if not ob: continue
                for region in self.regions:
                    for perm in region.permutations:
                        for instance_index in perm.instance_indexes:
                            if instance_index == instance.index:
                                if not ob.nwo.marker_uses_regions:
                                    ob.nwo.marker_uses_regions = True
                                    utils.set_region(ob, region.name)
                                i_permutations.append(perm.name)
                                break
                    
                    if ob.nwo.marker_uses_regions:
                        if len(i_permutations) != len(region.permutations):
                            # If not pick if this is include or exclude type depending on whichever means less permutation entries need to be added
                            # If a tie prefer exclude
                            exclude_permutations = [p.name for p in region.permutations if p.name not in i_permutations]
                            if len(i_permutations) < len(exclude_permutations):
                                ob.nwo.marker_permutation_type = "include"
                                utils.set_marker_permutations(ob, i_permutations)
                            else:
                                utils.set_marker_permutations(ob, exclude_permutations)
                        break
                
            objects.extend(ios)
        
        return objects
    
    def _create_markers(self):
        # Model Markers
        objects = []
        markers_collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_markers")
        self.collection.children.link(markers_collection)
        marker_size_factor = max(self.bounds.x1 - self.bounds.x0, self.bounds.y1 - self.bounds.y0, self.bounds.z1 - self.bounds.z0) * 0.025
        for element in self.block_marker_groups.Elements:
            marker_group = MarkerGroup(element, self.nodes, self.regions)
            objects.extend(marker_group.to_blender(self.armature, markers_collection, marker_size_factor))
            
        return objects
            
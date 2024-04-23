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

import bmesh
from mathutils import Matrix, Vector
from io_scene_foundry.managed_blam import Tag
from io_scene_foundry.utils import nwo_utils
from io_scene_foundry.utils.nwo_materials import collision
import bpy

class CollisionSurface:
    def __init__(self, surface_element, block_materials):
        self.material = block_materials.Elements[int(surface_element.SelectField("material").GetStringData())].Fields[0].GetStringData()
        flags = surface_element.SelectField("flags")
        self.two_sided = flags.TestBit("two sided")
        self.ladder = flags.TestBit("climbable")
        self.breakable = flags.TestBit("breakable")
        self.slip_surface = flags.TestBit("slip")

class CollisionTag(Tag):
    tag_ext = 'collision_model'

    def _read_fields(self):
        self.block_materials = self.tag.SelectField("Block:materials")
        self.block_regions = self.tag.SelectField("Block:regions")
        self.block_pathfinding_spheres = self.tag.SelectField("Block:pathfinding spheres")
        self.block_nodes = self.tag.SelectField("Block:nodes")
        
    def to_blend_objects(self, collection: bpy.types.Collection):
        # Find Armature
        armature = nwo_utils.get_rig()
        armature_bones = []
        if armature:
            armature_bones = [b.name for b in armature.data.bones]
            edit_armature = nwo_utils.EditArmature(armature)
        else:
            print("No Armature in Scene to parent collision mesh to")
        objects = []
        # Collision Mesh
        for region_element in self.block_regions.Elements:
            region = region_element.Fields[0].GetStringData()
            print(f"Building meshes for region: {region}")
            for permutation_element in region_element.Fields[1].Elements:
                permutation = permutation_element.Fields[0].GetStringData()
                for bsp_element in permutation_element.SelectField("bsps").Elements:
                    name = f"{region}:{permutation}:{bsp_element.ElementIndex}"
                    mesh = self.to_mesh(bsp_element, name)
                    if mesh:
                        node = self.block_nodes.Elements[int(bsp_element.Fields[0].GetStringData())].Fields[0].GetStringData()
                        collision_object = bpy.data.objects.new(name, mesh)
                        if armature:
                            collision_object.parent = armature
                            if node in armature_bones:
                                collision_object.parent_type = 'BONE'
                                collision_object.parent_bone = node
                                collision_object.matrix_parent_inverse = collision_object.matrix_parent_inverse @ Matrix.Translation([0, edit_armature.lengths[node], 0]).inverted()
                                
                            else:
                                nwo_utils.print_warning(f"Armature does not have bone [{node}] for {collision_object.name}")
                                
                        nwo_utils.set_region(collision_object, region)
                        nwo_utils.set_permutation(collision_object, permutation)
                        
                        collection.objects.link(collision_object)
                        objects.append(collision_object)
                        
        # Pathfinding Spheres
        for sphere_element in self.block_pathfinding_spheres.Elements:
            print(f"Adding pathfinding sphere")
            node = self.block_nodes.Elements[sphere_element.Fields[0].Value].Fields[0].GetStringData()
            sphere_object = bpy.data.objects.new("pathfinding_sphere", None)
            flags = sphere_element.SelectField("flags")
            sphere_object.nwo.pathfinding_sphere_remains_when_open_ui = flags.TestBit("remains when open")
            sphere_object.nwo.marker_pathfinding_sphere_vehicle_ui = flags.TestBit("vehicle only")
            sphere_object.nwo.pathfinding_sphere_with_sectors_ui = flags.TestBit("with sectors")
            location_coords_str = sphere_element.SelectField("center").GetStringData()
            location_coords = [float(co) for co in location_coords_str]
            sphere_object.location = Vector(location_coords) * 100
            sphere_object.empty_display_size = float(sphere_element.SelectField("radius").GetStringData()) * 100
            sphere_object.empty_display_type = "SPHERE"
            sphere_object.nwo.marker_type_ui = "_connected_geometry_marker_type_pathfinding_sphere"
            if armature:
                sphere_object.parent = armature
                if node in armature_bones:
                    sphere_object.parent_type = 'BONE'
                    sphere_object.parent_bone = node
                    sphere_object.matrix_parent_inverse = sphere_object.matrix_parent_inverse @ Matrix.Translation([0, edit_armature.lengths[node], 0]).inverted()
                else:
                    nwo_utils.print_warning(f"Armature does not have bone [{node}] for {sphere_object.name}")
            
            objects.append(sphere_object)
            collection.objects.link(sphere_object)
            
        return objects
            
                    
    def to_mesh(self, bsp_element, name="collision_mesh"):
        block_edges = bsp_element.SelectField("Struct:bsp[0]/Block:edges")
        block_surfaces = bsp_element.SelectField("Struct:bsp[0]/Block:surfaces")
        block_vertices = bsp_element.SelectField("Struct:bsp[0]/Block:vertices")
        surfaces = []
        bm = bmesh.new()
        for surface_element in block_surfaces.Elements:
            edge_index = int(surface_element.SelectField("first edge").GetStringData())
            surface_edges = []
            face_vertices = []
            while edge_index not in surface_edges:
                surface_edges.append(edge_index)
                edge_element = block_edges.Elements[edge_index]
                if int(edge_element.SelectField("left surface").GetStringData()) == surface_element.ElementIndex:
                    start_vertex_index = int(edge_element.SelectField("start vertex").GetStringData())
                    vertex_coords_str = block_vertices.Elements[start_vertex_index].Fields[0].GetStringData()
                    vertex_coords = [float(v) for v in vertex_coords_str]
                    face_vertices.append(bm.verts.new(Vector(vertex_coords)* 100))
                    edge_index = int(edge_element.SelectField("forward edge").GetStringData())
                else:
                    end_vertex_index = int(edge_element.SelectField("end vertex").GetStringData())
                    vertex_coords_str = block_vertices.Elements[end_vertex_index].Fields[0].GetStringData()
                    vertex_coords = [float(v) for v in vertex_coords_str]
                    face_vertices.append(bm.verts.new(Vector(vertex_coords)* 100))
                    edge_index = int(edge_element.SelectField("reverse edge").GetStringData())
                    
            bm.faces.new(face_vertices)
            surfaces.append(CollisionSurface(surface_element, self.block_materials))
        
        bm.faces.ensure_lookup_table()
        
        if not bm.faces:
            return
        
        mesh = bpy.data.meshes.new(name)
        # Determine if we need to write bmesh layers
        split_materials = len({surface.material for surface in surfaces}) > 1
        split_sides = len({int(surface.two_sided) for surface in surfaces}) > 1
        split_ladder = len({int(surface.ladder) for surface in surfaces}) > 1
        split_breakable = len({int(surface.breakable) for surface in surfaces}) > 1
        split_slip = len({int(surface.slip_surface) for surface in surfaces}) > 1
        if split_materials or split_sides or split_ladder or split_breakable or split_slip:
            layers = {}
            face_props = mesh.nwo.face_props
            if split_materials:
                for material in {surface.material for surface in surfaces}:
                    layers[f"material:{material}"] = nwo_utils.new_face_layer(bm, mesh, material, material, "face_global_material_override")
                    mesh.nwo.face_props[-1].face_global_material_ui = material
                    
            if split_sides:
                layers["flag:two_sided"] = nwo_utils.new_face_layer(bm, mesh, material, "two_sided", "two_sided_override")
            if split_ladder:
                layers["flag:ladder"] = nwo_utils.new_face_layer(bm, mesh, material, "ladder", "ladder_override")
            if split_breakable:
                layers["flag:breakable"] = nwo_utils.new_face_layer(bm, mesh, material, "breakable", "breakable_override")
            if split_slip:
                layers["flag:slip_surface"] = nwo_utils.new_face_layer(bm, mesh, material, "slip_surface", "slip_surface_override")
                    
            for idx, face in enumerate(bm.faces):
                surface = surfaces[idx]
                for key, layer in layers.items():
                    name = key.split(":")[1]
                    if surface.material == name:
                        face[layer] = 1
                    if surface.two_sided and name == "two_sided":
                        face[layer] = 1
                    if surface.ladder and name == "ladder":
                        face[layer] = 1
                    if surface.breakable and name == "breakable":
                        face[layer] = 1
                    if surface.slip_surface and name == "slip_surface":
                        face[layer] = 1
                            
            for layer in face_props:
                layer.face_count = nwo_utils.layer_face_count(bm, bm.faces.layers.int.get(layer.layer_name))
                
        bm.to_mesh(mesh)
                
        if not split_materials:
            mesh.nwo.face_global_material_ui = surfaces[0].material
        if not split_sides:
            mesh.nwo.face_two_sided_ui = surfaces[0].two_sided
        if not split_ladder:
            mesh.nwo.ladder_ui = surfaces[0].ladder
        if not split_breakable:
            mesh.nwo.breakable_ui = surfaces[0].breakable
        if not split_slip:
            mesh.nwo.slip_surface_ui = surfaces[0].slip_surface
        
        mesh.nwo.mesh_type_ui = "_connected_geometry_mesh_type_collision"
        
        mat = bpy.data.materials.get("+collision")
        if not mat:
            mat = bpy.data.materials.new("+collision")
            mat.use_fake_user = True
            mat.diffuse_color = collision.color
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes[0]
            bsdf.inputs[0].default_value = collision.color
            bsdf.inputs[4].default_value = collision.color[3]
            mat.blend_method = 'BLEND'
            mat.shadow_method = 'NONE'
            
        mesh.materials.append(mat)
        
        return mesh
                
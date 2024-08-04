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

from uuid import uuid4
from mathutils import Euler, Matrix, Vector

from .connected_geometry import BSP, CollisionMaterial, Node

# from .connected_geometry import CollisionSurface
from ..managed_blam import Tag
from .. import utils
from ..tools.materials import collision
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
        
    def to_blend_objects(self, collection: bpy.types.Collection, edit_armature=None, markers=True):
        # Find Armature
        armature = None
        if edit_armature:
            armature = edit_armature.ob
        if armature is None:
            armature = utils.get_rig()
            edit_armature = utils.EditArmature(armature)
        objects = []
        # Collision Mesh
        nodes = [e.Fields[0].Data for e in self.block_nodes.Elements]
        materials = [CollisionMaterial(e) for e in self.block_materials.Elements]
        for region_element in self.block_regions.Elements:
            region = region_element.Fields[0].GetStringData()
            print(f"Building collision meshes for region: {region}")
            for permutation_element in region_element.Fields[1].Elements:
                permutation = permutation_element.Fields[0].GetStringData()
                for bsp_element in permutation_element.SelectField("bsps").Elements:
                    name = f"{region}:{permutation}:{bsp_element.ElementIndex}"
                    bsp = BSP(bsp_element, name, materials, nodes)
                    ob = bsp.to_object()
                    ob.parent = armature
                    world = edit_armature.matrices[bsp.bone]
                    ob.parent_type = 'BONE'
                    ob.parent_bone = bsp.bone
                    ob.matrix_world = world
                    ob.matrix_local = Matrix.Translation([0, edit_armature.lengths[bsp.bone], 0]).inverted()
                    utils.set_region(ob, region)
                    utils.set_permutation(ob, permutation)
                    collection.objects.link(ob)
                    objects.append(ob)
                        
        # Pathfinding Spheres
        # if markers:
        #     for sphere_element in self.block_pathfinding_spheres.Elements:
        #         print(f"Adding pathfinding sphere")
        #         node = self.block_nodes.Elements[sphere_element.Fields[0].Value].Fields[0].GetStringData()
        #         sphere_object = bpy.data.objects.new("pathfinding_sphere", None)
        #         flags = sphere_element.SelectField("flags")
        #         sphere_object.nwo.pathfinding_sphere_remains_when_open = flags.TestBit("remains when open")
        #         sphere_object.nwo.marker_pathfinding_sphere_vehicle = flags.TestBit("vehicle only")
        #         sphere_object.nwo.pathfinding_sphere_with_sectors = flags.TestBit("with sectors")
        #         location_coords_str = sphere_element.SelectField("center").GetStringData()
        #         location_coords = [float(co) for co in location_coords_str]
        #         # sphere_object.location = Vector(location_coords) * 100
        #         sphere_object.empty_display_size = float(sphere_element.SelectField("radius").GetStringData()) * 100
        #         sphere_object.empty_display_type = "SPHERE"
        #         sphere_object.nwo.marker_type = "_connected_geometry_marker_type_pathfinding_sphere"
        #         if armature:
        #             sphere_object.parent = armature
        #             if node in armature_bones:
        #                 world = edit_armature.matrices[node]
        #                 sphere_object.parent_type = 'BONE'
        #                 sphere_object.parent_bone = node
        #                 sphere_object.matrix_world = world
        #                 sphere_object.matrix_local = Matrix.Translation([0, edit_armature.lengths[node], 0]).inverted() @ Matrix.LocRotScale(Vector(location_coords) * 100, Euler((0,0,0)), Vector.Fill(3, 1))
        #             else:
        #                 utils.print_warning(f"Armature does not have bone [{node}] for {sphere_object.name}")
                
        #         objects.append(sphere_object)
        #         collection.objects.link(sphere_object)
            
        return objects
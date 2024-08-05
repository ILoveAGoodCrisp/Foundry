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

from .connected_geometry import BSP, CollisionMaterial, PathfindingSphere

from ..managed_blam import Tag
from .. import utils
from ..tools.materials import collision
import bpy


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
        print(f"Building collision meshes")
        for region_element in self.block_regions.Elements:
            region = region_element.Fields[0].GetStringData()
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
        if markers:
            print(f"Adding pathfinding spheres")
            for sphere_element in self.block_pathfinding_spheres.Elements:
                sphere = PathfindingSphere(sphere_element, nodes)
                ob = sphere.to_object()
                ob.parent = armature
                world = edit_armature.matrices[sphere.bone]
                ob.parent_type = 'BONE'
                ob.parent_bone = sphere.bone
                ob.matrix_world = world
                ob.matrix_local = Matrix.Translation([0, edit_armature.lengths[sphere.bone], 0]).inverted() @ Matrix.LocRotScale(Vector(sphere.center) * 100, Euler((0,0,0)), Vector.Fill(3, 1))
                collection.objects.link(ob)
                objects.append(ob)
            
        return objects


import bpy

from .connected_geometry import CollisionMaterial, Hinge, LimitedHinge, Ragdoll, RigidBody
from .. import utils
from . import Tag

class PhysicsTag(Tag):
    tag_ext = 'physics_model'

    def _read_fields(self):
        self.block_rigid_bodies = self.tag.SelectField("Block:rigid bodies")
        self.block_hinge_constraints = self.tag.SelectField("Block:hinge constraints")
        self.block_ragdoll_constraints = self.tag.SelectField("Block:ragdoll constraints")
        self.block_node_edges = self.tag.SelectField("Block:node edges")
        self.block_materials = self.tag.SelectField("Block:materials")
        self.block_spheres = self.tag.SelectField("Block:spheres")
        self.block_pills = self.tag.SelectField("Block:pills")
        self.block_boxes = self.tag.SelectField("Block:boxes")
        self.block_polyhedra = self.tag.SelectField("Block:polyhedra")
        self.block_polyhedron_four_vectors = self.tag.SelectField("Block:polyhedron four vectors")
        self.block_polyhedron_plane_equations = self.tag.SelectField("Block:polyhedron plane equations")
        self.block_limited_hinge_constraints = self.tag.SelectField("Block:limited hinge constraints")
        self.block_nodes = self.tag.SelectField("Block:nodes")
        self.block_regions = self.tag.SelectField("Block:regions")
        self.block_mopps = self.tag.SelectField("Block:mopps")
        self.block_list_shapes = self.tag.SelectField("Block:list shapes")
        self.block_lists = self.tag.SelectField("Block:lists")
        
    def to_blend_objects(self, collection: bpy.types.Collection, armature=None, variant=""):
        if armature is None:
            armature = utils.get_rig()
        objects = []
        nodes = [e.Fields[0].Data for e in self.block_nodes.Elements]
        materials = [CollisionMaterial(e) for e in self.block_materials.Elements]
        # Meshes
        four_vectors_map = []
        size = 0
        list_shapes_offset = 0
        # cereal = self.tag.SelectField("Block:RigidBody Serialized Shapes[0]/Block:Mopp Serialized Havok Data")
        # if cereal.Elements.Count > 0:
        #     el = cereal.Elements[0]
        #     data = el.Fields[3].GetData()
        #     b = bytes([b for b in data])
        #     print(b.hex())
        if self.block_polyhedra.Elements.Count > 0:
            for element in self.block_polyhedra.Elements:
                size = element.SelectField("LongInteger:four vectors size").Data
                if element.ElementIndex == 0:
                    four_vectors_map.append(size)
                else:
                    four_vectors_map.append(size + four_vectors_map[-1])
        
        for region_element in self.block_regions.Elements:
            region = region_element.Fields[0].GetStringData()
            for permutation_element in region_element.Fields[1].Elements:
                permutation = permutation_element.Fields[0].GetStringData()
                for rigid_element in permutation_element.SelectField("rigid bodies").Elements:
                    body_index = rigid_element.Fields[0].Value
                    if body_index > -1 and self.block_rigid_bodies.Elements.Count > body_index:
                        body = RigidBody(self.block_rigid_bodies.Elements[body_index], region, permutation, materials, four_vectors_map, self, list_shapes_offset, self.corinth)
                        list_shapes_offset = body.list_shapes_offset
                        if body.valid:
                            body.to_objects()
                            for shape in body.shapes:
                                ob = shape.ob
                                bone = nodes[body.node_index]
                                ob.parent = armature
                                ob.parent_type = 'BONE'
                                ob.parent_bone = bone
                                ob.matrix_world = armature.pose.bones[bone].matrix @ shape.matrix
                                utils.set_region(ob, region)
                                utils.set_permutation(ob, permutation)
                                collection.objects.link(ob)
                                objects.append(ob)
                                        
        
        # Constraints
        for element in self.block_hinge_constraints.Elements:
            hinge = Hinge(element, nodes)
            ob = hinge.to_object(armature)
            self._parent_constraint(hinge, ob, armature)
            collection.objects.link(ob)
            objects.append(ob)
            
        for element in self.block_limited_hinge_constraints.Elements:
            limited_hinge = LimitedHinge(element, nodes)
            ob = limited_hinge.to_object(armature)
            self._parent_constraint(limited_hinge, ob, armature)
            collection.objects.link(ob)
            objects.append(ob)
            
        for element in self.block_ragdoll_constraints.Elements:
            ragdoll = Ragdoll(element, nodes)
            ob = ragdoll.to_object(armature)
            self._parent_constraint(ragdoll, ob, armature)
            collection.objects.link(ob)
            objects.append(ob)
            
        return objects
            
    def _parent_constraint(self, constraint: Hinge, ob: bpy.types.Object, armature):
        bone = constraint.bone_parent
        ob.parent = armature
        ob.parent_type = 'BONE'
        ob.parent_bone = bone
        ob.matrix_world = armature.pose.bones[bone].matrix @ constraint.matrix_a # @ Matrix.LocRotScale(Vector(constraint.center) * 100, Euler((0,0,0)), Vector.Fill(3, 1))
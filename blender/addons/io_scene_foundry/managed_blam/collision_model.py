from mathutils import Euler, Matrix, Vector

from .connected_geometry import CollisionMaterial, ModelCollision, PathfindingSphere

from ..managed_blam import Tag
from .. import utils
import bpy


class CollisionTag(Tag):
    tag_ext = 'collision_model'

    def _read_fields(self):
        self.block_materials = self.tag.SelectField("Block:materials")
        self.block_regions = self.tag.SelectField("Block:regions")
        self.block_pathfinding_spheres = self.tag.SelectField("Block:pathfinding spheres")
        self.block_nodes = self.tag.SelectField("Block:nodes")
        
    def to_blend_objects(self, collection: bpy.types.Collection, armature=None, variant=""):
        # Find Armature
        if armature is None:
            armature = utils.get_rig()
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
                    bsp = ModelCollision(bsp_element, name, materials, nodes)
                    ob = bsp.to_object()
                    ob.parent = armature
                    ob.parent_type = 'BONE'
                    ob.parent_bone = bsp.bone
                    ob.matrix_world = armature.pose.bones[bsp.bone].matrix
                    utils.set_region(ob, region)
                    utils.set_permutation(ob, permutation)
                    collection.objects.link(ob)
                    objects.append(ob)
                        
        # Pathfinding Spheres
        print(f"Adding pathfinding spheres")
        for sphere_element in self.block_pathfinding_spheres.Elements:
            sphere = PathfindingSphere(sphere_element, nodes)
            ob = sphere.to_object()
            ob.parent = armature
            ob.parent_type = 'BONE'
            ob.parent_bone = sphere.bone
            ob.matrix_world = armature.pose.bones[sphere.bone].matrix @ Matrix.LocRotScale(Vector(sphere.center) * 100, Euler((0,0,0)), Vector.Fill(3, 1))
            collection.objects.link(ob)
            objects.append(ob)
            
        return objects
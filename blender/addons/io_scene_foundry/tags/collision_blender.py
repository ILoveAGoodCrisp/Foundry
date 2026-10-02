"""Collision-model import using native tag records and existing Blender conversion."""
from mathutils import Euler, Matrix, Vector
from .connected_geometry import ModelCollision, PathfindingSphere
from .blender import BlenderTag
from .collision import CollisionDocument
from .model_permutations import select_model_records
from .. import utils
from .. import import_transform
import bpy


class CollisionTag(BlenderTag, CollisionDocument):
    tag_ext = 'collision_model'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)

    def to_blend_objects(self, collection: bpy.types.Collection, armature=None, variant=''):
        meshes, spheres = self.read_collision()
        meshes = select_model_records(meshes, variant)
        if not meshes and not spheres:
            return []
        for record in (*meshes, *spheres):
            if armature is not None and record.bone not in armature.pose.bones:
                raise ValueError(f'Collision bone {record.bone!r} is missing from the armature')
        objects = []
        for record in meshes:
            bsp = ModelCollision.from_native(record)
            ob = bsp.to_object()
            if armature is not None:
                ob.parent = armature
                ob.parent_type = 'BONE'
                ob.parent_bone = bsp.bone
                ob.matrix_world = armature.matrix_world @ armature.pose.bones[bsp.bone].matrix
            else:
                ob.matrix_world = import_transform.rotation_matrix()
            utils.set_region(ob, record.region, utils.SetType.MODEL)
            utils.set_permutation(ob, record.permutation, utils.SetType.MODEL)
            collection.objects.link(ob)
            objects.append(ob)
        for record in spheres:
            sphere = PathfindingSphere.from_native(record)
            ob = sphere.to_object()
            if armature is not None:
                ob.parent = armature
                ob.parent_type = 'BONE'
                ob.parent_bone = sphere.bone
            local_matrix = import_transform.object_matrix(
                Matrix.LocRotScale(Vector(sphere.center) * 100, Euler((0, 0, 0)), Vector.Fill(3, 1)),
                rotate=armature is None)
            ob.matrix_world = import_transform.keep_marker_axis(
                armature.matrix_world @ armature.pose.bones[sphere.bone].matrix @ local_matrix
                if armature is not None else local_matrix)
            collection.objects.link(ob)
            objects.append(ob)
        return objects

"""Native physics constraints with a temporary legacy rigid-body shape boundary."""
from ..tags.blender import BlenderTag
from ..tags.physics import PhysicsDocument, PhysicsShapesUnsupported
from .connected_geometry import Constraint, Sphere, Box, Pill, Polyhedron, RigidBody, HavokCollision
from mathutils import Matrix
from . import import_transform
from .. import utils


class PhysicsTag(BlenderTag, PhysicsDocument):
    tag_ext = 'physics_model'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)

    def to_blend_objects(self, collection, armature=None, variant=''):
        if armature is None:
            armature = utils.get_rig()
        constraints = [Constraint.from_native(record) for record in self.constraints()]
        for constraint in constraints:
            if armature is None or any(bone not in armature.pose.bones for bone in
                                      (constraint.bone_parent, constraint.bone_child)):
                raise ValueError(f'Physics constraint {constraint.name!r} requires both armature bones')
        objects = []
        try:
            records = self.primitive_bodies(include_serialized=True)
            shapes = []
            for record in records:
                if record.kind == 'serialized':
                    shape = HavokCollision.from_serialized_shape(record.data, record.name, record.materials)
                    if shape is None:
                        raise PhysicsShapesUnsupported('Unsupported serialized Havok geometry')
                    shape.matrix = Matrix.Identity(4)
                    for name in ('material', 'material_index', 'friction', 'restitution', 'volume'):
                        setattr(shape, name, getattr(record, name))
                else:
                    shape = {'sphere': Sphere, 'box': Box, 'pill': Pill, 'polyhedron': Polyhedron}[record.kind].from_native(record)
                shapes.append(shape)
        except PhysicsShapesUnsupported:
            records = None
        if records is None:
            from .physics_legacy import LegacyPhysicsTag
            with LegacyPhysicsTag(path=self.tag_path, tag_must_exist=True) as legacy:
                objects.extend(legacy.to_blend_objects(collection, armature, variant))
        else:
            for record in records:
                if armature is None or record.bone not in armature.pose.bones:
                    raise ValueError(f'Physics primitive requires armature bone {record.bone!r}')
            for record, shape in zip(records, shapes):
                body = RigidBody.__new__(RigidBody)
                body.shapes = [shape]
                body.is_havok_rigid_body = record.havok is not None
                body.havok_info = record.havok
                body.to_objects()
                ob = shape.ob
                ob.parent, ob.parent_type, ob.parent_bone = armature, 'BONE', record.bone
                ob.matrix_world = armature.pose.bones[record.bone].matrix @ import_transform.object_matrix(shape.matrix, rotate=False)
                utils.set_region(ob, record.region, utils.SetType.MODEL)
                utils.set_permutation(ob, record.permutation, utils.SetType.MODEL)
                collection.objects.link(ob)
                objects.append(ob)
        for constraint in constraints:
            ob = constraint.to_object(armature)
            self._parent_constraint(constraint, ob, armature)
            collection.objects.link(ob)
            objects.append(ob)
        return objects

    def _parent_constraint(self, constraint, ob, armature):
        bone = constraint.bone_parent
        ob.parent = armature
        ob.parent_type = 'BONE'
        ob.parent_bone = bone
        ob.empty_display_size *= import_transform.scale_factor()
        local_matrix = import_transform.object_matrix(constraint.matrix_a, rotate=False)
        ob.matrix_world = import_transform.keep_marker_axis(armature.pose.bones[bone].matrix @ local_matrix)

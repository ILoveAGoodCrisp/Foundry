"""Native physics import; unsupported shapes fail before object allocation."""
from .blender import BlenderTag
from .physics import PhysicsDocument, PhysicsShapesUnsupported
from .render_model import RenderModelMetadataTag
from .model_permutations import select_model_records
from .connected_geometry import Constraint, Sphere, Box, Pill, Polyhedron, RigidBody, HavokCollision
from mathutils import Matrix
from .. import import_transform
from .. import utils


class PhysicsTag(BlenderTag, PhysicsDocument):
    tag_ext = 'physics_model'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)

    def to_blend_objects(self, collection, armature=None, variant=''):
        constraints = [Constraint.from_native(record) for record in self.constraints()]
        for constraint in constraints:
            if armature is not None and any(bone not in armature.pose.bones for bone in
                                      (constraint.bone_parent, constraint.bone_child)):
                raise ValueError(f'Physics constraint {constraint.name!r} requires both armature bones')
        objects = []
        try:
            records = self.primitive_bodies(include_serialized=True)
            records = select_model_records(records, variant)
            if self.game == 'halo1' and armature is not None:
                self._resolve_halo1_bones(records, armature)
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
        except PhysicsShapesUnsupported as exc:
            raise PhysicsShapesUnsupported(f'Cannot import native physics in {self.system_path}: {exc}') from exc
        else:
            for record in records:
                if armature is not None and record.bone is not None and record.bone not in armature.pose.bones:
                    raise ValueError(f'Physics primitive requires armature bone {record.bone!r}')
            for record, shape in zip(records, shapes):
                body = RigidBody.__new__(RigidBody)
                body.shapes = [shape]
                body.is_havok_rigid_body = record.havok is not None
                body.havok_info = record.havok
                body.to_objects()
                ob = shape.ob
                local_matrix = import_transform.object_matrix(
                    shape.matrix, rotate=armature is None or getattr(record, 'model_space', False))
                if armature is None or record.bone is None:
                    ob.parent = armature
                    ob.matrix_world = armature.matrix_world @ local_matrix if armature is not None else local_matrix
                else:
                    ob.parent, ob.parent_type, ob.parent_bone = armature, 'BONE', record.bone
                    ob.matrix_world = armature.matrix_world @ (local_matrix if getattr(record, 'model_space', False)
                                       else armature.pose.bones[record.bone].matrix @ local_matrix)
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

    def _resolve_halo1_bones(self, records, armature):
        # Mass-point indices refer to the model tag's node block. Blender's
        # bone collection is reordered by hierarchy and may include controls.
        assigned = [record for record in records if record.node_index != -1]
        if not assigned:
            return
        source = armature.nwo.node_order_source.strip()
        if not source:
            raise ValueError('Halo 1 physics requires the armature model tag for node order')
        with RenderModelMetadataTag(path=self.tags_root / source) as model:
            model.read_only = True
            nodes = model.get_nodes()
        for record in assigned:
            if not 0 <= record.node_index < len(nodes):
                raise ValueError(f'Halo 1 physics mass point {record.name!r} model node index is out of range')
            record.bone = nodes[record.node_index]

    def _parent_constraint(self, constraint, ob, armature):
        bone = constraint.bone_parent
        ob.empty_display_size *= import_transform.scale_factor()
        local_matrix = import_transform.object_matrix(constraint.matrix_a, rotate=armature is None)
        if armature is None:
            ob.matrix_world = import_transform.keep_marker_axis(local_matrix)
            return
        ob.parent = armature
        ob.parent_type = 'BONE'
        ob.parent_bone = bone
        ob.matrix_world = import_transform.keep_marker_axis(armature.matrix_world @ armature.pose.bones[bone].matrix @ local_matrix)

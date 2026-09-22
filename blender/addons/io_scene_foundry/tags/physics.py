"""Native physics constraints and standalone rigid-body shape metadata."""
from dataclasses import dataclass
from types import SimpleNamespace
from math import isfinite
from .backend import TagDocument


CONSTRAINT_FIELDS = {
    'hinge constraints': {},
    'limited hinge constraints': {'limit_min_angle': 'limit min angle', 'limit_max_angle': 'limit max angle'},
    'ragdoll constraints': {'min_twist': 'min twist', 'max_twist': 'max twist', 'cone': 'max cone',
                           'min_plane': 'min plane', 'max_plane': 'max plane'},
    'stiff spring constraints': {'spring_length': 'spring_length'},
    'ball and socket constraints': {},
    'prismatic constraints': {'min_limit': 'min_limit', 'max_limit': 'max_limit', 'max_friction_force': 'max_friction_force'},
}


@dataclass(frozen=True)
class PhysicsMaterial:
    name: str
    global_material: str
    phantom: bool


class PhysicsShapesUnsupported(NotImplementedError):
    """A rigid-body shape still requires the legacy converter."""


class PhysicsDocument(TagDocument):
    tag_ext = 'physics_model'

    def materials(self) -> list[PhysicsMaterial]:
        result: list[PhysicsMaterial] = []
        for element in self.block(self.tag.root(), 'materials'):
            phantom = element.field('phantom type')
            result.append(PhysicsMaterial(
                name=str(self.value(element, 'name')),
                global_material=str(self.value(element, 'global material name')),
                phantom=phantom is not None and int(phantom.value) > -1,
            ))
        return result

    def primitive_bodies(self, *, include_serialized=False):
        root = self.tag.root()
        bodies = self.block(root, 'rigid bodies')
        nodes = [self.value(e, 'name') for e in self.block(root, 'nodes')]
        materials = [SimpleNamespace(index=i, name=self.value(e, 'name')) for i, e in enumerate(self.block(root, 'materials'))]
        result = []
        for region in self.block(root, 'regions'):
            for permutation in self.block(region, 'permutations'):
                for entry in self.block(permutation, 'rigid bodies'):
                    index = self.value(entry, 'rigid body')
                    if not 0 <= index < len(bodies):
                        continue  # Preserve unassigned region entries.
                    body = bodies[index]
                    serialized_records = []
                    if self.game in {'halo4', 'halo2a'}:
                        serialized = body.field('serialized shapes')
                        if serialized is not None and serialized.value >= 0:
                            if not include_serialized:
                                raise PhysicsShapesUnsupported('Serialized Havok shapes require legacy conversion')
                            serialized_records = self.serialized_shapes(serialized.value)
                            if not serialized_records:
                                raise PhysicsShapesUnsupported('Empty serialized physics shape group')
                    havok = self._havok_properties(body)
                    if serialized_records:
                        node_index = self.value(body, 'node')
                        if node_index < -1 or node_index >= len(nodes):
                            raise ValueError('Serialized physics node index is out of range')
                        bone: str | None = nodes[node_index] if node_index >= 0 else None
                        for record in serialized_records:
                            record.kind, record.index = 'serialized', index
                            record.node_index, record.bone = node_index, bone
                            record.region, record.permutation = self.value(region, 'name'), self.value(permutation, 'name')
                            record.havok = havok
                            result.append(record)
                    reference = self.required_field(body, 'shape reference').as_struct()
                    if serialized_records and self.value(reference, 'shape') == -1:
                        continue
                    for reference in self._primitive_references(reference):
                        kind = self.value(reference, 'shape type')
                        if kind in ('sphere', 0):
                            kind = 'sphere'
                        elif kind in ('box', 2):
                            kind = 'box'
                        elif kind in ('pill', 1):
                            kind = 'pill'
                        elif kind in ('polyhedron', 4):
                            kind = 'polyhedron'
                        else:
                            raise PhysicsShapesUnsupported('Unsupported native physics primitive')
                        shapes = self.block(root, {'sphere': 'spheres', 'box': 'boxes', 'pill': 'pills', 'polyhedron': 'polyhedra'}[kind])
                        shape_index = self.value(reference, 'shape')
                        node_index = self.value(body, 'node')
                        if not 0 <= shape_index < len(shapes) or node_index < -1 or node_index >= len(nodes):
                            raise ValueError('Physics primitive shape or node index is out of range')
                        sphere = shapes[shape_index]
                        base = self.required_field(sphere, 'base').as_struct()
                        friction, restitution = self.value(base, 'friction'), self.value(base, 'restitution')
                        if not all(isfinite(v) for v in (friction, restitution)):
                            raise ValueError('Non-finite physics friction or restitution')
                        geometry = {}
                        if kind == 'polyhedron':
                            convex = self.required_field(sphere, 'polyhedron shape').as_struct()
                            sizes = [self.value(e, 'four vectors size') for e in shapes]
                            if any(size < 0 for size in sizes):
                                raise ValueError('Negative physics polyhedron vector count')
                            offset, count = sum(sizes[:shape_index]), sizes[shape_index]
                            vectors = self.block(root, 'polyhedron four vectors')
                            if offset + count > len(vectors):
                                raise ValueError('Physics polyhedron vector range is out of bounds')
                            points = []
                            for i in range(offset, offset + count):
                                axes = [tuple(self.value(vectors[i], f'four vectors {axis}').to_array())
                                        + (self.value(vectors[i], f'havok w four vectors {axis}'),) for axis in ('x', 'y', 'z')]
                                points.extend(zip(*axes))
                            if len(set(points)) < 4 or any(not isfinite(v) for point in points for v in point):
                                raise ValueError('Invalid physics polyhedron vertices')
                            translation = (0., 0., 0.)
                            geometry = dict(vertices=points, offset=offset)
                        elif kind == 'pill':
                            convex = self.required_field(sphere, 'capsule shape').as_struct()
                            bottom = tuple(self.value(sphere, 'bottom').to_array())
                            top = tuple(self.value(sphere, 'top').to_array())
                            if not all(isfinite(v) for v in (*bottom, *top)):
                                raise ValueError('Invalid physics capsule endpoints')
                            if bottom == top:
                                raise PhysicsShapesUnsupported('Zero-length capsules require legacy conversion')
                            translation = bottom
                            geometry = dict(bottom=bottom, top=top)
                        else:
                            translated = self.required_field(sphere, 'translate shape' if kind == 'sphere' else 'convex transform shape').as_struct()
                            convex = (self.required_field(translated, 'convex').as_struct() if kind == 'sphere'
                                      else self.required_field(sphere, 'box shape').as_struct())
                            translation = tuple(self.value(translated, 'translation').to_array())
                        radius = self.value(convex, 'radius')
                        if radius < 0 or not all(isfinite(v) for v in (radius, *translation)):
                            raise ValueError('Invalid physics primitive dimensions')
                        material = self.value(base, 'material')
                        if kind == 'box':
                            extents = tuple(self.value(sphere, 'half extents').to_array())
                            axes = tuple(tuple(self.value(translated, f'rotation {axis}').to_array()) for axis in ('i', 'j', 'k'))
                            if any(v < 0 or not isfinite(v) for v in extents) or any(not isfinite(v) for row in axes for v in row):
                                raise ValueError('Invalid physics box dimensions or rotation')
                            geometry = dict(half_extents=extents, axes=axes)
                        result.append(SimpleNamespace(index=index, node_index=node_index,
                            bone=nodes[node_index] if node_index >= 0 else None,
                            region=self.value(region, 'name'), permutation=self.value(permutation, 'name'),
                            name=self.value(base, 'name'), material=materials[material] if 0 <= material < len(materials) else None,
                            kind=kind, material_index=material, radius=radius, translation=translation, havok=havok,
                            friction=friction, restitution=restitution, **geometry))
        return result

    def _havok_properties(self, body):
        if self.game not in {'halo4', 'halo2a'}:
            return None
        flags = self.required_field(body, 'flags')
        try:
            is_havok = flags.get_flag('Havok rigid body')
        except KeyError:
            # Older self-describing layouts predate this flag and serialized shapes.
            if body.field('serialized shapes') is not None:
                raise
            return None
        if not is_havok:
            return None
        mass = self.value(body, 'mass')
        center = tuple(self.value(body, 'center off mass offset').to_array())
        inertia = tuple(self.value(body, f'inertia tensor scale {axis}') for axis in ('x', 'y', 'z'))
        scale = self.value(body, 'inertia tensor scale')
        linear, angular = self.value(body, 'linear damping'), self.value(body, 'angular damping')
        if not all(isfinite(v) for v in (mass, *center, *inertia, scale, linear, angular)):
            raise ValueError('Non-finite Havok rigid-body property')
        return SimpleNamespace(change_mass=flags.get_flag('explicit mass'), mass=mass,
            change_center_of_mass=flags.get_flag('absolute center of mass'), center_of_mass=center,
            inertia_tensor=inertia, change_inertia_tensor=any(v != 1.0 for v in inertia),
            inertia_tensor_scale=scale, scale_inertia_tensor=scale != 1.0,
            linear_damping=linear, change_linear_damping=linear != 0.0,
            angular_damping=angular, change_angular_damping=angular != 0.0)

    def serialized_shapes(self, index):
        """Detach serialized geometry and its material metadata for the Havok decoder."""
        groups = self.block(self.tag.root(), 'RigidBody Serialized Shapes')
        if not 0 <= index < len(groups):
            raise ValueError('Serialized physics shape index is out of range')
        materials = [SimpleNamespace(index=i, name=self.value(e, 'name'))
                     for i, e in enumerate(self.block(self.tag.root(), 'materials'))]
        result = []
        for element in self.block(groups[index], 'Mopp Serialized Havok Data'):
            base = self.required_field(element, 'base').as_struct()
            material_index = self.value(base, 'material')
            friction, restitution = self.value(base, 'friction'), self.value(base, 'restitution')
            volume_field = base.field('volume')
            volume = volume_field.value if volume_field is not None else 0.0
            if not all(isfinite(v) for v in (friction, restitution, volume)):
                raise ValueError('Non-finite serialized physics shape property')
            result.append(SimpleNamespace(name=self.value(base, 'name'),
                data=bytes(self.value(element, 'Serialized Havok Data')),
                material_index=material_index,
                material=materials[material_index] if 0 <= material_index < len(materials) else None,
                materials=materials, friction=friction, restitution=restitution, volume=volume))
        return result

    def _primitive_references(self, reference):
        """Flatten compound geometry without recursion or circular references."""
        pending = [('reference', reference)]
        active, result = set(), []
        visits = 0
        while pending:
            action, item = pending.pop()
            if action == 'leave':
                active.remove(item)
                continue
            visits += 1
            if visits > 100000:
                raise ValueError('Physics compound shape expansion exceeds 100000 references')
            if action == 'list':
                kind, index = 'list', item
            else:
                kind, index = self.value(item, 'shape type'), self.value(item, 'shape')
                if kind in ('list', '_list', 14):
                    kind = 'list'
                elif kind in ('mopp', 15):
                    kind = 'mopp'
                else:
                    result.append(item)
                    continue
            key = (kind, index)
            if key in active:
                raise ValueError('Circular physics compound shape reference')
            active.add(key)
            pending.append(('leave', key))
            if kind == 'list':
                pending.extend(('reference', child) for child in reversed(self._list_references(index)))
            else:
                mopps = self.block(self.tag.root(), 'mopps')
                if not 0 <= index < len(mopps):
                    raise ValueError('Physics MOPP index is out of range')
                mopp = mopps[index]
                child = mopp.field('childShapePointer')
                if child is not None:
                    pending.append(('reference', child.as_struct()))
                else:
                    pending.append(('list', self.value(mopp, 'list')))
        return result

    def _list_references(self, index):
        lists = self.block(self.tag.root(), 'lists')
        if not 0 <= index < len(lists):
            raise ValueError('Physics list index is out of range')
        sizes = [self.value(element, 'child shapes size') for element in lists]
        if any(size < 0 for size in sizes):
            raise ValueError('Negative physics list child count')
        offset, count = sum(sizes[:index]), sizes[index]
        children = self.block(self.tag.root(), 'list shapes')
        if offset + count > len(children):
            raise ValueError('Physics list child range is out of bounds')
        if not count:
            raise PhysicsShapesUnsupported('Empty physics lists require legacy conversion')
        return [self.required_field(children[i], 'shape reference').as_struct()
                for i in range(offset, offset + count)]

    def constraints(self):
        nodes = [self.value(e, 'name') for e in self.block(self.tag.root(), 'nodes')]
        result = []
        for kind, fields in CONSTRAINT_FIELDS.items():
            for index, element in enumerate(self.block(self.tag.root(), kind)):
                body = self.required_field(element, 'constraint bodies').as_struct()
                a, b = self.value(body, 'node a'), self.value(body, 'node b')
                if not (0 <= a < len(nodes) and 0 <= b < len(nodes)):
                    raise ValueError(f'{kind} {index}: constraint node index is out of range')
                axes = {name: tuple(self.value(body, name).to_array())
                        for side in ('a', 'b') for name in (f'{side} forward', f'{side} left', f'{side} up', f'{side} position')}
                values = {attribute: self.value(element, name) for attribute, name in fields.items()}
                result.append(SimpleNamespace(kind=kind, index=index, name=self.value(body, 'name'),
                                              node_a_index=a, node_b_index=b, bone_parent=nodes[a],
                                              bone_child=nodes[b], axes=axes, values=values))
        return result

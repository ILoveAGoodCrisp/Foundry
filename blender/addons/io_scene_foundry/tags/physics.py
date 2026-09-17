"""Native physics-constraint metadata; rigid-body shape decoding is separate."""
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


class PhysicsShapesUnsupported(NotImplementedError):
    """A rigid-body shape still requires the legacy converter."""


class PhysicsDocument(TagDocument):
    tag_ext = 'physics_model'

    def sphere_bodies(self):
        root = self.tag.root()
        bodies, spheres = self.block(root, 'rigid bodies'), self.block(root, 'spheres')
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
                    if self.game in {'halo4', 'halo2a'}:
                        if body.field('serialized shapes') is None:
                            raise PhysicsShapesUnsupported('Older rigid-body layouts require legacy conversion')
                        if self.value(body, 'serialized shapes') >= 0 or self.required_field(body, 'flags').get_flag('Havok rigid body'):
                            raise PhysicsShapesUnsupported('Serialized or Havok rigid-body properties require legacy conversion')
                    reference = self.required_field(body, 'shape reference').as_struct()
                    if self.value(reference, 'shape type') not in ('sphere', 0):
                        raise PhysicsShapesUnsupported('Only standalone spheres currently use native rigid-body conversion')
                    shape_index = self.value(reference, 'shape')
                    node_index = self.value(body, 'node')
                    if not 0 <= shape_index < len(spheres) or not 0 <= node_index < len(nodes):
                        raise ValueError('Physics sphere shape or node index is out of range')
                    sphere = spheres[shape_index]
                    base = self.required_field(sphere, 'base').as_struct()
                    translated = self.required_field(sphere, 'translate shape').as_struct()
                    convex = self.required_field(translated, 'convex').as_struct()
                    radius = self.value(convex, 'radius')
                    translation = tuple(self.value(translated, 'translation').to_array())
                    if radius < 0 or not all(isfinite(v) for v in (radius, *translation)):
                        raise ValueError('Invalid physics sphere dimensions')
                    material = self.value(base, 'material')
                    result.append(SimpleNamespace(index=index, node_index=node_index, bone=nodes[node_index],
                        region=self.value(region, 'name'), permutation=self.value(permutation, 'name'),
                        name=self.value(base, 'name'), material=materials[material] if 0 <= material < len(materials) else None,
                        material_index=material, radius=radius, translation=translation,
                        friction=self.value(base, 'friction'), restitution=self.value(base, 'restitution')))
        return result

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

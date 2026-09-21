"""Detached collision-model geometry, with bounded surface-loop traversal."""
from types import SimpleNamespace as Record
from dataclasses import dataclass
from math import isfinite
from .backend import TagDocument


@dataclass(frozen=True, slots=True)
class CollisionMaterialRecord:
    index: int
    name: str


class CollisionDocument(TagDocument):
    tag_ext = 'collision_model'

    def read_collision(self):
        root = self.tag.root()
        nodes = [self.value(e, 'name') for e in self.block(root, 'nodes')]
        materials = [CollisionMaterialRecord(index=i, name=self.value(e, 'name'))
                     for i, e in enumerate(self.block(root, 'materials'))]
        def bone(index):
            if index < 0 or index >= len(nodes):
                raise ValueError(f'Collision node index {index} is out of range')
            return nodes[index]
        meshes = []
        for region in self.block(root, 'regions'):
            for permutation in self.block(region, 'permutations'):
                for index, element in enumerate(self.block(permutation, 'bsps')):
                    node = self.value(element, 'node index')
                    bsp = self.required_field(element, 'bsp').as_struct()
                    vertices = [tuple(self.value(v, 'point').to_array()) for v in self.block(bsp, 'vertices')]
                    if any(not isfinite(x) for v in vertices for x in v):
                        raise ValueError('Collision vertices contain non-finite coordinates')
                    edge_names = ('start vertex', 'end vertex', 'forward edge', 'reverse edge', 'left surface', 'right surface')
                    edges = [tuple(self.value(e, n) & 0xffff for n in edge_names) for e in self.block(bsp, 'edges')]
                    surfaces, polygons = [], []
                    for surface_index, surface in enumerate(self.block(bsp, 'surfaces')):
                        first = self.value(surface, 'first edge') & 0xffff
                        current, visited, polygon = first, set(), []
                        while True:
                            if current in visited or current >= len(edges):
                                raise ValueError(f'Collision surface {surface_index} has an invalid edge loop')
                            visited.add(current)
                            start, end, forward, reverse, left, right = edges[current]
                            if left == surface_index:
                                vertex, following = start, forward
                            elif right == surface_index:
                                vertex, following = end, reverse
                            else:
                                raise ValueError('Collision edge does not belong to its surface')
                            if vertex >= len(vertices):
                                raise ValueError('Collision edge vertex is out of range')
                            polygon.append(vertex)
                            if following == first:
                                break
                            current = following
                        if len(polygon) < 3 or len(set(polygon)) != len(polygon):
                            raise ValueError('Collision surface has a degenerate polygon')
                        flags = self.required_field(surface, 'flags')
                        values = {}
                        for attribute, name in (('negated', 'plane negated'), ('invalid', 'invalid'),
                                                ('ladder', 'climbable'), ('breakable', 'breakable'),
                                                ('slip_surface', 'slip'), ('invisible', 'invisible'),
                                                ('two_sided', 'two sided')):
                            if attribute == 'negated' and self.game in {'halo3', 'halo3odst'}:
                                values[attribute] = bool(self.value(surface, 'plane') & 0x8000)
                            else:
                                values[attribute] = flags.get_flag(name)
                        values['two_sided'] &= not (values['breakable'] or values['invisible'])
                        material_index = self.value(surface, 'material')
                        material = materials[material_index] if 0 <= material_index < len(materials) else None
                        surfaces.append(Record(index=surface_index, material=material, **values))
                        polygons.append(polygon)
                    region_name, permutation_name = self.value(region, 'name'), self.value(permutation, 'name')
                    meshes.append(Record(name=f'{region_name}:{permutation_name}:{index}', region=region_name,
                                         permutation=permutation_name, node_index=node, bone=bone(node),
                                         vertices=vertices, surfaces=surfaces, polygons=polygons))
        spheres = []
        for index, element in enumerate(self.block(root, 'pathfinding spheres')):
            node = self.value(element, 'node')
            flags = self.required_field(element, 'flags')
            center = tuple(self.value(element, 'center').to_array())
            radius = self.value(element, 'radius')
            if not all(isfinite(v) for v in (*center, radius)) or radius < 0:
                raise ValueError('Invalid pathfinding sphere dimensions')
            spheres.append(Record(index=index, node_index=node, bone=bone(node), center=center, radius=radius,
                                  when_open=flags.get_flag('remains when open'), vehicle=flags.get_flag('vehicle only'),
                                  sectors=flags.get_flag('with sectors')))
        return meshes, spheres

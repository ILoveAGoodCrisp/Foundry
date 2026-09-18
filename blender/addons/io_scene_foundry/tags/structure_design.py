"""Detached structure-design surfaces, without render-resource or Blender dependencies."""
from collections import defaultdict
from math import isfinite
from types import SimpleNamespace

from .backend import TagDocument


class StructureDesignDocument(TagDocument):
    def _vector(self, struct, name):
        value = self.value(struct, name)
        result = ((value.alpha, value.red, value.green, value.blue) if name == 'fog color'
                  else tuple(value.to_array()))
        if not all(isfinite(v) for v in result):
            raise ValueError(f'{self.path}: non-finite {name}')
        return result

    def _number(self, struct, name):
        value = self.value(struct, name)
        if not isfinite(value):
            raise ValueError(f'{self.path}: non-finite {name}')
        return value

    def surfaces(self):
        root = self.tag.root()
        definitions = root.field('instanced geometries definitions')
        instances = root.field('instanced geometry instances')
        if ((definitions is not None and len(definitions.as_block())) or
                (instances is not None and len(instances.as_block()))):
            raise NotImplementedError(f'{self.path}: native rain-blocker render geometry is not implemented')
        physics = self.required_field(root, 'physics').as_struct()
        records = []
        for ceiling in self.block(physics, 'soft ceilings block'):
            vertices = [self._vector(triangle, f'vertex{i}')
                        for triangle in self.block(ceiling, 'soft ceiling triangles') for i in range(3)]
            if not vertices:
                continue
            kind = self.value(ceiling, 'type')
            names = ('acceleration', 'soft kill', 'slip surface')
            if isinstance(kind, str):
                kind = names.index(kind.lower().replace('_', ' '))
            if kind not in range(3):
                raise ValueError(f'{self.path}: unknown boundary surface type {kind!r}')
            records.append(SimpleNamespace(kind='boundary', name=self.value(ceiling, 'name'),
                                           vertices=vertices, boundary_type=kind))
        fog_set = root.field('planar fog set')
        if fog_set is not None:
            for fog in self.block(fog_set.as_struct(), 'planar fogs'):
                vertices = [self._vector(v, 'position') for v in self.block(fog, 'vertices')]
                if not vertices:
                    continue
                if len(vertices) % 3:
                    raise ValueError(f'{self.path}: fog vertices do not form complete triangles')
                records.append(SimpleNamespace(kind='fog', name=self.value(fog, 'name'),
                    vertices=vertices, appearance=self.reference(fog, 'appearance settings'),
                    depth=self._number(fog, 'depth')))
        groups = [self.value(g, 'name') for g in self.block(physics, 'water groups block')]
        grouped = defaultdict(list)
        for water in self.block(physics, 'water instances block'):
            triangles = self.block(water, 'water debug triangles block')
            if not len(triangles):
                continue
            group = self.value(water, 'group')
            if not 0 <= group < len(groups):
                raise ValueError(f'{self.path}: invalid water group index {group}')
            points = [[self._vector(t, f'point{i}') for i in range(3)] for t in triangles]
            # Match the existing importer: highest average triangle represents the surface.
            top = max(points, key=lambda tri: sum(p[2] for p in tri))
            if water.field('flow velocity') is None:
                raise NotImplementedError(f'{self.path}: H3/ODST water direction/angle conversion is not implemented')
            grouped[group].append(SimpleNamespace(vertices=top,
                low=min(p[2] for tri in points for p in tri), high=max(p[2] for p in top),
                flow=self._vector(water, 'flow velocity'), color=self._vector(water, 'fog color'),
                murkiness=self._number(water, 'fog murkiness')))
        for group, waters in grouped.items():
            properties = waters[-1]
            records.append(SimpleNamespace(kind='water', name=groups[group],
                vertices=[v for water in waters for v in water.vertices],
                depth=max(w.high for w in waters) - min(w.low for w in waters),
                flow=properties.flow, color=properties.color, murkiness=properties.murkiness))
        return records

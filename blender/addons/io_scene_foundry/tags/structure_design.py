"""Detached structure-design surfaces and instanced rain geometry."""
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
            if self.game in {'halo3', 'halo3odst'}:
                # These are closed authored volumes, not Reach's surface/depth
                # water. Retain every face and each instance's current settings.
                records.append(SimpleNamespace(kind='water_volume', name=groups[group],
                    vertices=[p for triangle in points for p in triangle],
                    direction=self._vector(water, 'direction'), angle=self._number(water, 'angle')))
                continue
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

    def set_water_properties(self, properties):
        """Apply editable H3/ODST currents after Tool builds the volume planes."""
        physics = self.required_field(self.tag.root(), 'physics').as_struct()
        groups = [self.value(group, 'name') for group in self.block(physics, 'water groups block')]
        for water in self.block(physics, 'water instances block'):
            group = self.value(water, 'group')
            if not 0 <= group < len(groups) or groups[group] not in properties:
                continue
            direction, angle = properties[groups[group]]
            self.required_field(water, 'direction').set(self.api.RealVector3d(*direction))
            self.required_field(water, 'angle').set(angle)
            self.tag_has_changes = True

    def rain_geometry(self):
        """Decode design meshes with each definition's compression bounds.

        Structure designs use the same render resource layout as BSPs. Keep
        placement separate so repeated instances can share Blender mesh data.
        """
        root = self.tag.root()
        field = root.field('instanced geometry instances')
        instances = [] if field is None else field.as_block()
        if not len(instances):
            return [], []
        definitions = self.block(root, 'instanced geometries definitions')
        geometry = self.required_field(root, 'render geometry').as_struct()
        mesh_count = len(self.block(geometry, 'meshes'))
        bound_count = len(self.block(geometry, 'compression info'))
        compression = [-1] * mesh_count
        mesh_indices = []
        for index, definition in enumerate(definitions):
            mesh = self.value(definition, 'mesh index')
            bounds = self.value(definition, 'compression index')
            if not 0 <= mesh < mesh_count:
                raise ValueError(f'{self.path}: definition {index} has invalid mesh index {mesh}')
            if bounds < -1 or bounds >= bound_count:
                raise ValueError(f'{self.path}: definition {index} has invalid compression index {bounds}')
            if mesh in mesh_indices and compression[mesh] != bounds:
                raise ValueError(f'{self.path}: mesh {mesh} uses conflicting compression bounds')
            compression[mesh] = bounds
            mesh_indices.append(mesh)
        placements = []
        for index, instance in enumerate(instances):
            definition = self.value(instance, 'instance definition')
            if not 0 <= definition < len(definitions):
                raise ValueError(f'{self.path}: instance {index} has invalid definition index {definition}')
            sheet = self.required_field(instance, 'flags').get_flag('vertical rain sheet')
            placements.append(SimpleNamespace(
                mesh_index=mesh_indices[definition],
                name=self.value(instance, 'name') or f'rain_instance:{index}',
                vertical_rain_sheet=sheet, scale=self._number(instance, 'scale'),
                forward=self._vector(instance, 'forward'), left=self._vector(instance, 'left'),
                up=self._vector(instance, 'up'), position=self._vector(instance, 'position')))
        meshes = self.tag.sbsp_render_meshes(compression)
        if len(meshes) != mesh_count:
            raise ValueError(f'{self.path}: decoded {len(meshes)} of {mesh_count} rain meshes')
        return meshes, placements

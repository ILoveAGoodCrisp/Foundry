"""Native prefab metadata."""
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from types import SimpleNamespace as Record

from ..constants import (
    LIGHTMAP_ADDITIVE_TRANSPARENCY_COLOR,
    LIGHTMAP_ANALYTICAL_LIGHT_ABSORB,
    LIGHTMAP_CHART_GROUP_INDEX,
    LIGHTMAP_IGNORE_DEFAULT_RESOLUTION_SCALE,
    LIGHTMAP_LIGHTING_FROM_BOTH_SIDES,
    LIGHTMAP_NORMAL_LIGHT_ABSORD,
    LIGHTMAP_RESOLUTION_SCALE,
    LIGHTMAP_TRANSLUCENCY_TINT_COLOR,
    LIGHTMAP_TRANSPARENCY_OVERRIDE,
    WU_SCALAR,
)
from .backend import TagDocument, TagReference
from .blender import BlenderTag


@dataclass(frozen=True)
class StructureBspPrefab:
    reference: TagReference
    name: str
    forward: tuple[float, float, float]
    left: tuple[float, float, float]
    up: tuple[float, float, float]
    position: tuple[float, float, float]
    scale: float


@dataclass(frozen=True)
class StructureBspCollisionMaterial:
    index: int
    render_method: TagReference | None
    override_material_name: str
    is_seam: bool


@dataclass(frozen=True)
class StructureBspCompressionBounds:
    position_0: tuple[float, float, float]
    position_1: tuple[float, float, float]
    texcoord_0: tuple[float, float]
    texcoord_1: tuple[float, float]


@dataclass(frozen=True)
class StructureBspEmissive:
    power: float
    color: tuple[float, float, float]
    quality: float
    focus: float
    power_per_unit_area: bool
    use_shader_gel: bool
    attenuation_falloff: float
    attenuation_cutoff: float
    bounce_ratio: float


@dataclass(frozen=True)
class StructureBspRenderMaterial:
    index: int
    render_method: TagReference
    emissive_index: int
    lightmap_resolution: float
    additive_transparency: int
    translucency_tint: int
    lighting_from_both_sides: bool
    transparency_override: bool
    ignore_default_resolution: bool
    chart_group_index: int
    breakable_surface_index: int
    analytical_absorb: float
    normal_absorb: float


@dataclass(frozen=True)
class StructureBspPortal:
    index: int
    one_way: bool
    no_way: bool
    ai_deafening: bool
    blocks_sounds: bool
    is_door: bool
    vertices: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class StructureBspMarker:
    name: str
    rotation: tuple[float, float, float, float]
    position: tuple[float, float, float]


@dataclass(frozen=True)
class StructureBspEnvironmentObject:
    name: str
    rotation: tuple[float, float, float, float]
    translation: tuple[float, float, float]
    scale: float
    definition: TagReference | None
    variant: str


@dataclass(frozen=True)
class StructureBspHavokGeometry:
    data: bytes
    kind: str
    collision_type: int
    bounds_min: tuple[float, float, float] | None
    bounds_max: tuple[float, float, float] | None


class PrefabTag(BlenderTag, TagDocument):
    tag_ext = 'prefab'

    def bsp_path(self):
        reference = self.reference(self.tag.root(), 'bsp reference')
        if reference is None:
            return None
        path = Path(reference.Filename)
        return path if path.is_file() else None


class ScenarioStructureBspMetadataTag(BlenderTag, TagDocument):
    tag_ext = 'scenario_structure_bsp'

    def _set_vector(self, element, name, values):
        field = self.required_field(element, name)
        field.set(type(field.value)(*(float(value) for value in values)))

    def prefabs(self) -> list[StructureBspPrefab]:
        if not self.corinth:
            return []
        records = []
        for element in self.block(self.tag.root(), 'external references'):
            reference = self.reference(element, 'prefab reference')
            if reference is None:
                continue
            vectors = {
                name: tuple(self.value(element, name).to_array())
                for name in ('forward', 'left', 'up', 'position')
            }
            records.append(StructureBspPrefab(
                reference=reference,
                name=str(self.value(element, 'name')),
                scale=float(self.value(element, 'scale')),
                **vectors,
            ))
        return records

    def collision_materials(self) -> list[StructureBspCollisionMaterial]:
        records = []
        for index, element in enumerate(self.block(self.tag.root(), 'collision materials')):
            override = element.field('override material name')
            flags = element.field('flags')
            records.append(StructureBspCollisionMaterial(
                index=index,
                render_method=self.reference(element, 'render method'),
                override_material_name='' if override is None else str(override.value),
                is_seam=False if flags is None else flags.get_flag('is seam'),
            ))
        return records

    def structure_lighting_info(self):
        if not self.corinth:
            return None
        return self.reference(self.tag.root(), 'structure lighting_info')

    def structure_meta_data(self):
        if not self.corinth:
            return None
        return self.reference(self.tag.root(), 'structure meta data')

    def compression_bounds(self) -> list[StructureBspCompressionBounds]:
        geometry = self.required_field(self.tag.root(), 'render geometry').as_struct()
        if geometry is None:
            raise TypeError(f'{self.path}: render geometry is not a struct')
        records = []
        for element in self.block(geometry, 'compression info'):
            records.append(StructureBspCompressionBounds(*(
                tuple(self.value(element, name).to_array())
                for name in ('position bounds 0', 'position bounds 1',
                             'texcoord bounds 0', 'texcoord bounds 1')
            )))
        return records

    def emissive_materials(self) -> list[StructureBspEmissive]:
        if not self.corinth:
            return []
        records = []
        for element in self.block(self.tag.root(), 'emissive materials'):
            flags = self.required_field(element, 'flags')
            color = self.value(element, 'emissive color')
            records.append(StructureBspEmissive(
                power=float(self.value(element, 'emissive power')),
                color=(float(color.red), float(color.green), float(color.blue)),
                quality=float(self.value(element, 'emissive quality')),
                focus=float(self.value(element, 'emissive focus')),
                power_per_unit_area=flags.get_flag('power per unit area'),
                use_shader_gel=flags.get_flag('use shader gel'),
                attenuation_falloff=float(self.value(element, 'attenuation falloff')),
                attenuation_cutoff=float(self.value(element, 'attenuation cutoff')),
                bounce_ratio=float(self.value(element, 'bounce ratio')),
            ))
        return records

    def render_materials(self) -> list[StructureBspRenderMaterial]:
        records = []
        for index, element in enumerate(self.block(self.tag.root(), 'materials')):
            render_method = self.reference(element, 'render method')
            if render_method is None:
                raise ValueError(f'{self.path}: material {index} has no render method')

            resolution = LIGHTMAP_RESOLUTION_SCALE
            additive = LIGHTMAP_ADDITIVE_TRANSPARENCY_COLOR
            translucency = LIGHTMAP_TRANSLUCENCY_TINT_COLOR
            both_sides = LIGHTMAP_LIGHTING_FROM_BOTH_SIDES
            transparency_override = LIGHTMAP_TRANSPARENCY_OVERRIDE
            ignore_default = LIGHTMAP_IGNORE_DEFAULT_RESOLUTION_SCALE
            chart_group = LIGHTMAP_CHART_GROUP_INDEX
            analytical = LIGHTMAP_ANALYTICAL_LIGHT_ABSORB
            normal = LIGHTMAP_NORMAL_LIGHT_ABSORD

            properties = element.field('properties')
            if properties is not None:
                for prop in properties.as_block():
                    kind = self.value(prop, 'type')
                    if kind == 'lightmap resolution':
                        resolution = float(self.value(prop, 'real-value'))
                    elif kind == 'lightmap translucency tint color':
                        translucency = int(self.value(prop, 'long-value'))
                    elif kind == 'lightmap transparency override':
                        transparency_override = bool(self.value(prop, 'int-value'))
                    elif kind == 'lightmap additive transparency':
                        additive = int(self.value(prop, 'long-value'))
                    elif kind == 'lightmap ignore default res scale':
                        ignore_default = bool(self.value(prop, 'int-value'))
            else:
                resolution = float(self.value(element, 'lightmap resolution scale'))
                additive = int(self.value(element, 'lightmap additive transparency color'))
                translucency = int(self.value(element, 'lightmap traslucency tint color'))
                analytical = float(self.value(element, 'lightmap analytical light absorb'))
                normal = float(self.value(element, 'lightmap normal light absorb'))
                flags = self.required_field(element, 'lightmap flags')
                both_sides = flags.get_flag('lighting from both sides')
                transparency_override = flags.get_flag('transparency override')
                ignore_default = flags.get_flag('ignore default resolution scale')
                chart_group = int(self.value(element, 'lightmap chart group index'))

            records.append(StructureBspRenderMaterial(
                index=index,
                render_method=render_method,
                emissive_index=int(self.value(element, 'imported material index')),
                lightmap_resolution=resolution,
                additive_transparency=additive,
                translucency_tint=translucency,
                lighting_from_both_sides=both_sides,
                transparency_override=transparency_override,
                ignore_default_resolution=ignore_default,
                chart_group_index=chart_group,
                breakable_surface_index=int(self.value(element, 'breakable surface index')),
                analytical_absorb=analytical,
                normal_absorb=normal,
            ))
        return records

    def portals(self) -> list[StructureBspPortal]:
        records = []
        for index, element in enumerate(self.block(self.tag.root(), 'cluster portals')):
            flags = self.required_field(element, 'flags')
            vertices = tuple(
                tuple(self.value(vertex, 'point').to_array())
                for vertex in self.block(element, 'vertices')
            )
            records.append(StructureBspPortal(
                index=index,
                one_way=flags.get_flag('one-way') or flags.get_flag('one-way-reversed'),
                no_way=flags.get_flag('no-way'),
                ai_deafening=flags.get_flag("ai can't hear through this shit"),
                blocks_sounds=flags.get_flag('no one can hear through this'),
                is_door=flags.get_flag('door'),
                vertices=vertices,
            ))
        return records

    def markers(self) -> list[StructureBspMarker]:
        records = []
        for element in self.block(self.tag.root(), 'markers'):
            name_field = element.field('marker parameter') or element.field('name')
            if name_field is None:
                raise ValueError(f'{self.path}: structure marker has no name field')
            records.append(StructureBspMarker(
                name=str(name_field.value),
                rotation=tuple(self.value(element, 'rotation').to_array()),
                position=tuple(self.value(element, 'position').to_array()),
            ))
        return records

    def environment_objects(self) -> list[StructureBspEnvironmentObject]:
        if self.corinth:
            return []
        palette = [self.reference(element, 'definition')
                   for element in self.block(self.tag.root(), 'environment object palette')]
        records = []
        for element in self.block(self.tag.root(), 'environment objects'):
            palette_index = int(self.value(element, 'palette_index'))
            definition = (palette[palette_index]
                          if 0 <= palette_index < len(palette) else None)
            variant = element.field('variant name')
            records.append(StructureBspEnvironmentObject(
                name=str(self.value(element, 'name')),
                rotation=tuple(self.value(element, 'rotation').to_array()),
                translation=tuple(self.value(element, 'translation').to_array()),
                scale=float(self.value(element, 'scale')),
                definition=definition,
                variant='' if variant is None else str(variant.value),
            ))
        return records

    def havok_geometry(self) -> list[StructureBspHavokGeometry]:
        """Detach serialized H4/H2AMP structure collision from tag handles."""
        interface_field = self.tag.root().field('resource interface')
        if interface_field is None:
            return []
        interface = interface_field.as_struct()
        if interface is None:
            raise TypeError(f'{self.path}: resource interface is not a struct')
        raw_resources_field = interface.field('raw_resources')
        if raw_resources_field is None:
            return []
        raw_resources = raw_resources_field.as_block()
        if raw_resources is None:
            raise TypeError(f'{self.path}: raw resources is not a block')

        records: list[StructureBspHavokGeometry] = []
        for raw_resource in raw_resources:
            raw_items_field = raw_resource.field('raw_items')
            if raw_items_field is None:
                continue
            raw_items = raw_items_field.as_struct()
            if raw_items is None:
                raise TypeError(f'{self.path}: raw resource items is not a struct')
            havok_field = raw_items.field('Havok Data')
            if havok_field is None:
                continue
            havok_data = havok_field.as_block()
            if havok_data is None:
                raise TypeError(f'{self.path}: Havok data is not a block')
            for havok in havok_data:
                bounds = []
                for name in ('Shapes bounds min', 'Shapes bounds max'):
                    field = havok.field(name)
                    bounds.append(None if field is None else tuple(field.value.to_array()))
                per_type_field = havok.field('Serialized Per Collision Type Havok Geometry')
                if per_type_field is None:
                    continue
                per_type = per_type_field.as_block()
                if per_type is None:
                    raise TypeError(f'{self.path}: serialized Havok geometry is not a block')
                for index, element in enumerate(per_type):
                    collision_field = element.field('collision type')
                    collision_type = index if collision_field is None else int(collision_field.value)
                    for field_name, kind in (
                            ('Serialized Havok Data', 'havok_collision'),
                            ('Serialized Static Havok Data', 'static_havok_collision')):
                        field = element.field(field_name)
                        data = None if field is None else field.as_data()
                        if data:
                            records.append(StructureBspHavokGeometry(
                                data=bytes(data), kind=kind,
                                collision_type=collision_type,
                                bounds_min=bounds[0], bounds_max=bounds[1]))
        return records

    def cookie_cutters(self):
        field = self.tag.root().field('cookie cutters')
        if field is None:
            return []
        records = []
        edge_names = ('start vertex', 'end vertex', 'forward edge', 'reverse edge',
                      'left surface', 'right surface')
        for index, element in enumerate(field.as_block()):
            collision = self.required_field(element, 'collision model').as_struct()
            if collision is None:
                raise TypeError(f'{self.path}: cookie cutter collision model is not a struct')
            vertices = [tuple(self.value(vertex, 'point').to_array())
                        for vertex in self.block(collision, 'vertices')]
            if any(not isfinite(value) for vertex in vertices for value in vertex):
                raise ValueError(f'{self.path}: cookie cutter has non-finite vertices')
            edges = [tuple(int(self.value(edge, name)) & 0xffff for name in edge_names)
                     for edge in self.block(collision, 'edges')]
            surfaces, polygons = [], []
            for surface_index, surface in enumerate(self.block(collision, 'surfaces')):
                first = int(self.value(surface, 'first edge')) & 0xffff
                current, visited, polygon = first, set(), []
                while True:
                    if current in visited or current >= len(edges):
                        raise ValueError(
                            f'{self.path}: cookie cutter surface {surface_index} has an invalid edge loop')
                    visited.add(current)
                    start, end, forward, reverse, left, right = edges[current]
                    if left == surface_index:
                        vertex, following = start, forward
                    elif right == surface_index:
                        vertex, following = end, reverse
                    else:
                        raise ValueError(
                            f'{self.path}: cookie cutter edge does not belong to its surface')
                    if vertex >= len(vertices):
                        raise ValueError(f'{self.path}: cookie cutter vertex is out of range')
                    polygon.append(vertex)
                    if following == first:
                        break
                    current = following
                if len(polygon) < 3 or len(set(polygon)) != len(polygon):
                    raise ValueError(f'{self.path}: cookie cutter has a degenerate surface')
                flags = self.required_field(surface, 'flags')
                breakable = flags.get_flag('breakable')
                invisible = flags.get_flag('invisible')
                surfaces.append(Record(
                    index=surface_index,
                    material=None,
                    negated=flags.get_flag('plane negated'),
                    invalid=flags.get_flag('invalid'),
                    ladder=flags.get_flag('climbable'),
                    breakable=breakable,
                    slip_surface=flags.get_flag('slip'),
                    invisible=invisible,
                    two_sided=flags.get_flag('two sided') and not (breakable or invisible),
                ))
                polygons.append(polygon)
            records.append(Record(
                name=f'cookie_cutter{index}', node_index=-1, bone='', vertices=vertices,
                surfaces=surfaces, polygons=polygons))
        return records

    def fix_collision_render_surface_mapping(self):
        """Create the proxy-collision surface mapping omitted by older tools."""
        if self.corinth:
            return
        resource_interface = self.required_field(
            self.tag.root(), 'resource interface').as_struct()
        if resource_interface is None:
            raise TypeError(f'{self.path}: resource interface is not a struct')
        raw_resources = self.block(resource_interface, 'raw_resources')
        if not len(raw_resources):
            return
        raw_items = self.required_field(raw_resources[0], 'raw_items').as_struct()
        if raw_items is None:
            raise TypeError(f'{self.path}: raw_items is not a struct')

        changed = False
        for definition in self.block(raw_items, 'instanced geometries definitions'):
            surfaces = self.block(definition, 'surfaces')
            if len(surfaces):
                continue
            collision_info = self.required_field(definition, 'collision info').as_struct()
            if collision_info is None:
                raise TypeError(f'{self.path}: collision info is not a struct')
            for _ in self.block(collision_info, 'surfaces'):
                surfaces.add()
                changed = True
        if changed:
            self.tag_has_changes = True

    def write_prefabs(self, prefabs):
        if not self.corinth:
            raise ValueError('Structure-BSP prefab records only exist in H4/H2AMP')
        block = self.block(self.tag.root(), 'external references')
        if not prefabs and not len(block):
            return
        block.clear()
        for prefab in prefabs:
            element = block[block.add()]
            self.set_reference(element, 'prefab reference', prefab.reference)
            self.required_field(element, 'name').set(prefab.name)
            self.required_field(element, 'scale').set(float(prefab.scale))
            for name in ('forward', 'left', 'up', 'position'):
                self._set_vector(element, name, getattr(prefab, name))

            override_flags = self.required_field(element, 'override flags')
            flags_mask = self.required_field(element, 'instance flags Mask')
            policy_mask = self.required_field(element, 'instance policy mask')
            nwo = prefab.props

            if nwo.prefab_lighting != 'no_override':
                policy_mask.set_flag('override lightmapping policy', True)
                lighting = {
                    'per_pixel': 0, 'per_vertex': 1,
                    'single_probe': 2, 'per_vertex_ao': 5,
                }.get(nwo.prefab_lighting)
                if lighting is None:
                    raise ValueError(f'Unknown prefab lighting policy: {nwo.prefab_lighting}')
                self.required_field(element, 'override lightmapping policy').set(lighting)

            if nwo.prefab_lightmap_res > 0:
                policy_mask.set_flag('override lightmap resolution policy', True)
                self.required_field(element, 'override lightmap resolution scale').set(
                    nwo.prefab_lightmap_res)

            if nwo.prefab_pathfinding != 'no_override':
                policy_mask.set_flag('override pathfinding policy', True)
                pathfinding = {'cutout': 0, 'static': 1, 'none': 2}.get(
                    nwo.prefab_pathfinding)
                if pathfinding is None:
                    raise ValueError(
                        f'Unknown prefab pathfinding policy: {nwo.prefab_pathfinding}')
                self.required_field(element, 'override pathfinding policy').set(pathfinding)

            if nwo.prefab_imposter_policy != 'no_override':
                policy_mask.set_flag('override lmposter policy', True)
                imposter = {
                    'polygon_default': 0, 'polygon_high': 1,
                    'card_default': 2, 'card_high': 3, 'never': 4,
                }.get(nwo.prefab_imposter_policy)
                if imposter is None:
                    raise ValueError(
                        f'Unknown prefab imposter policy: {nwo.prefab_imposter_policy}')
                self.required_field(element, 'override imposter policy').set(imposter)
                if nwo.prefab_imposter_policy != 'never':
                    if nwo.prefab_imposter_brightness > 0:
                        policy_mask.set_flag('override imposter brightness', True)
                        self.required_field(element, 'override imposter brightness').set(
                            nwo.prefab_imposter_brightness)
                    if not nwo.prefab_imposter_transition_distance_auto:
                        policy_mask.set_flag(
                            'override imposter transition distance policy', True)
                        self.required_field(
                            element, 'override imposter transition distance').set(
                                nwo.prefab_imposter_transition_distance * WU_SCALAR)

            if nwo.prefab_streaming_priority != 'no_override':
                priority = {
                    '_connected_geometry_poop_streamingpriority_default': 0,
                    '_connected_geometry_poop_streamingpriority_higher': 1,
                    '_connected_geometry_poop_streamingpriority_highest': 2,
                }.get(nwo.prefab_streaming_priority)
                if priority is None:
                    raise ValueError(
                        f'Unknown prefab streaming priority: {nwo.prefab_streaming_priority}')
                self.required_field(element, 'override streaming priority').set(priority)

            flag_values = {
                'cinema only': nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_only',
                'exclude from cinema': nwo.prefab_cinematic_properties == '_connected_geometry_poop_cinema_exclude',
                'render only': nwo.prefab_render_only,
                'does not block aoe damage': nwo.prefab_does_not_block_aoe,
                'not in lightprobes': nwo.prefab_excluded_from_lightprobe,
                'decal spacing': nwo.prefab_decal_spacing,
                'remove from shadow geometry': nwo.prefab_remove_from_shadow_geometry,
                'disallow object lighting samples': nwo.prefab_disallow_lighting_samples,
            }
            for name, enabled in flag_values.items():
                if enabled:
                    override_flags.set_flag(name, True)
                    flags_mask.set_flag(name, True)
        self.tag_has_changes = True

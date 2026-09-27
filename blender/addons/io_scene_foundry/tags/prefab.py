"""Native prefab metadata."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from types import SimpleNamespace as Record
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast

if TYPE_CHECKING:
    import blam_tags

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
from .metadata import enum_index


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
    plane_index: int = -1
    back_cluster: int = -1
    front_cluster: int = -1
    polygons: tuple[tuple[int, ...], ...] = ()


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


@dataclass(frozen=True)
class StructureBspCollisionSurface:
    index: int
    material_index: int
    negated: bool
    invalid: bool
    ladder: bool
    breakable: bool
    slip_surface: bool
    invisible: bool
    two_sided: bool


@dataclass(frozen=True)
class StructureBspCollision:
    vertices: tuple[tuple[float, float, float], ...]
    surfaces: tuple[StructureBspCollisionSurface, ...]
    polygons: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class StructureBspSurfaceMapping:
    surface_index: int
    triangle_values: tuple[int, ...]
    direct_triangles: tuple[tuple[int, int], ...] = ()

    @property
    def collision_only(self) -> bool:
        return not self.triangle_values and not self.direct_triangles


@dataclass(frozen=True)
class StructureBspInstance:
    index: int
    definition_index: int
    scale: float
    forward: tuple[float, float, float]
    left: tuple[float, float, float]
    up: tuple[float, float, float]
    position: tuple[float, float, float]
    not_in_lightprobes: bool
    render_only: bool
    not_block_aoe: bool
    decal: bool
    imposter_transition: float
    pathfinding: int
    lightmapping: int
    imposter: int
    lightmap_resolution: float
    name: str
    remove_from_shadow: bool
    cinema_type: int
    imposter_brightness: float
    disallow_lighting_samples: bool
    streaming: int
    world_bound_sphere_radius: float


@dataclass(frozen=True)
class StructureBspPhysicsPolyhedron:
    material_index: int
    radius: float
    vertices: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class StructureBspInstanceDefinition:
    index: int
    mesh_index: int
    compression_index: int
    collision: StructureBspCollision | None
    collision_is_proxy: bool
    surface_mappings: tuple[StructureBspSurfaceMapping, ...]
    cookie_cutter: StructureBspCollision | None
    physics: tuple[StructureBspPhysicsPolyhedron, ...]


@dataclass(frozen=True)
class StructureBspRenderPart:
    material_index: int
    index_start: int
    index_count: int
    part_type: int


@dataclass(frozen=True)
class StructureBspRenderWater:
    triangles: tuple[tuple[tuple[int, int], ...], ...]
    base_texcoords: tuple[tuple[float, float, float], ...]
    part_indices: tuple[int, ...]


@dataclass(frozen=True)
class StructureBspRenderMesh:
    index: int
    positions: tuple[tuple[float, float, float], ...]
    texcoords: tuple[tuple[float, float], ...]
    normals: tuple[tuple[float, float, float], ...]
    node_indices: tuple[tuple[int, int, int, int], ...]
    node_weights: tuple[tuple[float, float, float, float], ...]
    lightmap_texcoords: tuple[tuple[float, float], ...]
    vertex_colors: tuple[tuple[float, float, float], ...]
    indices: tuple[int, ...]
    rigid_node_index: int
    parts: tuple[StructureBspRenderPart, ...]
    water: StructureBspRenderWater | None


class ClassicBspInstance(TypedDict):
    object_index: int
    name: str
    rotation: tuple[float, float, float, float]
    translation: tuple[float, float, float]
    scale: float
    mesh_type: str
    reference: str


class ClassicBspScene(TypedDict):
    materials: list[str]
    material_paths: NotRequired[list[str]]
    objects: list[dict[str, object] | None]
    instances: list[ClassicBspInstance]


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

    @staticmethod
    def _render_mesh_record(index: int, mesh: dict[str, object]) -> StructureBspRenderMesh:
        return StructureBspRenderMesh(
            index=index,
            positions=tuple(tuple(map(float, value)) for value in cast(list, mesh['positions'])),
            texcoords=tuple(tuple(map(float, value)) for value in cast(list, mesh['texcoords'])),
            normals=tuple(tuple(map(float, value)) for value in cast(list, mesh['normals'])),
            node_indices=tuple(tuple(map(int, value)) for value in cast(list, mesh['node_indices'])),
            node_weights=tuple(tuple(map(float, value)) for value in cast(list, mesh['node_weights'])),
            lightmap_texcoords=tuple(tuple(map(float, value)) for value in cast(list, mesh['lightmap_texcoords'])),
            vertex_colors=tuple(tuple(map(float, value)) for value in cast(list, mesh['vertex_colors'])),
            indices=tuple(map(int, cast(list, mesh['indices']))),
            rigid_node_index=(-1 if mesh['rigid_node_index'] is None
                              else int(cast(int, mesh['rigid_node_index']))),
            parts=tuple(StructureBspRenderPart(
                material_index=int(part['material_index']),
                index_start=int(part['index_start']),
                index_count=int(part['index_count']),
                part_type=int(part['part_type']),
            ) for part in cast(list[dict[str, object]], mesh['parts'])),
            water=None,
        )

    @staticmethod
    def _assign_classic_material_path(
        names: list[str], paths: list[str], reference: TagReference, start: int = 0,
    ) -> None:
        """Match a shader reference to the material name emitted by JMS/ASS."""
        name = Path(reference.RelativePath).name
        for index in range(start, len(names)):
            if names[index] == name and not paths[index]:
                paths[index] = reference.RelativePathWithExtension
                return

    def _classic_material_paths(self, names: list[str]) -> list[str]:
        """Read paths from classic BSP fields used by older native decoders."""
        paths = [''] * len(names)
        root = self.tag.root()
        if self.game == 'halo1':
            lightmaps_field = root.field('lightmaps')
            lightmaps = None if lightmaps_field is None else lightmaps_field.as_block()
            if lightmaps is not None:
                for lightmap in lightmaps:
                    materials_field = lightmap.field('materials')
                    materials = None if materials_field is None else materials_field.as_block()
                    if materials is None:
                        continue
                    for material in materials:
                        reference = self.reference(material, 'shader')
                        if reference is not None:
                            self._assign_classic_material_path(names, paths, reference)

            collision_field = root.field('collision materials')
            collision_materials = (
                None if collision_field is None else collision_field.as_block())
            if collision_materials is not None:
                collision_start = max(0, len(names) - len(collision_materials))
                for material in collision_materials:
                    reference = self.reference(material, 'shader')
                    if reference is not None:
                        self._assign_classic_material_path(
                            names, paths, reference, collision_start)
            return paths

        materials_field = root.field('materials')
        materials = None if materials_field is None else materials_field.as_block()
        if materials is None:
            return paths
        for index, material in enumerate(materials):
            if index >= len(paths):
                break
            reference = self.reference(material, 'shader')
            if reference is None:
                reference = self.reference(material, 'old shader')
            if reference is not None:
                paths[index] = reference.RelativePathWithExtension
        return paths

    def classic_render_scene(
        self,
    ) -> tuple[list[str], list[str], list[StructureBspRenderMesh | None], list[ClassicBspInstance]]:
        """Decode a complete H1/H2 BSP scene through the native classic extractor."""
        decoder = getattr(self.tag, 'classic_sbsp_scene', None)
        if decoder is None:
            raise RuntimeError(
                'The bundled blam-tags binding predates classic BSP geometry decoding')
        scene = cast(ClassicBspScene, decoder())
        meshes = [
            None if mesh is None else self._render_mesh_record(index, mesh)
            for index, mesh in enumerate(scene['objects'])
        ]
        material_names = scene['materials']
        material_paths = scene.get('material_paths')
        if material_paths is None:
            material_paths = self._classic_material_paths(material_names)
        if len(material_paths) != len(material_names):
            raise ValueError(
                f'{self.path}: native classic BSP decoder returned '
                f'{len(material_paths)} material paths for {len(material_names)} materials')
        return material_names, material_paths, meshes, scene['instances']

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
            if self.game == 'halo1':
                one_way = no_way = blocks_sounds = is_door = False
                ai_deafening = flags.get_flag("ai cant hear through this shit")
            else:
                one_way = (flags.get_flag('one-way')
                           or flags.get_flag('one-way-reversed'))
                no_way = flags.get_flag('no-way')
                ai_deafening = flags.get_flag("ai can't hear through this shit")
                blocks_sounds = flags.get_flag('no one can hear through this')
                is_door = flags.get_flag('door')
            vertices = tuple(
                tuple(self.value(vertex, 'point').to_array())
                for vertex in self.block(element, 'vertices')
            )
            if self.game != 'halo1' and flags.get_flag('one-way-reversed'):
                vertices = tuple(reversed(vertices))
            records.append(StructureBspPortal(
                index=index,
                one_way=one_way,
                no_way=no_way,
                ai_deafening=ai_deafening,
                blocks_sounds=blocks_sounds,
                is_door=is_door,
                vertices=vertices,
                plane_index=int(self.value(element, 'plane index')) if self.game == 'reach' else -1,
                back_cluster=int(self.value(element, 'back cluster')) if self.game == 'reach' else -1,
                front_cluster=int(self.value(element, 'front cluster')) if self.game == 'reach' else -1,
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

    def _raw_resource_items(self) -> list[blam_tags.TagStruct]:
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
        items = []
        for raw_resource in raw_resources:
            raw_items_field = raw_resource.field('raw_items')
            if raw_items_field is None:
                continue
            raw_items = raw_items_field.as_struct()
            if raw_items is None:
                raise TypeError(f'{self.path}: raw resource items is not a struct')
            items.append(raw_items)
        return items

    def _collision_bsp(self, collision: blam_tags.TagStruct, *, large: bool,
                       label: str) -> StructureBspCollision:
        vertices = tuple(
            tuple(cast('blam_tags.RealPoint3d', self.value(element, 'point')).to_array())
            for element in self.block(collision, 'vertices')
        )
        if any(not isfinite(value) for vertex in vertices for value in vertex):
            raise ValueError(f'{self.path}: {label} has non-finite vertices')
        mask = 0xffffffff if large else 0xffff
        edge_names = ('start vertex', 'end vertex', 'forward edge', 'reverse edge',
                      'left surface', 'right surface')
        edges = tuple(
            tuple(int(self.value(edge, name)) & mask for name in edge_names)
            for edge in self.block(collision, 'edges')
        )
        surfaces: list[StructureBspCollisionSurface] = []
        polygons: list[tuple[int, ...]] = []
        for surface_index, surface in enumerate(self.block(collision, 'surfaces')):
            first = int(self.value(surface, 'first edge')) & mask
            current, visited, polygon = first, set(), []
            while True:
                if current in visited or current >= len(edges):
                    raise ValueError(
                        f'{self.path}: {label} surface {surface_index} has an invalid edge loop')
                visited.add(current)
                start, end, forward, reverse, left, right = edges[current]
                if left == surface_index:
                    vertex, following = start, forward
                elif right == surface_index:
                    vertex, following = end, reverse
                else:
                    raise ValueError(f'{self.path}: {label} edge does not belong to its surface')
                if vertex >= len(vertices):
                    raise ValueError(f'{self.path}: {label} vertex is out of range')
                polygon.append(vertex)
                if following == first:
                    break
                current = following
            if len(polygon) < 3 or len(set(polygon)) != len(polygon):
                raise ValueError(f'{self.path}: {label} has a degenerate surface')
            flags = self.required_field(surface, 'flags')
            breakable = flags.get_flag('breakable')
            invisible = flags.get_flag('invisible')
            surfaces.append(StructureBspCollisionSurface(
                index=surface_index,
                material_index=int(self.value(surface, 'material')),
                negated=((int(self.value(surface, 'plane')) & 0x8000) != 0
                         if self.game == 'halo2' else
                         self.game not in {'halo3', 'halo3odst'} and flags.get_flag('plane negated')),
                invalid=flags.get_flag('invalid'),
                ladder=flags.get_flag('climbable'),
                breakable=breakable,
                slip_surface=False if self.game == 'halo2' else flags.get_flag('slip'),
                invisible=invisible,
                two_sided=(flags.get_flag('two sided') and
                           not (breakable or invisible)),
            ))
            polygons.append(tuple(polygon))
        return StructureBspCollision(vertices, tuple(surfaces), tuple(polygons))

    def portal_collision_tree(self):
        """Read Reach's visibility classification without assuming node zero is its root."""
        from .reach_portals import unpack_collision_node
        for raw in self._raw_resource_items():
            for name in ('collision bsp', 'large collision bsp'):
                field = raw.field(name)
                if field is None or field.as_block() is None or not len(field.as_block()):
                    continue
                bsp = field.as_block()[0]
                planes = [(p.i, p.j, p.k, p.d) for element in self.block(bsp, 'planes')
                          for p in (self.value(element, 'plane'),)]
                if name == 'large collision bsp':
                    nodes = [tuple(int(self.value(node, field))
                                   for field in ('plane', 'back child', 'front child'))
                             for node in self.block(bsp, 'bsp3d nodes')]
                else:
                    nodes = [unpack_collision_node(int(self.value(node, 'node data designator')))
                             for node in self.block(bsp, 'bsp3d nodes')]
                supernodes = []
                for node in self.block(bsp, 'bsp3d supernodes'):
                    # Wire order: 15 plane values, 16 children, packed axes.
                    # Reach's editor labels put "plane dimensions" on the first
                    # child and "child index15" on the axes word. Read by layout
                    # so those misleading labels cannot change the traversal.
                    values = [field.value for field in node.fields()]
                    if len(values) != 32:
                        return None
                    supernodes.append((tuple(values[:15]), tuple(map(int, values[15:31])),
                                       int(values[31])))
                clusters = [int(self.value(leaf, 'cluster'))
                            for leaf in self.block(self.tag.root(), 'leaves')]
                vertices = [tuple(self.value(vertex, 'point').to_array())
                            for vertex in self.block(bsp, 'vertices')]
                if not vertices or not clusters or len(clusters) != len(self.block(bsp, 'leaves')):
                    return None
                bounds = [(min(p[i] for p in vertices) - 1, max(p[i] for p in vertices) + 1)
                          for i in range(3)]
                return dict(planes=planes, nodes=nodes, supernodes=supernodes,
                            clusters=clusters, bounds=bounds)
        return None

    def structure_collision(self) -> StructureBspCollision | None:
        """Read the first standard or large structure collision BSP natively."""
        collision = None
        large = False
        for raw_items in self._raw_resource_items():
            for field_name, is_large in (('collision bsp', False),
                                         ('large collision bsp', True)):
                field = raw_items.field(field_name)
                if field is None:
                    continue
                block = field.as_block()
                if block is None:
                    raise TypeError(f'{self.path}: {field_name} is not a block')
                if len(block):
                    collision, large = block[0], is_large
                    break
            if collision is not None:
                break
        if collision is None:
            return None

        return self._collision_bsp(
            collision, large=large, label='structure collision')

    def surface_triangle_mappings(self) -> list[StructureBspSurfaceMapping]:
        root = self.tag.root()
        surfaces_field = root.field('large structure surfaces')
        mappings_field = root.field('structure surface to triangle mapping')
        if surfaces_field is None or mappings_field is None:
            return []
        surfaces = surfaces_field.as_block()
        mappings = mappings_field.as_block()
        if surfaces is None or mappings is None:
            raise TypeError(f'{self.path}: structure surface mappings are not blocks')
        packed_values: list[int] = []
        direct_values: list[tuple[int, int]] = []
        for element in mappings:
            packed = element.field('manual byteswarp1')
            if packed is not None:
                packed_values.append(int(packed.value))
            else:
                direct_values.append((
                    int(self.value(element, 'triangle_index')),
                    int(self.value(element, 'section_index')),
                ))
        value_count = len(packed_values) or len(direct_values)
        records = []
        for index, surface in enumerate(surfaces):
            first = int(self.value(
                surface, 'first_structure_surface_to_triangle_mapping_index'))
            count = int(self.value(
                surface, 'structure_surface_to_triangle_mapping_count'))
            if first < 0 or count < 0 or first + count > value_count:
                raise ValueError(
                    f'{self.path}: structure surface {index} has an invalid triangle mapping range')
            records.append(StructureBspSurfaceMapping(
                index,
                tuple(packed_values[first:first + count]),
                tuple(direct_values[first:first + count]),
            ))
        return records

    def cluster_mesh_indices(self) -> list[int]:
        field = self.tag.root().field('clusters')
        if field is None:
            return []
        clusters = field.as_block()
        if clusters is None:
            raise TypeError(f'{self.path}: clusters is not a block')
        return [int(self.value(element, 'mesh index')) for element in clusters]

    def instances(self) -> list[StructureBspInstance]:
        """Detach instance placement and policy data from the tag document."""
        field = self.tag.root().field('instanced geometry instances')
        if field is None:
            return []
        block = field.as_block()
        if block is None:
            raise TypeError(f'{self.path}: instanced geometry instances is not a block')

        def optional_value(element: blam_tags.TagStruct, name: str, default):
            value_field = element.field(name)
            return default if value_field is None else value_field.value

        def optional_enum(element: blam_tags.TagStruct, name: str,
                          options: tuple[str, ...], default: int) -> int:
            value_field = element.field(name)
            if value_field is None:
                return default
            return enum_index(value_field.value, options)

        lightmapping_options = (
            ('per-pixel seperate', 'per-vertex', 'single-probe', 'per-pixel shared')
            if self.game in {'halo3', 'halo3odst'} else
            ('per-pixel shared', 'per-vertex', 'single-probe', 'exclude',
             'per-pixel ao', 'per-vertex ao')
        )
        imposter_options = (
            ('polygon default', 'polygon high', 'cards medium', 'cards high',
             'none', 'rainbow box (runtime only)') if self.corinth else
            ('polygon default', 'polygon high', 'cards medium', 'cards high',
             'none', 'never')
        )
        records = []
        for index, element in enumerate(block):
            flags = self.required_field(element, 'flags')
            vectors = {
                name: tuple(cast('blam_tags.RealVector3d', self.value(element, name)).to_array())
                for name in ('forward', 'left', 'up')
            }
            position = cast(
                'blam_tags.RealPoint3d', self.value(element, 'position'))
            records.append(StructureBspInstance(
                index=index,
                definition_index=int(self.value(element, 'instance definition')),
                scale=float(self.value(element, 'scale')),
                position=tuple(position.to_array()),
                not_in_lightprobes=flags.get_flag('not in lightprobes'),
                render_only=flags.get_flag('render only'),
                not_block_aoe=flags.get_flag('does not block aoe damage'),
                decal=flags.get_flag('decal spacing'),
                imposter_transition=float(optional_value(
                    element, 'imposter transition complete distance', 0.0)),
                pathfinding=optional_enum(
                    element, 'pathfinding policy', ('cut-out', 'static', 'none'), 0),
                lightmapping=optional_enum(
                    element, 'lightmapping policy', lightmapping_options, 0),
                imposter=optional_enum(
                    element, 'imposter policy', imposter_options, 4),
                lightmap_resolution=float(optional_value(
                    element, 'lightmap resolution scale', 1.0)),
                name=str(optional_value(element, 'name', f'instance_{index}')),
                remove_from_shadow=(self.corinth and
                                    flags.get_flag('remove from shadow geometry')),
                cinema_type=(1 if self.corinth and flags.get_flag('cinema only')
                             else 2 if self.corinth and flags.get_flag('exclude from cinema')
                             else 0),
                imposter_brightness=float(optional_value(
                    element, 'imposter brightness', 0.0)),
                disallow_lighting_samples=(self.corinth and
                                           flags.get_flag('disallow object lighting samples')),
                streaming=optional_enum(
                    element, 'streaming priority', ('default', 'higher', 'highest'), 0),
                world_bound_sphere_radius=float(optional_value(
                    element, 'world bounding sphere radius', 0.0)),
                **vectors,
            ))
        return records

    def instance_definitions(self) -> list[StructureBspInstanceDefinition]:
        """Detach BSP instance-definition metadata; render meshes remain resources."""
        definitions = None
        for raw_items in self._raw_resource_items():
            field = raw_items.field('instanced geometries definitions')
            if field is None:
                continue
            definitions = field.as_block()
            if definitions is None:
                raise TypeError(
                    f'{self.path}: instanced geometries definitions is not a block')
            break
        if definitions is None:
            return []

        records = []
        for index, element in enumerate(definitions):
            collision_field = element.field('collision info')
            collision_struct = (None if collision_field is None
                                else collision_field.as_struct())
            collision = None
            if collision_struct is not None and len(self.block(collision_struct, 'surfaces')):
                collision = self._collision_bsp(
                    collision_struct, large=False,
                    label=f'instance definition {index} collision')

            mapping_surfaces_field = element.field('surfaces')
            mapping_values_field = element.field('surface to triangle mapping')
            mappings: list[StructureBspSurfaceMapping] = []
            if mapping_surfaces_field is not None and mapping_values_field is not None:
                mapping_surfaces = mapping_surfaces_field.as_block()
                mapping_values = mapping_values_field.as_block()
                if mapping_surfaces is None or mapping_values is None:
                    raise TypeError(
                        f'{self.path}: instance definition mappings are not blocks')
                packed_values = []
                direct_values = []
                for value in mapping_values:
                    packed = value.field('manual byteswarp1')
                    if packed is not None:
                        packed_values.append(int(packed.value))
                    else:
                        direct_values.append((
                            int(self.value(value, 'triangle_index')),
                            int(self.value(value, 'section_index')),
                        ))
                for surface_index, surface in enumerate(mapping_surfaces):
                    first = int(self.value(
                        surface, 'first_structure_surface_to_triangle_mapping_index'))
                    count = int(self.value(
                        surface, 'structure_surface_to_triangle_mapping_count'))
                    value_count = len(packed_values) or len(direct_values)
                    if first < 0 or count < 0 or first + count > value_count:
                        raise ValueError(
                            f'{self.path}: instance definition {index} surface '
                            f'{surface_index} has an invalid triangle mapping range')
                    mappings.append(StructureBspSurfaceMapping(
                        surface_index,
                        tuple(packed_values[first:first + count]),
                        tuple(direct_values[first:first + count]),
                    ))

            render_bsp_field = element.field('render bsp')
            render_bsp = None if render_bsp_field is None else render_bsp_field.as_block()
            collision_is_proxy = collision is not None and (
                not mappings or (render_bsp is not None and len(render_bsp) > 0))

            cookie_cutter = None
            cookie_field = element.field('poopie cutter collision')
            cookie_struct = None if cookie_field is None else cookie_field.as_struct()
            if cookie_struct is not None and len(self.block(cookie_struct, 'surfaces')):
                cookie_cutter = self._collision_bsp(
                    cookie_struct, large=False,
                    label=f'instance definition {index} cookie cutter')

            physics: list[StructureBspPhysicsPolyhedron] = []
            polyhedra_field = element.field('polyhedra_with_materials')
            vectors_field = element.field('polyhedron four vectors')
            if polyhedra_field is not None and vectors_field is not None:
                polyhedra = polyhedra_field.as_block()
                vectors = vectors_field.as_block()
                if polyhedra is None or vectors is None:
                    raise TypeError(
                        f'{self.path}: instance definition physics is not stored in blocks')
                vector_offset = 0
                for polyhedron in polyhedra:
                    shape = self.required_field(polyhedron, 'polyhedron').as_struct()
                    if shape is None:
                        raise TypeError(f'{self.path}: instance polyhedron is not a struct')
                    vector_count = int(self.value(shape, 'four vectors size'))
                    if vector_count < 0 or vector_offset + vector_count > len(vectors):
                        raise ValueError(
                            f'{self.path}: instance definition {index} has invalid physics vectors')
                    vertices = []
                    for vector_index in range(vector_offset, vector_offset + vector_count):
                        vector = vectors[vector_index]
                        x = tuple(cast('blam_tags.RealVector3d',
                                       self.value(vector, 'four vectors x')).to_array())
                        y = tuple(cast('blam_tags.RealVector3d',
                                       self.value(vector, 'four vectors y')).to_array())
                        z = tuple(cast('blam_tags.RealVector3d',
                                       self.value(vector, 'four vectors z')).to_array())
                        vertices.extend((x[i], y[i], z[i]) for i in range(3))
                        vertices.append((
                            float(self.value(vector, 'havok w four vectors x')),
                            float(self.value(vector, 'havok w four vectors y')),
                            float(self.value(vector, 'havok w four vectors z')),
                        ))
                    vector_offset += vector_count
                    convex = self.required_field(shape, 'polyhedron shape').as_struct()
                    if convex is None:
                        raise TypeError(f'{self.path}: instance convex shape is not a struct')
                    physics.append(StructureBspPhysicsPolyhedron(
                        material_index=int(self.value(polyhedron, 'material index')),
                        radius=float(self.value(convex, 'radius')),
                        vertices=tuple(vertices),
                    ))

            records.append(StructureBspInstanceDefinition(
                index=index,
                mesh_index=int(self.value(element, 'mesh index')),
                compression_index=int(self.value(element, 'compression index')),
                collision=collision,
                collision_is_proxy=collision_is_proxy,
                surface_mappings=tuple(mappings),
                cookie_cutter=cookie_cutter,
                physics=tuple(physics),
            ))
        return records

    def render_meshes(
            self, definitions: list[StructureBspInstanceDefinition]
            ) -> list[StructureBspRenderMesh]:
        """Decode renderer-ready BSP meshes through the blam-tags core."""
        geometry = self.required_field(self.tag.root(), 'render geometry').as_struct()
        if geometry is None:
            raise TypeError(f'{self.path}: render geometry is not a struct')
        mesh_count = len(self.block(geometry, 'meshes'))
        compression_indices = [-1] * mesh_count
        for definition in definitions:
            if definition.mesh_index < 0 or definition.mesh_index >= mesh_count:
                raise ValueError(
                    f'{self.path}: instance definition {definition.index} mesh '
                    f'index {definition.mesh_index} is out of range')
            previous = compression_indices[definition.mesh_index]
            if previous not in {-1, definition.compression_index}:
                raise ValueError(
                    f'{self.path}: mesh {definition.mesh_index} uses conflicting '
                    'compression bounds')
            compression_indices[definition.mesh_index] = definition.compression_index

        decoded = self.tag.sbsp_render_meshes(compression_indices)
        if len(decoded) != mesh_count:
            raise ValueError(
                f'{self.path}: decoded {len(decoded)} of {mesh_count} render meshes')
        records = []
        for index, mesh in enumerate(decoded):
            parts = tuple(StructureBspRenderPart(
                material_index=int(part['material_index']),
                index_start=int(part['index_start']),
                index_count=int(part['index_count']),
                part_type=int(part['part_type']),
            ) for part in cast(list[dict[str, object]], mesh['parts']))
            water_value = mesh['water_data']
            water = None
            if water_value is not None:
                water_data = cast(dict[str, object], water_value)
                water = StructureBspRenderWater(
                    triangles=tuple(tuple((int(point[0]), int(point[1]))
                                          for point in triangle)
                                    for triangle in cast(list, water_data['triangles'])),
                    base_texcoords=tuple(tuple(float(value) for value in vertex[2])
                                         for vertex in cast(list, water_data['vertices'])),
                    part_indices=tuple(int(part[0])
                                       for part in cast(list, water_data['parts'])),
                )
            records.append(StructureBspRenderMesh(
                index=index,
                positions=tuple(tuple(map(float, value)) for value in mesh['positions']),
                texcoords=tuple(tuple(map(float, value)) for value in mesh['texcoords']),
                normals=tuple(tuple(map(float, value)) for value in mesh['normals']),
                node_indices=tuple(tuple(map(int, value)) for value in mesh['node_indices']),
                node_weights=tuple(tuple(map(float, value)) for value in mesh['node_weights']),
                lightmap_texcoords=tuple(tuple(map(float, value))
                                         for value in mesh['lightmap_texcoords']),
                vertex_colors=tuple(tuple(map(float, value))
                                    for value in mesh['vertex_colors']),
                indices=tuple(map(int, mesh['indices'])),
                rigid_node_index=(-1 if mesh['rigid_node_index'] is None
                                  else int(mesh['rigid_node_index'])),
                parts=parts,
                water=water,
            ))
        return records

    def havok_geometry(self) -> list[StructureBspHavokGeometry]:
        """Detach serialized H4/H2AMP structure collision from tag handles."""
        records: list[StructureBspHavokGeometry] = []
        for raw_items in self._raw_resource_items():
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
                    bounds.append(None if field is None else tuple(
                        cast('blam_tags.RealPoint3d', field.value).to_array()))
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

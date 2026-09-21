"""Native render-model metadata and renderer-ready geometry."""

from dataclasses import dataclass
from typing import cast

from .backend import TagDocument
from .blender import BlenderTag
from .prefab import (ScenarioStructureBspMetadataTag, StructureBspCompressionBounds,
                     StructureBspRenderMaterial, StructureBspRenderMesh,
                     StructureBspRenderPart, StructureBspRenderWater)


@dataclass(frozen=True)
class RenderModelNode:
    index: int
    name: str
    parent_index: int
    translation: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    inverse_forward: tuple[float, float, float]
    inverse_left: tuple[float, float, float]
    inverse_up: tuple[float, float, float]
    inverse_position: tuple[float, float, float]
    inverse_scale: float


@dataclass(frozen=True)
class RenderModelPermutation:
    index: int
    name: str
    mesh_index: int
    mesh_count: int
    clone_name: str
    instance_indices: tuple[int, ...]


@dataclass(frozen=True)
class RenderModelRegion:
    index: int
    name: str
    permutations: tuple[RenderModelPermutation, ...]


@dataclass(frozen=True)
class RenderModelInstancePlacement:
    index: int
    name: str
    node_index: int
    scale: float
    forward: tuple[float, float, float]
    left: tuple[float, float, float]
    up: tuple[float, float, float]
    position: tuple[float, float, float]


@dataclass(frozen=True)
class RenderModelMarker:
    region_index: int
    permutation_index: int
    node_index: int
    translation: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    scale: float
    direction: tuple[float, float, float]


@dataclass(frozen=True)
class RenderModelMarkerGroup:
    index: int
    name: str
    markers: tuple[RenderModelMarker, ...]


@dataclass(frozen=True)
class RenderModelSkyLight:
    direction: tuple[float, float, float]
    intensity: tuple[float, float, float]
    solid_angle: float


@dataclass(frozen=True)
class RenderModelSkyData:
    is_sky: bool
    sun_as_vmf_light: bool
    lights: tuple[RenderModelSkyLight, ...]
    sun: tuple[float, ...]
    sun_bounce_scale: float
    skylight_bounce_scale: float


class RenderModelMetadataTag(BlenderTag, TagDocument):
    tag_ext = 'render_model'

    def get_nodes(self):
        return [self.value(element, 'name')
                for element in self.block(self.tag.root(), 'nodes')]

    def get_regions(self):
        return [self.value(element, 'name')
                for element in self.block(self.tag.root(), 'regions')]

    def get_permutations(self, region=''):
        regions = self.block(self.tag.root(), 'regions')
        names = []
        for element in regions:
            if region and self.value(element, 'name') != region:
                continue
            names.extend(self.value(permutation, 'name')
                         for permutation in self.block(element, 'permutations'))
            if region:
                break
        return list(dict.fromkeys(names))

    def get_markers(self):
        return [self.value(element, 'name')
                for element in self.block(self.tag.root(), 'marker groups')]

    def set_structure_meta_ref(self, meta_path):
        if not self.corinth:
            raise ValueError(
                'Structure metadata references only exist in H4/H2AMP render models')
        if not self.path_exists(self.reference_from_path(meta_path)):
            raise FileNotFoundError(meta_path)
        self.set_reference(self.tag.root(), 'structure meta data', meta_path)

    def first_render_method(self):
        materials = self.block(self.tag.root(), 'materials')
        if not len(materials):
            return None
        return self.reference(materials[0], 'render method')

    @staticmethod
    def _vector(value) -> tuple[float, ...]:
        return tuple(float(component) for component in value.to_array())

    def nodes(self) -> list[RenderModelNode]:
        elements = list(self.block(self.tag.root(), 'nodes'))
        return [RenderModelNode(
            index=index,
            name=str(self.value(element, 'name')),
            parent_index=int(self.value(element, 'parent node')),
            translation=cast(tuple[float, float, float], self._vector(
                self.value(element, 'default translation'))),
            rotation=cast(tuple[float, float, float, float], self._vector(
                self.value(element, 'default rotation'))),
            inverse_forward=cast(tuple[float, float, float], self._vector(
                self.value(element, 'inverse forward'))),
            inverse_left=cast(tuple[float, float, float], self._vector(
                self.value(element, 'inverse left'))),
            inverse_up=cast(tuple[float, float, float], self._vector(
                self.value(element, 'inverse up'))),
            inverse_position=cast(tuple[float, float, float], self._vector(
                self.value(element, 'inverse position'))),
            inverse_scale=float(self.value(element, 'inverse scale')),
        ) for index, element in enumerate(elements)]

    def regions(self) -> list[RenderModelRegion]:
        records = []
        for region_index, element in enumerate(self.block(self.tag.root(), 'regions')):
            permutations = []
            for permutation_index, permutation in enumerate(
                    self.block(element, 'permutations')):
                instance_indices = []
                for word, field_name in enumerate((
                        'instance mask 0-31', 'instance mask 32-63',
                        'instance mask 64-95', 'instance mask 96-127')):
                    field = permutation.field(field_name)
                    if field is None:
                        continue
                    options = field.options()
                    if options is None:
                        raise TypeError(f'{self.path}: {field_name} is not flags')
                    instance_indices.extend(
                        word * 32 + bit for bit, _name, enabled in options.flags
                        if enabled)
                clone = permutation.field('clone name')
                permutations.append(RenderModelPermutation(
                    index=permutation_index,
                    name=str(self.value(permutation, 'name')),
                    mesh_index=int(self.value(permutation, 'mesh index')),
                    mesh_count=int(self.value(permutation, 'mesh count')),
                    clone_name='' if clone is None else str(clone.value),
                    instance_indices=tuple(instance_indices),
                ))
            records.append(RenderModelRegion(
                index=region_index,
                name=str(self.value(element, 'name')),
                permutations=tuple(permutations),
            ))
        return records

    def instance_placements(self) -> list[RenderModelInstancePlacement]:
        field = self.tag.root().field('instance placements')
        if field is None:
            return []
        block = field.as_block()
        if block is None:
            raise TypeError(f'{self.path}: instance placements is not a block')
        return [RenderModelInstancePlacement(
            index=index,
            name=str(self.value(element, 'name')),
            node_index=int(self.value(element, 'node_index')),
            scale=float(self.value(element, 'scale')),
            forward=cast(tuple[float, float, float], self._vector(
                self.value(element, 'forward'))),
            left=cast(tuple[float, float, float], self._vector(
                self.value(element, 'left'))),
            up=cast(tuple[float, float, float], self._vector(
                self.value(element, 'up'))),
            position=cast(tuple[float, float, float], self._vector(
                self.value(element, 'position'))),
        ) for index, element in enumerate(block)]

    def marker_groups(self) -> list[RenderModelMarkerGroup]:
        records = []
        for group_index, element in enumerate(self.block(self.tag.root(), 'marker groups')):
            markers = []
            for marker in self.block(element, 'markers'):
                direction = marker.field('direction')
                markers.append(RenderModelMarker(
                    region_index=int(self.value(marker, 'region index')),
                    permutation_index=int(self.value(marker, 'permutation index')),
                    node_index=int(self.value(marker, 'node index')),
                    translation=cast(tuple[float, float, float], self._vector(
                        self.value(marker, 'translation'))),
                    rotation=cast(tuple[float, float, float, float], self._vector(
                        self.value(marker, 'rotation'))),
                    scale=float(self.value(marker, 'scale')),
                    direction=((0.0, 0.0, 0.0) if direction is None else
                               cast(tuple[float, float, float], self._vector(
                                   direction.value))),
                ))
            records.append(RenderModelMarkerGroup(
                index=group_index,
                name=str(self.value(element, 'name')),
                markers=tuple(markers),
            ))
        return records

    def instance_mesh_index(self) -> int:
        field = self.tag.root().field('instance mesh index')
        return -1 if field is None else int(field.value)

    def compression_bounds(self) -> list[StructureBspCompressionBounds]:
        return ScenarioStructureBspMetadataTag.compression_bounds(self)

    def render_materials(self) -> list[StructureBspRenderMaterial]:
        return ScenarioStructureBspMetadataTag.render_materials(self)

    def sky_data(self) -> RenderModelSkyData:
        root = self.tag.root()
        flags = self.required_field(root, 'flags')
        light_field = root.field('sky lights')
        lights = []
        if light_field is not None:
            block = light_field.as_block()
            if block is None:
                raise TypeError(f'{self.path}: sky lights is not a block')
            lights = [RenderModelSkyLight(
                direction=cast(tuple[float, float, float], self._vector(
                    self.value(element, 'direction'))),
                intensity=cast(tuple[float, float, float], self._vector(
                    self.value(element, 'intensity'))),
                solid_angle=float(self.value(element, 'solid angle')),
            ) for element in block]

        sun = ()
        sun_field = root.field('sun')
        if sun_field is not None:
            array = sun_field.as_array()
            if array is None:
                raise TypeError(f'{self.path}: sun is not an array')
            sun = tuple(float(element.fields()[0].value) for element in array)

        def optional_real(name: str, default: float) -> float:
            field = root.field(name)
            return default if field is None else float(field.value)

        return RenderModelSkyData(
            is_sky=flags.get_flag('this is supposed to be a sky'),
            sun_as_vmf_light=flags.get_flag('sun as vmf light'),
            lights=tuple(lights),
            sun=sun,
            sun_bounce_scale=optional_real('sun 1st bounce scaler', 1.0),
            skylight_bounce_scale=optional_real('sky light 1st bounce scaler', 1.0),
        )

    def render_meshes(self) -> list[StructureBspRenderMesh]:
        """Decode every model mesh through blam-tags' cross-game decoder."""
        decoded = self.tag.render_model_meshes()
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

    def insert_empty_region_perms(self, empty_region_perms: dict[str, set]):
        print("\nAdding Empty Region Permutations")
        regions = self.block(self.tag.root(), 'regions')
        for region_element in regions:
            region = self.value(region_element, 'name')
            permutations = empty_region_perms.get(region)
            if permutations is None:
                continue
            block = self.block(region_element, 'permutations')
            existing = {self.value(element, 'name') for element in block}
            print(f"\n--- Adding empty permutations to existing region {region}")
            for permutation in sorted(permutations.difference(existing)):
                element = block[block.add()]
                self.required_field(element, 'name').set(permutation)
                self.required_field(element, 'mesh index').set(-1)
                print(f"\tAdded permutation {permutation}")
                self.tag_has_changes = True
            empty_region_perms.pop(region)

        for region, permutations in empty_region_perms.items():
            region_element = regions[regions.add()]
            self.required_field(region_element, 'name').set(region)
            print(f"\n--- Created new empty region {region}")
            block = self.block(region_element, 'permutations')
            for permutation in sorted(permutations):
                element = block[block.add()]
                self.required_field(element, 'name').set(permutation)
                self.required_field(element, 'mesh index').set(-1)
                print(f"\tAdded permutation {permutation}")
            self.tag_has_changes = True

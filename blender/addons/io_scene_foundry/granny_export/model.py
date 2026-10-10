"""Owned, backend-independent export records. No native pointers or file layout.

Geometry buffers retain separate attributes in authored coordinates. Object
placement, reflection and destination basis are explicit pending operations;
they will be applied at the geometry/transform checkpoints, not here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import struct


class ExportDataError(ValueError):
    pass


IDENTITY = ((1., 0., 0., 0.), (0., 1., 0., 0.), (0., 0., 1., 0.), (0., 0., 0., 1.))


class Scalar(str, Enum):
    REAL32 = 'real32'
    INT32 = 'int32'
    UINT8 = 'uint8'
    NORMAL_UINT8 = 'normal_uint8'
    UINT16 = 'uint16'

    @property
    def size(self):
        return 1 if self in (Scalar.UINT8, Scalar.NORMAL_UINT8) else 2 if self is Scalar.UINT16 else 4

    @property
    def format(self):
        return 'f' if self is Scalar.REAL32 else 'i' if self is Scalar.INT32 else 'H' if self is Scalar.UINT16 else 'B'


@dataclass(frozen=True, slots=True)
class Buffer:
    scalar: Scalar
    width: int
    count: int
    data: bytes

    def __post_init__(self):
        object.__setattr__(self, 'data', bytes(self.data))
        if self.width < 1 or self.count < 0 or len(self.data) != self.count * self.width * self.scalar.size:
            raise ExportDataError('Numeric buffer shape does not match its owned bytes')

    def rows(self):
        """Convenience inspection, not interleaved vertex or file serialization."""
        return tuple(struct.iter_unpack('<' + self.scalar.format * self.width, self.data))


class ValueKind(str, Enum):
    INT32 = 'int32'
    REAL32 = 'real32'
    STRING = 'string'
    REAL32_ARRAY = 'real32_array'
    INT32_ARRAY = 'int32_array'
    REFERENCE = 'reference'
    RECORD_ARRAY = 'record_array'
    VARIANT_ARRAY = 'variant_array'


@dataclass(frozen=True, slots=True)
class Member:
    name: str
    kind: ValueKind
    value: object


@dataclass(frozen=True, slots=True)
class Metadata:
    # A sequence deliberately preserves repeated field names and order.
    members: tuple[Member, ...] = ()


@dataclass(frozen=True, slots=True)
class Attribute:
    name: str
    component_name: str
    buffer: Buffer


@dataclass(frozen=True, slots=True, eq=False)
class VertexData:
    attributes: tuple[Attribute, ...]
    placement: tuple = IDENTITY
    reflect_y: bool = False
    data_is_deltas: bool = False

    def __post_init__(self):
        if not self.attributes or len({a.buffer.count for a in self.attributes}) != 1:
            raise ExportDataError('Vertex attributes must have a common vertex count')
        if len({a.name for a in self.attributes}) != len(self.attributes):
            raise ExportDataError('Vertex declaration contains duplicate field names')

    @property
    def count(self):
        return self.attributes[0].buffer.count


@dataclass(frozen=True, slots=True)
class TriangleAnnotation:
    name: str
    member_name: str
    buffer: Buffer
    map_from_tri: bool = True
    indices: Buffer | None = None


@dataclass(frozen=True, slots=True)
class MaterialGroup:
    material_index: int
    first_triangle: int
    triangle_count: int


@dataclass(frozen=True, slots=True, eq=False)
class Topology:
    indices: Buffer
    groups: tuple[MaterialGroup, ...] = ()
    annotations: tuple[TriangleAnnotation, ...] = ()
    # Keep native negative-scale inversion distinct from the mirror helper's
    # permutation, until the geometry checkpoint applies them.
    invert_winding: bool = False
    reflect_winding: bool = False

    def __post_init__(self):
        if self.indices.width != 1 or self.indices.scalar not in (Scalar.INT32, Scalar.UINT16) or self.indices.count % 3:
            raise ExportDataError('Triangle topology requires triples of int32 or uint16 indices')
        if any(a.buffer.count != self.indices.count // 3 for a in self.annotations if a.indices is None):
            raise ExportDataError('Triangle annotation count does not match topology')


@dataclass(frozen=True, slots=True)
class TextureImage:
    width: int
    height: int
    stride: int
    rgba: bytes

    def __post_init__(self):
        object.__setattr__(self, 'rgba', bytes(self.rgba))
        if self.width <= 0 or self.height <= 0 or self.stride < self.width * 4 or len(self.rgba) != self.stride * self.height:
            raise ExportDataError('RGBA image dimensions do not match its owned bytes')


@dataclass(frozen=True, slots=True, eq=False)
class Texture:
    name: str
    images: tuple[TextureImage, ...] = ()
    requested_encoding: str = 'rgba'


@dataclass(frozen=True, slots=True)
class MaterialMap:
    usage: str
    material: Material


@dataclass(slots=True, eq=False)
class Material:
    name: str
    metadata: Metadata = Metadata()
    texture: Texture | None = None
    # Material maps can reference the material itself. Graph references are
    # assigned after construction; their numeric/string payloads remain owned.
    maps: tuple[MaterialMap, ...] = ()


@dataclass(frozen=True, slots=True)
class Bone:
    name: str
    parent_index: int
    local_matrix: tuple = IDENTITY
    world_matrix: tuple = IDENTITY
    lod_error: float = 0.
    metadata: Metadata = Metadata()


@dataclass(frozen=True, slots=True, eq=False)
class Skeleton:
    name: str
    bones: tuple[Bone, ...]
    lod_type: int = 0
    metadata: Metadata = Metadata()

    def __post_init__(self):
        for index, bone in enumerate(self.bones):
            if not -1 <= bone.parent_index < len(self.bones) or bone.parent_index == index:
                raise ExportDataError(f'Invalid parent for bone {bone.name}')
        for index, bone in enumerate(self.bones):
            visited, parent = {index}, bone.parent_index
            while parent != -1:
                if parent in visited:
                    raise ExportDataError('Skeleton hierarchy contains a cycle')
                visited.add(parent)
                parent = self.bones[parent].parent_index


@dataclass(frozen=True, slots=True)
class MorphTarget:
    name: str | None
    vertex_data: VertexData


@dataclass(frozen=True, slots=True, eq=False)
class Mesh:
    name: str
    vertices: VertexData
    topology: Topology
    materials: tuple[Material, ...] = ()
    bone_bindings: tuple[str, ...] = ()
    metadata: Metadata = Metadata()
    morph_targets: tuple[MorphTarget, ...] = ()


@dataclass(frozen=True, slots=True, eq=False)
class Model:
    name: str
    skeleton: Skeleton
    meshes: tuple[Mesh | None, ...] = ()
    placement: tuple = IDENTITY
    metadata: Metadata = Metadata()


@dataclass(frozen=True, slots=True)
class SampledCurve:
    controls: Buffer

    def __post_init__(self):
        if self.controls.scalar is not Scalar.REAL32 or self.controls.count < 1:
            raise ExportDataError('Sampled curves require nonempty float32 controls')


@dataclass(frozen=True, slots=True)
class TransformTrack:
    name: str
    position: SampledCurve
    orientation: SampledCurve
    scale_shear: SampledCurve
    flags: int = 0


@dataclass(frozen=True, slots=True)
class VectorTrack:
    name: str
    bone_name: str
    curve: SampledCurve
    # None records unresolved Granny key generation; it is never a guessed hash.
    track_key: int | None = None


@dataclass(frozen=True, slots=True, eq=False)
class TrackGroup:
    name: str
    transforms: tuple[TransformTrack, ...] = ()
    vectors: tuple[VectorTrack, ...] = ()
    flags: int = 2
    placement: tuple = IDENTITY
    metadata: Metadata = Metadata()


@dataclass(frozen=True, slots=True, eq=False)
class Animation:
    name: str
    duration: float
    time_step: float
    track_groups: tuple[TrackGroup, ...]
    oversampling: float = 1.
    default_loop_count: int = 0
    flags: int = 0
    metadata: Metadata = Metadata()


@dataclass(frozen=True, slots=True)
class ArtToolInfo:
    name: str
    major: int
    minor: int
    pointer_size: int
    units_per_meter: float
    origin: tuple = (0., 0., 0.)
    right: tuple = (0., -1., 0.)
    up: tuple = (0., 0., 1.)
    back: tuple = (-1., 0., 0.)


@dataclass(frozen=True, slots=True)
class ExporterInfo:
    name: str
    version: tuple[int, int, int]
    customization: int = 0


@dataclass(frozen=True, slots=True)
class CoordinateConversion:
    target_units_per_meter: float
    right: tuple
    up: tuple
    back: tuple
    reflect_y: bool = False
    # Source geometry, skeleton matrices and animation samples remain authored.
    state: str = 'authored'


@dataclass(frozen=True, slots=True)
class ExportFile:
    file_name: str
    art_tool: ArtToolInfo
    exporter: ExporterInfo
    conversion: CoordinateConversion
    materials: tuple[Material, ...] = ()
    textures: tuple[Texture, ...] = ()
    skeletons: tuple[Skeleton, ...] = ()
    vertex_data: tuple[VertexData, ...] = ()
    topologies: tuple[Topology, ...] = ()
    meshes: tuple[Mesh, ...] = ()
    models: tuple[Model, ...] = ()
    track_groups: tuple[TrackGroup, ...] = ()
    animations: tuple[Animation, ...] = ()
    metadata: Metadata = field(default_factory=Metadata)

    def reachable_materials(self):
        # Root arrays intentionally need not contain every reachable object.
        pending = list(self.materials)
        for mesh in self.meshes:
            pending.extend(mesh.materials)
        for model in self.models:
            for mesh in model.meshes:
                if mesh is not None:
                    pending.extend(mesh.materials)
        found = {}
        for material in pending:
            if material not in found:
                found[material] = None
                pending.extend(mapping.material for mapping in material.maps)
        return tuple(found)

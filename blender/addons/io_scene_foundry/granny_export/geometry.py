"""Independent static/skinned geometry serialization and buffer validation."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import struct

from .binary import BinaryWriteError
from .model import IDENTITY, Scalar, VertexData
from . import transforms as _transforms


@dataclass(frozen=True, slots=True, eq=False)
class _Payload:
    value: object
    role: str


def interleave(data):
    """Combine column buffers using strided byte copies, without vertex objects."""
    stride = sum(attribute.buffer.width * attribute.buffer.scalar.size for attribute in data.attributes)
    encoded = bytearray(stride * data.count)
    destination, offset = memoryview(encoded), 0
    for attribute in data.attributes:
        source = memoryview(attribute.buffer.data)
        size = attribute.buffer.width * attribute.buffer.scalar.size
        for byte in range(size):
            destination[offset + byte::stride] = source[byte::size]
        offset += size
    return bytes(encoded)


def topology_indices(topology, *, basis_reversal=False):
    rows = list(struct.iter_unpack('<' + topology.indices.scalar.format * 3, topology.indices.data))
    if topology.invert_winding:
        rows = [(c, b, a) for a, b, c in rows]
    if topology.reflect_winding:
        rows = [(a, c, b) for a, b, c in rows]
    if basis_reversal:
        rows = [(c, b, a) for a, b, c in rows]
    return rows


def _has_finite_values(buffer):
    np = _transforms._numpy_module() if len(buffer.data) >= 128 else None
    if np is not None:
        values = np.frombuffer(buffer.data, dtype='<f4')
        return all(np.isfinite(values[start:start + 65536]).all() for start in range(0, len(values), 65536))
    return all(isfinite(value) for (value,) in struct.iter_unpack('<f', buffer.data))


def _index_range(buffer):
    np = _transforms._numpy_module() if len(buffer.data) >= 128 else None
    if np is not None and buffer.count:
        dtype = '<i4' if buffer.scalar is Scalar.INT32 else '<u2'
        values = np.frombuffer(buffer.data, dtype=dtype)
        return int(values.min()), int(values.max())
    minimum, maximum = None, None
    for (value,) in struct.iter_unpack('<' + buffer.scalar.format, buffer.data):
        minimum = value if minimum is None else min(minimum, value)
        maximum = value if maximum is None else max(maximum, value)
    return minimum, maximum


class GeometryValidation:
    """Successful checks belong to one file and retain immutable record owners."""
    def __init__(self):
        self._vertices, self._topologies, self._meshes = {}, {}, {}
        self._finite_buffers, self._index_buffers = {}, {}

    def finite(self, buffer):
        key = id(buffer)
        if key not in self._finite_buffers:
            self._finite_buffers[key] = (buffer, _has_finite_values(buffer))
        return self._finite_buffers[key][1]

    def index_range(self, buffer):
        key = id(buffer)
        if key not in self._index_buffers:
            self._index_buffers[key] = (buffer, _index_range(buffer))
        return self._index_buffers[key][1]

    def _check(self, value, checked, callback):
        if id(value) not in checked:
            callback(value, validation=self)
            checked[id(value)] = value

    def vertices(self, value):
        self._check(value, self._vertices, validate_vertices)

    def topology(self, value):
        self._check(value, self._topologies, validate_topology)

    def mesh(self, value):
        self._check(value, self._meshes, validate_mesh)


def validate_vertices(data, *, validation=None):
    fields = {attribute.name: attribute for attribute in data.attributes}
    position = fields.get('Position')
    if position is None or position.buffer.scalar is not Scalar.REAL32 or position.buffer.width != 3:
        raise BinaryWriteError('Geometry requires a three-component float32 Position attribute')
    finite = validation.finite if validation is not None else _has_finite_values
    if any(not finite(attribute.buffer) for attribute in data.attributes if attribute.buffer.scalar is Scalar.REAL32):
        raise BinaryWriteError('Geometry attributes must contain finite values')
    weights, indices = fields.get('BoneWeights'), fields.get('BoneIndices')
    if (weights is None) != (indices is None):
        raise BinaryWriteError('Skinning requires both BoneWeights and BoneIndices')
    if weights is not None and (weights.buffer.scalar is not Scalar.NORMAL_UINT8 or weights.buffer.width != 4
            or indices.buffer.scalar is not Scalar.UINT8 or indices.buffer.width != 4):
        raise BinaryWriteError('Foundry skinning requires four normalized byte weights and four byte indices')


def validate_topology(topology, *, validation=None):
    triangles = topology.indices.count // 3
    index_range = validation.index_range if validation is not None else _index_range
    finite = validation.finite if validation is not None else _has_finite_values
    minimum, _ = index_range(topology.indices)
    if minimum is not None and minimum < 0:
        raise BinaryWriteError('Triangle indices cannot be negative')
    for group in topology.groups:
        if (group.material_index < 0 or group.first_triangle < 0 or group.triangle_count < 0
                or group.first_triangle + group.triangle_count > triangles):
            raise BinaryWriteError('Material group is outside triangle topology')
    for annotation in topology.annotations:
        if annotation.buffer.scalar not in (Scalar.INT32, Scalar.REAL32):
            raise BinaryWriteError('Face annotations require int32 or float32 records')
        if annotation.buffer.scalar is Scalar.REAL32 and not finite(annotation.buffer):
            raise BinaryWriteError('Face annotation values must be finite')
        if annotation.indices is not None:
            remap = annotation.indices
            if remap.scalar is not Scalar.INT32 or remap.width != 1 or remap.count != triangles:
                raise BinaryWriteError('Annotation index map must contain one int32 index per triangle')
            low, high = index_range(remap)
            if low is not None and (low < 0 or high >= annotation.buffer.count):
                raise BinaryWriteError('Annotation index is outside its record array')


def validate_mesh(mesh, *, validation=None):
    (validation.vertices if validation is not None else validate_vertices)(mesh.vertices)
    (validation.topology if validation is not None else validate_topology)(mesh.topology)
    if mesh.vertices.data_is_deltas:
        raise BinaryWriteError('Primary mesh vertices cannot be delta buffers')
    for morph in mesh.morph_targets:
        (validation.vertices if validation is not None else validate_vertices)(morph.vertex_data)
        if morph.vertex_data.count != mesh.vertices.count:
            raise BinaryWriteError('Morph target count must match the primary vertex count')
    _, maximum = (validation.index_range if validation is not None else _index_range)(mesh.topology.indices)
    if maximum is not None and maximum >= mesh.vertices.count:
        raise BinaryWriteError('Triangle index is outside the vertex array')
    # Material-less meshes exist in real Foundry/Granny source files. Keep their
    # topology groups instead of inventing material bindings.
    if mesh.materials and any(group.material_index >= len(mesh.materials) for group in mesh.topology.groups):
        raise BinaryWriteError('Material group references an absent mesh binding')
    attributes = {attribute.name: attribute.buffer for attribute in mesh.vertices.attributes}
    if 'BoneWeights' in attributes:
        for weight, index in zip(attributes['BoneWeights'].data, attributes['BoneIndices'].data):
            if weight and index >= len(mesh.bone_bindings):
                raise BinaryWriteError('Weighted bone index is outside the mesh binding palette')


class GeometryEmitter:
    def __init__(self, emitter, properties, *, object_section=0, buffer_section=None, transforms=None, validation=None):
        self.emitter, self.properties = emitter, properties
        self.builder, self.registry = emitter.builder, emitter.registry
        self.object_section = object_section
        self.buffer_section = object_section if buffer_section is None else buffer_section
        self.transforms = transforms
        self.validation = validation if validation is not None else GeometryValidation()
        self._written = set()
        self._owners = {}

    def owner(self, value, role):
        key = (id(value), role)
        if key not in self._owners:
            self._owners[key] = _Payload(value, role)
        return self._owners[key]

    def offset(self, schema, field):
        return self.registry.layout(schema).field(field).offset

    def string(self, address, value):
        self.builder.reference(address, self.builder.string(value, section=self.emitter.string_section))

    def array(self, parent, schema, field, element_type, values, *, owner=None):
        offset = self.offset(schema, field)
        parent.pack(offset, '<i', len(values))
        result = self.emitter.reserve(element_type, owner=owner or self.owner(values, schema + '.' + field),
                                      count=len(values), section=self.object_section)
        if result is not None:
            self.builder.reference(parent.at(offset + 4), result.item(0))
        return result

    def numeric(self, data, role, *, schema=None):
        if data.count == 0:
            return None
        schema = schema or {Scalar.INT32: 'Int32', Scalar.UINT16: 'UInt16',
                            Scalar.REAL32: 'Real32', Scalar.UINT8: 'UInt8'}[data.scalar]
        result = self.emitter.reserve(schema, owner=self.owner(data, role), count=data.count * data.width,
                                      section=self.buffer_section)
        if result.block not in self._written:
            result.block.write(0, data.data)
            self._written.add(result.block)
        return result.item(0)

    def vertices(self, data):
        self.validation.vertices(data)
        if self.transforms is None and (data.placement != IDENTITY or data.reflect_y):
            raise BinaryWriteError('Pending geometry transforms require a TransformContext')
        header = self.emitter.reserve('VertexData', owner=data, section=self.object_section).block
        if header in self._written:
            return header.at()
        self._written.add(header)
        schema = self.registry.vertex(data)
        offset = self.offset('VertexData', 'Vertices')
        self.builder.reference(header.at(offset), self.emitter.emit(schema))
        header.pack(offset + 8, '<i', data.count)
        payload = self.emitter.reserve(schema, owner=self.owner(data, 'interleaved'), count=data.count,
                                       section=self.buffer_section)
        if payload is not None:
            if self.transforms is None:
                encoded = interleave(data)
            else:
                encoded = interleave(VertexData(self.transforms.vertices(data)))
            payload.block.write(0, encoded)
            self.builder.reference(header.at(offset + 12), payload.item(0))
        names = tuple(attribute.component_name for attribute in data.attributes)
        array = self.array(header, 'VertexData', 'VertexComponentNames', 'String', names, owner=self.owner(data, 'component_names'))
        if array is not None:
            for index, name in enumerate(names):
                self.string(array.item(index), name)
        return header.at()

    def topology(self, data):
        self.validation.topology(data)
        header = self.emitter.reserve('TriTopology', owner=data, section=self.object_section).block
        if header in self._written:
            return header.at()
        self._written.add(header)
        groups = self.array(header, 'TriTopology', 'Groups', 'TriMaterialGroup', data.groups)
        if groups is not None and groups.block not in self._written:
            self._written.add(groups.block)
            for index, group in enumerate(data.groups):
                groups.block.pack(index * groups.item_size, '<3i', group.material_index, group.first_triangle, group.triangle_count)
        field = 'Indices16' if data.indices.scalar is Scalar.UINT16 else 'Indices'
        offset = self.offset('TriTopology', field)
        header.pack(offset, '<i', data.indices.count)
        if data.indices.count:
            # The standard Indices16 declaration uses Int16; unsigned index
            # values preserve their exact bits without promotion or truncation.
            element = 'Int16' if field == 'Indices16' else 'Int32'
            indices = self.emitter.reserve(element, owner=self.owner(data, 'indices'), count=data.indices.count,
                                           section=self.buffer_section)
            basis_reversal = self.transforms is not None and self.transforms.reorder_winding
            if data.invert_winding or data.reflect_winding or basis_reversal:
                rows = topology_indices(data, basis_reversal=basis_reversal)
                indices.block.write(0, b''.join(struct.pack('<' + data.indices.scalar.format * 3, *row) for row in rows))
            else:
                indices.block.write(0, data.indices.data)
            self.builder.reference(header.at(offset + 4), indices.item(0))
        annotations = self.array(header, 'TriTopology', 'TriAnnotationSets', 'TriAnnotationSet', data.annotations)
        if annotations is not None and annotations.block not in self._written:
            self._written.add(annotations.block)
            for index, annotation in enumerate(data.annotations):
                start = index * annotations.item_size
                self.string(annotations.block.at(start + self.offset('TriAnnotationSet', 'Name')), annotation.name)
                offset = start + self.offset('TriAnnotationSet', 'TriAnnotations')
                schema = self.registry.annotation(annotation)
                self.builder.reference(annotations.block.at(offset), self.emitter.emit(schema))
                annotations.block.pack(offset + 8, '<i', annotation.buffer.count)
                values = self.emitter.reserve(schema, owner=self.owner(annotation.buffer, 'annotation.' + schema.name),
                    count=annotation.buffer.count, section=self.buffer_section)
                if values is not None:
                    values.block.write(0, annotation.buffer.data)
                    self.builder.reference(annotations.block.at(offset + 12), values.item(0))
                annotations.block.pack(start + self.offset('TriAnnotationSet', 'IndicesMapFromTriToAnnotation'), '<i', int(annotation.map_from_tri))
                if annotation.indices is not None:
                    offset = start + self.offset('TriAnnotationSet', 'TriAnnotationIndices')
                    annotations.block.pack(offset, '<i', annotation.indices.count)
                    self.builder.reference(annotations.block.at(offset + 4), self.numeric(annotation.indices, 'annotation_map'))
        return header.at()

    def mesh(self, data):
        self.validation.mesh(data)
        header = self.emitter.reserve('Mesh', owner=data, section=self.object_section).block
        if header in self._written:
            return header.at()
        self._written.add(header)
        self.string(header.at(self.offset('Mesh', 'Name')), data.name)
        self.builder.reference(header.at(self.offset('Mesh', 'PrimaryVertexData')), self.vertices(data.vertices))
        self.builder.reference(header.at(self.offset('Mesh', 'PrimaryTopology')), self.topology(data.topology))
        self.properties.variant(header.at(self.offset('Mesh', 'ExtendedData')), data.metadata)
        morphs = self.array(header, 'Mesh', 'MorphTargets', 'MorphTarget', data.morph_targets)
        if morphs is not None and morphs.block not in self._written:
            self._written.add(morphs.block)
            for index, morph in enumerate(data.morph_targets):
                start = index*morphs.item_size
                if morph.name is not None:
                    self.string(morphs.block.at(start+self.offset('MorphTarget', 'ScalarName')), morph.name)
                self.builder.reference(morphs.block.at(start+self.offset('MorphTarget', 'VertexData')),
                    self.vertices(morph.vertex_data))
                morphs.block.pack(start+self.offset('MorphTarget', 'DataIsDeltas'), '<i', int(morph.vertex_data.data_is_deltas))
        materials = self.array(header, 'Mesh', 'MaterialBindings', 'MaterialBinding', data.materials)
        if materials is not None and materials.block not in self._written:
            self._written.add(materials.block)
            for index, material in enumerate(data.materials):
                self.builder.reference(materials.item(index), material)
        bones = self.array(header, 'Mesh', 'BoneBindings', 'BoneBinding', data.bone_bindings)
        if bones is not None and bones.block not in self._written:
            self._written.add(bones.block)
            for index, name in enumerate(data.bone_bindings):
                start = index * bones.item_size
                self.string(bones.block.at(start + self.offset('BoneBinding', 'BoneName')), name)
                # Match Foundry's current declared binding bounds. Computing
                # tighter bounds is not part of replacing the native writer.
                minimum, maximum = (-2., -2., -2.), (2., 2., 2.)
                if self.transforms is not None:
                    minimum, maximum = self.transforms.bounds(minimum, maximum)
                bones.block.pack(start + self.offset('BoneBinding', 'OBBMin'), '<3f', *minimum)
                bones.block.pack(start + self.offset('BoneBinding', 'OBBMax'), '<3f', *maximum)
        return header.at()

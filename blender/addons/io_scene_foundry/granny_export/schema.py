"""Independent, packed LE64 type definitions and SDK-compatible layout rules."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .binary import BinaryBuilder, BinaryWriteError, InlineArray, Marshalling, uint32
from .model import Metadata, Scalar, ValueKind


class MemberKind(IntEnum):
    INLINE = 1
    REFERENCE = 2
    REFERENCE_TO_ARRAY = 3
    ARRAY_OF_REFERENCES = 4
    VARIANT_REFERENCE = 5
    REFERENCE_TO_VARIANT_ARRAY = 7
    STRING = 8
    TRANSFORM = 9
    REAL32 = 10
    INT8 = 11
    UINT8 = 12
    BINORMAL_INT8 = 13
    NORMAL_UINT8 = 14
    INT16 = 15
    UINT16 = 16
    BINORMAL_INT16 = 17
    NORMAL_UINT16 = 18
    INT32 = 19
    UINT32 = 20
    REAL16 = 21
    EMPTY_REFERENCE = 22


_REFERENCED = {MemberKind.INLINE, MemberKind.REFERENCE, MemberKind.REFERENCE_TO_ARRAY, MemberKind.ARRAY_OF_REFERENCES}
_UNITS = {2: (8, 0), 3: (12, 4), 4: (12, 4), 5: (16, 0), 7: (20, 4), 8: (8, 4), 9: (68, 4),
          10: (4, 4), 11: (1, 1), 12: (1, 1), 13: (1, 1), 14: (1, 1),
          15: (2, 2), 16: (2, 2), 17: (2, 2), 18: (2, 2), 19: (4, 4), 20: (4, 4),
          21: (2, 2), 22: (8, 0)}
_SCALARS = {Scalar.REAL32: MemberKind.REAL32, Scalar.INT32: MemberKind.INT32,
            Scalar.UINT8: MemberKind.UINT8, Scalar.NORMAL_UINT8: MemberKind.NORMAL_UINT8,
            Scalar.UINT16: MemberKind.UINT16}


@dataclass(frozen=True, slots=True)
class SchemaMember:
    name: str
    kind: MemberKind
    width: int = 0
    reference: str | None = None
    extra: tuple[int, int, int] = (0, 0, 0)

    def __post_init__(self):
        try:
            object.__setattr__(self, 'kind', MemberKind(self.kind))
        except ValueError as error:
            raise BinaryWriteError('Unsupported or explicit END_MEMBER schema kind') from error
        object.__setattr__(self, 'extra', tuple(self.extra))
        if not isinstance(self.name, str) or '\0' in self.name:
            raise BinaryWriteError('Schema member names require text without embedded NUL')
        if not isinstance(self.width, int) or not 0 <= self.width < 2**31:
            raise BinaryWriteError('Schema member width must fit nonnegative int32')
        if len(self.extra) != 3 or any(not isinstance(v, int) or not -(2**31) <= v < 2**31 for v in self.extra):
            raise BinaryWriteError('Schema extra tags require three int32 values')
        if self.kind in _REFERENCED:
            if not isinstance(self.reference, str) or not self.reference:
                raise BinaryWriteError('This member kind requires a referenced schema')
        elif self.reference is not None:
            raise BinaryWriteError('This member kind has no static referenced schema')


@dataclass(frozen=True, slots=True, eq=False)
class Schema:
    name: str
    members: tuple[SchemaMember, ...]


@dataclass(frozen=True, slots=True)
class FieldLayout:
    member: SchemaMember
    offset: int
    unit_size: int
    size: int
    marshalling: int


@dataclass(frozen=True, slots=True)
class SchemaLayout:
    size: int
    marshalling: int
    fields: tuple[FieldLayout, ...]
    pointer_offsets: tuple[int, ...]

    def field(self, name, occurrence=None):
        matches = [field for field in self.fields if field.member.name == name]
        if not matches or (occurrence is None and len(matches) != 1):
            raise BinaryWriteError(f'Schema field is absent or ambiguous: {name}')
        index = 0 if occurrence is None else occurrence
        if not isinstance(index, int) or not 0 <= index < len(matches):
            raise BinaryWriteError('Repeated field occurrence is outside the schema')
        return matches[index]

    @property
    def storage(self):
        return {0: Marshalling.INT32, 1: Marshalling.INT8, 2: Marshalling.INT16,
                4: Marshalling.INT32}.get(self.marshalling, Marshalling.MIXED)


class SchemaRegistry:
    def __init__(self):
        self._schemas = {}
        self._pool = {}
        self._layouts = {}
        self._dynamic_count = 0

    def declare(self, name):
        if not isinstance(name, str) or not name or name in self._schemas:
            raise BinaryWriteError('Schema declaration requires a new nonempty name')
        self._schemas[name] = None

    def define(self, name, members):
        if not isinstance(name, str) or not name:
            raise BinaryWriteError('Schema definition requires a nonempty name')
        if name in self._schemas and self._schemas[name] is not None:
            raise BinaryWriteError(f'Schema is already defined: {name}')
        members = tuple(members)
        if any(not isinstance(member, SchemaMember) for member in members):
            raise BinaryWriteError('Schema definitions require typed members')
        schema = self._pool.get(members)
        if schema is None:
            schema = Schema(name, members)
            self._pool[members] = schema
        self._schemas[name] = schema
        return schema

    def resolve(self, value):
        if isinstance(value, Schema):
            if not any(schema is value for schema in self._schemas.values()):
                raise BinaryWriteError('Schema belongs to another registry')
            return value
        schema = self._schemas.get(value)
        if schema is None:
            raise BinaryWriteError(f'Referenced schema is not defined: {value}')
        return schema

    def intern(self, members, *, label='dynamic'):
        # References in dynamic definitions resolve before interning so named
        # aliases cannot accidentally produce duplicate dynamic layouts.
        normalized = tuple(SchemaMember(m.name, m.kind, m.width,
            self.resolve(m.reference).name if m.reference else None, m.extra) for m in members)
        if normalized in self._pool:
            return self._pool[normalized]
        name = f'{label}_{self._dynamic_count:04d}'
        self._dynamic_count += 1
        return self.define(name, normalized)

    @property
    def names(self):
        return tuple(self._schemas)

    def layout(self, value, _inline=()):
        schema = self.resolve(value)
        if schema in self._layouts:
            return self._layouts[schema]
        if schema in _inline:
            raise BinaryWriteError('Inline schema recursion has no finite object layout')
        rows, pointers, offset, mask = [], [], 0, 0
        for member in schema.members:
            child = self.resolve(member.reference) if member.reference is not None else None
            if member.kind is MemberKind.INLINE:
                nested = self.layout(child, (*_inline, schema))
                unit, flags = nested.size, nested.marshalling
                relative = nested.pointer_offsets
            else:
                unit, flags = _UNITS[member.kind]
                relative = ((0,) if member.kind in (MemberKind.REFERENCE, MemberKind.STRING, MemberKind.EMPTY_REFERENCE)
                    else (4,) if member.kind in (MemberKind.REFERENCE_TO_ARRAY, MemberKind.ARRAY_OF_REFERENCES)
                    else (0, 8) if member.kind is MemberKind.VARIANT_REFERENCE
                    else (0, 12) if member.kind is MemberKind.REFERENCE_TO_VARIANT_ARRAY else ())
            width = max(member.width, 1)
            size = uint32(unit * width, 'Schema member byte size')
            rows.append(FieldLayout(member, offset, unit, size, flags))
            if relative:
                pointers.extend(offset + index * unit + pointer for index in range(width) for pointer in relative)
            offset = uint32(offset + size, 'Schema object byte size')
            mask |= flags
        result = SchemaLayout(offset, mask, tuple(rows), tuple(pointers))
        self._layouts[schema] = result
        return result

    def vertex(self, data):
        return self.intern((SchemaMember(attribute.name, _SCALARS[attribute.buffer.scalar], attribute.buffer.width)
                            for attribute in data.attributes), label='vertex')

    def annotation(self, annotation):
        return self.intern((SchemaMember(annotation.member_name, _SCALARS[annotation.buffer.scalar],
                                         annotation.buffer.width),), label='annotation')

    def metadata(self, value: Metadata, _active=()):
        if not isinstance(value, Metadata) or id(value) in _active:
            raise BinaryWriteError('Metadata schemas require an acyclic typed record')
        members = []
        for member in value.members:
            if member.kind in (ValueKind.INT32, ValueKind.REAL32, ValueKind.STRING):
                kind = {ValueKind.INT32: MemberKind.INT32, ValueKind.REAL32: MemberKind.REAL32,
                        ValueKind.STRING: MemberKind.STRING}[member.kind]
                members.append(SchemaMember(member.name, kind))
            elif member.kind in (ValueKind.REAL32_ARRAY, ValueKind.INT32_ARRAY):
                if not member.value:
                    raise BinaryWriteError('Fixed scalar arrays require a positive width')
                kind = MemberKind.REAL32 if member.kind is ValueKind.REAL32_ARRAY else MemberKind.INT32
                members.append(SchemaMember(member.name, kind, len(member.value)))
            elif member.kind is ValueKind.REFERENCE:
                child = self.metadata(member.value, (*_active, id(value)))
                members.append(SchemaMember(member.name, MemberKind.REFERENCE, reference=child.name))
            elif member.kind in (ValueKind.RECORD_ARRAY, ValueKind.VARIANT_ARRAY):
                # Both use a runtime element type and count. Variant arrays
                # contain Variant records; record arrays contain homogeneous
                # dynamic objects. That payload distinction belongs to step 5.
                children = tuple(self.metadata(v, (*_active, id(value))) for v in member.value)
                if member.kind is ValueKind.RECORD_ARRAY and len(set(children)) > 1:
                    raise BinaryWriteError('Record arrays require a homogeneous element schema')
                members.append(SchemaMember(member.name, MemberKind.REFERENCE_TO_VARIANT_ARRAY))
            else:
                raise BinaryWriteError('Unsupported typed metadata member')
        return self.intern(members, label='metadata')


class SchemaEmitter:
    """Emit each canonical definition once, before descending recursive refs."""
    def __init__(self, builder: BinaryBuilder, registry: SchemaRegistry, *, type_section=0, string_section=0):
        self.builder, self.registry = builder, registry
        self.type_section, self.string_section = type_section, string_section
        self._definitions = {}
        self._typed_blocks = {}

    def emit(self, value):
        schema = self.registry.resolve(value)
        self.registry.layout(schema)  # Fail incomplete/inline-recursive types before allocation.
        if schema in self._definitions:
            return self._definitions[schema].at()
        block = self.builder.allocate((len(schema.members) + 1) * 44, section=self.type_section)
        self._definitions[schema] = block
        for index, member in enumerate(schema.members):
            offset = index * 44
            block.pack(offset, '<i', int(member.kind))
            self.builder.reference(block.at(offset + 4), self.builder.string(member.name, section=self.string_section))
            if member.reference is not None:
                self.builder.reference(block.at(offset + 12), self.emit(member.reference))
            block.pack(offset + 20, '<i3i', member.width, *member.extra)
        # The ignored pointer and all fields of the complete 44-byte sentinel stay zero.
        return block.at()

    def reserve(self, value, *, owner=None, count=1, section=0):
        schema = self.registry.resolve(value)
        layout = self.registry.layout(schema)
        uint32(count, 'Typed array count')
        if count == 0:
            return None
        if layout.size == 0:
            raise BinaryWriteError('Nonempty typed data requires a nonzero element size')
        alignment = 1 if layout.storage is Marshalling.INT8 else 2 if layout.storage is Marshalling.INT16 else 4
        options = dict(section=section, alignment=alignment, marshalling=layout.storage)
        if owner is None:
            array = InlineArray(self.builder.allocate(uint32(layout.size * count, 'Typed byte size'), **options), count, layout.size)
        else:
            array = self.builder.reserve_inline_array(owner, count, layout.size, **options)
        previous = self._typed_blocks.get(array.block)
        if previous is not None and previous != (schema, count):
            raise BinaryWriteError('Shared typed allocation has inconsistent schema')
        if previous is None:
            self._typed_blocks[array.block] = (schema, count)
            if layout.storage is Marshalling.MIXED:
                self.builder.mixed_marshalling(array.item(0), count, self.emit(schema), item_size=layout.size)
        return array

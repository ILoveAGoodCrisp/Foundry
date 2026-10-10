"""Serialize owned Halo properties and nested variants without a Granny DLL."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Integral, Real

from .binary import Address, BinaryWriteError, Marshalling
from .model import Metadata, ValueKind
from .schema import SchemaEmitter


@dataclass(frozen=True, slots=True, eq=False)
class _ArrayOwner:
    values: tuple
    kind: ValueKind
    schema: object


class MetadataEmitter:
    """Reuse schemas by shape, records by identity, and arrays by representation."""
    def __init__(self, emitter: SchemaEmitter, *, object_section=0):
        self.emitter = emitter
        self.registry, self.builder = emitter.registry, emitter.builder
        self.object_section = object_section
        self._records = {}
        self._arrays = {}

    @staticmethod
    def _int32(value):
        if not isinstance(value, Integral) or not -(2**31) <= value < 2**31:
            raise BinaryWriteError('Metadata integer must fit signed int32')
        return int(value)

    @staticmethod
    def _real32(value):
        if not isinstance(value, Real) or not isfinite(value):
            raise BinaryWriteError('Metadata scalar must be a finite real number')
        return float(value)

    def variant(self, source: Address, value: Metadata):
        """Write a type/object pair at any standard ExtendedData field."""
        schema = self.registry.metadata(value)
        record = self.record(value)
        self.builder.reference(source, self.emitter.emit(schema) if value.members else None)
        self.builder.reference(Address(source.block, source.offset + 8), record)

    def record(self, value: Metadata):
        schema = self.registry.metadata(value)
        if not value.members:
            return None
        previous = self._records.get(id(value))
        if previous is not None:
            if previous[0] is not value or previous[1] is not schema:
                raise BinaryWriteError('Metadata identity changed during serialization')
            return previous[2].item(0)
        allocation = self.emitter.reserve(schema, owner=value, section=self.object_section)
        self._records[id(value)] = (value, schema, allocation)
        self._write_record(allocation.item(0), value, schema)
        return allocation.item(0)

    def _array(self, values, kind, schema):
        values = tuple(values)
        key = (id(values), kind, schema)
        previous = self._arrays.get(key)
        if previous is not None:
            return previous[1]
        owner = _ArrayOwner(values, kind, schema)
        if not values:
            return None
        if self.registry.layout(schema).size == 0:
            # A nonempty array of empty records has zero stride. Keep a valid
            # non-null backing address rather than losing its cardinality.
            block = self.builder.allocate(1, section=self.object_section, alignment=1, marshalling=Marshalling.INT8)
            result = block.at()
            self._arrays[key] = (owner, result)
            return result
        allocation = self.emitter.reserve(schema, owner=owner, count=len(values), section=self.object_section)
        self._arrays[key] = (owner, allocation.item(0))
        for index, value in enumerate(values):
            if kind is ValueKind.VARIANT_ARRAY:
                self.variant(allocation.item(index), value)
            else:
                # Inline array elements are values, not standalone reference
                # objects. Repeated record identities still occupy each slot.
                self._write_record(allocation.item(index), value, schema)
        return allocation.item(0)

    def _write_record(self, source, value, schema):
        layout = self.registry.layout(schema)
        for field, member in zip(layout.fields, value.members):
            offset = source.offset + field.offset
            address = Address(source.block, offset)
            kind, data = member.kind, member.value
            if kind is ValueKind.INT32:
                source.block.pack(offset, '<i', self._int32(data))
            elif kind is ValueKind.REAL32:
                source.block.pack(offset, '<f', self._real32(data))
            elif kind in (ValueKind.INT32_ARRAY, ValueKind.REAL32_ARRAY):
                values = tuple(self._int32(v) if kind is ValueKind.INT32_ARRAY else self._real32(v) for v in data)
                source.block.pack(offset, '<' + ('i' if kind is ValueKind.INT32_ARRAY else 'f') * len(values), *values)
            elif kind is ValueKind.STRING:
                self.builder.reference(address, self.builder.string(data, section=self.emitter.string_section))
            elif kind is ValueKind.REFERENCE:
                self.builder.reference(address, self.record(data))
            elif kind in (ValueKind.RECORD_ARRAY, ValueKind.VARIANT_ARRAY):
                values = tuple(data)
                if len(values) >= 2**31:
                    raise BinaryWriteError('Metadata array count exceeds signed int32')
                if kind is ValueKind.VARIANT_ARRAY:
                    element_schema = self.registry.resolve('Variant')
                else:
                    element_schema = self.registry.metadata(values[0]) if values else None
                self.builder.reference(address, self.emitter.emit(element_schema) if element_schema else None)
                source.block.pack(offset + 8, '<i', len(values))
                self.builder.reference(Address(source.block, offset + 12),
                    self._array(values, kind, element_schema) if values else None)
            else:
                raise BinaryWriteError('Unsupported metadata payload kind')

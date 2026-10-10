"""GR2 v7 LE64 framing and symbolic allocation, independent of native code.

Per-asset schemas and serializers are introduced in later checkpoints. All
references here name owned allocations; no process address is written to disk.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import struct
import zlib

from .model import ExportDataError

UINT32_MAX = 0xFFFFFFFF
MAGIC_WORDS = (0x5E499BE5, 0x141F636F, 0xA9EB131E, 0xC4EDBE90)
STANDARD_TAG = 0x80000037
MAGIC_SIZE, HEADER_SIZE, SECTION_SIZE = 32, 72, 44
POINTER_SIZE = 8


class BinaryWriteError(ExportDataError):
    pass


class Marshalling(str, Enum):
    INT32 = 'int32'
    INT16 = 'int16'
    INT8 = 'int8'
    MIXED = 'mixed'


def uint32(value, label):
    if not isinstance(value, int) or not 0 <= value <= UINT32_MAX:
        raise BinaryWriteError(f'{label} is outside uint32 range')
    return value


def aligned(value, alignment):
    if not isinstance(alignment, int) or alignment < 1 or alignment & (alignment - 1):
        raise BinaryWriteError('Alignment must be a positive power of two')
    return (value + alignment - 1) & -alignment


@dataclass(frozen=True, slots=True)
class Address:
    block: Block
    offset: int = 0


class Block:
    __slots__ = ('_owner', '_data', '_section', '_alignment', '_marshalling')

    def __init__(self, owner, size, section, alignment, marshalling):
        self._owner = owner
        self._data = bytearray(size)
        self._section, self._alignment, self._marshalling = section, alignment, marshalling

    @property
    def section(self):
        return self._section

    @property
    def alignment(self):
        return self._alignment

    @property
    def marshalling(self):
        return self._marshalling

    @property
    def size(self):
        return len(self._data)

    def at(self, offset=0):
        if not isinstance(offset, int) or not 0 <= offset < self.size:
            raise BinaryWriteError('Address is outside its allocation')
        return Address(self, offset)

    def write(self, offset, data):
        view = memoryview(data)
        if not isinstance(offset, int) or offset < 0 or offset + view.nbytes > self.size:
            raise BinaryWriteError('Write is outside its allocation')
        self._data[offset:offset + view.nbytes] = view

    def pack(self, offset, format, *values):
        if not format.startswith('<'):
            raise BinaryWriteError('Packed values require explicit little-endian standard sizes')
        size = struct.calcsize(format)
        if not isinstance(offset, int) or offset < 0 or offset + size > self.size:
            raise BinaryWriteError('Packed write is outside its allocation')
        try:
            struct.pack_into(format, self._data, offset, *values)
        except (struct.error, OverflowError) as error:
            raise BinaryWriteError('Packed value does not fit its declared field') from error


@dataclass(frozen=True, slots=True)
class InlineArray:
    block: Block
    count: int
    item_size: int

    def item(self, index):
        if not isinstance(index, int) or not 0 <= index < self.count:
            raise BinaryWriteError('Inline array index is outside its allocation')
        return self.block.at(index * self.item_size)


def iter_graph_objects(root):
    """Discover record identities deterministically, including reference cycles.

    This is discovery, not a declaration that every record is a separate native
    object. Later serializers decide inline values, arrays and referenced data.
    """
    pending, seen = [root], set()
    while pending:
        value = pending.pop()
        if is_dataclass(value) and not isinstance(value, type):
            if id(value) in seen:
                continue
            seen.add(id(value))
            yield value
            pending.extend(reversed([getattr(value, field.name) for field in fields(value)]))
        elif isinstance(value, (tuple, list)):
            if id(value) in seen:
                continue
            seen.add(id(value))
            pending.extend(reversed(value))


class BinaryBuilder:
    """Own allocations, then resolve their locations after section grouping."""

    def __init__(self, section_count=1, *, max_file_size=UINT32_MAX):
        if not isinstance(section_count, int) or not 1 <= section_count <= 256:
            raise BinaryWriteError('Section count must be between 1 and 256')
        self.header_size = MAGIC_SIZE + HEADER_SIZE + SECTION_SIZE * section_count
        self.max_file_size = uint32(max_file_size, 'File size limit')
        if self.header_size > self.max_file_size:
            raise BinaryWriteError('File size limit cannot hold its header')
        self._sections = [[] for _ in range(section_count)]
        self._objects = {}  # Strong references prevent id reuse during allocation.
        self._array_shapes = {}
        self._strings = {}
        self._pointers = {}
        self._mixed = []
        self._budget = self.header_size

    def _charge(self, size):
        # Include worst-case per-allocation padding before allocating memory.
        if self._budget + size > self.max_file_size:
            raise BinaryWriteError('Allocations exceed the GR2 file size limit')
        self._budget += size

    def allocate(self, size, *, section=0, alignment=4, marshalling=Marshalling.INT32):
        uint32(size, 'Allocation size')
        aligned(0, alignment)
        if not size or not isinstance(section, int) or not 0 <= section < len(self._sections):
            raise BinaryWriteError('Allocation requires a nonempty size and a valid section')
        marshalling = Marshalling(marshalling)
        unit = 4 if marshalling is Marshalling.INT32 else 2 if marshalling is Marshalling.INT16 else 1
        if size % unit:
            raise BinaryWriteError('Allocation size does not match its marshalling width')
        self._charge(size + alignment - 1)
        block = Block(self, size, section, alignment, marshalling)
        self._sections[section].append(block)
        return block

    def reserve_object(self, value, size, **options):
        previous = self._objects.get(id(value))
        if previous is not None:
            block = previous[1]
            if (previous[0] is not value or block.size != size
                    or block.section != options.get('section', 0)
                    or block.alignment != options.get('alignment', 4)
                    or block.marshalling != Marshalling(options.get('marshalling', Marshalling.INT32))):
                raise BinaryWriteError('Shared object was requested with inconsistent allocation rules')
            return block
        block = self.allocate(size, **options)
        self._objects[id(value)] = (value, block)
        return block

    def reserve_inline_array(self, value, count, item_size, **options):
        uint32(count, 'Array count')
        uint32(item_size, 'Array item size')
        if not item_size:
            raise BinaryWriteError('Inline array items require a nonzero size')
        if not count:
            return None
        shape = (count, item_size)
        if id(value) in self._array_shapes and self._array_shapes[id(value)] != shape:
            raise BinaryWriteError('Shared inline array has inconsistent count or item size')
        block = self.reserve_object(value, uint32(count * item_size, 'Array byte size'), **options)
        self._array_shapes[id(value)] = shape
        return InlineArray(block, count, item_size)

    def string(self, value, *, section=0):
        if not isinstance(value, str) or '\0' in value:
            raise BinaryWriteError('Strings must be text without embedded NUL')
        key = (section, value)
        if key not in self._strings:
            data = value.encode('utf-8') + b'\0'
            block = self.allocate(len(data), section=section, alignment=1, marshalling=Marshalling.INT8)
            block.write(0, data)
            self._strings[key] = block.at()
        return self._strings[key]

    def _address(self, address, *, size=1):
        if (not isinstance(address, Address) or address.block._owner is not self
                or not isinstance(address.offset, int) or address.offset < 0
                or address.offset + size > address.block.size):
            raise BinaryWriteError('Reference is outside an owned allocation')
        return address

    def reference(self, source, target):
        source = self._address(source, size=POINTER_SIZE)
        key = (source.block, source.offset)
        if key in self._pointers:
            raise BinaryWriteError('Pointer field was registered more than once')
        if any((source.block, offset) in self._pointers
               for offset in range(source.offset - POINTER_SIZE + 1, source.offset + POINTER_SIZE)):
            raise BinaryWriteError('Pointer fields overlap')
        if isinstance(target, Address):
            self._address(target)
        if target is not None:
            self._charge(12)
        # The target may be an object not yet reserved; resolution is deferred.
        self._pointers[key] = target

    def mixed_marshalling(self, source, count, type_definition, *, item_size):
        uint32(count, 'Mixed marshalling count')
        uint32(item_size, 'Mixed marshalling item size')
        if not count or not item_size:
            raise BinaryWriteError('Mixed marshalling requires nonempty typed records')
        self._address(source, size=count * item_size)
        if source.block.marshalling is not Marshalling.MIXED:
            raise BinaryWriteError('Mixed marshalling requires a mixed allocation')
        if isinstance(type_definition, Address):
            self._address(type_definition)
        end = source.offset + count * item_size
        for previous, previous_count, _, previous_size in self._mixed:
            if (previous.block is source.block and source.offset < previous.offset + previous_count * previous_size
                    and previous.offset < end):
                raise BinaryWriteError('Mixed marshalling records overlap')
        self._charge(16)
        self._mixed.append((source, count, type_definition, item_size))

    def _target(self, value):
        if isinstance(value, Address):
            return self._address(value)
        previous = self._objects.get(id(value))
        if previous is None or previous[0] is not value:
            raise BinaryWriteError('A referenced object has no allocation')
        return previous[1].at()

    def build(self, root_type, root_object, *, type_tag=STANDARD_TAG):
        root_type, root_object = self._target(root_type), self._target(root_object)
        uint32(type_tag, 'File type tag')
        marked = {source.block for source, _, _, _ in self._mixed}
        if any(block.marshalling is Marshalling.MIXED and block not in marked
               for blocks in self._sections for block in blocks):
            raise BinaryWriteError('Mixed allocation has no typed marshalling record')
        offsets, sections = {}, []
        for blocks in self._sections:
            cursor = 0
            alignment = max((block.alignment for block in blocks), default=4)
            alignment = max(alignment, 4)
            groups = (tuple(b for b in blocks if b.marshalling in (Marshalling.INT32, Marshalling.MIXED)),
                      tuple(b for b in blocks if b.marshalling is Marshalling.INT16),
                      tuple(b for b in blocks if b.marshalling is Marshalling.INT8))
            boundaries = []
            for index, group in enumerate(groups):
                for block in group:
                    cursor = aligned(cursor, block.alignment)
                    offsets[block] = cursor
                    cursor += block.size
                if index < 2:
                    cursor = aligned(cursor, 4 if index == 0 else 2)
                    boundaries.append(cursor)
            size = aligned(cursor, alignment)
            sections.append(dict(size=size, alignment=alignment, first_16bit=boundaries[0],
                                 first_8bit=boundaries[1], pointers=[], mixed=[]))

        def location(address):
            return (address.block.section, uint32(offsets[address.block] + address.offset, 'Section offset'))

        for (block, offset), target in self._pointers.items():
            if target is not None:
                destination = self._target(target)
                sections[block.section]['pointers'].append((offsets[block] + offset, *location(destination)))
        for source, count, dtype, _ in self._mixed:
            destination = self._target(dtype)
            sections[source.block.section]['mixed'].append((count, offsets[source.block] + source.offset, *location(destination)))
        cursor = self.header_size
        for section in sections:
            section['pointers'].sort()
            section['mixed'].sort(key=lambda record: (record[1], record[0], record[2], record[3]))
            cursor = aligned(cursor, section['alignment'])
            section['data_offset'] = cursor
            cursor += section['size']
            section['pointer_offset'] = cursor if section['pointers'] else 0
            cursor += len(section['pointers']) * 12
            section['mixed_offset'] = cursor if section['mixed'] else 0
            cursor += len(section['mixed']) * 16
        uint32(cursor, 'Total file size')
        if cursor > self.max_file_size:
            raise BinaryWriteError('Final GR2 exceeds the file size limit')
        output = bytearray(cursor)
        struct.pack_into('<8I', output, 0, *MAGIC_WORDS, self.header_size, 0, 0, 0)
        struct.pack_into('<18I', output, MAGIC_SIZE, 7, cursor, 0, HEADER_SIZE, len(sections),
                         *location(root_type), *location(root_object), type_tag, *([0] * 8))
        for index, section in enumerate(sections):
            struct.pack_into('<11I', output, MAGIC_SIZE + HEADER_SIZE + SECTION_SIZE * index,
                0, section['data_offset'], section['size'], section['size'], section['alignment'],
                section['first_16bit'], section['first_8bit'], section['pointer_offset'], len(section['pointers']),
                section['mixed_offset'], len(section['mixed']))
            for block in self._sections[index]:
                start = section['data_offset'] + offsets[block]
                output[start:start + block.size] = block._data
            for position, record in enumerate(section['pointers']):
                struct.pack_into('<3I', output, section['pointer_offset'] + position * 12, *record)
            for position, record in enumerate(section['mixed']):
                struct.pack_into('<4I', output, section['mixed_offset'] + position * 16, *record)
        # All registered pointer fields are zero on disk, including null fields.
        for block, offset in self._pointers:
            start = sections[block.section]['data_offset'] + offsets[block] + offset
            output[start:start + POINTER_SIZE] = bytes(POINTER_SIZE)
        crc = zlib.crc32(memoryview(output)[MAGIC_SIZE + HEADER_SIZE:]) & UINT32_MAX
        struct.pack_into('<I', output, MAGIC_SIZE + 8, crc)
        return bytes(output)

from __future__ import annotations

from dataclasses import dataclass, field
import struct
from typing import Any


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    return (
        value.strip()
        .replace(":", " ")
        .replace("/", " ")
        .replace("-", "_")
        .replace(" ", "_")
        .lower()
    )


class _BinaryReader:
    def __init__(self, data: bytes | bytearray | memoryview):
        self.data = memoryview(data)
        self.offset = 0

    @property
    def length(self) -> int:
        return len(self.data)

    @property
    def remaining(self) -> int:
        return self.length - self.offset

    def tell(self) -> int:
        return self.offset

    def seek(self, offset: int):
        if offset < 0 or offset > self.length:
            raise ValueError(f"Seek out of range: {offset}")
        self.offset = offset

    def skip(self, size: int):
        self.seek(self.offset + size)

    def read_bytes(self, size: int) -> bytes:
        end = self.offset + size
        if end > self.length:
            raise ValueError("Unexpected end of serialized tag data")
        data = self.data[self.offset:end].tobytes()
        self.offset = end
        return data

    def _read(self, fmt: str):
        size = struct.calcsize(fmt)
        end = self.offset + size
        if end > self.length:
            raise ValueError("Unexpected end of serialized tag data")
        values = struct.unpack_from(fmt, self.data, self.offset)
        self.offset = end
        return values[0] if len(values) == 1 else values

    def read_i8(self) -> int:
        return self._read("<b")

    def read_u8(self) -> int:
        return self._read("<B")

    def read_i16(self) -> int:
        return self._read("<h")

    def read_u16(self) -> int:
        return self._read("<H")

    def read_i32(self) -> int:
        return self._read("<i")

    def read_u32(self) -> int:
        return self._read("<I")

    def read_i64(self) -> int:
        return self._read("<q")

    def read_u64(self) -> int:
        return self._read("<Q")

    def read_f32(self) -> float:
        return self._read("<f")

    def read_signature(self) -> str:
        data = bytearray(self.read_bytes(4))
        data.reverse()
        return data.decode("ascii", errors="replace")


@dataclass(slots=True)
class _ChunkHeader:
    signature: str
    version: int
    size: int


@dataclass(slots=True)
class _Chunk:
    header: _ChunkHeader
    data: bytes


class _ChunkReader(_BinaryReader):
    def read_next_chunk(self) -> _Chunk | None:
        if self.remaining < 12:
            return None
        signature = self.read_signature()
        version = self.read_i32()
        size = self.read_i32()
        if size < 0 or size > self.remaining:
            raise ValueError(f"Invalid chunk size {size} for {signature}")
        return _Chunk(_ChunkHeader(signature, version, size), self.read_bytes(size))

    def peek_next_chunk_header(self) -> _ChunkHeader | None:
        if self.remaining < 12:
            return None
        offset = self.tell()
        try:
            return _ChunkHeader(self.read_signature(), self.read_i32(), self.read_i32())
        finally:
            self.seek(offset)


@dataclass(slots=True)
class _PersistLayoutHeaderV3:
    root_block_index: int
    string_count: int
    string_offsets_count: int
    string_list_count: int
    custom_search_block_names_count: int
    data_definition_names_count: int
    array_count: int
    field_types_count: int
    field_count: int
    struct_count: int
    block_count: int
    resource_definition_count: int
    interop_definition_count: int


@dataclass(slots=True)
class _PersistFieldType:
    name_offset: int
    size: int
    unknown: int


@dataclass(slots=True)
class _PersistField:
    name_offset: int
    field_type_index: int
    definition: int


@dataclass(slots=True)
class _PersistBlockDefinition:
    name_offset: int
    max_element_count: int
    struct_index: int


@dataclass(slots=True)
class _PersistStructDefinition:
    unique_id: bytes
    name_offset: int
    first_field_index: int


@dataclass(slots=True)
class _PersistArrayDefinition:
    name_offset: int
    count: int
    struct_index: int


@dataclass(slots=True)
class _PersistResourceDefinition:
    name_offset: int
    unknown4: int
    struct_index: int


@dataclass(slots=True)
class _FieldTypeInfo:
    name: str
    normalized_name: str
    size: int


@dataclass(slots=True)
class _FieldDefinition:
    name: str
    normalized_name: str
    type_name: str
    type_size: int
    definition: Any
    offset: int = 0
    size: int = 0


@dataclass(slots=True)
class _StructDefinition:
    name: str
    unique_id: bytes
    first_field_index: int
    fields: list[_FieldDefinition] = field(default_factory=list)
    size: int = 0


@dataclass(slots=True)
class _BlockDefinition:
    name: str
    struct: _StructDefinition
    max_element_count: int


@dataclass(slots=True)
class _ArrayDefinition:
    name: str
    count: int
    struct: _StructDefinition


@dataclass(slots=True)
class _ResourceDefinition:
    name: str
    struct: _StructDefinition


class _StringBuffer:
    def __init__(self, data: bytes):
        self.data = data

    def get(self, offset: int) -> str:
        end = offset
        data_length = len(self.data)
        while end < data_length and self.data[end] != 0:
            end += 1
        return self.data[offset:end].decode("ascii", errors="replace")


@dataclass(slots=True)
class ParsedStruct:
    definition: _StructDefinition | None
    fields: dict[str, Any] = field(default_factory=dict)

    def get(self, *names: str, default=None):
        for name in names:
            key = _normalize_name(name)
            if key in self.fields:
                return self.fields[key]
        return default


@dataclass(slots=True)
class ParsedBlock:
    definition: _BlockDefinition | None
    elements: list[ParsedStruct] = field(default_factory=list)
    count: int = 0
    raw_unknown1: int = 0
    embedded_unknown1: int = 0


@dataclass(slots=True)
class SourceAnimationResourceMember:
    animation_index: int
    animation_checksum: int
    frame_count: int
    node_count: int
    movement_data_type: int
    static_flags_size: int
    animated_flags_size: int
    movement_data_size: int
    static_data_size: int
    shared_static_data_size: int
    animation_data: bytes
    section_boundaries: dict[str, int] = field(default_factory=dict)


class _SourceTagLayout:
    def __init__(
        self,
        header: _PersistLayoutHeaderV3,
        string_buffer: _StringBuffer,
        field_types: list[_PersistFieldType],
        fields: list[_PersistField],
        blocks: list[_PersistBlockDefinition],
        structs: list[_PersistStructDefinition],
        arrays: list[_PersistArrayDefinition],
        resources: list[_PersistResourceDefinition],
        data_definition_names: list[int],
        custom_search_block_names: list[int],
    ):
        self.header = header
        self.string_buffer = string_buffer
        self.persist_field_types = field_types
        self.persist_fields = fields
        self.persist_blocks = blocks
        self.persist_structs = structs
        self.persist_arrays = arrays
        self.persist_resources = resources
        self.data_definition_names = data_definition_names
        self.custom_search_block_names = custom_search_block_names

        self.field_type_infos: list[_FieldTypeInfo] = []
        for field_type in self.persist_field_types:
            name = self.string_buffer.get(field_type.name_offset)
            self.field_type_infos.append(_FieldTypeInfo(name, _normalize_name(name), field_type.size))

        self._field_cache: dict[int, _FieldDefinition] = {}
        self._struct_cache: dict[int, _StructDefinition] = {}
        self._block_cache: dict[int, _BlockDefinition] = {}
        self._array_cache: dict[int, _ArrayDefinition] = {}
        self._resource_cache: dict[int, _ResourceDefinition] = {}

    @property
    def root_block(self) -> _BlockDefinition:
        return self.get_block(self.header.root_block_index)

    def get_block(self, index: int) -> _BlockDefinition:
        if index not in self._block_cache:
            persist = self.persist_blocks[index]
            self._block_cache[index] = _BlockDefinition(
                self.string_buffer.get(persist.name_offset),
                self.get_struct(persist.struct_index),
                persist.max_element_count,
            )
        return self._block_cache[index]

    def get_struct(self, index: int) -> _StructDefinition:
        if index in self._struct_cache:
            return self._struct_cache[index]

        persist = self.persist_structs[index]
        struct_def = _StructDefinition(self.string_buffer.get(persist.name_offset), persist.unique_id, persist.first_field_index)
        self._struct_cache[index] = struct_def

        field_index = persist.first_field_index
        offset = 0
        while True:
            field_def = self.get_field(field_index)
            field_index += 1
            if field_def.type_name == "terminator_x":
                break
            field_copy = _FieldDefinition(
                field_def.name,
                field_def.normalized_name,
                field_def.type_name,
                field_def.type_size,
                field_def.definition,
                offset,
                self.get_field_size(field_def),
            )
            offset += field_copy.size
            struct_def.fields.append(field_copy)

        struct_def.size = offset
        return struct_def

    def get_array(self, index: int) -> _ArrayDefinition:
        if index not in self._array_cache:
            persist = self.persist_arrays[index]
            self._array_cache[index] = _ArrayDefinition(
                self.string_buffer.get(persist.name_offset),
                persist.count,
                self.get_struct(persist.struct_index),
            )
        return self._array_cache[index]

    def get_resource(self, index: int) -> _ResourceDefinition:
        if index not in self._resource_cache:
            persist = self.persist_resources[index]
            self._resource_cache[index] = _ResourceDefinition(
                self.string_buffer.get(persist.name_offset),
                self.get_struct(persist.struct_index),
            )
        return self._resource_cache[index]

    def get_field(self, index: int) -> _FieldDefinition:
        if index in self._field_cache:
            return self._field_cache[index]

        persist = self.persist_fields[index]
        field_type = self.field_type_infos[persist.field_type_index]
        field_name = self.string_buffer.get(persist.name_offset)
        definition = self._get_field_definition(field_type.normalized_name, persist.definition)
        field = _FieldDefinition(
            field_name,
            _normalize_name(field_name),
            field_type.normalized_name,
            field_type.size,
            definition,
        )
        field.size = self.get_field_size(field)
        self._field_cache[index] = field
        return field

    def _get_field_definition(self, type_name: str, definition: int) -> Any:
        if type_name == "struct":
            return self.get_struct(definition)
        if type_name == "block":
            return self.get_block(definition)
        if type_name == "array":
            return self.get_array(definition)
        if type_name == "pageable_resource":
            return self.get_resource(definition)
        if type_name in {"pad", "skip", "char_block_index", "short_block_index", "long_block_index", "byte_block_flags", "word_block_flags", "long_block_flags"}:
            return definition
        if type_name == "data" and 0 <= definition < len(self.data_definition_names):
            return self.string_buffer.get(self.data_definition_names[definition])
        if type_name in {"custom_char_block_index", "custom_short_block_index", "custom_long_block_index"} and 0 <= definition < len(self.custom_search_block_names):
            return self.string_buffer.get(self.custom_search_block_names[definition])
        return definition

    def get_field_size(self, field: _FieldDefinition) -> int:
        if field.type_name == "struct" and isinstance(field.definition, _StructDefinition):
            return field.definition.size
        if field.type_name == "array" and isinstance(field.definition, _ArrayDefinition):
            return field.definition.struct.size * field.definition.count
        if field.type_name in {"pad", "skip"} and isinstance(field.definition, int):
            return field.definition
        return field.type_size


class _SourceTagParser:
    def __init__(self, serialized_tag_data: bytes):
        self.serialized_tag_data = serialized_tag_data
        self.layout = self._read_layout()

    def _read_layout(self) -> _SourceTagLayout:
        reader = _ChunkReader(self.serialized_tag_data)
        if reader.length < 0x40:
            raise ValueError("Serialized tag is too small to contain a valid header")
        reader.skip(0x40)

        tag_chunk = reader.read_next_chunk()
        if tag_chunk is None or tag_chunk.header.signature != "tag!":
            raise ValueError("Expected tag! chunk in serialized tag data")
        tag_reader = _ChunkReader(tag_chunk.data)

        blay_chunk = tag_reader.read_next_chunk()
        if blay_chunk is None or blay_chunk.header.signature != "blay":
            raise ValueError("Expected blay chunk in serialized tag data")
        blay_reader = _ChunkReader(blay_chunk.data)

        blay_reader.read_i32()
        layout_id = blay_reader.read_bytes(16)
        layout_version = blay_reader.read_u32()
        if layout_version != 3:
            raise ValueError(f"Unsupported serialized tag layout version: {layout_version}")
        header = _PersistLayoutHeaderV3(
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
            blay_reader.read_i32(),
        )

        tgly_chunk = blay_reader.read_next_chunk()
        if tgly_chunk is None or tgly_chunk.header.signature != "tgly":
            raise ValueError("Expected tgly chunk in serialized tag data")
        tgly_reader = _ChunkReader(tgly_chunk.data)

        string_buffer = _StringBuffer(b"")
        string_offsets: list[int] = []
        data_definition_names: list[int] = []
        custom_search_block_names: list[int] = []
        field_types: list[_PersistFieldType] = []
        fields: list[_PersistField] = []
        blocks: list[_PersistBlockDefinition] = []
        structs: list[_PersistStructDefinition] = []
        arrays: list[_PersistArrayDefinition] = []
        resources: list[_PersistResourceDefinition] = []

        while True:
            chunk = tgly_reader.read_next_chunk()
            if chunk is None:
                break
            chunk_reader = _ChunkReader(chunk.data)
            match chunk.header.signature:
                case "str*":
                    string_buffer = _StringBuffer(chunk_reader.read_bytes(chunk.header.size))
                case "sz+x":
                    string_offsets = [chunk_reader.read_i32() for _ in range(header.string_offsets_count)]
                case "csbn":
                    custom_search_block_names = [chunk_reader.read_i32() for _ in range(header.custom_search_block_names_count)]
                case "dtnm":
                    data_definition_names = [chunk_reader.read_i32() for _ in range(header.data_definition_names_count)]
                case "tgft":
                    field_types = [_PersistFieldType(chunk_reader.read_i32(), chunk_reader.read_i32(), chunk_reader.read_i32()) for _ in range(header.field_types_count)]
                case "gras":
                    fields = [_PersistField(chunk_reader.read_i32(), chunk_reader.read_i32(), chunk_reader.read_i32()) for _ in range(header.field_count)]
                case "blv2":
                    blocks = [_PersistBlockDefinition(chunk_reader.read_i32(), chunk_reader.read_i32(), chunk_reader.read_i32()) for _ in range(header.block_count)]
                case "stv2" | "stv4":
                    structs = []
                    while chunk_reader.remaining > 0:
                        unique_id = chunk_reader.read_bytes(16)
                        name_offset = chunk_reader.read_i32()
                        first_field_index = chunk_reader.read_i32()
                        if chunk.header.signature == "stv4":
                            chunk_reader.read_i32()
                        structs.append(_PersistStructDefinition(unique_id, name_offset, first_field_index))
                case "arr!":
                    arrays = [_PersistArrayDefinition(chunk_reader.read_i32(), chunk_reader.read_i32(), chunk_reader.read_i32()) for _ in range(header.array_count)]
                case "rcv2":
                    resources = [_PersistResourceDefinition(chunk_reader.read_i32(), chunk_reader.read_i32(), chunk_reader.read_i32()) for _ in range(header.resource_definition_count)]

        return _SourceTagLayout(
            header,
            string_buffer,
            field_types,
            fields,
            blocks,
            structs,
            arrays,
            resources,
            data_definition_names,
            custom_search_block_names,
        )

    def parse_root(self) -> ParsedStruct:
        reader = _ChunkReader(self.serialized_tag_data)
        reader.skip(0x40)

        tag_chunk = reader.read_next_chunk()
        if tag_chunk is None or tag_chunk.header.signature != "tag!":
            raise ValueError("Expected tag! chunk in serialized tag data")
        tag_reader = _ChunkReader(tag_chunk.data)

        blay_chunk = tag_reader.read_next_chunk()
        if blay_chunk is None or blay_chunk.header.signature != "blay":
            raise ValueError("Expected blay chunk in serialized tag data")

        bdat_chunk = tag_reader.read_next_chunk()
        if bdat_chunk is None or bdat_chunk.header.signature != "bdat":
            raise ValueError("Expected bdat chunk in serialized tag data")
        bdat_reader = _ChunkReader(bdat_chunk.data)

        root_block_chunk = bdat_reader.read_next_chunk()
        if root_block_chunk is None or root_block_chunk.header.signature != "tgbl":
            raise ValueError("Expected tgbl chunk for serialized tag root block")

        root_block = self._parse_block_chunk(_ChunkReader(root_block_chunk.data), self.layout.root_block)
        if not root_block.elements:
            raise ValueError("Serialized tag root block had no elements")
        return root_block.elements[0]

    def _parse_block_chunk(self, chunk_reader: _ChunkReader, block_definition: _BlockDefinition, path: tuple[str, ...] = ()) -> ParsedBlock:
        element_count = chunk_reader.read_i32()
        embedded_unknown1 = chunk_reader.read_i32()
        raw_unknown1 = embedded_unknown1
        if element_count == 0 and block_definition.struct.size > 0 and chunk_reader.remaining > 0:
            element_count = chunk_reader.remaining // block_definition.struct.size

        elements: list[ParsedStruct] = []
        if element_count > 0 and block_definition.struct.size > 0:
            raw_size = element_count * block_definition.struct.size
            try:
                raw_reader = _BinaryReader(chunk_reader.read_bytes(raw_size))
            except Exception as exc:
                raise ValueError(
                    f"Failed to read raw bytes for block '{block_definition.name}' "
                    f"(count={element_count}, struct_size={block_definition.struct.size}, remaining={chunk_reader.remaining})"
                ) from exc
            empty_embedded = _ChunkReader(b"")
            for _ in range(element_count):
                elements.append(self._parse_struct(raw_reader, empty_embedded, block_definition.struct))

        for element in elements:
            header = chunk_reader.peek_next_chunk_header()
            if header is None or header.signature != "tgst":
                continue
            tgst = chunk_reader.read_next_chunk()
            if tgst is None:
                continue
            self._apply_struct_embedded_data(element, _ChunkReader(tgst.data), block_definition.struct, path)

        return ParsedBlock(block_definition, elements, element_count, raw_unknown1, embedded_unknown1)

    def _parse_struct(self, raw_reader: _BinaryReader, embedded_reader: _ChunkReader, definition: _StructDefinition) -> ParsedStruct:
        struct_start = raw_reader.tell()
        if embedded_reader.peek_next_chunk_header() is not None and embedded_reader.peek_next_chunk_header().signature == "tgst":
            tgst = embedded_reader.read_next_chunk()
            if tgst is not None and tgst.header.size:
                embedded_reader = _ChunkReader(tgst.data)

        parsed = ParsedStruct(definition)
        for field in definition.fields:
            parsed.fields[field.normalized_name] = self._read_raw_field(raw_reader, field)

        expected_end = struct_start + definition.size
        if raw_reader.tell() < expected_end:
            raw_reader.skip(expected_end - raw_reader.tell())
        return parsed

    def _apply_struct_embedded_data(self, parsed: ParsedStruct, embedded_reader: _ChunkReader, definition: _StructDefinition, path: tuple[str, ...] = ()):
        for field in definition.fields:
            current = parsed.fields.get(field.normalized_name)
            field_path = path + (field.normalized_name,)
            if self._should_descend(field_path):
                parsed.fields[field.normalized_name] = self._read_embedded_field(embedded_reader, field, current, field_path)
            else:
                self._skip_embedded_field(embedded_reader, field)
                parsed.fields[field.normalized_name] = current

    def _read_raw_field(self, reader: _BinaryReader, field: _FieldDefinition):
        type_name = field.type_name
        if type_name == "char_integer":
            return reader.read_i8()
        if type_name in {"byte_integer", "byte_flags", "char_enum", "char_block_index", "byte_block_flags"}:
            return reader.read_u8()
        if type_name in {"short_integer", "short_enum", "short_block_index", "custom_short_block_index"}:
            return reader.read_i16()
        if type_name in {"word_integer", "word_flags", "word_block_flags"}:
            return reader.read_u16()
        if type_name in {"long_integer", "long_enum", "long_block_index"}:
            return reader.read_i32()
        if type_name in {"dword_integer", "long_flags", "long_block_flags"}:
            return reader.read_u32()
        if type_name == "int64_integer":
            return reader.read_i64()
        if type_name == "qword_integer":
            return reader.read_u64()
        if type_name in {"real", "real_fraction", "angle"}:
            return reader.read_f32()
        if type_name == "string":
            return self._read_c_string(reader.read_bytes(field.size))
        if type_name == "long_string":
            return self._read_c_string(reader.read_bytes(field.size))
        if type_name == "tag":
            return reader.read_signature()
        if type_name == "struct" and isinstance(field.definition, _StructDefinition):
            raw = _BinaryReader(reader.read_bytes(field.definition.size))
            return self._parse_struct(raw, _ChunkReader(b""), field.definition)
        if type_name == "array" and isinstance(field.definition, _ArrayDefinition):
            items = []
            for _ in range(field.definition.count):
                items.append(self._parse_struct(reader, _ChunkReader(b""), field.definition.struct))
            return items
        if type_name == "block":
            count = reader.read_i32()
            unknown1 = reader.read_i32()
            if field.size > 8:
                reader.skip(field.size - 8)
            return ParsedBlock(field.definition if isinstance(field.definition, _BlockDefinition) else None, [], count, unknown1, unknown1)
        if type_name == "pageable_resource":
            reader.skip(field.size)
            return None
        if type_name == "data":
            reader.skip(field.size)
            return b""
        if type_name == "tag_reference":
            raw = reader.read_bytes(field.size)
            return raw

        reader.skip(field.size)
        return None

    def _read_embedded_field(self, reader: _ChunkReader, field: _FieldDefinition, current_value, path: tuple[str, ...]):
        type_name = field.type_name
        if type_name == "struct" and isinstance(current_value, ParsedStruct) and isinstance(field.definition, _StructDefinition):
            header = reader.peek_next_chunk_header()
            if header is None or header.signature != "tgst":
                return current_value
            tgst = reader.read_next_chunk()
            if tgst is None or tgst.header.size == 0:
                return current_value
            self._apply_struct_embedded_data(current_value, _ChunkReader(tgst.data), field.definition, path)
            return current_value

        if type_name == "block" and isinstance(field.definition, _BlockDefinition):
            header = reader.peek_next_chunk_header()
            if header is None or header.signature != "tgbl":
                if isinstance(current_value, ParsedBlock):
                    current_value.elements = []
                return current_value
            tgbl = reader.read_next_chunk()
            if tgbl is None:
                return current_value
            return self._parse_block_chunk(_ChunkReader(tgbl.data), field.definition, path)

        if type_name == "data":
            header = reader.peek_next_chunk_header()
            if header is None:
                return current_value
            if header.signature == "tgst":
                tgst = reader.read_next_chunk()
                if tgst is None:
                    return current_value
                reader = _ChunkReader(tgst.data)
                header = reader.peek_next_chunk_header()
                if header is None:
                    return current_value
            chunk = reader.read_next_chunk()
            if chunk is None:
                return current_value
            return chunk.data

        if type_name == "pageable_resource" and isinstance(field.definition, _ResourceDefinition):
            header = reader.peek_next_chunk_header()
            if header is None or header.signature != "tgrc":
                return current_value
            tgrc = reader.read_next_chunk()
            if tgrc is None:
                return current_value
            tgrc_reader = _ChunkReader(tgrc.data)
            tgdt_header = tgrc_reader.peek_next_chunk_header()
            if tgdt_header is not None and tgdt_header.signature == "tgdt":
                tgrc_reader.read_next_chunk()
            raw = _BinaryReader(tgrc_reader.read_bytes(field.definition.struct.size))
            resource_struct = self._parse_struct(raw, _ChunkReader(b""), field.definition.struct)
            self._apply_struct_embedded_data(resource_struct, tgrc_reader, field.definition.struct, path)
            return resource_struct

        if type_name == "tag_reference":
            header = reader.peek_next_chunk_header()
            if header is None or header.signature != "tgrf":
                return current_value
            tgrf = reader.read_next_chunk()
            if tgrf is None:
                return current_value
            return tgrf.data

        return current_value

    @staticmethod
    def _should_descend(path: tuple[str, ...]) -> bool:
        return bool(path) and path[0] == "tag_resource_groups"

    def _skip_embedded_field(self, reader: _ChunkReader, field: _FieldDefinition):
        header = reader.peek_next_chunk_header()
        if header is None:
            return

        type_name = field.type_name
        if type_name == "struct" and header.signature == "tgst":
            reader.read_next_chunk()
            return
        if type_name == "block" and header.signature == "tgbl":
            reader.read_next_chunk()
            return
        if type_name == "pageable_resource" and header.signature == "tgrc":
            reader.read_next_chunk()
            return
        if type_name == "tag_reference" and header.signature == "tgrf":
            reader.read_next_chunk()
            return
        if type_name == "data" and header.signature in {"tgst", "tgda"}:
            reader.read_next_chunk()

    @staticmethod
    def _read_c_string(data: bytes) -> str:
        terminator = data.find(b"\x00")
        if terminator >= 0:
            data = data[:terminator]
        return data.decode("ascii", errors="replace")


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


_RESOURCE_SECTION_NAME_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("static_node_flags", ("static_node_flags", "static node flags")),
    ("animated_node_flags", ("animated_node_flags", "animated node flags")),
    ("movement_data", ("movement_data", "movement data")),
    ("pill_offset_data", ("pill_offset_data", "pill offset data")),
    ("default_data", ("default_data", "default data", "static_data_size", "static data size")),
    ("uncompressed_data", ("uncompressed_data", "uncompressed data")),
    ("compressed_data", ("compressed_data", "compressed data")),
    ("blend_screen_data", ("blend_screen_data", "blend screen data")),
    ("object_space_offset_data", ("object_space_offset_data", "object space offset data")),
    ("ik_chain_event_data", ("ik_chain_event_data", "ik chain event data")),
    ("ik_chain_control_data", ("ik_chain_control_data", "ik chain control data")),
    ("ik_chain_proxy_data", ("ik_chain_proxy_data", "ik chain proxy data")),
    ("ik_chain_pole_vector_data", ("ik_chain_pole_vector_data", "ik chain pole vector data")),
    ("uncompressed_object_space_data", ("uncompressed_object_space_data", "uncompressed object space data")),
    ("fik_anchor_data", ("fik_anchor_data", "fik anchor data")),
    ("uncompressed_object_space_node_flags", ("uncompressed_object_space_node_flags", "uncompressed object space node flags")),
    ("compressed_event_curve", ("compressed_event_curve", "compressed event curve")),
    ("shared_static_data_size", ("shared_static_data_size", "shared static data size")),
)


def _section_boundaries(data_sizes: ParsedStruct | None) -> dict[str, int]:
    if not isinstance(data_sizes, ParsedStruct):
        return {}

    boundaries: dict[str, int] = {}
    for section_name, aliases in _RESOURCE_SECTION_NAME_ALIASES:
        value = _int_value(data_sizes.get(*aliases), -1)
        if value >= 0:
            boundaries[section_name] = value

    return boundaries


def read_model_animation_graph_resources(serialized_tag_data: bytes) -> list[list[SourceAnimationResourceMember]]:
    parser = _SourceTagParser(serialized_tag_data)
    root = parser.parse_root()
    resource_groups = root.get("tag resource groups")
    if not isinstance(resource_groups, ParsedBlock):
        raise ValueError("Serialized model_animation_graph did not contain tag resource groups")

    groups: list[list[SourceAnimationResourceMember]] = []
    for group in resource_groups.elements:
        tag_resource = group.get("tag_resource")
        if not isinstance(tag_resource, ParsedStruct):
            groups.append([])
            continue

        group_members = tag_resource.get("group_members", "resource_group_members")
        if not isinstance(group_members, ParsedBlock):
            groups.append([])
            continue

        members: list[SourceAnimationResourceMember] = []
        for member in group_members.elements:
            data_sizes = member.get("data sizes", "packed data sizes", "packed data sizes reach")
            if not isinstance(data_sizes, ParsedStruct):
                data_sizes = ParsedStruct(None)
            section_boundaries = _section_boundaries(data_sizes)

            members.append(
                SourceAnimationResourceMember(
                    animation_index=_int_value(member.get("animation_index", "animation index"), -1),
                    animation_checksum=_int_value(member.get("animation_checksum", "animation checksum"), 0),
                    frame_count=_int_value(member.get("frame count"), 0),
                    node_count=_int_value(member.get("node count"), 0),
                    movement_data_type=_int_value(member.get("movement_data_type", "movement data type"), 0),
                    static_flags_size=_int_value(data_sizes.get("static_node_flags", "static node flags"), 0),
                    animated_flags_size=_int_value(data_sizes.get("animated_node_flags", "animated node flags"), 0),
                    movement_data_size=_int_value(data_sizes.get("movement_data", "movement data"), 0),
                    static_data_size=_int_value(
                        data_sizes.get(
                            "default_data",
                            "default data",
                            "static_data_size",
                            "static data size",
                        ),
                        0,
                    ),
                    shared_static_data_size=_int_value(data_sizes.get("shared_static_data_size", "shared static data size"), 0),
                    animation_data=member.get("animation_data", "animation data", default=b"") or b"",
                    section_boundaries=section_boundaries,
                )
            )

        groups.append(members)

    return groups

"""Reader for the legacy binary Havok tagfiles embedded in Halo 4 tags."""

import struct


class HavokTagfileReader:
    """Decode the self-describing Havok tagfile object graph used by H4 Tool."""

    _MAGIC = bytes.fromhex("1e0db0cacefa11d0")
    _ARRAY = 16
    _TUPLE = 32
    _BASIC_TYPE_MASK = 15
    _MAX_VALUES = 4_000_000

    def __init__(self, data: bytes):
        self.data = data
        self.offset = len(self._MAGIC)
        self.strings = []
        self.types = [{"name": "BuiltinVoidType", "parent": 0, "members": []}]
        self.type_lookup = {}
        self.objects = {}
        self.next_object_index = 1

    def parse(self):
        if len(self.data) < len(self._MAGIC) or self.data[:len(self._MAGIC)] != self._MAGIC:
            raise ValueError("Invalid Havok tagfile magic")

        while self.offset < len(self.data):
            tag = self._read_varint()
            if tag == 0:  # Object alignment padding.
                continue
            if tag == 1:
                version = self._read_varint()
                if version not in (3, 4):
                    raise ValueError(f"Unsupported Havok tagfile version {version}")
                self.strings = ["", ""]
                if version == 4:
                    self._read_string()
            elif tag == 2:
                type_info = self._read_type_info()
                self.types.append(type_info)
                self.type_lookup[type_info["name"]] = len(self.types) - 1
            elif tag == 4:
                target = self.objects.setdefault(
                    self.next_object_index,
                    {"classes": [], "fields": {}, "id": self.next_object_index},
                )
                self.next_object_index += 1
                self._parse_struct(target=target)
            elif tag == 7:
                return self.objects.get(1)
            else:
                raise ValueError(f"Unsupported Havok tag {tag} at offset {self.offset}")

        raise EOFError("Havok tagfile ended before its end tag")

    def _read_raw(self, count: int) -> bytes:
        if count < 0:
            raise ValueError("Negative Havok data length")
        end = self.offset + count
        if end > len(self.data):
            raise EOFError("Havok tagfile read exceeded the payload")
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def _read_varint(self) -> int:
        byte = self._read_raw(1)[0]
        negative = bool(byte & 1)
        value = (byte & 0x7E) >> 1
        shift = 6
        while byte & 0x80:
            byte = self._read_raw(1)[0]
            value |= (byte & 0x7F) << shift
            shift += 7
            if shift > 63:
                raise ValueError("Invalid packed Havok integer")
        return -value if negative else value

    def _read_count(self) -> int:
        count = self._read_varint()
        if count < 0 or count > self._MAX_VALUES:
            raise ValueError(f"Invalid Havok collection size {count}")
        return count

    def _read_string(self) -> str:
        length = self._read_varint()
        if length <= 0:
            index = -length
            if index >= len(self.strings):
                raise ValueError(f"Invalid Havok string reference {index}")
            return self.strings[index]

        value = self._read_raw(length).decode("utf-8")
        self.strings.append(value)
        return value

    def _read_type_info(self):
        type_info = {
            "name": self._read_string(),
            "unknown": self._read_varint(),
            "parent": self._read_varint(),
            "members": [],
        }
        for _ in range(self._read_count()):
            member = {
                "name": self._read_string(),
                "type": self._read_varint(),
                "tuple_size": 0,
                "class_name": "",
            }
            if member["type"] & self._TUPLE:
                member["tuple_size"] = self._read_count()
            if (member["type"] & self._BASIC_TYPE_MASK) in (8, 9):
                member["class_name"] = self._read_string()
            type_info["members"].append(member)
        return type_info

    def _members(self, class_index: int):
        inheritance = []
        visited = set()
        while class_index:
            if class_index < 0 or class_index >= len(self.types) or class_index in visited:
                raise ValueError(f"Invalid Havok class index {class_index}")
            visited.add(class_index)
            inheritance.append(self.types[class_index])
            class_index = self.types[class_index]["parent"]
        for type_info in reversed(inheritance):
            yield from type_info["members"]

    def _class_names(self, class_index: int) -> list[str]:
        class_names = []
        visited = set()
        while class_index:
            if class_index < 0 or class_index >= len(self.types) or class_index in visited:
                raise ValueError(f"Invalid Havok class index {class_index}")
            visited.add(class_index)
            class_names.append(self.types[class_index]["name"])
            class_index = self.types[class_index]["parent"]
        return class_names

    def _parse_struct(self, class_index: int = 0, target=None):
        if not class_index:
            class_index = self._read_varint()
        if class_index <= 0 or class_index >= len(self.types):
            raise ValueError(f"Invalid Havok class index {class_index}")

        target = target if target is not None else {"classes": [], "fields": {}}
        target["classes"] = self._class_names(class_index)
        members = list(self._members(class_index))
        bitmap = self._read_raw((len(members) + 7) // 8)
        for index, member in enumerate(members):
            if bitmap[index // 8] & (1 << (index % 8)):
                target["fields"][member["name"]] = self._parse_field(member)
        return target

    def _parse_field(self, member):
        member_type = member["type"]
        flags = member_type & (self._ARRAY | self._TUPLE)
        basic_type = member_type & self._BASIC_TYPE_MASK
        if member_type == (self._TUPLE | 1):
            return self._read_raw(member["tuple_size"])
        if member_type == (self._ARRAY | 1):
            return self._read_raw(self._read_count())
        if flags:
            if flags == (self._ARRAY | self._TUPLE):
                raise ValueError("Havok field cannot be both an array and a tuple")
            count = member["tuple_size"] if flags & self._TUPLE else self._read_count()
            return self._parse_array(member, count)
        return self._parse_value(basic_type, member["class_name"], -1)

    def _parse_array(self, member, count: int, struct_member: bool = False):
        basic_type = member["type"] & self._BASIC_TYPE_MASK
        if struct_member and member["type"] & self._TUPLE:
            if basic_type == 1:
                return [self._read_raw(member["tuple_size"]) for _ in range(count)]
            return [
                tuple(
                    self._parse_value(basic_type, member["class_name"], -1)
                    for _ in range(member["tuple_size"])
                )
                for _ in range(count)
            ]

        prefix = self._read_varint() if basic_type in (2, 4) else -1
        if basic_type == 9:
            return self._parse_struct_array(member, count)
        return [
            self._parse_value(basic_type, member["class_name"], prefix)
            for _ in range(count)
        ]

    def _parse_struct_array(self, member, count: int):
        class_index = 0
        if member["type"] == (self._ARRAY | 9) and not member["class_name"]:
            class_index = self._read_varint()
        elif member["class_name"]:
            class_index = self.type_lookup.get(member["class_name"], 0)
        if class_index <= 0 or class_index >= len(self.types):
            raise ValueError(f"Unknown Havok struct array class {member['class_name']}")

        members = list(self._members(class_index))
        bitmap = self._read_raw((len(members) + 7) // 8)
        class_names = self._class_names(class_index)
        values = [{"classes": class_names.copy(), "fields": {}} for _ in range(count)]
        for index, field in enumerate(members):
            if bitmap[index // 8] & (1 << (index % 8)):
                field_values = self._parse_array(field, count, struct_member=True)
                for value, struct_value in zip(field_values, values):
                    struct_value["fields"][field["name"]] = value
        return values

    def _parse_value(self, basic_type: int, class_name: str, array_prefix: int):
        if basic_type == 0:
            return None
        if basic_type == 1:
            return self._read_raw(1)[0]
        if basic_type == 2:
            return self._read_varint()
        if basic_type == 3:
            return struct.unpack("<f", self._read_raw(4))[0]
        if basic_type in (4, 5, 6, 7):
            vector_size = {
                4: array_prefix if array_prefix >= 0 else 4,
                5: 8,
                6: 12,
                7: 16,
            }[basic_type]
            if basic_type == 4 and not 1 <= vector_size <= 4:
                raise ValueError(f"Unsupported Havok vector length {vector_size}")
            value = struct.unpack(f"<{vector_size}f", self._read_raw(vector_size * 4))
            if basic_type == 4 and vector_size < 4:
                value += (0.0,) * (4 - vector_size)
            return value
        if basic_type == 8:
            object_index = self._read_varint()
            if not object_index:
                return None
            if object_index < 0 or object_index > self._MAX_VALUES:
                raise ValueError(f"Invalid Havok object reference {object_index}")
            return self.objects.setdefault(
                object_index,
                {"classes": [], "fields": {}, "id": object_index},
            )
        if basic_type == 9:
            return self._parse_struct(self.type_lookup.get(class_name, 0))
        if basic_type == 10:
            return self._read_string()
        raise ValueError(f"Unsupported Havok field type {basic_type}")

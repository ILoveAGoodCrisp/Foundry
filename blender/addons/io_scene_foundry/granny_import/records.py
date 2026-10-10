"""Lazy typed records and bulk numeric arrays from a file's own schema."""
from dataclasses import dataclass
import numpy as np

from .container import MAX_BYTES, UnsupportedGrannyFormat, add, count, identity


NUMERIC = {10: 'f4', 11: 'i1', 12: 'u1', 13: 'i1', 14: 'u1',
           15: 'i2', 16: 'u2', 17: 'i2', 18: 'u2', 19: 'i4', 20: 'u4', 21: 'f2'}


def normalize(values, kind):
    if kind in (13, 17):
        return np.maximum(-1., values.astype(np.float32) / (127 if kind == 13 else 32767))
    if kind in (14, 18):
        return values.astype(np.float32) / (255 if kind == 14 else 65535)
    return values


@dataclass(frozen=True)
class Member:
    name: str
    kind: int
    width: int
    reference: tuple | None
    offset: int
    unit: int


class Records:
    def __init__(self, container):
        self.file = container
        self.layouts = {}
        self.active_types = set()
        self.metadata_budget = 2_000_000
        self.member_budget = 1_000_000

    def layout(self, dtype):
        if dtype in self.layouts:
            return self.layouts[dtype]
        if dtype is None or dtype in self.active_types or len(self.active_types) >= 32:
            raise ValueError('Missing or recursive inline GR2 schema')
        if len(self.layouts) > 100_000:
            raise ValueError('Too many GR2 schemas')
        self.active_types.add(dtype)
        members, offset, p = [], 0, self.file.pointer_size
        try:
            for index in range(1024):
                at = add(dtype, index * (20 + p * 3))
                kind = self.file.unpack(at, 'i')[0]
                if not kind:
                    self.layouts[dtype] = (members, offset)
                    return members, offset
                self.member_budget -= 1
                if self.member_budget < 0:
                    raise ValueError('Too many GR2 schema members')
                self.file.view(at, 20 + p * 3)
                name = self.file.string(self.file.pointer(add(at, 4)))
                reference = self.file.pointer(add(at, 4 + p))
                width = max(1, count(self.file.unpack(add(at, 4 + 2 * p), 'i')[0], 1024))
                if kind == 1:
                    unit = self.layout(reference)[1]
                elif kind in NUMERIC:
                    unit = np.dtype(NUMERIC[kind]).itemsize
                else:
                    unit = {2: p, 3: 4 + p, 4: 4 + p, 5: 2 * p, 7: 4 + 2 * p, 8: p, 9: 68, 22: p}.get(kind)
                    if unit is None:
                        raise ValueError(f'Invalid GR2 member type {kind}')
                members.append(Member(name, kind, width, reference, offset, unit))
                offset += unit * width
                if offset > 1024 * 1024:
                    raise ValueError('GR2 schema object is too large')
            raise ValueError('Unterminated GR2 type definition')
        finally:
            self.active_types.remove(dtype)

    def record(self, dtype, address):
        if address is None:
            return None
        self.file.view(address, self.layout(dtype)[1])
        return Record(self, dtype, address)

    def member(self, member, address):
        f, kind, p = self.file, member.kind, self.file.pointer_size
        if kind == 1:
            return self.record(member.reference, address)
        if kind == 2:
            return self.record(member.reference, f.pointer(address))
        if kind in (3, 4):
            return Array(self, member.reference, f.pointer(add(address, 4)), f.unpack(address, 'i')[0], kind == 4)
        if kind == 5:
            return self.record(f.pointer(address), f.pointer(add(address, p)))
        if kind == 7:
            return Array(self, f.pointer(address), f.pointer(add(address, p + 4)), f.unpack(add(address, p), 'i')[0])
        if kind == 8:
            return f.string(f.pointer(address))
        if kind == 9:
            from .transforms import transform_matrix
            return transform_matrix(f.unpack(address, 'I16f'))
        if kind in NUMERIC:
            return normalize(np.frombuffer(f.view(address, member.unit), dtype='<' + NUMERIC[kind]), kind)[0].item()
        if kind == 22:
            return None
        raise UnsupportedGrannyFormat(f'Unsupported GR2 member type {kind}')

    def detach(self, value, depth=0, *, allow_nonfinite=False):
        self.metadata_budget -= 1
        if depth > 24 or self.metadata_budget < 0:
            raise ValueError('GR2 metadata exceeds nesting or object limits')
        if isinstance(value, Record):
            names = [m.name for m in self.layout(value.dtype)[0]]
            if names[:6] == ['FromFileName', 'TextureType', 'Width', 'Height', 'Encoding', 'SubFormat']:
                return {**{name: value.get(name) for name in names[:6]},
                        'ImageCount': len(value.get('Images', ())), 'gr2_texture_id': value.id}
            result = {}
            for member in self.layout(value.dtype)[0]:
                item = None if member.kind == 22 else self.detach(value.value(member), depth + 1, allow_nonfinite=allow_nonfinite)
                if member.name in result:
                    old = result[member.name]
                    result[member.name] = (old if isinstance(old, list) else [old]) + [item]
                else:
                    result[member.name] = item
            return result
        if isinstance(value, (Array, list)):
            count(len(value), 100_000)
            return [self.detach(v, depth + 1, allow_nonfinite=allow_nonfinite) for v in value]
        if isinstance(value, np.ndarray):
            if not allow_nonfinite and not np.isfinite(value).all():
                raise ValueError('Non-finite GR2 metadata value')
            return value.tolist()
        if isinstance(value, float) and not allow_nonfinite and not np.isfinite(value):
            raise ValueError('Non-finite GR2 metadata value')
        return {} if value is None else value


class Record:
    def __init__(self, owner, dtype, address):
        self.owner, self.dtype, self.address = owner, dtype, address
        self.id = identity(address)

    def value(self, member):
        values = [self.owner.member(member, add(self.address, member.offset + i * member.unit)) for i in range(member.width)]
        return values[0] if member.width == 1 else values

    def get(self, name, default=None):
        for member in self.owner.layout(self.dtype)[0]:
            if member.name == name:
                return self.value(member)
        return default


class Array:
    def __init__(self, owner, dtype, address, length, indirect=False):
        self.owner, self.dtype, self.address = owner, dtype, address
        self.length, self.indirect = count(length, MAX_BYTES), indirect
        self.stride = owner.file.pointer_size if indirect else owner.layout(dtype)[1] if dtype else 0
        if length:
            if dtype is None or not self.stride:
                raise ValueError('Missing GR2 array element schema')
            owner.file.view(address, self.stride * length)

    def __len__(self):
        return self.length

    def __iter__(self):
        for i in range(self.length):
            yield self[i]

    def __getitem__(self, index):
        if not 0 <= index < self.length:
            raise IndexError(index)
        at = add(self.address, index * self.stride)
        return self.owner.record(self.dtype, self.owner.file.pointer(at) if self.indirect else at)

    def numeric(self):
        if not self.length:
            return {}
        if self.indirect:
            raise ValueError('Indirect GR2 numeric array')
        result = {}
        for member in self.owner.layout(self.dtype)[0]:
            if member.kind not in NUMERIC or member.name in result:
                raise ValueError('Unsupported or duplicate GR2 numeric component')
            values = np.ndarray((self.length, member.width), dtype='<' + NUMERIC[member.kind],
                                buffer=self.owner.file.view(self.address, self.length * self.stride),
                                offset=member.offset, strides=(self.stride, member.unit))
            result[member.name] = normalize(values, member.kind)
        return result

    def scalar(self):
        if not self.length:
            return np.empty(0, dtype=np.float32)
        values = list(self.numeric().values())
        if len(values) != 1 or values[0].shape[1] != 1:
            raise ValueError('Expected a GR2 scalar array')
        return values[0][:, 0]

"""Bounds-checked GR2 sections and symbolic relocations; never native pointers."""
from pathlib import Path
import struct
import zlib


class UnsupportedGrannyFormat(ValueError):
    """A valid format feature requires a codec that this reader does not have."""


PLATFORMS = {
    bytes.fromhex('29de6cc0baa4532b25f5b7a5f666e2ee'): 4,
    bytes.fromhex('e59b495e6f631f141e13eba990beedc4'): 8,
}
MAX_BYTES = 1024 * 1024 * 1024


def count(value, limit=10_000_000):
    if not isinstance(value, int) or not 0 <= value <= limit:
        raise ValueError(f'Invalid GR2 array count: {value}')
    return value


def add(address, offset):
    return (address[0], address[1] + offset)


def identity(address):
    return ((address[0] << 32) + address[1] + 1) if address is not None else 0


class Container:
    def __init__(self, data, *, decompress=None):
        if not 88 <= len(data) <= MAX_BYTES:
            raise ValueError('Invalid GR2 file size')
        magic = bytes(data[:16])
        self.pointer_size = PLATFORMS.get(magic)
        if self.pointer_size is None:
            if magic in (bytes.fromhex('0e1195b56aa5b54beb2828502578b304'), bytes.fromhex('3195d4e320dc4f62cc36d03ab182ff89')):
                raise UnsupportedGrannyFormat('Big-endian GR2 requires the compatibility reader')
            raise ValueError('Invalid GR2 platform magic')
        header_size, header_format = struct.unpack_from('<2I', data, 16)
        version, size, crc, section_relative, sections = struct.unpack_from('<5I', data, 32)
        if version not in (6, 7):
            raise UnsupportedGrannyFormat(f'Unsupported GR2 version {version}; expected 6 or 7')
        if header_format:
            raise UnsupportedGrannyFormat(f'Unsupported GR2 header compression {header_format}')
        start = 32 + section_relative
        if size != len(data) or not 1 <= sections <= 256:
            raise ValueError('Invalid GR2 file length or section count')
        if not (88 if version == 6 else 104) <= start <= start + sections * 44 <= header_size <= size:
            raise ValueError('Invalid GR2 section table')
        if zlib.crc32(memoryview(data)[start:]) != crc:
            raise ValueError('GR2 CRC mismatch')
        if version == 7 and struct.unpack_from('<I', data, 88)[0]:
            raise UnsupportedGrannyFormat('GR2 external string databases are not supported')

        def file_bytes(offset, length):
            if length and (offset < header_size or offset + length > size):
                raise ValueError('GR2 data extends beyond its file')
            return memoryview(data)[offset:offset + length]

        headers = [struct.unpack_from('<11I', data, start + index * 44) for index in range(sections)]
        if sum(h[3] + h[8] * 12 + h[10] * 16 for h in headers) > MAX_BYTES:
            raise ValueError('GR2 expanded data exceeds the memory limit')
        self.sections, self.pointers, self.strings = [], {}, {}
        self.string_budget = 64 * 1024 * 1024
        self.used_compression = set()
        for compression, offset, packed, expanded, alignment, stop0, stop1, fix, fixes, mix, mixes in headers:
            if not alignment or alignment & (alignment - 1) or alignment > 65536:
                raise ValueError('Invalid GR2 section alignment')
            if not 0 <= stop0 <= stop1 <= expanded:
                raise ValueError('Invalid GR2 marshalling boundaries')
            raw = file_bytes(offset, packed)
            file_bytes(fix, count(fixes) * 12)
            file_bytes(mix, count(mixes) * 16)
            if compression and expanded:
                if decompress is None:
                    raise UnsupportedGrannyFormat(f'GR2 section compression {compression} requires an Oodle decoder')
                raw = decompress(compression, raw, stop0, stop1, expanded)
                self.used_compression.add(compression)
            elif packed != expanded:
                raise ValueError('Uncompressed GR2 section has inconsistent sizes')
            if len(raw) != expanded:
                raise ValueError('GR2 decompressor returned the wrong section length')
            self.sections.append(raw)
        for section, h in enumerate(headers):
            for source, target_section, target_offset in struct.iter_unpack('<3I', file_bytes(h[7], h[8] * 12)):
                address, target = (section, source), (target_section, target_offset)
                self.view(address, self.pointer_size)
                self.view(target, 1)
                if address in self.pointers:
                    raise ValueError('Duplicate GR2 pointer relocation')
                self.pointers[address] = target
            for n, offset, type_section, type_offset in struct.iter_unpack('<4I', file_bytes(h[9], h[10] * 16)):
                count(n)
                self.view((section, offset), 1)
                self.view((type_section, type_offset), 4)
        self.root_type = struct.unpack_from('<2I', data, 52)
        self.root_address = struct.unpack_from('<2I', data, 60)
        self.view(self.root_type, 4)
        self.view(self.root_address, 1)

    @classmethod
    def read(cls, path, **options):
        path = Path(path)
        if path.stat().st_size > MAX_BYTES:
            raise ValueError('GR2 file exceeds the memory limit')
        with path.open('rb') as stream:
            return cls(stream.read(MAX_BYTES + 1), **options)

    def view(self, address, length):
        if address is None:
            raise ValueError('Missing GR2 data pointer')
        section, offset = address
        if not 0 <= section < len(self.sections) or offset < 0 or length < 0 or offset + length > len(self.sections[section]):
            raise ValueError('GR2 reference extends beyond its section')
        return memoryview(self.sections[section])[offset:offset + length]

    def unpack(self, address, fmt):
        return struct.unpack('<' + fmt, self.view(address, struct.calcsize('<' + fmt)))

    def pointer(self, address):
        self.view(address, self.pointer_size)
        # Older exporters leave unused pointer slots uninitialized. The
        # relocation table, not those process-address bytes, is authoritative.
        return self.pointers.get(address)

    def string(self, address):
        if address is None:
            return ''
        if address in self.strings:
            return self.strings[address]
        section, offset = address
        self.view(address, 1)
        # A bounded copy avoids scanning/copying an entire large section.
        length = 256
        while True:
            raw = bytes(memoryview(self.sections[section])[offset:offset + length])
            end = raw.find(b'\0')
            if end >= 0 or len(raw) < length or length >= 1024 * 1024:
                break
            length *= 2
        if end < 0:
            raise ValueError('Unterminated or oversized GR2 string')
        self.string_budget -= end
        if self.string_budget < 0:
            raise ValueError('GR2 strings exceed the memory limit')
        result = raw[:end].decode('utf-8', errors='replace')
        self.strings[address] = result
        return result

"""Losslessly recompress shader libraries (Python 3.14+, no Blender required).

Run without arguments to measure H2AMP/H4, then add --write to apply savings.
Repeat after editing/saving the libraries in Blender. Frame boundaries and the
seek table are preserved; decompressed Blender data must remain identical.
"""
from __future__ import annotations

import argparse
from compression import zstd
import hashlib
import os
from pathlib import Path
import struct
import tempfile


LIBRARIES = Path(__file__).resolve().parent / 'addons/io_scene_foundry/blends'
SEEK_MAGIC = 0x8F92EAB1
TABLE_MAGIC = 0x184D2A5E


def read_frames(data: bytes) -> tuple[list[tuple[bytes, bytes, bytes]], bytes]:
    """Validate a Zstandard seek table and return frames, contents, checksums.

    Format: https://github.com/facebook/zstd/blob/dev/contrib/seekable_format/
    zstd_seekable_compression_format.md
    """
    if len(data) < 17 or data[:4] != b'\x28\xb5\x2f\xfd':
        raise ValueError('Expected a seekable Zstandard-compressed .blend file')
    count, flags, magic = struct.unpack_from('<IBI', data, len(data) - 9)
    if magic != SEEK_MAGIC or flags & 0x7C or count == 0:
        raise ValueError('Missing or unsupported Zstandard seek table')
    entry_size = 12 if flags & 0x80 else 8
    table_size = count * entry_size + 9
    table_offset = len(data) - table_size - 8
    if table_offset < 0 or struct.unpack_from('<II', data, table_offset) != (TABLE_MAGIC, table_size):
        raise ValueError('Invalid Zstandard seek table size or header')
    frames = []
    offset = 0
    for index in range(count):
        entry = table_offset + 8 + index * entry_size
        compressed_size, raw_size = struct.unpack_from('<II', data, entry)
        if compressed_size == 0 or offset + compressed_size > table_offset:
            raise ValueError('Frame extends outside the compressed data')
        frame = data[offset:offset + compressed_size]
        raw = zstd.decompress(frame)
        if len(raw) != raw_size:
            raise ValueError('Decompressed frame size disagrees with seek table')
        frames.append((frame, raw, data[entry + 8:entry + entry_size]))
        offset += compressed_size
    if offset != table_offset:
        raise ValueError('Seek table does not account for every compressed byte')
    if not frames[0][1].startswith(b'BLENDER'):
        raise ValueError('Compressed data is not a Blender file')
    return frames, data[-9:]


def recompress(data: bytes, level: int = 19) -> bytes:
    frames, footer = read_frames(data)
    compressed_frames = []
    entries = []
    for original, raw, checksum in frames:
        # Preserve skippable frames and any frames already compressed better.
        frame = zstd.compress(raw, level=level) if raw else original
        if len(frame) >= len(original):
            frame = original
        if zstd.decompress(frame) != raw:
            raise ValueError('Recompression changed the decompressed Blender data')
        compressed_frames.append(frame)
        # Existing seek-table checksums remain valid for identical raw bytes.
        entries.append(struct.pack('<II', len(frame), len(raw)) + checksum)
    table = b''.join(entries) + footer
    result = b''.join(compressed_frames) + struct.pack('<II', TABLE_MAGIC, len(table)) + table
    checked, _ = read_frames(result)
    if any(before[1:] != after[1:] for before, after in zip(frames, checked, strict=True)):
        raise ValueError('Recompressed frames failed integrity verification')
    return result


def replace_file(path: Path, original: bytes, result: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(result)
        if path.read_bytes() != original:
            raise RuntimeError(f'{path} changed during compression; refusing to overwrite it')
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='*', type=Path, default=[LIBRARIES / f'{name}_nodes.blend' for name in ('h2amp', 'h4')])
    parser.add_argument('--level', type=int, choices=range(1, 23), default=19)
    parser.add_argument('--write', action='store_true', help='Replace files after validating identical decompressed data')
    args = parser.parse_args()
    for path in args.paths:
        original = path.read_bytes()
        result = recompress(original, args.level)
        frames, _ = read_frames(original)
        digest = hashlib.sha256()
        for _, raw, _ in frames:
            digest.update(raw)
        saved = len(original) - len(result)
        print(f'{path.name}: {len(original):,} -> {len(result):,} bytes '
              f'({saved / len(original):.1%} saved); raw SHA-256 {digest.hexdigest()}', flush=True)
        if args.write and saved:
            replace_file(path, original, result)


if __name__ == '__main__':
    main()

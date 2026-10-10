"""Private subprocess for legacy image codecs which may terminate on old data."""
from pathlib import Path
import json
import sys


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from granny_import.native import decode_native_texture
    encoded = sys.stdin.buffer.readline(65537)
    if len(encoded) > 65536 or not encoded.endswith(b'\n'):
        raise ValueError('Invalid image decoder request')
    header = json.loads(encoded)
    width, height = header['width'], header['height']
    if not 0 < width <= 32768 or not 0 < height <= 32768 or width * height * 4 > 256 * 1024 * 1024:
        raise ValueError('Invalid image dimensions')
    payload = sys.stdin.buffer.read(256 * 1024 * 1024 + 1)
    if not payload or len(payload) > 256 * 1024 * 1024:
        raise ValueError('Invalid image payload length')
    sys.stdout.buffer.write(decode_native_texture(header, payload).tobytes())


if __name__ == '__main__':
    main()

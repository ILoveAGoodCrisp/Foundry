"""Uncompressed RGBA TIFFs supported by the editing kits' TIFF readers."""
import struct
from io import BytesIO


def write_rgba_tiff(path, width, height, rgba):
    """Write 8-bit straight RGBA bytes in top-to-bottom row order."""
    encoded = rgba_tiff_bytes(width, height, rgba)
    with open(path, 'wb') as stream:
        stream.write(encoded)


def rgba_tiff_bytes(width, height, rgba):
    """Encode the canonical TIFF representation, also used to detect conflicts."""
    if width < 1 or height < 1 or len(rgba) != width * height * 4:
        raise ValueError('Invalid RGBA TIFF dimensions or pixel data')
    count = 11
    bits_offset = 8 + 2 + count * 12 + 4
    pixel_offset = bits_offset + 8
    fields = [(256, 4, 1, width), (257, 4, 1, height),
              (258, 3, 4, bits_offset), (259, 3, 1, 1), (262, 3, 1, 2),
              (273, 4, 1, pixel_offset), (277, 3, 1, 4), (278, 4, 1, height),
              (279, 4, 1, len(rgba)), (284, 3, 1, 1), (338, 3, 1, 2)]
    with BytesIO() as stream:
        stream.write(struct.pack('<2sHIH', b'II', 42, 8, count))
        for tag, kind, length, value in fields:
            stream.write(struct.pack('<HHII', tag, kind, length, value))
        stream.write(struct.pack('<I4H', 0, 8, 8, 8, 8))
        stream.write(rgba)
        return stream.getvalue()


def write_image_tiff(image, path):
    """Save a converted byte image without Blender's view transform or Deflate."""
    import numpy as np
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    rgba = np.rint(np.clip(pixels.reshape(height, width, 4), 0, 1) * 255).astype(np.uint8)
    write_rgba_tiff(path, width, height, rgba[::-1].tobytes())


def write_cube_tiff(image, path):
    """Repack an extracted DirectX cross into Tool's cube-slicer plate.

    Tool reads the middle row left-to-right, then the top-left and bottom-left
    cells, into the six DirectX storage faces (+X,-X,+Y,-Y,+Z,-Z).
    This is a lossless rearrangement of the original faces, not a lat-long bake.
    """
    import numpy as np
    width, height = image.size
    if width % 4 or height % 3 or width // 4 != height // 3:
        raise ValueError(f'{image.name}: expected a 4x3 cube cross, got {width}x{height}')
    size = width // 4
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    source = np.rint(np.clip(pixels.reshape(height, width, 4), 0, 1) * 255).astype(np.uint8)[::-1]
    plate = np.empty_like(source)
    plate[:] = (0, 0, 255, 255)
    source_cells = ((0, 1), (2, 1), (1, 0), (1, 2), (1, 1), (3, 1))
    target_cells = ((0, 1), (1, 1), (2, 1), (3, 1), (0, 0), (0, 2))
    for (sx, sy), (dx, dy) in zip(source_cells, target_cells):
        plate[dy*size:(dy+1)*size, dx*size:(dx+1)*size] = source[sy*size:(sy+1)*size, sx*size:(sx+1)*size]
    write_rgba_tiff(path, width, height, plate.tobytes())

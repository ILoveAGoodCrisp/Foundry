"""Portable raw pixel layouts and BC1/BC2/BC3 (S3TC) top-mip decoding."""
import numpy as np

from .container import count


def raw_pixels(payload, width, height, stride, layout):
    bpp = layout.get('BytesPerPixel')
    if not 1 <= bpp <= 8 or stride < width * bpp or len(payload) < (height - 1) * stride + width * bpp:
        raise ValueError('Invalid GR2 raw pixel layout or stride')
    raw = np.ndarray((height, width, bpp), dtype=np.uint8, buffer=payload,
                     strides=(stride, bpp, 1)).astype(np.uint64)
    packed = np.zeros((height, width), dtype=np.uint64)
    for byte in range(bpp):
        packed |= raw[:, :, byte] << (byte * 8)
    result = np.empty((height, width, 4), dtype=np.uint8)
    for channel, (shift, bits) in enumerate(zip(layout.get('ShiftForComponent'), layout.get('BitsForComponent'))):
        if not 0 <= bits <= 32 or shift < 0 or shift + bits > bpp * 8:
            raise ValueError('Invalid GR2 raw pixel component')
        if not bits:
            result[:, :, channel] = 255 if channel == 3 else 0
        else:
            mask = (1 << bits) - 1
            result[:, :, channel] = (((packed >> shift) & mask) * 255 // mask).astype(np.uint8)
    return result


def s3tc_pixels(payload, width, height, subformat):
    if subformat not in (0, 1, 2, 3):
        raise ValueError(f'Unsupported GR2 S3TC subformat {subformat}')
    bx, by = (width + 3) // 4, (height + 3) // 4
    block_size = 8 if subformat < 2 else 16
    if len(payload) < bx * by * block_size:
        raise ValueError('Truncated GR2 S3TC pixels')
    blocks = np.frombuffer(payload, dtype=np.uint8, count=bx * by * block_size).reshape(-1, block_size)
    color = blocks[:, -8:].astype(np.uint32)
    a, b = color[:, 0] + (color[:, 1] << 8), color[:, 2] + (color[:, 3] << 8)
    palette = np.zeros((len(blocks), 4, 4), dtype=np.uint32)
    for slot, value in enumerate((a, b)):
        r, g, bl = (value >> 11) & 31, (value >> 5) & 63, value & 31
        palette[:, slot, :3] = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (bl << 3) | (bl >> 2)), axis=1)
    palette[:, :, 3] = 255
    palette[:, 2, :3] = (2 * palette[:, 0, :3] + palette[:, 1, :3]) // 3
    palette[:, 3, :3] = (palette[:, 0, :3] + 2 * palette[:, 1, :3]) // 3
    if subformat < 2:
        transparent = a <= b
        palette[transparent, 2, :3] = (palette[transparent, 0, :3] + palette[transparent, 1, :3]) // 2
        palette[transparent, 3] = 0
    codes = color[:, 4] | (color[:, 5] << 8) | (color[:, 6] << 16) | (color[:, 7] << 24)
    selectors = (codes[:, None] >> (2 * np.arange(16, dtype=np.uint32))) & 3
    pixels = palette[np.arange(len(blocks))[:, None], selectors].astype(np.uint8)
    if subformat == 2:
        alpha = blocks[:, :8]
        pixels[:, 0::2, 3], pixels[:, 1::2, 3] = (alpha & 15) * 17, (alpha >> 4) * 17
    elif subformat == 3:
        alpha = np.zeros((len(blocks), 8), dtype=np.uint32)
        alpha[:, :2] = blocks[:, :2]
        long = alpha[:, 0] > alpha[:, 1]
        for i in range(2, 8):
            alpha[long, i] = ((8 - i) * alpha[long, 0] + (i - 1) * alpha[long, 1]) // 7
        for i in range(2, 6):
            alpha[~long, i] = ((6 - i) * alpha[~long, 0] + (i - 1) * alpha[~long, 1]) // 5
        alpha[~long, 7] = 255
        codes = np.zeros(len(blocks), dtype=np.uint64)
        for i in range(6):
            codes |= blocks[:, i + 2].astype(np.uint64) << (8 * i)
        selectors = (codes[:, None] >> (3 * np.arange(16, dtype=np.uint64))) & 7
        pixels[:, :, 3] = alpha[np.arange(len(blocks))[:, None], selectors]
    return pixels.reshape(by, bx, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(by * 4, bx * 4, 4)[:height, :width].copy()


def texture(record, decode=None):
    result = dict(name=record.get('FromFileName', ''), width=record.get('Width'), height=record.get('Height'),
                  texture_type=record.get('TextureType'), encoding=record.get('Encoding'),
                  sub_format=record.get('SubFormat'), props=record.owner.detach(record.get('ExtendedData')), images=[])
    try:
        width, height = count(result['width'], 32768), count(result['height'], 32768)
        images = record.get('Images', ())
        count(len(images), 256)
        count(width * height * len(images) * 4, 256 * 1024 * 1024)
        if images and (not width or not height):
            raise ValueError('Missing GR2 texture dimensions')
        for index, image in enumerate(images):
            mips = image.get('MIPLevels', ())
            count(len(mips), 32)
            if not mips:
                continue
            source = mips[0].get('PixelBytes')
            count(len(source), 256 * 1024 * 1024)
            payload = source.scalar().astype(np.uint8, copy=False).tobytes()
            if not payload:
                continue
            if result['encoding'] == 1:
                pixels = raw_pixels(payload, width, height, mips[0].get('Stride'), record.get('Layout'))
            elif result['encoding'] == 2:
                pixels = s3tc_pixels(payload, width, height, result['sub_format'])
            elif decode is not None:
                pixels = decode(record, payload, mips[0].get('Stride'))
            else:
                raise ValueError(f'Unsupported GR2 texture encoding {result["encoding"]}; embedded image was skipped')
            result['images'].append(dict(index=index, mip_levels=len(mips), pixels=pixels))
    except ValueError as error:
        result['error'] = str(error)
    return result

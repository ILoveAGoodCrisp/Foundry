"""Lossless RGBA preview texture serialization without a native codec."""
from dataclasses import dataclass

from .binary import BinaryWriteError


def validate_texture(texture):
    if texture.requested_encoding not in ('rgba', 'raw'):
        raise BinaryWriteError('Python preview textures require raw RGBA; S3TC/Bink compression is unsupported')
    if not texture.images:
        raise BinaryWriteError('Preview textures require at least one image')
    dimensions = {(image.width, image.height) for image in texture.images}
    if len(dimensions) != 1:
        raise BinaryWriteError('Texture images must have matching dimensions')
    for image in texture.images:
        if any(not isinstance(v, int) or not 0 < v < 2**31 for v in (image.width, image.height, image.stride, len(image.rgba))):
            raise BinaryWriteError('Texture dimensions/stride/pixel count must fit positive int32')


@dataclass(frozen=True, slots=True, eq=False)
class _Payload:
    value: object
    role: str


class TextureEmitter:
    def __init__(self, emitter, *, object_section=0, buffer_section=None):
        self.emitter, self.builder, self.registry = emitter, emitter.builder, emitter.registry
        self.object_section = object_section
        self.buffer_section = object_section if buffer_section is None else buffer_section
        self._owners, self._written = {}, set()

    def owner(self, value, role):
        key = (id(value), role)
        if key not in self._owners:
            self._owners[key] = _Payload(value, role)
        return self._owners[key]

    def offset(self, schema, field):
        return self.registry.layout(schema).field(field).offset

    def texture(self, texture):
        validate_texture(texture)
        header = self.emitter.reserve('Texture', owner=texture, section=self.object_section).block
        if header in self._written:
            return header.at()
        self._written.add(header)
        self.builder.reference(header.at(self.offset('Texture', 'FromFileName')),
            self.builder.string(texture.name, section=self.emitter.string_section))
        image = texture.images[0]
        # SDK ColorMap type 0, raw encoding 1. RGBA8888 in little-endian words.
        header.pack(self.offset('Texture', 'TextureType'), '<5i', 0, image.width, image.height, 1, 0)
        header.pack(self.offset('Texture', 'Layout'), '<9i', 4, 0, 8, 16, 24, 8, 8, 8, 8)
        offset = self.offset('Texture', 'Images')
        header.pack(offset, '<i', len(texture.images))
        images = self.emitter.reserve('TextureImage', owner=self.owner(texture.images, 'images'),
            count=len(texture.images), section=self.object_section)
        self.builder.reference(header.at(offset+4), images.item(0))
        if images.block not in self._written:
            self._written.add(images.block)
            for index, image in enumerate(texture.images):
                start = index*images.item_size
                images.block.pack(start, '<i', 1)
                mip = self.emitter.reserve('TextureMIPLevel', owner=self.owner(image, 'mip'), section=self.object_section).block
                self.builder.reference(images.block.at(start+4), mip.at())
                if mip in self._written:
                    continue
                self._written.add(mip)
                mip.pack(0, '<2i', image.stride, len(image.rgba))
                pixels = self.emitter.reserve('UInt8', owner=self.owner(image, 'pixels'), count=len(image.rgba), section=self.buffer_section)
                pixels.block.write(0, image.rgba)
                self.builder.reference(mip.at(8), pixels.item(0))
        return header.at()

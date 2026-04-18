from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import math
import struct

from mathutils import Euler, Matrix, Quaternion, Vector


class AnimationCodecType(IntEnum):
    NO_COMPRESSION = 0
    UNCOMPRESSED_STATIC = 1
    UNCOMPRESSED_ANIMATED = 2
    QUANTIZED_ROTATION_ONLY = 3
    BYTE_KEYFRAME_LIGHTLY_QUANTIZED = 4
    WORD_KEYFRAME_LIGHTLY_QUANTIZED = 5
    REVERSE_BYTE_KEYFRAME_LIGHTLY_QUANTIZED = 6
    REVERSE_WORD_KEYFRAME_LIGHTLY_QUANTIZED = 7
    BLEND_SCREEN = 8
    CURVE = 9
    REVISED_CURVE = 10
    SHARED_STATIC = 11

class FrameInfoType(IntEnum):
    NONE = 0
    DX_DY = 1
    DX_DY_DYAW = 2
    DX_DY_DZ_DYAW = 3
    DX_DY_DZ_DANGLE_AXIS = 4
    XYZ_ABSOLUTE = 5
    AUTO = 6

def _identity_quaternion() -> Quaternion:
    return Quaternion((1.0, 0.0, 0.0, 0.0))

def _zero_vector() -> Vector:
    return Vector((0.0, 0.0, 0.0))

def _normalize_quaternion(x: float, y: float, z: float, w: float) -> Quaternion:
    length = math.sqrt((w * w) + (x * x) + (y * y) + (z * z))
    if length <= 1e-8:
        return _identity_quaternion()
    inv = 1.0 / length
    return Quaternion((w * inv, x * inv, y * inv, z * inv))

class BinaryReader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def tell(self) -> int:
        return self.offset

    def seek(self, offset: int):
        if offset < 0 or offset > len(self.data):
            raise ValueError(f"Seek out of range: {offset}")
        self.offset = offset

    def skip(self, size: int):
        self.seek(self.offset + size)

    def _read(self, fmt: str):
        size = struct.calcsize(fmt)
        end = self.offset + size
        if end > len(self.data):
            raise ValueError("Unexpected end of animation resource data")
        values = struct.unpack_from(fmt, self.data, self.offset)
        self.offset = end
        return values[0] if len(values) == 1 else values

    def read_u8(self) -> int:
        return self._read("<B")

    def read_s16(self) -> int:
        return self._read("<h")

    def read_u16(self) -> int:
        return self._read("<H")

    def read_u32(self) -> int:
        return self._read("<I")

    def read_f32(self) -> float:
        return self._read("<f")


@dataclass
class DefaultAnimationNode:
    name: str
    parent_index: int
    translation: Vector
    rotation: Quaternion
    scale: float = 1.0


@dataclass
class FrameChannels:
    translations: list[Vector]
    rotations: list[Quaternion]
    scales: list[float]


@dataclass
class SharedStaticCodecData:
    rotations: list[tuple[int, int, int, int]]
    translations: list[Vector]
    scales: list[float]


@dataclass
class MovementData:
    frame_info_type: FrameInfoType
    translations: list[Vector]
    rotations: list[Quaternion]

@dataclass
class ExpandedAnimation:
    frame_count: int
    translations: list[list[Vector]]
    rotations: list[list[Quaternion]]
    scales: list[list[float]]
    translation_flags: list[bool]
    rotation_flags: list[bool]
    scale_flags: list[bool]

    @property
    def node_count(self) -> int:
        return len(self.rotations)

    def first_frame(self) -> FrameChannels:
        if self.frame_count < 1:
            return FrameChannels([], [], [])
        return FrameChannels(
            [self.translations[node_index][0].copy() for node_index in range(self.node_count)],
            [self.rotations[node_index][0].copy() for node_index in range(self.node_count)],
            [self.scales[node_index][0] for node_index in range(self.node_count)],
        )

    def frame_matrices(self) -> list[list[Matrix]]:
        frames: list[list[Matrix]] = []
        for frame_index in range(self.frame_count):
            frame: list[Matrix] = []
            for node_index in range(self.node_count):
                frame.append(
                    Matrix.LocRotScale(
                        self.translations[node_index][frame_index],
                        self.rotations[node_index][frame_index],
                        Vector.Fill(3, self.scales[node_index][frame_index]),
                    )
                )
            frames.append(frame)
        return frames


class CodecBase:
    def __init__(self, frame_count: int):
        self.frame_count = frame_count
        self.codec = AnimationCodecType.NO_COMPRESSION
        self.rotated_node_count = 0
        self.translated_node_count = 0
        self.scaled_node_count = 0
        self.error_value = 0.0
        self.compression_rate = 0.0
        self.rotation_data_offset = 0
        self.translation_data_offset = 0
        self.scale_data_offset = 0
        self.rotated_node_block_size = 0
        self.translated_node_block_size = 0
        self.scaled_node_block_size = 0
        self.rotation_keyframes: list[list[int]] = []
        self.translation_keyframes: list[list[int]] = []
        self.scale_keyframes: list[list[int]] = []
        self.rotations: list[list[Quaternion]] = []
        self.translations: list[list[Vector]] = []
        self.scales: list[list[float]] = []

    def read_header(self, reader: BinaryReader):
        self.codec = AnimationCodecType(reader.read_u8())
        self.rotated_node_count = reader.read_u8()
        self.translated_node_count = reader.read_u8()
        self.scaled_node_count = reader.read_u8()
        self.error_value = reader.read_f32()
        self.compression_rate = reader.read_f32() * 100.0

    def read(self, reader: BinaryReader):
        self.read_header(reader)


class UncompressedStaticDataCodec(CodecBase):
    def read(self, reader: BinaryReader):
        super().read(reader)
        self.translation_data_offset = reader.read_u32()
        self.scale_data_offset = reader.read_u32()
        self.rotated_node_block_size = reader.read_u32()
        self.translated_node_block_size = reader.read_u32()
        self.scaled_node_block_size = reader.read_u32()

        self.rotations = []
        for _ in range(self.rotated_node_count):
            x = reader.read_s16() / float(0x7FFF)
            y = reader.read_s16() / float(0x7FFF)
            z = reader.read_s16() / float(0x7FFF)
            w = reader.read_s16() / float(0x7FFF)
            self.rotations.append([_normalize_quaternion(x, y, z, w)])

        self.translations = []
        for _ in range(self.translated_node_count):
            self.translations.append(
                [Vector((reader.read_f32() * 100.0, reader.read_f32() * 100.0, reader.read_f32() * 100.0))]
            )

        self.scales = []
        for _ in range(self.scaled_node_count):
            self.scales.append([reader.read_f32()])


class SharedStaticDataCodec(UncompressedStaticDataCodec):
    def __init__(self, frame_count: int, shared_static_data: SharedStaticCodecData):
        super().__init__(frame_count)
        self.shared_static_data = shared_static_data

    def read(self, reader: BinaryReader):
        super(UncompressedStaticDataCodec, self).read(reader)
        self.translation_data_offset = reader.read_u32()
        self.scale_data_offset = reader.read_u32()
        self.rotated_node_block_size = reader.read_u32()
        self.translated_node_block_size = reader.read_u32()
        self.scaled_node_block_size = reader.read_u32()

        self.rotations = []
        for _ in range(self.rotated_node_count):
            block_index = reader.read_s16()
            if 0 <= block_index < len(self.shared_static_data.rotations):
                i, j, k, w = self.shared_static_data.rotations[block_index]
                quat = _normalize_quaternion(
                    i / float(0x7FFF),
                    j / float(0x7FFF),
                    k / float(0x7FFF),
                    w / float(0x7FFF),
                )
            else:
                quat = _identity_quaternion()
            self.rotations.append([quat])

        self.translations = []
        for _ in range(self.translated_node_count):
            block_index = reader.read_s16()
            if 0 <= block_index < len(self.shared_static_data.translations):
                value = self.shared_static_data.translations[block_index].copy()
                value *= 100.0
            else:
                value = _zero_vector()
            self.translations.append([value])

        self.scales = []
        for _ in range(self.scaled_node_count):
            block_index = reader.read_s16()
            scale = self.shared_static_data.scales[block_index] if 0 <= block_index < len(self.shared_static_data.scales) else 1.0
            self.scales.append([scale])


class QuantizedRotationOnlyCodec(CodecBase):
    def read(self, reader: BinaryReader):
        super().read(reader)
        self.translation_data_offset = reader.read_u32()
        self.scale_data_offset = reader.read_u32()
        self.rotated_node_block_size = reader.read_u32()
        self.translated_node_block_size = reader.read_u32()
        self.scaled_node_block_size = reader.read_u32()

        self.rotation_data_offset = reader.tell()
        self.translation_data_offset = self.rotation_data_offset + (self.rotated_node_block_size * self.rotated_node_count)
        self.scale_data_offset = self.translation_data_offset + (self.translated_node_block_size * self.translated_node_count)
        all_frames = list(range(self.frame_count))
        self.rotation_keyframes = [all_frames[:] for _ in range(self.rotated_node_count)]
        self.translation_keyframes = [all_frames[:] for _ in range(self.translated_node_count)]
        self.scale_keyframes = [all_frames[:] for _ in range(self.scaled_node_count)]

        reader.seek(self.rotation_data_offset)
        self.rotations = []
        for _ in range(self.rotated_node_count):
            node_rotations: list[Quaternion] = []
            for _frame in range(self.frame_count):
                x = reader.read_s16() / float(0x7FFF)
                y = reader.read_s16() / float(0x7FFF)
                z = reader.read_s16() / float(0x7FFF)
                w = reader.read_s16() / float(0x7FFF)
                node_rotations.append(_normalize_quaternion(x, y, z, w))
            self.rotations.append(node_rotations)

        reader.seek(self.translation_data_offset)
        self.translations = []
        for _ in range(self.translated_node_count):
            node_translations: list[Vector] = []
            for _frame in range(self.frame_count):
                node_translations.append(
                    Vector((reader.read_f32() * 100.0, reader.read_f32() * 100.0, reader.read_f32() * 100.0))
                )
            self.translations.append(node_translations)

        reader.seek(self.scale_data_offset)
        self.scales = []
        for _ in range(self.scaled_node_count):
            node_scales: list[float] = []
            for _frame in range(self.frame_count):
                node_scales.append(reader.read_f32())
            self.scales.append(node_scales)


class BlendScreenCodec(QuantizedRotationOnlyCodec):
    def read(self, reader: BinaryReader):
        super(QuantizedRotationOnlyCodec, self).read(reader)
        self.translation_data_offset = reader.read_u32()
        self.scale_data_offset = reader.read_u32()
        self.rotated_node_block_size = reader.read_u32()
        self.translated_node_block_size = reader.read_u32()
        self.scaled_node_block_size = reader.read_u32()

        self.rotation_data_offset = reader.tell()
        self.translation_data_offset = self.rotation_data_offset + (self.rotated_node_block_size * self.rotated_node_count)
        self.scale_data_offset = self.translation_data_offset + (self.translated_node_block_size * self.translated_node_count)
        all_frames = list(range(self.frame_count))
        self.rotation_keyframes = [all_frames[:] for _ in range(self.rotated_node_count)]
        self.translation_keyframes = [all_frames[:] for _ in range(self.translated_node_count)]
        self.scale_keyframes = [all_frames[:] for _ in range(self.scaled_node_count)]

        reader.seek(self.rotation_data_offset)
        self.rotations = []
        for _ in range(self.rotated_node_count):
            node_rotations: list[Quaternion] = []
            for _frame in range(self.frame_count):
                x = reader.read_f32()
                y = reader.read_f32()
                z = reader.read_f32()
                w = reader.read_f32()
                node_rotations.append(_normalize_quaternion(x, y, z, w))
            self.rotations.append(node_rotations)

        reader.seek(self.translation_data_offset)
        self.translations = []
        for _ in range(self.translated_node_count):
            node_translations: list[Vector] = []
            for _frame in range(self.frame_count):
                node_translations.append(
                    Vector((reader.read_f32() * 100.0, reader.read_f32() * 100.0, reader.read_f32() * 100.0))
                )
            self.translations.append(node_translations)

        reader.seek(self.scale_data_offset)
        self.scales = []
        for _ in range(self.scaled_node_count):
            node_scales: list[float] = []
            for _frame in range(self.frame_count):
                node_scales.append(reader.read_f32())
            self.scales.append(node_scales)


class KeyframeLightlyQuantizedCodec(CodecBase):
    def __init__(self, frame_count: int, key_size: int):
        super().__init__(frame_count)
        self.key_size = key_size

    def read(self, reader: BinaryReader):
        position = reader.tell()
        super().read(reader)
        reader.read_u32()
        reader.read_u32()
        reader.read_u32()
        reader.read_u32()
        reader.read_u32()
        self.rotation_data_offset = position + reader.read_u32()
        self.translation_data_offset = position + reader.read_u32()
        self.scale_data_offset = position + reader.read_u32()
        reader.read_u32()

        for _ in range(self.rotated_node_count):
            reader.read_u32()
        for _ in range(self.translated_node_count):
            reader.read_u32()
        for _ in range(self.scaled_node_count):
            reader.read_u32()

        self.rotation_keyframes = [self._read_keyframe_data(reader) for _ in range(self.rotated_node_count)]
        self.translation_keyframes = [self._read_keyframe_data(reader) for _ in range(self.translated_node_count)]
        self.scale_keyframes = [self._read_keyframe_data(reader) for _ in range(self.scaled_node_count)]

        reader.seek(self.rotation_data_offset)
        self.rotations = []
        for keyframes in self.rotation_keyframes:
            node_rotations: list[Quaternion] = []
            for _ in range(len(keyframes)):
                x = reader.read_s16() / float(0x7FFF)
                y = reader.read_s16() / float(0x7FFF)
                z = reader.read_s16() / float(0x7FFF)
                w = reader.read_s16() / float(0x7FFF)
                node_rotations.append(_normalize_quaternion(x, y, z, w))
            self.rotations.append(node_rotations)

        reader.seek(self.translation_data_offset)
        self.translations = []
        for keyframes in self.translation_keyframes:
            node_translations: list[Vector] = []
            for _ in range(len(keyframes)):
                node_translations.append(
                    Vector((reader.read_f32() * 100.0, reader.read_f32() * 100.0, reader.read_f32() * 100.0))
                )
            self.translations.append(node_translations)

        reader.seek(self.scale_data_offset)
        self.scales = []
        for keyframes in self.scale_keyframes:
            node_scales: list[float] = []
            for _ in range(len(keyframes)):
                node_scales.append(reader.read_f32())
            self.scales.append(node_scales)

    def _read_keyframe_data(self, reader: BinaryReader) -> list[int]:
        keyframes: list[int] = []
        while True:
            value = reader.read_u8() if self.key_size == 1 else reader.read_u16()
            if not keyframes or (keyframes[-1] <= value <= self.frame_count):
                keyframes.append(value)
                continue
            reader.skip(-self.key_size)
            return keyframes


class ReverseKeyframeLightlyQuantizedCodec(KeyframeLightlyQuantizedCodec):
    def read(self, reader: BinaryReader):
        super().read(reader)
        self.rotation_keyframes.reverse()
        self.translation_keyframes.reverse()
        self.scale_keyframes.reverse()
        self.rotations.reverse()
        self.translations.reverse()
        self.scales.reverse()


class CurveCodec(CodecBase):
    def __init__(self, frame_count: int):
        super().__init__(frame_count)
        self.payload_data_offset = 0
        self.total_compressed_size = 0

    def read(self, reader: BinaryReader):
        position = reader.tell()
        super().read(reader)
        self.translation_data_offset = reader.read_u32()
        self.scale_data_offset = reader.read_u32()
        self.payload_data_offset = reader.read_u32()
        self.total_compressed_size = reader.read_u32()
        reader.read_u32()

        self.rotation_keyframes = [list(range(self.frame_count)) for _ in range(self.rotated_node_count)]
        self.translation_keyframes = [list(range(self.frame_count)) for _ in range(self.translated_node_count)]
        self.scale_keyframes = [list(range(self.frame_count)) for _ in range(self.scaled_node_count)]
        self.rotations = [[] for _ in range(self.rotated_node_count)]
        self.translations = [[] for _ in range(self.translated_node_count)]
        self.scales = [[] for _ in range(self.scaled_node_count)]

        rotation_offsets = [reader.read_u32() for _ in range(self.rotated_node_count)]
        for node_index, node_offset in enumerate(rotation_offsets):
            reader.seek(position + self.payload_data_offset + node_offset)
            reader.read_u16()
            key_count = reader.read_u16()
            flags = reader.read_u8()
            reader.read_u8()
            reader.read_s16()
            keyframes = self._read_curve_keyframe_data(key_count, reader) if (flags & 1) == 0 else []
            self.rotations[node_index] = self._read_curve_rotations(reader, keyframes, flags)

        reader.seek(position + self.payload_data_offset + self.translation_data_offset)
        translation_offsets = [reader.read_u32() for _ in range(self.translated_node_count)]
        for node_index, node_offset in enumerate(translation_offsets):
            reader.seek(position + self.payload_data_offset + node_offset)
            reader.read_u16()
            key_count = reader.read_u16()
            flags = reader.read_u8()
            reader.read_u8()
            reader.read_u16()
            offset_x = reader.read_f32()
            offset_y = reader.read_f32()
            offset_z = reader.read_f32()
            scale = reader.read_f32()
            keyframes = self._read_curve_keyframe_data(key_count, reader) if (flags & 1) == 0 else []
            self.translations[node_index] = self._read_curve_translations(
                reader,
                keyframes,
                flags,
                offset_x,
                offset_y,
                offset_z,
                scale,
                True,
            )

        reader.seek(position + self.payload_data_offset + self.scale_data_offset)
        scale_offsets = [reader.read_u32() for _ in range(self.scaled_node_count)]
        for node_index, node_offset in enumerate(scale_offsets):
            reader.seek(position + self.payload_data_offset + node_offset)
            reader.read_u16()
            key_count = reader.read_u16()
            flags = reader.read_u8()
            reader.read_u8()
            reader.read_u16()
            offset = reader.read_f32()
            scale = reader.read_f32()
            keyframes = self._read_curve_keyframe_data(key_count, reader) if (flags & 1) == 0 else []
            self.scales[node_index] = self._read_curve_scales(reader, keyframes, flags, offset, scale)

        reader.seek(position + self.total_compressed_size)

    def _read_curve_keyframe_data(self, key_count: int, reader: BinaryReader) -> list[int]:
        keyframes = [0]
        total = 0
        for _ in range(key_count):
            total += reader.read_u8()
            keyframes.append(total)
        return keyframes

    def _decompress_quat(self, i: float, j: float, w: float) -> Quaternion:
        k = math.sqrt(max(1.0 - (i * i) - (j * j), 0.0))
        if w < 0.0:
            k *= -1.0
        w = (abs(w) * 2.0) - 1.0
        scale = math.sqrt(max(1.0 - (w * w), 0.0))
        return _normalize_quaternion(i * scale, j * scale, k * scale, w)

    def _curve_tangent_component(self, tangent_component: int, p1: float, p2: float) -> float:
        tangent = tangent_component / 7.0
        return abs(tangent) * (tangent * 0.300000011920929) + (p2 - p1)

    def _curve_position_scalar(self, time: float, tangent_1: float, tangent_2: float, p1: float, p2: float) -> float:
        term_1 = (2.0 * (time ** 3.0)) - (3.0 * (time ** 2.0)) + 1.0
        term_2 = (time ** 3.0) - (2.0 * (time ** 2.0)) + time
        term_3 = (3.0 * (time ** 2.0)) - (2.0 * (time ** 3.0))
        term_4 = (time ** 3.0) - (time ** 2.0)
        return (term_1 * p1) + (term_2 * tangent_1) + (term_3 * p2) + (term_4 * tangent_2)

    def _curve_tangent_quat(
        self, i_component: int, j_component: int, k_component: int, w_component: int, p1: Quaternion, p2: Quaternion
    ) -> tuple[float, float, float, float]:
        return (
            self._curve_tangent_component(i_component, p1.x, p2.x),
            self._curve_tangent_component(j_component, p1.y, p2.y),
            self._curve_tangent_component(k_component, p1.z, p2.z),
            self._curve_tangent_component(w_component, p1.w, p2.w),
        )

    def _curve_tangent_vec(self, x_component: int, y_component: int, z_component: int, p1: Vector, p2: Vector) -> Vector:
        return Vector(
            (
                self._curve_tangent_component(x_component, p1.x, p2.x),
                self._curve_tangent_component(y_component, p1.y, p2.y),
                self._curve_tangent_component(z_component, p1.z, p2.z),
            )
        )

    def _curve_position_quat(
        self, time: float, tangent_1: tuple[float, float, float, float], tangent_2: tuple[float, float, float, float], p1: Quaternion, p2: Quaternion
    ) -> Quaternion:
        return _normalize_quaternion(
            self._curve_position_scalar(time, tangent_1[0], tangent_2[0], p1.x, p2.x),
            self._curve_position_scalar(time, tangent_1[1], tangent_2[1], p1.y, p2.y),
            self._curve_position_scalar(time, tangent_1[2], tangent_2[2], p1.z, p2.z),
            self._curve_position_scalar(time, tangent_1[3], tangent_2[3], p1.w, p2.w),
        )

    def _curve_position_vec(self, time: float, tangent_1: Vector, tangent_2: Vector, p1: Vector, p2: Vector) -> Vector:
        return Vector(
            (
                self._curve_position_scalar(time, tangent_1.x, tangent_2.x, p1.x, p2.x),
                self._curve_position_scalar(time, tangent_1.y, tangent_2.y, p1.y, p2.y),
                self._curve_position_scalar(time, tangent_1.z, tangent_2.z, p1.z, p2.z),
            )
        )

    def _read_curve_rotations(self, reader: BinaryReader, keyframes: list[int], flags: int) -> list[Quaternion]:
        values: list[Quaternion] = []
        p1 = _identity_quaternion()
        p2 = _identity_quaternion()
        tangent_bytes = (0, 0, 0, 0)
        current_keyframe = 0
        keyframe_index = 0
        next_keyframe = 0
        for frame_index in range(self.frame_count):
            if flags & 1:
                quat = self._decompress_quat(
                    reader.read_s16() / float(0x7FFF),
                    reader.read_s16() / float(0x7FFF),
                    reader.read_s16() / float(0x7FFF),
                )
            else:
                if keyframes[keyframe_index] == frame_index and frame_index < self.frame_count - 1:
                    i1 = reader.read_s16() / float(0x7FFF)
                    j1 = reader.read_s16() / float(0x7FFF)
                    w1 = reader.read_s16() / float(0x7FFF)
                    tangent_bytes = (reader.read_u8(), reader.read_u8(), reader.read_u8(), reader.read_u8())
                    i2 = reader.read_s16() / float(0x7FFF)
                    j2 = reader.read_s16() / float(0x7FFF)
                    w2 = reader.read_s16() / float(0x7FFF)
                    p1 = self._decompress_quat(i1, j1, w1)
                    p2 = self._decompress_quat(i2, j2, w2)
                    current_keyframe = keyframes[keyframe_index]
                    next_keyframe = keyframes[keyframe_index + 1]
                    keyframe_index += 1
                    reader.skip(-6)
                tangent_1 = self._curve_tangent_quat(
                    (tangent_bytes[0] >> 4) - 7,
                    (tangent_bytes[1] >> 4) - 7,
                    (tangent_bytes[2] >> 4) - 7,
                    (tangent_bytes[3] >> 4) - 7,
                    p1,
                    p2,
                )
                tangent_2 = self._curve_tangent_quat(
                    (tangent_bytes[0] & 15) - 7,
                    (tangent_bytes[1] & 15) - 7,
                    (tangent_bytes[2] & 15) - 7,
                    (tangent_bytes[3] & 15) - 7,
                    p1,
                    p2,
                )
                quat = self._curve_position_quat(
                    (frame_index - current_keyframe) / float(next_keyframe - current_keyframe),
                    tangent_1,
                    tangent_2,
                    p1,
                    p2,
                )
            values.append(quat)
        return values

    def _read_curve_translations(
        self,
        reader: BinaryReader,
        keyframes: list[int],
        flags: int,
        offset_x: float,
        offset_y: float,
        offset_z: float,
        scale: float,
        apply_scale_100: bool,
    ) -> list[Vector]:
        values: list[Vector] = []
        p1 = _zero_vector()
        p2 = _zero_vector()
        tangent_bytes = (0, 0, 0)
        current_keyframe = 0
        keyframe_index = 0
        next_keyframe = 0
        for frame_index in range(self.frame_count):
            if flags & 1:
                value = Vector(
                    (
                        reader.read_s16() / float(0x7FFF),
                        reader.read_s16() / float(0x7FFF),
                        reader.read_s16() / float(0x7FFF),
                    )
                )
            else:
                if keyframes[keyframe_index] == frame_index and frame_index < self.frame_count - 1:
                    p1 = Vector(
                        (
                            reader.read_s16() / float(0x7FFF),
                            reader.read_s16() / float(0x7FFF),
                            reader.read_s16() / float(0x7FFF),
                        )
                    )
                    tangent_bytes = (reader.read_u8(), reader.read_u8(), reader.read_u8())
                    p2 = Vector(
                        (
                            reader.read_s16() / float(0x7FFF),
                            reader.read_s16() / float(0x7FFF),
                            reader.read_s16() / float(0x7FFF),
                        )
                    )
                    current_keyframe = keyframes[keyframe_index]
                    next_keyframe = keyframes[keyframe_index + 1]
                    keyframe_index += 1
                    reader.skip(-6)
                tangent_1 = self._curve_tangent_vec((tangent_bytes[0] >> 4) - 7, (tangent_bytes[1] >> 4) - 7, (tangent_bytes[2] >> 4) - 7, p1, p2)
                tangent_2 = self._curve_tangent_vec((tangent_bytes[0] & 15) - 7, (tangent_bytes[1] & 15) - 7, (tangent_bytes[2] & 15) - 7, p1, p2)
                value = self._curve_position_vec(
                    (frame_index - current_keyframe) / float(next_keyframe - current_keyframe),
                    tangent_1,
                    tangent_2,
                    p1,
                    p2,
                )
            value.x = (scale * value.x) + offset_x
            value.y = (scale * value.y) + offset_y
            value.z = (scale * value.z) + offset_z
            if apply_scale_100:
                value *= 100.0
            values.append(value)
        return values

    def _read_curve_scales(self, reader: BinaryReader, keyframes: list[int], flags: int, offset: float, scale: float) -> list[float]:
        values: list[float] = []
        p1 = 0.0
        p2 = 0.0
        tangent_byte = 0
        current_keyframe = 0
        keyframe_index = 0
        next_keyframe = 0
        for frame_index in range(self.frame_count):
            if flags & 1:
                value = reader.read_s16() / float(0x7FFF)
            else:
                if keyframes[keyframe_index] == frame_index and frame_index < self.frame_count - 1:
                    p1 = reader.read_s16() / float(0x7FFF)
                    tangent_byte = reader.read_u8()
                    p2 = reader.read_s16() / float(0x7FFF)
                    current_keyframe = keyframes[keyframe_index]
                    next_keyframe = keyframes[keyframe_index + 1]
                    keyframe_index += 1
                    reader.skip(-2)
                tangent_1 = self._curve_tangent_component((tangent_byte >> 4) - 7, p1, p2)
                tangent_2 = self._curve_tangent_component((tangent_byte & 15) - 7, p1, p2)
                value = self._curve_position_scalar(
                    (frame_index - current_keyframe) / float(next_keyframe - current_keyframe),
                    tangent_1,
                    tangent_2,
                    p1,
                    p2,
                )
            values.append((value * scale) + offset)
        return values


class RevisedCurveCodec(CurveCodec):
    def _decompress_revised_quat(self, v3: int, v4: int, v5: int) -> Quaternion:
        i = ((float(v3 & 0xFFFE) / float(0x7FFF)) * 0.70710677)
        j = ((float(v4 & 0xFFFE) / float(0x7FFF)) * 0.70710677)
        k = ((float(v5 & 0xFFFE) / float(0x7FFF)) * 0.70710677)
        missing = math.sqrt(max(0.0, 1.0 - ((j * j) + (i * i) + (k * k))))
        if v3 & 1:
            missing = -missing
        component_index = (v5 & 1) | (2 * (v4 & 1))
        output = [0.0, 0.0, 0.0, 0.0]
        output[(component_index + 1) & 3] = i
        output[(component_index - 2) & 3] = j
        output[(component_index - 1) & 3] = k
        output[component_index] = missing
        return _normalize_quaternion(output[0], output[1], output[2], output[3])

    def _read_curve_rotations(self, reader: BinaryReader, keyframes: list[int], flags: int) -> list[Quaternion]:
        values: list[Quaternion] = []
        p1 = _identity_quaternion()
        p2 = _identity_quaternion()
        tangent_bytes = (0, 0, 0, 0)
        current_keyframe = 0
        keyframe_index = 0
        next_keyframe = 0
        for frame_index in range(self.frame_count):
            if flags & 1:
                quat = self._decompress_revised_quat(reader.read_s16(), reader.read_s16(), reader.read_s16())
            else:
                if keyframes[keyframe_index] == frame_index and frame_index < self.frame_count - 1:
                    p1 = self._decompress_revised_quat(reader.read_s16(), reader.read_s16(), reader.read_s16())
                    tangent_bytes = (reader.read_u8(), reader.read_u8(), reader.read_u8(), reader.read_u8())
                    p2 = self._decompress_revised_quat(reader.read_s16(), reader.read_s16(), reader.read_s16())
                    current_keyframe = keyframes[keyframe_index]
                    next_keyframe = keyframes[keyframe_index + 1]
                    keyframe_index += 1
                    reader.skip(-6)
                tangent_1 = self._curve_tangent_quat(
                    (tangent_bytes[0] >> 4) - 7,
                    (tangent_bytes[1] >> 4) - 7,
                    (tangent_bytes[2] >> 4) - 7,
                    (tangent_bytes[3] >> 4) - 7,
                    p1,
                    p2,
                )
                tangent_2 = self._curve_tangent_quat(
                    (tangent_bytes[0] & 15) - 7,
                    (tangent_bytes[1] & 15) - 7,
                    (tangent_bytes[2] & 15) - 7,
                    (tangent_bytes[3] & 15) - 7,
                    p1,
                    p2,
                )
                quat = self._curve_position_quat(
                    (frame_index - current_keyframe) / float(next_keyframe - current_keyframe),
                    tangent_1,
                    tangent_2,
                    p1,
                    p2,
                )
            values.append(quat)
        return values

    def _read_curve_translations(
        self,
        reader: BinaryReader,
        keyframes: list[int],
        flags: int,
        offset_x: float,
        offset_y: float,
        offset_z: float,
        scale: float,
        apply_scale_100: bool,
    ) -> list[Vector]:
        return super()._read_curve_translations(reader, keyframes, flags, offset_x, offset_y, offset_z, scale, False)


@dataclass
class AnimationResourceData:
    frame_count: int
    node_count: int
    node_list_checksum: int
    frame_info_type: FrameInfoType
    static_flags_size: int
    animated_flags_size: int
    static_data_size: int
    movement_data_size: int = 0
    shared_static_data_size: int = 0
    static_data: CodecBase | None = None
    animation_data: CodecBase | None = None
    static_rotated_node_flags: list[bool] | None = None
    static_translated_node_flags: list[bool] | None = None
    static_scaled_node_flags: list[bool] | None = None
    animated_rotated_node_flags: list[bool] | None = None
    animated_translated_node_flags: list[bool] | None = None
    animated_scaled_node_flags: list[bool] | None = None
    static_codec_size: int = 0
    animated_codec_size: int = 0
    debug_name: str = ""
    movement_data: MovementData | None = None

    def read(self, reader: BinaryReader):
        resource_start = reader.tell()
        while self.animation_data is None:
            codec_offset = reader.tell()
            codec = AnimationCodecType(reader.read_u8())
            reader.skip(-1)
            if codec == AnimationCodecType.UNCOMPRESSED_STATIC:
                self.static_data = UncompressedStaticDataCodec(self.frame_count)
                self.static_data.read(reader)

                target_offset = self.static_codec_size or self.static_data_size
                if target_offset <= codec_offset:
                    label = f" for {self.debug_name}" if self.debug_name else ""
                    raise ValueError(
                        f"Native animation static codec did not advance{label} "
                        f"(codec_offset={codec_offset}, target_offset={target_offset})"
                    )

                reader.seek(resource_start + target_offset)
                continue
            if codec == AnimationCodecType.QUANTIZED_ROTATION_ONLY:
                self.animation_data = QuantizedRotationOnlyCodec(self.frame_count)
                self.animation_data.read(reader)
            elif codec == AnimationCodecType.BYTE_KEYFRAME_LIGHTLY_QUANTIZED:
                self.animation_data = KeyframeLightlyQuantizedCodec(self.frame_count, 1)
                self.animation_data.read(reader)
            elif codec == AnimationCodecType.WORD_KEYFRAME_LIGHTLY_QUANTIZED:
                self.animation_data = KeyframeLightlyQuantizedCodec(self.frame_count, 2)
                self.animation_data.read(reader)
            elif codec == AnimationCodecType.REVERSE_BYTE_KEYFRAME_LIGHTLY_QUANTIZED:
                self.animation_data = ReverseKeyframeLightlyQuantizedCodec(self.frame_count, 1)
                self.animation_data.read(reader)
            elif codec == AnimationCodecType.REVERSE_WORD_KEYFRAME_LIGHTLY_QUANTIZED:
                self.animation_data = ReverseKeyframeLightlyQuantizedCodec(self.frame_count, 2)
                self.animation_data.read(reader)
            elif codec == AnimationCodecType.BLEND_SCREEN:
                self.animation_data = BlendScreenCodec(self.frame_count)
                self.animation_data.read(reader)
            elif codec == AnimationCodecType.CURVE:
                self.animation_data = CurveCodec(self.frame_count)
                self.animation_data.read(reader)
            elif codec == AnimationCodecType.REVISED_CURVE:
                self.animation_data = RevisedCurveCodec(self.frame_count)
                self.animation_data.read(reader)
            else:
                raise ValueError(f"Unsupported animation codec: {codec.name}")

            if self.animated_codec_size:
                expected_end = resource_start + self.static_codec_size + self.animated_codec_size
                if expected_end > reader.tell():
                    reader.seek(expected_end)
                elif expected_end < reader.tell():
                    label = f" for {self.debug_name}" if self.debug_name else ""
                    raise ValueError(
                        f"Native animation codec read past expected section end{label} "
                        f"(expected_end={expected_end}, actual={reader.tell()})"
                    )

        flag_word_count = (self.node_count + 31) // 32
        if self.static_flags_size:
            self.static_rotated_node_flags = _bit_array_from_ints([reader.read_u32() for _ in range(flag_word_count)], self.node_count)
            self.static_translated_node_flags = _bit_array_from_ints([reader.read_u32() for _ in range(flag_word_count)], self.node_count)
            self.static_scaled_node_flags = _bit_array_from_ints([reader.read_u32() for _ in range(flag_word_count)], self.node_count)
        else:
            self.static_rotated_node_flags = [False] * self.node_count
            self.static_translated_node_flags = [False] * self.node_count
            self.static_scaled_node_flags = [False] * self.node_count

        if self.animated_flags_size:
            self.animated_rotated_node_flags = _bit_array_from_ints([reader.read_u32() for _ in range(flag_word_count)], self.node_count)
            self.animated_translated_node_flags = _bit_array_from_ints([reader.read_u32() for _ in range(flag_word_count)], self.node_count)
            self.animated_scaled_node_flags = _bit_array_from_ints([reader.read_u32() for _ in range(flag_word_count)], self.node_count)
        else:
            self.animated_rotated_node_flags = [False] * self.node_count
            self.animated_translated_node_flags = [False] * self.node_count
            self.animated_scaled_node_flags = [False] * self.node_count

        if self.frame_info_type != FrameInfoType.NONE:
            self.movement_data = _read_movement_data(reader, self.frame_info_type, self.frame_count)


def _read_flag_triplet(reader: BinaryReader, total_size: int, node_count: int) -> tuple[list[bool], list[bool], list[bool]]:
    length = total_size // 3 // 4
    first = [reader.read_u32() for _ in range(length)]
    second = [reader.read_u32() for _ in range(length)]
    third = [reader.read_u32() for _ in range(length)]
    return (
        _bit_array_from_ints(first, node_count),
        _bit_array_from_ints(second, node_count),
        _bit_array_from_ints(third, node_count),
    )


def _bit_array_from_ints(values: list[int], count: int) -> list[bool]:
    result: list[bool] = []
    for value in values:
        for bit in range(32):
            result.append(bool(value & (1 << bit)))
    if len(result) < count:
        result.extend([False] * (count - len(result)))
    return result[:count]

def _angle_axis_vector_to_quaternion(v: Vector) -> Quaternion:
    angle = v.length
    if angle <= 1e-8:
        return _identity_quaternion()

    axis = v / angle
    return Quaternion(axis, angle)


def _yaw_quaternion(yaw: float) -> Quaternion:
    return Euler((0.0, 0.0, yaw)).to_quaternion()


def _read_movement_data(reader: BinaryReader, frame_info_type: FrameInfoType, frame_count: int) -> MovementData:
    translations: list[Vector] = []
    rotations: list[Quaternion] = []

    for _ in range(frame_count):
        dx = 0.0
        dy = 0.0
        dz = 0.0
        delta_rotation = _identity_quaternion()
        
        match frame_info_type:
            case FrameInfoType.DX_DY:
                dx = reader.read_f32() * 100.0
                dy = reader.read_f32() * 100.0
            case FrameInfoType.DX_DY_DYAW:
                dx = reader.read_f32() * 100.0
                dy = reader.read_f32() * 100.0
                delta_yaw = reader.read_f32()
                delta_rotation = _yaw_quaternion(delta_yaw)
            case FrameInfoType.DX_DY_DZ_DYAW:
                dx = reader.read_f32() * 100.0
                dy = reader.read_f32() * 100.0
                dz = reader.read_f32() * 100.0
                delta_yaw = reader.read_f32()
                delta_rotation = _yaw_quaternion(delta_yaw)
            case FrameInfoType.DX_DY_DZ_DYAW:
                dx = reader.read_f32() * 100.0
                dy = reader.read_f32() * 100.0
                dz = reader.read_f32() * 100.0
                delta_yaw = reader.read_f32()
                delta_rotation = _yaw_quaternion(delta_yaw)
            case FrameInfoType.DX_DY_DZ_DANGLE_AXIS:
                dx = reader.read_f32() * 100.0
                dy = reader.read_f32() * 100.0
                dz = reader.read_f32() * 100.0

                angle_axis = Vector((reader.read_f32(), reader.read_f32(), reader.read_f32()))
                delta_rotation = _angle_axis_vector_to_quaternion(angle_axis)
            case FrameInfoType.XYZ_ABSOLUTE:
                dx = reader.read_f32() * 100.0
                dy = reader.read_f32() * 100.0
                dz = reader.read_f32() * 100.0
            case FrameInfoType.NONE:
                pass
            case _:
                raise ValueError(f"Unsupported native movement data type: {frame_info_type.name}")

        translations.append(Vector((dx, dy, dz)))
        rotations.append(delta_rotation)

    return MovementData(
        frame_info_type=frame_info_type,
        translations=translations,
        rotations=rotations,
    )

def apply_shared_static_codec(
    resource_data: AnimationResourceData, data: bytes, shared_static: SharedStaticCodecData
) -> AnimationResourceData:
    if resource_data.shared_static_data_size <= 0:
        return resource_data
    reader = BinaryReader(data)
    reader.seek(len(data) - resource_data.shared_static_data_size)
    codec = SharedStaticDataCodec(resource_data.frame_count, shared_static)
    codec.read(reader)
    resource_data.static_data = codec
    return resource_data


def apply_movement_data(animation: ExpandedAnimation, movement_data: MovementData | None) -> ExpandedAnimation:
    if movement_data is None:
        return animation

    if not movement_data.translations:
        return animation

    accumulated_translation = _zero_vector()
    accumulated_rotation = _identity_quaternion()

    frame_limit = min(animation.frame_count, len(movement_data.translations))

    for frame_index in range(frame_limit):
        local_delta_translation = movement_data.translations[frame_index].copy()
        local_delta_rotation = movement_data.rotations[frame_index].copy()

        if movement_data.frame_info_type == FrameInfoType.XYZ_ABSOLUTE:
            accumulated_translation = local_delta_translation
        else:
            world_delta_translation = local_delta_translation.copy()
            world_delta_translation.rotate(accumulated_rotation)
            accumulated_translation += world_delta_translation

        animation.translations[0][frame_index] = (
            animation.translations[0][frame_index].copy() + accumulated_translation
        )
        animation.translation_flags[0] = True

        accumulated_rotation = (accumulated_rotation @ local_delta_rotation).normalized()

        if movement_data.frame_info_type in (
            FrameInfoType.DX_DY_DYAW,
            FrameInfoType.DX_DY_DZ_DYAW,
            FrameInfoType.DX_DY_DZ_DANGLE_AXIS,
        ):
            combined_rotation = accumulated_rotation.copy()
            combined_rotation.rotate(animation.rotations[0][frame_index])
            animation.rotations[0][frame_index] = combined_rotation
            animation.rotation_flags[0] = True

    return animation


def default_frame_channels(default_nodes: list[DefaultAnimationNode]) -> FrameChannels:
    return FrameChannels(
        [node.translation.copy() for node in default_nodes],
        [node.rotation.copy() for node in default_nodes],
        [node.scale for node in default_nodes],
    )


def _expand_track(values: list, keyframes: list[int], frame_count: int, default_value, interpolator):
    if not values:
        return [default_value for _ in range(frame_count)]
    if not keyframes:
        return [values[0] for _ in range(frame_count)]
    if len(values) == frame_count and len(keyframes) == frame_count:
        return values[:]
    expanded = []
    key_index = 0
    for frame_index in range(frame_count):
        if frame_index <= keyframes[0]:
            expanded.append(values[0])
            continue
        if frame_index >= keyframes[-1]:
            expanded.append(values[-1])
            continue
        while key_index < len(keyframes) - 2 and frame_index > keyframes[key_index + 1]:
            key_index += 1
        if keyframes[key_index] == frame_index:
            expanded.append(values[key_index])
            continue
        previous_frame = keyframes[key_index]
        next_frame = keyframes[key_index + 1]
        t = (frame_index - previous_frame) / float(next_frame - previous_frame)
        expanded.append(interpolator(values[key_index], values[key_index + 1], t))
    return expanded


def _slerp_quaternion(a: Quaternion, b: Quaternion, t: float) -> Quaternion:
    return a.slerp(b, t)


def _lerp_vector(a: Vector, b: Vector, t: float) -> Vector:
    return a.lerp(b, t)


def _lerp_float(a: float, b: float, t: float) -> float:
    return a + ((b - a) * t)


def build_animation(
    resource_data: AnimationResourceData,
    default_nodes: list[DefaultAnimationNode],
    missing_mode: str = "default",
) -> ExpandedAnimation:
    if resource_data.animation_data is None:
        raise ValueError("Animation resource has no animated codec data")
    if resource_data.node_count != len(default_nodes):
        raise ValueError(f"Animation node count mismatch: resource={resource_data.node_count}, defaults={len(default_nodes)}")

    use_defaults = missing_mode == "default"
    rotations: list[list[Quaternion]] = []
    translations: list[list[Vector]] = []
    scales: list[list[float]] = []
    rotation_flags: list[bool] = []
    translation_flags: list[bool] = []
    scale_flags: list[bool] = []

    static_rotation_index = 0
    animated_rotation_index = 0
    static_translation_index = 0
    animated_translation_index = 0
    static_scale_index = 0
    animated_scale_index = 0

    static_rot_flags = resource_data.static_rotated_node_flags or [False] * resource_data.node_count
    static_trans_flags = resource_data.static_translated_node_flags or [False] * resource_data.node_count
    static_scale_flags = resource_data.static_scaled_node_flags or [False] * resource_data.node_count
    anim_rot_flags = resource_data.animated_rotated_node_flags or [False] * resource_data.node_count
    anim_trans_flags = resource_data.animated_translated_node_flags or [False] * resource_data.node_count
    anim_scale_flags = resource_data.animated_scaled_node_flags or [False] * resource_data.node_count

    for node_index, default_node in enumerate(default_nodes):
        rotation_present = anim_rot_flags[node_index]
        translation_present = anim_trans_flags[node_index]
        scale_present = anim_scale_flags[node_index]

        rotation_default = default_node.rotation.copy() if use_defaults else _identity_quaternion()
        translation_default = default_node.translation.copy() if use_defaults else _zero_vector()
        scale_default = default_node.scale if use_defaults else 0.0

        if static_rot_flags[node_index]:
            value = resource_data.static_data.rotations[static_rotation_index][0] if resource_data.static_data else rotation_default
            node_rotations = [value.copy() for _ in range(resource_data.frame_count)]
            static_rotation_index += 1
        elif anim_rot_flags[node_index]:
            node_rotations = [
                value.copy()
                for value in _expand_track(
                    resource_data.animation_data.rotations[animated_rotation_index],
                    resource_data.animation_data.rotation_keyframes[animated_rotation_index],
                    resource_data.frame_count,
                    rotation_default.copy(),
                    _slerp_quaternion,
                )
            ]
            animated_rotation_index += 1
        else:
            node_rotations = [rotation_default.copy() for _ in range(resource_data.frame_count)]

        if static_trans_flags[node_index]:
            value = resource_data.static_data.translations[static_translation_index][0] if resource_data.static_data else translation_default
            node_translations = [value.copy() for _ in range(resource_data.frame_count)]
            static_translation_index += 1
        elif anim_trans_flags[node_index]:
            node_translations = [
                value.copy()
                for value in _expand_track(
                    resource_data.animation_data.translations[animated_translation_index],
                    resource_data.animation_data.translation_keyframes[animated_translation_index],
                    resource_data.frame_count,
                    translation_default.copy(),
                    _lerp_vector,
                )
            ]
            animated_translation_index += 1
        else:
            node_translations = [translation_default.copy() for _ in range(resource_data.frame_count)]

        if static_scale_flags[node_index]:
            value = resource_data.static_data.scales[static_scale_index][0] if resource_data.static_data else scale_default
            node_scales = [value for _ in range(resource_data.frame_count)]
            static_scale_index += 1
        elif anim_scale_flags[node_index]:
            node_scales = _expand_track(
                resource_data.animation_data.scales[animated_scale_index],
                resource_data.animation_data.scale_keyframes[animated_scale_index],
                resource_data.frame_count,
                scale_default,
                _lerp_float,
            )
            animated_scale_index += 1
        else:
            node_scales = [scale_default for _ in range(resource_data.frame_count)]

        rotations.append(node_rotations)
        translations.append(node_translations)
        scales.append(node_scales)
        rotation_flags.append(rotation_present)
        translation_flags.append(translation_present)
        scale_flags.append(scale_present)

    return ExpandedAnimation(
        resource_data.frame_count,
        translations,
        rotations,
        scales,
        translation_flags,
        rotation_flags,
        scale_flags,
    )


def compose_overlay_animation(
    animation: ExpandedAnimation,
    base_frame: FrameChannels,
) -> ExpandedAnimation:
    translations: list[list[Vector]] = []
    rotations: list[list[Quaternion]] = []
    scales: list[list[float]] = []

    for node_index in range(animation.node_count):
        base_translation = base_frame.translations[node_index]
        base_rotation = base_frame.rotations[node_index]
        base_scale = base_frame.scales[node_index]
        node_translations: list[Vector] = []
        node_rotations: list[Quaternion] = []
        node_scales: list[float] = []
        for frame_index in range(animation.frame_count):
            translation = (
                base_translation + animation.translations[node_index][frame_index]
                if animation.translation_flags[node_index]
                else base_translation.copy()
            )
            
            if animation.rotation_flags[node_index]:
                rotation = animation.rotations[node_index][frame_index]
                rotation.rotate(base_rotation)
            else:
                rotation = base_rotation.copy()
            scale = (
                base_scale + animation.scales[node_index][frame_index]
                if animation.scale_flags[node_index]
                else base_scale
            )
            node_translations.append(translation)
            node_rotations.append(rotation)
            node_scales.append(scale)
        translations.append(node_translations)
        rotations.append(node_rotations)
        scales.append(node_scales)

    return ExpandedAnimation(
        animation.frame_count,
        translations,
        rotations,
        scales,
        animation.translation_flags[:],
        animation.rotation_flags[:],
        animation.scale_flags[:],
    )


def offset_overlay_animation(animation: ExpandedAnimation, default_nodes: list[DefaultAnimationNode]) -> ExpandedAnimation:
    if animation.node_count != len(default_nodes):
        raise ValueError(
            f"Overlay node count mismatch: animation={animation.node_count}, defaults={len(default_nodes)}"
        )

    translations: list[list[Vector]] = []
    rotations: list[list[Quaternion]] = []
    scales: list[list[float]] = []

    for node_index, default_node in enumerate(default_nodes):
        default_translation = default_node.translation.copy()
        default_rotation_inverse = default_node.rotation.copy()
        default_rotation_inverse.invert()
        default_scale = default_node.scale

        node_translations: list[Vector] = []
        node_rotations: list[Quaternion] = []
        node_scales: list[float] = []

        for frame_index in range(animation.frame_count):
            translation = animation.translations[node_index][frame_index].copy()
            if animation.translation_flags[node_index]:
                translation -= default_translation
            node_translations.append(translation)

            rotation = animation.rotations[node_index][frame_index].copy()
            if animation.rotation_flags[node_index]:
                rotation = (rotation @ default_rotation_inverse).normalized()
            node_rotations.append(rotation)

            scale = animation.scales[node_index][frame_index]
            if animation.scale_flags[node_index] and abs(default_scale) > 1e-8:
                scale /= default_scale
            node_scales.append(scale)

        translations.append(node_translations)
        rotations.append(node_rotations)
        scales.append(node_scales)

    return ExpandedAnimation(
        animation.frame_count,
        translations,
        rotations,
        scales,
        animation.translation_flags[:],
        animation.rotation_flags[:],
        animation.scale_flags[:],
    )


def compose_replacement_animation(animation: ExpandedAnimation, base_frame: FrameChannels) -> ExpandedAnimation:
    translations: list[list[Vector]] = []
    rotations: list[list[Quaternion]] = []
    scales: list[list[float]] = []
    for node_index in range(animation.node_count):
        base_translation = base_frame.translations[node_index]
        base_rotation = base_frame.rotations[node_index]
        base_scale = base_frame.scales[node_index]
        node_translations: list[Vector] = []
        node_rotations: list[Quaternion] = []
        node_scales: list[float] = []
        for frame_index in range(animation.frame_count):
            translation = animation.translations[node_index][frame_index].copy() if animation.translation_flags[node_index] else base_translation.copy()
            rotation = animation.rotations[node_index][frame_index].copy() if animation.rotation_flags[node_index] else base_rotation.copy()
            scale = animation.scales[node_index][frame_index] if animation.scale_flags[node_index] else base_scale
            node_translations.append(translation)
            node_rotations.append(rotation)
            node_scales.append(scale)
        translations.append(node_translations)
        rotations.append(node_rotations)
        scales.append(node_scales)

    return ExpandedAnimation(
        animation.frame_count,
        translations,
        rotations,
        scales,
        animation.translation_flags[:],
        animation.rotation_flags[:],
        animation.scale_flags[:],
    )

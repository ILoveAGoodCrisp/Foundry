"""Portable bone-linked vector keys, matching the SDK's CRC32 byte sequence."""
from zlib import crc32

from .binary import BinaryWriteError
from .model import Skeleton


def vector_track_key_for_bone(skeleton, bone_index, track_name):
    """CRC32(bone UTF-8 + parent UTF-8 + ... + root UTF-8 + track UTF-8).

    Names are case-sensitive, with no separators, NUL terminators or Unicode
    normalization. Skeleton name, array order and transforms do not contribute.
    See granny/WRITER_VECTOR_KEYS.md for the SDK compatibility evidence.
    """
    if not isinstance(skeleton, Skeleton):
        raise BinaryWriteError('Vector-key lookup requires an independent Skeleton record')
    if not isinstance(bone_index, int) or not 0 <= bone_index < len(skeleton.bones):
        raise BinaryWriteError('Vector key references an absent bone')

    def encoded(name):
        if not isinstance(name, str) or '\0' in name:
            raise BinaryWriteError('Vector-key names require UTF-8 strings without NUL')
        try:
            return name.encode('utf-8')
        except UnicodeEncodeError as error:
            raise BinaryWriteError('Vector-key names must be valid UTF-8') from error

    track = encoded(track_name)
    result, seen = 0, set()
    index = bone_index
    while index != -1:
        if not isinstance(index, int) or not 0 <= index < len(skeleton.bones):
            raise BinaryWriteError('Vector key references an absent ancestor bone')
        if index in seen:
            raise BinaryWriteError('Vector-key skeleton hierarchy has a cycle')
        seen.add(index)
        bone = skeleton.bones[index]
        result = crc32(encoded(bone.name), result)
        index = bone.parent_index
    return crc32(track, result)

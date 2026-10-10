"""Explicit SDK oracle for testing portable bone-linked vector keys.

Importing this module does not import ctypes or load a runtime. Neither file
serialization, curves, transforms nor textures use this bridge.
"""
from pathlib import Path

from .binary import BinaryWriteError
from .model import Skeleton


def native_vector_key_resolver(dll_path):
    """Return callback(skeleton, bone_index, track_name) -> uint32.

    Default exports use vector_keys.vector_track_key_for_bone instead. Keep
    this SDK query explicit for differential tests and caller-selected overrides.
    """
    import ctypes as c

    if c.sizeof(c.c_void_p) != 8:
        raise BinaryWriteError('Vector-key lookup requires the x64 Granny runtime')

    class NativeBone(c.Structure):
        _pack_ = 1
        _fields_ = [('name', c.c_char_p), ('parent', c.c_int32), ('flags', c.c_uint32),
            ('position', c.c_float*3), ('orientation', c.c_float*4), ('scale_shear', c.c_float*9),
            ('inverse_world', c.c_float*16), ('lod_error', c.c_float), ('extended', c.c_void_p*2)]

    class NativeSkeleton(c.Structure):
        _pack_ = 1
        _fields_ = [('name', c.c_char_p), ('count', c.c_int32), ('bones', c.POINTER(NativeBone)),
                   ('lod_type', c.c_int32), ('extended', c.c_void_p*2)]

    if c.sizeof(NativeBone) != 164 or c.sizeof(NativeSkeleton) != 40:
        raise BinaryWriteError('Unexpected x64 Granny vector-key ABI layout')

    try:
        dll = c.CDLL(str(Path(dll_path).resolve()))
        query = dll.GrannyVectorTrackKeyForBone
    except (OSError, AttributeError) as error:
        raise BinaryWriteError('Granny runtime lacks the vector-track key query') from error
    query.argtypes = [c.POINTER(NativeSkeleton), c.c_int32, c.c_char_p]
    query.restype = c.c_uint32
    skeletons, keys = {}, {}

    def encoded(name):
        if not isinstance(name, str) or '\0' in name:
            raise BinaryWriteError('Vector-key names require UTF-8 strings without NUL')
        return name.encode('utf-8')

    def resolve(skeleton, bone_index, track_name):
        if not isinstance(skeleton, Skeleton):
            raise BinaryWriteError('Vector-key lookup requires an independent Skeleton record')
        if not isinstance(bone_index, int) or not 0 <= bone_index < len(skeleton.bones):
            raise BinaryWriteError('Vector key references an absent bone')
        key = (id(skeleton), bone_index, track_name)
        if key in keys:
            return keys[key]
        if id(skeleton) not in skeletons:
            bones = (NativeBone*len(skeleton.bones))()
            for index, bone in enumerate(skeleton.bones):
                bones[index].name, bones[index].parent = encoded(bone.name), bone.parent_index
                bones[index].orientation[3] = 1.
                for i in (0, 4, 8):
                    bones[index].scale_shear[i] = 1.
                for i in (0, 5, 10, 15):
                    bones[index].inverse_world[i] = 1.
            value = NativeSkeleton(encoded(skeleton.name), len(bones), bones, skeleton.lod_type)
            skeletons[id(skeleton)] = (skeleton, value, bones)
        value = skeletons[id(skeleton)][1]
        keys[key] = int(query(c.byref(value), bone_index, encoded(track_name)))
        return keys[key]

    # The callable closes over the DLL and owned native records for their entire
    # lifetime; no pointers escape into independent export records or the file.
    resolve._dll = dll
    return resolve

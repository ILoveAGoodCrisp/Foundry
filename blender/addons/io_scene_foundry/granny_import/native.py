"""Lazy Oodle/Bink/YCoCg codecs. No native file or schema parsing is used."""
import platform
from pathlib import Path
import struct
import subprocess
import sys

from .container import UnsupportedGrannyFormat


def supported_platform():
    return sys.platform == 'win32' and struct.calcsize('P') == 8 and platform.machine().lower() in {'amd64', 'x86_64'}


class NativeDecompressor:
    def __init__(self, resolve_path, on_use=None):
        self.resolve_path, self.on_use, self.dll = resolve_path, on_use, None
        self.used = set()

    def _path(self, feature):
        if not supported_platform():
            raise UnsupportedGrannyFormat(f'{feature} currently requires the Windows x64 Granny DLL')
        if not hasattr(self, 'path'):
            try:
                self.path = self.resolve_path() if callable(self.resolve_path) else self.resolve_path
            except (OSError, RuntimeError) as error:
                raise UnsupportedGrannyFormat(f'Cannot decode {feature}: {error}') from error
        if feature not in self.used and self.on_use:
            self.on_use(f'Using Granny DLL for {feature}: {self.path}')
        self.used.add(feature)
        return self.path

    def _load(self, feature):
        import ctypes as c
        path = self._path(feature)
        if self.dll is None:
            try:
                dll = c.CDLL(str(path))
            except (OSError, RuntimeError) as error:
                raise UnsupportedGrannyFormat(f'Cannot decode {feature}: {error}') from error
            dll.GrannyGetCompressedBytesPaddingSize.argtypes = [c.c_int]
            dll.GrannyGetCompressedBytesPaddingSize.restype = c.c_int
            dll.GrannyDecompressData.argtypes = [c.c_int, c.c_bool, c.c_int, c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_void_p]
            dll.GrannyDecompressData.restype = c.c_bool
            self.dll = dll
        return self.dll

    def __call__(self, compression, data, stop0, stop1, expanded):
        if compression not in (1, 2):
            raise UnsupportedGrannyFormat(f'Unsupported GR2 section compression {compression}')
        import ctypes as c
        self._load('Oodle section decompression')
        padding = self.dll.GrannyGetCompressedBytesPaddingSize(compression)
        if not 0 <= padding <= 65536:
            raise ValueError('Invalid Granny decompressor padding')
        source = c.create_string_buffer(bytes(data), len(data) + padding + 1)
        result = c.create_string_buffer(expanded)
        if not self.dll.GrannyDecompressData(compression, False, len(data), source, stop0, stop1, expanded, result):
            raise ValueError('Could not decompress GR2 section')
        return result.raw

    def texture(self, record, payload, stride):
        """Run legacy image codecs outside Blender: some valid old files abort."""
        encoding = record.get('Encoding')
        if encoding not in (3, 4):
            raise UnsupportedGrannyFormat(f'Unsupported GR2 texture encoding {encoding}')
        import json
        import numpy as np
        path = self._path('Bink texture decoding' if encoding == 3 else 'YCoCg texture decoding')
        candidates = (Path(sys.prefix) / 'bin/python.exe', Path(sys.base_prefix) / 'python.exe', Path(sys.executable))
        executable = next((p for p in candidates if p.name.lower() in {'python.exe', 'pythonw.exe'} and p.is_file()), None)
        if executable is None:
            raise ValueError('No Python interpreter is available for isolated Granny image decoding')
        width, height = record.get('Width'), record.get('Height')
        header = dict(dll=str(path), width=width, height=height, encoding=encoding, stride=stride,
                      texture_type=record.get('TextureType'), subformat=record.get('SubFormat'),
                      layout=record.owner.detach(record.get('Layout')))
        request = json.dumps(header).encode('utf-8') + b'\n' + payload
        try:
            result = subprocess.run([str(executable), str(Path(__file__).with_name('native_texture_worker.py'))],
                                    input=request, capture_output=True, timeout=60,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError(f'Granny image decoder failed: {error}') from error
        if result.returncode or len(result.stdout) != width * height * 4:
            raise ValueError('Granny image decoder failed; embedded image was skipped')
        return np.frombuffer(result.stdout, dtype=np.uint8).reshape(height, width, 4).copy()


def decode_native_texture(header, payload):
    """Worker-only entry point; all ctypes image buffers are locally owned."""
    import ctypes as c
    import numpy as np
    dll = c.CDLL(header['dll'])

    class Layout(c.Structure):
        _pack_ = 1
        _fields_ = [('bytes', c.c_int), ('shifts', c.c_int * 4), ('bits', c.c_int * 4)]

    class Mip(c.Structure):
        _pack_ = 1
        _fields_ = [('stride', c.c_int), ('size', c.c_int), ('data', c.c_void_p)]

    class Image(c.Structure):
        _pack_ = 1
        _fields_ = [('count', c.c_int), ('mips', c.POINTER(Mip))]

    class Texture(c.Structure):
        _pack_ = 1
        _fields_ = [('name', c.c_char_p), ('type', c.c_int), ('width', c.c_int), ('height', c.c_int),
                    ('encoding', c.c_int), ('subformat', c.c_int), ('layout', Layout),
                    ('count', c.c_int), ('images', c.POINTER(Image)), ('extended', c.c_void_p * 2)]

    layout = header['layout']
    source = c.create_string_buffer(payload)
    mip = Mip(header['stride'], len(payload), c.addressof(source))
    image = Image(1, c.pointer(mip))
    texture = Texture(b'', header['texture_type'], header['width'], header['height'], header['encoding'],
                      header['subformat'], Layout(layout.get('BytesPerPixel'),
                      (c.c_int * 4)(*layout.get('ShiftForComponent')), (c.c_int * 4)(*layout.get('BitsForComponent'))),
                      1, c.pointer(image), (c.c_void_p * 2)())
    output_layout = Layout(4, (c.c_int * 4)(0, 8, 16, 24), (c.c_int * 4)(8, 8, 8, 8))
    pixels = np.empty((texture.height, texture.width, 4), dtype=np.uint8)
    function = dll.GrannyCopyTextureImage
    function.argtypes = [c.c_void_p, c.c_int, c.c_int, c.c_void_p, c.c_int, c.c_int, c.c_int, c.c_void_p]
    function.restype = c.c_bool
    if not function(c.byref(texture), 0, 0, c.byref(output_layout), texture.width, texture.height,
                    texture.width * 4, pixels.ctypes.data):
        raise ValueError('Granny could not decode the embedded texture')
    return pixels

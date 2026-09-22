

from math import sqrt
import math
import os
import struct
import sys
from pathlib import Path
import numpy as np

from ..constants import NormalType
from ..tags.backend import TagDocument
from ..tags.blender import BlenderTag
from .. import utils
import bpy

path_cache: set[Path] = set()
NORMAL_DEBUG_GAMMA = 2.2
NORMAL_DEBUG_GAMMA_LOOKUP = tuple(
    int(round(((i / 255.0) ** NORMAL_DEBUG_GAMMA) * 255.0))
    for i in range(256)
)
NORMAL_DEBUG_GAMMA_LOOKUP_NP = np.array(NORMAL_DEBUG_GAMMA_LOOKUP, dtype=np.uint8)

BITMAP_FORMAT_A8 = 0
BITMAP_FORMAT_Y8 = 1
BITMAP_FORMAT_AY8 = 2
BITMAP_FORMAT_A8Y8 = 3
BITMAP_FORMAT_R8 = 4
BITMAP_FORMAT_R5G6B5 = 6
BITMAP_FORMAT_A1R5G5B5 = 8
BITMAP_FORMAT_A4R4G4B4 = 9
BITMAP_FORMAT_X8R8G8B8 = 10
BITMAP_FORMAT_A8R8G8B8 = 11
BITMAP_FORMAT_DXT1 = 14
BITMAP_FORMAT_DXT3 = 15
BITMAP_FORMAT_DXT5 = 16
BITMAP_FORMAT_A4R4G4B4_FONT = 17
BITMAP_FORMAT_RGBFP32 = 20
BITMAP_FORMAT_V8U8 = 22
BITMAP_FORMAT_G8B8 = 23
BITMAP_FORMAT_ABGRFP32 = 24
BITMAP_FORMAT_ABGRFP16 = 25
BITMAP_FORMAT_16F_MONO = 26
BITMAP_FORMAT_16F_RED = 27
BITMAP_FORMAT_Q8W8V8U8 = 28
BITMAP_FORMAT_A2R10G10B10 = 29
BITMAP_FORMAT_A16B16G16R16 = 30
BITMAP_FORMAT_V16U16 = 31
BITMAP_FORMAT_L16 = 32
BITMAP_FORMAT_R16G16 = 33
BITMAP_FORMAT_SIGNED_R16G16B16A16 = 34
BITMAP_FORMAT_DXT3A = 35
BITMAP_FORMAT_DXT5A = 36
BITMAP_FORMAT_DXT3A_1111 = 37
BITMAP_FORMAT_DXN = 38
BITMAP_FORMAT_CTX1 = 39
BITMAP_FORMAT_DXT3A_ALPHA = 40
BITMAP_FORMAT_DXT3A_MONO = 41
BITMAP_FORMAT_DXT5A_ALPHA = 42
BITMAP_FORMAT_DXT5A_MONO = 43
BITMAP_FORMAT_DXN_MONO_ALPHA = 44
BITMAP_FORMAT_DXT5_RED = 45
BITMAP_FORMAT_DXT5_GREEN = 46
BITMAP_FORMAT_DXT5_BLUE = 47
BITMAP_FORMAT_DEPTH24 = 48

BITMAP_FORMAT_NAMES = {
    0: "a8",
    1: "y8",
    2: "ay8",
    3: "a8y8",
    4: "r8",
    5: "unused2",
    6: "r5g6b5",
    7: "unused3",
    8: "a1r5g5b5",
    9: "a4r4g4b4",
    10: "x8r8g8b8",
    11: "a8r8g8b8",
    12: "unused4",
    13: "unused5",
    14: "dxt1",
    15: "dxt3",
    16: "dxt5",
    17: "a4r4g4b4 font",
    18: "unused7",
    19: "unused8",
    20: "software rgbfp32",
    21: "unused9",
    22: "v8u8",
    23: "g8b8",
    24: "abgrfp32",
    25: "abgrfp16",
    26: "16f_mono",
    27: "16f_red",
    28: "q8w8v8u8",
    29: "a2r10g10b10",
    30: "a16b16g16r16",
    31: "v16u16",
    32: "l16",
    33: "r16g16",
    34: "signedr16g16b16a16",
    35: "dxt3a",
    36: "dxt5a",
    37: "dxt3a_1111",
    38: "dxn",
    39: "ctx1",
    40: "dxt3a_alpha",
    41: "dxt3a_mono",
    42: "dxt5a_alpha",
    43: "dxt5a_mono",
    44: "dxn_mono_alpha",
    45: "dxt5_red",
    46: "dxt5_green",
    47: "dxt5_blue",
    48: "depth 24",
}
BITMAP_FORMAT_BY_NAME = {
    name.casefold(): bitmap_format for bitmap_format, name in BITMAP_FORMAT_NAMES.items()
}

BITMAP_TYPE_NAMES = {
    0: "2d texture",
    1: "3d texture",
    2: "cube map",
    3: "array",
}

UNCOMPRESSED_BITMAP_FORMAT_NAMES = {
    BITMAP_FORMAT_A8: "A8",
    BITMAP_FORMAT_Y8: "Y8",
    BITMAP_FORMAT_AY8: "AY8",
    BITMAP_FORMAT_A8Y8: "A8Y8",
    BITMAP_FORMAT_R8: "R8",
    BITMAP_FORMAT_R5G6B5: "R5G6B5",
    BITMAP_FORMAT_A1R5G5B5: "A1R5G5B5",
    BITMAP_FORMAT_A4R4G4B4: "A4R4G4B4",
    BITMAP_FORMAT_X8R8G8B8: "X8R8G8B8",
    BITMAP_FORMAT_A8R8G8B8: "A8R8G8B8",
    BITMAP_FORMAT_A4R4G4B4_FONT: "A4R4G4B4_FONT",
    BITMAP_FORMAT_RGBFP32: "RGBFP32",
    BITMAP_FORMAT_V8U8: "V8U8",
    BITMAP_FORMAT_G8B8: "G8B8",
    BITMAP_FORMAT_ABGRFP32: "ABGRFP32",
    BITMAP_FORMAT_ABGRFP16: "ABGRFP16",
    BITMAP_FORMAT_16F_MONO: "16F_MONO",
    BITMAP_FORMAT_16F_RED: "16F_RED",
    BITMAP_FORMAT_Q8W8V8U8: "Q8W8V8U8",
    BITMAP_FORMAT_A2R10G10B10: "A2R10G10B10",
    BITMAP_FORMAT_A16B16G16R16: "A16B16G16R16",
    BITMAP_FORMAT_V16U16: "V16U16",
    BITMAP_FORMAT_L16: "L16",
    BITMAP_FORMAT_R16G16: "R16G16",
    BITMAP_FORMAT_SIGNED_R16G16B16A16: "SIGNED_R16G16B16A16",
    BITMAP_FORMAT_DEPTH24: "DEPTH24",
}

UNCOMPRESSED_BITMAP_BYTES_PER_PIXEL = {
    BITMAP_FORMAT_A8: 1,
    BITMAP_FORMAT_Y8: 1,
    BITMAP_FORMAT_AY8: 1,
    BITMAP_FORMAT_A8Y8: 2,
    BITMAP_FORMAT_R8: 1,
    BITMAP_FORMAT_R5G6B5: 2,
    BITMAP_FORMAT_A1R5G5B5: 2,
    BITMAP_FORMAT_A4R4G4B4: 2,
    BITMAP_FORMAT_X8R8G8B8: 4,
    BITMAP_FORMAT_A8R8G8B8: 4,
    BITMAP_FORMAT_A4R4G4B4_FONT: 2,
    BITMAP_FORMAT_RGBFP32: 12,
    BITMAP_FORMAT_V8U8: 2,
    BITMAP_FORMAT_G8B8: 2,
    BITMAP_FORMAT_ABGRFP32: 16,
    BITMAP_FORMAT_ABGRFP16: 8,
    BITMAP_FORMAT_16F_MONO: 2,
    BITMAP_FORMAT_16F_RED: 2,
    BITMAP_FORMAT_Q8W8V8U8: 4,
    BITMAP_FORMAT_A2R10G10B10: 4,
    BITMAP_FORMAT_A16B16G16R16: 8,
    BITMAP_FORMAT_V16U16: 4,
    BITMAP_FORMAT_L16: 2,
    BITMAP_FORMAT_R16G16: 4,
    BITMAP_FORMAT_SIGNED_R16G16B16A16: 8,
    BITMAP_FORMAT_DEPTH24: 3,
}

COMPRESSED_BITMAP_FORMAT_NAMES = {
    BITMAP_FORMAT_DXT1: "DXT1",
    BITMAP_FORMAT_DXT3: "DXT3",
    BITMAP_FORMAT_DXT5: "DXT5",
    BITMAP_FORMAT_DXT3A: "DXT3A",
    BITMAP_FORMAT_DXT5A: "DXT5A",
    BITMAP_FORMAT_DXT3A_1111: "DXT3A_1111",
    BITMAP_FORMAT_DXN: "DXN",
    BITMAP_FORMAT_CTX1: "CTX1",
    BITMAP_FORMAT_DXT3A_ALPHA: "DXT3A_ALPHA",
    BITMAP_FORMAT_DXT3A_MONO: "DXT3A_MONO",
    BITMAP_FORMAT_DXT5A_ALPHA: "DXT5A_ALPHA",
    BITMAP_FORMAT_DXT5A_MONO: "DXT5A_MONO",
    BITMAP_FORMAT_DXN_MONO_ALPHA: "DXN_MONO_ALPHA",
    BITMAP_FORMAT_DXT5_RED: "DXT5_RED",
    BITMAP_FORMAT_DXT5_GREEN: "DXT5_GREEN",
    BITMAP_FORMAT_DXT5_BLUE: "DXT5_BLUE",
}

SUPPORTED_BITMAP_FORMAT_NAMES = dict(UNCOMPRESSED_BITMAP_FORMAT_NAMES)
SUPPORTED_BITMAP_FORMAT_NAMES.update(COMPRESSED_BITMAP_FORMAT_NAMES)

EIGHT_BYTE_BLOCK_BITMAP_FORMATS = {
    BITMAP_FORMAT_DXT1,
    BITMAP_FORMAT_DXT3A,
    BITMAP_FORMAT_DXT5A,
    BITMAP_FORMAT_DXT3A_1111,
    BITMAP_FORMAT_CTX1,
    BITMAP_FORMAT_DXT3A_ALPHA,
    BITMAP_FORMAT_DXT3A_MONO,
    BITMAP_FORMAT_DXT5A_ALPHA,
    BITMAP_FORMAT_DXT5A_MONO,
}

SIXTEEN_BYTE_BLOCK_BITMAP_FORMATS = {
    BITMAP_FORMAT_DXT3,
    BITMAP_FORMAT_DXT5,
    BITMAP_FORMAT_DXN,
    BITMAP_FORMAT_DXN_MONO_ALPHA,
    BITMAP_FORMAT_DXT5_RED,
    BITMAP_FORMAT_DXT5_GREEN,
    BITMAP_FORMAT_DXT5_BLUE,
}

def clear_path_cache():
    global path_cache
    path_cache.clear()
    
class BitmapInfo:
    def __init__(self):
        self.image: bpy.types.Image = None
        self.image_path = ""
        self.curve = 0
        self.for_normal = True
        self.cubemap = False
        self.sequence_length = 1
        self.shader_type = "default"
        
used_plate_paths = []

BITMAP_SEQUENCE_EXTENSIONS = {".tif", ".tiff", ".tga"}

def _frame_suffix_number(path: Path) -> int | None:
    _, separator, suffix = path.stem.rpartition("_")
    if separator and suffix.isdigit():
        return int(suffix)
    return None

def _frame_sort_key(path: Path):
    frame_number = _frame_suffix_number(path)
    return (frame_number is None, frame_number if frame_number is not None else 0, path.name.lower())

def _sequence_files_in_directory(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(
        (
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in BITMAP_SEQUENCE_EXTENSIONS
        ),
        key=_frame_sort_key,
    )

def _numbered_sibling_sequence_paths(image_path: Path) -> list[Path]:
    frame_number = _frame_suffix_number(image_path)
    if frame_number is None or not image_path.parent.exists():
        return []

    prefix = image_path.stem.rpartition("_")[0]
    sequence_paths = []
    for candidate in image_path.parent.iterdir():
        if not candidate.is_file() or candidate.suffix.lower() not in BITMAP_SEQUENCE_EXTENSIONS:
            continue
        candidate_prefix, separator, suffix = candidate.stem.rpartition("_")
        if separator and candidate_prefix == prefix and suffix.isdigit():
            sequence_paths.append(candidate)

    return sorted(sequence_paths, key=_frame_sort_key)

def _bitmap_sequence_paths(image_path: str | Path) -> list[Path]:
    path = Path(image_path)
    if path.exists() and path.is_dir():
        return _sequence_files_in_directory(path)

    numbered_sequence = _numbered_sibling_sequence_paths(path)
    if len(numbered_sequence) > 1:
        return numbered_sequence

    # Tool plates and existing cached plate exports sit beside the source TIFF/TGA path.
    plate_dir = path.with_suffix("")
    plate_sequence = _sequence_files_in_directory(plate_dir)
    if len(plate_sequence) > 1:
        return plate_sequence

    return numbered_sequence

class BitmapExtractionError(RuntimeError):
    pass

def _bitmap_color_space_conversion_enabled() -> bool:
    try:
        return bool(utils.get_prefs().bitmap_color_space_conversion)
    except Exception:
        return True

def _bitmap_info_color_space(info: BitmapInfo) -> str:
    if info.for_normal:
        return "Non-Color"
    if info.curve == 3:
        return "Linear Rec.709"
    if info.curve in {0, 1, 2} and not _bitmap_color_space_conversion_enabled():
        return "xRGB"
    return "sRGB"

def apply_bitmap_info_color_space(image: bpy.types.Image, info: BitmapInfo):
    color_space = _bitmap_info_color_space(info)
    try:
        image.colorspace_settings.name = color_space
    except Exception as ex:
        if color_space != "xRGB":
            raise
        utils.print_warning(
            "Blender's xRGB color space is not available. Install it from Foundry preferences "
            "and restart Blender, or enable Bitmap Color Space Conversion. Falling back to sRGB."
        )
        image.colorspace_settings.name = "sRGB"

    if not info.for_normal:
        image.alpha_mode = 'CHANNEL_PACKED'
    
def bitmap_to_image(path: str | Path, always_extract_bitmaps=False) -> BitmapInfo:
    
    image = None
    
    data_dir = utils.get_data_path()
    tags_dir = utils.get_tags_path()
    
    rel_path = utils.relative_path(path)
    
    tag_path = Path(tags_dir, rel_path)
    
    info = BitmapInfo()
    
    if not tag_path.exists():
        return info
        
    system_tiff_path = Path(utils.get_data_path(), rel_path).with_suffix('.tiff')
    alt_system_tiff_path = system_tiff_path.with_suffix(".tif")
    sequence_tiff_path = None
    alt_sequence_tiff_path = None
    
    with BitmapTag(path=rel_path) as bitmap:
        if not bitmap.has_bitmap_data(): return info
        if bitmap.is_cubemap:
            info.cubemap = True
            rel_path = f"{bitmap.tag_path.RelativePath}_equirectangular"
            system_tiff_path = Path(data_dir, rel_path).with_suffix('.tiff')
            alt_system_tiff_path = system_tiff_path.with_suffix(".tif")
            sequence_tiff_path = system_tiff_path.with_name(
                f"{system_tiff_path.stem}_00001{system_tiff_path.suffix}")
            alt_sequence_tiff_path = sequence_tiff_path.with_suffix(".tif")

        info.curve = bitmap.curve_index()
        info.for_normal = bitmap.used_as_normal_map()
        info.shader_type = bitmap.get_shader_type()
        if always_extract_bitmaps:
            info.image_path = bitmap.save_to_tiff(info.for_normal)
        elif system_tiff_path.exists():
            info.image_path = str(system_tiff_path)
        elif alt_system_tiff_path.exists():
            info.image_path = str(alt_system_tiff_path)
        elif sequence_tiff_path is not None and sequence_tiff_path.exists():
            info.image_path = str(sequence_tiff_path)
        elif alt_sequence_tiff_path is not None and alt_sequence_tiff_path.exists():
            info.image_path = str(alt_sequence_tiff_path)
        else:
            info.image_path = bitmap.save_to_tiff(info.for_normal)
            
    if not info.image_path:
        return info
    
    image_path = Path(info.image_path)
    sequence_paths = _bitmap_sequence_paths(image_path)
    if sequence_paths and (len(sequence_paths) > info.sequence_length or image_path.is_dir()):
        info.sequence_length = max(info.sequence_length, len(sequence_paths))
        for sequence_path in sequence_paths:
            if sequence_path in used_plate_paths:
                continue
            used_plate_paths.append(sequence_path)
            info.image_path = str(sequence_path)
            break
        else:
            info.image_path = str(sequence_paths[0])
            
    image = bpy.data.images.load(filepath=info.image_path, check_existing=True)
    image.nwo.filepath = utils.relative_path(info.image_path)
    image.nwo.shader_type = info.shader_type

    apply_bitmap_info_color_space(image, info)

    if info.sequence_length > 1 and not info.cubemap:
        image.source = 'SEQUENCE'
        
    info.image = image
            
    return info

class BitmapTag(BlenderTag, TagDocument):
    tag_ext = 'bitmap'

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        self.data_dir = utils.get_data_path()
        super().__init__(path, **kwargs)
        if self.valid:
            self._read_fields()
    
    def _read_fields(self):
        root = self.tag.root()
        if self.game in {'halo1', 'halo2'}:
            self.longenum_usage = self.required_field(root, 'usage')
            self.charenum_usage = self.longenum_usage
            self.block_usage_override = None
            self.block_bitmaps = self.block(root, 'bitmaps')
            self.is_cubemap = bool(len(self.block_bitmaps) and
                                   self._enum_index(self.block_bitmaps[0], 'type') == 2)
            return
        self.longenum_usage = self.required_field(root, 'Usage')
        self.charenum_usage = self.required_field(root, 'curve mode')
        self.block_usage_override = self.block(root, 'usage override')
        self.block_bitmaps = self.block(root, 'bitmaps')
        self.is_cubemap = bool(len(self.block_bitmaps) and
                               self._enum_index(self.block_bitmaps[0], 'type') == 2)

    def _enum_index(self, element, name):
        field = self.required_field(element, name)
        options = field.options()
        if options is None or options.current is None:
            raise ValueError(f'{self.path}: {name!r} is not a known enum value')
        return options.current

    def _set_enum(self, element, name, value):
        field = self.required_field(element, name)
        field.set(value)
        self.tag_has_changes = True

    def set_registration_points(self, points: dict[int, tuple[int, int]]) -> None:
        for index, point in points.items():
            if not 0 <= index < len(self.block_bitmaps):
                raise IndexError(f'{self.path}: bitmap index {index} is out of range')
            field = self.required_field(self.block_bitmaps[index], 'registration point')
            field.set(type(field.value)(*point))
            self.tag_has_changes = True
        
    def new_bitmap(self, bitmap_name, bitmap_type, color_space):
        def get_type_from_name(bitmap_name):
            suffix = bitmap_name.rpartition("_")[2].lower()
            if suffix and "_" in bitmap_name.strip("_"):
                if suffix.startswith(("orm", "mro", "mtr", "rmo", "control", "arm")):
                    return "Material Map"
                elif suffix.startswith("3d"):
                    return "3D Texture"
                elif suffix.startswith("blend"):
                    return "Blend Map (linear for terrains)"
                elif suffix.startswith("bump"):
                    return "Bump Map (from Height Map)"
                elif suffix.startswith(("cc", "change")):
                    return "Change Color Map"
                elif suffix.startswith("cube"):
                    return "Cube Map (Reflection Map)"
                elif suffix.startswith(("detailb", "detail_b")):
                    return "Detail Bump Map (from Height Map - fades out)"
                elif suffix.startswith(("detailn", "detail_n")):
                    return "Detail Normal Map"
                elif suffix.startswith("det"):
                    return "Detail Map"
                elif suffix.startswith("dsprite"):
                    return "Sprite (Double Multiply, Gray Background)"
                elif suffix.startswith("float"):
                    return "Float Map (WARNING)"
                elif suffix.startswith("height"):
                    return "Height Map (for Parallax)"
                elif suffix.startswith(("illum", "self", "emm")):
                    return "Self-Illum Map"
                elif suffix.startswith("msprite"):
                    return "Sprite (Blend, White Background)"
                elif suffix.startswith("spec"):
                    return "Specular Map"
                elif suffix.startswith("sprite"):
                    return "Sprite (Additive, Black Background)"
                elif suffix.startswith("ui"):
                    return "Interface Bitmap"
                elif suffix.startswith("vec"):
                    return "Vector Map"
                elif suffix.startswith("warp"):
                    return "Warp Map (EMBM)"
                elif suffix.startswith(("zbump", "dx_normal", 'dxnormal', 'normaldx', 'normal_dx')):
                    return "ZBrush Bump Map (from Bump Map)"
                elif suffix.startswith(("nor", "nm", "nrm")):
                    if self.corinth:
                        return "Normal Map (from Standard Orientation of Maya, Modo, Zbrush)"
                    else:
                        return "Normal Map (aka zbump)"
                    
            return "Diffuse Map"
        
        if bitmap_type == 'default':
            bitmap_type = get_type_from_name(bitmap_name)
            
        normal_bitmap_types = (
            "ZBrush Bump Map (from Bump Map)",
            "Normal Map (aka zbump)",
            "Normal Map (from Standard Orientation of Maya, Modo, Zbrush)",
        )

        self.longenum_usage.set(bitmap_type)
        self.charenum_usage.set('force PRETTY')
        if not len(self.block_usage_override):
            self.block_usage_override.add()
        override = self.block_usage_override[0]
        source_gamma = self.required_field(override, 'source gamma')
        if bitmap_type in normal_bitmap_types:
            source_gamma_value = 1.0
        else:
            source_gamma_value = self._source_gamma_from_color_space(color_space)
        source_gamma.set(source_gamma_value)
        if source_gamma_value > 2.0:
            self._set_enum(override, 'bitmap curve', "sRGB (gamma 2.2)")
        elif source_gamma_value > 1:
            self._set_enum(override, 'bitmap curve', "xRGB (gamma about 2.0)")
        else:
            self._set_enum(override, 'bitmap curve', "linear")
            
        self.required_field(override, 'flags').set_flag("Ignore Curve Override", True)
        if bitmap_type in ("Material Map", "Diffuse Map", "Blend Map (linear for terrains)", "Self-Illum Map", "Cube Map (Reflection Map)", "Detail Map"):
            self._set_enum(override, 'bitmap format', 'DXT5 (Compressed Color + Compressed 8-bit Alpha)')
            if bitmap_type == 'Material Map':
                self.required_field(override, 'mipmap limit').set(-1)
        elif bitmap_type in normal_bitmap_types:
            self._set_enum(override, 'bitmap format', 'DXN Compressed Normals (better)')
            
        self.tag_has_changes = True
        
    def get_granny_data(self, fill_alpha: bool, calc_blue_channel: bool) -> object | None:
        if not len(self.block_bitmaps):
            return None
        bitmap = self.block_bitmaps[0]
        width = self._select_int(bitmap, 'width')
        height = self._select_int(bitmap, 'height')
        bitmap_type = self._select_int(bitmap, 'type')
        bitmap_format = self._bitmap_format(bitmap)
        pixels_offset = self._select_int(bitmap, 'pixels offset', -1)
        pixels_size = self._bitmap_base_pixel_size(
            width, height, bitmap_format, bitmap_type)
        if bitmap_type != 0 or width <= 0 or height <= 0:
            return None
        processed_data = bytes(self.required_field(self.tag.root(), 'processed pixel data').value)
        end = pixels_offset + pixels_size
        if pixels_offset < 0 or pixels_size <= 0 or end > len(processed_data):
            raise BitmapExtractionError(f'Invalid pixel-data range in {self.path}')
        rgba = self._decode_bitmap_rgba(
            width, height, bitmap_format, processed_data[pixels_offset:end])
        if rgba is None:
            raise BitmapExtractionError(
                f'Unsupported bitmap format {bitmap_format} in {self.path}')
        pixels = np.frombuffer(rgba, dtype=np.uint8).copy().reshape(-1, 4)
        if calc_blue_channel:
            red = NORMAL_DEBUG_GAMMA_LOOKUP_NP[pixels[:, 0]] / 255.0
            green_source = 255 - pixels[:, 1] if self.normal_type() == NormalType.OPENGL else pixels[:, 1]
            green = NORMAL_DEBUG_GAMMA_LOOKUP_NP[green_source] / 255.0
            pixels[:, 0] = np.clip(red * 255 + 0.5, 0, 255).astype(np.uint8)
            pixels[:, 1] = np.clip(green * 255 + 0.5, 0, 255).astype(np.uint8)
            pixels[:, 2] = np.clip(
                (np.sqrt(np.maximum(0.0, 1.0 - (red * 2 - 1) ** 2 -
                                    (green * 2 - 1) ** 2)) * 0.5 + 0.5) * 255 + 0.5,
                0, 255).astype(np.uint8)
        if fill_alpha:
            pixels[:, 3] = 255
        return width, height, width * 4, pixels.tobytes()
    
    @staticmethod
    def bgra_to_rgba_solid_alpha(total_bytes, bgra_array, gamma):
        for i in range(0, total_bytes, 4):
            bgra_array[i + 3] = 255
            red = bgra_array[i + 2] / 255.0
            green = bgra_array[i + 1] / 255.0
            blue = bgra_array[i] / 255.0
            # match gamma:
            #     case 'linear':
            #         red = red ** 2.0
            #         green = green ** 2.0
            #         blue = blue ** 2.0
            #     case 'srgb':
            #         red = utils.linear_to_srgb(red ** 2.0)
            #         green = utils.linear_to_srgb(green ** 2.0)
            #         blue = utils.linear_to_srgb(blue ** 2.0)
                    
            bgra_array[i] = int(red * 255)
            bgra_array[i + 1] = int(green * 255)
            bgra_array[i + 2] = int(blue * 255)
            
        return bgra_array
    
    @staticmethod
    def bgra_to_rgba(total_bytes, bgra_array, gamma):
        for i in range(0, total_bytes, 4):
            red = bgra_array[i + 2] / 255.0
            green = bgra_array[i + 1] / 255.0
            blue = bgra_array[i] / 255.0
            # match gamma:
            #     case 'linear':
            #         red = red ** 2.0
            #         green = green ** 2.0
            #         blue = blue ** 2.0
            #     case 'srgb':
            #         red = utils.linear_to_srgb(red ** 2.0)
            #         green = utils.linear_to_srgb(green ** 2.0)
            #         blue = utils.linear_to_srgb(blue ** 2.0)
                    
            bgra_array[i] = int(red * 255)
            bgra_array[i + 1] = int(green * 255)
            bgra_array[i + 2] = int(blue * 255)
            
        return bgra_array
    
    @staticmethod
    def bgra_to_rgba_with_calculated_blue(total_bytes, bgra_array, _gamma, standard_orientation=False):
        for i in range(0, total_bytes, 4):
            if standard_orientation:
                red_byte = bgra_array[i + 1]
                green_byte = 255 - bgra_array[i + 2]
            else:
                red_byte = bgra_array[i + 2]
                green_byte = bgra_array[i + 1]

            red_byte = NORMAL_DEBUG_GAMMA_LOOKUP[red_byte]
            green_byte = NORMAL_DEBUG_GAMMA_LOOKUP[green_byte]
            red = red_byte / 255.0
            green = green_byte / 255.0
            blue_byte = int(calculate_z_vector(red, green) * 255 + 0.5)
                    
            bgra_array[i] = red_byte
            bgra_array[i + 1] = green_byte
            bgra_array[i + 2] = blue_byte
            
        return bgra_array
    
        # faces = {
        #     "back": bitmap.Clone(Rectangle(f * 3, f, f, f), bitmap.PixelFormat), # CUBEMAP: 0,1 HALO: 3,1
        #     "left": bitmap.Clone(Rectangle(0, f, f, f), bitmap.PixelFormat), # CUBEMAP: 1,1 HALO: 0,1
        #     "front": bitmap.Clone(Rectangle(f, f, f, f), bitmap.PixelFormat), # CUBEMAP: 2,1 HALO: 1,1
        #     "right": bitmap.Clone(Rectangle(2 * f, f, f, f), bitmap.PixelFormat), # CUBEMAP: 3,1 HALO: 2,1
        #     "bottom": bitmap.Clone(Rectangle(0, 2 * f, f, f), bitmap.PixelFormat), # CUBEMAP: 1,2 HALO: 0, 2
        #     "top": bitmap.Clone(Rectangle(0, 0, f, f), bitmap.PixelFormat), # CUBEMAP: 1,0 HALO: 0,0
        # }


    def extract_faces(self, cubemap, face_size):
        from System.Drawing import Rectangle # type: ignore
        faces = {
            "+Y": cubemap.Clone(Rectangle(0, 0, face_size, face_size), cubemap.PixelFormat),
            "-Y": cubemap.Clone(Rectangle(0, 2 * face_size, face_size, face_size), cubemap.PixelFormat),
            "+Z": cubemap.Clone(Rectangle(0, face_size, face_size, face_size), cubemap.PixelFormat),
            "-Z": cubemap.Clone(Rectangle(2 * face_size, face_size, face_size, face_size), cubemap.PixelFormat),
            "+X": cubemap.Clone(Rectangle(face_size, face_size, face_size, face_size), cubemap.PixelFormat),
            "-X": cubemap.Clone(Rectangle(3 * face_size, face_size, face_size, face_size), cubemap.PixelFormat)
        }
        return faces

    def sample_cubemap(self, faces, theta, phi, face_size):
        x = math.cos(phi) * math.cos(theta)
        y = math.sin(phi)
        z = math.cos(phi) * math.sin(theta)

        abs_x, abs_y, abs_z = abs(x), abs(y), abs(z)

        if abs_y >= abs_x and abs_y >= abs_z:
            face = "+Y" if y > 0 else "-Y"
            u = (x / abs_y + 1) / 2
            v = (z / abs_y + 1) / 2
        elif abs_x >= abs_y and abs_x >= abs_z:
            face = "+X" if x > 0 else "-X"
            u = (-z / abs_x + 1) / 2
            v = (-y / abs_x + 1) / 2
        else:
            face = "+Z" if z > 0 else "-Z"
            u = (x / abs_z + 1) / 2
            v = (-y / abs_z + 1) / 2

        u = max(0, min(int(u * (face_size - 1)), face_size - 1))
        v = max(0, min(int(v * (face_size - 1)), face_size - 1))

        return faces[face].GetPixel(u, v)

    @staticmethod
    def _equirectangular_face_type(height: int, width: int):
        if width % 8 != 0:
            raise ValueError("equirectangular cubemap width must be a multiple of 8")

        front, right, back, left, up, down = range(6)
        quarter_width = width // 4
        eighth_width = width // 8
        third_height = height // 3
        face_type = np.empty((height, width), dtype=np.int32)

        face_type[:, :eighth_width] = back
        face_type[:, eighth_width:eighth_width + quarter_width] = left
        face_type[:, eighth_width + quarter_width:eighth_width + 2 * quarter_width] = front
        face_type[:, eighth_width + 2 * quarter_width:eighth_width + 3 * quarter_width] = right
        face_type[:, eighth_width + 3 * quarter_width:] = back

        indices = np.linspace(-np.pi, np.pi, quarter_width, dtype=np.float32) / 4
        edge_rows = np.round(height / 2 - np.arctan(np.cos(indices)) * height / np.pi).astype(np.int32)
        row_indices = np.arange(third_height, dtype=np.int32)[:, None]
        top_mask = row_indices < edge_rows[None]
        bottom_mask = np.flip(top_mask, 0)

        face_type[:third_height, :eighth_width][top_mask[:, eighth_width:]] = up
        face_type[-third_height:, :eighth_width][bottom_mask[:, eighth_width:]] = down

        for index in range(3):
            start = eighth_width + index * quarter_width
            stop = start + quarter_width
            face_type[:third_height, start:stop][top_mask] = up
            face_type[-third_height:, start:stop][bottom_mask] = down

        remainder = width - stop
        face_type[:third_height, stop:][top_mask[:, :remainder]] = up
        face_type[-third_height:, stop:][bottom_mask[:, :remainder]] = down
        return face_type

    @staticmethod
    def _cubemap_equirectangular_coordinates(face_size: int, height: int, width: int):
        up, down = 4, 5
        u = np.linspace(-np.pi, np.pi, num=width, dtype=np.float32)
        v = np.linspace(np.pi / 2, -np.pi / 2, num=height, dtype=np.float32)
        u, v = np.meshgrid(u, v)

        face_type = BitmapTag._equirectangular_face_type(height, width)
        coor_x = np.empty((height, width), dtype=np.float32)
        coor_y = np.empty((height, width), dtype=np.float32)
        half_size = face_size / 2

        mask = face_type < up
        angles = u[mask] - (np.pi / 2 * face_type[mask])
        coor_x[mask] = half_size * np.tan(angles)
        coor_y[mask] = -half_size * np.tan(v[mask]) / np.cos(angles)

        mask = face_type == up
        distance = half_size * np.tan(np.pi / 2 - v[mask])
        coor_x[mask] = distance * np.sin(u[mask])
        coor_y[mask] = distance * np.cos(u[mask])

        mask = face_type == down
        distance = half_size * np.tan(np.pi / 2 - np.abs(v[mask]))
        coor_x[mask] = distance * np.sin(u[mask])
        coor_y[mask] = -distance * np.cos(u[mask])

        coor_x += half_size
        coor_y += half_size
        coor_x.clip(0, face_size, out=coor_x)
        coor_y.clip(0, face_size, out=coor_y)
        return face_type, coor_x, coor_y

    @staticmethod
    def _pad_cubemap_faces(cube_faces):
        front, right, back, left, up, down = range(6)
        padded = np.pad(cube_faces, ((0, 0), (1, 1), (1, 1), (0, 0)), mode="edge")

        padded[front, 0, 1:-1] = cube_faces[up, -1, :]
        padded[front, -1, 1:-1] = cube_faces[down, 0, :]
        padded[right, 0, 1:-1] = cube_faces[up, ::-1, -1]
        padded[right, -1, 1:-1] = cube_faces[down, :, -1]
        padded[back, 0, 1:-1] = cube_faces[up, 0, ::-1]
        padded[back, -1, 1:-1] = cube_faces[down, -1, ::-1]
        padded[left, 0, 1:-1] = cube_faces[up, :, 0]
        padded[left, -1, 1:-1] = cube_faces[down, ::-1, 0]
        padded[up, 0, 1:-1] = cube_faces[back, 0, ::-1]
        padded[up, -1, 1:-1] = cube_faces[front, 0, :]
        padded[down, 0, 1:-1] = cube_faces[front, -1, :]
        padded[down, -1, 1:-1] = cube_faces[back, -1, ::-1]

        padded[front, 1:-1, 0] = cube_faces[left, :, -1]
        padded[front, 1:-1, -1] = cube_faces[right, :, 0]
        padded[right, 1:-1, 0] = cube_faces[front, :, -1]
        padded[right, 1:-1, -1] = cube_faces[back, :, 0]
        padded[back, 1:-1, 0] = cube_faces[right, :, -1]
        padded[back, 1:-1, -1] = cube_faces[left, :, 0]
        padded[left, 1:-1, 0] = cube_faces[back, :, -1]
        padded[left, 1:-1, -1] = cube_faces[front, :, 0]
        padded[up, 1:-1, 0] = cube_faces[left, 0, :]
        padded[up, 1:-1, -1] = cube_faces[right, 0, ::-1]
        padded[down, 1:-1, 0] = cube_faces[left, -1, ::-1]
        padded[down, 1:-1, -1] = cube_faces[right, -1, :]

        return padded

    @staticmethod
    def _sample_cubemap_faces(cube_faces, face_type, coor_x, coor_y, mode: str):
        mode = mode.lower()
        if mode not in {"nearest", "linear", "bilinear"}:
            raise ValueError(f'unsupported cubemap interpolation mode "{mode}"')

        padded = BitmapTag._pad_cubemap_faces(cube_faces)
        coor_x = coor_x + 1
        coor_y = coor_y + 1

        if mode == "nearest":
            x = np.rint(coor_x).astype(np.int32)
            y = np.rint(coor_y).astype(np.int32)
            x.clip(0, padded.shape[2] - 1, out=x)
            y.clip(0, padded.shape[1] - 1, out=y)
            return padded[face_type, y, x]

        x0 = np.floor(coor_x).astype(np.int32)
        y0 = np.floor(coor_y).astype(np.int32)
        x1 = x0 + 1
        y1 = y0 + 1
        x0.clip(0, padded.shape[2] - 1, out=x0)
        x1.clip(0, padded.shape[2] - 1, out=x1)
        y0.clip(0, padded.shape[1] - 1, out=y0)
        y1.clip(0, padded.shape[1] - 1, out=y1)

        x_weight = (coor_x - x0)[..., None]
        y_weight = (coor_y - y0)[..., None]
        top_left = padded[face_type, y0, x0].astype(np.float32)
        top_right = padded[face_type, y0, x1].astype(np.float32)
        bottom_left = padded[face_type, y1, x0].astype(np.float32)
        bottom_right = padded[face_type, y1, x1].astype(np.float32)

        top = top_left * (1 - x_weight) + top_right * x_weight
        bottom = bottom_left * (1 - x_weight) + bottom_right * x_weight
        sampled = top * (1 - y_weight) + bottom * y_weight

        if np.issubdtype(cube_faces.dtype, np.integer):
            sampled = np.clip(sampled + 0.5, 0, np.iinfo(cube_faces.dtype).max)
            return sampled.astype(cube_faces.dtype)

        return sampled.astype(cube_faces.dtype, copy=False)

    @staticmethod
    def _cubemap_faces_to_equirectangular(faces: dict, height: int, width: int, mode: str):
        cube_faces = np.stack([faces[name] for name in "FRBLUD"], axis=0)
        if cube_faces.shape[1] != cube_faces.shape[2]:
            raise ValueError("cubemap faces must be square")

        face_type, coor_x, coor_y = BitmapTag._cubemap_equirectangular_coordinates(cube_faces.shape[1], height, width)
        return BitmapTag._sample_cubemap_faces(cube_faces, face_type, coor_x, coor_y, mode)

    @staticmethod
    def _rotate_cubemap_face(face, rotation: int):
        if rotation == 0:
            return face
        return np.rot90(face, k=rotation).copy()

    @classmethod
    def _cubemap_faces_from_vertical_rgba(cls, rgba: bytes, face_size: int) -> dict:
        strip = np.frombuffer(rgba, dtype=np.uint8).reshape(face_size * 6, face_size, 4)
        # Reach/H4 MCC Gen3 raw cube order, matching Reclaimer's MccGen3CubeLayout.
        layout = (
            ("R", -1),
            ("B", 2),
            ("L", 1),
            ("F", 0),
            ("U", 0),
            ("D", 2),
        )

        faces = {}
        for index, (name, rotation) in enumerate(layout):
            face = strip[index * face_size:(index + 1) * face_size, :, :]
            faces[name] = cls._rotate_cubemap_face(face, rotation)

        return faces

    @classmethod
    def _cubemap_vertical_rgba_to_equirectangular(cls, rgba: bytes, face_size: int, mode: str = "bilinear") -> bytes:
        faces = cls._cubemap_faces_from_vertical_rgba(rgba, face_size)
        equirectangular = cls._cubemap_faces_to_equirectangular(faces, face_size * 2, face_size * 4, mode)
        return np.ascontiguousarray(equirectangular).tobytes()

    def cubemap_to_equirectangular(self, bitmap, mode: str = "bilinear"):
        from System.Drawing import Bitmap # type: ignore
        from System import Array, Byte # type: ignore
        from System.Runtime.InteropServices import Marshal # type: ignore
        from System.Drawing import Rectangle, Imaging # type: ignore

        w, h = bitmap.Width, bitmap.Height
        bmp_data = bitmap.LockBits(
            Rectangle(0, 0, w, h),
            Imaging.ImageLockMode.ReadOnly,
            Imaging.PixelFormat.Format32bppArgb
        )
        stride = bmp_data.Stride
        buf = Array.CreateInstance(Byte, stride * h)
        Marshal.Copy(bmp_data.Scan0, buf, 0, buf.Length)
        bitmap.UnlockBits(bmp_data)

        np_buf = np.frombuffer(bytearray(buf), dtype=np.uint8)
        np_buf = np_buf.reshape((h, stride))[:, : w * 4] 
        img_rgba = np_buf.reshape((h, w, 4))
        img_rgb  = img_rgba[..., [2, 1, 0]]

        def face(x: int, y: int, size: int):
            return img_rgb[y * size:(y + 1) * size, x * size:(x + 1) * size]

        if w % 4 == 0 and h % 3 == 0 and w // 4 == h // 3:
            f = w // 4
            faces = {
                "U": face(0, 0, f),
                "D": face(0, 2, f),
                "F": face(0, 1, f),
                "R": face(1, 1, f),
                "B": face(2, 1, f),
                "L": face(3, 1, f),
            }
        elif h == w * 6:
            f = w
            order = ("R", "L", "U", "D", "F", "B")
            faces = {name: img_rgb[index * f:(index + 1) * f, 0:f] for index, name in enumerate(order)}
        elif w == h * 6:
            f = h
            order = ("R", "L", "U", "D", "F", "B")
            faces = {name: img_rgb[0:f, index * f:(index + 1) * f] for index, name in enumerate(order)}
        else:
            raise ValueError(f"unsupported cubemap bitmap layout {w}x{h}")


        out_h = f * 2
        out_w = f * 4

        equi = self._cubemap_faces_to_equirectangular(faces, out_h, out_w, mode)

        equi_bgr = equi[..., ::-1].copy(order='C')
        out_bmp  = Bitmap(out_w, out_h,
                        Imaging.PixelFormat.Format24bppRgb)
        out_data = out_bmp.LockBits(
            Rectangle(0, 0, out_w, out_h),
            Imaging.ImageLockMode.WriteOnly,
            out_bmp.PixelFormat
        )
        dest_stride = out_data.Stride
        row_bytes = out_w * 3
        for y in range(out_h):
            Marshal.Copy(
                Array[Byte](bytearray(equi_bgr[y].ravel())),
                0,
                out_data.Scan0 + y * dest_stride,
                row_bytes
            )
        out_bmp.UnlockBits(out_data)
        return out_bmp

    
    def _convert_cubemap(self, bitmap, suffix):
        equirect = self.cubemap_to_equirectangular(bitmap)
        return equirect, str(Path(self.data_dir, f"{self.tag_path.RelativePath}{suffix}_equirectangular").with_suffix('.tiff'))
    
    @staticmethod
    def _dotnet_bytes_to_bytes(data) -> bytes:
        if data is None:
            return b""
        if isinstance(data, bytes):
            return data
        if isinstance(data, bytearray):
            return bytes(data)
        try:
            return bytes(data)
        except TypeError:
            return bytes(bytearray(data))

    @staticmethod
    def _select_int(element, field_path: str, default=0) -> int:
        name = field_path.rpartition(':')[2]
        field = element.field(name)
        if field is None:
            return default
        options = field.options()
        if options is not None and options.current is not None:
            return options.current
        try:
            return int(field.value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _bitmap_format(element) -> int:
        """Resolve title-specific bitmap enums to Foundry's canonical values."""
        field = element.field('format')
        if field is None:
            return -1
        options = field.options()
        if options is not None and options.current_name is not None:
            return BITMAP_FORMAT_BY_NAME.get(options.current_name.casefold(), -1)
        try:
            return int(field.value)
        except (TypeError, ValueError):
            return -1

    @staticmethod
    def _bitmap_level_byte_size(width: int, height: int, bitmap_format: int) -> int:
        """Calculate one surface's byte count instead of trusting tag metadata."""
        if width <= 0 or height <= 0:
            return 0
        bytes_per_pixel = UNCOMPRESSED_BITMAP_BYTES_PER_PIXEL.get(bitmap_format)
        if bytes_per_pixel is not None:
            return width * height * bytes_per_pixel
        if bitmap_format in EIGHT_BYTE_BLOCK_BITMAP_FORMATS:
            block_bytes = 8
        elif bitmap_format in SIXTEEN_BYTE_BLOCK_BITMAP_FORMATS:
            block_bytes = 16
        else:
            return 0
        return max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block_bytes

    @classmethod
    def _bitmap_base_pixel_size(cls, width: int, height: int,
                                bitmap_format: int, bitmap_type: int,
                                depth: int = 1) -> int:
        """Return base-mip bytes, including every cube face or array layer.

        Real Reach tags can leave ``pixels size`` at zero while carrying a
        complete processed-data blob. blam-tags and Baboon derive this size
        from the storage format and dimensions; Foundry follows that rule.
        """
        surface_size = cls._bitmap_level_byte_size(width, height, bitmap_format)
        surface_count = 6 if bitmap_type == 2 else max(1, depth) if bitmap_type == 3 else 1
        return surface_size * surface_count

    @staticmethod
    def _expand_bits(values, bits: int):
        maximum = (1 << bits) - 1
        return ((values.astype(np.uint32) * 255 + maximum // 2) // maximum).astype(np.uint8)

    @staticmethod
    def _expand_bit_value(value: int, bits: int) -> int:
        maximum = (1 << bits) - 1
        return (value * 255 + maximum // 2) // maximum

    @classmethod
    def _decode_rgb565(cls, value: int) -> tuple[int, int, int]:
        return (
            cls._expand_bit_value((value >> 11) & 0x1F, 5),
            cls._expand_bit_value((value >> 5) & 0x3F, 6),
            cls._expand_bit_value(value & 0x1F, 5),
        )

    @staticmethod
    def _lerp_byte(start: int, end: int, fraction: float) -> int:
        return int(round((start * (1 - fraction)) + (end * fraction)))

    @classmethod
    def _decode_bc4_palette(cls, endpoint0: int, endpoint1: int) -> list[int]:
        palette = [0] * 8
        palette[0] = endpoint0
        palette[1] = endpoint1

        if endpoint0 > endpoint1:
            for index in range(1, 7):
                palette[index + 1] = cls._lerp_byte(endpoint0, endpoint1, index / 7)
        else:
            for index in range(1, 5):
                palette[index + 1] = cls._lerp_byte(endpoint0, endpoint1, index / 5)
            palette[6] = 0
            palette[7] = 255

        return palette

    @staticmethod
    def _byte_to_sbyte(value: int) -> int:
        return value - 256 if value > 127 else value

    @staticmethod
    def _sbyte_to_normal_byte(value: int) -> int:
        return max(0, min(value + 128, 255))

    @classmethod
    def _decode_bc4_signed_palette(cls, endpoint0: int, endpoint1: int) -> list[int]:
        endpoint0 = cls._byte_to_sbyte(endpoint0)
        endpoint1 = cls._byte_to_sbyte(endpoint1)
        palette = [0] * 8
        palette[0] = endpoint0
        palette[1] = endpoint1

        if endpoint0 > endpoint1:
            for index in range(1, 7):
                palette[index + 1] = cls._lerp_byte(endpoint0, endpoint1, index / 7)
        else:
            for index in range(1, 5):
                palette[index + 1] = cls._lerp_byte(endpoint0, endpoint1, index / 5)
            palette[6] = -128
            palette[7] = 127

        return palette

    @staticmethod
    def _decode_dxn_z(red: int, green: int) -> int:
        x = red / 255.0 * 2.0 - 1.0
        y = green / 255.0 * 2.0 - 1.0
        z = math.sqrt(max(0.0, 1.0 - x * x - y * y))
        return int(round((z + 1.0) * 0.5 * 255.0))

    @classmethod
    def _decode_dxt1_bitmap_rgba(cls, width: int, height: int, data: bytes) -> bytes | None:
        if width <= 0 or height <= 0:
            return None

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        expected_size = blocks_x * blocks_y * 8
        if len(data) < expected_size:
            return None

        output = bytearray(width * height * 4)
        data = data[:expected_size]

        for y_block in range(blocks_y):
            for x_block in range(blocks_x):
                src_index = (y_block * blocks_x + x_block) * 8
                color0 = struct.unpack_from("<H", data, src_index)[0]
                color1 = struct.unpack_from("<H", data, src_index + 2)[0]
                rgb0 = cls._decode_rgb565(color0)
                rgb1 = cls._decode_rgb565(color1)

                if color0 <= color1:
                    palette = (
                        (*rgb0, 255),
                        (*rgb1, 255),
                        (*(cls._lerp_byte(rgb0[channel], rgb1[channel], 1 / 2) for channel in range(3)), 255),
                        (0, 0, 0, 0),
                    )
                else:
                    palette = (
                        (*rgb0, 255),
                        (*rgb1, 255),
                        (*(cls._lerp_byte(rgb0[channel], rgb1[channel], 1 / 3) for channel in range(3)), 255),
                        (*(cls._lerp_byte(rgb0[channel], rgb1[channel], 2 / 3) for channel in range(3)), 255),
                    )

                color_bits = struct.unpack_from("<I", data, src_index + 4)[0]
                for pixel in range(16):
                    local_x = pixel % 4
                    local_y = pixel // 4
                    dest_x = x_block * 4 + local_x
                    dest_y = y_block * 4 + local_y
                    if dest_x >= width or dest_y >= height:
                        continue

                    rgba = palette[(color_bits >> (pixel * 2)) & 0x3]
                    dest_index = (dest_y * width + dest_x) * 4
                    output[dest_index] = rgba[0]
                    output[dest_index + 1] = rgba[1]
                    output[dest_index + 2] = rgba[2]
                    output[dest_index + 3] = rgba[3]

        return bytes(output)

    @classmethod
    def _decode_dxt3_bitmap_rgba(cls, width: int, height: int, data: bytes) -> bytes | None:
        if width <= 0 or height <= 0:
            return None

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        expected_size = blocks_x * blocks_y * 16
        if len(data) < expected_size:
            return None

        output = bytearray(width * height * 4)
        data = data[:expected_size]

        for y_block in range(blocks_y):
            for x_block in range(blocks_x):
                src_index = (y_block * blocks_x + x_block) * 16
                color0 = struct.unpack_from("<H", data, src_index + 8)[0]
                color1 = struct.unpack_from("<H", data, src_index + 10)[0]
                rgb0 = cls._decode_rgb565(color0)
                rgb1 = cls._decode_rgb565(color1)
                rgb_palette = (
                    rgb0,
                    rgb1,
                    tuple(cls._lerp_byte(rgb0[channel], rgb1[channel], 1 / 3) for channel in range(3)),
                    tuple(cls._lerp_byte(rgb0[channel], rgb1[channel], 2 / 3) for channel in range(3)),
                )
                color_bits = struct.unpack_from("<I", data, src_index + 12)[0]

                for pixel in range(16):
                    local_x = pixel % 4
                    local_y = pixel // 4
                    dest_x = x_block * 4 + local_x
                    dest_y = y_block * 4 + local_y
                    if dest_x >= width or dest_y >= height:
                        continue

                    alpha_row = struct.unpack_from("<H", data, src_index + local_y * 2)[0]
                    alpha = ((alpha_row >> (local_x * 4)) & 0xF) * 17
                    rgb = rgb_palette[(color_bits >> (pixel * 2)) & 0x3]
                    dest_index = (dest_y * width + dest_x) * 4
                    output[dest_index] = rgb[0]
                    output[dest_index + 1] = rgb[1]
                    output[dest_index + 2] = rgb[2]
                    output[dest_index + 3] = alpha

        return bytes(output)

    @staticmethod
    def _channel_values_to_rgba(width: int, height: int, values: bytes, mode: str) -> bytes:
        channel = np.frombuffer(values, dtype=np.uint8).reshape(height, width)
        rgba = np.zeros((height, width, 4), dtype=np.uint8)

        match mode:
            case "scalar":
                rgba[..., 0] = channel
                rgba[..., 1] = channel
                rgba[..., 2] = channel
                rgba[..., 3] = channel
            case "mono":
                rgba[..., 0] = channel
                rgba[..., 1] = channel
                rgba[..., 2] = channel
                rgba[..., 3] = 255
            case "alpha":
                rgba[..., 3] = channel
            case "red":
                rgba[..., 0] = channel
                rgba[..., 3] = 255
            case "green":
                rgba[..., 1] = channel
                rgba[..., 3] = 255
            case "blue":
                rgba[..., 2] = channel
                rgba[..., 3] = 255
            case _:
                rgba[..., 3] = 255

        return rgba.tobytes()

    @classmethod
    def _decode_dxt3a_values(cls, width: int, height: int, data: bytes) -> bytes | None:
        if width <= 0 or height <= 0:
            return None

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        expected_size = blocks_x * blocks_y * 8
        if len(data) < expected_size:
            return None

        output = bytearray(width * height)
        data = data[:expected_size]

        for y_block in range(blocks_y):
            for x_block in range(blocks_x):
                src_index = (y_block * blocks_x + x_block) * 8
                for local_y in range(4):
                    alpha_row = struct.unpack_from("<H", data, src_index + local_y * 2)[0]
                    for local_x in range(4):
                        dest_x = x_block * 4 + local_x
                        dest_y = y_block * 4 + local_y
                        if dest_x >= width or dest_y >= height:
                            continue

                        output[dest_y * width + dest_x] = ((alpha_row >> (local_x * 4)) & 0xF) * 17

        return bytes(output)

    @classmethod
    def _decode_dxt5a_values(cls, width: int, height: int, data: bytes) -> bytes | None:
        if width <= 0 or height <= 0:
            return None

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        expected_size = blocks_x * blocks_y * 8
        if len(data) < expected_size:
            return None

        output = bytearray(width * height)
        data = data[:expected_size]

        for y_block in range(blocks_y):
            for x_block in range(blocks_x):
                src_index = (y_block * blocks_x + x_block) * 8
                palette = cls._decode_bc4_palette(data[src_index], data[src_index + 1])
                bits = int.from_bytes(data[src_index + 2:src_index + 8], "little")

                for pixel in range(16):
                    local_x = pixel % 4
                    local_y = pixel // 4
                    dest_x = x_block * 4 + local_x
                    dest_y = y_block * 4 + local_y
                    if dest_x >= width or dest_y >= height:
                        continue

                    output[dest_y * width + dest_x] = palette[(bits >> (pixel * 3)) & 0x7]

        return bytes(output)

    @classmethod
    def _decode_dxt3a_bitmap_rgba(cls, width: int, height: int, data: bytes, mode: str) -> bytes | None:
        values = cls._decode_dxt3a_values(width, height, data)
        if values is None:
            return None
        return cls._channel_values_to_rgba(width, height, values, mode)

    @classmethod
    def _decode_dxt5a_bitmap_rgba(cls, width: int, height: int, data: bytes, mode: str) -> bytes | None:
        values = cls._decode_dxt5a_values(width, height, data)
        if values is None:
            return None
        return cls._channel_values_to_rgba(width, height, values, mode)

    @classmethod
    def _decode_ctx1_bitmap_rgba(cls, width: int, height: int, data: bytes) -> bytes | None:
        if width <= 0 or height <= 0:
            return None

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        expected_size = blocks_x * blocks_y * 8
        if len(data) < expected_size:
            return None

        output = bytearray(width * height * 4)
        data = data[:expected_size]

        for y_block in range(blocks_y):
            for x_block in range(blocks_x):
                src_index = (y_block * blocks_x + x_block) * 8
                endpoint0 = (data[src_index + 1], data[src_index + 0])
                endpoint1 = (data[src_index + 3], data[src_index + 2])
                palette = (
                    endpoint0,
                    endpoint1,
                    tuple(cls._lerp_byte(endpoint0[channel], endpoint1[channel], 1 / 3) for channel in range(2)),
                    tuple(cls._lerp_byte(endpoint0[channel], endpoint1[channel], 2 / 3) for channel in range(2)),
                )

                for local_y in range(4):
                    index_bits = data[src_index + 4 + local_y]
                    for local_x in range(4):
                        dest_x = x_block * 4 + local_x
                        dest_y = y_block * 4 + local_y
                        if dest_x >= width or dest_y >= height:
                            continue

                        red, green = palette[(index_bits >> (local_x * 2)) & 0x3]
                        dest_index = (dest_y * width + dest_x) * 4
                        output[dest_index] = red
                        output[dest_index + 1] = green
                        output[dest_index + 2] = cls._decode_dxn_z(red, green)
                        output[dest_index + 3] = 255

        return bytes(output)

    @classmethod
    def _decode_bc5_unsigned_channels(cls, width: int, height: int, data: bytes) -> tuple[bytes, bytes] | None:
        if width <= 0 or height <= 0:
            return None

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        expected_size = blocks_x * blocks_y * 16
        if len(data) < expected_size:
            return None

        red_output = bytearray(width * height)
        green_output = bytearray(width * height)
        data = data[:expected_size]

        for y_block in range(blocks_y):
            for x_block in range(blocks_x):
                src_index = (y_block * blocks_x + x_block) * 16
                red_palette = cls._decode_bc4_palette(data[src_index], data[src_index + 1])
                green_palette = cls._decode_bc4_palette(data[src_index + 8], data[src_index + 9])
                red_bits = int.from_bytes(data[src_index + 2:src_index + 8], "little")
                green_bits = int.from_bytes(data[src_index + 10:src_index + 16], "little")

                for pixel in range(16):
                    local_x = pixel % 4
                    local_y = pixel // 4
                    dest_x = x_block * 4 + local_x
                    dest_y = y_block * 4 + local_y
                    if dest_x >= width or dest_y >= height:
                        continue

                    dest_index = dest_y * width + dest_x
                    red_output[dest_index] = red_palette[(red_bits >> (pixel * 3)) & 0x7]
                    green_output[dest_index] = green_palette[(green_bits >> (pixel * 3)) & 0x7]

        return bytes(red_output), bytes(green_output)

    @classmethod
    def _decode_dxn_mono_alpha_bitmap_rgba(cls, width: int, height: int, data: bytes) -> bytes | None:
        channels = cls._decode_bc5_unsigned_channels(width, height, data)
        if channels is None:
            return None

        mono = np.frombuffer(channels[0], dtype=np.uint8).reshape(height, width)
        alpha = np.frombuffer(channels[1], dtype=np.uint8).reshape(height, width)
        rgba = np.empty((height, width, 4), dtype=np.uint8)
        rgba[..., 0] = mono
        rgba[..., 1] = mono
        rgba[..., 2] = mono
        rgba[..., 3] = alpha
        return rgba.tobytes()

    @classmethod
    def _decode_dxt5_bitmap_rgba(cls, width: int, height: int, data: bytes) -> bytes | None:
        if width <= 0 or height <= 0:
            return None

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        expected_size = blocks_x * blocks_y * 16
        if len(data) < expected_size:
            return None

        output = bytearray(width * height * 4)
        data = data[:expected_size]

        for y_block in range(blocks_y):
            for x_block in range(blocks_x):
                src_index = (y_block * blocks_x + x_block) * 16

                alpha_palette = [0] * 8
                alpha_palette[0] = data[src_index]
                alpha_palette[1] = data[src_index + 1]

                if alpha_palette[0] > alpha_palette[1]:
                    for index in range(1, 7):
                        alpha_palette[index + 1] = cls._lerp_byte(alpha_palette[0], alpha_palette[1], index / 7)
                else:
                    for index in range(1, 5):
                        alpha_palette[index + 1] = cls._lerp_byte(alpha_palette[0], alpha_palette[1], index / 5)
                    alpha_palette[6] = 0
                    alpha_palette[7] = 255

                color0 = struct.unpack_from("<H", data, src_index + 8)[0]
                color1 = struct.unpack_from("<H", data, src_index + 10)[0]
                rgb0 = cls._decode_rgb565(color0)
                rgb1 = cls._decode_rgb565(color1)
                rgb_palette = (
                    rgb0,
                    rgb1,
                    tuple(cls._lerp_byte(rgb0[channel], rgb1[channel], 1 / 3) for channel in range(3)),
                    tuple(cls._lerp_byte(rgb0[channel], rgb1[channel], 2 / 3) for channel in range(3)),
                )

                alpha_bits = int.from_bytes(data[src_index + 2:src_index + 8], "little")
                color_bits = struct.unpack_from("<I", data, src_index + 12)[0]

                for pixel in range(16):
                    local_x = pixel % 4
                    local_y = pixel // 4
                    dest_x = x_block * 4 + local_x
                    dest_y = y_block * 4 + local_y
                    if dest_x >= width or dest_y >= height:
                        continue

                    rgb_index = (color_bits >> (pixel * 2)) & 0x3
                    alpha_index = (alpha_bits >> (pixel * 3)) & 0x7
                    dest_index = (dest_y * width + dest_x) * 4
                    rgb = rgb_palette[rgb_index]

                    output[dest_index] = rgb[0]
                    output[dest_index + 1] = rgb[1]
                    output[dest_index + 2] = rgb[2]
                    output[dest_index + 3] = alpha_palette[alpha_index]

        return bytes(output)

    @classmethod
    def _decode_dxn_bitmap_rgba(cls, width: int, height: int, data: bytes) -> bytes | None:
        if width <= 0 or height <= 0:
            return None

        blocks_x = (width + 3) // 4
        blocks_y = (height + 3) // 4
        expected_size = blocks_x * blocks_y * 16
        if len(data) < expected_size:
            return None

        output = bytearray(width * height * 4)
        data = data[:expected_size]

        for y_block in range(blocks_y):
            for x_block in range(blocks_x):
                src_index = (y_block * blocks_x + x_block) * 16
                red_palette = cls._decode_bc4_signed_palette(data[src_index], data[src_index + 1])
                green_palette = cls._decode_bc4_signed_palette(data[src_index + 8], data[src_index + 9])
                red_bits = int.from_bytes(data[src_index + 2:src_index + 8], "little")
                green_bits = int.from_bytes(data[src_index + 10:src_index + 16], "little")

                for pixel in range(16):
                    local_x = pixel % 4
                    local_y = pixel // 4
                    dest_x = x_block * 4 + local_x
                    dest_y = y_block * 4 + local_y
                    if dest_x >= width or dest_y >= height:
                        continue

                    shift = pixel * 3
                    red = cls._sbyte_to_normal_byte(red_palette[(red_bits >> shift) & 0x7])
                    green = cls._sbyte_to_normal_byte(green_palette[(green_bits >> shift) & 0x7])
                    dest_index = (dest_y * width + dest_x) * 4

                    output[dest_index] = red
                    output[dest_index + 1] = green
                    output[dest_index + 2] = cls._decode_dxn_z(red, green)
                    output[dest_index + 3] = 255

        return bytes(output)

    @classmethod
    def _decode_uncompressed_bitmap_rgba(cls, width: int, height: int, bitmap_format: int, data: bytes) -> bytes | None:
        bytes_per_pixel = UNCOMPRESSED_BITMAP_BYTES_PER_PIXEL.get(bitmap_format)
        if bytes_per_pixel is None:
            return None

        expected_size = width * height * bytes_per_pixel
        if width <= 0 or height <= 0 or len(data) < expected_size:
            return None

        data = data[:expected_size]
        rgba = np.empty((height, width, 4), dtype=np.uint8)

        match bitmap_format:
            case 0:  # A8
                alpha = np.frombuffer(data, dtype=np.uint8).reshape(height, width)
                rgba[..., 0] = 0
                rgba[..., 1] = 0
                rgba[..., 2] = 0
                rgba[..., 3] = alpha
            case 1:  # Y8
                luminance = np.frombuffer(data, dtype=np.uint8).reshape(height, width)
                rgba[..., 0] = luminance
                rgba[..., 1] = luminance
                rgba[..., 2] = luminance
                rgba[..., 3] = 255
            case 2:  # AY8
                value = np.frombuffer(data, dtype=np.uint8).reshape(height, width)
                rgba[..., 0] = value
                rgba[..., 1] = value
                rgba[..., 2] = value
                rgba[..., 3] = value
            case 3:  # A8Y8; source bytes are alpha, luminance.
                ay = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 2)
                rgba[..., 0] = ay[..., 1]
                rgba[..., 1] = ay[..., 1]
                rgba[..., 2] = ay[..., 1]
                rgba[..., 3] = ay[..., 0]
            case 4:  # R8
                red = np.frombuffer(data, dtype=np.uint8).reshape(height, width)
                rgba[..., 0] = red
                rgba[..., 1] = 0
                rgba[..., 2] = 0
                rgba[..., 3] = 255
            case 6:  # R5G6B5
                values = np.frombuffer(data, dtype="<u2").reshape(height, width)
                rgba[..., 0] = cls._expand_bits((values >> 11) & 0x1F, 5)
                rgba[..., 1] = cls._expand_bits((values >> 5) & 0x3F, 6)
                rgba[..., 2] = cls._expand_bits(values & 0x1F, 5)
                rgba[..., 3] = 255
            case 8:  # A1R5G5B5
                values = np.frombuffer(data, dtype="<u2").reshape(height, width)
                rgba[..., 0] = cls._expand_bits((values >> 10) & 0x1F, 5)
                rgba[..., 1] = cls._expand_bits((values >> 5) & 0x1F, 5)
                rgba[..., 2] = cls._expand_bits(values & 0x1F, 5)
                rgba[..., 3] = np.where((values & 0x8000) != 0, 255, 0).astype(np.uint8)
            case 9 | 17:  # A4R4G4B4 / A4R4G4B4 font
                values = np.frombuffer(data, dtype="<u2").reshape(height, width)
                rgba[..., 0] = cls._expand_bits((values >> 8) & 0x0F, 4)
                rgba[..., 1] = cls._expand_bits((values >> 4) & 0x0F, 4)
                rgba[..., 2] = cls._expand_bits(values & 0x0F, 4)
                rgba[..., 3] = cls._expand_bits((values >> 12) & 0x0F, 4)
            case 10 | 11:  # X8R8G8B8 / A8R8G8B8; source bytes are BGRA.
                bgra = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4)
                rgba[..., 0] = bgra[..., 2]
                rgba[..., 1] = bgra[..., 1]
                rgba[..., 2] = bgra[..., 0]
                rgba[..., 3] = bgra[..., 3] if bitmap_format == BITMAP_FORMAT_A8R8G8B8 else 255
            case 20:  # Software RGBFP32; source bytes are 32-bit float RGB.
                rgb_float = np.frombuffer(data, dtype="<f4").reshape(height, width, 3)
                rgb = np.clip(rgb_float, 0.0, 1.0)
                rgba[..., :3] = (rgb * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 3] = 255
            case 22:  # V8U8; signed two-channel normal data.
                vu = np.frombuffer(data, dtype=np.int8).reshape(height, width, 2)
                red = (vu[..., 0].astype(np.int16) + 128).astype(np.uint8)
                green = (vu[..., 1].astype(np.int16) + 128).astype(np.uint8)
                x = red.astype(np.float32) / 255.0 * 2.0 - 1.0
                y = green.astype(np.float32) / 255.0 * 2.0 - 1.0
                blue = np.sqrt(np.clip(1.0 - x * x - y * y, 0.0, 1.0)) * 0.5 + 0.5
                rgba[..., 0] = red
                rgba[..., 1] = green
                rgba[..., 2] = (blue * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 3] = 255
            case 23:  # G8B8; signed channels, matching Reclaimer's Xbox G8B8 path.
                gb = np.frombuffer(data, dtype=np.int8).reshape(height, width, 2)
                rgba[..., 0] = 0
                rgba[..., 1] = (gb[..., 1].astype(np.int16) + 128).astype(np.uint8)
                rgba[..., 2] = (gb[..., 0].astype(np.int16) + 128).astype(np.uint8)
                rgba[..., 3] = 255
            case 24:  # ABGRFP32; source bytes are 32-bit float A, B, G, R.
                abgr = np.frombuffer(data, dtype="<f4").reshape(height, width, 4)
                rgba[..., 0] = (np.clip(abgr[..., 3], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 1] = (np.clip(abgr[..., 2], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 2] = (np.clip(abgr[..., 1], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 3] = (np.clip(abgr[..., 0], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
            case 25:  # ABGRFP16; source bytes are 16-bit float A, B, G, R.
                abgr = np.frombuffer(data, dtype="<f2").reshape(height, width, 4).astype(np.float32)
                rgba[..., 0] = (np.clip(abgr[..., 3], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 1] = (np.clip(abgr[..., 2], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 2] = (np.clip(abgr[..., 1], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 3] = (np.clip(abgr[..., 0], 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
            case 26:  # 16F_MONO
                mono = np.frombuffer(data, dtype="<f2").reshape(height, width).astype(np.float32)
                value = (np.clip(mono, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 0] = value
                rgba[..., 1] = value
                rgba[..., 2] = value
                rgba[..., 3] = 255
            case 27:  # 16F_RED
                red = np.frombuffer(data, dtype="<f2").reshape(height, width).astype(np.float32)
                rgba[..., 0] = (np.clip(red, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 1] = 0
                rgba[..., 2] = 0
                rgba[..., 3] = 255
            case 28:  # Q8W8V8U8; signed four-channel vector data.
                values = np.frombuffer(data, dtype=np.int8).reshape(height, width, 4).astype(np.int16)
                rgba[...] = np.clip(values + 128, 0, 255).astype(np.uint8)
            case 29:  # A2R10G10B10
                values = np.frombuffer(data, dtype="<u4").reshape(height, width)
                rgba[..., 0] = cls._expand_bits((values >> 20) & 0x3FF, 10)
                rgba[..., 1] = cls._expand_bits((values >> 10) & 0x3FF, 10)
                rgba[..., 2] = cls._expand_bits(values & 0x3FF, 10)
                rgba[..., 3] = cls._expand_bits((values >> 30) & 0x03, 2)
            case 30:  # A16B16G16R16
                abgr = np.frombuffer(data, dtype="<u2").reshape(height, width, 4)
                rgba[..., 0] = ((abgr[..., 3].astype(np.uint32) * 255 + 32767) // 65535).astype(np.uint8)
                rgba[..., 1] = ((abgr[..., 2].astype(np.uint32) * 255 + 32767) // 65535).astype(np.uint8)
                rgba[..., 2] = ((abgr[..., 1].astype(np.uint32) * 255 + 32767) // 65535).astype(np.uint8)
                rgba[..., 3] = ((abgr[..., 0].astype(np.uint32) * 255 + 32767) // 65535).astype(np.uint8)
            case 31:  # V16U16; signed two-channel normal data.
                vu = np.frombuffer(data, dtype="<i2").reshape(height, width, 2).astype(np.int32)
                red = np.clip(((vu[..., 0] + 32768) * 255 + 32767) // 65535, 0, 255).astype(np.uint8)
                green = np.clip(((vu[..., 1] + 32768) * 255 + 32767) // 65535, 0, 255).astype(np.uint8)
                x = red.astype(np.float32) / 255.0 * 2.0 - 1.0
                y = green.astype(np.float32) / 255.0 * 2.0 - 1.0
                blue = np.sqrt(np.clip(1.0 - x * x - y * y, 0.0, 1.0)) * 0.5 + 0.5
                rgba[..., 0] = red
                rgba[..., 1] = green
                rgba[..., 2] = (blue * 255.0 + 0.5).astype(np.uint8)
                rgba[..., 3] = 255
            case 32:  # L16
                luminance = np.frombuffer(data, dtype="<u2").reshape(height, width)
                value = ((luminance.astype(np.uint32) * 255 + 32767) // 65535).astype(np.uint8)
                rgba[..., 0] = value
                rgba[..., 1] = value
                rgba[..., 2] = value
                rgba[..., 3] = 255
            case 33:  # R16G16
                rg = np.frombuffer(data, dtype="<u2").reshape(height, width, 2)
                rgba[..., 0] = ((rg[..., 0].astype(np.uint32) * 255 + 32767) // 65535).astype(np.uint8)
                rgba[..., 1] = ((rg[..., 1].astype(np.uint32) * 255 + 32767) // 65535).astype(np.uint8)
                rgba[..., 2] = 0
                rgba[..., 3] = 255
            case 34:  # SIGNED_R16G16B16A16
                signed = np.frombuffer(data, dtype="<i2").reshape(height, width, 4).astype(np.int32)
                rgba[...] = np.clip(((signed + 32768) * 255 + 32767) // 65535, 0, 255).astype(np.uint8)
            case 48:  # DEPTH24
                depth = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3).astype(np.uint32)
                value24 = depth[..., 0] | (depth[..., 1] << 8) | (depth[..., 2] << 16)
                value = ((value24 * 255 + 8388607) // 16777215).astype(np.uint8)
                rgba[..., 0] = value
                rgba[..., 1] = value
                rgba[..., 2] = value
                rgba[..., 3] = 255
            case _:
                return None

        return rgba.tobytes()

    @classmethod
    def _decode_bitmap_rgba(cls, width: int, height: int, bitmap_format: int, data: bytes) -> bytes | None:
        if bitmap_format in UNCOMPRESSED_BITMAP_FORMAT_NAMES:
            return cls._decode_uncompressed_bitmap_rgba(width, height, bitmap_format, data)
        if bitmap_format == BITMAP_FORMAT_DXT1:
            return cls._decode_dxt1_bitmap_rgba(width, height, data)
        if bitmap_format == BITMAP_FORMAT_DXT3:
            return cls._decode_dxt3_bitmap_rgba(width, height, data)
        if bitmap_format == BITMAP_FORMAT_DXT5:
            return cls._decode_dxt5_bitmap_rgba(width, height, data)
        if bitmap_format in {BITMAP_FORMAT_DXT3A, BITMAP_FORMAT_DXT3A_1111}:
            return cls._decode_dxt3a_bitmap_rgba(width, height, data, "scalar")
        if bitmap_format == BITMAP_FORMAT_DXT3A_ALPHA:
            return cls._decode_dxt3a_bitmap_rgba(width, height, data, "alpha")
        if bitmap_format == BITMAP_FORMAT_DXT3A_MONO:
            return cls._decode_dxt3a_bitmap_rgba(width, height, data, "mono")
        if bitmap_format == BITMAP_FORMAT_DXT5A:
            return cls._decode_dxt5a_bitmap_rgba(width, height, data, "scalar")
        if bitmap_format == BITMAP_FORMAT_DXT5A_ALPHA:
            return cls._decode_dxt5a_bitmap_rgba(width, height, data, "alpha")
        if bitmap_format == BITMAP_FORMAT_DXT5A_MONO:
            return cls._decode_dxt5a_bitmap_rgba(width, height, data, "mono")
        if bitmap_format == BITMAP_FORMAT_DXN:
            return cls._decode_dxn_bitmap_rgba(width, height, data)
        if bitmap_format == BITMAP_FORMAT_CTX1:
            return cls._decode_ctx1_bitmap_rgba(width, height, data)
        if bitmap_format == BITMAP_FORMAT_DXN_MONO_ALPHA:
            return cls._decode_dxn_mono_alpha_bitmap_rgba(width, height, data)
        if bitmap_format == BITMAP_FORMAT_DXT5_RED:
            return cls._decode_dxt5a_bitmap_rgba(width, height, data, "red")
        if bitmap_format == BITMAP_FORMAT_DXT5_GREEN:
            return cls._decode_dxt5a_bitmap_rgba(width, height, data, "green")
        if bitmap_format == BITMAP_FORMAT_DXT5_BLUE:
            return cls._decode_dxt5a_bitmap_rgba(width, height, data, "blue")
        return None

    @staticmethod
    def _bitmap_color_space_conversion_enabled() -> bool:
        return _bitmap_color_space_conversion_enabled()

    @staticmethod
    def _linear_to_srgb(linear):
        return np.where(
            linear <= 0.0031308,
            linear * 12.92,
            1.055 * np.power(linear, 1.0 / 2.4) - 0.055,
        )

    @classmethod
    def _convert_xrgb_rgba_to_srgb(cls, rgba: bytes, source_gamma: float) -> bytes:
        pixels = np.frombuffer(rgba, dtype=np.uint8).copy()
        pixel_rgba = pixels.reshape(-1, 4)
        rgb = pixel_rgba[:, :3].astype(np.float32) / 255.0
        linear = np.power(rgb, source_gamma)
        srgb = cls._linear_to_srgb(linear)
        pixel_rgba[:, :3] = np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return pixels.tobytes()

    def _should_convert_xrgb_to_srgb(self, convert_color_space: bool) -> bool:
        return (
            convert_color_space
            and self._bitmap_color_space_conversion_enabled()
            and self.get_gamma_name() == "xrgb"
        )

    @staticmethod
    def _tiff_entry(tag: int, field_type: int, count: int, value: int):
        if field_type == 3 and count == 1:
            value_data = struct.pack("<H", value) + b"\x00\x00"
        elif field_type == 4 and count == 1:
            value_data = struct.pack("<I", value)
        else:
            value_data = struct.pack("<I", value)
        return struct.pack("<HHI", tag, field_type, count) + value_data

    @classmethod
    def _write_rgba_tiff(cls, path: str, width: int, height: int, rgba: bytes):
        entries = 11
        ifd_offset = 8
        ifd_size = 2 + entries * 12 + 4
        bits_per_sample = struct.pack("<HHHH", 8, 8, 8, 8)
        extra_samples = struct.pack("<H", 2)
        bits_offset = ifd_offset + ifd_size
        extra_offset = bits_offset + len(bits_per_sample)
        pixel_offset = extra_offset + len(extra_samples)

        ifd = bytearray()
        ifd += struct.pack("<H", entries)
        ifd += cls._tiff_entry(256, 4, 1, width)              # ImageWidth
        ifd += cls._tiff_entry(257, 4, 1, height)             # ImageLength
        ifd += cls._tiff_entry(258, 3, 4, bits_offset)        # BitsPerSample
        ifd += cls._tiff_entry(259, 3, 1, 1)                  # Compression: none
        ifd += cls._tiff_entry(262, 3, 1, 2)                  # PhotometricInterpretation: RGB
        ifd += cls._tiff_entry(273, 4, 1, pixel_offset)       # StripOffsets
        ifd += cls._tiff_entry(277, 3, 1, 4)                  # SamplesPerPixel
        ifd += cls._tiff_entry(278, 4, 1, height)             # RowsPerStrip
        ifd += cls._tiff_entry(279, 4, 1, len(rgba))          # StripByteCounts
        ifd += cls._tiff_entry(284, 3, 1, 1)                  # PlanarConfiguration: chunky
        ifd += cls._tiff_entry(338, 3, 1, 2)  # ExtraSamples: unassociated alpha
        ifd += struct.pack("<I", 0)

        with open(path, "wb") as handle:
            handle.write(b"II")
            handle.write(struct.pack("<H", 42))
            handle.write(struct.pack("<I", ifd_offset))
            handle.write(ifd)
            handle.write(bits_per_sample)
            handle.write(extra_samples)
            handle.write(rgba)

    def _raw_tiff_save_path(self, suffix: str):
        if suffix:
            return str(Path(self.data_dir, self.tag_path.RelativePath, f"{self.tag_path.ShortName}{suffix}").with_suffix('.tiff'))
        return str(Path(self.data_dir, self.tag_path.RelativePath).with_suffix('.tiff'))

    def _raw_cubemap_equirectangular_save_path(self, suffix: str):
        return str(Path(
            self.data_dir, f"{self.tag_path.RelativePath}_equirectangular{suffix}"
        ).with_suffix('.tiff'))

    @staticmethod
    def _uncompressed_rgba_tiff(tiff: bytes) -> tuple[int, int, bytes]:
        """Read the simple uncompressed RGBA TIFF emitted by blam-tags."""
        if len(tiff) < 8 or tiff[:2] not in {b"II", b"MM"}:
            raise BitmapExtractionError("blam-tags returned an invalid TIFF header")
        endian = "<" if tiff[:2] == b"II" else ">"

        def unpack(fmt: str, offset: int):
            size = struct.calcsize(fmt)
            if offset < 0 or offset + size > len(tiff):
                raise BitmapExtractionError("blam-tags TIFF directory exceeds the returned data")
            return struct.unpack_from(endian + fmt, tiff, offset)

        if unpack("H", 2)[0] != 42:
            raise BitmapExtractionError("blam-tags returned an unsupported TIFF version")
        directory_offset = unpack("I", 4)[0]
        entry_count = unpack("H", directory_offset)[0]
        type_sizes = {1: 1, 3: 2, 4: 4}
        entries: dict[int, tuple[int, ...]] = {}
        for index in range(entry_count):
            entry_offset = directory_offset + 2 + index * 12
            tag, field_type, count = unpack("HHI", entry_offset)
            item_size = type_sizes.get(field_type)
            if item_size is None:
                continue
            byte_count = item_size * count
            value_offset = entry_offset + 8
            if byte_count > 4:
                value_offset = unpack("I", value_offset)[0]
            if value_offset + byte_count > len(tiff):
                raise BitmapExtractionError(
                    f"blam-tags TIFF field {tag} exceeds the returned data")
            format_char = {1: "B", 3: "H", 4: "I"}[field_type]
            entries[tag] = unpack(format_char * count, value_offset)

        def required(tag: int) -> tuple[int, ...]:
            values = entries.get(tag)
            if values is None:
                raise BitmapExtractionError(f"blam-tags TIFF is missing required field {tag}")
            return values

        width = required(256)[0]
        height = required(257)[0]
        bits = required(258)
        compression = required(259)[0]
        strip_offsets = required(273)
        samples = required(277)[0]
        strip_sizes = required(279)
        planar = entries.get(284, (1,))[0]
        orientation = entries.get(274, (1,))[0]
        if compression != 1 or samples != 4 or any(value != 8 for value in bits):
            raise BitmapExtractionError(
                "blam-tags cubemap TIFF must be uncompressed 8-bit RGBA")
        if planar != 1 or orientation != 1:
            raise BitmapExtractionError(
                "blam-tags cubemap TIFF must use chunky top-left pixel storage")
        if len(strip_offsets) != len(strip_sizes):
            raise BitmapExtractionError("blam-tags TIFF strip tables have different lengths")
        rgba = b"".join(
            tiff[offset:offset + size]
            for offset, size in zip(strip_offsets, strip_sizes, strict=True)
        )
        expected = width * height * 4
        if len(rgba) != expected:
            raise BitmapExtractionError(
                f"blam-tags TIFF has {len(rgba)} pixel bytes; expected {expected}")
        return width, height, rgba

    def _save_classic_cubemap_equirectangular(self, tiff: bytes, suffix: str) -> str:
        width, height, rgba = self._uncompressed_rgba_tiff(tiff)
        if width % 4 or height % 3 or width // 4 != height // 3:
            raise BitmapExtractionError(
                f"Classic cubemap TIFF must use a 4x3 square-face cross, got {width}x{height}")
        face_size = width // 4
        cross = np.frombuffer(rgba, dtype=np.uint8).reshape(height, width, 4)

        def face(column: int, row: int):
            x = column * face_size
            y = row * face_size
            return cross[y:y + face_size, x:x + face_size]

        # blam-tags emits the DirectX cross used by the classic Tool pipeline:
        # +Y on top, -Y below, and +X/+Z/-X/-Z across the middle row.
        faces = {
            "U": face(1, 0),
            "R": face(0, 1),
            "F": face(1, 1),
            "L": face(2, 1),
            "B": face(3, 1),
            "D": face(1, 2),
        }
        equirectangular = self._cubemap_faces_to_equirectangular(
            faces, face_size * 2, face_size * 4, "bilinear")
        save_path = self._raw_cubemap_equirectangular_save_path(suffix)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        self._write_rgba_tiff(
            save_path, face_size * 4, face_size * 2,
            np.ascontiguousarray(equirectangular).tobytes())
        return save_path

    def _bitmap_format_name(self, bitmap_format: int) -> str:
        return BITMAP_FORMAT_NAMES.get(bitmap_format, f"unknown format {bitmap_format}")

    def _bitmap_type_name(self, bitmap_type: int) -> str:
        return BITMAP_TYPE_NAMES.get(bitmap_type, f"unknown type {bitmap_type}")

    def _bitmap_extraction_details(self, bitmap_element, frame_index: int) -> str:
        width = self._select_int(bitmap_element, "ShortInteger:width")
        height = self._select_int(bitmap_element, "ShortInteger:height")
        depth = self._select_int(bitmap_element, "CharInteger:depth", 1)
        bitmap_type = self._select_int(bitmap_element, "CharEnum:type")
        bitmap_format = self._bitmap_format(bitmap_element)
        pixels_offset = self._select_int(bitmap_element, "LongInteger:pixels offset", -1)
        pixels_size = self._select_int(bitmap_element, "LongInteger:pixels size", -1)
        resolved_size = self._bitmap_base_pixel_size(
            width, height, bitmap_format, bitmap_type, depth)
        return (
            f"path={self.tag_path.RelativePath}, frame={frame_index}, "
            f"type={bitmap_type} ({self._bitmap_type_name(bitmap_type)}), "
            f"format={bitmap_format} ({self._bitmap_format_name(bitmap_format)}), "
            f"size={width}x{height}x{depth}, pixels offset={pixels_offset}, "
            f"declared pixels size={pixels_size}, resolved base size={resolved_size}"
        )

    def _save_single_raw_tiff(self, frame_index: int, suffix: str, convert_color_space: bool) -> str:
        if self.game in {'halo1', 'halo2'}:
            save_path = self._raw_tiff_save_path(suffix)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            try:
                tiff = self.tag.bitmap_tiff(frame_index)
            except (IndexError, ValueError) as exc:
                raise BitmapExtractionError(
                    f"Classic bitmap extraction failed for {self.tag_path.RelativePath}, "
                    f"frame {frame_index}: {exc}") from exc
            with open(save_path, 'wb') as stream:
                stream.write(tiff)
            if self.is_cubemap:
                return self._save_classic_cubemap_equirectangular(tiff, suffix)
            return save_path

        bitmap_elements = self.block_bitmaps
        if frame_index < 0 or frame_index >= len(bitmap_elements):
            raise BitmapExtractionError(
                f"Bitmap extraction failed for {self.tag_path.RelativePath}: frame {frame_index} is out of range "
                f"for {len(bitmap_elements)} bitmap frame(s)"
            )

        bitmap_element = bitmap_elements[frame_index]
        width = self._select_int(bitmap_element, "ShortInteger:width")
        height = self._select_int(bitmap_element, "ShortInteger:height")
        depth = self._select_int(bitmap_element, "CharInteger:depth", 1)
        bitmap_type = self._select_int(bitmap_element, "CharEnum:type")
        bitmap_format = self._bitmap_format(bitmap_element)
        pixels_offset = self._select_int(bitmap_element, "LongInteger:pixels offset", -1)
        pixels_size = self._bitmap_base_pixel_size(
            width, height, bitmap_format, bitmap_type, depth)
        details = self._bitmap_extraction_details(bitmap_element, frame_index)

        if bitmap_type not in {0, 2, 3}:
            raise BitmapExtractionError(f"Unsupported bitmap type for new extraction: {details}")
        if bitmap_type == 2 and width != height:
            raise BitmapExtractionError(f"Cubemap faces must be square for new extraction: {details}")
        if bitmap_format not in SUPPORTED_BITMAP_FORMAT_NAMES:
            raise BitmapExtractionError(f"Unsupported bitmap format for new extraction: {details}")
        if pixels_offset < 0 or pixels_size <= 0:
            raise BitmapExtractionError(f"Invalid bitmap pixel data range for new extraction: {details}")

        processed_data = bytes(self.required_field(self.tag.root(), 'processed pixel data').value)
        end = pixels_offset + pixels_size
        if end > len(processed_data):
            raise BitmapExtractionError(
                f"Bitmap pixel data exceeds processed data length for new extraction: {details}, "
                f"processed data length={len(processed_data)}"
            )

        surface_count = 6 if bitmap_type == 2 else max(1, depth) if bitmap_type == 3 else 1
        decode_height = height * surface_count
        rgba = self._decode_bitmap_rgba(width, decode_height, bitmap_format, processed_data[pixels_offset:end])
        if rgba is None:
            raise BitmapExtractionError(f"Failed to decode bitmap pixels for new extraction: {details}")

        if self._should_convert_xrgb_to_srgb(convert_color_space):
            rgba = self._convert_xrgb_rgba_to_srgb(rgba, self.get_gamma_value())

        save_path = self._raw_tiff_save_path(suffix)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        self._write_rgba_tiff(save_path, width, decode_height, rgba)

        if bitmap_type != 2:
            return save_path

        equirectangular_path = self._raw_cubemap_equirectangular_save_path(suffix)
        equirectangular = self._cubemap_vertical_rgba_to_equirectangular(rgba, width)
        os.makedirs(os.path.dirname(equirectangular_path), exist_ok=True)
        self._write_rgba_tiff(equirectangular_path, width * 4, height * 2, equirectangular)
        return equirectangular_path

    def _save_single(self, blue_channel_fix: bool, format: str, frame_index: int, suffix: str):
        if format != 'tiff':
            raise BitmapExtractionError(
                f"New bitmap extraction only supports TIFF output for now: "
                f"path={self.tag_path.RelativePath}, requested format={format}"
            )

        return self._save_single_raw_tiff(frame_index, suffix, not blue_channel_fix)
        
    def save_to_tiff(self, blue_channel_fix=False, format='tiff') -> str | None:
        global path_cache
        first_suffix = "_00001" if len(self.block_bitmaps) > 1 else ""
        expected_tiff_path = (Path(self._raw_cubemap_equirectangular_save_path(first_suffix))
                              if self.is_cubemap else
                              Path(self.data_dir, self.tag_path.RelativePath).with_suffix('.tiff'))
        expected_tif_path = expected_tiff_path.with_suffix('.tif')
        if expected_tiff_path in path_cache and expected_tiff_path.exists():
            return str(expected_tiff_path)
        elif expected_tif_path in path_cache and expected_tif_path.exists():
            return str(expected_tif_path)
        
        
        if not len(self.block_bitmaps):
            return
        bitmap_elements = self.block_bitmaps
        if len(bitmap_elements) > 1:
            for index in range(len(bitmap_elements)):
                temp_path = self._save_single(blue_channel_fix, format, index, f"_{index + 1:05}")
                if index == 0:
                    tiff_path = temp_path
            
            
            if not self.is_cubemap:
                full_tiff_path = Path(tiff_path)
                utils.run_tool(["plate", str(full_tiff_path.with_suffix(""))], null_output=True)
                # create plate but no longer use it blender
        else:
            tiff_path = self._save_single(blue_channel_fix, format, 0, "")
        
        
        path_cache.add(Path(tiff_path))
        return tiff_path
    
    def normal_type(self):
        if self.game in {'halo1', 'halo2'}:
            return NormalType.DIRECTX
        return NormalType.OPENGL if self._enum_index(self.tag.root(), 'Usage') == 36 else NormalType.DIRECTX
    
    def has_bitmap_data(self):
        return len(self.block_bitmaps)
    
    def is_linear(self):
        return self.curve_index() == 3

    def curve_index(self) -> int:
        if self.game in {'halo1', 'halo2'}:
            return 3 if self.used_as_normal_map() else 5
        return self._enum_index(self.block_bitmaps[0], 'curve')
    
    def used_as_normal_map(self):
        if self.game in {'halo1', 'halo2'}:
            options = self.longenum_usage.options()
            usage = options.current_name.casefold() if options is not None and options.current_name else ''
            return any(name in usage for name in ('height map', 'vector map', 'bump', 'normal', 'embm'))
        return self._enum_index(self.tag.root(), 'Usage') in {2, 3, 18, 19, 20, 21, 36, 38}
    
    def uses_srgb(self):
        if self.game in {'halo1', 'halo2'}:
            return not self.used_as_normal_map()
        return self._enum_index(self.tag.root(), 'Usage') in {0, 5, 7}
    
    def get_gamma_name(self) -> str:
        match self.curve_index():
            case 3:
                return 'linear'
            case 5:
                return 'srgb'
            case _:
                return 'xrgb'
            
    def get_gamma_value(self) -> str:
        match self.curve_index():
            case 0:
                return 1.95
            case 1:
                return 1.95
            case 2:
                return 2.0
            case 3:
                return 1.0
            case 4:
                return 1.0
            case 5:
                return 2.2
    
    def _source_gamma_from_color_space(self, color_space: str):
        match color_space:
            case 'sRGB':
                return 2.2
        
        return 1.0 # NOTE keeping this 1.0 as 0.96 seems dangerous and needs further testing. 0.96 produces more accurate colors than 1.0
    
    def get_shader_type(self):
        options = self.longenum_usage.options()
        if options is None or options.current is None:
            raise ValueError(f'{self.path}: bitmap usage has an unknown enum value')
        return options.names[options.current]
            
def lerp(p1: float, p2: float, fraction: float) -> float:
    return (p1 * (1 - fraction)) + (p2 * fraction)

def calculate_z_vector(r: float, g: float) -> float:
    x = lerp(-1.0, 1.0, r)
    y = lerp(-1.0, 1.0, g)
    z = sqrt(max(0, 1 - x * x - y * y))

    return (z + 1) / 2

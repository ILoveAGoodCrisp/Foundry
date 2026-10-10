"""Blender-facing bitmap extraction backed by blam-tags."""

from math import sqrt
import os
import struct
from pathlib import Path
import numpy as np

from ..constants import NormalType
from ..bitmap_usage import CLASSIC_GAMES, bitmap_usage_names, infer_bitmap_usage, resolve_bitmap_usage
from .backend import TagDocument
from .blender import BlenderTag
from .. import utils
import bpy

path_cache: set[Path] = set()
NORMAL_DEBUG_GAMMA = 2.2
NORMAL_DEBUG_GAMMA_LOOKUP = tuple(
    int(round(((i / 255.0) ** NORMAL_DEBUG_GAMMA) * 255.0))
    for i in range(256)
)
NORMAL_DEBUG_GAMMA_LOOKUP_NP = np.array(NORMAL_DEBUG_GAMMA_LOOKUP, dtype=np.uint8)

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
    
def bitmap_to_image(path: str | Path, always_extract_bitmaps=False, *, frame_index=None) -> BitmapInfo:
    
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
            cubemap_frame_count = len(bitmap.block_bitmaps)
            if frame_index is not None and not 0 <= frame_index < cubemap_frame_count:
                raise BitmapExtractionError(f'Bitmap frame {frame_index} is unavailable for {rel_path}')
            rel_path = f"{bitmap.tag_path.RelativePath}_equirectangular"
            system_tiff_path = Path(data_dir, rel_path).with_suffix('.tiff')
            alt_system_tiff_path = system_tiff_path.with_suffix(".tif")
            sequence_tiff_path = system_tiff_path.with_name(
                f"{system_tiff_path.stem}_00001{system_tiff_path.suffix}")
            alt_sequence_tiff_path = sequence_tiff_path.with_suffix(".tif")

        info.curve = bitmap.curve_index()
        info.for_normal = bitmap.used_as_normal_map()
        info.shader_type = bitmap.get_shader_type()
        first_bitmap = bitmap.block_bitmaps[frame_index or 0]
        array_shape = tuple(int(bitmap.required_field(first_bitmap, key).value)
                            for key in ('width', 'height', 'depth'))
        incomplete_cubemap_sequence = False
        if info.cubemap and len(bitmap.block_bitmaps) > 1:
            # Prefer the numbered sequence over a stale single-image preview.
            cubemap_sequence_paths = [system_tiff_path.with_name(
                f"{system_tiff_path.stem}_{index + 1:05}{system_tiff_path.suffix}")
                for index in range(cubemap_frame_count)]
            system_tiff_path = sequence_tiff_path
            alt_system_tiff_path = alt_sequence_tiff_path
            tiff_sequence_exists = all(preview.is_file() for preview in cubemap_sequence_paths)
            tif_sequence_exists = all(preview.with_suffix('.tif').is_file() for preview in cubemap_sequence_paths)
            incomplete_cubemap_sequence = not (tiff_sequence_exists or tif_sequence_exists)
            if tif_sequence_exists and not tiff_sequence_exists:
                system_tiff_path = alt_system_tiff_path
            if incomplete_cubemap_sequence:
                path_cache.discard(system_tiff_path)
                path_cache.discard(alt_system_tiff_path)
        if (always_extract_bitmaps or incomplete_cubemap_sequence
                or (frame_index is not None and len(bitmap.block_bitmaps) > 1)):
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

        if info.cubemap:
            source_frame = frame_index if frame_index is not None else 0
            suffix = f'_{source_frame + 1:05}' if len(bitmap.block_bitmaps) > 1 else ''
            cube_source = Path(bitmap._raw_tiff_save_path(suffix))
            if not cube_source.exists():
                # A cached preview alone is not sufficient for shader export.
                bitmap._save_single_raw_tiff(source_frame, suffix, not info.for_normal)
            
    if not info.image_path:
        return info
    
    image_path = Path(info.image_path)
    if info.cubemap:
        sequence_paths = ([preview.with_suffix(image_path.suffix) for preview in cubemap_sequence_paths]
                          if cubemap_frame_count > 1 else [])
    else:
        sequence_paths = _bitmap_sequence_paths(image_path)
    if frame_index is not None:
        if sequence_paths:
            if not 0 <= frame_index < len(sequence_paths):
                raise BitmapExtractionError(f'Bitmap frame {frame_index} is unavailable for {rel_path}')
            info.image_path = str(sequence_paths[frame_index])
        elif frame_index != 0:
            raise BitmapExtractionError(f'Bitmap frame {frame_index} is unavailable for {rel_path}')
    elif sequence_paths and (len(sequence_paths) > info.sequence_length or image_path.is_dir()):
        info.sequence_length = max(info.sequence_length, len(sequence_paths))
        # Every node has its own ImageUser and frame driver. All materials
        # must anchor that zero-based index to the same first bitmap.
        info.image_path = str(sequence_paths[0])
            
    image = bpy.data.images.load(filepath=info.image_path, check_existing=True)
    if frame_index is not None and image.source == 'SEQUENCE':
        image = image.copy()
        image.source = 'FILE'
    image.nwo.filepath = utils.relative_path(info.image_path)
    image['foundry_source_bitmap_path'] = utils.relative_path(path)
    image['foundry_bitmap_shape'] = array_shape
    image.nwo.shader_type = info.shader_type
    if info.cubemap:
        image['foundry_cubemap_source'] = str(cube_source)

    apply_bitmap_info_color_space(image, info)

    if info.sequence_length > 1:
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
        
    def new_bitmap(self, bitmap_name, bitmap_type, color_space, *, preserve_size=False, bitmap_shape='auto'):
        requested = bitmap_type if bitmap_type and bitmap_type != 'default' else infer_bitmap_usage(bitmap_name, self.game)
        bitmap_type = resolve_bitmap_usage(bitmap_name, bitmap_type, self.game)
        if self.game in CLASSIC_GAMES:
            if requested in {'usage:default', *self.longenum_usage.options().names}:
                requested = infer_bitmap_usage(bitmap_name, self.game)
            self._new_classic_bitmap(bitmap_type, requested, bitmap_shape)
            return

        normal_bitmap_types = (
            "ZBrush Bump Map (from Bump Map)",
            "Normal Map (aka zbump)",
            "Normal Map (from Standard Orientation of Maya, Modo, Zbrush)",
        )

        # Native field-name normalization treats ':' as metadata, including in
        # the Float Map label. Use the index from this game's exact definition.
        self.longenum_usage.set(bitmap_usage_names(self.game).index(bitmap_type))
        self.charenum_usage.set('force PRETTY')
        if not len(self.block_usage_override):
            # A zero-filled override replaces Tool's complete usage preset,
            # including height conversion, sprite packing and volume slicing.
            # Only create overrides for the usages Foundry configures below.
            if bitmap_type not in (*normal_bitmap_types, 'Material Map', 'Diffuse Map',
                                   'Blend Map (linear for terrains)', 'Self-Illum Map',
                                   'Cube Map (Reflection Map)', 'Detail Map'):
                self.tag_has_changes = True
                return
            self.block_usage_override.add()
        override = self.block_usage_override[0]
        source_gamma = self.required_field(override, 'source gamma')
        if bitmap_type in normal_bitmap_types:
            source_gamma_value = 1.0
        else:
            source_gamma_value = self._source_gamma_from_color_space(color_space)
        source_gamma.set(source_gamma_value)
        if source_gamma_value > 2.0:
            curve = 'sRGB' if self.game in {'halo3', 'halo3odst'} else 'sRGB (gamma 2.2)'
            self._set_enum(override, 'bitmap curve', curve)
        elif source_gamma_value > 1:
            self._set_enum(override, 'bitmap curve', "xRGB (gamma about 2.0)")
        else:
            self._set_enum(override, 'bitmap curve', "linear")
            
        self.required_field(override, 'flags').set_flag("Ignore Curve Override", True)
        if preserve_size:
            self.required_field(override, 'flags').set_flag("Dont Allow Size Optimization", True)
        if bitmap_type == 'Cube Map (Reflection Map)':
            # A newly allocated usage override is zero-filled (2D/no slicing).
            self._set_enum(override, 'type', 'cube map')
            self._set_enum(override, 'slicer', 'Cube Map Slicer')
        if bitmap_type in ("Material Map", "Diffuse Map", "Blend Map (linear for terrains)", "Self-Illum Map", "Cube Map (Reflection Map)", "Detail Map"):
            self._set_enum(override, 'bitmap format', 'DXT5 (Compressed Color + Compressed 8-bit Alpha)')
            if bitmap_type == 'Material Map':
                self.required_field(override, 'mipmap limit').set(-1)
        elif bitmap_type in normal_bitmap_types:
            self._set_enum(override, 'bitmap format', 'DXN Compressed Normals (better)')
            
        self.tag_has_changes = True
        
    def _new_classic_bitmap(self, usage, requested, shape):
        root = self.tag.root()
        self.longenum_usage.set(usage)
        shapes = {'2d': 0, '3d': 1, 'cube': 2, 'sprites': 3, 'interface': 4}
        if shape == 'auto':
            if requested == 'Cube Map (Reflection Map)':
                shape = 'cube'
            elif requested == '3D Texture':
                shape = '3d'
            elif requested.startswith('Sprite'):
                shape = 'sprites'
            elif requested == 'Interface Bitmap':
                shape = 'interface'
        if shape != 'auto':
            self.required_field(root, 'type').set(shapes[shape])
        if self._enum_index(root, 'type') == 4:
            # Classic interface/linear textures cannot use DXT compression.
            self.required_field(root, 'encoding format' if self.game == 'halo1' else 'format').set(4)
        if self.tag_is_new:
            # DXT5 preserves authored alpha. Normal/height maps must retain the
            # classic compiler's own normal encoding instead.
            if (self._enum_index(root, 'type') != 4 and
                    usage in {'default', 'alpha blend', 'alpha-blend', 'detail map', 'light map'}):
                self.required_field(root, 'encoding format' if self.game == 'halo1' else 'format').set(2)
            processing = self.required_field(root, 'processing').as_struct() if self.game == 'halo1' else root
            self.required_field(processing, 'bump height').set(1.0)
            self.required_field(processing, 'detail fade factor').set(0.5)
        if requested.startswith('Sprite'):
            sprite = self.required_field(root, 'sprite processing').as_struct() if self.game == 'halo1' else root
            sprite_usage = 2 if 'Double Multiply' in requested else 1 if 'White Background' in requested else 0
            self.required_field(sprite, 'usage' if self.game == 'halo1' else 'sprite usage').set(sprite_usage)
        self.tag_has_changes = True

    def get_granny_data(
        self, fill_alpha: bool, calc_blue_channel: bool
    ) -> tuple[int, int, int, bytes] | None:
        if not len(self.block_bitmaps):
            return None
        bitmap = self.block_bitmaps[0]
        width = self._select_int(bitmap, 'width')
        height = self._select_int(bitmap, 'height')
        bitmap_type = self._select_int(bitmap, 'type')
        if bitmap_type != 0 or width <= 0 or height <= 0:
            return None
        try:
            decoded_width, decoded_height, rgba = self._uncompressed_rgba_tiff(
                self.tag.bitmap_tiff(0))
        except (IndexError, ValueError) as exc:
            raise BitmapExtractionError(
                f'Native bitmap extraction failed for Granny data in {self.path}: {exc}') from exc
        if (decoded_width, decoded_height) != (width, height):
            raise BitmapExtractionError(
                f'Native bitmap dimensions changed in {self.path}: '
                f'{decoded_width}x{decoded_height}, expected {width}x{height}')
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
    def _equirectangular_face_type(height: int, width: int):
        if height <= 0 or width <= 0:
            raise ValueError("equirectangular dimensions must be positive")
        # Sample pixel centers rather than duplicating both longitude endpoints.
        u = (np.arange(width, dtype=np.float64) + .5) * (2 * np.pi / width) - np.pi
        v = np.pi / 2 - (np.arange(height, dtype=np.float64) + .5) * (np.pi / height)
        x = np.cos(v[:, None]) * np.sin(u[None, :])
        z = np.cos(v[:, None]) * np.cos(u[None, :])
        y = np.broadcast_to(np.sin(v[:, None]), x.shape)
        axis = np.argmax(np.stack([np.abs(x), np.abs(y), np.abs(z)]), axis=0)
        # Keep the existing F/R/B/L/U/D convention and panorama orientation.
        return np.where(axis == 1, np.where(y >= 0, 4, 5),
                        np.where(axis == 0, np.where(x >= 0, 1, 3),
                                 np.where(z >= 0, 0, 2))).astype(np.int32)

    @staticmethod
    def _cubemap_equirectangular_coordinates(face_size: int, height: int, width: int):
        up, down = 4, 5
        u = (np.arange(width, dtype=np.float64) + .5) * (2 * np.pi / width) - np.pi
        v = np.pi / 2 - (np.arange(height, dtype=np.float64) + .5) * (np.pi / height)
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

        # Cube UV edges are between texel centers: -0.5 and size-0.5.
        # Allow those half-texel border samples so bilinear filtering blends
        # the current face with the correctly oriented adjacent face.
        coor_x += half_size - .5
        coor_y += half_size - .5
        coor_x.clip(-.5, face_size - .5, out=coor_x)
        coor_y.clip(-.5, face_size - .5, out=coor_y)
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

        # A cube corner touches three faces. Average their corner texels for
        # the otherwise undefined diagonal border tap used by bilinear sampling.
        for row, inner_row in [(0, 1), (-1, -2)]:
            for column, inner_column in [(0, 1), (-1, -2)]:
                corner = (padded[:, row, inner_column].astype(np.float64) +
                          padded[:, inner_row, column].astype(np.float64) +
                          padded[:, inner_row, inner_column].astype(np.float64)) / 3
                if np.issubdtype(cube_faces.dtype, np.integer):corner = np.rint(corner)
                padded[:, row, column] = corner.astype(cube_faces.dtype)

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

    def _save_cubemap_equirectangular(self, tiff: bytes, suffix: str) -> str:
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




    def _save_single_raw_tiff(self, frame_index: int, suffix: str, convert_color_space: bool) -> str:
        save_path = self._raw_tiff_save_path(suffix)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        try:
            tiff = self.tag.bitmap_tiff(frame_index)
        except (IndexError, ValueError) as exc:
            raise BitmapExtractionError(
                f"Native bitmap extraction failed for {self.tag_path.RelativePath}, "
                f"frame {frame_index}: {exc}") from exc

        if (self.game not in {'halo1', 'halo2'} and
                self._should_convert_xrgb_to_srgb(convert_color_space)):
            width, height, rgba = self._uncompressed_rgba_tiff(tiff)
            rgba = self._convert_xrgb_rgba_to_srgb(rgba, self.get_gamma_value())
            self._write_rgba_tiff(save_path, width, height, rgba)
            with open(save_path, 'rb') as stream:
                tiff = stream.read()
        else:
            with open(save_path, 'wb') as stream:
                stream.write(tiff)

        if self.is_cubemap:
            return self._save_cubemap_equirectangular(tiff, suffix)
        return save_path

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
                              Path(self._raw_tiff_save_path(first_suffix)))
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
            
            
            # Classic frames are extracted natively; Blender uses the first
            # frame, not a Tool-generated plate. Do not require a kit executable.
            if not self.is_cubemap and self.game not in {'halo1', 'halo2'}:
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
        usage = self.longenum_usage.options().current_name
        return any(word in usage for word in ('Bump Map', 'Normal Map'))
    
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


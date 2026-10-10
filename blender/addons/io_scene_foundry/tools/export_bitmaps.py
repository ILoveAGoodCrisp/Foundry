

import os
import re
from subprocess import CalledProcessError
from pathlib import Path
import bpy
from ..tags.bitmap import BitmapTag
from ..bitmap_usage import CLASSIC_GAMES, bitmap_import_command, image_bitmap_type
from .bitmap_tiff import write_image_tiff, write_cube_tiff

import logging

from .. import utils

logging.basicConfig(level=logging.ERROR)
BITMAP_EXPORT_VERSION = 3

def recursive_image_search(tree_owner, images: set):
    nodes = tree_owner.node_tree.nodes
    for n in nodes:
        if getattr(n, "image", 0):
            images.add(n.image)
        elif n.type == 'GROUP':
            recursive_image_search(n, images)

class NWO_OT_ReloadImages(bpy.types.Operator):
    bl_idname = "nwo.reload_images"
    bl_label = "Reload Images"
    bl_description = "Reloads all images if they has been changed externally (e.g. edited in Photoshop)"
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob is None:
            return False
        
        return ob.active_material
    
    def execute(self, context):
        images = set()
        recursive_image_search(context.object.active_material, images)
        for im in images:
            im.reload()
            
        self.report({'INFO'}, f"Reloaded {len(images)} images")    
        
        return {'FINISHED'}
        

class NWO_ExportBitmapsSingle(bpy.types.Operator):
    bl_idname = "nwo.export_bitmaps_single"
    bl_label = "Export Bitmap"
    
    @classmethod
    def poll(cls, context):
        ob = context.object
        if ob is None:
            return False
        
        mat = ob.active_material
        
        if mat is None:
            return False
        
        return mat.nwo.active_image and utils.current_project_valid()

    def execute(self, context):
        image = context.object.active_material.nwo.active_image
        try:
            if export_bitmap(image, self.report) is None:
                return {'CANCELLED'}
        except (RuntimeError, ValueError, OSError, CalledProcessError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}

def bitmap_export_image(image):
    """Resolve Foundry's cubemap preview to its original cube-layout source."""
    source = image.get('foundry_cubemap_source')
    candidates = [Path(source)] if source else []
    preview = False
    paths = [Path(image.filepath_from_user())]
    if image.nwo.filepath:
        paths.append(Path(utils.get_data_path(), image.nwo.filepath))
    for path in paths:
        match = re.fullmatch(r'(.+)_equirectangular(_\d{5})?', path.stem, re.IGNORECASE)
        if not match:
            continue
        preview = True
        stem, frame = match.groups()
        raw = path.with_name(stem + path.suffix)
        if frame:
            raw = raw.with_suffix('') / (stem + frame + path.suffix)
        candidates.extend((raw, raw.with_suffix('.tiff'), raw.with_suffix('.tif')))
    if not source and not preview:
        return image
    raw_path = next((p for p in candidates if p.is_file()), None)
    if raw_path is None:
        raise RuntimeError(f'{image.name}: original cubemap TIFF is missing; reimport its source bitmap before exporting')
    cube = bpy.data.images.load(str(raw_path), check_existing=True)
    cube.colorspace_settings.name = image.colorspace_settings.name
    cube.alpha_mode = 'CHANNEL_PACKED'
    if utils.get_game() in CLASSIC_GAMES:
        cube.nwo.bitmap_type = 'usage:default'
        cube.nwo.bitmap_shape = 'cube'
    else:
        cube.nwo.bitmap_type = 'Cube Map (Reflection Map)'
    if cube.get('foundry_bitmap_export_root') != str(utils.get_data_path()):
        cube.nwo.filepath = ''
    cube['foundry_cubemap_export'] = True
    return cube


def bitmap_needs_rebuild(image):
    # Rebuild tags made by the old Deflate/preview export, even if they exist.
    return bool(image.get('foundry_channel_conversion') or image.get('foundry_cubemap_export')) and (
        image.get('foundry_bitmap_export_version') != BITMAP_EXPORT_VERSION or
        image.get('foundry_bitmap_export_root') != str(utils.get_data_path()))


def export_bitmap(image: bpy.types.Image, report=None, *, bitmaps_data_dir=None):
    image = bitmap_export_image(image)
    data_dir = utils.get_data_path()
    asset_path = utils.get_asset_path()
    
    if image.name != image.name_full:
        print("Image is linked, skipping")
        return
    
    user_path = Path(image.filepath_from_user())
    user_path_contains_data_dir = user_path.is_relative_to(data_dir)
            
    # Create a bitmap folder in the asset directory
    bitmaps_data_dir = Path(bitmaps_data_dir) if bitmaps_data_dir else Path(data_dir, asset_path, "bitmaps")
        # get a list of textures associated with this material
    # export the texture as a tiff to the asset bitmaps folder
    valid_name = utils.valid_image_name(image.name) + ".tif"
    if ".tiff" in image.name:
        valid_name += 'f'
        
    image.nwo.source_name = valid_name
    
    if image.get('foundry_cubemap_export'):
        # Tool's cube slicer uses a different face arrangement from extracted
        # DX crosses. Keep the source intact and write a lossless target plate.
        bitmaps_data_dir.mkdir(parents=True, exist_ok=True)
        destination = bitmaps_data_dir / (user_path.stem + '_cube.tif')
        write_cube_tiff(image, destination, classic=utils.get_game() in CLASSIC_GAMES)
        image.nwo.filepath = utils.relative_path(destination)
        image.nwo.source_name = destination.name
    elif (user_path.suffix.lower() in {'.tif', '.tiff'} and user_path_contains_data_dir
          and user_path.is_file() and not image.packed_file):
        logging.log(logging.DEBUG, f"Image is TIFF and has user path and user path starts with {data_dir} and {user_path} exists")
        image.nwo.filepath = utils.relative_path(user_path)
        if image.nwo.reexport_tiff or image.packed_file:
            if image.has_data or image.source == 'SEQUENCE':
                image.nwo.filepath = save_image_as(image, user_path.parent, tiff_name=image.nwo.source_name)
            else:
                utils.print_warning(f"{image.name} has no data. Cannot export Tif")
                if report:
                    report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
                return

    elif Path(image.nwo.filepath.lower()).suffix in {".tif", ".tiff"} and Path(data_dir, image.nwo.filepath).exists():
        logging.log(logging.DEBUG, f"Image has nwo filepath and {Path(data_dir, image.nwo.filepath)} exists")
        # Regenerate cached float-image exports too: older versions wrote
        # 16-bit TIFFs that classic Tool cannot decode.
        if (image.nwo.reexport_tiff or image.packed_file or
                (utils.get_game() in CLASSIC_GAMES and image.source == 'GENERATED' and image.is_float)):
            if image.has_data or image.source == 'SEQUENCE':
                image.nwo.filepath = save_image_as(image, Path(data_dir, image.nwo.filepath).parent, tiff_name=image.nwo.source_name)
            else:
                utils.print_warning(f"{image.name} has no data. Cannot export Tif")
                if report:
                    report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
                return
    else:
        logging.log(logging.DEBUG, "We hit the else...")
        if image.has_data or image.source == 'SEQUENCE':
            image.nwo.filepath = save_image_as(image, bitmaps_data_dir, tiff_name=image.nwo.source_name)
            logging.log(logging.DEBUG, f"nwo filepath: {image.nwo.filepath}")
        else:
            utils.print_warning(f"{image.name} has no data. Cannot export Tif")
            if report:
                report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
            return
            
    nwo_path = Path(image.nwo.filepath)
    if image.nwo.filepath and Path(data_dir, image.nwo.filepath).exists():
        converted = bool(image.get('foundry_channel_conversion'))
        if converted:
            # Also repair generated TIFFs retained in an older .blend file.
            write_image_tiff(image, Path(data_dir, image.nwo.filepath))
            if image.source == 'GENERATED':
                image.filepath_raw = str(Path(data_dir, image.nwo.filepath))
                image.source = 'FILE'
                image.reload()
        path_no_ext = nwo_path.with_suffix("")
        bitmap_path = nwo_path.with_suffix(".bitmap")
        with BitmapTag(path=bitmap_path) as bitmap:
            bitmap.new_bitmap(nwo_path.stem, image_bitmap_type(image), image.colorspace_settings.name,
                              preserve_size=converted or bool(image.get('foundry_cubemap_export')),
                              bitmap_shape=image.nwo.bitmap_shape)

        game = utils.get_game()
        # The H1 editing kit ships tool.exe only, regardless of the global
        # Tool Fast preference used by the later games.
        utils.run_tool(bitmap_import_command(path_no_ext, game), False, False,
                       force_tool=game == 'halo1')
        # Some versions of Tool return success after a failed TIFF decode.
        with BitmapTag(path=bitmap_path) as bitmap:
            if not bitmap.has_bitmap_data():
                raise RuntimeError(f'{image.name}: bitmap compiler produced no pixels')
            if converted or image.get('foundry_cubemap_export'):
                if converted:
                    first = bitmap.block_bitmaps[0]
                    actual = tuple(bitmap._select_int(first, field) for field in ('width', 'height'))
                    # preserve_size uses DXT5, whose smallest block is 4x4.
                    # Older conversions can contain valid 1x1 constant maps.
                    expected = tuple(max(4, dimension) for dimension in image.size)
                    if actual not in (tuple(image.size), expected):
                        raise RuntimeError(f'{image.name}: compiled bitmap is {actual}, expected {tuple(image.size)}')
                elif not bitmap.is_cubemap:
                    raise RuntimeError(f'{image.name}: bitmap compiler did not produce a cubemap')
                image['foundry_bitmap_export_version'] = BITMAP_EXPORT_VERSION
                image['foundry_bitmap_export_root'] = str(data_dir)
    else:
        if report:
            report({'ERROR'}, f"{image.name} has no data filepath. Cannot build bitmap")
            utils.print_error(f"{image.name} has no data filepath. Cannot build bitmap")
            return
        utils.print_error(f"{image.name} has no data filepath. Cannot build bitmap")
        return

    if report is not None:
        report({"INFO"}, "Bitmap Export Complete")
    return bitmap_path
                
def save_image_as(image, dir, tiff_name=""):
    dir = Path(dir)
    data_dir = Path(utils.get_data_path())
    if not dir.is_absolute():
        return ""
    temp_scene = None
    sequence_frame = None
    try:
        if image.source == 'SEQUENCE':
            # save_render uses its own ImageUser, which can select a missing
            # frame zero. Export the sequence's explicit source frame instead.
            sequence_frame = image.copy()
            sequence_frame.source = 'FILE'
            sequence_frame.reload()
            image = sequence_frame
        temp_scene = bpy.data.scenes.new("temp_tiff_export_scene")
        settings = temp_scene.render.image_settings
        settings.file_format = "TIFF"
        settings.color_mode = "RGBA" if image.alpha_mode != "NONE" else "RGB"
        # H1/H2 Tool reject 16-bit-per-channel TIFFs, including Blender's
        # default export of generated float images.
        settings.color_depth = "16" if image.is_float and utils.get_game() not in CLASSIC_GAMES else "8"
        settings.tiff_codec = "NONE"
        temp_scene.view_settings.view_transform = (
            'Standard' if image.colorspace_settings.name == 'sRGB' else 'Raw')
        temp_scene.view_settings.look = 'None'
        dir.mkdir(parents=True, exist_ok=True)
        full_path = Path(dir, tiff_name)
        image.save_render(filepath=str(full_path), scene=temp_scene)
        return str(full_path.relative_to(data_dir))
    finally:
        if temp_scene is not None:
            bpy.data.scenes.remove(temp_scene)
        if sequence_frame is not None:
            bpy.data.images.remove(sequence_frame)

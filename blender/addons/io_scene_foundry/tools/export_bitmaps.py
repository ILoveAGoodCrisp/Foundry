

import os
from pathlib import Path
import bpy
from ..managed_blam.bitmap import BitmapTag

import logging

from .. import utils

logging.basicConfig(level=logging.ERROR)

class NWO_ExportBitmapsSingle(bpy.types.Operator):
    bl_idname = "nwo.export_bitmaps_single"
    bl_label = "Export Bitmap"

    def execute(self, context):
        image = context.object.active_material.nwo.active_image
        nwo = image.nwo
        export_bitmap(image, self.report)
        return {'FINISHED'}

def export_bitmap(image: bpy.types.Image, report=None):
    data_dir = utils.get_data_path()
    asset_path = utils.get_asset_path()
    
    if image.name != image.name_full:
        print("Image is linked, skipping")
        return
    
    user_path = Path(image.filepath_from_user())
    user_path_contains_data_dir = user_path.is_relative_to(data_dir)
            
    # Create a bitmap folder in the asset directory
    bitmaps_data_dir = Path(data_dir, asset_path, "bitmaps")
        # get a list of textures associated with this material
    # export the texture as a tiff to the asset bitmaps folder
    valid_name = utils.valid_image_name(image.name) + ".tif"
    if ".tiff" in image.name:
        valid_name += 'f'
        
    image.nwo.source_name = valid_name
    
    if user_path and user_path_contains_data_dir and user_path.exists():
        logging.log(logging.DEBUG, f"Image is TIFF and has user path and user path starts with {data_dir} and {user_path} exists")
        image.nwo.filepath = utils.relative_path(user_path)
        if image.nwo.reexport_tiff:
            if image.has_data:
                image.nwo.filepath = save_image_as(image, user_path.parent, tiff_name=image.nwo.source_name)
            else:
                utils.print_warning(f"{image.name} has no data. Cannot export Tif")
                if report:
                    report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
                    return

    elif Path(image.nwo.filepath.lower()).suffix in {".tif", ".tiff"} and Path(data_dir, image.nwo.filepath).exists():
        logging.log(logging.DEBUG, f"Image has nwo filepath and {Path(data_dir, image.nwo.filepath)} exists")
        if image.nwo.reexport_tiff:
            if image.has_data:
                image.nwo.filepath = save_image_as(image, Path(data_dir, image.nwo.filepath).parent, tiff_name=image.nwo.source_name)
            else:
                utils.print_warning(f"{image.name} has no data. Cannot export Tif")
                if report:
                    report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
                    return
    else:
        logging.log(logging.DEBUG, "We hit the else...")
        if image.has_data:
            image.nwo.filepath = save_image_as(image, bitmaps_data_dir, tiff_name=image.nwo.source_name)
            logging.log(logging.DEBUG, f"nwo filepath: {image.nwo.filepath}")
        else:
            utils.print_warning(f"{image.name} has no data. Cannot export Tif")
            if report:
                report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
                return
            
    nwo_path = Path(image.nwo.filepath)
    if image.nwo.filepath and Path(data_dir, image.nwo.filepath).exists():
        path_no_ext = nwo_path.with_suffix("")
        bitmap_path = nwo_path.with_suffix(".bitmap")
        with BitmapTag(path=bitmap_path) as bitmap:
            bitmap.new_bitmap(utils.dot_partition(image.nwo.source_name), image.nwo.bitmap_type, image.colorspace_settings.name)

        if utils.is_corinth():
            process = utils.run_tool(["reimport-bitmaps-single", str(path_no_ext), "default"], False, False)
        else:
            process = utils.run_tool(["reimport-bitmaps-single", str(path_no_ext)], False, False)
    else:
        if report:
            report({'ERROR'}, f"{image.name} has no data filepath. Cannot build bitmap")
            utils.print_error(f"{image.name} has no data filepath. Cannot build bitmap")
            return
        utils.print_error(f"{image.name} has no data filepath. Cannot build bitmap")
        return

    if report is None:
        return bitmap_path
    else:
        report({"INFO"}, "Bitmap Export Complete")
                
def save_image_as(image, dir, tiff_name=""):
    # ensure image settings
    dir = Path(dir)
    data_dir = Path(utils.get_data_path())
    temp_scene = bpy.data.scenes.new("temp_tiff_export_scene")
    settings = temp_scene.render.image_settings
    settings.file_format = "TIFF"
    settings.color_mode = "RGBA" if image.alpha_mode != "NONE" else "RGB"
    settings.color_depth = "8" if image.depth < 16 else "16"
    settings.tiff_codec = "LZW"
    if not dir.is_absolute():
        return ""
    if not dir.exists():
        dir.mkdir(parents=True, exist_ok=True)
    full_path = Path(dir, tiff_name)
    image.save_render(filepath=str(full_path), scene=temp_scene)
    bpy.data.scenes.remove(temp_scene)

    return str(full_path.relative_to(data_dir))

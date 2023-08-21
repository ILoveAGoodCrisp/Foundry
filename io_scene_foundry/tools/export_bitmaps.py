# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

import os
import bpy
from io_scene_foundry.managed_blam.bitmaps import ManagedBlamNewBitmap
from io_scene_foundry.utils.nwo_utils import (
    dot_partition,
    get_asset_path,
    get_data_path,
    get_tags_path,
    not_bungie_game,
    run_tool,
)

class NWO_ExportBitmapsSingle(bpy.types.Operator):
    bl_idname = "nwo.export_bitmaps_single"
    bl_label = "Export Bitmap"

    def execute(self, context):
        image = context.object.active_material.nwo.active_image
        nwo = image.nwo
        export_bitmap(image, nwo.bitmap_dir, self.report)
        return {'FINISHED'}

def save_image_as(image, dir, tiff_name="", is_full_path=False):
    # ensure image settings
    temp_scene = bpy.data.scenes.new("temp_tiff_export_scene")
    settings = temp_scene.render.image_settings
    settings.file_format = "TIFF"
    settings.color_mode = "RGBA" if image.alpha_mode != "NONE" else "RGB"
    settings.color_depth = "8" if image.depth < 16 else "16"
    settings.tiff_codec = "LZW"
    if not is_full_path:
        full_path = os.path.join(dir, tiff_name)
    image.save(filepath=full_path)
    bpy.data.scenes.remove(temp_scene)

def export_bitmap(
    image,
    folder="",
    report=None,
):
    data_dir = get_data_path()
    tags_dir = get_tags_path()
    asset_path = get_asset_path()
    bitmap_path = dot_partition(image.nwo.filepath) + '.bitmap'
    if not os.path.exists(tags_dir + bitmap_path):
        bitmap_path = dot_partition(image.filepath_from_user().replace(data_dir, "")) + '.bitmap'
    if not os.path.exists(tags_dir + bitmap_path):
        bitmap_path = ""
    # Create a bitmap folder in the asset directory
    if folder:
        bitmaps_data_dir = os.path.join(data_dir + folder)
    else:
        bitmaps_data_dir = os.path.join(data_dir + asset_path, "bitmaps")
    if not os.path.exists(bitmaps_data_dir):
        os.makedirs(bitmaps_data_dir, exist_ok=True)
        # get a list of textures associated with this material
    # export the texture as a tiff to the asset bitmaps folder
    image.nwo.source_name = dot_partition(image.name) + ".tif"
    full_filepath = image.filepath_from_user()
    nwo_full_filepath = data_dir + image.nwo.filepath
    is_tiff = image.file_format == 'TIFF'
    if is_tiff and full_filepath and full_filepath.startswith(data_dir) and os.path.exists(full_filepath):
        image.nwo.filepath = full_filepath.replace(data_dir, "")
        if image.nwo.reexport_tiff:
            try:
                save_image_as(image, full_filepath, is_full_path=True)
            except:
                print(f"Failed to export {image.name}")
                if report:
                    report({"ERROR"}, f"Failed to save {image.name} as .tif")
                return {'CANCELLED'}

    elif is_tiff and nwo_full_filepath.lower().endswith("tif") or nwo_full_filepath.lower().endswith("tiff") and os.path.exists(data_dir + nwo_full_filepath):
        if image.nwo.reexport_tiff:
            try:
                save_image_as(image, data_dir + nwo_full_filepath, is_full_path=True)
            except:
                print(f"Failed to export {image.name}")
                if report:
                    report({"ERROR"}, f"Failed to save {image.name} as .tif")
                return {'CANCELLED'}
    else:
        try:
            save_image_as(image, bitmaps_data_dir, tiff_name=image.nwo.source_name)
            image.nwo.filepath = os.path.join(asset_path, "bitmaps", image.nwo.source_name).replace(data_dir, "")

        except:
            print(f"Failed to export {image.name}")
            if report:
                report({"ERROR"}, f"Failed to save {image.name} as .tif")
            return {'CANCELLED'}

    # Store processes
    bitmap = ManagedBlamNewBitmap(dot_partition(image.nwo.source_name), image.nwo.bitmap_type, image.nwo.filepath).path
    path = dot_partition(image.nwo.filepath)
    process = run_tool(["reimport-bitmaps-single", path, "default"], False, False)

    if report is None or folder:
        if folder:
            return process
        else:
            return bitmap
    else:
        report({"INFO"}, "Bitmap Export Complete")

    return {"FINISHED"}

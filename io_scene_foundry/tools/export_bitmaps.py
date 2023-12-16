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
from io_scene_foundry.managed_blam.bitmap import BitmapTag
from io_scene_foundry.utils.nwo_utils import (
    dot_partition,
    get_asset_path,
    get_data_path,
    get_tags_path,
    is_corinth,
    print_error,
    print_warning,
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

def save_image_as(image, dir, tiff_name=""):
    # ensure image settings
    data_dir = get_data_path()
    temp_scene = bpy.data.scenes.new("temp_tiff_export_scene")
    settings = temp_scene.render.image_settings
    settings.file_format = "TIFF"
    settings.color_mode = "RGBA" if image.alpha_mode != "NONE" else "RGB"
    settings.color_depth = "8" if image.depth < 16 else "16"
    settings.tiff_codec = "LZW"
    if dir and not os.path.exists(dir):
        os.makedirs(dir, exist_ok=True)
    full_path = os.path.join(dir, tiff_name)
    image.save_render(filepath=full_path, scene=temp_scene)
    bpy.data.scenes.remove(temp_scene)

    return full_path.replace(data_dir, "")

def export_bitmap(
    image,
    folder="",
    report=None,
):
    if image.name != image.name_full:
        print("Image is linked, skipping")
        return
    
    data_dir = get_data_path()
    tags_dir = get_tags_path()
    asset_path = get_asset_path()
    user_path = image.filepath_from_user().lower()
    if user_path:
        bitmap_path = dot_partition(user_path.replace(data_dir, "")) + '.bitmap'
        if not os.path.exists(tags_dir + bitmap_path):
            bitmap_path = ''
    else:
        bitmap_path = dot_partition(image.nwo.filepath) + '.bitmap'
        if not os.path.exists(tags_dir + bitmap_path):
            bitmap_path = ''
            
    image.nwo.filepath = bitmap_path
    # Create a bitmap folder in the asset directory
    if folder:
        bitmaps_data_dir = os.path.join(data_dir + folder)
    else:
        bitmaps_data_dir = os.path.join(data_dir + asset_path, "bitmaps")
        # get a list of textures associated with this material
    # export the texture as a tiff to the asset bitmaps folder
    image.nwo.source_name = dot_partition(image.name) + ".tif"
    is_tiff = image.file_format == 'TIFF'
    if is_tiff and user_path and user_path.startswith(data_dir) and os.path.exists(user_path):
        image.nwo.filepath = user_path.replace(data_dir, "")
        if image.nwo.reexport_tiff:
            if image.has_data:
                image.nwo.filepath = save_image_as(image, "", tiff_name=image.nwo.source_name)
            else:
                print_warning(f"{image.name} has no data. Cannot export Tif")
                if report:
                    report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
                    return

    elif is_tiff and image.nwo.filepath.lower().endswith((".tif", ".tiff")) and os.path.exists(data_dir + image.nwo.filepath):
        if image.nwo.reexport_tiff:
            if image.has_data:
                image.nwo.filepath = save_image_as(image, "", tiff_name=image.nwo.source_name)
            else:
                print_warning(f"{image.name} has no data. Cannot export Tif")
                if report:
                    report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
                    return
    else:
        if image.has_data:
            image.nwo.filepath = save_image_as(image, bitmaps_data_dir, tiff_name=image.nwo.source_name)
        else:
            print_warning(f"{image.name} has no data. Cannot export Tif")
            if report:
                report({'ERROR'}, f"{image.name} has no data. Cannot export Tif")
                return

    # Store processes
    if image.nwo.filepath and os.path.exists(data_dir + image.nwo.filepath):
        path_no_ext = dot_partition(image.nwo.filepath)
        bitmap_path = path_no_ext + '.bitmap'
        with BitmapTag(path=bitmap_path) as bitmap:
            bitmap.new_bitmap(dot_partition(image.nwo.source_name), image.nwo.bitmap_type)

        if is_corinth():
            process = run_tool(["reimport-bitmaps-single", path_no_ext, "default"], False, False)
        else:
            process = run_tool(["reimport-bitmaps-single", path_no_ext], False, False)
    else:
        if report:
            report({'ERROR'}, f"{image.name} has no data filepath. Cannot build bitmap")
            print_error(f"{image.name} has no data filepath. Cannot build bitmap")
            return
        print_error(f"{image.name} has no data filepath. Cannot build bitmap")
        return

    if report is None:
        if folder:
            return process
        else:
            return bitmap_path
    else:
        report({"INFO"}, "Bitmap Export Complete")

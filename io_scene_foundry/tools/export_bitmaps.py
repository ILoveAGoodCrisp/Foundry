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
from io_scene_foundry.managed_blam import ManagedBlamNewBitmap
from io_scene_foundry.utils.nwo_utils import (
    dot_partition,
    get_asset_info,
    get_data_path,
    not_bungie_game,
    run_tool,
    valid_nwo_asset,
)

class NWO_ExportBitmapsSingle(bpy.types.Operator):
    bl_idname = "nwo.export_bitmaps_single"
    bl_label = "Export Bitmap"

    @classmethod
    def poll(self, context):
        return valid_nwo_asset(context)

    def execute(self, context):
        export_bitmaps(self.report, context.scene.nwo_halo_launcher.sidecar_path, context.object.active_material.nwo.active_image)
        return {'FINISHED'}

class NWO_ExportBitmaps(bpy.types.Operator):
    bl_idname = "nwo.export_bitmaps"
    bl_label = "Export All Bitmaps"

    @classmethod
    def poll(self, context):
        return valid_nwo_asset(context)

    def execute(self, context):
        bitmaps = [i for i in bpy.data.images if i.nwo.export]
        export_bitmaps(self.report, context.scene.nwo_halo_launcher.sidecar_path, bitmaps)
        return {'FINISHED'}

def save_image_as(image, path, tiff_name):
    scene = bpy.data.scenes.new("temp")

    settings = scene.render.image_settings
    settings.file_format = "TIFF"
    settings.color_mode = "RGBA"
    settings.color_depth = "16"
    settings.tiff_codec = "LZW"
    path = os.path.join(path, tiff_name)
    image.save_render(filepath=path, scene=scene)
    bpy.data.scenes.remove(scene)

def export_bitmaps(
    report,
    sidecar_path,
    bitmaps,
):
    data_dir = get_data_path()
    asset_path, asset = get_asset_info(sidecar_path)
    # Create a bitmap folder in the asset directory
    bitmaps_data_dir = os.path.join(data_dir + asset_path, "bitmaps")
    if not os.path.exists(bitmaps_data_dir):
        os.mkdir(bitmaps_data_dir)
        # get a list of textures associated with this material
    bitmap_count = 0
    # export each texture as a tiff to the asset bitmaps folder
    if type(bitmaps) == list:
        textures = [b for b in bitmaps]
    else:
        textures = [bitmaps]
    for image in textures:
        image.nwo.source_name = dot_partition(image.name) + ".tiff"
        if image.nwo.reexport_tiff and image.filepath and image.file_format == 'TIFF' and image.filepath.startswith(data_dir):
            image.nwo.filepath = image.filepath.replace(data_dir, "")
            print("Using existing TIFF for bitmap import")
        else:
            try:
                save_image_as(image, bitmaps_data_dir, image.nwo.source_name)
                print(f"Exported {image.name} as tiff")
                bitmap_count += 1
                image.nwo.filepath = os.path.join(asset_path, "bitmaps", image.nwo.source_name).replace(data_dir, "")

            except:
                print(f"Failed to export {image.name}")

    if bitmap_count:
        report({"INFO"}, f"Exported {bitmap_count} bitmaps")
    else:
        report({"INFO"}, "No Bitmaps exported")
    # Store processes
    processes = []
    for image in textures:
        bitmap = ManagedBlamNewBitmap(dot_partition(image.nwo.source_name), image.nwo.bitmap_type)
        path = dot_partition(image.nwo.filepath)
        if not_bungie_game():
            processes.append(run_tool(["reimport-bitmaps-single", path, "default"], True, False))
        else:
            processes.append(run_tool(["reimport-bitmaps-single", path], True, True))

    if processes:
        for p in processes:
            p.wait()

    report({"INFO"}, "Bitmaps Import Complete")

    return {"FINISHED"}

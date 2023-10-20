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

import itertools
import multiprocessing
import os
import threading
import time
import bpy
from io_scene_foundry.managed_blam.bitmaps import ManagedBlamNewBitmap
from io_scene_foundry.tools.export_bitmaps import save_image_as
from io_scene_foundry.tools.shader_builder import build_shader

from io_scene_foundry.utils.nwo_utils import dot_partition, get_asset_path, get_data_path, get_tags_path, managed_blam_active, is_corinth, print_warning, run_tool, update_job, update_job_count, update_progress

BLENDER_IMAGE_FORMATS = (".bmp", ".sgi", ".rgb", ".bw", ".png", ".jpg", ".jpeg", ".jp2", ".j2c", ".tga", ".cin", ".dpx", ".exr", ".hdr", ".tif", ".tiff", ".webp")

class NWO_ShaderFarmPopover(bpy.types.Panel):
    bl_label = "Shader Farm Settings"
    bl_idname = "NWO_PT_ShaderFarmPopover"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"INSTANCED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        nwo = scene.nwo
        tag_type = "Material" if is_corinth(context) else "Shader"
        col = layout.column()
        col.prop(nwo, "farm_type", text="Type")
        col.separator()
        if nwo.farm_type in ("both", "shaders"):
            col.label(text=f"{tag_type} Settings")
            col.prop(nwo, "shaders_scope", text="Scope")
            col.prop(nwo, "shaders_dir", text="Folder")
            if is_corinth(context):
                row = col.row(align=True)
                row.prop(nwo, "default_material_shader", text="Shader")
                row.operator("nwo.get_material_shaders", text="", icon="VIEWZOOM").batch_panel = True
            col.prop(nwo, "link_shaders", text="Build Shaders from Blender Nodes")
            col.separator()
        if nwo.farm_type in ("both", "bitmaps"):
            col.label(text=f"Bitmaps Settings")
            col.prop(nwo, "bitmaps_scope", text="Scope")
            col.prop(nwo, "bitmaps_dir", text="Folder")
            col.prop(nwo, "link_bitmaps", text="Re-Export Existing TIFFs")
            col.prop(nwo, "all_bitmaps", text="Include All Blender Scene Images")

class NWO_FarmShaders(bpy.types.Operator):
    bl_label = "Shader Farm"
    bl_idname = "nwo.shader_farm"

    def image_in_valid_node(self, image, materials):
        for mat in materials:
            if not mat.node_tree:
                continue
            nodes = mat.node_tree.nodes
            for n in nodes:
                if getattr(n, "image", 0) == image:
                    return True
        return False

    def execute(self, context):
        self.corinth = is_corinth(context)
        self.thread_max = multiprocessing.cpu_count()
        self.running_check = 0
        self.bitmap_processes = 0
        self.exported_bitmaps = []
        shaders = {}
        shaders['new'] = []
        shaders['update'] = []
        bitmaps = {}
        bitmaps['new'] = []
        bitmaps['update'] = []
        self.tags_dir = get_tags_path()
        self.data_dir = get_data_path()
        self.asset_path = get_asset_path()
        tag_type = 'Material' if self.corinth else 'Shader'
        if not managed_blam_active():
            bpy.ops.managed_blam.init()
        start = time.perf_counter()
        settings = context.scene.nwo
        os.system("cls")
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            context.scene.nwo_export.show_output = False

        export_title = f"►►► {tag_type.upper()} FARM ◄◄◄"

        print(export_title)

        for mat in bpy.data.materials:
            if mat.name != mat.name_full:
                continue
            mat_nwo = mat.nwo
            if not mat_nwo.rendered or mat.is_grease_pencil:
                continue
            if mat_nwo.shader_path and os.path.exists(self.tags_dir + mat_nwo.shader_path):
                if mat_nwo.uses_blender_nodes:
                    shaders['update'].append(mat)
            else:
                shaders['new'].append(mat)

        if settings.shaders_scope == 'all':
            valid_shaders = shaders['new'] + shaders['update']
        elif settings.shaders_scope == "new":
            valid_shaders = shaders['new']
        else:
            valid_shaders = shaders['update']
        # create a list of non-duplicate bitmaps

        for image in bpy.data.images:
            if image.name != image.name_full:
                continue
            if dot_partition(image.name).endswith(BLENDER_IMAGE_FORMATS):
                print_warning(f"{image.name} looks like a duplicate image, skipping")
                continue
            if not settings.all_bitmaps and not self.image_in_valid_node(image, valid_shaders):
                continue
            bitmap = image.nwo
            bitmap_path = dot_partition(bitmap.filepath) + '.bitmap'
            if not os.path.exists(self.tags_dir + bitmap_path):
                bitmap_path = dot_partition(image.filepath_from_user().replace(self.data_dir, "")) + '.bitmap'
            if os.path.exists(self.tags_dir + bitmap_path):
                if image.nwo.export:
                    bitmaps['update'].append(image)
            else:
                bitmaps['new'].append(image)

        if settings.bitmaps_scope == 'all':
            valid_bitmaps = bitmaps['new'] + bitmaps['update']
        elif settings.bitmaps_scope == "new":
            valid_bitmaps = bitmaps['new']
        else:
            valid_bitmaps = bitmaps['update']

        if settings.farm_type == "both" or settings.farm_type == "bitmaps":
            bitmap_folder = settings.bitmaps_dir
            # Create a bitmap folder in the asset directory
            if bitmap_folder:
                self.bitmaps_data_dir = os.path.join(self.data_dir + bitmap_folder)
            else:
                self.bitmaps_data_dir = os.path.join(self.data_dir + self.asset_path, "bitmaps")
            print("\nStarting Bitmap Export")
            print(
                "-----------------------------------------------------------------------\n"
            )
            bitmap_count = len(valid_bitmaps)
            print(f"{bitmap_count} bitmaps in scope")
            print(f"Bitmaps Directory = {bitmap_folder}\n")
            for idx, bitmap in enumerate(valid_bitmaps):
                tiff_path = self.export_tiff_if_needed(bitmap, self.bitmaps_data_dir, settings.link_bitmaps)
                if tiff_path:
                    self.thread_bitmap_export(bitmap, tiff_path)
            self.report({'INFO'}, f"Exported {bitmap_count} Bitmaps")

            # Wait for Bitmap export to finish
            print("")
            job = "Reimporting Source Tiffs"
            spinner = itertools.cycle(["|", "/", "—", "\\"])
            total_p = self.bitmap_processes
            while self.running_check:
                update_job_count(
                    job, next(spinner), total_p - self.running_check, total_p
                )
                time.sleep(0.1)
            update_job_count(job, "", total_p, total_p)

        if settings.farm_type == "both" or settings.farm_type == "shaders":
            print(f"\nStarting {tag_type}s Export")
            print(
                "-----------------------------------------------------------------------\n"
            )
            shader_count = len(valid_shaders)
            print(f"{shader_count} {tag_type}s in Scope")
            print(f"{tag_type}s Directory = {settings.shaders_dir}\n")
            job = f"Exporting {tag_type}s"
            for idx, shader in enumerate(valid_shaders):
                update_progress(job, idx / shader_count)
                shader.nwo.uses_blender_nodes = settings.link_shaders
                if settings.default_material_shader and os.path.exists(self.tags_dir + settings.default_material_shader):
                    shader.nwo.material_shader = settings.default_material_shader
                build_shader(shader, self.corinth, settings.shaders_dir)
            update_progress(job, 1)
            self.report({'INFO'}, f"Exported {shader_count} {tag_type}s")

        end = time.perf_counter()

        print(
            "\n-----------------------------------------------------------------------"
        )
        print(f"{tag_type} Farm Completed in {round(end - start, 3)} seconds")

        print(
            "-----------------------------------------------------------------------\n"
        )

        self.report({'INFO'}, "Farm Complete")

        return {'FINISHED'}
    
    def export_tiff_if_needed(self, image, folder, export_tiff):
        image.nwo.source_name = dot_partition(image.name) + ".tif"
        job = f"-- Tiff Export: {image.nwo.source_name}"
        full_filepath = image.filepath_from_user()
        nwo_full_filepath = self.data_dir + image.nwo.filepath
        is_tiff = image.file_format == 'TIFF'
        reexport = image.nwo.reexport_tiff
        if not reexport and is_tiff and full_filepath and full_filepath.startswith(self.data_dir) and os.path.exists(full_filepath):
            image.nwo.filepath = full_filepath.replace(self.data_dir, "")
            if export_tiff:
                if image.has_data:
                    update_job(job, 0)
                    image.nwo.filepath = save_image_as(image, folder, tiff_name=image.nwo.source_name)
                    update_job(job, 1)
                else:
                    return print_warning(f"{image.name} has no data. Cannot export Tif")

        if is_tiff and nwo_full_filepath.lower().endswith(".tif") or nwo_full_filepath.lower().endswith(".tiff") and os.path.exists(self.data_dir + nwo_full_filepath):
            if export_tiff:
                if image.has_data:
                    update_job(job, 0)
                    image.nwo.filepath = save_image_as(image, folder, tiff_name=image.nwo.source_name)
                    update_job(job, 1)
                else:
                    return print_warning(f"{image.name} has no data. Cannot export Tif")
        else:
            if image.has_data:
                update_job(job, 0)
                image.nwo.filepath = save_image_as(image, folder, tiff_name=image.nwo.source_name)
                update_job(job, 1)
            else:
                return print_warning(f"{image.name} has no data. Cannot export Tif")
                
        
        return image.nwo.filepath
    
    def thread_bitmap_export(self, image, tiff_path):
        user_path = image.filepath_from_user().lower()
        if user_path:
            bitmap_path = dot_partition(user_path.replace(self.data_dir, "")) + '.bitmap'
            if not os.path.exists(self.tags_dir + bitmap_path):
                bitmap_path = ''
        else:
            bitmap_path = dot_partition(image.nwo.filepath) + '.bitmap'
            if not os.path.exists(self.tags_dir + bitmap_path):
                bitmap_path = ''
            
        image.nwo.filepath = bitmap_path
        if os.path.exists(self.tags_dir + bitmap_path):
            job = f"-- Updated Tag:"
        else:
            job = f"-- Created Tag:"

        if not bitmap_path or bitmap_path not in self.exported_bitmaps:
            bitmap = ManagedBlamNewBitmap(dot_partition(image.nwo.source_name), image.nwo.bitmap_type, tiff_path).path
            path = dot_partition(image.nwo.filepath)
            self.exported_bitmaps.append(bitmap)
            print(f"{job} {bitmap}")
            while self.running_check > self.thread_max * 2:
                time.sleep(0.1)

            thread = threading.Thread(target=self.export_bitmap, args=(path,))
            thread.start()
            self.first_bitmap = False

    def export_bitmap(self, bitmap_path):
        self.running_check += 1
        self.bitmap_processes += 1
        time.sleep(self.running_check / 10)
        if self.corinth:
            run_tool(["reimport-bitmaps-single", bitmap_path, "default"], False, True)
        else:
            run_tool(["reimport-bitmaps-single", bitmap_path], False, True)
        self.running_check -= 1


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
from io_scene_foundry.icons import get_icon_id
from io_scene_foundry.managed_blam.bitmap import BitmapTag
from io_scene_foundry.tools.export_bitmaps import save_image_as
from io_scene_foundry.tools.shader_builder import build_shader

from io_scene_foundry.utils.nwo_utils import ExportManager, asset_path_from_blend_location, clean_tag_path, dot_partition, get_asset_path, get_data_path, get_shader_name, get_tags_path, managed_blam_active, is_corinth, print_warning, relative_path, run_tool, update_job, update_job_count, update_progress, valid_filename, valid_image_name, valid_nwo_asset

BLENDER_IMAGE_FORMATS = (".bmp", ".sgi", ".rgb", ".bw", ".png", ".jpg", ".jpeg", ".jp2", ".j2c", ".tga", ".cin", ".dpx", ".exr", ".hdr", ".tif", ".tiff", ".webp")

class NWO_FarmShaders(bpy.types.Operator):
    bl_label = "Shader Farm"
    bl_idname = "nwo.shader_farm"
    bl_description = "Builds shader/material tags for all valid blender materials. Will export all necessary bitmaps"
    
    def update_shaders_dir(self, context):
        self["shaders_dir"] = clean_tag_path(self["shaders_dir"]).strip('"')

    def get_shaders_dir(self):
        context = bpy.context
        is_asset = valid_nwo_asset(context)
        if is_asset:
            return self.get("shaders_dir", os.path.join(get_asset_path(), "materials" if is_corinth(context) else "shaders"))
        return self.get("shaders_dir", "")
    
    def set_shaders_dir(self, value):
        self['shaders_dir'] = value

    shaders_dir : bpy.props.StringProperty(
        name="Shaders Directory",
        description="Specifies the directory to export shaders/materials. Defaults to the asset materials/shaders folder",
        options=set(),
        update=update_shaders_dir,
        get=get_shaders_dir,
        set=set_shaders_dir,
    )

    def update_bitmaps_dir(self, context):
        self["bitmaps_dir"] = clean_tag_path(self["bitmaps_dir"]).strip('"')

    def get_bitmaps_dir(self):
        context = bpy.context
        is_asset = valid_nwo_asset(context)
        if is_asset:
            return self.get("bitmaps_dir", os.path.join(get_asset_path(), "bitmaps"))
        return self.get("bitmaps_dir", "")
    
    def set_bitmaps_dir(self, value):
        self['bitmaps_dir'] = value

    bitmaps_dir : bpy.props.StringProperty(
        name="Bitmaps Directory",
        description="Specifies where the exported bitmaps (and tiffs, if they exist) should be saved. Defaults to the asset bitmaps folder",
        update=update_bitmaps_dir,
        get=get_bitmaps_dir,
        set=set_bitmaps_dir,
    )

    def farm_type_items(self, context):
        tag_type = "Materials" if is_corinth(context) else "Shaders"
        items = [
            ("both", f"{tag_type} & Bitmaps", ""),
            ("shaders", f"{tag_type}", ""),
            ("bitmaps", "Bitmaps", ""),
        ]

        return items

    farm_type : bpy.props.EnumProperty(
        name="Type",
        items=farm_type_items,
    )

    shaders_scope : bpy.props.EnumProperty(
        name="Shaders",
        items=[
            ("all", "All", ""),
            ("new", "New Only", ""),
            ("update", "Update Only", ""),
        ]
    )

    bitmaps_scope : bpy.props.EnumProperty(
        name="Bitmaps",
        items=[
            ("all", "All", ""),
            ("new", "New Only", ""),
            ("update", "Update Only", ""),
        ]
    )

    link_shaders : bpy.props.BoolProperty(
        name="Build Shaders from Blender Nodes",
        description="Build shader/material tags using Blender material node trees. If disabled, the farm will instead create empty shader/material tags",
        default=True,
    )
    link_bitmaps : bpy.props.BoolProperty(
        name="Re-Export Existing TIFFs",
        description="Build Shader/Material tags using Blender Material nodes",
        default=False,
    )

    all_bitmaps : bpy.props.BoolProperty(
        name="Include All Blender Scene Images",
        description="Includes all blender scene images in scope even if they are not present in any material nodes"
    )

    def update_default_material_shader(self, context):
        self["default_material_shader"] = clean_tag_path(self["default_material_shader"]).strip('"')
        
    def get_default_material_shader(self):
        from io_scene_foundry.tools.shader_builder import material_shader_path
        return material_shader_path
            
    def set_default_material_shader(self, value):
        from io_scene_foundry.tools import shader_builder
        shader_builder.material_shader_path = value
        self['default_material_shader'] = value

    default_material_shader : bpy.props.StringProperty(
        name="Material Shader",
        description="Path to the material shader to use for all materials (does not overwrite custom node group defined material shaders)",
        update=update_default_material_shader,
        get=get_default_material_shader,
        set=set_default_material_shader,
    )
    
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self, width=800)

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
        with ExportManager():
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
            blend_asset_path = asset_path_from_blend_location()
            tag_type = 'Material' if self.corinth else 'Shader'
            if not managed_blam_active():
                bpy.ops.managed_blam.init()
            start = time.perf_counter()
            shaders_dir = relative_path(self.shaders_dir)
            bitmaps_dir = relative_path(self.bitmaps_dir)
            os.system("cls")
            if context.scene.nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                context.scene.nwo_export.show_output = False

            export_title = f"►►► {tag_type.upper()} FARM ◄◄◄"

            print(export_title)
            shader_names = set()
            for mat in bpy.data.materials:
                # Check if material is library linked
                if mat.name != mat.name_full: continue
                mat_nwo = mat.nwo
                # Skip if either declared as not a shader or is a grease pencil material
                if not mat_nwo.RenderMaterial: continue
                s_name = get_shader_name(mat)
                if s_name in shader_names:
                    continue
                shader_names.add(s_name)
                if mat_nwo.shader_path and os.path.exists(self.tags_dir + mat_nwo.shader_path):
                    if mat_nwo.uses_blender_nodes:
                        shaders['update'].append(mat)
                else:
                    shaders['new'].append(mat)

            if self.shaders_scope == 'all':
                valid_shaders = shaders['new'] + shaders['update']
            elif self.shaders_scope == "new":
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
                if not self.all_bitmaps and not self.image_in_valid_node(image, valid_shaders):
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

            if self.bitmaps_scope == 'all':
                valid_bitmaps = bitmaps['new'] + bitmaps['update']
            elif self.bitmaps_scope == "new":
                valid_bitmaps = bitmaps['new']
            else:
                valid_bitmaps = bitmaps['update']

            if self.farm_type == "both" or self.farm_type == "bitmaps":
                # Create a bitmap folder in the asset directory
                if bitmaps_dir:
                    self.bitmaps_data_dir = os.path.join(self.data_dir + bitmaps_dir)
                elif self.asset_path:
                    self.bitmaps_data_dir = os.path.join(self.data_dir + self.asset_path, "bitmaps")
                elif blend_asset_path:
                    self.bitmaps_data_dir = os.path.join(blend_asset_path, 'bitmaps')
                else:
                    self.bitmaps_data_dir = self.data_dir + "bitmaps"
                    
                print("\nStarting Bitmap Export")
                print(
                    "-----------------------------------------------------------------------\n"
                )
                bitmap_count = len(valid_bitmaps)
                print(f"{bitmap_count} bitmaps in scope")
                print(f"Bitmaps Directory = {relative_path(self.bitmaps_data_dir)}\n")
                for idx, bitmap in enumerate(valid_bitmaps):
                    tiff_path = self.export_tiff_if_needed(bitmap)
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

            if self.farm_type == "both" or self.farm_type == "shaders":
                print(f"\nStarting {tag_type}s Export")
                print(
                    "-----------------------------------------------------------------------\n"
                )
                if not shaders_dir:
                    if self.asset_path:
                        shaders_dir = os.path.join(self.asset_path, "materials" if self.corinth else 'shaders')
                    elif blend_asset_path:
                        shaders_dir = os.path.join(blend_asset_path, "materials" if self.corinth else 'shaders')
                    else:
                        shaders_dir = "materials" if self.corinth else 'shaders'
                shader_count = len(valid_shaders)
                print(f"{shader_count} {tag_type}s in Scope")
                print(f"{tag_type}s Directory = {shaders_dir}\n")
                job = f"Exporting {tag_type}s"
                for idx, shader in enumerate(valid_shaders):
                    update_progress(job, idx / shader_count)
                    shader.nwo.uses_blender_nodes = self.link_shaders
                    if self.default_material_shader and os.path.exists(self.tags_dir + self.default_material_shader):
                        shader.nwo.material_shader = self.default_material_shader
                    build_shader(shader, self.corinth, shaders_dir)
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
    
    def export_tiff_if_needed(self, image):
        image.nwo.source_name = valid_image_name(image.name) + ".tif"
        user_path = image.filepath_from_user()
        is_tiff = image.file_format == 'TIFF'
        if is_tiff and user_path and user_path.startswith(self.data_dir) and os.path.exists(user_path):
            image.nwo.filepath = user_path.replace(self.data_dir, "")
            if image.nwo.reexport_tiff:
                if image.has_data:
                    image.nwo.filepath = save_image_as(image, "", tiff_name=image.nwo.source_name)
                else:
                    return print_warning(f"{image.name} has no data. Cannot export Tif")

        elif is_tiff and image.nwo.filepath.lower().endswith((".tif", ".tiff")) and os.path.exists(self.data_dir + image.nwo.filepath):
            if image.nwo.reexport_tiff:
                if image.has_data:
                    image.nwo.filepath = save_image_as(image, "", tiff_name=image.nwo.source_name)
                else:
                    return print_warning(f"{image.name} has no data. Cannot export Tif")
        else:
            if image.has_data:
                image.nwo.filepath = save_image_as(image, self.bitmaps_data_dir, tiff_name=image.nwo.source_name)
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
            
        if os.path.exists(self.tags_dir + bitmap_path):
            job = f"-- Updated Tag:"
        else:
            job = f"-- Created Tag:"

        if not bitmap_path or bitmap_path not in self.exported_bitmaps:
            path_no_ext = dot_partition(image.nwo.filepath)
            bitmap_path = path_no_ext + '.bitmap'
            with BitmapTag(path=bitmap_path) as bitmap:
                bitmap.new_bitmap(dot_partition(image.nwo.source_name), image.nwo.bitmap_type)
                
            self.exported_bitmaps.append(bitmap_path)
            print(f"{job} {bitmap_path}")
            while self.running_check > self.thread_max * 2:
                time.sleep(0.1)

            thread = threading.Thread(target=self.export_bitmap, args=(path_no_ext,))
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
        
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        tag_type = "Material" if is_corinth(context) else "Shader"
        col = layout.column()
        col.prop(self, "farm_type", text="Type")
        col.separator()
        if self.farm_type in ("both", "shaders"):
            col.prop(self, "shaders_scope", text=f"{tag_type}s Scope")
            col.prop(self, "shaders_dir", text=f"{tag_type}s Export Folder", icon='FILE_FOLDER')
            if is_corinth(context):
                row = col.row(align=True)
                row.prop(self, "default_material_shader", text="Material Shader (Optional)", icon_value=get_icon_id('tags'))
                row.operator("nwo.get_material_shaders", text="", icon="VIEWZOOM").batch_panel = True                
            col.prop(self, "link_shaders", text="Build Shaders from Blender Nodes")
            col.separator()
        if self.farm_type in ("both", "bitmaps"):
            col.prop(self, "bitmaps_scope", text="Bitmaps Scope")
            col.prop(self, "bitmaps_dir", text="Bitmaps Export Folder", icon='FILE_FOLDER')
            col.prop(self, "link_bitmaps", text="Re-Export Existing TIFFs")
            col.prop(self, "all_bitmaps", text="Include All Blender File Images")



import itertools
import multiprocessing
import os
from pathlib import Path
import threading
import time
import bpy

from .. import utils

from ..icons import get_icon_id
from ..managed_blam.bitmap import BitmapTag
from ..tools.export_bitmaps import save_image_as
from ..tools.shader_builder import build_shader

BLENDER_IMAGE_FORMATS = (".bmp", ".sgi", ".rgb", ".bw", ".png", ".jpg", ".jpeg", ".jp2", ".j2c", ".tga", ".cin", ".dpx", ".exr", ".hdr", ".tif", ".tiff", ".webp")

class NWO_FarmShaders(bpy.types.Operator):
    bl_label = "Shader Farm"
    bl_idname = "nwo.shader_farm"
    bl_description = "Builds shader/material tags for all valid blender materials. Will export all necessary bitmaps"

    def farm_type_items(self, context):
        tag_type = "Materials" if utils.is_corinth(context) else "Shaders"
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
        self["default_material_shader"] = utils.clean_tag_path(self["default_material_shader"]).strip('"')
        
    def get_default_material_shader(self):
        from ..tools.shader_builder import material_shader_path
        return material_shader_path
            
    def set_default_material_shader(self, value):
        from ..tools import shader_builder
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
        with utils.ExportManager():
            self.corinth = utils.is_corinth(context)
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
            self.tags_dir = utils.get_tags_path()
            self.data_dir = utils.get_data_path()
            self.asset_path = utils.get_asset_path()
            blend_asset_path = utils.asset_path_from_blend_location()
            tag_type = 'Material' if self.corinth else 'Shader'
            start = time.perf_counter()
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
                s_name = utils.get_shader_name(mat)
                if s_name in shader_names:
                    continue
                shader_names.add(s_name)
                if mat_nwo.shader_path and Path(self.tags_dir, mat_nwo.shader_path).exists():
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
                if utils.dot_partition(image.name).endswith(BLENDER_IMAGE_FORMATS):
                    utils.print_warning(f"{image.name} looks like a duplicate image, skipping")
                    continue
                if not self.all_bitmaps and not self.image_in_valid_node(image, valid_shaders):
                    continue
                bitmap = image.nwo
                bitmap_path = utils.dot_partition(bitmap.filepath) + '.bitmap'
                if not Path(self.tags_dir, bitmap_path).exists() and Path(image.filepath_from_user()).is_relative_to(self.data_dir):
                    bitmap_path = str(Path(image.filepath_from_user()).relative_to(self.data_dir).with_suffix('.bitmap'))
                if Path(self.tags_dir, bitmap_path).exists():
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
                if self.asset_path:
                    self.bitmaps_data_dir = os.path.join(self.data_dir, self.asset_path, "bitmaps")
                elif blend_asset_path:
                    self.bitmaps_data_dir = os.path.join(blend_asset_path, 'bitmaps')
                else:
                    self.bitmaps_data_dir = Path(self.data_dir, "bitmaps")
                    
                print("\nStarting Bitmap Export")
                print(
                    "-----------------------------------------------------------------------\n"
                )
                bitmap_count = len(valid_bitmaps)
                print(f"{bitmap_count} bitmaps in scope")
                print(f"Bitmaps Directory = {utils.relative_path(self.bitmaps_data_dir)}\n")
                for idx, bitmap in enumerate(valid_bitmaps):
                    tiff_path = self.export_tiff_if_needed(bitmap)
                    if tiff_path:
                        self.thread_bitmap_export(bitmap)
                self.report({'INFO'}, f"Exported {bitmap_count} Bitmaps")

                # Wait for Bitmap export to finish
                print("")
                job = "Reimporting Source Tiffs"
                spinner = itertools.cycle(["|", "/", "—", "\\"])
                total_p = self.bitmap_processes
                while self.running_check:
                    utils.update_job_count(
                        job, next(spinner), total_p - self.running_check, total_p
                    )
                    time.sleep(0.1)
                utils.update_job_count(job, "", total_p, total_p)

            if self.farm_type == "both" or self.farm_type == "shaders":
                print(f"\nStarting {tag_type}s Export")
                print(
                    "-----------------------------------------------------------------------\n"
                )
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
                    utils.update_progress(job, idx / shader_count)
                    shader.nwo.uses_blender_nodes = self.link_shaders
                    if self.default_material_shader and Path(self.tags_dir, self.default_material_shader).exists():
                        shader.nwo.material_shader = self.default_material_shader
                    build_shader(shader, self.corinth, shaders_dir)
                utils.update_progress(job, 1)
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
        valid_name = utils.valid_image_name(image.name) + ".tif"
        if ".tiff" in image.name:
            valid_name += 'f'
        image.nwo.source_name = valid_name
        user_path = Path(image.filepath_from_user())
        user_path_contains_data_dir = user_path.is_relative_to(self.data_dir)
            
        if user_path and user_path_contains_data_dir and user_path.exists():
            image.nwo.filepath = utils.relative_path(user_path)
            if image.nwo.reexport_tiff:
                if image.has_data:
                    image.nwo.filepath = save_image_as(image, user_path.parent, tiff_name=image.nwo.source_name)
                else:
                    utils.print_warning(f"{image.name} has no data. Cannot export Tif")

        elif Path(image.nwo.filepath.lower()).suffix in {".tif", ".tiff"} and Path(self.data_dir, image.nwo.filepath).exists():
            if image.nwo.reexport_tiff:
                if image.has_data:
                    image.nwo.filepath = save_image_as(image, Path(self.data_dir, image.nwo.filepath).parent, tiff_name=image.nwo.source_name)
                else:
                    utils.print_warning(f"{image.name} has no data. Cannot export Tif")
        else:
            if image.has_data:
                image.nwo.filepath = save_image_as(image, self.bitmaps_data_dir, tiff_name=image.nwo.source_name)
            else:
                utils.print_warning(f"{image.name} has no data. Cannot export Tif")
                
        return image.nwo.filepath
    
    def thread_bitmap_export(self, image):
        user_path = image.filepath_from_user()
        if user_path and Path(user_path).is_relative_to(Path(self.data_dir)):
            bitmap_path = str(Path(user_path).relative_to(Path(self.data_dir)).with_suffix('.bitmap'))
            if not Path(self.tags_dir, bitmap_path).exists():
                bitmap_path = ''
        else:
            bitmap_path = str(Path(image.nwo.filepath).with_suffix(".bitmap"))
            if not Path(self.tags_dir, bitmap_path).exists():
                bitmap_path = ''
            
        if Path(self.tags_dir, bitmap_path).exists():
            job = f"-- Updated Tag:"
        else:
            job = f"-- Created Tag:"

        if not bitmap_path or bitmap_path not in self.exported_bitmaps:
            path_no_ext = str(Path(image.nwo.filepath).with_suffix(""))
            bitmap_path = path_no_ext + '.bitmap'
            with BitmapTag(path=bitmap_path) as bitmap:
                bitmap.new_bitmap(utils.dot_partition(image.nwo.source_name), image.nwo.bitmap_type, image.colorspace_settings.name)
                
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
            utils.run_tool(["reimport-bitmaps-single", bitmap_path, "default"], False, True)
        else:
            utils.run_tool(["reimport-bitmaps-single", bitmap_path], False, True)
        self.running_check -= 1
        
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        tag_type = "Material" if utils.is_corinth(context) else "Shader"
        col = layout.column()
        col.prop(self, "farm_type", text="Type")
        col.separator()
        if self.farm_type in ("both", "shaders"):
            col.prop(self, "shaders_scope", text=f"{tag_type}s Scope")
            if utils.is_corinth(context):
                row = col.row(align=True)
                row.prop(self, "default_material_shader", text="Material Shader (Optional)", icon_value=get_icon_id('tags'))
                row.operator("nwo.get_material_shaders", text="", icon="VIEWZOOM").batch_panel = True                
            col.prop(self, "link_shaders", text="Build Shaders from Blender Nodes")
            col.separator()
        if self.farm_type in ("both", "bitmaps"):
            col.prop(self, "bitmaps_scope", text="Bitmaps Scope")
            col.prop(self, "link_bitmaps", text="Re-Export Existing TIFFs")
            col.prop(self, "all_bitmaps", text="Include All Blender File Images")



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
import time
import bpy
import addon_utils
from io_scene_foundry.managed_blam.bitmap import BitmapTag
from io_scene_foundry.tools.shader_finder import find_shaders
from io_scene_foundry.tools.shader_reader import tag_to_nodes
from io_scene_foundry.utils.nwo_constants import VALID_MESHES
from io_scene_foundry.utils.nwo_utils import ExportManager, MutePrints, amf_addon_installed, blender_toolset_installed, dot_partition, get_tags_path, is_corinth, print_warning, relative_path, set_active_object, stomp_scale_multi_user, unlink, update_progress

pose_hints = 'aim', 'look', 'acc', 'steer'
legacy_model_formats = '.jms', '.ass'
legacy_animation_formats = '.jmm', '.jma', '.jmt', '.jmz', '.jmv', '.jmw', '.jmo', '.jmr', '.jmrx'

class NWO_Import(bpy.types.Operator):
    bl_label = "Import File(s)/Folder(s)"
    bl_idname = "nwo.import"
    bl_description = "Imports a variety of filetypes and sets them up for Foundry. Currently supports: AMF, JMA, bitmap"
    
    @classmethod
    def poll(cls, context):
        return amf_addon_installed()
    
    filter_glob: bpy.props.StringProperty(
        default="",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    directory: bpy.props.StringProperty(
        name='Directory',
        subtype='DIR_PATH',
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    find_shader_paths: bpy.props.BoolProperty(
        name="Find Shader Paths",
        description="Searches the tags folder after import and tries to find shader/material tags which match the name of importer materials",
        default=True,
    )
    build_blender_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Builds Blender material nodes for materials based off their shader/material tags (if found)",
        default=True,
    )
    
    legacy_fix_rotations: bpy.props.BoolProperty(
        name="Fix Rotations",
        description="Rotates imported bones by 90 degrees on the Z Axis",
    )
    
    import_images_to_blender: bpy.props.BoolProperty(
        name="Import to Blend",
        description="Imports images into the blender after extracting bitmaps from the game",
        default=True,
    )
    images_fake_user: bpy.props.BoolProperty(
        name="Set Fake User",
        description="Sets the fake user property on imported images",
        default=True,
    )
    extracted_bitmap_format: bpy.props.EnumProperty(
        name="Image Format",
        description="Sets format to save the extracted bitmap as",
        items=[
            ("tiff", "TIFF", ""),
            ("png", "PNG", ""),
            ("jped", "JPEG", ""),
            ("bmp", "BMP", ""),
            
        ]
    )
    
    amf_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    legacy_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    scope: bpy.props.StringProperty(
        name="Scope",
        default='models',
        options={"HIDDEN", "SKIP_SAVE"}
    )
    
    def execute(self, context):
        filepaths = [self.directory + f.name for f in self.files]
        extensions = set([path.rpartition('.')[2] for path in filepaths])
        corinth = is_corinth(context)
        start = time.perf_counter()
        self.nothing_imported = False
        self.user_cancelled = False
        with ExportManager():
            os.system("cls")
            if context.scene.nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                context.scene.nwo_export.show_output = False
            try:
                export_title = f"►►► FOUNDRY IMPORTER ◄◄◄"
                print(export_title)
                if self.scope == 'models':
                    imported_objects: list[bpy.types.Material] = []
                    importer = NWOImporter(context, self.report, filepaths)
                    if 'amf' in extensions and self.amf_okay:
                        amf_module_name = amf_addon_installed()
                        amf_addon_enabled = addon_utils.check(amf_module_name)[0]
                        if not amf_addon_enabled:
                            addon_utils.enable(amf_module_name)
                        amf_files = importer.sorted_filepaths["amf"]
                        imported_amf_objects = importer.import_amf_files(amf_files)
                        
                        if not amf_addon_enabled:
                            addon_utils.disable(amf_module_name)
                        if imported_amf_objects:
                            imported_objects.extend(imported_amf_objects)
                            [ob.select_set(True) for ob in imported_amf_objects]
                    if self.legacy_okay and any([ext in ('jms', 'ass', 'jmm', 'jma', 'jmt', 'jmz', 'jmv', 'jmw', 'jmo', 'jmr', 'jmrx') for ext in extensions]):
                        toolset_addon_enabled = addon_utils.check('io_scene_halo')[0]
                        if not toolset_addon_enabled:
                            addon_utils.enable('io_scene_halo')
                        jms_files = importer.sorted_filepaths["jms"]
                        jma_files = importer.sorted_filepaths["jma"]
                        # imported_jms_objects = importer.import_jms_files(jms_files)
                        imported_jma_animations = importer.import_jma_files(jma_files)
                        if not toolset_addon_enabled:
                            addon_utils.disable('io_scene_halo')
                    
                    if self.find_shader_paths and imported_objects:
                        imported_meshes: list[bpy.types.Mesh] = set([ob.data for ob in imported_objects if ob.type in VALID_MESHES])
                        if imported_meshes:
                            mesh_material_groups = [me.materials for me in imported_meshes]
                            materials = set(material for mesh_materials in mesh_material_groups for material in mesh_materials)
                            if materials:
                                find_shaders(materials)
                                if self.build_blender_materials:
                                    for mat in materials:
                                        shader_path = mat.nwo.shader_path
                                        if shader_path:
                                            tag_to_nodes(corinth, mat, shader_path)
                        
                elif self.scope == 'images':
                    if not self.directory.startswith(get_tags_path()):
                        self.report({'WARNING'}, "Can only extract bitmaps from the current project's tags folder")
                        return {'CANCELLED'}
                    importer = NWOImporter(context, self.report, filepaths)
                    bitmap_files = importer.sorted_filepaths["bitmap"]
                    if not bitmap_files:
                        self.nothing_imported = True
                    else:
                        extracted_bitmaps = importer.extract_bitmaps(bitmap_files, self.extracted_bitmap_format)
                        if self.import_images_to_blender:
                            importer.load_bitmaps(extracted_bitmaps, self.images_fake_user)
                                    
                        self.report({'INFO'}, f"Extracted {'and imported' if self.import_images_to_blender else ''} {len(bitmap_files)} bitmaps")
                        
            except KeyboardInterrupt:
                print_warning("\nIMPORT CANCELLED BY USER")
                self.user_cancelled = True
        
        end = time.perf_counter()
        if self.user_cancelled:
            self.report({'WARNING'}, "Import cancelled by user")
        elif self.nothing_imported:
            print("No Folders/Filepaths supplied")
            self.report({'WARNING'}, "Nothing imported. No filepaths/folders supplied")
        else:
            print(
                "\n-----------------------------------------------------------------------"
            )
            print(f"Import Completed in {round(end - start, 3)} seconds")

            print(
                "-----------------------------------------------------------------------\n"
            )
            
        return {'FINISHED'}
    
    def invoke(self, context, event):
        if self.scope == 'images':
            self.directory = get_tags_path()
            self.filter_glob += "*.bitmap;"
        else:
            if amf_addon_installed():
                self.amf_okay = True
                self.filter_glob += "*.amf;"
            if blender_toolset_installed():
                self.legacy_okay = True
                self.filter_glob += '*.jms;*ass;*.jmm;*.jma;*.jmt;*.jmz;*.jmv;*.jmw;*.jmo;*.jmr;*.jmrx'
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.25
        if self.scope == 'images':
            layout.use_property_split = True
            layout.prop(self, 'extracted_bitmap_format')
            layout.prop(self, 'import_images_to_blender')
            if self.import_images_to_blender:
                layout.prop(self, 'images_fake_user')
        else:
            tag_type = 'material' if is_corinth(context) else 'shader'
            layout.prop(self, 'find_shader_paths', text=f"Find {tag_type.capitalize()} Tag Paths")
            if self.find_shader_paths:
                layout.prop(self, 'build_blender_materials', text=f"Blender Materials from {tag_type.capitalize()} Tags")
            
            box = layout.box()
            box.label(text="JMA/JMS/ASS Settings")
            box.prop(self, 'legacy_fix_rotations', text='Fix Rotations')

class NWOImporter():
    def __init__(self, context, report, filepaths, legacy_fix_rotations):
        self.filepaths = filepaths
        self.context = context
        self.report = report
        self.mesh_objects = []
        self.marker_objects = []
        self.sorted_filepaths = self.group_filetypes()
        
        self.legacy_fix_rotations = legacy_fix_rotations
    
    def group_filetypes(self):
        filetype_dict = {"amf": [], "jms": [], "jma": [], "bitmap": []}
        # Search for folders first and add their files to filepaths
        folders = [path for path in self.filepaths if os.path.isdir(path)]
        for f in folders:
            for root, _, files in os.walk(f):
                for file in files:
                    self.filepaths.append(os.path.join(root, file))
                
        for path in self.filepaths:
            if path.lower().endswith('.amf'):
                filetype_dict["amf"].append(path)
            elif path.lower().endswith(legacy_model_formats):
                filetype_dict["jms"].append(path)
            elif path.lower().endswith(legacy_animation_formats):
                filetype_dict["jma"].append(path)
            elif path.lower().endswith('.bitmap'):
                filetype_dict["bitmap"].append(path)
                
        return filetype_dict
        
    # Utility functions
    
    def set_region(self, ob, region):
        regions_table = self.context.scene.nwo.regions_table
        entry = regions_table.get(region, 0)
        if not entry:
            # Create the entry
            regions_table.add()
            entry = regions_table[-1]
            entry.old = region
            entry.name = region
            
        ob.nwo.region_name_ui = region

    def set_permutation(self, ob, permutation):
        permutations_table = self.context.scene.nwo.permutations_table
        entry = permutations_table.get(permutation, 0)
        if not entry:
            # Create the entry
            permutations_table.add()
            entry = permutations_table[-1]
            entry.old = permutation
            entry.name = permutation
            
        ob.nwo.permutation_name_ui = permutation
        
    # Bitmap Import
    def extract_bitmaps(self, bitmap_files, image_format):
        print("\nExtracting Bitmaps")
        print(
            "-----------------------------------------------------------------------\n"
        )
        extracted_bitmaps = {}
        job = "Progress"
        bitmap_count = len(bitmap_files)
        for idx, fp in enumerate(bitmap_files):
            update_progress(job, idx / bitmap_count)
            bitmap_name = os.path.basename(fp)
            if 'lp_array' in bitmap_name or 'global_render_texture' in bitmap_name: continue # Filter out the bitmaps that crash ManagedBlam
            with BitmapTag(path=fp) as bitmap:
                if not bitmap.has_bitmap_data(): continue
                is_non_color = bitmap.is_linear()
                image_path = bitmap.save_to_tiff(blue_channel_fix=bitmap.used_as_normal_map(), format=image_format)
                if image_path:
                    # print(f"--- Extracted {os.path.basename(fp)} to {relative_path(image_path)}")
                    extracted_bitmaps[image_path] = is_non_color
        update_progress(job, 1)
        print(f"\nExtracted {len(extracted_bitmaps)} bitmaps")
        return extracted_bitmaps
    
    def load_bitmaps(self, image_paths, fake_user):
        print("\nLoading Bitmaps")
        print(
            "-----------------------------------------------------------------------\n"
        )
        job = "Progress"
        image_paths_count = len(image_paths)
        for idx, (path, is_non_color) in enumerate(image_paths.items()):
            update_progress(job, idx / image_paths_count)
            image = bpy.data.images.load(filepath=path, check_existing=True)
            image.use_fake_user = fake_user
            if is_non_color:
                image.colorspace_settings.name = 'Non-Color'
            else:
                image.alpha_mode = 'CHANNEL_PACKED'
            
        update_progress(job, 1)
    
    # AMF Importer
    def import_amf_files(self, amf_files):
        """Imports all amf files supplied"""
        self.amf_marker_objects = []
        self.amf_mesh_objects = []
        for path in amf_files:
            self.import_amf_file(path)
            
        return self.amf_mesh_objects + self.amf_marker_objects

    def import_amf_file(self, path):
        # get all objects that exist prior to import
        pre_import_objects = bpy.data.objects[:]
        file_name = dot_partition(os.path.basename(path))
        print(f"Importing AMF: {file_name}")
        with MutePrints():
            bpy.ops.import_scene.amf(filepath=path, import_units='MAX')
        new_objects = [ob for ob in bpy.data.objects if ob not in pre_import_objects]
        self.process_amf_objects(new_objects, file_name)
        
    def process_amf_objects(self, objects, file_name):
        is_model = bool([ob for ob in objects if ob.type == 'ARMATURE'])
        possible_bsp = file_name.rpartition('_')[2]
        # Add all objects to a collection
        new_coll = bpy.data.collections.new(file_name)
        if not is_model and possible_bsp:
            new_coll.name = 'bsp::' + possible_bsp
            regions_table = self.context.scene.nwo.regions_table
            entry = regions_table.get(possible_bsp, 0)
            if not entry:
                regions_table.add()
                entry = regions_table[-1]
                entry.old = possible_bsp
                entry.name = possible_bsp
                
            new_coll.nwo.type = 'region'
            new_coll.nwo.region = possible_bsp
            
        self.context.scene.collection.children.link(new_coll)
        self.amf_poops = []
        print("Setting object properties")
        for ob in objects:
            unlink(ob)
            new_coll.objects.link(ob)
            if ob.type == 'MESH':
                self.setup_amf_mesh(ob, is_model)
            elif ob.type == 'EMPTY':
                self.setup_amf_marker(ob, is_model)
                
        if self.amf_poops:
            print("Fixing scale")
            stomp_scale_multi_user(self.amf_poops)
    
    def setup_amf_mesh(self, ob, is_model):
        name = dot_partition(ob.name)
        nwo = ob.nwo
        if is_model:
            if name.startswith('Instances:'):
                # Need to implement this
                pass
            else:
                region, permutation = name.split(':')
                self.set_region(ob, region)
                self.set_permutation(ob, permutation)
        else:
            if name.startswith('Clusters'):
                nwo.mesh_type_ui = '_connected_geometry_mesh_type_structure'
            else:
                self.amf_poops.append(ob)
                
        self.amf_mesh_objects.append(ob)
        
    def setup_amf_marker(self, ob, is_model):
        name = dot_partition(ob.name)
        nwo = ob.nwo
        if is_model:
            if name.startswith('fx'):
                nwo.marker_type_ui = '_connected_geometry_marker_type_effects'
            elif name.startswith('target'):
                nwo.marker_type_ui = '_connected_geometry_marker_type_target'
            elif name.startswith('garbage'):
                nwo.marker_type_ui = '_connected_geometry_marker_type_garbage'
            elif name.startswith('hint'):
                nwo.marker_type_ui = '_connected_geometry_marker_type_hint'
                hint_parts = name.split('_')
                if len(hint_parts) > 1:
                    hint_type = hint_parts[1]
                    nwo.marker_hint_type = hint_type
                    if nwo.marker_hint_type != 'bunker' and len(hint_parts) > 2:
                        hint_subtype = hint_parts[2]
                        if hint_subtype in ('right', 'left'):
                            nwo.marker_hint_side = hint_subtype
                        elif hint_subtype in ('step', 'crouch', 'stand'):
                            nwo.marker_hint_height = hint_subtype
                            
        self.amf_marker_objects.append(ob)
            

# Legacy Animation importer
######################################################################
    def import_jma_files(self, jma_files):
        """Imports all legacy animation files supplied"""
        self.animations = []
        scene_nwo = self.context.scene.nwo
        if scene_nwo.main_armature:
            arm = scene_nwo.main_armature
        else:
            arms = [ob for ob in bpy.context.view_layer.objects if ob.type == 'ARMATURE']
            if arms:
                arm = arms[0]
            else:
                arm_data = bpy.data.armatures.new('Armature')
                arm = bpy.data.objects.new('Armature', arm_data)
                self.context.scene.collection.objects.link(arm)
            
        arm.hide_set(False)
        arm.hide_select = False
        set_active_object(arm)
        
        for path in jma_files:
            self.import_legacy_animation(path)
            
        return self.animations
            
        
    def import_legacy_animation(self, path):
        existing_animations = bpy.data.actions[:]
        bpy.ops.import_scene.jma(filepath=path, fix_rotations=self.legacy_fix_rotations)
        anim = [a for a in bpy.data.actions if a not in existing_animations][0]
        self.animations.append(anim)
        filename = os.path.basename(path)
        anim_name, extension = filename.split('.')
        nwo = anim.nwo
        if anim:
            anim.use_fake_user = True
            anim.use_frame_range = True
            if len(filename) > 64:
                nwo.name_override = anim_name
            match extension.lower():
                case 'jmm':
                    nwo.animation_type = 'base'
                    nwo.animation_movement_data = 'none'
                case 'jma':
                    nwo.animation_type = 'base'
                    nwo.animation_movement_data = 'xy'
                case 'jmt':
                    nwo.animation_type = 'base'
                    nwo.animation_movement_data = 'xyyaw'
                case 'jmz':
                    nwo.animation_type = 'base'
                    nwo.animation_movement_data = 'xyzyaw'
                case 'jmv':
                    nwo.animation_type = 'base'
                    nwo.animation_movement_data = 'full'
                case 'jmw':
                    nwo.animation_type = 'world'
                case 'jmo':
                    nwo.animation_type = 'overlay'
                    nwo.animation_is_pose = any(hint in anim_name.lower() for hint in pose_hints)
                case 'jmr':
                    nwo.animation_type = 'replacement'
                case 'jmrx':
                    nwo.animation_type = 'replacement'
                    nwo.animation_space = 'local'
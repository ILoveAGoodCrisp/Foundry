# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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
from pathlib import Path
import re
import time
from uuid import uuid4
import bmesh
import bpy
import addon_utils
from mathutils import Color
from io_scene_foundry.tools.mesh_to_marker import convert_to_marker
from io_scene_foundry.managed_blam.bitmap import BitmapTag
from io_scene_foundry.managed_blam.camera_track import CameraTrackTag
from io_scene_foundry.tools.clear_duplicate_materials import clear_duplicate_materials
from io_scene_foundry.tools.property_apply import apply_props_material
from io_scene_foundry.tools.shader_finder import find_shaders
from io_scene_foundry.tools.shader_reader import tag_to_nodes
from io_scene_foundry.utils.nwo_constants import VALID_MESHES
from io_scene_foundry.utils.nwo_utils import ExportManager, MutePrints, amf_addon_installed, apply_loop_normals, blender_toolset_installed, closest_bsp_object, dot_partition, get_prefs, get_rig, get_tags_path, human_time, is_corinth, layer_face_count, mute_armature_mods, print_warning, random_color, rotation_diff_from_forward, save_loop_normals, set_active_object, stomp_scale_multi_user, transform_scene, true_region, unlink, unmute_armature_mods, update_progress, legacy_lightmap_prefixes, clean_materials

pose_hints = 'aim', 'look', 'acc', 'steer'
legacy_model_formats = '.jms', '.ass'
legacy_animation_formats = '.jmm', '.jma', '.jmt', '.jmz', '.jmv', '.jmw', '.jmo', '.jmr', '.jmrx'
legacy_poop_prefixes = '%', '+', '-', '?', '!', '>', '*', '&', '^', '<', '|',
legacy_frame_prefixes = "frame_", "frame ", "bip_", "bip ", "b_", "b "

formats = "amf", "jms", "jma", "bitmap", "camera_track"

class NWO_OT_ConvertScene(bpy.types.Operator):
    bl_label = "Convert Scene"
    bl_idname = "nwo.convert_scene"
    bl_description = "Converts the scene from the selected format to Foundry standard"
    
    selected_only: bpy.props.BoolProperty(
        name="Selected Only",
        description="Restrict affected objects to only those selected"
    )
    
    convert_type: bpy.props.EnumProperty(
        name="Current Type",
        description="The type of format objects are currently in",
        items=[
            ('amf', "AMF", ""),
            ('jms', "JMS/ASS", ""),
        ]
    )
    
    jms_type: bpy.props.EnumProperty(
        name="JMS Type",
        description="Whether this is a model or a scenario",
        items=[
            ("model", "Model", ""),
            ("scenario", "Scenario", "")
        ]
    )
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "selected_only")
        layout.prop(self, "convert_type", expand=True)
        if self.convert_type == "jms":
            layout.prop(self, "jms_type", expand=True)
        
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        if self.selected_only:
            objects_in_scope = context.selected_objects
        else:
            objects_in_scope = bpy.data.objects
            
        with ExportManager():
            os.system("cls")
            start = time.perf_counter()
            user_cancelled = False
            if context.scene.nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                context.scene.nwo_export.show_output = False
            try:
                export_title = f"►►► FOUNDRY CONVERTER ◄◄◄"
                print(export_title, '\n')
                converter = NWOImporter(context, self.report, [], [])
                match self.convert_type:
                    case "amf":
                        converter.amf_marker_objects = []
                        converter.amf_mesh_objects = []
                        converter.amf_other_objects = []
                        converter.process_amf_objects(objects_in_scope, "")
                    case "jms":
                        converter.jms_marker_objects = []
                        converter.jms_mesh_objects = []
                        converter.jms_other_objects = []
                        converter.process_jms_objects(objects_in_scope, "", self.jms_type == 'model')
                
            except KeyboardInterrupt:
                print_warning("\nCANCELLED BY USER")
                user_cancelled = True
                
        end = time.perf_counter()
        if user_cancelled:
            self.report({'WARNING'}, "Cancelled by user")
        else:
            print(
                "\n-----------------------------------------------------------------------"
            )
            print(f"Completed in {round(end - start, 3)} seconds")

            print(
                "-----------------------------------------------------------------------\n"
            )
        return {'FINISHED'}

class NWO_Import(bpy.types.Operator):
    bl_label = "Import File(s)/Folder(s)"
    bl_idname = "nwo.import"
    bl_description = "Imports a variety of filetypes and sets them up for Foundry. Currently supports: AMF, JMA, JMS, ASS, bitmap tag, camera_track tag"
    
    @classmethod
    def poll(cls, context):
        return True
    
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
    
    filepath: bpy.props.StringProperty(
        name='Filepath',
        subtype='FILE_PATH',
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
    
    camera_track_animation_scale: bpy.props.FloatProperty(
        name='Animation Scale',
        default=1,
        min=1,
    )
    
    amf_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    legacy_okay : bpy.props.BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    
    scope: bpy.props.StringProperty(
        name="Scope",
        options={"HIDDEN", "SKIP_SAVE"}
    )
    
    def execute(self, context):
        filepaths = [self.directory + f.name for f in self.files]
        corinth = is_corinth(context)
        scale_factor = 0.03048 if context.scene.nwo.scale == 'blender' else 1
        to_x_rot = rotation_diff_from_forward(context.scene.nwo.forward_direction, 'x')
        from_x_rot = rotation_diff_from_forward('x', context.scene.nwo.forward_direction)
        needs_scaling = scale_factor != 1 or to_x_rot
        start = time.perf_counter()
        imported_objects = []
        imported_actions = []
        starting_materials = bpy.data.materials[:]
        self.nothing_imported = False
        self.user_cancelled = False
        with ExportManager():
            os.system("cls")
            if context.scene.nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                context.scene.nwo_export.show_output = False
            try:
                export_title = f"►►► FOUNDRY IMPORTER ◄◄◄"
                print(export_title, '\n')
                scope_list = []
                if self.scope:
                    scope_list = self.scope.split(',')
                importer = NWOImporter(context, self.report, filepaths, scope_list)
                if 'amf' in importer.extensions and self.amf_okay:
                    amf_module_name = amf_addon_installed()
                    amf_addon_enabled = addon_utils.check(amf_module_name)[0]
                    if not amf_addon_enabled:
                        addon_utils.enable(amf_module_name)
                    amf_files = importer.sorted_filepaths["amf"]
                    imported_amf_objects = importer.import_amf_files(amf_files, scale_factor)
                    if not amf_addon_enabled:
                        addon_utils.disable(amf_module_name)
                    if imported_amf_objects:
                        imported_objects.extend(imported_amf_objects)
                    
                    if to_x_rot:
                        transform_scene(context, 1, from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_amf_objects, actions=[])
                        
                if self.legacy_okay and any([ext in ('jms', 'jma') for ext in importer.extensions]):
                    toolset_addon_enabled = addon_utils.check('io_scene_halo')[0]
                    if not toolset_addon_enabled:
                        addon_utils.enable('io_scene_halo')
                    jms_files = importer.sorted_filepaths["jms"]
                    jma_files = importer.sorted_filepaths["jma"]
                    # Transform Scene so it's ready for JMA/JMS files
                    if needs_scaling:
                        transform_scene(context, (1 / scale_factor), to_x_rot, context.scene.nwo.forward_direction, 'x')
                        
                    imported_jms_objects = importer.import_jms_files(jms_files, self.legacy_fix_rotations)
                    imported_jma_animations = importer.import_jma_files(jma_files, self.legacy_fix_rotations)
                    if imported_jma_animations:
                        imported_actions.extend(imported_jma_animations)
                    if imported_jms_objects:
                        imported_objects.extend(imported_jms_objects)
                    if not toolset_addon_enabled:
                        addon_utils.disable('io_scene_halo')
                        
                    # Return to our scale
                    if needs_scaling:
                        transform_scene(context, scale_factor, from_x_rot, 'x', context.scene.nwo.forward_direction)
                
                new_materials = [mat for mat in bpy.data.materials if mat not in starting_materials]
                # Clear duplicate materials
                if new_materials:
                    new_materials = clear_duplicate_materials(True, new_materials)
                
                if self.find_shader_paths and imported_objects:
                    print('Updating shader tag paths for imported objects')
                    imported_meshes: list[bpy.types.Mesh] = set([ob.data for ob in imported_objects if ob.type in VALID_MESHES])
                    if imported_meshes:
                        if new_materials:
                            find_shaders(new_materials)
                            if self.build_blender_materials:
                                print('Building materials from shader tags')
                                with MutePrints():
                                    for mat in new_materials:
                                        shader_path = mat.nwo.shader_path
                                        if shader_path:
                                            tag_to_nodes(corinth, mat, shader_path)
                        
                if 'bitmap' in importer.extensions:
                    if not self.directory.startswith(get_tags_path()):
                        self.report({'WARNING'}, "Can only extract bitmaps from the current project's tags folder")
                        return {'FINISHED'}
                    bitmap_files = importer.sorted_filepaths["bitmap"]
                    if not bitmap_files:
                        self.nothing_imported = True
                    else:
                        extracted_bitmaps = importer.extract_bitmaps(bitmap_files, self.extracted_bitmap_format)
                        if self.import_images_to_blender:
                            importer.load_bitmaps(extracted_bitmaps, self.images_fake_user)
                                    
                        self.report({'INFO'}, f"Extracted {'and imported' if self.import_images_to_blender else ''} {len(bitmap_files)} bitmaps")
                        
                if 'camera_track' in importer.extensions:
                    camera_track_files = importer.sorted_filepaths["camera_track"]
                    imported_camera_track_objects = importer.import_camera_tracks(camera_track_files, self.camera_track_animation_scale)
                    if needs_scaling:
                        transform_scene(context, scale_factor, from_x_rot, 'x', context.scene.nwo.forward_direction, objects=imported_camera_track_objects)
                        
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
            print(f"Import Completed in {human_time(end - start)}")

            print(
                "-----------------------------------------------------------------------\n"
            )
            
        return {'FINISHED'}
    
    def invoke(self, context, event):
        if 'bitmap' in self.scope:
            self.directory = get_tags_path()
        elif 'camera_track' in self.scope:
            cameras_dir = get_tags_path() + 'camera'
            if os.path.exists(cameras_dir):
                self.directory = get_tags_path() + 'camera'
            else:
                self.directory = get_tags_path()
        else:
            self.directory = ''
            self.filepath = ''
            
        self.filename = ''
        if (not self.scope or 'bitmap' in self.scope):
            self.directory = get_tags_path()
            self.filter_glob += "*.bitmap;"
        if amf_addon_installed() and (not self.scope or 'amf' in self.scope):
            self.amf_okay = True
            self.filter_glob += "*.amf;"
        if blender_toolset_installed() and (not self.scope or 'jms' in self.scope):
            self.legacy_okay = True
            self.filter_glob += '*.jms;*.ass;'
        if blender_toolset_installed() and (not self.scope or 'jma' in self.scope):
            self.legacy_okay = True
            self.filter_glob += '*.jmm;*.jma;*.jmt;*.jmz;*.jmv;*.jmw;*.jmo;*.jmr;*.jmrx'
        if (not self.scope or 'camera_track' in self.scope):
            self.filter_glob += '*.camera_track'
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.25
        if not self.scope or ('amf' in self.scope or 'jms' in self.scope):
            box = layout.box()
            box.label(text="Model Settings")
            tag_type = 'material' if is_corinth(context) else 'shader'
            box.prop(self, 'find_shader_paths', text=f"Find {tag_type.capitalize()} Tag Paths")
            if self.find_shader_paths:
                box.prop(self, 'build_blender_materials', text=f"Blender Materials from {tag_type.capitalize()} Tags")
        
        if not self.scope or ('jma' in self.scope or 'jms' in self.scope):
            box = layout.box()
            box.label(text="JMA/JMS/ASS Settings")
            box.prop(self, 'legacy_fix_rotations', text='Fix Rotations')
        
        if not self.scope or ('bitmap' in self.scope):
            box = layout.box()
            box.label(text="Bitmap Settings")
            box.use_property_split = True
            box.prop(self, 'extracted_bitmap_format')
            box.prop(self, 'import_images_to_blender')
            if self.import_images_to_blender:
                box.prop(self, 'images_fake_user')
                
        if not self.scope or ('camera_track' in self.scope):
            box = layout.box()
            box.label(text='Camera Track Settings')
            box.prop(self, 'camera_track_animation_scale')
            
class JMSMaterialSlot:
    def __init__(self, slot: bpy.types.MaterialSlot):
        self.material = slot.material
        self.index = slot.slot_index
        self.name = slot.material.name
        self._material_props_from_name()
        self._material_props_from_ui()
        
        if self.water_surface:
            self.mesh_type = '_connected_geometry_mesh_type_water_surface'
        else:
            self.mesh_type = self._mesh_type_from_special_name()
        
    def _mesh_type_from_special_name(self):
        name = self.material.name
        if name.startswith('+portal') or self.portal_one_way or self.portal_vis_blocker:
            return 'portal'
        elif name.startswith('+seam') and not name.startswith('+seams'):
            return 'seam'
        elif name.startswith('+soft_ceiling'):
            return 'soft_ceiling'
        elif name.startswith('+soft_kill'):
            return 'soft_kill'
        elif name.startswith('+slip_surface'):
            return 'slip_surface'
        elif self.collision_only or self.sphere_collision_only:
            return 'collision'
        elif self.fog_plane:
            return 'fog'
        elif self.lightmap_only:
            return 'lightmap_only'
        elif self.water_surface:
            return 'water_surface'
        
        return 'default'
            
    def _material_props_from_ui(self):
        self.two_sided = self.material.ass_jms.two_sided or self.two_sided
        self.transparent_one_sided = self.material.ass_jms.transparent_1_sided or self.transparent_one_sided
        self.transparent_two_sided = self.material.ass_jms.transparent_2_sided or self.transparent_two_sided
        self.render_only = self.material.ass_jms.render_only or self.render_only
        self.collision_only = self.material.ass_jms.collision_only or self.collision_only
        self.sphere_collision_only = self.material.ass_jms.sphere_collision_only or self.sphere_collision_only
        self.fog_plane = self.material.ass_jms.fog_plane or self.fog_plane
        self.ladder = self.material.ass_jms.ladder or self.ladder
        self.breakable = self.material.ass_jms.breakable or self.breakable
        self.ai_deafening = self.material.ass_jms.ai_deafening or self.ai_deafening
        self.no_shadow = self.material.ass_jms.no_shadow or self.no_shadow
        self.lightmap_only = self.material.ass_jms.lightmap_only or self.lightmap_only
        self.precise = self.material.ass_jms.precise or self.precise
        self.portal_one_way = self.material.ass_jms.portal_1_way or self.portal_one_way
        self.portal_door = self.material.ass_jms.portal_door or self.portal_door
        self.portal_vis_blocker = self.material.ass_jms.portal_vis_blocker or self.portal_vis_blocker
        self.ignored_by_lightmaps = self.material.ass_jms.ignored_by_lightmaps or self.ignored_by_lightmaps
        self.blocks_sound = self.material.ass_jms.blocks_sound or self.blocks_sound
        self.decal_offset = self.material.ass_jms.decal_offset or self.decal_offset
        self.water_surface = self.material.ass_jms.water_surface or self.water_surface
        self.slip_surface = self.material.ass_jms.slip_surface
        self.global_material = self.material.ass_jms.material_effect
        # lightmap
        if self.material.ass_jms.lightmap_res != 1:
            self.lightmap_resolution_scale = self.material.ass_jms.lightmap_res
        if self.material.ass_jms.additive_transparency != Color((0.0, 0.0, 0.0)):
            self.lightmap_additive_transparency = self.material.ass_jms.additive_transparency
        if self.material.ass_jms.two_sided_transparent_tint != Color((0.0, 0.0, 0.0)):
            self.lightmap_translucency_tint_color = self.material.ass_jms.additive_transparency
            
        # Emissive
        self.emissive_power = None
        self.emissive_color = None
        self.emissive_quality = None
        self.emissive_per_unit = None
        self.emissive_shader_gel = None
        self.emissive_focus = None
        self.emissive_attenuation = None
        self.emissive_attenuation_falloff = None
        self.emissive_attenuation_cutoff = None
        self.emissive_frustum_blend = None
        self.emissive_frustum_falloff = None
        self.emissive_frustum_cutoff = None
        
        if self.material.ass_jms.power > 0:
            self.emissive_power = self.material.ass_jms.power
            self.emissive_color = self.material.ass_jms.color
            self.emissive_quality = self.material.ass_jms.quality
            self.emissive_per_unit = self.material.ass_jms.power_per_unit_area
            self.emissive_shader_gel = self.material.ass_jms.use_shader_gel
            self.emissive_focus = self.material.ass_jms.emissive_focus
            self.emissive_attenuation = self.material.ass_jms.attenuation_enabled
            if self.emissive_attenuation:
                self.emissive_attenuation_falloff = self.material.ass_jms.falloff_distance
                self.emissive_attenuation_cutoff = self.material.ass_jms.cutoff_distance
            else:
                self.emissive_attenuation_falloff = 0
                self.emissive_attenuation_cutoff = 0
        
    def _material_props_from_name(self):
        name = self.material.name
        self.two_sided = '%' in name
        self.transparent_one_sided = '#' in name
        self.transparent_two_sided = '?' in name
        self.render_only = '!' in name
        self.collision_only = '@' in name
        self.sphere_collision_only = '*' in name
        self.fog_plane = '$' in name
        self.ladder = '^' in name
        self.breakable = '-' in name
        self.ai_deafening = '&' in name
        self.no_shadow = '=' in name
        self.lightmap_only = ';' in name
        self.precise = ')' in name
        self.portal_one_way = '<' in name
        self.portal_door = '|' in name
        self.portal_vis_blocker = '~' in name
        self.ignored_by_lightmaps = '{' in name
        self.blocks_sound = '}' in name
        self.decal_offset = '[' in name
        self.water_surface = "'" in name
        # self.slip_surface = False
        
        # lighting props
        self.lightmap_resolution_scale = None
        self.lightmap_translucency_tint_color = None
        self.lightmap_additive_transparency = None
        
        parts = name.split()
        if len(parts) > 1 and (parts[0].startswith(legacy_lightmap_prefixes) or parts[-1].startswith(legacy_lightmap_prefixes)):
            pattern = r'(' + '|'.join(legacy_lightmap_prefixes) + r')(\d+\.?\d*)'
            matches = re.findall(pattern, name)
            for match_groups in matches:
                if len(match_groups) <= 1:
                    continue
                match match_groups[0]:
                    # Only handling lightmap res currently
                    case 'lm:':
                        self.lightmap_resolution_scale = float(match_groups[1])
        
    def __eq__(self, __value: 'JMSMaterialSlot') -> bool:
        if not isinstance(__value, self.__class__):
            return False
        if self.two_sided != __value.two_sided:
            return False
        if self.transparent_one_sided != __value.transparent_one_sided:
            return False
        if self.transparent_two_sided != __value.transparent_two_sided:
            return False
        if self.render_only != __value.render_only:
            return False
        if self.collision_only != __value.collision_only:
            return False
        if self.sphere_collision_only != __value.sphere_collision_only:
            return False
        if self.fog_plane != __value.fog_plane:
            return False
        if self.ladder != __value.ladder:
            return False
        if self.breakable != __value.breakable:
            return False
        if self.ai_deafening != __value.ai_deafening:
            return False
        if self.no_shadow != __value.no_shadow:
            return False
        if self.lightmap_only != __value.lightmap_only:
            return False
        if self.precise != __value.precise:
            return False
        if self.portal_one_way != __value.portal_one_way:
            return False
        if self.portal_door != __value.portal_door:
            return False
        if self.portal_vis_blocker != __value.portal_vis_blocker:
            return False
        if self.ignored_by_lightmaps != __value.ignored_by_lightmaps:
            return False
        if self.blocks_sound != __value.blocks_sound:
            return False
        if self.decal_offset != __value.decal_offset:
            return False
        if self.water_surface != __value.water_surface:
            return False
        if self.slip_surface != __value.slip_surface:
            return False
        if self.global_material != __value.global_material:
            return False
        
        return True


class NWOImporter:
    def __init__(self, context, report, filepaths, scope):
        self.filepaths = filepaths
        self.context = context
        self.report = report
        self.mesh_objects = []
        self.marker_objects = []
        self.extensions = set()
        self.apply_materials = get_prefs().apply_materials
        self.prefix_setting = get_prefs().apply_prefix
        if filepaths:
            self.sorted_filepaths = self.group_filetypes(scope)
        else:
            self.sorted_filepaths = []
    
    def group_filetypes(self, scope):
        if scope:
            filetype_dict = {ext: [] for ext in scope}
        else:
            filetype_dict = {ext: [] for ext in formats}
        # Search for folders first and add their files to filepaths
        folders = [path for path in self.filepaths if os.path.isdir(path)]
        for f in folders:
            for root, _, files in os.walk(f):
                for file in files:
                    self.filepaths.append(os.path.join(root, file))
                    
        valid_exts = filetype_dict.keys()
        for path in self.filepaths:
            if 'amf' in valid_exts and path.lower().endswith('.amf'):
                self.extensions.add('amf')
                filetype_dict["amf"].append(path)
            elif 'jms' in valid_exts and path.lower().endswith(legacy_model_formats):
                self.extensions.add('jms')
                filetype_dict["jms"].append(path)
            elif 'jma' in valid_exts and path.lower().endswith(legacy_animation_formats):
                self.extensions.add('jma')
                filetype_dict["jma"].append(path)
            elif 'bitmap' in valid_exts and path.lower().endswith('.bitmap'):
                self.extensions.add('bitmap')
                filetype_dict["bitmap"].append(path)
            elif 'camera_track' in valid_exts and path.lower().endswith('.camera_track'):
                self.extensions.add('camera_track')
                filetype_dict["camera_track"].append(path)
                
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
        
    def new_face_prop(self, data, layer_name, display_name, override_prop, other_props={}) -> str:
        face_props = data.nwo.face_props
        layer = face_props.add()
        layer.layer_name = layer_name
        layer.name = display_name
        layer.layer_color = random_color()
        setattr(layer, override_prop, True)
        for prop, value in other_props.items():
            setattr(layer, prop, value)
            
        return layer_name
        
    # Camera track import
    def import_camera_tracks(self, paths, animation_scale):
        imported_objects = []
        for file in paths:
            imported_objects.append(self.import_camera_track(file, animation_scale))
        
        return imported_objects
            
    def import_camera_track(self, file, animation_scale):
        with CameraTrackTag(path=file) as camera_track:
            camera = camera_track.to_blender_animation(self.context, animation_scale)
            
        return camera
        
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
    def import_amf_files(self, amf_files, scale_factor):
        """Imports all amf files supplied"""
        self.amf_marker_objects = []
        self.amf_mesh_objects = []
        self.amf_other_objects = []
        import_size = 'MAX' if scale_factor == 1 else 'METERS'
        for path in amf_files:
            self.import_amf_file(path, import_size)
            
        return self.amf_mesh_objects + self.amf_marker_objects + self.amf_other_objects

    def import_amf_file(self, path, import_size):
        # get all objects that exist prior to import
        path = Path(path)
        pre_import_objects = bpy.data.objects[:]
        file_name = dot_partition(os.path.basename(path))
        print(f"Importing AMF: {file_name}")
        with MutePrints():
            bpy.ops.import_scene.amf(files=[{'name': path.name}], directory=str(path.parent), import_units=import_size, marker_prefix='')
        new_objects = [ob for ob in bpy.data.objects if ob not in pre_import_objects]
        self.process_amf_objects(new_objects, file_name)
        
    def process_amf_objects(self, objects, file_name):
        is_model = bool([ob for ob in objects if ob.type == 'ARMATURE'])
        possible_bsp = file_name.rpartition('_')[2]
        # Add all objects to a collection
        if file_name:
            new_coll = bpy.data.collections.get(file_name, 0)
            if not new_coll:
                new_coll = bpy.data.collections.new(file_name)
                self.context.scene.collection.children.link(new_coll)
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
            
        self.amf_poops = []
        print("Setting object properties")
        for ob in objects:
            if file_name:
                unlink(ob)
                new_coll.objects.link(ob)
            if ob.type == 'MESH':
                self.setup_amf_mesh(ob, is_model)
            elif ob.type == 'EMPTY':
                self.setup_amf_marker(ob, is_model)
            else:
                self.amf_other_objects.append(ob)
                
        if self.amf_poops:
            print("Fixing scale")
            stomp_scale_multi_user(self.amf_poops)
    
    def setup_amf_mesh(self, ob, is_model):
        name = dot_partition(ob.name)
        if is_model:
            if name.startswith('Instances:'):
                ob.data.nwo.mesh_type_ui = '_connected_geometry_mesh_type_object_instance'
            else:
                parts = name.split(':')
                if len(parts) > 1:
                    region, permutation = parts[0], parts[1]
                    self.set_region(ob, dot_partition(region))
                    self.set_permutation(ob, dot_partition(permutation))
        else:
            if name.startswith('Clusters'):
                ob.data.nwo.mesh_type_ui = '_connected_geometry_mesh_type_structure'
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
                            nwo.marker_hint_height = hint_subtype#
                            
        self.amf_marker_objects.append(ob)
        
# JMS/ASS importer
######################################################################

    def import_jms_files(self, jms_files, legacy_fix_rotations):
        """Imports all JMS/ASS files supplied"""
        if not jms_files:
            return []
        self.jms_marker_objects = []
        self.jms_mesh_objects = []
        self.jms_other_objects = []
        self.seams = []
        for path in jms_files:
            self.import_jms_file(path,legacy_fix_rotations)
            
        if self.seams:
            print('Calculating seam BSP references')
            self.context.view_layer.update()
            disallowed_front_back_associations = set()
            to_remove = []
            for ob in self.seams:
                bsp_ob = closest_bsp_object(self.context, ob)
                if not bsp_ob:
                    continue
                back_face = true_region(bsp_ob.nwo)
                if (true_region(ob.nwo) + back_face) in disallowed_front_back_associations:
                    to_remove.append(ob)
                    continue
                ob.nwo.seam_back_ui = true_region(bsp_ob.nwo)
                disallowed_front_back_associations.add(ob.nwo.seam_back_ui + true_region(ob.nwo))
                
            for ob in to_remove:
                self.jms_mesh_objects.remove(ob)
                bpy.data.objects.remove(ob)
            
        return self.jms_marker_objects + self.jms_mesh_objects + self.jms_other_objects
    
    def import_jms_file(self, path, legacy_fix_rotations):
        # get all objects that exist prior to import
        pre_import_objects = bpy.data.objects[:]
        file_name = dot_partition(os.path.basename(path))
        ext = dot_partition(os.path.basename(path), True).upper()
        print(f"Importing {ext}: {file_name}")
        with MutePrints():
            if ext == 'JMS':
                bpy.ops.import_scene.jms(filepath=path, fix_rotations=legacy_fix_rotations, reuse_armature=True, empty_markers=True)
            else:
                bpy.ops.import_scene.ass(filepath=path)
                
        new_objects = [ob for ob in bpy.data.objects if ob not in pre_import_objects]
        self.process_jms_objects(new_objects, file_name, bool([ob for ob in new_objects if ob.type == 'ARMATURE']) or ext == 'JMS')
        
    def process_jms_objects(self, objects: list[bpy.types.Object], file_name, is_model):
        # Add all objects to a collection
        if file_name:
            new_coll = bpy.data.collections.get(file_name, 0)
            if not new_coll:
                new_coll = bpy.data.collections.new(file_name)
                self.context.scene.collection.children.link(new_coll)
        if not is_model and file_name:
            possible_bsp = file_name.rpartition('_')[2]
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
        
        print("Setting object properties")
        if is_model:
            objects_with_halo_regions = [ob for ob in objects if ob.region_list]
            for ob in objects_with_halo_regions:
                prefix = ob.name[0] if ob.name[0] in ('$', '@', '%', '~') else ''
                if len(ob.region_list) == 1:
                    parts = ob.region_list[0].name.split(' ')
                    if len(parts) == 1:
                        region = parts[0]
                        ob.name = f'{prefix}{region}'
                    elif len(parts) == 2:
                        perm = parts[0]
                        region = parts[1]
                        ob.name = f'{prefix}{region}:{perm}'
                    elif len(parts) > 2:
                        perm = parts[-2]
                        region = parts[-1]
                        ob.name = f'{prefix}{region}:{perm}'
                else:
                    original_bm = bmesh.new()
                    original_bm.from_mesh(ob.data)
                    save_loop_normals(original_bm, ob.data)
                    for idx, perm_region in enumerate(ob.region_list):
                        parts = perm_region.name.split(' ')
                        if len(parts) == 1:
                            region = parts[0]
                            new_name = f'{prefix}{region}'
                        elif len(parts) == 2:
                            perm = parts[0]
                            region = parts[1]
                            new_name = f'{prefix}{region}:{perm}'
                        elif len(parts) > 2:
                            perm = parts[-2]
                            region = parts[-1]
                            new_name = f'{prefix}{region}:{perm}'

                        new_ob = ob.copy()
                        new_ob.name = new_name
                        new_ob.data = ob.data.copy()
                        bm = original_bm.copy()
                        region_layer = bm.faces.layers.int.get("Region Assignment")
                        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[region_layer] != idx + 1], context='FACES')
                        bm.to_mesh(new_ob.data)
                        apply_loop_normals(new_ob.data)
                        clean_materials(new_ob)
                        objects.append(new_ob)
                
                    objects.remove(ob)
                    bpy.data.objects.remove(ob)
        
        self.processed_meshes = []
        if file_name:
            self.new_coll = new_coll
        else:
            self.new_coll = self.context.scene.collection
            
        for ob in objects:
            if file_name:
                unlink(ob)
                new_coll.objects.link(ob)
            if ob.name.startswith(legacy_frame_prefixes) or ob.type == 'ARMATURE':
                self.setup_jms_frame(ob)
            elif ob.name.startswith('#') or (is_model and ob.type =='EMPTY' and ob.name.startswith('$')):
                self.setup_jms_marker(ob, is_model)
            elif ob.type == 'MESH':
                self.setup_jms_mesh(ob, is_model)
                
    def setup_jms_frame(self, ob):
        ob.nwo.frame_override = True
        if ob.type == 'MESH':
            marker = convert_to_marker(ob)
            bpy.data.objects.remove(ob)
            self.jms_other_objects.append(marker)
        else:
            self.jms_other_objects.append(ob)
            
    def setup_jms_marker(self, ob, is_model):
        perm, region = None, None
        constraint = is_model and ob.name.startswith('$')
        name = ob.name[1:]
        if ')' in name:
            perm_region, name = name.split(')')
            perm, region = perm_region[1:].split(' ')
        
        if ob.type == 'EMPTY':
            marker = ob
            marker.name = name
        else:
            original_matrix = ob.matrix_world.copy()
            original_parent = ob.parent
            original_parent_type = ob.parent_type
            original_parent_bone = ob.parent_bone
            radius = max(ob.dimensions.x, ob.dimensions.y, ob.dimensions.z) / 2
            scale = ob.scale.copy()
            bpy.data.objects.remove(ob)
            marker = bpy.data.objects.new(name, None)
            marker.parent = original_parent
            marker.parent_type = original_parent_type
            marker.parent_bone = original_parent_bone
            marker.matrix_world = original_matrix
            marker.scale = scale
            marker.empty_display_size = radius
            marker.empty_display_type = 'ARROWS'
            
        if is_model and region is not None:
            if region not in [region.name for region in self.context.scene.nwo.regions_table]:
                region_entry = self.context.scene.nwo.regions_table.add()
                region_entry.name = region
                region_entry.old = region
            marker.nwo.region_name_ui = region
            marker.nwo.marker_uses_regions = True
            
            if is_model and perm is not None:
                if perm not in [perm.name for perm in self.context.scene.nwo.permutations_table]:
                    perm_entry = self.context.scene.nwo.permutations_table.add()
                    perm_entry.name = perm
                    perm_entry.old = perm
                marker.nwo.marker_permutations.add().name = perm
                marker.nwo.marker_permutation_type = 'include'
                
        if constraint:
            marker.nwo.marker_type_ui = '_connected_geometry_marker_type_physics_constraint'
            marker.nwo.physics_constraint_parent_ui = marker.rigid_body_constraint.object1
            marker.nwo.physics_constraint_child_ui = marker.rigid_body_constraint.object2
            if marker.rigid_body_constraint.type == 'HINGE':
                marker.nwo.physics_constraint_type_ui = '_connected_geometry_marker_type_physics_hinge_constraint'
                if marker.rigid_body_constraint.use_limit_ang_z:
                    marker.nwo.physics_constraint_uses_limits_ui = True
                    marker.nwo.hinge_constraint_minimum_ui = marker.rigid_body_constraint.limit_ang_z_lower
                    marker.nwo.hinge_constraint_maximum_ui = marker.rigid_body_constraint.limit_ang_z_upper
            elif marker.rigid_body_constraint.type == 'GENERIC':
                marker.nwo.physics_constraint_type_ui = '_connected_geometry_marker_type_physics_socket_constraint'
                if marker.rigid_body_constraint.use_limit_ang_x or marker.rigid_body_constraint.use_limit_ang_y or marker.rigid_body_constraint.use_limit_ang_z:
                    marker.nwo.physics_constraint_uses_limits_ui = True
                    if marker.rigid_body_constraint.use_limit_ang_x:
                        marker.nwo.twist_constraint_start_ui = marker.rigid_body_constraint.limit_ang_x_lower
                        marker.nwo.twist_constraint_end_ui = marker.rigid_body_constraint.limit_ang_x_upper
                    if marker.rigid_body_constraint.use_limit_ang_y:
                        marker.nwo.cone_angle_ui = marker.rigid_body_constraint.limit_ang_y_upper
                    if marker.rigid_body_constraint.use_limit_ang_z:
                        marker.nwo.plane_constraint_minimum_ui = marker.rigid_body_constraint.limit_ang_z_lower
                        marker.nwo.plane_constraint_maximum_ui = marker.rigid_body_constraint.limit_ang_z_upper
                
        elif name.startswith('fx'):
            marker.nwo.marker_type_ui = '_connected_geometry_marker_type_effects'
        elif name.startswith('target'):
            marker.nwo.marker_type_ui = '_connected_geometry_marker_type_target'
            marker.empty_display_type = 'SPHERE'
        elif name.startswith('garbage'):
            marker.nwo.marker_type_ui = '_connected_geometry_marker_type_garbage'
        elif name.startswith('hint'):
            marker.nwo.marker_type_ui = '_connected_geometry_marker_type_hint'
            hint_parts = name.split('_')
            if len(hint_parts) > 1:
                hint_type = hint_parts[1]
                marker.nwo.marker_hint_type = hint_type
                if marker.nwo.marker_hint_type != 'bunker' and len(hint_parts) > 2:
                    hint_subtype = hint_parts[2]
                    if hint_subtype in ('right', 'left'):
                        marker.nwo.marker_hint_side = hint_subtype
                    elif hint_subtype in ('step', 'crouch', 'stand'):
                        marker.nwo.marker_hint_height = hint_subtype
                
        self.jms_marker_objects.append(marker)
        
    def setup_jms_mesh(self, ob, is_model):
        new_objects = self.convert_material_props(ob)
        for ob in new_objects:
            mesh_type_legacy = self.get_mesh_type(ob, is_model)
            ob.nwo.mesh_type = ''
            if ob.name.startswith('%'):
                self.set_poop_policies(ob)
            if mesh_type_legacy:
                mesh_type, material = self.mesh_and_material(mesh_type_legacy, is_model)
                ob.data.nwo.mesh_type_ui = mesh_type
                if mesh_type == '_connected_geometry_mesh_type_structure':
                    ob.nwo.proxy_instance = True
                elif mesh_type == '_connected_geometry_mesh_type_seam':
                    self.seams.append(ob)

                elif mesh_type_legacy in ('collision', 'physics'):
                    self.setup_collision_materials(ob, mesh_type_legacy)
                    if mesh_type_legacy == 'physics':
                        match ob.data.ass_jms.Object_Type:
                            case "CAPSULES":
                                ob.nwo.mesh_primitive_type_ui = "_connected_geometry_primitive_type_pill"
                            case "SPHERE":
                                ob.nwo.mesh_primitive_type_ui = "_connected_geometry_primitive_type_sphere"
                            case "BOX":
                                ob.nwo.mesh_primitive_type_ui = "_connected_geometry_primitive_type_box"
                            case _:
                                ob.nwo.mesh_primitive_type_ui = "_connected_geometry_primitive_type_none"
                    
                if self.apply_materials:
                    apply_props_material(ob, material)
                
            if is_model:
                if ':' not in ob.name:
                    self.set_region(ob, ob.name.strip('@$~%'))
                else:
                    region, permutation = ob.name.strip('@$~%').split(':')
                    self.set_region(ob, dot_partition(region))
                    self.set_permutation(ob, dot_partition(permutation))
                
            self.jms_mesh_objects.append(ob)
            
    def set_poop_policies(self, ob):
        for char in ob.name[1:]:
            match char:
                case '+':
                    ob.nwo.poop_pathfinding_ui = '_connected_poop_instance_pathfinding_policy_static'
                case '-':
                    ob.nwo.poop_pathfinding_ui = '_connected_poop_instance_pathfinding_policy_none'
                case '?':
                    ob.nwo.poop_lighting_ui = '_connected_geometry_poop_lighting_per_vertex'
                case '!':
                    ob.nwo.poop_lighting_ui = '_connected_geometry_poop_lighting_per_pixel'
                case '>':
                    ob.nwo.poop_lighting_ui = '_connected_geometry_poop_lighting_single_probe'
                case '*':
                    ob.data.nwo.render_only_ui = True
                case '&':
                    ob.nwo.poop_chops_portals_ui = True
                case '^':
                    ob.nwo.poop_does_not_block_aoe_ui = True
                case '<':
                    ob.nwo.poop_excluded_from_lightprobe_ui = True
                case '|':
                    ob.data.nwo.decal_offset_ui = True
                case _:
                    return
        
    def convert_material_props(self, ob: bpy.types.Object):
        if ob.name.startswith('$'):
            return [ob]
        
        if ob.data in self.processed_meshes:
            ob.nwo.mesh_type = 'skip'
            return [ob]

        objects_to_setup = [ob]
        self.processed_meshes.append(ob.data)
        jms_materials: list[JMSMaterialSlot] = []
        for slot in ob.material_slots:
            if not slot.material:
                continue
            jms_materials.append(JMSMaterialSlot(slot))
        
        if len(jms_materials) == 1:
            jms_mat = jms_materials[0]
            ob.nwo.mesh_type = jms_mat.mesh_type
            nwo = ob.data.nwo
            nwo.face_two_sided_ui = jms_mat.two_sided or jms_mat.transparent_two_sided
            nwo.face_transparent_ui = jms_mat.transparent_one_sided or jms_mat.transparent_two_sided
            nwo.render_only_ui = jms_mat.render_only
            nwo.sphere_collision_only_ui = jms_mat.sphere_collision_only
            nwo.ladder_ui = jms_mat.ladder
            nwo.breakable_ui = jms_mat.breakable
            nwo.portal_ai_deafening_ui = jms_mat.ai_deafening
            nwo.no_shadow_ui = jms_mat.no_shadow
            nwo.precise_position_ui = jms_mat.precise
            if jms_mat.portal_one_way:
                nwo.portal_type_ui = '_connected_geometry_portal_type_one_way'
            nwo.portal_is_door_ui = jms_mat.portal_door
            if jms_mat.portal_vis_blocker:
                nwo.portal_type_ui = '_connected_geometry_portal_type_no_way'
            nwo.no_lightmap_ui = jms_mat.ignored_by_lightmaps
            nwo.portal_blocks_sounds_ui = jms_mat.blocks_sound
            nwo.decal_offset_ui = jms_mat.decal_offset
            nwo.slip_surface_ui = jms_mat.slip_surface
            nwo.face_global_material_ui = jms_mat.global_material
        
        mesh_types = list(set([m.mesh_type for m in jms_materials if m.mesh_type]))
        if len(mesh_types) == 1:
            ob.nwo.mesh_type = mesh_types[0]
        elif len(mesh_types) > 1:
            linked_objects = [o for o in bpy.data.objects if o != ob and o.data == ob.data]
            bm_original = bmesh.new()
            bm_original.from_mesh(ob.data)
            save_loop_normals(bm_original, ob.data)
            for jms_mat in jms_materials:
                if jms_mat.mesh_type == 'default':
                    continue
                new_ob = ob.copy()
                new_ob.data = ob.data.copy()
                bm = bm_original.copy()
                faces_to_remove = [face for face in bm.faces if face.material_index != jms_mat.index]
                faces_to_remove_original = [face for face in bm_original.faces if face.material_index == jms_mat.index]
                bmesh.ops.delete(bm, geom=faces_to_remove, context='FACES')
                bmesh.ops.delete(bm_original, geom=faces_to_remove_original, context='FACES')
                bm.to_mesh(new_ob.data)
                apply_loop_normals(new_ob.data)
                clean_materials(new_ob)
                    
                new_ob.nwo.mesh_type = jms_mat.mesh_type
                objects_to_setup.append(new_ob)
                self.new_coll.objects.link(new_ob)
                for obj in linked_objects:
                    new_ob_copy = new_ob.copy()
                    new_ob_copy.parent = obj.parent
                    new_ob_copy.parent_type = obj.parent_type
                    new_ob_copy.parent_bone = obj.parent_bone
                    new_ob_copy.matrix_world = obj.matrix_world
                
            bm_original.to_mesh(ob.data)
            if not ob.data.polygons:
                objects_to_setup.remove(ob)
                bpy.data.objects.remove(ob)
            else:
                apply_loop_normals(ob.data)
                clean_materials(ob)
            
        for ob in objects_to_setup:
            if len(ob.data.materials) == 1 or self.matching_material_properties(ob.data.materials, jms_materials):
                jms_mats = [mat for mat in jms_materials if mat.name == ob.data.materials[0].name]
                if jms_mats:
                    jms_mat = jms_mats[0]
                    ob.nwo.mesh_type = jms_mat.mesh_type
                    nwo = ob.data.nwo
                    nwo.face_two_sided_ui = jms_mat.two_sided or jms_mat.transparent_two_sided
                    nwo.face_transparent_ui = jms_mat.transparent_one_sided or jms_mat.transparent_two_sided
                    nwo.render_only_ui = jms_mat.render_only
                    nwo.sphere_collision_only_ui = jms_mat.sphere_collision_only
                    nwo.ladder_ui = jms_mat.ladder
                    nwo.breakable_ui = jms_mat.breakable
                    nwo.portal_ai_deafening_ui = jms_mat.ai_deafening
                    nwo.no_shadow_ui = jms_mat.no_shadow
                    nwo.precise_position_ui = jms_mat.precise
                    if jms_mat.portal_one_way:
                        nwo.portal_type_ui = '_connected_geometry_portal_type_one_way'
                    nwo.portal_is_door_ui = jms_mat.portal_door
                    if jms_mat.portal_vis_blocker:
                        nwo.portal_type_ui = '_connected_geometry_portal_type_no_way'
                    nwo.no_lightmap_ui = jms_mat.ignored_by_lightmaps
                    nwo.portal_blocks_sounds_ui = jms_mat.blocks_sound
                    nwo.decal_offset_ui = jms_mat.decal_offset
                    nwo.slip_surface_ui = jms_mat.slip_surface
                    nwo.face_global_material_ui = jms_mat.global_material
                    # Lightmap
                    if jms_mat.lightmap_resolution_scale:
                        nwo.lightmap_resolution_scale_active = True
                        nwo.lightmap_resolution_scale_ui = jms_mat.lightmap_resolution_scale
                    if jms_mat.lightmap_additive_transparency:
                        nwo.lightmap_additive_transparency_active = True
                        nwo.lightmap_additive_transparency_ui = jms_mat.lightmap_additive_transparency
                    if jms_mat.lightmap_translucency_tint_color:
                        nwo.lightmap_translucency_tint_color_active = True
                        nwo.lightmap_translucency_tint_color_ui = jms_mat.lightmap_translucency_tint_color
                    # Emissive
                    if jms_mat.emissive_power:
                        nwo.emissive_active = True
                        nwo.material_lighting_emissive_power_ui = jms_mat.emissive_power
                        nwo.material_lighting_emissive_color_ui = jms_mat.emissive_color
                        nwo.material_lighting_emissive_quality_ui = jms_mat.emissive_quality
                        nwo.material_lighting_emissive_per_unit_ui = jms_mat.emissive_per_unit
                        nwo.material_lighting_use_shader_gel_ui = jms_mat.emissive_shader_gel
                        nwo.material_lighting_emissive_focus_ui = jms_mat.emissive_focus
                        nwo.material_lighting_attenuation_falloff_ui = jms_mat.emissive_attenuation_falloff
                        nwo.material_lighting_attenuation_cutoff_ui = jms_mat.emissive_attenuation_cutoff
                    
            elif len(ob.data.materials) > 1:
                bm = bmesh.new()
                bm.from_mesh(ob.data)
                layers = {}
                face_props = ob.data.nwo.face_props
                for idx, material in enumerate(ob.data.materials):
                    layers[idx] = []
                    jms_mats = [mat for mat in jms_materials if mat.name == material.name]
                    if jms_mats:
                        jms_mat = jms_mats[0]
                        if jms_mat.two_sided or jms_mat.transparent_two_sided:
                            l_name = 'two_sided'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Two Sided", "face_two_sided_override")))
                                
                        if jms_mat.transparent_one_sided or jms_mat.transparent_two_sided:
                            l_name = 'transparent'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Transparent", "face_transparent_override")))
                                
                        if jms_mat.render_only:
                            l_name = 'render_only'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Render Only", "render_only_override")))
                                
                        if jms_mat.collision_only:
                            l_name = 'collision_only'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Collision Only", "collision_only_override")))
                                
                        if jms_mat.sphere_collision_only:
                            l_name = 'sphere_collision_only'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Sphere Collision Only", "sphere_collision_only_override")))
                                
                        if jms_mat.ladder:
                            l_name = 'ladder'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Ladder", "ladder_override")))
                                
                        if jms_mat.breakable:
                            l_name = 'breakable'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Breakable", "breakable_override")))
                                
                        if jms_mat.no_shadow:
                            l_name = 'no_shadow'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "No Shadow", "no_shadow_override")))
                                
                        if jms_mat.precise:
                            l_name = 'uncompressed'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Uncompressed", "precise_position_override")))
                                
                        if jms_mat.ignored_by_lightmaps:
                            l_name = 'no_lightmap'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "No Lightmap", "no_lightmap_override")))
                                
                        if jms_mat.decal_offset:
                            l_name = 'decal_offset'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Decal Offset", "decal_offset_override")))
                                
                        if jms_mat.slip_surface:
                            l_name = 'slip_surface'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Slip Surface", "slip_surface_override")))
                        
                        # Lightmap
                        if jms_mat.lightmap_resolution_scale:
                            l_name = 'lightmap_resolution_scale'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Lightmap Resolution Scale", "lightmap_resolution_scale_override", {"lightmap_resolution_scale_ui": jms_mat.lightmap_resolution_scale})))
                        
                        if jms_mat.lightmap_translucency_tint_color:
                            l_name = 'lightmap_translucency_tint_color'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Lightmap Translucency Tint Color", "lightmap_translucency_tint_color_override", {"lightmap_translucency_tint_color_ui": jms_mat.lightmap_translucency_tint_color})))
                        
                        if jms_mat.lightmap_additive_transparency:
                            l_name = 'lightmap_additive_transparency'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Lightmap Additive Transparency", "lightmap_additive_transparency_override", {"lightmap_additive_transparency_ui": jms_mat.lightmap_additive_transparency})))
                        
                        # Emissive
                        if jms_mat.emissive_power:
                            l_name = 'emissive'
                            if bm.faces.layers.int.get(l_name):
                                layers[idx].append(bm.faces.layers.int.get(l_name))
                            else:
                                emissive_props_dict = {
                                    "material_lighting_emissive_power_ui": jms_mat.emissive_power,
                                    "material_lighting_emissive_color_ui": jms_mat.emissive_color,
                                    "material_lighting_emissive_quality_ui": jms_mat.emissive_quality,
                                    "material_lighting_emissive_per_unit_ui": jms_mat.emissive_per_unit,
                                    "material_lighting_use_shader_gel_ui": jms_mat.emissive_shader_gel,
                                    "material_lighting_emissive_focus_ui": jms_mat.emissive_focus,
                                    "material_lighting_attenuation_falloff_ui": jms_mat.emissive_attenuation_falloff,
                                    "material_lighting_attenuation_cutoff_ui": jms_mat.emissive_attenuation_cutoff,
                                }
                                layers[idx].append(bm.faces.layers.int.new(self.new_face_prop(ob.data, l_name, "Emissive", "emissive_override", emissive_props_dict)))
                        
                        
                for face in bm.faces:
                    for idx, face_layer_list in layers.items():
                        if face.material_index == idx:
                            for face_layer in face_layer_list:
                                face[face_layer] = 1
                                
                for layer in face_props:
                    layer.face_count = layer_face_count(bm, bm.faces.layers.int.get(layer.layer_name))
                                
                bm.to_mesh(ob.data)
        
        return objects_to_setup
    
    def matching_material_properties(self, materials: list[bpy.types.Material], scoped_jms_materials: list[JMSMaterialSlot]):
        '''Checks if all jms materials have matching properties'''
        if len(materials) <= 1:
            return True
        material_names = [m.name for m in materials]
        jms_materials = [jms_mat for jms_mat in scoped_jms_materials if jms_mat.name in material_names]
        first_mat = jms_materials[0]
        for mat in jms_materials[1:]:
            if mat != first_mat:
                return False
            
        return True
        
    def setup_collision_materials(self, ob: bpy.types.Object, mesh_type_legacy: str):
        if not ob.material_slots:
            return
        if mesh_type_legacy == 'physics' or len(ob.material_slots) == 1:
            if ob.material_slots[0].material:
                ob.data.nwo.face_global_material_ui = ob.material_slots[0].material.name
                
        elif mesh_type_legacy == 'collision':
            face_props = ob.data.nwo.face_props
            for slot in ob.material_slots:
                if not slot.material:
                    continue
                layer = face_props.add()
                layer.name = slot.material.name
                layer.layer_name = 'face_global_material'
                layer.face_global_material_ui = slot.material.name
                layer.face_global_material_override = True
                material_index = slot.slot_index
                layer.layer_name, layer.face_count = self.add_collision_face_layer(ob.data, material_index, layer.layer_name)
                layer.layer_color = random_color()
                
    def add_collision_face_layer(self, mesh, material_index, prefix):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        face_layer = bm.faces.layers.int.new(f"{prefix}_{str(uuid4())}")
        for face in bm.faces:
            if face.material_index == material_index:
                face[face_layer] = 1
        
        bm.to_mesh(mesh)
                
        return face_layer.name, layer_face_count(bm, face_layer)
        
    def get_mesh_type(self, ob: bpy.types.Object, is_model):
        if ob.nwo.mesh_type == 'skip':
            return ''
        name = ob.name
        if name.startswith('@'):
            return 'collision'
        elif name.startswith('$'):
            return 'physics'
        elif name.startswith('~') and not is_model:
            return 'water_physics'
        elif name.startswith('%'):
            if is_model:
                return 'io'
            elif ob.nwo.mesh_type and ob.nwo.mesh_type != 'default':
                return ob.nwo.mesh_type
            else:
                return 'instance'
            
        elif ob.nwo.mesh_type:
            return ob.nwo.mesh_type
        
        return 'default'
    
    def mesh_and_material(self, mesh_type, is_model):
        material = ""
        match mesh_type:
            case "collision":
                mesh_type = "_connected_geometry_mesh_type_collision"
                material = "Collision"
            case "physics":
                mesh_type = "_connected_geometry_mesh_type_physics"
                material = "Physics"
            case "default":
                if is_model:
                    mesh_type = "_connected_geometry_mesh_type_default"
                else:
                    mesh_type = "_connected_geometry_mesh_type_structure"
            case "io":
                mesh_type = "_connected_geometry_mesh_type_object_instance"
            case "instance":
                mesh_type = "_connected_geometry_mesh_type_default"
            case "seam":
                mesh_type = "_connected_geometry_mesh_type_seam"
                material = "Seam"
            case "portal":
                mesh_type = "_connected_geometry_mesh_type_portal"
                material = "Portal"
            case "lightmap_only":
                mesh_type = "_connected_geometry_mesh_type_lightmap_only"
                material = "Portal"
            case "water_surface":
                mesh_type = "_connected_geometry_mesh_type_water_surface"
            case "rain_sheet":
                mesh_type = "_connected_geometry_mesh_type_poop_vertical_rain_sheet"
                material = "RainSheet"
            case "fog":
                mesh_type = "_connected_geometry_mesh_type_planar_fog_volume"
                material = "Fog"
            case "soft_ceiling":
                mesh_type = "_connected_geometry_mesh_type_soft_ceiling"
                material = "SoftCeiling"
            case "soft_kill":
                mesh_type = "_connected_geometry_mesh_type_soft_kill"
                material = "SoftKill"
            case "slip_surface":
                mesh_type = "_connected_geometry_mesh_type_slip_surface"
                material = "SlipSurface"
            case "water_physics":
                mesh_type = "_connected_geometry_mesh_type_water_physics_volume"
                material = "WaterVolume"
            case "invisible_wall":
                mesh_type = "_connected_geometry_mesh_type_invisible_wall"
                material = "WaterVolume"
            case "streaming":
                mesh_type = "_connected_geometry_mesh_type_streaming"
                material = "StreamingVolume"
            case "lightmap":
                if is_corinth(self.context):
                    mesh_type = "_connected_geometry_mesh_type_lightmap_exclude"
                    material = "LightmapExcludeVolume"

            case "cookie_cutter":
                mesh_type = "_connected_geometry_mesh_type_cookie_cutter"
                material = "CookieCutter"

            case "rain_blocker":
                mesh_type = "_connected_geometry_mesh_type_poop_rain_blocker"
                material = "RainBlocker"
            case "decorator":
                mesh_type = "_connected_geometry_mesh_type_decorator"
                
        return mesh_type, material
            

# Legacy Animation importer
######################################################################
    def import_jma_files(self, jma_files, legacy_fix_rotations):
        """Imports all legacy animation files supplied"""
        if not jma_files:
            return []
        self.animations = []
        self.objects = []
        scene_nwo = self.context.scene.nwo
        if scene_nwo.main_armature:
            arm = scene_nwo.main_armature
        else:
            arm = get_rig(self.context)
            if not arm:
                arm_data = bpy.data.armatures.new('Armature')
                arm = bpy.data.objects.new('Armature', arm_data)
                self.context.scene.collection.objects.link(arm)
            
        arm.hide_set(False)
        arm.hide_select = False
        set_active_object(arm)
        muted_armature_deforms = mute_armature_mods()
        if jma_files:
            print("Importing Animations")
            print(
                "-----------------------------------------------------------------------\n"
            )
            for path in jma_files:
                self.import_legacy_animation(path, legacy_fix_rotations)
            
            unmute_armature_mods(muted_armature_deforms)
            
            return self.animations
            
        
    def import_legacy_animation(self, path, legacy_fix_rotations):
        existing_animations = bpy.data.actions[:]
        print(f"--- {dot_partition(os.path.basename(path))}")
        with MutePrints():
            bpy.ops.import_scene.jma(filepath=path, fix_rotations=legacy_fix_rotations)
        if bpy.data.actions:
            new_animations = [a for a in bpy.data.actions if a not in existing_animations]
            if not new_animations:
                return print_warning(f"Failed to import animation: {path}")
                
            anim = new_animations[0]
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
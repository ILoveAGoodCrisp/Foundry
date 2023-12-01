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

# main_script.py

import importlib
amf_module = importlib.import_module("Blender AMF2")

import os
import bpy
from mathutils import Vector
from io_scene_halo.file_jma.import_jma import load_file as import_jma

class NWO_Import(bpy.types.Operator):
    bl_label = "Importer"
    bl_idname = "nwo.import"
    bl_description = "Imports a variety of filetypes and sets them up for Foundry. Currently supports: AMF, JMA"
    
    @classmethod
    def poll(cls, context):
        return amf_addon_installed()
    
    filter_glob: bpy.props.StringProperty(
        default="*.amf",
        options={"HIDDEN"},
    )

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={"HIDDEN", "SKIP_SAVE"},
    )
    
    directory: bpy.props.StringProperty(
        name='Directory',
        subtype='DIR_PATH'
    )
    
    def execute(self, context):
        filepaths = [self.directory + f.name for f in self.files]
        importer = NWOImporter(context, self.report, filepaths)
        amf_files = importer.sorted_filepaths["amf"]
        imported_amf_objects = importer.import_amf_files(amf_files)
        if imported_amf_objects:
            [ob.select_set(True) for ob in imported_amf_objects]
        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class NWOImporter():
    def __init__(self, context, report, filepaths):
        self.filepaths = filepaths
        self.context = context
        self.report = report
        self.mesh_objects = []
        self.marker_objects = []
        self.sorted_filepaths = self.group_filetypes()
    
    def group_filetypes(self):
        filetype_dict = {"amf": [], "jma": []}
        for path in self.filepaths:
            if path.lower().endswith('.amf'):
                filetype_dict["amf"].append(path)
                
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
    
    # Legacy Animation Importer
    
    # AMF Importer
    
    def import_amf_files(self, amf_files):
        """Imports all amf files supplied"""
        for path in amf_files:
            self.import_amf_file(path)
            
        return self.mesh_objects.extend(self.marker_objects)

    def import_amf_file(self, path):
        # get all objects that exist prior to import
        pre_import_objects = bpy.data.objects[:]
        options = amf_module.ImportOptions()
        options.PREFIX_MARKER = ''
        options.MODE_SCALE = 'MAX'
        file_name = dot_partition(os.path.basename(path))
        print(f"Importing AMF: {file_name}")
        with MutePrints():
            amf_module.main(self.context, path, options)
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
        self.poops = []
        print("Setting object properties")
        for ob in objects:
            unlink(ob)
            new_coll.objects.link(ob)
            if ob.type == 'MESH':
                self.setup_amf_mesh(ob, is_model)
            elif ob.type == 'EMPTY':
                self.setup_amf_marker(ob, is_model)
                
        if self.poops:
            print("Fixing scale")
            stomp_scale_multi_user(self.poops)
            enforce_uniformity(self.poops)
    
    def setup_amf_mesh(self, ob, is_model):
        name = dot_partition(ob.name)
        nwo = ob.nwo
        if is_model:
            permutation, region = name.split(':')
            self.set_region(ob, region)
            self.set_permutation(ob, permutation)
        else:
            if name.startswith('Clusters'):
                nwo.mesh_type_ui = '_connected_geometry_mesh_type_structure'
            else:
                self.poops.append(ob)
                
        self.mesh_objects.append(ob)
        
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
            
            
            
        


# Legacy Animation importer
######################################################################

pose_hints = ['aim', 'look', 'acc', 'steer']

def import_legacy_animations(context, filepaths, report):
    """Imports all legacy animation files supplied"""
    for path in filepaths:
        import_legacy_animation(context, path, report)
        
    
def import_legacy_animation(context, filepath, report):
    import_jma(context, filepath, 'halo3', False, False, "", "", report)
    filename = os.path.basename(filepath)
    anim_name, extension = filename.split('.')
    anim = bpy.data.actions.get(anim_name[:64], 0)
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
 

    

from io_scene_foundry.utils.nwo_utils import MutePrints, amf_addon_installed, any_partition, disable_prints, dot_partition, enable_prints, enforce_uniformity, stomp_scale_multi_user, unlink
    

# AMF Importer
######################################################################


         

def amf_assign(context, report):
    # Loop through scene objects and apply appropriate perm / region names
    loop_count = 0
    for ob in context.view_layer.objects:
        true_name = dot_partition(ob.name)
        if not true_name.startswith(("+", ":")) and ":" in true_name:
            if true_name.rpartition(":")[0] != "":
                ob.nwo.region_name = true_name.rpartition(":")[0]
            if true_name.rpartition(":")[2] != "":
                ob.nwo.permutation_name = true_name.rpartition(":")[2]
            loop_count += 1

    report(
        {"INFO"},
        f"Updated regions & permutations for {loop_count} AMF objects",
    )

    return {"FINISHED"}

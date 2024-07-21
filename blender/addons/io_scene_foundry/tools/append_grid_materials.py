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

from pathlib import Path
import zipfile
import bpy
import os

from mathutils import Vector

from io_scene_foundry.utils import nwo_utils

script_file = os.path.realpath(__file__)
addon_dir = os.path.dirname(os.path.dirname(script_file))
resources_zip = Path(addon_dir, "resources.zip")

class NWO_OT_AppendGridMaterials(bpy.types.Operator):
    bl_idname = "nwo.append_grid_materials"
    bl_label = "Append Grid Materials"
    bl_description = "Adds a collection of grid materials to the blend file"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return nwo_utils.get_project()

    def execute(self, context):
        self.append_grid_materials()
        return {"FINISHED"}
    
def append_grid_materials():
    filepaths = []
    if not bpy.data.materials.get("grid_checkered"): filepaths.append(os.path.join(addon_dir, "images", 'grid_checkered.png')) 
    if not bpy.data.materials.get("grid_checkered_cross"): filepaths.append(os.path.join(addon_dir, "images", 'grid_checkered_cross.png')) 
    if not bpy.data.materials.get("grid_dark_cross"): filepaths.append(os.path.join(addon_dir, "images", 'grid_dark_cross.png')) 
    if not bpy.data.materials.get("grid_dark_diagonal"): filepaths.append(os.path.join(addon_dir, "images", 'grid_dark_diagonal.png')) 
    if not bpy.data.materials.get("grid_dark_square"): filepaths.append(os.path.join(addon_dir, "images", 'grid_dark_square.png')) 
    if not bpy.data.materials.get("grid_orange_cross"): filepaths.append(os.path.join(addon_dir, "images", 'grid_orange_cross.png')) 
    if not bpy.data.materials.get("grid_orange_diagonal"): filepaths.append(os.path.join(addon_dir, "images", 'grid_orange_diagonal.png')) 
    if not bpy.data.materials.get("grid_orange_square"): filepaths.append(os.path.join(addon_dir, "images", 'grid_orange_square.png')) 
    
    for filepath in filepaths:
        if os.path.exists(filepath):
            setup_grid_material(filepath)
        else:
            print("Images not found")

def setup_grid_material(filepath):
    material_name = Path(filepath).with_suffix("").name
    material = bpy.data.materials.new(material_name)
    material.use_nodes = True
    material.use_fake_user = True
    tree = material.node_tree
    nodes = tree.nodes
    nodes.clear()
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = Vector((300, 0))
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tree.links.new(input=output.inputs[0], output=bsdf.outputs[0])
    tex_node = nodes.new(type="ShaderNodeTexImage")
    tex_node.location = Vector((-300, 0))
    image = bpy.data.images.load(filepath=filepath, check_existing=True)
    tex_node.image = image
    tree.links.new(input=bsdf.inputs[0], output=tex_node.outputs[0])
    
    if nwo_utils.is_corinth():
        shader_path = str(Path("shaders", "foundry", "materials", material_name + ".material"))
    else:
        shader_path = str(Path("shaders", "foundry", "shaders", material_name + ".shader"))
        
    if not Path(nwo_utils.get_tags_path(), shader_path).exists():
        copy_grid_shader(material_name)
        
    material.nwo.shader_path = shader_path
    
def copy_grid_shader(name):
    if nwo_utils.is_corinth():
        source_shader_path = Path(addon_dir, "resources", "textures", "materials", name + ".material")
        dest_shader_path = Path(nwo_utils.get_tags_path(), "shaders", "foundry", "materials", name + ".material")
    else:
        source_shader_path = Path(addon_dir, "resources", "textures", "shaders", name + ".shader")
        dest_shader_path = Path(nwo_utils.get_tags_path(), "shaders", "foundry", "shaders", name + ".shader")
        
    print(source_shader_path)
        
    os.makedirs(dest_shader_path.parent, exist_ok=True)
        
    if source_shader_path.exists():
        nwo_utils.copy_file(source_shader_path, dest_shader_path)
    elif resources_zip.exists():
        os.chdir(addon_dir)
        if nwo_utils.is_corinth():
            file_relative = f"textures/materials/{name}.material"
        else:
            file_relative = f"textures/shaders/{name}.shader"
        with zipfile.ZipFile(resources_zip, "r") as zip:
            filepath = zip.extract(file_relative)
            nwo_utils.copy_file(source_shader_path, dest_shader_path)

        os.remove(filepath)
        os.rmdir(os.path.dirname(filepath))
    else:
        print("Resources not found")
        
    source_bitmap_path = Path(addon_dir, "resources", "textures", "bitmaps", name + ".bitmap")
    dest_bitmap_path = Path(nwo_utils.get_tags_path(), "shaders", "foundry", "bitmaps", name + ".bitmap")
    os.makedirs(dest_bitmap_path.parent, exist_ok=True)
    
    if source_bitmap_path.exists():
        nwo_utils.copy_file(source_bitmap_path, dest_bitmap_path)
    elif resources_zip.exists():
        os.chdir(addon_dir)
        file_relative = f"textures/bitmaps/{name}.bitmap"
        with zipfile.ZipFile(resources_zip, "r") as zip:
            filepath = zip.extract(file_relative)
            nwo_utils.copy_file(source_bitmap_path, dest_bitmap_path)
            
        os.remove(filepath)
        os.rmdir(os.path.dirname(filepath))
    else:
        print("Resources not found")

    
    
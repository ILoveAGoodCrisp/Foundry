

from pathlib import Path
import zipfile
import bpy
import os

from mathutils import Vector

from .. import utils

script_file = os.path.realpath(__file__)
addon_dir = os.path.dirname(os.path.dirname(script_file))
resources_zip = Path(addon_dir, "resources.zip")

class NWO_OT_AppendGridMaterials(bpy.types.Operator):
    bl_idname = "nwo.append_grid_materials"
    bl_label = "Append Grid Materials"
    bl_description = "Adds a collection of grid materials to the blend file"
    bl_options = {"UNDO"}

    def execute(self, context):
        append_grid_materials()
        self.report({'INFO'}, "Grid Materials Added")
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
            print(f"{filepath} not found")

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
    image.nwo.filepath = str(Path(r"shaders\foundry\bitmaps", Path(filepath).name))
    tex_node.image = image
    tree.links.new(input=bsdf.inputs[0], output=tex_node.outputs[0])
    
    if utils.is_corinth():
        shader_path = str(Path("shaders", "foundry", "shaders", material_name + ".material"))
    else:
        shader_path = str(Path("shaders", "foundry", "shaders", material_name + ".shader"))
        
    if not Path(utils.get_tags_path(), shader_path).exists():
        copy_grid_shader(material_name)
        
    material.nwo.shader_path = shader_path
    
def copy_grid_shader(name):
    if utils.is_corinth():
        source_shader_path = Path(addon_dir, "resources", "textures", "materials", name + ".material")
        dest_shader_path = Path(utils.get_tags_path(), "shaders", "foundry", "shaders", name + ".material")
    else:
        source_shader_path = Path(addon_dir, "resources", "textures", "shaders", name + ".shader")
        dest_shader_path = Path(utils.get_tags_path(), "shaders", "foundry", "shaders", name + ".shader")
        
    print(source_shader_path)
        
    os.makedirs(dest_shader_path.parent, exist_ok=True)
        
    if source_shader_path.exists():
        utils.copy_file(source_shader_path, dest_shader_path)
    elif resources_zip.exists():
        os.chdir(addon_dir)
        if utils.is_corinth():
            file_relative = f"textures/shaders/{name}.material"
        else:
            file_relative = f"textures/shaders/{name}.shader"
        with zipfile.ZipFile(resources_zip, "r") as zip:
            filepath = zip.extract(file_relative)
            utils.copy_file(filepath, dest_shader_path)

        os.remove(filepath)
        os.rmdir(os.path.dirname(filepath))
    else:
        print("Resources not found")
        
    source_bitmap_path = Path(addon_dir, "resources", "textures", "bitmaps", name + ".bitmap")
    dest_bitmap_path = Path(utils.get_tags_path(), "shaders", "foundry", "bitmaps", name + ".bitmap")
    os.makedirs(dest_bitmap_path.parent, exist_ok=True)
    
    if source_bitmap_path.exists():
        utils.copy_file(source_bitmap_path, dest_bitmap_path)
    elif resources_zip.exists():
        os.chdir(addon_dir)
        file_relative = f"textures/bitmaps/{name}.bitmap"
        with zipfile.ZipFile(resources_zip, "r") as zip:
            filepath = zip.extract(file_relative)
            utils.copy_file(filepath, dest_bitmap_path)
            
        os.remove(filepath)
        os.rmdir(os.path.dirname(filepath))
    else:
        print("Resources not found")

    
    
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
import bpy
import os
from io_scene_foundry.managed_blam.shaders import ManagedBlamNewShader
from io_scene_foundry.utils.nwo_utils import (
    dot_partition,
    get_asset_path,
    get_asset_path_full,
    get_tags_path,
    get_valid_shader_name,
    not_bungie_game,
    os_sep_partition,
    protected_material_name,
    valid_nwo_asset,
)

global_material_shaders = []

def is_tag_candidate(shader_path, update_existing, mat):
    if shader_path == "" or shader_path.startswith(get_asset_path()):
        if not protected_material_name(mat.name):
            shader_name = get_valid_shader_name(mat.name)
            if shader_name != "":
                full_path = os.path.join(
                    get_asset_path_full(True), "shaders", shader_name
                )
                return update_existing or not os.path.exists(full_path)

    return False


def build_shaders(context, material_selection, report, shader_info, update_existing=False):
    # get blender materials to be added
    shader_materials = []
    material_names = []
    if material_selection == "all":
        # get a list of all scene materials to be made into tags
        for mat in bpy.data.materials:
            if mat.name != "":
                material_names.append(mat.name)
                shader_path = mat.nwo.shader_path
                if is_tag_candidate(shader_path, update_existing, mat):
                    shader_materials.append(mat)

    else:
        active_material = context.active_object.active_material
        if active_material.name != "":
            shader_path = active_material.nwo.shader_path
            if is_tag_candidate(shader_path, update_existing, active_material):
                shader_materials.append(active_material)

    # Pass to ManagedBlam Operator
    for mat in shader_materials:
        # need to check for duplicates
        material_names = []
        mat_name = get_valid_shader_name(mat.name)
        if mat_name not in material_names:
            material_names.append(mat_name)
            print(f"Bulding shader for {mat.name}")
            
            if not_bungie_game(context):
                tag = ManagedBlamNewShader(mat.name, False, context.object.active_material.nwo.material_shader)
                mat.nwo.shader_path = tag.path
                report({'INFO'}, f"Created Material Tag for {mat.name}")
            else:
                tag = ManagedBlamNewShader(mat.name, True, ".shader")
                mat.nwo.shader_path = tag.path
                report({'INFO'}, f"Created Shader Tag for {mat.name}")

    return {"FINISHED"}

class NWO_ListMaterialShaders(bpy.types.Operator):
    bl_idname = "nwo.get_material_shaders"
    bl_label = "Get Material Shaders"
    bl_options = {"UNDO"}
    bl_property = "shader_info"

    @classmethod
    def poll(cls, context):
        return valid_nwo_asset(context) and context.object and context.object.active_material and not protected_material_name(context.object.active_material.name) and not_bungie_game(context)
    
    def shader_info_items(self, context):
        global global_material_shaders
        if global_material_shaders:
            return global_material_shaders
        items = []
        tags_dir = get_tags_path()
        shaders_dir = os.path.join(tags_dir + "shaders", "material_shaders")
        material_shaders = []
        # walk shaders dir and collect
        for root, dirs, files in os.walk(shaders_dir):
            for file in files:
                if file.endswith(".material_shader"):
                    material_shaders.append(os.path.join(root, file).replace(tags_dir, ""))
        
        # Order so we get shaders in the materials folder first
        ordered_shaders = sorted(material_shaders, key=lambda s: (0, s) if s.startswith(r"shaders\material_shaders\materials") else (1, s))

        for ms in ordered_shaders:
            items.append((ms, dot_partition(os_sep_partition(ms, True)), ""))

        return items
    
    shader_info : bpy.props.EnumProperty(
        name="Type",
        items=shader_info_items,
    )

    def execute(self, context):
        context.object.active_material.nwo.material_shader = self.shader_info
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}

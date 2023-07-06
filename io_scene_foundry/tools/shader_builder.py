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
from io_scene_foundry.managed_blam import ManagedBlam, ManagedBlamNewShader
from io_scene_foundry.utils.nwo_utils import (
    get_asset_path,
    get_asset_path_full,
    get_valid_shader_name,
    not_bungie_game,
    protected_material_name,
)


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


def build_shaders(context, material_selection, report, update_existing=False):
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
            
            if not_bungie_game():
                tag = ManagedBlamNewShader(mat.name, False)
                mat.nwo.shader_path = tag.path
                report({'INFO'}, f"Created Material Tag for {mat.name}")
            else:
                tag = ManagedBlamNewShader(mat.name, True)
                mat.nwo.shader_path = tag.path
                report({'INFO'}, f"Created Shader Tag for {mat.name}")

    return {"FINISHED"}

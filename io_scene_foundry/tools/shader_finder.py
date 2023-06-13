# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2022 Crisp
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
from io_scene_foundry.utils.nwo_utils import (
    dot_partition,
    get_tags_path,
    shader_exts,
)

def scan_tree(shaders_dir, shaders):
    for root, dirs, files in os.walk(shaders_dir):
        for file in files:
            if file.endswith(shader_exts):
                shaders.add(os.path.join(root, file))

    return shaders


def find_shaders(materials, report=None, shaders_dir="", overwrite=False):
    shaders = set()
    update_count = 0
    tags_path = get_tags_path()

    if not shaders_dir:
        # clean shaders directory path
        shaders_dir = (
            shaders_dir.replace('"', "").strip("\\").replace(tags_path, "")
        )

    # verify that the path created actually exists
    shaders_dir = os.path.join(tags_path, shaders_dir)
    shaders = set()
    if os.path.isdir(shaders_dir):
        scan_tree(shaders_dir, shaders)
        # loop through mats, find a matching shader, and apply it if the shader path field is empty
        for mat in materials:
            shader_path = find_shader_match(mat, shaders, tags_path)
            if shader_path:
                if overwrite or not mat.nwo.shader_path:
                    mat.nwo.shader_path = shader_path
                    update_count += 1

    if report is not None:
        report({"INFO"}, "Updated " + str(update_count) + " shader paths")
        
    return {"FINISHED"}


def find_shader_match(mat, shaders, tags_path):
    material_name = mat.name
    material_parts = material_name.split(" ")
    # clean material name
    if len(material_parts) > 1:
        material_name = material_parts[1]
    else:
        material_name = material_parts[0]
    # ignore if duplicate name
    dot_partition(material_name)
    # ignore material suffixes
    material_name = material_name.rstrip("%#?!@*$^-&=.;)><|~({]}['0")
    # dot partition again in case a pesky dot remains
    dot_partition(material_name)
    for s in shaders:
        # get just the shader name
        shader_name = s.rpartition("\\")[2]
        shader_name = shader_name.rpartition(".")[0]
        if material_name.lower() == shader_name.lower():
            return s.replace(tags_path, "")

    return ""

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
from io_scene_foundry.utils.nwo_utils import (
    dot_partition,
    get_tags_path,
    is_corinth,
    shader_exts,
)


def scan_tree(shaders_dir, shaders):
    for root, dirs, files in os.walk(shaders_dir):
        for file in files:
            if file.endswith(shader_exts):
                shaders.add(os.path.join(root, file))

    return shaders


def find_shaders(materials_all, h4, report=None, shaders_dir="", overwrite=False, set_non_export=False):
    materials = [
        mat for mat in materials_all if mat.nwo.rendered and not mat.grease_pencil
    ]
    shaders = set()
    update_count = 0
    no_path_materials = []
    tags_path = get_tags_path()

    if not shaders_dir:
        # clean shaders directory path
        shaders_dir = shaders_dir.replace('"', "").strip("\\").replace(tags_path, "")

    # verify that the path created actually exists
    shaders_dir = os.path.join(tags_path, shaders_dir)
    shaders = set()
    if os.path.isdir(shaders_dir):
        scan_tree(shaders_dir, shaders)
        # loop through mats, find a matching shader, and apply it if the shader path field is empty
        for mat in materials:
            no_path = not bool(mat.nwo.shader_path)
            if no_path or overwrite:
                shader_path = find_shader_match(mat, shaders)
                if shader_path:
                    mat.nwo.shader_path = shader_path
                    update_count += 1
                elif no_path:
                    no_path_materials.append(mat.name)
                    if report is None:
                        if h4:
                            mat.nwo.shader_path = r"shaders\missing.material"
                        else:
                            mat.nwo.shader_path = r"shaders\invalid.shader"
                    elif set_non_export:
                        mat.nwo.rendered = False

    if report is not None:
        if no_path_materials and not set_non_export:
            report({"WARNING"}, "Missing material paths:")
            for m in no_path_materials:
                report({"ERROR"}, m)
            if is_corinth():
                report(
                    {"WARNING"},
                    "These materials should either be given paths to Halo material tags, or specified as a Blender only material (by using the checkbox in Halo Material Paths)",
                )
            else:
                report(
                    {"WARNING"},
                    "These materials should either be given paths to Halo shader tags, or specified as a Blender only material (by using the checkbox in Halo Shader Paths)",
                )
            if update_count:
                report(
                    {"WARNING"},
                    f"Updated {update_count} material paths, but couldn't find paths for {len(no_path_materials)} materials. Click here for details",
                )
            else:
                report(
                    {"WARNING"},
                    f"Couldn't find paths for {len(no_path_materials)} materials. Click here for details",
                )
        elif no_path_materials and set_non_export:
            report(
                {"INFO"},
                f"Updated {update_count} material paths, and disabled export property for {len(no_path_materials)} materials",
            )
                
        else:
            report({"INFO"}, f"Updated {update_count} material paths")

        return {"FINISHED"}

    return no_path_materials


def find_shader_match(mat, shaders):
    """Tries to find a shader match. Includes logic for filtering out legacy material name prefixes/suffixes"""
    material_lower = mat.name.lower()
    material_short = dot_partition(material_lower)
    material_parts = material_short.split(" ")
    # clean material name
    if len(material_parts) > 1:
        material_name = material_parts[1]
    else:
        material_name = material_parts[0]
    # ignore material suffixes
    material_name = material_name.rstrip("%#?!@*$^-&=.;)><|~({]}['0")
    for s in shaders:
        # get just the shader name
        shader_name = dot_partition(s.rpartition("\\")[2]).lower()
        # changing this to check 3 versions, to ensure the correct material is picked
        if shader_name in (material_lower, material_short, material_name):
            return s

    return ""

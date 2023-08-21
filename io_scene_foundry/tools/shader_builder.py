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
    get_tags_path,
    get_valid_shader_name,
    not_bungie_game,
    os_sep_partition,
    protected_material_name,
)

global_material_shaders = []

def get_shader_name(mat):
    if not protected_material_name(mat.name):
        shader_name = get_valid_shader_name(mat.name)
        if shader_name != "":
            return shader_name

    return None


def build_shader(material, corinth, folder="", report=None):
    if not get_shader_name(material):
        return {"FINISHED"}
    nwo = material.nwo
    if corinth:
        tag = ManagedBlamNewShader(material.name, nwo.material_shader, nwo.uses_blender_nodes, nwo.shader_path, folder if folder else nwo.shader_dir)
        nwo.shader_path = tag.path
        if report is not None:
            report({'INFO'}, f"Created Material Tag for {material.name}")
    else:
        tag = ManagedBlamNewShader(material.name, nwo.shader_type, nwo.uses_blender_nodes, nwo.shader_path, folder if folder else nwo.shader_dir)
        nwo.shader_path = tag.path
        if report is not None:
            report({'INFO'}, f"Created Shader Tag for {material.name}")

    return {"FINISHED"}

class NWO_ListMaterialShaders(bpy.types.Operator):
    bl_idname = "nwo.get_material_shaders"
    bl_label = "Get Material Shaders"
    bl_options = {"UNDO"}
    bl_property = "shader_info"

    batch_panel : bpy.props.BoolProperty()

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and not_bungie_game(context)
    
    def shader_info_items(self, context):
        global global_material_shaders
        if global_material_shaders:
            return global_material_shaders
        items = []
        tags_dir = get_tags_path()
        shaders_dir = os.path.join(tags_dir + "shaders", "material_shaders")
        material_shaders = []
        # walk shaders dir and collect
        for root, _, files in os.walk(shaders_dir):
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
        if self.batch_panel:
            context.scene.nwo.default_material_shader = self.shader_info
        else:
            context.object.active_material.nwo.material_shader = self.shader_info
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.invoke_search_popup(self)
        return {"FINISHED"}

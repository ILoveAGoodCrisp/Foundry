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
import bpy
from io_scene_foundry.managed_blam.material import MaterialTag
from io_scene_foundry.managed_blam.shader import ShaderTag
from io_scene_foundry.utils import nwo_utils

class NWO_ShaderToNodes(bpy.types.Operator):
    bl_idname = "nwo.shader_to_nodes"
    bl_label = "Convert Shader to Blender Material Nodes"
    bl_description = "Builds a new node tree for the active material based on the referenced shader/material tag. Will import required bitmaps"
    bl_options = {"UNDO"}
    
    mat_name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        return not context.scene.nwo.export_in_progress

    def execute(self, context):
        mat = bpy.data.materials.get(self.mat_name, 0)
        if not mat:
            self.report({'WARNING'}, "Material not supplied")
            return {"CANCELLED"}
        shader_path = mat.nwo.shader_path
        full_path = nwo_utils.get_tags_path() + shader_path
        if not os.path.exists(full_path):
            self.report({'WARNING'}, "Tag not found")
            return {"CANCELLED"}
        if not shader_path.endswith(('.shader', '.material')):
            self.report({'WARNING'}, f'Tag Type [{nwo_utils.dot_partition(shader_path, True)}] is not supported')
            return {"CANCELLED"}
        tag_to_nodes(nwo_utils.is_corinth(context), mat, shader_path)
        return {"FINISHED"}

def tag_to_nodes(corinth: bool, mat: bpy.types.Material, tag_path: str):
    """Turns a shader/material tag into blender material nodes"""
    if corinth:
        with MaterialTag(path=tag_path) as material:
            material.to_nodes(mat)
    else:
        with ShaderTag(path=tag_path) as shader:
            shader.to_nodes(mat)
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
from bpy.types import PropertyGroup
from bpy.props import StringProperty, BoolProperty
from io_scene_foundry.utils.nwo_utils import clean_tag_path
from .templates import NWO_Op_Path


class NWO_ShaderPath(NWO_Op_Path):
    bl_idname = "nwo.shader_path"
    bl_description = "Set the path to a material / shader tag"

    def __init__(self):
        self.filter_glob = "*.material;*.shader*"
        self.tag_path_field = bpy.context.object.active_material.nwo.shader_path

    def execute(self, context):
        mat = context.object.active_material
        mat.nwo.shader_path = self.filepath
        return {"FINISHED"}


class NWO_MaterialPropertiesGroup(PropertyGroup):
    def update_shader(self, context):
        self["shader_path"] = clean_tag_path(self["shader_path"]).strip('"')

    shader_path: StringProperty(
        name="Shader Path",
        description="Define the path to a shader. This can either be a relative path, or if you have added your Editing Kit Path to add on preferences, the full path. Including the file extension will automatically update the shader type",
        update=update_shader,
    )

    rendered: BoolProperty(default=True)

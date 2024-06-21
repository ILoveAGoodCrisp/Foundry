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

import bpy
from io_scene_foundry.utils import nwo_utils
from pathlib import Path
import shutil

class NWO_OT_ShaderDuplicate(bpy.types.Operator):
    bl_idname = "nwo.shader_duplicate"
    bl_label = "Duplicate Tag"
    bl_description = "Copies the currently referenced shader/material tag to the specified directory (renaming if necessary) and updates the shader/material tag to this new tag"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and context.object.active_material.nwo.shader_path and nwo_utils.valid_nwo_asset() and Path(nwo_utils.get_tags_path(), nwo_utils.relative_path(context.object.active_material.nwo.shader_path)).exists()

    def execute(self, context):
        tags_dir = nwo_utils.get_tags_path()
        nwo = context.object.active_material.nwo
        file = Path(tags_dir, nwo_utils.relative_path(nwo.shader_path))
        asset_dir = nwo_utils.get_asset_path()
        if nwo_utils.is_corinth():
            dir = Path(tags_dir, asset_dir, "materials")
        else:
            dir = Path(tags_dir, asset_dir, "shaders")
        
        if not dir.exists():
            dir.mkdir(parents=True)
        
        shader_name = Path(nwo.shader_path).name
        destination = Path(dir, shader_name)
        suffix = 1
        while destination.exists():
            destination = Path(str(destination.with_suffix("")).rstrip("0123456789") + str(suffix)).with_suffix(destination.suffix)
            suffix += 1
        
        try:
            shutil.copyfile(file, destination)
        except:
            self.report({"WARNING"}, "Failed to copy tag")
            return {'CANCELLED'}
        
        nwo.shader_path = nwo_utils.relative_path(destination)
        self.report({"INFO"}, f"Tag successfully duplicated")
        return {"FINISHED"}

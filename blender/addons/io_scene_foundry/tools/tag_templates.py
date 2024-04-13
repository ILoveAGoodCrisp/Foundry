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
import bpy
import os
from io_scene_foundry.managed_blam.object import ObjectTag
from io_scene_foundry.utils import nwo_utils

class NWO_OT_LoadTemplate(bpy.types.Operator):
    bl_idname = "nwo.load_template"
    bl_label = "Load Template"
    bl_description = "Loads a template tag for the given tag type"
    bl_options = {"UNDO"}
    
    tag_type: bpy.props.StringProperty(options={'SKIP_SAVE', 'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return nwo_utils.valid_nwo_asset()

    def execute(self, context):
        if self.tag_type == "":
            return {'CANCELLED'}
        tag_ext = "." + self.tag_type
        template_tag_str = getattr(context.scene.nwo, f"template_{self.tag_type}")
        template_tag_path = Path(nwo_utils.relative_path(template_tag_str))
        template_full_path = Path(nwo_utils.get_tags_path(), template_tag_path)
        if not template_full_path.exists():
            self.report({'WARNING'}, "Template tag does not exist")
            return {'CANCELLED'}
        
        asset_dir, asset_name = nwo_utils.get_asset_info()
        full_asset_dir_path = Path(nwo_utils.get_tags_path(), asset_dir)
        if not full_asset_dir_path.exists():
            os.makedirs(full_asset_dir_path, exist_ok=True) 
        tag_path = str(Path(asset_dir, asset_name).with_suffix(tag_ext))
        full_path = Path(nwo_utils.get_tags_path(), tag_path)
        nwo_utils.copy_file(template_full_path, full_path)
        with ObjectTag(path=tag_path) as tag:
            tag.set_model_tag_path(str(Path(asset_dir, asset_name).with_suffix(".model")))
        return {"FINISHED"}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text=f"This will override the current {self.tag_type} tag with:", icon='ERROR')
        layout.label(text=getattr(context.scene.nwo, f"template_{self.tag_type}"))

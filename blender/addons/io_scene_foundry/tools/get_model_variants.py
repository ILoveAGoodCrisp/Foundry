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
from ..managed_blam.model import ModelTag
from ..managed_blam.object import ObjectTag

from ..utils import get_tags_path

class NWO_GetModelVariants(bpy.types.Operator):
    bl_idname = "nwo.get_model_variants"
    bl_label = "Model Variants"
    bl_description = "Returns a list of model variants"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(self, context):
        return context.object.nwo.marker_game_instance_tag_name_ui and Path(get_tags_path(), context.object.nwo.marker_game_instance_tag_name_ui).exists()
    
    def variant_items(self, context):
        with ObjectTag(path=context.object.nwo.marker_game_instance_tag_name_ui) as object:
            model_tag = object.get_model_tag_path()
        if not model_tag or not Path(get_tags_path(), model_tag).exists():
            return [("default", "default", "")]
        with ModelTag(path=model_tag) as model:
            variants = model.get_model_variants()
        if not variants:
            return [("default", "default", "")]
        items = []
        for v in variants:
            items.append((v, v, ""))

        return items
    
    variant: bpy.props.EnumProperty(
        name="Variant",
        items=variant_items,
    )
    
    def execute(self, context):
        nwo = context.object.nwo
        if str(Path(get_tags_path(), nwo.marker_game_instance_tag_name_ui)):
            nwo.marker_game_instance_tag_variant_name_ui = self.variant
            return {'FINISHED'}
        
        self.report({'ERROR'}, "Tag does not exist or is not a valid type. Cannot find variants")
        return {'CANCELLED'}
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

# MATERIAL PROPERTIES
import os

from ..icons import get_icon_id
from ..utils.nwo_utils import get_tags_path, is_corinth, run_ek_cmd
from .templates import NWO_Op, NWO_PropPanel


class NWO_ShaderProps(NWO_PropPanel):
    bl_label = "Halo Material Path"
    bl_idname = "NWO_PT_ShaderPanel"
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material

    def draw_header(self, context):
        current_material = context.material
        material_nwo = current_material.nwo
        self.layout.prop(material_nwo, "rendered", text="")

    def draw(self, context):
        layout = self.layout
        current_material = context.material
        material_nwo = current_material.nwo
        if not material_nwo.rendered:
            if self.bl_idname == "NWO_PT_MaterialPanel":
                layout.label(text="Not a Halo Material")
            else:
                layout.label(text="Not a Halo Shader")

            layout.enabled = False

        else:
            # layout.use_property_split = True
            flow = layout.grid_flow(
                row_major=True,
                columns=0,
                even_columns=True,
                even_rows=False,
                align=False,
            )
            col = flow.column()
            row = col.row(align=True)
            row.prop(material_nwo, "shader_path", text="")
            row.operator("nwo.shader_path", icon="FILE_FOLDER", text="")
            ext = material_nwo.shader_path.rpartition(".")[2]
            if ext != material_nwo.shader_path and (
                ext == "material" or "shader" in ext
            ):
                col.separator()
                row = col.row()
                row.scale_y = 1.5
                row.operator(
                    "nwo.open_halo_material",
                    icon_value=get_icon_id("foundation"),
                )


class NWO_MaterialOpenTag(NWO_Op):
    bl_idname = "nwo.open_halo_material"
    bl_label = "Open in Foundation"
    bl_description = "Opens the active material's Halo Shader/Material in Foundation"

    def execute(self, context):
        tag_path = get_tags_path() + context.object.active_material.nwo.shader_path
        if os.path.exists(tag_path):
            run_ek_cmd(["foundation", "/dontloadlastopenedwindows", tag_path], True)
        else:
            if is_corinth():
                self.report({"ERROR_INVALID_INPUT"}, "Material tag does not exist")
            else:
                self.report({"ERROR_INVALID_INPUT"}, "Shader tag does not exist")

        return {"FINISHED"}

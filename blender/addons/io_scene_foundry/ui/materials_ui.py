from pathlib import Path
from ..utils import get_tags_path, is_corinth, run_ek_cmd
import bpy

class NWO_MaterialOpenTag(bpy.types.Operator):
    bl_idname = "nwo.open_halo_material"
    bl_label = "Open in Foundation"
    bl_description = "Opens the active material's Halo Shader/Material in Foundation"

    def execute(self, context):
        tag_path = Path(get_tags_path(), context.object.active_material.nwo.shader_path)
        if tag_path.exists():
            run_ek_cmd(["foundation", "/dontloadlastopenedwindows", str(tag_path)], True)
        else:
            if is_corinth():
                self.report({"ERROR_INVALID_INPUT"}, "Material tag does not exist")
            else:
                self.report({"ERROR_INVALID_INPUT"}, "Shader tag does not exist")

        return {"FINISHED"}


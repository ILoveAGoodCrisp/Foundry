

import bpy
from .. import utils
from pathlib import Path
import shutil

class NWO_OT_ShaderDuplicate(bpy.types.Operator):
    bl_idname = "nwo.shader_duplicate"
    bl_label = "Duplicate Tag"
    bl_description = "Copies the currently referenced shader/material tag to the specified directory (renaming if necessary) and updates the shader/material tag to this new tag"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.active_material and context.object.active_material.nwo.shader_path and utils.valid_nwo_asset() and Path(utils.get_tags_path(), utils.relative_path(context.object.active_material.nwo.shader_path)).exists()

    def execute(self, context):
        tags_dir = utils.get_tags_path()
        nwo = context.object.active_material.nwo
        file = Path(tags_dir, utils.relative_path(nwo.shader_path))
        asset_dir = utils.get_asset_path()
        if utils.is_corinth():
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
        
        nwo.shader_path = utils.relative_path(destination)
        self.report({"INFO"}, f"Tag successfully duplicated")
        return {"FINISHED"}

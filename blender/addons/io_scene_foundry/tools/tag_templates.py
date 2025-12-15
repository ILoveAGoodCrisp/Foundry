from pathlib import Path
import bpy
import os
from ..managed_blam.model import ModelTag
from ..managed_blam.object import ObjectTag
from .. import utils

class NWO_OT_LoadTemplate(bpy.types.Operator):
    bl_idname = "nwo.load_template"
    bl_label = "Load Template"
    bl_description = "Loads a template tag for the given tag type"
    bl_options = {"UNDO"}
    
    tag_type: bpy.props.StringProperty(options={'SKIP_SAVE', 'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return utils.valid_nwo_asset()

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        if self.tag_type == "":
            return {'CANCELLED'}
        tag_ext = "." + self.tag_type
        template_tag_str = getattr(scene_nwo, f"template_{self.tag_type}")
        template_tag_path = Path(utils.relative_path(template_tag_str))
        template_full_path = Path(utils.get_tags_path(), template_tag_path)
        if not template_full_path.exists():
            self.report({'WARNING'}, "Template tag does not exist")
            return {'CANCELLED'}
        
        asset_dir, asset_name = utils.get_asset_info()
        full_asset_dir_path = Path(utils.get_tags_path(), asset_dir)
        if not full_asset_dir_path.exists():
            os.makedirs(full_asset_dir_path, exist_ok=True) 
        tag_path = str(Path(asset_dir, asset_name).with_suffix(tag_ext))
        full_path = Path(utils.get_tags_path(), tag_path)
        utils.copy_file(template_full_path, full_path) 
        if self.tag_type == 'model':
            with ModelTag(path=tag_path) as model:
                model.set_asset_paths()
                model.set_model_overrides(scene_nwo.template_render_model, scene_nwo.template_collision_model, scene_nwo.template_model_animation_graph, scene_nwo.template_physics_model)
        else:
            with ObjectTag(path=tag_path) as tag:
                tag.set_model_tag_path(str(Path(asset_dir, asset_name).with_suffix(".model")))
        return {"FINISHED"}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)
    
    def draw(self, context):
        layout = self.layout
        layout.label(text=f"This will override the current {self.tag_type} tag with:", icon='ERROR')
        layout.label(text=getattr(utils.get_scene_props(), f"template_{self.tag_type}"))


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
        return context.object.nwo.marker_game_instance_tag_name and Path(get_tags_path(), context.object.nwo.marker_game_instance_tag_name).exists()
    
    def variant_items(self, context):
        with ObjectTag(path=context.object.nwo.marker_game_instance_tag_name) as object:
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
        if str(Path(get_tags_path(), nwo.marker_game_instance_tag_name)):
            nwo.marker_game_instance_tag_variant_name = self.variant
            return {'FINISHED'}
        
        self.report({'ERROR'}, "Tag does not exist or is not a valid type. Cannot find variants")
        return {'CANCELLED'}
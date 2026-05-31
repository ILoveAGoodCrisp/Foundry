
from pathlib import Path
import bpy

from ..managed_blam.render_model import RenderModelTag
from ..managed_blam.model import ModelTag
from ..managed_blam.object import ObjectTag

from ..utils import get_tags_path, relative_path, current_project_valid, get_scene_props

class NWO_OT_GetModelMarkersForEvent(bpy.types.Operator):
    bl_idname = "nwo.get_model_markers_event"
    bl_label = "Get Model Markers"
    bl_description = "Returns a list of model markers for a cinematic event"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        nwo = get_scene_props()
        scene_nwo = context.scene.nwo # scene specific
        if nwo.asset_type == 'cinematic' and scene_nwo.cinematic_events and scene_nwo.active_cinematic_event_index > -1 and scene_nwo.active_cinematic_event_index < len(scene_nwo.cinematic_events):
            event = scene_nwo.cinematic_events[scene_nwo.active_cinematic_event_index]
            ob = event.marker
            if ob and ob.type == 'ARMATURE':
                tag_path = Path(get_tags_path(), relative_path(ob.nwo.cinematic_object))
                return tag_path.is_absolute() and tag_path.exists() and tag_path.is_file()
        
        return False
    
    def marker_items(self, context):
        scene_nwo = context.scene.nwo # scene specific
        event = scene_nwo.cinematic_events[scene_nwo.active_cinematic_event_index]
        ob = event.marker
        
        with ObjectTag(path=ob.nwo.cinematic_object) as object:
            model_tag = object.get_model_tag_path()
        if not model_tag or not Path(get_tags_path(), model_tag).exists():
            return [("", "None", "")]
        with ModelTag(path=model_tag) as model:
            render_tag = model.get_render_model()
        if not render_tag or not Path(get_tags_path(), render_tag).exists():
            return [("", "None", "")]
        with RenderModelTag(path=render_tag) as render:
            markers = render.get_markers()
        if not markers:
            return [("", "None", "")]
        items = []
        for v in markers:
            items.append((v, v, ""))

        return items
    
    marker: bpy.props.EnumProperty(
        name="marker",
        items=marker_items,
    )
    
    def execute(self, context):
        nwo = context.scene.nwo # scene specific
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        event.marker_name = self.marker
        return {'FINISHED'}

class NWO_OT_GetModelMarkers(bpy.types.Operator):
    bl_idname = "nwo.get_model_markers"
    bl_label = "Get Model Markers"
    bl_description = "Returns a list of model markers"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.object is None:
            return False
        if not context.object.nwo.cinematic_object.strip():
            return False
        
        if not current_project_valid():
            return False
        
        tag_path = Path(get_tags_path(), relative_path(context.object.nwo.cinematic_object))
        return tag_path.is_absolute() and tag_path.exists() and tag_path.is_file()
    
    def marker_items(self, context):
        with ObjectTag(path=context.object.nwo.cinematic_object) as object:
            model_tag = object.get_model_tag_path()
        if not model_tag or not Path(get_tags_path(), model_tag).exists():
            return [("", "None", "")]
        with ModelTag(path=model_tag) as model:
            render_tag = model.get_render_model()
        if not render_tag or not Path(get_tags_path(), render_tag).exists():
            return [("", "None", "")]
        with RenderModelTag(path=render_tag) as render:
            markers = render.get_markers()
        if not markers:
            return [("", "None", "")]
        items = []
        for v in markers:
            items.append((v, v, ""))

        return items
    
    marker: bpy.props.EnumProperty(
        name="marker",
        items=marker_items,
    )
    
    def execute(self, context):
        nwo = context.object.nwo
        nwo.cinematic_lighting_marker = self.marker
        return {'FINISHED'}

class NWO_OT_GetCinematicModelVariants(bpy.types.Operator):
    bl_idname = "nwo.get_cinematic_model_variants"
    bl_label = "Cinematic Variants"
    bl_description = "Returns a list of cinematic object variants"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.object is None:
            return False
        if not context.object.nwo.cinematic_object.strip():
            return False
        
        if not current_project_valid():
            return False
        
        tag_path = Path(get_tags_path(), relative_path(context.object.nwo.cinematic_object))
        return tag_path.is_absolute() and tag_path.exists() and tag_path.is_file()
    
    def variant_items(self, context):
        with ObjectTag(path=context.object.nwo.cinematic_object) as object:
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
        nwo.cinematic_variant = self.variant
        return {'FINISHED'}

class NWO_GetModelVariants(bpy.types.Operator):
    bl_idname = "nwo.get_model_variants"
    bl_label = "Model Variants"
    bl_description = "Returns a list of model variants"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.object is None:
            return False
        if not context.object.nwo.marker_game_instance_tag_name.strip():
            return False
        
        if not current_project_valid():
            return False
        
        tag_path = Path(get_tags_path(), relative_path(context.object.nwo.marker_game_instance_tag_name))
        return tag_path.is_absolute() and tag_path.exists() and tag_path.is_file()
    
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
        nwo.marker_game_instance_tag_variant_name = self.variant
        return {'FINISHED'}
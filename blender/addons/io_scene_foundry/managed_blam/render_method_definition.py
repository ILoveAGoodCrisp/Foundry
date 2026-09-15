"""Render-method category metadata, backed by blam-tags."""
from ..tags.blender import BlenderTag
from ..tags.metadata import RenderMethodDefinitionDocument


class RenderMethodDefinitionTag(BlenderTag, RenderMethodDefinitionDocument):
    tag_ext = 'render_method_definition'

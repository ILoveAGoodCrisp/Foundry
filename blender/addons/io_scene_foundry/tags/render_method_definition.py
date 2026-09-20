"""Render-method category metadata, backed by blam-tags."""
from .blender import BlenderTag
from .metadata import RenderMethodDefinitionDocument


class RenderMethodDefinitionTag(BlenderTag, RenderMethodDefinitionDocument):
    tag_ext = 'render_method_definition'

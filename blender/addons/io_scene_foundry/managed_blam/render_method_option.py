"""Render-method option metadata, backed by blam-tags."""
from ..tags.blender import BlenderTag
from ..tags.metadata import RenderMethodOptionDocument, option_rgba
from types import SimpleNamespace

OptionParameter = SimpleNamespace

# Keep the public color helper used by older callers.
convert_bungie_rgb = option_rgba


class RenderMethodOptionTag(BlenderTag, RenderMethodOptionDocument):
    tag_ext = 'render_method_option'

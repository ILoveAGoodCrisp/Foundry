"""Blender-facing sky tag wrapper."""

from .blender import BlenderTag
from .sky import SkyDocument


class SkyTag(BlenderTag, SkyDocument):
    tag_ext = 'sky'


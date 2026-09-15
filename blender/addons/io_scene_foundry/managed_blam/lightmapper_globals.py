"""Lightmapper globals backed by blam-tags."""
from ..tags.blender import BlenderTag
from ..tags.lighting import LightmapperGlobalsDocument


class LightmapperGlobalsTag(BlenderTag, LightmapperGlobalsDocument):
    tag_ext = 'lightmapper_globals'
        

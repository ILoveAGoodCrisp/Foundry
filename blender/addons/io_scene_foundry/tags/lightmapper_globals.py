"""Lightmapper globals backed by blam-tags."""
from .blender import BlenderTag
from .lighting import LightmapperGlobalsDocument


class LightmapperGlobalsTag(BlenderTag, LightmapperGlobalsDocument):
    tag_ext = 'lightmapper_globals'
        

"""Material-shader metadata, backed by blam-tags."""
from types import SimpleNamespace
from ..tags.blender import BlenderTag
from ..tags.metadata import MaterialShaderDocument, rgba

# Existing material consumers use these names for annotations and colors.
MaterialShaderParameter = SimpleNamespace
convert_argb = rgba


class MaterialShaderTag(BlenderTag, MaterialShaderDocument):
    tag_ext = 'material_shader'
        

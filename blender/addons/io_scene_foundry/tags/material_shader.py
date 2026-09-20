"""Material-shader metadata, backed by blam-tags."""
from types import SimpleNamespace
from .blender import BlenderTag
from .metadata import MaterialShaderDocument, rgba

# Existing material consumers use these names for annotations and colors.
MaterialShaderParameter = SimpleNamespace
convert_argb = rgba


class MaterialShaderTag(BlenderTag, MaterialShaderDocument):
    tag_ext = 'material_shader'
        

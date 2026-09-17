


from .. import utils
from ..tags.blender import BlenderTag
from ..tags.backend import TagDocument
from .light_functions import light_functions
from . import import_transform
import bpy

class CheapLightTag(BlenderTag, TagDocument):
    tag_ext = 'cheap_light'
        
    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)
        
    def to_blender(self, primary_scale="", secondary_scale="", attachment=None):
        radius = 'Falloff End' if self.corinth else 'radius'
        with light_functions(self, ('color', radius, 'intensity')) as functions:
            return self._to_blender(primary_scale, secondary_scale, attachment, *functions)

    def _to_blender(self, primary_scale, secondary_scale, attachment,
                    color_function, size_function, intensity_function):
        data = bpy.data.lights.new(self.tag_path.ShortName, type='POINT')
        
        data.shadow_soft_size = 0.5 * (1 / 0.03048) * import_transform.scale_factor()
        
        
        color_node = None
        color_function_name = f"{self.tag_path.ShortName}_color"
        if color_function.is_basic_function:
            data.color = [utils.srgb_to_linear(c) for c in color_function.colors[0][:3]]
        else:
            color_node = color_function.to_blend_nodes(name=color_function_name)
            
        atten_max = size_function.clamp_min if size_function.is_basic_function else size_function.clamp_max
        
        data.nwo.light_far_attenuation_end = import_transform.distance(atten_max)
        
        
        strength_node = None
        intensity_function_name = f"{self.tag_path.ShortName}_strength"
        if intensity_function.is_basic_function:
            data.nwo.light_intensity = intensity_function.clamp_min
        else:
            data.nwo.light_intensity = intensity_function.clamp_max
            strength_node = intensity_function.to_blend_nodes(name=intensity_function_name, normalize=True)
        
        if attachment is not None:
            if intensity_function.input:
                attachment.function_names.add(intensity_function.input)
            if intensity_function.range and intensity_function.is_ranged:
                attachment.function_names.add(intensity_function.range)
            if intensity_function.output_modifier and intensity_function.output_modifier_type.value > 0:
                attachment.function_names.add(intensity_function.output_modifier)

        utils.make_halo_light(data, primary_scale, secondary_scale, color_node, strength_node)
        
        return data

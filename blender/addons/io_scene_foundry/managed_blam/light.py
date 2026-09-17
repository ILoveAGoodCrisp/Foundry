


from math import radians

from .bitmap import bitmap_to_image
from .. import utils
from ..tags.blender import BlenderTag
from ..tags.backend import TagDocument
from ..tags.metadata import enum_index
from .light_functions import light_functions
from . import import_transform
import bpy

class LightTag(BlenderTag, TagDocument):
    tag_ext = 'light'
        
    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)
        
    def _to_blender_reach(self, primary_scale, secondary_scale, attachment):
        with light_functions(self, ('color', 'intensity')) as functions:
            return self._convert(primary_scale, secondary_scale, attachment, *functions)

    def _convert(self, primary_scale, secondary_scale, attachment, color_function, intensity_function):
        root = self.tag.root()
        is_spot_light = enum_index(self.value(root, 'type'), ('sphere', 'frustum')) == 1
        data = bpy.data.lights.new(self.tag_path.ShortName, type='SPOT' if is_spot_light else 'POINT')
        # intensity_scale = 1
        if is_spot_light:
            # intensity_scale = 100
            hotspot_cutoff_size = self.value(root, 'frustum field of view')
            data.spot_size = radians(hotspot_cutoff_size)
            if hotspot_cutoff_size > 0.0:
                data.spot_blend = 1 - self.value(root, 'angular hotspot') / hotspot_cutoff_size
                
        data.shadow_soft_size = 0.5 * (1 / 0.03048) * import_transform.scale_factor()
        
        
        color_node = None
        color_function_name = f"{self.tag_path.ShortName}_color"
        if color_function.is_basic_function:
            data.color = [utils.srgb_to_linear(c) for c in color_function.colors[0][:3]]
        else:
            color_node = color_function.to_blend_nodes(name=color_function_name)
        
        
        strength_node = None
        intensity_function_name = f"{self.tag_path.ShortName}_strength"
        
        atten_falloff = self.value(root, 'attenuation start distance')
        data.nwo.light_far_attenuation_start = import_transform.distance(atten_falloff)
        atten_cutoff = self.value(root, 'attenuation end distance')
        data.nwo.light_far_attenuation_end = import_transform.distance(atten_cutoff)
        
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
                
        gobo_tag_path = self.reference(root, 'gel bitmap')
        gobo_image = None
        if self.path_exists(gobo_tag_path):
            gobo_info = bitmap_to_image(gobo_tag_path.Filename)
            if gobo_info.image:
                gobo_image = gobo_info.image

        utils.make_halo_light(data, primary_scale, secondary_scale, color_node, strength_node, gobo_image)
        
        return data
    
    def _to_blender_corinth(self, primary_scale, secondary_scale, attachment):
        pass
        
    def to_blender(self, primary_scale="", secondary_scale="", attachment=None):
        if self.game in {'halo3', 'halo3odst'}:
            raise NotImplementedError('Halo 3/ODST light falloff conversion is not implemented')
        if self.corinth:
            return self._to_blender_corinth(primary_scale, secondary_scale, attachment)
        else:
            return self._to_blender_reach(primary_scale, secondary_scale, attachment)

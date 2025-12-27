


from math import radians

from .bitmap import bitmap_to_image
from .. import utils
from .connected_material import Function
from . import Tag
import bpy

class LightTag(Tag):
    tag_ext = 'light'
        
    def _read_fields(self):
        if self.corinth:
            pass
        else:
            self.color_struct = self.tag.SelectField("Struct:color")
            self.intensity_struct = self.tag.SelectField("Struct:intensity")
            self.radius_struct = self.tag.SelectField("Struct:radius")
            self.falloff = self.tag.SelectField("Real:falloff")
        
    def _to_blender_reach(self, primary_scale, secondary_scale, attachment):
        is_spot_light = self.tag.SelectField("ShortEnum:type").Value == 1
        data = bpy.data.lights.new(self.tag_path.ShortName, type='SPOT' if is_spot_light else 'POINT')
        if is_spot_light:
            hotspot_cutoff_size = self.tag.SelectField("Real:frustum field of view").Data
            data.spot_size = radians(hotspot_cutoff_size)
            if hotspot_cutoff_size > 0.0:
                data.spot_blend = 1 - self.tag.SelectField("Real:angular hotspot").Data / hotspot_cutoff_size
                
        data.shadow_soft_size = 0.5 * (1 / 0.03048)
        
        color_function = Function()
        color_function.from_element(self.color_struct.Elements[0], "Mapping")
        
        color_node = None
        color_function_name = f"{self.tag_path.ShortName}_color"
        if color_function.is_basic_function:
            data.color = [utils.srgb_to_linear(c) for c in color_function.colors[0][:3]]
        else:
            color_node = color_function.to_blend_nodes(name=color_function_name)
        
        intensity_function = Function()
        intensity_function.from_element(self.intensity_struct.Elements[0], "Mapping")
        
        strength_node = None
        intensity_function_name = f"{self.tag_path.ShortName}_strength"
        
        # atten_cutoff = self.tag.SelectField("Real:attenuation end distance").Data
        # data.nwo.light_far_attenuation_end = atten_cutoff * 100
        
        if intensity_function.is_basic_function:
            data.energy = utils.calc_light_energy(data, intensity_function.clamp_min) 
        else:
            data.energy = utils.calc_light_energy(data, intensity_function.clamp_max) 
            strength_node = intensity_function.to_blend_nodes(name=intensity_function_name, normalize=True)
        
        if attachment is not None:
            if intensity_function.input:
                attachment.function_names.add(intensity_function.input)
            if intensity_function.range and intensity_function.is_ranged:
                attachment.function_names.add(intensity_function.range)
            if intensity_function.output_modifier and intensity_function.output_modifier_type.value > 0:
                attachment.function_names.add(intensity_function.output_modifier)
                
        gobo_tag_path = self.tag.SelectField("Reference:gel bitmap").Path
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
        
        if self.corinth:
            return self._to_blender_corinth(primary_scale, secondary_scale, attachment)
        else:
            return self._to_blender_reach(primary_scale, secondary_scale, attachment)
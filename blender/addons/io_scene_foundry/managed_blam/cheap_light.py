


from .. import utils
from .connected_material import Function
from . import Tag
import bpy

class CheapLightTag(Tag):
    tag_ext = 'cheap_light'
        
    def _read_fields(self):
        self.color_struct = self.tag.SelectField("Struct:color")
        self.intensity_struct = self.tag.SelectField("Struct:intensity")
        self.radius_struct = self.tag.SelectField("Struct:radius")
        self.falloff = self.tag.SelectField("Real:falloff")
        
    def to_blender(self, primary_scale="", secondary_scale="", attachment=None):
        data = bpy.data.lights.new(self.tag_path.ShortName, type='POINT')
        
        data.shadow_soft_size = 0.5 * (1 / 0.03048)
        
        color_function = Function()
        color_function.from_element(self.color_struct.Elements[0], "Mapping")
        
        color_node = None
        color_function_name = f"{self.tag_path.ShortName}_color"
        if color_function.is_basic_function:
            data.color = [utils.srgb_to_linear(c) for c in color_function.colors[0][:3]]
        else:
            color_node = color_function.to_blend_nodes(name=color_function_name)
            
        size_function = Function()
        size_function.from_element(self.radius_struct.Elements[0], "Mapping")
        atten_max = size_function.clamp_min if size_function.is_basic_function else size_function.clamp_max
        
        data.nwo.light_far_attenuation_end = atten_max * 100
        
        intensity_function = Function()
        intensity_function.from_element(self.intensity_struct.Elements[0], "Mapping")
        
        strength_node = None
        intensity_function_name = f"{self.tag_path.ShortName}_strength"
        if intensity_function.is_basic_function:
            data.nwo.light_intensity = data.nwo.light_intensity = intensity_function.clamp_min
        else:
            data.nwo.light_intensity = data.nwo.light_intensity = intensity_function.clamp_max
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
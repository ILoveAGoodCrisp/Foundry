


from .. import utils
from .connected_material import Function
from . import Tag
import bpy

class CheapLightTag(Tag):
    tag_ext = 'cheap_light'
        
    def _read_fields(self):
        self.color_struct = self.tag.SelectField("Struct:color[0]")
        self.intensity_struct = self.tag.SelectField("Struct:intensity[0]")
        self.radius_struct = self.tag.SelectField("Struct:radius[0]")
        self.falloff = self.tag.SelectField("Real:falloff")
        
    def to_blender(self, collection=None):
        if collection is None:
            collection = bpy.data.collections.new("cheap_lights")
            self.context.scene.collections.children.link(collection)
            
        data = bpy.data.lights.new(self.tag_path.ShortName)
        
        color_function = Function()
        color_function.from_element(self.color_struct, "Custom:Mapping")
        
        data.color = [utils.srgb_to_linear(c) for c in color_function.colors[0][:3]]
        
        intensity_function = Function()
        intensity_function.from_element(self.intensity_struct, "Custom:Mapping")
        
        data.nwo.light_intensity = intensity_function.clamp_min
        
        
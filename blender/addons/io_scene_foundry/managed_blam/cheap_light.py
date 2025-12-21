


from ..managed_blam import Tag

class CheapLightTag(Tag):
    tag_ext = 'cheap_light'
        
    def _read_fields(self):
        self.color_struct = self.tag.SelectField("Struct:color[0]")
        self.intensity_struct = self.tag.SelectField("Struct:intensity[0]")
        self.radius_struct = self.tag.SelectField("Struct:radius[0]")
        self.falloff = self.tag.SelectField("Real:falloff")
        

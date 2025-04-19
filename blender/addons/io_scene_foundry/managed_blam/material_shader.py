

from pathlib import Path
from ..managed_blam import Tag, tag_path_from_string

def convert_argb(color):
    red = color[1]
    green = color[2]
    blue = color[3]
    alpha = color[0]
    return red, green, blue, alpha

class MaterialShaderParameter:
    def __init__(self, element, tags_dir):
        self.name = element.Fields[0].GetStringData()
        self.ui_name = element.SelectField("display name").DataAsText
        if not self.ui_name:
            self.ui_name = self.name
            
        self.type = element.Fields[1].Value
        self.default_bitmap = None
        tif = element.SelectField("bitmap path").GetStringData()
        if tif.strip():
           tif_path = Path(tags_dir, tif).with_suffix(".bitmap")
           if tif_path.exists():
               self.default_bitmap = tag_path_from_string(tif_path)
           
        self.default_color = convert_argb(element.SelectField("color").Data)
        self.default_real = element.SelectField("real").Data
        self.default_vector = element.SelectField("vector").Data
        self.default_int = element.SelectField(r"int\bool").Data
        match self.type:
            case 0:
                self.default = self.default_bitmap
            case 1:
                self.default = self.default_real
            case 2 | 3:
                self.default = self.default_int
            case 4:
                self.default = self.default_color

class MaterialShaderTag(Tag):
    tag_ext = 'material_shader'
    
    def _read_fields(self):
        self.block_parameters = self.tag.SelectField("Block:material parameters")
        
    def read_parameters(self):
        parameters = {}
        for e in self.block_parameters.Elements:
            parameters[e.SelectField('parameter name').GetStringData()] = [e.SelectField('display name').DataAsText, self._Element_get_enum_as_string(e, 'parameter type')]
        return parameters
    
    def read_parameters_list(self):
        return [e.SelectField('parameter name').GetStringData() for e in self.block_parameters.Elements]
    
    # def get_defaults(self):
    #     defaults = {}
    #     parameter_types = {}
    #     for element in self.block_parameters.Elements:
    #         name = element.Fields[0].GetStringData()
    #         p_type = element.Fields[1].Value
    #         parameter_types[name] = p_type
            
    #         match p_type:
    #             case 0: # bitmap
    #                 path = element.SelectField("bitmap path").GetStringData()
    #                 if not path:
    #                     defaults[name] = None
    #                 else:
    #                     bitmap_path = Path(path).with_suffix(".bitmap")
    #                     defaults[name] = self._TagPath_from_string(bitmap_path)
    #             case 1: # real
    #                 defaults[name] = element.SelectField("real").Data
    #             case 2 | 3: # int / bool
    #                 defaults[name] = element.SelectField(r"int\bool").Data
    #             case 4: # color
    #                 defaults[name] = [n for n in element.SelectField("color").Data]

    #     return defaults, parameter_types
    
    def get_defaults(self):
        return {element.Fields[0].GetStringData(): MaterialShaderParameter(element, self.tags_dir) for element in self.block_parameters.Elements}
        
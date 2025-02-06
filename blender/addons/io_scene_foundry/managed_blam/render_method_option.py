

import numpy as np
from ..managed_blam import Tag

bungie_cannot_spell = {
    "point_specular_contribtuion": "point_specular_contribution"
}

def convert_channel(value):
    if value <= 0:
        return np.clip(255 * (1 - abs(value) / 128), 0, 255).astype(int) / 255
    else:
        return np.clip(255 * (1 - value / 128), 0, 255).astype(int) / 255
    
def convert_bungie_rgb(color):
    red = convert_channel(color[1])
    green = convert_channel(color[2])
    blue = convert_channel(color[3])
    alpha = convert_channel(color[0])
    
    return (red, green, blue, alpha)

class OptionParameter:
    def __init__(self, element):
        self.name = element.Fields[0].GetStringData()
        self.ui_name = element.Fields[1].GetStringData()
        if not self.ui_name:
            self.ui_name = self.name
        
        fixed_name = bungie_cannot_spell.get(self.ui_name)
        if fixed_name is not None:
            self.ui_name = fixed_name
            
        self.type = element.Fields[2].Value
        self.default_bitmap = element.Fields[4].Path
        self.default_real = element.Fields[5].Data
        self.default_int = element.Fields[6].Data
        self.default_color = convert_bungie_rgb(element.Fields[11].Data)
        match self.type:
            case 0:
                self.default = self.default_bitmap
            case 1:
                self.default = self.default_color
            case 2:
                self.default = self.default_real
            case 3 | 4:
                self.default = self.default_int
            case 5:
                self.default = tuple((self.default_color, self.default_real))

class RenderMethodOptionTag(Tag):
    tag_ext = 'render_method_option'
    
    def _read_fields(self):
        self.block_parameters = self.tag.SelectField("Block:parameters")
        
    def get_option_parameters(self):
        return {element.Fields[0].GetStringData(): OptionParameter(element) for element in self.block_parameters.Elements}
        
    def read_options(self):
        parameters = {}
        for e in self.block_parameters.Elements:
            parameters[e.SelectField('parameter name').GetStringData()] = [e.SelectField('parameter ui override name').GetStringData(), e.SelectField('parameter type').Value]
        return parameters
    
    def read_parameter_types(self):
        return {element.Fields[0].GetStringData(): element.Fields[2].Value for element in self.block_parameters.Elements}
    
    def read_parameter_names(self):
        names = {}
        for element in self.block_parameters.Elements:
            ui_name = element.Fields[1].GetStringData()
            real_name = element.Fields[0].GetStringData()
            if ui_name:
                names[ui_name] = real_name
            else:
                names[real_name] = real_name
                
        return names
    
    def read_defaults(self) -> dict:
        """Returns a dict of parameter names and their default bitmaps/values"""
        defaults = {}
        for element in self.block_parameters.Elements:
            name = element.Fields[0].GetStringData()
            match element.Fields[2].Value:
                case 0: # bitmap
                    defaults[name] = element.Fields[4].Path
                case 1: # color
                    defaults[name] = [n for n in element.SelectField("default color").Data]
                case 2: # real
                    defaults[name] = element.SelectField("default real value").Data
                case 3 | 4: # int / bool
                    defaults[name] = element.SelectField(r"default int\bool value").Data
                case 5: # color & Alpha
                    color = [n for n in element.SelectField("default color").Data]
                    alpha = element.SelectField("default real value").Data
                    defaults[name] = tuple((color, alpha))
                    
        return defaults
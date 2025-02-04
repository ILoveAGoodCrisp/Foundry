

from pathlib import Path
from ..managed_blam import Tag

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
    
    def get_defaults(self):
        defaults = {}
        parameter_types = {}
        for element in self.block_parameters.Elements:
            name = element.Fields[0].GetStringData()
            p_type = element.Fields[1].Value
            parameter_types[name] = p_type
            
            match p_type:
                case 0: # bitmap
                    path = element.SelectField("bitmap path").GetStringData()
                    if not path:
                        defaults[name] = None
                    else:
                        bitmap_path = Path(path).with_suffix(".bitmap")
                        defaults[name] = self._TagPath_from_string(bitmap_path)
                case 1: # real
                    defaults[name] = element.SelectField("real").Data
                case 2 | 3: # int / bool
                    defaults[name] = element.SelectField(r"int\bool").Data
                case 4: # color
                    defaults[name] = [n for n in element.SelectField("color").Data]

        return defaults, parameter_types
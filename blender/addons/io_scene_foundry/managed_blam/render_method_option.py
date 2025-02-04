

from ..managed_blam import Tag

class RenderMethodOptionTag(Tag):
    tag_ext = 'render_method_option'
    
    def _read_fields(self):
        self.block_parameters = self.tag.SelectField("Block:parameters")
        
    def read_options(self):
        parameters = {}
        for e in self.block_parameters.Elements:
            parameters[e.SelectField('parameter name').GetStringData()] = [e.SelectField('parameter ui override name').GetStringData(), e.SelectField('parameter type').Value]
        return parameters
    
    def read_parameter_types(self):
        return {element.Fields[0].GetStringData(): element.Fields[2].Value for element in self.block_parameters.Elements}
    
    def read_defaults(self) -> dict:
        """Returns a dict of parameter names and their default bitmaps/values"""
        defaults = {}
        for element in self.block_parameters.Elements:
            name = element.Fields[0].GetStringData()
            match element.Fields[2].Value:
                case 0: # bitmap
                    defaults[name] = element.Fields[4].Path
                case 1 | 5: # color
                    defaults[name] = [n for n in element.SelectField("default color").Data]
                case 2: # real
                    defaults[name] = element.SelectField("default real value").Data
                case 3 | 4: # int / bool
                    defaults[name] = element.SelectField(r"default int\bool value").Data
                    
        return defaults
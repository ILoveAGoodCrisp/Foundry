

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
    
    def read_default_bitmaps(self) -> dict:
        """Returns a dict of parameter names and their default bitmaps"""
        return {element.Fields[0].GetStringData(): element.Fields[4].Path for element in self.block_parameters.Elements}
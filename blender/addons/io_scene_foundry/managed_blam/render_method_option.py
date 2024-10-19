

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
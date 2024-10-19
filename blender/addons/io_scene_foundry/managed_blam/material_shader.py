

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
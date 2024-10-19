

from ..managed_blam import Tag
from ..managed_blam.render_method_option import RenderMethodOptionTag

class RenderMethodDefinitionTag(Tag):
    tag_ext = 'render_method_definition'
    
    def _read_fields(self):
        self.block_categories = self.tag.SelectField("Block:categories")
        
    def get_categories(self):
        categories = {}
        for e in self.block_categories.Elements:
            e_options = e.Elements
            options_dict = {}
            for e_option in e_options:
                with RenderMethodOptionTag() as render_method_option:
                    option_parameters = render_method_option.read_options()
                options_dict[e_option.SelectField("option name").GetStringData()] = option_parameters
                
            categories[e.Fields[0].Value] = options_dict
            
        return categories
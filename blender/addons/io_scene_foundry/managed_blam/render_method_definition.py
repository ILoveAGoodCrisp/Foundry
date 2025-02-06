

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
    
    def get_defaults(self):
        category_options = {}
        for element in self.block_categories.Elements:
            category_name = element.Fields[0].GetStringData()
            option_parameters = {}
            for sub_element in element.Fields[1].Elements:
                option_name = sub_element.Fields[0].GetStringData()
                option_path = sub_element.Fields[1].Path
                if option_path is None:
                    option_parameters[option_name] = {}
                else:
                    with RenderMethodOptionTag(path=option_path) as render_method_option:
                        option_parameters[option_name] = render_method_option.get_option_parameters()
                        
            category_options[category_name] = option_parameters

        return category_options
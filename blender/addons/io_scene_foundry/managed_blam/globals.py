

from enum import Enum
from ..managed_blam import Tag

class FPARMS(Enum):
    NONE = 0
    SPARTAN = 1
    ELITE = 2

class GlobalsTag(Tag):
    tag_ext = 'globals'
    needs_explicit_path = True
    
    def _read_fields(self):
        self.block_materials = self.tag.SelectField("Block:materials")
        
    def get_global_materials(self):
        return [e.SelectField('name').GetStringData() for e in self.block_materials.Elements]
    
    def get_fp_arms_path(self, character_type: FPARMS):
        
        if self.corinth:
            character_type = FPARMS.SPARTAN
        
        match character_type:
            case FPARMS.SPARTAN:
                element = self.tag.SelectField("Block:@player representation").Elements[0]
            case FPARMS.ELITE:
                element = self.tag.SelectField("Block:@player representation").Elements[1]
            case _:
                return
            
        return element.SelectField("Reference:first person hands").Path.Filename, element.SelectField("Reference:third person unit").Path.Filename


from ..managed_blam import Tag
import os

class GlobalsTag(Tag):
    tag_ext = 'globals'
    needs_explicit_path = True
    
    def _read_fields(self):
        self.block_materials = self.tag.SelectField("Block:materials")
        
    def get_global_materials(self):
        return [e.SelectField('name').GetStringData() for e in self.block_materials.Elements]
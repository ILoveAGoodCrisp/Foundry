

from enum import Enum
from pathlib import Path

from .model import ModelTag
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
        allowed_fp_region_perms = "default"
        match character_type:
            case FPARMS.SPARTAN:
                element = self.tag.SelectField("Block:@player representation").Elements[0]
            case FPARMS.ELITE:
                element = self.tag.SelectField("Block:@player representation").Elements[1]
            case _:
                return
        
        if self.corinth:
            fp_model_path = element.SelectField("Reference:first person hands model").Path
            variant = element.SelectField("StringId:first person multiplayer hands variant").GetStringData()
            if fp_model_path is None or not Path(fp_model_path.Filename).exists():
                return
            
            with ModelTag(path=fp_model_path.RelativePathWithExtension) as model:
                fp_path = model.reference_render_model.Path
                if fp_path is not None:
                    if variant:
                        allowed_fp_region_perms = model.get_variant_regions_and_permutations(variant, -1)

        else:
            fp_path = element.SelectField("Reference:first person hands").Path
            
        tp_path = element.SelectField("Reference:third person unit").Path
        
        if fp_path is not None and tp_path is not None:
            return fp_path.Filename, tp_path.Filename, allowed_fp_region_perms
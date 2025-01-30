

from pathlib import Path

from .model import ModelTag
from . import Tag

class ObjectTag(Tag):
    """For ManagedBlam task that cover all tags that are classed as objects"""
    def _read_fields(self):
        first_struct = self.tag.Fields[0]
        if first_struct.DisplayName == "object":
            object_struct = first_struct
        else:
            object_struct = first_struct.Elements[0].Fields[0]
        self.reference_model = self.tag.SelectField(f"{object_struct.FieldPath}/Reference:model")
        self.default_variant = self.tag.SelectField(f"{object_struct.FieldPath}/StringId:default model variant")
        self.block_change_colors = self.tag.SelectField(f"{object_struct.FieldPath}/Block:change colors")
            
    def get_model_tag_path(self):
        model_path = self.reference_model.Path
        if model_path:
            return model_path.RelativePathWithExtension
        else:
            print(f"{self.path} has no model reference")
            
    def get_model_tag_path_full(self):
        model_path = self.reference_model.Path
        if model_path:
            return model_path.Filename
        else:
            print(f"{self.path} has no model reference")
            
    def set_model_tag_path(self, new_path: str):
        self.reference_model.Path = self._TagPath_from_string(new_path)
        self.tag_has_changes = True
        
    def get_change_colors(self, variant="") -> list:
        change_colors = [tuple((1, 1, 1)), tuple((1, 1, 1)), tuple((1, 1, 1)), tuple((1, 1, 1))]
        if not variant:
            variant = self.default_variant.GetStringData()
        if not variant:
            return change_colors
        
        for element in self.block_change_colors.Elements:
            perms = element.Fields[0]
            for sub_element in perms.Elements:
                 if sub_element.Fields[3].GetStringData() == variant:
                     color = [n for n in sub_element.Fields[2].Data]
                     color.append(1.0) # Alpha
                     change_colors[element.ElementIndex] = color
                     break
                 
        return change_colors
    
    def get_variants(self) -> list[str]:
        model_path = self.get_model_tag_path_full()
        if not Path(model_path).exists():
            return []
        with ModelTag(path=model_path) as model:
            return model.get_model_variants()
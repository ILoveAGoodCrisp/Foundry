

from pathlib import Path
from .connected_material import Function
import bpy
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
        self.object_struct = object_struct
        self.reference_model = self.tag.SelectField(f"{object_struct.FieldPath}/Reference:model")
        self.default_variant = self.tag.SelectField(f"{object_struct.FieldPath}/StringId:default model variant")
        self.block_change_colors = self.tag.SelectField(f"{object_struct.FieldPath}/Block:change colors")
        self.block_functions = self.tag.SelectField(f"{object_struct.FieldPath}/Block:functions")
        self.runtime_object_type = self.tag.SelectField(f"{object_struct.FieldPath}/ShortInteger:runtime object type")
            
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
        if self.block_change_colors.Elements.Count == 0:
            return
        change_colors = [tuple((1.0, 1.0, 1.0, 1.0)), tuple((1.0, 1.0, 1.0, 1.0)), tuple((1.0, 1.0, 1.0, 1.0)), tuple((1.0, 1.0, 1.0, 1.0))]
        if not variant:
            variant = self.default_variant.GetStringData()
        if not variant:
            return change_colors

        for element in self.block_change_colors.Elements:
            perms = element.Fields[0]
            for sub_element in perms.Elements:
                text = sub_element.Fields[3].GetStringData()
                if text == variant or (variant == "default" and not text):
                    color = [float(n) for n in sub_element.Fields[2].Data]
                    color.append(1.0) # Alpha
                    change_colors[element.ElementIndex] = color
                    break
                 
        return change_colors
    
    def get_magazine_size(self):
        if self.tag_path.Extension != "weapon":
            return 0
        
        magazines = self.tag.SelectField("Block:magazines")
        if magazines.Elements.Count == 0:
            return 0
        
        return magazines.Elements[0].SelectField("rounds loaded maximum").Data
    
    def get_variants(self) -> list[str]:
        model_path = self.get_model_tag_path_full()
        if not Path(model_path).exists():
            return []
        with ModelTag(path=model_path) as model:
            return model.get_model_variants()
        
    def functions_from_tag(self) -> list[str, float]:
        for element in self.block_functions.Elements:
            export_name = element.SelectField("export name").GetStringData()
            if not export_name.strip():
                continue
            node_group_name = f"{self.tag_path.ShortName} {export_name}"
            group = bpy.data.node_groups.get(node_group_name)
            if group is None:
                group = bpy.data.node_groups.new(node_group_name)
                
    def functions_to_blender(self) -> list:
        '''Converts object functions to blender shader node groups'''
        functions = set()
        for element in self.block_functions.Elements:
            export_name = element.SelectField("StringId:export name").GetStringData()
            if not export_name.strip():
                continue
            func = Function()
            func.from_element(element, "default function")
            func.to_blend_nodes(name=export_name)
            # functions.add(export_name)
            if func.input:
                functions.add(func.input)
            if func.ranged_interpolation_name:
                functions.add(func.ranged_interpolation_name)

        return sorted(functions)
            
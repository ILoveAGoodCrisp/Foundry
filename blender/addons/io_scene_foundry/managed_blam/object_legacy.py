"""Remaining object function and cinematic block conversion using .NET."""
from collections import defaultdict
from . import Tag
from .connected_material import Function, game_functions


class LegacyObjectTag(Tag):
    """Custom function and cinematic conversion operations awaiting native bindings."""
    def _read_fields(self):
        first_struct = self.tag.Fields[0]
        if first_struct.DisplayName == "object":
            object_struct = first_struct
        else:
            object_struct = first_struct.Elements[0].Fields[0]
        self.object_struct = object_struct
        self.reference_model = self.tag.SelectField(f"{object_struct.FieldPath}/Reference:model")
        self.block_functions = self.tag.SelectField(f"{object_struct.FieldPath}/Block:functions")
        
    def get_model_tag_path_full(self):
        model_path = self.reference_model.Path
        if model_path:
            return model_path.Filename
        else:
            print(f"{self.path} has no model reference")
            
    def functions_to_blender(self) -> dict:
        '''Converts object functions to blender shader node groups'''
        functions = defaultdict(list)
        node_funcs = []
        valid_functions = {}
        game_func_names = set(game_functions)
        for element in self.block_functions.Elements:
            export_name = element.SelectField("StringId:export name").GetStringData()
            if not export_name.strip():
                continue
            elif export_name == element.SelectField("StringId:import name").GetStringData():
                continue
            elif export_name in game_func_names:
                continue
            func = Function()
            func.from_element(element, "default function")
            func.make_node_group(export_name)
            valid_functions[export_name] = func
        
        export_names = set(valid_functions)
            
        for export_name, func in valid_functions.items():
            func.to_blend_nodes(name=export_name)
            node_funcs.append(func)
            if func.input.strip():
                functions[export_name].append(func.input)
            if func.range.strip():
                if func.range in export_names:
                    functions[export_name].append(valid_functions[func.range].input)
                else:
                    functions[export_name].append(func.range)
            if func.scale_by.strip():
                if func.scale_by in export_names:
                    functions[export_name].append(valid_functions[func.scale_by].input)
                else:
                    functions[export_name].append(func.scale_by)
            if func.turn_off_with.strip():
                if func.turn_off_with in export_names:
                    functions[export_name].append(valid_functions[func.turn_off_with].input)
                else:
                    functions[export_name].append(func.turn_off_with)

        return functions
    
    

"""Remaining object function and cinematic block conversion using .NET."""
from collections import defaultdict
from . import Tag
from .connected_material import Function, game_functions


class LegacyObjectTag(Tag):
    """Custom function and cinematic conversion operations awaiting native bindings."""
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self.tag_has_changes = False
            self.always_save = False
        return super().__exit__(exc_type, exc_value, traceback)

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

def copy_cinematic_scenery_legacy(object_path, scenery_path, ammo_functions):
    """Compatibility fallback for shipped layouts that differ from the native schema."""
    AMMO_FUNCTIONS = ammo_functions
    with LegacyObjectTag(path=object_path, tag_must_exist=True) as obj, LegacyObjectTag(path=scenery_path) as scenery:
        scenery.reference_model.Path = obj.reference_model.Path
        scenery_object = scenery.object_struct.Elements[0]
        obj_object = obj.object_struct.Elements[0]
        scenery_flags = scenery_object.SelectField("Flags:flags")
        obj_flags = obj_object.SelectField("Flags:flags")
        scenery_flags.SetBit("does not cast shadow", obj_flags.TestBit("does not cast shadow"))
        scenery_flags.SetBit("search cardinal direction lightmaps on failure", obj_flags.TestBit("search cardinal direction lightmaps on failure"))
        scenery_flags.SetBit("object scales attachments", obj_flags.TestBit("object scales attachments"))
        scenery_flags.SetBit("sample enviroment lighting only ignore object lighting", obj_flags.TestBit("sample enviroment lighting only ignore object lighting"))
        scenery_object.SelectField("bounding radius").Data = obj_object.SelectField("bounding radius").Data
        scenery_object.SelectField("bounding offset").Data = obj_object.SelectField("bounding offset").Data
        scenery_object.SelectField("lightmap shadow mode").Value = obj_object.SelectField("lightmap shadow mode").Value
        scenery_object.SelectField("sweetener size").Value = obj_object.SelectField("sweetener size").Value
        scenery_object.SelectField("dynamic light sphere radius").Data = obj_object.SelectField("dynamic light sphere radius").Data
        scenery_object.SelectField("dynamic light sphere offset").Data = obj_object.SelectField("dynamic light sphere offset").Data
        scenery_object.SelectField("default model variant").Data = obj_object.SelectField("default model variant").Data
        scenery_object.SelectField("crate object").Path = obj_object.SelectField("crate object").Path
        scenery_object.SelectField("creation effect").Path = obj_object.SelectField("creation effect").Path
        scenery_object.SelectField("material effects").Path = obj_object.SelectField("material effects").Path
        interpolation = obj_object.SelectField("simulation_interpolation")
        if interpolation is not None:
            scenery_object.SelectField("simulation_interpolation").Path = interpolation.Path
        funcs = scenery_object.SelectField("functions")
        funcs.Deserialize(obj_object.SelectField("functions").Serialize())
        found_ones = False
        found_tens = False
        is_weapon = object_path.suffix.lower() == '.weapon'
        for e in funcs.Elements:
            e.SelectField("import name").SetStringData("zero")
            if is_weapon:
                if e.SelectField("export name").GetStringData() == AMMO_FUNCTIONS[0]:
                    found_ones = True
                elif e.SelectField("export name").GetStringData() == AMMO_FUNCTIONS[1]:
                    found_tens = True

        if is_weapon:
            if not found_ones:
                e = funcs.AddElement()
                e.SelectField("import name").SetStringData("zero")
                e.SelectField("export name").SetStringData(AMMO_FUNCTIONS[0])
            if not found_tens:
                e = funcs.AddElement()
                e.SelectField("import name").SetStringData("zero")
                e.SelectField("export name").SetStringData(AMMO_FUNCTIONS[1])

        for name in ('attachments', 'hull surfaces', 'jetwash', 'widgets', 'change colors', 'spawn effects'):
            source_block = obj_object.SelectField(name)
            if source_block is not None:
                scenery_object.SelectField(name).Deserialize(source_block.Serialize())

        scenery.tag_has_changes = True



from collections import defaultdict
from math import radians
from pathlib import Path

from mathutils import Matrix

from .. import utils


from .light import LightTag
from .cheap_light import CheapLightTag
from .connected_material import Function
import bpy
from . import Tag
from . import import_transform
from .connected_material import game_functions

class Attachment:
    def __init__(self):
        self.function_names = set()
        self.objects = []
        self.armature = None
    
valid_attachment_tags = "cheap_light", "light"

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
        self.default_variant = self.tag.SelectField(f"{object_struct.FieldPath}/StringId:default model variant")
        self.block_change_colors = self.tag.SelectField(f"{object_struct.FieldPath}/Block:change colors")
        self.block_functions = self.tag.SelectField(f"{object_struct.FieldPath}/Block:functions")
        self.runtime_object_type = self.tag.SelectField(f"{object_struct.FieldPath}/ShortInteger:runtime object type")
        self.attachments = self.tag.SelectField(f"{object_struct.FieldPath}/Block:attachments")
        
    def attachments_to_blender(self, armature: bpy.types.Object, markers: list[bpy.types.Object], parent_collection):
        
        collection = bpy.data.collections.new(f"{self.tag_path.ShortName}_attachments")
        collection.nwo.type = 'exclude'
        parent_collection.children.link(collection)
        
        attachments = []
        for element in self.attachments.Elements:
            attach_type = element.SelectField("type").Path
            if not (self.path_exists(attach_type) and attach_type.Extension in valid_attachment_tags):
                continue
            
            primary_scale = element.SelectField("primary scale").GetStringData()
            secondary_scale = element.SelectField("secondary scale").GetStringData()
            
            data = None
            attachment = Attachment()
            if primary_scale:
                attachment.function_names.add(primary_scale)
            if secondary_scale:
                attachment.function_names.add(secondary_scale)
            match attach_type.Extension:
                case "cheap_light":
                    with CheapLightTag(path=attach_type) as cheap_light:
                        data = cheap_light.to_blender(primary_scale, secondary_scale, attachment)
                case "light":
                    with LightTag(path=attach_type) as light:
                        data = light.to_blender(primary_scale, secondary_scale, attachment)
                        
            if data is None:
                continue
            
            marker_name = element.SelectField("marker").GetStringData()
            found_marker = False
            for m in markers:
                if m.nwo.marker_model_group == marker_name:
                    found_marker = True
                    ob = bpy.data.objects.new(data.name, data)
                    collection.objects.link(ob)
                    if ob.type == 'LIGHT':
                        ob.matrix_world = utils.halo_transforms(ob) @ Matrix.Rotation(radians(-90.0), 4, 'X')
                        ob.scale *= (1 / 0.03048) * import_transform.scale_factor()
                        # ob.update_tag(refresh={'DATA'})
                        
                    ob.parent = m
                    ob.parent_type = 'OBJECT'
                    attachment.objects.append(ob)
            
            attachment.armature = armature
            attachments.append(attachment)
                        
            # if not found_marker:
            #     ob = bpy.data.objects.new(data.name, data)
            #     collection.objects.link(ob)
            #     ob.parent = armature
            #     ob.parent_type = 'OBJECT'
            #     objects.append(ob)
            
        if not attachments:
            bpy.data.collections.remove(collection)
            
        return attachments
            

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
    
    

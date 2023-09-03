# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

from io_scene_foundry import managed_blam
from io_scene_foundry.tools.export_bitmaps import export_bitmap
from io_scene_foundry.utils.nwo_utils import cull_invalid_chars, dot_partition, get_valid_shader_name, is_halo_node, os_sep_partition, print_warning, remove_chars, space_partition
import os
import bpy

HALO_SCALE_NODE = ['Scale Multiplier', 'Scale X', 'Scale Y']

all_material_shaders = []
global_material_shader = None

class ManagedBlamReadMaterialShader(managed_blam.ManagedBlam):
    def __init__(self, group_node):
        super().__init__()
        self.group_node = group_node
        self.parameters = {}
        self.tag_helper()

    def get_path(self):
        material_shader_name = self.group_node.node_tree.name
        global all_material_shaders
        if not all_material_shaders:
            # Check \shaders\ for the given material_shader
            shaders_dir = os.path.join(self.tags_dir, "shaders")
            for root, _, files in os.walk(shaders_dir):
                for file in files:
                    if file.endswith(".material_shader"):
                        all_material_shaders.append(os.path.join(root, file).replace(self.tags_dir, ""))

        for mat_sha in all_material_shaders:
            if remove_chars(dot_partition(os_sep_partition(mat_sha, True)).lower(), list(" _-")) == remove_chars(material_shader_name.lower(), list(" _-")):
                return mat_sha
        
        return print(f"No material shader found in tags\shaders\... named {material_shader_name}")

    def tag_read(self, tag):
        block_material_parameters = tag.SelectField("Block:material parameters")
        elements = block_material_parameters.Elements
        for e in elements:
            self.parameters[self.Element_get_field_value(e, "parameter name")] = [
                self.Element_get_field_value(e, "display name"),
                self.Element_get_field_value(e, "parameter type"),
            ]

class ManagedBlamReadRenderMethodDefinition(managed_blam.ManagedBlam):
    def __init__(self, group_node):
        super().__init__()
        self.group_node = group_node
        self.categories = {}
        self.tag_helper()

    def get_path(self):
        render_method_definition_name = space_partition(self.group_node.node_tree.name)
        # Check \shaders\ for the given render_method_definition
        shaders_dir = os.path.join(self.tags_dir, "shaders")
        for root, _, files in os.walk(shaders_dir):
            for file in files:
                if file.endswith(".render_method_definition"):
                    if remove_chars(dot_partition(file).lower(), list(" _-")) == remove_chars(render_method_definition_name.lower(), list(" _-")):
                        return os.path.join(root, file).replace(self.tags_dir, "")
        
        return print(f"No render method definition found in tags\shaders\... named {render_method_definition_name}")

    def tag_read(self, tag):
        block_categories = tag.SelectField("Block:categories")
        elements_cats = block_categories.Elements
        self.categories = {}
        for e_cat in elements_cats:
            elements_options = e_cat.Elements
            cat_name = e_cat.Fields[0].Value
            options_dict = {}
            for e_option in elements_options:
                option_name = self.Element_get_field_value(e_option, "option name")
                option_parameters = ManagedBlamReadRenderMethodOption(self.Element_get_field_value(e_option, "option")).parameters
                options_dict[option_name] = option_parameters
            
            self.categories[cat_name] = options_dict

class ManagedBlamReadRenderMethodOption(managed_blam.ManagedBlam):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.parameters = {}
        self.tag_helper()

    def tag_read(self, tag):
        block_parameters = tag.SelectField("Block:parameters")
        elements = block_parameters.Elements
        for e in elements:
            self.parameters[self.Element_get_field_value(e, "parameter name")] = [
                self.Element_get_field_value(e, "parameter ui override name"),
                self.Element_get_field_value(e, "parameter type"),
            ]


class ManagedBlamNewShader(managed_blam.ManagedBlam):
    def __init__(self, blender_material, shader_type, linked_to_blender, specified_path="", export_dir=""):
        super().__init__()
        self.blender_material = blender_material
        self.shader_type = shader_type
        self.linked_to_blender = linked_to_blender
        self.group_node = self.blender_halo_material()
        self.custom = False
        self.export_dir = export_dir
        self.specified_path = specified_path if specified_path and os.path.exists(self.tags_dir + specified_path) else None
        if linked_to_blender and self.group_node:
            if self.corinth:
                global global_material_shader
                if not global_material_shader or global_material_shader.group_node != self.group_node:
                    global_material_shader = ManagedBlamReadMaterialShader(self.group_node) 
            else:
                global global_render_method_definition
                if not global_render_method_definition or global_render_method_definition.group_node != self.group_node:
                    global_render_method_definition = ManagedBlamReadRenderMethodDefinition(self.group_node).categories
            self.custom = bool(getattr(global_material_shader, "tag_path", 0))
        self.tag_helper()

    def get_path(self):
        if self.specified_path:
            return self.specified_path
        elif self.export_dir:
            shaders_dir = self.export_dir
        else:
            shaders_dir = os.path.join(self.asset_dir, "materials" if self.corinth else "shaders")
        shader_name = get_valid_shader_name(self.blender_material)
        tag_ext = ".material" if self.corinth else self.get_shader_type()
        shader_path = os.path.join(shaders_dir, shader_name + tag_ext)

        return shader_path
    
    def blender_halo_material(self):
        nodes = bpy.data.materials[self.blender_material].node_tree.nodes
        for n in nodes:
            if n.type != "OUTPUT_MATERIAL":
                continue
            links = n.inputs[0].links
            if not links:
                continue
            from_node = links[0].from_node
            if from_node.type != "GROUP":
                continue
            group_tree = from_node.node_tree
            if group_tree:
                return from_node
        return None

    def tag_edit(self, tag):
        if self.corinth:
            self.material_tag_edit(tag)
        else:
            self.shader_tag_edit(tag)

    def shader_tag_edit(self, tag):
        if not self.linked_to_blender:
            return
        struct_render_method = tag.SelectField("Struct:render_method").Elements[0]
        # if self.custom:
        #     self.custom_shader(struct_render_method, self.group_node)
        # else:
        self.basic_shader(struct_render_method)

    def setup_options_dicts(self, i, material_model_group_node, option_name):
        from_node = i.links[0].from_node
        option_name, option_value = from_node.node_tree.name.split(" ")[:2]
        if not option_name == option_name:
            print_warning(f"Incompatiable node plugged into {material_model_group_node} {option_name} input")
            return
        self.options_nodes[option_name] = from_node
        self.options_dict[option_name] = getattr(globals(), f"enum_{option_name}_{option_value}")


    def get_shader_type(self):
        return bpy.data.materials[self.blender_material].nwo.shader_type

    def custom_shader(self, struct_render_method, material_model_group_node):
        self.options_nodes = {}
        self.options_dict = {}
        material_parameters = {}
        input_parameter_pairings = {}
        inputs = material_model_group_node.inputs
        cull_chars = list(" _-()'\"")
        # Ensure options block has 12 elements
        options_block = struct_render_method.SelectField("options")
        # while options_block.ElementCount < 12:
        #     new_element = options_block.AddElement()
        #     new_element.SetStringData("-1")
        # toggle off all options
        for e in options_block:
            e.Fields[0].value = -1
        for i in inputs:
            # CONSTANT INPUTS
            if i.name == 'albedo' and i.links:
                self.setup_options_dicts(i, material_model_group_node, 'albedo')
            if i.name == 'bump_mapping' and i.links:
                self.setup_options_dicts(i, material_model_group_node, 'bump_mapping')
            if i.name == 'alpha_test' and i.links:
                self.setup_options_dicts(i, material_model_group_node, 'alpha_test')
            if i.name == 'environment_mapping' and i.links:
                self.setup_options_dicts(i, material_model_group_node, 'environment_mapping')
            if i.name == 'self_illumination' and i.links:
                self.setup_options_dicts(i, material_model_group_node, 'self_illumination')
            if i.name == 'parallax' and i.links:
                self.setup_options_dicts(i, material_model_group_node, 'parallax')
            if i.name == 'wetness' and i.links:
                self.setup_options_dicts(i, material_model_group_node, 'wetness')
            if i.name == 'alpha_blend_source' and i.links:
                self.setup_options_dicts(i, material_model_group_node, 'alpha_blend_source')
            # MATERIAL MODELS
            #################
            # GENERAL
        # Set up options
        for option_name, option_type in self.options_dict.items():
            op_element = options_block.Elements[getattr(globals(), f"enum_{option_name}")]
            op_element.Fields[0].Value = option_type

        # set up categories
        for node in self.options_nodes:
            for i in node.inputs:
                parameters, animated_parameters = self.shader_parameters(i)


    def shader_parameters(self, input):
        parameters = {}
        animated_parameters = {}

        parameters['parameter name'] = input.name
        parameters['parameter type'] = self.parameter_type_from_name(input.name)

    def basic_shader(self, struct_render_method):
        maps = self.get_maps()
        if not maps:
            return print("Cannot read Blender Material Nodes into tag. Blender Material does not have a valid custom node group connected to the material output or does not have a BSDF node connected to the material output")
        if self.shader_type == ".shader":
            # Set up shader options
            block_options = struct_render_method.SelectField("options")
            # Set albedo to default
            if hasattr(self, "has_diffuse"):
                self.Element_set_field_value(block_options.Elements[0], "short", "0")
            elif hasattr(self, "has_albedo"):
                self.Element_set_field_value(block_options.Elements[0], "short", "2")
            # Set bump_mapping to standard
            if hasattr(self, "has_normal"):
                self.Element_set_field_value(block_options.Elements[1], "short", "1")
            else:
                self.Element_set_field_value(block_options.Elements[1], "short", "0")
            # Set up shader parameters
            block_parameters = struct_render_method.SelectField("parameters")
            for m in maps:
                sub_map = m['animated parameters']
                m.pop('animated parameters')
                element = self.Element_from_field_value(block_parameters, "parameter name", m['parameter name'])
                if element is None:
                    element = block_parameters.AddElement()
                    if m['parameter type'] == "bitmap":
                        self.Element_set_field_value(element, "bitmap flags", "1") # sets override
                        self.Element_set_field_value(element, "bitmap filter mode", "6") # sets anisotropic (4) EXPENSIVE

                self.Element_set_field_values(element, m)

                
                if not sub_map: continue
                block_animated_parameters = element.SelectField("animated parameters")
                for k, v in sub_map.items():
                    new = False
                    enum_index = self.EnumIntValue(block_animated_parameters, "type", k)
                    if enum_index is None:
                        sub_element = None
                    else:
                        sub_element = self.Element_from_field_value(block_animated_parameters, "type", enum_index)
                        if sub_element and (v == 1 or v == 0):
                            block_animated_parameters.RemoveElement(sub_element.ElementIndex)
                            continue

                    if sub_element is None:
                        if v == 1 or v == 0: continue
                        new = True
                        sub_element = block_animated_parameters.AddElement()
                        self.Element_set_field_value(sub_element, "type", k)

                    field_animation_function = sub_element.SelectField("animation function")
                    self.set_custom_function_values(field_animation_function, new, k, v)

    def set_custom_function_values(self, element, new, k, v):
        Value = element.Value
        if k == 'color':
            if new:
                Value.ColorGraphType = managed_blam.Halo.Tags.FunctionEditorColorGraphType(2) # Sets 2-color
            new_color = self.GameColor_from_RGB(*v)
            Value.SetColor(0, new_color)
            Value.SetColor(1, new_color)
        else:
            Value.ClampRangeMin = v
        if new:
            Value.MasterType = managed_blam.Halo.Tags.FunctionEditorMasterType(0) # basic type

    def material_tag_edit(self, tag):
        reference_material_shader = tag.SelectField("Reference:material shader")
        if self.linked_to_blender:
            if self.custom:
                reference_material_shader.Reference.Path = global_material_shader.tag_path
        else:
            reference_material_shader.Reference.Path = self.TagPath_from_string(self.shader_type) if self.shader_type else self.TagPath_from_string(self.find_best_material_shader())
            return
        
        block_material_parameters = tag.SelectField("Block:material parameters")
        if self.custom:
            self.custom_material(block_material_parameters, self.group_node, global_material_shader.parameters)
        else:
            self.basic_material(block_material_parameters, reference_material_shader.Reference)

            # H4 is wierd. Function values get updated automatically when the real and vector values are set
            # Key:
            # real = scale u
            # vector[0] = scale v
            # vector[1] = offset u
            # vector[2] = offset v

            #field_animation_function = sub_element.SelectField("Custom:function")
            #value = field_animation_function.Value
            # Have to set the bitmap vector temporarily for some reason...
            # self.Element_set_field_value(element, "real", str(v))
            # self.Element_set_field_value(element, "vector", [str(v), str(v), str(v)])
            # value.ClampRangeMin = v
            # if new:
            #     value.MasterType = self.Bungie.Tags.FunctionEditorMasterType(0) # basic type

    def custom_material(self, block_material_parameters, group_node, material_shader):
        material_parameters = {}
        input_parameter_pairings = {}
        inputs = group_node.inputs
        cull_chars = list(" _-()'\"")
        for i in inputs:
            for parameter_name, value in material_shader.items():
                parameter_name_culled = remove_chars(parameter_name.lower(), cull_chars)
                display_name = remove_chars(value[0].lower(), cull_chars)
                input_name = remove_chars(i.name.lower(), cull_chars)
                parameter_type = value[1]
                if input_name == parameter_name_culled or input_name == display_name:
                    input_parameter_pairings[i] = [parameter_name, parameter_type]

        for i, value in input_parameter_pairings.items():
            name = value[0]
            type = value[1]
            material_parameters[name] = self.parameters_element_dict(i, name, type)

        for name, element_dict in material_parameters.items():
            element = self.Element_create_if_needed(block_material_parameters, "parameter name", name)
            self.Element_set_field_values(element, element_dict)
            if self.Element_get_field_value(element, "bitmap flags") == "0":
                self.Element_set_field_value(element, "bitmap flags", "1") # sets override
                self.Element_set_field_value(element, "bitmap filter mode", "6") # sets anisotropic (4) EXPENSIVE
            # Handle function parameters
            current_type = element_dict['parameter type']
            func_block = element.SelectField("function parameters")
            if current_type == 0:
                self.new_func_param(func_block, 3, float(element_dict.get('real', 0)))
                self.new_func_param(func_block, 4, float(element_dict.get('vector', [0,0,0])[0]))
                self.new_func_param(func_block, 5, float(element_dict.get('vector', [0,0,0])[1]))
                self.new_func_param(func_block, 6, float(element_dict.get('vector', [0,0,0])[2]))

            elif current_type == 4:
                if element_dict.get('color', 0):
                    a = float(element_dict['color'][0])
                    r = float(element_dict['color'][1])
                    g = float(element_dict['color'][2])
                    b = float(element_dict['color'][3])
                    self.new_func_param(func_block, 1, [a, r, g, b])
                else:
                    self.new_func_param(func_block, 1, 0)
            elif current_type == 1:
                self.new_func_param(func_block, 0, float(element_dict.get('real', 0)))

    def new_func_param(self, func_block, type_int, value):
        if value:
            func_element, new = self.Element_create_if_needed_and_confirm(func_block, "type", type_int)
            type_field = func_element.SelectField("type")
            type_field.Value = type_int
            func_field = func_element.SelectField("function")
            if type_int == 1:
                if new:
                    func_field.Value.ColorGraphType = managed_blam.Halo.Tags.FunctionEditorColorGraphType(2) # Sets 2-color
                func_field.Value.SetColor(0, self.GameColor_from_ARGB(*value))
                func_field.Value.SetColor(1, self.GameColor_from_ARGB(*value))
            else:
                func_field.Value.ClampRangeMin = value
            if new:
                func_field.Value.MasterType = managed_blam.Halo.Tags.FunctionEditorMasterType(0)
        else:
            self.Element_remove_if_needed(func_block, "type", type_int)


    def parameters_element_dict(self, input, name, type):
        new_dict = {}
        new_dict['parameter name'] = name
        new_dict['parameter type'] = type
        if type == 0: # bitmap
            image_node, group_node = self.image_node_from_input(input)
            if image_node:
                bitmap = self.get_bitmap(image_node)
                if bitmap:
                    new_dict['bitmap'] = bitmap
                else:
                    new_dict['bitmap'] = ""
                mapping = self.get_mapping_as_corinth_dict(image_node, group_node)
                if mapping:
                    if mapping.get('scatran', 0):
                        new_dict['real'] = mapping['scale u']
                        new_dict['vector'] = mapping['scatran']
                    else:
                        new_dict['real'] = mapping['scale u']
                        new_dict['vector'] = [mapping['scale v'], "0", "0"]
            else:
                new_dict['bitmap'] = ""

        elif type == 1: # real
            real = str(input.default_value)
            new_dict['real'] = real
        elif type == 2: # int
            int_value = str(int(input.default_value))
            new_dict['int/bool'] = int_value
        elif type == 3: # bool
            bool_value = str(int(bool(input.default_value,0)))
            new_dict['int/bool'] = bool_value
        elif type == 4: # color
            r = input.default_value[0]
            g = input.default_value[1]
            b = input.default_value[2]
            a = input.default_value[3]
            # new_dict['color'] = self.GameColor_from_ARGB(a, r, g, b)
            new_dict['color'] = [str(a), str(r), str(g), str(b)]

        return new_dict

    def image_node_from_input(self, input):
        group_node = None
        links = input.links
        if not links:
            return None, None
        node = links[0].from_node
        if node.type == "TEX_IMAGE":
            return node, group_node
        elif node.type == 'GROUP':
            found_image_node, group_node = self.find_image_node_in_chain(node, links[0].from_socket.name)
        else:
            found_image_node, group_node = self.find_image_node_in_chain(node, input.name)
        if found_image_node:
            return found_image_node, group_node
        
    # def default_value_node_from_input(self, input):
    #     group_node = None
    #     links = input.links
    #     if not links:
    #         return input.default_value, None
    #     node = links[0].from_node
    #     if node.type == 'GROUP':
    #         found_node, group_node = self.find_default_value_in_chain(node, links[0].from_socket.name)
    #     else:
    #         found_node, group_node = self.find_default_value_in_chain(node, input.name)
    #     if found_node:
    #         return found_node, group_node
        
    # def find_default_value_in_chain(self, node, group_output_input=None, group_node=None):
    #     if node.type == 'TEX_IMAGE':
    #         return node, group_node
        
    #     elif node.type == 'GROUP':
    #         group_nodes = node.node_tree.nodes
    #         for n in group_nodes:
    #             if n.type == 'GROUP_OUTPUT':
    #                 for i in n.inputs:
    #                     if i.name == group_output_input:
    #                         links = i.links
    #                         if links:
    #                             for l in links:
    #                                 new_node = l.from_node
    #                                 group_image, group_node = self.find_image_node_in_chain(new_node, group_output_input, group_node=node)
    #                                 if group_image:
    #                                     return group_image, group_node
    #                                 break
    #                 break
        
    #     for input in node.inputs:
    #         for link in input.links:
    #             next_node = link.from_node
    #             if next_node.type == 'GROUP':
    #                 tex_image_node, group_node = self.find_image_node_in_chain(next_node, link.from_socket.name, group_node=node)
    #             else:
    #                 tex_image_node, group_node = self.find_image_node_in_chain(next_node, group_output_input)
    #             if tex_image_node:
    #                 return tex_image_node, group_node
        
    #     return None, None

    def get_mapping_as_corinth_dict(self, image_node, group_node):
        mapping = {}
        links = image_node.inputs[0].links
        if not links:
            return
        node = links[0].from_node
        mapping_node = self.find_mapping_node_in_chain(node, links[0].from_socket, last_group_node=group_node, previous_node=image_node)
        if not mapping_node:
            return
        
        if mapping_node.type == 'MAPPING':
            mapping['scale u'] = str(mapping_node.inputs[3].default_value[0])
            mapping['scatran'] = [str(mapping_node.inputs[3].default_value[1]), str(mapping_node.inputs[1].default_value[0]), str(mapping_node.inputs[1].default_value[1])]
        else:
            mapping['scale u'] = str(mapping_node.inputs[1].default_value * mapping_node.inputs[0].default_value)
            mapping['scale v'] = str(mapping_node.inputs[2].default_value * mapping_node.inputs[0].default_value)

        return mapping
    
    def find_mapping_node_in_chain(self, node, group_output_input, last_group_node=None, previous_node=None, out_group_node=False):
        if not out_group_node:
            if node.type == 'MAPPING':
                return node
            elif node.type == "GROUP":
                if node.node_tree.name == "Texture Tiling":
                    return node
                group_nodes = node.node_tree.nodes
                for n in group_nodes:
                    if n.type == 'GROUP_OUTPUT':
                        for i in n.inputs:
                            if i.name == group_output_input:
                                links = i.links
                                if links:
                                    for l in links:
                                        new_node = l.from_node
                                        group_node = self.find_mapping_node_in_chain(new_node, group_output_input, last_group_node=node, previous_node=node)
                                        if group_node:
                                            return group_node
                                        break
                        break

            elif node.type == "GROUP_INPUT":
                for output in node.outputs:
                    for link in output.links:
                        if link.to_node == previous_node:
                            mapping_node_maybe = self.find_mapping_node_in_chain(last_group_node, output, last_group_node=last_group_node, previous_node=previous_node, out_group_node=True)
                            if mapping_node_maybe:
                                return mapping_node_maybe
            
        for input in node.inputs:
            if out_group_node:
                if group_output_input.name != input.name:
                    continue
            for link in input.links:
                next_node = link.from_node
                if next_node.type == 'GROUP':
                    if next_node.node_tree.name == "Texture Tiling":
                        return next_node
                    new_node = self.find_mapping_node_in_chain(next_node, link.from_socket.name, last_group_node=node)
                else:
                    new_node = self.find_mapping_node_in_chain(next_node, group_output_input, last_group_node=last_group_node, previous_node=node)
                if new_node:
                    return new_node
                
        return
        

    def basic_material(self, block_material_parameters, material_shader_path):
        maps = self.get_maps()
        if not maps:
            return print("Cannot read Blender Material Nodes into tag, created empty tag instead. Blender Material does not have a valid custom node group connected to the material output or does not have a BSDF node connected to the material output")
        if self.shader_type and os.path.exists(self.tags_dir + self.shader_type):
            material_shader_path.Path = self.TagPath_from_string(self.shader_type)
        else:
            material_shader_path.Path = self.TagPath_from_string(self.find_best_material_shader())
        # Set albedo to default
        # if not hasattr(self, "has_diffuse"):
        #     diffuse_element = self.Element_from_field_value(block_material_parameters, "parameter name", 'color_map')
        #     if diffuse_element:
        #         block_material_parameters.RemoveElement(diffuse_element.ElementIndex)
        # if not hasattr(self, "has_specular") and not hasattr(self, "specular_from_diff_alpha"):
        #     specular_element = self.Element_from_field_value(block_material_parameters, "parameter name", 'specular_map')
        #     if specular_element:
        #         block_material_parameters.RemoveElement(diffuse_element.ElementIndex)
        # if not hasattr(self, "has_albedo"):
        #     albedo_element = self.Element_from_field_value(block_material_parameters, "parameter name", 'albedo_tint')
        #     if albedo_element:
        #         block_material_parameters.RemoveElement(albedo_element.ElementIndex)
        # # Set bump_mapping to standard
        # if not hasattr(self, "has_normal"):
        #     normal_element = self.Element_from_field_value(block_material_parameters, "parameter name", 'normal_map')
        #     if normal_element:
        #         block_material_parameters.RemoveElement(normal_element.ElementIndex)
        for m in maps:
            sub_map = m['function parameters']
            m.pop('function parameters')
            element = self.Element_create_if_needed(block_material_parameters, "parameter name", m['parameter name'])
            if self.Element_get_field_value(element, "bitmap flags") == "0":
                self.Element_set_field_value(element, "bitmap flags", "1") # sets override
                self.Element_set_field_value(element, "bitmap filter mode", "6") # sets anisotropic (4) EXPENSIVE

            self.Element_set_field_values(element, m)

            if not sub_map: continue
            block_function_parameters = element.SelectField("function parameters")
            to_strip = []
            for k, v in sub_map.items():
                new = False
                enum_index = self.EnumIntValue(block_function_parameters, "type", k)
                if enum_index is None:
                    sub_element = None
                else:
                    sub_element = self.Element_from_field_value(block_function_parameters, "type", enum_index)
                    if sub_element and (v == 1 or v == 0):
                        block_function_parameters.RemoveElement(sub_element.ElementIndex)
                        continue

                if sub_element is None:
                    if v == 1 or v == 0: continue
                    new = True
                    sub_element = block_function_parameters.AddElement()
                    self.Element_set_field_value(sub_element, "type", k)

                field_animation_function = sub_element.SelectField("function")
                self.set_custom_function_values(field_animation_function, new, k, v)

                to_strip.append(k)

            if k == 'color':
                color_field = element.SelectField("color")
                color_field.SetStringData(self.corinth_extra_mapping['color'])
            else:
                self.Element_set_field_values(element, self.corinth_extra_mapping)

    def find_best_material_shader(self):
        if hasattr(self, "specular_from_diff_alpha"):
            return r"shaders\material_shaders\materials\srf_ca_blinn_diffspec.material_shader"
        return r"shaders\material_shaders\materials\srf_blinn.material_shader"

    def get_maps(self):
        maps = []
        node_tree = bpy.data.materials[self.blender_material].node_tree
        shader_node = self.get_blender_shader(node_tree)
        if not shader_node:
            return
        diffuse_map = self.get_diffuse_map(shader_node)
        if diffuse_map:
            maps.append(diffuse_map)
        specular_map = self.get_specular_map(shader_node)
        if specular_map and not hasattr(self, "specular_from_diff_alpha"):
            maps.append(specular_map)
        normal_map = self.get_normal_map(shader_node)
        if normal_map:
            maps.append(normal_map)
        albedo_tint = self.get_albedo_tint(shader_node)
        if albedo_tint:
            maps.append(albedo_tint)

        return maps

    def get_blender_shader(self, node_tree):
        output = None
        shaders = []
        for node in node_tree.nodes:
            if node.type == "OUTPUT_MATERIAL":
                output = node
            elif node.type.startswith("BSDF"):
                shaders.append(node)
        # Get the shader plugged into the output
        if output is None:
            #print("Material has no output")
            return
        for s in shaders:
            outputs = s.outputs
            if not outputs:
                return
            links = outputs[0].links
            if not links:
                return
            if links[0].to_node == output:
                return s
        else:
            #print("No shader found connected to output")
            return

    def get_diffuse_map(self, shader):
        diffuse_map = {}
        diffuse_map['parameter name'] = 'color_map' if self.corinth else 'base_map'
        diffuse_map['parameter type'] = "bitmap"
        image_node = self.get_image_node(shader, "color")
        if image_node is None:
            return #print("Node is not image node")
        
        bitmap = self.get_bitmap(image_node)
        if bitmap is None:
            return #print("No bitmap found")

        diffuse_map['bitmap'] = bitmap
        # Check for mapping node
        if self.corinth:
            diffuse_map['function parameters'] = self.get_node_mapping(image_node)
        else:
            diffuse_map['animated parameters'] = self.get_node_mapping(image_node)
        self.has_diffuse = True
        return diffuse_map
    
    def get_specular_map(self, shader):
        specular_map = {}
        specular_map['parameter name'] = 'color_map' if self.corinth else 'base_map'
        specular_map['parameter type'] = "bitmap"
        image_node = self.get_image_node(shader, "specular")
        if image_node is None:
            return #print("Node is not image node")
        
        bitmap = self.get_bitmap(image_node)
        if bitmap is None:
            return #print("No bitmap found")

        specular_map['bitmap'] = bitmap
        # Check for mapping node
        if self.corinth:
            specular_map['function parameters'] = self.get_node_mapping(image_node)
        else:
            specular_map['animated parameters'] = self.get_node_mapping(image_node)
        self.has_specular = True
        return specular_map

    def get_normal_map(self, shader):
        normal_map = {}
        normal_map['parameter name'] = 'normal_map' if self.corinth else 'bump_map'
        normal_map['parameter type'] = "bitmap"
        image_node = self.get_image_node(shader, "normal")
        if image_node is None:
            return #print("Node is not image node")
        
        bitmap = self.get_bitmap(image_node)
        if bitmap is None:
            return #print("No bitmap found")

        normal_map['bitmap'] = bitmap
        # Check for mapping node
        if self.corinth:
            normal_map['function parameters'] = self.get_node_mapping(image_node)
        else:
            normal_map['animated parameters'] = self.get_node_mapping(image_node)
        self.has_normal = True
        return normal_map
    
    def get_albedo_tint(self, shader):
        albedo_tint = {}
        albedo_tint['parameter name'] = 'albedo_tint' if self.corinth else 'albedo_color'
        albedo_tint['parameter type'] = "color" if self.corinth else "argb color"
        tint_parameters = {}
        color = self.get_default_color(shader, "color")
        if color is None: return
        if self.corinth:
            tint_parameters['color'] = color[:3]
        else:
            tint_parameters['color'] = color[:3]
            tint_parameters['alpha'] = color[3]
        if self.corinth:
            albedo_tint['function parameters'] = tint_parameters
        else:
            albedo_tint['animated parameters'] = tint_parameters
        if self.corinth:
            self.corinth_extra_mapping = {}
            self.corinth_extra_mapping['color'] = [str(color[3]), str(color[0]), str(color[1]), str(color[2])]
        self.has_albedo = True
        return albedo_tint


    def get_default_color(self, shader, input_name):
        for i in shader.inputs:
            if input_name in i.name.lower():
                if not i.links:
                    return i.default_value

    def get_node_mapping(self, node):
        bitmap_mapping = {}
        self.corinth_extra_mapping = {}
        links = node.inputs['Vector'].links
        if not links: return
        scale_node = links[0].from_node
        if scale_node.type == 'MAPPING':
            sca_x = scale_node.inputs['Scale'].default_value.x
            sca_y = scale_node.inputs['Scale'].default_value.y
            loc_x = scale_node.inputs['Location'].default_value.x #* self.unit_scale
            loc_y = scale_node.inputs['Location'].default_value.y #* self.unit_scale
            if self.corinth:
                self.corinth_extra_mapping['real'] = str(sca_x)
                self.corinth_extra_mapping['vector'] = [str(sca_y), str(loc_x), str(loc_y)]
                bitmap_mapping['scale u'] = sca_x
                bitmap_mapping['scale v'] = sca_y
                bitmap_mapping['offset u'] = loc_x
                bitmap_mapping['offset v'] = loc_y
            else:
                bitmap_mapping['scale x'] = sca_x
                bitmap_mapping['scale y'] = sca_y
                bitmap_mapping['translation x'] = loc_x
                bitmap_mapping['translation y'] = loc_y
        elif is_halo_node(scale_node, HALO_SCALE_NODE):
            sca_x = scale_node.inputs['Scale X'].default_value
            sca_y = scale_node.inputs['Scale Y'].default_value
            if self.corinth:
                self.corinth_extra_mapping['real'] = str(sca_x)
                self.corinth_extra_mapping['vector'] = [str(sca_y), 0, 0]
                bitmap_mapping['scale u'] = sca_x
                bitmap_mapping['scale v'] = sca_y
            else:
                bitmap_mapping['scale uniform'] = scale_node.inputs['Scale Multiplier'].default_value
                bitmap_mapping['scale x'] = sca_x
                bitmap_mapping['scale y'] = sca_y

        return bitmap_mapping

    def get_bitmap(self, node):
        image = node.image
        if not image:
            return
        nwo = image.nwo
        if nwo.filepath:
            bitmap = dot_partition(nwo.filepath) + ".bitmap"
            if os.path.exists(self.tags_dir + bitmap):
                return bitmap
            
        if image.filepath and os.path.exists(image.filepath_from_user()):
            bitmap = dot_partition(image.filepath_from_user().replace(self.data_dir, "")) + ".bitmap"
            if os.path.exists(self.tags_dir + bitmap):
                return bitmap

        bitmap = export_bitmap(image)
        if not bitmap:
            return None
        if os.path.exists(self.tags_dir + bitmap):
            return bitmap
        
    def get_image_node(self, shader, input_name):
        for i in shader.inputs:
            if input_name in i.name.lower():
                if i.links:
                    tex_input = i
                    break
                else:
                    return
        else:
            return
        
        node, _ = self.find_image_node_in_chain(tex_input.links[0].from_node)
        if node:
            if input_name == "specular" and tex_input.links[0].from_socket.name == "Alpha":
                self.specular_from_diff_alpha = True
            return node
        
    def find_image_node_in_chain(self, node, group_output_input=None, group_node=None):
        if node.type == 'TEX_IMAGE':
            return node, group_node
        
        elif node.type == 'GROUP':
            group_nodes = node.node_tree.nodes
            for n in group_nodes:
                if n.type == 'GROUP_OUTPUT':
                    for i in n.inputs:
                        if i.name == group_output_input:
                            links = i.links
                            if links:
                                for l in links:
                                    new_node = l.from_node
                                    group_image, group_node = self.find_image_node_in_chain(new_node, group_output_input, group_node=node)
                                    if group_image:
                                        return group_image, group_node
                                    break
                    break
        
        for input in node.inputs:
            for link in input.links:
                next_node = link.from_node
                if next_node.type == 'GROUP':
                    tex_image_node, group_node = self.find_image_node_in_chain(next_node, link.from_socket.name, group_node=node)
                else:
                    tex_image_node, group_node = self.find_image_node_in_chain(next_node, group_output_input)
                if tex_image_node:
                    return tex_image_node, group_node
        
        return None, None


    def element_dict_from_input(self, input, dict_value):
        """Returns a dict representing a Element using the given input"""
        element_dict = {}
        element_dict['parameter name'] = dict_value[0]
        type = dict_value[1]
        element_dict['parameter type'] = type
        if len(dict_value) > 2:
            value_method = dict_value[2]
            return self.new_dict_from_special_method(value_method, dict_value)
        
        if type == 'bitmap':
            element_dict['bitmap'] = self.bitmap_from_input(input)
        elif type == 'color':
            element_dict['color'] = self.GameColor_from_input(input)
        elif type == 'real':
            element_dict['real'] = self.Real_from_input(input)


# OPTIONS MAPPING
#################

# INDEXES
enum_albedo = 0
enum_bump_mapping = 1
enum_alpha_test = 2
enum_material_model = 3
enum_environment_mapping = 4
enum_self_illumination = 5
enum_blend_mode = 6
enum_parallax = 7
enum_misc = 8
enum_wetness = 9
enum_alpha_blend_source = 10

# ALBEDO
enum_albedo_default = 0
enum_albedo_detail_blend = 1
enum_albedo_constant_color = 2
enum_albedo_two_change_color = 3
enum_albedo_four_change_color = 4
enum_albedo_three_detail_blend = 5
enum_albedo_two_detail_overlay = 6
enum_albedo_two_detail = 7
enum_albedo_color_mask = 8
enum_albedo_two_detail_black_point = 9
enum_albedo_four_change_color_applying_to_specular = 10
enum_albedo_simple = 11

# BUMP MAPPING
enum_bump_mapping_off = 0
enum_bump_mapping_standard = 1
enum_bump_mapping_detail = 2
enum_bump_mapping_detail_blend = 3
enum_bump_mapping_three_detail_blend = 4
enum_bump_mapping_standard_wrinkle = 5
enum_bump_mapping_detail_wrinkle = 6

# ALPHA TEST
enum_alpha_test_none = 0
enum_alpha_test_simple = 1

# SPECULAR MASK
enum_specular_mask_no_specular_mask = 0
enum_specular_mask_specular_mask_from_diffuse = 1
enum_specular_mask_specular_mask_mult_diffuse = 2
enum_specular_mask_specular_mask_from_texture = 3

# MATERIAL MODEL
enum_material_model_diffuse_only = 0
enum_material_model_cook_torrance = 1
enum_material_model_two_lobe_phong = 2
enum_material_model_foliage = 3
enum_material_model_none = 4
enum_material_model_organism = 5
enum_material_model_hair = 6

# ENVIRONMENT MAPPING
enum_environment_mapping_none = 0
enum_environment_mapping_per_pixel = 1
enum_environment_mapping_dynamic = 2
enum_environment_mapping_from_flat_texture = 3

# SELF ILLUMINATION
enum_self_illumination_off = 0
enum_self_illumination_simple = 1
enum_self_illumination_3_channel_self_illum = 2
enum_self_illumination_plasma = 3
enum_self_illumination_from_diffuse = 4
enum_self_illumination_illum_detail = 5
enum_self_illumination_meter = 6
enum_self_illumination_self_illum_times_diffuse = 7
enum_self_illumination_simple_with_alpha_mask = 8
enum_self_illumination_multilayer_additive = 9
enum_self_illumination_palettized_plasma = 10
enum_self_illumination_change_color = 11
enum_self_illumination_change_color_detail = 12

# BLEND MODE
enum_blend_mode_opaque = 0
enum_blend_mode_additive = 1
enum_blend_mode_multiply = 2
enum_blend_mode_alpha_blend = 3
enum_blend_mode_double_multiply = 4
enum_blend_mode_pre_multiplied_alpha = 5

# PARALLAX
enum_parallax_off = 0
enum_parallax_simple = 1
enum_parallax_interpolated = 2
enum_parallax_simple_detail = 3

# MISC
enum_misc_default = 0
enum_misc_rotating_bitmaps_super_slow = 1

# WETNESS
enum_wetness_default = 0
enum_wetness_flood = 0
enum_wetness_proof = 0
enum_wetness_simple = 0
enum_wetness_ripples = 0

# ALPHA BLEND SOURCE
enum_alpha_blend_source_from_albedo_alpha_without_fresnel = 0
enum_alpha_blend_source_from_albedo_alpha = 1
enum_alpha_blend_source_from_opacity_map_alpha = 2
enum_alpha_blend_source_from_opacity_map_rgb = 3
enum_alpha_blend_source_from_opacity_map_alpha_and_albedo_alpha = 4
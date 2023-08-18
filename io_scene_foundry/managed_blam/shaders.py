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
from io_scene_foundry.tools.export_bitmaps import export_bitmaps
from io_scene_foundry.utils.nwo_utils import dot_partition, get_asset_path, get_valid_shader_name, is_halo_node
import os
import bpy

HALO_SCALE_NODE = ['Scale Multiplier', 'Scale X', 'Scale Y']

class ManagedBlamReadMaterialShader(managed_blam.ManagedBlam):
    def __init__(self, group_node):
        super().__init__()
        self.read_only = True
        self.group_node = group_node
        self.parameters = {}
        self.tag_helper()

    def get_path(self):
        material_shader_name = self.group_node.node_tree.name
        # Check \shaders\ for the given material_shader
        shaders_dir = os.path.join(self.tags_dir, "shaders")
        for root, _, files in os.walk(shaders_dir):
            for file in files:
                if file.endswith("material_shader"):
                    if dot_partition(file) == material_shader_name:
                        return os.path.join(root, file).replace(self.tags_dir, "")
        
        return print(f"No material shader found in tags\shaders\... named {material_shader_name}")

    def tag_read(self, tag):
        block_material_parameters = tag.SelectField("Block:material parameters")
        elements = block_material_parameters.Elements
        for e in elements:
            self.parameters[self.Element_get_field_value(e, "parameter name")] = [
                self.Element_get_field_value(e, "display name"),
                self.Element_get_field_value(e, "parameter type"),
            ]

class ManagedBlamNewShader(managed_blam.ManagedBlam):
    def __init__(self, blender_material, shader_type, linked_to_blender, specified_path=""):
        super().__init__()
        self.blender_material = blender_material
        self.shader_type = shader_type
        self.linked_to_blender = linked_to_blender
        self.group_node = self.blender_halo_material()
        self.custom = False
        self.specified_path = specified_path if specified_path and os.path.exists(self.tags_dir + specified_path) else None
        if linked_to_blender and self.group_node:
            self.material_shader = ManagedBlamReadMaterialShader(self.group_node)
            self.custom = bool(getattr(self.material_shader, "tag_path", 0))
        self.tag_helper()

    def get_path(self):
        if self.specified_path:
            return self.specified_path
        shaders_dir = os.path.join(self.asset_dir, "materials" if self.corinth else "shaders")
        shader_name = get_valid_shader_name(self.blender_material)
        tag_ext = ".material" if self.corinth else self.shader_type
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
        if not self.shader_type:
            self.shader_type = self.find_best_material_shader()
        reference_material_shader = tag.SelectField("Reference:material shader")
        reference_material_shader.Reference.Path = self.material_shader.tag_path if self.custom else self.TagPath_from_string(self.shader_type)
        if not self.linked_to_blender:
            return
        block_material_parameters = tag.SelectField("Block:material parameters")
        if self.custom:
            self.custom_material(block_material_parameters, self.group_node, self.material_shader.parameters)
        else:
            self.basic_material(block_material_parameters)

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
        for i in inputs:
            for parameter_name, value in material_shader.items():
                display_name = value[0]
                parameter_type = value[1]
                if i.name == parameter_name or i.name == display_name:
                    input_parameter_pairings[i] = [parameter_name, parameter_type]

        for i, value in input_parameter_pairings.items():
            name = value[0]
            type = value[1]
            material_parameters[name] = self.parameters_element_dict(i, name, type)

        for name, element_dict in material_parameters.items():
            element = self.Element_create_if_needed(block_material_parameters, "parameter name", name)
            if hasattr(element_dict, "color"):
                # Clearing the function block in this case, as this way the color value is taken from the material parameter color field
                self.clear_block(element, "function parameters")

            self.Element_set_field_values(element, element_dict)

    def parameters_element_dict(self, input, name, type):
        new_dict = {}
        new_dict['parameter name'] = name
        new_dict['parameter type'] = type
        if type == 0: # bitmap
            image_node = self.image_node_from_input(input)
            if image_node:
                bitmap = self.get_bitmap(image_node)
                if bitmap:
                    new_dict['bitmap'] = bitmap
                mapping = self.get_mapping_as_corinth_dict(image_node)
                if mapping:
                    new_dict['real'] = mapping['scale u']
                    new_dict['vector'] = mapping['scatran']
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
        links = input.links
        if not links:
            return
        node = links[0].from_node
        if node.type == "TEX_IMAGE":
            return node

    def get_mapping_as_corinth_dict(self, image_node):
        mapping = {}
        links = image_node.inputs[0].links
        if not links:
            return
        mapping_node = links[0].from_node
        if mapping_node.type != 'MAPPING':
            return
        mapping['scale u'] = str(mapping_node.inputs[3].default_value[0])
        mapping['scatran'] = [str(mapping_node.inputs[3].default_value[1]), str(mapping_node.inputs[2].default_value[0]), str(mapping_node.inputs[2].default_value[1])]
        

    def basic_material(self, block_material_parameters):
        maps = self.get_maps()
        if not maps:
            return print("Cannot read Blender Material Nodes into tag, created empty tag instead. Blender Material does not have a valid custom node group connected to the material output or does not have a BSDF node connected to the material output")
        # Set albedo to default
        if not hasattr(self, "has_diffuse"):
            diffuse_element = self.Element_from_field_value(block_material_parameters, "parameter name", 'color_map')
            if diffuse_element:
                block_material_parameters.RemoveElement(diffuse_element.ElementIndex)
        if not hasattr(self, "has_albedo"):
            albedo_element = self.Element_from_field_value(block_material_parameters, "parameter name", 'albedo_tint')
            if albedo_element:
                block_material_parameters.RemoveElement(albedo_element.ElementIndex)
        # Set bump_mapping to standard
        if not hasattr(self, "has_normal"):
            normal_element = self.Element_from_field_value(block_material_parameters, "parameter name", 'normal_map')
            if normal_element:
                block_material_parameters.RemoveElement(normal_element.ElementIndex)
        for m in maps:
            sub_map = m['function parameters']
            m.pop('function parameters')
            element = self.Element_from_field_value(block_material_parameters, "parameter name", m['parameter name'])
            if element is None:
                element = block_material_parameters.AddElement()
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
        return r"shaders\material_shaders\materials\srf_ward.material_shader"

    def get_maps(self):
        maps = []
        node_tree = bpy.data.materials[self.blender_material].node_tree
        shader_node = self.get_blender_shader(node_tree)
        if not shader_node:
            return
        diffuse_map = self.get_diffuse_map(shader_node)
        if diffuse_map:
            maps.append(diffuse_map)
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
            if s.outputs[0].links[0].to_node == output:
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
        if nwo.filepath and os.path.exists(self.tags_dir + nwo.filepath):
            bitmap = dot_partition(nwo.filepath) + ".bitmap"
            if os.path.exists(self.tags_dir + bitmap):
                return bitmap
            
        if image.filepath and os.path.exists(self.tags_dir + image.filepath):
            bitmap = dot_partition(image.filepath_from_user().replace(self.data_dir, "")) + ".bitmap"
            if os.path.exists(self.tags_dir + bitmap):
                return bitmap

        bitmap = export_bitmaps(None, self.context.scene.nwo_halo_launcher.sidecar_path, [image])
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
        
        node = tex_input.links[0].from_node
        if node.type == 'TEX_IMAGE':
            return node

    def get_material_parameters(self, tag):
        pass


    def build_parameters(self, values, material_parameters):
        for v in values:
            element = self.Element_create_if_needed(material_parameters, "parameter name", v['parameter name'])
            self.Element_set_field_values(element, v)
            function_parameters = self.get_function_parameters(element)

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
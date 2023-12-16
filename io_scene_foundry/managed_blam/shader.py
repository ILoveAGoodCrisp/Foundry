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

from io_scene_foundry.managed_blam import Tag
from io_scene_foundry.managed_blam.Tags import TagsNameSpace
import os
from io_scene_foundry.tools.export_bitmaps import export_bitmap
from io_scene_foundry.utils import nwo_utils
import bpy

from io_scene_foundry.managed_blam.render_method_definition import RenderMethodDefinitionTag

global_render_method_definition = None
last_group_node = None

class ShaderTag(Tag):
    tag_ext = 'shader'
    scale_u = 'scale x'
    scale_v = 'scale y'
    translation_u = 'translation x'
    translation_v = 'translation y'
    function_parameters = 'animated parameters'
    animated_function = 'animation function'
    color_parameter_type = 'argb color'
    
    def _read_fields(self):
        self.render_method = self.tag.SelectField("Struct:render_method").Elements[0]
    
    def _get_info(self):
        global global_render_method_definition
        global last_group_node
        if not global_render_method_definition or last_group_node != self.group_node:
            last_group_node = self.group_node
            with RenderMethodDefinitionTag() as render_method_definition:
                global_render_method_definition = render_method_definition.get_categories()
    
    def write_tag(self, blender_material, linked_to_blender, material_shader=''):
        self.blender_material = blender_material
        self.material_shader = material_shader
        def _get_group_node(blender_material):
            """Gets a group node from a blender material node tree if one exists and it plugged into the output node"""
            tree = self.blender_material.node_tree
            if tree is None:
                return None
            nodes = tree.nodes
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
        self.group_node = _get_group_node(blender_material)
        # TODO implement custom shaders for Reach. Currently forcing custom off if reach
        self.custom = True if self.group_node and self.corinth else False
        if linked_to_blender:
            self._edit_tag()
            
        return self.tag.Path.RelativePathWithExtension
        
    def _edit_tag(self):
        if self.custom:
            self._get_info()
            self._build_custom()
        else:
            def get_basic_mapping(blender_material):
                """Maps all the important parts we need from a blender material node tree to generate a basic shader"""
                maps = {}
                node_tree = blender_material.node_tree
                if node_tree and node_tree.nodes:
                    shader_node = nwo_utils.get_blender_shader(node_tree)
                    if not shader_node:
                        albedo_tint = nwo_utils.get_material_albedo(blender_material)
                        if albedo_tint:
                            maps['albedo_tint'] = albedo_tint
                        return maps
                    diffuse = nwo_utils.find_linked_node(shader_node, 'base color', 'TEX_IMAGE')
                    if diffuse:
                        maps['diffuse'] = diffuse
                    specular = nwo_utils.find_linked_node(shader_node, 'specular ior level', 'TEX_IMAGE')
                    if specular:
                        maps['specular'] = specular
                    normal = nwo_utils.find_linked_node(shader_node, 'normal', 'TEX_IMAGE')
                    if normal:
                        maps['normal'] = normal
                    if diffuse is None:
                        albedo_tint = nwo_utils.get_material_albedo(shader_node)
                        if albedo_tint:
                            maps['albedo_tint'] = albedo_tint
                        
                return maps
            self._build_basic(get_basic_mapping(self.blender_material))
        
        self.tag_has_changes = True
            
    def _build_basic(self, map):
        block_options = self.render_method.SelectField('options')
        albedo = block_options.Elements[0].SelectField('short')
        bump_mapping = block_options.Elements[1].SelectField('short')
        alpha_test = block_options.Elements[2].SelectField('short')
        specular_mask = block_options.Elements[3].SelectField('short')
        # Set up shader parameters
        self.block_parameters = self.render_method.SelectField("parameters")
        spec_alpha_from_diffuse = False
        if map.get('diffuse', 0):
            if int(albedo.GetStringData()) == 2 or int(albedo.GetStringData()) == -1: # if is constant color or none
                albedo.SetStringData('0') # sets default
            element = self._setup_parameter(map['diffuse'], 'base_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['diffuse'], element, 'bitmap')
            diff_outputs: bpy.types.NodeInputs = map['diffuse'].outputs
            for i in diff_outputs:
                if i.links:
                    for l in i.links:
                        if l.from_socket.name.lower() == 'alpha':
                            spec_alpha_from_diffuse = True
                            break
                
        elif map.get('albedo_tint', 0):
            albedo.SetStringData('2') # constant color
            element = self._setup_parameter(map['albedo_tint'], 'albedo_color', self.color_parameter_type)
            if element:
                self._setup_function_parameters(map['albedo_tint'], element, 'color')
                
        if spec_alpha_from_diffuse:
            specular_mask.SetStringData('1') # Specular mask from diffuse
        elif map.get('specular', 0):
            specular_mask.SetStringData('3') # Specular mask from texture
            element = self._setup_parameter(map['specular'], 'specular_mask_texture', 'bitmap')
            if element:
                self._setup_function_parameters(map['specular'], element, 'bitmap')
        else:
            specular_mask.SetStringData('-1')
            
        if map.get('normal', 0):
            if int(bump_mapping.GetStringData()) < 1:
                bump_mapping.SetStringData('1') # standard
            element = self._setup_parameter(map['normal'], 'bump_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['normal'], element, 'bitmap')
        elif int(bump_mapping.GetStringData()) > 0:
            bump_mapping.SetStringData('-1') # none
            
        if self.blender_material.nwo.uses_alpha:
            alpha_test.SetStringData('1')
        else:
            alpha_test.SetStringData('-1')
          
    def _setup_parameter(self, source, parameter_name, parameter_type):
        element = self._Element_from_field_value(self.block_parameters, 'parameter name', parameter_name)
        if element is None:
            element = self.block_parameters.AddElement()
            element.SelectField('parameter name').SetStringData(parameter_name)
            element.SelectField('parameter type').SetValue(parameter_type)
        match parameter_type:
            case 'bitmap':
                bitmap_path = self._get_bitmap_path(source)
                if bitmap_path:
                    element.SelectField('bitmap flags').SetStringData('1') # sets override
                    element.SelectField('bitmap filter mode').SetStringData('6') # sets anisotropic (4) EXPENSIVE
                    element.SelectField('bitmap').Path = self._TagPath_from_string(bitmap_path)
                else:
                    element.SelectField('bitmap').Path = None
                    return 
                    
            case 'real':
                element.SelectField('real').SetStringData(str(source))
            case 'int':
                element.SelectField('int\\bool').SetStringData(str(source))
            case 'bool':
                element.SelectField('int\\bool').SetStringData(str(source))
                
        return element
    
    def _get_bitmap_path(self, node):
        if not hasattr(node, 'image'):
            return
        image = node.image
        if not image:
            return
        nwo = image.nwo
        if nwo.filepath:
            bitmap = nwo_utils.dot_partition(nwo.filepath) + ".bitmap"
            if os.path.exists(self.tags_dir + bitmap):
                return bitmap
            
        if image.filepath and os.path.exists(image.filepath_from_user()):
            bitmap = nwo_utils.dot_partition(image.filepath_from_user().replace(self.data_dir, "")) + ".bitmap"
            if os.path.exists(self.tags_dir + bitmap):
                return bitmap

        bitmap = export_bitmap(image)
        if not bitmap:
            return
        if os.path.exists(self.tags_dir + bitmap):
            return bitmap
    
    def _function_parameters_from_node(self, source, parameter_type):
        mapping = {}
        match parameter_type:
            case 'bitmap':
                links = source.inputs['Vector'].links
                if not links: return mapping
                scale_node = links[0].from_node
                if scale_node.type == 'MAPPING':
                    mapping[self.scale_u] = scale_node.inputs['Scale'].default_value.x
                    mapping[self.scale_v] = scale_node.inputs['Scale'].default_value.y
                    mapping[self.translation_u] = scale_node.inputs['Location'].default_value.x
                    mapping[self.translation_v] = scale_node.inputs['Location'].default_value.y
                elif nwo_utils.is_halo_mapping_node(scale_node):
                    factor = scale_node.inputs['Scale Multiplier'].default_value
                    mapping[self.scale_u] = scale_node.inputs['Scale X'].default_value * factor
                    mapping[self.scale_v] = scale_node.inputs['Scale Y'].default_value * factor
            case 'color':
                mapping['color'] = source

        return mapping
        
            
    def _setup_function_parameters(self, source: tuple[float] | bpy.types.Node, element: TagsNameSpace.TagElement, parameter_type: str):
        block_animated_parameters = element.SelectField(self.function_parameters)
        mapping = self._function_parameters_from_node(source, parameter_type)
        for k, v in mapping.items():
            new = False
            enum_index = self._EnumIntValue(block_animated_parameters, 'type', k)
            if enum_index is None:
                sub_element = None
            else:
                sub_element = self._Element_from_field_value(block_animated_parameters, 'type', enum_index)
                if sub_element and (v == 1 or v == 0):
                    block_animated_parameters.RemoveElement(sub_element.ElementIndex)
                    continue

            if sub_element is None:
                if v == 1 or v == 0: continue
                new = True
                sub_element = block_animated_parameters.AddElement()
                sub_element.SelectField('type').SetValue(k)

            field_animation_function = sub_element.SelectField(self.animated_function)
            value = field_animation_function.Value
            if k == 'color':
                if new:
                    value.ColorGraphType = self._FunctionEditorColorGraphType(2) # Sets 2-color
                new_color = self._GameColor_from_RGB(*v)
                value.SetColor(0, new_color)
                value.SetColor(1, new_color)
            else:
                value.ClampRangeMin = v
            if new:
                value.MasterType = self._FunctionEditorMasterType(0) # basic type
                
        return mapping
    
    def _source_from_input_and_parameter_type(self, input, parameter_type):
        input_name = input.name.lower()
        match parameter_type:
            case 'bitmap':
                return nwo_utils.find_linked_node(self.group_node, input_name, 'TEX_IMAGE')
            case 'real':
                return float(input.default_value)
            case 'int':
                return int(input.default_value)
            case 'bool':
                return int(bool(input.default_value))
            case 'color':
                return nwo_utils.get_material_albedo(self.group_node, input)
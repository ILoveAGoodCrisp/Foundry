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

from mathutils import Vector
from io_scene_foundry.managed_blam import Tag
from io_scene_foundry.managed_blam.Tags import TagsNameSpace
import os
from io_scene_foundry.managed_blam.bitmap import BitmapTag
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
        self.block_parameters = self.render_method.SelectField("parameters")
        self.block_options = self.render_method.SelectField('options')
        self.reference = self.render_method.SelectField('reference')
    
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
        albedo = self.block_options.Elements[0].SelectField('short')
        bump_mapping = self.block_options.Elements[1].SelectField('short')
        alpha_test = self.block_options.Elements[2].SelectField('short')
        specular_mask = self.block_options.Elements[3].SelectField('short')
        # Set up shader parameters
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
            
            
    # READING
    def to_nodes(self, blender_material):
        shader_path: str = blender_material.nwo.shader_path
        if shader_path.endswith('.shader'):
            self._build_nodes_basic(blender_material)
        else:
            print('Shader type not supported')
            
    def _option_value_from_index(self, index):
        option_enum = int(self.block_options.Elements[index].Fields[0].GetStringData())
        if option_enum == -1 and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                return shader._option_value_from_index(index)
        else:
            return option_enum
        
    def _mapping_from_parameter_name(self, name):
        element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        if element is None:
            if self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._mapping_from_parameter_name(name)
            else:
                return
            
        block_animated_parameters = element.SelectField(self.function_parameters)
        mapping = {}
        for e in block_animated_parameters.Elements:
            type = e.Fields[0].Value
            value = e.SelectField(self.animated_function).Value
            match type:
                case 2:
                    mapping['scale_uni'] = value.ClampRangeMin
                case 3:
                    mapping['scale_x'] = value.ClampRangeMin
                case 4:
                    mapping['scale_y'] = value.ClampRangeMin
                case 5:
                    mapping['offset_x'] = value.ClampRangeMin
                case 6:
                    mapping['offset_y'] = value.ClampRangeMin
                    
        return mapping
        
    def _image_from_parameter_name(self, name, blue_channel_fix=False):
        """Saves an image (or gets the already existing one) from a shader parameter element"""
        element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        if element is None:
            if self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._image_from_parameter_name(name)
            else:
                return
        bitmap_path = element.SelectField('bitmap').Path
        if not bitmap_path:
            return
        system_bitmap_path = self.tags_dir + bitmap_path.RelativePathWithExtension
        image_path = ''
        if not os.path.exists(system_bitmap_path):
            return
        system_tiff_path = self.data_dir + bitmap_path.RelativePath + '.tiff'
        if os.path.exists(system_tiff_path):
            image_path = system_tiff_path
        else:
            with BitmapTag(path=bitmap_path) as bitmap:
                image_path = bitmap.save_to_tiff(blue_channel_fix)
                if not image_path: return
    
        return bpy.data.images.load(filepath=image_path, check_existing=True)
    
    def _normal_type_from_parameter_name(self, name):
        if not self.corinth:
            return 'directx' # Reach normals are always directx
        element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        bitmap_path = element.SelectField('bitmap').Path
        system_bitmap_path = self.tags_dir + bitmap_path.RelativePathWithExtension
        if not os.path.exists(system_bitmap_path):
            return
        with BitmapTag(path=bitmap_path) as bitmap:
            return bitmap.normal_type()
    
    def _color_from_parameter_name(self, name):
        color = [1, 1, 1, 1]
        element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        if element is None:
            if self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._color_from_parameter_name(name)
            else:
                return
            
        block_animated_parameters = element.SelectField(self.function_parameters)
        color_element = self._Element_from_field_value(block_animated_parameters, 'type', 1)
        if color_element:
            game_color = color_element.SelectField(self.animated_function).Value.GetColor(0)
            if game_color.ColorMode == 1: # Is HSV
                game_color = game_color.ToRgb()
                
            color = [game_color.Red, game_color.Green, game_color.Blue, game_color.Alpha]
        
        return color
    
    def _build_nodes_basic(self, blender_material: bpy.types.Material):
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        # Make the BSDF and Output
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = Vector((300, 0))
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        tree.links.new(input=output.inputs[0], output=bsdf.outputs[0])
        albedo_enum = self._option_value_from_index(0)
        bump_mapping_enum = self._option_value_from_index(1)
        alpha_test = self._option_value_from_index(2)
        specular_mask_enum = self._option_value_from_index(3)
        diffuse = None
        normal = None
        specular = None
        if albedo_enum == 2:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_color'))
        else:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeTexImage', data=self._image_from_parameter_name('base_map'), mapping=self._mapping_from_parameter_name('base_map'))
            if not diffuse.data:
                diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_color'))

        if bump_mapping_enum > 0:
            normal = BSDFParameter(tree, bsdf, bsdf.inputs['Normal'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('bump_map', True), special_type=self._normal_type_from_parameter_name('bump_map'), mapping=self._mapping_from_parameter_name('bump_map'))
            if normal.data:
                normal.data.colorspace_settings.name = 'Non-Color'
            else:
                normal = None
                
        if specular_mask_enum == 3:
            specular = BSDFParameter(tree, bsdf, bsdf.inputs['Specular IOR Level'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('specular_mask_texture'), mapping=self._mapping_from_parameter_name('specular_mask_texture'))
            if specular.data:
                specular.data.colorspace_settings.name = 'Non-Color'
            else:
                specular = None
        elif specular_mask_enum > 0 and diffuse and type(diffuse.data) == bpy.types.Image:
            diffuse.special_type = 'diffspec'
            
        if diffuse:
            diffuse.build(Vector((-300, 100)))
        if normal:
            normal.build()
        if specular:
            specular.build(Vector((-300, -800)))
            
            
class BSDFParameter():
    """Representation of a Halo Shader parameter element in Blender node form"""
    tree: bpy.types.NodeTree
    main_node: bpy.types.Node
    input: bpy.types.NodeInputs
    link_node_type: str
    data: any # The data this node holds such an image or color
    default_value: any # The fallback data to set for the input if no data
    mapping: list # Mapping is [loc_x, loc_y, sca_x, sca_y]
    special_type: str # from opengl, directx, diffspec
    
    def __init__(self, tree, main_node, input, link_node_type, data=None, default_value=None, mapping=[], special_type=None):
        self.tree = tree
        self.main_node = main_node
        self.input = input
        self.link_node_type = link_node_type
        self.data = data
        self.default_value = default_value
        self.mapping = mapping
        self.special_type = special_type
        
    
    def build(self, vector=Vector((0, 0))):
        if not (self.data or self.default_value):
            print("No data and no default value")
            return
        
        output_index = 0
        data_node = self.tree.nodes.new(self.link_node_type)
        data_node.location = vector
        if self.link_node_type == 'ShaderNodeTexImage':
            data_node.image = self.data
        elif self.link_node_type == 'ShaderNodeRGB':
            data_node.outputs[0].default_value = self.data
        
        if self.special_type in ('opengl', 'directx'):
            normal_map_node = self.tree.nodes.new('ShaderNodeNormalMap')
            normal_map_node.location = Vector((-200, -400))
            self.tree.links.new(input=self.input, output=normal_map_node.outputs[0])
            if self.special_type == 'opengl':
                data_node.location.x = normal_map_node.location.x - 300
                data_node.location.y = normal_map_node.location.y
                self.tree.links.new(input=normal_map_node.inputs[1], output=data_node.outputs[0])
            else:
                combine_rgb = self.tree.nodes.new('ShaderNodeCombineColor')
                combine_rgb.location.x = normal_map_node.location.x - 200
                combine_rgb.location.y = normal_map_node.location.y
                self.tree.links.new(input=normal_map_node.inputs[1], output=combine_rgb.outputs[0])
                invert_color = self.tree.nodes.new('ShaderNodeInvert')
                invert_color.location.x = combine_rgb.location.x - 200
                invert_color.location.y = combine_rgb.location.y + 80
                self.tree.links.new(input=combine_rgb.inputs[1], output=invert_color.outputs[0])
                separate_rgb = self.tree.nodes.new('ShaderNodeSeparateColor')
                separate_rgb.location.x = invert_color.location.x - 200
                separate_rgb.location.y = combine_rgb.location.y
                self.tree.links.new(input=combine_rgb.inputs[0], output=separate_rgb.outputs[0])
                self.tree.links.new(input=invert_color.inputs[1], output=separate_rgb.outputs[1])
                self.tree.links.new(input=combine_rgb.inputs[2], output=separate_rgb.outputs[2])
                
                self.tree.links.new(input=separate_rgb.inputs[0], output=data_node.outputs[0])
                data_node.location.x = separate_rgb.location.x - 300
                data_node.location.y = separate_rgb.location.y
                
        else:
            self.tree.links.new(input=self.input, output=data_node.outputs[output_index])
            if self.special_type == 'diffspec':
                self.tree.links.new(input=self.main_node.inputs['Specular IOR Level'], output=data_node.outputs[1])
            
            
        if self.mapping:
            mapping_node = self.tree.nodes.new('ShaderNodeGroup')
            mapping_node.node_tree = nwo_utils.add_node_from_resources('Texture Tiling')
            mapping_node.location.x = data_node.location.x - 300
            mapping_node.location.y = data_node.location.y
            scale_uni = self.mapping.get('scale_uni', 0)
            if scale_uni:
                mapping_node.inputs[0].default_value = scale_uni
            scale_x = self.mapping.get('scale_x', 0)
            if scale_x:
                mapping_node.inputs[1].default_value = scale_x
            scale_y = self.mapping.get('scale_y', 0)
            if scale_y:
                mapping_node.inputs[2].default_value = scale_y
                
            self.tree.links.new(input=data_node.inputs[0], output=mapping_node.outputs[0])
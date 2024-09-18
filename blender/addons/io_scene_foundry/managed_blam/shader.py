# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
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

from pathlib import Path
from mathutils import Vector
from ..managed_blam import Tag
from ..managed_blam.Tags import TagsNameSpace
import os
from ..managed_blam.bitmap import BitmapTag
from ..tools.export_bitmaps import export_bitmap
from .. import utils
import bpy

from ..managed_blam.render_method_definition import RenderMethodDefinitionTag

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
    
    self_illum_map_names = 'meter_map', 'self_illum_map'
    
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
            if not blender_material.use_nodes:
                return None
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
        if linked_to_blender and blender_material.use_nodes:
            self._edit_tag()
        elif self.corinth and self.material_shader:
            self.tag.SelectField("Reference:material shader").Path = self._TagPath_from_string(self.material_shader)
            
        return self.tag.Path.RelativePathWithExtension
        
    def _edit_tag(self):
        self.alpha_type = self._alpha_type_from_blender_material()
        if self.custom:
            self._get_info()
            self._build_custom()
        else:
            def get_basic_mapping(blender_material):
                """Maps all the important parts we need from a blender material node tree to generate a basic shader"""
                maps = {}
                node_tree = blender_material.node_tree
                if node_tree and node_tree.nodes:
                    shader_node = utils.get_blender_shader(node_tree)
                    if not shader_node:
                        albedo_tint = utils.get_material_albedo(blender_material)
                        if albedo_tint:
                            maps['albedo_tint'] = albedo_tint
                        return maps
                    
                    maps['bsdf'] = shader_node
                    diffuse = utils.find_linked_node(shader_node, 'base color', 'TEX_IMAGE')
                    if diffuse:
                        maps['diffuse'] = diffuse
                    specular = utils.find_linked_node(shader_node, 'specular ior level', 'TEX_IMAGE')
                    if specular:
                        maps['specular'] = specular
                    normal = utils.find_linked_node(shader_node, 'normal', 'TEX_IMAGE')
                    if normal:
                        maps['normal'] = normal
                    self_illum = utils.find_linked_node(shader_node, 'emission color', 'TEX_IMAGE')
                    if self_illum:
                        maps['self_illum'] = self_illum
                    alpha = utils.find_linked_node(shader_node, 'alpha', 'TEX_IMAGE')
                    if alpha and alpha not in maps.values():
                        maps['alpha'] = alpha
                    if diffuse is None:
                        albedo_tint = utils.get_material_albedo(shader_node)
                        if albedo_tint:
                            maps['albedo_tint'] = albedo_tint
                        
                return maps
            self._build_basic(get_basic_mapping(self.blender_material))
        
        self.tag_has_changes = True
        
    def _alpha_type_from_blender_material(self):
        if self.blender_material.surface_render_method == 'DITHERED':
                return ''
            
        return 'blend'
            
    def _build_basic(self, map: dict):
        self.group_node = map.get("bsdf")
        albedo = self.block_options.Elements[0].SelectField('short')
        bump_mapping = self.block_options.Elements[1].SelectField('short')
        alpha_test = self.block_options.Elements[2].SelectField('short')
        specular_mask = self.block_options.Elements[3].SelectField('short')
        self_illumination = self.block_options.Elements[6].SelectField('short')
        blend_mode = self.block_options.Elements[7].SelectField('short')
        alpha_blend_source = self.block_options.Elements[11].SelectField('short')
        # Set up shader parameters
        spec_alpha_from_diffuse = False
        si_alpha_from_diffuse = False
        if map.get('diffuse', 0):
            if int(albedo.GetStringData()) == 2 or int(albedo.GetStringData()) == -1: # if is constant color or none
                albedo.SetStringData('0') # sets default
            element = self._setup_parameter(map['diffuse'], 'base_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['diffuse'], element, 'bitmap')
                diff_alpha_output: bpy.types.NodeInputs = map['diffuse'].outputs[1]
                if diff_alpha_output.links:
                    for l in diff_alpha_output.links:
                        if l.to_socket.name.lower() == 'specular ior level':
                            spec_alpha_from_diffuse = True
                        if l.to_socket.name.lower() == 'emission color':
                            si_alpha_from_diffuse = True
                
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
            
        if si_alpha_from_diffuse:
            print("AYYY")
            self_illumination.SetStringData('4') # self illum mask from diffuse
        elif map.get('self_illum', 0):
            si_enum = int(self_illumination.GetStringData())
            if si_enum < 1 or si_enum == 4:
                self_illumination.SetStringData('1') # simple
            element = self._setup_parameter(map['self_illum'], 'self_illum_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['self_illum'], element, 'bitmap')
                
        if si_alpha_from_diffuse or map.get('self_illum', 0):
            si_intensity = map['bsdf'].inputs['Emission Strength'].default_value
            element = self._setup_parameter(si_intensity, 'self_illum_intensity', 'real')
            if element:
                self._setup_function_parameters(si_intensity, element, 'real')
        else:
            self_illumination.SetStringData('-1')
            
        if map.get('normal', 0):
            if int(bump_mapping.GetStringData()) < 1:
                bump_mapping.SetStringData('1') # standard
            element = self._setup_parameter(map['normal'], 'bump_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['normal'], element, 'bitmap')
        elif int(bump_mapping.GetStringData()) > 0:
            bump_mapping.SetStringData('-1') # none
            
        if self.alpha_type == 'clip' and map.get('alpha', 0):
            alpha_test.SetStringData('1')
            element = self._setup_parameter(map['alpha'], 'alpha_test_map', 'bitmap')
            if element:
                self._setup_function_parameters(map['alpha'], element, 'bitmap')
        elif self.alpha_type == 'blend':
            alpha_test.SetStringData('-1')
            if int(blend_mode.GetStringData()) < 1:
                blend_mode.SetStringData('3')
            if map.get('alpha', 0):
                if int(alpha_blend_source.GetStringData()) != 4:
                    alpha_blend_source.SetStringData('3') if map.get('alpha').inputs[0].links else alpha_blend_source.SetStringData('2')
                element = self._setup_parameter(map['alpha'], 'opacity_map', 'bitmap')
                if element:
                    self._setup_function_parameters(map['alpha'], element, 'bitmap')
        else:
            alpha_test.SetStringData('-1')
            blend_mode.SetStringData('-1')
            alpha_blend_source.SetStringData('-1')
          
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
            bitmap = str(Path(nwo.filepath).with_suffix(".bitmap"))
            if Path(self.tags_dir, bitmap).exists():
                return bitmap
            
        if image.filepath and Path(image.filepath_from_user()).exists() and Path(image.filepath_from_user()).is_relative_to(Path(self.data_dir)):
            bitmap = str(Path(image.filepath_from_user()).relative_to(Path(self.data_dir)).with_suffix(".bitmap"))
            if Path(self.tags_dir, bitmap).exists():
                return bitmap

        bitmap = export_bitmap(image)
        if not bitmap:
            return
        if Path(self.tags_dir, bitmap).exists():
            return bitmap
    
    def _function_parameters_from_node(self, source, parameter_type):
        mapping = {}
        match parameter_type:
            case 'bitmap':
                if isinstance(source, bpy.types.Node):
                    scale_node, is_texture_tiling = utils.find_mapping_node(source, self.group_node)
                    if not scale_node: return mapping
                    if is_texture_tiling:
                        factor = scale_node.inputs['Scale Multiplier'].default_value
                        mapping[self.scale_u] = scale_node.inputs['Scale X'].default_value * factor
                        mapping[self.scale_v] = scale_node.inputs['Scale Y'].default_value * factor
                    elif scale_node.type == 'MAPPING':
                        mapping[self.scale_u] = scale_node.inputs['Scale'].default_value.x
                        mapping[self.scale_v] = scale_node.inputs['Scale'].default_value.y
                        mapping[self.translation_u] = scale_node.inputs['Location'].default_value.x
                        mapping[self.translation_v] = scale_node.inputs['Location'].default_value.y
            case 'color':
                mapping['color'] = source
            case 'real':
                mapping['value'] = source

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
                return utils.find_linked_node(self.group_node, input_name, 'TEX_IMAGE')
            case 'real':
                return float(input.default_value)
            case 'int':
                return int(input.default_value)
            case 'bool':
                return int(bool(input.default_value))
            case 'color':
                return utils.get_material_albedo(self.group_node, input)
            
            
    # READING
    def to_nodes(self, blender_material):
        shader_path: str = blender_material.nwo.shader_path
        if shader_path.endswith('.' + self.tag_ext):
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
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._mapping_from_parameter_name(name)
            else:
                return
            
        block_animated_parameters = element.SelectField(self.function_parameters)
        mapping = {}
        for e in block_animated_parameters.Elements:
            f_type = e.Fields[0].Value
            value = e.SelectField(self.animated_function).Value
            match f_type:
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
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._image_from_parameter_name(name)
            else:
                return
        bitmap_path = element.SelectField('bitmap').Path
        if not bitmap_path:
            return
        system_bitmap_path = str(Path(self.tags_dir, bitmap_path.RelativePathWithExtension))
        image_path = ''
        if not os.path.exists(system_bitmap_path):
            return
        system_tiff_path = Path(self.data_dir, bitmap_path.RelativePath).with_suffix('.tiff')
        with BitmapTag(path=bitmap_path) as bitmap:
            is_non_color = bitmap.is_linear()
            if system_tiff_path.exists():
                image_path = str(system_tiff_path)
            else:
                image_path = bitmap.save_to_tiff(blue_channel_fix)

            image = bpy.data.images.load(filepath=image_path, check_existing=True)
            if is_non_color:
                image.colorspace_settings.name = 'Non-Color'
            else:
                image.alpha_mode = 'CHANNEL_PACKED'
                
            return image
    
    def _normal_type_from_parameter_name(self, name):
        if not self.corinth:
            return 'directx' # Reach normals are always directx
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            return 'opengl'
        bitmap_path = element.SelectField('bitmap').Path
        if bitmap_path:
            system_bitmap_path = Path(self.tags_dir, bitmap_path.RelativePathWithExtension)
            if not os.path.exists(system_bitmap_path):
                return 'opengl'
            with BitmapTag(path=bitmap_path) as bitmap:
                return bitmap.normal_type()
        else:
            return 'opengl'
    
    def _color_from_parameter_name(self, name):
        color = [1, 1, 1, 1]
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            if not self.corinth and self.reference.Path:
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
    
    def _set_alpha(self, alpha_type, blender_material):
        if alpha_type == 'blend':
            blender_material.surface_render_method = 'BLENDED'
        else:
            blender_material.surface_render_method = 'DITHERED'
            
    def _alpha_type(self, alpha_test, blend_mode):
        if blend_mode > 0:
            return 'blend'
        elif alpha_test > 0:
            return 'clip'
        else:
            return ''
    
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
        alpha_test_enum = self._option_value_from_index(2)
        specular_mask_enum = self._option_value_from_index(3)
        self_illumination_enum = self._option_value_from_index(6)
        blend_mode_enum = self._option_value_from_index(7)
        alpha_blend_source_enum = self._option_value_from_index(11)
        alpha_type = self._alpha_type(alpha_test_enum, blend_mode_enum)
        diffuse = None
        normal = None
        specular = None
        self_illum = None
        alpha = None
        if albedo_enum == 2:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_color'))
        else:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeTexImage', data=self._image_from_parameter_name('base_map'), mapping=self._mapping_from_parameter_name('base_map'), diffalpha=bool(alpha_type))
            if not diffuse.data:
                diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_color'))

        if bump_mapping_enum > 0:
            normal = BSDFParameter(tree, bsdf, bsdf.inputs['Normal'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('bump_map', True), normal_type=self._normal_type_from_parameter_name('bump_map'), mapping=self._mapping_from_parameter_name('bump_map'))
            if not normal.data:
                normal = None
                
        if specular_mask_enum == 3:
            specular = BSDFParameter(tree, bsdf, bsdf.inputs['Specular IOR Level'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('specular_mask_texture'), mapping=self._mapping_from_parameter_name('specular_mask_texture'))
            if not specular.data:
                specular = None
        elif specular_mask_enum > 0 and diffuse and type(diffuse.data) == bpy.types.Image:
            diffuse.diffspec = True
            
        if self_illumination_enum > 0:
            if self_illumination_enum == 4 and diffuse and type(diffuse.data) == bpy.types.Image:
                diffuse.diffillum = True
            else:
                self_illum = BSDFParameter(tree, bsdf, bsdf.inputs['Emission Color'], 'ShaderNodeTexImage', data=self._image_from_parameter_name(self.self_illum_map_names), mapping=self._mapping_from_parameter_name(self.self_illum_map_names))
            if self_illum and self_illum.data:
                bsdf.inputs['Emission Strength'].default_value = 1
                intensity_element = self._Element_from_field_value(self.block_parameters, 'parameter name', 'self_illum_intensity')
                if intensity_element:
                    value_element = self._Element_from_field_value(intensity_element.SelectField('animated parameters'), 'type', 0)
                    if value_element:
                        bsdf.inputs['Emission Strength'].default_value = value_element.SelectField(self.animated_function).Value.ClampRangeMin
            else:
                self_illum = None
                
        if alpha_type:
            if alpha_blend_source_enum > 1:
                alpha = BSDFParameter(tree, bsdf, bsdf.inputs['Alpha'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('opacity_texture'), mapping=self._mapping_from_parameter_name('opacity_texture'))
            elif diffuse and diffuse.data and type(diffuse.data) == bpy.types.Image:
                diffuse.diffalpha = True
            
        if diffuse:
            diffuse.build(Vector((-300, 400)))
        if normal:
            normal.build(Vector((-200, 100)))
        if specular:
            specular.build(Vector((-300, -200)))
        if self_illum:
            self_illum.build(Vector((-300, -500)))
        if alpha:
            alpha.build(Vector((-600, 300)))
            
        self._set_alpha(alpha_type, blender_material)
        
        
    def get_diffuse_bitmap_data_for_granny(self) -> None | tuple:
        has_alpha = self.block_options.Elements[7].Fields[0].Data > 0
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == "base_map":
                full_path = element.SelectField("bitmap").Path.Filename
                if not os.path.exists(full_path):
                    return None
                
                bitmap_path = element.SelectField("bitmap").Path.RelativePathWithExtension
                with BitmapTag(path=bitmap_path) as bitmap:
                    return bitmap.get_granny_data(), has_alpha
            
            
            
class BSDFParameter():
    """Representation of a Halo Shader parameter element in Blender node form"""
    tree: bpy.types.NodeTree
    main_node: bpy.types.Node
    input: bpy.types.NodeInputs
    link_node_type: str
    data: any
    default_value: any
    mapping: list
    normal_type: str
    alpha: str
    
    def __init__(self, tree, main_node, input, link_node_type, data=None, default_value=None, mapping=[], normal_type='', diffalpha=False, diffillum=False, diffspec=False):
        self.tree = tree
        self.main_node = main_node
        self.input = input
        self.link_node_type = link_node_type
        self.data = data
        self.default_value = default_value
        self.mapping = mapping
        self.normal_type = normal_type
        self.diffalpha = diffalpha
        self.diffillum = diffillum
        self.diffspec = diffspec
        
    
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
        
        if self.normal_type in ('opengl', 'directx'):
            normal_map_node = self.tree.nodes.new('ShaderNodeNormalMap')
            normal_map_node.location = vector
            self.tree.links.new(input=self.input, output=normal_map_node.outputs[0])
            if self.normal_type == 'opengl':
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
                
        elif self.link_node_type == 'ShaderNodeTexImage':
            self.tree.links.new(input=self.input, output=data_node.outputs[output_index])
            if self.diffspec:
                self.tree.links.new(input=self.main_node.inputs['Specular IOR Level'], output=data_node.outputs[1])
            if self.diffillum:
                self.tree.links.new(input=self.main_node.inputs['Emission Color'], output=data_node.outputs[1])
            if self.diffalpha:
                self.tree.links.new(input=self.main_node.inputs['Alpha'], output=data_node.outputs[1])
            
            
        if self.mapping:
            mapping_node = self.tree.nodes.new('ShaderNodeGroup')
            mapping_node.node_tree = utils.add_node_from_resources('Texture Tiling')
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
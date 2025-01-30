

from enum import Enum
from pathlib import Path
from mathutils import Vector

from ..constants import NormalType
from ..managed_blam import Tag
from ..managed_blam.Tags import TagPath, TagsNameSpace
import os
from ..managed_blam.bitmap import BitmapTag
from ..tools.export_bitmaps import export_bitmap
from .. import utils
import bpy

from ..managed_blam.render_method_definition import RenderMethodDefinitionTag

global_render_method_definition = None
last_group_node = None
default_parameter_bitmaps = None

class ChannelType(Enum):
    DEFAULT = 0
    RGB = 1
    ALPHA = 2
    RGB_ALPHA = 3

# OPTION ENUMS
class Albedo(Enum):
    DEFAULT = 0
    DETAIL_BLEND = 1
    CONSTANT_COLOR = 2
    TWO_CHANGE_COLOR = 3
    FOUR_CHANGE_COLOR = 4
    THREE_DETAIL_BLEND = 5
    TWO_DETAIL_OVERLAY = 6
    TWO_DETAIL = 7
    COLOR_MASK = 8
    TWO_DETAIL_BLACK_POINT = 9
    FOUR_CHANGE_COLOR_APPLYING_TO_SPECULAR = 10
    SIMPLE = 11
    
class BumpMapping(Enum):
    OFF = 0
    STANDARD = 1
    DETAIL = 2
    DETAIL_BLEND = 3
    THREE_DETAIL_BLEND = 4
    STANDARD_WRINKLE = 5
    DETAIL_WRINKLE = 6
    
class AlphaTest(Enum):
    NONE = 0
    SIMPLE = 1
    
class SpecularMask(Enum):
    NO_SPECULAR_MASK = 0
    SPECULAR_MASK_FROM_DIFFUSE = 1
    SPECULAR_MASK_MULT_DIFFUSE = 2
    SPECULAR_MASK_FROM_TEXTURE = 3
    
class MaterialModel(Enum):
    DIFFUSE_ONLY = 0
    COOK_TORRANCE = 1
    TWO_LOBE_PHONG = 2
    FOLIAGE = 3
    NONE = 4
    ORGANISM = 5
    HAIR = 6
    
class EnvironmentMapping(Enum):
    NONE = 0
    PER_PIXEL = 1
    DYNAMIC = 2
    FROM_FLAT_TEXTURE = 3
    
class SelfIllumination(Enum):
    OFF = 0
    SIMPLE = 1
    _3_CHANNEL_SELF_ILLUM = 2
    PLASMA = 3
    FROM_DIFFUSE = 4
    ILLUM_DETAIL = 5
    METER = 6
    SELF_ILLUM_TIMES_DIFFUSE = 7
    SIMPLE_WITH_ALPHA_MASK = 8
    MULTILAYER_ADDITIVE = 9
    PALETTIZED_PLASMA = 10
    CHANGE_COLOR = 11
    CHANGE_COLOR_DETAIL = 12
    
class BlendMode(Enum):
    OPAQUE = 0
    ADDITIVE = 1
    MULTIPLY = 2
    ALPHA_BLEND = 3
    DOUDBLE_MULTIPLY = 4
    PRE_MULTIPLIED_ALPHA = 5
    
class Parallax(Enum):
    OFF = 0
    SIMPLE = 1
    INTERPOLATED = 2
    SIMPLE_DETAIL = 3
    
class Misc(Enum):
    DEFAULT = 0
    ROTATING_BITMAPS_SUPER_SLOW = 1
    
class Wetness(Enum):
    DEFAULT = 0
    FLOOD = 1
    PROOF = 2
    SIMPLE = 3
    RIPPLES = 4
    
class AlphaBlendSource(Enum):
    FROM_ALBEDO_ALPHA_WITHOUT_FRESNEL = 0
    FROM_ALBEDO_ALPHA = 1
    FROM_OPACITY_MAP_ALPHA = 2
    FROM_OPACITY_MAP_RGB = 3
    FROM_OPACITY_MAP_ALPHA_AND_ALBEDO_ALPHA = 4

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
    
    group_supported = True
    
    def _read_fields(self):
        self.render_method = self.tag.SelectField("Struct:render_method").Elements[0]
        self.block_parameters = self.render_method.SelectField("parameters")
        self.block_options = self.render_method.SelectField('options')
        self.reference = self.render_method.SelectField('reference')
        self.definition = self.render_method.SelectField('definition')
                
    def _get_default_bitmaps(self):
        global default_parameter_bitmaps
        if default_parameter_bitmaps is None:
            def_path = self.definition.Path
            if def_path is None:
                default_parameter_bitmaps = {}
                return
            with RenderMethodDefinitionTag(path=def_path) as render_method_definition:
                default_parameter_bitmaps = render_method_definition.get_default_bitmaps()
    
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
    def to_nodes(self, blender_material, change_colors=None):
        shader_path: str = blender_material.nwo.shader_path
        self._get_default_bitmaps()
        if self.group_supported:
            self._to_nodes_group(blender_material, change_colors)
        else:
            self._to_nodes_bsdf(blender_material)
            
    def _option_value_from_index(self, index):
        option_enum = self.block_options.Elements[index].Fields[0].Data
        if option_enum == -1 and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                return shader._option_value_from_index(index)
        else:
            if option_enum == -1:
                return 0
            return option_enum
        
    def _mapping_from_parameter_name(self, name, mapping={}):
        the_one = name == "bump_detail_map" and self.tag_path.RelativePathWithExtension == r"objects\characters\spartans\shaders\spartan_rubber_suit.shader"
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                if element: break
                
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader._mapping_from_parameter_name(name, mapping)
            else:
                return
        else:
            block_animated_parameters = element.SelectField(self.function_parameters)
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
                    
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader._mapping_from_parameter_name(name, mapping)
        
    def _image_from_parameter_name(self, name, blue_channel_fix=False, default_bitmap=None):
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

        if bitmap_path is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    result = shader._image_from_parameter_name(name)
                    if result is not None:
                        return result
            bitmap_path = default_bitmap
            if bitmap_path is None:
                bitmap_path = default_parameter_bitmaps.get(name)
                if bitmap_path is None:
                    return
        
        if not os.path.exists(bitmap_path.Filename):
            return
        
        system_tiff_path = Path(self.data_dir, bitmap_path.RelativePath).with_suffix('.tiff')
        alt_system_tiff_path = system_tiff_path.with_suffix(".tif")
        with BitmapTag(path=bitmap_path) as bitmap:
            is_non_color = bitmap.is_linear()
            # print(f"Writing Tiff from {bitmap.tag_path.RelativePathWithExtension}")
            # image_path = bitmap.save_to_tiff(bitmap.used_as_normal_map())
            if system_tiff_path.exists():
                image_path = str(system_tiff_path)
            elif alt_system_tiff_path.exists():
                image_path = str(alt_system_tiff_path)
            else:
                image_path = bitmap.save_to_tiff(bitmap.used_as_normal_map())

            image = bpy.data.images.load(filepath=image_path, check_existing=True)
            if is_non_color:
                image.colorspace_settings.name = 'Non-Color'
            else:
                image.alpha_mode = 'CHANNEL_PACKED'
                
            return image
    
    def _normal_type_from_parameter_name(self, name):
        if not self.corinth:
            return NormalType.DIRECTX # Reach normals are always directx
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            return NormalType.OPENGL
        bitmap_path = element.SelectField('bitmap').Path
        if bitmap_path:
            system_bitmap_path = Path(self.tags_dir, bitmap_path.RelativePathWithExtension)
            if not os.path.exists(system_bitmap_path):
                return NormalType.OPENGL
            with BitmapTag(path=bitmap_path) as bitmap:
                return bitmap.normal_type()
        else:
            return NormalType.OPENGL
    
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
    
    def _value_from_parameter_name(self, name):
        value = 0
        if type(name) == str:
            element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
        else:
            for n in name:
                 element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
                 if element: break
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._value_from_parameter_name(name)
            else:
                return
            
        block_animated_parameters = element.SelectField(self.function_parameters)
        color_element = self._Element_from_field_value(block_animated_parameters, 'type', 1)
        if color_element:
            game_color = color_element.SelectField(self.animated_function).Value.GetColor(0)
            if game_color.ColorMode == 1: # Is HSV
                game_color = game_color.ToRgb()
                
            color = [game_color.Red, game_color.Green, game_color.Blue, game_color.Alpha]
        
        return value
    
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
    
    def _to_nodes_bsdf(self, blender_material: bpy.types.Material):
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
        fill_alpha = True
        calc_blue = False
        # has_normal = self.block_options.Elements[1].Fields[0].Data > 0
        for element in self.block_parameters.Elements:
            match element.Fields[0].GetStringData():
                case "base_map":
                    fill_alpha = self.block_options.Elements[7].Fields[0].Data < 1
                # case "bump_map":
                #     if has_normal:
                #         calc_blue = True
                #     else: continue
                case _:
                    continue
                    
            p = element.SelectField("bitmap").Path
            if not p:
                continue
            full_path = p.Filename
            if not os.path.exists(full_path):
                continue
            
            bitmap_path = element.SelectField("bitmap").Path.RelativePathWithExtension
            with BitmapTag(path=bitmap_path) as bitmap:
                return bitmap.get_granny_data(fill_alpha, calc_blue)
            
    def group_set_image(self, tree: bpy.types.NodeTree, node: bpy.types.Node, parameter_name: str, vector: Vector, channel_type=ChannelType.DEFAULT, normal_type: NormalType = None, return_image_node=False, default_bitmap=None):
        data = self._image_from_parameter_name(parameter_name, normal_type is not None, default_bitmap=default_bitmap)
        
        if data is None:
            if return_image_node:
                return vector, None
            return vector
        
        mapping = {}
        self._mapping_from_parameter_name(parameter_name, mapping)
        
        data_node = tree.nodes.new("ShaderNodeTexImage")
        data_node.location = vector
        data_node.image = data
        
        if normal_type is not None:
            normal_map_node = tree.nodes.new('ShaderNodeNormalMap')
            normal_map_node.location = vector
            tree.links.new(input=node.inputs[0], output=normal_map_node.outputs[0])
            if normal_type == NormalType.OPENGL:
                data_node.location.x = normal_map_node.location.x - 300
                data_node.location.y = normal_map_node.location.y
                tree.links.new(input=normal_map_node.inputs[1], output=data_node.outputs[0])
            else:
                combine_rgb = tree.nodes.new('ShaderNodeCombineColor')
                combine_rgb.location.x = normal_map_node.location.x - 200
                combine_rgb.location.y = normal_map_node.location.y
                tree.links.new(input=normal_map_node.inputs[1], output=combine_rgb.outputs[0])
                invert_color = tree.nodes.new('ShaderNodeInvert')
                invert_color.location.x = combine_rgb.location.x - 200
                invert_color.location.y = combine_rgb.location.y + 80
                tree.links.new(input=combine_rgb.inputs[1], output=invert_color.outputs[0])
                separate_rgb = tree.nodes.new('ShaderNodeSeparateColor')
                separate_rgb.location.x = invert_color.location.x - 200
                separate_rgb.location.y = combine_rgb.location.y
                tree.links.new(input=combine_rgb.inputs[0], output=separate_rgb.outputs[0])
                tree.links.new(input=invert_color.inputs[1], output=separate_rgb.outputs[1])
                tree.links.new(input=combine_rgb.inputs[2], output=separate_rgb.outputs[2])
                
                tree.links.new(input=separate_rgb.inputs[0], output=data_node.outputs[0])
                data_node.location.x = separate_rgb.location.x - 300
                data_node.location.y = separate_rgb.location.y
                
        else:
            match channel_type:
                case ChannelType.DEFAULT:
                    tree.links.new(input=node.inputs[parameter_name], output=data_node.outputs[0])
                case ChannelType.RGB:
                    tree.links.new(input=node.inputs[f"{parameter_name}.rgb"], output=data_node.outputs[0])
                case ChannelType.ALPHA:
                    tree.links.new(input=node.inputs[f"{parameter_name}.a"], output=data_node.outputs[1])
                case ChannelType.RGB_ALPHA:
                    tree.links.new(input=node.inputs[f"{parameter_name}.rgb"], output=data_node.outputs[0])
                    tree.links.new(input=node.inputs[f"{parameter_name}.a"], output=data_node.outputs[1])
        
        if mapping:
            mapping_node = tree.nodes.new('ShaderNodeGroup')
            mapping_node.node_tree = utils.add_node_from_resources("shared_nodes", 'Texture Tiling')
            mapping_node.location.x = data_node.location.x - 300
            mapping_node.location.y = data_node.location.y
            scale_uni = mapping.get('scale_uni')
            if scale_uni is not None:
                mapping_node.inputs[0].default_value = scale_uni
            scale_x = mapping.get('scale_x')
            if scale_x is not None:
                mapping_node.inputs[1].default_value = scale_x
            scale_y = mapping.get('scale_y')
            if scale_y is not None:
                mapping_node.inputs[2].default_value = scale_y
                
            tree.links.new(input=data_node.inputs[0], output=mapping_node.outputs[0])
                    
            
        vector = Vector((vector.x, vector.y - 300))
        
        if return_image_node:
            return vector, data_node
        return vector
    
    def _add_group_node(self, tree: bpy.types.NodeTree, nodes: bpy.types.Nodes, name: str, location: Vector) -> bpy.types.Node:
        node = nodes.new(type='ShaderNodeGroup')
        node.node_tree = utils.add_node_from_resources("reach_nodes", name)
        node.location = location
        self.populate_chiefster_node(tree, node)
        return node
    
    def _add_group_material_model(self, tree: bpy.types.NodeTree, nodes: bpy.types.Nodes, name: str, location: Vector, supports_glancing_spec: bool) -> bpy.types.Node:
        node_material_model = nodes.new(type="ShaderNodeGroup")
        node_material_model.node_tree = utils.add_node_from_resources("reach_nodes", f"material_model - {name}")
            
        self.populate_chiefster_node(tree, node_material_model)
        
        # specular color has be dealt with specially
        if supports_glancing_spec:
            for element in self.block_parameters.Elements:
                if element.Fields[0].GetStringData() == "specular_color_by_angle":
                    for animated_element in element.SelectField("animated parameters").Elements:
                        value = animated_element.SelectField(self.animated_function).Value
                        normal_color = value.GetColor(0)
                        if normal_color.ColorMode == 1:
                            normal_color = normal_color.ToRgb()
                        glancing_color = value.GetColor(1)
                        if glancing_color.ColorMode == 1:
                            glancing_color = glancing_color.ToRgb()
                            
                        node_material_model.inputs["normal_specular_color"].default_value = glancing_color.Red, glancing_color.Green, glancing_color.Blue, 1
                        node_material_model.inputs["glancing_specular_color"].default_value = normal_color.Red, normal_color.Green, normal_color.Blue, 1
                        break
                    break

        node_material_model.location = location
        return node_material_model
    
    def _to_nodes_group(self, blender_material: bpy.types.Material, change_colors: list):
        
        # Get options
        e_albedo = Albedo(self._option_value_from_index(0))
        e_bump_mapping = BumpMapping(self._option_value_from_index(1))
        e_alpha_test = AlphaTest(self._option_value_from_index(2))
        e_specular_mask = SpecularMask(self._option_value_from_index(3))
        e_material_model = MaterialModel(self._option_value_from_index(4))
        e_environment_mapping = EnvironmentMapping(self._option_value_from_index(5))
        e_self_illumination = SelfIllumination(self._option_value_from_index(6))
        e_blend_mode = BlendMode(self._option_value_from_index(7))
        e_parallax = Parallax(self._option_value_from_index(8))
        e_misc = Misc(self._option_value_from_index(9))
        e_wetness = Wetness(self._option_value_from_index(10))
        e_alpha_blend_source = AlphaBlendSource(self._option_value_from_index(11))
        
        if e_material_model == MaterialModel.NONE:
            e_material_model = MaterialModel.DIFFUSE_ONLY
        
        if e_material_model.value > 2:
            old_model = e_material_model.name
            if e_material_model == MaterialModel.FOLIAGE:
                e_material_model = MaterialModel.DIFFUSE_ONLY
            else:
                e_material_model = MaterialModel.COOK_TORRANCE
                
            utils.print_warning(f"Unsupported material model : {old_model}. Using {e_material_model.name} instead")
        
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        has_bump = e_bump_mapping.value > 0
        
        node_material_model = self._add_group_material_model(tree, nodes, utils.game_str(e_material_model.name), Vector((0, 0)), e_material_model.value > 0)
        final_node = node_material_model
        
        node_albedo = self._add_group_node(tree, nodes, f"albedo - {utils.game_str(e_albedo.name)}", Vector((node_material_model.location.x - 300, node_material_model.location.y + 500)))
        
        if e_albedo in {Albedo.FOUR_CHANGE_COLOR, Albedo.FOUR_CHANGE_COLOR_APPLYING_TO_SPECULAR, Albedo.TWO_CHANGE_COLOR} and change_colors:
            node_albedo.inputs["Primary Color"].default_value = change_colors[0]
            node_albedo.inputs["Secondary Color"].default_value = change_colors[1]
            if e_albedo != Albedo.TWO_CHANGE_COLOR:
                node_albedo.inputs["Tertiary Color"].default_value = change_colors[2]
                node_albedo.inputs["Quaternary Color"].default_value = change_colors[3]
        
        tree.links.new(input=node_material_model.inputs[0], output=node_albedo.outputs[0])
        if e_material_model.value > 0: # Diffuse only does not have alpha input
            tree.links.new(input=node_material_model.inputs[1], output=node_albedo.outputs[1])
        
        if has_bump:
            node_bump_mapping = self._add_group_node(tree, nodes, f"bump_mapping - {utils.game_str(e_bump_mapping.name)}", Vector((node_albedo.location.x, node_material_model.location.y - 500)))
            tree.links.new(input=node_material_model.inputs["Normal"], output=node_bump_mapping.outputs[0])
            
        if e_environment_mapping.value > 0:
            node_environment_mapping = self._add_group_node(tree, nodes, f"environment_mapping - {utils.game_str(e_environment_mapping.name)}", Vector((node_material_model.location.x + 600, node_material_model.location.y - 200)))
            tree.links.new(input=node_environment_mapping.inputs[0], output=node_material_model.outputs[1])
            if e_environment_mapping == EnvironmentMapping.DYNAMIC:
                tree.links.new(input=node_environment_mapping.inputs[1], output=node_material_model.outputs[2])
                
            node_model_environment_add = nodes.new(type='ShaderNodeAddShader')
            node_model_environment_add.location.x = node_environment_mapping.location.x + 300
            node_model_environment_add.location.y = node_material_model.location.y
            tree.links.new(input=node_model_environment_add.inputs[0], output=node_material_model.outputs[0])
            tree.links.new(input=node_model_environment_add.inputs[1], output=node_environment_mapping.outputs[0])
            final_node = node_model_environment_add
            if has_bump:
                tree.links.new(input=node_environment_mapping.inputs["Normal"], output=node_bump_mapping.outputs[0])
            
        if e_self_illumination.value > 0:
            node_self_illumination = self._add_group_node(tree, nodes, f"self_illumination - {utils.game_str(e_self_illumination.name)}", Vector((final_node.location.x + 300, final_node.location.y - 200)))
            node_illum_add = nodes.new(type='ShaderNodeAddShader')
            node_illum_add.location.x = node_self_illumination.location.x + 300
            node_illum_add.location.y = final_node.location.y
            tree.links.new(input=node_illum_add.inputs[0], output=final_node.outputs[0])
            tree.links.new(input=node_illum_add.inputs[1], output=node_self_illumination.outputs[0])
            final_node = node_illum_add
            
        if e_blend_mode in {BlendMode.ADDITIVE, BlendMode.ALPHA_BLEND}:
            blender_material.surface_render_method = 'BLENDED'
            node_blend_mode = self._add_group_node(tree, nodes, f"blend_mode - {utils.game_str(e_blend_mode.name)}", Vector((final_node.location.x + 300, final_node.location.y)))
            tree.links.new(input=node_blend_mode.inputs[0], output=final_node.outputs[0])
            final_node = node_blend_mode
            if e_blend_mode == BlendMode.ALPHA_BLEND:
                if e_alpha_blend_source.value > 0:
                    node_alpha_blend_source = self._add_group_node(tree, nodes, f"alpha_blend_source - {utils.game_str(e_alpha_blend_source.name)}", Vector((node_blend_mode.location.x - 300, node_blend_mode.location.y - 300)))
                    tree.links.new(input=node_blend_mode.inputs[1], output=node_alpha_blend_source.outputs[0])
                    if has_bump:
                        tree.links.new(input=node_alpha_blend_source.inputs["Normal"], output=node_bump_mapping.outputs[0])
                else:
                    tree.links.new(input=node_blend_mode.inputs[1], output=node_albedo.outputs[1])
            
        if e_alpha_test.value > 0:
            node_alpha_test = self._add_group_node(tree, nodes, f"alpha_test - {utils.game_str(e_alpha_test.name)}", Vector((final_node.location.x + 300, final_node.location.y)))
            tree.links.new(input=node_alpha_test.inputs[0], output=final_node.outputs[0])
            final_node = node_alpha_test
            
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location.x = final_node.location.x + 300
        node_output.location.y = final_node.location.y
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=final_node.outputs[0])

    def group_set_color(self, tree: bpy.types.NodeTree, node: bpy.types.Node, parameter_name: str):
        element = self._Element_from_field_value(self.block_parameters, 'parameter name', parameter_name)
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader.group_set_color(parameter_name)
            else:
                return
            
        block_animated_parameters = element.SelectField(self.function_parameters)
        color_element = self._Element_from_field_value(block_animated_parameters, 'type', 1)
        if color_element:
            game_color = color_element.SelectField(self.animated_function).Value.GetColor(0)
            if game_color.ColorMode == 1: # Is HSV
                game_color = game_color.ToRgb()
                
            color = [game_color.Red, game_color.Green, game_color.Blue, game_color.Alpha]
            node.inputs[parameter_name].default_value = color

    def group_set_value(self, tree: bpy.types.NodeTree, node: bpy.types.Node, parameter_name: str):
        element = self._Element_from_field_value(self.block_parameters, 'parameter name', parameter_name)
        if element is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader.group_set_value(parameter_name)
            else:
                return
            
        block_animated_parameters = element.SelectField(self.function_parameters)
        value_element = self._Element_from_field_value(block_animated_parameters, 'type', 0)
        if value_element:
            value = value_element.SelectField(self.animated_function).Value.ClampRangeMin
            node.inputs[parameter_name].default_value = value

    def group_set_flag(self, tree: bpy.types.NodeTree, node: bpy.types.Node, parameter_name: str):
        pass
    
    def populate_chiefster_node(self, tree: bpy.types.NodeTree, node: bpy.types.Node):
        last_parameter_name = None
        last_input_node = None
        location = Vector((node.location.x - 300, node.location.y + 300))
        for input in node.inputs:
            parameter_name = input.name.lower() if "." not in input.name else input.name.partition(".")[0].lower()
            if "gamma curve" in parameter_name:
                input.default_value = 1
                last_parameter_name = None
                continue
            input: bpy.types.NodeGroupInput
            if parameter_name == last_parameter_name and last_input_node is not None:
                # plug in alpha
                alpha_input = node.inputs.get(f"{parameter_name}.a")
                if alpha_input is None:
                    alpha_input = node.inputs[f"{parameter_name}.a/specular_mask.a"]
                tree.links.new(input=alpha_input, output=last_input_node.outputs[1])
            else:
                parameter_type = self._parameter_type_from_name(parameter_name)
                default_bitmap = None
                if parameter_type == ParameterType.NONE:
                    default_bitmap = default_parameter_bitmaps.get(parameter_name)
                    if default_bitmap is None:
                        last_parameter_name = None
                        continue
                    
                match parameter_type:
                    case ParameterType.COLOR | ParameterType.ARGB_COLOR:
                        self.group_set_color(tree, node, parameter_name)
                    case ParameterType.REAL | ParameterType.INT | ParameterType.BOOL:
                        self.group_set_value(tree, node, parameter_name)
                    case _:
                        if ".rgb" in input.name:
                            location, last_input_node = self.group_set_image(tree, node, parameter_name, location, ChannelType.RGB, return_image_node=True, default_bitmap=default_bitmap)
                        elif ".a" in input.name:
                            location, last_input_node = self.group_set_image(tree, node, parameter_name, location, ChannelType.ALPHA, return_image_node=True, default_bitmap=default_bitmap)
                        else:
                            location, last_input_node = self.group_set_image(tree, node, parameter_name, location, ChannelType.DEFAULT, return_image_node=True, default_bitmap=default_bitmap)
                        
                last_parameter_name = parameter_name
                
    def _parameter_type_from_name(self, name: str):
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == name:
                return ParameterType(element.Fields[1].Value)
                
        return ParameterType.NONE
                

class BSDFParameter:
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
    
    def __init__(self, tree, main_node, input, link_node_type, data=None, default_value=None, mapping=[], normal_type: NormalType = None, diffalpha=False, diffillum=False, diffspec=False):
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
            # print("No data and no default value")
            return
        
        output_index = 0
        data_node = self.tree.nodes.new(self.link_node_type)
        data_node.location = vector
        if self.link_node_type == 'ShaderNodeTexImage':
            data_node.image = self.data
        elif self.link_node_type == 'ShaderNodeRGB':
            data_node.outputs[0].default_value = self.data
        
        if self.normal_type is not None:
            normal_map_node = self.tree.nodes.new('ShaderNodeNormalMap')
            normal_map_node.location = vector
            self.tree.links.new(input=self.input, output=normal_map_node.outputs[0])
            if self.normal_type == NormalType.OPENGL:
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
            mapping_node.node_tree = utils.add_node_from_resources("shared_nodes", 'Texture Tiling')
            mapping_node.location.x = data_node.location.x - 300
            mapping_node.location.y = data_node.location.y
            try:
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
            except:
                pass
        
class ParameterType(Enum):
    NONE = -1
    BITMAP = 0
    COLOR = 1
    REAL = 2
    INT = 3
    BOOL = 4
    ARGB_COLOR = 5
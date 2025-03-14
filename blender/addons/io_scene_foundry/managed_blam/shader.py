

from enum import Enum
from pathlib import Path
from mathutils import Vector

from .render_method_option import OptionParameter

from ..constants import NormalType
from ..managed_blam import Tag
from ..managed_blam.Tags import TagFieldBlockElement, TagPath, TagsNameSpace
import os
from ..managed_blam.bitmap import BitmapTag
from ..tools.export_bitmaps import export_bitmap
from .. import utils
import bpy

from ..managed_blam.render_method_definition import RenderMethodDefinitionTag

global_render_method_definition = None
last_group_node = None

ammo_names = "primary_ammunition_ones", "primary_ammunition_tens", "primary_ammunition_hundreds"

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
    DOUBLE_MULTIPLY = 4
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
    
class FunctionEditorColorGraphType(Enum):
    Scalar = 0
    OneColor = 1
    TwoColor = 2
    ThreeColor = 3
    FourColor = 4
    
class FunctionEditorMasterType(Enum):
    Basic = 0
    Curve = 1
    Periodic = 2
    Exponent = 3
    Transition = 4
    
class FunctionEditorSegmentCornerType(Enum):
    NotApplicable = 0
    Corner = 1
    Smooth = 2
    
class FunctionEditorSegmentType(Enum):
    Linear = 0
    Spline = 1
    Spline2 = 2
    
# class FunctionEditorPeriodicType(Enum):
#     One = 0
#     Zero = 1
#     Cosine = 2
#     CosineVariable = 3
#     DiagonalWave = 4
#     DiagonalWaveVariable = 5
#     Slide = 6
#     SlideVariable = 7
#     Noise = 8
#     Jitter = 9
#     Wander = 10
#     Spark = 11
    
# class FunctionEditorTransitionType(Enum):
#     Linear = 0
#     Early = 1
#     VeryEarly = 2
#     Late = 3
#     VeryLate = 4
#     Cosine = 5
#     One = 6
#     Zero = 7
    
class AnimatedParameterType(Enum):
    VALUE = 0
    COLOR = 1
    SCALE_UNIFORM = 2
    SCALE_X = 3
    SCALE_Y = 4
    TRANSLATION_X = 5
    TRANSLATION_Y = 6
    FRAME_INDEX = 7
    ALPHA = 8
    
class TilingNodeInputs(Enum):
    TRANSLATION_X = 0
    TRANSLATION_Y = 1
    SCALE_UNIFORM = 2
    SCALE_X = 3
    SCALE_Y = 4
    
class ControlPoint:
    def __init__(self, graph_index, point_index):
        self.graph_index = graph_index
        self.point_index = point_index
        self.x = 0
        self.y = 0
        self.corner_type = FunctionEditorSegmentCornerType.NotApplicable
        self.segment = None
        
    def from_editor(self, editor, last_point_index):
        game_point_2d = editor.GetControlPoint(self.graph_index, self.point_index)
        self.x = game_point_2d.X
        self.y = game_point_2d.Y
        if self.point_index > 0 and self.point_index < last_point_index:
            print(self.point_index)
            self.corner_type = FunctionEditorSegmentCornerType[editor.GetControlPointCornerType(self.graph_index, self.point_index).ToString()]
        
class Segment:
    def __init__(self, graph_index, segment_index):
        self.graph_index = graph_index
        self.segment_index = segment_index
        self.type = FunctionEditorSegmentType.Linear
        
    def from_editor(self, editor):
        self.type = FunctionEditorSegmentType[editor.GetSegmentType(self.graph_index, self.segment_index).ToString()]
    
class AnimatedParameter:
    def __init__(self):
        self.time_period = 0.0
        self.input = ""
        self.range = ""
        self.is_ranged = False
        self.master_type = FunctionEditorMasterType.Basic
        self.is_color = False
        self.color_type = FunctionEditorColorGraphType.Scalar
        self.color_count = 1
        self.input_periodic_function = "one"
        self.range_periodic_function = "one"
        self.input_transition_function = "linear"
        self.range_transition_function = "linear"
        self.input_frequency = 0
        self.range_frequency = 0
        self.input_phase = 0
        self.range_phase = 0
        self.input_exponent = 5
        self.range_exponent = 5
        self.input_min = 0
        self.input_max = 1
        self.range_min = 0
        self.range_max = 1
        self.clamp_min = 0
        self.clamp_max = 1
        self.is_exclusion = False
        self.exclusion_min = 0
        self.exclusion_max = 0
        self.colors = [tuple((1, 1, 1)), tuple((1, 1, 1)), tuple((1, 1, 1)), tuple((1, 1, 1))]
        self.control_points = []
    
    def from_element(self, element: TagFieldBlockElement, animated_name: str):
        self.time_period = element.SelectField("time period").Data
        self.input = element.SelectField("input name").GetStringData()
        self.range = element.SelectField("range name").GetStringData()
        editor = element.SelectField(animated_name).Value
        self.is_ranged = editor.IsRanged
        self.master_type = FunctionEditorMasterType(editor.MasterType.value__)
        self.color_type = FunctionEditorColorGraphType(editor.ColorGraphType.value__)
        self.is_color = self.color_type != FunctionEditorColorGraphType.Scalar
        self.color_count = editor.ColorCount
        
        self.is_exclusion = editor.IsExclusion
        self.exclusion_min = editor.ExclusionMin
        self.exclusion_max = editor.ExclusionMax
        
        match self.master_type:
            case FunctionEditorMasterType.Periodic:
                self.input_periodic_function = editor.GetPeriodicFunctionText(editor.GetFunctionIndex(0))
                self.input_frequency = editor.GetFrequency(0)
                self.input_phase = editor.GetPhase(0)
                self.input_min = editor.GetAmplitudeMin(0)
                self.input_max = editor.GetAmplitudeMax(0)
                if self.is_ranged:
                    self.range_periodic_function = editor.GetPeriodicFunctionText(editor.GetFunctionIndex(1))
                    self.range_frequency = editor.GetFrequency(1)
                    self.range_phase = editor.GetPhase(1)
                    self.range_min = editor.GetAmplitudeMin(1)
                    self.range_max = editor.GetAmplitudeMax(1)
            case FunctionEditorMasterType.Exponent:
                self.input_exponent = editor.GetExponent(0)
                self.input_min = editor.GetAmplitudeMin(0)
                self.input_max = editor.GetAmplitudeMax(0)
                if self.is_ranged:
                    self.range_exponent = editor.GetExponent(1)
                    self.range_min = editor.GetAmplitudeMin(1)
                    self.range_max = editor.GetAmplitudeMax(1)
            case FunctionEditorMasterType.Transition:
                self.input_transition_function = editor.GetTransitionFunctionText(editor.GetFunctionIndex(0))
                self.input_min = editor.GetAmplitudeMin(0)
                self.input_max = editor.GetAmplitudeMax(0)
                if self.is_ranged:
                    self.range_transition_function = editor.GetTransitionFunctionText(editor.GetFunctionIndex(1))
                    self.range_min = editor.GetAmplitudeMin(1)
                    self.range_max = editor.GetAmplitudeMax(1)
            case FunctionEditorMasterType.Curve:
                pass
                # Loop segments
                # Get segment type, if spline then each CP on segment has a handle (another CP)
                
                
                # input_control_count = editor.GetControlPointCount(0)
                # segment_count = editor.GetSegmentCount(0)
                # last_control_index = input_control_count - 1
                # for i in range(input_control_count):
                #     control_point = ControlPoint(0, i)
                #     control_point.from_editor(editor, segment_count)
                #     if i < segment_count:
                #         segment = Segment(0, i)
                #         segment.from_editor(editor)
                #         control_point.segment = segment
                #     self.control_points.append(control_point)
                    
        if self.is_color:
            for i in range(self.color_count):
                game_color = editor.GetColor(i)
                if game_color.ColorMode == 1:
                    game_color = game_color.ToRgb()
                
                self.colors[i] = game_color.Red, game_color.Green, game_color.Blue, game_color.Alpha
        else:
            self.clamp_min = editor.ClampRangeMin
            self.clamp_max = editor.ClampRangeMax
            
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("time period").Data = self.time_period
        editor = element.SelectField(self.animated_function).Value
        editor.BeginUpdate()
        # Do stuff
        editor.EndUpdate()
        

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
    category_parameters = None
    
    def _read_fields(self):
        self.render_method = self.tag.SelectField("Struct:render_method").Elements[0]
        self.block_parameters = self.render_method.SelectField("parameters")
        self.block_options = self.render_method.SelectField('options')
        self.reference = self.render_method.SelectField('reference')
        if self.reference.Path and self.reference.Path == self.tag_path: # prevent recursion issues
            self.reference.Path = None
        self.definition = self.render_method.SelectField('definition')
    
    @classmethod
    def _get_info(cls, definition_path: TagPath):
        if cls.category_parameters is None:
            def_path = definition_path
            if def_path is None:
                cls.category_parameters = {}
                return
            with RenderMethodDefinitionTag(path=def_path) as render_method_definition:
                cls.category_parameters = render_method_definition.get_defaults()
    
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
            self._get_info(self.definition.Path)
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
    def to_nodes(self, blender_material, always_extract_bitmaps=False):
        self.game_functions = set()
        self.always_extract_bitmaps = always_extract_bitmaps
        self._get_info(self.reference_material_shader.Path if self.corinth else self.definition.Path)
        if self.group_supported:
            self._to_nodes_group(blender_material)
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
        
    # def _mapping_from_parameter_name(self, name, mapping={}):
    #     if type(name) == str:
    #         element = self._Element_from_field_value(self.block_parameters, 'parameter name', name)
    #     else:
    #         for n in name:
    #             element = self._Element_from_field_value(self.block_parameters, 'parameter name', n)
    #             if element: break
                
    #     if element is None:
    #         if not self.corinth and self.reference.Path:
    #             with ShaderTag(path=self.reference.Path) as shader:
    #                 shader._mapping_from_parameter_name(name, mapping)
    #         else:
    #             return
    #     else:
    #         block_animated_parameters = element.SelectField(self.function_parameters)
    #         for e in block_animated_parameters.Elements:
    #             ap_type = AnimatedParameterType(e.Fields[0].Value)
    #             ap = AnimatedParameter()
    #             ap.from_element(e, self.animated_function)
    #             mapping[ap_type] = ap
                    
    #         if not self.corinth and self.reference.Path:
    #             with ShaderTag(path=self.reference.Path) as shader:
    #                 shader._mapping_from_parameter_name(name, mapping)
                    
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
        
    def _image_from_parameter(self, parameter: OptionParameter, return_none_if_default=False):
        """Saves an image (or gets the already existing one) from a shader parameter element"""
        element = None
        bitmap_path = None
        wrap_mode = 'REPEAT'
        plate_info = None
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == parameter.name:
                break
        else:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader.always_extract_bitmaps = self.always_extract_bitmaps
                    return shader._image_from_parameter(parameter)
            else:
                if return_none_if_default:
                    return
                else:
                    bitmap_path = parameter.default_bitmap
                    element = None
                    if bitmap_path is None:
                        return
        
        if bitmap_path is None:
            bitmap_path = element.SelectField('bitmap').Path

        if bitmap_path is None:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader.always_extract_bitmaps = self.always_extract_bitmaps
                    result = shader._image_from_parameter(parameter)
                    if result is not None:
                        return result
                    
            if not return_none_if_default:
                bitmap_path = parameter.default_bitmap
                element = None
        elif element is not None:
            match element.SelectField("bitmap address mode").Data:
                case 1 | 3: # clamp | black border
                    wrap_mode = 'CLIP'
                case 2 | 4 | 5: # Mirror
                    wrap_mode = 'MIRROR'
                    
                
        if bitmap_path is None:
            return
        
        if not os.path.exists(bitmap_path.Filename):
            return
        
        rel_path = f"{bitmap_path.RelativePath}_equirectangular" if "cubemap" in bitmap_path.ShortName else bitmap_path.RelativePath
        
        system_tiff_path = Path(self.data_dir, rel_path).with_suffix('.tiff')
        alt_system_tiff_path = system_tiff_path.with_suffix(".tif")
        with BitmapTag(path=bitmap_path) as bitmap:
            # is_non_color = bitmap.is_linear()
            for_normal = bitmap.used_as_normal_map()
            if self.always_extract_bitmaps:
                image_path = bitmap.save_to_tiff(for_normal)
            else:
                if system_tiff_path.exists():
                    image_path = str(system_tiff_path)
                elif alt_system_tiff_path.exists():
                    image_path = str(alt_system_tiff_path)
                else:
                    image_path = bitmap.save_to_tiff(for_normal)
                    
            # Check if this image is a plate
            plate_dir = Path(image_path).with_suffix("")
            if plate_dir.exists() and plate_dir.is_dir():
                print(plate_dir)
                plate_info = []
                tifs = list(plate_dir.iterdir())
                plate_info.append(len(tifs))
                
            image = bpy.data.images.load(filepath=image_path, check_existing=True)
            if plate_info:
                plate_info.append(image.size[0])

            if for_normal:
                image.colorspace_settings.name = 'Non-Color'
            else:
                image.colorspace_settings.name = 'Linear Rec.709'
                image.alpha_mode = 'CHANNEL_PACKED'
            # if bitmap.uses_srgb():
            #     image.alpha_mode = 'CHANNEL_PACKED'
            # else:
            #     image.colorspace_settings.name = 'Non-Color'
                
            return image, wrap_mode, plate_info
    
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
                
    def _value_from_parameter(self, parameter: OptionParameter, value_type: AnimatedParameterType):
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == parameter.name:
                break
        else:
            if not self.corinth and self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    return shader._value_from_parameter(parameter, value_type)
            else:
                return parameter.default
            
        for element in element.SelectField(self.function_parameters).Elements:
            if element.Fields[0].Value != value_type.value:
                continue
            ap = AnimatedParameter()
            ap.from_element(element, self.animated_function)
            return ap

        if not self.corinth and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                return shader._value_from_parameter(parameter, value_type)
        else:
            return parameter.default
    
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
            
    def _tiling_from_animated_parameters(self, tree: bpy.types.NodeTree, parameter: OptionParameter, needs_texcoord_node=True):
        animated_parameters = {}

        if not self.corinth and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                shader._recursive_tiling_parameters_get(parameter, animated_parameters)
                
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == parameter.name:
                for element in element.SelectField(self.function_parameters).Elements:
                    value_type = AnimatedParameterType(element.Fields[0].Value)
                    if value_type in {AnimatedParameterType.SCALE_UNIFORM, AnimatedParameterType.SCALE_X, AnimatedParameterType.SCALE_Y, AnimatedParameterType.TRANSLATION_X, AnimatedParameterType.TRANSLATION_Y}:
                        ap = AnimatedParameter()
                        ap.from_element(element, self.animated_function)
                        # if value_type == AnimatedParameterType.TRANSLATION_Y and ap.clamp_min != 0:
                        #     ap.clamp_min = -3.669 * ap.clamp_min -33.125
                        animated_parameters[value_type] = ap
        
        if animated_parameters:
            tiling_node = tree.nodes.new('ShaderNodeGroup')
            tiling_node.node_tree = utils.add_node_from_resources("shared_nodes", 'Texture Tiling')
            if needs_texcoord_node:
                self.add_texcoord_node(tree, tiling_node.inputs["Vector"])
            for value_type, ap in animated_parameters.items():
                self._setup_input_with_function(tiling_node.inputs[TilingNodeInputs[value_type.name].value], ap)
            return tiling_node
    
    def _recursive_tiling_parameters_get(self, parameter: OptionParameter, animated_parameters: dict):
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == parameter.name:
                for element in element.SelectField(self.function_parameters).Elements:
                    value_type = AnimatedParameterType(element.Fields[0].Value)
                    if value_type in {AnimatedParameterType.SCALE_UNIFORM, AnimatedParameterType.SCALE_X, AnimatedParameterType.SCALE_Y, AnimatedParameterType.TRANSLATION_X, AnimatedParameterType.TRANSLATION_Y}:
                        ap = AnimatedParameter()
                        ap.from_element(element, self.animated_function)
                        animated_parameters[value_type] = ap
                    
        if not self.corinth and self.reference.Path:
            with ShaderTag(path=self.reference.Path) as shader:
                shader._recursive_tiling_parameters_get(parameter, animated_parameters)
            
    def group_set_image(self, tree: bpy.types.NodeTree, node: bpy.types.Node, parameter: OptionParameter, channel_type=ChannelType.DEFAULT, specified_input=None):
        result = self._image_from_parameter(parameter)
        if result is None:
            return
        
        data, wrap_mode, plate_info = result
        
        if data is None:
            return
        
        data_node = tree.nodes.new("ShaderNodeTexImage")
        data_node.image = data
        data_node.extension = wrap_mode
        
        if plate_info is not None:
            plate_node = tree.nodes.new('ShaderNodeGroup')
            plate_node.node_tree = utils.add_node_from_resources("shared_nodes", 'Plate')
            plate_node.inputs[1].default_value = plate_info[0]
            plate_node.inputs[2].default_value = plate_info[1]
            tree.links.new(input=data_node.inputs[0], output=plate_node.outputs[0])
        
        if specified_input is None:
            match channel_type:
                case ChannelType.DEFAULT:
                    tree.links.new(input=node.inputs[parameter.ui_name], output=data_node.outputs[0])
                case ChannelType.RGB:
                    tree.links.new(input=node.inputs[f"{parameter.ui_name}.rgb"], output=data_node.outputs[0])
                case ChannelType.ALPHA:
                    tree.links.new(input=node.inputs[f"{parameter.ui_name}.a"], output=data_node.outputs[1])
                case ChannelType.RGB_ALPHA:
                    tree.links.new(input=node.inputs[f"{parameter.ui_name}.rgb"], output=data_node.outputs[0])
                    tree.links.new(input=node.inputs[f"{parameter.ui_name}.a"], output=data_node.outputs[1])
        else:
            match channel_type:
                case ChannelType.DEFAULT | ChannelType.RGB:
                    tree.links.new(input=node.inputs[specified_input], output=data_node.outputs[0])
                case ChannelType.ALPHA:
                    tree.links.new(input=node.inputs[specified_input], output=data_node.outputs[1])
        
        tiling_node = self._tiling_from_animated_parameters(tree, parameter, not plate_info)
        if tiling_node is not None:
            if plate_info:
                tree.links.new(input=plate_node.inputs[0], output=tiling_node.outputs[0])
            else:
                tree.links.new(input=data_node.inputs[0], output=tiling_node.outputs[0])
        elif plate_info:
            self._setup_input_with_function(plate_node.inputs["Image Index"], self._value_from_parameter(parameter, AnimatedParameterType.FRAME_INDEX))
            self.add_texcoord_node(tree, plate_node.inputs[0])
        
        return data_node
    
    def _set_input_from_animated_parameter(self, tree: bpy.types.NodeTree, input, ap: AnimatedParameter):
        match ap.master_type:
            case FunctionEditorMasterType.Basic:
                if ap.color_type != FunctionEditorColorGraphType.Scalar:
                    input.default_value = ap.colors[0]
                else:
                    input.default_value = ap.input_min
            case FunctionEditorMasterType.Curve:
                # I'm scared
                pass
            case FunctionEditorMasterType.Periodic:
                pass
    
    def _add_group_node(self, tree: bpy.types.NodeTree, nodes: bpy.types.Nodes, name: str) -> bpy.types.Node:
        node = nodes.new(type='ShaderNodeGroup')
        node.node_tree = utils.add_node_from_resources("reach_nodes", name)
        self.populate_chiefster_node(tree, node)
        return node
    
    def get_model_material_spec(self, node_material_model, uses_spec_exponent_min_max: bool):
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
                        
                    node_material_model.inputs["glancing_specular_color"].default_value = glancing_color.Red, glancing_color.Green, glancing_color.Blue, 1
                    node_material_model.inputs["normal_specular_color"].default_value = normal_color.Red, normal_color.Green, normal_color.Blue, 1
                    node_material_model.inputs["specular_color_exponent"].default_value = value.GetExponent(0)
                    if uses_spec_exponent_min_max:
                        node_material_model.inputs["specular_color_exponent_min"].default_value = value.GetAmplitudeMin(0)
                        node_material_model.inputs["specular_color_exponent_max"].default_value = value.GetAmplitudeMax(0)
                    break
                else:
                    if self.reference.Path:
                        with ShaderTag(path=self.reference.Path) as shader:
                            shader.get_model_material_spec(node_material_model, uses_spec_exponent_min_max)
                break
        else:
            if self.reference.Path:
                with ShaderTag(path=self.reference.Path) as shader:
                    shader.get_model_material_spec(node_material_model, uses_spec_exponent_min_max)
    
    def _add_group_material_model(self, tree: bpy.types.NodeTree, nodes: bpy.types.Nodes, name: str, supports_glancing_spec: bool, uses_spec_exponent_min_max: bool) -> bpy.types.Node:
        node_material_model = nodes.new(type="ShaderNodeGroup")
        node_material_model.node_tree = utils.add_node_from_resources("reach_nodes", f"material_model - {name}")
            
        self.populate_chiefster_node(tree, node_material_model)
        
        # specular color has be dealt with specially
        if supports_glancing_spec:
            self.get_model_material_spec(node_material_model, uses_spec_exponent_min_max)

        return node_material_model
    
    def add_texcoord_node(self, tree, input):
        nodes = tree.nodes
        node = nodes.new(type="ShaderNodeTexCoord")
        tree.links.new(input=input, output=node.outputs[2])
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
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
        
        if e_material_model.value > 4:
            old_model = e_material_model.name
            e_material_model = MaterialModel.COOK_TORRANCE
            utils.print_warning(f"Unsupported material model : {old_model}. Using {e_material_model.name} instead")
            
        if e_bump_mapping.value > 4:
            old_bump = e_bump_mapping.name
            e_bump_mapping = BumpMapping.STANDARD
            utils.print_warning(f"Unsupported bump mapping : {old_bump}. Using {e_bump_mapping.name} instead")
            
        if e_environment_mapping.value > 2:
            old_env = e_environment_mapping.name
            e_environment_mapping = EnvironmentMapping.DYNAMIC
            utils.print_warning(f"Unsupported environment mapping : {old_env}. Using {e_environment_mapping.name} instead")
        
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["albedo"][utils.game_str(e_albedo.name)])
        self.shader_parameters.update(self.category_parameters["bump_mapping"][utils.game_str(e_bump_mapping.name)])
        self.shader_parameters.update(self.category_parameters["alpha_test"][utils.game_str(e_alpha_test.name)])
        self.shader_parameters.update(self.category_parameters["specular_mask"][utils.game_str(e_specular_mask.name)])
        self.shader_parameters.update(self.category_parameters["material_model"][utils.game_str(e_material_model.name)])
        self.shader_parameters.update(self.category_parameters["environment_mapping"][utils.game_str(e_environment_mapping.name)])
        self.shader_parameters.update(self.category_parameters["self_illumination"][utils.game_str(e_self_illumination.name)])
        self.shader_parameters.update(self.category_parameters["blend_mode"][utils.game_str(e_blend_mode.name)])
        # self.shader_parameters.update(self.category_parameters[utils.game_str(e_parallax.name)])
        # self.shader_parameters.update(self.category_parameters[utils.game_str(e_misc.name)])
        # self.shader_parameters.update(self.category_parameters[utils.game_str(e_wetness.name)])
        self.shader_parameters.update(self.category_parameters["alpha_blend_source"][utils.game_str(e_alpha_blend_source.name)])
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}

        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        illum_uses_diffuse = e_self_illumination in {SelfIllumination.FROM_DIFFUSE, SelfIllumination.SELF_ILLUM_TIMES_DIFFUSE}
        has_illum = e_self_illumination != SelfIllumination.OFF
        has_albedo = illum_uses_diffuse or not has_illum
        
        if has_albedo:
            node_albedo = self._add_group_node(tree, nodes, f"albedo - {utils.game_str(e_albedo.name)}")
            final_node = node_albedo
        
        no_material_model = e_material_model == MaterialModel.NONE
        has_bump = e_bump_mapping.value > 0 and not no_material_model
        mm_supports_glancing_spec = False
        material_model_has_alpha_input = False
        if e_material_model != MaterialModel.NONE:
            material_model_has_alpha_input = e_material_model != MaterialModel.FOLIAGE
            mm_supports_glancing_spec = e_material_model.value > 0
            node_material_model = self._add_group_material_model(tree, nodes, utils.game_str(e_material_model.name), mm_supports_glancing_spec, e_material_model == MaterialModel.COOK_TORRANCE)
            final_node = node_material_model
        
        if has_albedo and e_albedo == Albedo.FOUR_CHANGE_COLOR_APPLYING_TO_SPECULAR and mm_supports_glancing_spec:
            tree.links.new(input=node_material_model.inputs["glancing_specular_color"], output=node_albedo.outputs["glancing_specular_color"])
            tree.links.new(input=node_material_model.inputs["normal_specular_color"], output=node_albedo.outputs["normal_specular_color"])
        
        if has_albedo and e_albedo in {Albedo.FOUR_CHANGE_COLOR, Albedo.FOUR_CHANGE_COLOR_APPLYING_TO_SPECULAR, Albedo.TWO_CHANGE_COLOR}:
            node_cc_primary = nodes.new(type="ShaderNodeAttribute")
            node_cc_primary.attribute_name = "change_color_primary"
            node_cc_primary.attribute_type = 'INSTANCER'
            tree.links.new(input=node_albedo.inputs["Primary Color"], output=node_cc_primary.outputs[0])
            self.game_functions.add("change_color_primary")
            node_cc_secondary = nodes.new(type="ShaderNodeAttribute")
            node_cc_secondary.attribute_name = "change_color_secondary"
            node_cc_secondary.attribute_type = 'INSTANCER'
            tree.links.new(input=node_albedo.inputs["Secondary Color"], output=node_cc_secondary.outputs[0])
            self.game_functions.add("change_color_secondary")

            if e_albedo != Albedo.TWO_CHANGE_COLOR:
                node_cc_tertiary = nodes.new(type="ShaderNodeAttribute")
                node_cc_tertiary.attribute_name = "change_color_tertiary"
                node_cc_tertiary.attribute_type = 'INSTANCER'
                tree.links.new(input=node_albedo.inputs["Tertiary Color"], output=node_cc_tertiary.outputs[0])
                self.game_functions.add("change_color_tertiary")
                node_cc_quaternary = nodes.new(type="ShaderNodeAttribute")
                node_cc_quaternary.attribute_name = "change_color_quaternary"
                node_cc_quaternary.attribute_type = 'INSTANCER'
                tree.links.new(input=node_albedo.inputs["Quaternary Color"], output=node_cc_quaternary.outputs[0])
                self.game_functions.add("change_color_quaternary")
        
        if not no_material_model and has_albedo:
            tree.links.new(input=node_material_model.inputs[0], output=node_albedo.outputs[0])
            if material_model_has_alpha_input: # Diffuse only does not have alpha input
                match e_specular_mask:
                    case SpecularMask.SPECULAR_MASK_FROM_DIFFUSE:
                        tree.links.new(input=node_material_model.inputs[1], output=node_albedo.outputs[1])
                    case SpecularMask.SPECULAR_MASK_FROM_TEXTURE | SpecularMask.SPECULAR_MASK_MULT_DIFFUSE:
                        spec_param = self.true_parameters.get("specular_mask_texture")
                        if spec_param is not None:
                            self.group_set_image(tree, node_material_model, spec_param, ChannelType.ALPHA, specified_input=1)
        
        if has_bump:
            node_bump_mapping = self._add_group_node(tree, nodes, f"bump_mapping - {utils.game_str(e_bump_mapping.name)}")
            tree.links.new(input=node_material_model.inputs["Normal"], output=node_bump_mapping.outputs[0])
            
        if e_environment_mapping.value > 0 and not no_material_model:
            node_environment_mapping = self._add_group_node(tree, nodes, f"environment_mapping - {utils.game_str(e_environment_mapping.name)}")
            tree.links.new(input=node_environment_mapping.inputs[0], output=node_material_model.outputs[1])
            if e_environment_mapping == EnvironmentMapping.DYNAMIC:
                tree.links.new(input=node_environment_mapping.inputs[1], output=node_material_model.outputs[2])
                
            node_model_environment_add = nodes.new(type='ShaderNodeAddShader')
            tree.links.new(input=node_model_environment_add.inputs[0], output=node_material_model.outputs[0])
            tree.links.new(input=node_model_environment_add.inputs[1], output=node_environment_mapping.outputs[0])
            final_node = node_model_environment_add
            if has_bump:
                tree.links.new(input=node_environment_mapping.inputs["Normal"], output=node_bump_mapping.outputs[0])
            
        if e_self_illumination.value > 0:
            node_self_illumination = self._add_group_node(tree, nodes, f"self_illumination - {utils.game_str(e_self_illumination.name)}")
            final_node = node_self_illumination
            if e_self_illumination == SelfIllumination.PALETTIZED_PLASMA:
                node_self_illumination_vector = self._add_group_node(tree, nodes, f"self_illumination - palettized_plasma - Vector")
                end_node = utils.get_end_node(node_self_illumination)
                tree.links.new(input=end_node.inputs[0], output=node_self_illumination_vector.outputs[0])
                    
            elif e_self_illumination in {SelfIllumination.FROM_DIFFUSE, SelfIllumination.SELF_ILLUM_TIMES_DIFFUSE}:
                tree.links.new(input=node_self_illumination.inputs[0], output=node_albedo.outputs[0])
            if has_albedo:
                node_illum_add = nodes.new(type='ShaderNodeAddShader')
                tree.links.new(input=node_illum_add.inputs[0], output=node_albedo.outputs[0])
                tree.links.new(input=node_illum_add.inputs[1], output=node_self_illumination.outputs[0])
                final_node = node_illum_add
            
        if e_blend_mode in {BlendMode.ADDITIVE, BlendMode.ALPHA_BLEND}:
            blender_material.surface_render_method = 'BLENDED'
            node_blend_mode = self._add_group_node(tree, nodes, f"blend_mode - {utils.game_str(e_blend_mode.name)}")
            node_blend_mode.inputs["material is two-sided"].default_value = True
            tree.links.new(input=node_blend_mode.inputs[0], output=final_node.outputs[0])
            final_node = node_blend_mode
            if e_blend_mode == BlendMode.ALPHA_BLEND:
                if e_alpha_blend_source.value > 0:
                    node_alpha_blend_source = self._add_group_node(tree, nodes, f"alpha_blend_source - {utils.game_str(e_alpha_blend_source.name)}")
                    tree.links.new(input=node_blend_mode.inputs[1], output=node_alpha_blend_source.outputs[0])
                    if has_bump:
                        tree.links.new(input=node_alpha_blend_source.inputs["Normal"], output=node_bump_mapping.outputs[0])
                elif has_albedo:
                    tree.links.new(input=node_blend_mode.inputs[1], output=node_albedo.outputs[1])
            
        if e_alpha_test.value > 0:
            node_alpha_test = self._add_group_node(tree, nodes, f"alpha_test - {utils.game_str(e_alpha_test.name)}")
            node_alpha_test.inputs["two-sided material"].default_value = True
            tree.links.new(input=node_alpha_test.inputs[1], output=final_node.outputs[0])
            final_node = node_alpha_test
            
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')

        # Link to output
        tree.links.new(input=node_output.inputs[0], output=final_node.outputs[0])
        
    def _setup_input_with_function(self, end_input, data: float | tuple | AnimatedParameter, for_alpha=False):
        tree: bpy.types.NodeTree = end_input.id_data
        if not isinstance(data, AnimatedParameter):
            if type(data) == tuple:
                if for_alpha:
                    end_input.default_value = data[1]
                else:
                    end_input.default_value = data[0]
            else:
                end_input.default_value = data
            return

        if data.master_type == FunctionEditorMasterType.Basic and not data.is_ranged:
            if data.color_type != FunctionEditorColorGraphType.Scalar and end_input.type == 'RGBA':
                end_input.default_value = data.colors[0]
            elif data.color_type == FunctionEditorColorGraphType.Scalar and end_input.type in {'VALUE', 'INT', 'BOOLEAN', 'ROTATION'}:
                if end_input.type == 'INT':
                    end_input.default_value = int(data.clamp_min)
                else:
                    end_input.default_value = data.clamp_min
            return
        
        function_node = tree.nodes.new('ShaderNodeGroup')
        first_node_input = function_node
        first_node_range = function_node
        
        # print(self.tag_path.ShortName, data.color_type.name, data.master_type.name)
        
        match data.color_type:
            case FunctionEditorColorGraphType.Scalar:
                function_node.node_tree = utils.add_node_from_resources("reach_nodes", "Function - 2-float")
                function_node.inputs[1].default_value = data.clamp_min
                function_node.inputs[2].default_value = data.clamp_max
            case FunctionEditorColorGraphType.TwoColor:
                function_node.node_tree = utils.add_node_from_resources("reach_nodes", "Function - 2-color")
                function_node.inputs[1].default_value = data.colors[0]
                function_node.inputs[2].default_value = data.colors[1]
            case FunctionEditorColorGraphType.ThreeColor:
                function_node.node_tree = utils.add_node_from_resources("reach_nodes", "Function - 3-color")
                function_node.inputs[1].default_value = data.colors[0]
                function_node.inputs[2].default_value = data.colors[1]
                function_node.inputs[3].default_value = data.colors[2]
            case FunctionEditorColorGraphType.FourColor:
                function_node.node_tree = utils.add_node_from_resources("reach_nodes", "Function - 4-color")
                function_node.inputs[1].default_value = data.colors[0]
                function_node.inputs[2].default_value = data.colors[1]
                function_node.inputs[3].default_value = data.colors[2]
                function_node.inputs[4].default_value = data.colors[3]
        
        if data.master_type not in {FunctionEditorMasterType.Basic, FunctionEditorMasterType.Curve}:
            clamp_node = tree.nodes.new('ShaderNodeClamp')
            clamp_node.inputs["Max"].default_value = data.input_max
            clamp_node.inputs["Min"].default_value = data.input_min
            if data.is_ranged:
                clamp_node_ranged = tree.nodes.new('ShaderNodeClamp')
                clamp_node_ranged.inputs["Max"].default_value = data.range_max
                clamp_node_ranged.inputs["Min"].default_value = data.range_min
                mix_clamp_node = tree.nodes.new('ShaderNodeMix')
                mix_clamp_node.clamp_factor = True
                mix_clamp_node.inputs[0].default_value = 0.5
                tree.links.new(input=mix_clamp_node.inputs["A"], output=clamp_node.outputs[0])
                tree.links.new(input=mix_clamp_node.inputs["B"], output=clamp_node_ranged.outputs[0])
                tree.links.new(input=function_node.inputs[0], output=mix_clamp_node.outputs[0])
                first_node_input = clamp_node
                first_node_range = clamp_node_ranged
            else:
                tree.links.new(input=function_node.inputs[0], output=clamp_node.outputs[0])
                first_node_input = clamp_node
                
        if data.master_type != FunctionEditorMasterType.Basic and data.is_exclusion:
            exclusion_node = tree.nodes.new('ShaderNodeGroup')
            periodic_node.node_tree = utils.add_node_from_resources("shared_nodes", "Exclusion")
        
        match data.master_type:
            case FunctionEditorMasterType.Curve:
                curve_node = tree.nodes.new('ShaderNodeFloatCurve')
                tree.links.new(input=first_node_input.inputs[0], output=curve_node.outputs[0])
                first_node_input = curve_node
                if data.is_ranged:
                    curve_node_range = tree.nodes.new('ShaderNodeFloatCurve')
                    tree.links.new(input=first_node_range.inputs[0], output=curve_node_range.outputs[0])
                    first_node_range = curve_node_range
            case FunctionEditorMasterType.Periodic:
                periodic_node = tree.nodes.new('ShaderNodeGroup')
                periodic_node.node_tree = utils.add_node_from_resources("reach_nodes", f"periodic function type - {data.input_periodic_function}")
                if data.input_periodic_function not in {"one", "zero"}:
                    periodic_node.inputs[1].default_value = data.input_frequency
                    periodic_node.inputs[2].default_value = data.input_phase
                tree.links.new(input=first_node_input.inputs[0], output=periodic_node.outputs[0])
                first_node_input = periodic_node
                if data.is_ranged:
                    periodic_node_range = tree.nodes.new('ShaderNodeGroup')
                    periodic_node_range.node_tree = utils.add_node_from_resources("reach_nodes", f"periodic function type - {data.range_periodic_function}")
                    if data.range_periodic_function not in {"one", "zero"}:
                        periodic_node_range.inputs[1].default_value = data.range_frequency
                        periodic_node_range.inputs[2].default_value = data.range_phase
                    tree.links.new(input=first_node_range.inputs[0], output=periodic_node_range.outputs[0])
                    first_node_range = periodic_node_range
            case FunctionEditorMasterType.Exponent:
                math_node = tree.nodes.new('ShaderNodeMath')
                math_node.operation = 'EXPONENT'
                math_node.inputs[0].default_value = data.input_exponent
                tree.links.new(input=first_node_input.inputs[0], output=math_node.outputs[0])
                first_node_input = math_node
                if data.is_ranged:
                    math_node_range = tree.nodes.new('ShaderNodeMath')
                    math_node_range.operation = 'EXPONENT'
                    math_node_range.inputs[0].default_value = data.range_exponent
                    tree.links.new(input=first_node_range.inputs[0], output=math_node_range.outputs[0])
                    first_node_range = math_node_range
            case FunctionEditorMasterType.Transition:
                transition_node = tree.nodes.new('ShaderNodeGroup')
                transition_node.node_tree = utils.add_node_from_resources("reach_nodes", f"transition function type - {data.input_transition_function}")
                tree.links.new(input=first_node_input.inputs[0], output=transition_node.outputs[0])
                first_node_input = transition_node
                if data.is_ranged:
                    transition_node_range = tree.nodes.new('ShaderNodeGroup')
                    transition_node_range.node_tree = utils.add_node_from_resources("reach_nodes", f"transition function type - {data.range_transition_function}")
                    tree.links.new(input=first_node_range.inputs[0], output=transition_node_range.outputs[0])
                    first_node_range = transition_node_range
                
        if data.input:
            attribute_node = tree.nodes.new('ShaderNodeAttribute')
            attribute_node.attribute_type = 'INSTANCER'
            if data.input in ammo_names:
                attribute_node.attribute_name = "ammo"
                digits_node = tree.nodes.new('ShaderNodeGroup')
                digits_node.node_tree = utils.add_node_from_resources("shared_nodes", f"Digits")
                tree.links.new(input=digits_node.inputs[0], output=attribute_node.outputs[2])
                tree.links.new(input=first_node_input.inputs[1] if data.master_type == FunctionEditorMasterType.Curve else first_node_input.inputs[0], output=digits_node.outputs[data.input.rpartition("_")[2].capitalize()])
            else:
                attribute_node.attribute_name = data.input
                tree.links.new(input=first_node_input.inputs[1] if data.master_type == FunctionEditorMasterType.Curve else first_node_input.inputs[0], output=attribute_node.outputs[2])
            if data.is_ranged:
                attribute_node_range = tree.nodes.new('ShaderNodeAttribute')
                attribute_node_range.attribute_type = 'INSTANCER'
                if data.range in ammo_names:
                    attribute_node_range.attribute_name = "ammo"
                    digits_node_range = tree.nodes.new('ShaderNodeGroup')
                    digits_node_range.node_tree = utils.add_node_from_resources("shared_nodes", f"Digits")
                    tree.links.new(input=digits_node_range.inputs[0], output=attribute_node_range.outputs[2])
                    tree.links.new(input=first_node_range.inputs[1] if data.master_type == FunctionEditorMasterType.Curve else first_node_range.inputs[0], output=digits_node_range.outputs[data.range.rpartition("_")[2].capitalize()])
                else:
                    attribute_node_range.attribute_name = data.range
                    tree.links.new(input=first_node_range.inputs[1] if data.master_type == FunctionEditorMasterType.Curve else first_node_range.inputs[0], output=attribute_node_range.outputs[2])
            
        tree.links.new(input=end_input, output=function_node.outputs[0])
        
    
    def populate_chiefster_node(self, tree: bpy.types.NodeTree, node: bpy.types.Node):
        last_parameter_name = None
        last_input_node = None
        for input in node.inputs:
            parameter_name_ui = input.name.lower() if "." not in input.name else input.name.partition(".")[0].lower()
            if "gamma curve" in parameter_name_ui:
                if "base_map" in parameter_name_ui:
                    input.default_value = 2.2
                else:
                    input.default_value = 1
                # if last_input_node.image.colorspace_settings.name == 'Non-Color':
                #     input.default_value = 1
                # else:
                #     input.default_value = 1.95
                last_parameter_name = None
                continue
            input: bpy.types.NodeGroupInput
            if parameter_name_ui == last_parameter_name and last_input_node is not None:
                # plug in alpha
                alpha_input = node.inputs.get(f"{parameter_name_ui}.a")
                if alpha_input is None:
                    alpha_input = node.inputs[f"{parameter_name_ui}.a/specular_mask.a"]
                tree.links.new(input=alpha_input, output=last_input_node.outputs[1])
            elif parameter_name_ui == f"{last_parameter_name}_alpha":
                self._setup_input_with_function(input, self._value_from_parameter(self.true_parameters.get(last_parameter_name), AnimatedParameterType.ALPHA), True)
            else:
                # parameter_type = self._parameter_type_from_name(parameter_name)
                parameter = self.true_parameters.get(parameter_name_ui)
                if parameter is None:
                    last_parameter_name = None
                    continue
                parameter_type = ParameterType(parameter.type)
                match parameter_type:
                    case ParameterType.COLOR | ParameterType.ARGB_COLOR:
                        self._setup_input_with_function(input, self._value_from_parameter(parameter, AnimatedParameterType.COLOR))
                    case ParameterType.REAL | ParameterType.INT | ParameterType.BOOL:
                        self._setup_input_with_function(input, self._value_from_parameter(parameter, AnimatedParameterType.VALUE))
                    case _:
                        if ".rgb" in input.name:
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.RGB)
                        elif ".a" in input.name:
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.ALPHA)
                        else:
                            last_input_node = self.group_set_image(tree, node, parameter, ChannelType.DEFAULT)
                        
                last_parameter_name = parameter_name_ui
                
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
        if not (self.data or self.default_value) or self.data == self.default_value:
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
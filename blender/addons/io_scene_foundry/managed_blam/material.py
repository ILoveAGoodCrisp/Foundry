

import os
from pathlib import Path
from typing import cast
from mathutils import Vector

from .connected_material import AnimatedParameterType, Function
from .Tags import TagFieldBlockElement, TagPath

from .bitmap import BitmapTag
from .material_shader import MaterialShaderParameter, MaterialShaderTag, convert_argb
from .shader import BSDFParameter, ChannelType, ParameterType, ShaderTag
from .. import utils
import bpy

from ..constants import MATERIAL_SHADERS_DIR

srgb_names = "color map", "control map", "self illum"

class MaterialParameter:
    def __init__(self, material_shader_parameter: MaterialShaderParameter):
        self.name = material_shader_parameter.name
        self.ui_name = material_shader_parameter.ui_name
        self.type = material_shader_parameter.type
        self.default = material_shader_parameter.default
        self.functions: list[Function] = []
        
    def from_element(self, element: TagFieldBlockElement):
        match self.type:
            case 0:
                bitmap_path = element.SelectField("bitmap").Path
                if bitmap_path is not None:
                    self.default = bitmap_path
            case 1:
                self.default = element.SelectField("real").Data
            case 2 | 3:
                self.default = element.SelectField(r"int\bool").Data
            case 4:
                self.default = convert_argb(element.SelectField("color").Data)
            
class MaterialTag(ShaderTag):
    tag_ext = 'material'
    scale_u = 'scale u'
    scale_v = 'scale v'
    translation_u = 'offset x'
    translation_v = 'offset y'
    function_parameters = 'function parameters'
    animated_function = 'function'
    color_parameter_type = 'color'
    group_supported = True
    
    default_parameters = None
    shader_parameters = None
    material_parameters: dict[str: MaterialParameter] = None
    
    global_material_shader = None
    last_group_node = None
    last_material_shader = None
    group_node = None
    
    material_shaders = {}
    
    def _read_fields(self):
        self.block_parameters = self.tag.SelectField("Block:material parameters")
        self.reference_material_shader = self.tag.SelectField("Reference:material shader")
        self.alpha_blend_mode = self.tag.SelectField('CharEnum:alpha blend mode')
    
    @classmethod
    def _get_info(cls, material_shader_path: TagPath):
        if material_shader_path is None:
            return
        
        material_parameters = cls.material_shaders.get(material_shader_path.ShortName)
        if material_parameters is None:
            with MaterialShaderTag(path=material_shader_path) as material_shader:
                material_parameters = material_shader.get_defaults()
                cls.material_shaders[material_shader.tag_path.ShortName] = material_parameters
        
        # with MaterialShaderTag(path=material_shader_path) as material_shader:
        #     cls.default_parameters, cls.shader_parameters = material_shader.get_defaults()
        # if not cls.global_material_shader or cls.last_group_node != cls.group_node or path == "":
        #     group_node_name = utils.dot_partition(cls.group_node.node_tree.name.lower().replace(' ', '_'))
        #     path = cls._material_shader_path_from_group_node(group_node_name)
        #     assert path, f"Group node in use for material but no corresponding material shader found. Expected material shader named {group_node_name} in {MATERIAL_SHADERS_DIR} (or sub-folders)"
        #     with MaterialShaderTag(path=path) as material_shader:
        #         cls.material_shader_data[material_shader.tag_path.RelativePath] = material_shader.read_parameters()

    def _material_shader_path_from_group_node(self, group_node_name):
        filename = group_node_name + '.material_shader'
        return utils.relative_path(utils.find_file_in_directory(str(Path(self.tags_dir, MATERIAL_SHADERS_DIR)), filename))
                
    def _from_nodes_group(self):
        name_type_node_dict = {}
        inputs = self.group_node.inputs
        cull_chars = " _-()'\""
        for i in inputs:
            for parameter_name, value in self.global_material_shader.items():
                d_name, param_type = value
                parameter_name_culled = utils.remove_chars(parameter_name.lower(), cull_chars)
                display_name = utils.remove_chars(d_name.lower(), cull_chars)
                input_name = utils.remove_chars(i.name.lower(), cull_chars)
                if input_name == parameter_name_culled or input_name == display_name:
                    name_type_node_dict[parameter_name] = [param_type, self._source_from_input_and_parameter_type(i, param_type)]
                    break
                    
        for name, value in name_type_node_dict.items():
            param_type, source = value
            element = self._setup_parameter(source, name, param_type)
            if element:
                mapping = self._setup_function_parameters(source, element, param_type)
                self._finalize_material_parameters(mapping, element)
        
        group_node_name = utils.dot_partition(self.group_node.node_tree.name.lower().replace(' ', '_'))
        self.reference_material_shader.Path = self._TagPath_from_string(self._material_shader_path_from_group_node(group_node_name))
                
    def _build_basic(self, map: dict):
        # Set up shader parameters
        self.group_node = map.get("bsdf")
        spec_alpha_from_diffuse = False
        si_alpha_from_diffuse = False
        if map.get('diffuse', 0):
            element = self._setup_parameter(map['diffuse'], 'color_map', 'bitmap')
            if element:
                mapping = self._setup_function_parameters(map['diffuse'], element, 'bitmap')
                self._finalize_material_parameters(mapping, element)
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'albedo_tint')
            diff_alpha_output: bpy.types.NodeInputs = map['diffuse'].outputs[1]
            if diff_alpha_output.links:
                for l in diff_alpha_output.links:
                    if l.to_socket.name.lower() == 'specular ior level':
                        spec_alpha_from_diffuse = True
                    if l.to_socket.name.lower() == 'emission color':
                        si_alpha_from_diffuse = True
                
        elif map.get('albedo_tint', 0):
            element = self._setup_parameter(map['albedo_tint'], 'albedo_tint', 'color')
            if element:
                mapping = self._setup_function_parameters(map['albedo_tint'], element, 'color')
                self._finalize_material_parameters(mapping, element)
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'color_map')
        else:
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'color_map')
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'albedo_tint')
                
        if not spec_alpha_from_diffuse and map.get('specular', 0):
            element = self._setup_parameter(map['specular'], 'specular_map', 'bitmap')
            if element:
                mapping = self._setup_function_parameters(map['specular'], element, 'bitmap')
                self._finalize_material_parameters(mapping, element)
        else:
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'specular_map')
            
        if si_alpha_from_diffuse:
            element = self._setup_parameter(map['diffuse'], 'control_map_spglrf', 'bitmap')
            if element:
                mapping = self._setup_function_parameters(map['diffuse'], element, 'bitmap')
                self._finalize_material_parameters(mapping, element)
        else:
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'control_map_spglrf')
            
        if map.get('self_illum', 0):
            element = self._setup_parameter(map['self_illum'], 'selfillum_mod_map', 'bitmap')
            if element:
                mapping = self._setup_function_parameters(map['self_illum'], element, 'bitmap')
                self._finalize_material_parameters(mapping, element)
            element = self._setup_parameter(map['self_illum'], 'selfillum_map', 'bitmap')
            if element:
                mapping = self._setup_function_parameters(map['self_illum'], element, 'bitmap')
                self._finalize_material_parameters(mapping, element)
        else:
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'selfillum_mod_map')
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'selfillum_map')
        
        if si_alpha_from_diffuse or map.get('self_illum', 0):
            si_intensity = map['bsdf'].inputs['Emission Strength'].default_value
            element = self._setup_parameter(si_intensity, 'si_intensity', 'real')
            if element:
                mapping = self._setup_function_parameters(si_intensity, element, 'real')
                self._finalize_material_parameters(mapping, element)
        else:
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'si_intensity')
            
        if map.get('normal', 0):
            element = self._setup_parameter(map['normal'], 'normal_map', 'bitmap')
            if element:
                mapping = self._setup_function_parameters(map['normal'], element, 'bitmap')
                self._finalize_material_parameters(mapping, element)
        else:
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'normal_map')
            
            
        if self.alpha_type == 'blend' and self.alpha_blend_mode.Value == 0:
            self.alpha_blend_mode.Value = 3
        elif not self.alpha_type and self.alpha_blend_mode.Value == 3:
            self.alpha_blend_mode.Value = 0
            
        if self.material_shader:
            self.reference_material_shader.Path = self._TagPath_from_string(self.material_shader)
        elif map.get('albedo_tint', 0) and not map.get('specular', 0) and not map.get('normal', 0):
            if self.alpha_type == 'clip':
                self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_constant_clip.material_shader')
            else:
                self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_constant.material_shader')
        elif si_alpha_from_diffuse:
            self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_ca_blinn_diffspec_selfillum.material_shader')
        elif spec_alpha_from_diffuse:
            if self.alpha_type == 'clip':
                self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_ca_blinn_diffspec_clip.material_shader')
            else:
                self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_ca_blinn_diffspec.material_shader')
        elif map.get('self_illum', 0):
            self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_blinn_selfillum_mod.material_shader')
        elif self.alpha_type == 'clip':
            self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_blinn_clip.material_shader')
        else:
            self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_blinn.material_shader')
            
            
    def _finalize_material_parameters(self, mapping, element):
        color = mapping.get('color', 0)
        if color:
            argb_color = ['1', str(utils.linear_to_srgb(color[0])), str(utils.linear_to_srgb(color[1])), str(utils.linear_to_srgb(color[2]))]
            element.SelectField('color').SetStringData(argb_color)
        if mapping.get(self.scale_u, 0):
            element.SelectField('real').SetStringData(str(mapping.get(self.scale_u)))
        if mapping.get(self.scale_v, 0):
            if mapping.get(self.translation_u, 0):
                element.SelectField('vector').SetStringData([str(mapping.get(self.scale_v), str(mapping.get(self.translation_u)), str(mapping.get(self.translation_v)))])
            else:
                element.SelectField('vector').SetStringData([str(mapping.get(self.scale_v)), '0', '0'])

    
    def _alpha_type(self, material_shader_name):
        if self.alpha_blend_mode.Value != 0:
            return 'blend'
        elif 'clip' in material_shader_name or 'foliage' in material_shader_name:
            return 'clip'
        else:
            return ''
        
    def _get_material_shader_parameter_names(self, material_shader_path):
            with MaterialShaderTag(path=material_shader_path) as material_shader:
                return material_shader.read_parameters_list()
            
    def _map_from_control_name(self, name):
        assert(len(name) == 2), "Expected control name of length 2"
        match name.lower():
            case 'sp':
                return 'specular'
            case 'gl':
                return 'glow'
            case 'rf':
                return 'reflection'
            case 'si':
                return 'self_illum'
            
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
        diffuse = None
        normal = None
        specular = None
        self_illum = None
        alpha = None
        material_shader_name = ''
        parameter_names = []
        if self.reference_material_shader.Path:
            material_shader_name = utils.os_sep_partition(self.reference_material_shader.Path.RelativePath, True)
            parameter_names = self._get_material_shader_parameter_names(self.reference_material_shader.Path)
        
        alpha_type = self._alpha_type(material_shader_name)
        has_color_map = 'color_map' in parameter_names
        has_albedo_tint = 'albedo_tint' in parameter_names
        has_normal_map = 'normal_map' in parameter_names
        has_specular_map = 'specular_map' in parameter_names
        has_self_illum_map = 'selfillum_map' in parameter_names
        has_alpha_map = 'alpha_mask_map' in parameter_names
        
        control_map_name = ''
        for name in parameter_names:
            if name.startswith('control_map_'):
                controls = name.replace('control_map_', '')
                if len(controls) == 6:
                    control_red = self._map_from_control_name(controls[:2])
                    control_green = self._map_from_control_name(controls[2:4])
                    control_blue = self._map_from_control_name(controls[4:6])
                    control_channels = (control_red, control_green, control_blue)
                    control_map_name = name
                
        if control_map_name:
            control_map_node = tree.nodes.new('ShaderNodeTexImage')
            control_map_node.location = Vector((-1000, -100))
            control_map_node.image = self._image_from_parameter_name(control_map_name)
            separate_node = tree.nodes.new('ShaderNodeSeparateColor')
            separate_node.location = Vector((-700, -100))
            tree.links.new(input=separate_node.inputs[0], output=control_map_node.outputs[0])
        
        if has_color_map or has_albedo_tint:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeTexImage', data=self._image_from_parameter_name('color_map'), mapping=self._mapping_from_parameter_name('color_map'), diffalpha=bool(alpha_type))
            if not diffuse.data:
                diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_tint'))
                
        if diffuse and not diffuse.data:
            diffuse = None

        if has_normal_map:
            normal = BSDFParameter(tree, bsdf, bsdf.inputs['Normal'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('normal_map', True), normal_type=self._normal_type_from_parameter_name('normal_map'), mapping=self._mapping_from_parameter_name('normal_map'))
            if normal.data:
                normal.data.colorspace_settings.name = 'Non-Color'
            else:
                normal = None
        
        
        if control_map_name and 'specular' in control_channels:
            tree.links.new(input=bsdf.inputs['Specular IOR Level'], output=separate_node.outputs[control_channels.index('specular')])
        elif diffuse and 'diffspec' in material_shader_name and type(diffuse.data) == bpy.types.Image:
            diffuse.special_type = 'diffspec'
        elif has_specular_map:
            specular = BSDFParameter(tree, bsdf, bsdf.inputs['Specular IOR Level'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('specular_map'), mapping=self._mapping_from_parameter_name('specular_map'))
            if specular.data:
                specular.data.colorspace_settings.name = 'Non-Color'
            else:
                specular = None
                
        control_si = control_map_name and 'self_illum' in control_channels
                
        if control_si:
            tree.links.new(input=bsdf.inputs['Emission Color'], output=separate_node.outputs[control_channels.index('self_illum')])
        elif diffuse and 'selfillum' in material_shader_name and type(diffuse.data) == bpy.types.Image:
            diffuse.diffillum = True
        elif has_self_illum_map:
            self_illum = BSDFParameter(tree, bsdf, bsdf.inputs['Emission Color'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('selfillum_map'), mapping=self._mapping_from_parameter_name('selfillum_map'))
        else:
            self_illum = None
                
        if control_si or (self_illum and self_illum.data):
            bsdf.inputs['Emission Strength'].default_value = 1
            intensity_element = self._Element_from_field_value(self.block_parameters, 'parameter name', 'si_intensity')
            if intensity_element:
                value_element = self._Element_from_field_value(intensity_element.SelectField('function parameters'), 'type', 0)
                if value_element:
                    bsdf.inputs['Emission Strength'].default_value = value_element.SelectField(self.animated_function).Value.ClampRangeMin
                
        if alpha_type:
            if has_alpha_map:
                alpha = BSDFParameter(tree, bsdf, bsdf.inputs['Alpha'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('alpha_mask_map'), mapping=self._mapping_from_parameter_name('alpha_mask_map'))
            else:
                if diffuse and diffuse.data:
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
        for element in self.block_parameters.Elements:
            match element.Fields[0].GetStringData():
                case "color_map":
                    fill_alpha = self.alpha_blend_mode.Value < 1
                case _:
                    continue
                    

            path = element.SelectField("bitmap").Path
            if not path:
                continue
            full_path = path.Filename
            if not os.path.exists(full_path):
                continue
            
            bitmap_path = element.SelectField("bitmap").Path.RelativePathWithExtension
            with BitmapTag(path=bitmap_path) as bitmap:
                return bitmap.get_granny_data(fill_alpha, calc_blue)
            
            
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        if self.reference_material_shader.Path is None:
            return
        material_shader_name = self.reference_material_shader.Path.ShortName
        material_shader_parameters = self.material_shaders.get(material_shader_name)
        if material_shader_parameters is None:
            return

        node_tree = utils.add_node_from_resources("h4_nodes", name=material_shader_name)
        if node_tree is None:
            utils.print_warning(f"No node group for {material_shader_name}, creating BSDF shader nodes")
            return self._to_nodes_bsdf(blender_material)
        
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        nodes.clear()
        group_node = nodes.new(type='ShaderNodeGroup')
        group_node.node_tree = node_tree
        
        material_parameters = {}
        
        for element in self.block_parameters.Elements:
            shader_parameter = material_shader_parameters.get(element.Fields[0].GetStringData())
            if shader_parameter is None:
                continue
            
            mat_par = MaterialParameter(shader_parameter)
            material_parameters[mat_par.ui_name.lower()] = mat_par

        self.populate_chiefster_node(tree, group_node, material_parameters)
        
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')

        # Link to output
        tree.links.new(input=node_output.inputs[0], output=group_node.outputs[0])
            
            
    def populate_chiefster_node(self, tree: bpy.types.NodeTree, node: bpy.types.Node, material_parameters: dict[MaterialParameter]):
        match self.alpha_blend_mode.Value:
            case 0:
                node.inputs[0].default_value = 0.0
            case 3:
                node.inputs[0].default_value = 1.0
            case _:
                node.inputs[0].default_value = 0.5
        
        for input in cast(list[bpy.types.NodeSocket], node.inputs[3:]): # ignore the first 3 inputs
            parameter_name_ui = input.name.lower() if "." not in input.name else input.name.partition(".")[0].lower()
            if "gamma curve" in parameter_name_ui:
                if any(srgb_name in parameter_name_ui for srgb_name in srgb_names):
                    input.default_value = 2.2
                else:
                    input.default_value = 1
            # parameter_type = self._parameter_type_from_name(parameter_name)
            parameter = material_parameters.get(parameter_name_ui)
            if parameter is None:
                continue
            parameter_type = ParameterType(parameter.type)
            match parameter_type:
                case ParameterType.COLOR | ParameterType.ARGB_COLOR:
                    self._setup_input_with_function(input, self._value_from_parameter(parameter, AnimatedParameterType.COLOR))
                case ParameterType.REAL | ParameterType.INT | ParameterType.BOOL:
                    self._setup_input_with_function(input, self._value_from_parameter(parameter, AnimatedParameterType.VALUE))
                case _:
                    self.group_set_image(tree, node, parameter, ChannelType.DEFAULT)
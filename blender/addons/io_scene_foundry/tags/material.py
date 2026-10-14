

from enum import Enum, IntEnum
import os
from pathlib import Path
from typing import cast
from mathutils import Vector
from blam_tags import RealArgbColor, RealVector3d

from .connected_material import AnimatedParameterType, Function
from .backend import TagReference
from .field_view import NativeTagStruct

from .bitmap import BitmapTag
from .material_shader import MaterialShaderParameter, MaterialShaderTag, convert_argb
from .shader_converter import BSDFParameter, ChannelType, ShaderTag
from .. import utils
import bpy

from ..constants import MATERIAL_SHADERS_DIR
from ..material_shader_library import (MATERIAL_LIBRARIES, find_shader_tag,
                                       group_name, parameter_key, source_shader)

srgb_names = "color map", "control map", "self illum"

class ParameterType(Enum):
    NONE = -1
    BITMAP = 0
    REAL = 1
    INT = 2
    BOOL = 3
    COLOR = 4
    
SUPPORTED_BLEND_MODES = {
    "opaque",
    "additive",
    "multiply",
    "alpha_blend",
    "double_multiply",
    "pre_multiplied_alpha",
    "add_src_times_srcalpha",
    "inv_alpha_blend",
    "opaque_alpha_blend",
    "alpha_blend_additive_transparent"
}
    
class MaterialParameter:
    def __init__(self, material_shader_parameter: MaterialShaderParameter):
        self.name = material_shader_parameter.name
        self.ui_name = material_shader_parameter.ui_name
        self.type = material_shader_parameter.type
        self.default = material_shader_parameter.default
        self.functions: list[Function] = []
        self.default_bitmap = material_shader_parameter.default_bitmap
        
    def from_element(self, element: NativeTagStruct):
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
    
    def get_global_material(self):
        return self._native_root.SelectField("StringId:physics material name").GetStringData()
    
    def _read_fields(self):
        self.block_parameters = self._native_root.SelectField("Block:material parameters")
        self.reference_material_shader = self._native_root.SelectField("Reference:material shader")
        self.alpha_blend_mode = self._native_root.SelectField('CharEnum:alpha blend mode')
    
    def _get_info(self, material_shader_path: TagReference | str):
        if material_shader_path is None:
            return
        
        filename = str(Path(self.tags_dir, material_shader_path)) if isinstance(material_shader_path, str) else material_shader_path.Filename
        key = (self.game, os.path.normcase(filename))
        material_parameters = self.material_shaders.get(key)
        if material_parameters is None:
            with MaterialShaderTag(path=material_shader_path) as material_shader:
                material_parameters = material_shader.get_defaults()
                self.material_shaders[key] = material_parameters
        
        return material_parameters
    
    def get_albedo_bitmap(self):
        for element in self.block_parameters.Elements:
            if element.Fields[0].GetStringData() == 'color_map':
                bitmap = element.SelectField("Reference:bitmap").Path
                if self.path_exists(bitmap):
                    return bitmap

    def _material_shader_path_from_group_node(self, group):
        if not isinstance(group, str):
            node = group if getattr(group, 'type', None) == 'GROUP' else None
            resource = node.node_tree if node else group
            if resource.get('foundry_material_game', self.game) != self.game:
                return ''
            # Keep an imported tag's full path, including approximate previews.
            source = node.get('foundry_material_shader_path') if node else None
            source = source or source_shader(resource)
        else:
            source = source_shader(group)
        return find_shader_tag(self.tags_dir, source)

    def _group_node_is_export_candidate(self, group_node: bpy.types.Node | None) -> bool:
        if group_node is None or group_node.type != "GROUP":
            return False
        group_tree = getattr(group_node, "node_tree", None)
        if group_tree is None:
            return False

        return bool(self._material_shader_path_from_group_node(group_node))

    def _material_parameter_from_input(self, input: bpy.types.NodeSocket, parameters: dict[str, MaterialParameter], cull_chars: str, ignored_parameters: set[str] = None):
        ignored_parameters = ignored_parameters or set()
        input_name = utils.remove_chars(input.name.lower(), cull_chars)
        for parameter_name, value in parameters.items():
            if parameter_name in ignored_parameters:
                continue
            parameter_name_culled = utils.remove_chars(parameter_name.lower(), cull_chars)
            display_name = utils.remove_chars(value.ui_name.lower(), cull_chars)
            if input_name == parameter_name_culled or input_name == display_name:
                return parameter_name, value

        return None, None

    def _iter_upstream_group_nodes(self, node: bpy.types.Node):
        visited = []
        pending = []
        for input in node.inputs:
            for link in input.links:
                pending.append(link.from_node)

        while pending:
            upstream_node = pending.pop(0)
            if upstream_node in visited:
                continue

            visited.append(upstream_node)
            if upstream_node.type == 'GROUP':
                yield upstream_node

            for input in upstream_node.inputs:
                for link in input.links:
                    pending.append(link.from_node)

    def _source_from_input_and_parameter_type(self, input, parameter_type, source_node=None):
        if parameter_type == 'bitmap' and input.is_linked:
            sample = input.links[0].from_node
            while sample.type == 'REROUTE' and sample.inputs[0].is_linked:
                sample = sample.inputs[0].links[0].from_node
            original = sample.inputs.get(sample.get('foundry_material_texture_input', ''))
            if original is not None:
                return super()._source_from_input_and_parameter_type(original, parameter_type, sample)
        return super()._source_from_input_and_parameter_type(input, parameter_type, source_node)

    def _function_parameters_from_node(self, source, parameter_type):
        if parameter_type == 'bitmap' and isinstance(source, bpy.types.Node) and source.get('foundry_material_parameter'):
            from .material_source_io import mapping
            return mapping(source, AnimatedParameterType)
        return super()._function_parameters_from_node(source, parameter_type)

    def _from_nodes_group(self):
        name_type_node_dict = {}
        inputs = self.group_node.inputs
        cull_chars = " _-()'\""
        
        group_node_name = self.group_node.node_tree.name
        material_shader_path = self._material_shader_path_from_group_node(self.group_node)
        if not material_shader_path:
            utils.print_warning(f"No material shader found for group node [{group_node_name}]. Falling back to adaptive basic mapping")
            return
        
        self.reference_material_shader.Path = self._TagPath_from_string(material_shader_path)
        if self.reference_material_shader.Path is None:
            utils.print_warning(f"Failed to resolve material shader path [{material_shader_path}] for group node [{group_node_name}]. Falling back to adaptive basic mapping")
            return

        parameters = self._get_info(self.reference_material_shader.Path)
        if not parameters:
            utils.print_warning(f"Material shader defaults missing for [{self.reference_material_shader.Path.ShortName}]. Falling back to adaptive basic mapping")
            return
        
        for i in inputs:
            if i.name == "blend mode":
                if i.type != 'MENU':
                    continue
                blend_mode_items = [i.EnumName for i in self.alpha_blend_mode.Items]
                if i.default_value in blend_mode_items:
                    self.alpha_blend_mode.Value = blend_mode_items.index(i.default_value)
            parameter_name, value = self._material_parameter_from_input(i, parameters, cull_chars)
            if parameter_name:
                name_type_node_dict[parameter_name] = [value.type_name, self._source_from_input_and_parameter_type(i, value.type_name, self.group_node)]

        for upstream_node in self._iter_upstream_group_nodes(self.group_node):
            for i in upstream_node.inputs:
                ignored_parameters = {
                    name for name, (param_type, source) in name_type_node_dict.items()
                    if param_type != 'bitmap' or source is not None
                }
                parameter_name, value = self._material_parameter_from_input(i, parameters, cull_chars, ignored_parameters)
                if parameter_name:
                    name_type_node_dict[parameter_name] = [value.type_name, self._source_from_input_and_parameter_type(i, value.type_name, upstream_node)]

        if self.group_node.node_tree.get('foundry_source_compiled'):
            from .material_source_io import textures
            for name, source in textures(self.group_node).items():
                if name in parameters:
                    name_type_node_dict[name] = ['bitmap', source]

        for name, value in name_type_node_dict.items():
            param_type, source = value
            if source is None:
                if param_type == 'bitmap':
                    self._Element_remove_if_needed(self.block_parameters, 'parameter name', name)
                continue
            element = self._setup_parameter(source, name, param_type)
            if element:
                mapping = self._setup_function_parameters(source, element, param_type)
                self._finalize_material_parameters(mapping, element)
                
        return True
                
    def _build_basic(self, map: dict):
        from .material_basic import write_material
        write_material(self, map)

    def _finalize_material_parameters(self, mapping, element):
        names = {AnimatedParameterType.COLOR: 'color', AnimatedParameterType.VALUE: 'value',
                 AnimatedParameterType.SCALE_X: self.scale_u, AnimatedParameterType.SCALE_Y: self.scale_v,
                 AnimatedParameterType.TRANSLATION_X: self.translation_u,
                 AnimatedParameterType.TRANSLATION_Y: self.translation_v}
        mapping = {names.get(key, key): value for key, value in mapping.items()}
        color = mapping.get('color', 0)
        if color:
            argb_color = [1, utils.linear_to_srgb(color[0]), utils.linear_to_srgb(color[1]), utils.linear_to_srgb(color[2])]
            element.SelectField('color').Data = RealArgbColor(*argb_color)
        if mapping.get(self.scale_u) is not None:
            element.SelectField('real').Data = mapping.get(self.scale_u)
        if mapping.get(self.scale_v) is not None:
            if mapping.get(self.translation_u) is not None:
                element.SelectField('vector').Data = RealVector3d(mapping.get(self.scale_v), mapping.get(self.translation_u), mapping.get(self.translation_v))
            else:
                element.SelectField('vector').Data = RealVector3d(mapping.get(self.scale_v), 0, 0)
        
        value = mapping.get('value')
        if value is not None:
            element.SelectField('real').Data = value
            element.SelectField(r'int\bool').Data = int(value)

    
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
            try:
                with BitmapTag(path=bitmap_path) as bitmap:
                    return bitmap.get_granny_data(fill_alpha, calc_blue)
            except:
                pass
            
            
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        if self.reference_material_shader.Path is None:
            return
        shader_path = self.reference_material_shader.Path.RelativePath
        material_shader_name = self.reference_material_shader.Path.ShortName.casefold()
        material_shader_parameters = self._get_info(self.reference_material_shader.Path)
        if not material_shader_parameters:
            return self._to_nodes_bsdf(blender_material)
        library = MATERIAL_LIBRARIES[self.game]
        node_tree = utils.add_node_from_resources(library, name=shader_path, check_multiple=True)
        if node_tree is None:
            utils.print_warning(f"No node group for {material_shader_name}, creating BSDF shader nodes")
            return self._to_nodes_bsdf(blender_material)
        elif group_name(shader_path).casefold() != node_tree.get('foundry_resource_name', node_tree.name).casefold():
            utils.print_warning(f"Failed to find node group for {material_shader_name}, using {node_tree.name} instead")
        
        tree = blender_material.node_tree
        nodes = tree.nodes
        nodes.clear()
        group_node = nodes.new(type='ShaderNodeGroup')
        group_node.node_tree = node_tree
        group_node['foundry_material_shader_path'] = shader_path
        
        material_parameters = {}
        material_parameters_true = {}
        
        for shader_parameter in material_shader_parameters.values():
            mat_par = MaterialParameter(shader_parameter)
            material_parameters[parameter_key(mat_par.ui_name)] = mat_par
            material_parameters_true[parameter_key(mat_par.name)] = mat_par

        self.populate_chiefster_node(tree, group_node, material_parameters, material_parameters_true)

        if node_tree.get('foundry_source_compiled'):
            from .material_source_io import make_instance, populate
            make_instance(tree, group_node)
            populate(self, group_node, material_parameters_true)
            output = nodes.new('ShaderNodeOutputMaterial')
            tree.links.new(group_node.outputs['Shader'], output.inputs['Surface'])
            if group_node.outputs.get('Displacement') is not None:
                tree.links.new(group_node.outputs['Displacement'], output.inputs['Displacement'])
            return
        
        # Handle special case group nodes
        match material_shader_name:
            case 'srf_pbr_covenant':
                rainbow_node = tree.nodes.new('ShaderNodeGroup')
                rainbow_node.node_tree = utils.add_node_from_resources(library, name='srf_pbr_covenant rainbow_map_vector')
                self.populate_chiefster_node(tree, rainbow_node, material_parameters, material_parameters_true)
                
                if group_node.inputs['rainbow_map'].links:
                    rainbow_map_node = group_node.inputs['rainbow_map'].links[0].from_node
                    tree.links.new(input=rainbow_map_node.inputs[0], output=rainbow_node.outputs[0])
                
                reflection_node = tree.nodes.new('ShaderNodeGroup')
                reflection_node.node_tree = utils.add_node_from_resources(library, name='srf_pbr_covenant reflection_map_vector')
                self.populate_chiefster_node(tree, reflection_node, material_parameters, material_parameters_true)
                
                if rainbow_node.inputs['reflection_map'].links:
                    reflection_map_node = rainbow_node.inputs['reflection_map'].links[0].from_node
                    tree.links.new(input=reflection_map_node.inputs[0], output=reflection_node.outputs[0])
                    
            case 'srf_pbr_ca_terrain_macrocolor_paintrough_world' | 'srf_pbr_ca_terrain_world_blend':
                vector_node = tree.nodes.new('ShaderNodeGroup')
                vector_node.node_tree = utils.add_node_from_resources(library, name='srf_pbr_ca_terrain_macrocolor_paintrough_world - vector')
                
                if group_node.inputs['layer2_coMap'].links:
                    coMap_node = group_node.inputs['layer2_coMap'].links[0].from_node
                    if coMap_node.type == 'TEX_IMAGE':
                        tree.links.new(input=coMap_node.inputs[0], output=vector_node.outputs[0])
                        coMap_xz_node = tree.nodes.new('ShaderNodeTexImage')
                        coMap_xz_node.image = coMap_node.image
                        coMap_xz_node.extension = coMap_node.extension
                        tree.links.new(input=coMap_xz_node.inputs[0], output=vector_node.outputs[1])
                        tree.links.new(input=group_node.inputs['layer2_coMap_xz'], output=coMap_xz_node.outputs[0])
                        tree.links.new(input=group_node.inputs['layer2_coMap_alpha_xz'], output=coMap_xz_node.outputs[1])
                
            case 'srf_blinn_detail_satramp':
                vector_node = tree.nodes.new('ShaderNodeGroup')
                vector_node.node_tree = utils.add_node_from_resources(library, name='srf_blinn_detail_satramp - saturation_ramp_vector')
                
                if group_node.inputs['saturation_ramp'].links:
                    sat_ramp_node = group_node.inputs['saturation_ramp'].links[0].from_node
                    tree.links.new(input=sat_ramp_node.inputs[0], output=vector_node.outputs[0])
                    
                self.populate_chiefster_node(tree, vector_node, material_parameters, material_parameters_true)
                
            case 'srf_matcap_normal_uv2':
                vector_node = tree.nodes.new('ShaderNodeGroup')
                vector_node.node_tree = utils.add_node_from_resources(library, name='srf_matcap_normal_uv2 - edge_map_vector')
                has_edge_map = False
                if group_node.inputs['edge_map'].links:
                    has_edge_map = True
                    edge_map_node = group_node.inputs['edge_map'].links[0].from_node
                    tree.links.new(input=edge_map_node.inputs[0], output=vector_node.outputs[0])
                    
                if group_node.inputs['edge_map_alpha'].links:
                    if has_edge_map:
                        edge_map_alpha_node = tree.nodes.new('ShaderNodeTexImage')
                        edge_map_alpha_node.image = edge_map_node.image
                        tree.links.new(input=group_node.inputs['edge_map_alpha'], output=edge_map_alpha_node.outputs[1])
                    else:
                        edge_map_alpha_node = group_node.inputs['edge_map_alpha'].links[0].from_node
                    tree.links.new(input=edge_map_alpha_node.inputs[0], output=vector_node.outputs[1])
                    
                self.populate_chiefster_node(tree, vector_node, material_parameters, material_parameters_true)
                
            case 'srf_env_m90_phong_reflection':
                if group_node.inputs['control_map_spglrf'].links:
                    control_map_node = group_node.inputs['control_map_spglrf'].links[0].from_node
                    utils.insert_uv_map_node(control_map_node, "UVMap1")
                    
            case 'srf_env_m90_phong_reflection_detail':
                if group_node.inputs['control_map_spglrf'].links:
                    control_map_node = group_node.inputs['control_map_spglrf'].links[0].from_node
                    utils.insert_uv_map_node(control_map_node, "UVMap1")
                if group_node.inputs['normal_detail_map'].links:
                    normal_detail_node = group_node.inputs['normal_detail_map'].links[0].from_node
                    utils.insert_uv_map_node(normal_detail_node, "UVMap1")

        from .material_vectors import setup_material_vectors
        setup_material_vectors(self, tree, group_node, material_parameters, material_parameters_true)

        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')

        # Link to output
        tree.links.new(input=node_output.inputs[0], output=group_node.outputs[0])
            
            
    def _value_from_parameter(self, parameter, value_type):
        """Material tags use a different type enum from render-method options."""
        value = parameter.default
        for element in self.block_parameters.Elements:
            if parameter_key(element.Fields[0].GetStringData()) != parameter_key(parameter.name):
                continue
            match ParameterType(parameter.type):
                case ParameterType.REAL:
                    value = element.SelectField('real').Data
                case ParameterType.INT:
                    value = element.SelectField(r'int\bool').Data
                case ParameterType.BOOL:
                    value = bool(element.SelectField(r'int\bool').Data)
                case ParameterType.COLOR:
                    value = convert_argb(element.SelectField('color').Data)
            for animated in element.SelectField(self.function_parameters).Elements:
                if animated.Fields[0].Value == value_type.value:
                    function = Function()
                    function.from_element(animated, self.animated_function)
                    return function
            break
        return value

    def populate_chiefster_node(self, tree: bpy.types.NodeTree, node: bpy.types.Node, material_parameters: dict[MaterialParameter], material_parameters_true: dict[MaterialParameter]):
        parameters = {parameter_key(p.name): p for p in material_parameters_true.values()}
        display_parameters = {parameter_key(p.ui_name): p for p in material_parameters.values()}
        populated_bitmaps = set()
        for input in cast(list[bpy.types.NodeSocket], node.inputs):
            match input.name:
                case 'blend mode':
                    if input.type != 'MENU':
                        continue
                    blend_mode_items = [i.EnumName for i in self.alpha_blend_mode.Items]
                    item = blend_mode_items[self.alpha_blend_mode.Value]
                    if item in blend_mode_items:
                        input.default_value = item
                case 'cull shadows':
                    pass
                case 'material is two-sided':
                    pass
                case 'Primary Change Color':
                    link_change_color(tree, input, "Primary Color")
                case 'Secondary Change Color':
                    link_change_color(tree, input, "Secondary Color")
                case 'Tertiary Change Color':
                    link_change_color(tree, input, "Tertiary Color")
                case 'Quaternary Color':
                    link_change_color(tree, input, "Quaternary Color")
                case _:
                    parameter_name_ui = input.name.lower() if "." not in input.name else input.name.partition(".")[0].lower()
                    if "gamma curve" in parameter_name_ui or "gamma_curve" in parameter_name_ui:
                        # if any(srgb_name in parameter_name_ui for srgb_name in srgb_names):
                        #     input.default_value = 2.2
                        # else:
                        input.default_value = 1
                    # parameter_type = self._parameter_type_from_name(parameter_name)
                    key = parameter_key(parameter_name_ui)
                    parameter = parameters.get(key) or display_parameters.get(key)
                    alpha_only = False
                    if parameter is None and key.endswith('alpha'):
                        parameter = parameters.get(key[:-5]) or display_parameters.get(key[:-5])
                        alpha_only = parameter is not None and parameter.type == ParameterType.BITMAP.value
                    if parameter is None:
                        continue
                    parameter_type = ParameterType(parameter.type)
                    match parameter_type:
                        case ParameterType.COLOR:
                            self._setup_input_with_function(input, self._value_from_parameter(parameter, AnimatedParameterType.COLOR), color_no_alpha=True)
                        case ParameterType.REAL | ParameterType.INT | ParameterType.BOOL:
                            self._setup_input_with_function(input, self._value_from_parameter(parameter, AnimatedParameterType.VALUE), for_alpha=True)
                        case _:
                            if alpha_only and parameter.name in populated_bitmaps:
                                continue
                            image = self.group_set_image(tree, node, parameter,
                                ChannelType.ALPHA if alpha_only else ChannelType.DEFAULT,
                                specified_input=input.name.lower())
                            if image and not alpha_only:
                                populated_bitmaps.add(parameter.name)
                                alpha_key = parameter_key(input.name + '_alpha')
                                alpha_input = next((s for s in node.inputs if parameter_key(s.name) == alpha_key), None)
                                if alpha_input is not None and 'Alpha' in image.outputs:
                                    tree.links.new(image.outputs['Alpha'], alpha_input)
                            

def link_change_color(tree: bpy.types.NodeTree, input: bpy.types.NodeGroupInput, attribute: str):
    node_cc = tree.nodes.new(type="ShaderNodeAttribute")
    node_cc.attribute_name = attribute
    node_cc.attribute_type = 'INSTANCER'
    tree.links.new(input=input, output=node_cc.outputs[0])

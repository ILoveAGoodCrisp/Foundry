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
from io_scene_foundry.managed_blam.material_shader import MaterialShaderTag
from io_scene_foundry.managed_blam.shader import BSDFParameter, ShaderTag
from io_scene_foundry.utils import nwo_utils
import bpy

from io_scene_foundry.utils.nwo_constants import MATERIAL_SHADERS_DIR


global_material_shader = None
last_group_node = None
material_shader_path = ""

class MaterialTag(ShaderTag):
    tag_ext = 'material'
    scale_u = 'scale u'
    scale_v = 'scale v'
    translation_u = 'offset x'
    translation_v = 'offset y'
    function_parameters = 'function parameters'
    animated_function = 'function'
    color_parameter_type = 'color'
    
    def _read_fields(self):
        self.block_parameters = self.tag.SelectField("Block:material parameters")
        self.reference_material_shader = self.tag.SelectField("Reference:material shader")
        self.alpha_blend_mode = self.tag.SelectField('CharEnum:alpha blend mode')
        
    def _get_info(self):
        global global_material_shader
        global last_group_node
        global material_shader_path
        if not global_material_shader or last_group_node != self.group_node or material_shader_path == "":
            group_node_name = nwo_utils.dot_partition(self.group_node.node_tree.name.lower().replace(' ', '_'))
            material_shader_path = self._material_shader_path_from_group_node(group_node_name)
            assert material_shader_path, f"Group node in use for material but no corresponding material shader found. Expected material shader named {group_node_name} in {MATERIAL_SHADERS_DIR} (or sub-folders)"
            last_group_node = self.group_node
            with MaterialShaderTag(path=material_shader_path) as material_shader:
                global_material_shader = material_shader.read_parameters()

    def _material_shader_path_from_group_node(self, group_node_name):
        filename = group_node_name + '.material_shader'
        return nwo_utils.tag_relative(nwo_utils.find_file_in_directory(self.tags_dir + MATERIAL_SHADERS_DIR, filename))
                
    def _build_custom(self):
        name_type_node_dict = {}
        inputs = self.group_node.inputs
        cull_chars = list(" _-()'\"")
        for i in inputs:
            for parameter_name, value in global_material_shader.items():
                d_name, param_type = value
                parameter_name_culled = nwo_utils.remove_chars(parameter_name.lower(), cull_chars)
                display_name = nwo_utils.remove_chars(d_name.lower(), cull_chars)
                input_name = nwo_utils.remove_chars(i.name.lower(), cull_chars)
                if input_name == parameter_name_culled or input_name == display_name:
                    name_type_node_dict[parameter_name] = [param_type, self._source_from_input_and_parameter_type(i, param_type)]
                    break

        for name, value in name_type_node_dict.items():
            param_type, source = value
            element = self._setup_parameter(source, name, param_type)
            if element:
                mapping = self._setup_function_parameters(source, element, param_type)
                self._finalize_material_parameters(mapping, element)
            
        self.reference_material_shader.Path = self._TagPath_from_string(material_shader_path)
                
    def _build_basic(self, map):
        # Set up shader parameters
        spec_alpha_from_diffuse = False
        if map.get('diffuse', 0):
            element = self._setup_parameter(map['diffuse'], 'color_map', 'bitmap')
            if element:
                mapping = self._setup_function_parameters(map['diffuse'], element, 'bitmap')
                self._finalize_material_parameters(mapping, element)
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'albedo_tint')
            diff_outputs = map['diffuse'].outputs
            for i in diff_outputs:
                if i.name.lower() == 'alpha' and i.links:
                    for l in i.links:
                        if 'specular' in l.to_socket.name.lower():
                            spec_alpha_from_diffuse = True
                            break
                
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
            
        if map.get('normal', 0):
            element = self._setup_parameter(map['normal'], 'normal_map', 'bitmap')
            if element:
                mapping = self._setup_function_parameters(map['normal'], element, 'bitmap')
                self._finalize_material_parameters(mapping, element)
        else:
            self._Element_remove_if_needed(self.block_parameters, 'parameter name', 'normal_map')
            
        if self.blender_material.nwo.uses_alpha and self.alpha_blend_mode.Value == 0:
            self.alpha_blend_mode.Value = 3
        elif self.alpha_blend_mode.Value == 3:
            self.alpha_blend_mode.Value = 0
            
        if self.material_shader:
            self.reference_material_shader.Path = self._TagPath_from_string(self.material_shader)
        elif map.get('albedo_tint', 0) and not map.get('specular', 0) and not map.get('normal', 0):
            self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_constant.material_shader')
        elif spec_alpha_from_diffuse:
            self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_ca_blinn_diffspec.material_shader')
        else:
            self.reference_material_shader.Path = self._TagPath_from_string(r'shaders\material_shaders\materials\srf_blinn.material_shader')
            
            
    def _finalize_material_parameters(self, mapping, element):
        color = mapping.get('color', 0)
        if color:
            argb_color = ['1', str(color[0]), str(color[1]), str(color[2])]
            element.SelectField('color').SetStringData(argb_color)
        if mapping.get(self.scale_u, 0):
            element.SelectField('real').SetStringData(str(mapping.get(self.scale_u)))
        if mapping.get(self.scale_v, 0):
            if mapping.get(self.translation_u, 0):
                element.SelectField('vector').SetStringData(str(mapping.get(self.scale_v), str(mapping.get(self.translation_u)), str(mapping.get(self.translation_v))))
            else:
                element.SelectField('vector').SetStringData(str(mapping.get(self.scale_v)), '0', '0')
                
                
                
    # READING
    
    def _alpha_type(self, material_shader_name):
        if self.alpha_blend_mode.Value != 0:
            return 'blend'
        elif 'clip' in material_shader_name:
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
        diffuse = None # has a parameter named color_map
        normal = None # has a parameter named normal_map
        specular = None # has a parameter named normal_map
        if self.reference_material_shader:
            material_shader_name = nwo_utils.os_sep_partition(self.reference_material_shader.Path.RelativePath, True)
        else:
            material_shader_name = ''
        print(material_shader_name)
        alpha_type = self._alpha_type(material_shader_name)
        if 'constant' in material_shader_name:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_tint'))
        else:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeTexImage', data=self._image_from_parameter_name('color_map'), mapping=self._mapping_from_parameter_name('color_map'), alpha=alpha_type)
            if not diffuse.data:
                diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_tint'))
                
        if not diffuse.data:
            diffuse = None

        normal = BSDFParameter(tree, bsdf, bsdf.inputs['Normal'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('normal_map', True), special_type=self._normal_type_from_parameter_name('normal_map'), mapping=self._mapping_from_parameter_name('normal_map'))
        if normal.data:
            normal.data.colorspace_settings.name = 'Non-Color'
        else:
            normal = None
                
        if 'diffspec' in material_shader_name and type(diffuse.data) == bpy.types.Image:
            diffuse.special_type = 'diffspec'
        else:
            specular = BSDFParameter(tree, bsdf, bsdf.inputs['Specular IOR Level'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('specular_map'), mapping=self._mapping_from_parameter_name('specular_map'))
            if specular.data:
                specular.data.colorspace_settings.name = 'Non-Color'
            else:
                specular = None
            
        if diffuse:
            diffuse.build(Vector((-300, 100)))
        if normal:
            normal.build()
        if specular:
            specular.build(Vector((-600, -100)))
            
        self._set_alpha(alpha_type, blender_material)
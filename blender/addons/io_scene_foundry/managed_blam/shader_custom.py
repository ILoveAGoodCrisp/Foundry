


from enum import Enum

import bpy

from .. import utils

from .shader import ChannelType, ShaderTag

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
    WATERFALL = 10
    MULTIPLY_MAP = 11
    SIMPLE = 11
    
class BumpMapping(Enum):
    OFF = 0
    STANDARD = 1
    DETAIL = 2
    
class AlphaTest(Enum):
    NONE = 0
    SIMPLE = 1
    MULTIPLY_MAP = 2
    
class SpecularMask(Enum):
    NO_SPECULAR_MASK = 0
    SPECULAR_MASK_FROM_DIFFUSE = 1
    SPECULAR_MASK_MULT_DIFFUSE = 2
    SPECULAR_MASK_FROM_TEXTURE = 3
    
class MaterialModel(Enum):
    DIFFUSE_ONLY = 0
    TWO_LOBE_PHONG = 1
    FOLIAGE = 2
    NONE = 3
    CUSTOM_SPECULAR = 4
    
class EnvironmentMapping(Enum):
    NONE = 0
    PER_PIXEL = 1
    DYNAMIC = 2
    FROM_FLAT_TEXTURE = 3
    PER_PIXEL_MIP = 4
    
class SelfIllumination(Enum):
    OFF = 0
    SIMPLE = 1
    _3_CHANNEL_SELF_ILLUM = 2
    PLASMA = 3
    FROM_DIFFUSE = 4
    ILLUM_DETAIL = 5
    METER = 6
    SELF_ILLUM_TIMES_DIFFUSE = 7
    WINDOW_ROOM = 8
    
class BlendMode(Enum):
    OPAQUE = 0
    ADDITIVE = 1
    MULTIPLY = 2
    ALPHA_BLEND = 3
    DOUBLE_MULTIPLY = 4

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
    RIPPLES = 3

class ShaderCustomTag(ShaderTag):
    tag_ext = 'shader_custom'
    group_supported = True
    
    default_parameter_bitmaps = None
    category_parameters = None
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        e_albedo = Albedo(self._option_value_from_index(0))
        e_bump_mapping = BumpMapping(self._option_value_from_index(1))
        e_alpha_test = AlphaTest(self._option_value_from_index(2))
        e_specular_mask = SpecularMask(self._option_value_from_index(3))
        e_material_model = MaterialModel(self._option_value_from_index(4))
        e_environment_mapping = EnvironmentMapping(self._option_value_from_index(5))
        e_self_illumination = SelfIllumination(self._option_value_from_index(6))
        e_blend_mode = BlendMode(self._option_value_from_index(7))
        # e_parallax = BlendMode(self._option_value_from_index(8))
        e_misc = Misc(self._option_value_from_index(9))
        
        self.has_rotating_bitmaps = e_misc == Misc.ROTATING_BITMAPS_SUPER_SLOW
        
        if e_albedo == Albedo.MULTIPLY_MAP:
            old_albedo = e_albedo.name
            e_albedo = Albedo.DEFAULT
            utils.print_warning(f"Unsupported albedo: {old_albedo}. Using {e_albedo.name} instead")
        
        if e_material_model == MaterialModel.CUSTOM_SPECULAR:
            old_model = e_material_model.name
            e_material_model = MaterialModel.TWO_LOBE_PHONG
            utils.print_warning(f"Unsupported material model: {old_model}. Using {e_material_model.name} instead")
            
        if e_environment_mapping == EnvironmentMapping.PER_PIXEL_MIP:
            old_env = e_environment_mapping.name
            e_environment_mapping = EnvironmentMapping.PER_PIXEL
            utils.print_warning(f"Unsupported environment mapping: {old_env}. Using {e_environment_mapping.name} instead")
            
        if e_self_illumination == SelfIllumination.WINDOW_ROOM:
            old_illum = e_self_illumination.name
            e_self_illumination = SelfIllumination.SIMPLE
            utils.print_warning(f"Unsupported self illumination: {old_illum}. Using {e_self_illumination.name} instead")
        
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["albedo"][utils.game_str(e_albedo.name)])
        self.shader_parameters.update(self.category_parameters["bump_mapping"][utils.game_str(e_bump_mapping.name)])
        self.shader_parameters.update(self.category_parameters["alpha_test"][utils.game_str(e_alpha_test.name)])
        self.shader_parameters.update(self.category_parameters["specular_mask"][utils.game_str(e_specular_mask.name)])
        self.shader_parameters.update(self.category_parameters["material_model"][utils.game_str(e_material_model.name)])
        self.shader_parameters.update(self.category_parameters["environment_mapping"][utils.game_str(e_environment_mapping.name)])
        self.shader_parameters.update(self.category_parameters["self_illumination"][utils.game_str(e_self_illumination.name)])
        self.shader_parameters.update(self.category_parameters["blend_mode"][utils.game_str(e_blend_mode.name)])
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}

        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        if Albedo == Albedo.WATERFALL:
            node_albedo = self._add_group_node(tree, nodes, f"shader_custom albedo - waterfall")
        else:
            node_albedo = self._add_group_node(tree, nodes, f"albedo - {utils.game_str(e_albedo.name)}")
        final_node = node_albedo
        
        has_bump = e_bump_mapping.value > 0 and e_material_model != MaterialModel.NONE
        mm_supports_glancing_spec = False
        material_model_has_alpha_input = False
        has_material_model = e_material_model != MaterialModel.NONE
        if has_material_model:
            material_model_has_alpha_input = e_material_model != MaterialModel.FOLIAGE
            mm_supports_glancing_spec = e_material_model.value > 0
            node_material_model = self._add_group_material_model(tree, nodes, utils.game_str(e_material_model.name), mm_supports_glancing_spec, False)
            final_node = node_material_model
        
        if e_albedo in {Albedo.FOUR_CHANGE_COLOR, Albedo.TWO_CHANGE_COLOR}:
            node_cc_primary = nodes.new(type="ShaderNodeAttribute")
            node_cc_primary.attribute_name = "Primary Color"
            node_cc_primary.attribute_type = 'INSTANCER'
            node_cc_primary.location.x = node_albedo.location.x - 300
            node_cc_primary.location.y = node_albedo.location.y + 200
            tree.links.new(input=node_albedo.inputs["Primary Color"], output=node_cc_primary.outputs[0])
            self.game_functions.add("Primary Color")
            node_cc_secondary = nodes.new(type="ShaderNodeAttribute")
            node_cc_secondary.attribute_name = "Secondary Color"
            node_cc_secondary.attribute_type = 'INSTANCER'
            node_cc_secondary.location.x = node_albedo.location.x - 300
            node_cc_secondary.location.y = node_albedo.location.y
            tree.links.new(input=node_albedo.inputs["Secondary Color"], output=node_cc_secondary.outputs[0])
            self.game_functions.add("Secondary Color")

            if e_albedo != Albedo.TWO_CHANGE_COLOR:
                node_cc_tertiary = nodes.new(type="ShaderNodeAttribute")
                node_cc_tertiary.attribute_name = "Tertiary Color"
                node_cc_tertiary.attribute_type = 'INSTANCER'
                node_cc_tertiary.location.x = node_albedo.location.x - 300
                node_cc_tertiary.location.y = node_albedo.location.y - 200
                tree.links.new(input=node_albedo.inputs["Tertiary Color"], output=node_cc_tertiary.outputs[0])
                self.game_functions.add("Tertiary Color")
                node_cc_quaternary = nodes.new(type="ShaderNodeAttribute")
                node_cc_quaternary.attribute_name = "Quaternary Color"
                node_cc_quaternary.attribute_type = 'INSTANCER'
                node_cc_quaternary.location.x = node_albedo.location.x - 300
                node_cc_quaternary.location.y = node_albedo.location.y - 400
                tree.links.new(input=node_albedo.inputs["Quaternary Color"], output=node_cc_quaternary.outputs[0])
                self.game_functions.add("Quaternary Color")
        
        if has_material_model:
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
            
            if e_environment_mapping.value > 0:
                node_environment_mapping = self._add_group_node(tree, nodes, f"environment_mapping - {utils.game_str(e_environment_mapping.name)}")
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
            node_self_illumination = self._add_group_node(tree, nodes, f"self_illumination - {utils.game_str(e_self_illumination.name)}")
            node_illum_add = nodes.new(type='ShaderNodeAddShader')
            node_illum_add.location.x = node_self_illumination.location.x + 300
            node_illum_add.location.y = final_node.location.y
            tree.links.new(input=node_illum_add.inputs[0], output=final_node.outputs[0])
            tree.links.new(input=node_illum_add.inputs[1], output=node_self_illumination.outputs[0])
            final_node = node_illum_add
            
        if e_blend_mode in {BlendMode.ADDITIVE, BlendMode.ALPHA_BLEND}:
            blender_material.surface_render_method = 'BLENDED'
            node_blend_mode = self._add_group_node(tree, nodes, f"blend_mode - {utils.game_str(e_blend_mode.name)}")
            for input in node_blend_mode.inputs:
                if input.name == "material is two-sided":
                    input.default_value = True
                    break
            tree.links.new(input=node_blend_mode.inputs[0], output=final_node.outputs[0])
            final_node = node_blend_mode
            
        if e_alpha_test.value > 0:
            node_alpha_test = self._add_group_node(tree, nodes, f"alpha_test - {utils.game_str(e_alpha_test.name)}")
            node_alpha_test.inputs["two-sided material"].default_value = True
            tree.links.new(input=node_alpha_test.inputs[1], output=final_node.outputs[0])
            final_node = node_alpha_test
            
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location.x = final_node.location.x + 300
        node_output.location.y = final_node.location.y
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=final_node.outputs[0])
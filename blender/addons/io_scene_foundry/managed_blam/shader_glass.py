


from enum import Enum
import bpy
from .. import utils
from .shader import ShaderTag

# OPTION ENUMS
class Albedo(Enum):
    MAP = 0
    
class BumpMapping(Enum):
    OFF = 0
    STANDARD = 1
    DETAIL = 2
    DETAIL_BLEND = 3
    THREE_DETAIL_BLEND = 4
    STANDARD_WRINKLE = 5
    DETAIL_WRINKLE = 6
    
class MaterialModel(Enum):
    TWO_LOBE_PHONG = 0
    
class EnvironmentMapping(Enum):
    NONE = 0
    PER_PIXEL = 1
    DYNAMIC = 2
    FROM_FLAT_TEXTURE = 3
    
class AlphaBlendSource(Enum):
    FROM_ALBEDO_ALPHA_WITHOUT_FRESNEL = 0
    FROM_ALBEDO_ALPHA = 1
    FROM_OPACITY_MAP_ALPHA = 2
    FROM_OPACITY_MAP_RGB = 3
    FROM_OPACITY_MAP_ALPHA_AND_ALBEDO_ALPHA = 4

class ShaderGlassTag(ShaderTag):
    tag_ext = 'shader_glass'
    group_supported = True
    
    default_parameter_bitmaps = None
    category_parameters = None
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        e_albedo = Albedo(self._option_value_from_index(0))
        e_bump_mapping = BumpMapping(self._option_value_from_index(1))
        e_material_model = MaterialModel(self._option_value_from_index(2))
        e_environment_mapping = EnvironmentMapping(self._option_value_from_index(3))
        e_alpha_blend_source = AlphaBlendSource(self._option_value_from_index(4))
            
        if e_environment_mapping.value > 2:
            old_env = e_environment_mapping.name
            e_environment_mapping = EnvironmentMapping.DYNAMIC
            utils.print_warning(f"Unsupported environment mapping : {old_env}. Using {e_environment_mapping.name} instead")
        
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["albedo"][utils.game_str(e_albedo.name)])
        self.shader_parameters.update(self.category_parameters["bump_mapping"][utils.game_str(e_bump_mapping.name)])
        self.shader_parameters.update(self.category_parameters["material_model"][utils.game_str(e_material_model.name)])
        self.shader_parameters.update(self.category_parameters["environment_mapping"][utils.game_str(e_environment_mapping.name)])
        self.shader_parameters.update(self.category_parameters["alpha_blend_source"][utils.game_str(e_alpha_blend_source.name)])
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}

        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        node_albedo = self._add_group_node(tree, nodes, f"albedo - default")
        final_node = node_albedo
        
        has_bump = e_bump_mapping.value > 0
        node_material_model = self._add_group_material_model(tree, nodes, utils.game_str(e_material_model.name), True, False)
        final_node = node_material_model
        
        tree.links.new(input=node_material_model.inputs[0], output=node_albedo.outputs[0])
            
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
                
        blender_material.surface_render_method = 'BLENDED'
        node_blend_mode = self._add_group_node(tree, nodes, f"blend_mode - alpha_blend")
        for input in node_blend_mode.inputs:
            if input.name == "material is two-sided":
                input.default_value = True
                break
        tree.links.new(input=node_blend_mode.inputs[0], output=final_node.outputs[0])
        final_node = node_blend_mode
        if e_alpha_blend_source.value > 0:
            node_alpha_blend_source = self._add_group_node(tree, nodes, f"alpha_blend_source - {utils.game_str(e_alpha_blend_source.name)}")
            tree.links.new(input=node_blend_mode.inputs[1], output=node_alpha_blend_source.outputs[0])
            if has_bump:
                tree.links.new(input=node_alpha_blend_source.inputs["Normal"], output=node_bump_mapping.outputs[0])
        else:
            tree.links.new(input=node_blend_mode.inputs[1], output=node_albedo.outputs[1])
            
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location.x = final_node.location.x + 300
        node_output.location.y = final_node.location.y
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=final_node.outputs[0])
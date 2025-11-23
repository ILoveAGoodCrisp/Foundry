


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
        
        group_node = self._add_group_node(tree, nodes, f"foundry_reach.shader_glass")
        
        group_node.inputs[0].default_value = e_albedo.name.lower()
        group_node.inputs[1].default_value = e_bump_mapping.name.lower()
        group_node.inputs[2].default_value = e_material_model.name.lower()
        group_node.inputs[3].default_value = e_environment_mapping.name.lower()
        group_node.inputs[4].default_value = e_alpha_blend_source.name.lower()

        self.populate_chiefster_node(tree, group_node, 5)

        blender_material.surface_render_method = 'BLENDED'
        group_node.inputs["material is two-sided"].default_value = True
            
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=group_node.outputs[0])
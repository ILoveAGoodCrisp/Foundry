


from enum import Enum

import bpy
from mathutils import Vector

from .. import utils

from .shader import BSDFParameter, ShaderTag

class Albedo(Enum):
    SIMPLE = 0
    DEFAULT = 1
    
class AlphaTest(Enum):
    NONE = 0
    FROM_ALBEDO_ALPHA = 1
    FROM_TEXTURE = 2
    
class MaterialModel(Enum):
    FLAT = 0
    SPECULAR = 1
    TRANSLUCENT = 2
    
class Wetness(Enum):
    SIMPLE = 0
    PROOF = 1

class ShaderFoliageTag(ShaderTag):
    tag_ext = 'shader_foliage'
    group_supported = True
    
    default_parameter_bitmaps = None
    category_parameters = None
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        # Get options
        e_albedo = Albedo(self._option_value_from_index(0))
        e_alpha_test = AlphaTest(self._option_value_from_index(1))
        e_material_model = MaterialModel(self._option_value_from_index(2))
            
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["albedo"][utils.game_str(e_albedo.name)])
        self.shader_parameters.update(self.category_parameters["alpha_test"][utils.game_str(e_alpha_test.name)])
        self.shader_parameters.update(self.category_parameters["material_model"][utils.game_str(e_material_model.name)])
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}
        
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        node_albedo = self._add_group_node(tree, nodes, f"albedo - {utils.game_str(e_albedo.name)}")
        node_material_model = self._add_group_node(tree, nodes, f"shader_foliage material_model - {utils.game_str(e_material_model.name)}")
        final_node = node_material_model
        
        tree.links.new(input=node_material_model.inputs[0], output=node_albedo.outputs[0])
        
        if e_alpha_test.value > 0:
            node_alpha_test = self._add_group_node(tree, nodes, f"alpha_test - simple")
            node_alpha_test.inputs["two-sided material"].default_value = True
            if e_alpha_test == AlphaTest.FROM_ALBEDO_ALPHA:
                tree.links.new(input=node_albedo.inputs[1], output=node_alpha_test.outputs[0])
                
            tree.links.new(input=node_alpha_test.inputs[1], output=final_node.outputs[0])
            final_node = node_alpha_test
                
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=final_node.outputs[0])
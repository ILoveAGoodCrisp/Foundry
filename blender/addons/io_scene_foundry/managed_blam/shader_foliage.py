


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
        
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        group_node = self._add_group_node(tree, nodes, f"foundry_reach.shader_foliage")
        
        group_node.inputs[0].default_value = e_albedo.name.lower()
        group_node.inputs[1].default_value = e_alpha_test.name.lower()
        group_node.inputs[2].default_value = e_material_model.name.lower()

        self.populate_chiefster_node(tree, group_node, 3)
        
        if e_alpha_test.value > 0:
            blender_material.surface_render_method = 'BLENDED'
            group_node.inputs["material is two-sided"].default_value = True
                
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=group_node.outputs[0])
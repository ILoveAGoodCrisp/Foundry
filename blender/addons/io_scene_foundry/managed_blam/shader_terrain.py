


from enum import Enum

import bpy
from mathutils import Vector

from ..constants import NormalType

from .. import utils

from .shader import ChannelType, ShaderTag


class TerrainBlending(Enum):
    MORPH = 0
    DYNAMIC_MORPH = 1
    DISTANCE_BLEND_BASE = 2
    
class TerrainEnvironmentMapping(Enum):
    NONE = 0
    PER_PIXEL = 1
    DYNAMIC = 2
    
class TerrainMaterial(Enum):
    DIFFUSE_ONLY = 0
    DIFFUSE_PLUS_SPECULAR = 1
    OFF = 2
    
class TerrainMaterial3(Enum):
    OFF = 0
    DIFFUSE_ONLY = 1
    DIFFUSE_PLUS_SPECULAR = 2
    
class TerrainWetness(Enum):
    DEFAULT = 0
    PROOF = 1
    FLOOD = 2
    RIPPLES = 3
        
class ShaderTerrainTag(ShaderTag):
    tag_ext = 'shader_terrain'
    group_supported = True
    
    default_parameter_bitmaps = None
    category_parameters = None
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        # Get options
        e_blending = TerrainBlending(self._option_value_from_index(0))
        e_environment_mapping = TerrainEnvironmentMapping(self._option_value_from_index(1))
        e_material_0 = TerrainMaterial(self._option_value_from_index(2))
        e_material_1 = TerrainMaterial(self._option_value_from_index(3))
        e_material_2 = TerrainMaterial(self._option_value_from_index(4))
        e_material_3 = TerrainMaterial3(self._option_value_from_index(5))
        # e_wetness = TerrainWetness(self._option_value_from_index(6))
        
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["blending"][utils.game_str(e_blending.name)])
        self.shader_parameters.update(self.category_parameters["environment_map"][utils.game_str(e_environment_mapping.name)])
        self.shader_parameters.update(self.category_parameters["material_0"][utils.game_str(e_material_0.name)])
        self.shader_parameters.update(self.category_parameters["material_1"][utils.game_str(e_material_1.name)])
        self.shader_parameters.update(self.category_parameters["material_2"][utils.game_str(e_material_2.name)])
        if e_material_3 == TerrainMaterial3.OFF:
            self.shader_parameters.update(self.category_parameters["material_3"]["off"])
        else:
            self.shader_parameters.update(self.category_parameters["material_3"][f"{utils.game_str(e_material_3.name)}_(four_material_shaders_disable_detail_bump)"])
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}
        
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        node_group = self._add_group_node(tree, nodes, "Master Terrain Material")
        final_node = node_group
        
        if e_material_0 != TerrainMaterial.OFF:
            node_group.inputs["Enable material_0"].default_value = True
        if e_material_1 != TerrainMaterial.OFF:
            node_group.inputs["Enable material_1"].default_value = True
        if e_material_2 != TerrainMaterial.OFF:
            node_group.inputs["Enable material_2"].default_value = True
        if e_material_3 != TerrainMaterial3.OFF:
            node_group.inputs["Enable material_3"].default_value = True
            
        if e_environment_mapping.value > 0:
            node_environment_mapping = self._add_group_node(tree, nodes, f"environment_mapping - {utils.game_str(e_environment_mapping.name)}")
            tree.links.new(input=node_environment_mapping.inputs[0], output=node_group.outputs[1])
            tree.links.new(input=node_environment_mapping.inputs["Normal"], output=node_group.outputs["Normal"])
            if e_environment_mapping == TerrainEnvironmentMapping.DYNAMIC:
                tree.links.new(input=node_environment_mapping.inputs[1], output=node_group.outputs[2])
                
            node_model_environment_add = nodes.new(type='ShaderNodeAddShader')
            node_model_environment_add.location.x = node_environment_mapping.location.x + 300
            node_model_environment_add.location.y = node_group.location.y
            tree.links.new(input=node_model_environment_add.inputs[0], output=node_group.outputs[0])
            tree.links.new(input=node_model_environment_add.inputs[1], output=node_environment_mapping.outputs[0])
            final_node = node_model_environment_add
            
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location.x = final_node.location.x + 300
        node_output.location.y = final_node.location.y
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=final_node.outputs[0])
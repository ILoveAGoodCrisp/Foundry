


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
    
class TerrainWetness(Enum):
    DEFAULT = 0
    PROOF = 1
    FLOOD = 2
    RIPPLES = 3
        
class ShaderTerrainTag(ShaderTag):
    tag_ext = 'shader_terrain'
    group_supported = True
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        # Get options
        e_blending = TerrainBlending(self._option_value_from_index(0))
        e_environment_mapping = TerrainEnvironmentMapping(self._option_value_from_index(1))
        e_material_0 = TerrainMaterial(self._option_value_from_index(2))
        e_material_1 = TerrainMaterial(self._option_value_from_index(3))
        e_material_2 = TerrainMaterial(self._option_value_from_index(4))
        e_material_3 = TerrainMaterial(self._option_value_from_index(5))
        e_wetness = TerrainMaterial(self._option_value_from_index(6))
        
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        node_group = self._add_group_node(tree, nodes, "Master Terrain Material", Vector((0, 0)))
        final_node = node_group
        
        node_group = nodes.new(type="ShaderNodeGroup")
        node_group.node_tree = utils.add_node_from_resources("reach_nodes", "Master Terrain Material")
        
        if e_material_0 in {TerrainMaterial.DIFFUSE_ONLY, TerrainMaterial.DIFFUSE_PLUS_SPECULAR}:
            node_group.inputs["enable material_0"].default_value = True
        if e_material_1 in {TerrainMaterial.DIFFUSE_ONLY, TerrainMaterial.DIFFUSE_PLUS_SPECULAR}:
            node_group.inputs["Enable material_1"].default_value = True
        if e_material_2 in {TerrainMaterial.DIFFUSE_ONLY, TerrainMaterial.DIFFUSE_PLUS_SPECULAR}:
            node_group.inputs["Enable material_2"].default_value = True
        if e_material_3 in {TerrainMaterial.DIFFUSE_ONLY, TerrainMaterial.DIFFUSE_PLUS_SPECULAR}:
            node_group.inputs["Enable material_3"].default_value = True
            
        if e_environment_mapping.value > 0:
            node_environment_mapping = self._add_group_node(tree, nodes, f"environment_mapping - {utils.game_str(e_environment_mapping.name)}", Vector((node_group.location.x + 600, node_group.location.y - 200)))
            tree.links.new(input=node_environment_mapping.inputs[0], output=node_group.outputs[1])
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
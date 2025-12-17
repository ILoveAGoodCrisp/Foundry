


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
    
    def get_global_material(self):
        global_material = self.tag.SelectField("StringId:material name 0").GetStringData()
        
        if not global_material and self.reference.Path is not None and self.path_exists(self.reference.Path):
            with ShaderTerrainTag(path=self.reference.Path) as ref_shader:
                return ref_shader.get_global_material()
            
        return global_material
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        # Get options
        e_blending = TerrainBlending(self._option_value_from_index(0))
        e_environment_mapping = TerrainEnvironmentMapping(self._option_value_from_index(1))
        e_material_0 = TerrainMaterial(self._option_value_from_index(2))
        e_material_1 = TerrainMaterial(self._option_value_from_index(3))
        e_material_2 = TerrainMaterial(self._option_value_from_index(4))
        e_material_3 = TerrainMaterial3(self._option_value_from_index(5))
        # e_wetness = TerrainWetness(self._option_value_from_index(6))
        
        if e_blending.value > 1:
            old_model = e_blending.name
            e_blending = TerrainBlending.DYNAMIC_MORPH
            utils.print_warning(f"Unsupported material model : {old_model}. Using {e_blending.name} instead")
        
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["blending"][utils.game_str(e_blending.name)])
        self.shader_parameters.update(self.category_parameters["environment_map"][utils.game_str(e_environment_mapping.name)])
        self.shader_parameters.update(self.category_parameters["material_0"][utils.game_str(e_material_0.name)])
        self.shader_parameters.update(self.category_parameters["material_1"][utils.game_str(e_material_1.name)])
        self.shader_parameters.update(self.category_parameters["material_2"][utils.game_str(e_material_2.name)])
        
        match e_material_3:
            case TerrainMaterial3.OFF:
                material_3 = "off"
            case TerrainMaterial3.DIFFUSE_ONLY:
                material_3 = "diffuse_only_(four_material_shaders_disable_detail_bump)"
            case TerrainMaterial3.DIFFUSE_PLUS_SPECULAR:
                material_3 = "diffuse_plus_specular_(four_material_shaders_disable_detail_bump)"
        
        self.shader_parameters.update(self.category_parameters["material_3"][material_3])
        
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}
        
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        group_node = self._add_group_node(tree, nodes, f"foundry_reach.shader_terrain")
        
        group_node.inputs[0].default_value = e_blending.name.lower().strip('_')
        group_node.inputs[1].default_value = e_environment_mapping.name.lower().strip('_')
        group_node.inputs[2].default_value = e_material_0.name.lower().strip('_')
        group_node.inputs[3].default_value = e_material_1.name.lower().strip('_')
        group_node.inputs[4].default_value = e_material_2.name.lower().strip('_')
        group_node.inputs[5].default_value = material_3
        
        self.populate_chiefster_node(tree, group_node, 6)
            
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')

        # Link to output
        tree.links.new(input=node_output.inputs[0], output=group_node.outputs[0])



from enum import Enum

import bpy
from mathutils import Vector

from ..constants import NormalType

from .. import utils

from .shader import ChannelType, ShaderTag


class TerrainBlending(Enum):
    NULL = -1
    MORPH = 0
    DYNAMIC_MORPH = 1
    DISTANCE_BLEND_BASE = 2
    
class TerrainEnvironmentMap(Enum):
    NULL = -1
    NONE = 0
    PER_PIXEL = 1
    DYNAMIC = 2
    
class TerrainMaterial(Enum):
    NULL = -1
    DIFFUSE_ONLY = 0
    DIFFUSE_PLUS_SPECULAR = 1
    OFF = 2
    
class TerrainWetness(Enum):
    NULL = -1
    DEFAULT = 0
    PROOF = 1
    FLOOD = 2
    RIPPLES = 3
        
class ShaderTerrainTag(ShaderTag):
    tag_ext = 'shader_terrain'
    group_supported = True
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        # Make the Group and Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location = Vector((300, 0))
        
        node_group = nodes.new(type="ShaderNodeGroup")
        node_group.node_tree = utils.add_node_from_resources("reach_nodes", "Master Terrain Material")
        node_group.location.x = node_output.location.x - 300
        node_group.location.y = node_output.location.y
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=node_group.outputs[0])
        # Get options
        e_blending = TerrainBlending(self._option_value_from_index(0))
        e_environment_map = TerrainEnvironmentMap(self._option_value_from_index(1))
        e_material_0 = TerrainMaterial(self._option_value_from_index(2))
        e_material_1 = TerrainMaterial(self._option_value_from_index(3))
        e_material_2 = TerrainMaterial(self._option_value_from_index(4))
        e_material_3 = TerrainMaterial(self._option_value_from_index(5))
        e_wetness = TerrainMaterial(self._option_value_from_index(6))
        
        # Add blend_map parameter
        self.group_set_image(tree, node_group, "blend_map", Vector((node_group.location.x - 300, node_group.location.y + 300)), channel_type=ChannelType.RGB_ALPHA)
        self.group_set_value(tree, node_group, "global_albedo_tint")
        
        if e_material_0 in {TerrainMaterial.DIFFUSE_ONLY, TerrainMaterial.DIFFUSE_PLUS_SPECULAR}:
            location = Vector((node_group.location.x - 300, node_group.location.y))
            node_group.inputs["enable material_0"].default_value = True
            location = self.group_set_image(tree, node_group, "base_map_m_0", location, channel_type=ChannelType.RGB_ALPHA)
            location = self.group_set_image(tree, node_group, "detail_map_m_0", location, channel_type=ChannelType.RGB_ALPHA)
            # location = self.group_set_image(tree, node_group, "detail_map2_m_0", location, has_alpha_input=True)
            location = self.group_set_image(tree, node_group, "bump_map_m_0", location)
            location = self.group_set_image(tree, node_group, "detail_bump_m_0", location)
            self.group_set_value(tree, node_group, "diffuse_coefficient_m_0")
            self.group_set_value(tree, node_group, "specular_coefficient_m_0")
            self.group_set_value(tree, node_group, "specular_power_m_0")
            self.group_set_color(tree, node_group, "specular_tint_m_0")
            self.group_set_value(tree, node_group, "area_specular_contribution_m_0")
            self.group_set_value(tree, node_group, "analytical_specular_contribution_m_0")
            self.group_set_value(tree, node_group, "fresnel_curve_steepness_m_0")
            self.group_set_value(tree, node_group, "environment_specular_contribution_m_0")
            self.group_set_value(tree, node_group, "albedo_specular_tint_blend_m_0")
        if e_material_1 in {TerrainMaterial.DIFFUSE_ONLY, TerrainMaterial.DIFFUSE_PLUS_SPECULAR}:
            location = Vector((node_group.location.x - 300, node_group.location.y - 300))
            node_group.inputs["Enable material_1"].default_value = True
            location = self.group_set_image(tree, node_group, "base_map_m_1", location, channel_type=ChannelType.RGB_ALPHA)
            location = self.group_set_image(tree, node_group, "detail_map_m_1", location, channel_type=ChannelType.RGB_ALPHA)
            # location = self.group_set_image(tree, node_group, "detail_map2_m_1", location, has_alpha_input=True)
            location = self.group_set_image(tree, node_group, "bump_map_m_1", location)
            location = self.group_set_image(tree, node_group, "detail_bump_m_1", location)
            self.group_set_value(tree, node_group, "diffuse_coefficient_m_1")
            self.group_set_value(tree, node_group, "specular_coefficient_m_1")
            self.group_set_value(tree, node_group, "specular_power_m_1")
            self.group_set_color(tree, node_group, "specular_tint_m_1")
            self.group_set_value(tree, node_group, "area_specular_contribution_m_1")
            self.group_set_value(tree, node_group, "analytical_specular_contribution_m_1")
            self.group_set_value(tree, node_group, "fresnel_curve_steepness_m_1")
            self.group_set_value(tree, node_group, "environment_specular_contribution_m_1")
            self.group_set_value(tree, node_group, "albedo_specular_tint_blend_m_1")
        if e_material_2 in {TerrainMaterial.DIFFUSE_ONLY, TerrainMaterial.DIFFUSE_PLUS_SPECULAR}:
            location = Vector((node_group.location.x - 300, node_group.location.y - 600))
            node_group.inputs["Enable material_2"].default_value = True
            location = self.group_set_image(tree, node_group, "base_map_m_2", location, channel_type=ChannelType.RGB_ALPHA)
            location = self.group_set_image(tree, node_group, "detail_map_m_2", location, channel_type=ChannelType.RGB_ALPHA)
            # location = self.group_set_image(tree, node_group, "detail_map2_m_2", location, has_alpha_input=True)
            location = self.group_set_image(tree, node_group, "bump_map_m_2", location)
            location = self.group_set_image(tree, node_group, "detail_bump_m_2", location)
            self.group_set_value(tree, node_group, "diffuse_coefficient_m_2")
            self.group_set_value(tree, node_group, "specular_coefficient_m_2")
            self.group_set_value(tree, node_group, "specular_power_m_2")
            self.group_set_color(tree, node_group, "specular_tint_m_2")
            self.group_set_value(tree, node_group, "area_specular_contribution_m_2")
            self.group_set_value(tree, node_group, "analytical_specular_contribution_m_2")
            self.group_set_value(tree, node_group, "fresnel_curve_steepness_m_2")
            self.group_set_value(tree, node_group, "environment_specular_contribution_m_2")
            self.group_set_value(tree, node_group, "albedo_specular_tint_blend_m_2")
        if e_material_3 in {TerrainMaterial.DIFFUSE_ONLY, TerrainMaterial.DIFFUSE_PLUS_SPECULAR}:
            location = Vector((node_group.location.x - 300, node_group.location.y - 900))
            node_group.inputs["Enable material_3"].default_value = True
            location = self.group_set_image(tree, node_group, "base_map_m_3", location, channel_type=ChannelType.RGB_ALPHA)
            location = self.group_set_image(tree, node_group, "detail_map_m_3", location, channel_type=ChannelType.RGB_ALPHA)
            # location = self.group_set_image(tree, node_group, "detail_map2_m_3", location, has_alpha_input=True)
            location = self.group_set_image(tree, node_group, "bump_map_m_3", location)
            location = self.group_set_image(tree, node_group, "detail_bump_m_3", location)
            self.group_set_value(tree, node_group, "diffuse_coefficient_m_3")
            self.group_set_value(tree, node_group, "specular_coefficient_m_3")
            self.group_set_value(tree, node_group, "specular_power_m_3")
            self.group_set_color(tree, node_group, "specular_tint_m_3")
            self.group_set_value(tree, node_group, "area_specular_contribution_m_3")
            self.group_set_value(tree, node_group, "analytical_specular_contribution_m_3")
            self.group_set_value(tree, node_group, "fresnel_curve_steepness_m_3")
            self.group_set_value(tree, node_group, "environment_specular_contribution_m_3")
            self.group_set_value(tree, node_group, "albedo_specular_tint_blend_m_3")
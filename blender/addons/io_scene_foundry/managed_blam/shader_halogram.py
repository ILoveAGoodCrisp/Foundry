


from enum import Enum

import bpy
from mathutils import Vector

from .. import utils

from .shader import ShaderTag

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
    
class SelfIllumination(Enum):
    OFF = 0
    SIMPLE = 1
    _3_CHANNEL_SELF_ILLUM = 2
    PLASMA = 3
    FROM_DIFFUSE = 4
    ILLUM_DETAIL = 5
    METER = 6
    SELF_ILLUM_TIMES_DIFFUSE = 7
    MULTILAYER_ADDITIVE = 8
    SCOPE_BLUR = 9
    PALETTIZED_PLASMA = 10
    PALETTIZED_PLASMA_CHANGE_COLOR = 11
    PALETTIZED_DEPTH_FADE = 12
    
class BlendMode(Enum):
    OPAQUE = 0
    ADDITIVE = 1
    MULTIPLY = 2
    ALPHA_BLEND = 3
    DOUDBLE_MULTIPLY = 4
    
class Overlay(Enum):
    NONE = 0
    ADDITIVE = 1
    ADDITIVE_DETAIL = 2
    MULTIPLY = 3
    MULTIPLY_AND_ADDITIVE_DETAIL = 4
    
class EdgeFade(Enum):
    NONE = 0
    SIMPLE = 1
        
class ShaderHalogramTag(ShaderTag):
    tag_ext = 'shader_halogram'
    group_supported = True
    
    category_parameters = None
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        # Get options
        e_albedo = Albedo(self._option_value_from_index(0))
        e_self_illumination = SelfIllumination(self._option_value_from_index(1))
        if e_self_illumination == SelfIllumination.SCOPE_BLUR:
            e_self_illumination = SelfIllumination.SIMPLE
        e_blend_mode = BlendMode(self._option_value_from_index(2))
        e_overlay = Overlay(self._option_value_from_index(5))
        e_edge_fade = EdgeFade(self._option_value_from_index(6))
        
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["albedo"][utils.game_str(e_albedo.name)])
        self.shader_parameters.update(self.category_parameters["self_illumination"][utils.game_str(e_self_illumination.name)])
        self.shader_parameters.update(self.category_parameters["blend_mode"][utils.game_str(e_blend_mode.name)])
        self.shader_parameters.update(self.category_parameters["overlay"][utils.game_str(e_overlay.name)])
        self.shader_parameters.update(self.category_parameters["edge_fade"][utils.game_str(e_edge_fade.name)])
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}
        
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        node_albedo = self._add_group_node(tree, nodes, f"albedo - {utils.game_str(e_albedo.name)}", Vector((0, 0)))
        final_node = node_albedo
        
        if e_albedo in {Albedo.FOUR_CHANGE_COLOR, Albedo.TWO_CHANGE_COLOR}:
            node_cc_primary = nodes.new(type="ShaderNodeAttribute")
            node_cc_primary.attribute_name = "change_color_primary"
            node_cc_primary.attribute_type = 'INSTANCER'
            node_cc_primary.location.x = node_albedo.location.x - 300
            node_cc_primary.location.y = node_albedo.location.y + 200
            tree.links.new(input=node_albedo.inputs["Primary Color"], output=node_cc_primary.outputs[0])
            self.game_functions.add("change_color_primary")
            node_cc_secondary = nodes.new(type="ShaderNodeAttribute")
            node_cc_secondary.attribute_name = "change_color_secondary"
            node_cc_secondary.attribute_type = 'INSTANCER'
            node_cc_secondary.location.x = node_albedo.location.x - 300
            node_cc_secondary.location.y = node_albedo.location.y
            tree.links.new(input=node_albedo.inputs["Secondary Color"], output=node_cc_secondary.outputs[0])
            self.game_functions.add("change_color_secondary")
            if e_albedo != Albedo.TWO_CHANGE_COLOR:
                node_cc_tertiary = nodes.new(type="ShaderNodeAttribute")
                node_cc_tertiary.attribute_name = "change_color_tertiary"
                node_cc_tertiary.attribute_type = 'INSTANCER'
                node_cc_tertiary.location.x = node_albedo.location.x - 300
                node_cc_tertiary.location.y = node_albedo.location.y - 200
                tree.links.new(input=node_albedo.inputs["Tertiary Color"], output=node_cc_tertiary.outputs[0])
                self.game_functions.add("change_color_tertiary")
                node_cc_quaternary = nodes.new(type="ShaderNodeAttribute")
                node_cc_quaternary.attribute_name = "change_color_quaternary"
                node_cc_quaternary.attribute_type = 'INSTANCER'
                node_cc_quaternary.location.x = node_albedo.location.x - 300
                node_cc_quaternary.location.y = node_albedo.location.y - 400
                tree.links.new(input=node_albedo.inputs["Quaternary Color"], output=node_cc_quaternary.outputs[0])
                self.game_functions.add("change_color_quaternary")
        
        
        if e_self_illumination.value > 0:
            node_self_illumination = self._add_group_node(tree, nodes, f"self_illumination - {utils.game_str(e_self_illumination.name)}", Vector((final_node.location.x + 300, final_node.location.y - 200)))
            final_node = node_self_illumination
            node_albedo_illum_add = nodes.new(type='ShaderNodeMix')
            node_albedo_illum_add.data_type = 'RGBA'
            tree.links.new(input=node_albedo_illum_add.inputs[6], output=node_albedo.outputs[0])
            tree.links.new(input=node_albedo_illum_add.inputs[7], output=node_self_illumination.outputs[0])
            uses_overlay = e_overlay.value > 0
            uses_edge_fade = e_edge_fade.value > 0
            
            if uses_overlay:
                node_overlay = self._add_group_node(tree, nodes, f"shader_halogram overlay - {utils.game_str(e_overlay.name)}", Vector((final_node.location.x + 300, final_node.location.y - 200)))
                tree.links.new(input=node_overlay.inputs[0], output=node_albedo_illum_add.outputs[2])
                final_node = node_overlay
                
            if uses_edge_fade:
                node_edge_fade = self._add_group_node(tree, nodes, f"shader_halogram edge_fade - {utils.game_str(e_edge_fade.name)}", Vector((final_node.location.x + 300, final_node.location.y - 200)))
                tree.links.new(input=node_edge_fade.inputs[0], output=final_node.outputs[0])
                final_node = node_edge_fade
            
        if e_blend_mode != BlendMode.OPAQUE:
            blender_material.surface_render_method = 'BLENDED'
            node_blend_mode = self._add_group_node(tree, nodes, f"blend_mode - {utils.game_str(e_blend_mode.name)}", Vector((final_node.location.x + 300, final_node.location.y)))
            node_blend_mode.inputs["material is two-sided"].default_value = True
            tree.links.new(input=node_blend_mode.inputs[0], output=final_node.outputs[0])
            final_node = node_blend_mode
            if e_blend_mode == BlendMode.ALPHA_BLEND:
                tree.links.new(input=node_blend_mode.inputs[1], output=node_albedo.outputs[1])
                
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location.x = final_node.location.x + 300
        node_output.location.y = final_node.location.y
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=final_node.outputs[0])



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
    
class Misc(Enum):
    FIRST_PERSON_NEVER = 0
    FIRST_PERSON_SOMETIMES = 1
    FIRST_PERSON_ALWAYS = 2
    FIRST_PERSON_W_ROTATING_BITMAPS = 3
    
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
        e_misc = Misc(self._option_value_from_index(3))
        e_overlay = Overlay(self._option_value_from_index(5))
        e_edge_fade = EdgeFade(self._option_value_from_index(6))
        
        self.has_rotating_bitmaps = e_misc == Misc.FIRST_PERSON_W_ROTATING_BITMAPS
        
        if e_self_illumination.value > 10:
            old_illum = e_self_illumination.name
            e_self_illumination = SelfIllumination.PALETTIZED_PLASMA
            utils.print_warning(f"Unsupported self-illumination : {old_illum}. Using {e_self_illumination.name} instead")
            
        if e_blend_mode.value > BlendMode.ALPHA_BLEND.value:
            old_blend = e_blend_mode.name
            e_blend_mode = BlendMode.ALPHA_BLEND
            utils.print_warning(f"Unsupported blend mode : {old_blend}. Using {e_blend_mode.name} instead")
        
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
        
        illum_uses_diffuse = e_self_illumination in {SelfIllumination.FROM_DIFFUSE, SelfIllumination.SELF_ILLUM_TIMES_DIFFUSE}
        has_illum = e_self_illumination != SelfIllumination.OFF
        
        if illum_uses_diffuse or not has_illum or e_blend_mode == BlendMode.ALPHA_BLEND:
            node_albedo = self._add_group_node(tree, nodes, f"albedo - {utils.game_str(e_albedo.name)}")
            if not has_illum:
                final_node = node_albedo
            
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
        
        if e_self_illumination.value > 0:
            node_self_illumination = self._add_group_node(tree, nodes, f"self_illumination - {utils.game_str(e_self_illumination.name)}")
            if e_self_illumination == SelfIllumination.PALETTIZED_PLASMA:
                node_self_illumination_vector = self._add_group_node(tree, nodes, f"self_illumination - palettized_plasma - Vector")
                end_node = utils.get_end_node(node_self_illumination)
                tree.links.new(input=end_node.inputs[0], output=node_self_illumination_vector.outputs[0])
                
            final_node = node_self_illumination
            if illum_uses_diffuse:
                tree.links.new(input=node_self_illumination.inputs[0], output=node_albedo.outputs[0])
        
        uses_overlay = e_overlay.value > 0
        uses_edge_fade = e_edge_fade.value > 0
        
        if uses_overlay:
            node_overlay = self._add_group_node(tree, nodes, f"shader_halogram overlay - {utils.game_str(e_overlay.name)}")
            tree.links.new(input=node_overlay.inputs[0], output=final_node.outputs[0])
            final_node = node_overlay
            
        if uses_edge_fade:
            node_edge_fade = self._add_group_node(tree, nodes, f"shader_halogram edge_fade - {utils.game_str(e_edge_fade.name)}")
            tree.links.new(input=node_edge_fade.inputs[0], output=final_node.outputs[0])
            final_node = node_edge_fade
            
        if e_blend_mode in {BlendMode.ADDITIVE, BlendMode.ALPHA_BLEND}:
            blender_material.surface_render_method = 'BLENDED'
            node_blend_mode = self._add_group_node(tree, nodes, f"blend_mode - {utils.game_str(e_blend_mode.name)}")
            for input in node_blend_mode.inputs:
                if input.name == "material is two-sided":
                    input.default_value = True
                    break
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
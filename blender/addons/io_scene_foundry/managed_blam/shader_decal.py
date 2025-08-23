


from enum import Enum

import bpy
from mathutils import Vector

from ..constants import NormalType

from .. import utils

from .shader import BSDFParameter, ChannelType, ShaderTag

class Albedo(Enum):
    DIFFUSE_ONLY = 0
    PALETTIZED = 1
    PALETTIZED_PLUS_ALPHA = 2
    DIFFUSE_PLUS_ALPHA = 3
    EMBLEM_CHANGE_COLOR = 4
    CHANGE_COLOR = 5
    DIFFUSE_PLUS_ALPHA_MASK = 6
    PALETTIZED_PLUS_ALPHA_MASK = 7
    VECTOR_ALPHA = 8
    VECTOR_ALPHA_DROP_SHADOW = 9
    PATCHY_EMBLEM = 10
    
class BlendMode(Enum):
    OPAQUE = 0
    ADDITIVE = 1
    MULTIPLY = 2
    ALPHA_BLEND = 3
    DOUDBLE_MULTIPLY = 4
    MAXIMUM = 5
    MULTIPLY_ADD = 6
    ADD_SRC_TIMES_DSTALPHA = 7
    ADD_SRC_TIMES_SRCALPHA = 8
    INV_ALPHA_BLEND = 9
    PRE_MULTIPLIED_ALPHA = 10
    
class RenderPass(Enum):
    PRE_LIGHTING = 0
    POST_LIGHTING = 1
    
class Specular(Enum):
    LEAVE = 0
    MODULATE = 1
    
class BumpMapping(Enum):
    LEAVE = 0
    STANDARD = 1
    STANDARD_MASK = 2
    

class ShaderDecalTag(ShaderTag):
    tag_ext = 'shader_decal'
    group_supported = True
    
    default_parameter_bitmaps = None
    category_parameters = None
    
    def _to_nodes_group(self, blender_material: bpy.types.Material):
        # Get options
        e_albedo = Albedo(self._option_value_from_index(0))
        e_blend_mode = BlendMode(self._option_value_from_index(1))
        # e_render_pass = RenderPass(self._option_value_from_index(2))
        # e_specular = Specular(self._option_value_from_index(3))
        e_bump_mapping = BumpMapping(self._option_value_from_index(4))
        # e_tinting = Tinting(self._option_value_from_index(5))
        # e_parallax = Parallax(self._option_value_from_index(6))
        # e_interier = Interier(self._option_value_from_index(7))
        
        if e_albedo in {Albedo.EMBLEM_CHANGE_COLOR, Albedo.DIFFUSE_PLUS_ALPHA_MASK, Albedo.VECTOR_ALPHA, Albedo.VECTOR_ALPHA_DROP_SHADOW, Albedo.PATCHY_EMBLEM}:
            utils.print_warning(f"Albedo not supported: {e_albedo.name}. Using {Albedo.DIFFUSE_ONLY.name}")
            e_albedo = Albedo.DIFFUSE_ONLY
            
        if e_blend_mode not in {BlendMode.OPAQUE, BlendMode.ADDITIVE, BlendMode.ALPHA_BLEND, BlendMode.MULTIPLY}:
            utils.print_warning(f"Blend Mode not supported: {e_blend_mode.name}. Using {BlendMode.MULTIPLY.name}")
            e_blend_mode = BlendMode.MULTIPLY
            
        self.shader_parameters = {}
        self.shader_parameters.update(self.category_parameters["albedo"][utils.game_str(e_albedo.name)])
        self.shader_parameters.update(self.category_parameters["blend_mode"][utils.game_str(e_blend_mode.name)])
        self.shader_parameters.update(self.category_parameters["bump_mapping"][utils.game_str(e_bump_mapping.name)])
        self.true_parameters = {option.ui_name: option for option in self.shader_parameters.values()}
        
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        
        has_bump = e_bump_mapping.value > 0
        
        node_albedo = self._add_group_node(tree, nodes, f"shader_decal albedo - {utils.game_str(e_albedo.name)}")
        final_node = node_albedo
        
        if e_albedo == Albedo.CHANGE_COLOR:
            node_cc_primary = nodes.new(type="ShaderNodeAttribute")
            node_cc_primary.attribute_name = "nwo.cc_primary"
            node_cc_primary.attribute_type = 'OBJECT'
            node_cc_primary.location.x = node_albedo.location.x - 300
            node_cc_primary.location.y = node_albedo.location.y + 200
            tree.links.new(input=node_albedo.inputs["Primary Color"], output=node_cc_primary.outputs[0])
            node_cc_secondary = nodes.new(type="ShaderNodeAttribute")
            node_cc_secondary.attribute_name = "nwo.cc_secondary"
            node_cc_secondary.attribute_type = 'OBJECT'
            node_cc_secondary.location.x = node_albedo.location.x - 300
            node_cc_secondary.location.y = node_albedo.location.y
            tree.links.new(input=node_albedo.inputs["Secondary Color"], output=node_cc_secondary.outputs[0])
            node_cc_tertiary = nodes.new(type="ShaderNodeAttribute")
            node_cc_tertiary.attribute_name = "nwo.cc_tertiary"
            node_cc_tertiary.attribute_type = 'OBJECT'
            node_cc_tertiary.location.x = node_albedo.location.x - 300
            node_cc_tertiary.location.y = node_albedo.location.y - 200
            tree.links.new(input=node_albedo.inputs["Tertiary Color"], output=node_cc_tertiary.outputs[0])
            
        if has_bump:
            node_bump_mapping = self._add_group_node(tree, nodes, f"bump_mapping - {utils.game_str(e_bump_mapping.name)}")
            tree.links.new(input=node_albedo.inputs["Normal"], output=node_bump_mapping.outputs[0])
            
            
        if e_blend_mode in {BlendMode.ADDITIVE, BlendMode.ALPHA_BLEND, BlendMode.MULTIPLY}:
            blender_material.surface_render_method = 'BLENDED'
            node_blend_mode = self._add_group_node(tree, nodes, f"blend_mode - {utils.game_str(e_blend_mode.name)}")
            tree.links.new(input=node_blend_mode.inputs[0], output=final_node.outputs[0])
            final_node = node_blend_mode
            if e_blend_mode == BlendMode.ALPHA_BLEND and len(node_albedo.outputs) > 1:
                tree.links.new(input=node_blend_mode.inputs[1], output=node_albedo.outputs[1])
            elif e_blend_mode == BlendMode.MULTIPLY:
                tree.links.new(input=node_blend_mode.inputs[1], output=node_albedo.outputs[0])
                if len(node_albedo.outputs) > 1:
                    tree.links.new(input=node_blend_mode.inputs[2], output=node_albedo.outputs[1])
                
        # Make the Output
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        node_output.location.x = final_node.location.x + 300
        node_output.location.y = final_node.location.y
        
        # Link to output
        tree.links.new(input=node_output.inputs[0], output=final_node.outputs[0])

    def _to_nodes_bsdf(self, blender_material: bpy.types.Material):
        blender_material.use_nodes = True
        tree = blender_material.node_tree
        nodes = tree.nodes
        # Clear it out
        nodes.clear()
        # Make the BSDF and Output
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = Vector((300, 0))
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        tree.links.new(input=output.inputs[0], output=bsdf.outputs[0])
        albedo_enum = self._option_value_from_index(0)
        bump_mapping_enum = self._option_value_from_index(4)
        specular_mask_enum = self._option_value_from_index(3)
        blend_mode_enum = self._option_value_from_index(1)
        alpha_type = self._alpha_type(0, blend_mode_enum)
        diffuse = None
        normal = None
        specular = None
        if albedo_enum == 2:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_color'))
        else:
            diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeTexImage', data=self._image_from_parameter_name('base_map'), mapping=self._mapping_from_parameter_name('base_map'), diffalpha=bool(alpha_type))
            if not diffuse.data:
                diffuse = BSDFParameter(tree, bsdf, bsdf.inputs[0], 'ShaderNodeRGB', data=self._color_from_parameter_name('albedo_color'))

        if bump_mapping_enum > 0:
            normal = BSDFParameter(tree, bsdf, bsdf.inputs['Normal'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('bump_map', True), normal_type=self._normal_type_from_parameter_name('bump_map'), mapping=self._mapping_from_parameter_name('bump_map'))
            if not normal.data:
                normal = None
                
        if specular_mask_enum == 3:
            specular = BSDFParameter(tree, bsdf, bsdf.inputs['Specular IOR Level'], 'ShaderNodeTexImage', data=self._image_from_parameter_name('specular_mask_texture'), mapping=self._mapping_from_parameter_name('specular_mask_texture'))
            if not specular.data:
                specular = None
        elif specular_mask_enum > 0 and diffuse and type(diffuse.data) == bpy.types.Image:
            diffuse.diffspec = True
            
        if diffuse:
            diffuse.build(Vector((-300, 400)))
        if normal:
            normal.build(Vector((-200, 100)))
        if specular:
            specular.build(Vector((-300, -200)))

        self._set_alpha(alpha_type, blender_material)
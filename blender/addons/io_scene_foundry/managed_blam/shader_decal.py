


from enum import Enum

import bpy
from mathutils import Vector

from ..constants import NormalType

from .. import utils

from .shader import BSDFParameter, ChannelType, ShaderTag


class ShaderDecalTag(ShaderTag):
    tag_ext = 'shader_decal'
    group_supported = False

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
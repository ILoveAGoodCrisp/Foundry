"""H3 specialized render methods, dispatched through the named option library."""
from .shader_converter import ShaderTag


class ShaderCortanaTag(ShaderTag):
    tag_ext = 'shader_cortana'
    group_node_name = 'foundry_h3.shader_cortana'
    category_parameters = None
    category_parameters_path = None


class ShaderSkinTag(ShaderTag):
    tag_ext = 'shader_skin'
    group_node_name = 'foundry_h3.shader_skin'
    category_parameters = None
    category_parameters_path = None


class ShaderWaterTag(ShaderTag):
    tag_ext = 'shader_water'
    group_node_name = 'foundry_h3.shader_water'
    category_parameters = None
    category_parameters_path = None


class ShaderFurTag(ShaderTag):
    tag_ext = 'shader_fur'
    group_node_name = 'foundry_reach.shader_fur'
    category_parameters = None
    category_parameters_path = None


class ShaderFurStencilTag(ShaderTag):
    tag_ext = 'shader_fur_stencil'
    group_node_name = 'foundry_reach.shader_fur_stencil'
    category_parameters = None
    category_parameters_path = None


class ShaderMuxTag(ShaderTag):
    tag_ext = 'shader_mux'
    group_node_name = 'foundry_reach.shader_mux'
    category_parameters = None
    category_parameters_path = None


class ShaderMuxMaterialTag(ShaderTag):
    tag_ext = 'shader_mux_material'
    group_node_name = 'foundry_reach.shader_mux_material'
    category_parameters = None
    category_parameters_path = None


class ShaderScreenTag(ShaderTag):
    tag_ext = 'shader_screen'
    group_node_name = 'foundry_reach.shader_screen'
    category_parameters = None
    category_parameters_path = None

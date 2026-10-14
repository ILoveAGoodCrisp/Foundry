"""Reach render methods use native category order and saved socket bindings.

In particular, glass has a wetness category before opacity and custom's simple
albedo is distinct from multiply_map. Reach must not use shared Python enums
to address those native option blocks.
"""
import json
from .. import utils
from .connected_material import AnimatedParameterType
from .halo3_shader_io import render_method_family, selections
from .shader_preview_limits import engine_only_limit

FAMILIES = frozenset(('shader','shader_cortana','shader_custom','shader_decal',
    'shader_foliage','shader_fur','shader_fur_stencil','shader_glass',
    'shader_halogram','shader_mux','shader_mux_material','shader_screen',
    'shader_skin','shader_terrain','shader_water'))

def canonical(name):
    return {'from_opacity_alpha_and_albedo_alpha':'from_opacity_map_alpha_and_albedo_alpha'}.get(name,name)

def apply_options(shader):
    """Export visible menu selections, without imported option snapshots."""
    selected = {}
    for index, (category, options) in enumerate(shader.category_parameters.items()):
        names = list(options)
        if not names:
            continue
        socket = shader.group_node.inputs.get(category)
        value = canonical(socket.default_value) if socket is not None and socket.type == 'MENU' else None
        choice = next((name for name in names if canonical(name) == value), None)
        if choice is not None:
            while shader.block_options.Elements.Count <= index:
                shader.block_options.AddElement()
            shader.block_options.Elements[index].SelectField('short').SetStringData(str(names.index(choice)))
        else:
            # No authoring control: leave an existing destination value alone.
            raw = shader._option_value_from_index(index)
            choice = names[raw] if 0 <= raw < len(names) else names[0]
        selected[category] = choice
    return selected


def populate(shader,tree,node):
    bindings=json.loads(node.node_tree.get('reach_parameter_sockets','{}'))
    for name,parameter in shader.shader_parameters.items():
        ports=[node.inputs.get(s) for s in bindings.get(name,[])]
        if not ports or ports[0] is None:continue
        if parameter.type==0:
            texture=shader.group_set_image(tree,node,parameter,specified_input=ports[0].name)
            if texture is not None and len(ports)>1 and ports[1] is not None:
                if texture.type=='TEX_ENVIRONMENT':
                    alpha=tree.nodes.new('ShaderNodeTexImage');alpha.image=texture.image
                    tree.links.new(alpha.outputs['Alpha'],ports[1])
                else:tree.links.new(texture.outputs['Alpha'],ports[1])
        else:
            kind=AnimatedParameterType.COLOR if parameter.type in {1,5} else AnimatedParameterType.VALUE
            # RGB defaults are RGBA tuples; ARGB defaults are (RGBA, alpha)
            # pairs. Only the separate alpha socket should use for_alpha.
            shader._setup_input_with_function(
                ports[0],shader._value_from_parameter(parameter,kind),
                color_no_alpha=parameter.type==1)
            if parameter.type==5 and len(ports)>1:
                shader._setup_input_with_function(ports[1],shader._value_from_parameter(parameter,AnimatedParameterType.ALPHA),for_alpha=True)

def to_nodes(shader,material):
    selected=selections(shader)
    shader.has_rotating_bitmaps='rotating_bitmaps' in selected.get('misc','')
    shader.shader_parameters={}
    for category,option in selected.items():shader.shader_parameters.update(shader.category_parameters[category][option])
    shader.true_parameters={p.ui_name:p for p in shader.shader_parameters.values()}
    shader.true_parameters.update(shader.shader_parameters)
    family=render_method_family(shader)
    material.use_nodes=True;tree=material.node_tree;tree.nodes.clear()
    root=shader._add_group_node(tree,tree.nodes,'foundry_reach.'+family)
    if root.node_tree is None:raise RuntimeError('Missing Reach shader group: '+family)
    if not root.node_tree.get('reach_source_revision'):
        raise RuntimeError('The loaded Reach group predates the source audit. Reload reach_nodes.blend before importing.')
    choices=json.loads(root.node_tree['reach_option_choices'])
    unsupported=json.loads(root.node_tree.get('reach_unsupported_options','{}'));preview={}
    for category,option in selected.items():
        port=root.inputs.get(category)
        if port is None or port.type!='MENU':continue
        allowed=choices.get(category,[])
        target=next((o for o in allowed if canonical(o)==canonical(option)),None)
        if target is None:continue
        port.default_value=target;preview[category]=target
        # if option in unsupported.get(category,[]) and not engine_only_limit('reach',family,category,option):
        #     utils.print_warning(f'Reach {family}/{category}/{option}: limited preview; source option and parameters are preserved. See group limitations.')
    root['foundry_source_game']='reach'
    populate(shader,tree,root)
    from .reach_sampling import setup_sampling
    setup_sampling(shader,tree,root,selected)
    from .shader_address import finalize_addresses
    finalize_addresses(tree)
    if family in {'shader_cortana','shader_water','shader_fur_stencil'} or selected.get('blend_mode','opaque')!='opaque' or selected.get('alpha_test','none') not in {'none','off'}:
        material.surface_render_method='BLENDED'
    out=tree.nodes.new('ShaderNodeOutputMaterial');tree.links.new(root.outputs['Shader'],out.inputs['Surface'])
    from .connected_material import add_change_color_attributes
    add_change_color_attributes(shader,tree,root)
    return root

"""H3 group dispatch uses the tag definition's ordered names, not Reach enums.

Exports use the current menu sockets. Options without an authoring socket leave
the destination tag unchanged.
"""
import json
import bpy
from .. import utils
from .shader_preview_limits import engine_only_limit

ALIASES = {
    'from_flat_exture_as_cubemap': 'from_flat_texture_as_cubemap',
    'diffuse_only_(four_material_shaders_disable_detail_bump)': 'diffuse_only',
    'diffuse_plus_specular_(four_material_shaders_disable_detail_bump)': 'diffuse_plus_specular',
}
FALLBACKS = {'albedo':'default', 'bump_mapping':'standard', 'material_model':'cook_torrance',
             'environment_mapping':'dynamic', 'self_illumination':'simple'}
SCROLLING_CUBES = {'tint_blend_mask_cubemap', 'spec_tint_cubemap'}
SCROLLING_HELPER = 'foundry_h3.shader - scrolling cube vector'


def scrolling_vector_node(shader):
    return next((n for n in shader.group_node.id_data.nodes
                 if n.type == 'GROUP' and n.node_tree
                 and (n.node_tree.name == SCROLLING_HELPER or
                      (n.node_tree.name.startswith(SCROLLING_HELPER + '.')
                       and n.node_tree.name[len(SCROLLING_HELPER)+1:].isdigit()))), None)


def option_socket(shader, category):
    socket = shader.group_node.inputs.get(category)
    if socket is None and category == 'misc_attr_animation':
        helper = scrolling_vector_node(shader)
        if helper is not None:
            socket = helper.inputs.get(category)
    return socket

def canonical(name):
    return ALIASES.get(name, name)

def group_choices(tree):
    """Saved build metadata is also usable without constructing an instance."""
    return json.loads(tree.get('h3_option_choices', '{}'))


def render_method_family(shader):
    """Decal systems embed shader_decal render methods inside their layers."""
    family = shader.system_path.suffix.lstrip('.').casefold()
    return 'shader_decal' if family == 'decal_system' else family

def selections(shader):
    result={}
    for index,(category,options) in enumerate(shader.category_parameters.items()):
        index_value=shader._option_value_from_index(index)
        names=list(options)
        if not names:continue
        if not 0 <= index_value < len(names):
            # utils.print_warning(f'H3 {category} option {index_value} is not defined; preview uses {names[0]}')
            index_value=0
        result[category]=names[index_value]
    return result

def apply_options(shader):
    """Export visible menu selections, without imported option snapshots."""
    selected = {}
    for index, (category, options) in enumerate(shader.category_parameters.items()):
        names = list(options)
        if not names:
            continue
        socket = option_socket(shader, category)
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


def to_nodes(shader,material):
    selected=selections(shader)
    shader.has_rotating_bitmaps='rotating_bitmaps' in selected.get('misc','')
    shader.shader_parameters={}
    for category,choice in selected.items():shader.shader_parameters.update(shader.category_parameters[category][choice])
    family=render_method_family(shader)
    if shader.game == 'halo3odst':
        from .halo3_odst_io import normalise_parameters
        shader.shader_parameters = normalise_parameters(shader.shader_parameters, family)
    shader.true_parameters={p.ui_name:p for p in shader.shader_parameters.values()}
    # H3 options sometimes use the internal name in sockets and UI text in tags.
    shader.true_parameters.update(shader.shader_parameters)
    material.use_nodes=True;tree=material.node_tree;tree.nodes.clear()
    prefix = 'foundry_h3odst.' if shader.game == 'halo3odst' else 'foundry_h3.'
    node=shader._add_group_node(tree,tree.nodes,prefix+family)
    if node.node_tree is None:raise RuntimeError('Missing H3 node library group: '+family)
    choices=group_choices(node.node_tree);unsupported=json.loads(node.node_tree.get('h3_unsupported_options','{}'))
    preview={}
    for category,choice in selected.items():
        socket=node.inputs.get(category)
        if socket is None or socket.type!='MENU':
            first=next(iter(shader.category_parameters[category]),None)
            helper_supported=(category=='warp' and choice=='from_texture' and hasattr(shader,'_setup_warp')) or (
                category=='misc_attr_animation' and choice=='scrolling_cube'
                and selected.get('material_model') in {'cook_torrance_scrolling_cube_mask','cook_torrance_scrolling_cube'})
            # if choice!=first and category not in {'misc'} and not helper_supported and not engine_only_limit(shader.game,family,category,choice):
            #     utils.print_warning(f'H3 {category}: {choice} has no node preview. The source option is retained for export.')
            continue
        allowed=choices.get(category,[])
        target=next((s for s in allowed if canonical(s)==canonical(choice)),None)
        if target in unsupported.get(category,[]):target=None
        if target is None:
            target=next((s for s in allowed if canonical(s)==FALLBACKS.get(category)),None)
            if target is None:target=allowed[0] if allowed else socket.default_value
            # if not engine_only_limit(shader.game,family,category,choice):
            #     utils.print_warning(f'H3 {category}: {choice} is not implemented; preview uses {target}. The source option is retained for export.')
        socket.default_value=target;preview[category]=target
    node['foundry_source_game'] = shader.game
    shader.populate_chiefster_node(tree,node,0)
    # Alpha components are sometimes appended far from their original color
    # socket to preserve the existing interface order.
    from .connected_material import AnimatedParameterType
    for socket in node.inputs:
        if not socket.name.endswith('_alpha'):continue
        parameter=shader.true_parameters.get(socket.name[:-6])
        if parameter is not None:
            shader._setup_input_with_function(socket,shader._value_from_parameter(parameter,AnimatedParameterType.ALPHA),True)
    shader._setup_h3_cubemap_reflector(tree,node)
    setup_extra_vectors(shader,tree,node)
    setup_scrolling_vectors(shader,tree,node,selected)
    if family=='shader_cortana':
        from .halo3_specialized_io import setup_cortana
        setup_cortana(shader,tree,node)
    if family=='shader_halogram' and hasattr(shader,'_setup_warp'):shader._setup_warp(tree,node)
    if node.node_tree.get('h3_sampling_revision'):
        from .halo3_sampling import setup_sampling
        setup_sampling(shader, tree, node, selected)
    if shader.game == 'halo3odst':
        from .halo3_odst_io import setup_odst
        setup_odst(shader, tree, node, selected)
    elif family == 'shader_halogram' and selected.get('self_illumination') == 'multilayer_additive':
        from .halo3_odst_io import setup_multilayer
        setup_multilayer(shader, tree, node)
    from .shader_address import finalize_addresses
    finalize_addresses(tree)
    from .detail_mip_fade import setup_detail_fade
    setup_detail_fade(shader, tree, node)
    # if family=='shader_skin':
    #     utils.print_warning('H3 skin.fx contains white placeholder passes. Skin tag options are preserved, but the preview is a source placeholder.')
    if family in {'shader_cortana','shader_water'} or selected.get('blend_mode','opaque')!='opaque' or selected.get('alpha_test','none') not in {'none','off'}:
        material.surface_render_method='BLENDED'
        if node.inputs.get('material is two-sided'):node.inputs['material is two-sided'].default_value=True
    out=tree.nodes.new('ShaderNodeOutputMaterial');tree.links.new(node.outputs['Shader'],out.inputs['Surface'])
    from .connected_material import add_change_color_attributes
    add_change_color_attributes(shader,tree,node,decal=family=='shader_decal')
    return node


def setup_scrolling_vectors(shader,tree,node,selected):
    textures=[]
    for socket in node.inputs:
        if socket.name.partition('.')[0] not in SCROLLING_CUBES or not socket.is_linked:continue
        texture=socket.links[0].from_node
        if texture.type=='TEX_ENVIRONMENT':textures.append(texture)
    if not textures:return
    helper=shader._add_group_node(tree,tree.nodes,SCROLLING_HELPER)
    if helper.node_tree is None:
        tree.nodes.remove(helper);return
    choice=selected.get('misc_attr_animation','off')
    preview=choice if choice in {'off','scrolling_cube'} else 'off'
    helper.inputs['misc_attr_animation'].default_value=preview
    from .connected_material import AnimatedParameterType
    for socket in helper.inputs:
        if socket.type=='MENU':continue
        parameter=shader.true_parameters.get(socket.name)
        if parameter is not None:
            shader._setup_input_with_function(socket,shader._value_from_parameter(parameter,AnimatedParameterType.VALUE),True)
    for texture in textures:tree.links.new(helper.outputs['Vector'],texture.inputs['Vector'])

def setup_extra_vectors(shader,tree,node):
    """Normal-directed tint cubes and dependent decal palette lookups."""
    normal_maps={'custom_cube','blend_map','spec_blend_map'}
    for socket in node.inputs:
        if socket.name.partition('.')[0] not in normal_maps or not socket.is_linked:continue
        texture=socket.links[0].from_node
        if texture.type!='TEX_ENVIRONMENT':continue
        # The custom material tint uses the same bumped normal as the surface.
        reflector=next((n for n in tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.name.startswith('foundry_h3 - cubemap reflector')),None)
        if reflector is None:
            reflector=shader._add_group_node(tree,tree.nodes,'foundry_h3 - cubemap reflector')
            for dest in reflector.inputs:
                source=node.inputs.get(dest.name)
                if source is None:continue
                dest.default_value=source.default_value
                if source.is_linked:tree.links.new(source.links[0].from_socket,dest)
        vector=reflector.outputs.get('Normal') if reflector else None
        if vector is None:
            geom=tree.nodes.new('ShaderNodeNewGeometry');geom.label='H3 normal-directed color cube';vector=geom.outputs['Normal']
        tree.links.new(vector,texture.inputs['Vector'])
    palette=node.inputs.get('palette.rgb')
    if palette is not None and palette.is_linked:
        tex=palette.links[0].from_node;base=node.inputs.get('base_map.rgb')
        # The base map is consumed by this dependent lookup outside the group,
        # so Blender marks its group socket unused and population skips it.
        if base is not None and not base.is_linked:
            parameter=shader.true_parameters.get('base_map')
            if parameter is not None:
                shader.group_set_image(tree,node,parameter,specified_input=base.name)
        if tex.type=='TEX_IMAGE' and base is not None and base.is_linked:
            helper=shader._add_group_node(tree,tree.nodes,'foundry_h3.shader_decal - palette_vector')
            if helper.node_tree:
                tree.links.new(base.links[0].from_socket,helper.inputs['base_map.rgb'])
                tree.links.new(helper.outputs['Vector'],tex.inputs['Vector'])
                # Palette endpoints must not wrap back to the opposite colour.
                tex.extension='EXTEND'
    # A decal alpha mask uses the untiled tile UV, independently of the base
    # texture's authored transform. Full sprite-atlas runtime data is unavailable.
    option=node.inputs.get('albedo')
    alpha=node.inputs.get('alpha_map.a')
    if option and option.default_value.endswith('alpha_mask') and alpha and alpha.is_linked:
        tex=alpha.links[0].from_node
        if tex.type=='TEX_IMAGE':shader.add_texcoord_node(tree,tex.inputs['Vector'])

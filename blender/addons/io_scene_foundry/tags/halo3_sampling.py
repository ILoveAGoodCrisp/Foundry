"""Source-coordinate sampling for H3/ODST, using native Blender closures.

Closures are private sampler plumbing; material controls remain tag parameters.
The original texture nodes remain available for bitmap/transform export.
"""
import bpy
from .. import utils
from .connected_material import AnimatedParameterType
from .halo3_specialized_io import _copy_input, _math, _value
from .halo3_odst_io import (_put, _vector, _xyz, _mapping, _scale, _copy_sample,
                           _tangent_view, _remember, _texture)


def _ensure_texture(shader, tree, root, name):
    port = root.inputs.get(name + '.rgb')
    if port is None: return None
    if port.is_linked:
        node = port.links[0].from_node
        return node if node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'} else None
    parameter = shader.shader_parameters.get(name)
    if parameter is None: return None
    return shader.group_set_image(tree, root, parameter, specified_input=port.name)


def _ensure_value(shader, root, name):
    port = root.inputs.get(name); parameter = shader.shader_parameters.get(name)
    if port is None or parameter is None or port.is_linked: return
    kind = AnimatedParameterType.COLOR if parameter.type in {1, 5} else AnimatedParameterType.VALUE
    # RGB defaults are RGBA tuples; ARGB defaults pair that tuple with alpha.
    # Sampling controls need the color component, not the separate alpha value.
    shader._setup_input_with_function(
        port, shader._value_from_parameter(parameter, kind), color_no_alpha=parameter.type == 1)


def height_closure(tree, texture):
    """Re-evaluate the same green-channel image at each supplied coordinate."""
    start = tree.nodes.new('NodeClosureInput'); end = tree.nodes.new('NodeClosureOutput')
    start.label = 'Height sampler coordinates'; end.label = 'Height sampler: green'
    start.pair_with_output(end); end.define_signature = True
    end.input_items.new('VECTOR', 'Vector'); end.output_items.new('FLOAT', 'Height')
    sample = _copy_sample(tree, texture, 'Parallax height sampler')
    channel = tree.nodes.new('ShaderNodeSeparateColor')
    tree.links.new(start.outputs['Vector'], sample.inputs['Vector'])
    tree.links.new(sample.outputs['Color'], channel.inputs[0])
    tree.links.new(channel.outputs['Green'], end.inputs['Height'])
    # Only sampler copies are inside the zone. The exported original keeps its mapping.
    start.location = (texture.location.x, texture.location.y-400)
    sample.location = start.location + __import__('mathutils').Vector((220, 0))
    channel.location = start.location + __import__('mathutils').Vector((500, 0))
    end.location = start.location + __import__('mathutils').Vector((720, 0))
    return end.outputs['Closure']


def base_uv(tree):
    helper = next((n for n in tree.nodes if n.get('h3_parallax_vector')), None)
    if helper: return helper.outputs['Vector']
    return tree.nodes.new('ShaderNodeTexCoord').outputs['UV']


def setup_parallax(shader, tree, root, selected):
    mode = selected.get('parallax', 'off')
    if mode not in {'simple','interpolated','simple_detail'}: return
    texture = _ensure_texture(shader, tree, root, 'height_map')
    if texture is None or texture.type != 'TEX_IMAGE':
        utils.print_warning('H3 parallax needs a height bitmap. The tag option is retained; UVs are unchanged.')
        return
    _ensure_value(shader, root, 'height_scale')
    detail = _ensure_texture(shader, tree, root, 'height_scale_map') if mode == 'simple_detail' else None
    # Capture the authored samples before making the closure's private copy.
    targets = set()
    excluded = {'height_map','height_scale_map','flat_environment_map','palette','specular_lobe','glancing_falloff'}
    for port in root.inputs:
        if port.name.partition('.')[0] in excluded: continue
        if port.is_linked and port.links[0].from_node.type == 'TEX_IMAGE': targets.add(port.links[0].from_node)
    mapping = _mapping(texture)
    uv_port = mapping.inputs['Vector'] if mapping else texture.inputs['Vector']
    uv = uv_port.links[0].from_socket if uv_port.is_linked else None
    helper = shader._add_group_node(tree, tree.nodes, '.H3 parallax vector')
    helper.label = 'Halo parallax — reimport after changing mode'
    helper['h3_parallax_vector'] = True
    helper.inputs['parallax'].default_value = mode
    if uv is None: shader.add_texcoord_node(tree, helper.inputs['UV'])
    else: _put(tree, helper.inputs['UV'], uv)
    tree.links.new(_tangent_view(tree), helper.inputs['View'])
    tree.links.new(height_closure(tree, texture), helper.inputs['Height Texture'])
    tree.links.new(_scale(tree, mapping), helper.inputs['Scale'])
    offset = [_value(mapping.inputs['Translate '+axis]) if mapping else 0 for axis in ('X','Y')]
    tree.links.new(_xyz(tree, (*offset,0), 'Height-map offset'), helper.inputs['Offset'])
    _copy_input(tree, root.inputs['height_scale'], helper.inputs['height_scale'])
    if detail:
        separate = tree.nodes.new('ShaderNodeSeparateColor')
        tree.links.new(detail.outputs['Color'], separate.inputs[0])
        tree.links.new(separate.outputs['Green'], helper.inputs['Height Scale Sample'])
    for sample in targets:
        own_mapping = _mapping(sample)
        tree.links.new(helper.outputs['Vector'], own_mapping.inputs['Vector'] if own_mapping else sample.inputs['Vector'])


def setup_scope_blur(shader, tree, root):
    texture = _ensure_texture(shader, tree, root, 'self_illum_map')
    if texture is None or texture.type != 'TEX_IMAGE': return
    _remember(root, texture, 'self_illum_map')
    if not texture.inputs['Vector'].is_linked: tree.links.new(base_uv(tree), texture.inputs['Vector'])
    base = texture.inputs['Vector'].links[0].from_socket
    # Keep the first original sample in the result, so export finds its source.
    # Save the input mapping before offsetting this image, then offset all copies.
    total = None
    for i,(x,y) in enumerate(((1,1),(-1,1),(-1,-1),(1,-1))):
        sample = texture if i == 0 else _copy_sample(tree, texture, 'Scope blur corner '+str(i))
        coord = _vector(tree, 'ADD', base, (x*.001736/2,y*.003125/2,0), 'Source PC scope offset')
        tree.links.new(coord, sample.inputs['Vector'])
        total = sample.outputs['Color'] if total is None else _vector(tree, 'ADD', total, sample.outputs['Color'], 'Four scope samples')
    tree.links.new(_vector(tree, 'SCALE', total, .25, 'Scope sample average'), root.inputs['self_illum_map.rgb'])
    # The authored tiling now sits before an offset node; exporter handles it.
    texture['h3_sampling_offset'] = True


def setup_flat_environment(shader, tree, root, selected):
    mode = selected.get('environment_mapping','')
    if mode not in {'from_flat_texture','from_flat_exture_as_cubemap','from_flat_texture_as_cubemap'}: return
    texture = _ensure_texture(shader, tree, root, 'flat_environment_map')
    if texture is None: return
    cube = mode != 'from_flat_texture'
    if (texture.type == 'TEX_ENVIRONMENT') != cube:
        utils.print_warning('H3 flat environment bitmap type does not match its selected 2D/cubemap mode; check the source tag.')
        return
    prefix = 'foundry_h3odst' if getattr(shader,'game','halo3') == 'halo3odst' else 'foundry_h3'
    reflector = next((n for n in tree.nodes if n.type=='GROUP' and n.node_tree and n.node_tree.name==prefix+' - cubemap reflector'), None)
    if reflector is None:
        reflector = shader._add_group_node(tree,tree.nodes,prefix+' - cubemap reflector')
        for port in reflector.inputs:
            source = root.inputs.get(port.name)
            if source is None: source = root.inputs.get(port.name+'.rgb')
            if source is not None:
                value = _value(source)
                if port.type == 'MENU' and isinstance(value,str): value = {'detail_blend':'detail_masked','three_detail_blend':'detail_plus_detail_masked'}.get(value,value)
                _put(tree,port,value)
    helper = shader._add_group_node(tree,tree.nodes,'.H3 flat environment vector')
    helper.label = 'Halo flat environment projection'
    tree.links.new(reflector.outputs['Vector'],helper.inputs['Reflection'])
    for port in helper.inputs:
        if port.name=='Reflection':continue
        _ensure_value(shader,root,port.name);_copy_input(tree,root.inputs[port.name],port)
    tree.links.new(helper.outputs['Cube Vector' if cube else 'UV'],texture.inputs['Vector'])


def setup_sampling(shader, tree, root, selected):
    if selected.get('specular') == 'modulate':
        # Preserve this native control even though the receiving G-buffer is
        # unavailable and the preview deliberately leaves specular unchanged.
        _ensure_value(shader, root, 'specular_multiplier')
    setup_parallax(shader,tree,root,selected)
    setup_flat_environment(shader,tree,root,selected)
    if selected.get('self_illumination')=='scope_blur':setup_scope_blur(shader,tree,root)


def authored_mapping(texture):
    """Find a scope sample's original mapping through its fixed offset only."""
    if not texture.get('h3_sampling_offset'):return None
    port=texture.inputs['Vector']
    if not port.is_linked:return None
    offset=port.links[0].from_node
    if offset.type!='VECT_MATH' or offset.operation!='ADD' or not offset.inputs[0].is_linked:return None
    source=offset.inputs[0].links[0].from_node
    return source if source.type=='GROUP' and source.inputs.get('Scale X') is not None else None

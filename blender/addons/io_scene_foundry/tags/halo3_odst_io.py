"""ODST dependent texture sampling; tag bitmaps stay identifiable on export.

Portable Eevee/Cycles nodes cannot access Halo's per-light half vectors or
depth buffer. The view-angle lobe proxy and disabled depth fade are explicit
preview limitations, not additional tag options.
"""
import math
from copy import copy
import bpy
from .. import utils
from .halo3_specialized_io import _copy_input, _math, _value


def normalise_parameters(parameters, family):
    """Repair the shipped decal option's bitmap-typed scalar declarations.

    Other decal options and decal.fx:69-70 define u_tiles/v_tiles as floats.
    Work on copies so cached editing-kit definitions remain unchanged.
    """
    if family != 'shader_decal': return parameters
    result = dict(parameters)
    for name in ('u_tiles', 'v_tiles'):
        if name in result and result[name].type == 0:
            parameter = copy(result[name]); parameter.type = 2
            parameter.default = parameter.default_real; result[name] = parameter
    return result


def _put(tree, port, value):
    if isinstance(value, bpy.types.NodeSocket):
        tree.links.new(value, port)
    else:
        port.default_value = value


def _vector(tree, operation, a, b=(0, 0, 0), label=''):
    n = tree.nodes.new('ShaderNodeVectorMath'); n.operation = operation; n.label = label
    _put(tree, n.inputs[0], a); _put(tree, n.inputs[3 if operation == 'SCALE' else 1], b)
    return n.outputs[1 if operation in {'DOT_PRODUCT', 'LENGTH'} else 0]


def _xyz(tree, values, label):
    n = tree.nodes.new('ShaderNodeCombineXYZ'); n.label = label
    for port, value in zip(n.inputs, values): _put(tree, port, value)
    return n.outputs[0]


def _uv(tree):
    # Parallax runs before ODST dependent samplers, matching entry_points.fx.
    parallax = next((n for n in tree.nodes if n.get('h3_parallax_vector')), None)
    if parallax is not None: return parallax.outputs['Vector']
    n = tree.nodes.new('ShaderNodeTexCoord')
    return n.outputs['UV']


def _tangent_view(tree):
    geo = tree.nodes.new('ShaderNodeNewGeometry')
    tangent = tree.nodes.new('ShaderNodeTangent'); tangent.direction_type = 'UV_MAP'
    bitangent = _vector(tree, 'CROSS_PRODUCT', geo.outputs['Normal'], tangent.outputs[0], 'UV bitangent')
    return _xyz(tree, [_vector(tree, 'DOT_PRODUCT', geo.outputs['Incoming'], axis) for axis in (tangent.outputs[0], bitangent, geo.outputs['Normal'])], 'Tangent-space view toward camera')


def _texture(root, parameter):
    port = root.inputs.get(parameter + '.rgb')
    if port is None: port = root.inputs.get(parameter + '.a')
    if port is None or not port.is_linked: return None
    n = port.links[0].from_node
    while n.type == 'REROUTE' and n.inputs[0].is_linked: n = n.inputs[0].links[0].from_node
    return n if n.type == 'TEX_IMAGE' else None


def _remember(root, texture, parameter):
    texture['h3_source_parameter'] = parameter
    root['h3_dependent_textures'] = True


def source_texture(root, port):
    """Find the authored sample only within this input's upstream graph.

    Renaming the image node is safe. Replacing its wire with a new image lets
    the normal exporter use the new image instead of stale stored metadata.
    """
    parameter = port.name.partition('.')[0]
    pending = [link.from_node for link in port.links]; seen = set()
    while pending:
        n = pending.pop(0)
        if n in seen: continue
        seen.add(n)
        if n.type == 'TEX_IMAGE' and n.get('h3_source_parameter') == parameter: return n
        # Do not search a directly replaced image's vector dependencies.
        if n.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'}: continue
        pending.extend(link.from_node for s in n.inputs for link in s.links)
    return None


def _mapping(texture):
    if texture is None or not texture.inputs['Vector'].is_linked: return None
    n = texture.inputs['Vector'].links[0].from_node
    return n if n.type == 'GROUP' and n.inputs.get('Scale X') is not None else None


def _scale(tree, mapping):
    values = []
    for axis in ('X', 'Y'):
        values.append(_math(tree, 'MULTIPLY', _value(mapping.inputs['Scale ' + axis]), _value(mapping.inputs['Scale Multiplier']), 'Authored map scale ' + axis) if mapping else 1)
    return _xyz(tree, (*values, 1), 'Map XY scale')


def _set_coordinates(tree, texture, vector, transformed=True):
    mapping = _mapping(texture)
    destination = mapping.inputs['Vector'] if transformed and mapping else texture.inputs['Vector']
    tree.links.new(vector, destination)


def _window_room(shader, tree, root):
    transform = _texture(root, 'transform')
    if transform is None:
        # The source reads only transform_xform, so this parameter often has no
        # bitmap reference. Still import/export its authored transform functions.
        transform = tree.nodes.new('ShaderNodeTexImage'); transform.label = 'Room grid transform (bitmap unused)'
        transform['h3_transform_only'] = True
        tree.links.new(transform.outputs['Color'], root.inputs['transform.rgb'])
        parameter = shader.shader_parameters.get('transform')
        mapping = shader._tiling_from_animated_parameters(tree, parameter) if parameter else None
        if mapping: tree.links.new(mapping.outputs[0], transform.inputs['Vector'])
    _remember(root, transform, 'transform')
    mapping = _mapping(transform)
    helper = shader._add_group_node(tree, tree.nodes, '.ODST window intersection')
    if helper.node_tree is None: raise RuntimeError('Missing ODST window intersection helper')
    helper.label = 'ODST room intersection and depth falloff'
    base_uv = _value(mapping.inputs['Vector']) if mapping and mapping.inputs['Vector'].is_linked else _uv(tree)
    _put(tree, helper.inputs['UV'], base_uv)
    tree.links.new(_tangent_view(tree), helper.inputs['View'])
    tree.links.new(_scale(tree, mapping), helper.inputs['Scale'])
    offset = [_value(mapping.inputs['Translate ' + axis]) if mapping else 0 for axis in ('X', 'Y')]
    tree.links.new(_xyz(tree, (*offset, 0), 'Room grid offset'), helper.inputs['Offset'])
    _copy_input(tree, root.inputs['distance_fade_scale'], helper.inputs['distance_fade_scale'])
    for parameter, vector, weight in [('walls', 'Walls', 'Wall weight'), ('floors', 'Horizontal', 'Floor weight'), ('ceiling', 'Horizontal', 'Ceiling weight')]:
        texture = _texture(root, parameter)
        # A missing bitmap still needs its default color masked by the selected
        # face, otherwise it contributes on every face of the room.
        color = _value(root.inputs[parameter + '.rgb'])
        if texture:
            _remember(root, texture, parameter)
            _set_coordinates(tree, texture, helper.outputs[vector])
        result = _vector(tree, 'SCALE', color, helper.outputs[weight], parameter.title() + ' selection and distance falloff')
        tree.links.new(result, root.inputs[parameter + '.rgb'])


def _normal(shader, tree, root):
    helper = next((n for n in tree.nodes if n.type == 'GROUP' and n.node_tree and n.node_tree.name.startswith('foundry_h3odst - cubemap reflector')), None)
    if helper is None:
        helper = shader._add_group_node(tree, tree.nodes, 'foundry_h3odst - cubemap reflector')
        for port in helper.inputs:
            source = root.inputs.get(port.name)
            if source is None: source = root.inputs.get(port.name + '.rgb')
            if source is not None: _copy_input(tree, source, port)
    return helper.outputs['Normal']


def _custom_specular(shader, tree, root):
    geo = tree.nodes.new('ShaderNodeNewGeometry')
    cosine = _vector(tree, 'DOT_PRODUCT', _normal(shader, tree, root), geo.outputs['Incoming'], 'View cosine for lookup preview')
    cosine = _math(tree, 'MAXIMUM', cosine, 0, 'Nonnegative lookup cosine')
    fresnel = _texture(root, 'glancing_falloff')
    if fresnel: _set_coordinates(tree, fresnel, _xyz(tree, (cosine, 0, 0), 'Fresnel lookup N.V'), transformed=False)
    material = tree.nodes.new('ShaderNodeSeparateColor')
    _put(tree, material.inputs[0], _value(root.inputs['material_map.rgb']))
    lobe = _texture(root, 'specular_lobe')
    if lobe: _set_coordinates(tree, lobe, _xyz(tree, (cosine, material.outputs['Green'], 0), 'Lobe lookup: N.V proxy and material row'), transformed=False)
    # Per-light half vectors are unavailable; this expected limitation is
    # documented on the group rather than reported for every material.


def _palette(shader, tree, root):
    texture = _texture(root, 'palette')
    if texture:
        helper = shader._add_group_node(tree, tree.nodes, 'foundry_h3odst.shader_halogram - palette vector')
        for port in helper.inputs: _copy_input(tree, root.inputs[port.name], port)
        _set_coordinates(tree, texture, helper.outputs[0], transformed=False)
    # Engine depth fading is documented on the group; keep the neutral preview.


def _copy_sample(tree, original, label):
    n = tree.nodes.new('ShaderNodeTexImage'); n.label = label
    if 'foundry_address_modes' in original:
        n['foundry_address_modes'] = list(original['foundry_address_modes'])
    n.image = original.image; n.interpolation = original.interpolation; n.extension = original.extension; n.projection = original.projection
    for key in ('frame_duration', 'frame_start', 'frame_offset', 'use_auto_refresh', 'use_cyclic'): setattr(n.image_user, key, getattr(original.image_user, key))
    if tree.animation_data:
        path = original.image_user.path_from_id('frame_offset')
        if any(f.data_path == path for f in tree.animation_data.drivers):
            driver = n.image_user.driver_add('frame_offset').driver; driver.type = 'SCRIPTED'
            variable = driver.variables.new(); variable.name = 'offset'; variable.type = 'SINGLE_PROP'
            variable.targets[0].id_type = 'NODETREE'; variable.targets[0].id = tree; variable.targets[0].data_path = path
            driver.expression = 'offset'
    return n


def setup_multilayer(shader, tree, root):
    texture = _texture(root, 'self_illum_map')
    if texture is None: return
    _remember(root, texture, 'self_illum_map')
    requested = max(0, root.inputs['layers_of_4'].default_value)
    count = min(128, math.ceil(requested) * 4)
    if count == 0:
        # Keep the source sample reachable for bitmap export at zero intensity.
        tree.links.new(_vector(tree, 'SCALE', texture.outputs['Color'], 0, 'Zero source layers'), root.inputs['self_illum_map.rgb'])
        return
    mapping = _mapping(texture)
    if not texture.inputs['Vector'].is_linked: tree.links.new(_uv(tree), texture.inputs['Vector'])
    base = texture.inputs['Vector'].links[0].from_socket
    view = tree.nodes.new('ShaderNodeSeparateXYZ'); tree.links.new(_tangent_view(tree), view.inputs[0])
    tangent_xy = _xyz(tree, (_math(tree, 'MULTIPLY', view.outputs['X'], _value(root.inputs['texcoord_aspect_ratio']), 'Layer aspect'), view.outputs['Y'], 0), 'Layer offset direction')
    offset = _vector(tree, 'SCALE', _vector(tree, 'MULTIPLY', tangent_xy, _scale(tree, mapping)), _math(tree, 'DIVIDE', _value(root.inputs['layer_depth']), requested * 4, 'Depth per layer'), 'Per-layer texture offset')
    rgb = None
    for index in range(count):
        sample = texture if index == 0 else _copy_sample(tree, texture, 'ODST illumination layer ' + str(index))
        if index: tree.links.new(_vector(tree, 'SUBTRACT', base, _vector(tree, 'SCALE', offset, index), 'Layer sample offset'), sample.inputs['Vector'])
        weight = _math(tree, 'DIVIDE', _math(tree, 'POWER', _value(root.inputs['depth_darken']), index, 'Layer depth attenuation'), requested * 4, 'Source layer average')
        color = _vector(tree, 'SCALE', sample.outputs['Color'], weight, 'Weighted illumination sample')
        rgb = color if rgb is None else _vector(tree, 'ADD', rgb, color, 'Accumulated layers')
    tree.links.new(rgb, root.inputs['self_illum_map.rgb'])
    if requested * 4 > 128 or root.inputs['layers_of_4'].is_linked:
        utils.print_warning('ODST multilayer preview uses up to 128 fixed samples. Reimport after changing layers_of_4; animated sample counts are not supported.')


def setup_odst(shader, tree, root, selected):
    mode = selected.get('self_illumination')
    if mode == 'window_room': _window_room(shader, tree, root)
    elif mode == 'palettized_plasma': _palette(shader, tree, root)
    elif mode == 'multilayer_additive': setup_multilayer(shader, tree, root)
    if selected.get('material_model') == 'custom_specular': _custom_specular(shader, tree, root)
    if selected.get('material_model') == 'hair':
        # hair_material.fx samples these textures directly at texcoord.
        vector = _uv(tree)
        for name in ('specular_map', 'specular_noise_map', 'specular_shift_map'):
            texture = _texture(root, name)
            if texture: _set_coordinates(tree, texture, vector, transformed=False)

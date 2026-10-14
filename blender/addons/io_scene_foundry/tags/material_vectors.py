"""Texture-coordinate sampling required by H4/H2AMP material templates."""
import bpy

from .. import utils
from ..material_shader_library import MATERIAL_LIBRARIES, parameter_key, source_shader


def _socket(node, name):
    key = parameter_key(name)
    return next((s for s in node.inputs if parameter_key(s.name) == key), None)


def _texture(node, name):
    socket = _socket(node, name)
    if socket is not None and socket.links:
        source = socket.links[0].from_node
        if source.type == 'TEX_IMAGE':
            return source


def _duplicate(tree, texture):
    copy = tree.nodes.new('ShaderNodeTexImage')
    for attr in ('image', 'extension', 'interpolation', 'projection', 'projection_blend'):
        setattr(copy, attr, getattr(texture, attr))
    if texture.inputs['Vector'].links:
        tree.links.new(_copy_vector_chain(tree, texture.inputs['Vector'].links[0].from_socket), copy.inputs['Vector'])
    return copy


def _copy_vector_chain(tree, output):
    node = output.node
    if node.type not in {'GROUP', 'MAPPING', 'REROUTE'} or node.inputs.get('Vector') is None:
        return output
    copy = tree.nodes.new(node.bl_idname)
    if node.type == 'GROUP':
        copy.node_tree = node.node_tree
    elif node.type == 'MAPPING':
        copy.vector_type = node.vector_type
    for key, value in node.items():
        copy[key] = value
    for source, target in zip(node.inputs, copy.inputs):
        if source.links:
            upstream = source.links[0].from_socket
            tree.links.new(_copy_vector_chain(tree, upstream) if source.name == 'Vector' else upstream, target)
        elif hasattr(source, 'default_value'):
            target.default_value = source.default_value
    return next(s for s in copy.outputs if s.identifier == output.identifier)


def _vector_input(texture, before_transform=False):
    socket = texture.inputs['Vector']
    seen = set()
    while socket.links:
        node = socket.links[0].from_node
        if node in seen:
            break
        seen.add(node)
        address = node.type == 'GROUP' and node.node_tree and 'foundry_address_modes' in node.node_tree
        if not address and not before_transform:
            break
        upstream = node.inputs.get('Vector')
        if upstream is None:
            break
        socket = upstream
    return socket


def _uv(tree, name='UVMap0'):
    node = tree.nodes.new('ShaderNodeUVMap')
    node.uv_map = name
    return node.outputs['UV']


def _coordinates(tree, texture, before_transform=False):
    socket = _vector_input(texture, before_transform)
    return socket, socket.links[0].from_socket if socket.links else _uv(tree)


def _offset(tree, texture, offset, before_transform=False):
    socket, previous = _coordinates(tree, texture, before_transform)
    add = tree.nodes.new('ShaderNodeVectorMath'); add.operation = 'ADD'
    tree.links.new(previous, add.inputs[0]); tree.links.new(offset, add.inputs[1])
    tree.links.new(add.outputs['Vector'], socket)


def _time(tree):
    node = tree.nodes.new('ShaderNodeValue'); node.label = 'Shader time (seconds)'
    driver = node.outputs[0].driver_add('default_value').driver
    for name, path in (('start', 'frame_start'), ('fps', 'render.fps'), ('base', 'render.fps_base')):
        variable = driver.variables.new(); variable.name = name; variable.type = 'SINGLE_PROP'
        variable.targets[0].id_type = 'SCENE'; variable.targets[0].id = bpy.context.scene
        variable.targets[0].data_path = path
    driver.expression = '(frame - start) * base / fps'
    return node.outputs[0]


def setup_material_vectors(material, tree, surface, ui_parameters, true_parameters):
    shader = source_shader(surface.node_tree)
    basename = shader.rsplit('/', 1)[-1]
    library = MATERIAL_LIBRARIES[material.game]

    def helper(name):
        resource = utils.add_node_from_resources(library, name)
        if resource is None:
            return None
        node = tree.nodes.new('ShaderNodeGroup'); node.node_tree = resource
        material.populate_chiefster_node(tree, node, ui_parameters, true_parameters)
        if 'time' in node.inputs:
            tree.links.new(_time(tree), node.inputs['time'])
        return node

    if basename in {'srf_ca_color_warp', 'srf_ca_color_warp_vertmask'}:
        node = helper('srf_ca_color_warp [vector]')
        if node:
            for name in ('diffuseMap', 'selfIllumMap'):
                texture = _texture(surface, name)
                if texture:
                    _offset(tree, texture, node.outputs[0])

    elif basename.startswith('srf_forerunner_lewis_lights'):
        texture = _texture(surface, 'selfillum_map')
        if texture is None:
            return
        scroll = helper('srf_forerunner_lewis_lights - scroll_vector')
        vector = helper('srf_forerunner_lewis_lights - selfillum_map_vector')
        if scroll is None or vector is None:
            return
        uv = _uv(tree)
        tree.links.new(uv, scroll.inputs['UV']); tree.links.new(uv, vector.inputs['UV'])
        # Alpha is sampled at the original coordinates; only emission is warped.
        alpha = _socket(surface, 'selfillum_map_alpha')
        if alpha is not None:
            original = _duplicate(tree, texture)
            tree.links.new(original.outputs['Alpha'], alpha)
        for index in (1, 2):
            sample = _duplicate(tree, texture)
            # Give auxiliary samples their own address graph before changing UVs.
            from .shader_address import setup_address
            for link in list(sample.inputs['Vector'].links):
                tree.links.remove(link)
            tree.links.new(scroll.outputs[f'UV{index}'], sample.inputs['Vector'])
            setup_address(tree, sample, texture.get('foundry_address_modes', (0, 0)))
            tree.links.new(sample.outputs['Color'], vector.inputs[f'scrolling_map{index}'])
        tree.links.new(vector.outputs[0], _vector_input(texture, before_transform=True))

    elif basename == 'srf_ca_skybox_6texcombine':
        node = helper('srf_ca_skybox_6texcombine texture_vector')
        if node is None:
            return
        controls = helper('srf_ca_skybox_6texcombine UV controls')
        if controls is None:
            return
        tree.links.new(_uv(tree), controls.inputs['UV0'])
        tree.links.new(_uv(tree, 'UVMap1'), controls.inputs['UV1'])
        for index in range(1, 7):
            texture = _texture(surface, f'texture_{index:02}_map')
            if texture is None:
                continue
            # Keep these scalar parameters in a group so export can recover them.
            tree.links.new(controls.outputs[f'UV{index}'], _vector_input(texture, before_transform=True))
            scale = tree.nodes.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'
            tree.links.new(node.outputs[0], scale.inputs[0])
            tree.links.new(controls.outputs[f'warp{(index-1)//2+1}'], scale.inputs['Scale'])
            _offset(tree, texture, scale.outputs['Vector'])

    elif shader == 'special/srf_energy_sword':
        core = _texture(surface, 'color_map')
        node = helper('srf_energy_sword vector [H2AMP]')
        if node is None:
            return
        if core:
            socket, coords = _coordinates(tree, core)
            tree.links.new(coords, node.inputs['color_map_uv'])
            second = _duplicate(tree, core)
            # The second flow phase must not share the first phase's address node.
            for link in list(second.inputs['Vector'].links): tree.links.remove(link)
            tree.links.new(node.outputs['UV1'], second.inputs['Vector'])
            from .shader_address import setup_address
            setup_address(tree, second, core.get('foundry_address_modes', (0, 0)))
            tree.links.new(node.outputs['UV0'], socket)
            mix = tree.nodes.new('ShaderNodeMixRGB')
            # Export the authored color sampler, not a texture in its flow graph.
            mix['foundry_material_texture_input'] = 'Color1'
            tree.links.new(node.outputs['flow_lerp'], mix.inputs[0])
            tree.links.new(core.outputs['Color'], mix.inputs[1]); tree.links.new(second.outputs['Color'], mix.inputs[2])
            tree.links.new(mix.outputs[0], _socket(surface, 'color_map'))
        for name in ('detail', 'fog'):
            texture = _texture(surface, name+'_map')
            if texture:
                _offset(tree, texture, node.outputs[name+'_offset'], before_transform=name=='fog')

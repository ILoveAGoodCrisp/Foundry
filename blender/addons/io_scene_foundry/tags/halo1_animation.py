"""Shared H1 animation calculations; keep arithmetic out of material layouts."""
import bpy

PLASMA_GROUP = '.H1 environment plasma waveform'


def build_plasma_group():
    """env_lm_normal.psh:69-75, using the sampled bitmap alpha unchanged."""
    group = bpy.data.node_groups.get(PLASMA_GROUP)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(PLASMA_GROUP, 'ShaderNodeTree')
    group.use_fake_user = True
    for name, direction in [('Animation', 'INPUT'), ('Map Alpha', 'INPUT'), ('Activation', 'OUTPUT')]:
        group.interface.new_socket(name=name, in_out=direction, socket_type='NodeSocketFloat')
    inputs = group.nodes.new('NodeGroupInput')
    inputs.location = (-220, 0)

    def put(socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            group.links.new(value, socket)
        else:
            socket.default_value = value

    def math(name, operation, a, b, x, y, clamp=False):
        node = group.nodes.new('ShaderNodeMath')
        node.name = node.label = name
        node.operation = operation
        node.use_clamp = clamp
        node.location = (x, y)
        node.width = 170
        put(node.inputs[0], a)
        put(node.inputs[1], b)
        return node.outputs[0]

    animation, alpha = inputs.outputs['Animation'], inputs.outputs['Map Alpha']
    a = math('Animation + 0.5', 'ADD', animation, .5, 0, 0)
    b = math('Nonnegative map alpha', 'MAXIMUM', alpha, 0, 0, -200)
    first = math('Plasma intermediate 1', 'SUBTRACT', a, b, 210, 0)
    a = math('Map alpha + 0.5', 'ADD', alpha, .5, 0, -430)
    b = math('Nonnegative animation', 'MAXIMUM', animation, 0, 0, -630)
    second = math('Plasma intermediate 2', 'SUBTRACT', a, b, 210, -430)
    select = math('First < 0.5', 'LESS_THAN', first, .5, 420, 0)
    mix = group.nodes.new('ShaderNodeMix')
    mix.name = mix.label = 'Choose plasma intermediate'
    mix.data_type = 'FLOAT'
    mix.clamp_factor = False
    mix.location = (630, -130)
    put(mix.inputs[0], select)
    put(mix.inputs[2], second)
    put(mix.inputs[3], first)
    square = math('Square intermediate', 'MULTIPLY', mix.outputs[0], mix.outputs[0], 840, -130)
    scaled = math('Saturate 4 × square', 'MULTIPLY', square, 4, 1050, -130, True)
    fourth = math('Square again', 'MULTIPLY', scaled, scaled, 1260, -130)
    on = math('Pulse above threshold', 'GREATER_THAN', fourth, .5, 1470, -360)
    doubled = math('Double pulse', 'MULTIPLY', fourth, 2, 1470, -130)
    biased = math('Subtract one', 'SUBTRACT', doubled, 1, 1680, -130)
    squared = math('Square pulse', 'MULTIPLY', biased, biased, 1890, -130)
    result = math('Thresholded plasma pulse', 'MULTIPLY', squared, on, 2100, -130)
    output = group.nodes.new('NodeGroupOutput')
    output.location = (2310, -130)
    put(output.inputs['Activation'], result)
    for socket in inputs.outputs:
        socket.hide = not socket.is_linked
    group['h1_source'] = 'HCEEK/shaders/fx/env_lm_normal.psh:69-75'
    return group

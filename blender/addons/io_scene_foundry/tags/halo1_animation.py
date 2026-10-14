"""Shared H1 animation calculations; keep arithmetic out of material layouts."""
import bpy

PLASMA_GROUP = '.H1 environment plasma waveform'
MAP_ANIMATION_GROUP = 'foundry_h1.map_animation'


def build_map_animation_group(animation_group):
    """Tag-space animated offsets for the existing H1 coordinate helpers.

    shaders.c:shader_texture_animation_evaluate rotates scale + translation
    around the authored center. The coordinate helper handles the UV convention;
    this group retains tag-space values (including signed periods) for export.
    """
    group = bpy.data.node_groups.get(MAP_ANIMATION_GROUP)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(MAP_ANIMATION_GROUP, 'ShaderNodeTree')
    group.use_fake_user = True

    def socket(name, kind='NodeSocketFloat', direction='INPUT', parent=None, default=None):
        s = group.interface.new_socket(name=name, in_out=direction, socket_type=kind, parent=parent)
        if default is not None:
            s.default_value = default
        return s

    for axis in ('u', 'v', 'rotation'):
        panel = group.interface.new_panel(axis.upper() if axis != 'rotation' else 'Rotation', default_closed=True)
        socket('map rotation' if axis == 'rotation' else 'map ' + axis + '-offset', parent=panel, default=0)
        socket(axis + ' animation function', 'NodeSocketMenu', parent=panel)
        for suffix in ('period', 'phase', 'scale'):
            s = socket(axis + ' animation ' + suffix, parent=panel, default=0)
            if suffix == 'period':
                s.description = 'Seconds per cycle; negative reverses the cycle; zero means one second'
            elif suffix == 'scale':
                s.description = 'Zero uses the tag default: 360 degrees for rotation, one for U/V'
        if axis == 'rotation':
            for component in ('u', 'v'):
                socket('rotation center ' + component, parent=panel, default=0)
    for name in ('map u-offset', 'map v-offset', 'map rotation'):
        socket(name, direction='OUTPUT')

    def node(kind, name, x, y):
        n = group.nodes.new(kind)
        n.name = n.label = name
        n.location = (x, y)
        n.width = 190
        return n

    def put(s, v):
        if isinstance(v, bpy.types.NodeSocket):
            group.links.new(v, s)
        else:
            s.default_value = v

    def math(name, op, a, b, x, y):
        n = node('ShaderNodeMath', name, x, y)
        n.operation = op
        put(n.inputs[0], a)
        put(n.inputs[1], b)
        return n.outputs[0]

    results = {}
    for i, axis in enumerate(('u', 'v', 'rotation')):
        y = -i * 620
        inputs = node('NodeGroupInput', axis.upper() + ' controls', 0, y)
        wave = node('ShaderNodeGroup', axis.upper() + ' waveform (seconds)', 230, y)
        wave.node_tree = animation_group
        for suffix in ('Function', 'Period', 'Phase'):
            put(wave.inputs['Animation ' + suffix], inputs.outputs[axis + ' animation ' + suffix.lower()])
        wave.inputs['No Random Phase'].default_value = True
        scale = inputs.outputs[axis + ' animation scale']
        zero = math(axis + ' zero scale', 'COMPARE', scale, 0, 230, y - 300)
        zero.node.inputs[2].default_value = 0
        fallback = node('ShaderNodeMix', axis + ' tag scale default', 460, y - 220)
        fallback.data_type = 'FLOAT'
        fallback.clamp_factor = False
        put(fallback.inputs[0], zero)
        put(fallback.inputs[2], scale)
        put(fallback.inputs[3], 360 if axis == 'rotation' else 1)
        delta = math(axis + ' waveform amplitude', 'MULTIPLY', wave.outputs[0], fallback.outputs[0], 700, y)
        local = node('NodeGroupInput', axis.upper() + ' static offset', 700, y - 240)
        port = 'map rotation' if axis == 'rotation' else 'map ' + axis + '-offset'
        results[axis] = math(axis + ' animated value', 'ADD', local.outputs[port], delta, 940, y)

    # R(S*uv + offset - center) + center == R(S*uv + adjusted_offset).
    # Fold R^-1(center)-center into the offset, avoiding extra vector-group ports.
    local = node('NodeGroupInput', 'Rotation center (tag space)', 940, -1730)
    rad = math('Rotation radians', 'RADIANS', results['rotation'], 0, 1170, -1240)
    cosine = math('Center cosine', 'COSINE', rad, 0, 1400, -1240)
    sine = math('Center sine', 'SINE', rad, 0, 1400, -1500)
    cx, cy = local.outputs['rotation center u'], local.outputs['rotation center v']
    cosx = math('Center U cosine', 'MULTIPLY', cx, cosine, 1640, -800)
    siny = math('Center V sine', 'MULTIPLY', cy, sine, 1640, -1000)
    cosy = math('Center V cosine', 'MULTIPLY', cy, cosine, 1640, -1300)
    sinx = math('Center U sine', 'MULTIPLY', cx, sine, 1640, -1500)
    x = math('Inverse rotated center U', 'ADD', cosx, siny, 1870, -800)
    y = math('Inverse rotated center V', 'SUBTRACT', cosy, sinx, 1870, -1300)
    x = math('Center U correction', 'SUBTRACT', x, cx, 2100, -800)
    y = math('Center V correction', 'SUBTRACT', y, cy, 2100, -1300)
    u = math('Final tag U offset', 'ADD', results['u'], x, 2330, 0)
    v = math('Final tag V offset', 'ADD', results['v'], y, 2330, -620)
    output = node('NodeGroupOutput', 'Animated map transform', 2580, 0)
    for name, value in [('map u-offset', u), ('map v-offset', v), ('map rotation', results['rotation'])]:
        put(output.inputs[name], value)
    for n in group.nodes:
        if n.type == 'GROUP_INPUT':
            for s in n.outputs:
                s.hide = not s.is_linked
    return group


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
    return group

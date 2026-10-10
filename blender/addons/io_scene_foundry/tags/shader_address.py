"""Halo sampler addressing with independent U/V axes for Blender textures."""
import bpy

NAMES = ('Wrap', 'Clamp', 'Mirror', 'Black Border', 'Mirror Once', 'Mirror Once Border')


def read_address_modes(element, default=0):
    """Address flags gate fields; per-axis overrides win over the common one."""
    defaults = tuple(default) if isinstance(default, (tuple, list)) else (default, default)
    if element is None:
        return defaults
    flags = element.SelectField('bitmap flags')
    bits = int(flags.Data) if flags is not None else 0
    common = element.SelectField('bitmap address mode')
    bases = (int(common.Data),) * 2 if bits & 2 and common is not None else defaults
    result = []
    for index, (axis, bit) in enumerate([('x', 4), ('y', 8)]):
        field = element.SelectField('bitmap address mode ' + axis)
        result.append(int(field.Data) if bits & bit and field is not None else bases[index])
    return tuple(result)


def address_group(modes):
    name = 'Texture Address - ' + ' / '.join(NAMES[i] for i in modes)
    group = bpy.data.node_groups.get(name)
    if group is not None:
        return group
    group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    group.interface.new_socket('Vector', in_out='INPUT', socket_type='NodeSocketVector')
    group.interface.new_socket('Vector', in_out='OUTPUT', socket_type='NodeSocketVector')
    group['foundry_address_modes'] = list(modes)
    source = group.nodes.new('NodeGroupInput'); source.location = (-600, 80)
    split = group.nodes.new('ShaderNodeSeparateXYZ'); split.location = (-400, 80)
    group.links.new(source.outputs['Vector'], split.inputs[0])
    combine = group.nodes.new('ShaderNodeCombineXYZ'); combine.location = (300, 80)
    output = group.nodes.new('NodeGroupOutput'); output.location = (510, 80)
    group.links.new(combine.outputs[0], output.inputs[0])
    for axis, mode in enumerate(modes):
        socket = split.outputs[axis]
        def math(operation, value=None, x=-160):
            nonlocal socket
            node = group.nodes.new('ShaderNodeMath'); node.operation = operation
            node.location = (x, 140 - axis * 250); node.width = 150
            group.links.new(socket, node.inputs[0])
            if value is not None:node.inputs[1].default_value = value
            socket = node.outputs[0]
        if mode == 0:math('FRACT')
        elif mode == 2:math('PINGPONG', 1.0)
        elif mode in {4, 5}:math('ABSOLUTE')
        if mode in {1, 4}:
            clamp = group.nodes.new('ShaderNodeClamp'); clamp.location = (40, 140-axis*250)
            group.links.new(socket, clamp.inputs[0]); socket = clamp.outputs[0]
        # Border axes remain outside [0,1] for the texture's CLIP sampler.
        group.links.new(socket, combine.inputs[axis])
    group.links.new(split.outputs[2], combine.inputs[2])
    for socket in source.outputs:socket.hide = not socket.is_linked
    return group


def setup_address(tree, texture, modes):
    """Insert after authored mapping; leave the RGB/alpha and mapping intact."""
    if isinstance(modes, str):  # Third-party/older callers of group_set_image.
        texture.extension = modes
        return
    texture['foundry_address_modes'] = list(modes)
    vector = texture.inputs['Vector']
    if vector.is_linked:
        old = vector.links[0].from_node
        if old.type == 'GROUP' and old.node_tree and tuple(old.node_tree.get('foundry_address_modes', ())) == tuple(modes):
            return
    if modes[0] == modes[1] and modes[0] in {0, 1, 2, 3}:
        texture.extension = {0:'REPEAT', 1:'EXTEND', 2:'MIRROR', 3:'CLIP'}[modes[0]]
        return
    texture.extension = 'CLIP' if any(i in {3, 5} for i in modes) else 'EXTEND'
    address = tree.nodes.new('ShaderNodeGroup'); address.node_tree = address_group(modes)
    address.label = 'U: ' + NAMES[modes[0]] + ' • V: ' + NAMES[modes[1]]
    address.location = (texture.location.x - 240, texture.location.y)
    if vector.is_linked:
        tree.links.new(vector.links[0].from_socket, address.inputs['Vector'])
    else:
        uv = tree.nodes.new('ShaderNodeTexCoord'); uv.location = (address.location.x - 220, address.location.y)
        tree.links.new(uv.outputs['UV'], address.inputs['Vector'])
    tree.links.new(address.outputs['Vector'], vector)


def finalize_addresses(tree):
    # Dependent samplers replace their coordinates during import. Apply address
    # handling last, including copies inside closure zones and layered effects.
    for node in list(tree.nodes):
        if node.type == 'TEX_IMAGE' and 'foundry_address_modes' in node:
            setup_address(tree, node, tuple(node['foundry_address_modes']))

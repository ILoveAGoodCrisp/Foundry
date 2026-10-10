"""Preview for H2's emissive detail template, including weapon counters."""
import bpy


def illum_detail_group():
    name = 'foundry_h2.illum_detail'
    tree = bpy.data.node_groups.get(name)
    if tree is not None:
        return tree
    tree = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for label, kind, default in (
        ('self_illum_map.rgb', 'NodeSocketColor', (1, 1, 1, 1)),
        ('detail_map.rgb', 'NodeSocketColor', (.5, .5, .5, 1)),
        ('self_illum_color', 'NodeSocketColor', (1, 1, 1, 1)),
        ('self_illum_brightness', 'NodeSocketFloat', 1.0),
    ):
        socket = tree.interface.new_socket(name=label, in_out='INPUT', socket_type=kind)
        socket.default_value = default
    tree.interface.new_socket(name='Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    inputs = tree.nodes.new('NodeGroupInput')
    inputs.location = (-600, 0)
    detail = tree.nodes.new('ShaderNodeMixRGB')
    detail.blend_type = 'MULTIPLY'
    detail.inputs[0].default_value = 1.0
    detail.location = (-400, 100)
    tree.links.new(inputs.outputs['self_illum_map.rgb'], detail.inputs[1])
    tree.links.new(inputs.outputs['detail_map.rgb'], detail.inputs[2])
    tint = tree.nodes.new('ShaderNodeMixRGB')
    tint.blend_type = 'MULTIPLY'
    tint.inputs[0].default_value = 1.0
    tint.location = (-200, 100)
    tree.links.new(detail.outputs[0], tint.inputs[1])
    tree.links.new(inputs.outputs['self_illum_color'], tint.inputs[2])
    brightness = tree.nodes.new('ShaderNodeMath')
    brightness.operation = 'MULTIPLY'
    brightness.inputs[1].default_value = 2.0
    brightness.location = (-200, -150)
    tree.links.new(inputs.outputs['self_illum_brightness'], brightness.inputs[0])
    emission = tree.nodes.new('ShaderNodeEmission')
    emission.location = (0, 100)
    tree.links.new(tint.outputs[0], emission.inputs['Color'])
    tree.links.new(brightness.outputs[0], emission.inputs['Strength'])
    output = tree.nodes.new('NodeGroupOutput')
    output.location = (200, 100)
    tree.links.new(emission.outputs[0], output.inputs['Shader'])
    return tree

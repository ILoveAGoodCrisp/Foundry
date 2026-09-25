"""Add optional H1 area softening to shared_nodes.blend (run with Blender).

H1 Triangle Area must be in squared Blender coordinate units, matching Ray
Length. Zero disables the approximation. Authored positive cutoffs retain
the original attenuation graph. This does not implement the H1 radiosity bake.
"""
import math
from pathlib import Path

import bpy


PATH = Path(__file__).resolve().parents[1] / 'blender/addons/io_scene_foundry/blends/shared_nodes.blend'
bpy.ops.wm.open_mainfile(filepath=str(PATH))
attenuation = bpy.data.node_groups['Attenuation']
emissive = bpy.data.node_groups['Halo Light Emissive']
wrapper = bpy.data.node_groups['Halo Emissive']
assert 'H1 Triangle Area' not in attenuation.nodes, 'Already updated'


def area_socket(tree):
    socket = tree.interface.new_socket(name='H1 Triangle Area', in_out='INPUT', socket_type='NodeSocketFloat')
    socket.default_value = 0.0
    socket.min_value = 0.0
    socket.description = ('Optional H1 softening approximation: original emitting triangle area in squared '
                          'Blender coordinate units. Zero disables it; positive Cutoff overrides it.')


def math_node(tree, name, operation, location, value=None):
    node = tree.nodes.new('ShaderNodeMath')
    node.name = node.label = name
    node.operation = operation
    node.location = location
    if value is not None:
        node.inputs[1].default_value = value
    return node


# Capture the authored branch so edits cannot silently disconnect it.
mix = attenuation.nodes['Mix']
assert mix.data_type == 'FLOAT'
original_custom = mix.inputs[3].links[0].from_socket
original_custom_name = original_custom.node.name
original_strength = mix.inputs[2].links[0].from_socket
original_factor = mix.inputs[0].links[0].from_socket
assert original_factor.node.operation == 'GREATER_THAN'
assert original_factor.node.inputs[1].default_value == 0.0

for tree in (attenuation, emissive, wrapper):
    area_socket(tree)

inputs = attenuation.nodes.new('NodeGroupInput')
inputs.name = 'H1 Triangle Area'
inputs.location = (-1000, -650)
distance = attenuation.nodes['Light Path'].outputs['Ray Length']
links = attenuation.links

square = math_node(attenuation, 'H1 Distance Squared', 'MULTIPLY', (-800, -400))
links.new(distance, square.inputs[0])
links.new(distance, square.inputs[1])
pi_distance = math_node(attenuation, 'H1 Pi Distance Squared', 'MULTIPLY', (-600, -400), math.pi)
links.new(square.outputs[0], pi_distance.inputs[0])
area = math_node(attenuation, 'H1 Sample Area', 'DIVIDE', (-800, -650), 3.0)
links.new(inputs.outputs['H1 Triangle Area'], area.inputs[0])
denominator = math_node(attenuation, 'H1 Softened Denominator', 'ADD', (-400, -550))
links.new(pi_distance.outputs[0], denominator.inputs[0])
links.new(area.outputs[0], denominator.inputs[1])
ratio = math_node(attenuation, 'H1 Softening Ratio', 'DIVIDE', (-200, -400))
links.new(pi_distance.outputs[0], ratio.inputs[0])
links.new(denominator.outputs[0], ratio.inputs[1])
enabled = math_node(attenuation, 'H1 Area Enabled', 'GREATER_THAN', (-400, -800), 0.0)
links.new(inputs.outputs['H1 Triangle Area'], enabled.inputs[0])
correction = attenuation.nodes.new('ShaderNodeMix')
correction.name = correction.label = 'H1 Optional Softening'
correction.data_type = 'FLOAT'
correction.location = (0, -600)
correction.inputs[2].default_value = 1.0
links.new(enabled.outputs[0], correction.inputs[0])
links.new(ratio.outputs[0], correction.inputs[3])
strength = math_node(attenuation, 'H1 Natural Strength', 'MULTIPLY', (220, -400))
links.new(original_strength, strength.inputs[0])
links.new(correction.outputs[0], strength.inputs[1])
links.new(strength.outputs[0], mix.inputs[2])

# Append sockets rather than changing any existing socket indices/identifiers.
for tree, target in ((emissive, emissive.nodes['Attenuation']),
                     (wrapper, wrapper.nodes['Group.012'])):
    source = tree.nodes.new('NodeGroupInput')
    source.name = source.label = 'H1 Triangle Area'
    source.location = (target.location.x - 220, target.location.y - 250)
    tree.links.new(source.outputs['H1 Triangle Area'], target.inputs['H1 Triangle Area'])

assert mix.inputs[3].links[0].from_socket == original_custom
assert mix.inputs[0].links[0].from_socket == original_factor
assert bpy.data.node_groups['Halo Light'].nodes['Attenuation'].inputs['H1 Triangle Area'].default_value == 0

# Numerically evaluate the added math and mix graph at representative distances.
def evaluate(socket, distance_value, area_value):
    node = socket.node
    if node.bl_idname == 'NodeGroupInput':
        return {'H1 Triangle Area': area_value, 'Strength': 4.5}[socket.name]
    if node.bl_idname == 'ShaderNodeLightPath':
        return distance_value
    def value(index):
        inp = node.inputs[index]
        return evaluate(inp.links[0].from_socket, distance_value, area_value) if inp.is_linked else inp.default_value
    if node.bl_idname == 'NodeReroute':
        return value(0)
    if node.bl_idname == 'ShaderNodeMix':
        factor = value(0)
        return (1 - factor) * value(2) + factor * value(3)
    a, b = value(0), value(1)
    return {'MULTIPLY': lambda: a * b, 'ADD': lambda: a + b,
            'DIVIDE': lambda: a / b if b else 0.0,
            'GREATER_THAN': lambda: float(a > b)}[node.operation]()

for d in (0.0, 0.01, 1.0, 100.0):
    for a in (0.0, 0.03, 3.0):
        expected = 4.5 if a == 0 else 4.5 * math.pi * d*d / (math.pi*d*d + a/3)
        actual = evaluate(strength.outputs[0], d, a)
        assert math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-8), (d, a, actual, expected)

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(PATH))
bpy.ops.wm.open_mainfile(filepath=str(PATH))
assert bpy.data.node_groups['Attenuation'].nodes['Mix'].inputs[3].links[0].from_node.name == original_custom_name
print('Verified H1 softening math, unchanged custom branch, default-off light behavior, and saved/reopened asset.')

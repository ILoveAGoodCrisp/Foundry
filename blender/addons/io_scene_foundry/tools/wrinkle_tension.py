"""Live wrinkle preview for H4/H2AMP materials.

New material/PCA imports set this up automatically. For an existing scene use
Set Up Wrinkle Tension (F3 or Foundry mesh properties); re-import its PCA clips
to recover authored channels that older imports discarded. The modifier's
Force Geometry Tension checkbox compares calculated strain with authored PCA.
Strength affects either preview; Geometry Gain defaults to the export gain 3.

Spreadsheet point attributes retain both authored and calculated channels, plus
foundry_wrinkle_using_authored (1 when the authored basis matches the geometry).
The modifier is placed before armature and subdivision so only shape-key/local
deformation contributes. Signed authored values are not clamped. Scalar/vector
attributes deliberately avoid export color slots; export still computes tension
from its own evaluated reference geometry, independently of preview controls.
"""
import hashlib
from pathlib import Path

import bpy
import numpy as np


GROUP_NAME = 'Foundry Wrinkle Tension'
COMPRESSION = 'foundry_wrinkle_compression'
STRETCH = 'foundry_wrinkle_stretch'
GEOMETRY_COMPRESSION = 'foundry_geometry_compression'
GEOMETRY_STRETCH = 'foundry_geometry_stretch'
AUTHORED_COMPRESSION = 'foundry_authored_compression'
AUTHORED_STRETCH = 'foundry_authored_stretch'
USING_AUTHORED = 'foundry_wrinkle_using_authored'
WRINKLE_SHADERS = frozenset({
    'xsrf_cortana_placeholder_pca', 'xsrf_pca', 'srf_char_skin_tension',
    'srf_char_skin_tension_detailnormal', 'srf_char_skin_tension_detailnormal_generic',
})


def node(tree, kind, label, **properties):
    result = tree.nodes.new(kind)
    result.label = label
    for name, value in properties.items():
        setattr(result, name, value)
    return result


def math_node(tree, operation, *values, label=''):
    result = node(tree, 'ShaderNodeMath', label, operation=operation)
    for socket, value in zip(result.inputs, values):
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return result.outputs[0]


def named_attribute(tree, name, data_type='FLOAT'):
    result = node(tree, 'GeometryNodeInputNamedAttribute', name, data_type=data_type)
    result.inputs['Name'].default_value = name
    return result


def interface(tree):
    tree.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    socket = tree.interface.new_socket(name='Force Geometry Tension', in_out='INPUT', socket_type='NodeSocketBool')
    socket.description = 'Debug: always calculate tension from deformation, even when authored PCA tension is available'
    socket = tree.interface.new_socket(name='Strength', in_out='INPUT', socket_type='NodeSocketFloat')
    socket.default_value = 1
    socket.min_value = 0
    socket.description = 'Preview wrinkle strength; does not change exported PCA tension'
    socket = tree.interface.new_socket(name='Geometry Gain', in_out='INPUT', socket_type='NodeSocketFloat')
    socket.default_value = 3
    socket.min_value = 0
    socket.description = 'Gain for calculated tension; 3 matches Foundry PCA export'


def library_group():
    for group in bpy.data.node_groups:
        if group.get('foundry_wrinkle_calculator') == 1:
            return group
    path = Path(__file__).resolve().parents[1] / 'blends/geometry_nodes.blend'
    with bpy.data.libraries.load(str(path), link=False) as (source, target):
        if GROUP_NAME not in source.node_groups:
            raise RuntimeError(f'{GROUP_NAME} is missing from {path}')
        target.node_groups = [GROUP_NAME]
    return target.node_groups[0]


def wrinkle_modifier(ob):
    return next((m for m in ob.modifiers if m.type == 'NODES' and m.node_group
                 and m.node_group.get('foundry_wrinkle_preview')), None)


def ensure_wrinkle_modifier(ob):
    """Run after shape keys, before armature/subdivision, without changing topology."""
    modifier = wrinkle_modifier(ob)
    if modifier is not None:
        return modifier
    calculation = library_group()
    tree = bpy.data.node_groups.new(f'{GROUP_NAME} — {ob.name}', 'GeometryNodeTree')
    tree['foundry_wrinkle_preview'] = 1
    tree.is_modifier = True
    interface(tree)
    source = node(tree, 'NodeGroupInput', 'Preview controls')
    destination = node(tree, 'NodeGroupOutput', 'Wrinkle attributes')
    calc = node(tree, 'GeometryNodeGroup', 'Authored PCA or calculated tension', node_tree=calculation)
    calc.name = 'Tension calculation'
    for socket in source.outputs:
        if socket.name in calc.inputs:
            tree.links.new(socket, calc.inputs[socket.name])
    tree.links.new(calc.outputs['Geometry'], destination.inputs['Geometry'])
    source.location = (-600, 400)
    calc.location = (200, 400)
    destination.location = (500, 400)
    modifier = ob.modifiers.new('Foundry Wrinkle Tension', 'NODES')
    modifier.node_group = tree
    ob.modifiers.move(len(ob.modifiers) - 1, 0)
    ob.add_rest_position_attribute = True
    return modifier


def _vector_attribute(mesh, name, values):
    attribute = mesh.attributes.get(name)
    if attribute is None:
        attribute = mesh.attributes.new(name, 'FLOAT_VECTOR', 'POINT')
    if attribute.domain != 'POINT' or attribute.data_type != 'FLOAT_VECTOR':
        raise ValueError(f'Incompatible PCA preview attribute: {name}')
    attribute.data.foreach_set('vector', np.asarray(values, dtype=np.float32).ravel())


def _add_vector(tree, first, second, label):
    result = node(tree, 'ShaderNodeVectorMath', label, operation='ADD')
    tree.links.new(first, result.inputs[0])
    tree.links.new(second, result.inputs[1])
    return result.outputs['Vector']


def install_pca_tension(ob, keys, tension, deltas):
    """Keep signed RGB basis data and weight it with the actual animated Key values.

    Raw PCA vertices already contain the unquantized basis; buffer scale/offset
    fields apply to packed runtime buffers, not these raw colors. No gamma or
    clamping is appropriate here (the basis has large negative values).
    """
    tension = np.asarray(tension, dtype=np.float32)
    deltas = np.asarray(deltas, dtype=np.float32)
    expected = (len(keys), len(ob.data.vertices), 3)
    if tension.shape != expected or deltas.shape != expected or not np.isfinite(tension).all() or not np.isfinite(deltas).all():
        raise ValueError('PCA wrinkle basis does not match the shape keys')
    modifier = ensure_wrinkle_modifier(ob)
    tree = modifier.node_group
    calc = tree.nodes['Tension calculation']
    # Each shape owns two persistent point attributes. Re-importing another clip
    # in the same PCA group reuses its basis and drivers instead of summing twice.
    for key, colors, positions in zip(keys, tension, deltas):
        path = key.path_from_id('value')
        existing = next((n for n in tree.nodes if n.get('foundry_pca_weight') and
                         n.outputs[0].is_linked and tree.animation_data and any(
                             fc.data_path == n.outputs[0].path_from_id('default_value') and
                             fc.driver.variables[0].targets[0].data_path == path
                             for fc in tree.animation_data.drivers)), None)
        if existing is not None:
            _vector_attribute(ob.data, existing['foundry_pca_tension'], colors)
            _vector_attribute(ob.data, existing['foundry_pca_delta'], positions)
            continue
        token = hashlib.sha1(path.encode()).hexdigest()[:16]
        tension_name = f'foundry_pca_{token}_tension'
        delta_name = f'foundry_pca_{token}_delta'
        _vector_attribute(ob.data, tension_name, colors)
        _vector_attribute(ob.data, delta_name, positions)
        frame = node(tree, 'NodeFrame', key.name)
        frame.location = (-1400, -350 * sum(bool(n.get('foundry_pca_weight')) for n in tree.nodes))
        value = node(tree, 'ShaderNodeValue', key.name)
        value['foundry_pca_weight'] = True
        value['foundry_pca_tension'] = tension_name
        value['foundry_pca_delta'] = delta_name
        driver = value.outputs[0].driver_add('default_value').driver
        for name, data_path in (('weight', path), ('muted', key.path_from_id('mute'))):
            var = driver.variables.new()
            var.name = name
            var.type = 'SINGLE_PROP'
            var.targets[0].id_type = 'KEY'
            var.targets[0].id = ob.data.shape_keys
            var.targets[0].data_path = data_path
        driver.expression = 'weight * (1 - muted)'
        value.parent = frame
        value.location = (0, 0)
        for index, (name, input_name) in enumerate(((tension_name, 'Authored Tension'), (delta_name, 'Authored Delta'))):
            attr = named_attribute(tree, name, 'FLOAT_VECTOR')
            weighted = node(tree, 'ShaderNodeVectorMath', 'Signed PCA contribution', operation='SCALE')
            tree.links.new(attr.outputs['Attribute'], weighted.inputs[0])
            tree.links.new(value.outputs[0], weighted.inputs['Scale'])
            socket = calc.inputs[input_name]
            result = weighted.outputs['Vector']
            if socket.is_linked:
                result = _add_vector(tree, socket.links[0].from_socket, result, 'Sum PCA basis')
            tree.links.new(result, socket)
            available = calc.inputs['Authored Available']
            exists = attr.outputs['Exists']
            if available.is_linked:
                exists = math_node(tree, 'MULTIPLY', available.links[0].from_socket, exists, label='All PCA attributes present')
            tree.links.new(exists, available)
            attr.parent = weighted.parent = frame
            attr.location = (0, -150 - index * 150)
            weighted.location = (250, -150 - index * 150)
    ob.data.update()
    ob.update_tag()
    return modifier


def shader_name(group):
    return group.get('foundry_material_shader', group.get('foundry_resource_name', group.name)).replace('\\', '/').rsplit('/', 1)[-1].split('.')[0]


def patch_material_group(group):
    """Adapt only known wrinkle consumers; leave regular painted colors intact."""
    name = shader_name(group)
    if name not in WRINKLE_SHADERS or group.get('foundry_wrinkle_attributes'):
        return False
    colors = [n for n in group.nodes if n.type == 'VERTEX_COLOR' and n.layer_name in {'', 'tension'}]
    if not colors:
        return False
    compression = node(group, 'ShaderNodeAttribute', 'Facial compression (neutral when absent)')
    compression.attribute_name = COMPRESSION
    stretch = node(group, 'ShaderNodeAttribute', 'Facial stretch (neutral when absent)')
    stretch.attribute_name = STRETCH
    # Cortana/skin implement 1-red in the source. xsrf_pca expects a direct
    # wrinkle weight instead. Keep that convention local to the consumer.
    red = compression.outputs['Fac']
    direct = name == 'xsrf_pca' or not group.get('foundry_source_compiled')
    if not direct:
        red = math_node(group, 'SUBTRACT', 1, red, label='Engine compression channel: 1 - tension')
    combine = node(group, 'ShaderNodeCombineXYZ', 'PCA deformation channels')
    group.links.new(red, combine.inputs['X'])
    # The older hand-built skin groups consume raw tension RGB directly.
    combine.inputs['Y'].default_value = 0 if direct else 1
    blue = math_node(group, 'SUBTRACT', 1, stretch.outputs['Fac'], label='Engine stretch channel') if not direct else stretch.outputs['Fac']
    group.links.new(blue, combine.inputs['Z'])
    for color in colors:
        for link in list(color.outputs['Color'].links):
            group.links.new(combine.outputs[0], link.to_socket)
        # Do not replace unrelated alpha consumers.
        if not any(output.is_linked for output in color.outputs):
            group.nodes.remove(color)
    compression.location = (-900, 400)
    stretch.location = (-900, 150)
    combine.location = (-450, 400)
    group['foundry_wrinkle_attributes'] = 1
    return True


def setup_object_wrinkles(ob):
    """Also upgrades existing local material instances when explicitly requested."""
    if ob.type != 'MESH':
        return False
    found = False
    seen = set()

    def visit(tree):
        nonlocal found
        if tree in seen:
            return
        seen.add(tree)
        for n in tree.nodes:
            if n.type != 'GROUP' or n.node_tree is None:
                continue
            if shader_name(n.node_tree) in WRINKLE_SHADERS:
                found = True
                if not n.node_tree.get('foundry_wrinkle_attributes'):
                    n.node_tree = n.node_tree.copy()
                    patch_material_group(n.node_tree)
            else:
                visit(n.node_tree)

    for slot in ob.material_slots:
        if slot.material and slot.material.node_tree:
            visit(slot.material.node_tree)
    if found:
        ensure_wrinkle_modifier(ob)
    return found


def setup_material_users(material):
    """Material-only rebuilds on existing meshes also need the geometry modifier."""
    if material.node_tree is None:
        return
    # At import time the material may have no object users yet; setup_materials
    # performs a second pass once imported meshes and reused materials are ready.
    if not any(n.type == 'GROUP' and n.node_tree and shader_name(n.node_tree) in WRINKLE_SHADERS
               for n in material.node_tree.nodes):
        return
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and any(slot.material == material for slot in ob.material_slots):
            setup_object_wrinkles(ob)


class NWO_OT_SetupWrinkleTension(bpy.types.Operator):
    bl_idname = 'nwo.setup_wrinkle_tension'
    bl_label = 'Set Up Wrinkle Tension'
    bl_description = 'Drive facial wrinkles from authored PCA or shape-key deformation; comparison controls are in the modifier'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(ob.type == 'MESH' for ob in context.selected_objects)

    def execute(self, context):
        count = 0
        for ob in context.selected_objects:
            if ob.type == 'MESH':
                setup_object_wrinkles(ob)
                ensure_wrinkle_modifier(ob)
                count += 1
        self.report({'INFO'}, f'Wrinkle preview ready on {count} meshes. Compare with Force Geometry Tension in the modifier')
        return {'FINISHED'}

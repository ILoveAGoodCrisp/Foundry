"""Dependent texture sampling for specialized H3 material groups."""
import math
import bpy
from .. import utils


def _copy_input(tree, source, destination):
    destination.default_value = source.default_value
    if source.is_linked:
        tree.links.new(source.links[0].from_socket, destination)


def _math(tree, operation, a, b, label):
    node = tree.nodes.new('ShaderNodeMath')
    node.operation = operation
    node.label = label
    for socket, value in zip(node.inputs, (a, b)):
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return node.outputs[0]


def _value(socket):
    return socket.links[0].from_socket if socket.is_linked else socket.default_value


def setup_cortana(shader, tree, root):
    """cortana.fx detail parallax and resolution-normalized screen scanlines.

    The layer count determines texture-node count, so changes require reimport.
    Keep the unshifted source texture for ordinary bitmap/UV-transform export.
    """
    scan = root.inputs.get('scanline_map.rgb')
    if scan and scan.is_linked and scan.links[0].from_node.type == 'TEX_IMAGE':
        texture = scan.links[0].from_node
        coordinates = tree.nodes.new('ShaderNodeTexCoord')
        coordinates.label = 'Cortana screen scanlines'
        separate = tree.nodes.new('ShaderNodeSeparateXYZ')
        tree.links.new(coordinates.outputs['Window'], separate.inputs[0])
        render = bpy.context.scene.render
        aspect = render.resolution_x * render.pixel_aspect_x / max(1, render.resolution_y * render.pixel_aspect_y)
        # ODST's DX11 source divides fragment_position by 1.5; H3 additionally
        # normalizes by render height / 720. Capture actual pixels at import.
        odst = getattr(shader, 'game', 'halo3') == 'halo3odst'
        scan_y = render.resolution_y * render.resolution_percentage / 100 / 1.5 if odst else 480
        scan_x = render.resolution_x * render.resolution_percentage / 100 / 1.5 if odst else 480 * aspect
        vector = tree.nodes.new('ShaderNodeCombineXYZ')
        tree.links.new(_math(tree, 'MULTIPLY', separate.outputs['X'], scan_x, 'Scanline pixel width'), vector.inputs['X'])
        tree.links.new(_math(tree, 'MULTIPLY', _math(tree, 'SUBTRACT', 1, separate.outputs['Y'], 'Screen origin at top'), scan_y, 'Scanline pixel height'), vector.inputs['Y'])
        destination = texture.inputs['Vector']
        if destination.is_linked:
            mapping = destination.links[0].from_node
            if mapping.type == 'GROUP' and mapping.inputs.get('Vector'):
                destination = mapping.inputs['Vector']
        tree.links.new(vector.outputs[0], destination)

    socket = root.inputs.get('detail_map.rgb')
    if not socket or not socket.is_linked:
        return
    texture = socket.links[0].from_node
    if texture.type != 'TEX_IMAGE':
        return
    count_socket = root.inputs['layer_count']
    requested = count_socket.default_value
    count = min(32, max(1, math.ceil(requested)))
    if requested > 32 or count_socket.is_linked:
        utils.print_warning('H3 Cortana detail uses up to 32 fixed preview layers. Reimport after changing layer_count; animated layer counts are not sampled dynamically.')
    root['h3_cortana_detail_texture'] = texture.name
    texture['h3_cortana_source_detail'] = True
    mapping = texture.inputs['Vector'].links[0].from_node if texture.inputs['Vector'].is_linked else None
    if not texture.inputs['Vector'].is_linked:
        coordinates = tree.nodes.new('ShaderNodeTexCoord')
        tree.links.new(coordinates.outputs['UV'], texture.inputs['Vector'])
    vector = texture.inputs['Vector'].links[0].from_socket
    scale = tree.nodes.new('ShaderNodeCombineXYZ')
    scale.label = 'Detail map transform scale for parallax'
    for axis in ('X', 'Y'):
        if mapping and mapping.type == 'GROUP' and mapping.inputs.get('Scale '+axis):
            value = _math(tree, 'MULTIPLY', _value(mapping.inputs['Scale '+axis]), _value(mapping.inputs['Scale Multiplier']), 'Detail scale '+axis)
            tree.links.new(value, scale.inputs[axis])
        else:
            scale.inputs[axis].default_value = 1
    rgb, alpha = None, None
    for index in range(count):
        sample = texture
        if index:
            sample = tree.nodes.new('ShaderNodeTexImage')
            if 'foundry_address_modes' in texture:
                sample['foundry_address_modes'] = list(texture['foundry_address_modes'])
            sample.image = texture.image
            sample.interpolation = texture.interpolation
            sample.extension = texture.extension
            sample.projection = texture.projection
            # Preserve image sequences and their frame driver for all samples.
            for key in ('frame_duration', 'frame_start', 'frame_offset', 'use_auto_refresh', 'use_cyclic'):
                setattr(sample.image_user, key, getattr(texture.image_user, key))
            animation = tree.animation_data
            if animation:
                path = texture.image_user.path_from_id('frame_offset')
                driver = next((f for f in animation.drivers if f.data_path == path), None)
                if driver:
                    clone = sample.image_user.driver_add('frame_offset').driver
                    clone.type = 'SCRIPTED'
                    variable = clone.variables.new()
                    variable.name = 'offset'
                    variable.type = 'SINGLE_PROP'
                    variable.targets[0].id_type = 'NODETREE'
                    variable.targets[0].id = tree
                    variable.targets[0].data_path = path
                    clone.expression = 'offset'
            sample.label = 'Cortana detail layer '+str(index)
            helper = shader._add_group_node(tree, tree.nodes, '.H3 Cortana layer vector')
            if helper.node_tree is None:
                raise RuntimeError('Missing H3 Cortana layer vector resource')
            helper.inputs['Layer'].default_value = index
            for key in ('layer_depth', 'layer_count', 'texcoord_aspect_ratio'):
                _copy_input(tree, root.inputs[key], helper.inputs[key])
            tree.links.new(vector, helper.inputs['Vector'])
            tree.links.new(scale.outputs[0], helper.inputs['Scale'])
            tree.links.new(helper.outputs[0], sample.inputs['Vector'])
        weight = _math(tree, 'DIVIDE', _math(tree, 'POWER', _value(root.inputs['depth_darken']), index, 'Layer depth attenuation'), max(1, requested), 'Source layer average')
        color = tree.nodes.new('ShaderNodeVectorMath')
        color.operation = 'SCALE'
        tree.links.new(sample.outputs['Color'], color.inputs[0])
        tree.links.new(weight, color.inputs[3])
        a = _math(tree, 'MULTIPLY', sample.outputs['Alpha'], weight, 'Layer alpha')
        if rgb is None:
            rgb, alpha = color.outputs[0], a
        else:
            add = tree.nodes.new('ShaderNodeVectorMath')
            add.operation = 'ADD'
            tree.links.new(rgb, add.inputs[0])
            tree.links.new(color.outputs[0], add.inputs[1])
            rgb = add.outputs[0]
            alpha = _math(tree, 'ADD', alpha, a, 'Accumulated layer alpha')
    tree.links.new(rgb, root.inputs['detail_map.rgb'])
    tree.links.new(alpha, root.inputs['detail_map.a'])


def source_detail_texture(root):
    """Return the original bitmap without mistaking a parallax sample for it."""
    name = root.get('h3_cortana_detail_texture')
    if not name:
        return None
    # Restrict the fallback to images actually upstream of this group.
    pending = [root.inputs['detail_map.rgb'].links[0].from_node] if root.inputs['detail_map.rgb'].is_linked else []
    visited = set()
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        visited.add(node)
        if node.type == 'TEX_IMAGE' and node.get('h3_cortana_source_detail'):
            return node
        pending.extend(link.from_node for socket in node.inputs for link in socket.links)
    return None

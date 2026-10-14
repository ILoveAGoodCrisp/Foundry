"""Transfer authored samples between matching H4/H2AMP source templates.

The destination keeps its own shader implementation. Only texture samples and
their coordinate branches are copied into a private destination instance.
"""
from collections import defaultdict
import json

from ..material_shader_library import parameter_key


def _samples(tree):
    samples = defaultdict(list)
    for node in tree.nodes:
        name = node.get('foundry_material_parameter')
        if name and not node.get('foundry_preview_only') and node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'}:
            key = (parameter_key(name), node.type, bool(node.get('foundry_source_alpha')),
                   bool(node.get('foundry_source_gamma')))
            samples[key].append(node)
    return samples


def _material_files(tree):
    return {path.replace('\\', '/').casefold(): digest
            for path, digest in json.loads(tree.get('foundry_source_files', '{}')).items()
            if path.replace('\\', '/').casefold().startswith('materials/')}


def copy_source_samples(source, target, created_groups):
    """Reject incompatible sampling instead of silently dropping bitmap data."""
    original = source.node_tree
    destination = target.node_tree
    files = _material_files(original)
    if not files or files != _material_files(destination):
        raise ValueError('Source-built shader implementations differ; an explicit material mapping is required')

    def parameters(tree):
        return {parameter_key(name): value['kind']
                for name, value in json.loads(tree.get('foundry_source_parameters', '{}')).items()
                if not value.get('preview_only')}

    samples = _samples(original)
    if (parameters(original) != parameters(destination)
            or {key: len(value) for key, value in samples.items()}
            != {key: len(value) for key, value in _samples(destination).items()}):
        raise ValueError('Source-built shader parameters or texture samples differ')
    animation = original.animation_data
    if animation and (animation.action or animation.drivers or animation.nla_tracks):
        raise ValueError('Animated internal texture sampling requires an explicit target-game mapping')

    destination = destination.copy()
    created_groups.append(destination)
    destination['foundry_source_instance'] = True
    destination.use_fake_user = False
    target.node_tree = destination
    target_samples = _samples(destination)
    original_transforms = [n for n in destination.nodes if n.get('foundry_material_transform')]
    copied = {}
    copied_transforms = set()

    def copy_input(source_socket, target_socket):
        for link in list(target_socket.links):
            destination.links.remove(link)
        if source_socket.is_linked:
            destination.links.new(copy_output(source_socket.links[0].from_socket), target_socket)
        elif hasattr(source_socket, 'default_value'):
            target_socket.default_value = source_socket.default_value

    def copy_output(socket):
        node = socket.node
        if node.type == 'GROUP_INPUT':
            # Interface identifiers can differ across independently built games.
            candidates = [s for s in node.outputs if s.name == socket.name and s.type == socket.type]
            index = candidates.index(socket)
            group_input = next((n for n in destination.nodes if n.type == 'GROUP_INPUT'), None)
            if group_input is None:
                group_input = destination.nodes.new('NodeGroupInput')
            matches = [s for s in group_input.outputs if s.name == socket.name and s.type == socket.type]
            if index >= len(matches):
                raise ValueError(f'Missing sampling input {socket.name}')
            return matches[index]
        if node not in copied:
            # These nodes have fixed sockets (or a shared group interface). Keep
            # the supported set explicit so new procedural sampling fails safely.
            if node.type not in {'TEX_COORD', 'UVMAP', 'MAPPING', 'REROUTE', 'GROUP',
                                 'MATH', 'VECT_MATH', 'SEPXYZ', 'COMBXYZ', 'VALUE', 'RGB',
                                 'SEPARATE_COLOR', 'COMBINE_COLOR', 'ATTRIBUTE', 'NEW_GEOMETRY',
                                 'VECT_TRANSFORM', 'VECTOR_ROTATE'}:
                raise ValueError(f'{node.type} texture coordinates need an explicit target-game mapping')
            clone = destination.nodes.new(node.bl_idname)
            copied[node] = clone
            if node.type == 'GROUP':
                clone.node_tree = node.node_tree
            for attr in ('operation', 'use_clamp', 'vector_type', 'convert_from', 'convert_to',
                         'rotation_type', 'invert', 'uv_map', 'from_instancer', 'attribute_name',
                         'attribute_type', 'mode', 'mute', 'label', 'location'):
                if hasattr(node, attr):
                    setattr(clone, attr, getattr(node, attr))
            for name, value in node.items():
                clone[name] = value
            if node.get('foundry_material_transform'):
                copied_transforms.add(parameter_key(node['foundry_material_transform']))
            for a, b in zip(node.inputs, clone.inputs):
                copy_input(a, b)
            if node.type in {'VALUE', 'RGB'}:
                clone.outputs[0].default_value = node.outputs[0].default_value
        return copied[node].outputs[list(node.outputs).index(socket)]

    for key, sources in samples.items():
        for sample, replacement in zip(sources, target_samples[key]):
            for attr in ('image', 'extension', 'interpolation', 'projection', 'projection_blend'):
                if hasattr(sample, attr):
                    setattr(replacement, attr, getattr(sample, attr))
            for attr in ('frame_current', 'frame_duration', 'frame_start', 'frame_offset',
                         'use_cyclic', 'use_auto_refresh', 'tile'):
                if hasattr(sample.image_user, attr):
                    setattr(replacement.image_user, attr, getattr(sample.image_user, attr))
            if sample.get('foundry_address_modes') is not None:
                replacement['foundry_address_modes'] = sample['foundry_address_modes']
            copy_input(sample.inputs['Vector'], replacement.inputs['Vector'])
    # Export must find the copied authored transform, not a disconnected default.
    for node in original_transforms:
        if parameter_key(node['foundry_material_transform']) in copied_transforms:
            del node['foundry_material_transform']

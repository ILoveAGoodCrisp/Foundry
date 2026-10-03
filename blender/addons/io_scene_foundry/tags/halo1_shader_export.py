"""Export classic model/environment shaders using the H1 importer's layout."""
from blam_tags import RealRgbColor

from .. import utils
from .connected_material import AnimatedParameterType


def write_shader(shader):
    kind = shader.system_path.suffix[1:].lower()
    if kind not in {'shader_model', 'shader_environment'}:
        raise ValueError(f'Linked Halo 1 export is not supported for {kind}; create an empty tag instead')
    root = shader.tag.root()

    def child(struct, name):
        return shader.required_field(struct, name).as_struct()

    def set_value(struct, name, value):
        shader.required_field(struct, name).set(value)

    def menu(struct, name, value):
        # Reverse the display spelling used by _to_nodes_halo1_group.
        value = value.replace('multipurpose map alpha', 'auxiliary mask')
        key = lambda text: ''.join(c for c in text.casefold() if c.isalnum())
        field = shader.required_field(struct, name)
        for index, option in enumerate(field.options().names):
            if key(option) == key(value):
                field.set(index)
                return
        raise ValueError(f'Unknown {kind} {name}: {value}')

    def bitmap(struct, name, node):
        shader.set_reference(struct, name, shader._get_bitmap_path(node) if node else None)

    def tiling(node):
        parameters = shader._function_parameters_from_node(node, 'bitmap') if node else {}
        return (parameters.get(AnimatedParameterType.SCALE_X, 1.0),
                parameters.get(AnimatedParameterType.SCALE_Y, 1.0))

    properties = child(root, 'properties')
    flags = shader.required_field(properties, 'flags')
    group = shader.group_node
    uses_h1_group = (group is not None and group.node_tree is not None and
                     shader._normalize_group_name(group.node_tree.name) == 'foundry_h1.' + kind)
    if not uses_h1_group:
        # Principled and arbitrary graphs share the existing adaptive image mapper,
        # but write H1 structs rather than modern render-method options.
        mapping = shader._get_basic_mapping(shader.blender_material)
        shader.group_node = mapping.get('mapping_root') or mapping.get('bsdf')
        if kind == 'shader_model':
            maps = child(root, 'maps')
            bitmap(maps, 'base map', mapping.get('diffuse'))
            u, v = tiling(mapping.get('diffuse'))
            set_value(maps, 'map u scale', u)
            set_value(maps, 'map v scale', v)
            flags.set_flag('not alpha tested', not bool(mapping.get('alpha')))
            flags.set_flag('alpha blended decal', shader.blender_material.surface_render_method == 'BLENDED')
            flags.set_flag('two sided', not shader.blender_material.use_backface_culling)
        else:
            diffuse = child(root, 'diffuse')
            bitmap(diffuse, 'base map', mapping.get('diffuse'))
            tint = mapping.get('albedo_tint')
            set_value(diffuse, 'material color', RealRgbColor(*(tint[:3] if tint is not None else (1., 1., 1.))))
            bump = child(root, 'bump')
            bitmap(bump, 'bump map', mapping.get('normal'))
            set_value(bump, 'bump map scale', tiling(mapping.get('normal'))[0])
            illumination = child(root, 'self-illumination')
            bitmap(illumination, 'map', mapping.get('self_illum'))
            set_value(illumination, 'map scale', tiling(mapping.get('self_illum'))[0])
            flags.set_flag('alpha tested', bool(mapping.get('alpha')))
        return

    # Invert the model/environment resource importer, including external bitmap
    # nodes, UV scales, display menus, reflection and static illumination bounds.
    def copy_value(struct, field_name, socket_name=None):
        socket = group.inputs.get(socket_name or field_name.title())
        if socket is None:
            return
        value = socket.default_value
        if isinstance(shader.value(struct, field_name), RealRgbColor):
            value = RealRgbColor(*value[:3])
        set_value(struct, field_name, value)

    def copy_menu(struct, field_name, socket_name=None):
        socket = group.inputs.get(socket_name or field_name.title())
        if socket is not None:
            menu(struct, field_name, socket.default_value)

    def image_node(socket_name):
        node = utils.find_linked_node(group, socket_name.lower(), 'TEX_IMAGE')
        if node is None:
            node = utils.find_linked_node(group, socket_name.lower(), 'TEX_ENVIRONMENT')
        return node

    def image(struct, name, socket_name=None):
        node = image_node(socket_name or name.title())
        bitmap(struct, name, node)
        return tiling(node)

    def activation(struct, field_name, socket_name):
        socket = group.inputs.get(socket_name)
        if socket is not None:
            # Import previews collapse animated functions to 0/1. Preserve the
            # authored animation unless the socket enables/disables illumination.
            current = shader.required_field(struct, field_name).options().current_name
            if socket.default_value == 0:
                menu(struct, field_name, 'zero')
            elif current == 'zero':
                menu(struct, field_name, 'one')

    illumination = child(root, 'self-illumination')
    reflection = child(root, 'reflection')
    if kind == 'shader_model':
        for flag, socket_name in (
                ('detail after reflection', 'Detail After Reflections'),
                ('two sided', 'Two-Sided'), ('not alpha tested', 'Not Alpha-Tested'),
                ('alpha blended decal', 'Alpha-Blended Decal'),
                ('use xbox multipurpose channel order', 'Multipurpose Map Uses OG Xbox Channel Order')):
            flags.set_flag(flag, group.inputs[socket_name].default_value)
        for name in ('animation color lower bound', 'animation color upper bound'):
            copy_value(illumination, name)
        activation(illumination, 'animation function', 'Animation Color Bound Factor')
        maps = child(root, 'maps')
        image(maps, 'base map')
        u, v = tiling(image_node('Base Map') or image_node('Multipurpose Map'))
        set_value(maps, 'map u scale', u)
        set_value(maps, 'map v scale', v)
        image(maps, 'multipurpose map')
        copy_menu(maps, 'detail function')
        copy_menu(maps, 'detail mask')
        detail_u, detail_v = image(maps, 'detail map')
        set_value(maps, 'detail map scale', detail_u / (u or 1.0))
        set_value(maps, 'detail map v scale', detail_v / (v or 1.0))
        specular = child(reflection, 'cube map properties')
        for field in ('perpendicular brightness', 'parallel brightness',
                      'perpendicular tint color', 'parallel tint color'):
            copy_value(specular, field)
        image(reflection, 'cube map', 'Reflection Cube Map')
        attribute = utils.find_linked_node(group, 'primary change color', 'ATTRIBUTE')
        source = {'Primary Color': 'a', 'Secondary Color': 'b',
                  'Tertiary Color': 'c', 'Quaternary Color': 'd'}.get(
                      attribute.attribute_name if attribute else '', 'none')
        menu(child(root, 'change color'), 'change color source', source)
    else:
        flags.set_flag('alpha tested', group.inputs['Alpha Tested'].default_value)
        copy_menu(properties, 'shader environment type', 'Blend Type')
        diffuse = child(root, 'diffuse')
        image(diffuse, 'base map')
        copy_menu(diffuse, 'detail map function')
        copy_menu(diffuse, 'micro detail map function')
        for name in ('primary detail map', 'secondary detail map', 'micro detail map'):
            set_value(diffuse, name + ' scale', image(diffuse, name)[0])
        bump = child(root, 'bump')
        set_value(bump, 'bump map scale', image(bump, 'bump map')[0])
        for layer in ('primary', 'secondary', 'plasma'):
            copy_value(illumination, layer + ' on color')
            copy_value(illumination, layer + ' off color')
            activation(illumination, layer + ' animation function',
                       layer.title() + ' Self-Illumination Activation Level')
        set_value(illumination, 'map scale', image(illumination, 'map', 'Self-Illumination Map')[0])
        specular = child(root, 'specular')
        for field in ('brightness', 'perpendicular color', 'parallel color'):
            copy_value(specular, field)
        for field in ('perpendicular brightness', 'parallel brightness'):
            copy_value(reflection, field)
        image(reflection, 'reflection cube map')

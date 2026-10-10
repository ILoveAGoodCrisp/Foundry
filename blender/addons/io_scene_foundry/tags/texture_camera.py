"""The shader bitmap override that displays Halo's live texture-camera feed."""
TEXTURE_CAMERA_EXTERN_MODE = 1


def _parameters(document):
    # Decal systems embed a shader/material in each decal rather than at the
    # tag root. Use the element selected by the converter when it is available.
    render_method = getattr(getattr(document, 'render_method', None), 'struct', None)
    if render_method is None:
        root = document.tag.root()
        field = root.field('render_method')
        render_method = field.as_struct() if field is not None else root
    name = 'parameters' if render_method.field('parameters') is not None else 'material parameters'
    return render_method, document.block(render_method, name)


def texture_camera_parameters(document):
    _, parameters = _parameters(document)
    return [document.value(p, 'parameter name') for p in parameters
            if any(p.field(name) is not None and p.field(name).value == TEXTURE_CAMERA_EXTERN_MODE
                   for name in ('bitmap extern RTT mode', 'bitmap extern mode'))]


def write_texture_camera_source(document, parameter_name, enabled):
    """Use authored parameter metadata; Tool regenerates the postprocess data."""
    names = [name.strip() for name in parameter_name.split(',') if name.strip()] if enabled else []
    if enabled and not names:
        raise ValueError('Select a bitmap parameter for the texture-camera feed')
    _, parameters = _parameters(document)
    for element in parameters:
        if document.value(element, 'parameter name') not in names:
            for field_name in ('bitmap extern RTT mode', 'bitmap extern mode'):
                field = element.field(field_name)
                if field is not None and field.value == TEXTURE_CAMERA_EXTERN_MODE:
                    field.set(0)
                    document.tag_has_changes = True
    for name in names:
        _write_texture_camera_parameter(document, name)


def _write_texture_camera_parameter(document, parameter_name):
    render_method, parameters = _parameters(document)
    parameter_name = parameter_name.strip()
    selected = next((p for p in parameters if document.value(p, 'parameter name') == parameter_name), None)
    options = render_method.field('options')
    family = document.system_path.suffix
    if selected is None:
        # Standard shader inputs can be enabled without a placeholder bitmap.
        if options is None or parameter_name not in {'base_map', 'self_illum_map'}:
            raise ValueError(f'Texture-camera parameter {parameter_name!r} is missing; select an exported bitmap input')
        if family not in {'.shader', '.shader_custom', '.shader_halogram'}:
            raise ValueError('Export this shader bitmap input before using it for the texture camera')
        selected = parameters[parameters.add()]
        document.required_field(selected, 'parameter name').set(parameter_name)
        document.required_field(selected, 'parameter type').set('bitmap')
    if document.value(selected, 'parameter type') != 'bitmap':
        raise ValueError(f'Texture-camera parameter {parameter_name!r} is not a bitmap')
    field = selected.field('bitmap extern RTT mode') or selected.field('bitmap extern mode')
    if field is None:
        raise ValueError('This material layout does not support texture-camera bitmap inputs')
    field.set(TEXTURE_CAMERA_EXTERN_MODE)
    if options is not None and family in {'.shader', '.shader_custom', '.shader_halogram'}:
        block = options.as_block()
        if parameter_name == 'base_map':
            setting = document.required_field(block[0], 'short')
            if setting.value == 2 or setting.value < 0:
                setting.set(0)
        elif parameter_name == 'self_illum_map':
            index = 1 if family == '.shader_halogram' else 6
            setting = document.required_field(block[index], 'short')
            if setting.value <= 0 or setting.value == 4:
                setting.set(1)
    document.tag_has_changes = True

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


def _defined_bitmap_parameters(document, render_method):
    """Include inactive options: a camera feed need not have a preview image."""
    from .backend import TagDocument
    from .metadata import MaterialShaderDocument, RenderMethodDefinitionDocument

    if render_method.field('definition') is not None:
        reference = TagDocument.reference(document, render_method, 'definition')
        document_type = RenderMethodDefinitionDocument
    else:
        reference = TagDocument.reference(document, render_method, 'material shader')
        document_type = MaterialShaderDocument
    if reference is None or not reference.IsTagFileAccessible():
        return set()
    with document_type(reference, tags_root=document.tags_root, game=document.game,
                       definitions=document.definitions, must_exist=True) as definition:
        defaults = definition.get_defaults()
    if document_type is RenderMethodDefinitionDocument:
        parameters = (parameters for options in defaults.values() for parameters in options.values())
    else:
        parameters = (defaults,)
    return {name for group in parameters for name, parameter in group.items() if parameter.type == 0}


def write_texture_camera_source(document, parameter_name, enabled):
    """Use authored parameter metadata; Tool regenerates the postprocess data."""
    names = [name.strip() for name in parameter_name.split(',') if name.strip()] if enabled else []
    if enabled and not names:
        raise ValueError('Select a bitmap parameter for the texture-camera feed')
    render_method, parameters = _parameters(document)
    existing_names = {document.value(element, 'parameter name') for element in parameters}
    bitmap_parameters = (_defined_bitmap_parameters(document, render_method)
                         if set(names) - existing_names else set())
    for element in parameters:
        if document.value(element, 'parameter name') not in names:
            for field_name in ('bitmap extern RTT mode', 'bitmap extern mode'):
                field = element.field(field_name)
                if field is not None and field.value == TEXTURE_CAMERA_EXTERN_MODE:
                    field.set(0)
                    document.tag_has_changes = True
    for name in names:
        _write_texture_camera_parameter(document, name, bitmap_parameters)


def _write_texture_camera_parameter(document, parameter_name, bitmap_parameters=()):
    render_method, parameters = _parameters(document)
    parameter_name = parameter_name.strip()
    selected = next((p for p in parameters if document.value(p, 'parameter name') == parameter_name), None)
    options = render_method.field('options')
    family = document.system_path.suffix
    if selected is None:
        # A runtime camera feed has no source bitmap. Validate the name against
        # the definition before adding its override, even for an inactive option.
        standard_input = (options is not None
                          and family in {'.shader', '.shader_custom', '.shader_halogram'}
                          and parameter_name in {'base_map', 'self_illum_map'})
        if not standard_input and parameter_name not in bitmap_parameters:
            raise ValueError(f'Texture-camera parameter {parameter_name!r} is missing; select an exported bitmap input')
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

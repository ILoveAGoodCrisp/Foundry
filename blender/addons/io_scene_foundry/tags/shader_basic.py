"""Write ordinary Blender surfaces using the target render method's categories."""


def write_shader(shader, mapping):
    shader.group_node = mapping.get('mapping_root') or mapping.get('bsdf')
    shader._get_info(shader.definition.Path)
    categories = shader.category_parameters
    if not categories:
        raise ValueError(f'{shader.tag_path.RelativePathWithExtension}: missing render method categories')

    diffuse = mapping.get('diffuse')
    normal = mapping.get('normal')
    specular = mapping.get('specular')
    illumination = mapping.get('self_illum')
    alpha = mapping.get('alpha')
    strength = mapping.get('emission_strength', 0.)
    color = mapping.get('emission_color', (0., 0., 0.))
    emissive = strength > 0 and (illumination is not None or any(color))
    diffuse_specular = mapping.get('specular_from_diffuse_alpha', False)
    diffuse_illumination = mapping.get('self_illum_from_diffuse_alpha', False)
    clip = shader.alpha_type == 'clip'
    blend = shader.alpha_type == 'blend'

    choices = {
        'albedo': ('default', 'diffuse_only', 'simple') if diffuse is not None else ('constant_color', 'default', 'diffuse_only'),
        'bump_mapping': ('standard',) if normal is not None else ('off', 'leave', 'none'),
        'alpha_test': ('simple', 'on') if clip else ('none', 'off'),
        'specular_mask': (('specular_mask_from_diffuse',) if diffuse_specular else
                          ('specular_mask_from_texture',) if specular is not None else ('no_specular_mask',)),
        'material_model': ('cook_torrance', 'two_lobe_phong') if specular is not None else ('diffuse_only',),
        'self_illumination': (('from_diffuse',) if diffuse_illumination else ('simple',)) if emissive else ('off', 'none'),
        'blend_mode': ('alpha_blend',) if blend else ('opaque',),
        'alpha_blend_source': (('from_opacity_map_alpha',) if mapping.get('alpha_channel') == 'alpha' else
                               ('from_opacity_map_rgb',)) if blend and alpha is not None else ('from_albedo_alpha',),
    }
    parameters = {}
    for index, (category, options) in enumerate(categories.items()):
        names = list(options)
        if not names:
            continue
        selected = next((name for name in choices.get(category, ()) if name in options), names[0])
        while shader.block_options.Elements.Count <= index:
            shader.block_options.AddElement()
        shader.block_options.Elements[index].SelectField('short').SetStringData(str(names.index(selected)))
        parameters.update(options[selected])

    # Only regenerate overrides owned by the generic exporter. Other tag metadata
    # survives; obsolete maps/functions cannot leak into the new surface.
    owned = {'base_map', 'albedo_color', 'specular_mask_texture', 'self_illum_map',
             'self_illum_color', 'self_illum_intensity', 'bump_map', 'alpha_test_map',
             'opacity_map', 'alpha', 'base_map_m_0', 'bump_map_m_0'}
    for name in owned:
        shader._Element_remove_if_needed(shader.block_parameters, 'parameter name', name)

    def write(name, source, kind):
        if source is None or name not in parameters:
            return
        parameter = parameters[name]
        # Match the selected option's parameter kind before writing an override.
        source_type, tag_type = shader._parameter_type_tokens(parameter)
        if source_type != kind:
            return
        element = shader._setup_parameter(source, name, tag_type)
        if element:
            shader._setup_function_parameters(source, element, kind)

    write('base_map', diffuse, 'bitmap')
    write('base_map_m_0', diffuse, 'bitmap')
    if diffuse is None:
        write('albedo_color', mapping.get('albedo_tint'), 'color')
    write('bump_map', normal, 'bitmap')
    write('bump_map_m_0', normal, 'bitmap')
    if not diffuse_specular:
        write('specular_mask_texture', specular, 'bitmap')
    if emissive:
        if not diffuse_illumination:
            write('self_illum_map', illumination if illumination is not None else
                  'shaders/default_bitmaps/bitmaps/color_white.bitmap', 'bitmap')
        write('self_illum_color', (1., 1., 1.) if illumination is not None else color, 'color')
        write('self_illum_intensity', strength, 'real')
    if clip:
        write('alpha_test_map', alpha, 'bitmap')
    elif blend:
        write('opacity_map', alpha, 'bitmap')
        write('alpha', mapping.get('opacity', 1.), 'real')

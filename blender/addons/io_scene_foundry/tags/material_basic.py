"""Generic surfaces mapped to material shaders actually present in the kit."""


def write_material(material, mapping):
    material.group_node = mapping.get('mapping_root') or mapping.get('bsdf')
    diffuse = mapping.get('diffuse')
    normal = mapping.get('normal')
    specular = mapping.get('specular')
    illumination = mapping.get('self_illum')
    strength = mapping.get('emission_strength', 0.)
    color = mapping.get('emission_color', (0., 0., 0.))
    emissive = strength > 0 and (illumination is not None or any(color))
    diffuse_specular = mapping.get('specular_from_diffuse_alpha', False)
    diffuse_illumination = mapping.get('self_illum_from_diffuse_alpha', False)
    clip = material.alpha_type == 'clip'

    candidates = []
    if emissive:
        if diffuse_illumination:
            candidates.append('srf_ca_blinn_diffspec_selfillum')
        if clip:
            candidates.append('srf_blinn_selfillum_clip')
        candidates.append('srf_blinn_selfillum_mod')
        # H2A omits H4's separate selfillum modulation shader. Its Blinn shader
        # takes an illumination mask in the blue channel of its control map.
        candidates.append('srf_blinn_selfillum')
    elif diffuse_specular:
        candidates.append('srf_ca_blinn_diffspec_clip' if clip else 'srf_ca_blinn_diffspec')
    elif diffuse is None and normal is None and specular is None:
        candidates.append('srf_constant_clip' if clip else 'srf_constant')
    candidates.append('srf_blinn_clip' if clip else 'srf_blinn')

    if material.material_shader:
        path = material.material_shader
    else:
        path = next((path for name in candidates
                     if (path := material._material_shader_path_from_group_node(name))), None)
        if path is None:
            raise ValueError(f'No compatible material shader found in {material.tags_dir}')
    material.reference_material_shader.Path = material._TagPath_from_string(path)
    parameters = material._get_info(material.reference_material_shader.Path)
    material.alpha_blend_mode.Value = 3 if material.alpha_type == 'blend' else 0

    owned = {'color_map', 'albedo_tint', 'specular_map', 'normal_map', 'selfillum_map',
             'selfillum_mod_map', 'control_map_spglsi', 'control_map_spglrf',
             'si_color', 'si_intensity', 'si_amount', 'diffuse_alpha_mask_specular'}
    for name in owned:
        material._Element_remove_if_needed(material.block_parameters, 'parameter name', name)

    def write(name, source, kind):
        parameter = parameters.get(name)
        if source is None or parameter is None or parameter.type_name != kind:
            return
        element = material._setup_parameter(source, name, kind)
        if element:
            functions = material._setup_function_parameters(source, element, kind)
            material._finalize_material_parameters(functions, element)

    white = 'shaders/default_bitmaps/bitmaps/color_white.bitmap'
    write('color_map', diffuse if diffuse is not None else white, 'bitmap')
    write('albedo_tint', mapping.get('albedo_tint', (1., 1., 1.)), 'color')
    write('normal_map', normal, 'bitmap')
    if not diffuse_specular:
        write('specular_map', specular, 'bitmap')
    write('diffuse_alpha_mask_specular', int(diffuse_specular),
          parameters['diffuse_alpha_mask_specular'].type_name if 'diffuse_alpha_mask_specular' in parameters else 'bool')
    write('si_intensity', strength if emissive else 0., 'real')
    if emissive:
        source = illumination if illumination is not None else white
        if 'selfillum_mod_map' in parameters:
            write('selfillum_mod_map', source, 'bitmap')
            write('control_map_spglrf', white, 'bitmap')
        elif 'selfillum_map' in parameters:
            write('selfillum_map', source, 'bitmap')
        elif 'control_map_spglsi' in parameters:
            write('control_map_spglsi', source, 'bitmap')
        else:
            write('control_map_spglrf', source, 'bitmap')
        write('si_color', (1., 1., 1.) if illumination is not None else color, 'color')
        write('si_amount', 1., 'real')

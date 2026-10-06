"""Translate resolved Foundry face properties into legacy material variants."""
from ..exceptions import ExportCancelled
from ..legacy.lighting import ass_rgb


def material_variant(shader, props, global_material='default', ass_version=None,
                     target_game=None, model=False):
    def get(name, default=0):
        return props.get('bungie_' + name, default)

    name = shader
    special = {13: '+portal', 14: '+seam', 15: '+fog', 16: '+cookiecutter',
               17: '+water', 18: '+water', 8: '+rainblocker', 9: '+rain'}
    water_surface = target_game in {'halo3', 'halo3odst'} and get('mesh_type') == 17
    if target_game in {'halo3', 'halo3odst'}:
        # Physics-water is classified by the ~ ASS instance, not +water.
        special[18] = '+unused'
    if water_surface:
        # H3/ODST water retains its shader and is identified by the apostrophe
        # material symbol. +water is not a special water-surface material.
        special.pop(17)
    if target_game == 'halo1':
        # H1 has its own hard-coded BSP material names. Water uses a real
        # shader, while standalone fog is the unused material with a $ flag.
        # Always use exact portals to avoid Tool's unearthed portal warning.
        special = {13: '+exactportal', 14: '+seamsealer', 15: '+unused',
                   8: '+weatherpoly'}
    name = special.get(get('mesh_type'), name)
    if target_game == 'halo1' and props.get('foundry_weather_polyhedron'):
        name = '+weatherpoly'
    if get('face_type') == 1:
        name = '+seamsealer'
    elif get('face_type') == 2:
        sky_index = get('sky_permutation_index')
        name = '+sky' + (str(sky_index) if target_game == 'halo1' and sky_index else '')
    # These suffixes are also understood by Foundry's legacy importer.
    sides, mode = get('face_sides'), get('face_mode')
    portal_type = get('mesh_portal_type', '')
    if water_surface:
        # Water surfaces must never enter the solid BSP collision pass, even
        # when a mesh/face override requests a collision mode.
        mode = 1
    if mode == 4 and (ass_version is None or ass_version < 4):
        raise ExportCancelled('Shadow Only requires ASS 7 material flags; this output dialect cannot encode it')
    flags = [sides in {2, 3, 4, 5, 6, 7}, sides == 1, sides in {3, 5, 7},
             mode == 1, mode == 2,
             mode == 3 or (mode == 2 and props.get('foundry_legacy_sphere_collision', False)), get('mesh_type') == 15,
             bool(get('ladder')), mode == 6, bool(get('mesh_portal_ai_deafening')), bool(get('no_shadow')),
             mode == 4, mode == 5,
             bool(get('precise_position')) and target_game != 'halo1', False,
             bool(get('portal_one_way')) or portal_type == '_connected_geometry_portal_type_one_way',
             bool(get('portal_door')) or bool(get('mesh_portal_is_door')),
             bool(get('portal_vis_blocker')) or portal_type == '_connected_geometry_portal_type_no_way',
             bool(get('no_lightmap')), bool(get('mesh_portal_blocks_sound')),
             bool(get('decal_offset')), bool(get('slip_surface'))]
    if sides == props.get('foundry_legacy_import_sides') and 'foundry_legacy_side_flags' in props:
        mask = props['foundry_legacy_side_flags']
        flags[:3] = [bool(mask & (1 << bit)) for bit in range(3)]
    suffixes = ('%', '#', '?', '!', '@', '*', '$', '^', '-', '&', '=', '', ';', ')', '', '<', '|', '~', '{', '}', '[', ']')
    if target_game == 'halo1':
        flags[9] = bool(get('mesh_portal_ai_deafening'))
        # Later games' symbols are not H1 material flags.
        flags = [flag and symbol in '%#!@*$^-&' for flag, symbol in zip(flags, suffixes)]
    # CE's model compiler resolves these characters as part of the shader
    # filename. Only its BSP compiler interprets material flag suffixes.
    if not (target_game == 'halo1' and model):
        name += ''.join(s for flag, s in zip(flags, suffixes) if flag)
    if water_surface:
        name += "'"
    legacy_resolution = target_game in {'halo1', 'halo2', 'halo3', 'halo3odst'}
    lmres = get('lightmap_resolution_scale', 1 if legacy_resolution else 3)
    lmres_scale = lmres if legacy_resolution else lmres / 3
    has_lightmap_record = bool(ass_version and ass_version >= 4
                              and props.get('foundry_legacy_lightmap_record_size', 11))
    if target_game != 'halo1' and not has_lightmap_record and lmres != (1 if legacy_resolution else 3):
        name += f' lm:{lmres_scale:g}'
    power = get('lighting_emissive_power')
    if target_game == 'halo2':
        scale = get('lighting_emissive_power_scale', 1.0)
        if scale != 1.0:
            name += f' lp:{scale:g}'
        half_life = props.get('foundry_lighting_emissive_half_life', 0.0)
        if half_life:
            name += f' hl:{half_life:g}'
    elif (power or props.get('foundry_lighting_basic_present')) and target_game != 'halo1' and not (ass_version and ass_version >= 4):
        name += f' lp:{power:g}'
    lighting = ()
    if ass_version and ass_version >= 4:
        # Resolved face properties use 0-255 RGB for these two colours;
        # ASS lighting records require normalized real RGB values.
        tint = tuple(v / 255 for v in get('lightmap_translucency_tint_color', (0, 0, 0)))[:3]
        additive = tuple(v / 255 for v in get('lightmap_additive_transparency', (0, 0, 0)))[:3]
        color = ass_rgb(get('lighting_emissive_color', (255, 255, 255, 255)))
        lighting = ('BM_FLAGS ' + ''.join('1' if v else '0' for v in flags),)
        lightmap = (lmres_scale, props.get('foundry_lightmap_photon_fidelity', 1), *tint,
                    int(get('lightmap_transparency_override')), *additive, int(get('lighting_use_shader_gel')),
                    int(get('lightmap_ignore_default_resolution_scale')))
        size = props.get('foundry_legacy_lightmap_record_size', 11)
        if size == 0:
            # Resolution-only edits already use the native lm: name token.
            # Omitted records must not become explicit colour/alpha overrides.
            if any(lightmap[2:]) or lightmap[1] != 1:
                size = 11
        elif size < 10 and any(lightmap[5:]):
            size = 11
        elif size == 10 and lightmap[10]:
            size = 11
        if size:
            if size == 3:
                values = lightmap[:2] + (tint[0],)
                if max(tint)-min(tint)>1e-6:
                    values = lightmap[:5]
            else:
                values = lightmap[:size]
            lighting += ('BM_LMRES ' + ' '.join(map(str, values)),)
        basic = bool(power or props.get('foundry_lighting_basic_present'))
        if basic:
            lighting += ('BM_LIGHTING_BASIC ' + ' '.join(map(str, (power, *color, get('lighting_emissive_quality', 1),
                int(get('lighting_emissive_per_unit')), get('lighting_emissive_focus')))),)
        if basic or props.get('foundry_lighting_attenuation_authored'):
            lighting += ('BM_LIGHTING_ATTEN ' + ' '.join(map(str, (int(get('lighting_attenuation_enabled')),
                get('lighting_attenuation_falloff'), get('lighting_attenuation_cutoff')))),)
        if props.get('foundry_lighting_frustum_present'):
            lighting += ('BM_LIGHTING_FRUS ' + ' '.join(map(str, (
                props['foundry_lighting_frustum_blend'], props['foundry_lighting_frustum_falloff'],
                props['foundry_lighting_frustum_cutoff']))),)
    if global_material and global_material != 'default':
        name = global_material + ' ' + name
    return name, lighting

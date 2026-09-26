"""Translate resolved Foundry face properties into legacy material variants."""
from math import degrees


def material_variant(shader, props, global_material='default', ass_version=None,
                     target_game=None):
    def get(name, default=0):
        return props.get('bungie_' + name, default)

    name = shader
    special = {13: '+portal', 14: '+seam', 15: '+fog', 16: '+cookiecutter',
               17: '+water', 18: '+water', 8: '+rainblocker', 9: '+rain'}
    if target_game == 'halo1':
        # H1 has its own hard-coded BSP material names. Water uses a real
        # shader, while standalone fog is the unused material with a $ flag.
        special = {13: '+portal', 14: '+seamsealer', 15: '+unused',
                   8: '+weatherpoly'}
        if get('mesh_type') == 13 and shader.startswith('+exactportal'):
            special[13] = '+exactportal'
        if props.get('foundry_weather_polyhedron'):
            return '+weatherpoly', ()
    name = special.get(get('mesh_type'), name)
    if get('face_type') == 1:
        name = '+seamsealer'
    elif get('face_type') == 2:
        sky_index = get('sky_permutation_index')
        name = '+sky' + (str(sky_index) if target_game == 'halo1' and sky_index else '')
    # These suffixes are also understood by Foundry's legacy importer.
    sides, mode = get('face_sides'), get('face_mode')
    if mode == 4 and (ass_version is None or ass_version < 4):
        raise ValueError('Shadow Only requires ASS 7 material flags; this output dialect cannot encode it')
    flags = [sides in {2, 3, 4, 5, 6, 7}, sides == 1, sides in {3, 5, 7},
             mode == 1, mode == 2, mode == 3, get('mesh_type') == 15,
             bool(get('ladder')), mode == 6, False, bool(get('no_shadow')),
             mode == 4, mode == 5,
             bool(get('precise_position')) and target_game != 'halo1', False,
             bool(get('portal_one_way')), bool(get('portal_door')), bool(get('portal_vis_blocker')),
             bool(get('no_lightmap')), False, bool(get('decal_offset')), bool(get('slip_surface'))]
    suffixes = ('%', '#', '?', '!', '@', '*', '$', '^', '-', '&', '=', '', ';', ')', '', '<', '|', '~', '{', '}', '[', ']')
    if target_game == 'halo1':
        flags[9] = bool(get('mesh_portal_ai_deafening'))
        # Later games' symbols are not H1 material flags.
        flags = [flag and symbol in '%#!@*$^-&' for flag, symbol in zip(flags, suffixes)]
        if name == '+unused':
            return '+unused$', ()
    name += ''.join(s for flag, s in zip(flags, suffixes) if flag)
    legacy_resolution = target_game in {'halo1', 'halo2', 'halo3', 'halo3odst'}
    lmres = get('lightmap_resolution_scale', 1 if legacy_resolution else 3)
    lmres_scale = lmres if legacy_resolution else lmres / 3
    if target_game != 'halo1' and lmres != (1 if legacy_resolution else 3):
        name += f' lm:{lmres_scale:g}'
    power = get('lighting_emissive_power')
    if power and target_game != 'halo1':
        name += f' lp:{power:g}'
    lighting = ()
    if ass_version and ass_version >= 4:
        tint = tuple(get('lightmap_translucency_tint_color', (0, 0, 0)))[:3]
        additive = tuple(get('lightmap_additive_transparency', (0, 0, 0)))[:3]
        color = tuple(get('lighting_emissive_color', (1, 1, 1)))[:3]
        lighting = (
            'BM_FLAGS ' + ''.join('1' if v else '0' for v in flags),
            'BM_LMRES ' + ' '.join(map(str, (lmres_scale, 1, *tint,
                int(get('lightmap_transparency_override')), *additive, int(get('lighting_use_shader_gel')),
                int(get('lightmap_ignore_default_resolution_scale'))))),
            'BM_LIGHTING_BASIC ' + ' '.join(map(str, (power, *color, get('lighting_emissive_quality', 1),
                int(get('lighting_emissive_per_unit')), 1 - degrees(get('lighting_emissive_focus')) / 180))),
            'BM_LIGHTING_ATTEN ' + ' '.join(map(str, (int(get('lighting_attenuation_enabled')),
                get('lighting_attenuation_falloff'), get('lighting_attenuation_cutoff')))),
        )
    if global_material and global_material != 'default':
        name = global_material + ' ' + name
    return name, lighting

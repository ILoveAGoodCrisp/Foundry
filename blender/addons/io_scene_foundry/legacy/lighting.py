"""Emissive values at the pre-Reach interchange boundary.

Blender keeps angles in radians and distances in scene units. Virtual geometry
uses ARGB 0-255 and a normalized focus factor; ASS uses RGB 0-1, the same focus
factor, and JMS/ASS distances. Keep these conversions in one place.
"""
from math import degrees


def emissive_properties(prop, distance_scale, automatic_distances=None):
    mode = prop.material_lighting_attenuation_mode
    falloff = prop.material_lighting_attenuation_falloff
    cutoff = prop.material_lighting_attenuation_cutoff
    if mode == 'AUTO' and falloff == cutoff == 0 and automatic_distances is not None:
        falloff, cutoff = automatic_distances
    color = tuple(prop.material_lighting_emissive_color)
    return {
        'foundry_lighting_emissive_present': 1,
        'foundry_lighting_basic_present': int(prop.material_lighting_emissive_basic),
        'bungie_lighting_emissive_power': prop.material_lighting_emissive_power,
        'bungie_lighting_emissive_color': (255.0, *(c * 255 for c in color)),
        'bungie_lighting_emissive_quality': prop.material_lighting_emissive_quality,
        'bungie_lighting_emissive_per_unit': int(prop.material_lighting_emissive_per_unit),
        'bungie_lighting_use_shader_gel': int(prop.material_lighting_use_shader_gel),
        'bungie_lighting_emissive_focus': max(0.0, min(1.0, 1 - degrees(prop.material_lighting_emissive_focus) / 180)),
        'bungie_lighting_attenuation_enabled': int(mode != 'DISABLED'),
        'bungie_lighting_attenuation_falloff': falloff * distance_scale,
        'bungie_lighting_attenuation_cutoff': cutoff * distance_scale,
        'foundry_lighting_attenuation_authored': int(mode != 'AUTO'),
        'foundry_lighting_frustum_present': int(prop.material_lighting_emissive_frustum),
        'foundry_lighting_frustum_blend': prop.material_lighting_frustum_blend,
        'foundry_lighting_frustum_falloff': degrees(prop.material_lighting_frustum_falloff),
        'foundry_lighting_frustum_cutoff': degrees(prop.material_lighting_frustum_cutoff),
    }


def ass_rgb(argb):
    values = tuple(argb)
    if len(values) == 4:
        return tuple(c / 255 for c in values[1:])
    return tuple(c / 255 for c in values[:3])


def jms_emissive_unsupported(props):
    """JMS material names encode power, but not ASS's lighting records."""
    if 'bungie_lighting_emissive_power' not in props:
        return False
    if not props.get('foundry_lighting_emissive_present') and props['bungie_lighting_emissive_power'] <= 0:
        return False
    color = ass_rgb(props.get('bungie_lighting_emissive_color', (255, 255, 255, 255)))
    return (any(abs(c - 1) > 1e-5 for c in color)
            or props.get('bungie_lighting_emissive_quality', 1) != 1
            or bool(props.get('bungie_lighting_emissive_per_unit', 0))
            or bool(props.get('bungie_lighting_use_shader_gel', 0))
            or abs(props.get('bungie_lighting_emissive_focus', 0)) > 1e-5
            or bool(props.get('foundry_lighting_attenuation_authored', 0))
            or bool(props.get('foundry_lighting_frustum_present', 0)))

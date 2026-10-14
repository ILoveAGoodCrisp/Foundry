"""Lighting units from the H2 MCC photon mapper and H3/ODST faux/runtime.

These are relative scene-linear values; game exposure and BRDFs are separate.
Distances and areas passed here are in world units and square world units.
"""
from math import cos, exp, pi, sqrt


H3_SOURCE_RADIUS = 0.02
H3_TYPE_SCALE = {'POINT': 0.003, 'SPOT': 0.025, 'SUN': 0.005}
H3_FAR_FIELD = {kind: 100000 * pi * H3_SOURCE_RADIUS ** 2 * scale
                for kind, scale in H3_TYPE_SCALE.items()}


def h3_solid_angle(distance):
    ratio = (H3_SOURCE_RADIUS / max(distance, 0.0202)) ** 2
    # Rationalized 1-sqrt(1-x) avoids cancellation for distant lights.
    return 2 * pi * ratio / (1 + sqrt(1 - ratio))


def h3_baked_energy(intensity, kind, scene_units_per_wu):
    if kind == 'SUN':
        return intensity * 100000 * H3_TYPE_SCALE[kind] * h3_solid_angle(1)
    return intensity * H3_FAR_FIELD[kind] * 4 * pi * scene_units_per_wu ** 2


def h3_baked_intensity(energy, kind, scene_units_per_wu):
    return energy / h3_baked_energy(1, kind, scene_units_per_wu)


def h3_dynamic_attenuation(distance, maximum_distance, diffusion):
    radius = maximum_distance if maximum_distance > 0 else 5.0
    return max(0.0, 1 - distance ** 2 / radius ** 2) / (distance ** 2 + max(diffusion, 1e-6))


def h3_dynamic_cone(cos_theta, fov, smoothness, spherical):
    smoothness = smoothness if smoothness > 0 else 1.0
    spherical = min(1.0, max(0.0, spherical))
    edge = cos((fov if fov > 0 else 0.5) * 0.5)
    scale = (1 - spherical) ** (1 / smoothness) / max(1e-8, 1 - edge)
    return min(1.0, max(0.0, scale * (cos_theta - edge)) ** smoothness + spherical)


def linear_window(distance, start, end):
    if end <= start:
        return float(distance <= end)
    return min(1.0, max(0.0, (end - distance) / (end - start)))


def h2_color_curve(linear_color):
    """Input has already been gamma-2.2 decoded by the tag importer."""
    color = tuple(max(0.0, c) for c in linear_color[:3])
    luminance = sum(c * w for c, w in zip(color, (0.2126, 0.7152, 0.0722)))
    limited = min(luminance, 1.0)
    multiplier = limited / (4.5 - 3.5 * limited) / luminance if luminance > 0 else 0.0
    return tuple(c * multiplier for c in color)


def h2_half_life(distance, half_life):
    return exp(-0.693 * max(0.0, distance) / half_life) if half_life > 0 else 1.0


def h3_emissive_density(power, area, per_unit_area, frustum_blend=0):
    return power * (1 if per_unit_area else 0.3 / max(area, 1e-8)) * (1 - frustum_blend)

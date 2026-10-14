"""Halo 2's single global water definition per structure BSP.

Values use the tag's native units (including radians and world units). Geometry
and resource bookkeeping belong to Tool and must survive settings updates.
"""
from .backend import TagDocument


# Property suffix, tag field, value kind, default. Appearance defaults follow
# Delta Halo. Projection defaults follow General_101's H2 water guide:
# https://c20.reclaimers.net/h2/guides/map-making/level-creation/blender-level-modeling/blender-level-creation-additional-info/#water-definitions
WATER_FIELDS = (
    ('sun_spot_color', 'sun spot color', 'color', (0.85, 0.9, 0.27)),
    ('reflection_tint', 'reflection tint', 'color', (0.25, 0.28, 0.31)),
    ('refraction_tint', 'refraction tint', 'color', (0.0, 0.31, 0.33)),
    ('horizon_color', 'horizon color', 'color', (0.29, 0.28, 0.38)),
    ('sun_specular_power', 'sun specular power', 'real', 32.0),
    ('reflection_bump_scale', 'reflection bump scale', 'real', 0.2),
    ('refraction_bump_scale', 'refraction bump scale', 'real', 0.1),
    ('fresnel_scale', 'fresnel scale', 'real', 0.2),
    ('sun_dir_heading', 'sun dir heading', 'angle', -2.2),
    ('sun_dir_pitch', 'sun dir pitch', 'angle', 1.54),
    ('fov', 'fov', 'angle', 1.1),
    ('aspect', 'aspect', 'real', 4 / 3),
    ('height', 'height', 'distance', 0.0),
    ('farz', 'farz', 'distance', 512.0),
    ('rotate_offset', 'rotate_offset', 'angle', 0.0),
    ('center', 'center', 'vector', (0.0, 0.0)),
    ('extents', 'extents', 'vector', (0.0, 0.0)),
    ('fog_near', 'fog near', 'distance', 0.0),
    ('fog_far', 'fog far', 'distance', 0.0),
    ('dynamic_height_bias', 'dynamic_height_bias', 'distance', 0.0),
)

# H2 renders an infinite horizontal ocean. Only height depends on geometry;
# FOV/aspect/farz are projection settings, and the guide reports no effect from
# rotate_offset/center/extents. Do not infer these from the plane's dimensions.
AUTOMATIC_WATER_FIELDS = frozenset({
    'fov', 'aspect', 'height', 'farz', 'rotate_offset', 'center', 'extents',
})
WATER_APPEARANCE_FIELDS = tuple(
    field for field in WATER_FIELDS if field[0] not in AUTOMATIC_WATER_FIELDS)


def water_settings(nwo):
    """Detach appearance settings; the exporter supplies evaluated mesh height."""
    settings = {'shader': nwo.halo2_water_shader}
    for suffix, field, kind, default in WATER_FIELDS:
        value = (default if suffix in AUTOMATIC_WATER_FIELDS else
                 getattr(nwo, 'halo2_water_' + suffix))
        settings[field] = tuple(value) if kind in {'color', 'vector'} else value
    return settings


def write_water_definition(path, tags_root, settings):
    """Sync an exported BSP's water; None removes a deleted Blender plane."""
    with TagDocument(path, tags_root=tags_root, game='halo2', must_exist=True) as tag:
        block = tag.block(tag.tag.root(), 'water definitions')
        if settings is None:
            if len(block):
                block.clear()
                tag.tag_has_changes = True
            return
        if not len(block):
            block.add()
        water = block[0]
        tag.set_reference(water, 'shader', settings['shader'] or None)
        for _, field, kind, _ in WATER_FIELDS:
            value = settings[field]
            if kind == 'color':
                value = tag.api.RealRgbColor(*value)
            elif kind == 'vector':
                value = tag.api.RealVector2d(*value)
            tag.required_field(water, field).set(value)
        tag.tag_has_changes = True

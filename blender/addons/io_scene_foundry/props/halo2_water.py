"""Object controls matching Halo 2's BSP water definition."""
import bpy

from .. import utils
from ..tags.halo2_water import WATER_APPEARANCE_FIELDS


def clean_water_shader(self, context):
    self['halo2_water_shader'] = utils.clean_tag_path(self['halo2_water_shader']).strip('"')


def halo2_water_properties():
    common = dict(options=set(), override={'LIBRARY_OVERRIDABLE'})
    properties = {'halo2_water_shader': bpy.props.StringProperty(
        name='Water Shader', description='Shader used by the Halo 2 BSP water definition',
        update=clean_water_shader, **common)}
    labels = {'sun_dir_heading': 'Sun Direction Heading', 'sun_dir_pitch': 'Sun Direction Pitch'}
    for suffix, field, kind, default in WATER_APPEARANCE_FIELDS:
        args = dict(common, name=labels.get(suffix, field.replace('_', ' ').title()), default=default)
        units = (' (radians)' if kind == 'angle' else
                 ' (Halo world units)' if kind in {'distance', 'vector'} else '')
        args['description'] = f'Halo 2 water definition: {field}{units}. Shared by all water in this BSP'
        if kind == 'color':
            prop = bpy.props.FloatVectorProperty(size=3, subtype='COLOR_GAMMA', min=0, max=1, **args)
        elif kind == 'vector':
            prop = bpy.props.FloatVectorProperty(size=2, **args)
        else:
            # Keep the raw numbers shown in the tag editor, independent of
            # Blender scene units and angle-display preferences.
            prop = bpy.props.FloatProperty(**args)
        properties['halo2_water_' + suffix] = prop
    return properties

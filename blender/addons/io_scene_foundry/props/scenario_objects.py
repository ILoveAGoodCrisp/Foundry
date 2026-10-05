"""Blender properties for the authored portion of scenario object schemas."""
from functools import lru_cache
import bpy
from .. import utils
from ..tags.backend import PROFILES
from ..tags.scenario_objects import object_types, object_fields, authored_default


def current_game():
    project = utils.get_project()
    return project.game if project else 'reach'


@lru_cache(maxsize=7)
def type_items(game):
    return [(row[0], row[3].replace('_', ' ').title(), '', i) for i, row in enumerate(object_types(game))]


def scenario_object_types(self, context):
    return type_items(current_game())


@lru_cache(maxsize=None)
def option_items(game, block, path, kind):
    field = next((f for f in object_fields(game, block) if f.path == path and f.kind == kind), None)
    return [(str(i), name.split('{')[0].title(), '', i) for i, name in enumerate(field.options)] if field else [('0', 'Default', '', 0)]


def enum_callback(field):
    def items(self, context):
        return option_items(current_game(), self.scenario_object_type, field.path, field.kind)
    return items


def variant_callback(field):
    def update(self, context):
        self.marker_game_instance_tag_variant_name = getattr(self, field.property_name())
    return update


def add_object_properties(cls):
    annotations = cls.__annotations__
    for game in PROFILES:
        for block, *_ in object_types(game):
            for field in object_fields(game, block):
                base = dict(name=field.path[-1].split('{')[0].title(), options=set())
                key = field.property_name()
                if field.kind.endswith('_flags'):
                    for name in field.options:
                        if name.lower().startswith(('unused', 'obsolete')):
                            continue
                        flag_key = field.property_name(name)
                        if flag_key not in annotations:
                            annotations[flag_key] = bpy.props.BoolProperty(name=name.split('{')[0].title(), options=set())
                    continue
                if key in annotations:
                    continue
                if field.kind.endswith('_enum'):
                    prop = bpy.props.EnumProperty(**base, items=enum_callback(field),
                        default=authored_default(field))
                elif field.kind in {'string', 'string_id'}:
                    if field.path[-1] == 'variant name':
                        base['update'] = variant_callback(field)
                    prop = bpy.props.StringProperty(**base)
                elif field.kind in {'rgb_color', 'real_rgb_color'}:
                    prop = bpy.props.FloatVectorProperty(**base, size=3, subtype='COLOR', min=0, max=1, default=(1, 1, 1))
                elif field.kind in {'real_bounds', 'angle_bounds', 'real_point_3d', 'real_vector_3d'}:
                    prop = bpy.props.FloatVectorProperty(**base, size=2 if 'bounds' in field.kind else 3,
                        subtype='EULER' if field.kind == 'angle_bounds' else 'NONE')
                elif field.kind in {'real', 'angle'}:
                    prop = bpy.props.FloatProperty(**base, default=authored_default(field), subtype='ANGLE' if field.kind == 'angle' else 'NONE')
                else:
                    size = 8 if field.kind.startswith('char') else 16 if field.kind.startswith('short') else 32
                    prop = bpy.props.IntProperty(**base, min=-(1 << (size - 1)), max=(1 << (size - 1)) - 1,
                        default=authored_default(field))
                annotations[key] = prop


def authored_options(nwo, game):
    result = {}
    for field in object_fields(game, nwo.scenario_object_type):
        if field.kind.endswith('_flags'):
            value = sum(1 << i for i, name in enumerate(field.options)
                        if not name.lower().startswith(('unused', 'obsolete')) and getattr(nwo, field.property_name(name)))
        else:
            value = getattr(nwo, field.property_name())
            if field.kind.endswith('_enum'):
                value = int(value)
            elif field.kind in {'rgb_color', 'real_rgb_color', 'real_bounds', 'angle_bounds', 'real_point_3d', 'real_vector_3d'}:
                value = tuple(value)
        result[field.path] = value
    return result

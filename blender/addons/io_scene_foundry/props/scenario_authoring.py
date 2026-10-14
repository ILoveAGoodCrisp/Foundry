"""Shared scenario authoring controls for the asset editor."""
from ..tags.scenario_objects import authoring_property, object_types


METADATA_PROPERTIES = (
    'player_starts_from_blender',
    'cutscene_flags_from_blender',
    'camera_points_from_blender',
)


def scenario_authoring_properties(settings):
    from .. import utils
    game = utils.get_game(settings.scene_project, use_external=False)
    properties = ['skies_authored_from_blender', 'decals_from_blender',
                  'decorators_from_blender', *METADATA_PROPERTIES]
    properties.extend(authoring_property(block) for block, *_ in object_types(game))
    if utils.supports_game_feature('airprobes', game):
        properties.append('airprobes_from_blender')
    return properties


def get_scenario_authoring_all(settings):
    return all(getattr(settings, prop) for prop in scenario_authoring_properties(settings))


def set_scenario_authoring_all(settings, enabled):
    for prop in scenario_authoring_properties(settings):
        setattr(settings, prop, enabled)


def scenario_metadata_enabled(settings):
    return any(getattr(settings, prop) for prop in METADATA_PROPERTIES)

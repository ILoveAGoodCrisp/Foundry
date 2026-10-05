"""Scenario marker authoring fields, taken from each engine's native schema."""
from functools import lru_cache
import json
from pathlib import Path

from .backend import PROFILES

MARKER_PREFIX = '_connected_geometry_marker_type_'
SCENARIO_MARKER_TYPES = ('decal', 'decorator', 'player_start', 'cutscene_flag')


def field_name(name):
    return (name or '').split(':')[0].split('#')[0].split('{')[0].rstrip('*!^~')


@lru_cache(maxsize=7)
def scenario_schema(game):
    return json.loads((Path(__file__).parent / 'definitions' / PROFILES[game] / 'scenario.json').read_text())


def block_definition(game, name):
    schema = scenario_schema(game)
    root = schema['structs'][schema['blocks'][schema['block']]['struct']]
    field = next(f for f in root['fields'] if f['type'] == 'block' and field_name(f['name']) == name)
    return schema['blocks'][field['definition']]


def block_fields(game, name):
    schema = scenario_schema(game)
    return {field_name(f['name']): f for f in schema['structs'][block_definition(game, name)['struct']]['fields']
            if f.get('name') and f['type'] not in ('pad', 'skip', 'custom', 'explanation')}


def enum_options(game, block, name):
    field = block_fields(game, block).get(name)
    if field is None:
        return ()
    return tuple(scenario_schema(game)['enums_flags'][field['definition']]['options'])


# Blender property -> native authored field. Transforms are handled separately.
PLAYER_FIELDS = {
    'player_start_team': 'team index',
    'player_start_team_designator': 'team designator',
    'scenario_bsp_index': 'bsp index',
    **{f'player_start_type_{i}': f'type {i}' for i in range(4)},
    **{f'player_start_spawn_type_{i}': f'spawn type {i}' for i in range(4)},
    'player_start_campaign_player': 'campaign player type',
    'player_start_insertion_point': 'insertion point index',
    'scenario_editor_folder': 'editor folder',
}

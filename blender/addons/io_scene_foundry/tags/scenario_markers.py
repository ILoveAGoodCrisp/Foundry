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
    **{f'player_start_type_{i}': f'type {i}' for i in range(4)},
    **{f'player_start_spawn_type_{i}': f'spawn type {i}' for i in range(4)},
    'player_start_campaign_player': 'campaign player type',
    'player_start_insertion_point': 'insertion point index',
    'scenario_editor_folder': 'editor folder',
}


def editor_folder_name(document, index):
    field = document.tag.root().field('editor folders')
    if field is None or not 0 <= index < len(field.as_block()):
        return ''
    rows, parts, visited = field.as_block(), [], set()
    while 0 <= index < len(rows):
        if index in visited:
            raise ValueError('Scenario editor folders contain a parent cycle')
        visited.add(index)
        row = rows[index]
        parts.append(str(document.value(row, 'name')))
        parent = row.field('parent folder')
        index = parent.value if parent is not None else -1
    return '/'.join(reversed(parts))


def editor_folder_index(document, name):
    """Resolve a folder name/path, coalescing duplicate named folders."""
    name = name.strip()
    if not name:
        return -1
    field = document.tag.root().field('editor folders')
    if field is None:
        raise ValueError(f'{document.game} does not support editor folders')
    rows = field.as_block()
    matches = [i for i in range(len(rows)) if editor_folder_name(document, i) == name]
    if matches:
        return matches[0]
    parent_name, _, leaf = name.rpartition('/')
    parent_index = editor_folder_index(document, parent_name) if parent_name else -1
    rows = document.block(document.tag.root(), 'editor folders')
    definition = block_fields(document.game, 'editor folders')['name']
    if not leaf or len(leaf.encode('utf-8')) >= definition.get('definition', 256):
        raise ValueError(f'Editor folder name is too long: {name!r}')
    if len(rows) >= block_definition(document.game, 'editor folders')['max_count']:
        raise ValueError('Too many editor folders')
    index = rows.add()
    row = document.block(document.tag.root(), 'editor folders')[index]
    document._set_value(row, 'name', leaf)
    if row.field('parent folder') is not None:
        document._set_value(row, 'parent folder', parent_index)
    return index

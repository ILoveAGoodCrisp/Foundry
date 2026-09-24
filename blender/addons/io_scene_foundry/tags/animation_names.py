"""Pure helpers for canonical animation graph paths and rename detection."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
import re


DAMAGE_STATES = ('h_ping', 's_ping', 'h_kill', 's_kill')
DIRECTIONS = ('front', 'left', 'right', 'back')
REGIONS = (
    'gut', 'chest', 'head', 'l_arm', 'l_hand', 'l_leg', 'l_foot',
    'r_arm', 'r_hand', 'r_leg', 'r_foot',
)

H1_MODE_CONVERSIONS = {
    'stand': 'combat',
    'b-driver': 'banshee_d',
    'w-driver': 'warthog_d',
    'w-gunner': 'warthog_g',
    'w-passenger': 'warthog_p',
    'scorpion-driver': 'scorpion_d',
    'gt-gunner': 'shade_g',
    'g-driver': 'ghost_d',
    'p-riderlb02': 'pelican_p_l05',
    'p-riderlb01': 'pelican_p_l04',
    'p-riderlb': 'pelican_p_l03',
    'p-riderlm': 'pelican_p_l02',
    'p-riderlf': 'pelican_p_l01',
    'p-riderrb02': 'pelican_p_r05',
    'p-riderrb01': 'pelican_p_r04',
    'p-riderrb': 'pelican_p_r03',
    'p-riderrm': 'pelican_p_r02',
    'p-riderrf': 'pelican_p_r01',
    'scorpionlf': 'scorpion_p_lf',
    'scorpionlb': 'scorpion_p_lb',
    'scorpionrf': 'scorpion_p_rf',
    'scorpionrb': 'scorpion_p_rb',
    'wraith-driver': 'wraith_d',
    'cd-passenger01': 'fork_p_r1',
    'cd-passengerl01': 'fork_p_l1',
}

H1_STATE_CONVERSIONS = {
    'aim-move': 'aim_move_up',
    'aim-still': 'aim_still_up',
}

H1_REGION_CONVERSIONS = {
    'l-thigh': 'l_leg',
    'r-thigh': 'r_leg',
}

LEGACY_GAMES = {'halo1', 'halo2', 'halo3', 'halo3odst'}
REACH_PLUS_GAMES = {'reach', 'halo4', 'halo2a'}


def convert_animation_name_for_project(
        name: str, source_game: str, target_game: str) -> str:
    """Convert legacy animation-name tokens to the target project's style."""
    if not name:
        return name

    h1_to_h2 = source_game == 'halo1' and target_game != 'halo1'
    legacy_to_reach = (source_game in LEGACY_GAMES and
                       target_game in REACH_PLUS_GAMES)
    if not h1_to_h2 and not legacy_to_reach:
        return name

    variant = None
    variant_match = re.search(r'%([0-9]+)$', name) if h1_to_h2 else None
    if variant_match is not None:
        variant = variant_match.group(1)
        name = name[:variant_match.start()]

    parts = re.split(r'([ :]+)', name)
    tokens = parts[::2]
    transition_index = next(
        (index for index, token in enumerate(tokens) if token == '2'), None)
    mode_indices = {1 if tokens and tokens[0].casefold() == 'stance' else 0}
    state_indices = {len(tokens) - 1}
    if transition_index is not None:
        if transition_index > 0:
            state_indices.add(transition_index - 1)
        if transition_index + 1 < len(tokens):
            mode_indices.add(transition_index + 1)

    for token_index, part_index in enumerate(range(0, len(parts), 2)):
        token = parts[part_index]
        key = token.casefold()
        if h1_to_h2:
            if token_index in mode_indices:
                token = H1_MODE_CONVERSIONS.get(key, token)
            if token_index in state_indices:
                token = H1_STATE_CONVERSIONS.get(key, token)
            token = H1_REGION_CONVERSIONS.get(key, token)
            token = token.replace('-', '_')
            key = token.casefold()
        if legacy_to_reach and key == 'berserk':
            token = 'go_berserk'
        parts[part_index] = token

    converted = ''.join(parts)
    if variant is not None:
        separator = ':' if ':' in converted and ' ' not in converted else ' '
        converted = f'{converted}{separator}var{variant}'
    return converted


def _strip_trailing_any(tokens: list[str]) -> list[str]:
    while tokens and tokens[-1] == 'any':
        tokens.pop()
    return tokens


def minimal_animation_path(tokens: Iterable[str]) -> list[str]:
    """Remove variants and redundant trailing ``any`` graph levels."""
    tokens = [token for token in tokens
              if not (token.startswith('var') and token[3:].isdigit())]
    if not tokens:
        return []

    if len(tokens) >= 5 and tokens[-3] == '2':
        base, tail = tokens[:-4], tokens[-4:]
        return _strip_trailing_any(base) + tail

    if (len(tokens) >= 5
            and tokens[-3] in DAMAGE_STATES
            and tokens[-2] in DIRECTIONS
            and tokens[-1] in REGIONS):
        base, tail = tokens[:-3], tokens[-3:]
        return _strip_trailing_any(base) + tail

    head, state = tokens[:-1], tokens[-1:]
    return _strip_trailing_any(head) + state


def normalized_animation_graph_path(path: str) -> str:
    tokens = [token for token in (path or '').replace(' ', ':').split(':')
              if token]
    return ':'.join(minimal_animation_path(tokens))


def renames_from_paths(
        name_to_paths: Mapping[str, Iterable[str]]) -> list[tuple[str, str]]:
    """Return noncanonical paths for animations used by multiple graph states."""
    renames: list[tuple[str, str]] = []
    for animation_name, paths in name_to_paths.items():
        paths = list(paths)
        if len(paths) < 2:
            continue
        canonical_source = normalized_animation_graph_path(animation_name)
        seen: set[str] = set()
        for path in paths:
            rename = normalized_animation_graph_path(path)
            if rename and rename != canonical_source and rename not in seen:
                renames.append((animation_name, rename))
                seen.add(rename)
    return renames


def detect_renames(graph: dict[str, object]) -> list[tuple[str, str]]:
    """Collect rename pairs from the legacy detached graph representation."""
    name_to_paths: dict[str, list[str]] = defaultdict(list)

    def walk(path_tokens: list[str], node: dict[str, object]) -> None:
        for category in ('actions', 'overlay_animations', 'transitions',
                         'death_and_damage'):
            category_data = node.get(category)
            if not isinstance(category_data, dict):
                continue
            if category in ('actions', 'overlay_animations'):
                for state, animation in category_data.items():
                    name_to_paths[animation.name.tag_name].append(
                        ':'.join(path_tokens + [state]))
            elif category == 'transitions':
                for state, destinations in category_data.items():
                    for destination, animation in destinations.items():
                        name_to_paths[animation.name.tag_name].append(
                            ':'.join(path_tokens + [state, destination]))
            else:
                for damage_state, directions in category_data.items():
                    for direction, regions in directions.items():
                        for region, animation in regions.items():
                            name_to_paths[animation.name.tag_name].append(
                                ':'.join(path_tokens + [damage_state, direction,
                                                        region]))

        categories = {'actions', 'overlay_animations', 'transitions',
                      'death_and_damage'}
        for name, child in node.items():
            if isinstance(child, dict) and name not in categories:
                walk(path_tokens + [name], child)

    walk([], graph)
    return renames_from_paths(name_to_paths)


def animation_rename_map(graph: dict[str, object]) -> dict[str, set[str]]:
    renames_by_name: dict[str, set[str]] = defaultdict(set)
    for source_name, rename in detect_renames(graph):
        normalized = normalized_animation_graph_path(rename)
        if normalized:
            renames_by_name[source_name].add(normalized)
    return dict(renames_by_name)

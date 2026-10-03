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

BUNKER_MODE_CONVERSIONS = {
    'bunker_cover': 'center_crouch_closed',
    'bunker_open': 'center_crouch_open',
    'corner_cover_left': 'left_stand_closed',
    'corner_open_left': 'left_stand_open',
    'corner_cover_right': 'right_stand_closed',
    'corner_open_right': 'right_stand_open',
}


def _convert_bunker_name(name: str, *, to_reach: bool) -> str:
    tokens = re.split(r'[ :]+', name.strip(' :'))
    keys = [token.casefold() for token in tokens]
    converted = None
    if to_reach and len(tokens) >= 2 and keys[0] in BUNKER_MODE_CONVERSIONS:
        bunker_set = BUNKER_MODE_CONVERSIONS[keys[0]]
        tail = tokens[2:]
        # H2+ switches modes with idle transitions; Reach uses set actions.
        if keys == ['bunker_cover', keys[1], 'idle', '2', 'bunker_open', 'idle']:
            tail = ['open']
        elif keys == ['bunker_open', keys[1], 'idle', '2', 'bunker_cover', 'idle']:
            tail = ['close']
        elif '2' in tail:
            return name
        converted = ['bunker', tokens[1], 'any', bunker_set] + tail
    elif (not to_reach and len(tokens) >= 4 and keys[0] == 'bunker'
          and keys[2] == 'any'):
        legacy_mode = {value: key for key, value in BUNKER_MODE_CONVERSIONS.items()}.get(keys[3])
        if legacy_mode is not None:
            tail = tokens[4:]
            if keys[3:] == ['center_crouch_closed', 'open']:
                tail = ['idle', '2', 'bunker_open', 'idle']
            elif keys[3:] == ['center_crouch_open', 'close']:
                tail = ['idle', '2', 'bunker_cover', 'idle']
            converted = [legacy_mode, tokens[1]] + tail
    if converted is None:
        return name
    separator = ':' if ':' in name and ' ' not in name else ' '
    trailing = name[len(name.rstrip(' :')):]
    return separator.join(converted) + trailing


def _convert_h1_mode(token: str, *, to_h1: bool = False) -> str:
    if to_h1:
        key = token.casefold()
        converted = {value: name for name, value in H1_MODE_CONVERSIONS.items()}.get(key)
        if converted is not None:
            return converted
        seat = re.fullmatch(r'fork_p_([lr])([0-9]+)', key)
        if seat is not None:
            return f'cd-passenger{seat[1]}{int(seat[2]):02d}'
        return token.replace('_', '-')

    # Graph seat labels can use underscores even when animation names use
    # hyphens. Apply the same mapping to both spellings, including aliases for
    # numbered passenger seats beyond the first one.
    key = token.casefold().replace('_', '-')
    converted = H1_MODE_CONVERSIONS.get(key)
    if converted is not None:
        return converted
    seat = re.fullmatch(r'cd-passenger([lr]?)([0-9]+)', key)
    if seat is not None:
        return f'fork_p_{seat[1] or "r"}{int(seat[2])}'
    return token


def convert_animation_name_for_project(
        name: str, source_game: str, target_game: str) -> str:
    """Convert animation-name tokens in either direction between game styles."""
    if not name:
        return name

    h1_to_h2 = source_game == 'halo1' and target_game != 'halo1'
    to_h1 = source_game != 'halo1' and target_game == 'halo1'
    legacy_to_reach = (source_game in LEGACY_GAMES and
                       target_game in REACH_PLUS_GAMES)
    reach_to_legacy = (source_game in REACH_PLUS_GAMES and target_game in LEGACY_GAMES)
    if not any((h1_to_h2, to_h1, legacy_to_reach, reach_to_legacy)):
        return name

    variant = None
    variant_match = re.search(r'%([0-9]+)$', name) if h1_to_h2 else None
    if variant_match is not None:
        variant = variant_match.group(1)
        name = name[:variant_match.start()]
    later_variant = re.search(r'([ :]+)var([0-9]+)$', name, re.IGNORECASE)
    variant_suffix = ''
    if later_variant is not None:
        variant_suffix = name[later_variant.start():]
        name = name[:later_variant.start()]
        if to_h1:
            variant = later_variant.group(2)
            variant_suffix = ''

    parts = re.split(r'([ :]+)', name)
    tokens = parts[::2]
    transition_index = next(
        (index for index, token in enumerate(tokens) if token == '2'), None)
    mode_indices = {1 if tokens and tokens[0].casefold() == 'stance' else 0}
    state_indices = {len(tokens) - 1}
    damage = (len(tokens) >= 3 and tokens[-3].lower().replace('-', '_') in DAMAGE_STATES
              and tokens[-2].lower() in DIRECTIONS)
    if damage:
        state_indices = {len(tokens) - 3}
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
                token = _convert_h1_mode(token)
            if token_index in state_indices:
                token = H1_STATE_CONVERSIONS.get(key.replace('_', '-'), token)
            token = H1_REGION_CONVERSIONS.get(key.replace('_', '-'), token)
            token = token.replace('-', '_')
            key = token.casefold()
        if legacy_to_reach and key == 'berserk' and token_index in state_indices:
            token = 'go_berserk'
        elif reach_to_legacy and key == 'go_berserk' and token_index in state_indices:
            token = 'berserk'
        if to_h1:
            if token_index in mode_indices:
                token = _convert_h1_mode(token, to_h1=True)
            if token_index in state_indices:
                token = {value: key for key, value in H1_STATE_CONVERSIONS.items()}.get(key, token)
                token = token.replace('_', '-')
            if damage and token_index == len(tokens) - 1:
                token = {value: key for key, value in H1_REGION_CONVERSIONS.items()}.get(key, token)
                token = token.replace('_', '-')
        parts[part_index] = token

    converted = ''.join(parts)
    if legacy_to_reach and source_game != 'halo1':
        converted = _convert_bunker_name(converted, to_reach=True)
    elif reach_to_legacy and target_game != 'halo1':
        converted = _convert_bunker_name(converted, to_reach=False)
    if variant is not None:
        if to_h1:
            converted = f'{converted}%{variant}'
        else:
            separator = ':' if ':' in converted and ' ' not in converted else ' '
            converted = f'{converted}{separator}var{variant}'
    return converted + variant_suffix


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


def animation_name_key(name: str) -> str:
    """Compare names across UI/tag separators, whitespace and letter casing."""
    return ':'.join((name or '').replace(':', ' ').split()).casefold()


def renames_from_paths(
        name_to_paths: Mapping[str, Iterable[str]]) -> list[tuple[str, str]]:
    """Return distinct noncanonical graph paths for each animation."""
    renames: list[tuple[str, str]] = []
    for animation_name, paths in name_to_paths.items():
        canonical_source = animation_name_key(normalized_animation_graph_path(animation_name))
        seen: set[str] = set()
        for path in paths:
            rename = normalized_animation_graph_path(path)
            key = animation_name_key(rename)
            if key and key != canonical_source and key not in seen:
                renames.append((animation_name, rename))
                seen.add(key)
    return renames


def copies_from_paths(
        name_to_paths: Mapping[str, Iterable[str]],
        ) -> list[tuple[str, str, frozenset[tuple[str, str]]]]:
    """Find complete hierarchy copies among graph aliases.

    The first four path components are mode, class, type and set. A copy is
    inferred only when at least two distinct source animations have canonical
    paths in the source subtree and *every* such path occurs in the destination
    subtree with the same animation index/name and unchanged remainder.
    """
    paths: dict[tuple[str, ...], set[str]] = defaultdict(set)
    canonical: dict[tuple[str, ...], str] = {}
    paths_by_name: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for name, graph_paths in name_to_paths.items():
        normalized_name = normalized_animation_graph_path(name)
        for path in graph_paths:
            tokens = tuple(token for token in path.replace(' ', ':').split(':') if token)
            if len(tokens) < 5:
                continue
            paths[tokens].add(name)
            paths_by_name[name].add(tokens)
            if normalized_animation_graph_path(path) == normalized_name:
                canonical[tokens] = name

    source_groups: dict[tuple[int, tuple[str, ...]], dict[tuple[str, ...], set[str]]] = defaultdict(dict)
    for path, names in paths.items():
        for depth in range(1, 5):
            source_groups[depth, path[:depth]][path] = names

    candidates = set()
    for source_path, source_name in canonical.items():
        for destination_path in paths_by_name[source_name]:
            for depth in range(1, 5):
                source_prefix = source_path[:depth]
                destination_prefix = destination_path[:depth]
                if (source_prefix == destination_prefix or
                        source_path[depth:] != destination_path[depth:]):
                    continue
                members = source_groups[depth, source_prefix]
                if len(set().union(*members.values())) < 2:
                    continue
                if any(paths.get(destination_prefix + path[depth:]) != names
                       for path, names in members.items()):
                    continue
                covered = frozenset(
                    (name, normalized_animation_graph_path(
                        ':'.join(destination_prefix + path[depth:])))
                    for path, names in members.items() for name in names)
                if not covered:
                    continue
                source_copy = ' '.join(source_prefix + ('any',) * (4 - depth))
                destination_copy = ' '.join(destination_prefix + ('any',) * (4 - depth))
                candidates.add((depth, source_copy, destination_copy, covered))

    result = []
    claimed: set[tuple[str, str]] = set()
    for _, source, destination, covered in sorted(
            candidates, key=lambda item: (item[0], -len(item[3]), item[1], item[2])):
        if covered & claimed:
            continue
        result.append((source, destination, covered))
        claimed.update(covered)
    return result


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

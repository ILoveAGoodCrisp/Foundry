"""Pure helpers for canonical animation graph paths and rename detection."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping


DAMAGE_STATES = ('h_ping', 's_ping', 'h_kill', 's_kill')
DIRECTIONS = ('front', 'left', 'right', 'back')
REGIONS = (
    'gut', 'chest', 'head', 'l_arm', 'l_hand', 'l_leg', 'l_foot',
    'r_arm', 'r_hand', 'r_leg', 'r_foot',
)


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

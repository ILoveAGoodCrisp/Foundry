"""Conservative Reach/H4/H2AMP overlay planning and native tag application.

No Blender dependency. Existing authored records are authoritative. Generated
records are updated only while their last saved snapshot still matches. We never
compact the definition tables: every external block index therefore stays stable.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import struct
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import blam_tags

GAMES = frozenset({'reach', 'halo4', 'halo2a'})
SCREENS = 'NEW blend screens'
FUNCTIONS = 'NEW function overlays'
GROUPS = 'overlay groups'
TABLES = (SCREENS, FUNCTIONS, GROUPS)
PAIN_REGIONS = ('gut', 'chest', 'head', 'left_shoulder', 'right_shoulder',
                'left_arm', 'right_arm', 'left_leg', 'right_leg', 'left_foot', 'right_foot')
LIMITS = {SCREENS: 1024, FUNCTIONS: 32, GROUPS: 1056}


def key(name: str) -> str:
    return ':'.join(name.replace(':', ' ').split()).casefold()


def animation_path(name: str) -> tuple[str, ...] | None:
    """Expand known source naming forms without splitting underscores or losing any."""
    parts = key(name).split(':')
    if parts[-1].startswith('var') and parts[-1][3:].isdigit():
        parts.pop()
    if not 2 <= len(parts) <= 5:
        return None
    if parts[0] in {'first_person', 'vehicle', 'weapon', 'device'}:
        if len(parts) == 2:
            return ('any', 'any', 'any', 'any', parts[-1])
        if parts[:2] == ['first_person', 'dual'] and len(parts) == 3:
            return ('any', 'any', 'any', 'dual', parts[-1])
        return None
    return tuple(parts[:-1] + ['any'] * (5 - len(parts)) + parts[-1:])


def role(state: str) -> str | None:
    if state in {'acc', 'acceleration', 'acceleration_screens'}:
        return 'acc'
    if state in {'steer', 'steering'}:
        return 'steering'
    if state in {'aim', 'vehicle_aiming'}:
        return 'aiming'
    if state == 'throttle':
        return 'throttle'
    if state in {'look', 'aiming', 'pitch_and_turn', 'position_offset'}:
        return state
    for prefix in ('aim_', 'look_', 'throttle_', 'defense_', 'pill_fix_'):
        if state.startswith(prefix):
            return prefix[:-1]
    if state.startswith('pain_') and any(state.endswith('_' + r) for r in PAIN_REGIONS):
        return 'pain'
    return None


def screen_settings(state: str, profile: str) -> dict:
    kind = role(state)
    yaw = pitch = weight = 'none'
    rate = 0.0
    flags = []
    function = ''
    if kind in {'aim', 'aiming', 'pill_fix'}:
        yaw, pitch = 'aim yaw', 'aim pitch'
        if kind == 'pill_fix':
            weight, function = 'object function', 'pill_fix'
        elif state.endswith(('_in', '_out')):
            weight = 'object function'
            function = 'animation_event_function_' + ('c' if state.endswith('_in') else 'd')
    elif kind == 'look':
        yaw, pitch = 'look yaw', 'look pitch'
        flags.append('allow parent adjustment')
        if profile == 'first_person':
            rate = 0.5
        else:
            weight, function = 'object function', 'impulse_channel_valid_inverted'
    elif kind == 'acc':
        yaw, pitch, weight = 'acceleration yaw', 'acceleration pitch', 'acceleration magnitude'
        rate = 0.0 if profile == 'vehicle' else 0.333
        if profile == 'first_person':
            yaw, pitch = 'throttle side', 'throttle_forward'
    elif kind == 'steering':
        yaw = pitch = 'steering'
        rate = 0.33
    elif kind == 'throttle':
        yaw, pitch, rate = 'throttle side', 'throttle_forward', 0.1
        if profile == 'vehicle' and state == 'throttle':
            yaw = 'none'
    elif kind == 'defense':
        yaw, pitch, weight, rate = 'defense yaw', 'defense pitch', 'defense', 0.25
    elif kind == 'pain':
        region = next(r for r in PAIN_REGIONS if state.endswith('_' + r)).replace('_', ' ')
        yaw, pitch, weight, rate = f'damage {region} yaw', f'damage {region} pitch', f'damage {region}', 0.333
    elif kind == 'pitch_and_turn':
        yaw, pitch = 'first person turn', 'first person pitch'
    if state.endswith('_down'):
        flags.append('active only when weapon down')
    if state == 'aiming':
        flags.append('attempt piece-wise blending')
    return {'flags': flags, 'weight': 0.0, 'interpolation rate': rate,
            'yaw source': yaw, 'pitch source': pitch, 'weight source': weight,
            'yaw source object function': '', 'pitch source object function': '',
            'weight source object function': function, 'weight function': -1}


def snapshot(struct) -> dict:
    result = {}
    for f in struct.fields():
        name = f.clean_name
        if not name:
            continue
        if f.type_name == 'struct':
            result[name] = snapshot(f.as_struct())
        elif f.type_name in {'block', 'array'}:
            block = f.as_block() if f.type_name == 'block' else f.as_array()
            result[name] = [snapshot(x) for x in block]
        elif f.type_name not in {'data', 'pageable resource'}:
            value = f.value
            result[name] = value.to_array() if hasattr(value, 'to_array') else value
    return result


@dataclass
class Graph:
    game: str
    tables: dict[str, list[dict]]
    animations: list[tuple[str, str]]
    # label path, native field path, current group; includes every hierarchy level.
    bindings: list[tuple[tuple[str, ...], str, int]]
    overlays: dict[tuple[str, ...], list[dict]]
    masks: list[str]
    functions: list[str]
    suspension: list[dict]


def read_graph(tag, game: str) -> Graph:
    if game not in GAMES:
        raise ValueError(f'Overlay group setup is unavailable for {game}')
    definitions = tag.root().descend('definitions')
    tables = {name: [snapshot(e) for e in definitions.field(name).as_block()] for name in TABLES}
    animations = []
    for e in definitions.field('animations').as_block():
        f = e.field('shared animation data')
        shared = f.as_struct() if f.type_name == 'struct' else next(iter(f.as_block()), None)
        kind = shared.field('animation type').value if shared else ''
        animations.append((e.field('name').value, kind))
    bindings = []
    overlays = defaultdict(list)

    def visit(struct, labels, path, level):
        group = struct.field('overlay group')
        if group is not None:
            bindings.append((labels, path + '/overlay group', int(group.value)))
        if level == 4:
            for e in struct.field('overlay animations').as_block():
                overlays[labels + (key(e.field('label').value),)].append(snapshot(e.field('animation').as_struct()))
        children = ('modes', 'weapon class', 'weapon type', 'sets', 'actions')
        if level < len(children):
            name = children[level]
            for i, e in enumerate(struct.field(name).as_block()):
                visit(e, labels + (key(e.field('label').value),), f'{path}/{name}[{i}]', level + 1)

    visit(tag.root().descend('content'), (), 'content', 0)
    return Graph(game, tables, animations, bindings, dict(overlays),
                 [e.field('name').value for e in definitions.field('node masks').as_block()],
                 [e.field('name').value for e in definitions.field('functions').as_block()],
                 [snapshot(e) for e in tag.root().descend('content').field('vehicle suspension').as_block()])


@dataclass
class Plan:
    tables: dict[str, list[dict]]
    updates: dict[str, dict[int, dict]] = field(default_factory=lambda: {n: {} for n in TABLES})
    bindings: dict[str, int] = field(default_factory=dict)
    owned: dict[str, set[str]] = field(default_factory=lambda: {n: set() for n in TABLES})
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self):
        return bool(self.bindings or any(self.updates.values()))


def detect_profile(graph: Graph) -> str:
    names = [key(n) for n, _ in graph.animations]
    generic_modes = all(p[0] == 'any' for p, _, _ in graph.bindings)
    # Character graphs can also carry a few first-person source animations.
    if generic_modes and any(n.startswith('first_person:') for n in names):
        return 'first_person'
    if graph.suspension or any(n.startswith('vehicle:') for n in names):
        return 'vehicle'
    # A mode-level vehicle group is useful evidence, but arbitrary character
    # functions are not. Do not classify character vehicle-seat animations here.
    if generic_modes and any(
            role(n.rsplit(':', 1)[-1]) == 'steering' for n in names):
        return 'vehicle'
    return 'character'


def action_states(action: str, game: str) -> list[str]:
    if action in {'idle', 'idle_reset', 'locomote_walk_inplace'}:
        return ['still']
    if action in {'airborne', 'airborne_arc'}:
        return ['airborne_arc']
    if action in {'enter', 'exit', 'open', 'close', 'board', 'enter_long'}:
        return [action]
    if action in {'turn_left_composite', 'turn_right_composite'}:
        return ['turn'] if game != 'reach' else []
    state = re.sub(r'_(slow|fast|intermediate)$', '', action)
    if state.startswith('jog_'):
        state = 'move_' + state[4:]
    return [state]


def build_plan(graph: Graph, *, pose_names=(), profile='auto', previous=None, overrides=None) -> Plan:
    """Compute additions/owned updates; do not mutate the graph or existing tag."""
    if graph.game not in GAMES:
        raise ValueError(f'Unsupported overlay game: {graph.game}')
    if profile not in {'auto', 'character', 'first_person', 'vehicle'}:
        raise ValueError(f'Unknown overlay profile: {profile}')
    profile = detect_profile(graph) if profile == 'auto' else profile
    previous = previous or {}
    overrides = overrides or {}
    if not isinstance(overrides, dict) or any(not isinstance(v, dict) for v in overrides.values()):
        raise ValueError('Overlay overrides must contain objects named screens, functions and groups')
    for section, entries in overrides.items():
        if any(not isinstance(name, str) or not isinstance(value, dict) for name, value in entries.items()):
            raise ValueError(f'Overlay {section} overrides must map names to settings objects')
    unknown = set(overrides) - {'screens', 'functions', 'groups'}
    if unknown:
        raise ValueError(f'Unknown overlay override sections: {sorted(unknown)}')
    plan = Plan(deepcopy(graph.tables))
    tables = plan.tables
    names = {n: defaultdict(list) for n in TABLES}
    for table in TABLES:
        for i, record in enumerate(tables[table]):
            names[table][key(record['name'])].append(i)
            old = previous.get(table, {}).get(record['name'])
            if old == record:
                plan.owned[table].add(record['name'])
            elif old is not None:
                plan.warnings.append(f'{table}: preserved edited record {record["name"]!r}')
    current_bindings = defaultdict(set)
    for path, _, index in graph.bindings:
        if 0 <= index < len(tables[GROUPS]):
            current_bindings[tables[GROUPS][index]['name']].add(':'.join(path))
    for name in tuple(plan.owned[GROUPS]):
        prior_paths = {path for path, group in previous.get('_bindings', {}).items() if group == name}
        if current_bindings[name] != prior_paths:
            plan.owned[GROUPS].remove(name)
            plan.warnings.append(f'Group {name!r}: preserved changed graph assignments')
    source_names = defaultdict(list)
    for i, (name, kind) in enumerate(graph.animations):
        source_names[key(name)].append(i)
    explicit_pose = {key(n) for n in pose_names}

    def valid(ref):
        # Nonlocal references remain paired with their graph. New inherited
        # records require an existing screen; we never index the local table.
        return ref['graph index'] == -1 and 0 <= ref['animation'] < len(graph.animations)

    def put(table, record, index=None, own=True):
        # Native real fields are f32. Compare their stored representation so
        # interpolation defaults such as .333 do not dirty every subsequent run.
        record = {k: struct.unpack('<f', struct.pack('<f', v))[0] if isinstance(v, float) else v
                  for k, v in record.items()}
        if index is None:
            index = len(tables[table])
            if index >= LIMITS[table]:
                raise ValueError(f'{table}: exceeds {LIMITS[table]} records')
            tables[table].append(record)
            names[table][key(record['name'])].append(index)
        elif tables[table][index] == record:
            return index
        else:
            tables[table][index] = record
        plan.updates[table][index] = deepcopy(record)
        if own:
            plan.owned[table].add(record['name'])
        plan.messages.append(f'{table}[{index}]: {record["name"]}')
        return index

    # Repair only unambiguous missing LOCAL references. Preserve all settings and
    # every table index, including unrelated unresolved legacy placeholders.
    for i, screen in enumerate(tables[SCREENS]):
        ref = screen['animation']
        if ref['graph index'] == -1 and not valid(ref):
            matches = [a for a in source_names[key(screen['name'])] if graph.animations[a][1] == 'overlay']
            if len(matches) == 1:
                repaired = deepcopy(screen)
                repaired['animation']['animation'] = matches[0]
                put(SCREENS, repaired, i, own=screen['name'] in plan.owned[SCREENS])
                # Authored settings/unknown flags need not be rewritten to fix
                # a reference. Preserve their original bytes exactly.
                plan.updates[SCREENS][i] = {'animation': repaired['animation']}
            else:
                plan.warnings.append(f'Blend screen {screen["name"]!r}: unresolved animation {ref}; preserved')

    candidates = defaultdict(list)
    # Explicit graph aliases win over source-name inference at the same path.
    for path, refs in graph.overlays.items():
        if role(path[-1]):
            candidates[path] = [(ref, True) for ref in refs]
    for i, (name, kind) in enumerate(graph.animations):
        path = animation_path(name)
        if kind == 'overlay' and path and (role(path[-1]) or key(name) in explicit_pose):
            if path not in candidates:
                candidates[path].append(({'graph index': -1, 'animation': i}, False))
            elif not any(alias for _, alias in candidates[path]):
                candidates[path].append(({'graph index': -1, 'animation': i}, False))

    cache = {}

    def select(context, state):
        paths = [context + (state,)]
        # The literal any levels are explicit, ordered fallback contexts. Never
        # search a sibling weapon, mode or set by substring similarity.
        for pos in (3, 2, 1):
            base = list(paths[-1][:-1])
            base[pos] = 'any'
            path = tuple(base) + (state,)
            if path not in paths:
                paths.append(path)
        for path in paths:
            options = candidates.get(path, [])
            refs = {tuple(sorted(ref.items())) for ref, _ in options}
            if len(refs) > 1:
                plan.warnings.append(f'{":".join(path)}: ambiguous animation sources; skipped')
                return None
            if refs:
                return path, dict(next(iter(refs)))
        return None

    def ensure_screen(selection, *, pill=False):
        path, ref = selection
        state = path[-1]
        cache_key = (path, tuple(sorted(ref.items())), pill)
        if cache_key in cache:
            return cache[cache_key]
        requested = ':'.join(path)
        weighted_variant = pill and role(state) == 'aim' and state.endswith('_up')
        generated_name = requested + ':pill_fix' if weighted_variant else requested
        if ref['animation'] < 0 or (ref['graph index'] == -1 and not valid(ref)):
            plan.warnings.append(f'{requested}: unresolved animation {ref}; skipped')
            cache[cache_key] = None
            return None
        expected = screen_settings(state, profile)
        if weighted_variant:
            expected.update({'weight source': 'object function', 'weight source object function': 'pill_fix_inverted'})
        expected['weight function'] = graph.functions.index(state) if state in graph.functions else -1
        config = overrides.get('screens', {}).get(requested, {})
        if set(config) - set(expected):
            raise ValueError(f'{requested}: unknown screen settings {sorted(set(config) - set(expected))}')
        expected.update(config)
        owned_matches = [i for i, s in enumerate(tables[SCREENS])
                         if (key(s['name']) == generated_name or (not weighted_variant and animation_path(s['name']) == path))
                         and s['name'] in plan.owned[SCREENS]]
        if len(owned_matches) == 1 and valid(ref):
            i = owned_matches[0]
            put(SCREENS, dict(expected, name=tables[SCREENS][i]['name'], animation=ref), i)
            cache[cache_key] = i
            return i
        # First prefer an exact semantic alias; then a source screen with the
        # same role. Short/arbitrary authored names are supported via reference.
        exact, reused = [], []
        for i, screen in enumerate(tables[SCREENS]):
            if screen['animation'] != ref:
                continue
            if (screen['name'] in plan.owned[SCREENS] and
                    screen['weight source object function'] != expected['weight source object function']):
                continue
            sp = animation_path(screen['name'])
            semantic = sp[-1] if sp else key(screen['name'])
            source = animation_path(graph.animations[ref['animation']][0]) if valid(ref) else None
            if key(screen['name']) == requested or sp == path:
                exact.append(i)
            elif (semantic == state or (not role(semantic) and source and source[-1] == state)
                  or (profile == 'first_person' and role(semantic) == role(state))):
                reused.append(i)
        options = exact or reused
        if len(options) > 1:
            # Identical settings may be safely shared; distinct authored screens
            # require a graph-specific alias rather than choosing by list order.
            signatures = {json.dumps({k: v for k, v in tables[SCREENS][i].items() if k != 'name'}, sort_keys=True) for i in options}
            if len(signatures) > 1:
                plan.warnings.append(f'{requested}: multiple authored screens; skipped')
                cache[cache_key] = None
                return None
        if options:
            index = options[0]
            screen = tables[SCREENS][index]
            if screen['name'] in plan.owned[SCREENS]:
                put(SCREENS, dict(expected, name=screen['name'], animation=ref), index)
            cache[cache_key] = index
            return index
        if not valid(ref) or graph.animations[ref['animation']][1] != 'overlay':
            plan.warnings.append(f'{requested}: unresolved/non-overlay source {ref}; skipped')
            cache[cache_key] = None
            return None
        if names[SCREENS].get(generated_name):
            plan.warnings.append(f'{requested}: existing screen has a different source; preserved')
            cache[cache_key] = None
            return None
        index = put(SCREENS, dict(expected, name=generated_name, animation=ref))
        cache[cache_key] = index
        return index

    def members(selections):
        has_pill = any(role(path[-1]) == 'pill_fix' for path, _ in selections)
        result = []
        for selection in selections:
            i = ensure_screen(selection, pill=has_pill)
            if i is not None and all(e['blend screen'] != i for e in result):
                result.append({'blend screen': i, 'flags': [], 'node mask': -1})
        has_look = any(tables[SCREENS][e['blend screen']]['yaw source'] == 'look yaw' for e in result)
        if profile == 'character' and has_look and graph.masks.count('look') == 1:
            for e in result:
                s = tables[SCREENS][e['blend screen']]
                if s['yaw source'] == 'aim yaw' and s['pitch source'] == 'aim pitch':
                    e['node mask'] = graph.masks.index('look')
        return result

    binding_map = {path: index for path, _, index in graph.bindings}

    def bind(path, native_path, old_index, screens, functions=()):
        if len(screens) > 10 or len(functions) > 32:
            raise ValueError(f'{":".join(path)}: {len(screens)} screens/{len(functions)} functions exceed group limits (10/32)')
        if not screens and not functions:
            if 0 <= old_index < len(tables[GROUPS]):
                old = tables[GROUPS][old_index]
                if old['name'] in plan.owned[GROUPS]:
                    put(GROUPS, dict(old, **{'blend screens': [], 'function overlays': []}), old_index)
                    plan.bindings[native_path] = -1
                    plan.messages.append(f'{":".join(path)}: removed unavailable generated overlays')
            return
        if 0 <= old_index < len(tables[GROUPS]):
            old = tables[GROUPS][old_index]
            if old['name'] not in plan.owned[GROUPS]:
                return
            name = old['name']
            index = old_index
        else:
            # A broader authored assignment is intentional. Do not shadow it
            # with a generated action group or flatten the graph hierarchy.
            if any(0 <= binding_map.get(path[:n], -1) < len(tables[GROUPS]) for n in range(1, len(path))):
                return
            name = 'foundry:' + ':'.join(path)
            found = names[GROUPS].get(key(name), [])
            if found:
                if len(found) != 1 or name not in plan.owned[GROUPS]:
                    plan.warnings.append(f'{name}: authored name collision; skipped')
                    return
                index = found[0]
            else:
                index = None
        record = {'name': name, 'blend screens': screens, 'function overlays': list(functions)}
        index = put(GROUPS, record, index)
        if old_index != index:
            plan.bindings[native_path] = index
            plan.messages.append(f'{":".join(path)} -> {name}')

    # Create only explicitly mapped functions. Suspension mappings are backed by
    # the actual exported suspension block, not a substring in an animation name.
    function_configs = dict(overrides.get('functions', {}))
    suspension_refs = set()
    if profile == 'vehicle':
        for suspension in graph.suspension:
            label = suspension.get('label', '')
            source = suspension.get('animation')
            if source and valid(source):
                suspension_refs.add(source['animation'])
                source_name = graph.animations[source['animation']][0]
            else:
                source_name = label
            channel = key(label).replace(':', '_')
            if channel.startswith('suspension_'):
                function_configs.setdefault(source_name, {'frame ratio object function': channel + '_interpolated'})
    for name, config in sorted(function_configs.items()):
        matches = source_names[key(name)]
        if len(matches) != 1:
            plan.warnings.append(f'Function overlay {name!r}: source missing or ambiguous; skipped')
            continue
        ref = {'graph index': -1, 'animation': matches[0]}
        expected = {'name': name, 'flags': [], 'frame ratio object function': '',
                    'playback speed object function': '', 'blend weight object function': '', 'animation': ref}
        if set(config) - (set(expected) - {'name', 'animation'}):
            raise ValueError(f'{name}: unknown function overlay settings')
        expected.update(config)
        existing = [i for i, f in enumerate(tables[FUNCTIONS]) if key(f['name']) == key(name) or f['animation'] == ref]
        if not existing:
            put(FUNCTIONS, expected)
        elif len(existing) == 1 and tables[FUNCTIONS][existing[0]]['name'] in plan.owned[FUNCTIONS]:
            expected['name'] = tables[FUNCTIONS][existing[0]]['name']
            put(FUNCTIONS, expected, existing[0])

    for path, native_path, current in graph.bindings:
        # Existing groups and broader bindings are authoritative; do not even
        # create unused helper screens for an authored group.
        if 0 <= current < len(tables[GROUPS]) and tables[GROUPS][current]['name'] not in plan.owned[GROUPS]:
            continue
        if any(0 <= binding_map.get(path[:n], -1) < len(tables[GROUPS]) for n in range(1, len(path))):
            continue
        selections = []
        functions = []
        authored_vehicle_screens = []
        group_config = overrides.get('groups', {}).get(':'.join(path))
        if group_config is not None:
            if set(group_config) - {'screens', 'functions'}:
                raise ValueError(f'{path}: unknown group override settings')
            for name in group_config.get('screens', []):
                selection_path = animation_path(name)
                selection = select(selection_path[:4], selection_path[4]) if selection_path else None
                if selection is None:
                    raise ValueError(f'{path}: explicit screen {name!r} cannot be resolved')
                selections.append(selection)
            for name in group_config.get('functions', []):
                indices = names[FUNCTIONS].get(key(name), [])
                if len(indices) != 1:
                    raise ValueError(f'{path}: explicit function {name!r} cannot be resolved')
                functions.append({'function overlay': indices[0], 'flags': []})
        elif profile == 'vehicle' and len(path) == 1:
            for state in ('steering', 'steer', 'acceleration', 'acc', 'aiming', 'vehicle_aiming', 'aim', 'throttle'):
                selected = select(path + ('any', 'any', 'any'), state)
                if selected:
                    selections.append(selected)
            for i, f in enumerate(tables[FUNCTIONS]):
                ref = f['animation']
                if valid(ref):
                    source = animation_path(graph.animations[ref['animation']][0])
                    if ((source and source[0] == path[0]) or
                            (path[0] == 'any' and ref['animation'] in suspension_refs)):
                        functions.append({'function overlay': i, 'flags': []})
            for i, screen in enumerate(tables[SCREENS]):
                ref = screen['animation']
                if valid(ref):
                    source = animation_path(graph.animations[ref['animation']][0])
                    if source and source[0] == path[0] and screen['name'] not in plan.owned[SCREENS]:
                        authored_vehicle_screens.append({'blend screen': i, 'flags': [], 'node mask': -1})
        elif profile == 'first_person' and len(path) == 5 and path[-1] == 'idle':
            for family in (('acceleration_screens', 'acceleration', 'acc'), ('look', 'pitch_and_turn')):
                for state in family:
                    selected = select(path[:4], state)
                    if selected:
                        selections.append(selected)
                        break
        elif profile == 'character' and len(path) == 5:
            for state in action_states(path[-1], graph.game):
                transition = state in {'enter', 'exit', 'open', 'close', 'board', 'enter_long'}
                primary = [f'aim_{state}_in', f'aim_{state}_out'] if transition else [f'aim_{state}_up']
                if state.startswith('move_'):
                    primary += ['aim_move_up']
                for aim in primary:
                    selected = select(path[:4], aim)
                    if selected:
                        selections.append(selected)
                        if not transition:
                            break
                if not transition:
                    companions = [f'aim_{state}_down', f'look_{state}_up', f'look_{state}_down',
                                  f'throttle_{state}_up', f'throttle_{state}_down', f'defense_{state}_up',
                                  f'pill_fix_{state}_up', 'position_offset']
                    if state == 'still':
                        companions += ['acc']
                    companion_selections = [s for c in companions if (s := select(path[:4], c))]
                    if not selections and not any(role(p[-1]) in {'aim', 'look'} for p, _ in companion_selections):
                        continue
                    for region in PAIN_REGIONS:
                        choices = [f'pain_{state}_{region}', f'pain_still_{region}']
                        for choice in dict.fromkeys(choices):
                            selected = select(path[:4], choice)
                            if selected:
                                selections.append(selected)
                                break
                    # Only known aim/look families imply a group. An unrelated
                    # action must not pick up a global pain or position screen.
                    selections.extend(companion_selections)
        if selections or functions or authored_vehicle_screens or (0 <= current < len(tables[GROUPS]) and tables[GROUPS][current]['name'] in plan.owned[GROUPS]):
            screen_members = members(selections)
            for member in authored_vehicle_screens:
                if all(m['blend screen'] != member['blend screen'] for m in screen_members):
                    screen_members.append(member)
            bind(path, native_path, current, screen_members, functions)

    # Explicit pose records still need their metadata even without an action.
    for path, choices in candidates.items():
        if len(choices) == 1:
            ref = choices[0][0]
            if valid(ref) and key(graph.animations[ref['animation']][0]) in explicit_pose:
                ensure_screen((path, ref))
    # Existing legacy faults are diagnostics, not a reason to erase authored data.
    for group in graph.tables[GROUPS]:
        if len(group['blend screens']) > 10 or len(group['function overlays']) > 32:
            plan.warnings.append(f'Group {group["name"]!r}: exceeds member limits; preserved')
        for member in group['blend screens']:
            index = member['blend screen']
            if not 0 <= index < len(tables[SCREENS]):
                plan.warnings.append(f'Group {group["name"]!r}: invalid blend screen index {index}; preserved')
            if not -1 <= member['node mask'] < len(graph.masks):
                plan.warnings.append(f'Group {group["name"]!r}: invalid node mask {member["node mask"]}; preserved')
        for member in group['function overlays']:
            index = member['function overlay']
            if not 0 <= index < len(tables[FUNCTIONS]):
                plan.warnings.append(f'Group {group["name"]!r}: invalid function overlay index {index}; preserved')
    for path, native_path, index in graph.bindings:
        if not -1 <= index < len(graph.tables[GROUPS]) and native_path not in plan.bindings:
            plan.warnings.append(f'{":".join(path)}: invalid overlay group index {index}; preserved')
    plan.warnings = list(dict.fromkeys(plan.warnings))
    return plan


def write_record(tag, path: str, values: dict):
    """Resolve handles afresh after every block mutation."""
    for name, value in values.items():
        f = tag.root().descend(path).field(name)
        if f is None:
            raise ValueError(f'{path}: missing field {name}')
        if f.type_name == 'struct':
            write_record(tag, path + '/' + name, value)
        elif f.type_name == 'block':
            f.as_block().clear()
            for item in value:
                block = tag.root().descend(path).field(name).as_block()
                i = block.add()
                write_record(tag, f'{path}/{name}[{i}]', item)
        elif 'flags' in f.type_name:
            # New/replaced records only; no authored flag field reaches here.
            for _, flag in f.flag_names() or ():
                f.set_flag(flag, False)
            for flag in value:
                f.set_flag(flag, True)
        else:
            f.set(value)


def apply_plan(tag, plan: Plan):
    """Return an edited clone; errors cannot leave the caller's tag half changed."""
    if not plan.changed:
        return tag
    clone = type(tag).read_from_bytes(tag.write_to_bytes())
    for table in TABLES:
        for index, values in sorted(plan.updates[table].items()):
            block = clone.root().descend('definitions').field(table).as_block()
            if index == len(block):
                block.add()
            write_record(clone, f'definitions/{table}[{index}]', values)
    for path, index in plan.bindings.items():
        clone.root().field_path(path).set(index)
    # Validate actual serialized field acceptance and newly generated references.
    for index in plan.updates[GROUPS]:
        group = snapshot(clone.root().descend(f'definitions/{GROUPS}[{index}]'))
        for member in group['blend screens']:
            i = member['blend screen']
            if not 0 <= i < len(plan.tables[SCREENS]):
                raise ValueError(f'{group["name"]}: invalid generated screen index {i}')
            mask = member['node mask']
            masks = clone.root().descend('definitions').field('node masks').as_block()
            if not -1 <= mask < len(masks):
                raise ValueError(f'{group["name"]}: invalid generated node mask {mask}')
        for member in group['function overlays']:
            i = member['function overlay']
            if not 0 <= i < len(plan.tables[FUNCTIONS]):
                raise ValueError(f'{group["name"]}: invalid generated function index {i}')
    return clone


def ownership(tag, plan: Plan) -> dict:
    result = {name: {e.field('name').value: snapshot(e)
                   for e in tag.root().descend('definitions').field(name).as_block()
                   if e.field('name').value in plan.owned[name]} for name in TABLES}
    # read_graph only needs the game for validation; all three share this layout.
    graph = read_graph(tag, 'reach')
    result['_bindings'] = {':'.join(path): graph.tables[GROUPS][index]['name']
                           for path, _, index in graph.bindings
                           if 0 <= index < len(graph.tables[GROUPS])
                           and graph.tables[GROUPS][index]['name'] in plan.owned[GROUPS]}
    return result


def load_state(path: Path, graph_path: str, game: str) -> dict:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Overlay ownership must be an object')
    if data.get('version') != 1 or data.get('graph') != graph_path or data.get('game') != game:
        return {}
    records = data.get('records', {})
    if not isinstance(records, dict) or any(not isinstance(v, dict) for v in records.values()):
        raise ValueError('Overlay ownership records must be objects')
    return records


def save_state(path: Path, graph_path: str, game: str, records: dict):
    """Commit only after the tag save; a stale ledger always fails conservatively."""
    data = json.dumps({'version': 1, 'graph': graph_path, 'game': game, 'records': records}, indent=2)
    if path.is_file() and path.read_text(encoding='utf-8') == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        temporary = Path(f.name)
        f.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)

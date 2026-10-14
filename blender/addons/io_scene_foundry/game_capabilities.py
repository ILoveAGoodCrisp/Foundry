"""Engine capabilities shared by menus, operators and export workflows."""
from functools import lru_cache
import json
from pathlib import Path

GAMES = frozenset({'halo1', 'halo2', 'halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'})
LEGACY_GAMES = frozenset({'halo1', 'halo2', 'halo3', 'halo3odst'})
CORINTH_GAMES = frozenset({'halo4', 'halo2a'})
RENDER_METHOD_GAMES = frozenset({'halo3', 'halo3odst', 'reach'})
LIGHTING_GAMES = GAMES - {'halo1', 'halo2'}
FEATURE_GAMES = {
    'shader_templates': RENDER_METHOD_GAMES,
    'cubemap_farm': LIGHTING_GAMES,
    'imposter_farm': GAMES - LEGACY_GAMES,
    'wetness': frozenset({'reach'}),
    'megalo': GAMES - LEGACY_GAMES,
    'airprobes': LIGHTING_GAMES,
    'lighting_info': LIGHTING_GAMES,
    'lightmap_region': LIGHTING_GAMES,
    'external_gr2': GAMES - LEGACY_GAMES,
    'composite_animation': CORINTH_GAMES,
}

def supports(game, feature):
    return game in FEATURE_GAMES[feature]

def instance_proxy_types(game):
    """Proxy geometry supported by the game's structure importer."""
    if game in {'halo2', 'halo3', 'halo3odst'}:
        # ASS collision children of instanced geometry use the @ prefix.
        return ('collision',)
    if game == 'reach':
        return ('collision', 'physics', 'cookie_cutter')
    if game in CORINTH_GAMES:
        return ('collision', 'physics')
    return ()

def mesh_type_supported(kind, game, asset_type='model'):
    if asset_type == 'resource':
        return True
    kind = kind.removeprefix('_connected_geometry_mesh_type_')
    kind = {'object_instance': 'io', 'poop': 'instance', 'water_physics_volume': 'water_surface', 'poop_rain_blocker': 'rain_blocker',
            'poop_vertical_rain_sheet': 'rain_sheet', 'planar_fog_volume': 'fog'}.get(kind, kind)
    if kind in {'rain_blocker', 'rain_sheet'}:
        return game == 'reach'
    if kind == 'weather_polyhedron':
        return game in LEGACY_GAMES
    if kind == 'fog':
        # H3/ODST accept legacy fog material flags but discard the fog planes.
        return game not in {'halo3', 'halo3odst'}
    if kind == 'boundary_surface':
        return game not in {'halo1', 'halo2'}
    if kind == 'lightmap_region':
        return supports(game, 'lightmap_region')
    if kind in {'io', 'instance', 'seam', 'water_surface', 'cookie_cutter'}:
        return game != 'halo1'
    if kind == 'obb_volume':
        return game in CORINTH_GAMES
    return True

def marker_type_supported(kind, game, asset_type='model'):
    if asset_type == 'resource':
        return True
    kind = kind.removeprefix('_connected_geometry_marker_type_')
    if kind == 'airprobe':
        return supports(game, 'airprobes')
    if kind in {'physics_constraint', 'game_instance'}:
        return game != 'halo1'
    if kind in {'envfx', 'lightcone', 'lightCone'}:
        return game in CORINTH_GAMES
    return True

ANIMATION_TYPE_ITEMS = (
    ('base', 'Base', 'Base animation with optional movement', 0),
    ('overlay', 'Overlay', 'Animation blended over a base animation', 1),
    ('replacement', 'Replacement', 'Replace animated nodes in object or local space', 2),
    ('world', 'World', 'Animation relative to the world', 3),
    ('composite', 'Composite', 'Reference and blend other animations (Halo 4 / H2A)', 4),
)
ANIMATION_EVENT_ITEMS = tuple((f'_connected_geometry_animation_event_type_{kind}', label, '', index)
    for index, (kind, label) in enumerate((('frame', 'Frame'), ('object_function', 'Object Function'),
        ('import', 'Pose Overlay Wrap'), ('wrinkle_map', 'Wrinkle Map'), ('ik_active', 'IK Active'), ('ik_passive', 'IK Passive'))))
EVENT_DATA_ITEMS = (('SOUND', 'Sound', '', 0), ('EFFECT', 'Effect', '', 1), ('DIALOGUE', 'Dialogue', '', 2))

@lru_cache(maxsize=7)
def animation_type_items(game):
    return [item for item in ANIMATION_TYPE_ITEMS if item[0] != 'composite' or supports(game, 'composite_animation')]

@lru_cache(maxsize=7)
def animation_event_items(game):
    return list(ANIMATION_EVENT_ITEMS[:1] if game in LEGACY_GAMES else ANIMATION_EVENT_ITEMS)

@lru_cache(maxsize=7)
def event_data_items(game):
    return list(EVENT_DATA_ITEMS[:1] if game == 'halo1' else EVENT_DATA_ITEMS[:2] if game == 'halo2' else EVENT_DATA_ITEMS)

def event_data_property_supported(game, prop, data_type):
    if prop in {'marker', 'marker_name'}:
        return game != 'halo1' and not (game == 'halo2' and data_type == 'EFFECT')
    if prop == 'damage_effect_reporting_type':
        return data_type == 'EFFECT' and game in {'halo3odst', 'reach', 'halo4', 'halo2a'}
    if prop in {'event_model', 'variant'}:
        return game in CORINTH_GAMES
    if prop.startswith('flag_'):
        if game == 'halo1':
            return False
        if prop == 'flag_third_person_only':
            return game not in LEGACY_GAMES
        if prop == 'flag_fp_no_aged_weapons':
            return game not in {'halo1', 'halo2'}
    return True

PROFILES = {'halo1':'haloce_mcc','halo2':'halo2_mcc','halo3':'halo3_mcc','halo3odst':'halo3odst_mcc',
            'reach':'haloreach_mcc','halo4':'halo4_mcc','halo2a':'halo2amp_mcc'}

@lru_cache(maxsize=7)
def frame_event_names(game):
    if game == 'halo1':
        return frozenset({'none', 'primary keyframe', 'secondary keyframe', 'left foot', 'right foot'})
    schema = Path(__file__).parent/'tags/definitions'/PROFILES[game]/'model_animation_graph.json'
    enums = json.loads(schema.read_text(encoding='utf-8'))['enums_flags']
    names = enums['type_enum_2' if game == 'halo2' else 'frame_event_type_new']['options']
    def canonical(name):
        key = name.partition('{')[0].strip().replace('_', ' ').casefold()
        return 'match '+key[-1] if key in {'transition a','transition b','transition c','transition d'} else key
    return frozenset({'none', *(canonical(name) for name in names)})

def _stored_enum(owner, name, items, default=0):
    if hasattr(owner, 'get'):
        value = owner.get(name, default)
        if isinstance(value, int):
            return next((item[0] for item in items if item[-1] == value), '')
    return getattr(owner, name, '')

def validate_legacy_animation(owner, game, name):
    """Reject incompatible saved settings before any intermediate is written."""
    from .animation_events import FRAME_EVENT_ITEMS
    if getattr(owner, 'external', False):
        raise ValueError(f'{name}: import the external GR2 as action tracks before exporting to this game')
    if hasattr(owner, 'animation_type'):
        kind = _stored_enum(owner, 'animation_type', ANIMATION_TYPE_ITEMS)
        if kind not in {item[0] for item in animation_type_items(game)}:
            raise ValueError(f'{name}: animation type is not supported by {game}')
        if game == 'halo1':
            if kind == 'base' and owner.get('animation_movement_data', 0) == 4:
                raise ValueError(f'{name}: Halo 1 does not support Full movement')
            if kind == 'replacement' and owner.get('animation_space', 0) == 1:
                raise ValueError(f'{name}: Halo 1 does not support Local replacement space')
            if getattr(owner, 'author_type', 'TAG') == 'BLENDER':
                flags = ('disable_interpolation_in','disable_interpolation_out','disable_mode_ik','disable_weapon_ik',
                    'disable_weapon_aim','disable_look_screen','disable_transition_adjustment','force_weapon_ik_on',
                    'enable_animated_source_interpolation','disable_ik_sets','disable_ik_chains','translate_and_scale_root_only',
                    'enable_blend_out_on_replacement_anims','override_player_input_with_motion','disable_subframe_interp_on_loop',
                    'do_not_monitor_changes','verify_sound_events','do_not_inherit_for_player_graphs')
                if any(getattr(owner, flag, False) for flag in flags) or any(getattr(owner, prop, 0) > 0 for prop in ('override_blend_in_time','override_blend_out_time')):
                    raise ValueError(f'{name}: Halo 1 cannot store the selected animation flags or blend-time overrides')
    sound_count = 0
    seen_slots = set()
    for event in getattr(owner, 'animation_events', ()):
        if _stored_enum(event, 'event_type', ANIMATION_EVENT_ITEMS) != ANIMATION_EVENT_ITEMS[0][0]:
            raise ValueError(f'{name}: this game only supports Frame animation events')
        event_name = _stored_enum(event, 'frame_name', FRAME_EVENT_ITEMS)
        if event_name not in frame_event_names(game):
            raise ValueError(f'{name}: the selected frame event is not supported by {game}')
        if game == 'halo1':
            if event.get('multi_frame', 0) == 1:
                raise ValueError(f'{name}: Halo 1 frame events must use a single frame')
            if event_name != 'none':
                if event_name in seen_slots:
                    raise ValueError(f'{name}: Halo 1 stores only one {event_name} event')
                seen_slots.add(event_name)
        for data in event.event_data:
            dtype = _stored_enum(data, 'data_type', EVENT_DATA_ITEMS)
            if dtype not in {item[0] for item in event_data_items(game)}:
                raise ValueError(f'{name}: {game} cannot store the selected event-data type')
            for prop in ('marker','marker_name','flag_allow_on_player','flag_left_arm_only','flag_right_arm_only',
                         'flag_first_person_only','flag_third_person_only','flag_forward_only','flag_reverse_only',
                         'flag_fp_no_aged_weapons','event_model','variant'):
                if getattr(data, prop, None) and not event_data_property_supported(game, prop, dtype):
                    raise ValueError(f'{name}: {prop.replace("_", " ")} is not supported by this game')
            if dtype == 'SOUND':
                sound_count += 1
    if game == 'halo1' and sound_count > 1:
        raise ValueError(f'{name}: Halo 1 stores only one sound event per animation')

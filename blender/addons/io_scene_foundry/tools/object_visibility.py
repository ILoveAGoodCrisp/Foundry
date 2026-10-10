"""Object types available in the Sets Manager visibility row."""

from ..constants import object_asset_validation, object_game_validation


# Keep the order of the visibility buttons stable, including types unavailable
# in the current asset so isolation can also hide objects left over from it.
OBJECT_VISIBILITY_TYPES = (
    ('mesh', 'default', 'Render', 'render_geometry'),
    ('mesh', 'collision', 'Collision', 'collider'),
    ('mesh', 'physics', 'Physics', 'physics'),
    ('mesh', 'object_instance', 'Object Instance', 'instance'),
    ('mesh', 'structure', 'Structure', 'structure'),
    ('mesh', 'weather_polyhedron', 'Weather Polyhedron', 'rain_blocker'),
    ('mesh', 'seam', 'Seam', 'seam'),
    ('mesh', 'portal', 'Portal', 'portal'),
    ('mesh', 'water_surface', 'Water', 'water'),
    ('mesh', 'planar_fog_volume', 'Fog', 'fog'),
    ('mesh', 'lightmap_region', 'Lightmap Region', 'lightmap'),
    ('mesh', 'boundary_surface', 'Boundary Surface', 'soft_ceiling'),
    ('mesh', 'obb_volume', 'Bounding Box', 'streaming'),
    ('mesh', 'cookie_cutter', 'Pathfinding Cutout Volume', 'cookie_cutter'),
    ('mesh', 'poop_vertical_rain_sheet', 'Rain Sheet', 'rain_sheet'),
    ('mesh', 'poop_rain_blocker', 'Rain Blocker', 'rain_blocker'),
    ('marker', 'model', 'Model Marker', 'marker'),
    ('marker', 'effects', 'Effects', 'effects'),
    ('marker', 'garbage', 'Garbage', 'garbage'),
    ('marker', 'hint', 'Hint', 'hint'),
    ('marker', 'pathfinding_sphere', 'Pathfinding Sphere', 'pathfinding_sphere'),
    ('marker', 'physics_constraint', 'Physics Constraint', 'physics_constraint'),
    ('marker', 'target', 'Target', 'target'),
    ('marker', 'airprobe', 'Airprobe', 'airprobe'),
    ('marker', 'scenario_object', 'Scenario Object', 'scenario'),
    ('marker', 'game_instance', 'Game Object', 'game_object'),
    ('marker', 'decal', 'Decal', 'marker'),
    ('marker', 'decorator', 'Decorator', 'decorator'),
    ('marker', 'player_start', 'Player Starting Location', 'marker'),
    ('marker', 'cutscene_flag', 'Cutscene Flag', 'marker'),
    ('marker', 'envfx', 'Environment Effect', 'environment_effect'),
    ('marker', 'lightCone', 'Light Cone', 'light_cone'),
    ('object', 'frame', 'Frame', 'frame'),
    ('object', 'light', 'Light', 'light'),
)


def visibility_type_id(category, kind):
    return f'_connected_geometry_{category}_type_{kind}'


def visibility_items(asset_type, game):
    """Apply asset validation plus the capabilities of the actual editing kit."""
    engine = 'corinth' if game in {'halo4', 'halo2a', 'corinth'} else 'reach'
    # Cinematics contain model actors; standalone animations use the same
    # geometry and marker types as animation graphs.
    asset_type = {'cinematic': 'model', 'single_animation': 'animation'}.get(asset_type, asset_type)
    items = []
    for category, kind, label, icon in OBJECT_VISIBILITY_TYPES:
        object_type = visibility_type_id(category, kind)
        if category == 'object':
            if kind == 'frame':
                valid = asset_type in {'model', 'sky', 'scenario', 'prefab', 'animation',
                                       'resource', 'multi_model', 'multi_prefab'}
            else:
                # Area lights become emissive geometry, and skies support suns
                # even in the older kits. Multi-assets do not support lights.
                valid = asset_type in {'model', 'sky', 'scenario', 'prefab', 'resource'}
        else:
            valid = (asset_type in object_asset_validation.get(object_type, ())
                     and engine in object_game_validation.get(object_type, ()))
            if category == 'mesh':
                if kind == 'weather_polyhedron':
                    valid = valid and game in {'halo1', 'halo2'}
                elif kind in {'poop_vertical_rain_sheet', 'poop_rain_blocker'}:
                    valid = valid and game == 'reach'
                elif kind == 'boundary_surface':
                    valid = valid and game not in {'halo1', 'halo2'}
                elif kind in {'object_instance', 'seam', 'water_surface', 'lightmap_region', 'cookie_cutter'}:
                    valid = valid and game != 'halo1'
            elif kind == 'airprobe':
                valid = (asset_type in {'scenario', 'prefab', 'resource', 'multi_prefab'}
                         or (engine == 'corinth' and asset_type in {'model', 'multi_model'}))
                valid = valid and game not in {'halo1', 'halo2', 'halo3', 'halo3odst'}
            elif kind == 'physics_constraint':
                valid = valid and game != 'halo1'
        if not valid:
            continue
        if category == 'mesh' and kind == 'default':
            if asset_type in {'scenario', 'prefab', 'multi_prefab'}:
                label, icon = ('Render', 'render_geometry') if game == 'halo1' else ('Instance', 'instance')
            elif asset_type == 'decorator_set':
                label, icon = 'Decorator', 'decorator'
        elif category == 'marker' and kind == 'model' and asset_type in {'scenario', 'prefab', 'multi_prefab'}:
            label = 'Structure Marker'
        items.append((object_type, label, icon))
    return items

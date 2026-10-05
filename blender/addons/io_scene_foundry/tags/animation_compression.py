"""Resolve authoring compression without changing Blender animation properties."""


def import_animation_compression(value: int, game: str) -> str:
    if game in {'halo2', 'halo3', 'halo3odst'}:
        return ('Medium', 'Rough', 'Uncompressed', 'Uncompressed', 'Medium', 'Medium')[value]
    return ('Medium', 'Rough', 'Uncompressed', 'Medium', 'Medium', 'Rough')[value]


def export_animation_compression(compression: str, forced: str = 'none',
                                 game: str = 'reach') -> str:
    if game != 'halo1' and forced != 'none':
        return {'medium': 'Medium', 'rough': 'Rough',
                'uncompressed': 'Uncompressed'}[forced]
    # Older blends can retain the removed Default enum value.
    return compression if compression in {'Medium', 'Rough', 'Uncompressed'} else 'Medium'


def migrate_animation_compression(scene_nwo) -> None:
    """Preserve explicit enum IDs and resolve inherited settings in older blends."""
    previous_default = scene_nwo.get('default_animation_compression', 0)
    inherited = {0: 'Medium', 1: 'Uncompressed', 2: 'Medium', 3: 'Rough',
                 'Automatic': 'Medium', 'Uncompressed': 'Uncompressed',
                 'Medium': 'Medium', 'Rough': 'Rough'}.get(previous_default, 'Medium')
    for animation in scene_nwo.animations:
        if animation.get('compression', 0) in {0, '', 'Default'}:
            animation.compression = inherited

"""Game-specific bitmap choices, with stable Blender enum values."""
from functools import lru_cache
import json
from pathlib import Path

from .tags.backend import PROFILES


CLASSIC_GAMES = {'halo1', 'halo2'}
USAGE_ALIASES = {
    'Float Map (WARNING)': 'Float Map (WARNING: HUGE)',
    'Detail Normal Map (from Standard Orientation with distance face)':
        'Detail Normal Map (from Standard Orientation with distance fade)',
}


@lru_cache(maxsize=7)
def bitmap_usage_names(game):
    path = Path(__file__).parent / 'tags/definitions' / PROFILES[game] / 'bitmap.json'
    enums = json.loads(path.read_text(encoding='utf-8'))['enums_flags']
    return tuple(enums['usage_enum' if game in CLASSIC_GAMES else 'bitmap_usage_global_enum']['options'])


@lru_cache(maxsize=1)
def _usage_numbers():
    # The old menu used these implicit numbers. Do not renumber when filtering
    # H3/ODST choices, or existing .blend files will silently change usage.
    numbers = {name: index for index, name in enumerate(bitmap_usage_names('halo4'), 1)}
    classic = list(bitmap_usage_names('halo1'))
    classic.extend(name for name in bitmap_usage_names('halo2') if name not in classic)
    numbers.update({('usage:default' if name == 'default' else name): index
                    for index, name in enumerate(classic, 100)})
    return numbers


@lru_cache(maxsize=7)
def bitmap_type_items(game):
    # Cache the actual strings/tuples: Blender retains references to enum text.
    items = [('default', 'Automatic (from name)' if game in CLASSIC_GAMES else 'Default',
              'Usage is defined by the suffix of the bitmap name', 0)]
    for name in bitmap_usage_names(game):
        identifier = 'usage:default' if name == 'default' else name
        items.append((identifier, name, '', _usage_numbers()[identifier]))
    return items


def image_bitmap_type(image):
    """Read stored selections even after switching to a different game menu."""
    stored = image.nwo.get('bitmap_type', 0)
    if isinstance(stored, int):
        return next((name for name, number in _usage_numbers().items() if number == stored), 'default')
    return USAGE_ALIASES.get(stored, stored) or 'default'


def infer_bitmap_usage(name, game):
    name = name.lower().strip('_')
    suffix = name.rpartition('_')[2] if '_' in name else ''
    if name.endswith(('_dx_normal', '_normal_dx')):
        return 'ZBrush Bump Map (from Bump Map)'
    for prefixes, usage in (
        (('orm', 'mro', 'mtr', 'rmo', 'control', 'arm'), 'Material Map'),
        (('3d',), '3D Texture'),
        (('blend',), 'Blend Map (linear for terrains)'),
        (('bump',), 'Bump Map (from Height Map)'),
        (('cc', 'change'), 'Change Color Map'),
        (('cube',), 'Cube Map (Reflection Map)'),
        (('detailb',), 'Detail Bump Map (from Height Map - fades out)'),
        (('detailn',), 'Detail Normal Map'),
        (('det',), 'Detail Map'),
        (('dsprite',), 'Sprite (Double Multiply, Gray Background)'),
        (('float',), 'Float Map (WARNING: HUGE)'),
        (('height',), 'Height Map (for Parallax)'),
        (('illum', 'self', 'emm'), 'Self-Illum Map'),
        (('msprite',), 'Sprite (Blend, White Background)'),
        (('spec',), 'Specular Map'),
        (('sprite',), 'Sprite (Additive, Black Background)'),
        (('ui',), 'Interface Bitmap'),
        (('vec',), 'Vector Map'),
        (('warp',), 'Warp Map (EMBM)'),
        (('zbump', 'dxnormal', 'normaldx'), 'ZBrush Bump Map (from Bump Map)'),
        (('nor', 'nm', 'nrm'), 'Normal Map (from Standard Orientation of Maya, Modo, Zbrush)'
            if game in {'halo4', 'halo2a'} else 'Normal Map (aka zbump)'),
    ):
        if suffix.startswith(prefixes):
            return usage
    return 'Diffuse Map'


def resolve_bitmap_usage(name, usage, game):
    usage = USAGE_ALIASES.get(usage, usage)
    inferred = not usage or usage == 'default'
    if inferred:
        usage = infer_bitmap_usage(name, game)
    if usage == 'usage:default':
        usage = 'default'
    if game not in CLASSIC_GAMES:
        usage = {'default': 'Diffuse Map', 'alpha blend': 'Diffuse Map',
                 'alpha-blend': 'Diffuse Map', 'height map': 'Bump Map (from Height Map)',
                 'detail map': 'Detail Map', 'light map': 'Diffuse Map',
                 'vector map': 'ZBrush Bump Map (from Bump Map)', 'embm': 'Warp Map (EMBM)'}.get(usage, usage)
    elif usage in {'alpha blend', 'alpha-blend'}:
        usage = 'alpha blend' if game == 'halo1' else 'alpha-blend'
    if game in CLASSIC_GAMES and usage not in bitmap_usage_names(game):
        if 'Height Map' in usage or usage == 'Height Map (for Parallax)':
            usage = 'height map'
        elif 'Normal' in usage or 'ZBrush' in usage or usage == 'Vector Map':
            usage = 'vector map'
        elif usage == 'Detail Map':
            usage = 'detail map'
        elif usage == 'Warp Map (EMBM)':
            usage = 'vector map' if game == 'halo1' else 'embm'
        elif usage.startswith('Sprite'):
            usage = 'alpha blend' if game == 'halo1' else 'alpha-blend'
        else:
            usage = 'default'
    elif game in {'halo3', 'halo3odst'} and usage not in bitmap_usage_names(game):
        if 'Normal' in usage or 'ZBrush' in usage:
            usage = 'ZBrush Bump Map (from Bump Map)'
        elif usage == 'Material Map' or inferred:
            usage = 'Diffuse Map'
    if usage not in bitmap_usage_names(game):
        raise ValueError(f'{game} does not support bitmap usage {usage!r}')
    return usage


def bitmap_import_command(path, game):
    path = Path(path).with_suffix('') if Path(path).suffix in {'.bitmap', '.tif', '.tiff'} else Path(path)
    if game in CLASSIC_GAMES:
        # Prepare the folder's tags before compiling its TIFFs together.
        return ['bitmaps', str(path.parent)]
    return ['reimport-bitmaps-single', str(path)] + (['default'] if game in {'halo4', 'halo2a'} else [])

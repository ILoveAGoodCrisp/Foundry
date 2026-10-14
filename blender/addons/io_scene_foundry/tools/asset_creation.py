"""Asset destinations and folder scaffolds shared by creation and its preview."""
from pathlib import Path
import re


LEGACY_GAMES = frozenset({'halo1', 'halo2', 'halo3', 'halo3odst'})
WORK_FOLDERS = frozenset({'models', 'export', 'animations', 'cinematics', 'work', '000'})
MODEL_OUTPUTS = (
    'scenery', 'crate', 'biped', 'creature', 'device_control', 'device_machine',
    'device_terminal', 'device_dispenser', 'effect_scenery', 'equipment',
    'giant', 'vehicle', 'weapon',
)


def template_tag_extensions(game, asset_type, object_type='custom', outputs=()):
    """Tag classes for the selected asset, using the source game's names."""
    if asset_type in {'model', 'multi_model'}:
        types = outputs if object_type == 'custom' else (object_type,)
        excluded = {'crate'} if game == 'halo1' else set()
        if game in {'halo1', 'halo2'}:
            excluded.update(('device_terminal', 'giant', 'effect_scenery'))
        if game not in {'halo4', 'halo2a'}:
            excluded.add('device_dispenser')
        result = tuple('.' + name for name in types if name in MODEL_OUTPUTS and name not in excluded)
        if types:
            return result
        return ('.model', '.gbxmodel') if game == 'halo1' else ('.model',)
    return {
        'sky': ('.sky',) if game in {'halo1', 'halo2'} else ('.model', '.render_model'),
        'animation': ('.model_animations',) if game == 'halo1' else ('.model_animation_graph',),
        'single_animation': ('.model_animations',) if game == 'halo1' else ('.model_animation_graph',),
        'scenario': ('.scenario',), 'decorator_set': ('.decorator_set',),
        'particle_model': ('.particle_model',), 'cinematic': ('.cinematic',),
        'camera_track_set': ('.camera_track',), 'prefab': ('.prefab',),
        'multi_prefab': ('.prefab',), 'polyart': ('.polyart_asset',),
    }.get(asset_type, ())


def resolve_template_tag(tags_directory, value, extensions):
    if not extensions:
        raise ValueError('This asset type has no matching tag in the selected source project.')
    if not value.strip():
        raise ValueError('Choose an existing asset tag to start with.')
    root = Path(tags_directory).resolve()
    tag = Path(value.strip().strip('"'))
    if not tag.is_absolute():
        tag = root / tag
    tag = tag.resolve()
    if not tag.is_relative_to(root):
        raise ValueError("Choose a tag inside the source project's tags folder.")
    if tag.suffix.casefold() not in extensions:
        raise ValueError('Choose a matching tag: ' + ', '.join(extensions) + '.')
    if not tag.is_file():
        raise ValueError('The selected asset tag does not exist.')
    return tag


def asset_folders(game, asset_type):
    """Return relative leaf directories; mkdir also creates their parents."""
    if asset_type in {'resource', 'camera_track_set'}:
        return ()
    animations = asset_type in {'model', 'multi_model', 'animation', 'single_animation'}
    geometry = asset_type not in {'animation', 'single_animation', 'cinematic'}
    if game in LEGACY_GAMES:
        if asset_type == 'cinematic':
            return ('objects',)
        folders = []
        if asset_type == 'scenario':
            folders.append('models' if game == 'halo1' else 'structure')
        elif geometry:
            # H2 particle/decorator JMI children receive their own render folder
            # at export, once the child model names are known.
            if game != 'halo2' or asset_type not in {'particle_model', 'decorator_set'}:
                folders.append('models' if game == 'halo1' else 'render')
            if asset_type in {'model', 'multi_model'}:
                folders.extend(('physics',) if game == 'halo1' else ('collision', 'physics'))
        if animations:
            folders.append('animations')
        return tuple(folders)
    folders = []
    if geometry:
        folders.extend(('models/work', 'export/models'))
    if animations:
        folders.extend(('animations/work', 'export/animations'))
        if asset_type == 'animation':
            folders.extend(('animations/rigs', 'export/models'))
    if asset_type == 'cinematic':
        folders.extend(('cinematics', 'export/models', 'export/animations'))
    return tuple(folders)


def folder_tree(folders):
    """Stable (depth, label) rows, including implicit parent folders."""
    tree = {}
    for folder in folders:
        branch = tree
        for part in folder.split('/'):
            branch = branch.setdefault(part, {})
    def walk(branch, depth):
        for name, children in branch.items():
            yield depth, name
            yield from walk(children, depth + 1)
    return tuple(walk(tree, 0))


def suggested_parent(asset_type, object_type='scenery'):
    if asset_type in {'model', 'multi_model'}:
        return {
            'biped': 'objects/characters', 'creature': 'objects/characters',
            'giant': 'objects/characters', 'vehicle': 'objects/vehicles',
            'weapon': 'objects/weapons', 'equipment': 'objects/equipment',
            'crate': 'objects/crates', 'scenery': 'objects/scenery',
            'device_machine': 'objects/levels/shared/device_machines',
            'device_control': 'objects/levels/shared/device_controls',
            'device_terminal': 'objects/levels/shared/device_terminals',
            'device_dispenser': 'objects/levels/shared/device_dispensers',
        }.get(object_type, 'objects')
    return {
        'scenario': 'levels/custom', 'sky': 'skies', 'animation': 'objects/animations',
        'single_animation': 'objects/animations', 'decorator_set': 'objects/decorators',
        'particle_model': 'effects/particle_models', 'cinematic': 'cinematics',
        'resource': 'resources', 'prefab': 'levels/shared/prefabs',
        'multi_prefab': 'levels/shared/prefabs',
    }.get(asset_type, 'objects')


def name_suggestion(name):
    name = re.sub(r'\.blend$', '', name, flags=re.IGNORECASE).lower()
    return re.sub(r'[^a-z0-9_]+', '_', name).strip('_')


def name_error(name):
    if not name:
        return 'Enter an asset name.'
    if not re.fullmatch(r'[a-z0-9][a-z0-9_]*', name):
        return 'Use lowercase letters, numbers, and underscores, without a file extension.'
    if re.fullmatch(r'(con|prn|aux|nul|com[0-9]|lpt[0-9])', name):
        return 'This name is reserved by Windows. Choose another asset name.'
    return ''


def resolve_parent(data_directory, directory):
    root = Path(data_directory).resolve()
    parent = Path(directory) if directory else root
    if not parent.is_absolute():
        parent = root / parent
    parent = parent.resolve()
    if not parent.is_relative_to(root):
        raise ValueError("Choose a parent folder inside this project's data directory.")
    if parent.exists() and not parent.is_dir():
        raise ValueError('The parent location is a file. Choose a folder.')
    return root, parent


def existing_asset(parent, root):
    """Find a sidecar in the chosen folder or any ancestor beneath data."""
    for folder in (parent, *parent.parents):
        if folder == root or not folder.is_relative_to(root):
            break
        if folder.is_dir() and any(folder.glob('*.sidecar.xml')):
            return folder
    return None


def reuse_candidate(parent, name, root):
    for folder in (parent, *parent.parents):
        if folder == root or not folder.is_relative_to(root):
            break
        if folder.name.casefold() == name.casefold():
            tail = parent.relative_to(folder).parts
            if all(part.casefold() in WORK_FOLDERS for part in tail):
                return folder
    destination = parent / name
    return destination if destination.is_dir() else None


def folder_conflict(folder, current_blend='', save_blend=True):
    """Report a file collision or existing contents; the caller chooses severity."""
    if not folder.exists():
        return ''
    if not folder.is_dir():
        return 'A file already has this asset name. Choose another name.'
    current = Path(current_blend).resolve() if current_blend else None
    for item in folder.rglob('*'):
        if item.is_file():
            if not save_blend and current is not None and item.resolve() == current:
                continue
            return 'This folder already contains files.'
    return ''

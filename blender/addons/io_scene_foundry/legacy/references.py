"""ASS game-object reference conventions, separate from structural xrefs."""
import re
from pathlib import Path, PureWindowsPath

from ..project_config import relative_content_path

ASS_GAMES = frozenset({'halo2', 'halo3', 'halo3odst'})
ASS_GAME_OBJECT_EXTENSIONS = ('.scenery', '.device_machine')


def embedded_game_object_tag(xref_path, xref_name, tags_path, data_path, known_tag_paths=frozenset(), *, known_only=False):
    """Resolve an exact source asset directory, never a basename guess."""
    if not xref_path:
        return ''
    relative = relative_content_path(PureWindowsPath(xref_path), tags_path, data_path)
    if relative is None:
        return ''
    parts = list(relative.parts[:-1])
    component_source = parts and parts[-1].casefold() in {'render', 'collision', 'physics'}
    if component_source:
        parts.pop()
    if not parts or any(part in {'.', '..'} for part in parts):
        return ''
    asset_dirs = [Path(*parts)]
    # Shared Max files can name a child asset, rather than the Max file's stem.
    source_name = xref_name.strip()
    if (not component_source and source_name and source_name not in {'.', '..'}
            and not any(c in source_name for c in '<>:"/\\|?*')):
        asset_dirs.insert(0, Path(*parts, source_name))
    candidates = [asset_dir / (asset_dir.name + extension)
                  for asset_dir in asset_dirs for extension in ASS_GAME_OBJECT_EXTENSIONS]
    # The compiled BSP is authoritative when an embedded reference's target is
    # missing (for example, H2 scenery later replaced by crate tags).
    for path in candidates:
        if PureWindowsPath(path) in known_tag_paths:
            return str(path)
    if known_only:
        return ''
    for path in candidates:
        if Path(tags_path, path).is_file():
            return str(path)
    return ''


def ass_reference_type(name):
    name = name.strip().casefold()
    if name.startswith('?machine?'):
        return '.device_machine'
    return '.scenery' if name.startswith('?') else None


def ass_reference_name(name):
    return re.sub(r'^\?(?:machine\?|scenery\?)?', '', name.strip(), flags=re.I).strip()


def ass_reference_prefix(tag_path):
    suffix = tag_path.rpartition('.')[2].casefold()
    if suffix == 'device_machine':
        return '?machine?'
    if suffix == 'scenery':
        return '?'
    raise ValueError('ASS game objects support only scenery and device_machine tags')

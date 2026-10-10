"""ASS game-object reference conventions, separate from structural xrefs."""
import re

ASS_GAMES = frozenset({'halo2', 'halo3', 'halo3odst'})
ASS_GAME_OBJECT_EXTENSIONS = ('.scenery', '.device_machine')


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

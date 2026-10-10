"""Lazy bridge to Foundry's own compiled writer; no vendor writer is imported."""
from functools import lru_cache
from .binary import BinaryWriteError
from .model import ExportFile

@lru_cache(maxsize=1)
def _module():
    try:
        import foundry_granny
    except (ImportError, OSError) as error:
        raise BinaryWriteError('The compiled GR2 writer wheel is unavailable; select Python or install an updated Foundry build') from error
    if getattr(foundry_granny, 'PROTOCOL_VERSION', None) != 1:
        raise BinaryWriteError('The compiled GR2 writer wheel is incompatible with this Foundry build')
    if not {'geometry', 'skeletons', 'metadata', 'animation', 'textures', 'vector_keys'}.issubset(getattr(foundry_granny, 'CAPABILITIES', ())):
        raise BinaryWriteError('The compiled GR2 writer wheel lacks the required export capabilities')
    return foundry_granny

def available():
    try:
        _module()
    except BinaryWriteError:
        return False
    return True

def build_rust_file(data, *, vector_key_resolver=None, **options):
    if not isinstance(data, ExportFile):
        raise BinaryWriteError('Rust writing requires independent ExportFile records')
    try:
        keys = {}
        if vector_key_resolver is not None:
            from .animation import resolve_vector_keys
            keys = resolve_vector_keys(data, vector_key_resolver)
        return _module().build_file(data, vector_keys=keys, **options)
    except (ValueError, TypeError, OverflowError) as error:
        raise BinaryWriteError(str(error)) from error

def write_rust_file(data, path, **options):
    from .minimal import _write_encoded_file
    _write_encoded_file(build_rust_file(data, **options), path)

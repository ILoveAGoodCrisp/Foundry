"""Explicit export modes, separate from whether a Granny DLL is loaded."""
from enum import Enum
from .model import ExportDataError


class ExportBackend(str, Enum):
    LEGACY = 'legacy_text'
    NATIVE = 'native_gr2'
    PYTHON = 'python_gr2'
    RUST = 'rust_gr2'

    @property
    def is_gr2(self):
        return self is not ExportBackend.LEGACY

    @property
    def uses_native(self):
        return self is ExportBackend.NATIVE


DEFAULT_GR2_BACKEND = ExportBackend.PYTHON
DEFAULT_GR2_WRITER = 'auto_gr2'


def backend_for_export(legacy, settings=None, override=None):
    value = override if override is not None else (ExportBackend.LEGACY if legacy else
        getattr(settings, 'gr2_writer', DEFAULT_GR2_WRITER))
    if value == 'auto_gr2':
        if legacy:
            raise ExportDataError('The selected export backend is incompatible with this project')
        from .rust_writer import available
        value = ExportBackend.RUST if available() else DEFAULT_GR2_BACKEND
    backend = ExportBackend(value)
    if bool(legacy) != (backend is ExportBackend.LEGACY):
        raise ExportDataError('The selected export backend is incompatible with this project')
    return backend


def backend_for_scene(scene) -> ExportBackend:
    value = getattr(scene, 'export_backend', None)
    if value is not None:
        return ExportBackend(value)
    # Compatibility for older extensions and test fixtures. VirtualScene and
    # ExportScene themselves always set an explicit mode.
    return ExportBackend.NATIVE if getattr(scene, 'granny', None) is not None else ExportBackend.LEGACY

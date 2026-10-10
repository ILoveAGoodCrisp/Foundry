"""Independent GR2 export preparation; no Blender or native runtime imports.

The writer supports static/skinned geometry, skeleton/model transforms, basis
conversion, reflection, sampled skeletal/cinematic animation, vector tracks,
morph/PCA buffers, raw RGBA previews and Halo metadata. The optional vector-key
resolver is retained for explicit compatibility checks; default writing is portable.
The package can also be imported directly with the add-on directory on Python's
search path.
"""
from .backend import ExportBackend, backend_for_export, backend_for_scene
from .model import ExportDataError, ExportFile
from .adapter import build_export_file
from .minimal import (
    build_geometry_file, build_minimal_file, write_geometry_file, write_minimal_file,
    build_animation_file, write_animation_file,
)
from .schema import SchemaEmitter, SchemaRegistry
from .metadata import MetadataEmitter
from .standard_schemas import standard_registry
from .native_keys import native_vector_key_resolver
from .vector_keys import vector_track_key_for_bone
from .rust_writer import build_rust_file, write_rust_file

__all__ = ['ExportBackend', 'ExportDataError', 'ExportFile', 'backend_for_scene', 'backend_for_export',
           'build_export_file', 'build_minimal_file', 'write_minimal_file',
           'build_geometry_file', 'write_geometry_file',
           'build_animation_file', 'write_animation_file',
           'SchemaEmitter', 'SchemaRegistry', 'MetadataEmitter', 'standard_registry',
           'native_vector_key_resolver', 'vector_track_key_for_bone', 'build_rust_file', 'write_rust_file']

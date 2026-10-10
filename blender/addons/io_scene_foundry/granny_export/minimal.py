"""Geometry, skeletons and raw sampled animation writing with Halo metadata."""
from __future__ import annotations

from math import isfinite
import os
from pathlib import Path
import tempfile

from .binary import BinaryBuilder, BinaryWriteError, iter_graph_objects
from .model import Animation, Bone, ExportFile, Mesh, Model, Skeleton, Texture, Topology, TrackGroup, VertexData
from .animation import AnimationEmitter, resolve_vector_keys, validate_animation, validate_group
from .texture import TextureEmitter, validate_texture
from .geometry import GeometryEmitter, GeometryValidation
from .metadata import MetadataEmitter
from .schema import SchemaEmitter
from .standard_schemas import standard_registry
from .transforms import TransformContext


def _preflight(data, validation):
    if not isinstance(data, ExportFile):
        raise BinaryWriteError('Minimal writing requires independent ExportFile records')
    for value in iter_graph_objects(data):
        if isinstance(value, Texture):
            validate_texture(value)
        if isinstance(value, VertexData):
            validation.vertices(value)
        if isinstance(value, Topology):
            validation.topology(value)
        if isinstance(value, Mesh):
            validation.mesh(value)
        if isinstance(value, TrackGroup):
            validate_group(value)
        if isinstance(value, Animation):
            validate_animation(value)
        if isinstance(value, Bone):
            if not isfinite(value.lod_error):
                raise BinaryWriteError('Bone LOD error must be finite')
        if isinstance(value, Model):
            names = {bone.name for bone in value.skeleton.bones}
            if any(name not in names for mesh in value.meshes if mesh is not None for name in mesh.bone_bindings):
                raise BinaryWriteError('Model mesh bone binding is absent from its skeleton')


def build_minimal_file(data: ExportFile, *, section_count=1, type_section=0, object_section=0, string_section=0, buffer_section=None, vector_key_resolver=None):
    """Return v7 LE64 bytes for geometry, skeletons, sampled animation and metadata.

    Models may share skeletons, including skeletons absent from root arrays.
    Unsupported payloads raise before writing; no native fallback is used.
    """
    validation = GeometryValidation()
    _preflight(data, validation)
    vector_keys = resolve_vector_keys(data, vector_key_resolver)
    transforms = TransformContext(data.art_tool, data.conversion)
    writer = BinaryBuilder(section_count)
    registry = standard_registry()
    emitter = SchemaEmitter(writer, registry, type_section=type_section, string_section=string_section)
    properties = MetadataEmitter(emitter, object_section=object_section)
    geometry = GeometryEmitter(emitter, properties, object_section=object_section,
                               buffer_section=buffer_section, transforms=transforms, validation=validation)
    motion = AnimationEmitter(emitter, properties, transforms, object_section=object_section,
        buffer_section=buffer_section, vector_keys=vector_keys)
    textures = TextureEmitter(emitter, object_section=object_section, buffer_section=buffer_section)
    root_type = emitter.emit('FileInfo')

    def offset(schema, field):
        return registry.layout(schema).field(field).offset

    def string_reference(address, value):
        writer.reference(address, writer.string(value, section=string_section))

    root = emitter.reserve('FileInfo', owner=data, section=object_section).block
    art = emitter.reserve('ArtToolInfo', owner=data.art_tool, section=object_section).block
    exporter = emitter.reserve('ExporterInfo', owner=data.exporter, section=object_section).block
    writer.reference(root.at(offset('FileInfo', 'ArtToolInfo')), data.art_tool)
    writer.reference(root.at(offset('FileInfo', 'ExporterInfo')), data.exporter)
    string_reference(root.at(offset('FileInfo', 'FromFileName')), data.file_name)
    string_reference(art.at(offset('ArtToolInfo', 'FromArtToolName')), data.art_tool.name)
    art.pack(offset('ArtToolInfo', 'ArtToolMajorRevision'), '<3if12f', data.art_tool.major, data.art_tool.minor, 64,
             data.conversion.target_units_per_meter, 0., 0., 0.,
             *data.conversion.right, *data.conversion.up, *data.conversion.back)
    string_reference(exporter.at(offset('ExporterInfo', 'ExporterName')), data.exporter.name)
    major, minor, build = data.exporter.version
    exporter.pack(offset('ExporterInfo', 'ExporterMajorRevision'), '<4i', major, minor, data.exporter.customization, build)
    properties.variant(root.at(offset('FileInfo', 'ExtendedData')), data.metadata)
    written_arrays = set()
    materials = data.reachable_materials()
    for material in materials:
        block = emitter.reserve('Material', owner=material, section=object_section).block
        string_reference(block.at(offset('Material', 'Name')), material.name)
        properties.variant(block.at(offset('Material', 'ExtendedData')), material.metadata)
        writer.reference(block.at(offset('Material', 'Texture')), material.texture)
        block.pack(offset('Material', 'Maps'), '<i', len(material.maps))
        maps = emitter.reserve('MaterialMap', owner=material.maps, count=len(material.maps), section=object_section)
        if maps is not None:
            writer.reference(block.at(offset('Material', 'Maps') + 4), maps.item(0))
            if maps.block not in written_arrays:
                written_arrays.add(maps.block)
                for index, mapping in enumerate(material.maps):
                    start = index * maps.item_size
                    string_reference(maps.block.at(start + offset('MaterialMap', 'Usage')), mapping.usage)
                    writer.reference(maps.block.at(start + offset('MaterialMap', 'Map')), mapping.material)
    skeletons = []
    seen = set()
    for value in (*data.skeletons, *(model.skeleton for model in data.models)):
        if id(value) not in seen:
            seen.add(id(value))
            skeletons.append(value)
    for skeleton in skeletons:
        block = emitter.reserve('Skeleton', owner=skeleton, section=object_section).block
        string_reference(block.at(offset('Skeleton', 'Name')), skeleton.name)
        block.pack(offset('Skeleton', 'Bones'), '<i', len(skeleton.bones))
        block.pack(offset('Skeleton', 'LODType'), '<i', skeleton.lod_type)
        properties.variant(block.at(offset('Skeleton', 'ExtendedData')), skeleton.metadata)
        array = emitter.reserve('Bone', owner=skeleton.bones, count=len(skeleton.bones), section=object_section)
        if array is not None:
            writer.reference(block.at(offset('Skeleton', 'Bones') + 4), array.block.at())
            if array.block not in written_arrays:
                written_arrays.add(array.block)
                for index, bone in enumerate(skeleton.bones):
                    start = index * array.item_size
                    string_reference(array.block.at(start + offset('Bone', 'Name')), bone.name)
                    array.block.pack(start + offset('Bone', 'ParentIndex'), '<i', bone.parent_index)
                    flags, values = transforms.transform(bone.local_matrix)
                    array.block.pack(start + offset('Bone', 'Transform'), '<I16f', flags, *values)
                    array.block.pack(start + offset('Bone', 'InverseWorldTransform'), '<16f',
                                     *transforms.inverse_world(bone.world_matrix))
                    array.block.pack(start + offset('Bone', 'LODError'), '<f', bone.lod_error)
                    properties.variant(array.block.at(start + offset('Bone', 'ExtendedData')), bone.metadata)
    # Referenced geometry may be absent from root arrays. Discover and write
    # the complete graph while keeping the declared root collections intact.
    for value in iter_graph_objects(data):
        if isinstance(value, Mesh):
            geometry.mesh(value)
        elif isinstance(value, VertexData):
            geometry.vertices(value)
        elif isinstance(value, Topology):
            geometry.topology(value)
        elif isinstance(value, TrackGroup):
            motion.group(value)
        elif isinstance(value, Animation):
            motion.animation(value)
        elif isinstance(value, Texture):
            textures.texture(value)
    for model in data.models:
        block = emitter.reserve('Model', owner=model, section=object_section).block
        string_reference(block.at(offset('Model', 'Name')), model.name)
        writer.reference(block.at(offset('Model', 'Skeleton')), model.skeleton)
        flags, values = transforms.transform(model.placement)
        block.pack(offset('Model', 'InitialPlacement'), '<I16f', flags, *values)
        properties.variant(block.at(offset('Model', 'ExtendedData')), model.metadata)
        bindings = emitter.reserve('ModelMeshBinding', owner=geometry.owner(model.meshes, 'model_mesh_bindings'),
                                   count=len(model.meshes), section=object_section)
        block.pack(offset('Model', 'MeshBindings'), '<i', len(model.meshes))
        if bindings is not None:
            writer.reference(block.at(offset('Model', 'MeshBindings') + 4), bindings.item(0))
            if bindings.block not in written_arrays:
                written_arrays.add(bindings.block)
                for index, mesh in enumerate(model.meshes):
                    writer.reference(bindings.item(index), mesh)
    for name, values in (('Textures', data.textures), ('Materials', data.materials), ('Skeletons', data.skeletons), ('Models', data.models),
                         ('VertexDatas', data.vertex_data), ('TriTopologies', data.topologies), ('Meshes', data.meshes),
                         ('TrackGroups', data.track_groups), ('Animations', data.animations)):
        count_offset = offset('FileInfo', name)
        pointer_offset = count_offset + 4
        root.pack(count_offset, '<i', len(values))
        array = writer.reserve_inline_array(values, len(values), 8, section=object_section)
        if array is not None:
            writer.reference(root.at(pointer_offset), array.block.at())
            for index, value in enumerate(values):
                writer.reference(array.item(index), value)
    return writer.build(root_type, root.at())


def write_minimal_file(data: ExportFile, path: str | Path, **options):
    """Validate/build first, then replace the destination with a complete file."""
    encoded = build_minimal_file(data, **options)
    _write_encoded_file(encoded, path)


def _write_encoded_file(encoded: bytes, path: str | Path):
    """Commit a completed backend result with the same atomic file policy."""
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.' + destination.name + '.', suffix='.tmp',
                                         dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name).resolve()
            if temporary.parent != destination.parent:
                raise BinaryWriteError('Temporary output escaped its destination directory')
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.parent == destination.parent:
            temporary.unlink(missing_ok=True)


def build_geometry_file(data: ExportFile, **options):
    """Build static/skinned geometry, applying its pending transforms and basis."""
    return build_minimal_file(data, **options)


def write_geometry_file(data: ExportFile, path: str | Path, **options):
    """Atomically save prepared static/skinned geometry using only Python."""
    return write_minimal_file(data, path, **options)


def build_animation_file(data: ExportFile, **options):
    """Build raw sampled animation, applying reflection and destination basis."""
    return build_minimal_file(data, **options)


def write_animation_file(data: ExportFile, path: str | Path, **options):
    """Atomically save sampled skeletal/cinematic animation using only Python."""
    return write_minimal_file(data, path, **options)

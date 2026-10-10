"""Detach Foundry's prepared virtual scene into independent Python records.

This module deliberately imports neither Blender, NumPy nor ctypes. Array
producers may offer astype/tobytes; plain Python sequences work as well.
"""
from __future__ import annotations

from dataclasses import replace
from numbers import Integral, Real
import struct

from .model import (
    IDENTITY, Animation, ArtToolInfo, Attribute, Bone, Buffer, CoordinateConversion,
    ExportDataError, ExporterInfo, ExportFile, Material, MaterialGroup, MaterialMap, Member,
    Mesh, Metadata, Model, MorphTarget, SampledCurve, Scalar, Skeleton, Topology,
    TrackGroup, TransformTrack, TriangleAnnotation, ValueKind, VectorTrack, VertexData,
)


def matrix_rows(value):
    result = tuple(tuple(float(v) for v in row) for row in value)
    if len(result) != 4 or any(len(row) != 4 for row in result):
        raise ExportDataError('Expected a 4x4 placement matrix')
    return result


def text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


def numeric_buffer(value, scalar=Scalar.REAL32, width=1):
    if hasattr(value, 'astype') and hasattr(value, 'shape'):
        shape = value.shape
        if len(shape) not in (1, 2) or (len(shape) == 2 and shape[1] != width):
            raise ExportDataError('Array dimensions do not match the declared member width')
        dtype = '<f4' if scalar is Scalar.REAL32 else '<i4' if scalar is Scalar.INT32 else '<u2' if scalar is Scalar.UINT16 else 'u1'
        data = value.astype(dtype, copy=False).tobytes(order='C')
    else:
        values = tuple(value)
        flat = tuple(v for row in values for v in row) if values and not isinstance(values[0], Real) else values
        try:
            data = struct.pack('<' + scalar.format * len(flat), *flat)
        except (struct.error, TypeError, OverflowError) as error:
            raise ExportDataError(f'Invalid {scalar.value} buffer') from error
    unit = scalar.size * width
    if len(data) % unit:
        raise ExportDataError('Control or attribute data is not divisible by its width')
    return Buffer(scalar, width, len(data) // unit, data)


def metadata(properties=None):
    members = []
    for name, value in (properties or {}).items():
        name = text(name)
        if name == '_granny_subshapes':
            if value:
                members.append(Member('SubShapes', ValueKind.VARIANT_ARRAY, tuple(metadata(v) for v in value)))
            continue
        if isinstance(value, (str, bytes)):
            kind, value = ValueKind.STRING, text(value)
        elif isinstance(value, Integral):
            kind, value = ValueKind.INT32, int(value)
            if not -(2**31) <= value < 2**31:
                raise ExportDataError(f'Metadata integer outside int32 range: {name}')
        elif isinstance(value, Real):
            kind, value = ValueKind.REAL32, float(value)
        else:
            if hasattr(value, 'ravel'):
                value = value.ravel()
            try:
                values = tuple(value)
            except TypeError as error:
                raise ExportDataError(f'Unsupported metadata value: {name}') from error
            if not values:
                continue  # Matches the existing property conversion.
            if not all(isinstance(v, Real) for v in values):
                raise ExportDataError(f'Unsupported metadata sequence: {name}')
            kind, value = ValueKind.REAL32_ARRAY, tuple(float(v) for v in values)
        members.append(Member(name, kind, value))
    return Metadata(tuple(members))


def mesh_metadata(properties, siblings=(), *, corinth=False, name=None):
    result = list(metadata(properties).members)
    paths = Metadata(tuple(Member('String', ValueKind.STRING, sibling) for sibling in siblings))
    if siblings and corinth:
        instance = Metadata((Member('IsInstanced', ValueKind.INT32, 1),
            Member('IndirectlyInstanced', ValueKind.INT32, 1),
            Member('AllPaths', ValueKind.RECORD_ARRAY, (paths,))))
        result.append(Member('InstancingInfo', ValueKind.REFERENCE, instance))
    elif siblings:
        result.append(Member('SiblingInstances', ValueKind.RECORD_ARRAY, (paths,)))
        if name is not None:
            result.append(Member('FullPath', ValueKind.STRING, name))
    return Metadata(tuple(result))


def vertex_data(source, *, corinth=False, placement=IDENTITY, reflect_y=False, morph=False,
                positions=None, normals=None, tension=None):
    """Copy separate attribute buffers, preserving declaration/component names."""
    attributes = []

    def add(name, component, value, width=3, scalar=Scalar.REAL32):
        if value is not None:
            attributes.append(Attribute(name, component, numeric_buffer(value, scalar, width)))

    add('Position', 'Position', source.positions if positions is None else positions)
    add('Normal', 'Normal', getattr(source, 'normals', None) if normals is None else normals)
    if morph:
        add(getattr(source, 'tension_field_name', 'DiffuseColor0'), 'tension', getattr(source, 'tension', None))
    else:
        add('BoneWeights', 'BoneWeights', getattr(source, 'bone_weights', None), 4, Scalar.NORMAL_UINT8)
        add('BoneIndices', 'BoneIndices', getattr(source, 'bone_indices', None), 4, Scalar.UINT8)
        texcoords = getattr(source, 'texcoords', ())
        colors = getattr(source, 'vertex_colors', ())
        for index, value in enumerate(texcoords):
            add(f'TextureCoordinates{index}', f'TextureCoordinates{index}', value)
        add('TextureCoordinateslighting', 'lighting', getattr(source, 'lighting_texcoords', None))
        for index, value in enumerate(colors):
            add(f'DiffuseColor{index}', f'colorSet{index + 1}' if corinth else f'DiffuseColor{index}', value)
        tension = getattr(source, 'tension', None) if tension is None else tension
        add(f'DiffuseColor{len(colors)}', 'tension', tension)
        add(f'DiffuseColor{len(colors) + int(tension is not None)}', 'pca_mask', getattr(source, 'pca_mask', None))
        add(f'TextureCoordinates{len(texcoords)}', 'vertex_id', getattr(source, 'vertex_ids', None), 2)
    return VertexData(tuple(attributes), matrix_rows(placement), reflect_y)


def sampled_animation(name, time_step, frame_count, tracks, vector_events=()):
    """Retain raw sampler output; vector key generation is deferred to step 9."""
    transforms = []
    for bone_name, positions, rotations, scales in tracks:
        values = [SampledCurve(numeric_buffer(data, width=width))
                  for data, width in ((positions, 3), (rotations, 4), (scales, 9))]
        if any(curve.controls.count != frame_count for curve in values):
            raise ExportDataError('Animation sample count does not match frame count')
        transforms.append(TransformTrack(bone_name, *values))
    # Foundry's GR2 payload includes an identity wrapper track.
    transforms.append(TransformTrack('world',
        SampledCurve(numeric_buffer((0., 0., 0.) * frame_count, width=3)),
        SampledCurve(numeric_buffer((0., 0., 0., 1.) * frame_count, width=4)),
        SampledCurve(numeric_buffer((1., 0., 0., 0., 1., 0., 0., 0., 1.) * frame_count, width=9))))
    transforms.sort(key=lambda track: track.name.encode('utf-8'))
    vectors, separate = [], []
    for event in vector_events:
        curve = SampledCurve(numeric_buffer(event.effect_data))
        if curve.controls.count != frame_count:
            raise ExportDataError('Vector event sample count does not match animation')
        vector = VectorTrack(event.effect_name, event.name, curve)
        if event.on_event_model:
            separate.append(TrackGroup(event.name, vectors=(vector,)))
        else:
            vectors.append(vector)
    group = TrackGroup('world', tuple(transforms), tuple(vectors))
    return Animation(name, time_step * (frame_count - 1) + .00001, time_step, (group, *separate))


def animation_bone_properties(animation, name):
    prefixes = ('b ', 'b_', 'bone ', 'bone_', 'frame ', 'frame_', 'bip01 ', 'bip01_')

    def key(value):
        result = value.strip().casefold()
        return next((result[len(prefix):] for prefix in prefixes if result.startswith(prefix)), result)

    flags = {'object_space_offset_node': 'bungie_is_object_space_offset_node',
             'replacement_correction_node': 'bungie_is_replacement_correction_node',
             'fik_anchor_node': 'bungie_is_fik_anchor_node'}
    return {flags[item.node_type]: 1 for item in getattr(animation, 'animation_nodes', ())
            if item.node_type in flags and key(item.name) == key(name)}


def build_export_file(scene, nodes, *, animation=None, export_info=None, file_name='',
                      art_tool_name='Blender', art_tool_version=(0, 0), exporter_version=(0, 0, 0), scale=.03048):
    corinth, mirror = bool(scene.corinth), bool(scene.mirror)
    animated = animation is not None
    include_geometry = not animated or bool(animation.is_pca)
    materials, vertices, topologies, meshes, skeletons, models = [], [], [], [], [], []
    material_cache, vertex_cache, topology_cache = {}, {}, {}
    valid_siblings = {node.name for node in nodes.values() if node.mesh is not None}
    exporting_physics = any(node.tag_type == 'physics' for node in nodes.values())

    def material(source):
        key = id(source)
        if key not in material_cache:
            # No fallback to granny_material pointers: preparation must supply
            # real names and shader metadata, even without a runtime.
            result = Material(source.name, metadata({'bungie_shader_path': source.shader_path,
                'bungie_shader_type': source.shader_type}), getattr(source, 'export_texture', None))
            if result.texture is not None:
                result.maps = (MaterialMap('diffuse', result),)
            material_cache[key] = result
            materials.append(result)
        return material_cache[key]

    def geometry(node):
        source = node.mesh
        morphs = getattr(animation, 'export_morph_targets', {}).get(node, ()) if animated else ()
        is_pca = animated and node.for_pca
        pca = getattr(source, 'export_pca_vertices', None) if is_pca else None
        overrides = getattr(node, 'export_vertex_overrides', {})
        override = overrides.get(animation.anim) if is_pca else None
        placement = matrix_rows(node.matrix_world)
        key = (id(source), placement, mirror, id(override), id(pca))
        if key not in vertex_cache:
            if override is not None or pca is not None:
                result = replace(override or pca, placement=placement, reflect_y=mirror)
            else:
                result = vertex_data(source, corinth=corinth, placement=placement, reflect_y=mirror)
            vertex_cache[key] = result
            vertices.append(result)
        source_indices = getattr(source, 'pca_indices', None) if is_pca else None
        if source_indices is None:
            source_indices = source.indices
        invert = bool(node.negative_scaling)
        topology_key = (id(source), is_pca, invert, mirror)
        if topology_key not in topology_cache:
            annotations = []
            for name, face_set in source.face_properties.items():
                value = face_set.array
                dtype = getattr(value, 'dtype', None)
                first = value[0] if len(value) else 0
                row = first if not isinstance(first, Real) else (first,)
                is_int = getattr(dtype, 'kind', None) == 'i' if dtype is not None else all(isinstance(v, Integral) for v in row)
                scalar = Scalar.INT32 if is_int else Scalar.REAL32
                width = value.shape[1] if hasattr(value, 'shape') and len(value.shape) == 2 else len(row)
                annotations.append(TriangleAnnotation(name, 'Int32' if is_int else 'Real32',
                    numeric_buffer(value, scalar, width)))
            groups = tuple(MaterialGroup(index, bounds[0], bounds[1]) for _, index, bounds in source.groups)
            result = Topology(numeric_buffer(source_indices, Scalar.INT32), groups, tuple(annotations), invert, mirror)
            topology_cache[topology_key] = result
            topologies.append(result)
        siblings = tuple(text(s) for s in source.siblings if text(s) != node.name and text(s) in valid_siblings)
        morph_targets = tuple(replace(m, vertex_data=replace(m.vertex_data, placement=placement, reflect_y=mirror)) for m in morphs)
        for morph in morph_targets:
            if morph.vertex_data not in vertices:
                vertices.append(morph.vertex_data)
        result = Mesh(node.name, vertex_cache[key], topology_cache[topology_key],
            tuple(material(source_material) for source_material in source.materials), tuple(node.bone_bindings),
            mesh_metadata(node.props, siblings, corinth=corinth, name=node.name), morph_targets)
        meshes.append(result)
        return result

    for source_model in scene.models.values():
        model_node = nodes.get(source_model.ob)
        if model_node is None:
            continue
        selected = [(index, bone) for index, bone in enumerate(source_model.skeleton.bones)
                    if bone.node is None or nodes.get(bone.bone) is not None or bone.is_proxy]
        remap = {old: new for new, (old, _) in enumerate(selected)}
        bones, bindings = [], []
        for _, source_bone in selected:
            parent = source_bone.parent_index
            if parent != -1 and parent not in remap:
                raise ExportDataError(f'Exported bone {source_bone.name} has an excluded parent')
            properties = dict(source_bone.props)
            properties.update(animation_bone_properties(animation, source_bone.name))
            if exporting_physics and source_bone.physics_subshapes:
                properties['_granny_subshapes'] = source_bone.physics_subshapes
            bones.append(Bone(source_bone.name, remap.get(parent, -1), matrix_rows(source_bone.matrix_local),
                              matrix_rows(source_bone.matrix_world), metadata=metadata(properties)))
            node = source_bone.node
            if node is not None and (nodes.get(source_bone.bone) is not None or source_bone.is_proxy) and node.mesh is not None:
                bindings.append(geometry(node) if include_geometry else None)
        skeleton = Skeleton(model_node.name, tuple(bones))
        skeletons.append(skeleton)
        models.append(Model(source_model.name, skeleton, tuple(bindings), matrix_rows(source_model.node.matrix_local)))
    if export_info:
        header = Skeleton('BungieExportInfo', (Bone('BungieExportInfo', -1, metadata=metadata(export_info)),))
        skeletons.insert(0, header)
        models.append(Model('BungieExportInfo', header))
    prepared_animation = getattr(animation, 'export_animation', None) if animated else None
    if animated and prepared_animation is None:
        raise ExportDataError('Animation has no independent samples; prepare it with the Python GR2 backend')
    conversion = CoordinateConversion(1 / (.3048 if corinth else .03048),
        (-1., 0., 0.) if corinth else (0., -1., 0.), (0., 1., 0.) if corinth else (0., 0., 1.),
        (0., 0., -1.) if corinth else (-1., 0., 0.), mirror)
    return ExportFile(file_name, ArtToolInfo(art_tool_name, *art_tool_version[:2], 64, (1 / .03048) * scale),
        ExporterInfo('Foundry', exporter_version), conversion,
        materials=tuple(materials) if not animated else (),
        textures=tuple(dict.fromkeys(m.texture for m in materials if m.texture is not None)) if not animated else (),
        skeletons=tuple(skeletons), vertex_data=tuple(vertices), topologies=tuple(topologies), meshes=tuple(meshes),
        models=tuple(models), track_groups=prepared_animation.track_groups if animated else (),
        animations=(prepared_animation,) if animated else ())

"""Read GR2s with the source kit's Granny runtime; detach data before freeing it.

Keep this layer independent of Blender. Granny handles compression, pointer-size
conversion, packed vertex formats and compressed animation curves.
"""
from ctypes import (
    CDLL, POINTER, addressof, byref, c_bool, c_char_p, c_float, c_int,
    c_ubyte, c_void_p, cast, pointer, sizeof,
)
from math import floor, isclose, isfinite
from pathlib import Path
import struct

import numpy as np

from .formats import (
    GrannyCurve2, GrannyDataTypeDefinition, GrannyFileArtToolInfo, GrannyFileInfo, GrannyMesh,
    GrannyPixelLayout, GrannyTexture, GrannyTransform, GrannyVariant,
)


def decode_string(value):
    return value.decode('utf-8', errors='replace') if value else ''


def pointer_address(value):
    return cast(value, c_void_p).value or 0


def checked_count(count, limit=10_000_000):
    if not 0 <= count <= limit:
        raise ValueError(f'Invalid GR2 array count: {count}')
    return count


class GrannyReader:
    def __init__(self, dll_path):
        self.dll = CDLL(str(dll_path))
        signatures = {
            'GrannyReadEntireFile': ([c_char_p], c_void_p),
            'GrannyGetFileInfo': ([c_void_p], POINTER(GrannyFileInfo)),
            'GrannyFreeFile': ([c_void_p], None),
            'GrannyGetMemberTypeSize': ([POINTER(GrannyDataTypeDefinition)], c_int),
            'GrannyGetTotalObjectSize': ([POINTER(GrannyDataTypeDefinition)], c_int),
            'GrannyDataTypesAreEqualWithNames': ([POINTER(GrannyDataTypeDefinition)] * 2, c_bool),
            'GrannyCopyTextureImage': ([POINTER(GrannyTexture), c_int, c_int, POINTER(GrannyPixelLayout),
                                        c_int, c_int, c_int, c_void_p], c_bool),
            'GrannyCopyMeshVertices': ([POINTER(GrannyMesh), POINTER(GrannyDataTypeDefinition), c_void_p], None),
            'GrannyBuildCompositeTransform4x4': ([POINTER(GrannyTransform), POINTER(c_float)], None),
            'GrannyComputeBasisConversion': ([POINTER(GrannyFileInfo), c_float] + [POINTER(c_float)] * 7, c_bool),
            'GrannyTransformFile': ([POINTER(GrannyFileInfo)] + [POINTER(c_float)] * 3 + [c_float, c_float, c_int], None),
            'GrannyEvaluateCurveAtT': ([c_int, c_bool, c_bool, POINTER(GrannyCurve2), c_bool, c_float, c_float, POINTER(c_float), POINTER(c_float)], None),
            'GrannyCurveIsKeyframed': ([POINTER(GrannyCurve2)], c_bool),
            'GrannyCurveIsIdentity': ([POINTER(GrannyCurve2)], c_bool),
            'GrannyCurveGetDimension': ([POINTER(GrannyCurve2)], c_int),
            'GrannyCurveGetKnotCount': ([POINTER(GrannyCurve2)], c_int),
            'GrannyCurveExtractKnotValue': ([POINTER(GrannyCurve2), c_int, POINTER(c_float), POINTER(c_float)], c_float),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.dll, name)
            function.argtypes = args
            function.restype = result
        self.texture_type = POINTER(GrannyDataTypeDefinition).in_dll(self.dll, 'GrannyTextureType')

    def members(self, dtype):
        if not dtype:
            return
        offset = 0
        for index in range(1024):
            member = dtype[index]
            if member.member_type == 0:
                return
            ptr = cast(addressof(member), POINTER(GrannyDataTypeDefinition))
            size = self.dll.GrannyGetMemberTypeSize(ptr)
            if size < 0 or size > 1_000_000:
                raise ValueError('Invalid GR2 member size')
            yield member, offset, size
            offset += size
        raise ValueError('Unterminated GR2 type definition')

    def variant(self, variant):
        return self.object(variant.type, variant.object)

    def object(self, dtype, address, depth=0, *, allow_nonfinite=False):
        if not dtype or not address:
            return {}
        if depth > 24:
            raise ValueError('GR2 metadata is nested too deeply')
        if (getattr(self, 'texture_type', None) and dtype[0].name == b'FromFileName'
                and self.dll.GrannyDataTypesAreEqualWithNames(dtype, self.texture_type)):
            # Maya shader metadata can reference a complete texture. Its pixel
            # buffer is binary image data, not an array of metadata objects.
            texture = cast(address, POINTER(GrannyTexture)).contents
            return dict(FromFileName=decode_string(texture.file_name), TextureType=texture.texture_type,
                        Width=texture.width, Height=texture.height, Encoding=texture.encoding,
                        SubFormat=texture.sub_format, ImageCount=texture.image_count,
                        gr2_texture_id=address)
        result = {}
        for member, offset, size in self.members(dtype):
            name = decode_string(member.name)
            width = max(1, member.array_width)
            unit = size // width
            values = [self.member(member, address + offset + i * unit, depth, allow_nonfinite=allow_nonfinite)
                      for i in range(width)]
            value = values[0] if width == 1 else values
            # Max/Maya exporters sometimes use repeated String members.
            if name in result:
                old = result[name]
                result[name] = (old if isinstance(old, list) else [old]) + [value]
            else:
                result[name] = value
        return result

    def member(self, member, address, depth, *, allow_nonfinite=False):
        kind = member.member_type
        if kind == 1:
            return self.object(member.reference_type, address, depth + 1, allow_nonfinite=allow_nonfinite)
        if kind == 2:
            return self.object(member.reference_type, c_void_p.from_address(address).value, depth + 1,
                               allow_nonfinite=allow_nonfinite)
        if kind in (3, 4):
            count = checked_count(c_int.from_address(address).value, 100_000)
            data = c_void_p.from_address(address + 4).value
            if not data:
                if count:
                    raise ValueError('Missing GR2 metadata array')
                return []
            stride = self.dll.GrannyGetTotalObjectSize(member.reference_type)
            return [self.object(member.reference_type,
                                c_void_p.from_address(data + i * sizeof(c_void_p)).value if kind == 4 else data + i * stride,
                                depth + 1, allow_nonfinite=allow_nonfinite) for i in range(count)]
        if kind == 5:
            variant = GrannyVariant.from_address(address)
            return self.object(variant.type, variant.object, depth + 1, allow_nonfinite=allow_nonfinite)
        if kind == 7:
            dtype = cast(c_void_p.from_address(address).value, POINTER(GrannyDataTypeDefinition))
            count = checked_count(c_int.from_address(address + sizeof(c_void_p)).value, 100_000)
            data = c_void_p.from_address(address + sizeof(c_void_p) + 4).value
            if count and not data:
                raise ValueError('Missing GR2 variant array')
            stride = self.dll.GrannyGetTotalObjectSize(dtype) if dtype else 0
            return [self.object(dtype, data + i * stride, depth + 1, allow_nonfinite=allow_nonfinite)
                    for i in range(count)]
        if kind == 8:
            return decode_string(c_char_p.from_address(address).value)
        if kind == 9:
            return self.matrix(GrannyTransform.from_address(address)).tolist()
        formats = {10: 'f', 11: 'b', 12: 'B', 13: 'b', 14: 'B',
                   15: 'h', 16: 'H', 17: 'h', 18: 'H', 19: 'i', 20: 'I', 21: 'e'}
        if kind in formats:
            fmt = formats[kind]
            value = struct.unpack(fmt, bytes((c_ubyte * struct.calcsize(fmt)).from_address(address)))[0]
            if kind in (13, 17):
                value = max(-1.0, value / (127 if kind == 13 else 32767))
            elif kind in (14, 18):
                value /= 255 if kind == 14 else 65535
            if not allow_nonfinite and isinstance(value, float) and not isfinite(value):
                raise ValueError('Non-finite GR2 metadata value')
            return value
        if kind == 22:
            return None
        raise ValueError(f'Unsupported GR2 metadata member type {kind}')

    def matrix(self, transform):
        matrix = (c_float * 16)()
        self.dll.GrannyBuildCompositeTransform4x4(byref(transform), matrix)
        return np.array(matrix, dtype=np.float32).reshape(4, 4).T.copy()

    def texture(self, texture_ptr):
        """Detach top-level images as RGBA8; Granny decodes raw/Bink/S3TC."""
        texture = texture_ptr.contents
        result = dict(name=decode_string(texture.file_name), width=texture.width, height=texture.height,
                      texture_type=texture.texture_type, encoding=texture.encoding, sub_format=texture.sub_format,
                      props=self.variant(texture.extended_data), images=[])
        try:
            width, height = checked_count(texture.width, 32768), checked_count(texture.height, 32768)
            count = checked_count(texture.image_count, 256)
            if not count:
                return result  # External/reference-only texture with no payload.
            if not width or not height or not texture.images:
                raise ValueError('Missing GR2 texture dimensions or image array')
            checked_count(width * height * 4 * count, 256 * 1024 * 1024)
            layout = GrannyPixelLayout(4, (c_int * 4)(0, 8, 16, 24), (c_int * 4)(8, 8, 8, 8))
            for index in range(count):
                image = texture.images[index]
                mips = checked_count(image.mip_level_count, 32)
                if not mips:
                    continue
                if not image.mip_levels:
                    raise ValueError('Missing GR2 texture mip array')
                mip = image.mip_levels[0]
                if not checked_count(mip.pixel_byte_count, 256 * 1024 * 1024):
                    continue
                if not mip.pixel_bytes:
                    raise ValueError('Missing GR2 texture pixels')
                pixels = np.empty((height, width, 4), dtype=np.uint8)
                if not self.dll.GrannyCopyTextureImage(texture_ptr, index, 0, byref(layout),
                                                     width, height, width * 4, pixels.ctypes.data):
                    raise ValueError('Granny could not decode the texture encoding')
                result['images'].append(dict(index=index, mip_levels=mips, pixels=pixels))
        except ValueError as error:
            # Optional/unsupported textures should not discard usable geometry.
            result['error'] = str(error)
        return result

    @staticmethod
    def default_art_tool_info():
        """Assume Foundry's canonical GR2 basis when the source omits its basis."""
        return GrannyFileArtToolInfo(art_tool_name=b'Foundry defaults', units_per_meter=1 / .03048,
                                     right_vector=(c_float * 3)(0, -1, 0),
                                     up_vector=(c_float * 3)(0, 0, 1),
                                     back_vector=(c_float * 3)(-1, 0, 0))

    def source_basis(self, info, source_game=None):
        """Resolve Halo Maya's authored units without changing source metadata."""
        missing = not info.contents.art_tool_info
        tool = self.default_art_tool_info() if missing else info.contents.art_tool_info.contents
        units = float(tool.units_per_meter)
        if not isfinite(units) or units <= 0:
            raise ValueError('Invalid GR2 units per meter')
        basis = dict(art_tool=decode_string(tool.art_tool_name), units_per_meter=units,
                     effective_units_per_meter=units, unit_correction=1.0,
                     origin=list(tool.origin), right=list(tool.right_vector),
                     up=list(tool.up_vector), back=list(tool.back_vector))
        if missing:
            basis['coordinate_defaults'] = True
        if 'maya' in basis['art_tool'].casefold() and isclose(units, 100, rel_tol=1e-5):
            corinth = source_game in {'halo4', 'halo2a', 'corinth'}
            if not corinth:
                # Original 343 files often still declare Maya centimetres, but
                # their exported geometry/transforms use Halo feet. Inspect the
                # header too so direct/cross-project imports detect this case.
                for i in range(checked_count(info.contents.skeleton_count, 100_000)):
                    skeleton = info.contents.skeletons[i].contents
                    if decode_string(skeleton.name).casefold() != 'bungieexportinfo' or not skeleton.bone_count:
                        continue
                    props = self.variant(skeleton.bones[0].extended_data)
                    pending = [props]
                    while pending:
                        node = pending.pop()
                        corinth |= str(node.get('bungie_export_toolset', '')).casefold() in {'343', '343i'}
                        settings = str(node.get('bungie_export_granny_settings_file', '')).casefold()
                        corinth |= 'corinth' in settings
                        pending.extend(value for value in node.values() if isinstance(value, dict))
            if corinth:
                basis['effective_units_per_meter'] = 1 / .3048
                basis['unit_correction'] = units * .3048
        return basis

    def canonical_basis(self, info, source_game=None, *, convert_scale=True):
        """Convert axes and optionally units for geometry, bind poses and curves."""
        basis = self.source_basis(info, source_game)
        basis['convert_scale'] = convert_scale
        if not convert_scale:
            basis.update(effective_units_per_meter=basis['units_per_meter'], unit_correction=1.0)
        origin = (c_float * 3)(0, 0, 0)
        right = (c_float * 3)(0, -1, 0)
        up = (c_float * 3)(0, 0, 1)
        back = (c_float * 3)(-1, 0, 0)
        affine = (c_float * 3)()
        linear = (c_float * 9)()
        inverse = (c_float * 9)()
        missing = not info.contents.art_tool_info
        if missing:
            # Keep the temporary structure alive through both native calls and
            # remove its pointer before Granny frees the file's own memory.
            default_tool = self.default_art_tool_info()
            info.contents.art_tool_info = pointer(default_tool)
        tool = info.contents.art_tool_info.contents
        original_units = tool.units_per_meter
        target_units = 1 / .03048 if convert_scale else basis['units_per_meter']
        try:
            tool.units_per_meter = basis['effective_units_per_meter']
            try:
                converted = self.dll.GrannyComputeBasisConversion(info, target_units, origin, right, up, back, affine, linear, inverse)
            finally:
                tool.units_per_meter = original_units
            if not converted:
                raise ValueError('Could not convert GR2 coordinate system')
            self.dll.GrannyTransformFile(info, affine, linear, inverse, 1e-5, 1e-5, 3)
        finally:
            if missing:
                info.contents.art_tool_info = POINTER(GrannyFileArtToolInfo)()
        return basis

    def vertices(self, mesh_ptr):
        data = mesh_ptr.contents.primary_vertex_data.contents
        count = checked_count(data.vertex_count)
        source_members = list(self.members(data.vertex_type))
        # Let Granny unpack and normalize numeric vertex members to float32.
        definitions = (GrannyDataTypeDefinition * (len(source_members) + 1))()
        dtype = []
        names = []
        for i, (member, _, _) in enumerate(source_members):
            if not 10 <= member.member_type <= 21:
                raise ValueError('Unsupported nonnumeric GR2 vertex component')
            name = decode_string(member.name)
            definitions[i] = GrannyDataTypeDefinition(10, member.name, None, member.array_width)
            dtype.append((name, np.float32, (max(1, member.array_width),)))
            names.append(name)
        vertices = np.empty(count, dtype=dtype)
        self.dll.GrannyCopyMeshVertices(mesh_ptr, definitions, vertices.ctypes.data)
        # Broken UVs occur in shipped Max exports. Keep them for the adapter
        # to repair and report; positions and other components must be finite.
        if any(not np.isfinite(vertices[name]).all() for name in names
               if not name.startswith('TextureCoordinates') and name != 'lighting'):
            raise ValueError('Non-finite GR2 vertex data')
        return {name: vertices[name].copy() for name in names}

    def mesh(self, mesh_ptr):
        mesh = mesh_ptr.contents
        result = dict(name=decode_string(mesh.name), props=self.variant(mesh.extended_data),
                      materials=[pointer_address(mesh.material_bindings[i].material) for i in range(checked_count(mesh.material_binding_count, 100_000))],
                      bones=[decode_string(mesh.bone_bindings[i].bone_name) for i in range(checked_count(mesh.bone_bindings_count, 100_000))])
        if not mesh.primary_vertex_data or not mesh.primary_topology:
            # Max can include line/helper nodes in the mesh table with no
            # geometry. Keep their bindings and properties for reconstruction.
            result.update(vertices={}, component_names={}, triangles=np.empty((0, 3), dtype=np.int32),
                          groups=[], annotations={}, geometry_missing=[name for name in
                          ('primary_vertex_data', 'primary_topology') if not getattr(mesh, name)])
            return result
        vertex_data = mesh.primary_vertex_data.contents
        topology = mesh.primary_topology.contents
        if checked_count(vertex_data.vertex_count) == 0 and not (
                checked_count(topology.index_count, 30_000_000) or checked_count(topology.index16_count, 30_000_000)):
            # Some exporters allocate empty data/topology blocks for helpers
            # instead of leaving the pointers null (Spindle01, gate_house03).
            result.update(vertices={}, component_names={}, triangles=np.empty((0, 3), dtype=np.int32),
                          groups=[], annotations={}, geometry_missing=['vertices'])
            return result
        vertices = self.vertices(mesh_ptr)
        component_names = {
            decode_string(member.name): decode_string(vertex_data.vertex_component_names[i])
            for i, (member, _, _) in enumerate(self.members(vertex_data.vertex_type))
            if i < vertex_data.vertex_component_name_count
        }
        if 'Position' not in vertices:
            raise ValueError('GR2 mesh has no positions')
        count = topology.index_count or topology.index16_count
        checked_count(count, 30_000_000)
        source = topology.indices if topology.index_count else topology.indices16
        if count % 3 or (count and not source):
            raise ValueError('Invalid GR2 triangle index array')
        indices = np.ctypeslib.as_array(source, shape=(count,)).astype(np.int32).reshape(-1, 3) if count else np.empty((0, 3), dtype=np.int32)
        if indices.size and (indices.min() < 0 or indices.max() >= len(vertices['Position'])):
            raise ValueError('GR2 triangle index outside vertex array')
        annotations = {}
        for i in range(checked_count(topology.tri_annotation_set_count, 1024)):
            annotation = topology.tri_annotation_sets[i]
            count = checked_count(annotation.tri_annotation_count)
            if not count and not annotation.tri_annotation_index_count:
                # An optional annotation set with no records adds no override.
                continue
            stride = self.dll.GrannyGetTotalObjectSize(annotation.tri_annotation_type)
            address = pointer_address(annotation.tri_annotations)
            # Optional face overrides can contain NaN/Infinity in original Max
            # exports. Detach them intact so the adapter can retain the source
            # values and apply defaults only to the affected faces.
            records = [self.object(annotation.tri_annotation_type, address + j * stride, allow_nonfinite=True)
                       for j in range(count)]
            if annotation.tri_annotation_index_count:
                remap = [annotation.tri_annotation_indices[j] for j in range(checked_count(annotation.tri_annotation_index_count))]
                if any(j < 0 or j >= count for j in remap):
                    raise ValueError('Invalid GR2 triangle annotation index')
                records = [records[j] for j in remap]
            if len(records) != len(indices):
                raise ValueError('GR2 triangle annotation count does not match geometry')
            annotations[decode_string(annotation.name)] = records
        groups = [(topology.groups[i].material_index, topology.groups[i].tri_first, topology.groups[i].tri_count)
                  for i in range(checked_count(topology.group_count, 100_000))]
        result.update(vertices=vertices, component_names=component_names, triangles=indices,
                      groups=groups, annotations=annotations)
        return result

    def curve_samples(self, curve, dimension, duration, times, identity, normalize=False):
        identity = (c_float * dimension)(*identity)
        pointer = byref(curve)
        if self.dll.GrannyCurveIsIdentity(pointer):
            return [tuple(identity)] * len(times)
        if self.dll.GrannyCurveGetDimension(pointer) != dimension:
            raise ValueError('Invalid GR2 animation curve dimension')
        keyframed = self.dll.GrannyCurveIsKeyframed(pointer)
        knots = checked_count(self.dll.GrannyCurveGetKnotCount(pointer), 100_000)
        if keyframed and knots < len(times):
            raise ValueError('GR2 keyframe curve has fewer samples than the animation')
        result = (c_float * dimension)()
        samples = []
        for index, time in enumerate(times):
            if keyframed:
                # DaKeyframes32f has one control per animation sample and no
                # spline knots. EvaluateCurveAtT does not evaluate this format.
                self.dll.GrannyCurveExtractKnotValue(pointer, index, result, identity)
            else:
                self.dll.GrannyEvaluateCurveAtT(dimension, normalize, False, pointer, False, duration, time, result, identity)
            if not all(isfinite(value) for value in result):
                raise ValueError('Non-finite GR2 animation sample')
            sample = tuple(result)
            if normalize:
                length = sum(value * value for value in sample) ** .5
                if length < 1e-10:
                    raise ValueError('Invalid GR2 animation orientation')
                sample = tuple(value / length for value in sample)
            samples.append(sample)
        return samples

    def read(self, path, animations=True, *, source_game=None, convert_scale=True):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        file = self.dll.GrannyReadEntireFile(str(path).encode('utf-8'))
        if not file:
            raise ValueError(f'Could not read GR2 {path}')
        try:
            pointer = self.dll.GrannyGetFileInfo(file)
            if not pointer:
                raise ValueError('GR2 has no file info')
            basis = self.canonical_basis(pointer, source_game, convert_scale=convert_scale)
            info = pointer.contents
            result = dict(materials={}, textures={}, skeletons={}, meshes={}, models=[], animations=[],
                          props=self.variant(info.extended_data), source_basis=basis)
            texture_ptrs = [info.textures[i] for i in range(checked_count(info.texture_count, 100_000))]
            material_ptrs = [info.materials[i] for i in range(checked_count(info.material_count, 100_000))]
            while material_ptrs:
                ptr = material_ptrs.pop()
                address = pointer_address(ptr)
                if not address or address in result['materials']:
                    continue
                checked_count(len(result['materials']) + 1, 100_000)
                material = ptr.contents
                maps = [material.maps[i] for i in range(checked_count(material.map_count, 100_000))]
                result['materials'][address] = dict(name=decode_string(material.name), props=self.variant(material.extended_data),
                    texture=pointer_address(material.texture),
                    maps=[dict(usage=decode_string(mapping.usage), material=pointer_address(mapping.material)) for mapping in maps])
                material_ptrs.extend(mapping.material for mapping in maps)
                if material.texture:
                    texture_ptrs.append(material.texture)
            for ptr in texture_ptrs:
                address = pointer_address(ptr)
                if address and address not in result['textures']:
                    result['textures'][address] = self.texture(ptr)
            for i in range(checked_count(info.skeleton_count, 100_000)):
                ptr = info.skeletons[i]
                skeleton = ptr.contents
                bones = [dict(name=decode_string(skeleton.bones[j].name), parent=skeleton.bones[j].parent_index,
                              matrix=self.matrix(skeleton.bones[j].local_transform), props=self.variant(skeleton.bones[j].extended_data))
                         for j in range(checked_count(skeleton.bone_count, 100_000))]
                result['skeletons'][pointer_address(ptr)] = dict(name=decode_string(skeleton.name), bones=bones)
            for i in range(checked_count(info.mesh_count, 100_000)):
                ptr = info.meshes[i]
                result['meshes'][pointer_address(ptr)] = self.mesh(ptr)
            for i in range(checked_count(info.model_count, 100_000)):
                model = info.models[i].contents
                result['models'].append(dict(name=decode_string(model.name), skeleton=pointer_address(model.skeleton),
                                              matrix=self.matrix(model.initial_placement), props=self.variant(model.extended_data),
                                              meshes=[pointer_address(model.mesh_bindings[j].mesh) for j in range(checked_count(model.mesh_binding_count, 100_000))]))
            if animations:
                for i in range(checked_count(info.animation_count, 100_000)):
                    animation = info.animations[i].contents
                    dt, duration = animation.time_step, animation.duration
                    if not isfinite(duration) or not isfinite(dt) or duration < 0 or dt <= 0:
                        raise ValueError('Invalid GR2 animation timing')
                    # Duration is the last sample time, including Foundry's tiny
                    # endpoint epsilon, rather than the number of sample intervals.
                    count = checked_count(max(1, int(floor(duration / dt + .001)) + 1), 100_000)
                    times = [j * dt for j in range(count)]
                    groups = []
                    for j in range(checked_count(animation.track_group_count, 100_000)):
                        group = animation.track_groups[j].contents
                        tracks = []
                        for k in range(checked_count(group.transform_track_count, 100_000)):
                            track = group.transform_tracks[k]
                            tracks.append(dict(name=decode_string(track.name),
                                               positions=self.curve_samples(track.position_curve, 3, duration, times, (0, 0, 0)),
                                               orientations=self.curve_samples(track.orientation_curve, 4, duration, times, (0, 0, 0, 1), True),
                                               scales=self.curve_samples(track.scale_shear_curve, 9, duration, times, (1, 0, 0, 0, 1, 0, 0, 0, 1))))
                        name = decode_string(group.name)
                        source_skeleton = next((s for s in result['skeletons'].values() if s['name'].casefold() == name.casefold()), None)
                        root = next((b for b in source_skeleton['bones'] if b['parent'] == -1 and b['name'].casefold() == name.casefold()), None) if source_skeleton else None
                        groups.append(dict(name=name, tracks=tracks, root_rest=root['matrix'] if root else None))
                    result['animations'].append(dict(name=decode_string(animation.name), dt=dt, duration=duration, groups=groups))
            return result
        finally:
            self.dll.GrannyFreeFile(file)

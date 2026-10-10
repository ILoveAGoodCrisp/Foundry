"""Raw sampled skeletal/cinematic animation serialization, using only Python."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import struct

from .binary import BinaryWriteError, uint32
from .model import Scalar
from .transforms import float32


def int32(value, label):
    if not isinstance(value, int) or not -(2**31) <= value < 2**31:
        raise BinaryWriteError(f'{label} is outside int32 range')
    return value


def validate_track(track):
    curves = ((track.position, 3), (track.orientation, 4), (track.scale_shear, 9))
    if any(curve.controls.scalar is not Scalar.REAL32 or curve.controls.width != width for curve, width in curves):
        raise BinaryWriteError('Transform tracks require float32 position/orientation/scale widths 3/4/9')
    if len({curve.controls.count for curve, _ in curves}) != 1:
        raise BinaryWriteError('Transform track component sample counts differ')
    for curve, width in curves:
        int32(curve.controls.count*width, 'Curve scalar control count')
        if any(not isfinite(value) for (value,) in struct.iter_unpack('<f', curve.controls.data)):
            raise BinaryWriteError('Animation samples must contain finite float32 values')
    if any(abs(sum(v*v for v in row)-1) > 1e-3 for row in track.orientation.controls.rows()):
        raise BinaryWriteError('Animation orientation samples must be unit quaternions')
    int32(track.flags, 'Transform track flags')


def validate_vector(track):
    values = track.curve.controls
    if values.scalar is not Scalar.REAL32 or not 1 <= values.width <= 16:
        raise BinaryWriteError('Vector tracks require float32 vectors of dimension 1 through 16')
    int32(values.count*values.width, 'Vector scalar control count')
    if any(not isfinite(value) for (value,) in struct.iter_unpack('<f', values.data)):
        raise BinaryWriteError('Vector samples must contain finite values')
    if track.track_key is not None:
        uint32(track.track_key, 'Vector track key')


def validate_group(group):
    int32(group.flags, 'Track group flags')
    if len({track.name for track in group.transforms}) != len(group.transforms):
        raise BinaryWriteError('Track group contains duplicate transform track names')
    for track in group.transforms:
        validate_track(track)
    for track in group.vectors:
        validate_vector(track)
    if len({track.position.controls.count for track in group.transforms}
           | {track.curve.controls.count for track in group.vectors}) > 1:
        raise BinaryWriteError('Sampled track group has inconsistent frame counts')


def resolve_vector_keys(data, resolver=None):
    from .binary import iter_graph_objects
    from .model import Skeleton, VectorTrack
    from .vector_keys import vector_track_key_for_bone
    if resolver is None:
        resolver = vector_track_key_for_bone
    objects = tuple(iter_graph_objects(data))
    skeletons = [value for value in objects if isinstance(value, Skeleton)]
    keys = {}
    for track in (value for value in objects if isinstance(value, VectorTrack)):
        validate_vector(track)
        if track.track_key is not None:
            keys[id(track)] = track.track_key
            continue
        matches = [(skeleton, index) for skeleton in skeletons for index, bone in enumerate(skeleton.bones)
                   if bone.name == track.bone_name]
        if not matches:
            raise BinaryWriteError(f'Vector event references an absent bone: {track.bone_name}')
        values = {uint32(resolver(skeleton, index, track.name), 'Resolved vector track key') for skeleton, index in matches}
        if len(values) != 1:
            raise BinaryWriteError('Vector event bone is ambiguous across skeleton hierarchies; supply an authoritative track_key')
        keys[id(track)] = values.pop()
    return keys


def validate_animation(animation):
    duration, step, oversampling = (float32(value) for value in
        (animation.duration, animation.time_step, animation.oversampling))
    if duration < 0 or step <= 0 or oversampling <= 0:
        raise BinaryWriteError('Animation requires nonnegative duration and positive timestep/oversampling')
    int32(animation.flags, 'Animation flags')
    int32(animation.default_loop_count, 'Animation default loop count')


@dataclass(frozen=True, slots=True, eq=False)
class _Payload:
    value: object
    role: str


class AnimationEmitter:
    def __init__(self, emitter, properties, transforms, *, object_section=0, buffer_section=None, vector_keys=None):
        self.emitter, self.properties, self.transforms = emitter, properties, transforms
        self.builder, self.registry = emitter.builder, emitter.registry
        self.object_section = object_section
        self.buffer_section = object_section if buffer_section is None else buffer_section
        self.vector_keys = {} if vector_keys is None else vector_keys
        self._written, self._owners = set(), {}

    def owner(self, value, role):
        key = (id(value), role)
        if key not in self._owners:
            self._owners[key] = _Payload(value, role)
        return self._owners[key]

    def offset(self, schema, field):
        return self.registry.layout(schema).field(field).offset

    def string(self, address, value):
        self.builder.reference(address, self.builder.string(value, section=self.emitter.string_section))

    def curve(self, address, curve, role):
        schema = 'CurveDataDaKeyframes32f'
        header = self.emitter.reserve(schema, owner=self.owner(curve, role), section=self.object_section).block
        self.builder.reference(address, self.emitter.emit(schema))
        self.builder.reference(address.block.at(address.offset+8), header.at())
        if header in self._written:
            return
        self._written.add(header)
        values = curve.controls if role == 'vector' else self.transforms.sampled_buffer(curve.controls, role)
        # Format 0, degree 0; ControlCount is the scalar count, not frame count.
        header.pack(0, '<BBhi', 0, 0, values.width, values.count*values.width)
        payload = self.emitter.reserve('Real32', owner=self.owner(curve, role+'.controls'),
            count=values.count*values.width, section=self.buffer_section)
        payload.block.write(0, values.data)
        self.builder.reference(header.at(self.offset(schema, 'Controls')+4), payload.item(0))

    def group(self, group):
        validate_group(group)
        header = self.emitter.reserve('TrackGroup', owner=group, section=self.object_section).block
        if header in self._written:
            return header.at()
        self._written.add(header)
        self.string(header.at(self.offset('TrackGroup', 'Name')), group.name)
        sorted_tracks = bool(group.flags & 2)
        # SDK ResortTrackGroup leaves vectors in their original order; the
        # sorted flag controls transform-track ordering.
        vectors = group.vectors
        offset = self.offset('TrackGroup', 'VectorTracks')
        header.pack(offset, '<i', len(vectors))
        vector_array = self.emitter.reserve('VectorTrack', owner=self.owner(group.vectors, 'vectors'),
            count=len(vectors), section=self.object_section)
        if vector_array is not None:
            self.builder.reference(header.at(offset+4), vector_array.item(0))
            if vector_array.block not in self._written:
                self._written.add(vector_array.block)
                for index, track in enumerate(vectors):
                    start = index*vector_array.item_size
                    self.string(vector_array.block.at(start+self.offset('VectorTrack', 'Name')), track.name)
                    vector_array.block.pack(start+self.offset('VectorTrack', 'TrackKey'), '<Ii',
                        self.vector_keys[id(track)], track.curve.controls.width)
                    self.curve(vector_array.block.at(start+self.offset('VectorTrack', 'ValueCurve')), track.curve, 'vector')
        tracks = tuple(sorted(group.transforms, key=lambda track: track.name.encode('utf-8'))) if sorted_tracks else group.transforms
        offset = self.offset('TrackGroup', 'TransformTracks')
        header.pack(offset, '<i', len(tracks))
        array = self.emitter.reserve('TransformTrack', owner=self.owner(group.transforms,
            'tracks.sorted' if sorted_tracks else 'tracks.authored'), count=len(tracks), section=self.object_section)
        if array is not None:
            self.builder.reference(header.at(offset+4), array.item(0))
            if array.block not in self._written:
                self._written.add(array.block)
                for index, track in enumerate(tracks):
                    start = index*array.item_size
                    self.string(array.block.at(start+self.offset('TransformTrack', 'Name')), track.name)
                    array.block.pack(start+self.offset('TransformTrack', 'Flags'), '<i', track.flags)
                    for field, curve, role in (('PositionCurve', track.position, 'position'),
                            ('OrientationCurve', track.orientation, 'orientation'), ('ScaleShearCurve', track.scale_shear, 'scale_shear')):
                        self.curve(array.block.at(start+self.offset('TransformTrack', field)), curve, role)
        flags, values = self.transforms.transform(group.placement)
        header.pack(self.offset('TrackGroup', 'InitialPlacement'), '<I16f', flags, *values)
        header.pack(self.offset('TrackGroup', 'AccumulationFlags'), '<i', group.flags)
        self.properties.variant(header.at(self.offset('TrackGroup', 'ExtendedData')), group.metadata)
        return header.at()

    def animation(self, animation):
        validate_animation(animation)
        header = self.emitter.reserve('Animation', owner=animation, section=self.object_section).block
        if header in self._written:
            return header.at()
        self._written.add(header)
        self.string(header.at(self.offset('Animation', 'Name')), animation.name)
        header.pack(self.offset('Animation', 'Duration'), '<3f', animation.duration, animation.time_step, animation.oversampling)
        header.pack(self.offset('Animation', 'DefaultLoopCount'), '<2i', animation.default_loop_count, animation.flags)
        self.properties.variant(header.at(self.offset('Animation', 'ExtendedData')), animation.metadata)
        offset = self.offset('Animation', 'TrackGroups')
        header.pack(offset, '<i', len(animation.track_groups))
        array = self.builder.reserve_inline_array(self.owner(animation.track_groups, 'group_references'),
            len(animation.track_groups), 8, section=self.object_section)
        if array is not None:
            self.builder.reference(header.at(offset+4), array.item(0))
            if array.block not in self._written:
                self._written.add(array.block)
                for index, group in enumerate(animation.track_groups):
                    self.builder.reference(array.item(index), self.group(group))
        return header.at()

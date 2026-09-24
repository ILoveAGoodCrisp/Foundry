"""Convert decoded Reach pose screens and turns to legacy animation conventions."""
from math import pi

from mathutils import Matrix

from ... import utils
from .generate_aim_look_overlays import (
    _base_candidate_score, _compose_overlay_transform, _is_eligible_animation_mode,
    _WRAP_EVENT_NAMES, _WRAP_EVENT_TYPE,
)
from .legacy_turns import _TURN_DIRECTIONS


def _interpolate_pose(first, second, weight):
    result = []
    for a, b in zip(first, second):
        a_location, a_rotation, a_scale = a.decompose()
        b_location, b_rotation, b_scale = b.decompose()
        result.append(Matrix.LocRotScale(
            a_location.lerp(b_location, weight),
            a_rotation.slerp(b_rotation, weight),
            a_scale.lerp(b_scale, weight),
        ))
    return result


def _sample_axis(samples, coordinate, blend):
    samples = sorted(samples, key=lambda sample: sample[0])
    if coordinate <= samples[0][0]:
        return samples[0][1]
    for (low, first), (high, second) in zip(samples, samples[1:]):
        if coordinate <= high:
            return blend(first, second, (coordinate - low) / (high - low))
    return samples[-1][1]


def sample_pose_screen(vertices, poses, yaw, pitch, blend=_interpolate_pose, *, require_coverage=False):
    """Interpolate ragged yaw columns, clamping outside the authored aim limits."""
    columns = {}
    for (sample_yaw, sample_pitch), pose in zip(vertices, poses):
        # Wrapped duplicates belong to the Reach triangulation, not the old grid.
        if abs(sample_yaw) <= pi + 1e-5:
            columns.setdefault(round(sample_yaw, 5), {})[round(sample_pitch, 5)] = pose
    if require_coverage:
        columns = {yaw: column for yaw, column in columns.items()
                   if min(column) - 1e-5 <= pitch <= max(column) + 1e-5}
    if not columns or require_coverage and not min(columns) - 1e-5 <= yaw <= max(columns) + 1e-5:
        return None
    return _sample_axis([
        (column_yaw, _sample_axis(list(column.items()), pitch, blend))
        for column_yaw, column in columns.items()
    ], yaw, blend)


def _interpolate_weights(first, second, weight):
    return {frame: first.get(frame, 0.0) * (1.0 - weight) + second.get(frame, 0.0) * weight
            for frame in first.keys() | second.keys()}


def legacy_screen_vertices():
    # Legacy aim/look screens: down to up, each row right to left. The additive
    # reference is a separate leading frame and must not be included in this grid.
    return [(yaw, pitch) for pitch in (-pi / 2, 0.0, pi / 2)
            for yaw in (-pi / 2, 0.0, pi / 2)]


class LegacyAnimationConverter:
    def __init__(self, tag, nodes, animations, decode):
        self.tag = tag
        self.nodes = nodes
        self.animations = animations
        self.decode = decode
        self.frame_maps = {}
        self.frame_samples = {}
        self.converted_turns = set()
        self._screens = {}
        usages = tag._native_node_usages
        self.controls = {usages.get('pose blend yaw'), usages.get('pose blend pitch')}
        self.controls.discard(None)
        self.controls.update(index for index, node in enumerate(nodes)
                             if utils.remove_node_prefix(node.name).lower() in {'aim_yaw', 'aim_pitch'})
        pedestal = usages.get('pedestal', 0)
        self.preserved = set()
        node = nodes[pedestal] if 0 <= pedestal < len(nodes) else nodes[0]
        while node is not None and node not in self.preserved:
            self.preserved.add(node)
            node = node.parent

    def _screen(self, animation):
        if animation.index not in self._screens:
            vertices = self.tag._pose_overlay_blend_screen_vertices(animation)
            frames = self.decode(animation).frame_matrices()
            self._screens[animation.index] = (
                (vertices, frames) if vertices and len(vertices) == len(frames) - 1 else None)
        return self._screens[animation.index]

    def _turn_reference(self, turn):
        candidates = []
        for animation in self.animations:
            name = animation.name
            if (not animation.is_pose_overlay or name.state not in {'aim_still_up', 'aim_still'}
                    or not name.valid or name.custom or name.type != utils.AnimationStateType.ACTION):
                continue
            score = _base_candidate_score(turn.name, name, animation.index)
            if score is not None:
                candidates.append(((*score[:4], name.state == 'aim_still_up',
                                    name.variant == turn.name.variant, *score[4:]), animation))
        for _, animation in sorted(candidates, key=lambda item: item[0], reverse=True):
            screen = self._screen(animation)
            if screen is not None:
                vertices, frames = screen
                reference = sample_pose_screen(vertices, frames[1:], 0.0, 0.0, require_coverage=True)
                if reference is not None:
                    return reference
        return None

    def frames(self, animation, data):
        from ...tags.animation import AnimationType

        frames = data.frame_matrices()
        if not frames:
            return frames
        name = animation.name
        if (animation.animation_type == AnimationType.OVERLAY and animation.is_pose_overlay
                and (name.state in {'aim', 'look'} or name.state.startswith(('aim_', 'look_')))):
            screen = self._screen(animation)
            if screen is None:
                utils.print_warning(f"Skipping legacy screen conversion for [{name.data_name}]: missing blend-screen samples")
                return frames
            vertices, source_frames = screen
            targets = legacy_screen_vertices()
            samples = [sample_pose_screen(vertices, source_frames[1:], *vertex) for vertex in targets]
            if any(sample is None for sample in samples):
                return frames
            frames = [source_frames[0], *samples]
            # Control rotations describe Reach's triangulation; body transforms
            # are already baked by the native decoder, so keep these controls neutral.
            frames = [[frames[0][index] if index in self.controls else matrix
                       for index, matrix in enumerate(frame)] for frame in frames]
            self.frame_maps[animation.index] = {
                1: 1,
                **{index + 2: min(range(len(targets)), key=lambda target:
                    sum((a - b) ** 2 for a, b in zip(vertex, targets[target]))) + 2
                   for index, vertex in enumerate(vertices)},
            }
            source_weights = [{index + 2: 1.0} for index in range(len(vertices))]
            self.frame_samples[animation.index] = {
                1: {1: 1.0},
                **{index + 2: sample_pose_screen(vertices, source_weights, *vertex,
                                               blend=_interpolate_weights)
                   for index, vertex in enumerate(targets)},
            }
        elif (animation.animation_type in {AnimationType.NONE, AnimationType.BASE}
              and name.valid and not name.custom and name.type == utils.AnimationStateType.ACTION
              and name.state in _TURN_DIRECTIONS and _is_eligible_animation_mode(name.mode)):
            reference = self._turn_reference(animation)
            if reference is None:
                utils.print_warning(f"Skipping legacy turn conversion for [{name.data_name}]: no matching neutral aim sample")
                return frames
            first = frames[0]
            frames = [[matrix if node in self.preserved else
                       _compose_overlay_transform(first[index], matrix, reference[index])
                       for index, (node, matrix) in enumerate(zip(self.nodes, frame))]
                      for frame in frames]
            self.converted_turns.add(animation.index)
        return frames


def resample_screen_event_curves(animation, samples, preserved_curves):
    """Resample event influence and IK control curves added after the body bake."""
    visited = set()
    for track in animation.action_tracks:
        if track.action is None or track.object is None:
            continue
        for curve in utils.get_fcurves(track.action, track.object) or ():
            pointer = curve.as_pointer()
            if pointer in preserved_curves or pointer in visited:
                continue
            visited.add(pointer)
            values = {frame: sum(curve.evaluate(source) * weight for source, weight in weights.items())
                      for frame, weights in samples.items()}
            curve.keyframe_points.clear()
            for frame, value in values.items():
                key = curve.keyframe_points.insert(frame, value, options={'FAST'})
                key.interpolation = 'LINEAR'
            curve.update()


def remap_legacy_screen_events(animations, frame_maps):
    """Run after both regular and graph frame events have been imported."""
    for animation in animations:
        mapping = frame_maps.get(animation.name)
        if mapping is None:
            continue

        def remap(frame):
            return mapping[min(mapping, key=lambda source: abs(source - frame))]

        for index in reversed(range(len(animation.animation_events))):
            event = animation.animation_events[index]
            if event.event_type == _WRAP_EVENT_TYPE and event.import_name in _WRAP_EVENT_NAMES:
                animation.animation_events.remove(index)
                continue
            start, end = remap(event.frame_frame), remap(event.frame_range)
            event.frame_frame = min(start, end) if event.multi_frame == 'range' else start
            event.frame_range = max(start, end)
        # The graph stores a zero-based loop index, whereas Blender frames start at 1.
        animation.loop_frame_index = remap(animation.loop_frame_index + 1) - 1


def retarget_frame_parents(frame, nodes):
    """Fold unmapped source ancestors (notably pedestal) into the target skeleton."""
    world = {}

    def resolve(node):
        if node not in world:
            local = frame[node]
            world[node] = resolve(node.parent) @ local if node.parent in frame else local
        return world[node]

    mapped = {node.pose_bone.name: node for node in nodes if node.pose_bone is not None}
    result = {}
    for node in mapped.values():
        parent = node.pose_bone.parent
        if parent is None:
            result[node] = resolve(node)
        else:
            parent_node = mapped.get(parent.name)
            parent_world = resolve(parent_node) if parent_node is not None else parent.bone.matrix_local
            result[node] = parent_world.inverted_safe() @ resolve(node)
    return result

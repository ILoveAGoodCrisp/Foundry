"""Recover authoring reference poses without baking runtime parent corrections.

Codec decoding stays in blam-tags. This module uses the original channel masks,
parent references and model-space offsets to recover inputs expected by Tool.
Transforms use Halo units and (x, y, z, w) quaternions throughout.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import math
import struct

import numpy as np


@dataclass
class AuthoringResource:
    # Component order matches Tool's flags: rotation, translation, scale.
    animated: np.ndarray
    offsets: dict[int, np.ndarray]
    reference_object: dict[int, np.ndarray]
    fik_data: bytes


def _flags(data: bytes, count: int) -> np.ndarray:
    if not data:
        return np.zeros((count, 3), dtype=bool)
    width = ((count + 31) // 32) * 4
    if len(data) != width * 3:
        raise ValueError('Animation animated-node flags have an invalid size')
    return np.array([[bool(struct.unpack_from('<I', data, c * width + (i // 32) * 4)[0]
                           & (1 << (i % 32))) for c in range(3)] for i in range(count)])


def read_authoring_resource(tag, group: int, member: int, count: int) -> AuthoringResource | None:
    """Read the Reach/H4 positional resource layout; leave classic layouts alone."""
    root = tag.root()
    field = root.field('tag resource groups')
    if field is None or group < 0 or member < 0:
        return None
    groups = field.as_block()
    if group >= len(groups):
        raise ValueError('Animation resource group is out of range')
    resource = groups[group].field('tag_resource').as_resource().as_struct()
    members = resource.field('group_members').as_block()
    if member >= len(members):
        raise ValueError('Animation resource member is out of range')
    element = members[member]
    sizes = element.field('data sizes').as_struct().fields()
    if not any(f.name == 'object_space_offset_data' for f in sizes):
        return None
    blob = bytes(element.field('animation_data').value)
    sections = {}
    cursor = 0
    for field in sizes:
        size = int(field.value)
        if size < 0 or cursor + size > len(blob):
            raise ValueError('Animation resource section extends beyond its payload')
        sections[field.name] = blob[cursor:cursor + size]
        cursor += size
    # Names of the first four size fields predate their positional meanings.
    encoded_count = int(element.field('node count').value)
    if encoded_count < 0:
        encoded_count += 256
    encoded_flags = _flags(sections[sizes[3].name], encoded_count)
    animated = np.zeros((count, 3), dtype=bool)
    animated[:min(count, encoded_count)] = encoded_flags[:min(count, encoded_count)]
    frame_count = int(element.field('frame count').value)
    offsets = {}
    data = sections.get('object_space_offset_data', b'')
    if data:
        if len(data) < 12:
            raise ValueError('Object-space offset header is truncated')
        nodes, indices, orientations = struct.unpack_from('<III', data)
        if (nodes > count or indices < 12 or orientations < indices + nodes * 2
                or orientations + nodes * frame_count * 32 > len(data)):
            raise ValueError('Object-space offset arrays are out of range')
        for i in range(nodes):
            node = struct.unpack_from('<h', data, indices + i * 2)[0]
            if not 0 <= node < count or node in offsets:
                raise ValueError('Object-space offset node index is invalid or duplicated')
            values = np.frombuffer(data, dtype='<f4', count=frame_count * 8,
                                   offset=orientations + i * frame_count * 32).reshape(-1, 8).astype(float)
            # Serialized real_orientation: quaternion, translation, scale.
            offsets[node] = values[:, [4, 5, 6, 0, 1, 2, 3, 7]]
    reference = {}
    data = sections.get('uncompressed_object_space_data', b'')
    membership = sections.get('uncompressed_object_space_node_flags', b'')
    if data:
        if len(data) < 4:
            raise ValueError('Retained object-space header is truncated')
        nodes, frames = struct.unpack_from('<HH', data)
        if frames < 1 or len(data) != 4 + nodes * frames * 32:
            raise ValueError('Retained object-space tracks have an invalid size')
        present = [i for i in range(count) if i // 8 < len(membership)
                   and membership[i // 8] & (1 << (i % 8))]
        if not membership and nodes == count:
            present = list(range(count))
        if len(present) != nodes:
            raise ValueError('Retained object-space node membership does not match its tracks')
        for i, node in enumerate(present):
            values = np.frombuffer(data, dtype='<f4', count=8,
                                   offset=4 + i * frames * 32).astype(float)
            reference[node] = values[[4, 5, 6, 0, 1, 2, 3, 7]]
    return AuthoringResource(animated, offsets, reference, sections.get('fik_anchor_data', b''))


def qnormalize(q):
    length = np.linalg.norm(q, axis=-1, keepdims=True)
    if np.any(length < 1e-10) or not np.all(np.isfinite(q)):
        raise ValueError('Animation contains an invalid quaternion')
    return q / length


def qinverse(q):
    return q * np.array([-1., -1., -1., 1.])


def qmultiply(a, b):
    av, bv = a[..., :3], b[..., :3]
    aw, bw = a[..., 3:4], b[..., 3:4]
    return np.concatenate((aw * bv + bw * av + np.cross(av, bv),
                           aw * bw - np.sum(av * bv, axis=-1, keepdims=True)), axis=-1)


def qrotate(q, v):
    t = 2 * np.cross(q[..., :3], v)
    return v + q[..., 3:4] * t + np.cross(q[..., :3], t)


def hierarchy_order(parents):
    order, visiting, complete = [], set(), set()
    def visit(i):
        if i in complete:
            return
        if i in visiting:
            raise ValueError('Animation skeleton contains a parent cycle')
        visiting.add(i)
        parent = parents[i]
        if parent >= len(parents) or parent == i:
            raise ValueError('Animation skeleton contains an invalid parent')
        if parent >= 0:
            visit(parent)
        visiting.remove(i)
        complete.add(i)
        order.append(i)
    for i in range(len(parents)):
        visit(i)
    return order


def object_transforms(local, parents, order):
    result = local.copy()
    for i in order:
        p = parents[i]
        if p >= 0:
            result[..., i, :3] = result[..., p, :3] + qrotate(
                result[..., p, 3:7], local[..., i, :3] * result[..., p, 7:8])
            result[..., i, 3:7] = qmultiply(result[..., p, 3:7], local[..., i, 3:7])
            result[..., i, 7] = result[..., p, 7] * local[..., i, 7]
    return result


def local_transform(child, parent):
    result = child.copy()
    inverse = qinverse(parent[..., 3:7])
    result[..., :3] = qrotate(inverse, child[..., :3] - parent[..., :3]) / parent[..., 7:8]
    result[..., 3:7] = qmultiply(inverse, child[..., 3:7])
    result[..., 7] = child[..., 7] / parent[..., 7]
    return result


def authoring_pose(native_pose: dict, parents: list[int], resource: AuthoringResource,
                   parent_references: dict[int, tuple], overlay: bool) -> tuple[dict, dict]:
    """Preserve codec channels and recover the missing authoring reference basis.

    The input must be decoded with runtime object-space corrections disabled.
    Parent references describe the designated bone's *parent*, irrespective of
    the designated bone's component flags. Those flags classify playback data.
    """
    reference = np.asarray(native_pose['leading_frame'], dtype=float).copy()
    frames = np.asarray(native_pose['frames'], dtype=float).copy()
    count = len(parents)
    if reference.shape != (count, 8) or frames.ndim != 3 or frames.shape[1:] != (count, 8):
        raise ValueError('Animation authoring transforms do not match the skeleton')
    if not len(frames):
        return native_pose, {}
    if not np.all(np.isfinite(reference)) or not np.all(np.isfinite(frames)):
        raise ValueError('Animation authoring transforms contain non-finite values')
    reference[:, 3:7] = qnormalize(reference[:, 3:7])
    frames[..., 3:7] = qnormalize(frames[..., 3:7])
    if np.any(np.abs(reference[:, 7]) < 1e-8):
        raise ValueError('Animation reference contains a zero scale')
    order = hierarchy_order(parents)
    mask = resource.animated
    if mask.shape != (count, 3):
        raise ValueError('Animation channel masks do not match the skeleton')
    deltas = frames.copy()
    if overlay:
        deltas[..., :3] -= reference[:, :3]
        deltas[..., 3:7] = qmultiply(qinverse(reference[:, 3:7]), frames[..., 3:7])
        deltas[..., 7] /= reference[:, 7]

    targets = {int(i): np.asarray(t, dtype=float).copy() for i, t in resource.reference_object.items()}
    for node, transform in parent_references.items():
        if not 0 <= node < count:
            raise ValueError('Object-space parent reference node is out of range')
        parent = parents[node]
        # Tool records identity for a parentless node; it does not pin the node itself.
        if parent >= 0 and parent not in targets:
            targets[parent] = np.asarray(transform, dtype=float).copy()
    for target in targets.values():
        if not np.all(np.isfinite(target)) or abs(target[7]) < 1e-8:
            raise ValueError('Animation object-space reference contains an invalid transform')
        target[3:7] = qnormalize(target[3:7])

    def constrain_ref(ref):
        ref = ref.copy()
        objects = object_transforms(ref, parents, order)
        for i in order:
            p = parents[i]
            if i in targets:
                ref[i] = local_transform(targets[i], objects[p]) if p >= 0 else targets[i]
            if p >= 0:
                objects[i] = ref[i]
                objects[i, :3] = objects[p, :3] + qrotate(objects[p, 3:7], ref[i, :3] * objects[p, 7])
                objects[i, 3:7] = qmultiply(objects[p, 3:7], ref[i, 3:7])
                objects[i, 7] = objects[p, 7] * ref[i, 7]
            else:
                objects[i] = ref[i]
        return ref

    def compose(ref):
        body = np.broadcast_to(ref, frames.shape).copy()
        for component, (lo, hi) in enumerate(((3, 7), (0, 3), (7, 8))):
            enabled = mask[:, component]
            if overlay:
                if component == 0:
                    body[:, enabled, lo:hi] = qmultiply(ref[enabled, lo:hi], deltas[:, enabled, lo:hi])
                elif component == 1:
                    body[:, enabled, lo:hi] = ref[enabled, lo:hi] + deltas[:, enabled, lo:hi]
                else:
                    body[:, enabled, lo:hi] = ref[enabled, lo:hi] * deltas[:, enabled, lo:hi]
            else:
                body[:, enabled, lo:hi] = frames[:, enabled, lo:hi]
        return body

    reference = constrain_ref(reference)
    diagnostic = {'retained_reference_nodes': len(resource.reference_object), 'offset_fit_iterations': 0}
    offsets = resource.offsets if overlay else {}
    for node, values in offsets.items():
        if len(values) != len(frames):
            raise ValueError('Object-space offsets do not match the decoded pose sample count')
        if not np.all(np.isfinite(values[:, :7])):
            raise ValueError('Object-space offsets contain non-finite transforms')
    if offsets:
        offset_nodes = sorted(offsets)
        stored = np.stack([offsets[i] for i in offset_nodes], axis=1)
        stored[..., 3:7] = qnormalize(stored[..., 3:7])
        # Only reference channels on an offset node's ancestry can affect its data.
        ancestors = set()
        for node in offset_nodes:
            while node >= 0:
                ancestors.add(node)
                node = parents[node]
        variables = [(node, component, axis) for node in order if node in ancestors and node not in targets
                     for component in range(3) if mask[node, component]
                     for axis in range(1 if component == 2 else 3)]
        basis = reference.copy()

        def candidate(parameters):
            ref = basis.copy()
            rotations = np.zeros((count, 3))
            for value, (node, component, axis) in zip(parameters, variables):
                if component == 0:
                    rotations[node, axis] = value
                elif component == 1:
                    ref[node, axis] += value
                else:
                    ref[node, 7] *= math.exp(float(np.clip(value, -10, 10)))
            angle = np.linalg.norm(rotations, axis=1, keepdims=True)
            factor = np.divide(np.sin(angle / 2), angle, out=np.full_like(angle, .5), where=angle > 1e-12)
            q = np.concatenate((rotations * factor, np.cos(angle / 2)), axis=1)
            ref[:, 3:7] = qmultiply(ref[:, 3:7], q)
            return constrain_ref(ref)

        def errors(ref):
            ref_object = object_transforms(ref, parents, order)[offset_nodes]
            objects = object_transforms(compose(ref), parents, order)[:, offset_nodes]
            translation = objects[..., :3] - ref_object[:, :3] - stored[..., :3]
            rotation = qmultiply(qinverse(stored[..., 3:7]), qmultiply(
                qinverse(ref_object[:, 3:7]), objects[..., 3:7]))
            rotation *= np.where(rotation[..., 3:4] < 0, -1, 1)
            return translation, rotation

        def residual(parameters):
            translation, rotation = errors(candidate(parameters))
            return np.concatenate((translation.ravel(), (2 * rotation[..., :3]).ravel()))

        x = np.zeros(len(variables))
        r = residual(x)
        damping = 1e-4
        for iteration in range(60 if variables else 0):
            # Codec quantization gives a nonzero residual floor; do not chase it
            # after reaching 0.0002 Halo units / approximately .02 degrees.
            if np.max(np.abs(r)) < 2e-4:
                break
            columns = []
            step = 1e-5
            for j in range(len(x)):
                perturbed = x.copy(); perturbed[j] += step
                columns.append((residual(perturbed) - r) / step)
            jacobian = np.column_stack(columns)
            update = np.linalg.lstsq(np.vstack((jacobian, np.eye(len(x)) * math.sqrt(damping))),
                                     np.concatenate((-r, np.zeros(len(x)))), rcond=None)[0]
            length = np.linalg.norm(update)
            if length > .5:
                update *= .5 / length
            trial = x + update
            trial_r = residual(trial)
            if np.dot(trial_r, trial_r) < np.dot(r, r):
                x, r = trial, trial_r
                damping = max(damping / 3, 1e-10)
            else:
                damping = min(damping * 10, 1e8)
            diagnostic['offset_fit_iterations'] = iteration + 1
            if np.linalg.norm(update) < 1e-8:
                break
        reference = candidate(x)
        translation, rotation = errors(reference)
        diagnostic['offset_translation_error'] = float(np.max(np.linalg.norm(translation, axis=-1)))
        diagnostic['offset_rotation_error_degrees'] = float(np.max(2 * np.arctan2(
            np.linalg.norm(rotation[..., :3], axis=-1), np.abs(rotation[..., 3]))) * 180 / math.pi)
    body = compose(reference)
    # Quaternion sign is immaterial to the pose but must not manufacture animation.
    reference[:, 3:7] = qnormalize(reference[:, 3:7])
    body[..., 3:7] = qnormalize(body[..., 3:7])
    result = dict(native_pose)
    result['leading_frame'] = reference.tolist()
    result['frames'] = body.tolist()
    result['animated_node_flags'] = mask.tolist()
    return result, diagnostic


def source_metadata(resource: AuthoringResource, diagnostics: dict) -> dict:
    """Retain opaque FIK data without claiming to interpret the runtime solver."""
    return {'version': 1, 'animated_node_flags': resource.animated.tolist(),
            'fik_anchor_data': base64.b64encode(resource.fik_data).decode('ascii'),
            'reconstruction': diagnostics}

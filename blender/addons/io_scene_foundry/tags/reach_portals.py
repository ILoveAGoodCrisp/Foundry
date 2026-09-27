"""Recover connected Reach portal volumes from BSP leaf cluster boundaries.

Compiled portal outlines are visibility bounds, not necessarily sealed authoring
polygons. The collision tree and its leaf cluster table retain the actual cuts.
Solid-only branches may inherit their neighbour's cluster: this extends cuts
through walls without changing the classification of any original empty space.
"""
from dataclasses import replace
from functools import lru_cache
import math

import numpy as np

from .portal_reconstruction import reconstruct_portals


def unpack_collision_node(value):
    """Expand Reach's 16-bit plane / two 24-bit child designator."""
    def child(bits):
        if bits == 0xffffff:
            return 0xffffffff
        return (bits & 0x7fffff) | ((bits & 0x800000) << 8)
    return value & 0xffff, child((value >> 16) & 0xffffff), child((value >> 40) & 0xffffff)


def _clip(poly, plane, front):
    distances = [float(np.dot(p, plane[:3]) - plane[3]) for p in poly]
    if not front:
        distances = [-d for d in distances]
    if min(distances) >= -1e-8:
        return poly
    if max(distances) < -1e-8:
        return []
    result = []
    for a, b, da, db in zip(poly, poly[1:] + poly[:1], distances, distances[1:] + distances[:1]):
        if da >= -1e-8:
            result.append(a)
        if da < 0 < db or db < 0 < da:
            result.append(a + (b - a) * (da / (da - db)))
    return result


def _area(poly):
    if len(poly) < 3:
        return 0.0
    origin = poly[0]
    return float(np.linalg.norm(sum((np.cross(a - origin, b - origin)
                 for a, b in zip(poly, poly[1:] + poly[:1])), np.zeros(3)))) / 2


def _cluster_tree(data):
    """Collapse uniform-cluster branches, preserving every non-solid leaf."""
    planes, nodes, supers, clusters = (data[k] for k in ('planes', 'nodes', 'supernodes', 'clusters'))
    active = set()

    def combine(plane, back, front):
        if back is None:
            return front
        if front is None or back == front:
            return back
        return plane, back, front

    @lru_cache(None)
    def node(index, super_mode=False):
        index &= 0xffffffff
        if index == 0xffffffff:
            return None
        if index & 0x80000000:
            leaf = index & 0x7fffffff
            if leaf >= len(clusters) or clusters[leaf] < 0:
                raise ValueError('Portal BSP has an invalid leaf cluster')
            return clusters[leaf]
        key = index, super_mode
        if key in active:
            raise ValueError('Portal BSP contains a node cycle')
        active.add(key)
        try:
            if super_mode and not index & 0x40000000:
                if index >= len(supers):
                    raise ValueError('Portal BSP has an invalid supernode')
                return supernode(index, 0)
            index &= 0x3fffffff
            if index >= len(nodes):
                raise ValueError('Portal BSP has an invalid node')
            plane, back, front = nodes[index]
            if not 0 <= plane < len(planes):
                raise ValueError('Portal BSP has an invalid plane')
            return combine(plane, node(back), node(front))
        finally:
            active.remove(key)

    @lru_cache(None)
    def supernode(index, slot):
        values, children, dimensions = supers[index]
        if slot >= 15:
            child = children[slot - 15]
            return None if child == 0 else node(child, True)
        axis = (dimensions >> (slot * 2)) & 3
        if axis > 2:
            raise ValueError('Portal BSP has an invalid supernode axis')
        plane = [0.0, 0.0, 0.0, values[slot]]
        plane[axis] = 1.0
        return combine(tuple(plane), supernode(index, slot * 2 + 1),
                       supernode(index, slot * 2 + 2))

    try:
        return node(0, bool(supers))
    finally:
        node.cache_clear()
        supernode.cache_clear()


def reconstruct_reach_portals(records, data):
    """Use cluster cuts for connected volumes and H1 repair for isolated holes.

    Return one mesh record per original portal connection, with convex polygons
    in ``polygons``. Do not join different flags or invent cluster connections.
    Missing metadata retains the existing conservative reconstruction.
    """
    if not data or any(r.plane_index < 0 or r.back_cluster < 0 or r.front_cluster < 0 for r in records):
        return reconstruct_portals(records)[0]
    selected = set()
    for i, a in enumerate(records):
        for b in records[:i]:
            if a.plane_index != b.plane_index and any(
                    sum((x - y) ** 2 for x, y in zip(p, q)) < .0025 ** 2
                    for p in a.vertices for q in b.vertices):
                selected.update((a.plane_index, b.plane_index))
    if not selected:
        return reconstruct_portals(records)[0]

    owners = {}
    for record in records:
        if record.plane_index not in selected:
            continue
        key = record.plane_index, frozenset((record.back_cluster, record.front_cluster))
        if key in owners:
            # Distinct authored doors/flags on the same connection cannot be
            # recovered from the leaf cluster table alone.
            return reconstruct_portals(records)[0]
        owners[key] = record

    tree = _cluster_tree(data)
    planes = np.asarray(data['planes'], dtype=np.float64)
    bounds = data['bounds']
    recovered = {r.index: [] for r in owners.values()}
    for plane_index in sorted(selected):
        if not 0 <= plane_index < len(planes):
            raise ValueError('Portal plane is outside the collision plane table')
        length = np.linalg.norm(planes[plane_index, :3])
        if not math.isfinite(length) or length < .5:
            raise ValueError('Portal has an invalid cutting plane')
        plane = planes[plane_index] / length
        normal = plane[:3]
        center = np.array([sum(b) / 2 for b in bounds])
        center += normal * (plane[3] - np.dot(center, normal))
        u = np.cross(normal, (0, 0, 1) if abs(normal[2]) < .9 else (1, 0, 0))
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        radius = math.sqrt(sum((b - a) ** 2 for a, b in bounds))
        poly = [center + u*x*radius + v*y*radius for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        for axis, (low, high) in enumerate(bounds):
            constraint = np.zeros(4)
            constraint[axis] = 1
            constraint[3] = low
            poly = _clip(poly, constraint, True) if poly else []
            constraint[3] = high
            poly = _clip(poly, constraint, False) if poly else []

        def partition(branch, polygon, side):
            if len(polygon) < 3:
                return []
            if not isinstance(branch, tuple):
                return [(polygon, branch)]
            key, back, front = branch
            other = planes[key] if isinstance(key, int) else np.asarray(key)
            distances = [float(np.dot(p, other[:3]) - other[3]) for p in polygon]
            if max(abs(d) for d in distances) < 1e-7:
                return partition(front if np.dot(other[:3], normal)*side > 0 else back, polygon, side)
            return (partition(back, _clip(polygon, other, False), side)
                    + partition(front, _clip(polygon, other, True), side))

        for back_poly, back in partition(tree, poly, -1):
            for polygon, front in partition(tree, back_poly, 1):
                if back == front or back is None or front is None or _area(polygon) <= 1e-7:
                    continue
                record = owners.get((plane_index, frozenset((back, front))))
                if record is None:
                    continue
                original = np.asarray(record.vertices)
                winding = sum((np.cross(a - original[0], b - original[0])
                               for a, b in zip(original, np.roll(original, -1, axis=0))), np.zeros(3))
                if np.dot(winding, normal) < 0:
                    polygon = list(reversed(polygon))
                recovered[record.index].append(polygon)

    if any(not polygons for polygons in recovered.values()):
        return reconstruct_portals(records)[0]
    result = reconstruct_portals([r for r in records if r.plane_index not in selected])[0]
    for record in owners.values():
        vertices, faces = [], []
        for polygon in recovered[record.index]:
            faces.append(tuple(range(len(vertices), len(vertices) + len(polygon))))
            vertices.extend(tuple(map(float, p)) for p in polygon)
        result.append(replace(record, vertices=tuple(vertices), polygons=tuple(faces)))
    return sorted(result, key=lambda r: r.index)

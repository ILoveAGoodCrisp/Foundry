"""Stabilize H1 portal planes in final JMS coordinates, before serialization."""
from dataclasses import replace

import numpy as np


def planarize_halo1_portals(asset, tolerance=0.025):
    """Project compiler-roundoff onto one best-fit plane per connected portal.

    JMS units are 100 per tag world unit. Do this after export transforms:
    projecting in Blender first reintroduces float32 error during conversion.
    Do not flatten deliberately non-planar geometry or move structure vertices.
    """
    if asset.version != 8200:
        return 0
    parents = {}
    protected = set()

    def root(index):
        parents.setdefault(index, index)
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for triangle in asset.triangles:
        name = asset.materials[triangle.material].name.lower()
        if not name.startswith(('+portal', '+exactportal')):
            protected.update(triangle.vertices)
            continue
        a, b, c = triangle.vertices
        parents[root(b)] = root(a)
        parents[root(c)] = root(a)
    groups = {}
    for index in parents:
        groups.setdefault(root(index), []).append(index)
    corrected = 0
    for indices in groups.values():
        if len(indices) < 4 or protected.intersection(indices):
            continue
        points = np.array([asset.vertices[i].position for i in indices], dtype=np.float64)
        if not np.all(np.isfinite(points)):
            continue
        center = points.mean(axis=0)
        _, singular, axes = np.linalg.svd(points-center, full_matrices=False)
        if singular[1] <= 1e-10:
            continue
        normal = axes[-1]
        distances = (points-center) @ normal
        error = float(np.max(np.abs(distances)))
        if error <= 1e-10 or error > tolerance:
            continue
        projected = points - np.outer(distances, normal)
        for index, position in zip(indices, projected):
            asset.vertices[index] = replace(asset.vertices[index], position=tuple(position))
        corrected += 1
    return corrected

"""Small, bounded fixes for H1 structure collision in final JMS coordinates."""
from collections import defaultdict
from dataclasses import replace

import numpy as np


def stabilize_halo1_collision_slivers(asset, *, minimum_altitude=0.1):
    """Keep near-collinear sky shell triangles from opening the collision BSP.

    H1 Tool drops exceptionally thin triangles while building collision. Their
    three edges are then reported as open. Move the middle corner just enough
    to survive that reduction, together with all coincident JMS vertices so
    neighbouring render/collision faces retain their shared boundary. Units
    here are JMS units (100 per tag world unit).
    """
    if asset.version != 8200:
        return 0

    coincident = defaultdict(list)
    for index, vertex in enumerate(asset.vertices):
        coincident[tuple(vertex.position)].append(index)

    incident = defaultdict(set)
    for triangle_index, triangle in enumerate(asset.triangles):
        for vertex_index in triangle.vertices:
            incident[tuple(asset.vertices[vertex_index].position)].add(triangle_index)

    corrected = 0
    for triangle in asset.triangles:
        material = asset.materials[triangle.material].name.casefold()
        if not material.startswith(('+sky', '+seamsealer')):
            continue
        points = np.asarray([asset.vertices[i].position for i in triangle.vertices], dtype=np.float64)
        lengths = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
        longest = int(np.argmax(lengths))
        if lengths[longest] < 100:
            continue
        a, b, c = points[longest], points[(longest + 1) % 3], points[(longest + 2) % 3]
        direction = b - a
        fraction = float(np.dot(c - a, direction) / np.dot(direction, direction))
        if not 0.05 < fraction < 0.95:
            continue
        offset = c - (a + fraction * direction)
        altitude = float(np.linalg.norm(offset))
        if not 1e-8 < altitude < 0.01:
            continue

        key = tuple(asset.vertices[triangle.vertices[(longest + 2) % 3]].position)
        affected = incident[key]
        # Moving a vertex belonging to a portal or another helper can alter
        # that helper's plane. Leave such intersections for manual repair.
        if any(asset.materials[asset.triangles[i].material].name.casefold().startswith(
                ('+portal', '+exactportal', '+unused', '+weatherpoly')) for i in affected):
            continue
        displacement = offset * ((minimum_altitude - altitude) / altitude)
        if np.linalg.norm(displacement) > minimum_altitude:
            continue
        originals = {i: asset.vertices[i] for i in coincident[key]}
        before = {}
        for i in affected:
            tri = asset.triangles[i]
            p = np.asarray([asset.vertices[v].position for v in tri.vertices], dtype=np.float64)
            before[i] = np.cross(p[1] - p[0], p[2] - p[0])
        for index, vertex in originals.items():
            asset.vertices[index] = replace(vertex, position=tuple(np.asarray(vertex.position) + displacement))
        # Reject a correction that folds a neighbouring surface or collapses
        # a previously well-formed triangle.
        valid = True
        for i, old_normal in before.items():
            tri = asset.triangles[i]
            p = np.asarray([asset.vertices[v].position for v in tri.vertices], dtype=np.float64)
            new_normal = np.cross(p[1] - p[0], p[2] - p[0])
            if np.dot(old_normal, new_normal) <= 0 or (
                    np.linalg.norm(old_normal) > 1 and
                    np.linalg.norm(new_normal) < 0.5 * np.linalg.norm(old_normal)):
                valid = False
                break
        if valid:
            corrected += 1
            new_key = tuple(asset.vertices[next(iter(originals))].position)
            coincident[new_key] = coincident.pop(key)
            incident[new_key] = incident.pop(key)
        else:
            for index, vertex in originals.items():
                asset.vertices[index] = vertex
    return corrected

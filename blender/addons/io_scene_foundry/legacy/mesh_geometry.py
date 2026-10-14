"""Validate mesh data at the legacy interchange boundary."""
from dataclasses import replace
from math import hypot, isfinite


def _ass_mesh_is_clean(geometry):
    """Check the no-repair case in arrays, without changing any numeric data."""
    if len(geometry.triangles) < 32:
        return False
    try:
        import numpy as np
    except ImportError:
        return False

    positions = np.asarray([v.position for v in geometry.vertices])
    if positions.dtype != np.dtype(np.float64):
        # The exporter owns Python float records. Widening externally supplied
        # float32 or integer records would change the scalar repair arithmetic.
        return False
    used = np.zeros(len(geometry.vertices), dtype=bool)
    # Stay well clear of hypot's overflow boundary. Exceptional coordinates
    # use the scalar repair path, preserving its errors and arithmetic.
    limit = np.finfo(np.float64).max / 4
    with np.errstate(over='ignore', invalid='ignore', under='ignore'):
        for start in range(0, len(geometry.triangles), 65536):
            try:
                indices = np.asarray([t.vertices for t in geometry.triangles[start:start + 65536]],
                                     dtype=np.intp)
            except (OverflowError, TypeError, ValueError):
                return False
            if np.any(indices < 0) or np.any(indices >= len(positions)):
                return False
            a = positions[indices[:, 1]] - positions[indices[:, 0]]
            b = positions[indices[:, 2]] - positions[indices[:, 0]]
            normals = np.cross(a, b)
            if (not np.isfinite(normals).all() or np.any(np.abs(normals) > limit)
                    or np.any(np.all(normals == 0, axis=1))):
                return False
            used[indices.ravel()] = True
        if not used.all():
            return False
        for start in range(0, len(geometry.vertices), 65536):
            normals = np.asarray([v.normal for v in geometry.vertices[start:start + 65536]],
                                 dtype=np.float64)
            if not np.isfinite(normals).all() or np.any(np.all(normals == 0, axis=1)):
                return False
    return True


def clean_ass_mesh(geometry, *, preserve_degenerate=False):
    """Drop zero-area faces and recover invalid normals from incident faces.

    Preserve authored normals and all attributes on retained vertices. Use the
    largest incident face for recovery so opposing faces cannot cancel out.
    ASS structure compilation can use zero-area faces when constructing portal
    boundaries. Preserve those when requested, repairing their zero Blender
    normals instead of silently changing the native partition inputs.
    """
    if _ass_mesh_is_clean(geometry):
        return 0, 0
    triangles = []
    face_normals = {}
    used = set()
    removed = repaired = 0
    for triangle in geometry.triangles:
        points = [geometry.vertices[i].position for i in triangle.vertices]
        a = tuple(points[1][i] - points[0][i] for i in range(3))
        b = tuple(points[2][i] - points[0][i] for i in range(3))
        normal = (a[1] * b[2] - a[2] * b[1],
                  a[2] * b[0] - a[0] * b[2],
                  a[0] * b[1] - a[1] * b[0])
        length = hypot(*normal)
        if not isfinite(length):
            raise ValueError('ASS mesh contains non-finite triangle coordinates')
        if length == 0 and not preserve_degenerate:
            removed += 1
            continue
        triangles.append(triangle)
        used.update(triangle.vertices)
        if length == 0:
            continue
        for index in triangle.vertices:
            if index not in face_normals or length > face_normals[index][0]:
                face_normals[index] = length, normal

    remap = {}
    vertices = []
    coincident_normals = {}
    vertex_materials = {}
    if preserve_degenerate:
        for triangle in triangles:
            for index in triangle.vertices:
                vertex_materials.setdefault(index, set()).add(triangle.material)
        for index in sorted(used):
            vertex = geometry.vertices[index]
            length = hypot(*vertex.normal)
            if length > 0 and isfinite(length):
                for material in vertex_materials[index]:
                    key = (vertex.position, vertex.uvs, vertex.color, vertex.influences, material)
                    coincident_normals.setdefault(key, tuple(c / length for c in vertex.normal))
    for index, vertex in enumerate(geometry.vertices):
        if index not in used:
            continue
        length = hypot(*vertex.normal)
        if not all(isfinite(c) for c in vertex.normal) or length == 0:
            # Blender gives isolated zero-area corners a zero normal. Recover
            # from an equivalent current corner first: a synthetic up vector
            # can contaminate visible wall normals when Tool welds the faces.
            normal = next((coincident_normals[key] for material in sorted(vertex_materials.get(index, ()))
                           if (key := (vertex.position, vertex.uvs, vertex.color, vertex.influences, material))
                           in coincident_normals), None)
            if normal is None:
                face_length, face_normal = face_normals.get(index, (1, (0, 0, 1)))
                normal = tuple(c / face_length for c in face_normal)
            vertex = replace(vertex, normal=normal)
            repaired += 1
        remap[index] = len(vertices)
        vertices.append(vertex)
    geometry.vertices = vertices
    geometry.triangles = [replace(t, vertices=tuple(remap[i] for i in t.vertices))
                          for t in triangles]
    return removed, repaired

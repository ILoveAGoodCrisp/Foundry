"""Validate mesh data at the legacy interchange boundary."""
from dataclasses import replace
from math import hypot, isfinite


def clean_ass_mesh(geometry):
    """Drop zero-area faces and recover invalid normals from incident faces.

    Preserve authored normals and all attributes on retained vertices. Use the
    largest incident face for recovery so opposing faces cannot cancel out.
    """
    triangles = []
    face_normals = {}
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
        if length == 0:
            removed += 1
            continue
        triangles.append(triangle)
        for index in triangle.vertices:
            if index not in face_normals or length > face_normals[index][0]:
                face_normals[index] = length, normal

    remap = {}
    vertices = []
    for index, vertex in enumerate(geometry.vertices):
        if index not in face_normals:
            continue
        length = hypot(*vertex.normal)
        if not all(isfinite(c) for c in vertex.normal) or length == 0:
            face_length, normal = face_normals[index]
            vertex = replace(vertex, normal=tuple(c / face_length for c in normal))
            repaired += 1
        remap[index] = len(vertices)
        vertices.append(vertex)
    geometry.vertices = vertices
    geometry.triangles = [replace(t, vertices=tuple(remap[i] for i in t.vertices))
                          for t in triangles]
    return removed, repaired

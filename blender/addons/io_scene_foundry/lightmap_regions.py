"""Evaluated region geometry shared by ASS and lighting-info exports."""
import math

import bpy
from mathutils import Matrix, Vector


def capture_lightmap_region(proxy):
    """Snapshot local triangles before export visibility and frames are restored."""
    evaluated = getattr(proxy, 'eval_ob', None)
    if evaluated is None:
        evaluated = proxy.ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        triangles = tuple(tuple(tuple(mesh.vertices[index].co) for index in tri.vertices)
                          for tri in mesh.loop_triangles)
        if not all(math.isfinite(v) for tri in triangles for point in tri for v in point):
            raise ValueError(f'{proxy.name}: lightmap region contains non-finite vertices')
        return triangles
    finally:
        evaluated.to_mesh_clear()


def lightmap_region_triangles(proxy, matrix, *, mirror=False):
    triangles = getattr(proxy, 'lightmap_region_triangles', None)
    if triangles is None:
        triangles = capture_lightmap_region(proxy)
    if mirror:
        matrix = Matrix.Diagonal((1., -1., 1., 1.)) @ matrix
    order = (0, 2, 1) if matrix.determinant() < 0 else (0, 1, 2)
    result = tuple(tuple(tuple(matrix @ Vector(tri[index])) for index in order)
                   for tri in triangles)
    if not all(math.isfinite(v) for tri in result for point in tri for v in point):
        raise ValueError(f'{proxy.name}: lightmap region contains non-finite vertices')
    return result

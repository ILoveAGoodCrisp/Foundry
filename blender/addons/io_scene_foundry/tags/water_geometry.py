"""Preserve water paint coordinates independently of ordinary mesh UVs."""
import numpy as np



def water_triangle_uvs(water, reverse_winding=False):
    result = {}
    for triangle in water.triangles:
        order = (0, 2, 1) if reverse_winding else (0, 1, 2)
        pairs = [triangle[i] for i in order]
        if not all(0 <= wi < len(water.base_texcoords) for _, wi in pairs):
            continue
        result[tuple(ri for ri, _ in pairs)] = tuple(
            (water.base_texcoords[wi][0], 1 - water.base_texcoords[wi][1])
            for _, wi in pairs)
    return result


def set_water_uv_attribute(mesh, layer, source_triangles=None, first_vertex=0):
    """Use per-corner source water indices, including seams at shared vertices."""
    # The water shader reads the ordinary, editable second UV layer.
    existing = mesh.uv_layers.get('UVMap1')
    if existing is not None and existing != layer:
        existing.name = 'UVMap_detail'
    layer.name = 'UVMap1'
    values = np.empty(len(mesh.loops) * 2, np.float32)
    layer.data.foreach_get('uv', values)
    values = values.reshape(-1, 2)
    if source_triangles:
        for polygon in mesh.polygons:
            key = tuple(int(v) + first_vertex for v in polygon.vertices)
            source = source_triangles.get(key)
            if source is not None:
                values[polygon.loop_start:polygon.loop_start + polygon.loop_total] = source
        layer.data.foreach_set('uv', values.reshape(-1))

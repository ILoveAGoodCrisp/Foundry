"""Preserve water paint coordinates independently of ordinary mesh UVs."""
import numpy as np

WATER_UV_ATTRIBUTE = 'foundry_water_uv'


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
    attribute = mesh.attributes.get(WATER_UV_ATTRIBUTE)
    if attribute is None:
        attribute = mesh.attributes.new(WATER_UV_ATTRIBUTE, 'FLOAT_VECTOR', 'CORNER')
    vectors = np.zeros((len(values), 3), np.float32)
    vectors[:, :2] = values
    attribute.data.foreach_set('vector', vectors.reshape(-1))
    valid = mesh.attributes.get(WATER_UV_ATTRIBUTE + '_valid')
    if valid is None:
        valid = mesh.attributes.new(WATER_UV_ATTRIBUTE + '_valid', 'FLOAT', 'CORNER')
    valid.data.foreach_set('value', np.ones(len(values), np.float32))

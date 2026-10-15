"""Source identities for PCA imports after editable-mesh welding.

Point IDs select the current vertex's source. Corner IDs retain every original
seam vertex, so a later PCA group can separate a weld with differing motion.
IDs are one-based: zero on newly created geometry is not a valid source ID.
"""
from collections import defaultdict

import bmesh
import numpy as np

from .. import utils


SOURCE_TAG = 'foundry_pca_source_render_model'
SOURCE_MESH = 'foundry_pca_source_mesh_index'
SOURCE_COUNT = 'foundry_pca_source_vertex_count'
POINT_ID = '.foundry_pca_source_vertex'
CORNER_ID = '.foundry_pca_source_corner'


def normalized_tag_path(path):
    return str(path).replace('\\', '/').casefold()


def store_mapping(mesh, render_model, mesh_index, source_count, source_indices):
    """Record native identities before any vertex trimming, welding or sorting."""
    indices = np.asarray(source_indices, dtype=np.int32)
    if len(indices) != len(mesh.vertices) or np.any(indices < 0) or np.any(indices >= source_count):
        raise ValueError('PCA source vertex mapping does not match the imported mesh')
    mesh[SOURCE_TAG] = normalized_tag_path(render_model)
    mesh[SOURCE_MESH] = int(mesh_index)
    mesh[SOURCE_COUNT] = int(source_count)
    points = mesh.attributes.get(POINT_ID) or mesh.attributes.new(POINT_ID, 'INT', 'POINT')
    points.data.foreach_set('value', indices + 1)
    loops = np.empty(len(mesh.loops), dtype=np.int32)
    mesh.loops.foreach_get('vertex_index', loops)
    corners = mesh.attributes.get(CORNER_ID) or mesh.attributes.new(CORNER_ID, 'INT', 'CORNER')
    corners.data.foreach_set('value', indices[loops] + 1)


def source_mesh_index(mesh, render_model):
    if SOURCE_TAG not in mesh:
        return None
    if normalized_tag_path(mesh[SOURCE_TAG]) != normalized_tag_path(render_model):
        return None
    index = mesh.get(SOURCE_MESH)
    if not isinstance(index, int) or index < 0:
        raise ValueError(f'{mesh.name}: invalid PCA source mesh identity')
    return index


def vertex_indices(mesh, source_count):
    """Read current point IDs; never infer correspondence from positions."""
    if mesh.get(SOURCE_COUNT) != source_count:
        raise ValueError(f'{mesh.name}: PCA source vertex count has changed; reimport the model')
    result = []
    for name, domain, size in ((POINT_ID, 'POINT', len(mesh.vertices)),
                               (CORNER_ID, 'CORNER', len(mesh.loops))):
        attribute = mesh.attributes.get(name)
        if attribute is None or attribute.domain != domain or attribute.data_type != 'INT':
            raise ValueError(f'{mesh.name}: missing PCA source mapping; reimport the model')
        indices = np.empty(size, dtype=np.int32)
        attribute.data.foreach_get('value', indices)
        if np.any(indices <= 0) or np.any(indices > source_count):
            raise ValueError(f'{mesh.name}: unmapped geometry cannot receive source PCA animation')
        result.append(indices - 1)
    return tuple(result)


def prepare_mapping(mesh, source_positions, source_tension):
    """Split only welds that cannot represent the incoming group's point data.

    Existing shape keys, skin weights, UVs, materials and point attributes travel
    with BMesh elements. The original corner IDs survive both splitting and
    welding, including when clips are imported in separate Blender sessions.
    """
    count = source_positions.shape[1]
    points, corners = vertex_indices(mesh, count)
    signatures = [source_positions[:, i].tobytes() + source_tension[:, i].tobytes()
                  for i in range(count)]
    expected = [signatures[i] for i in points]
    conflicts = set()
    for loop, source in zip(mesh.loops, corners):
        if signatures[source] != expected[loop.vertex_index]:
            conflicts.add(loop.vertex_index)
    if not conflicts:
        return points

    bm = bmesh.new()
    preserve_normals = mesh.has_custom_normals
    try:
        bm.from_mesh(mesh)
        if preserve_normals:
            utils.save_loop_normals(bm, mesh)
        origin = bm.verts.layers.int.new('.foundry_pca_split_origin')
        point_layer = bm.verts.layers.int[POINT_ID]
        corner_layer = bm.loops.layers.int[CORNER_ID]
        for index, vertex in enumerate(bm.verts):
            vertex[origin] = index
        edges = {edge for vertex in bm.verts if vertex[origin] in conflicts for edge in vertex.link_edges}
        bmesh.ops.split_edges(bm, edges=list(edges))
        groups = defaultdict(list)
        for vertex in bm.verts:
            sources = [loop[corner_layer] - 1 for loop in vertex.link_loops]
            source = sources[0] if sources else vertex[point_layer] - 1
            signature = signatures[source]
            if any(signatures[other] != signature for other in sources):
                raise ValueError(f'{mesh.name}: could not separate conflicting PCA source vertices')
            vertex[point_layer] = source + 1
            groups[vertex[origin], signature].append(vertex)
        targets = {vertex: vertices[0] for vertices in groups.values() for vertex in vertices[1:]}
        if targets:
            bmesh.ops.weld_verts(bm, targetmap=targets)
        bm.verts.layers.int.remove(origin)
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if preserve_normals:
        utils.apply_loop_normals(mesh)
    mesh.update()
    return vertex_indices(mesh, count)[0]

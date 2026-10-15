"""Reassemble named source shapes without guessing across authoring boundaries."""
from collections import defaultdict
import json

import bmesh
import bpy
import numpy as np

from .. import utils


NAMES = 'foundry_source_shape_names'
FACE_SHAPE = '.foundry_source_shape'
POINT_SHAPE = '.foundry_source_vertex_shape'
VERTEX_KEY = '.foundry_source_vertex_key'
SHAPE_NAME = 'foundry_source_shape_name'
SHAPE_KEY = 'foundry_source_shape_key'
INSTANCE_NAME = 'foundry_source_instance_name'


def has_source_shapes(mesh):
    return mesh.attributes.get(FACE_SHAPE) is not None


def store_source_shapes(mesh, names, keys, vertex_start=0):
    """Store identities before topology cleanup, with zero for unknown faces."""
    if not names or not keys:
        return
    lookup = {key: i + 1 for i, (key, name) in enumerate(names)}
    subset = keys[vertex_start:vertex_start + len(mesh.vertices)]
    if len(subset) != len(mesh.vertices):
        return
    point_shapes = [lookup.get(key2, 0) for key1, key2 in subset]
    faces = []
    for face in mesh.polygons:
        shapes = {point_shapes[i] for i in face.vertices}
        faces.append(next(iter(shapes)) if len(shapes) == 1 else 0)
    if not any(faces):
        return
    mesh[NAMES] = json.dumps(names)
    for name, domain, values in ((FACE_SHAPE, 'FACE', faces),
                                 (POINT_SHAPE, 'POINT', point_shapes),
                                 (VERTEX_KEY, 'POINT', [k[0] for k in subset])):
        attr = mesh.attributes.new(name, 'INT', domain)
        attr.data.foreach_set('value', values)


def weld_source_vertices(mesh):
    """Reconnect equal keys only when all retained point data agree.

    Corner UVs, normals and PCA IDs survive. Avoid any weld that would collapse
    a face or merge overlapping faces. Positions alone never establish source
    identity, and opposite-facing compiled sheets remain separate.
    """
    if not has_source_shapes(mesh) or mesh.shape_keys:
        return
    shape_attr, key_attr = mesh.attributes.get(POINT_SHAPE), mesh.attributes.get(VERTEX_KEY)
    if shape_attr is None or key_attr is None:
        return
    # Point PCA IDs deliberately differ at a compiler split; corner IDs retain
    # the complete correspondence and prepare_mapping can separate later motion.
    ignored = {POINT_SHAPE, VERTEX_KEY, 'position', '.foundry_pca_source_vertex'}
    attributes = [a for a in mesh.attributes if a.domain == 'POINT'
                  and a.name not in ignored and not a.name.startswith('.select')]

    def value(item):
        for name in ('value', 'vector', 'color'):
            if hasattr(item, name):
                result = getattr(item, name)
                return result if isinstance(result, (int, float, bool, str)) else tuple(result)
        return None

    groups = defaultdict(list)
    for vertex in mesh.vertices:
        i = vertex.index
        shape = shape_attr.data[i].value
        if shape <= 0:
            continue
        signature = (shape, key_attr.data[i].value, tuple(vertex.co),
                     tuple(sorted((g.group, g.weight) for g in vertex.groups)),
                     tuple(value(a.data[i]) for a in attributes))
        groups[signature].append(i)
    targets = {i: vertices[0] for vertices in groups.values() for i in vertices[1:]}
    if not targets:
        return
    # Reject complete weld groups involved in a degeneracy/duplicate, including
    # front/back sheets with equal keys. No compiled face is silently discarded.
    seen = {}
    unsafe = set()
    for face in mesh.polygons:
        mapped = tuple(targets.get(i, i) for i in face.vertices)
        signature = tuple(sorted(mapped))
        if len(set(mapped)) != len(mapped):
            unsafe.update(mapped)
        if signature in seen:
            unsafe.update(mapped)
        seen[signature] = face.index
    targets = {i: target for i, target in targets.items() if target not in unsafe}
    if not targets:
        return
    bm = bmesh.new()
    normals = mesh.has_custom_normals
    try:
        bm.from_mesh(mesh)
        if normals:
            utils.save_loop_normals(bm, mesh)
        bm.verts.ensure_lookup_table()
        bmesh.ops.weld_verts(bm, targetmap={bm.verts[i]: bm.verts[target] for i, target in targets.items()})
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if normals:
        utils.apply_loop_normals(mesh)


def _split_mesh(mesh, names):
    attribute = mesh.attributes.get(FACE_SHAPE)
    if attribute is None:
        return [(0, mesh)]
    identities = np.empty(len(mesh.polygons), dtype=np.int32)
    attribute.data.foreach_get('value', identities)
    groups = sorted(set(map(int, identities)))
    if not groups or not any(0 < group <= len(names) for group in groups):
        return [(0, mesh)]
    # Invalid identities and generated/unknown faces stay together on the
    # original behaviour path rather than being assigned to a guessed shape.
    identities[(identities < 0) | (identities > len(names))] = 0
    groups = sorted(set(map(int, identities)))
    if len(groups) == 1:
        return [(groups[0], mesh)]
    result = []
    for group in groups:
        piece = mesh.copy()
        bm = bmesh.new()
        normals = mesh.has_custom_normals
        try:
            bm.from_mesh(piece)
            if normals:
                utils.save_loop_normals(bm, piece)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for i, f in enumerate(bm.faces) if identities[i] != group], context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            bm.to_mesh(piece)
        finally:
            bm.free()
        if normals:
            utils.apply_loop_normals(piece)
        if result:
            # A placement's complete collision/cookie/physics proxies remain
            # attached once, on its first piece, in the same coordinate space.
            for prop in piece.nwo.bl_rna.properties:
                if prop.identifier.startswith('proxy_') and prop.type == 'POINTER':
                    setattr(piece.nwo, prop.identifier, None)
        result.append((group, piece))
    return result


def reconstruct_objects(objects, names=None):
    """Split each placement independently; shared definitions remain shared.

    Call after material, region, permutation, collision and parent assignment.
    A source shape can have multiple objects where those semantics differ (or
    where facial animation uses different compiled mesh identities).
    """
    cache = {}
    old_meshes = set()
    result = []
    for ob in objects:
        if ob.type != 'MESH' or not has_source_shapes(ob.data):
            result.append(ob)
            continue
        source = ob.data
        shape_names = names if names is not None else json.loads(source.get(NAMES, '[]'))
        if not shape_names:
            result.append(ob)
            continue
        pieces = cache.get(source.as_pointer())
        if pieces is None:
            pieces = _split_mesh(source, shape_names)
            for identity, mesh in pieces:
                if identity:
                    mesh[NAMES] = json.dumps(shape_names)
                    mesh.name = shape_names[identity - 1][1]
                    weld_source_vertices(mesh)
                else:
                    for name in (FACE_SHAPE, POINT_SHAPE, VERTEX_KEY):
                        attr = mesh.attributes.get(name)
                        if attr is not None:
                            mesh.attributes.remove(attr)
                    if NAMES in mesh:
                        del mesh[NAMES]
                utils.calc_face_prop_counts(mesh)
            cache[source.as_pointer()] = pieces
        base_name = ob.name
        collections = tuple(ob.users_collection)
        has_proxy = any(prop.type == 'POINTER'
                        and (prop.identifier == 'proxy_collision' or prop.identifier.startswith('proxy_physics'))
                        and getattr(source.nwo, prop.identifier) is not None
                        for prop in source.nwo.bl_rna.properties)
        for index, (identity, mesh) in enumerate(pieces):
            piece = ob if index == 0 else ob.copy()
            piece.data = mesh
            if index:
                for collection in collections:
                    collection.objects.link(piece)
                if has_proxy:
                    piece.nwo.poop_render_only = True
            if identity:
                key, name = shape_names[identity - 1]
                piece[SHAPE_NAME], piece[SHAPE_KEY] = name, key
                if INSTANCE_NAME in piece:
                    piece.name = base_name if len(pieces) == 1 else f'{base_name}:{name}'
                else:
                    piece.name = name
            elif len(pieces) > 1:
                piece.name = f'{base_name}_unmapped'
            result.append(piece)
        if all(mesh != source for _, mesh in pieces):
            old_meshes.add(source)
    for mesh in old_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    return result

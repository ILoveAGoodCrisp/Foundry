"""Recover shared classic BSP surfaces independently of their triangulation.

Render and collision compilers split the same surface differently. Subtracting
the union of coplanar triangles keeps the render topology wherever possible.
Shared patch boundaries also recover non-planar authored polygons whose two
triangulations do not describe exactly the same surface.
"""
from collections import defaultdict
from dataclasses import dataclass
from math import floor, log2

import bmesh
import numpy as np
from mathutils import kdtree, bvhtree

from .. import utils


def _area(polygon):
    return abs(sum(a[0] * b[1] - a[1] * b[0]
                   for a, b in zip(polygon, polygon[1:] + polygon[:1]))) * 0.5


def _subtract(polygon, clip):
    """Partition a convex polygon into its intersection and disjoint remainder."""
    winding = sum(a[0] * b[1] - a[1] * b[0]
                  for a, b in zip(clip, clip[1:] + clip[:1]))
    sign = 1 if winding >= 0 else -1
    inside = polygon
    outside = []
    for a, b in zip(clip, clip[1:] + clip[:1]):
        if not inside:
            break
        dx, dy = b[0] - a[0], b[1] - a[1]
        distances = [sign * (dx * (p[1] - a[1]) - dy * (p[0] - a[0]))
                     for p in inside]
        positive, negative = [], []
        for index, p in enumerate(inside):
            q = inside[(index + 1) % len(inside)]
            dp, dq = distances[index], distances[(index + 1) % len(inside)]
            if dp >= 0:
                positive.append(p)
            if dp <= 0:
                negative.append(p)
            if (dp > 0 and dq < 0) or (dp < 0 and dq > 0):
                t = dp / (dp - dq)
                point = (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
                positive.append(point)
                negative.append(point)
        if len(negative) >= 3 and _area(negative) > 0:
            outside.append(negative)
        inside = positive if len(positive) >= 3 else []
    # A cutter with no positive-area intersection must not subdivide the face.
    if not inside or _area(inside) == 0:
        return [polygon], []
    return outside, inside


@dataclass
class _Triangle:
    polygon: int
    coords: np.ndarray
    normal: np.ndarray
    minimum: np.ndarray
    maximum: np.ndarray
    center: np.ndarray
    radius: float


def _triangles(mesh):
    mesh.calc_loop_triangles()
    positions = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
    mesh.vertices.foreach_get('co', positions)
    positions = positions.reshape((-1, 3))
    result = []
    for tri in mesh.loop_triangles:
        material = mesh.materials[tri.material_index] if tri.material_index < len(mesh.materials) else None
        # Sky, seam sealers, ladders, etc. are authored helper geometry. Their
        # semantics come from the special material, not spatial coincidence.
        if material is not None and material.name.lstrip().startswith('+'):
            continue
        coords = positions[list(tri.vertices)]
        normal = np.cross(coords[1] - coords[0], coords[2] - coords[0])
        length = np.linalg.norm(normal)
        if length == 0:
            continue
        minimum, maximum = coords.min(axis=0), coords.max(axis=0)
        center = (minimum + maximum) * 0.5
        result.append(_Triangle(
            tri.polygon_index, coords, normal / length, minimum, maximum,
            center, float(np.linalg.norm(maximum - minimum) * 0.5)))
    return result


def _candidates(render, collision, tolerance):
    # Bucket bounding spheres by size. Including BOTH radii also finds large
    # render triangles whose centres lie outside a small collision triangle.
    buckets = defaultdict(list)
    for index, triangle in enumerate(render):
        buckets[floor(log2(max(triangle.radius, tolerance)))].append(index)
    trees = []
    for indices in buckets.values():
        tree = kdtree.KDTree(len(indices))
        for index in indices:
            tree.insert(render[index].center, index)
        tree.balance()
        trees.append((tree, max(render[index].radius for index in indices)))

    render_matches, collision_matches = defaultdict(list), defaultdict(list)
    for collision_index, c in enumerate(collision):
        for tree, radius in trees:
            for _, render_index, _ in tree.find_range(c.center, c.radius + radius + tolerance):
                r = render[render_index]
                if np.any(c.maximum < r.minimum - tolerance) or np.any(r.maximum < c.minimum - tolerance):
                    continue
                # Very thin compiled triangles have unstable normals. The
                # all-vertex plane distances below are the decisive check.
                if abs(float(c.normal @ r.normal)) < 0.999:
                    continue
                # Check every vertex, in both directions: a centre-only test
                # can merge triangles which cross instead of sharing a plane.
                if (np.max(np.abs((r.coords - c.coords[0]) @ c.normal)) > tolerance
                        or np.max(np.abs((c.coords - r.coords[0]) @ r.normal)) > tolerance):
                    continue
                render_matches[render_index].append(collision_index)
                collision_matches[collision_index].append(render_index)
    return render_matches, collision_matches


def _partition(triangle, cutters, tolerance):
    origin = triangle.coords[0]
    drop_axis = int(np.argmax(np.abs(triangle.normal)))
    axes = [axis for axis in range(3) if axis != drop_axis]
    polygon = [tuple(point) for point in (triangle.coords - origin)[:, axes]]
    area = _area(polygon)
    # Ignore only narrow numeric cracks, with a relative cap so tiny faces are
    # not classified as covered just because their area is below a fixed epsilon.
    perimeter = sum(np.linalg.norm(b - a) for a, b in zip(
        triangle.coords, np.roll(triangle.coords, -1, axis=0)))
    area_tolerance = min(area * 0.001, tolerance * perimeter)
    remaining, covered = [polygon], []
    for cutter in cutters:
        clip = [tuple(point) for point in (cutter.coords - origin)[:, axes]]
        next_remaining = []
        for piece in remaining:
            outside, inside = _subtract(piece, clip)
            next_remaining.extend(outside)
            if inside:
                covered.append(inside)
        remaining = next_remaining
        if sum(_area(piece) for piece in remaining) <= area_tolerance:
            return [], [triangle.coords.tolist()]
    if sum(_area(piece) for piece in covered) <= area_tolerance:
        return [triangle.coords.tolist()], []

    def unproject(pieces):
        result = []
        for piece in pieces:
            if _area(piece) <= area * 1e-10:
                continue
            points = []
            for x, y in piece:
                point = np.zeros(3)
                point[axes] = (x, y)
                point[drop_axis] = -float(point @ triangle.normal) / triangle.normal[drop_axis]
                points.append((point + origin).tolist())
            result.append(points)
        return result

    return unproject(remaining), unproject(covered)


def _patch_edges(mesh, vertex_ids, face_indices):
    edges = defaultdict(list)
    for index in face_indices:
        vertices = [vertex_ids[i] for i in mesh.polygons[index].vertices]
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            if a != b:
                edges[tuple(sorted((a, b)))].append(index)
    return edges


def _boundary_patches(edges, common_edges, face_indices):
    """Internal edges present in just one mesh are compiler triangulation cuts."""
    neighbours = defaultdict(set)
    face_edges = defaultdict(list)
    for edge, faces in edges.items():
        for face in faces:
            face_edges[face].append(edge)
        if edge not in common_edges and len(faces) == 2:
            a, b = faces
            neighbours[a].add(b)
            neighbours[b].add(a)
    pending = set(face_indices)
    patches = defaultdict(list)
    while pending:
        start = pending.pop()
        component, todo = {start}, [start]
        while todo:
            for face in neighbours[todo.pop()]:
                if face in pending:
                    pending.remove(face)
                    component.add(face)
                    todo.append(face)
        counts = defaultdict(int)
        for face in component:
            for edge in face_edges[face]:
                counts[edge] += 1
        boundary = frozenset(edge for edge, count in counts.items() if count == 1)
        # A closed shell or non-manifold patch has no unambiguous authored
        # polygon boundary. Neither is evidence for a shared surface.
        if not boundary or not boundary.issubset(common_edges) or any(n > 2 for n in counts.values()):
            continue
        degree = defaultdict(int)
        for a, b in boundary:
            degree[a] += 1
            degree[b] += 1
        if any(n != 2 for n in degree.values()):
            continue
        patches[boundary].append(component)
    return patches


def _patch_vertices_match(mesh, faces, ids, other_mesh, other_faces, other_ids, tolerance):
    """Reject different surfaces bulging away from an otherwise shared border."""
    vertices = {v for face in faces for v in mesh.polygons[face].vertices}
    other_vertices = {v for face in other_faces for v in other_mesh.polygons[face].vertices}
    shared_ids = {other_ids[v] for v in other_vertices}
    unmatched = [v for v in vertices if ids[v] not in shared_ids]
    if not unmatched:
        return True
    indices = sorted(other_vertices)
    remap = {v: i for i, v in enumerate(indices)}
    tree = bvhtree.BVHTree.FromPolygons(
        [other_mesh.vertices[v].co for v in indices],
        [tuple(remap[v] for v in other_mesh.polygons[f].vertices) for f in other_faces])
    for vertex in unmatched:
        _, _, _, distance = tree.find_nearest(mesh.vertices[vertex].co)
        if distance is None or distance > tolerance:
            return False
    return True


def _match_boundary_patches(render_mesh, collision_mesh, render, collision,
                           render_parts, collision_parts, tolerance):
    """Match warped authored polygons by their shared border, not their diagonals.

    Only unique, closed matching boundaries qualify. Additional interior
    vertices must lie on the opposite surface, so a raised detail cannot claim
    the collision of a flat polygon just because it has the same outside edge.
    """
    if not any(uncovered for uncovered, _ in render_parts.values()):
        return
    positions = {}
    render_ids = []
    for vertex in render_mesh.vertices:
        key = tuple(vertex.co)
        render_ids.append(positions.setdefault(key, len(positions)))
    tree = kdtree.KDTree(len(positions))
    for point, index in positions.items():
        tree.insert(point, index)
    tree.balance()
    collision_ids, collision_positions = [], {}
    for vertex in collision_mesh.vertices:
        key = tuple(vertex.co)
        index = collision_positions.get(key)
        if index is None:
            _, nearest, distance = tree.find(vertex.co)
            index = nearest if distance <= tolerance else -len(collision_positions) - 1
            collision_positions[key] = index
        collision_ids.append(index)

    render_faces = {triangle.polygon for triangle in render}
    collision_faces = {triangle.polygon for triangle in collision}
    render_edges = _patch_edges(render_mesh, render_ids, render_faces)
    collision_edges = _patch_edges(collision_mesh, collision_ids, collision_faces)
    common_edges = render_edges.keys() & collision_edges.keys()
    render_patches = _boundary_patches(render_edges, common_edges, render_faces)
    collision_patches = _boundary_patches(collision_edges, common_edges, collision_faces)
    for boundary, rpatches in render_patches.items():
        cpatches = collision_patches.get(boundary, ())
        if len(rpatches) != 1 or len(cpatches) != 1:
            continue
        rfaces, cfaces = rpatches[0], cpatches[0]
        if not any(render_parts[f][0] for f in rfaces):
            continue
        if not _patch_vertices_match(render_mesh, rfaces, render_ids,
                                     collision_mesh, cfaces, collision_ids, tolerance):
            continue
        if not _patch_vertices_match(collision_mesh, cfaces, collision_ids,
                                     render_mesh, rfaces, render_ids, tolerance):
            continue
        for mesh, faces, parts in ((render_mesh, rfaces, render_parts),
                                   (collision_mesh, cfaces, collision_parts)):
            for index in faces:
                parts[index] = ([], [[tuple(mesh.vertices[v].co)
                                      for v in mesh.polygons[index].vertices]])


def _replace_faces(mesh, partitions, render):
    """Retain whole render faces; interpolate UVs/normals only at real boundaries."""
    if not mesh.polygons:
        return
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        utils.save_loop_normals(bm, mesh)
        mode = utils.add_face_prop(mesh, 'face_mode', np.ones(len(mesh.polygons), dtype=np.int8))
        mode.face_mode = 'render_only' if render else 'collision_only'
        layer = bm.faces.layers.bool.new(mode.attribute_name)
        original_faces = list(bm.faces)
        for index, face in enumerate(original_faces):
            uncovered, covered = partitions.get(index, ([], []))
            if not covered:
                face[layer] = True
                continue
            if not uncovered:
                if not render:
                    bm.faces.remove(face)
                continue
            # This face straddles the boundary of the other mesh. Split only
            # here; differing internal diagonals should not affect render UVs.
            source_coords = np.array([tuple(v.co) for v in face.verts])
            # Relative coordinates keep interpolation stable far from origin.
            origin = source_coords[0]
            basis = np.vstack(((source_coords - origin).T, np.ones(len(source_coords))))
            source_normals = np.array([tuple(face[bm.faces.layers.float_vector[f'ln{j}']])
                                       for j in range(len(face.verts))])
            for pieces, is_uncovered in ((uncovered, True), (covered, False)):
                if not render and not is_uncovered:
                    continue
                for points in pieces:
                    # A fan keeps normal storage compatible with Foundry's
                    # per-face ln0/ln1/ln2 attributes, including clipped quads.
                    for i in range(1, len(points) - 1):
                        coords = [points[0], points[i], points[i + 1]]
                        if np.linalg.norm(np.cross(np.subtract(coords[1], coords[0]),
                                                   np.subtract(coords[2], coords[0]))) == 0:
                            continue
                        vertices = [bm.verts.new(point) for point in coords]
                        new_face = bm.faces.new(vertices, face)
                        new_face[layer] = is_uncovered
                        for loop in new_face.loops:
                            loop.copy_from_face_interp(face, True)
                        for j, point in enumerate(coords):
                            weights = np.linalg.lstsq(basis, [*(point - origin), 1], rcond=None)[0]
                            normal = weights @ source_normals
                            length = np.linalg.norm(normal)
                            if length:
                                normal /= length
                            new_face[bm.faces.layers.float_vector[f'ln{j}']] = normal
            bm.faces.remove(face)
        # Face removal alone leaves loose collision edges/vertices in the result.
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if mesh.polygons:
        utils.apply_loop_normals(mesh)
    utils.calc_face_prop_counts(mesh)


def merge_classic_surfaces(render_mesh, collision_mesh, tolerance):
    """Recover shared surfaces by planar coverage and matching patch boundaries."""
    render, collision = _triangles(render_mesh), _triangles(collision_mesh)
    render_matches, collision_matches = _candidates(render, collision, tolerance)
    mesh_partitions = []
    for triangles, cutters, matches in (
        (render, collision, render_matches),
        (collision, render, collision_matches),
    ):
        partitions = defaultdict(lambda: ([], []))
        for index, triangle in enumerate(triangles):
            uncovered, covered = _partition(
                triangle, (cutters[i] for i in sorted(matches.get(index, ()))), tolerance)
            partitions[triangle.polygon][0].extend(uncovered)
            partitions[triangle.polygon][1].extend(covered)
        mesh_partitions.append(partitions)
    _match_boundary_patches(render_mesh, collision_mesh, render, collision,
                           *mesh_partitions, tolerance)
    _replace_faces(render_mesh, mesh_partitions[0], True)
    _replace_faces(collision_mesh, mesh_partitions[1], False)

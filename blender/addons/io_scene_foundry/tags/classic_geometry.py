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
    material: object


def _material_key(material):
    """Compare shader references, not material slot numbers or display names."""
    if material is not None and material.nwo.shader_path:
        return material.nwo.shader_path.replace('/', '\\').strip('\\').casefold()
    return material


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
        if (material is not None and material.name.lstrip().startswith('+')
                and not material.nwo.shader_path):
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
            center, float(np.linalg.norm(maximum - minimum) * 0.5), _material_key(material)))
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
                if r.material != c.material:
                    continue
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
    if not any(uncovered for parts in (render_parts, collision_parts)
               for uncovered, _ in parts.values()):
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

    # At an intersection of planes, compiler roundoff can displace a corner
    # farther than the surface tolerance. Recover its identity when two
    # matched neighbours and the incident planes agree, or three matched
    # neighbours establish the same corner despite slightly larger plane error.
    # This does not move vertices or relax the planar overlap tests.
    render_neighbours, collision_neighbours = defaultdict(set), defaultdict(set)
    render_normals = defaultdict(list)
    for triangles, mesh, ids, neighbours in (
        (render, render_mesh, render_ids, render_neighbours),
        (collision, collision_mesh, collision_ids, collision_neighbours),
    ):
        for triangle in triangles:
            vertices = [ids[v] for v in mesh.polygons[triangle.polygon].vertices]
            for a, b in zip(vertices, vertices[1:] + vertices[:1]):
                neighbours[a].add(b)
                neighbours[b].add(a)
            if mesh == render_mesh:
                for vertex in vertices:
                    render_normals[vertex].append(triangle.normal)
    corner_matches = {}
    for point, index in collision_positions.items():
        if index >= 0:
            continue
        candidates = []
        for co, candidate, _ in tree.find_range(point, tolerance * 2):
            shared_neighbours = collision_neighbours[index] & render_neighbours[candidate]
            if len(shared_neighbours) < 2:
                continue
            displacement = np.subtract(point, co)
            # Some H1 compiler corners exceed the plane tolerance as well
            # (b40_c1). Three independently matched edge neighbours identify
            # the corner even then. Keep the bounded search, unique candidate,
            # material and closed-patch checks; do not widen planar matching.
            if len(shared_neighbours) >= 3 or all(
                    abs(float(displacement @ normal)) <= tolerance
                    for normal in render_normals[candidate]):
                candidates.append(candidate)
        if len(candidates) == 1:
            corner_matches[index] = candidates[0]
    if corner_matches:
        collision_ids = [corner_matches.get(index, index) for index in collision_ids]

    # Material boundaries are authored boundaries too. A coplanar light/decal
    # must not become part of a wall's collision through this fallback match.
    render_groups, collision_groups = defaultdict(set), defaultdict(set)
    for triangle in render:
        render_groups[triangle.material].add(triangle.polygon)
    for triangle in collision:
        collision_groups[triangle.material].add(triangle.polygon)
    groups = [(render_groups[material], collision_groups[material])
              for material in render_groups.keys() & collision_groups.keys()]
    # Opposite sides of a sheet can have different diagonals. Combining both
    # sides in an undirected edge map hides their boundary (or makes it appear
    # non-manifold). Match each orientation separately as well. Try each axis
    # so slightly warped faces near a dominant-axis tie stay in the same patch.
    for axis in range(3):
        oriented = []
        for triangles in (render, collision):
            directions = defaultdict(set)
            for triangle in triangles:
                component = triangle.normal[axis]
                if abs(component) > 0.5:
                    directions[triangle.material, component > 0].add(triangle.polygon)
            oriented.append(directions)
        for (material, sign), faces in oriented[0].items():
            for other_sign in (sign, not sign):
                other_faces = oriented[1].get((material, other_sign))
                if other_faces:
                    groups.append((faces, other_faces))
    for render_faces, collision_faces in groups:
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
            if not (any(render_parts[f][0] for f in rfaces)
                    or any(collision_parts[f][0] for f in cfaces)):
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


def _match_collision_edge_slivers(render_mesh, collision_mesh, collision, partitions, tolerance):
    """Discard compiler slivers along an already connected render edge chain.

    H1 collision can contain an almost collinear triangle where render uses
    two edges through its middle vertex. Its unstable normal prevents a planar
    match, and keeping it adds a spurious shortcut across that vertex. Require
    exact shared positions and oppositely wound render faces on each short
    edge; proximity alone must not remove an authored thin collision surface.
    """
    edges = defaultdict(list)
    for face in render_mesh.polygons:
        points = [tuple(render_mesh.vertices[v].co) for v in face.vertices]
        material = render_mesh.materials[face.material_index] if render_mesh.materials else None
        for a, b in zip(points, points[1:] + points[:1]):
            edges[a, b].append(_material_key(material))

    for triangle in collision:
        face = collision_mesh.polygons[triangle.polygon]
        if len(face.vertices) != 3:
            continue
        points = triangle.coords
        longest = max(range(3), key=lambda i: np.linalg.norm(points[(i + 1) % 3] - points[i]))
        a, b, c = (points[(longest + i) % 3] for i in range(3))
        delta = b - a
        length_squared = float(delta @ delta)
        if not length_squared:
            continue
        fraction = float((c - a) @ delta) / length_squared
        if not 0 < fraction < 1 or np.linalg.norm(c - (a + fraction * delta)) > tolerance:
            continue
        a, b, c = tuple(a), tuple(b), tuple(c)
        if (a, b) in edges or (b, a) in edges:
            continue
        material = triangle.material
        for start, end in ((a, c), (c, b)):
            forward, reverse = edges.get((start, end), ()), edges.get((end, start), ())
            # Two-sided glass and coplanar detail can add more than one face
            # in a direction. They do not invalidate an already supported
            # edge chain, provided both directions and this shader exist.
            if not forward or not reverse or material not in (*forward, *reverse):
                break
        else:
            partitions[triangle.polygon] = ([], [points.tolist()])


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
                        # Clipping uses doubles, but Blender stores float32
                        # coordinates. Reject triangles which collapse at
                        # that precision before creating faces/UV loops.
                        coords = np.asarray([points[0], points[i], points[i + 1]],
                                            dtype=np.float32).astype(np.float64)
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
    _match_collision_edge_slivers(render_mesh, collision_mesh, collision,
                                 mesh_partitions[1], tolerance)
    _replace_faces(render_mesh, mesh_partitions[0], True)
    _replace_faces(collision_mesh, mesh_partitions[1], False)


def dissolve_collision_edge_slivers(render_mesh, collision_mesh, tolerance):
    """Replace a compiler sliver's shortcut with the existing render edge chain.

    Unlike the H1 duplicate-sliver case, one side of the chain can be a retained
    collision polygon. Dissolve only their shared long edge, retaining the
    middle vertex, positions and face properties. Never delete an isolated thin
    triangle merely because its area is small.
    """
    render_edges = set()
    for face in render_mesh.polygons:
        points = [tuple(render_mesh.vertices[v].co) for v in face.vertices]
        render_edges.update(zip(points, points[1:] + points[:1]))
    attributes = [a for a in collision_mesh.attributes if a.domain == 'FACE'
                  and not a.name.startswith('.') and a.data_type in {'BOOLEAN', 'INT', 'FLOAT'}]
    bm = bmesh.new()
    dissolved = 0
    try:
        bm.from_mesh(collision_mesh)
        identities = {f: (f.material_index, tuple(a.data[f.index].value for a in attributes))
                      for f in bm.faces}
        for face in list(bm.faces):
            if not face.is_valid or len(face.verts) != 3:
                continue
            coords = np.array([tuple(v.co) for v in face.verts], dtype=np.float64)
            longest = max(range(3), key=lambda i: np.linalg.norm(coords[(i + 1) % 3] - coords[i]))
            a, b, c = (coords[(longest + i) % 3] for i in range(3))
            delta = b - a
            length_squared = float(delta @ delta)
            if not length_squared:
                continue
            fraction = float((c - a) @ delta) / length_squared
            if not 0 < fraction < 1 or np.linalg.norm(c - (a + fraction * delta)) > tolerance:
                continue
            a, b, c = tuple(a), tuple(b), tuple(c)
            if ((a, b) in render_edges or (b, a) in render_edges
                    or (a, c) not in render_edges or (c, b) not in render_edges):
                continue
            edge = face.loops[longest].edge
            if len(edge.link_faces) != 2 or not edge.is_contiguous:
                continue
            other = next(f for f in edge.link_faces if f != face)
            if other not in identities or identities[face] != identities[other]:
                continue
            # A merged polygon must not revisit the sliver's middle vertex.
            middle = face.verts[(longest + 2) % 3]
            if middle in other.verts:
                continue
            bmesh.ops.dissolve_edges(bm, edges=[edge], use_verts=False, use_face_split=False)
            dissolved += 1
        if dissolved:
            bm.to_mesh(collision_mesh)
    finally:
        bm.free()
    if dissolved:
        collision_mesh.update()
        utils.calc_face_prop_counts(collision_mesh)
    return dissolved


def align_collision_boundary(render_mesh, collision_mesh, tolerance, *, other_render_meshes=()):
    """Align unambiguous collision boundary matches without moving render detail.

    Separate tag streams can round the same position differently. Match unique
    positions one-to-one, rejecting nearby thin layers and many-to-one matches.
    Interior collision vertices and unmatched boundaries remain untouched.
    """
    positions = sorted({tuple(v.co) for mesh in (render_mesh, *other_render_meshes)
                        for v in mesh.vertices})
    if not positions:
        return 0
    tree = kdtree.KDTree(len(positions))
    for i, co in enumerate(positions):
        tree.insert(co, i)
    tree.balance()
    bm = bmesh.new()
    try:
        bm.from_mesh(collision_mesh)
        boundary = {v.index for e in bm.edges if e.is_boundary for v in e.verts}
    finally:
        bm.free()
    candidates = {}
    owners = defaultdict(set)
    for vertex in collision_mesh.vertices:
        matches = tree.find_range(vertex.co, tolerance)
        if len(matches) != 1:
            continue
        target = positions[matches[0][1]]
        owners[target].add(tuple(vertex.co))
        if vertex.index in boundary:
            candidates[vertex.index] = target
    moved = 0
    for index, target in candidates.items():
        if len(owners[target]) == 1 and tuple(collision_mesh.vertices[index].co) != target:
            collision_mesh.vertices[index].co = target
            moved += 1
    if moved:
        collision_mesh.update()
    return moved


def weld_classic_vertices(mesh):
    """Reconnect exact shared vertices after surface reconstruction.

    Tag meshes split vertices for UVs/normals, and clipping creates new vertices
    per face. Blender stores those seams per corner, so they need not disconnect
    editable geometry. Do not use a distance weld: thin BSP features must retain
    their positions. Stacked faces are left for the explicit sidedness pass.
    """
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        by_position = defaultdict(list)
        by_face = defaultdict(list)
        protected = set()
        for vertex in bm.verts:
            by_position[tuple(vertex.co)].append(vertex)
        for face in bm.faces:
            coords = frozenset(tuple(v.co) for v in face.verts)
            by_face[coords].append(face)
            if len(coords) != len(face.verts):
                protected.update(face.verts)
        for faces in by_face.values():
            if len(faces) > 1:
                protected.update(v for f in faces for v in f.verts)
        targets = {}
        for vertices in by_position.values():
            if len(vertices) > 1 and not any(v in protected for v in vertices):
                targets.update((v, vertices[0]) for v in vertices[1:])
        if not targets:
            return 0
        preserve_normals = mesh.has_custom_normals
        if preserve_normals and bm.faces:
            utils.save_loop_normals(bm, mesh)
        before = len(bm.faces)
        bmesh.ops.weld_verts(bm, targetmap=targets)
        if len(bm.faces) != before:
            raise ValueError('Exact BSP vertex welding unexpectedly changed the face count')
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if preserve_normals:
        utils.apply_loop_normals(mesh)
    mesh.update()
    return len(targets)

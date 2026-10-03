"""Conservative reconstruction of H1 cutting planes from compiled portals.

Coordinates and margins are in tag world units. This is an approximation:
only convex, connected unions are rebuilt, and nearby portal intersections
cause the original fragments to be retained.
"""
from dataclasses import replace
import bmesh
import numpy as np
from mathutils import Vector, kdtree


def _triangle_plane_error(points, triangles):
    """Measure the plane drift Tool can see in float32 tag coordinates."""
    points = np.asarray(points, dtype=np.float32)
    corners = points[np.asarray(triangles)]
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    if np.any(lengths <= 1e-12):
        return float('inf')
    normals /= lengths[:, None]
    distances = np.einsum('ij,ij->i', corners[:, 0], normals)
    return float(np.max(np.abs(points @ normals.T - distances)))


def stabilize_halo1_portal(record, tolerance=0.0005):
    """Probe a compiled H1 outline for a stable plane and triangulation.

    Bound plane correction to 0.05 JMS units (about 1.5 mm at Blender scale).
    Keep each cutting plane independent, including adjoining creased portals.
    Try an interior fan only if its float32 planes are more stable than ear
    clipping. The batch repair retains its perimeter as an editable ngon.
    """
    vertices = record.vertices
    count = len(vertices)
    if count < 4 or (record.polygons and record.polygons != (tuple(range(count)),)):
        return record
    points = np.asarray(vertices, dtype=np.float64)
    if not np.all(np.isfinite(points)):
        return record
    center = points.mean(axis=0)
    relative = points - center
    _, singular, axes = np.linalg.svd(relative, full_matrices=False)
    if singular[1] <= 1e-10:
        return record
    normal = axes[-1]
    distances = relative @ normal
    error = float(np.max(np.abs(distances)))
    if error > tolerance:
        return record
    projected = points - np.outer(distances, normal)
    edges = np.roll(projected, -1, axis=0) - projected
    oriented = np.cross(projected-center, np.roll(projected, -1, axis=0)-center).sum(axis=0)
    length = np.linalg.norm(oriented)
    if length <= 1e-12:
        return record
    oriented /= length
    # Retain repeated points and outlines with a centre outside an edge.
    # The fan must cover the same opening without crossing its boundary.
    if (np.any(np.linalg.norm(edges, axis=1) <= 0.001) or
            np.any(np.cross(edges, center-projected) @ oriented <= 1e-12)):
        return record
    prepared = replace(record, vertices=tuple(map(tuple, projected))) if error > 1e-10 else record
    bm = bmesh.new()
    try:
        verts = [bm.verts.new(point) for point in points]
        bm.faces.new(verts)
        bm.verts.index_update()
        bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method='FIXED', ngon_method='EAR_CLIP')
        ears = [tuple(v.index for v in face.verts) for face in bm.faces]
    finally:
        bm.free()
    center_index = count
    fan = [(i, (i+1) % count, center_index) for i in range(count)]
    fan_points = np.vstack((projected, center))
    corners = fan_points[np.asarray(fan)]
    fan_edges = np.roll(corners, -1, axis=1) - corners
    altitudes = (np.linalg.norm(np.cross(fan_edges[:, 0], fan_edges[:, 1]), axis=1) /
                 np.linalg.norm(fan_edges, axis=2).max(axis=1))
    # Tiny boundary subdivisions can collapse during Tool's point welding.
    # Retain the original triangulation rather than introducing such a fan.
    if np.min(altitudes) <= 0.005:
        return prepared
    before = _triangle_plane_error(points, ears)
    after = _triangle_plane_error(fan_points, fan)
    if before <= 1e-5 or after > before * 0.8:
        return prepared
    return replace(prepared, vertices=tuple(map(tuple, fan_points)), polygons=tuple(fan))


def stabilize_halo1_portals(records, is_solid=None, source_records=None):
    """Repair compiled cutting planes without requiring Tool's WRL diagnostics.

    Fans can themselves introduce clipping failures in ordinary fragments.
    Use them for appreciable compiler warpage, adjoining creased planes, or
    openings whose complete expanded boundary is enclosed by solid geometry.
    The latter get at most 0.01 tag units of wall overlap, preventing float32
    conversion from leaving their edges just inside the opening.
    """
    records = list(records)
    sources = list(records if source_records is None else source_records)
    outlines = [np.asarray(record.vertices, dtype=np.float64) for record in sources]
    normals = []
    for points in outlines:
        if len(points) < 3 or not np.all(np.isfinite(points)):
            normals.append(None)
            continue
        _, singular, axes = np.linalg.svd(points-points.mean(axis=0), full_matrices=False)
        normals.append(axes[-1] if singular[1] > 1e-10 else None)
    creased = set()
    for first, (points, normal) in enumerate(zip(outlines, normals)):
        if normal is None:
            continue
        for second in range(first+1, len(sources)):
            other_normal = normals[second]
            # Between reconstruction's coplanar tolerance and about one degree.
            if other_normal is None or not .99985 < abs(normal @ other_normal) < .99999:
                continue
            other = outlines[second]
            shared = sum(np.linalg.norm(other-point, axis=1).min() <= .00025 for point in points)
            if shared >= 2:
                creased.update((sources[first].index, sources[second].index))

    result = []
    for record in records:
        prepared = stabilize_halo1_portal(record)
        if not prepared.polygons or record.polygons:
            result.append(prepared)
            continue
        points = np.asarray(prepared.vertices[:-1], dtype=np.float64)
        center = points.mean(axis=0)
        radius = float(np.linalg.norm(points-center, axis=1).max())
        factor = 1 + min(.01, radius*.001)/radius
        expanded = center + (points-center)*factor
        _, _, axes = np.linalg.svd(points-center, full_matrices=False)
        normal = axes[-1]
        enclosed = is_solid is not None
        if enclosed:
            for a, b in zip(expanded, np.roll(expanded, -1, axis=0)):
                for fraction in (0, .01, .1, .25, .5, .75, .9, .99):
                    point = a + (b-a)*fraction
                    if not all(is_solid(Vector(point+normal*offset))
                               for offset in (-.00025, 0, .00025)):
                        enclosed = False
                        break
                if not enclosed:
                    break
        if enclosed:
            result.append(portal_outline(replace(
                prepared, vertices=tuple(map(tuple, np.vstack((expanded, center)))))))
            continue
        original = np.asarray(record.vertices, dtype=np.float64)
        center = original.mean(axis=0)
        _, _, axes = np.linalg.svd(original-center, full_matrices=False)
        warpage = float(np.abs((original-center) @ axes[-1]).max())
        result.append(portal_outline(prepared) if warpage > .0001 or record.index in creased else record)
    # The fan is a stability probe, not the editable surface. Its projected
    # outline and certified overlap also stabilize ordinary ngon export, which
    # lets Tool recover a single cutting surface instead of fan fragments.
    return result


def portal_outline(record):
    """Dissolve a generated centre fan, retaining its repaired perimeter."""
    count = len(record.vertices)-1
    fan = tuple((i, (i+1) % count, count) for i in range(count)) if count >= 3 else ()
    if fan and record.polygons == fan:
        return replace(record, vertices=record.vertices[:-1], polygons=())
    return record


def group_halo1_portals(records, source_records, tolerance=0.00025):
    """Join adjoining pieces of the same opening without flattening creases.

    Use the compiled boundaries for adjacency: a certified wall overlap may
    move repaired corners apart. Keep flags, cluster pairs and winding intact;
    a point contact or a different opening must remain a separate object.
    """
    sources = {record.index: record for record in source_records}
    outlines = [[Vector(p) for p in sources[record.index].vertices] for record in records]
    normals = [_normal(points) if all(np.all(np.isfinite(p)) for p in points) else Vector()
               for points in outlines]
    keys = [(record.one_way, record.no_way, record.ai_deafening,
             record.blocks_sounds, record.is_door,
             record.front_cluster, record.back_cluster) for record in records]
    pending = set(range(len(records)))
    groups = []
    while pending:
        first = min(pending)
        pending.remove(first)
        group, todo = [first], [first]
        while todo:
            current = todo.pop()
            if min(records[current].front_cluster, records[current].back_cluster) < 0:
                continue
            for other in sorted(pending):
                if keys[current] != keys[other] or normals[current].dot(normals[other]) < .99985:
                    continue
                shared = [a for a in outlines[current]
                          if any((a-b).length <= tolerance for b in outlines[other])]
                if not any((a-b).length > tolerance for a in shared for b in shared):
                    continue
                pending.remove(other)
                group.append(other)
                todo.append(other)
        groups.append(tuple(records[i] for i in sorted(group)))
    return groups


def _portal_junctions(group, source_records, tolerance):
    """Find boundary contacts with cutting surfaces outside this object."""
    sources = {record.index: record for record in source_records}
    owners = {record.index for record in group}
    other_points = np.asarray([point for record in source_records if record.index not in owners
                               for point in record.vertices], dtype=np.float64).reshape((-1, 3))
    junctions = []
    for record in group:
        for point in sources[record.index].vertices:
            p = np.asarray(point)
            if (len(other_points) and np.any(np.linalg.norm(other_points-p, axis=1) <= tolerance)
                    and not any(np.linalg.norm(p-other) <= tolerance for other in junctions)):
                junctions.append(point)
    return np.asarray(junctions, dtype=np.float64).reshape((-1, 3))


def _portal_join_plane(points, junctions, tolerance):
    """Fit the opening while keeping neighbouring portal junctions in plane."""
    origin = points.mean(axis=0)
    _, singular, axes = np.linalg.svd(points-origin, full_matrices=False)
    if singular[1] <= 1e-10:
        return None
    normal = axes[-1]
    if len(junctions):
        origin = junctions.mean(axis=0)
        _, singular, axes = np.linalg.svd(junctions-origin, full_matrices=True)
        if len(singular) > 1 and singular[1] > tolerance:
            normal = axes[-1]
        elif len(junctions) > 1:
            # Collinear contacts fix a hinge line, leaving one rotation free.
            basis = axes[1:]
            _, _, directions = np.linalg.svd((points-origin) @ basis.T, full_matrices=False)
            normal = directions[-1] @ basis
        else:
            _, _, directions = np.linalg.svd(points-origin, full_matrices=False)
            normal = directions[-1]
        if np.abs((junctions-origin) @ normal).max() > tolerance:
            return None
    return origin, normal


def _weld_portal_contacts(bm, group, source_records, scale):
    """Weld compiled contacts, without merging nearby corners of small holes."""
    sources = {record.index: record for record in source_records}
    offsets, points, count = [], [], 0
    for record in group:
        offsets.append(count)
        points.append(np.asarray(record.vertices, dtype=np.float64))
        count += len(record.vertices)
    bm.verts.ensure_lookup_table()
    if count != len(bm.verts):
        return
    parents = list(range(count))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for first, record in enumerate(group):
        for second in range(first+1, len(group)):
            other = np.asarray(sources[group[second].index].vertices, dtype=np.float64)
            for point in sources[record.index].vertices:
                distances = np.linalg.norm(other-point, axis=1)
                match = int(distances.argmin())
                if distances[match] > .00025:
                    continue
                a_distances = np.linalg.norm(points[first]-point, axis=1)
                b_distances = np.linalg.norm(points[second]-other[match], axis=1)
                a, b = int(a_distances.argmin()), int(b_distances.argmin())
                if max(a_distances[a], b_distances[b]) > .03:
                    continue
                a, b = a+offsets[first], b+offsets[second]
                if (bm.verts[a].co-bm.verts[b].co).length > .03*scale:
                    continue
                a, b = root(a), root(b)
                parents[max(a, b)] = min(a, b)
    bmesh.ops.weld_verts(bm, targetmap={bm.verts[i]: bm.verts[root(i)]
                                     for i in range(count) if root(i) != i})


def dissolve_halo1_portal_seams(mesh, group, source_records, is_solid, scale):
    """Remove redundant fragment boundaries from an imported portal object.

    Coordinates are evaluated in tag units. Weld only contacts between faces,
    within 0.03 units of the already repaired outlines. A single surface must
    preserve other portal junctions and existing solid-wall coverage. Bound its
    plane change to 0.1 units and 0.1% of the opening's size. Unsupported joins
    retain their cutting faces; welding still removes duplicate boundaries.
    """
    if len(group) < 2 or len(mesh.polygons) < 2:
        return False
    bm = bmesh.new()
    saved = None
    try:
        bm.from_mesh(mesh)
        _weld_portal_contacts(bm, group, source_records, scale)
        bm.normal_update()
        saved = bm.copy()
        # Dissolve only internal edges. Simplifying the perimeter first would
        # erase bends before the displacement and wall-coverage checks.
        bmesh.ops.dissolve_edges(bm, edges=[edge for edge in bm.edges if len(edge.link_faces) == 2],
                                use_verts=False, use_face_split=False)
        bmesh.ops.delete(bm, geom=[vertex for vertex in bm.verts if not vertex.link_faces],
                         context='VERTS')
        if len(bm.faces) != 1:
            saved.to_mesh(mesh)
            return False
        face = next(iter(bm.faces))
        if len(set(face.verts)) != len(face.verts) or set(face.verts) != set(bm.verts):
            saved.to_mesh(mesh)  # A hole or disconnected piece needs separate faces.
            return False
        points = np.asarray([vertex.co for vertex in bm.verts], dtype=np.float64) / scale
        if not np.all(np.isfinite(points)):
            saved.to_mesh(mesh)
            return False
        junctions = _portal_junctions(group, source_records, .00025)
        plane = _portal_join_plane(points, junctions, .0005)
        if plane is None:
            saved.to_mesh(mesh)
            return False
        origin, normal = plane
        distances = (points-origin) @ normal
        limit = min(.1, float(np.linalg.norm(np.ptp(points, axis=0)))*.001)
        if np.abs(distances).max() > limit:
            saved.to_mesh(mesh)
            return False
        projected = points-np.outer(distances, normal)
        lookup = {vertex: index for index, vertex in enumerate(bm.verts)}
        if is_solid is None and np.abs(distances).max() > .0005:
            saved.to_mesh(mesh)
            return False
        if is_solid is not None:
            for loop in face.loops:
                a, b = lookup[loop.vert], lookup[loop.link_loop_next.vert]
                for fraction in (0, .01, .1, .25, .5, .75, .9, .99):
                    before = points[a]+(points[b]-points[a])*fraction
                    after = projected[a]+(projected[b]-projected[a])*fraction
                    offsets = (-.00025, 0, .00025)
                    if (all(is_solid(Vector(before+normal*d)) for d in offsets)
                            and not all(is_solid(Vector(after+normal*d)) for d in offsets)):
                        saved.to_mesh(mesh)
                        return False
        boundary = tuple(tuple(projected[lookup[vertex]]) for vertex in face.verts)
        boundary = _simplify_outline(boundary, set(), .00025)
        bm.clear()
        bm.faces.new([bm.verts.new(tuple(value*scale for value in point)) for point in boundary])
        bm.to_mesh(mesh)
        return True
    finally:
        if saved is not None:
            saved.free()
        bm.free()


def _simplify_outline(vertices, protected, tolerance):
    """Remove straight-edge subdivisions with a bounded change to the outline."""
    remaining = list(range(len(vertices)))
    changed = True
    while changed and len(remaining) > 3:
        changed = False
        for slot, index in enumerate(remaining):
            previous, following = remaining[slot - 1], remaining[(slot + 1) % len(remaining)]
            a, p, b = vertices[previous], vertices[index], vertices[following]
            if p == a or p == b:
                remaining.pop(slot)
                changed = True
                break
            if index in protected:
                continue
            # Use Python floats for this test: compiled portals can be far
            # from the origin, where float32 arithmetic hides small bends.
            incoming = tuple(p[i] - a[i] for i in range(3))
            outgoing = tuple(b[i] - p[i] for i in range(3))
            dot = sum(x*y for x, y in zip(incoming, outgoing))
            incoming_squared = sum(x*x for x in incoming)
            outgoing_squared = sum(x*x for x in outgoing)
            lengths = incoming_squared * outgoing_squared
            # Clipping can leave a tiny bevel beside a real corner. Its angle
            # is not collinear, but retaining it produces degenerate triangles
            # in Tool. Allow its removal only beside a much longer edge, and
            # still bound the displacement of every source point below.
            tiny_bevel = (min(incoming_squared, outgoing_squared) <= (4*tolerance)**2
                          and max(incoming_squared, outgoing_squared) > (100*tolerance)**2)
            if not tiny_bevel and (dot <= 0 or dot*dot < lengths * (1 - 1e-4)):
                continue  # Preserve real corners and edges which double back.
            delta = tuple(b[i] - a[i] for i in range(3))
            length_squared = sum(x*x for x in delta)
            # Check every original point on this span, including points
            # removed on earlier passes, to prevent accumulated drift.
            span = (following - previous) % len(vertices)
            for step in range(1, span):
                q = vertices[(previous + step) % len(vertices)]
                offset = tuple(q[i] - a[i] for i in range(3))
                fraction = sum(x*y for x, y in zip(offset, delta)) / length_squared
                distance_squared = sum((offset[i] - fraction*delta[i])**2 for i in range(3))
                if not 0 <= fraction <= 1 or distance_squared > tolerance*tolerance:
                    break
            else:
                remaining.pop(slot)
                changed = True
                break
    return tuple(vertices[i] for i in remaining)


def simplify_portals(records, tolerance=0.00025):
    """Dissolve redundant edge vertices, retaining junctions with other portals."""
    points = [(owner, index, point) for owner, record in enumerate(records)
              for index, point in enumerate(record.vertices)]
    if not points:
        return records
    tree = kdtree.KDTree(len(points))
    for index, (_, _, point) in enumerate(points):
        tree.insert(point, index)
    tree.balance()
    protected = [set() for _ in records]
    for owner, index, point in points:
        if any(points[other][0] != owner for _, other, _ in tree.find_range(point, tolerance)):
            protected[owner].add(index)
    result = []
    for record, junctions in zip(records, protected):
        vertices = _simplify_outline(record.vertices, junctions, tolerance)
        result.append(record if vertices == record.vertices else replace(record, vertices=vertices))
    return result


def _normal(points):
    normal = Vector((0, 0, 0))
    if not points:
        return normal
    origin = points[0]
    for a, b in zip(points, points[1:] + points[:1]):
        normal += (a-origin).cross(b-origin)
    return normal.normalized()


def _hull(points):
    points = sorted(set(points))
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    def half(sequence):
        result = []
        for p in sequence:
            while len(result) > 1 and cross(result[-2], result[-1], p) <= 1e-10:
                result.pop()
            result.append(p)
        return result[:-1]
    return half(points) + half(reversed(points))


def _area(points):
    return abs(sum(a[0]*b[1]-a[1]*b[0]
                   for a,b in zip(points, points[1:]+points[:1]))) / 2


def _near_portal(a, b, tolerance):
    # Conservative bounding-box/plane test: false positives retain the source.
    if any(max(p[j] for p in a) < min(p[j] for p in b)-tolerance or
           max(p[j] for p in b) < min(p[j] for p in a)-tolerance for j in range(3)):
        return False
    for plane, points in ((a, b), (b, a)):
        normal = _normal(plane)
        distances = [normal.dot(p-plane[0]) for p in points]
        if min(distances) > tolerance or max(distances) < -tolerance:
            return False
    return True


def _extend_solid_edges(record, is_solid, tolerance, margin):
    """Offset cliff-facing edges while keeping boundaries in open space fixed."""
    points = [Vector(p) for p in record.vertices]
    if len(points) < 3:
        return record
    normal = _normal(points)
    if normal.length < .5:
        return record
    origin = points[0]
    if any(abs(normal.dot(p-origin)) > tolerance for p in points):
        return record
    u = normal.orthogonal().normalized()
    v = normal.cross(u)
    projected = [((p-origin).dot(u), (p-origin).dot(v)) for p in points]
    hull = _hull(projected)
    area = _area(hull)
    if len(hull) < 3 or abs(area-_area(projected)) > max(area*1e-5, tolerance*tolerance):
        return record
    def world(p):
        return origin + u*p[0] + v*p[1]
    def solid(p):
        # Avoid accepting a point solely because it lies exactly on a BSP plane.
        return all(is_solid(p + normal*d) for d in (-tolerance, 0, tolerance))
    constraints = []
    moved = False
    for a, b in zip(hull, hull[1:] + hull[:1]):
        edge = Vector(b)-Vector(a)
        outward = Vector((edge.y, -edge.x)).normalized()
        # Test along the entire edge, including near both corners. Extension
        # into another portal's open space is not evidence of a wall.
        offset = margin
        for fraction in (0.01, .1, .25, .5, .75, .9, .99):
            p = Vector(a) + edge*fraction
            if not all(solid(world(p+outward*d)) for d in (margin*.25, margin*.5, margin)):
                offset = 0
                break
        moved |= bool(offset)
        constraints.append((outward, outward.dot(Vector(a)) + offset))
    if not moved:
        return record
    # Intersect the shifted half-planes; this also handles collinear compiler
    # vertices without unstable miter calculations at tiny edges.
    low = [min(p[i] for p in hull)-margin*4 for i in range(2)]
    high = [max(p[i] for p in hull)+margin*4 for i in range(2)]
    expanded = [(low[0],low[1]),(high[0],low[1]),(high[0],high[1]),(low[0],high[1])]
    for n, limit in constraints:
        clipped = []
        for a, b in zip(expanded, expanded[1:]+expanded[:1]):
            da, db = n.dot(Vector(a))-limit, n.dot(Vector(b))-limit
            if da <= 0:
                clipped.append(a)
            if (da < 0 < db) or (db < 0 < da):
                q = Vector(a)+(Vector(b)-Vector(a))*(da/(da-db))
                clipped.append(tuple(q))
        expanded = clipped
        if len(expanded) < 3:
            return record
    # Reject miter corners that extend into open space, not just the edge
    # midpoint. Points still on the original boundary need no solid test.
    original_constraints = []
    for a, b in zip(hull, hull[1:]+hull[:1]):
        e = Vector(b)-Vector(a)
        n = Vector((e.y,-e.x)).normalized()
        original_constraints.append((n,n.dot(Vector(a))))
    for a, b in zip(expanded, expanded[1:]+expanded[:1]):
        for fraction in (0, .25, .5, .75):
            p = Vector(a)+(Vector(b)-Vector(a))*fraction
            if any(n.dot(p)-d > tolerance for n,d in original_constraints) and not solid(world(p)):
                return record
    return replace(record, vertices=tuple(tuple(world(p)) for p in expanded))


def reconstruct_portals(records, tolerance=0.00025, margin=0.01, is_solid=None):
    """Return records and the number of source fragments successfully rebuilt."""
    points = [[Vector(v) for v in r.vertices] for r in records]
    normals = [_normal(p) if len(p) >= 3 else Vector() for p in points]
    flags = [(r.one_way, r.no_way, r.ai_deafening, r.blocks_sounds, r.is_door,
              r.front_cluster, r.back_cluster)
             for r in records]
    pending = set(range(len(records)))
    candidates = []
    while pending:
        first = min(pending)
        pending.remove(first)
        group = {first}
        normal = normals[first]
        if normal.length < .5:
            candidates.append((group, None))
            continue
        todo = [first]
        while todo:
            current = todo.pop()
            for other in sorted(pending):
                if flags[first] != flags[other] or normal.dot(normals[other]) < .99999:
                    continue
                if any(abs(normal.dot(p-points[first][0])) > tolerance for p in points[other]):
                    continue
                # Two shared vertices identify adjoining fragments, not a
                # point contact between otherwise unrelated portal openings.
                shared = sum(any((a-b).length <= tolerance for b in points[current])
                             for a in points[other])
                if shared >= 2:
                    pending.remove(other)
                    group.add(other)
                    todo.append(other)
        origin = points[first][0]
        u = normal.orthogonal().normalized()
        v = normal.cross(u)
        projected = [[((p-origin).dot(u), (p-origin).dot(v)) for p in points[i]]
                     for i in sorted(group)]
        hull = _hull([p for poly in projected for p in poly])
        area = _area(hull)
        source_area = sum(_area(poly) for poly in projected)
        if len(hull) < 3 or area < tolerance*tolerance or abs(area-source_area) > max(area*1e-5, tolerance*tolerance):
            candidates.append((group, None))
            continue
        center = sum((Vector(p) for p in hull), Vector((0, 0))) / len(hull)
        # A small bounded extension avoids recreating a level-wide plane.
        radius = min((Vector(p)-center).length for p in hull)
        factor = 1 + min(margin, radius*.01) / max(radius, tolerance)
        expanded = [origin + u*q.x + v*q.y
                    for p in hull for q in [center+(Vector(p)-center)*factor]]
        candidates.append((group, expanded))
    rejected = set()
    for a, (group, expanded) in enumerate(candidates):
        if expanded is None:
            continue
        for b, (other_group, other_expanded) in enumerate(candidates):
            if a == b:
                continue
            others = [other_expanded] if other_expanded is not None else [points[i] for i in other_group]
            if any(len(p) >= 3 and _near_portal(expanded, p, tolerance) for p in others):
                rejected.add(a)
                rejected.add(b)
    result, rebuilt = [], 0
    for i, (group, expanded) in enumerate(candidates):
        if expanded is None or i in rejected:
            result.extend(records[j] for j in sorted(group))
        else:
            result.append(replace(records[min(group)], vertices=tuple(tuple(p) for p in expanded)))
            rebuilt += len(group)
    if is_solid is not None:
        originals = {r.index: r for r in records}
        for i, record in enumerate(result):
            if record.vertices == originals[record.index].vertices:
                extended = _extend_solid_edges(record, is_solid, tolerance, margin)
                if extended is not record:
                    result[i] = extended
                    rebuilt += 1
    # Clipping and retained compiler fragments can both leave unnecessary
    # points along straight edges. Clean these only after reconstruction so
    # they still participate in the original fragment adjacency tests.
    return simplify_portals(sorted(result, key=lambda r: r.index), tolerance), rebuilt

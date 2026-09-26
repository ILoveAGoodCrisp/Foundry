"""Conservative reconstruction of H1 cutting planes from compiled portals.

Coordinates and margins are in tag world units. This is an approximation:
only convex, connected unions are rebuilt, and nearby portal intersections
cause the original fragments to be retained.
"""
from dataclasses import replace
from mathutils import Vector, kdtree


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
    flags = [(r.one_way, r.no_way, r.ai_deafening, r.blocks_sounds, r.is_door)
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

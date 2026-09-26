"""Find opposite planar collision patches independently of triangulation."""
from collections import defaultdict, Counter


def opposite_patches(polygons):
    """Return face sets to keep/remove; records are (points, normal, properties)."""
    groups = defaultdict(list)
    for index, (points, normal, properties) in enumerate(polygons):
        if not points or sum(n * n for n in normal) < .5:
            continue
        distance = sum(a * b for a, b in zip(points[0], normal))
        if any(abs(sum(a * b for a, b in zip(p, normal)) - distance) > 1e-5
               for p in points):
            continue
        key = (tuple(round(n, 5) for n in normal), round(distance, 5), properties)
        groups[key].append(index)
    patches = defaultdict(list)
    for (normal, distance, properties), faces in groups.items():
        edges = defaultdict(list)
        face_edges = {}
        for face in faces:
            points = polygons[face][0]
            boundary = [tuple(sorted((a, b))) for a, b in
                        zip(points, points[1:] + points[:1])]
            face_edges[face] = boundary
            for edge in boundary:
                edges[edge].append(face)
        pending = set(faces)
        while pending:
            first = pending.pop()
            component, todo = {first}, [first]
            while todo:
                for edge in face_edges[todo.pop()]:
                    for neighbour in edges[edge]:
                        if neighbour in pending:
                            pending.remove(neighbour)
                            component.add(neighbour)
                            todo.append(neighbour)
            counts = Counter(e for f in component for e in face_edges[f])
            boundary = frozenset(e for e, count in counts.items() if count == 1)
            degree = Counter(v for edge in boundary for v in edge)
            if not boundary or any(n != 2 for n in degree.values()) or any(n > 2 for n in counts.values()):
                continue
            patches[(boundary, properties)].append((normal, distance, component))
    result = []
    for candidates in patches.values():
        if len(candidates) != 2:
            continue
        (n, d, keep), (other, od, remove) = candidates
        if sum(a * b for a, b in zip(n, other)) < -.99999 and abs(d + od) < 1e-5:
            result.append((keep, remove))
    # Compiler diagonals can make a slightly warped authored polygon have
    # different triangle planes on each side. Match its shared boundary, too.
    matched = {i for pair in result for side in pair for i in side}
    oriented = defaultdict(lambda: [[], []])
    for i, (points, normal, properties) in enumerate(polygons):
        if i in matched or not points or sum(n*n for n in normal) < .5:
            continue
        axis = max(range(3), key=lambda j: abs(normal[j]))
        oriented[(properties, axis)][normal[axis] < 0].append(i)
    for sides in oriented.values():
        edge_maps = []
        for faces in sides:
            edges = defaultdict(list)
            for i in faces:
                points = polygons[i][0]
                for a, b in zip(points, points[1:] + points[:1]):
                    edges[tuple(sorted((a, b)))].append(i)
            edge_maps.append(edges)
        common = edge_maps[0].keys() & edge_maps[1].keys()
        borders = []
        for faces, edges in zip(sides, edge_maps):
            neighbours = defaultdict(set)
            for edge, fs in edges.items():
                if edge not in common and len(fs) == 2:
                    a, b = fs
                    neighbours[a].add(b)
                    neighbours[b].add(a)
            pending = set(faces)
            patches_by_border = defaultdict(list)
            while pending:
                first = pending.pop()
                component, todo = {first}, [first]
                while todo:
                    for i in neighbours[todo.pop()]:
                        if i in pending:
                            pending.remove(i)
                            component.add(i)
                            todo.append(i)
                counts = Counter()
                for i in component:
                    points = polygons[i][0]
                    counts.update(tuple(sorted((a,b))) for a,b in zip(points,points[1:]+points[:1]))
                boundary = frozenset(e for e,c in counts.items() if c == 1)
                degree = Counter(v for e in boundary for v in e)
                if (boundary and boundary <= common and all(c <= 2 for c in counts.values())
                        and all(c == 2 for c in degree.values())):
                    patches_by_border[boundary].append(component)
            borders.append(patches_by_border)
        for boundary, candidates in borders[0].items():
            other = borders[1].get(boundary, [])
            if len(candidates) != 1 or len(other) != 1:
                continue
            keep, remove = candidates[0], other[0]
            # Only boundary vertices: don't flatten distinct interior details.
            boundary_vertices = {v for edge in boundary for v in edge}
            if all(set(polygons[i][0]) <= boundary_vertices for i in keep | remove):
                result.append((keep, remove))
    return result

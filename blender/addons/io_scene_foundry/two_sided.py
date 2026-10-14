"""Recover compiled two-sided patch winding from its one-sided boundary."""

from collections import defaultdict


def two_sided_faces_to_flip(
        faces: dict[int, tuple[tuple[float, float, float], ...]],
        two_sided_faces: set[int]) -> set[int]:
    """Return representatives whose opposing face should be retained instead.

    ``faces`` maps active face indices to ordered position tuples after duplicate
    backsides have been excluded. Coincident split vertices therefore still
    share edges. An orientable patch needs a one-sided boundary to establish its
    front. Ignore non-manifold edges, and preserve the caller's choice for
    unanchored patches or patches with conflicting winding constraints.
    """
    edges = defaultdict(list)
    for index, positions in faces.items():
        for a, b in zip(positions, positions[1:] + positions[:1]):
            if a == b:
                continue
            key = (a, b) if a < b else (b, a)
            edges[key].append((index, a < b))

    neighbors = defaultdict(list)
    anchors = defaultdict(list)
    for entries in edges.values():
        if len(entries) != 2:
            continue
        (a, direction_a), (b, direction_b) = entries
        if a == b:
            continue
        # Adjacent front faces traverse their shared edge in opposite directions.
        different_flips = direction_a == direction_b
        if a in two_sided_faces and b in two_sided_faces:
            neighbors[a].append((b, different_flips))
            neighbors[b].append((a, different_flips))
        elif a in two_sided_faces:
            anchors[a].append(different_flips)
        elif b in two_sided_faces:
            anchors[b].append(different_flips)

    visited = set()
    to_flip = set()
    for start in sorted(two_sided_faces):
        if start in visited:
            continue
        relative_flips = {start: False}
        pending = [start]
        root_flips = set()
        conflict = False
        while pending:
            index = pending.pop()
            visited.add(index)
            flip = relative_flips[index]
            root_flips.update(required ^ flip for required in anchors[index])
            for neighbor, different_flips in neighbors[index]:
                required = flip ^ different_flips
                if neighbor in relative_flips:
                    conflict |= relative_flips[neighbor] != required
                else:
                    relative_flips[neighbor] = required
                    pending.append(neighbor)

        if conflict or len(root_flips) != 1:
            continue
        root_flip = root_flips.pop()
        to_flip.update(index for index, flip in relative_flips.items()
                       if flip ^ root_flip)
    return to_flip

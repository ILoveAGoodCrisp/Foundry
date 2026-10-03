"""Conservative point and convex-volume queries against a collision BSP."""
import numpy as np


def _clip_face(points, distances, front):
    result, crossings = [], []
    for a, b, da, db in zip(points, np.roll(points, -1, axis=0),
                            distances, np.roll(distances, -1)):
        keep = da >= 0 if front else da <= 0
        if keep:
            result.append(a)
        if (da < 0 < db) or (db < 0 < da):
            point = a + (b-a)*(da/(da-db))
            result.append(point)
            crossings.append(point)
    return np.asarray(result), crossings


class CollisionSolidQuery:
    """Unknown leaves, malformed trees and unresolved queries remain unsafe."""
    def __init__(self, planes, nodes, leaf_clusters=(), *, root=0):
        self.planes = np.asarray(planes, dtype=np.float64)
        self.nodes = tuple(nodes)
        self.leaf_clusters = tuple(leaf_clusters)
        self.root = root

    def __call__(self, point):
        if not np.all(np.isfinite(point)):
            return False
        index = self.root
        for _ in range(len(self.nodes) + 1):
            index &= 0xffffffff
            if index == 0xffffffff:
                return True
            if index & 0x80000000 or index >= len(self.nodes):
                return False
            plane, back, front = self.nodes[index]
            if not 0 <= plane < len(self.planes):
                return False
            normal = self.planes[plane, :3]
            if not np.all(np.isfinite(self.planes[plane])) or np.linalg.norm(normal) < 1e-12:
                return False
            index = front if normal @ point >= self.planes[plane, 3] else back
        return False

    def contains_prism(self, polygon, normal, thickness=.00025, *, allowed_clusters=()):
        """Prove the entire extrusion is solid by splitting it at BSP planes.

        Checking a few points can miss another opening inside an extension.
        This visits every intersected leaf of the actual convex volume, on
        both sides of the portal, including its interior. A bounded portal
        plane correction can explicitly admit its original adjacent clusters;
        missing cluster labels and every other empty leaf still fail.
        """
        points = np.asarray(polygon, dtype=np.float64)
        normal = np.asarray(normal, dtype=np.float64)
        if (len(points) < 3 or not np.all(np.isfinite(points))
                or not np.all(np.isfinite(normal)) or np.linalg.norm(normal) < 1e-12
                or not np.isfinite(thickness) or thickness <= 0):
            return False
        lower, upper = points-normal*thickness, points+normal*thickness
        faces = [lower, upper]
        faces.extend(np.asarray((lower[i], lower[(i+1) % len(points)],
                                 upper[(i+1) % len(points)], upper[i]))
                     for i in range(len(points)))
        pending = [(self.root, faces, 0)]
        allowed_clusters = set(allowed_clusters)
        visits = 0
        while pending:
            index, faces, depth = pending.pop()
            index &= 0xffffffff
            if index == 0xffffffff:
                continue
            if index & 0x80000000:
                leaf = index & 0x7fffffff
                if (leaf < len(self.leaf_clusters) and self.leaf_clusters[leaf] >= 0
                        and self.leaf_clusters[leaf] in allowed_clusters):
                    continue
                return False
            if index >= len(self.nodes) or depth > len(self.nodes):
                return False
            visits += 1
            if visits > 100000:
                return False
            plane, back, front = self.nodes[index]
            if not 0 <= plane < len(self.planes):
                return False
            n, distance = self.planes[plane, :3], self.planes[plane, 3]
            if not np.all(np.isfinite(self.planes[plane])) or np.linalg.norm(n) < 1e-12:
                return False
            signed = [face @ n-distance for face in faces]
            low = min(float(d.min()) for d in signed)
            high = max(float(d.max()) for d in signed)
            if low >= 0:
                pending.append((front, faces, depth+1))
                continue
            if high <= 0:
                pending.append((back, faces, depth+1))
                continue
            for child, keep_front in ((back, False), (front, True)):
                clipped, cap = [], []
                for face, distances in zip(faces, signed):
                    part, crossings = _clip_face(face, distances, keep_front)
                    if len(part) >= 3:
                        clipped.append(part)
                    for point in crossings:
                        if not any(np.linalg.norm(point-other) < 1e-10 for other in cap):
                            cap.append(point)
                    # A cut through an existing vertex must also close the
                    # cap; strict edge crossings alone omit those vertices.
                    for point in part:
                        if (abs(point @ n-distance) < 1e-10
                                and not any(np.linalg.norm(point-other) < 1e-10 for other in cap)):
                            cap.append(point)
                if len(cap) >= 3:
                    cap = np.asarray(cap)
                    origin = cap.mean(axis=0)
                    u = cap[0]-origin
                    v = np.cross(n, u)
                    order = np.argsort(np.arctan2((cap-origin) @ v / max(np.linalg.norm(v), 1e-30),
                                                  (cap-origin) @ u / max(np.linalg.norm(u), 1e-30)))
                    clipped.append(cap[order])
                if not clipped:
                    return False
                pending.append((child, clipped, depth+1))
        return True


def collision_query_from_tree(data, *, allow_cluster_regions=False):
    """Expand packed supernode roots without inheriting clusters into solid.

    Reach's visibility recovery may collapse solid branches. Outline expansion
    needs the original solid/empty classification, including H4/H2A supernodes.
    Normalize the reachable graph iteratively, retaining leaf indices and the
    distinction between an ordinary node zero and a supernode child zero.
    Collision and visibility partitions can differ in later games: permit
    labelled empty regions only when the caller knows their correspondence.
    """
    if not data:
        return None
    planes = list(data['planes'])
    source_nodes, supers = data['nodes'], data.get('supernodes', ())
    clusters = data.get('clusters', ()) if allow_cluster_regions else ()
    if not supers:
        return CollisionSolidQuery(planes, source_nodes, clusters)
    nodes, indices, pending = [], {}, []

    def reserve(key):
        if key not in indices:
            if len(nodes) >= 1000000:
                raise ValueError('Portal collision tree is too large')
            indices[key] = len(nodes)
            nodes.append(None)
            pending.append(key)
        return indices[key]

    def child(index, super_mode=False):
        index &= 0xffffffff
        if index & 0x80000000:
            return index
        if super_mode and not index & 0x40000000:
            if index >= len(supers):
                raise ValueError('Portal collision tree has an invalid supernode')
            return reserve(('super', index, 0))
        index &= 0x3fffffff
        if index >= len(source_nodes):
            raise ValueError('Portal collision tree has an invalid node')
        return reserve(('node', index, 0))

    root = child(0, True)
    while pending:
        key = pending.pop()
        kind, index, slot = key
        if kind == 'node':
            plane, back, front = source_nodes[index]
            nodes[indices[key]] = plane, child(back), child(front)
            continue
        values, children, dimensions = supers[index]
        if len(values) != 15 or len(children) != 16:
            raise ValueError('Portal collision tree has an invalid supernode layout')
        axis = (dimensions >> (slot*2)) & 3
        if axis > 2:
            raise ValueError('Portal collision tree has an invalid supernode axis')
        plane = [0., 0., 0., float(values[slot])]
        plane[axis] = 1.
        plane_index = len(planes)
        planes.append(tuple(plane))

        def branch(next_slot):
            if next_slot < 15:
                return reserve(('super', index, next_slot))
            value = children[next_slot-15]
            return 0xffffffff if value == 0 else child(value, True)

        nodes[indices[key]] = plane_index, branch(slot*2+1), branch(slot*2+2)
    return CollisionSolidQuery(planes, nodes, clusters, root=root)

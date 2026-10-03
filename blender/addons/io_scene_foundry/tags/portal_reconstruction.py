"""Conservative reconstruction of cutting planes from compiled tag portals.

Coordinates and margins are in tag world units. Compiled fragments become
connected surfaces, with enclosing outlines recovered where solid-volume and
bounded cluster-region proofs preserve the opening and its portal junctions.
Unsupported outlines retain their cutting faces.
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
        if record.polygons:
            # A recovered single ngon can also be probed with a fan. Keep its
            # editable outline; existing multi-face records retain their loops.
            result.append(portal_outline(prepared) if prepared is not record else prepared)
            continue
        if not prepared.polygons:
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


def stabilize_halo1_portal_tessellation(ob, scale):
    """Keep an editable ngon while evaluating a stable fan for fragile planes.

    Beauty and ear clipping can amplify float32 roundoff in shallow boundary
    bends, even after the joined face is planar. Use a modifier only when both
    triangulations drift and a fan substantially reduces the worst plane error.
    Preserve every perimeter point, winding and material; exclude real warps,
    small triangles and faces whose centre is outside their visibility kernel.
    """
    mesh = ob.data
    if (len(mesh.polygons) != 1 or len(mesh.polygons[0].vertices) <= 4
            or ob.modifiers or not np.isfinite(scale) or scale <= 0):
        return False
    order = tuple(mesh.polygons[0].vertices)
    if set(order) != set(range(len(mesh.vertices))):
        return False
    points = np.asarray([mesh.vertices[i].co for i in order], dtype=np.float64)/scale
    if not np.all(np.isfinite(points)):
        return False
    center = points.mean(axis=0)
    _, singular, axes = np.linalg.svd(points-center, full_matrices=False)
    if singular[1] <= 1e-10 or np.abs((points-center) @ axes[-1]).max() > .0005:
        return False
    winding = np.cross(points-center, np.roll(points, -1, axis=0)-center).sum(axis=0)
    length = np.linalg.norm(winding)
    if length <= 1e-12:
        return False
    normal = winding/length
    if np.any(np.cross(np.roll(points, -1, axis=0)-points, center-points) @ normal <= 1e-12):
        return False
    count = len(points)
    fan = [(i, (i+1) % count, count) for i in range(count)]
    fan_points = np.vstack((points, center))
    corners = fan_points[np.asarray(fan)]
    edges = np.roll(corners, -1, axis=1)-corners
    heights = np.linalg.norm(np.cross(edges[:, 0], edges[:, 1]), axis=1)/np.linalg.norm(edges, axis=2).max(axis=1)
    if heights.min() <= .005:
        return False
    errors = []
    lookup = {index: i for i, index in enumerate(order)}
    for method in ('EAR_CLIP', 'BEAUTY'):
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            bm.verts.index_update()
            bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method='FIXED', ngon_method=method)
            triangles = [tuple(lookup[v.index] for v in face.verts) for face in bm.faces]
            errors.append(_triangle_plane_error(points, triangles))
        finally:
            bm.free()
    after = _triangle_plane_error(fan_points, fan)
    # A shallow perimeter bend can be poorly conditioned in either export
    # triangulation. Require appreciable instability in the worst case and
    # improvement over it; a tiny change in the best case does not predict
    # Tool's clipping, which also rounds the exported coordinates.
    if (min(errors) <= .0001 or max(errors) <= .001
            or after > min(.0005, max(errors)*.2)):
        return False

    import bpy
    group = next((g for g in bpy.data.node_groups
                  if g.bl_idname == 'GeometryNodeTree'
                  and (g.get('foundry_portal_fan') == 1 or g.get('foundry_halo1_portal_fan') == 1)), None)
    if group is None:
        group = bpy.data.node_groups.new('Portal plane triangulation', 'GeometryNodeTree')
        group['foundry_portal_fan'] = 1
        group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        group.interface.new_socket(name='Material', in_out='INPUT', socket_type='NodeSocketMaterial')
        group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        nodes, links = group.nodes, group.links
        input_node, output_node = nodes.new('NodeGroupInput'), nodes.new('NodeGroupOutput')
        size = nodes.new('GeometryNodeAttributeDomainSize')
        position = nodes.new('GeometryNodeInputPosition')
        index = nodes.new('GeometryNodeInputIndex')
        circle = nodes.new('GeometryNodeMeshCircle')
        circle.fill_type = 'TRIANGLE_FAN'
        sample = nodes.new('GeometryNodeSampleIndex')
        sample.data_type, sample.domain = 'FLOAT_VECTOR', 'CORNER'
        mean = nodes.new('GeometryNodeAttributeStatistic')
        mean.data_type, mean.domain = 'FLOAT_VECTOR', 'POINT'
        compare = nodes.new('FunctionNodeCompare')
        compare.data_type, compare.operation = 'INT', 'EQUAL'
        switch = nodes.new('GeometryNodeSwitch')
        switch.input_type = 'VECTOR'
        set_position = nodes.new('GeometryNodeSetPosition')
        material = nodes.new('GeometryNodeSetMaterial')
        for node in (size, sample, mean):
            links.new(input_node.outputs['Geometry'], node.inputs['Geometry'])
        links.new(size.outputs['Face Corner Count'], circle.inputs['Vertices'])
        links.new(position.outputs['Position'], sample.inputs['Value'])
        links.new(index.outputs['Index'], sample.inputs['Index'])
        links.new(position.outputs['Position'], mean.inputs['Attribute'])
        links.new(index.outputs['Index'], compare.inputs['A'])
        links.new(size.outputs['Face Corner Count'], compare.inputs['B'])
        links.new(compare.outputs['Result'], switch.inputs['Switch'])
        links.new(sample.outputs['Value'], switch.inputs['False'])
        links.new(mean.outputs['Mean'], switch.inputs['True'])
        links.new(circle.outputs['Mesh'], set_position.inputs['Geometry'])
        links.new(switch.outputs['Output'], set_position.inputs['Position'])
        links.new(set_position.outputs['Geometry'], material.inputs['Geometry'])
        links.new(input_node.outputs['Material'], material.inputs['Material'])
        links.new(material.outputs['Geometry'], output_node.inputs['Geometry'])
        for node, location in ((input_node, (-700, 0)), (size, (-470, 250)),
                               (position, (-700, -250)), (index, (-700, -450)),
                               (sample, (-470, -100)), (mean, (-470, -400)),
                               (compare, (-240, 100)), (switch, (0, -100)),
                               (circle, (0, 250)), (set_position, (240, 200)),
                               (material, (470, 200)), (output_node, (700, 200))):
            node.location = location
    modifier = ob.modifiers.new('Portal plane triangulation', 'NODES')
    modifier.node_group = group
    modifier.show_in_editmode = False
    material_socket = next(s for s in group.interface.items_tree
                           if s.item_type == 'SOCKET' and s.in_out == 'INPUT' and s.name == 'Material')
    if mesh.materials:
        face_material = mesh.materials[mesh.polygons[0].material_index]
        if hasattr(modifier, 'properties'):
            getattr(modifier.properties.inputs, material_socket.identifier).value = face_material
        else:
            modifier[material_socket.identifier] = face_material
    return True


def group_halo1_portals(records, source_records, tolerance=0.00025):
    """Join adjoining pieces of the same opening without flattening creases.

    Use the compiled boundaries for adjacency: a certified wall overlap may
    move repaired corners apart. Keep flags, cluster pairs and winding intact;
    a point contact or a different opening must remain a separate object.
    """
    sources = {record.index: record for record in source_records}
    outlines = [[Vector(p) for p in sources[record.index].vertices] for record in records]
    normals = [_normal([points[i] for i in sources[record.index].polygons[0]]
                       if sources[record.index].polygons else points)
               if all(np.all(np.isfinite(p)) for p in points) else Vector()
               for points, record in zip(outlines, records)]
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


def _weld_recovered_portal_faces(bm, scale):
    """Reconnect duplicated corners of faces recovered from a cluster tree.

    Only weld contacts between different faces, never nearby corners belonging
    to the same face. In particular, retain narrow holes and disconnected cuts.
    """
    vertices = list(bm.verts)
    tree = kdtree.KDTree(len(vertices))
    for index, vertex in enumerate(vertices):
        tree.insert(vertex.co, index)
    tree.balance()
    members = [{v} for v in vertices]
    parents = list(range(len(vertices)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for i, vertex in enumerate(vertices):
        for _, j, _ in tree.find_range(vertex.co, 1e-7*scale):
            a, b = root(i), root(j)
            if a == b:
                continue
            a, b = min(a, b), max(a, b)
            faces_a = {face for v in members[a] for face in v.link_faces}
            faces_b = {face for v in members[b] for face in v.link_faces}
            if faces_a & faces_b:
                continue
            parents[b] = a
            members[a].update(members[b])
    bmesh.ops.weld_verts(bm, targetmap={v: vertices[root(i)] for i, v in enumerate(vertices) if root(i) != i})


def dissolve_halo1_portal_seams(mesh, group, source_records, is_solid, scale, *, _wall_recovery=None):
    """Remove redundant fragment boundaries from an imported portal object.

    Coordinates are evaluated in tag units. Weld only contacts between faces,
    within 0.03 units of the already repaired outlines. A single surface must
    preserve other portal junctions and existing solid-wall coverage. Bound its
    plane change to 0.1 units and 0.1% of the opening's size. Unsupported joins
    retain their cutting faces; welding still removes duplicate boundaries.
    The private recovery pass supplies the measured displacement to the
    enclosing-outline proof and works exclusively on a temporary mesh.
    """
    recovered_faces = any(record.polygons and len(record.polygons) > 1 for record in group)
    if (len(group) < 2 and not recovered_faces) or len(mesh.polygons) < 2:
        return False
    bm = bmesh.new()
    saved = None
    try:
        bm.from_mesh(mesh)
        _weld_portal_contacts(bm, group, source_records, scale)
        if recovered_faces:
            _weld_recovered_portal_faces(bm, scale)
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
        if _wall_recovery is not None:
            _wall_recovery['motion'] = float(np.abs(distances).max())
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
                        if _wall_recovery is not None:
                            continue  # The caller must recover and certify the wall sides.
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
        if record.polygons and record.polygons != (tuple(range(len(record.vertices))),):
            result.append(record)  # Indices describe several independent face loops.
            continue
        vertices = _simplify_outline(record.vertices, junctions, tolerance)
        if vertices == record.vertices:
            result.append(record)
        else:
            faces = (tuple(range(len(vertices))),) if record.polygons else ()
            result.append(replace(record, vertices=vertices, polygons=faces))
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


def _clip_2d(polygon, normal, distance, inside=True):
    """Clip a convex polygon in double precision, retaining its winding."""
    if len(polygon) < 3:
        return []
    points = np.asarray(polygon, dtype=np.float64)
    signed = points @ normal-distance
    result = []
    for a, b, da, db in zip(points, np.roll(points, -1, axis=0),
                            signed, np.roll(signed, -1)):
        keep = da <= 0 if inside else da >= 0
        if keep:
            result.append(tuple(a))
        if (da < 0 < db) or (db < 0 < da):
            result.append(tuple(a+(b-a)*(da/(da-db))))
    return result if len(result) >= 3 and _area(result) > 1e-12 else []


def _subtract_convex(polygon, opening):
    """Partition polygon minus a CCW convex opening into convex pieces."""
    remaining, outside = polygon, []
    for a, b in zip(opening, opening[1:]+opening[:1]):
        edge = np.asarray(b)-a
        normal = np.asarray((edge[1], -edge[0]))
        distance = normal @ a
        part = _clip_2d(remaining, normal, distance, inside=False)
        if part:
            outside.append(part)
        remaining = _clip_2d(remaining, normal, distance)
        if not remaining:
            break
    return outside


def _outside_outline_band(pieces, outline, width):
    """Exclude a finite, bounded ribbon around each old perimeter edge."""
    for a, b in zip(outline, np.roll(outline, -1, axis=0)):
        edge = b-a
        length = float(np.linalg.norm(edge))
        if length <= 1e-12:
            continue
        offset = np.asarray((edge[1], -edge[0])) * (width/length)
        ribbon = _hull([tuple(p) for p in (a-offset, b-offset, b+offset, a+offset)])
        pieces = [outside for part in pieces for outside in _subtract_convex(part, ribbon)]
    return pieces


def _portal_extension_intersects(part, other, tolerance=.00025):
    """Detect a new cut through a portal polygon, allowing point contacts."""
    part, other = np.asarray(part, dtype=np.float64), np.asarray(other, dtype=np.float64)
    if len(part) < 3 or len(other) < 3:
        return True
    if np.any(part.max(axis=0) < other.min(axis=0)-tolerance) or np.any(other.max(axis=0) < part.min(axis=0)-tolerance):
        return False
    origin = other.mean(axis=0)
    _, singular, axes = np.linalg.svd(other-origin)
    if singular[1] <= 1e-10:
        return True
    normal = axes[-1]
    signed = (part-origin) @ normal
    if signed.min() > tolerance or signed.max() < -tolerance:
        return False
    basis = axes[:2]
    hull = _hull([tuple(p) for p in (other-origin) @ basis.T])
    if np.abs(signed).max() <= tolerance:
        overlap = [tuple(p) for p in (part-origin) @ basis.T]
        for a, b in zip(hull, hull[1:]+hull[:1]):
            edge = np.asarray(b)-a
            n = np.asarray((edge[1], -edge[0]))
            overlap = _clip_2d(overlap, n, n @ a)
            if not overlap:
                return False
        return _area(overlap) > tolerance*tolerance
    section = [p for p, d in zip(part, signed) if abs(d) <= tolerance]
    for a, b, da, db in zip(part, np.roll(part, -1, axis=0), signed, np.roll(signed, -1)):
        if (da < 0 < db) or (db < 0 < da):
            section.append(a+(b-a)*(da/(da-db)))
    if len(section) < 2:
        return False
    # Plane clipping leaves a line segment; choose its furthest endpoints.
    a, b = max(((a, b) for a in section for b in section), key=lambda pair: np.linalg.norm(pair[1]-pair[0]))
    length = float(np.linalg.norm(b-a))
    if length <= tolerance:
        return False
    a, b = (a-origin) @ basis.T, (b-origin) @ basis.T
    low, high = 0., 1.
    for p, q in zip(hull, hull[1:]+hull[:1]):
        edge = np.asarray(q)-p
        n = np.asarray((edge[1], -edge[0]))
        da, db = n @ (a-p), n @ (b-p)
        if da > 0 and db > 0:
            return False
        if da > 0:
            low = max(low, float(da/(da-db)))
        elif db > 0:
            high = min(high, float(da/(da-db)))
        if low >= high:
            return False
    return (high-low)*length > tolerance


def rectangularize_halo1_portal(mesh, group, source_records, is_solid, scale, *, _plane_motion=0.):
    """Recover a compact, nearly rectangular face inside proven solid.

    The tag lost the authored outline and exact-portal flag. An enclosing
    rectangle is an approximation. Outside the existing outline tolerance,
    every added convex piece must be wholly solid in the source BSP, including
    a thin volume on both sides. Preserve junctions and reject new crossings
    through the source portal openings. Reconstructed extensions may overlap
    each other inside proven solid, where Tool clips them away. Unsupported
    shapes keep their repaired outlines. Shared supporting edges constrain
    individual sides. A joined plane's narrow displacement band must belong
    to its original cluster pair; all added area beyond that band stays solid.
    """
    if (not hasattr(is_solid, 'contains_prism')
            or not np.isfinite(scale) or scale <= 0):
        return False
    if len(mesh.polygons) > 1:
        # A near-coplanar join can move an old wall edge into the opening.
        # Work on a copy: only commit the flattened plane together with a
        # certified replacement outline, never a face with an uncovered edge.
        import bpy
        working = mesh.copy()
        recovery = {}
        try:
            if (not dissolve_halo1_portal_seams(working, group, source_records, is_solid, scale,
                                               _wall_recovery=recovery)
                    or not rectangularize_halo1_portal(working, group, source_records, is_solid, scale,
                                                       _plane_motion=recovery['motion'])):
                return False
            bm = bmesh.new()
            try:
                bm.from_mesh(working)
                bm.to_mesh(mesh)
            finally:
                bm.free()
            mesh.update()
            return True
        finally:
            bpy.data.meshes.remove(working)
    if len(mesh.polygons) != 1:
        return False
    order = tuple(mesh.polygons[0].vertices)
    points = np.asarray([mesh.vertices[i].co for i in order], dtype=np.float64)/scale
    if len(points) < 3 or not np.all(np.isfinite(points)):
        return False
    origin = points.mean(axis=0)
    _, singular, axes = np.linalg.svd(points-origin)
    if singular[1] < 1e-8 or np.abs((points-origin) @ axes[-1]).max() > .0005:
        return False
    normal = axes[-1]
    winding = np.cross(points-origin, np.roll(points, -1, axis=0)-origin).sum(axis=0)
    if normal @ winding < 0:
        normal = -normal
    ids = {record.index for record in group}
    others = [record.vertices for record in source_records if record.index not in ids]
    # A shared edge between coplanar portals belonging to different groups
    # carries a cluster subdivision. Keep that compiled boundary: replacing
    # both faces with overlapping rectangles lets Tool combine their cuts.
    # Wall overlap has already moved the displayed vertices, so identify
    # shared edges using their source coordinates, as with fragment grouping.
    source_points = np.asarray([p for record in source_records if record.index in ids
                                for p in record.vertices])
    if not len(source_points):
        return False
    for other in others:
        other_points = np.asarray(other, dtype=np.float64)
        if len(other_points) < 3 or not np.all(np.isfinite(other_points)):
            return False
        center = other_points.mean(axis=0)
        _, _, directions = np.linalg.svd(other_points-center)
        if (abs(directions[-1] @ normal) >= .99999
                and np.abs((other_points-origin) @ normal).max() <= .0005
                and sum(np.linalg.norm(source_points-p, axis=1).min() <= .00025 for p in other_points) >= 2):
            return False
    base_u = axes[0]
    base_v = np.cross(normal, base_u)
    projected = (points-origin) @ np.asarray((base_u, base_v)).T
    hull = _hull([tuple(p) for p in projected])
    if len(hull) < 3:
        return False
    # Prefer the smallest enclosing rectangle. Its directions come from
    # surviving straight sides, rather than arbitrary world-axis alignment.
    candidates = []
    for a, b in zip(hull, hull[1:]+hull[:1]):
        u = np.asarray(b)-a
        u /= np.linalg.norm(u)
        v = np.asarray((-u[1], u[0]))
        basis = np.asarray((u, v))
        local = projected @ basis.T
        low, high = local.min(axis=0), local.max(axis=0)
        rectangle = np.asarray(((low[0], low[1]), (high[0], low[1]),
                                (high[0], high[1]), (low[0], high[1]))) @ basis
        candidates.append((float(np.prod(high-low)), rectangle))
    candidates.sort(key=lambda item: item[0])
    best_rectangle = candidates[0]
    # Compiler clipping can leave two long sides slightly non-perpendicular.
    # Rotating either into a strict rectangle can add a thin wedge of open
    # space at a junction. Also try nearly rectangular parallelograms whose
    # supporting lines follow both surviving sides without moving them.
    directions = []
    for a, b in zip(hull, hull[1:]+hull[:1]):
        direction = np.asarray(b)-a
        direction /= np.linalg.norm(direction)
        if not any(abs(direction @ other) > 1-1e-10 for other in directions):
            directions.append(direction)
    alternatives = []
    for i, u in enumerate(directions):
        for v in directions[i+1:]:
            if abs(u @ v) > .08:
                continue
            basis = np.asarray(((-u[1], u[0]), (-v[1], v[0])))
            local = projected @ basis.T
            low, high = local.min(axis=0), local.max(axis=0)
            corners = np.asarray(((low[0], low[1]), (high[0], low[1]),
                                  (high[0], high[1]), (low[0], high[1])))
            outline = _hull(list(map(tuple, np.linalg.solve(basis, corners.T).T)))
            alternatives.append((_area(outline), np.asarray(outline)))
    alternatives.sort(key=lambda item: item[0])
    candidates = [best_rectangle, *alternatives[:8]]
    # Junctions are constraints on individual sides, rather than a reason to
    # preserve every cliff-clipped side. Clip enclosing candidates at any
    # shared supporting line, keeping the original cut through open space.
    junctions = _portal_junctions(group, source_records, .00025)
    contacts = (junctions-origin) @ np.asarray((base_u, base_v)).T
    constraints = []
    for i, a in enumerate(contacts):
        for b in contacts[i+1:]:
            edge = b-a
            length = np.linalg.norm(edge)
            if length <= .00025:
                continue
            u = edge/length
            basis = np.asarray((u, (-u[1], u[0])))
            local = projected @ basis.T
            low, high = local.min(axis=0), local.max(axis=0)
            rectangle = np.asarray(((low[0], low[1]), (high[0], low[1]),
                                    (high[0], high[1]), (low[0], high[1]))) @ basis
            candidates.append((float(np.prod(high-low)), rectangle))
            n = np.asarray((edge[1], -edge[0]))/length
            d = float(n @ a)
            signed = projected @ n-d
            if signed.max() <= .0005:
                constraints.append((n, d))
            elif signed.min() >= -.0005:
                constraints.append((-n, -d))
    if constraints:
        constrained = []
        for _, candidate in candidates:
            outline = list(map(tuple, candidate))
            for n, d in constraints:
                outline = _clip_2d(outline, n, d)
            if outline:
                outline = [p[:2] for p in _simplify_outline(
                    [(*p, 0.) for p in outline], set(), .00025)]
                constrained.append((_area(outline), np.asarray(outline)))
        candidates = sorted(constrained, key=lambda item: (len(item[1]), item[0]))
        if not candidates:
            return False
    source_area = _area(list(map(tuple, projected)))
    if candidates[0][0] > source_area*3 or candidates[0][0] <= 1e-8:
        return False
    # Subtract the actual face, including concave notches, using its Blender
    # triangulation. A hull alone would hide openings inside those notches.
    mesh.calc_loop_triangles()
    index_lookup = {index: i for i, index in enumerate(order)}
    triangles = [_hull([tuple(projected[index_lookup[i]]) for i in tri.vertices])
                 for tri in mesh.loop_triangles]
    if not triangles or any(len(triangle) != 3 for triangle in triangles):
        return False
    for area, rectangle in candidates:
        if area > source_area*3:
            continue
        # This also protects isolated point contacts, which do not define a
        # supporting side: a recovered face must keep them on its boundary.
        junctions_preserved = True
        for point in contacts:
            distances = []
            for a, b in zip(rectangle, np.roll(rectangle, -1, axis=0)):
                edge = b-a
                fraction = np.clip((point-a) @ edge/(edge @ edge), 0., 1.)
                distances.append(np.linalg.norm(point-a-fraction*edge))
            if min(distances) > .00025:
                junctions_preserved = False
                break
        if not junctions_preserved:
            continue
        pieces = [list(map(tuple, rectangle))]
        for triangle in triangles:
            pieces = [outside for part in pieces for outside in _subtract_convex(part, triangle)]
        world = origin + rectangle[:, :1]*base_u + rectangle[:, 1:]*base_v
        # Float32 clipping permits the same .00025 outline tolerance as edge
        # cleanup. A joined plane also has a bounded displacement band, which
        # needs cluster membership proof instead of blindly ignoring it.
        certified = _outside_outline_band(pieces, projected, .00025 + _plane_motion)
        proof = [origin + np.asarray(part)[:, :1]*base_u + np.asarray(part)[:, 1:]*base_v
                 for part in certified]
        if _plane_motion:
            clusters = {r.front_cluster for r in group} | {r.back_cluster for r in group}
            if (len(clusters) != 2 or min(clusters) < 0
                    or not getattr(is_solid, 'leaf_clusters', ())
                    or not is_solid.contains_prism(world, normal, allowed_clusters=clusters)):
                continue
            # Moving the plane must not introduce an interior intersection,
            # even within the old opening or its narrow displacement band.
            # Only boundary contacts with neighbouring portals are allowed.
            interior = list(map(tuple, rectangle))
            for a, b in zip(rectangle, np.roll(rectangle, -1, axis=0)):
                edge = b-a
                n = np.asarray((edge[1], -edge[0]))/np.linalg.norm(edge)
                interior = _clip_2d(interior, n, n @ a-.0005)
            if not interior:
                continue
            inside_world = origin + np.asarray(interior)[:, :1]*base_u + np.asarray(interior)[:, 1:]*base_v
            if any(_portal_extension_intersects(inside_world, other) for other in others):
                continue
        if any(not is_solid.contains_prism(part, normal) for part in proof):
            continue
        # Plane motion never broadens the tolerance for other portal cuts.
        crossings = _outside_outline_band(pieces, projected, .00025) if _plane_motion else certified
        crossing_world = [origin + np.asarray(part)[:, :1]*base_u + np.asarray(part)[:, 1:]*base_v
                          for part in crossings]
        if any(_portal_extension_intersects(part, other)
               for part in crossing_world for other in others):
            continue
        # Four vertices are already as simple as a rectangle. Avoid replacing
        # a source quad unless its enclosing rectangle actually changes it.
        if len(order) == 4 and area <= source_area*(1+1e-5):
            return False
        mesh.clear_geometry()
        mesh.from_pydata([tuple(value*scale for value in p) for p in world], [], [tuple(range(len(world)))])
        mesh.update()
        return True
    return False


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


# Keep the H1 entry points used by existing callers and validation scripts.
# Their geometric guards also apply to the other tag portal formats.
stabilize_portal_tessellation = stabilize_halo1_portal_tessellation
dissolve_portal_seams = dissolve_halo1_portal_seams
rectangularize_portal = rectangularize_halo1_portal


def prepare_portal_import(records, game, is_solid=None):
    """Prepare compatible fragment groups without changing their semantics.

    H1 retains its validated reconstruction and wall-overlap behavior. Other
    games share bounded plane repair, junction-aware simplification and merging;
    added outlines are committed later only with a complete solid-volume proof.
    Recovered Reach face loops remain intact until seam cleanup on the mesh.
    """
    sources = list(records)
    if game == 'halo1':
        records, _ = reconstruct_portals(sources, is_solid=is_solid)
    else:
        records = simplify_portals(sources)
    records = stabilize_halo1_portals(records, is_solid if game == 'halo1' else None, sources)
    return group_halo1_portals(records, sources), sources

"""Conservative repairs for compiler triangulation in Reach tag meshes."""
from collections import Counter, defaultdict
from dataclasses import replace

import bpy
import bmesh
import numpy as np
from mathutils import kdtree

from .. import utils


def preserve_two_sided_sealers(mesh):
    """Represent untextured two-sided collision without Tool's sealer type.

    Reach treats seam sealers as solid boundary faces even with a two-sided
    annotation. An ordinary collision-only face preserves the recovered sheet
    without making its free edges into holes in the surrounding solid shell.
    """
    two_sided = set()
    for prop in mesh.nwo.face_props:
        if prop.type == 'face_sides' and prop.two_sided:
            attribute = mesh.attributes.get(prop.attribute_name)
            if attribute is not None:
                two_sided.update(i for i, value in enumerate(attribute.data) if value.value)
    indices = [face.index for face in mesh.polygons if face.index in two_sided
               and face.material_index < len(mesh.materials)
               and mesh.materials[face.material_index] is not None
               and mesh.materials[face.material_index].name.lower().startswith('+seamsealer')
               and not mesh.materials[face.material_index].nwo.shader_path.strip()]
    if not indices:
        return 0
    material = next((m for m in bpy.data.materials if m.get('foundry_untextured_collision')), None)
    if material is None:
        material = bpy.data.materials.new('Reach two-sided collision')
        material['foundry_untextured_collision'] = True
    slot = next((i for i, m in enumerate(mesh.materials) if m == material), None)
    if slot is None:
        slot = len(mesh.materials)
        mesh.materials.append(material)
    mask = np.zeros(len(mesh.polygons), dtype=np.int8)
    for index in indices:
        mesh.polygons[index].material_index = slot
        mask[index] = 1
    utils.add_face_prop(mesh, 'face_mode', mask).face_mode = 'collision_only'
    utils.add_face_prop(mesh, 'global_material', mask).global_material = 'default'
    return len(indices)


def recover_mapped_collision(collision_mesh, render_meshes, tolerance):
    """Keep uncovered parts of collision polygons which have render mappings.

    A tag mapping says which triangles correspond to a polygon, not that their
    union covers all of it. Reuse H1's coverage calculation across the whole
    polygon, including cases with one covered and one entirely missing half.
    Only restore whole source triangles that reconnect an open boundary; leave
    partial clips and uncertain plane matches for explicit reconstruction.
    """
    from .classic_geometry import _triangles, _candidates, _partition, _replace_faces

    # Mapped Reach surfaces can span several render materials. Any existing
    # coplanar render coverage prevents adding duplicate collision there.
    render = [replace(triangle, material=None) for mesh in render_meshes
              for triangle in _triangles(mesh)]
    collision = [replace(triangle, material=None) for triangle in _triangles(collision_mesh)]
    _, matches = _candidates(render, collision, tolerance)
    edges = Counter()
    for mesh in render_meshes:
        excluded = set()
        for prop in mesh.nwo.face_props:
            if (prop.type == 'face_mode' and prop.face_mode == 'render_only'
                    or prop.type == 'face_sides' and prop.two_sided):
                attribute = mesh.attributes.get(prop.attribute_name)
                if attribute is not None:
                    excluded.update(i for i, value in enumerate(attribute.data) if value.value)
        for face in mesh.polygons:
            if face.index in excluded:
                continue
            points = [tuple(mesh.vertices[i].co) for i in face.vertices]
            edges.update(zip(points, points[1:] + points[:1]))
    positions = sorted({p for edge in edges for p in edge})
    tree = kdtree.KDTree(len(positions))
    for i, position in enumerate(positions):
        tree.insert(position, i)
    tree.balance()
    position_set = set(positions)

    def existing_position(point):
        point = tuple(point)
        if point in position_set:
            return point
        nearby = tree.find_range(point, tolerance * .1)
        return positions[nearby[0][1]] if len(nearby) == 1 else point

    pieces = defaultdict(lambda: ([], []))
    split_polygons = set()
    for index, triangle in enumerate(collision):
        uncovered, covered = _partition(
            triangle, (render[i] for i in matches.get(index, ())), tolerance)
        if uncovered and covered:
            split_polygons.add(triangle.polygon)
        pieces[triangle.polygon][0].extend(uncovered)
        pieces[triangle.polygon][1].extend(covered)

    # Nonmatching/nonplanar polygons retain the existing mapping behavior.
    # Only positive partial coverage is evidence of a missing collision patch.
    partitions = {face.index: ([], [None]) for face in collision_mesh.polygons}
    recovered = 0
    for index, (uncovered, covered) in pieces.items():
        if not uncovered or not covered or index in split_polygons:
            continue
        area = sum(np.linalg.norm(np.cross(np.subtract(p[i], p[0]), np.subtract(p[i+1], p[0]))) / 2
                   for p in uncovered for i in range(1, len(p)-1))
        face = collision_mesh.polygons[index]
        coords = [collision_mesh.vertices[i].co for i in face.vertices]
        perimeter = sum((b-a).length for a, b in zip(coords, coords[1:] + coords[:1]))
        if area <= max(face.area * .001, tolerance * perimeter):
            continue
        # A real remainder reconnects an open boundary. Do not add triangles
        # over already closed render edges merely because a compiled plane's
        # normal differs enough to fail the coplanarity test.
        boundary_matches = 0
        occupied = False
        for polygon in uncovered:
            points = [existing_position(point) for point in polygon]
            for a, b in zip(points, points[1:] + points[:1]):
                if edges[(a, b)] or edges[(b, a)] > 1:
                    occupied = True
                boundary_matches += edges[(b, a)] == 1 and edges[(a, b)] == 0
        if occupied or not boundary_matches:
            continue
        partitions[index] = (uncovered, [None])
        recovered += 1
    _replace_faces(collision_mesh, partitions, False)
    return recovered


def retriangulate_render_slivers(mesh, tolerance):
    """Replace bad diagonals without moving vertices or crossing data seams.

    Reach's compiled render triangles can be nearly collinear, even though
    their surrounding polygon has a valid triangulation. Tool drops these
    triangles on reimport. Keep every boundary vertex and change only an
    internal diagonal between compatible triangles. At UV or normal seams,
    retain the render triangles and recover collision separately instead.
    """
    bm = bmesh.new()
    changed = 0
    try:
        bm.from_mesh(mesh)
        preserve_normals = mesh.has_custom_normals
        if preserve_normals:
            utils.save_loop_normals(bm, mesh)
        mode_layers = [bm.faces.layers.bool.new('.reach_sliver_' + mode)
                       for mode in ('render_only', 'collision_only')]
        attributes = [a for a in mesh.attributes if a.domain == 'FACE'
                      and not a.name.startswith(('.', 'ln'))
                      and a.data_type in {'BOOLEAN', 'INT', 'FLOAT'}]
        identities = {f: (f.material_index, tuple(a.data[f.index].value for a in attributes))
                      for f in bm.faces}
        uv_layers = list(bm.loops.layers.uv.values())
        separated = set()
        excluded = {f for f in bm.faces for prop in mesh.nwo.face_props
                    if (prop.type == 'face_mode' and prop.face_mode != 'normal'
                        or prop.type == 'face_sides' and prop.two_sided)
                    and mesh.attributes.get(prop.attribute_name) is not None
                    and mesh.attributes[prop.attribute_name].data[f.index].value}

        def altitude(points):
            a, b, c = points
            longest = max((a-b).length, (b-c).length, (c-a).length)
            return (b-a).cross(c-a).length / longest if longest else 0

        def normal(loop):
            return loop.face[bm.faces.layers.float_vector[f'ln{list(loop.face.loops).index(loop)}']]

        for face in list(bm.faces):
            if not face.is_valid or face in separated or face in excluded or len(face.verts) != 3:
                continue
            old_altitude = altitude([v.co for v in face.verts])
            if old_altitude > tolerance:
                continue
            choices = []
            for loop in face.loops:
                edge = loop.edge
                if len(edge.link_faces) != 2 or not edge.is_contiguous:
                    continue
                other = next(f for f in edge.link_faces if f != face)
                if (other in separated or other in excluded or len(other.verts) != 3
                        or identities.get(face) != identities.get(other)):
                    continue
                a, b = loop.vert, loop.link_loop_next.vert
                c = loop.link_loop_prev.vert
                d = next(v for v in other.verts if v not in edge.verts)
                if d == c or bm.edges.get((c, d)) is not None:
                    continue
                # The replacement must lie in the same local surface and keep
                # its winding; a narrow folded feature is not a bad diagonal.
                if abs((c.co-a.co).dot(other.normal)) > tolerance:
                    continue
                triangles = ((c, a, d), (c, d, b))
                normals = [(t[1].co-t[0].co).cross(t[2].co-t[0].co) for t in triangles]
                if any(n.dot(other.normal) <= 0 for n in normals):
                    continue
                quality = min(altitude([v.co for v in t]) for t in triangles)
                if quality < max(tolerance * 2, old_altitude * 4):
                    continue
                loops = {l.vert: l for l in other.loops}
                compatible = True
                for l in face.loops:
                    previous = loops.get(l.vert)
                    if previous is not None:
                        if any((l[layer].uv-previous[layer].uv).length > 1e-5 for layer in uv_layers):
                            compatible = False
                        if preserve_normals and (normal(l)-normal(previous)).length > 1e-3:
                            compatible = False
                    else:
                        loops[l.vert] = l
                choices.append((compatible, quality, other, edge, triangles, loops))
            if not choices:
                # A folded sliver can backtrack along a neighbour's boundary:
                # A--C--D is one straight edge, but the compiled pair takes
                # A--D--B--C--A. Keep the visible faces, and recover collision
                # as C--D--B plus a C split on the face across A--D.
                longest = max(face.edges, key=lambda e: e.calc_length())
                if len(longest.link_faces) != 2 or not longest.is_contiguous:
                    continue
                other = next(f for f in longest.link_faces if f != face)
                if (other in excluded or other in separated or len(other.verts) != 3
                        or identities[face] != identities.get(other)):
                    continue
                c = next(v for v in face.verts if v not in longest.verts)
                d = next(v for v in other.verts if v not in longest.verts)
                for a in longest.verts:
                    delta = d.co-a.co
                    if not delta.length_squared:
                        continue
                    t = (c.co-a.co).dot(delta) / delta.length_squared
                    if not 0 < t < 1 or (c.co-(a.co+t*delta)).length > tolerance * .1:
                        continue
                    edge = bm.edges.get((a, d))
                    if edge is None or len(edge.link_faces) != 2 or not edge.is_contiguous:
                        continue
                    across = next(f for f in edge.link_faces if f != other)
                    if across in excluded or across in separated or c in across.verts:
                        continue
                    triangle = [c if v == a else v for v in other.verts]
                    if altitude([v.co for v in triangle]) < tolerance * 2:
                        continue
                    boundary = []
                    for loop in across.loops:
                        boundary.append(loop.vert)
                        if loop.edge == edge:
                            boundary.append(c)
                    for vertices, template in ((triangle, other), (boundary, across)):
                        new = bm.faces.new([bm.verts.new(v.co) for v in vertices], template)
                        for loop in new.loops:
                            loop.copy_from_face_interp(template, True)
                        new[mode_layers[1]] = True
                        separated.add(new)
                    for original in (face, other, across):
                        original[mode_layers[0]] = True
                        separated.add(original)
                    changed += 1
                    break
                continue
            compatible, _, other, edge, triangles, loops = max(choices, key=lambda choice: choice[:2])
            for vertices in triangles:
                new_vertices = vertices if compatible else [bm.verts.new(v.co) for v in vertices]
                new = bm.faces.new(new_vertices, face)
                identities[new] = identities[face]
                for index, loop in enumerate(new.loops):
                    original = loops[vertices[index]]
                    loop.copy_from(original)
                    if preserve_normals:
                        new[bm.faces.layers.float_vector[f'ln{index}']] = normal(original)
                if not compatible:
                    new[mode_layers[1]] = True
                    separated.add(new)
            if compatible:
                bm.faces.remove(face)
                bm.faces.remove(other)
                bm.edges.remove(edge)
            else:
                # A UV/hard-normal seam must remain in the visible surface.
                # Preserve both render triangles and give their same outer
                # boundary a separate, valid collision triangulation.
                face[mode_layers[0]] = other[mode_layers[0]] = True
                separated.update((face, other))
            changed += 1
        if changed:
            bm.to_mesh(mesh)
    finally:
        bm.free()
    if changed:
        mesh.update()
        if preserve_normals:
            utils.apply_loop_normals(mesh)
        for mode in ('render_only', 'collision_only'):
            attribute = mesh.attributes.get('.reach_sliver_' + mode)
            mask = np.array([v.value for v in attribute.data], dtype=np.int8)
            if mask.any():
                utils.add_face_prop(mesh, 'face_mode', mask).face_mode = mode
            mesh.attributes.remove(attribute)
        utils.calc_face_prop_counts(mesh)
    return changed

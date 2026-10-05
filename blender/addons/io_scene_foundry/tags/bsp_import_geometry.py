"""Finish BSP source reconstruction entirely during import."""

from collections import Counter, defaultdict
from dataclasses import replace
import bpy
import bmesh
import numpy as np
from mathutils import kdtree

from .. import utils


def reconnect_collinear_triangles(mesh, tolerance=0):
    """Replace zero-width compiler triangles by a real boundary junction.

    A mapped triangle may consist of three points on one straight mesh edge,
    within the import caller's physical position tolerance.
    Tool discards it, leaving an otherwise closed instance open. Insert its
    middle vertex into the face across the long edge and remove the zero-width
    triangle. Keep positions and every surviving corner's data; the new corner
    inherits the enclosing face's UVs, colors and normals. Its other neighbours
    retain their own UV and normal seams. No alternate collision faces are made.
    """
    provenance = mesh.attributes.get('.foundry_collision_plane')
    if provenance is None:
        return 0
    bm = bmesh.new()
    changed = 0
    try:
        bm.from_mesh(mesh)
        normal_layer = None
        if mesh.has_custom_normals:
            normal_layer = bm.loops.layers.float_vector.new('.foundry_junction_normal')
            for face, polygon in zip(bm.faces, mesh.polygons):
                for loop, index in zip(face.loops, polygon.loop_indices):
                    loop[normal_layer] = mesh.corner_normals[index].vector
        plane = bm.faces.layers.int[provenance.name]
        excluded = {face for face in bm.faces for prop in mesh.nwo.face_props
                    if (prop.type == 'face_mode' and prop.face_mode != 'normal'
                        or prop.type == 'face_sides' and prop.two_sided)
                    and (attribute := mesh.attributes.get(prop.attribute_name)) is not None
                    and attribute.data[face.index].value}
        for face in list(bm.faces):
            if not face.is_valid or face in excluded or face[plane] < 0 or len(face.verts) != 3:
                continue
            # Only reconnect a closed local shell. Genuine open faces and
            # non-manifold junctions do not establish which side survives.
            if any(len(edge.link_faces) != 2 or not edge.is_contiguous for edge in face.edges):
                continue
            edge = max(face.edges, key=lambda e: e.calc_length())
            other = next(f for f in edge.link_faces if f != face)
            if other in excluded or len(other.verts) != 3 or other[plane] < 0:
                continue
            c = next(v for v in face.verts if v not in edge.verts)
            loop = next(loop for loop in other.loops if loop.edge == edge)
            a, b, d = loop.vert, loop.link_loop_next.vert, loop.link_loop_prev.vert
            if c in other.verts or bm.edges.get((c, d)) is not None:
                continue
            delta = b.co - a.co
            if not delta.length_squared:
                continue
            fraction = (c.co - a.co).dot(delta) / delta.length_squared
            magnitude = max(delta.length, *(abs(value) for v in face.verts for value in v.co))
            epsilon = max(float(np.spacing(np.float32(magnitude))) * 4, tolerance)
            if not 0 < fraction < 1 or (c.co - (a.co + fraction * delta)).length > epsilon:
                continue
            if other.calc_area() <= max(face.calc_area() * 100, epsilon * epsilon):
                continue
            triangles = ((a, c, d), (c, b, d))
            if any((y.co-x.co).cross(z.co-x.co).dot(other.normal) <= 0 for x,y,z in triangles):
                continue
            original = {loop.vert: loop for loop in other.loops}
            for vertices in triangles:
                new = bm.faces.new(vertices, other)
                for loop in new.loops:
                    if loop.vert in original:
                        loop.copy_from(original[loop.vert])
                    else:
                        loop.copy_from_face_interp(other, False)
            bm.faces.remove(face)
            bm.faces.remove(other)
            bm.edges.remove(edge)
            changed += 1
        if not changed:
            return 0
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if normal_layer is not None:
        attribute = mesh.attributes.get('.foundry_junction_normal')
        values = np.empty((len(mesh.loops), 3), dtype=np.float32)
        attribute.data.foreach_get('vector', values.ravel())
        lengths = np.linalg.norm(values, axis=1)
        valid = lengths > 0
        values[valid] /= lengths[valid, None]
        mesh.normals_split_custom_set(values)
        mesh.attributes.remove(attribute)
    mesh.update()
    utils.calc_face_prop_counts(mesh)
    return changed


def recover_folded_patch_boundaries(mesh, tolerance):
    """Cancel a compiler fold, retaining one real textured physical surface.

    Require the same native plane, material and face properties. Opposing
    fragments must have a unique closed outer boundary with a collinear
    backtrack. A UV or normal seam on their internal edge prevents merging.
    No positions move, and no replacement render/collision overlays survive.
    """
    provenance = mesh.attributes.get('.foundry_collision_plane')
    if provenance is None or not mesh.polygons:
        return 0
    bm = bmesh.new()
    changed = 0
    try:
        bm.from_mesh(mesh)
        bm.faces.ensure_lookup_table()
        original_faces = list(bm.faces)
        if mesh.has_custom_normals:
            normal_layer = bm.loops.layers.float_vector.new('.foundry_fold_normal')
            normals = mesh.corner_normals
            for face in bm.faces:
                for loop, index in zip(face.loops, mesh.polygons[face.index].loop_indices):
                    loop[normal_layer] = normals[index].vector
        else:
            normal_layer = None
        plane = bm.faces.layers.int[provenance.name]
        properties = [a for a in mesh.attributes if a.domain=='FACE' and not a.name.startswith('.')
                      and a.data_type in {'BOOLEAN','INT','FLOAT'}]
        identities = {face:(face.material_index,face.smooth,
                           tuple(a.data[face.index].value for a in properties)) for face in bm.faces}
        excluded = {face for face in bm.faces for prop in mesh.nwo.face_props
                    if (prop.type=='face_mode' and prop.face_mode!='normal'
                        or prop.type=='face_sides' and prop.two_sided)
                    and (a:=mesh.attributes.get(prop.attribute_name)) is not None
                    and a.data[face.index].value}
        uv_layers = list(bm.loops.layers.uv.values())
        color_layers = [*bm.loops.layers.color.values(),*bm.loops.layers.float_color.values()]
        pairs = set()
        for edge in bm.edges:
            if len(edge.link_faces)==2 and edge.is_contiguous:
                a,b = edge.link_faces
                pairs.add(tuple(sorted((a.index,b.index))))

        def redundant(loop):
            a,b,c = loop.link_loop_prev.vert.co,loop.vert.co,loop.link_loop_next.vert.co
            delta=c-a
            if not delta.length_squared:
                return True
            t=(b-a).dot(delta)/delta.length_squared
            return 0<t<1 and (b-(a+t*delta)).length<=tolerance

        for ai,bi in sorted(pairs):
            a,b = original_faces[ai],original_faces[bi]
            if (not a.is_valid or not b.is_valid or a in excluded or b in excluded
                    or a[plane]<0 or a[plane]!=b[plane] or identities[a]!=identities[b]
                    or a.normal.dot(b.normal)>-.999):
                continue
            common = set(a.edges)&set(b.edges)
            if not common:
                continue
            choices = {}
            for face in (a,b):
                for loop in face.loops:
                    choices.setdefault(loop.vert,[]).append(loop)
            # Ignore only redundant corners introduced on an existing edge;
            # their interpolated data do not supersede an original source corner.
            compatible = True
            for vertex, loops in choices.items():
                significant = [loop for loop in loops if not redundant(loop)]
                if len(significant)!=2:
                    continue
                x,y=significant
                if (any((x[layer].uv-y[layer].uv).length>1e-5 for layer in uv_layers)
                        or any((x[layer]-y[layer]).length>1e-5 for layer in color_layers)
                        or normal_layer is not None and (x[normal_layer]-y[normal_layer]).length>1e-3):
                    compatible=False
                    break
            if not compatible:
                continue
            edges=Counter((loop.vert,loop.link_loop_next.vert) for face in (a,b) for loop in face.loops)
            boundary=[(x,y) for (x,y),count in edges.items() for _ in range(max(0,count-edges[y,x]))]
            outgoing={}
            for x,y in boundary:
                if x in outgoing:
                    break
                outgoing[x]=y
            else:
                if not outgoing:
                    continue
                start=min(outgoing,key=lambda v:v.index)
                vertices=[]
                current=start
                while current in outgoing and current not in vertices:
                    vertices.append(current)
                    current=outgoing[current]
                if current!=start or len(vertices)!=len(boundary):
                    continue
                removed=0
                for vertex in list(vertices):
                    if len(vertices)<4:
                        break
                    i=vertices.index(vertex)
                    prev,nxt=vertices[i-1],vertices[(i+1)%len(vertices)]
                    x,y=prev.co-vertex.co,nxt.co-vertex.co
                    if (x.dot(y)>0 and x.cross(y).length/max(x.length,y.length,1e-20)<=tolerance):
                        vertices.remove(vertex)
                        removed+=1
                # Two shared edges may already have cancelled the spur.
                removed += len(choices)-len(outgoing)
                if not removed or len(vertices)<3 or len(set(vertices))!=len(vertices):
                    continue
                template = a if a.calc_area()>b.calc_area() else b
                origin=vertices[0].co
                normal=sum(((vertices[i].co-origin).cross(vertices[i+1].co-origin)
                            for i in range(1,len(vertices)-1)),origin*0)
                if normal.dot(template.normal)<=0 or normal.length<=tolerance*tolerance:
                    continue
                # An existing boundary face makes this more than a simple
                # two-fragment fold. Leave that ambiguous patch for inspection.
                if bm.faces.get(vertices) is not None:
                    continue
                new=bm.faces.new(vertices,template)
                for loop in new.loops:
                    candidates=choices[loop.vert]
                    source=min(candidates,key=redundant)
                    loop.copy_from(source)
                bm.faces.remove(a)
                bm.faces.remove(b)
                changed+=1
        if not changed:
            return 0
        bmesh.ops.delete(bm,geom=[e for e in bm.edges if not e.link_faces],context='EDGES')
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if normal_layer is not None:
        attribute=mesh.attributes.get('.foundry_fold_normal')
        values=np.empty((len(mesh.loops),3),dtype=np.float32)
        attribute.data.foreach_get('vector',values.ravel())
        lengths=np.linalg.norm(values,axis=1)
        valid=lengths>0
        values[valid]/=lengths[valid,None]
        mesh.normals_split_custom_set(values)
        mesh.attributes.remove(attribute)
    mesh.update()
    utils.calc_face_prop_counts(mesh)
    return changed

def discard_import_working_data(mesh):
    """Leave a normal source mesh after all native-boundary repairs finish."""
    for attribute in list(mesh.attributes):
        if attribute.name.startswith(('.foundry_collision_', '.foundry_render_', '.foundry_shared_render')):
            mesh.attributes.remove(attribute)


def recover_mapped_collision(collision_mesh, render_meshes, tolerance):
    """Keep uncovered parts of collision polygons which have render mappings.

    A tag mapping says which triangles correspond to a polygon, not that their
    union covers all of it. Reuse H1's coverage calculation across the whole
    polygon, including cases with one covered and one entirely missing half.
    Only restore whole source triangles that reconnect an open boundary; leave
    partial clips and uncertain plane matches for explicit reconstruction.
    """
    from .classic_geometry import _triangles, _candidates, _partition, _replace_faces

    # Mapped BSP surfaces can span several render materials. Any existing
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

def retriangulate_render_slivers(mesh, tolerance, *, collision_only=False,
                                relative_tolerance=0, respect_shading=True):
    """Replace bad diagonals without moving vertices or crossing data seams.

    Compiled render triangles can be nearly collinear, even though
    their surrounding polygon has a valid triangulation. Tool drops these
    triangles on reimport. Keep every boundary vertex and change only an
    internal diagonal between compatible triangles. At UV or normal seams,
    retain the original shared geometry rather than generating overlapping
    render-only and collision-only alternatives. Non-rendered seam surfaces
    may ignore shading discontinuities with respect_shading=False; their
    existing corner data and perimeter still survive the diagonal replacement.
    """
    bm = bmesh.new()
    changed = 0
    try:
        bm.from_mesh(mesh)
        preserve_normals = mesh.has_custom_normals
        if preserve_normals:
            utils.save_loop_normals(bm, mesh)
        attributes = [a for a in mesh.attributes if a.domain == 'FACE'
                      and not a.name.startswith(('.', 'ln'))
                      and a.data_type in {'BOOLEAN', 'INT', 'FLOAT'}]
        identities = {f: (f.material_index, tuple(a.data[f.index].value for a in attributes))
                      for f in bm.faces}
        uv_layers = list(bm.loops.layers.uv.values())
        excluded = {f for f in bm.faces for prop in mesh.nwo.face_props
                    if (prop.type == 'face_mode' and prop.face_mode not in
                        ({'normal', 'collision_only'} if collision_only else {'normal'})
                        or prop.type == 'face_sides' and prop.two_sided)
                    and mesh.attributes.get(prop.attribute_name) is not None
                    and mesh.attributes[prop.attribute_name].data[f.index].value}
        if collision_only:
            helpers = {f for f in bm.faces for prop in mesh.nwo.face_props
                       if prop.type == 'face_mode' and prop.face_mode == 'collision_only'
                       and mesh.attributes.get(prop.attribute_name) is not None
                       and mesh.attributes[prop.attribute_name].data[f.index].value}
            excluded.update(f for f in bm.faces if f not in helpers)

        def altitude(points):
            a, b, c = points
            longest = max((a-b).length, (b-c).length, (c-a).length)
            return (b-a).cross(c-a).length / longest if longest else 0

        def normal(loop):
            return loop.face[bm.faces.layers.float_vector[f'ln{list(loop.face.loops).index(loop)}']]

        for face in list(bm.faces):
            if not face.is_valid or face in excluded or len(face.verts) != 3:
                continue
            old_altitude = altitude([v.co for v in face.verts])
            # Tool also loses normals on very long, narrow helper triangles:
            # normalized float edges can round to parallel despite large area.
            relative_width = max(e.calc_length() for e in face.edges) * max(
                relative_tolerance, .0002 if collision_only else 0)
            if old_altitude > max(tolerance, relative_width):
                continue
            choices = []
            for loop in face.loops:
                edge = loop.edge
                if len(edge.link_faces) != 2 or not edge.is_contiguous:
                    continue
                other = next(f for f in edge.link_faces if f != face)
                if (other in excluded or len(other.verts) != 3
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
                        if respect_shading and not collision_only and any((l[layer].uv-previous[layer].uv).length > 1e-5 for layer in uv_layers):
                            compatible = False
                        if respect_shading and not collision_only and preserve_normals and (normal(l)-normal(previous)).length > 1e-3:
                            compatible = False
                    else:
                        loops[l.vert] = l
                choices.append((compatible, quality, other, edge, triangles, loops))
            choices = [choice for choice in choices if choice[0]]
            if not choices:
                continue
            _, _, other, edge, triangles, loops = max(choices, key=lambda choice: choice[:2])
            for vertices in triangles:
                new = bm.faces.new(vertices, face)
                identities[new] = identities[face]
                for index, loop in enumerate(new.loops):
                    original = loops[vertices[index]]
                    loop.copy_from(original)
                    if preserve_normals:
                        new[bm.faces.layers.float_vector[f'ln{index}']] = normal(original)
            bm.faces.remove(face)
            bm.faces.remove(other)
            bm.edges.remove(edge)
            changed += 1
        if changed:
            bm.to_mesh(mesh)
    finally:
        bm.free()
    if changed:
        mesh.update()
        if preserve_normals:
            utils.apply_loop_normals(mesh)
        utils.calc_face_prop_counts(mesh)
    return changed

def repair_collision_triangulation(mesh, tolerance):
    """Bake a safer helper triangulation only when it repairs a bad diagonal."""
    helpers = set()
    for prop in mesh.nwo.face_props:
        if prop.type == 'face_mode' and prop.face_mode == 'collision_only':
            attribute = mesh.attributes.get(prop.attribute_name)
            if attribute is not None:
                helpers.update(i for i, value in enumerate(attribute.data) if value.value)
    if not helpers:
        return 0
    candidate = mesh.copy()
    try:
        bm = bmesh.new()
        try:
            bm.from_mesh(candidate)
            if candidate.has_custom_normals:
                utils.save_loop_normals(bm, candidate)
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces
                                          if f.index in helpers and len(f.verts) > 3])
            bm.to_mesh(candidate)
        finally:
            bm.free()
        if mesh.has_custom_normals:
            utils.apply_loop_normals(candidate)
        changed = retriangulate_render_slivers(candidate, tolerance, collision_only=True)
        if not changed:
            return 0
        normals = [tuple(n.vector) for n in candidate.corner_normals] if candidate.has_custom_normals else None
        bm = bmesh.new()
        try:
            bm.from_mesh(candidate)
            bm.to_mesh(mesh)
        finally:
            bm.free()
        mesh.nwo.face_props.clear()
        for prop in candidate.nwo.face_props:
            result = mesh.nwo.face_props.add()
            for key, value in prop.items():
                result[key] = value
        mesh.update()
        if normals:
            mesh.normals_split_custom_set(normals)
        utils.calc_face_prop_counts(mesh)
        return changed
    finally:
        bpy.data.meshes.remove(candidate)

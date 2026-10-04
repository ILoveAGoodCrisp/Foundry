"""Finish BSP source reconstruction entirely during import."""

from collections import Counter
import bmesh
import numpy as np

from .. import utils


def reconnect_collinear_triangles(mesh):
    """Replace zero-width compiler triangles by a real boundary junction.

    A mapped triangle may consist of three points on one straight mesh edge.
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
            epsilon = float(np.spacing(np.float32(magnitude))) * 4
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

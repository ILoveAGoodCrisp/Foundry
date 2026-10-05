"""Convert imported shading into mesh data that remains useful while editing."""

from math import cos, radians

import bmesh

from ..tags.classic_geometry import weld_classic_vertices


def make_mesh_editable(mesh):
    """Weld coincident vertices and replace custom normals with edge sharpness.

    Exact welding keeps thin features, UV seams, face properties and separate
    render/collision overlays intact. Compare both ends of each shared edge:
    an authored normal split at either end makes that edge sharp. Allow one
    degree of encoding noise in the imported normals.
    """
    weld_classic_vertices(mesh, preserve_deformation=True)
    if not mesh.has_custom_normals:
        return

    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        normals = mesh.corner_normals
        loop_normals = {
            loop: normals[index].vector.copy()
            for face, polygon in zip(bm.faces, mesh.polygons)
            for loop, index in zip(face.loops, polygon.loop_indices)
        }
        threshold = cos(radians(1))
        for face in bm.faces:
            face.smooth = True
        for edge in bm.edges:
            if len(edge.link_faces) < 2:
                continue
            edge.smooth = True
            for vertex in edge.verts:
                values = [loop_normals[loop if loop.vert == vertex else loop.link_loop_next]
                          for loop in edge.link_loops]
                if any(values[0].dot(normal) < threshold for normal in values[1:]):
                    edge.smooth = False
                    break
        bm.to_mesh(mesh)
    finally:
        bm.free()

    # Blender stores custom normals as a corner attribute. Removing the layer
    # releases the normals entirely, rather than assigning automatic vectors
    # while leaving custom normal data on the mesh.
    attribute = mesh.attributes.get('custom_normal')
    if attribute is not None:
        mesh.attributes.remove(attribute)
    mesh.nwo.from_vert_normals = False
    mesh.update()

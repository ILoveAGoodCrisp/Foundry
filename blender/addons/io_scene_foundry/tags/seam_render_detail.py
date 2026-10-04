"""Keep compiled seam boundaries independent of render triangulation."""

import bmesh
from mathutils import kdtree

from .. import utils


def seam_adjacent_face_indices(mesh, seam_meshes):
    points = [vertex.co for seam_mesh in seam_meshes
              for vertex in seam_mesh.vertices]
    if not points:
        return set()
    tree = kdtree.KDTree(len(points))
    for index, point in enumerate(points):
        tree.insert(point, index)
    tree.balance()
    # Separate matching boundaries, without including nearby distinct detail.
    # Both streams have already been converted to Blender float32 positions.
    vertices = set()
    for vertex in mesh.vertices:
        distance = tree.find(vertex.co)[2]
        if distance == 0 or distance < max(abs(value) for value in vertex.co) * 2**-22:
            vertices.add(vertex.index)
    return {face.index for face in mesh.polygons
            if vertices.intersection(face.vertices)}


def separate_seam_render_detail(ob, seam_meshes, name):
    """Copy seam-adjacent render faces without changing positions or flags."""
    selected = seam_adjacent_face_indices(ob.data, seam_meshes)
    if not selected:
        return None
    detail = ob.copy()
    detail.data = ob.data.copy()
    detail.name = name
    detail.nwo.proxy_instance = False
    detail.data.nwo.mesh_type = '_connected_geometry_mesh_type_poop'
    for target, remove_selected in ((ob, True), (detail, False)):
        mesh = target.data
        preserve_normals = mesh.has_custom_normals
        bm = bmesh.new()
        try:
            bm.from_mesh(mesh)
            bm.faces.index_update()
            if preserve_normals:
                utils.save_loop_normals(bm, mesh)
            bmesh.ops.delete(bm, geom=[face for face in bm.faces
                                      if (face.index in selected) == remove_selected],
                             context='FACES')
            bm.to_mesh(mesh)
        finally:
            bm.free()
        if preserve_normals:
            utils.apply_loop_normals(mesh)
        utils.calc_face_prop_counts(mesh)
    return detail

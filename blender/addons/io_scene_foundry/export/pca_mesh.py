"""Read a triangulated PCA pose without changing evaluated shape-key data."""
from contextlib import contextmanager
import bmesh
import bpy


@contextmanager
def pca_sample_mesh(ob, depsgraph, quad_method, ngon_method, *, reference_positions=None, reference_indices=None):
    evaluated = ob.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    triangulated = None
    try:
        if reference_positions is not None and len(mesh.vertices) != len(reference_positions):
            raise ValueError(f'PCA mesh {ob.name!r} changes vertex count between its reference mesh and animation')
        if any(p.loop_total != 3 for p in mesh.polygons):
            bm = bmesh.new()
            try:
                bm.from_mesh(mesh)
                # Beauty/shortest-diagonal triangulation is pose-dependent.
                # Choose diagonals in the same coordinates as the reference
                # mesh, then restore this frame before calculating normals.
                if reference_positions is not None:
                    animated_positions = [v.co.copy() for v in bm.verts]
                    for vertex, position in zip(bm.verts, reference_positions):
                        vertex.co = position
                    bm.normal_update()
                bmesh.ops.triangulate(bm, faces=bm.faces, quad_method=quad_method, ngon_method=ngon_method)
                if reference_positions is not None:
                    for vertex, position in zip(bm.verts, animated_positions):
                        vertex.co = position
                    bm.normal_update()
                # Writing back into the evaluated mesh also writes its shape-key
                # layers. Blender then accumulates those changes on later poses.
                # A fresh mesh has no shape-key datablock to modify.
                triangulated = bpy.data.meshes.new('Foundry PCA sample')
                bm.to_mesh(triangulated)
                mesh = triangulated
            finally:
                bm.free()
        if reference_indices is not None:
            indices = [loop.vertex_index for loop in mesh.loops]
            if len(indices) != len(reference_indices) or any(a != b for a, b in zip(indices, reference_indices)):
                raise ValueError(
                    f'PCA mesh {ob.name!r} changes triangle topology or corner order during animation. '
                    'Apply topology-changing modifiers in the reference pose before exporting PCA.')
        yield mesh
    finally:
        if triangulated is not None:
            bpy.data.meshes.remove(triangulated)
        evaluated.to_mesh_clear()

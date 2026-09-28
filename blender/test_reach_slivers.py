"""Blender --background --factory-startup --python this_file."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import test_reach_geometry as h
import bpy
import bmesh
import numpy as np

from io_scene_foundry.tags.reach_geometry import (
    preserve_two_sided_sealers, recover_mapped_collision, retriangulate_render_slivers,
    repair_collision_triangulation)


def make_patch(seam=False):
    mesh = bpy.data.meshes.new('sliver_patch')
    mesh.from_pydata([(0, 0, 0), (2, 0, 0), (1, .000001, 0), (1, -1, 0)],
                     [], [(0, 1, 2), (1, 0, 3)])
    mesh.materials.append(bpy.data.materials.new('surface'))
    uv = mesh.uv_layers.new()
    for face in mesh.polygons:
        for index in face.loop_indices:
            co = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = (co.x + (2 if seam and face.index == 0 else 0), co.y)
    mesh.normals_split_custom_set([(0, 0, 1)] * len(mesh.loops))
    return mesh


class ReachSliverTests(unittest.TestCase):
    def test_helper_triangulation_preserves_boundary_and_visible_faces(self):
        mesh = make_patch(seam=True)
        h.utils.add_face_prop(mesh, 'face_mode').face_mode = 'collision_only'
        points = {tuple(v.co) for v in mesh.vertices}
        boundary = h.solid_edge_counts(mesh)
        self.assertEqual(repair_collision_triangulation(mesh, .001), 1)
        self.assertEqual(len(mesh.polygons), 2, 'helper UV seams must not retain overlapping special faces')
        self.assertEqual({tuple(v.co) for v in mesh.vertices}, points)
        self.assertEqual(h.solid_edge_counts(mesh), boundary)
        self.assertTrue(all(f.area > .1 for f in mesh.polygons))
        self.assertEqual(repair_collision_triangulation(mesh, .001), 0)
        visible = make_patch()
        self.assertEqual(repair_collision_triangulation(visible, .001), 0)

    def test_large_helper_triangle_repairs_float_normal_degeneracy(self):
        mesh = bpy.data.meshes.new('long_seam')
        mesh.from_pydata([(0, -14000, 250), (0, -750, -90),
                          (0, -700, -90), (0, -100, 250)], [], [(0, 1, 2), (0, 2, 3)])
        mesh.materials.append(bpy.data.materials.new('+seam'))
        h.utils.add_face_prop(mesh, 'face_mode').face_mode = 'collision_only'
        boundary = h.solid_edge_counts(mesh)
        points = {tuple(v.co) for v in mesh.vertices}
        self.assertEqual(repair_collision_triangulation(mesh, .000762), 1)
        self.assertEqual(h.solid_edge_counts(mesh), boundary)
        self.assertEqual({tuple(v.co) for v in mesh.vertices}, points)
        self.assertEqual(repair_collision_triangulation(mesh, .000762), 0)

    def test_mapped_polygon_keeps_missing_half_and_uses_all_clusters(self):
        material = bpy.data.materials.new('mapped_surface')

        def mesh(name, faces):
            result = bpy.data.meshes.new(name)
            result.from_pydata([(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)], [], faces)
            result.materials.append(material)
            return result

        a, b = mesh('cluster_a', [(0, 1, 2)]), mesh('cluster_b', [(0, 2, 3)])
        collision = mesh('collision', [(0, 1, 2, 3)])
        h.utils.add_face_prop(collision, 'slip_surface')
        self.assertEqual(recover_mapped_collision(collision, [a], .001), 1)
        self.assertAlmostEqual(sum(p.area for p in collision.polygons), 2)
        self.assertEqual(len(a.polygons), 1)
        slip = next(p for p in collision.nwo.face_props if p.type == 'slip_surface')
        self.assertTrue(all(v.value for v in collision.attributes[slip.attribute_name].data))
        collision = mesh('collision_complete', [(0, 1, 2, 3)])
        self.assertEqual(recover_mapped_collision(collision, [a, b], .001), 0)
        self.assertEqual(len(collision.polygons), 0)
        # Reach mappings can span a material boundary; geometric coverage is
        # still complete and must not produce overlapping collision.
        b.materials[0] = bpy.data.materials.new('other_render_material')
        collision = mesh('collision_material_boundary', [(0, 1, 2, 3)])
        self.assertEqual(recover_mapped_collision(collision, [a, b], .001), 0)
        self.assertEqual(len(collision.polygons), 0)

    def test_mapped_remainder_cannot_attach_to_an_already_closed_edge(self):
        material = bpy.data.materials.new('closed_surface')
        render = bpy.data.meshes.new('closed_boundary')
        render.from_pydata([(0, 0, 0), (2, 0, 0), (2, 2, 0), (1, 1, 2)],
                           [], [(0, 1, 2), (0, 2, 3)])
        collision = bpy.data.meshes.new('nonmatching_compiled_plane')
        collision.from_pydata([(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)],
                              [], [(0, 1, 2, 3)])
        for mesh in (render, collision):
            mesh.materials.append(material)
        self.assertEqual(recover_mapped_collision(collision, [render], .001), 0)
        self.assertEqual(len(collision.polygons), 0)

    def test_collision_join_without_uvs_preserves_special_flags(self):
        objects = []
        for i in range(2):
            mesh = bpy.data.meshes.new('collision_without_uvs')
            mesh.from_pydata([(i*2, 0, 0), (i*2+1, 0, 0), (i*2, 1, 0)], [], [(0, 1, 2)])
            mesh.materials.append(bpy.data.materials.new('+seamsealer'))
            h.utils.add_face_prop(mesh, 'face_sides')
            objects.append(bpy.data.objects.new('collision', mesh))
        result = h.utils.join_objects(objects, cleanup_geometry=False, preserve_special_faces=True)
        self.assertEqual(len(result.data.polygons), 2)
        prop = next(p for p in result.data.nwo.face_props if p.type == 'face_sides')
        self.assertEqual([v.value for v in result.data.attributes[prop.attribute_name].data], [True, True])

    def test_diagonal_changes_preserve_vertices_uvs_normals_and_properties(self):
        mesh = make_patch()
        h.utils.add_face_prop(mesh, 'slip_surface')
        positions = {tuple(v.co) for v in mesh.vertices}
        self.assertEqual(retriangulate_render_slivers(mesh, .001), 1)
        self.assertEqual(positions, {tuple(v.co) for v in mesh.vertices})
        self.assertEqual(len(mesh.polygons), 2)
        self.assertGreater(min(f.area for f in mesh.polygons), .49)
        for loop in mesh.loops:
            np.testing.assert_allclose(mesh.uv_layers[0].data[loop.index].uv,
                                       mesh.vertices[loop.vertex_index].co[:2])
        np.testing.assert_allclose([n.vector[:] for n in mesh.corner_normals], [(0, 0, 1)] * 6)
        self.assertTrue(all(v.value for v in mesh.attributes[mesh.nwo.face_props[0].attribute_name].data))
        self.assertEqual(retriangulate_render_slivers(mesh, .001), 0)

    def test_uv_seam_keeps_visible_triangles_and_separates_collision(self):
        mesh = make_patch(seam=True)
        original = [(tuple(mesh.vertices[l.vertex_index].co), tuple(mesh.uv_layers[0].data[l.index].uv))
                    for l in mesh.loops]
        self.assertEqual(retriangulate_render_slivers(mesh, .001), 1)
        h.weld_classic_vertices(mesh)
        self.assertEqual(len(mesh.polygons), 4)
        render = next(p for p in mesh.nwo.face_props if p.face_mode == 'render_only')
        collision = next(p for p in mesh.nwo.face_props if p.face_mode == 'collision_only')
        kept = [f for f in mesh.polygons if mesh.attributes[render.attribute_name].data[f.index].value]
        self.assertEqual(original, [(tuple(mesh.vertices[mesh.loops[i].vertex_index].co),
                                     tuple(mesh.uv_layers[0].data[i].uv))
                                    for f in kept for i in f.loop_indices])
        self.assertEqual(sum(v.value for v in mesh.attributes[collision.attribute_name].data), 2)
        self.assertEqual(h.solid_edge_counts(mesh), (4, 0))
        self.assertEqual(retriangulate_render_slivers(mesh, .001), 0)

    def test_material_and_collision_property_boundaries_are_not_crossed(self):
        for material in (False, True):
            with self.subTest(material=material):
                mesh = make_patch()
                if material:
                    mesh.materials.append(bpy.data.materials.new('other'))
                    mesh.polygons[1].material_index = 1
                else:
                    h.utils.add_face_prop(mesh, 'slip_surface', [1, 0])
                self.assertEqual(retriangulate_render_slivers(mesh, .001), 0)
                self.assertEqual(len(mesh.polygons), 2)

    def test_thin_closed_volume_and_render_only_faces_are_not_repaired(self):
        mesh = bpy.data.meshes.new('thin_volume')
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, .000001)],
                         [], [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)])
        self.assertEqual(retriangulate_render_slivers(mesh, .001), 0)
        mesh = make_patch()
        h.utils.add_face_prop(mesh, 'face_mode', [1, 0]).face_mode = 'render_only'
        self.assertEqual(retriangulate_render_slivers(mesh, .001), 0)

    def test_backtracking_sliver_keeps_render_and_recovers_collision_boundary(self):
        mesh = bpy.data.meshes.new('backtracking')
        mesh.from_pydata([(0, 0, 0), (2, 0, 0), (2, .005, 0), (.01, 0, 0), (0, -1, 0)],
                         [], [(0, 1, 2), (2, 3, 0), (1, 0, 4)])
        self.assertEqual(retriangulate_render_slivers(mesh, .0001), 1)
        h.weld_classic_vertices(mesh)
        self.assertEqual(len(mesh.polygons), 5)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        self.assertEqual(h.solid_edge_counts(mesh), (5, 0))
        collision = next(p for p in mesh.nwo.face_props if p.face_mode == 'collision_only')
        self.assertTrue(all(f.area > .001 for f in mesh.polygons
                            if mesh.attributes[collision.attribute_name].data[f.index].value))

    def test_special_material_two_sided_flags_survive_reach_cleanup(self):
        mesh = make_patch()
        mesh.materials[0].name = '+seamsealer'
        h.utils.add_face_prop(mesh, 'face_sides', [1, 0])
        h.utils.consolidate_face_attributes(mesh, preserve_special_faces=True)
        prop = next(p for p in mesh.nwo.face_props if p.type == 'face_sides')
        self.assertEqual([v.value for v in mesh.attributes[prop.attribute_name].data], [True, False])
        self.assertEqual(preserve_two_sided_sealers(mesh), 1)
        self.assertFalse(mesh.materials[mesh.polygons[0].material_index].name.startswith('+'))
        self.assertTrue(mesh.materials[mesh.polygons[1].material_index].name.startswith('+'))
        self.assertTrue(any(p.face_mode == 'collision_only' for p in mesh.nwo.face_props))
        self.assertTrue(any(p.type == 'global_material' and p.global_material == 'default'
                            for p in mesh.nwo.face_props))
        self.assertEqual(preserve_two_sided_sealers(mesh), 0)


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('Reach sliver regression tests failed')

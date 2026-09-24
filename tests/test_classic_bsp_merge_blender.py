"""Run with Blender --background --python-exit-code 1 --python this_file."""
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ADDONS = Path(__file__).resolve().parents[1] / 'blender/addons'
sys.path.insert(0, str(ADDONS))
_wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (ADDONS / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as wheel:
        wheel.extractall(_wheels.name)
sys.path.insert(0, _wheels.name)

import bpy
from mathutils import Matrix
from io_scene_foundry import props, utils
from io_scene_foundry.tags.classic_geometry import merge_classic_surfaces
from io_scene_foundry.tags.scenario_structure_bsp import ScenarioStructureBspTag

props.register()


def make_mesh(points, faces):
    mesh = bpy.data.meshes.new('merge_test')
    mesh.from_pydata(points, [], faces)
    uv = mesh.uv_layers.new(name='UVMap0')
    lighting = mesh.uv_layers.new(name='lighting')
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        uv.data[loop.index].uv = co.xy
        lighting.data[loop.index].uv = co.xy * 0.25
    mesh.materials.append(bpy.data.materials.get('test') or bpy.data.materials.new('test'))
    mesh.normals_split_custom_set([(0, 0, 1)] * len(mesh.loops))
    return mesh


SQUARE = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]


def mode_faces(mesh, mode):
    result = set()
    for prop in mesh.nwo.face_props:
        if prop.type == 'face_mode' and prop.face_mode == mode:
            attribute = mesh.attributes[prop.attribute_name]
            result.update(i for i, value in enumerate(attribute.data) if value.value)
    return result


def area(mesh, indices=None):
    return sum(face.area for face in mesh.polygons if indices is None or face.index in indices)


class ClassicMergeTests(unittest.TestCase):
    def setUp(self):
        self.project_patch = patch.object(utils, 'get_project', return_value=None)
        self.project_patch.start()
        self.meshes_before = set(bpy.data.meshes)
        self.objects_before = set(bpy.data.objects)

    def tearDown(self):
        for ob in set(bpy.data.objects) - self.objects_before:
            bpy.data.objects.remove(ob, do_unlink=True)
        for mesh in set(bpy.data.meshes) - self.meshes_before:
            bpy.data.meshes.remove(mesh)
        self.project_patch.stop()

    def test_crossing_diagonals_preserve_render_topology_uvs_and_normals(self):
        render = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
        collision = make_mesh(SQUARE, [(0, 1, 3), (1, 2, 3)])
        original_uvs = [tuple(uv.uv) for uv in render.uv_layers[0].data]
        merge_classic_surfaces(render, collision, 0.00005)
        self.assertEqual(len(render.polygons), 2)
        self.assertEqual(len(collision.polygons), 0)
        self.assertEqual(len(collision.vertices), 0)
        self.assertFalse(mode_faces(render, 'render_only'))
        self.assertEqual([tuple(uv.uv) for uv in render.uv_layers[0].data], original_uvs)
        for normal in render.corner_normals:
            self.assertAlmostEqual(normal.vector.z, 1)

    def test_subdivided_collision_and_large_render_triangle(self):
        points = [(0, 0, 0), (8, 0, 0), (0, 8, 0)]
        render = make_mesh(points, [(0, 1, 2)])
        collision = make_mesh(points + [(4, 0, 0), (4, 4, 0), (0, 4, 0)],
                              [(0, 3, 5), (3, 1, 4), (5, 4, 2), (3, 4, 5)])
        merge_classic_surfaces(render, collision, 0.00005)
        self.assertFalse(mode_faces(render, 'render_only'))
        self.assertEqual(len(render.polygons), 1)
        self.assertEqual(len(collision.polygons), 0)

    def test_warped_patch_with_opposite_diagonals_and_vertex_rounding(self):
        points = [(0, 0, 0), (2, 0, 0), (2, 2, 0.25), (0, 2, 0)]
        render = make_mesh(points, [(0, 1, 2), (0, 2, 3)])
        # The corner correspondence identifies the original warped polygon;
        # neither collision triangle lies on either render triangle's plane.
        collision = make_mesh([(x + 0.00001, y, z) for x, y, z in points],
                              [(0, 1, 3), (1, 2, 3)])
        original = [tuple(v.co) for v in render.vertices]
        original_uvs = [tuple(uv.uv) for uv in render.uv_layers[0].data]
        merge_classic_surfaces(render, collision, 0.00005)
        self.assertFalse(mode_faces(render, 'render_only'))
        self.assertEqual(len(render.polygons), 2)
        self.assertEqual(len(collision.polygons), 0)
        self.assertEqual([tuple(v.co) for v in render.vertices], original)
        self.assertEqual([tuple(uv.uv) for uv in render.uv_layers[0].data], original_uvs)

    def test_shared_border_does_not_merge_raised_interior_geometry(self):
        render = make_mesh(SQUARE + [(1, 1, 0.25)],
                           [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)])
        collision = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
        merge_classic_surfaces(render, collision, 0.00005)
        self.assertEqual(len(mode_faces(render, 'render_only')), 4)
        self.assertEqual(len(collision.polygons), 2)

    def test_matching_closed_shell_is_not_a_shared_patch(self):
        points = [(0, 0, 0), (2, 0, 0), (0, 2, 0), (0, 0, 2)]
        render = make_mesh(points, [(0, 1, 2)])
        collision = make_mesh(points, [(0, 1, 3), (1, 2, 3), (2, 0, 3)])
        merge_classic_surfaces(render, collision, 0.00005)
        self.assertEqual(len(mode_faces(render, 'render_only')), 1)
        self.assertEqual(len(collision.polygons), 3)

    def test_partial_coverage_splits_only_boundary_and_interpolates_data(self):
        render = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
        collision = make_mesh([(1, 0, 0), (3, 0, 0), (3, 2, 0), (1, 2, 0)],
                              [(0, 1, 2), (0, 2, 3)])
        merge_classic_surfaces(render, collision, 0.00005)
        self.assertAlmostEqual(area(render), 4)
        self.assertAlmostEqual(area(render, mode_faces(render, 'render_only')), 2)
        self.assertAlmostEqual(area(collision), 2)
        for vertex in collision.vertices:
            self.assertGreaterEqual(vertex.co.x, 2 - 1e-6)
        for loop in render.loops:
            co = render.vertices[loop.vertex_index].co
            uv = render.uv_layers['UVMap0'].data[loop.index].uv
            lighting = render.uv_layers['lighting'].data[loop.index].uv
            self.assertLess((co.xy - uv).length, 1e-5)
            self.assertLess((co.xy * 0.25 - lighting).length, 1e-5)
        for normal in render.corner_normals:
            self.assertAlmostEqual(normal.vector.z, 1)

    def test_nearby_parallel_and_crossing_planes_remain_distinct(self):
        for points in (
            [(x, y, 0.001) for x, y, z in SQUARE],
            [(x, y, (x - 1) * 0.001) for x, y, z in SQUARE],
        ):
            render = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
            collision = make_mesh(points, [(0, 1, 2), (0, 2, 3)])
            merge_classic_surfaces(render, collision, 0.00005)
            self.assertEqual(len(mode_faces(render, 'render_only')), 2)
            self.assertEqual(len(collision.polygons), 2)

    def test_special_collision_helpers_are_preserved(self):
        render = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
        collision = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
        collision.materials[0] = bpy.data.materials.new('+ladder test')
        merge_classic_surfaces(render, collision, 0.00005)
        self.assertEqual(len(collision.polygons), 2)
        self.assertEqual(len(mode_faces(render, 'render_only')), 2)

    def test_compiler_rounding_on_thin_triangles(self):
        # A tiny vertex displacement changes a narrow triangle's normal much
        # more than its surface position. Plane distance must control the match.
        for displacement, should_match in ((0.007, True), (0.03, False)):
            render = make_mesh([(0, 0, 0), (100, 0, 0), (0, 0.2, 0)], [(0, 1, 2)])
            collision = make_mesh([(0, 0, 0), (100, 0, 0), (0, 0.2, displacement)], [(0, 1, 2)])
            merge_classic_surfaces(render, collision, 0.025)
            self.assertEqual(len(collision.polygons), 0 if should_match else 1)
            self.assertEqual(bool(mode_faces(render, 'render_only')), not should_match)

    def test_compiler_rounding_on_thin_triangles(self):
        # A tiny vertex displacement changes a narrow triangle's normal much
        # more than its surface position. Plane distance must control the match.
        for displacement, should_match in ((0.007, True), (0.03, False)):
            render = make_mesh([(0, 0, 0), (100, 0, 0), (0, 0.2, 0)], [(0, 1, 2)])
            collision = make_mesh([(0, 0, 0), (100, 0, 0), (0, 0.2, displacement)], [(0, 1, 2)])
            merge_classic_surfaces(render, collision, 0.025)
            self.assertEqual(len(collision.polygons), 0 if should_match else 1)
            self.assertEqual(bool(mode_faces(render, 'render_only')), not should_match)

    def test_reversed_winding_and_tiny_geometry(self):
        render = make_mesh([(x * 0.001, y * 0.001, z) for x, y, z in SQUARE],
                           [(0, 1, 2), (0, 2, 3)])
        collision = make_mesh([(x * 0.001, y * 0.001, z) for x, y, z in SQUARE],
                              [(3, 1, 0), (3, 2, 1)])
        merge_classic_surfaces(render, collision, 0.000001)
        self.assertFalse(mode_faces(render, 'render_only'))
        self.assertEqual(len(collision.polygons), 0)

    def test_join_does_not_weld_away_thin_geometry(self):
        tag = ScenarioStructureBspTag.__new__(ScenarioStructureBspTag)
        tag.tag_path = SimpleNamespace(ShortName='thin')
        objects = []
        points = [(0, 0, 0), (0.002, 0, 0), (0, 0.002, 0)]
        for kind in ('structure', 'collision'):
            mesh = make_mesh(points, [(0, 1, 2)])
            mesh.nwo.mesh_type = '_connected_geometry_mesh_type_' + kind
            ob = bpy.data.objects.new(kind, mesh)
            bpy.context.scene.collection.objects.link(ob)
            objects.append(ob)
        merged, = tag._merge_classic_structure_geometry(objects, False)
        self.assertEqual(len(merged.data.polygons), 1)
        self.assertAlmostEqual(area(merged.data), 0.000002)

    def test_overlapping_cutters_do_not_hide_holes(self):
        render = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
        collision = make_mesh([(0, 0, 0), (1, 0, 0), (1, 2, 0), (0, 2, 0)],
                              [(0, 1, 2), (0, 2, 3), (0, 1, 2), (0, 2, 3)])
        merge_classic_surfaces(render, collision, 0.00005)
        self.assertAlmostEqual(area(render, mode_faces(render, 'render_only')), 2)
        self.assertEqual(len(collision.polygons), 0)

    def test_import_merge_bakes_transforms_and_respects_skip(self):
        tag = ScenarioStructureBspTag.__new__(ScenarioStructureBspTag)
        tag.tag_path = SimpleNamespace(ShortName='test')
        for scale in (1, 0.03048):
            objects = []
            for kind, points, transform in (
                ('structure', SQUARE, Matrix.Translation((10, 0, 0))),
                ('collision', [(x + 10, y, z) for x, y, z in SQUARE], Matrix.Identity(4)),
            ):
                mesh = make_mesh(points, [(0, 1, 2), (0, 2, 3)])
                mesh.nwo.mesh_type = '_connected_geometry_mesh_type_' + kind
                ob = bpy.data.objects.new(kind, mesh)
                bpy.context.scene.collection.objects.link(ob)
                ob.matrix_world = Matrix.Scale(scale, 4) @ transform
                objects.append(ob)
            self.assertEqual(tag._merge_classic_structure_geometry(objects, True), objects)
            with patch('io_scene_foundry.import_transform.scale_factor', return_value=scale):
                merged, = tag._merge_classic_structure_geometry(objects, False)
            self.assertEqual(len(merged.data.polygons), 2)
            self.assertFalse(mode_faces(merged.data, 'render_only'))
            self.assertAlmostEqual(min(v.co.x for v in merged.data.vertices), 10 * scale, places=5)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ClassicMergeTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)

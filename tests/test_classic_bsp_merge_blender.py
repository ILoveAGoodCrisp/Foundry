"""Run with Blender --background --python-exit-code 1 --python this_file."""
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
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
            self.assertEqual(tag._merge_classic_structure_geometry(
                objects, True, merge_render_collision=False), objects)
            with patch('io_scene_foundry.import_transform.scale_factor', return_value=scale):
                merged, = tag._merge_classic_structure_geometry(objects, False)
            self.assertEqual(len(merged.data.polygons), 2)
            self.assertFalse(mode_faces(merged.data, 'render_only'))
            self.assertAlmostEqual(min(v.co.x for v in merged.data.vertices), 10 * scale, places=5)

    def test_cluster_join_and_surface_merge_are_independent(self):
        tag = ScenarioStructureBspTag.__new__(ScenarioStructureBspTag)
        tag.tag_path = SimpleNamespace(ShortName='test')
        for merge in (False, True):
            for skip in (False, True):
                for extra_collision in (False, True):
                    with self.subTest(merge=merge, skip=skip, extra_collision=extra_collision):
                        objects = []
                        for index, face in enumerate(((0, 1, 2), (0, 2, 3))):
                            mesh = make_mesh([SQUARE[i] for i in face], [(0, 1, 2)])
                            mesh.nwo.mesh_type = '_connected_geometry_mesh_type_structure'
                            ob = bpy.data.objects.new(f'cluster_{index}', mesh)
                            ob['cluster_test'] = index
                            bpy.context.scene.collection.objects.link(ob)
                            objects.append(ob)
                        clusters = list(objects)
                        cluster_names = [ob.name for ob in clusters]
                        original_uvs = [[tuple(uv.uv) for uv in ob.data.uv_layers[0].data] for ob in clusters]
                        points = SQUARE + ([(5, 0, 0), (6, 0, 0), (5, 1, 0)] if extra_collision else [])
                        faces = [(0, 1, 2, 3)] + ([(4, 5, 6)] if extra_collision else [])
                        collision = make_mesh(points, faces)
                        collision.nwo.mesh_type = '_connected_geometry_mesh_type_collision'
                        ob = bpy.data.objects.new('collision', collision)
                        bpy.context.scene.collection.objects.link(ob)
                        objects.append(ob)
                        result = tag._merge_classic_structure_geometry(
                            objects, skip, merge_render_collision=merge)
                        if merge:
                            self.assertEqual(sum(len(ob.data.polygons) for ob in result), 2 + extra_collision)
                            self.assertFalse(any(mode_faces(ob.data, 'render_only') for ob in result))
                            self.assertEqual(sum(len(mode_faces(ob.data, 'collision_only')) for ob in result), int(extra_collision))
                            self.assertEqual(len(result), (2 + extra_collision) if skip else 1)
                        else:
                            self.assertEqual(len(result), 3 if skip else 2)
                            self.assertEqual(len(collision.polygons), 1 + extra_collision)
                            self.assertFalse(any(ob.data.nwo.face_props for ob in result))
                        if skip:
                            for index, cluster in enumerate(clusters):
                                self.assertIn(cluster, result)
                                self.assertEqual(cluster.name, cluster_names[index])
                                self.assertEqual(cluster['cluster_test'], index)
                                self.assertEqual(len(cluster.data.vertices), 3)
                                self.assertEqual([tuple(uv.uv) for uv in cluster.data.uv_layers[0].data], original_uvs[index])
                                self.assertTrue(all(n.vector.z > 0.999 for n in cluster.data.corner_normals))
                        self.assertFalse(any(a.name.startswith('classic_cluster_') for ob in result for a in ob.data.attributes))

    def test_surface_merge_option_in_both_importers_and_h1_ui(self):
        from io_scene_foundry.tools.importer import (
            IMPORT_TEMPLATE_VALUES, NWO_Import, NWO_OT_ImportFromDrop,
            draw_scenario_import_sections,
        )
        for operator_type in (NWO_Import, NWO_OT_ImportFromDrop):
            prop = operator_type.__annotations__['tag_bsp_merge_render_collision']
            self.assertTrue(prop.keywords['default'])
        self.assertTrue(all(values['tag_bsp_merge_render_collision'] for values in IMPORT_TEMPLATE_VALUES.values()))
        for game in ('halo1', 'halo2', 'halo3'):
            layout = MagicMock()
            operator = SimpleNamespace(tag_bsp_render_only=False, tag_bsp_import_geometry=True)
            with patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)):
                draw_scenario_import_sections(operator, layout, False, show_template=False)
            properties = [call.args[1] for call in layout.mock_calls if call[0].endswith('.prop')]
            self.assertIn('tag_bsp_skip_structure_merge', properties)
            self.assertEqual('tag_bsp_merge_render_collision' in properties, game == 'halo1')

    def test_separate_clusters_preserve_ownership_when_faces_split(self):
        tag = ScenarioStructureBspTag.__new__(ScenarioStructureBspTag)
        tag.tag_path = SimpleNamespace(ShortName='split')
        objects = []
        for kind, points, faces in (
            ('structure', [SQUARE[i] for i in (0, 1, 2)], [(0, 1, 2)]),
            ('structure', [SQUARE[i] for i in (0, 2, 3)], [(0, 1, 2)]),
            ('collision', [(0, 0, 0), (1, 0, 0), (1, 2, 0), (0, 2, 0)], [(0, 1, 2, 3)]),
        ):
            mesh = make_mesh(points, faces)
            mesh.nwo.mesh_type = '_connected_geometry_mesh_type_' + kind
            ob = bpy.data.objects.new(kind, mesh)
            bpy.context.scene.collection.objects.link(ob)
            objects.append(ob)
        first, second = objects[:2]
        result = tag._merge_classic_structure_geometry(objects, True)
        self.assertEqual(result, [first, second])
        for ob in result:
            self.assertAlmostEqual(area(ob.data), 2)
            for loop in ob.data.loops:
                co = ob.data.vertices[loop.vertex_index].co
                uv = ob.data.uv_layers[0].data[loop.index].uv
                self.assertAlmostEqual(uv.x, co.x)
                self.assertAlmostEqual(uv.y, co.y)
        self.assertAlmostEqual(area(first.data, mode_faces(first.data, 'render_only')), 1.5)
        self.assertAlmostEqual(area(second.data, mode_faces(second.data, 'render_only')), 0.5)

    def test_classic_emissive_face_props_follow_material_slots(self):
        mesh = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
        mesh.materials.append(bpy.data.materials.new('emissive'))
        mesh.polygons[1].material_index = 1

        ScenarioStructureBspTag._apply_classic_emissives(
            mesh, {1: (4.5, (0.25, 0.5, 0.75))})

        props = [prop for prop in mesh.nwo.face_props if prop.type == 'emissive']
        self.assertEqual(len(props), 1)
        prop = props[0]
        self.assertAlmostEqual(prop.material_lighting_emissive_power, 4.5)
        self.assertEqual(tuple(prop.material_lighting_emissive_color), (0.25, 0.5, 0.75))
        attribute = mesh.attributes[prop.attribute_name]
        self.assertEqual([value.value for value in attribute.data], [False, True])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ClassicMergeTests)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)

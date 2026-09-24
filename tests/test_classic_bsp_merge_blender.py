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
    def halo2_mapping_fixture(self):
        class Fields(dict):
            def field(self, name):
                return self[name]
        points = [(0., 0., 0.), (1., 0., 0.), (0., 1., 0.),
                  (2., 0., 0.), (3., 0., 0.), (2., 1., 0.)]
        mesh = SimpleNamespace(index=0, positions=points, indices=(0, 1, 2, 3, 4, 5))
        section = {
            'raw vertices': [{'position': SimpleNamespace(to_array=lambda p=p: p)} for p in points],
            'strip indices': [{'index': i} for i in (0, 1, 2, 3, 4, 5)],
            'parts': [Fields({'strip start index': 0, 'strip length': 6,
                              'flags': SimpleNamespace(get_flag=lambda name: True)})],
        }
        record = SimpleNamespace(vertices=points, polygons=((0, 1, 2), (3, 4, 5)),
                                 surfaces=[SimpleNamespace(invalid=False), SimpleNamespace(invalid=False)])
        collision = {
            'leaves': [{'first bsp2d reference': 0, 'bsp2d reference count': 1}],
            'bsp3d nodes': [SimpleNamespace(raw_bytes=b'\x00' * 8) for _ in range(4)],
            'planes': [{'plane': SimpleNamespace(i=0, j=0, k=1, d=0)}],
            'bsp2d references': [{'plane': 0, 'bsp2d node': 0}],
            'bsp2d nodes': [{'left child': -32768, 'right child': -32767}],
        }
        owner = {
            'leaves': [{'cluster': 7, 'first surface reference index': 0, 'surface reference count': 2}],
            'surface references': [{'strip index': 3, 'lightmap triangle index': 99, 'bsp node index': 3}] * 2,
        }
        doc = SimpleNamespace(block=lambda owner, name: owner[name], value=lambda owner, name: owner[name],
                              _collision_bsp=lambda *args, **kwargs: record)
        return doc, owner, collision, {7: mesh}, {7: section}

    def test_halo2_references_resolve_nodes_leaves_and_strip_offsets(self):
        from io_scene_foundry.tags.halo2_geometry import surface_mappings
        doc, owner, collision, meshes, sections = self.halo2_mapping_fixture()
        _, mappings = surface_mappings(doc, owner, collision, meshes, sections)
        self.assertTrue(mappings[0].collision_only)
        # Node 3, strip offset 3, and lightmap triangle 99 are NOT surface IDs.
        self.assertEqual(mappings[1].direct_triangles, ((1, 7),))

    def test_halo2_unlinked_triangles_do_not_gain_collision_from_proximity(self):
        from io_scene_foundry.tags.halo2_geometry import surface_mappings
        doc, owner, collision, meshes, sections = self.halo2_mapping_fixture()
        owner['surface references'] = [{'strip index': 3, 'bsp node index': -1}] * 2
        _, mappings = surface_mappings(doc, owner, collision, meshes, sections)
        self.assertTrue(all(m.collision_only for m in mappings))

    def test_halo2_reference_validation(self):
        from io_scene_foundry.tags.halo2_geometry import surface_mappings
        args = self.halo2_mapping_fixture()
        args[1]['surface references'][0]['bsp node index'] = 100
        with self.assertRaisesRegex(ValueError, 'BSP3D node'):
            surface_mappings(*args)
        args = self.halo2_mapping_fixture()
        args[1]['leaves'][0]['surface reference count'] = 100
        with self.assertRaisesRegex(ValueError, 'surface reference range'):
            surface_mappings(*args)
        args = self.halo2_mapping_fixture()
        args[1]['surface references'][0]['strip index'] = 100
        with self.assertRaisesRegex(ValueError, 'strip offset'):
            surface_mappings(*args)

    def test_halo2_strip_reindex_skips_connectors(self):
        from io_scene_foundry.tags.halo2_geometry import _strip_faces
        doc, _, _, meshes, sections = self.halo2_mapping_fixture()
        section = sections[7]
        section['strip indices'] = [{'index': i} for i in (0, 1, 2, 2, 3, 3, 4, 5)]
        section['parts'][0]['strip length'] = 8
        section['parts'][0]['flags'] = SimpleNamespace(get_flag=lambda name: False)
        self.assertEqual(_strip_faces(doc, section, meshes[7]), {0: 0, 5: 1})

    def test_halo2_strip_offsets_are_unsigned(self):
        from io_scene_foundry.tags.halo2_geometry import _strip_faces
        doc, _, _, meshes, sections = self.halo2_mapping_fixture()
        section = sections[7]
        section['strip indices'] = [{'index': 0}] * 32768 + section['strip indices']
        section['parts'][0]['strip start index'] = -32768
        self.assertEqual(_strip_faces(doc, section, meshes[7]), {32768: 0, 32771: 1})

    def test_halo2_import_uses_h3_mapping_path_not_geometric_merge(self):
        from io_scene_foundry.tags.prefab import (
            StructureBspCollision, StructureBspCollisionSurface, StructureBspRenderMesh,
            StructureBspRenderPart, StructureBspSurfaceMapping,
        )
        render = StructureBspRenderMesh(
            0, tuple(SQUARE), ((0, 0), (1, 0), (1, 1), (0, 1)), ((0, 0, 1),) * 4,
            (), (), (), (), (0, 1, 2, 0, 2, 3), -1, (StructureBspRenderPart(0, 0, 6, 0),), None)
        surfaces = tuple(StructureBspCollisionSurface(
            i, -1, False, False, i == 0, i == 0, False, False, False) for i in range(2))
        collision = StructureBspCollision(tuple(SQUARE), surfaces, ((0, 2, 3), (0, 1, 2)))
        mappings = [StructureBspSurfaceMapping(0, (), ((1, 0),)), StructureBspSurfaceMapping(1, ())]
        tag = ScenarioStructureBspTag.__new__(ScenarioStructureBspTag)
        tag.game = 'halo2'
        tag.tag_path = SimpleNamespace(ShortName='mapped')
        tag._tag = SimpleNamespace(root=lambda: {})
        instances = [dict(object_index=i, name=name, rotation=(0, 0, 0, 1), translation=(0, 0, 0),
                          scale=1, mesh_type=kind, reference='')
                     for i, name, kind in ((0, 'cluster_0', 'render'), (1, '@CollideOnly', 'collision'))]
        for skip in (False, True):
            with self.subTest(skip=skip), patch.object(tag, 'classic_render_scene', return_value=(['test'], [''], [render, render], instances)), \
                    patch.object(tag, 'block', return_value=[]), \
                    patch('io_scene_foundry.tags.scenario_structure_bsp.halo2_bsp_mappings', return_value=[(collision, mappings, {0: 0}, True)]), \
                    patch('io_scene_foundry.tags.scenario_structure_bsp.merge_classic_surfaces', side_effect=AssertionError('H2 must use references')):
                objects, _ = tag._classic_render_objects(bpy.context.scene.collection, skip)
            self.assertEqual(len(objects), 2 if skip else 1)
            self.assertEqual(sum(len(ob.data.polygons) for ob in objects), 3)
            self.assertEqual(sum(len(mode_faces(ob.data, 'render_only')) for ob in objects), 1)
            self.assertEqual(sum(len(mode_faces(ob.data, 'collision_only')) for ob in objects), 1)
            self.assertEqual(sum(len(mode_faces(ob.data, 'breakable')) for ob in objects), 1)
            self.assertTrue(any(p.type == 'ladder' for ob in objects for p in ob.data.nwo.face_props))

    def test_join_preserves_face_flags_on_repeated_instances(self):
        mesh = make_mesh(SQUARE, [(0, 1, 2), (0, 2, 3)])
        utils.add_face_prop(mesh, 'face_mode', [0, 1]).face_mode = 'breakable'
        objects = []
        for i in range(3):
            ob = bpy.data.objects.new(f'instance_{i}', mesh.copy())
            bpy.context.scene.collection.objects.link(ob)
            objects.append(ob)
        joined = utils.join_objects(objects, cleanup_geometry=False)
        self.assertEqual(len(mode_faces(joined.data, 'breakable')), 3)

    def test_halo2_real_bsp_imports_when_fixture_root_is_set(self):
        import os
        from io_scene_foundry.tags.backend import TagDocument
        tags_root = os.environ.get('FOUNDRY_H2_TEST_TAGS')
        if not tags_root:
            self.skipTest('Set FOUNDRY_H2_TEST_TAGS to run Chiron Station and Zanzibar integration checks')
        for level in ('chironstation', 'zanzibar'):
            tag = ScenarioStructureBspTag.__new__(ScenarioStructureBspTag)
            TagDocument.__init__(tag, f'scenarios/multi/{level}/{level}.scenario_structure_bsp', tags_root=tags_root, game='halo2')
            tag.tag_path = tag.reference_from_path(tag.path)
            tag.tags_dir = str(tag.tags_root)
            tag.corinth = False
            with patch.object(tag, '_classic_shader_emissive', return_value=None), \
                    patch.object(utils, 'get_prefs', return_value=SimpleNamespace(update_materials_on_shader_path=False)), \
                    patch('io_scene_foundry.tags.scenario_structure_bsp.merge_classic_surfaces', side_effect=AssertionError('H2 must use references')):
                separate, _ = tag._classic_render_objects(bpy.context.scene.collection, True)
                counts = {mode: sum(len(mode_faces(ob.data, mode)) for ob in separate if ob.type == 'MESH')
                          for mode in ('render_only', 'collision_only', 'breakable')}
                faces = sum(len(ob.data.polygons) for ob in separate if ob.type == 'MESH')
                self.assertGreater(faces, 0)
                self.assertLess(counts['render_only'] + counts['collision_only'], faces)
                joined, _ = tag._classic_render_objects(bpy.context.scene.collection, False)
                self.assertEqual(sum(len(ob.data.polygons) for ob in joined if ob.type == 'MESH'), faces)
                for mode, count in counts.items():
                    self.assertEqual(sum(len(mode_faces(ob.data, mode)) for ob in joined if ob.type == 'MESH'), count)
                print(f'{level}: {faces} faces, {counts}')
            tag.__exit__(None, None, None)

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

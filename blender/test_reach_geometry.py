"""Blender --background --factory-startup --python this_file.

Optionally add -- --reach-bsp <absolute .scenario_structure_bsp path> to audit
real decoded clusters and instance meshes without changing the source tag.
"""
from collections import Counter
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import bpy
import numpy as np

addons = Path(__file__).parent / 'addons'
sys.path.insert(0, str(addons))
wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (addons / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as wheel:
        wheel.extractall(wheels.name)
sys.path.insert(0, wheels.name)
from io_scene_foundry import props, utils
from io_scene_foundry.tags.classic_geometry import weld_classic_vertices
from io_scene_foundry.tags.connected_geometry import Mesh
from io_scene_foundry.tags.prefab import StructureBspRenderMesh, StructureBspRenderPart
from io_scene_foundry.tags.scenario_structure_bsp import ScenarioStructureBspTag

utils.get_project = lambda *a, **k: SimpleNamespace(game='reach', corinth=False)
props.register()


def boundary_edges(mesh):
    counts = Counter(tuple(sorted((a, b))) for face in mesh.polygons
                     for a, b in zip(face.vertices, (*face.vertices[1:], face.vertices[0])))
    return sum(count == 1 for count in counts.values())


def record(index, triangles):
    points = tuple(point for triangle in triangles for point in triangle)
    return StructureBspRenderMesh(
        index=index, positions=points,
        texcoords=tuple((i / 20, i / 30) for i in range(len(points))),
        normals=tuple(((0, 0, 1) if i < 3 else (0, 1, 0)) for i in range(len(points))),
        node_indices=(), node_weights=(), lightmap_texcoords=(), vertex_colors=(),
        indices=tuple(range(len(points))), rigid_node_index=-1,
        parts=(StructureBspRenderPart(0, 0, len(points), 3),), water=None)


def import_records(records, *, skip_merge=False, instances=False):
    # Exercise the actual Reach BSP orchestration, substituting only tag data.
    tag = SimpleNamespace(game='reach', corinth=False,
                          tag_path=SimpleNamespace(ShortName='test', Filename='test.scenario_structure_bsp'))
    for name in ('collision_materials', 'emissive_materials', 'render_materials',
                 'portals', 'markers', 'environment_objects', 'cookie_cutters',
                 'surface_triangle_mappings', 'instances', 'instance_definitions'):
        setattr(tag, name, lambda: [])
    for name in ('structure_lighting_info', 'structure_collision', 'structure_meta_data'):
        setattr(tag, name, lambda: None)
    tag.cluster_mesh_indices = lambda: [] if instances else list(range(len(records)))
    tag.render_meshes = lambda definitions: records
    collection = bpy.data.collections.new('reach_test')
    bpy.context.scene.collection.children.link(collection)
    definition = SimpleNamespace(index=0, create=lambda *args: Mesh.from_native(
        records[0], [], False).create(None, None))
    if instances:
        tag.instance_definitions = lambda: [None]
    with patch('io_scene_foundry.tags.scenario_structure_bsp.InstanceDefinition.from_native',
               return_value=definition):
        return ScenarioStructureBspTag.to_blend_objects(
            tag, collection, False, lighting_info_path=Path(wheels.name) / 'missing',
            import_lights=False, skip_structure_merge=skip_merge)[0]


class ReachGeometryTests(unittest.TestCase):
    def setUp(self):
        bpy.context.scene.nwo.forward_direction = 'x'
        a, b, c, d = (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, .00001)
        self.triangles = [(a, c, b), (a, b, d), (a, d, c), (b, c, d)]

    def test_closed_thin_shell_survives_cluster_join_at_both_scales(self):
        for scale in ('blender', 'max'):
            with self.subTest(scale=scale):
                bpy.context.scene.nwo.scale = scale
                objects = import_records([record(0, self.triangles[:2]), record(1, self.triangles[2:])])
                mesh = objects[0].data
                self.assertEqual(len(mesh.polygons), 4)
                self.assertEqual(len(mesh.vertices), 4)
                self.assertEqual(boundary_edges(mesh), 0)

    def test_single_and_unmerged_clusters_are_welded(self):
        for skip in (False, True):
            with self.subTest(skip_merge=skip):
                objects = import_records([record(0, self.triangles)], skip_merge=skip)
                self.assertEqual(len(objects[0].data.polygons), 4)
                self.assertEqual(boundary_edges(objects[0].data), 0)

    def test_instance_definition_is_welded(self):
        objects = import_records([record(0, self.triangles)], instances=True)
        self.assertEqual(len(objects[0].data.polygons), 4)
        self.assertEqual(boundary_edges(objects[0].data), 0)

    def test_weld_preserves_corner_data_and_face_properties(self):
        raw = record(0, self.triangles)
        source = Mesh.from_native(raw, [], False).create(None, None)[0].data
        utils.add_face_prop(source, 'face_mode', [0, 1, 0, 1]).face_mode = 'collision_only'
        positions = [tuple(source.vertices[i].co) for face in source.polygons for i in face.vertices]
        uvs = [tuple(item.uv) for item in source.uv_layers[0].data]
        normals = [tuple(loop.normal) for loop in source.loops]
        attributes = {p.attribute_name: [v.value for v in source.attributes[p.attribute_name].data]
                      for p in source.nwo.face_props}
        weld_classic_vertices(source)
        self.assertEqual(positions, [tuple(source.vertices[i].co) for face in source.polygons for i in face.vertices])
        np.testing.assert_allclose(uvs, [tuple(item.uv) for item in source.uv_layers[0].data])
        np.testing.assert_allclose(normals, [tuple(loop.normal) for loop in source.loops], atol=1e-5)
        for name, values in attributes.items():
            self.assertEqual(values, [v.value for v in source.attributes[name].data])

    def test_stacked_faces_and_nearby_shells_remain_separate(self):
        # Same coordinates with distinct materials must not lose a surface.
        mesh = bpy.data.meshes.new('stacked')
        triangle = self.triangles[0]
        mesh.from_pydata(triangle * 2, [], [(0, 1, 2), (3, 4, 5)])
        mesh.materials.append(bpy.data.materials.new('front'))
        mesh.materials.append(bpy.data.materials.new('overlay'))
        mesh.polygons[1].material_index = 1
        self.assertEqual(weld_classic_vertices(mesh), 0)
        self.assertEqual(len(mesh.polygons), 2)
        shifted = [tuple((x, y, z + .00002) for x, y, z in tri) for tri in self.triangles]
        objects = import_records([record(0, self.triangles), record(1, shifted)])
        self.assertEqual(len(objects[0].data.polygons), 8)
        self.assertEqual(len(objects[0].data.vertices), 8)

    def test_spatial_edge_stitching_matches_original(self):
        # Several splits on one edge, plus points just inside/outside the
        # existing distance tolerance and distant unrelated geometry.
        mesh = bpy.data.meshes.new('junctions')
        mesh.from_pydata([(0, 0, 0), (10, 0, 0), (0, -1, 0),
                          (2, .004, 0), (5, 0, 0), (8, 0, 0),
                          (2, 1, 0), (8, 1, 0), (4, .02, 0),
                          (100, 100, 100), (101, 100, 100), (100, 101, 100)],
                         [], [(0, 1, 2), (3, 4, 6), (4, 5, 7), (9, 10, 11)])
        mesh.uv_layers.new()
        mesh.normals_split_custom_set([(0, 0, 1)] * len(mesh.loops))
        utils.add_face_prop(mesh, 'face_mode', [0, 1, 0, 0]).face_mode = 'collision_only'
        original = mesh.copy()
        utils.connect_verts_on_edge(original)
        utils.connect_verts_on_edge(mesh, spatial_search=True)

        def signature(result):
            return sorted(tuple(tuple(result.vertices[v].co) for v in f.vertices)
                          for f in result.polygons)

        self.assertEqual(signature(mesh), signature(original))
        self.assertEqual(len(mesh.polygons), 4)
        self.assertEqual(len(mesh.polygons[0].vertices), 6)
        for prop in original.nwo.face_props:
            self.assertEqual([v.value for v in original.attributes[prop.attribute_name].data],
                             [v.value for v in mesh.attributes[prop.attribute_name].data])


class WaterDecoderTests(unittest.TestCase):
    def test_water_uvs_across_tag_schemas(self):
        import blam_tags
        for game, dimensions in (('halo3_mcc', 3), ('haloreach_mcc', 2), ('halo4_mcc', 2)):
            with self.subTest(game=game):
                tag = blam_tags.TagFile.new(str(addons / 'io_scene_foundry/tags/definitions' /
                                                game / 'scenario_structure_bsp.json'))

                def field(path):
                    return tag.root().field_path('render geometry/' + path)

                def add(path):
                    return field(path).as_block().add()

                add('meshes')
                add('meshes[0]/parts')
                field('meshes[0]/parts[0]/part flags').set_flag('is water surface', True)
                field('meshes[0]/parts[0]/index count').set(3)
                add('meshes[0]/water indices start')
                add('per mesh temporary')
                pmt = 'per mesh temporary[0]/'
                add(pmt + 'raw water data')
                water = pmt + 'raw water data[0]/'
                for i in range(3):
                    add(pmt + 'raw vertices')
                    add(pmt + 'raw indices')
                    field(pmt + f'raw indices[{i}]/word').set(i)
                    add(water + 'raw water indices')
                    field(water + f'raw water indices[{i}]/word').set(i)
                    add(water + 'raw water vertices')
                    vertex = water + f'raw water vertices[{i}]/'
                    uv = (blam_tags.RealPoint2d(.25, .75) if dimensions == 2 else
                          blam_tags.RealPoint3d(.25, .75, .5))
                    field(vertex + 'base texcoord').set(uv)
                    if dimensions == 3:
                        field(vertex + 'local info').set(blam_tags.RealPoint3d(1, 2, 3))
                        field(vertex + 'water velocity').set(blam_tags.RealPoint3d(4, 5, 6))

                decoded = tag.sbsp_render_meshes([-1])[0]['water_data']
                self.assertIsNotNone(decoded)
                self.assertEqual(len(decoded['triangles']), 1)
                self.assertEqual(len(decoded['vertices']), 3)
                for local, velocity, uv in decoded['vertices']:
                    self.assertEqual(tuple(uv), (.25, .75, .5 if dimensions == 3 else 0.0))
                    self.assertEqual(tuple(local), (1, 2, 3) if dimensions == 3 else (0, 0, 0))
                    self.assertEqual(tuple(velocity), (4, 5, 6) if dimensions == 3 else (0, 0, 0))


def audit_tag(path):
    tags_root = next(parent for parent in path.parents if parent.name.lower() == 'tags')
    bpy.context.scene.nwo.scale = 'blender'
    with patch.object(utils, 'get_tags_path', return_value=str(tags_root)), \
            patch.object(utils, 'get_data_path', return_value=str(tags_root.parent / 'data')), \
            patch.object(utils, 'get_prefs', return_value=SimpleNamespace(update_materials_on_shader_path=False)):
        with ScenarioStructureBspTag(path=path) as tag:
            records = tag.render_meshes(tag.instance_definitions())
            cluster_indices = tag.cluster_mesh_indices()
            collection = bpy.data.collections.new('reach_full_import')
            bpy.context.scene.collection.children.link(collection)
            objects, _, _ = tag.to_blend_objects(
                collection, False, import_lights=False,
                lighting_info_path=Path(wheels.name) / 'missing')
            unique_meshes = {ob.data for ob in objects if ob.type == 'MESH'}
            print(f'REACH AUDIT full import: {len(unique_meshes)} unique meshes, '
                  f'{sum(len(mesh.polygons) for mesh in unique_meshes)} faces', flush=True)
    bpy.context.scene.nwo.scale = 'blender'
    total_before = total_after = faces = meshes = 0
    clusters = []
    for raw in records:
        for ob in Mesh.from_native(raw, [], False).create(None, None):
            before = len(ob.data.polygons)
            total_before += boundary_edges(ob.data)
            weld_classic_vertices(ob.data)
            total_after += boundary_edges(ob.data)
            assert len(ob.data.polygons) == before
            faces += before
            meshes += 1
            if raw.index in cluster_indices:
                clusters.append(ob)
    print(f'REACH AUDIT {path.name}: {meshes} meshes, {faces} faces retained; '
          f'boundary edges {total_before} -> {total_after}', flush=True)
    if clusters:
        before = sum(len(ob.data.polygons) for ob in clusters)
        joined = utils.join_objects(clusters, cleanup_geometry=False)
        weld_classic_vertices(joined.data)
        assert len(joined.data.polygons) == before
        print(f'REACH AUDIT joined clusters: {before} faces retained, '
              f'{boundary_edges(joined.data)} boundary edges', flush=True)


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('Reach geometry regression tests failed')
    if '--reach-bsp' in sys.argv:
        audit_tag(Path(sys.argv[sys.argv.index('--reach-bsp') + 1]))

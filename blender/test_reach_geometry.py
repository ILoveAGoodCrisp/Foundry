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
from io_scene_foundry.tags.classic_geometry import (
    align_collision_boundary, dissolve_collision_edge_slivers, weld_classic_vertices)
from io_scene_foundry.tags.connected_geometry import InstanceCollision, Mesh, Portal
from io_scene_foundry.tags.prefab import StructureBspPortal, StructureBspRenderMesh, StructureBspRenderPart
from io_scene_foundry.tags.scenario_structure_bsp import ScenarioStructureBspTag

utils.get_project = lambda *a, **k: SimpleNamespace(game='reach', corinth=False)
props.register()


def boundary_edges(mesh):
    counts = Counter(tuple(sorted((a, b))) for face in mesh.polygons
                     for a, b in zip(face.vertices, (*face.vertices[1:], face.vertices[0])))
    return sum(count == 1 for count in counts.values())


def solid_edge_counts(mesh):
    """Tool's closed-shell check excludes two-sided and render-only faces."""
    excluded = set()
    for prop in mesh.nwo.face_props:
        if (prop.type == 'face_sides' and prop.two_sided
                or prop.type == 'face_mode' and prop.face_mode == 'render_only'):
            attribute = mesh.attributes.get(prop.attribute_name)
            if attribute is not None:
                excluded.update(i for i, value in enumerate(attribute.data) if value.value)
    counts = Counter(tuple(sorted((a, b))) for face in mesh.polygons
                     if face.index not in excluded
                     for a, b in zip(face.vertices, (*face.vertices[1:], face.vertices[0])))
    return sum(n == 1 for n in counts.values()), sum(n > 2 for n in counts.values())


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
    for name in ('structure_lighting_info', 'structure_collision', 'structure_meta_data',
                 'portal_collision_tree'):
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

    def test_collision_sliver_dissolves_only_the_render_boundary_shortcut(self):
        import bmesh
        points = [(0, 0, 0), (2, 0, 0), (1, .000001, 0),
                  (0, -1, 0), (2, -1, 0), (1, 1, 0)]
        for rejection in (None, 'different_property', 'different_material',
                          'isolated', 'render_shortcut', 'missing_render_chain', 'same_winding'):
            with self.subTest(rejection=rejection):
                render = bpy.data.meshes.new('sliver_render')
                faces = [(0, 2, 5), (2, 1, 5)]
                if rejection == 'render_shortcut':
                    faces.append((0, 1, 5))
                if rejection == 'missing_render_chain':
                    faces.pop()
                render.from_pydata(points, [], faces)
                collision = bpy.data.meshes.new('sliver_collision')
                faces = [(0, 1, 2), (1, 0, 3, 4)]
                if rejection == 'isolated':
                    faces.pop()
                if rejection == 'same_winding':
                    faces[1] = tuple(reversed(faces[1]))
                collision.from_pydata(points, [], faces)
                attr = collision.attributes.new('surface_flags', 'INT', 'FACE')
                for datum in attr.data:
                    datum.value = 7
                if rejection == 'different_property':
                    attr.data[1].value = 8
                if rejection == 'different_material':
                    for name in ('sliver_a', 'sliver_b'):
                        collision.materials.append(bpy.data.materials.new(name))
                    collision.polygons[1].material_index = 1
                original = [tuple(v.co) for v in collision.vertices]
                count = dissolve_collision_edge_slivers(render, collision, .0001)
                self.assertEqual(count, int(rejection is None))
                self.assertEqual([tuple(v.co) for v in collision.vertices], original)
                if rejection is None:
                    self.assertEqual(len(collision.polygons), 1)
                    self.assertEqual(set(collision.polygons[0].vertices), {0, 1, 2, 3, 4})
                    self.assertEqual(collision.attributes['surface_flags'].data[0].value, 7)
                    bm = bmesh.new()
                    try:
                        bm.from_mesh(collision)
                        bmesh.ops.triangulate(bm, faces=list(bm.faces))
                        self.assertTrue(all(f.calc_area() > .1 for f in bm.faces))
                        self.assertFalse(any({v.index for v in e.verts} == {0, 1} for e in bm.edges))
                    finally:
                        bm.free()

    def test_collision_boundary_alignment_preserves_render_and_rejects_thin_layers(self):
        render = bpy.data.meshes.new('render_boundary')
        render.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        collision = render.copy()
        collision.vertices[0].co.x += .00001
        original = [tuple(v.co) for v in render.vertices]
        self.assertEqual(align_collision_boundary(render, collision, .0001), 1)
        self.assertEqual([tuple(v.co) for v in collision.vertices], original)
        self.assertEqual([tuple(v.co) for v in render.vertices], original)
        thin = bpy.data.meshes.new('thin_layers')
        thin.from_pydata(original + [(0, 0, .00002)], [], [(0, 1, 2)])
        collision.vertices[0].co.z = .00001
        before = tuple(collision.vertices[0].co)
        self.assertEqual(align_collision_boundary(thin, collision, .0001), 0)
        self.assertEqual(tuple(collision.vertices[0].co), before)

    def test_opposing_collision_faces_preserve_surface_selection_and_sidedness(self):
        surfaces = tuple(SimpleNamespace(index=i, material_index=-1, negated=i == 1,
                         invalid=False, ladder=False, breakable=False, slip_surface=False,
                         invisible=False, two_sided=False) for i in range(3))
        native = SimpleNamespace(vertices=((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                 polygons=((0, 1, 2), (0, 2, 1), (0, 3, 1)), surfaces=surfaces)
        collision = InstanceCollision.from_native(native, 'opposing_test', [])
        collision.mark_opposite_surfaces()
        self.assertEqual([s.two_sided for s in collision.surfaces], [True, True, False])
        selected = collision.to_object(mesh_only=True, surface_indices=[2])
        self.assertEqual(len(selected.polygons), 1)
        self.assertGreater(max(v.co.z for v in selected.vertices), 0)
        selected_coords = [selected.vertices[i].co for i in selected.polygons[0].vertices]
        self.assertTrue(any(v.z > 0 for v in selected_coords))
        self.assertTrue(all(v.y == 0 for v in selected_coords))
        both = collision.to_object(mesh_only=True, surface_indices=[0, 1])
        self.assertEqual(len(both.polygons), 1)
        self.assertTrue(any(p.type == 'face_sides' and p.two_sided for p in both.nwo.face_props))
        # Real Reach pairs can have an unmaterialed compiler backface.
        collision.surfaces[1].material = SimpleNamespace(render_method='rock.shader',
                                                         global_material_override='')
        for surface in collision.surfaces:
            surface.two_sided = False
        collision.mark_opposite_surfaces()
        self.assertTrue(collision.surfaces[0].two_sided and collision.surfaces[1].two_sided)
        collision.surfaces[0].material = SimpleNamespace(render_method='different.shader',
                                                         global_material_override='')
        for surface in collision.surfaces:
            surface.two_sided = False
        collision.mark_opposite_surfaces()
        self.assertFalse(any(s.two_sided for s in collision.surfaces))

    def test_reach_portals_reuse_conservative_h1_reconstruction_and_keep_flags(self):
        from dataclasses import replace
        from io_scene_foundry.tags.portal_reconstruction import reconstruct_portals
        first = StructureBspPortal(0, True, False, True, True, True,
                                  ((0, 0, 0), (.5, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)))
        rebuilt, count = reconstruct_portals([first])
        self.assertEqual(count, 1)
        self.assertEqual(len(rebuilt[0].vertices), 4)
        self.assertEqual(rebuilt[0].vertices[0][2], 0)
        ob = Portal(rebuilt[0]).create()
        self.assertEqual(ob.nwo.portal_type, '_connected_geometry_portal_type_one_way')
        self.assertTrue(ob.nwo.portal_ai_deafening and ob.nwo.portal_blocks_sounds and ob.nwo.portal_is_door)
        blocked = Portal(replace(first, one_way=False, no_way=True)).create()
        self.assertEqual(blocked.nwo.portal_type, '_connected_geometry_portal_type_no_way')
        crossing = replace(first, index=1, vertices=((.5, -.5, -1), (.5, 1.5, -1),
                                                     (.5, 1.5, 1), (.5, -.5, 1)))
        _, count = reconstruct_portals([first, crossing])
        self.assertEqual(count, 0, 'intersecting portals must not be extended')

    def test_reach_supernodes_select_the_real_tree_root_and_preserve_leaf_tags(self):
        from io_scene_foundry.tags.reach_portals import _cluster_tree, unpack_collision_node
        packed = 7 | (0xffffff << 16) | (0x800012 << 40)
        self.assertEqual(unpack_collision_node(packed), (7, 0xffffffff, 0x80000012))
        planes = [(1, 0, 0, 0), (0, 1, 0, 0)]
        nodes = [(0, -1, 0x80000000), (1, 0x80000000, 0x80000001)]
        supernode = ((0,) * 15, (0x40000001,) * 16, 0)
        data = dict(planes=planes, nodes=nodes, supernodes=[], clusters=[0, 1])
        self.assertEqual(_cluster_tree(data), 0)
        recovered = _cluster_tree(dict(data, supernodes=[supernode]))
        # Four axis splits collapse to the selected ordinary node, not node 0.
        self.assertEqual(recovered, (1, 0, 1))
        for child, expected in ((-1, None), (0x80000001, 1), (0, None)):
            tree = [((0,) * 15, (child,) * 16, 0)]
            self.assertEqual(_cluster_tree(dict(data, supernodes=tree)), expected)
        for tree in ([((0,) * 15, (99,) * 16, 0)], [((0,) * 15, (-1,) * 16, 3)]):
            with self.assertRaises(ValueError):
                _cluster_tree(dict(data, supernodes=tree))

    def test_intersecting_portals_extend_only_into_verified_solid_space(self):
        from dataclasses import replace
        from io_scene_foundry.tags.portal_reconstruction import reconstruct_portals
        first = StructureBspPortal(0, False, False, True, False, False,
                                  ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)))
        crossing = replace(first, index=1, vertices=((.5, -.5, -1), (.5, 1.5, -1),
                                                    (.5, 1.5, 1), (.5, -.5, 1)))
        rebuilt, count = reconstruct_portals([first, crossing], is_solid=lambda p: p.x < 0)
        self.assertEqual(count, 1)
        self.assertLess(min(p[0] for p in rebuilt[0].vertices), -.005)
        self.assertAlmostEqual(max(p[0] for p in rebuilt[0].vertices), 1, delta=1e-6)
        self.assertAlmostEqual(min(p[1] for p in rebuilt[0].vertices), 0, delta=1e-6)
        self.assertAlmostEqual(max(p[1] for p in rebuilt[0].vertices), 1, delta=1e-6)
        self.assertEqual(rebuilt[1].vertices, crossing.vertices)
        self.assertTrue(rebuilt[0].ai_deafening)

    def test_reach_cluster_boundaries_recover_connected_portals_and_preserve_flags(self):
        from dataclasses import replace
        from io_scene_foundry.tags.reach_portals import reconstruct_reach_portals
        left = StructureBspPortal(0, True, False, True, False, False,
            ((-1, -1, 0), (0, -1, 0), (0, 1, 0), (-1, 1, 0)), 0, 0, 2)
        right = replace(left, index=1, one_way=False, no_way=True, back_cluster=1,
                        vertices=((0, -1, 0), (1, -1, 0), (1, 1, 0), (0, 1, 0)))
        vertical = replace(left, index=2, plane_index=1, back_cluster=0, front_cluster=1,
                           vertices=((0, -1, -1), (0, 1, -1), (0, 1, 0), (0, -1, 0)))
        records = [left, right, vertical]
        data = dict(planes=[(0, 0, 1, 0), (1, 0, 0, 0)],
                    nodes=[(0, 1, 0x80000002), (1, 0x80000000, 0x80000001)],
                    supernodes=[], clusters=[0, 1, 2], bounds=[(-2, 2)] * 3)
        rebuilt = reconstruct_reach_portals(records, data)
        self.assertEqual(len(rebuilt), 3)
        for original, result in zip(records, rebuilt):
            self.assertEqual(len(result.polygons), 1)
            self.assertEqual((result.one_way, result.no_way, result.ai_deafening),
                             (original.one_way, original.no_way, original.ai_deafening))
            self.assertEqual(len(Portal(result).create().data.polygons), 1)
        self.assertEqual(min(p[0] for p in rebuilt[0].vertices), -2)
        self.assertEqual(max(p[0] for p in rebuilt[0].vertices), 0)
        self.assertEqual(min(p[0] for p in rebuilt[1].vertices), 0)
        self.assertEqual(max(p[0] for p in rebuilt[1].vertices), 2)
        self.assertTrue(all(p[0] == 0 for p in rebuilt[2].vertices))
        self.assertEqual(max(p[2] for p in rebuilt[2].vertices), 0)
        shifted = [replace(r, vertices=tuple((x, y, z + 5) for x, y, z in r.vertices)) for r in records]
        scaled_planes = dict(data, planes=[(0, 0, 2, 10), (1, 0, 0, 0)],
                             bounds=[(-2, 2), (-2, 2), (3, 7)])
        normalized = reconstruct_reach_portals(shifted, scaled_planes)
        self.assertTrue(all(abs(p[2] - 5) < 1e-10 for r in normalized[:2] for p in r.vertices))
        # Unrecoverable flag boundaries retain the original portal records.
        conflict = replace(left, index=3, one_way=False)
        self.assertTrue(all(not r.polygons for r in reconstruct_reach_portals([*records, conflict], data)))
        cycle = dict(data, nodes=[(0, 0, 0x80000002)])
        with self.assertRaisesRegex(ValueError, 'cycle'):
            reconstruct_reach_portals(records, cycle)

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
            for ob in objects:
                if ob.name == 'island_rock_1':
                    edges = solid_edge_counts(ob.data)
                    assert edges == (0, 0), f'island_rock_1 solid shell has invalid edges: {edges}'
                    assert len(ob.data.polygons) == 1610
                    print('REACH AUDIT island_rock_1: 1610 faces retained; '
                          'solid shell has no open or overused edges', flush=True)
                if ob.name == 'for_tunnel_column05':
                    import bmesh
                    assert len(ob.data.polygons) == 258
                    assert solid_edge_counts(ob.data) == (0, 0)
                    bm = bmesh.new()
                    triangulated = bpy.data.meshes.new('tunnel_triangulation_audit')
                    try:
                        bm.from_mesh(ob.data)
                        bmesh.ops.triangulate(bm, faces=list(bm.faces))
                        bm.to_mesh(triangulated)
                        assert solid_edge_counts(triangulated) == (0, 0)
                        assert min(p.area for p in triangulated.polygons) > .003
                    finally:
                        bm.free()
                        bpy.data.meshes.remove(triangulated)
                    print('REACH AUDIT for_tunnel_column05: no sliver, open or '
                          'overused edges, including after triangulation', flush=True)
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

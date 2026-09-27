"""Run in background Blender; optional -- --reach-kit <kit directory>."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import bpy

addons = Path(__file__).parent / 'addons'
sys.path.insert(0, str(addons))
wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (addons / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as wheel:
        wheel.extractall(wheels.name)
sys.path.insert(0, wheels.name)
from io_scene_foundry import props, utils, import_transform
from io_scene_foundry.tags.structure_design_blender import StructureDesignTag

props.register()
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
kit = Path(args[args.index('--reach-kit') + 1]) if '--reach-kit' in args else None


class StructureDesignTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.scene = SimpleNamespace(scene_project='test', scale='max', forward_direction='x', transforming=True)
        for name, value in (
            ('get_project', SimpleNamespace(game='reach', corinth=False)),
            ('get_scene_props', self.scene),
            ('get_tags_path', str(kit / 'tags' if kit else self.root)),
            ('get_data_path', str(self.root)),
            ('get_prefs', SimpleNamespace(apply_materials=False, update_materials_on_shader_path=False)),
            ('is_corinth', False),
        ):
            self.enterContext(patch.object(utils, name, return_value=value))

    def test_shared_definition_keeps_sheet_type_and_transform(self):
        from io_scene_foundry.tags.prefab import ScenarioStructureBspMetadataTag
        tag = StructureDesignTag.__new__(StructureDesignTag)
        tag.game = 'reach'
        tag.tag_path = SimpleNamespace(ShortName='test')
        geometry = dict(positions=[(0., 0., 0.), (1., 0., 0.), (0., 1., 0.)],
            texcoords=[(0., 0.), (1., 0.), (0., 1.)], normals=[(0., 0., 1.)] * 3,
            node_indices=[], node_weights=[], lightmap_texcoords=[], vertex_colors=[],
            indices=[0, 1, 2], rigid_node_index=None,
            parts=[dict(material_index=0, index_start=0, index_count=3, part_type=2)])
        placements = [SimpleNamespace(mesh_index=0, vertical_rain_sheet=sheet,
            name=f'rain_{i}', forward=(0., 1., 0.), left=(-1., 0., 0.), up=(0., 0., 1.),
            position=(2., 3., 4.), scale=2.) for i, sheet in enumerate((False, True, False))]
        for scale, forward in (('max', 'x'), ('blender', 'y-')):
            self.scene.scale, self.scene.forward_direction = scale, forward
            collection = bpy.data.collections.new('rain_test')
            with patch.object(ScenarioStructureBspMetadataTag, 'render_materials', return_value=[]):
                objects = tag._rain_to_blender(collection, [geometry], placements)
            self.assertEqual(len(objects), 3)
            self.assertIs(objects[0].data, objects[2].data)
            self.assertIsNot(objects[0].data, objects[1].data)
            self.assertTrue(objects[1].data.nwo.mesh_type.endswith('vertical_rain_sheet'))
            self.assertTrue(objects[0].data.nwo.mesh_type.endswith('rain_blocker'))
            expected = import_transform.position((2., 5., 4.))
            actual = objects[0].matrix_world @ objects[0].data.vertices[1].co
            self.assertLess((expected - actual).length, .001)

    def test_invalid_placement_fails_before_blender_changes(self):
        with patch.object(utils, 'get_tags_path', return_value=str(self.root)):
            tag = StructureDesignTag('invalid.structure_design', tag_must_exist=False)
        root = tag.tag.root()
        instances = tag.block(root, 'instanced geometry instances')
        instance = instances[instances.add()]
        instance.field('instance definition').set(4)
        collection = bpy.data.collections.new('invalid_design')
        before = len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.collections)
        with self.assertRaisesRegex(ValueError, 'invalid definition index 4'):
            tag.to_blender(collection)
        self.assertEqual(before, (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.collections)))

    @unittest.skipUnless(kit, 'requires --reach-kit')
    def test_reach_designs(self):
        paths = sorted((kit / 'tags/levels').rglob('*.structure_design'))
        self.assertTrue(paths)
        counts = {}
        for path in paths:
            with self.subTest(path=path), StructureDesignTag(path) as tag:
                records = tag.surfaces()
                meshes, placements = tag.rain_geometry()
                counts[path.stem] = (len(records), len(placements))
                collection = bpy.data.collections.new(path.stem)
                objects = tag.to_blender(collection)
                nonempty = sum(bool(meshes[p.mesh_index]['indices']) for p in placements)
                self.assertEqual(len(objects), len(records) + nonempty)
                self.assertTrue(all(len(ob.data.polygons) for ob in objects))
                if path.stem == 'm10_rain_occluders':
                    self.assertEqual(len(placements), 96)
        print(f'Imported {len(paths)} Reach structure designs; m10: {counts["m10_rain_occluders"]}')


suite = unittest.defaultTestLoader.loadTestsFromTestCase(StructureDesignTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)

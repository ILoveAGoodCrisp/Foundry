"""Run in background Blender; optionally append -- --reach-kit <kit path>.

The real-tag check only reads kit assets; extracted textures go to a temporary directory.
"""
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
from io_scene_foundry import props, utils
from io_scene_foundry.tags import structure_lighting

props.register()


class ReachLightingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.tags = self.root / 'tags'
        self.data = self.root / 'data'
        self.tags.mkdir()
        self.data.mkdir()
        for name, value in (
            ('get_project', SimpleNamespace(game='reach', corinth=False)),
            ('get_scene_props', SimpleNamespace(scene_project='test', scale='max', forward_direction='x', transforming=True)),
            ('get_tags_path', str(self.tags)),
            ('get_data_path', str(self.data)),
            ('get_prefs', SimpleNamespace(link_resource_nodes=False, bitmap_color_space_conversion=True)),
            ('is_corinth', False),
        ):
            self.enterContext(patch.object(utils, name, return_value=value))
        # Background Blender has no UI scale for the cosmetic node layout.
        self.enterContext(patch.object(utils, 'arrange'))

    def fixture(self, gels, inverse=False):
        tag = structure_lighting.ScenarioStructureLightingInfoTag('test.scenario_structure_lighting_info')
        definition = tag._add(tag.block_generic_light_definitions)
        for name, value in (('type', 1), ('shape', 0), ('color', (1., 1., 1.)),
                            ('intensity', 10.), ('hotspot cutoff size', 60.),
                            ('hotspot size', 30.), ('far attenuation bounds', (10., 20.))):
            tag._set(definition, name, value)
        tag.required_field(definition, 'flags').set_flag('invere squared falloff', inverse)
        for gel in gels:
            instance = tag._add(tag.block_generic_light_instances)
            tag._set(instance, 'definition index', 0)
            tag._set(instance, 'forward', (1., 0., 0.))
            tag._set(instance, 'up', (0., 0., 1.))
            if gel:
                tag.set_reference(instance, 'gel reference', gel)
        return tag

    def images(self, ob):
        return [node.image for node in ob.data.node_tree.nodes if node.type == 'TEX_IMAGE']

    def test_gels_on_shared_definition_have_independent_nodes(self):
        for name in ('a.bitmap', 'b.bitmap'):
            (self.tags / name).touch()
        images = {name: bpy.data.images.new(name, width=2, height=2)
                  for name in ('a.bitmap', 'b.bitmap')}
        with patch.object(structure_lighting, 'bitmap_to_image',
                          side_effect=lambda path: SimpleNamespace(image=images[Path(path).name])) as convert:
            tag = self.fixture(['a.bitmap', 'b.bitmap', '', 'a.bitmap'])
            objects = tag.to_blender()
        self.assertEqual(convert.call_count, 2)
        self.assertEqual(self.images(objects[0]), [images['a.bitmap']])
        self.assertEqual(self.images(objects[1]), [images['b.bitmap']])
        self.assertEqual(self.images(objects[2]), [])
        self.assertEqual(objects[0].data, objects[3].data)
        self.assertNotEqual(objects[0].data, objects[1].data)
        self.assertEqual(objects[0].nwo.light_gel_reference, 'a.bitmap')
        self.assertEqual(objects[1].nwo.light_gel_reference, 'b.bitmap')

    def test_missing_and_empty_gels_import_without_conversion(self):
        with patch.object(structure_lighting, 'bitmap_to_image') as convert:
            objects = self.fixture(['missing.bitmap', '']).to_blender()
        convert.assert_not_called()
        self.assertEqual(len(objects), 2)
        self.assertEqual(objects[0].nwo.light_gel_reference, 'missing.bitmap')
        self.assertEqual(self.images(objects[0]), [])

    def test_inverse_squared_energy_is_preserved(self):
        objects = self.fixture(['', ''], inverse=True).to_blender()
        self.assertEqual(objects[0].data, objects[1].data)
        self.assertAlmostEqual(objects[0].data.energy,
                               utils.calc_light_energy(objects[0].data, 10., 1), places=4)

    @unittest.skipUnless('--reach-kit' in sys.argv, 'No Reach kit supplied')
    def test_sword_slayer_native_bitmaps(self):
        kit = Path(sys.argv[sys.argv.index('--reach-kit') + 1])
        tags = kit / 'tags'
        relative = Path('levels/multi/20_sword_slayer/20_sword_slayer.scenario_structure_lighting_info')
        before = (tags / relative).read_bytes()
        with patch.object(utils, 'get_tags_path', return_value=str(tags)):
            tag = structure_lighting.ScenarioStructureLightingInfoTag(relative, tag_must_exist=True)
            objects = tag.to_blender()
        self.assertEqual(len(objects), len(tag.block_generic_light_instances))
        textured = [ob for ob in objects if self.images(ob)]
        self.assertTrue(textured)
        for image in {image for ob in textured for image in self.images(ob)}:
            self.assertGreater(len(image.pixels), 0, image.filepath)
            self.assertTrue(image.has_data)
        self.assertEqual((tags / relative).read_bytes(), before)
        print(f'Sword Slayer: imported {len(objects)} lights, {len(textured)} with gel textures')


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('Structure lighting regression tests failed')

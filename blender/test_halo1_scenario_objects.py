"""Blender --background --factory-startup --python-exit-code 1 --python this_file [-- --a10]."""
from collections import Counter
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

runpy.run_path(str(Path(__file__).with_name('test_classic_geometry.py')), run_name='bootstrap')
import bpy
from io_scene_foundry import utils, import_transform
from io_scene_foundry.tags.backend import TagDocument
from io_scene_foundry.tags.scenario import ScenarioMetadataTag
from io_scene_foundry.tools.importer import NWOImporter
from mathutils import Euler, Matrix, Vector


def open_scenario(root, path, game='halo1'):
    scenario = ScenarioMetadataTag.__new__(ScenarioMetadataTag)
    TagDocument.__init__(scenario, path, tags_root=root, game=game)
    scenario.corinth = False
    scenario.tag_path = scenario.reference_from_path(path)
    return scenario


class ScenarioObjectTests(unittest.TestCase):
    def test_halo1_placement_layouts_and_missing_palette_entries(self):
        with tempfile.TemporaryDirectory() as root:
            scenario = open_scenario(root, 'test.scenario')
            root_struct = scenario.tag.root()
            names = scenario.block(root_struct, 'object names')
            names.add()
            scenario._set_value(names[0], 'name', 'named_object')
            for block_name, palette_name in scenario.OBJECT_BLOCKS:
                block = scenario._optional_block(root_struct, block_name)
                if block is None:
                    continue
                with self.subTest(block=block_name):
                    palette = scenario.block(root_struct, palette_name)
                    palette.add()
                    reference = Path(root, block_name + '.scenery')
                    reference.touch()
                    scenario.set_reference(palette[0], 'name', reference)
                    for index, type_index in enumerate((0, 0, -1, 99)):
                        block.add()
                        element = block[index]
                        scenario._set_value(element, 'type', type_index)
                        scenario._set_value(element, 'name', 0 if index == 0 else -1)
                        owner = (element.field('properties').as_struct()
                                 if block_name in {'bipeds', 'vehicles'} else element)
                        placement = owner.field('placement').as_struct()
                        scenario._set_vector(placement, 'position', (1.25, -2.5, 3.75))
                        scenario._set_vector(placement, 'rotation', (.5, -.25, .125))
            count, folders, placements = scenario.object_placements()
            self.assertEqual(count, 1)
            self.assertEqual(folders, [])
            self.assertEqual(len(placements), 28)
            for placement in placements:
                self.assertEqual(placement.position, (1.25, -2.5, 3.75))
                self.assertEqual(placement.rotation, (.5, -.25, .125))
                self.assertEqual(placement.scale, 1)
                self.assertEqual(placement.folder_index, -1)
                self.assertEqual(placement.parent_index, -1)
                self.assertEqual(placement.bsps, frozenset())
            self.assertEqual(sum(p.definition is not None for p in placements), 14)
            self.assertEqual(sum(p.name == 'named_object' for p in placements), 7)
            self.assertIn('scenery:1', [p.name for p in placements])

    def test_reach_placement_layout_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            scenario = open_scenario(root, 'reach.scenario', 'reach')
            root_struct = scenario.tag.root()
            folders = scenario.block(root_struct, 'editor folders')
            folders.add()
            scenario._set_value(folders[0], 'name', 'props')
            scenario._set_value(folders[0], 'parent folder', -1)
            block = scenario.block(root_struct, 'scenery')
            block.add()
            scenario._set_value(block[0], 'type', -1)
            scenario._set_value(block[0], 'name', -1)
            data = block[0].field('object data').as_struct()
            scenario._set_vector(data, 'position', (2, 3, 4))
            scenario._set_vector(data, 'rotation', (.25, .5, .75))
            scenario._set_value(data, 'scale', 2)
            scenario._set_value(data, 'editor folder', 0)
            scenario._set_value(data.field('object id').as_struct(), 'origin bsp index', 3)
            _, folders, placements = scenario.object_placements()
            self.assertEqual(folders[0].name, 'props')
            placement = placements[0]
            self.assertEqual(placement.position, (2, 3, 4))
            self.assertEqual(placement.rotation, (.25, .5, .75))
            self.assertEqual(placement.scale, 2)
            self.assertEqual(placement.folder_index, 0)
            self.assertEqual(placement.bsps, frozenset({3}))

    @unittest.skipUnless('--a10' in sys.argv, 'Requires local HCEEK a10 tags')
    def test_a10_imports_real_geometry_as_shared_collection_instances(self):
        root = Path(r'G:\Halo\Modding\Main\HCEEK\tags')
        path = root / 'levels/a10/a10.scenario'
        project = SimpleNamespace(game='halo1', corinth=False, tags_directory=str(root),
                                  data_directory=str(root.parent / 'data'), project_path=str(root.parent))
        with patch.object(utils, 'get_project', return_value=project), patch.object(
                utils, 'get_tags_path', return_value=str(root)), patch.object(
                utils, 'get_export_props', return_value=SimpleNamespace()), patch.object(
                utils, 'get_prefs', return_value=SimpleNamespace(
                    apply_materials=False, apply_prefix='none', update_materials_on_shader_path=False)):
            importer = NWOImporter(bpy.context)
            importer.tag_scenario_import_objects = True
            importer.render_lod = 'L5'
            # BSP geometry is already covered separately; exercise the complete
            # scenario-object path with actual scenario, object and model tags.
            with patch.object(importer, 'import_bsp', return_value=([], None)):
                objects = importer.import_scenarios([str(path)], False, False)
            with ScenarioMetadataTag(path=str(path)) as scenario:
                _, _, placements = scenario.object_placements()
            expected = [p for p in placements if p.definition is not None]
            instances = [ob for ob in objects if ob.type == 'EMPTY' and ob.nwo.marker_game_instance_tag_name]
            self.assertEqual(len(instances), len(expected))
            self.assertGreater(len(instances), 0)
            collections = {}
            for ob, placement in zip(instances, expected):
                self.assertEqual(ob.instance_type, 'COLLECTION', placement.definition)
                self.assertTrue(ob.nwo.marker_instance)
                self.assertTrue(any(child.type == 'MESH' and len(child.data.polygons)
                                    for child in ob.instance_collection.all_objects), placement.definition)
                key = placement.definition
                self.assertIs(collections.setdefault(key, ob.instance_collection), ob.instance_collection)
                yaw, pitch, roll = placement.rotation
                expected_matrix = import_transform.marker_matrix(Matrix.LocRotScale(
                    Vector(tuple(v * 100 for v in placement.position)),
                    Euler((roll, -pitch, yaw), 'ZYX'), Vector.Fill(3, placement.scale)))
                for actual_row, expected_row in zip(ob.matrix_world, expected_matrix):
                    for actual, expected_value in zip(actual_row, expected_row):
                        self.assertAlmostEqual(actual, expected_value, places=4)
            self.assertLess(len(collections), len(instances))
            print('a10 object counts:', dict(Counter(p.block_name for p in placements)))
            print(f'Validated {len(instances)} placements sharing {len(collections)} geometry collections')


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('Halo 1 scenario object tests failed')

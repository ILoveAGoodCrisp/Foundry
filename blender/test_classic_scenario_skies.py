"""Blender --background --factory-startup --python-exit-code 1 --python this_file."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch
from zipfile import ZipFile

addons = Path(__file__).parent / 'addons'
sys.path.insert(0, str(addons))
wheels = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
for path in (addons / 'io_scene_foundry/wheels').glob('*.whl'):
    with ZipFile(path) as wheel:
        wheel.extractall(wheels.name)
sys.path.insert(0, wheels.name)

from io_scene_foundry.tags.backend import TagDocument
from io_scene_foundry.tags.scenario import ScenarioMetadataTag
from io_scene_foundry.export.process import ExportScene
from io_scene_foundry.export import legacy
from io_scene_foundry.tools.asset_types import AssetType
from io_scene_foundry import utils


def new_scenario(root, game):
    scenario = ScenarioMetadataTag.__new__(ScenarioMetadataTag)
    TagDocument.__init__(scenario, 'test.scenario', tags_root=root, game=game)
    scenario.corinth = False
    return scenario


class ClassicScenarioSkiesTests(unittest.TestCase):
    def test_sky_references_without_name_field(self):
        for game in ('halo1', 'halo2'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with new_scenario(root, game) as scenario:
                    scenario.set_skies(['levels/test/first.sky', 'levels/test/second.sky'])
                    self.assertEqual(scenario.get_sky_references(),
                                     ['levels\\test\\first.sky', 'levels\\test\\second.sky'])
                    self.assertEqual(scenario.get_skies_mapping(), ['first', 'second'])
                    scenario.set_skies(['levels/test/second.sky'])
                    self.assertEqual(scenario.get_skies_mapping(), ['second'])
                    scenario.add_new_sky('levels/test/third.sky')
                    self.assertEqual(scenario.get_skies_mapping(), ['second', 'third'])
                with new_scenario(root, game) as scenario:
                    self.assertEqual(scenario.get_skies_mapping(), ['second', 'third'])

    def test_named_sky_entries_still_write(self):
        for game in ('halo3', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with new_scenario(root, game) as scenario:
                    scenario.set_skies(['levels/test/first.scenery', 'levels/test/second.scenery'])
                    self.assertEqual(scenario.get_skies_mapping(), ['first', 'second'])
                    scenario.set_skies(['levels/test/third.scenery'])
                with new_scenario(root, game) as scenario:
                    self.assertEqual(scenario.get_skies_mapping(), ['third'])

    def test_export_updates_classic_scenario_skies(self):
        for game in ('halo1', 'halo2'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with new_scenario(root, game) as scenario:
                    scenario.set_skies(['levels/test/old.sky'])
                settings = SimpleNamespace(
                    scene_project='test', skies_authored_from_blender=True,
                    scenario_skies=[SimpleNamespace(path='levels/test/new.sky')],
                )
                export = ExportScene.__new__(ExportScene)
                export.asset_type = AssetType.SCENARIO
                export.scene_settings = settings
                export.tags_dir = Path(root)
                export.asset_path_relative = Path('.')
                export.asset_name = 'test'
                export.print_post = Mock()
                with patch.object(utils, 'get_scene_props', return_value=settings), \
                        patch.object(utils, 'get_project', return_value=SimpleNamespace(game=game)), \
                        patch.object(utils, 'get_tags_path', return_value=root):
                    export.update_scenario_skies()
                with new_scenario(root, game) as scenario:
                    self.assertEqual(scenario.get_skies_mapping(), ['new'])

    def test_halo1_asset_export_updates_skies_after_tag_compilation(self):
        with tempfile.TemporaryDirectory() as root:
            data = Path(root, 'data')
            asset = data / 'levels' / 'test'
            asset.mkdir(parents=True)
            export = Mock()
            export.original_cwd = os.getcwd()
            export.warnings = []
            settings = SimpleNamespace(asset_type='scenario', scene_project='test')
            options = SimpleNamespace(export_mode='TAGS', lightmap_structure=False)
            with patch.object(utils, 'get_project', return_value=SimpleNamespace(game='halo1')), \
                    patch.object(utils, 'get_data_path', return_value=str(data)), \
                    patch.object(legacy, 'ensure_asset_marker'), \
                    patch.object(legacy, 'LegacyExportScene', return_value=export):
                legacy.export_legacy_asset(Mock(), 'test', str(asset), settings, options, False)
            calls = export.mock_calls
            self.assertLess(calls.index(call.write_tags(False)),
                            calls.index(call.update_scenario_skies()))


if __name__ == '__main__':
    unittest.main(argv=[__file__])

"""Blender --background --factory-startup --python this_file.

Optionally append -- --blend <path> to check first-export tag setup using a
saved scene's settings. All generated tags go into a temporary directory.
"""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
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
from io_scene_foundry.export.process import ExportScene
from io_scene_foundry.tags.scenario import ScenarioDocument
from io_scene_foundry.tools.asset_types import AssetType


class ScenarioExportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.tags = root / 'tags'
        self.data = root / 'data'
        self.settings = SimpleNamespace(scene_project='test', ik_chains=(),
                                        parent_animation_graph='', scenario_type='multiplayer')
        for name, value in (
            ('get_project', SimpleNamespace(game='reach', corinth=False)),
            ('get_scene_props', self.settings),
            ('get_tags_path', str(self.tags)),
            ('get_data_path', str(self.data)),
            ('get_asset_path', 'foundry_blam/forge_world'),
        ):
            self.enterContext(patch.object(utils, name, return_value=value))

    def exporter(self, name='forge_world', settings=None):
        scene = ExportScene.__new__(ExportScene)
        scene.asset_type = AssetType.SCENARIO
        scene.has_animations = False
        scene.exported_animations = ()
        scene.scene_settings = settings or self.settings
        scene.tags_dir = self.tags
        scene.asset_path = self.data / 'foundry_blam' / name
        scene.asset_name = name
        scene.setup_scenario = False
        scene.print_pre = Mock()
        return scene

    def tag_path(self, name='forge_world'):
        return self.tags / 'foundry_blam' / name / f'{name}.scenario'

    def assert_setup(self, name='forge_world', scenario_type=1):
        with ScenarioDocument(self.tag_path(name), tags_root=self.tags,
                              game='reach', must_exist=True) as tag:
            self.assertEqual(tag.scenario_type(), scenario_type)
            profiles = tag.block(tag.tag.root(), 'player starting profile')
            self.assertEqual(len(profiles), 1)
            self.assertEqual(tag.value(profiles[0], 'name'), 'default_single')
            self.assertEqual(len(tag.block(tag.tag.root(), 'player starting locations')), 1)

    def test_first_export_creates_scenario_before_tool_import(self):
        self.assertFalse(self.tag_path().exists())
        scene = self.exporter()
        scene.preprocess_tags()
        self.assertTrue(scene.setup_scenario)
        self.assert_setup()

    def test_existing_scenario_is_not_reinitialized(self):
        self.exporter().preprocess_tags()
        with ScenarioDocument(self.tag_path(), tags_root=self.tags, game='reach') as tag:
            tag.set_scenario_type('solo')
        before = self.tag_path().read_bytes()
        scene = self.exporter()
        scene.preprocess_tags()
        self.assertFalse(scene.setup_scenario)
        self.assertEqual(self.tag_path().read_bytes(), before)
        self.assert_setup(scenario_type=0)

    def test_creation_uses_export_target_not_current_scene_asset(self):
        scene = self.exporter('collection_export')
        scene.preprocess_tags()
        self.assert_setup('collection_export')
        self.assertFalse(self.tag_path().exists())


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('Scenario export regression tests failed')
    if '--blend' in sys.argv:
        props.register()
        bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index('--blend') + 1],
                                 load_ui=False, use_scripts=False)
        settings = utils.get_scene_props()
        test = ScenarioExportTests()
        test.setUp()
        try:
            scene = test.exporter(settings=settings)
            scene.preprocess_tags()
            test.assert_setup(scenario_type={'solo': 0, 'multiplayer': 1, 'main menu': 2}[settings.scenario_type])
            print(f'SAVED SCENE CHECK: new {settings.scenario_type} scenario created and reopened successfully', flush=True)
        finally:
            test.doCleanups()

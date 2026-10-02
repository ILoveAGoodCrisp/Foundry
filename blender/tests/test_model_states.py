"""Regression checks for damage-state selection and legacy source dispatch."""
import ast
import importlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


ADDON = Path(__file__).resolve().parents[1] / 'addons' / 'io_scene_foundry'
PACKAGE = '_foundry_model_state_tests'
package = ModuleType(PACKAGE)
package.__path__ = [str(ADDON / 'tags')]
sys.modules[PACKAGE] = package
model_module = importlib.import_module(f'{PACKAGE}.model')


class FixtureModel(model_module.ModelDocument):
    reference_render_model = SimpleNamespace(Path=True)

    def __init__(self, game):
        self.game = game
        self.regions = {'hull': ['base', 'minor', 'major'],
                        'wheel': ['base', 'destroyed'],
                        'unlisted': ['base', 'major']}
        self.entries = [{'name': 'standard', 'regions': [
            {'region name': 'hull', 'permutations': [
                {'permutation name': 'base', 'states': [
                    {'state': 'minor damage', 'permutation name': 'minor'},
                    {'state': 3, 'permutation name': 'major'}]}]},
            {'region name': 'wheel', 'permutations': [
                {'permutation name': 'base', 'states': [
                    {'state': 4, 'permutation name': 'destroyed'}]}]}]}]

    def variants(self):
        return self.entries

    def render_regions(self):
        return self.regions

    def value(self, entry, name):
        return entry[name]

    def block(self, entry, name):
        return entry[name]

    def path_exists(self, path):
        return True


class ModelStateTests(unittest.TestCase):
    def test_selected_state_replaces_base_for_each_game(self):
        for game in ('halo2', 'halo3', 'halo3odst'):
            with self.subTest(game=game):
                model = FixtureModel(game)
                # Every candidate must respect the requested state, even if
                # random choice selects either end of the candidate list.
                for choose in (lambda options: options[0], lambda options: options[-1]):
                    with patch.object(model_module.random, 'choice', choose):
                        self.assertEqual(model.get_variant_regions_and_permutations('standard', 3),
                                         {('hull', 'major'), ('wheel', 'base'), ('unlisted', 'base')})

    def test_default_excludes_damage(self):
        model = FixtureModel('halo3')
        self.assertEqual(model.get_variant_regions_and_permutations('standard', 0),
                         {(region, 'base') for region in model.regions})

    def test_explicit_default_state_does_not_replace_base(self):
        model = FixtureModel('halo2')
        model.entries[0]['regions'][0]['permutations'][0]['states'].append(
            {'state': 0, 'permutation name': 'intact'})
        self.assertEqual(model.variant_region_options('standard', 0)['hull'], ['base'])

    def test_all_states_keeps_every_permutation(self):
        model = FixtureModel('halo3odst')
        self.assertEqual(model.get_variant_regions_and_permutations('standard', -1),
                         {(region, permutation) for region, names in model.regions.items()
                          for permutation in names})

    def test_no_variant_remains_unfiltered(self):
        self.assertEqual(FixtureModel('halo3').get_variant_regions_and_permutations('', 0), set())

    def test_legacy_sources_receive_state_filter_and_tag_skeleton(self):
        # Execute the real dispatch method with recording adapters so that the
        # test does not require a Blender process or installed game tags.
        tree = ast.parse((ADDON / 'tools' / 'importer.py').read_text(encoding='utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'NWOImporter')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'import_render_model')
        module = ast.Module(body=[method], type_ignores=[])
        for game in ('halo2', 'halo3', 'halo3odst'):
            for sources in (['mesh.jms'], ['mesh.ass'], ['mesh.jms', 'mesh.ass']):
                with self.subTest(game=game, sources=sources):
                    armature = object()
                    selected = {('hull', 'major')}
                    calls = []
                    collection = SimpleNamespace(children=SimpleNamespace(link=lambda child: None))
                    class Render:
                        def __init__(self, **kwargs): pass
                        def __enter__(self): return self
                        def __exit__(self, *args): pass
                        def to_blend_objects(self, *args, **kwargs): return [], armature
                        def skylights_to_blender(self, collection): return []
                        def _resolve_region_permutations(self, selection): return selection
                        def sky_data(self): return SimpleNamespace(is_sky=False, lights=[])
                        def render_materials(self):
                            return [SimpleNamespace(render_method=SimpleNamespace(
                                ShortName='blur', RelativePathWithExtension='warthog/blur.shader'))]
                    class Mover:
                        def __init__(self, *args): self.tag_path = 'mesh.render_model'
                        def __enter__(self): return self
                        def __exit__(self, *args): pass
                    env = {'Path': Path, 'legacy_model_formats': {'.jms', '.ass'},
                           'bpy': SimpleNamespace(data=SimpleNamespace(collections=SimpleNamespace(new=lambda name: collection))),
                           'utils': SimpleNamespace(print_tag=lambda text: None, TagImportMover=Mover),
                           'RenderModelTag': Render}
                    exec(compile(module, '<import_render_model>', 'exec'), env)
                    importer = SimpleNamespace(game=game, tag_markers=False, tag_import_attachments=False,
                                               tags_dir='', build_control_rig=False,
                                               import_info_sources_for_tag=lambda file: sources,
                                               import_jms_files=lambda *args, **kwargs: calls.append(kwargs) or [])
                    env['import_render_model'](importer, 'mesh.render_model', collection, None, selected)
                    self.assertEqual(len(calls), 1)
                    self.assertIs(calls[0]['tag_armature'], armature)
                    self.assertTrue(calls[0]['geometry_only'])
                    self.assertEqual(calls[0]['allowed_region_permutations'], selected)
                    self.assertEqual(calls[0]['shader_paths'], {'blur': 'warthog/blur.shader'})


if __name__ == '__main__':
    unittest.main()

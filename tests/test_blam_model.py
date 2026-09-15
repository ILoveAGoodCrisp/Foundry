"""Model metadata and editing tests using actual blam-tags files."""
import importlib
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest

ADDON = Path(__file__).resolve().parents[1] / 'blender/addons/io_scene_foundry'
package = ModuleType('foundry_model_tags')
package.__path__ = [str(ADDON / 'tags')]
sys.modules[package.__name__] = package
m = importlib.import_module('foundry_model_tags.model')


class ModelTests(unittest.TestCase):
    def test_reference_edits_and_rollback(self):
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                with m.ModelDocument('test.model', **args) as doc:
                    doc.reference_render_model.Path = 'test.render_model'
                    doc.reference_animation.Path = 'test.model_animation_graph'
                    materials = doc.block(doc.tag.root(), 'materials' if game in {'halo3', 'halo3odst'} else 'model materials')
                    material = materials[materials.add()]
                    doc.required_field(material, 'material name').set('paint')
                    doc.required_field(material, 'global material name').set('metal')
                path = Path(root) / 'test.model'
                before = path.read_bytes()
                with m.ModelDocument(path, **args) as doc:
                    self.assertEqual(doc.get_model_paths(), (str(Path(root) / 'test.render_model'), '',
                                     str(Path(root) / 'test.model_animation_graph'), ''))
                    doc.reference_render_model.Path = doc.reference_render_model.Path
                    self.assertFalse(doc.tag_has_changes)
                    self.assertEqual(doc.model_materials(), {'paint': 'metal'})
                self.assertEqual(before, path.read_bytes())
                with self.assertRaises(RuntimeError):
                    with m.ModelDocument(path, **args) as doc:
                        doc.reference_render_model.Path = None
                        raise RuntimeError('abort')
                self.assertEqual(before, path.read_bytes())

    def test_variants_regions_and_damage_states(self):
        with tempfile.TemporaryDirectory() as root:
            args = dict(tags_root=root, game='reach')
            with m.TagDocument('test.render_model', **args) as render:
                regions = render.block(render.tag.root(), 'regions')
                for name, names in [('body', ['base', 'damaged']), ('extra', ['a', 'b'])]:
                    region = regions[regions.add()]
                    render.required_field(region, 'name').set(name)
                    permutations = render.block(region, 'permutations')
                    for name in names:
                        element = permutations[permutations.add()]
                        render.required_field(element, 'name').set(name)
            with m.ModelDocument('test.model', **args) as doc:
                doc.reference_render_model.Path = 'test.render_model'
                variants = doc.variants()
                variant = variants[variants.add()]
                doc.required_field(variant, 'name').set('standard')
                regions = doc.block(variant, 'regions')
                region = regions[regions.add()]
                doc.required_field(region, 'region name').set('default')
                permutations = doc.block(region, 'permutations')
                permutation = permutations[permutations.add()]
                doc.required_field(permutation, 'permutation name').set('base')
                states = doc.block(permutation, 'states')
                state = states[states.add()]
                doc.required_field(state, 'permutation name').set('damaged')
                doc.required_field(state, 'state').set(1)
            with m.ModelDocument('test.model', **args) as doc:
                self.assertEqual(doc.get_model_variants(), ['standard'])
                self.assertEqual(doc.variant_region_options('standard', 0), {'body': ['base'], 'extra': ['a', 'b']})
                self.assertEqual(doc.variant_region_options('standard', 1)['body'], ['base', 'damaged'])
                self.assertEqual(doc.variant_region_options('missing'), {})
                for _ in range(5):
                    result = dict(doc.get_variant_regions_and_permutations('standard', 1))
                    self.assertIn(result['body'], ['base', 'damaged'])
                    self.assertIn(result['extra'], ['a', 'b'])

    def test_game_mode_override(self):
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with m.ModelDocument('test.model', tags_root=root, game=game) as doc:
                    doc.reference_render_model.Path = 'base.render_model'
                    overrides = doc.block(doc.tag.root(), 'game mode render model override')
                    entry = overrides[overrides.add()]
                    doc.required_field(entry, 'game mode').set(1)
                    doc.set_reference(entry, 'render model override', 'multiplayer.render_model')
                    self.assertEqual(doc.get_render_model(override_type=m.RenderModelOverrideType.multiplayer),
                                     str(Path(root) / 'multiplayer.render_model'))
                    self.assertEqual(doc.get_render_model(), str(Path(root) / 'base.render_model'))


if __name__ == '__main__':
    unittest.main()

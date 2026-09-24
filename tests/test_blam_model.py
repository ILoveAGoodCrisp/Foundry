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
s = importlib.import_module('foundry_model_tags.sky')
p = importlib.import_module('foundry_model_tags.physics')


class ModelTests(unittest.TestCase):
    def test_halo1_single_permutation_falls_back_per_region(self):
        with tempfile.TemporaryDirectory() as root:
            with m.ModelDocument('test.gbxmodel', tags_root=root, game='halo1') as model:
                regions = model.block(model.tag.root(), 'regions')
                for region_name, permutation_names in (
                        ('body', ('base', 'damaged')),
                        ('weapon', ('rifle', 'pistol'))):
                    region = regions[regions.add()]
                    model.required_field(region, 'name').set(region_name)
                    permutations = model.block(region, 'permutations')
                    for permutation_name in permutation_names:
                        permutation = permutations[permutations.add()]
                        model.required_field(permutation, 'name').set(permutation_name)

                self.assertEqual(
                    model.get_halo1_region_permutations('damaged'),
                    {('body', 'damaged'), ('weapon', 'rifle')},
                )
                self.assertEqual(model.get_halo1_region_permutations('all_permutations'), set())

    def test_halo1_physics_mass_points(self):
        with tempfile.TemporaryDirectory() as root:
            with p.PhysicsDocument('test.physics', tags_root=root, game='halo1') as physics:
                point = physics.block(physics.tag.root(), 'mass points')
                point = point[point.add()]
                physics.required_field(point, 'name').set('front wheel')
                physics.required_field(point, 'model node').set(7)
                physics.required_field(point, 'radius').set(0.25)
                position = physics.required_field(point, 'position')
                position.set(type(position.value)(1.0, 2.0, 3.0))

            with p.PhysicsDocument('test.physics', tags_root=root, game='halo1') as physics:
                record, = physics.primitive_bodies()
                self.assertEqual(record.name, 'front wheel')
                self.assertEqual(record.kind, 'sphere')
                self.assertEqual(record.node_index, 7)
                self.assertEqual(record.radius, 0.25)
                self.assertEqual(record.translation, (1.0, 2.0, 3.0))
                self.assertEqual(physics.constraints(), [])
                self.assertEqual(physics.materials(), [])

    def test_halo1_sky_references_compiled_gbxmodel(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            with s.SkyDocument('test.sky', tags_root=root, game='halo1') as sky:
                sky.set_reference(sky.tag.root(), 'model', 'levels/sky.model')
                sky.set_reference(sky.tag.root(), 'animation graph', 'levels/sky.model_animations')
            (root / 'levels').mkdir()
            (root / 'levels/sky.gbxmodel').touch()
            (root / 'levels/sky.model_animations').touch()

            with s.SkyDocument('test.sky', tags_root=root, game='halo1') as sky:
                self.assertEqual(sky.get_model_path(), str(root / 'levels/sky.gbxmodel'))
                self.assertEqual(sky.get_animation_path(), str(root / 'levels/sky.model_animations'))

    def test_halo2_sky_references_render_model(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            with s.SkyDocument('test.sky', tags_root=root, game='halo2') as sky:
                sky.set_reference(sky.tag.root(), 'render model', 'levels/sky.render_model')
                sky.set_reference(sky.tag.root(), 'animation graph', 'levels/sky.model_animation_graph')
            (root / 'levels').mkdir()
            (root / 'levels/sky.render_model').touch()
            (root / 'levels/sky.model_animation_graph').touch()

            with s.SkyDocument('test.sky', tags_root=root, game='halo2') as sky:
                self.assertEqual(sky.get_model_path(), str(root / 'levels/sky.render_model'))
                self.assertEqual(sky.get_animation_path(), str(root / 'levels/sky.model_animation_graph'))

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

"""Native object edits against real schemas and serialized tag files."""
import importlib
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest

ADDON = Path(__file__).resolve().parents[1] / 'blender/addons/io_scene_foundry'
package = ModuleType('foundry_object_tags')
package.__path__ = [str(ADDON / 'tags')]
sys.modules[package.__name__] = package
m = importlib.import_module('foundry_object_tags.object')
GAMES = ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a')


class ObjectTests(unittest.TestCase):
    def test_attachment_records_survive_close(self):
        for game in GAMES:
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                with m.ObjectDocument('test.scenery', **args) as doc:
                    block = doc.block(doc.object_struct(), 'attachments')
                    for path in ('lamp.light', None, 'effect.effect'):
                        element = block[block.add()]
                        doc.set_reference(element, 'type', path)
                        for name, value in [('marker', 'head'), ('primary scale', 'power'),
                                            ('secondary scale', 'pulse')]:
                            doc.required_field(element, name).set(value)
                with m.ObjectDocument('test.scenery', **args) as doc:
                    records = doc.get_attachments()
                    self.assertFalse(doc.tag_has_changes)
                self.assertEqual(records[0].reference.RelativePathWithExtension, 'lamp.light')
                self.assertEqual(records[0].marker, 'head')
                self.assertEqual(records[0].primary_scale, 'power')
                self.assertEqual(records[0].secondary_scale, 'pulse')
                self.assertIsNone(records[1].reference)
                self.assertEqual(records[2].reference.Extension, 'effect')

    def test_references_roundtrip_and_abort(self):
        for game in GAMES:
            for group in ('scenery', 'weapon', 'biped', 'vehicle', 'device_machine'):
                with self.subTest(game=game, group=group), tempfile.TemporaryDirectory() as root:
                    args = dict(tags_root=root, game=game)
                    path = Path(root) / ('test.' + group)
                    with m.ObjectDocument(path, **args) as doc:
                        doc.set_model_tag_path('test.model')
                        self.assertEqual(doc.get_default_variant(), '')
                        self.assertEqual(doc.get_function_names(), [])
                        self.assertIsNone(doc.get_change_colors())
                    before = path.read_bytes()
                    with m.ObjectDocument(path, **args) as doc:
                        self.assertEqual(doc.get_model_tag_path(), 'test.model')
                        doc.set_model_tag_path(doc.reference_model.Path)
                        self.assertFalse(doc.tag_has_changes)
                    self.assertEqual(before, path.read_bytes())
                    with self.assertRaises(RuntimeError):
                        with m.ObjectDocument(path, **args) as doc:
                            doc.reference_model.Path = None
                            raise RuntimeError('abort')
                    self.assertEqual(before, path.read_bytes())

    def test_weapon_metadata_and_first_person_edits(self):
        for game in GAMES:
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                (Path(root) / 'fp.render_model').touch()
                with m.ObjectDocument('test.weapon', **args) as doc:
                    magazines = doc.block(doc.tag.root(), 'magazines')
                    doc.required_field(magazines[magazines.add()], 'rounds loaded maximum').set(32)
                    triggers = doc.block(doc.tag.root(), 'new triggers')
                    doc.required_field(triggers[triggers.add()], 'behavior').set(3)
                    doc.set_fp_weapon_render_model('fp.render_model')
                    doc.set_reference(doc.first_person()[0], 'first person animations', 'fp.model_animation_graph')
                with m.ObjectDocument('test.weapon', **args) as doc:
                    self.assertEqual(doc.get_magazine_size(), 32)
                    self.assertEqual(doc.get_uses_tether(), game not in {'halo3', 'halo3odst'})
                    self.assertEqual(len(doc.first_person()), 2)
                    self.assertEqual(doc.get_fp_animation(0).Extension, 'model_animation_graph')
                    self.assertIsNone(doc.get_fp_animation(1))
                    for element in doc.first_person():
                        self.assertEqual(doc.reference(element, 'first person model').RelativePathWithExtension, 'fp.render_model')
                    doc.set_fp_weapon_render_model('fp.render_model')
                    self.assertFalse(doc.tag_has_changes)
                with m.ObjectDocument('test.scenery', **args) as doc:
                    self.assertEqual(doc.get_magazine_size(), 0)
                    self.assertEqual(doc.get_magazine_size(find_weapon=True), 32)
                    self.assertEqual(doc.get_uses_tether(find_weapon=True), game not in {'halo3', 'halo3odst'})

    def test_colors_and_unit_metadata(self):
        for game in GAMES:
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                with m.ObjectDocument('test.biped', **args) as doc:
                    obj = doc.object_struct()
                    doc.required_field(obj, 'default model variant').set('blue')
                    colors = doc.block(obj, 'change colors')
                    color = colors[colors.add()]
                    permutations = doc.block(color, 'initial permutations')
                    permutation = permutations[permutations.add()]
                    doc.required_field(permutation, 'variant name').set('blue')
                    field = doc.required_field(permutation, 'color upper bound')
                    field.set(type(field.value)(0.25, 0.5, 0.75))
                    unit = doc.nested(doc.tag.root(), 'unit')
                    seats = doc.block(unit, 'seats')
                    doc.required_field(seats[seats.add()], 'label').set('driver')
                    weapons = doc.block(unit, 'weapons')
                    doc.set_reference(weapons[weapons.add()], 'weapon', 'test.weapon')
                with m.ObjectDocument('test.biped', **args) as doc:
                    self.assertEqual(doc.get_change_colors()[0], [0.25, 0.5, 0.75, 1.0])
                    self.assertEqual(doc.get_change_colors('missing'), [(1.0, 1.0, 1.0, 1.0)] * 4)
                    self.assertEqual(doc.get_seat_names(), ['driver'])
                    self.assertEqual(doc.get_unit_weapons()[0].RelativePathWithExtension, 'test.weapon')
                    self.assertEqual(len(doc.get_weapon_markers()), 2)


if __name__ == '__main__':
    unittest.main()

"""Native object edits against real schemas and serialized tag files."""
import importlib
import json
import shutil
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
    def test_h3_unused_function_layout_does_not_force_legacy_copy(self):
        with tempfile.TemporaryDirectory() as root:
            definitions = Path(root) / 'definitions'
            profile = definitions / 'halo3_mcc'
            shutil.copytree(ADDON / 'tags/definitions/halo3_mcc', profile)
            schema_path = profile / 'object.json'
            schema = json.loads(schema_path.read_text())
            function = schema['structs']['object_change_color_function']
            function['size'] += 4
            function['fields'].insert(0, {'type': 'pad', 'name': 'legacy padding', 'definition': 4})
            schema['structs']['object_change_colors']['fields'].insert(0, {'type': 'custom', 'name': ''})
            schema_path.write_text(json.dumps(schema))
            args = dict(tags_root=root, game='halo3')
            with m.ObjectDocument('test.weapon', definitions=definitions, **args) as source:
                colors = source.block(source.object_struct(), 'change colors')
                permutations = source.block(colors[colors.add()], 'initial permutations')
                source.required_field(permutations[permutations.add()], 'variant name').set('blue')
            with m.ObjectDocument('test.weapon', **args) as source, m.ObjectDocument('test.scenery', **args) as target:
                target.copy_cinematic_object(source)
            with m.ObjectDocument('test.scenery', **args) as target:
                colors = target.block(target.object_struct(), 'change colors')
                self.assertEqual(target.value(target.block(colors[0], 'initial permutations')[0], 'variant name'), 'blue')
                self.assertEqual(len(target.block(colors[0], 'functions')), 0)
            # Populated incompatible function data must still fail and must not save a partial tag.
            with m.ObjectDocument('test.weapon', **args) as source:
                functions = source.block(source.block(source.object_struct(), 'change colors')[0], 'functions')
                functions.add()
                source.tag_has_changes = True
            before = (Path(root) / 'test.scenery').read_bytes()
            with self.assertRaises(m.CinematicCopyUnsupported):
                with m.ObjectDocument('test.weapon', **args) as source, m.ObjectDocument('test.scenery', **args) as target:
                    target.copy_cinematic_object(source)
            self.assertEqual(before, (Path(root) / 'test.scenery').read_bytes())

    def test_cinematic_copy_preserves_nested_data_and_references(self):
        for game in GAMES:
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                with m.ObjectDocument('test.weapon', **args) as source:
                    obj = source.object_struct()
                    source.set_model_tag_path('test.model')
                    if game != 'halo3':
                        source.set_reference(obj, 'simulation_interpolation', 'test.simulation_interpolation')
                    source.set_reference(obj, 'material effects', 'test.material_effects')
                    functions = source.block(obj, 'functions')
                    function = functions[functions.add()]
                    source.required_field(function, 'import name').set('power')
                    source.required_field(function, 'export name').set('ammo_one')
                    # Function curves are opaque data and must survive verbatim.
                    curve = source.nested(function, 'default function')
                    data = next(f for f in curve.fields() if f.type_name == 'data')
                    data.set(bytes(range(32)))
                    colors = source.block(obj, 'change colors')
                    permutations = source.block(colors[colors.add()], 'initial permutations')
                    permutation = permutations[permutations.add()]
                    source.required_field(permutation, 'variant name').set('blue')
                before = (Path(root) / 'test.weapon').read_bytes()
                with m.ObjectDocument('test.weapon', **args) as source, \
                     m.ObjectDocument('test.scenery', **args) as target:
                    target.copy_cinematic_object(source, ('ammo_one', 'ammo_tens'))
                self.assertEqual(before, (Path(root) / 'test.weapon').read_bytes())
                with m.ObjectDocument('test.scenery', **args) as target:
                    obj = target.object_struct()
                    self.assertEqual(target.get_model_tag_path(), 'test.model')
                    if game != 'halo3':
                        self.assertEqual(target.reference(obj, 'simulation_interpolation').Extension, 'simulation_interpolation')
                    self.assertEqual(target.reference(obj, 'material effects').Extension, 'material_effects')
                    self.assertEqual(target.get_function_names(), ['ammo_one', 'ammo_tens'])
                    functions = target.block(obj, 'functions')
                    self.assertEqual([target.value(e, 'import name') for e in functions], ['zero', 'zero'])
                    curve = target.nested(functions[0], 'default function')
                    self.assertEqual(next(f for f in curve.fields() if f.type_name == 'data').value, bytes(range(32)))
                    colors = target.block(obj, 'change colors')
                    self.assertEqual(target.value(target.block(colors[0], 'initial permutations')[0], 'variant name'), 'blue')

    def test_incompatible_block_copy_is_atomic(self):
        with tempfile.TemporaryDirectory() as root:
            args = dict(tags_root=root, game='reach')
            with m.ObjectDocument('source.weapon', **args) as source, \
                 m.ObjectDocument('target.scenery', **args) as target:
                functions = target.block(target.object_struct(), 'functions')
                target.required_field(functions[functions.add()], 'export name').set('keep')
                before = target.tag.write_to_bytes()
                with self.assertRaises(ValueError):
                    functions.copy_from(source.block(source.object_struct(), 'attachments'))
                self.assertEqual(target.tag.write_to_bytes(), before)

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

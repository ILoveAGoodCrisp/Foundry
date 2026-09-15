"""Real-binding metadata regression tests, no Blender or .NET required."""
import importlib
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest

ADDON = Path(__file__).resolve().parents[1] / 'blender/addons/io_scene_foundry'
package = ModuleType('foundry_native_tags')
package.__path__ = [str(ADDON / 'tags')]
sys.modules[package.__name__] = package
metadata = importlib.import_module('foundry_native_tags.metadata')
backend = importlib.import_module('foundry_native_tags.backend')
lighting = importlib.import_module('foundry_native_tags.lighting')
lighting = importlib.import_module('foundry_native_tags.lighting')


class MetadataTests(unittest.TestCase):
    def test_lightmap_region_settings(self):
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    doc.restrict_to_region((-1., -2., -3.), (1., 2., 3.))
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    settings = doc.settings('Global lightmapper settings')
                    self.assertEqual(doc.value(settings, 'Mode'), 'One bounce')
                    self.assertEqual(tuple(doc.value(settings, 'Indirect Restrict AABB Min').to_array()), (-1., -2., -3.))
                    self.assertTrue(doc.required_field(settings, 'Global flags').get_flag('Restrict lightmap samples to Maya regions'))
                    self.assertTrue(doc.required_field(doc.settings('Local lightmapper settings'), 'Local flags').get_flag('Enable AO'))
                    doc.required_field(settings, 'Mode').set(2)
                    doc.restrict_to_region((0., 0., 0.), (1., 1., 1.))
                    self.assertEqual(doc.value(settings, 'Mode'), 'Two bounce')
                    doc.clear_region_restriction()
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    self.assertFalse(doc.required_field(doc.settings('Global lightmapper settings'), 'Global flags').get_flag('Restrict lightmap samples to Maya regions'))
                    with self.assertRaises(ValueError):
                        doc.restrict_to_region((1., 0., 0.), (0., 0., 0.))

    def test_lightmap_region_settings(self):
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    doc.restrict_to_region((-1., -2., -3.), (1., 2., 3.))
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    settings = doc.settings('Global lightmapper settings')
                    self.assertEqual(doc.value(settings, 'Mode'), 'One bounce')
                    self.assertEqual(tuple(doc.value(settings, 'Indirect Restrict AABB Min').to_array()), (-1., -2., -3.))
                    self.assertTrue(doc.required_field(settings, 'Global flags').get_flag('Restrict lightmap samples to Maya regions'))
                    self.assertTrue(doc.required_field(doc.settings('Local lightmapper settings'), 'Local flags').get_flag('Enable AO'))
                    doc.required_field(settings, 'Mode').set(2)
                    doc.restrict_to_region((0., 0., 0.), (1., 1., 1.))
                    self.assertEqual(doc.value(settings, 'Mode'), 'Two bounce')
                    doc.clear_region_restriction()
                with self.create(lighting.LightmapperGlobalsDocument, root, game) as doc:
                    self.assertFalse(doc.required_field(doc.settings('Global lightmapper settings'), 'Global flags').get_flag('Restrict lightmap samples to Maya regions'))
                    with self.assertRaises(ValueError):
                        doc.restrict_to_region((1., 0., 0.), (0., 0., 0.))

    def create(self, cls, root, game, name='test'):
        return cls(name + '.' + cls.tag_ext, tags_root=root, game=game)

    def populate_option(self, doc):
        block = doc.parameters()
        for index, kind in enumerate(metadata.OPTION_TYPES):
            element = block[block.add()]
            for name, value in [('parameter name', kind), ('parameter type', index),
                                ('default real value', 2.5), ('default int/bool value', 7)]:
                doc.required_field(element, name).set(value)
            if index == 0:
                doc.required_field(element, 'default bitmap').set((doc.api.parse_group_tag('bitm'), 'textures/test'))
            color_field = doc.required_field(element, 'default color')
            color_field.set(type(color_field.value)(0xFF804020))
        doc.tag_has_changes = True

    def test_option_types_and_detached_defaults(self):
        for game in ('halo3', 'halo3odst', 'reach'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(metadata.RenderMethodOptionDocument, root, game) as doc:
                    self.populate_option(doc)
                with self.create(metadata.RenderMethodOptionDocument, root, game) as doc:
                    result = doc.get_option_parameters()
                    self.assertEqual(doc.read_parameter_types(), dict(zip(metadata.OPTION_TYPES, range(6))))
                    self.assertEqual(doc.read_defaults()['real'], 2.5)
                    self.assertEqual(doc.read_parameter_names()['real'], 'real')
                self.assertEqual(result['int'].default, 7)
                self.assertEqual(result['argb color'].default[1], 2.5)
                self.assertEqual(result['color'].default, (128/255, 64/255, 32/255, 1.))
                reference = result['bitmap'].default
                self.assertEqual(reference.RelativePathWithExtension, r'textures\test.bitmap')
                self.assertEqual(reference.Filename, str(Path(root) / r'textures\test.bitmap'))

    def test_definition_follows_reference_and_handles_null(self):
        with tempfile.TemporaryDirectory() as root:
            with self.create(metadata.RenderMethodOptionDocument, root, 'reach', 'option') as doc:
                self.populate_option(doc)
            with self.create(metadata.RenderMethodDefinitionDocument, root, 'reach') as doc:
                categories = doc.block(doc.tag.root(), 'categories')
                category = categories[categories.add()]
                doc.required_field(category, 'category name').set('albedo')
                options = doc.block(category, 'options')
                option = options[options.add()]
                doc.required_field(option, 'option name').set('default')
                doc.required_field(option, 'option').set((doc.api.parse_group_tag('rmop'), 'option'))
                option = options[options.add()]
                doc.required_field(option, 'option name').set('none')
            with self.create(metadata.RenderMethodDefinitionDocument, root, 'reach') as doc:
                result = doc.get_defaults()
                self.assertEqual(result['albedo']['default']['real'].default, 2.5)
                self.assertEqual(result['albedo']['none'], {})

    def test_material_defaults_for_h4_and_h2amp(self):
        for game in ('halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(metadata.MaterialShaderDocument, root, game) as doc:
                    block = doc.parameters()
                    for index, kind in enumerate(metadata.MATERIAL_TYPES):
                        element = block[block.add()]
                        for name, value in [('parameter name', kind), ('parameter type', index),
                                            ('display name', b'Display\0'), ('real', 3.5), ('int/bool', 5)]:
                            doc.required_field(element, name).set(value)
                with self.create(metadata.MaterialShaderDocument, root, game) as doc:
                    result = doc.get_defaults()
                    self.assertEqual(doc.read_parameters()['real'], ['Display', 'real'])
                    self.assertEqual(doc.read_parameters_list(), list(metadata.MATERIAL_TYPES))
                self.assertEqual(result['real'].default, 3.5)
                self.assertEqual(result['bitmap'].default, None)
                self.assertEqual(result['color'].ui_name, 'Display')

    def test_globals_names_and_empty_camera(self):
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with self.create(metadata.GlobalsDocument, root, game) as doc:
                    block = doc.block(doc.tag.root(), 'materials')
                    element = block[block.add()]
                    doc.required_field(element, 'name').set('metal')
                with self.create(metadata.GlobalsDocument, root, game) as doc:
                    self.assertEqual(doc.get_global_materials(), ['metal'])
                    self.assertIsNone(doc.get_camera_fov())
                    cameras = doc.block(doc.tag.root(), 'camera')
                    camera = cameras[cameras.add()]
                    field = camera.field('field of view')
                    if field is not None:
                        field.set(78.)
                    self.assertEqual(doc.get_camera_fov(), None if game == 'halo3' else 78.)


if __name__ == '__main__':
    unittest.main()

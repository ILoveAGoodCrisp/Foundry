"""Unit tests for pre-Reach shader-path material names."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


ADDON = Path(__file__).resolve().parents[1] / 'blender/addons/io_scene_foundry'
spec = importlib.util.spec_from_file_location(
    'shader_collections', ADDON / 'export/shader_collections.py')
shader_collections = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shader_collections)


class ShaderCollectionTests(unittest.TestCase):
    def test_halo1_uses_simple_name_matching(self):
        collections = shader_collections.ShaderCollections('.', 'halo1')
        name = collections.material_name(
            r'levels\mine\shaders\metal.shader_environment')
        self.assertEqual(name, 'metal')
        self.assertFalse(collections.dirty)

    def test_existing_prefix_and_default_are_reused(self):
        with TemporaryDirectory() as root:
            path = Path(root) / 'scenarios/shaders/shader_collections.shader_collections'
            path.parent.mkdir(parents=True)
            path.write_text(
                '; stock\n*\tscenarios\\shaders\nmine\tlevels\\mine\\shaders\n',
                encoding='utf-8')
            collections = shader_collections.ShaderCollections(root, 'halo2')
            self.assertEqual(
                collections.material_name(r'levels\mine\shaders\metal'),
                'mine metal')
            self.assertEqual(
                collections.material_name(r'scenarios\shaders\generic'),
                'generic')
            self.assertFalse(collections.dirty)

    def test_generated_prefix_is_stable_and_appended_once(self):
        with TemporaryDirectory() as root:
            first = shader_collections.ShaderCollections(root, 'halo3')
            material_name = first.material_name(
                r'levels\custom\shaders\metal.shader')
            self.assertRegex(material_name, r'^f_[0-9a-f]{10} metal$')
            first.path.parent.mkdir(parents=True)
            first.path.write_text(first.text(), encoding='utf-8')

            second = shader_collections.ShaderCollections(root, 'halo3')
            self.assertEqual(
                second.material_name(r'levels\custom\shaders\metal'),
                material_name)
            self.assertFalse(second.dirty)
            self.assertEqual(
                second.original.count(shader_collections.FOUNDRY_HEADING), 1)

    def test_ambiguous_stock_prefix_is_not_reused(self):
        with TemporaryDirectory() as root:
            path = Path(root) / 'levels/shader_collections.txt'
            path.parent.mkdir(parents=True)
            path.write_text(
                'same\tlevels\\first\nsame\tlevels\\second\n',
                encoding='utf-8')
            collections = shader_collections.ShaderCollections(root, 'halo3odst')
            for directory in ('first', 'second'):
                self.assertTrue(collections.material_name(
                    rf'levels\{directory}\metal').startswith('f_'))


if __name__ == '__main__':
    unittest.main()

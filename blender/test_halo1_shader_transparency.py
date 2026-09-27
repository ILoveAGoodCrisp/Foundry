"""Blender --background --factory-startup --python this_file (optional -- --a10)."""
from pathlib import Path
import runpy
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

runpy.run_path(str(Path(__file__).with_name('test_classic_geometry.py')), run_name='bootstrap')
import bpy
from io_scene_foundry.tags import halo1_bsp_blender as helpers
from io_scene_foundry.tags.backend import TagDocument


class TransparencyTests(unittest.TestCase):
    def test_material_mask_and_shader_cache(self):
        mesh = bpy.data.meshes.new('transparency_test')
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], [],
                         [(0, 1, 2), (0, 2, 3), (1, 2, 3)])
        for path in ('cutout.shader_environment', 'opaque.shader_environment', 'cutout.shader_environment'):
            mat = bpy.data.materials.new(path)
            mat.nwo['shader_path'] = path
            mesh.materials.append(mat)
        for i, face in enumerate(mesh.polygons):
            face.material_index = i
        ob = bpy.data.objects.new('transparency_test', mesh)
        with patch.object(helpers, 'TagDocument') as document, patch.object(
                helpers, 'shader_alpha_tested', side_effect=[True, False]):
            helpers.apply_shader_transparency(SimpleNamespace(tags_root='unused', definitions='unused'), [ob, ob])
            self.assertEqual(document.call_count, 2)
        prop = mesh.nwo.face_props[0]
        self.assertEqual(prop.type, 'transparent')
        self.assertTrue(prop.transparent)
        self.assertEqual([v.value for v in mesh.attributes[prop.attribute_name].data], [True, False, True])

    @unittest.skipUnless('--a10' in sys.argv, 'Requires local HCEEK a10 tags')
    def test_a10_shader_flags(self):
        root = r'G:\Halo\Modding\Main\HCEEK\tags'
        for path, expected in [('alpha test.shader_environment', True),
                               ('steel.shader_environment', False),
                               ('cryo glass.shader_transparent_generic', False)]:
            with self.subTest(path=path), TagDocument('levels/a10/shaders/' + path,
                    tags_root=root, game='halo1', must_exist=True) as shader:
                self.assertEqual(helpers.shader_alpha_tested(shader), expected)


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('H1 shader transparency tests failed')

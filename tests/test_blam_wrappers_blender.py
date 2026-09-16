"""Exercise the real addon imports and migrated wrappers without starting .NET."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import sys

ADDONS = Path(__file__).resolve().parents[1] / 'blender/addons'
sys.path.insert(0, str(ADDONS))
from io_scene_foundry import utils, managed_blam
from io_scene_foundry.managed_blam.model import ModelTag
from io_scene_foundry.managed_blam.object import ObjectTag
from io_scene_foundry.managed_blam.globals import GlobalsTag
from io_scene_foundry.managed_blam.render_method_option import RenderMethodOptionTag
from io_scene_foundry.managed_blam.render_method_definition import RenderMethodDefinitionTag
from io_scene_foundry.managed_blam.material_shader import MaterialShaderTag


class WrapperTests(unittest.TestCase):
    def test_migrated_wrappers_do_not_initialize_managedblam(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
                 patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
                 patch.object(utils, 'get_tags_path', return_value=root), \
                 patch.object(utils, 'get_asset_path', return_value='objects/test'), \
                 patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
                with ModelTag('test.model') as model:
                    model.reference_render_model.Path = 'test.render_model'
                    self.assertEqual(model.get_model_variants(), [])
                with ModelTag('test.model') as model:
                    self.assertEqual(model.reference_render_model.Path.RelativePathWithExtension, 'test.render_model')
                with ObjectTag('test.scenery') as obj:
                    obj.set_model_tag_path('test.model')
                    self.assertEqual(obj.get_variants(), [])
                    self.assertEqual(obj.functions_to_blender(), {})
                    self.assertEqual(obj.attachments_to_blender(None, [], None), [])
                with ObjectTag('test.scenery') as obj:
                    self.assertEqual(obj.get_model_tag_path(), 'test.model')
                for cls, method in [(GlobalsTag, 'get_global_materials'),
                                    (RenderMethodOptionTag, 'read_options'),
                                    (RenderMethodDefinitionTag, 'get_defaults')]:
                    with cls('test.' + cls.tag_ext, tag_must_exist=False) as tag:
                        self.assertFalse(getattr(tag, method)())
                with patch.object(utils, 'get_project', return_value=SimpleNamespace(game='halo4')):
                    with MaterialShaderTag('test.material_shader', tag_must_exist=False) as tag:
                        self.assertEqual(tag.read_parameters_list(), [])
                (Path(root) / 'bad.model').write_bytes(b'not a tag')
                with ModelTag('bad.model', raise_on_error=False, hide_prints=True, always_save=True) as model:
                    self.assertFalse(model.valid)
                    self.assertIsNotNone(model.error)
                self.assertEqual((Path(root) / 'bad.model').read_bytes(), b'not a tag')

    def test_reference_converts_at_legacy_boundary(self):
        from io_scene_foundry.tags.backend import TagReference
        tag = object.__new__(managed_blam.Tag)
        tag.path = TagReference(Path('G:/tags'), 'textures/test', 'bitmap')
        factory = SimpleNamespace(TagFile=lambda: 'file',
                                  TagPath=SimpleNamespace(FromPathAndExtension=lambda p, e: (p, e)))
        with patch.object(managed_blam, 'Tags', factory):
            file, path = tag._get_tag_and_path(True)
        self.assertEqual(file, 'file')
        self.assertEqual(path, ('textures/test', 'bitmap'))


if __name__ == '__main__':
    unittest.main()

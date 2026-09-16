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
from io_scene_foundry.managed_blam.cinematic_lighting import CinematicLightingTag
from io_scene_foundry.managed_blam.globals import GlobalsTag
from io_scene_foundry.managed_blam.render_method_option import RenderMethodOptionTag
from io_scene_foundry.managed_blam.render_method_definition import RenderMethodDefinitionTag
from io_scene_foundry.managed_blam.material_shader import MaterialShaderTag


class WrapperTests(unittest.TestCase):
    def test_native_attachment_records_reach_light_converter(self):
        from unittest.mock import MagicMock
        collection = SimpleNamespace(nwo=SimpleNamespace(), objects=SimpleNamespace(link=MagicMock()))
        parent = SimpleNamespace(children=SimpleNamespace(link=MagicMock()))
        created = []
        def new_object(name, data):
            ob = SimpleNamespace(name=name, data=data, type='EMPTY')
            created.append(ob)
            return ob
        fake_bpy = SimpleNamespace(data=SimpleNamespace(
            collections=SimpleNamespace(new=MagicMock(return_value=collection), remove=MagicMock()),
            objects=SimpleNamespace(new=new_object)))
        marker = SimpleNamespace(nwo=SimpleNamespace(marker_model_group='head'))
        other = SimpleNamespace(nwo=SimpleNamespace(marker_model_group='body'))
        armature = object()
        converter = MagicMock()
        converter.__enter__.return_value.to_blender.return_value = SimpleNamespace(name='lamp')
        with tempfile.TemporaryDirectory() as root, \
             patch.object(utils, 'get_scene_props', return_value=SimpleNamespace(scene_project='test')), \
             patch.object(utils, 'get_project', return_value=SimpleNamespace(game='reach')), \
             patch.object(utils, 'get_tags_path', return_value=root), \
             patch.object(managed_blam, 'mb_init', side_effect=AssertionError('ManagedBlam started')):
            (Path(root) / 'lamp.light').touch()
            with ObjectTag('test.scenery') as obj:
                block = obj.block(obj.object_struct(), 'attachments')
                element = block[block.add()]
                obj.set_reference(element, 'type', 'lamp.light')
                obj.required_field(element, 'marker').set('head')
                obj.required_field(element, 'primary scale').set('power')
                obj.required_field(element, 'secondary scale').set('pulse')
                with patch.dict(sys.modules, {'bpy': fake_bpy}), \
                     patch('io_scene_foundry.managed_blam.light.LightTag', return_value=converter) as factory:
                    attachments = obj.attachments_to_blender(armature, [marker, other], parent)
                self.assertEqual(factory.call_args.kwargs['path'].RelativePathWithExtension, 'lamp.light')
                self.assertTrue(factory.call_args.kwargs['tag_must_exist'])
                self.assertEqual(len(created), 1)
                self.assertIs(created[0].parent, marker)
                self.assertEqual(attachments[0].objects, created)
                self.assertIs(attachments[0].armature, armature)
                self.assertEqual(attachments[0].function_names, {'power', 'pulse'})
                converter.__enter__.return_value.to_blender.assert_called_once_with('power', 'pulse', attachments[0])
                parent.children.link.assert_called_once_with(collection)

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
                    attachments = obj.block(obj.object_struct(), 'attachments')
                    for reference in (None, 'missing.light', 'test.model'):
                        obj.set_reference(attachments[attachments.add()], 'type', reference)
                    # A populated block must not start .NET for missing or unsupported attachments.
                    self.assertEqual(obj.attachments_to_blender(None, [], None), [])
                with ObjectTag('test.scenery') as obj:
                    self.assertEqual(obj.get_model_tag_path(), 'test.model')
                    with ObjectTag('cinematic.scenery') as scenery:
                        scenery.copy_cinematic_object(obj)
                        self.assertEqual(scenery.get_model_tag_path(), 'test.model')
                (Path(root) / 'lamp.light').touch()
                with CinematicLightingTag('test.new_cinematic_lighting') as tag:
                    block = tag.block(tag.tag.root(), 'dynamic lights')
                    element = block[block.add()]
                    tag.set_reference(element, 'light', 'lamp.light')
                    for field, value in [('Direction', 90.), ('Front-Back', 30.), ('Distance', 2.)]:
                        tag.required_field(element, field).set(value)
                    result = tag.to_cinematic_lighting('head', True, 3)
                    self.assertEqual((result.marker, result.persist, result.shot_index), ('head', True, 3))
                    light = result.dynamic_lights[0]
                    self.assertEqual(light.light_tag.RelativePathWithExtension, 'lamp.light')
                    self.assertAlmostEqual(light.matrix.translation.x, 0., places=4)
                    self.assertAlmostEqual(light.matrix.translation.y, 173.20508, places=4)
                    self.assertAlmostEqual(light.matrix.translation.z, 100., places=4)
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

    def test_failed_legacy_object_conversion_does_not_save(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam.object_legacy import LegacyObjectTag
        document = object.__new__(LegacyObjectTag)
        document.tag = MagicMock()
        document.tag_has_changes = True
        document.always_save = True
        document.hide_prints = False
        document.__exit__(RuntimeError, RuntimeError('copy failed'), None)
        document.tag.Save.assert_not_called()
        document.tag.Dispose.assert_called_once()

    def test_failed_legacy_object_conversion_does_not_save(self):
        from unittest.mock import MagicMock
        from io_scene_foundry.managed_blam.object_legacy import LegacyObjectTag
        document = object.__new__(LegacyObjectTag)
        document.tag = MagicMock()
        document.tag_has_changes = True
        document.always_save = True
        document.hide_prints = False
        document.__exit__(RuntimeError, RuntimeError('copy failed'), None)
        document.tag.Save.assert_not_called()
        document.tag.Dispose.assert_called_once()


if __name__ == '__main__':
    unittest.main()

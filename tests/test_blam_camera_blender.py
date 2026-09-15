"""Run in Blender background mode with blam_tags available on sys.path."""
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import bpy
from mathutils import Matrix

ADDON = Path(__file__).resolve().parents[1] / 'blender/addons/io_scene_foundry'
# Isolate the migrated feature from addon registration and ManagedBlam startup.
for name, directory in [('pilot', ADDON), ('pilot.tags', ADDON / 'tags'),
                        ('pilot.managed_blam', ADDON / 'managed_blam')]:
    module = ModuleType(name)
    module.__path__ = [str(directory)]
    sys.modules[name] = module
utils = ModuleType('pilot.utils')
sys.modules['pilot.utils'] = utils
from pilot.managed_blam.camera_track import CameraTrackTag


class Items(list):
    def add(self):
        item = SimpleNamespace(action_tracks=Items())
        self.append(item)
        return item


class CameraTests(unittest.TestCase):
    def test_import_export_and_frame_restoration(self):
        with tempfile.TemporaryDirectory() as root:
            scene_nwo = SimpleNamespace(scene_project='test', animations=Items(),
                                        scale='max', forward_direction='x')
            utils.get_scene_props = lambda: scene_nwo
            utils.get_project = lambda name: SimpleNamespace(game='reach')
            utils.get_tags_path = lambda: root
            utils.get_camera_track_camera = lambda context: None
            utils.rotation_diff_from_forward = lambda a, b: 0
            utils.print_warning = print
            def halo_matrix(matrix):
                result = matrix.copy()
                result.translation /= 100
                return result
            utils.halo_transforms_matrix = halo_matrix
            points = [((1., 2., 3.), (0., 0., 0., 1.)),
                      ((4., 5., 6.), (0., 0., 0., 1.))]
            with CameraTrackTag('input') as tag:
                tag.replace_control_points(points)
            with CameraTrackTag('input', tag_must_exist=True) as tag:
                camera, action = tag.to_blender_animation(bpy.context)
            self.assertEqual(action.frame_end, 2)
            bpy.context.scene.frame_set(1)
            self.assertAlmostEqual(camera.location.x, 100)
            bpy.context.scene.frame_set(2)
            self.assertAlmostEqual(camera.location.x, 400)
            bpy.context.scene.frame_set(7)
            with CameraTrackTag('output') as tag:
                tag.to_tag(bpy.context, scene_nwo.animations[0], camera)
            self.assertEqual(bpy.context.scene.frame_current, 7)
            with CameraTrackTag('output', tag_must_exist=True) as tag:
                for actual, expected in zip(tag.control_points(), points):
                    for a, e in zip(actual[0], expected[0]):
                        self.assertAlmostEqual(a, e, places=4)
                    self.assertAlmostEqual(abs(actual[1][3]), 1, places=4)
            with self.assertRaisesRegex(RuntimeError, 'sampling failed'):
                with CameraTrackTag('failed') as tag:
                    with patch.object(utils, 'halo_transforms_matrix', side_effect=RuntimeError('sampling failed')):
                        tag.to_tag(bpy.context, scene_nwo.animations[0], camera)
            self.assertEqual(bpy.context.scene.frame_current, 7)
            self.assertFalse((Path(root) / 'failed.camera_track').exists())


if __name__ == '__main__':
    unittest.main()

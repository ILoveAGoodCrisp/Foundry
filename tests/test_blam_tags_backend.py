"""Integration tests: run with the built blam_tags wheel installed."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ADDON = Path(__file__).resolve().parents[1] / 'blender/addons/io_scene_foundry'
spec = importlib.util.spec_from_file_location('foundry_tags', ADDON / 'tags/backend.py')
backend = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backend
spec.loader.exec_module(backend)
POINTS = [((1., 2., 3.), (0., 0., 0., 1.)), ((4., 5., 6.), (0., 0., 1., 0.))]


class BackendTests(unittest.TestCase):
    def test_all_title_schemas_roundtrip_and_replace(self):
        for game in ('halo3', 'halo3odst', 'reach', 'halo4', 'halo2a'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                args = dict(tags_root=root, game=game)
                with backend.CameraTrackDocument('camera/test', **args) as doc:
                    doc.replace_control_points(POINTS)
                    self.assertEqual(doc.control_points(), POINTS)
                path = Path(root) / 'camera/test.camera_track'
                original = path.read_bytes()
                with backend.CameraTrackDocument(path, **args) as doc:
                    self.assertEqual(doc.control_points(), POINTS)
                    self.assertEqual(doc.tag.write_to_bytes(), original)
                self.assertEqual(path.read_bytes(), original)
                with backend.CameraTrackDocument(path, **args) as doc:
                    doc.replace_control_points(POINTS[:1])
                with backend.CameraTrackDocument(path, **args) as doc:
                    self.assertEqual(doc.control_points(), POINTS[:1])

    def test_classic_camera_tracks_roundtrip(self):
        for game in ('halo1', 'halo2'):
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with backend.CameraTrackDocument(
                    'test', tags_root=root, game=game,
                ) as document:
                    document.replace_control_points(POINTS)
                with backend.CameraTrackDocument(
                    'test', tags_root=root, game=game, must_exist=True,
                ) as document:
                    self.assertEqual(document.control_points(), POINTS)

    def test_every_schema_can_create_an_mcc_container(self):
        for game in backend.PROFILES:
            with self.subTest(game=game), tempfile.TemporaryDirectory() as root:
                with backend.TagDocument('test.camera_track', tags_root=root, game=game) as doc:
                    self.assertIsNotNone(doc.tag.root().field('control points'))

    def test_exception_does_not_save_new_or_existing_tag(self):
        with tempfile.TemporaryDirectory() as root:
            args = dict(tags_root=root, game='reach')
            path = Path(root) / 'test.camera_track'
            for existing in (False, True):
                if existing:
                    with backend.CameraTrackDocument(path, **args) as doc:
                        doc.replace_control_points(POINTS)
                    original = path.read_bytes()
                with self.assertRaisesRegex(RuntimeError, 'abort'):
                    with backend.CameraTrackDocument(path, **args) as doc:
                        doc.replace_control_points(POINTS[:1])
                        raise RuntimeError('abort')
                self.assertFalse(doc.valid)
                if existing:
                    self.assertEqual(path.read_bytes(), original)
                else:
                    self.assertFalse(path.exists())

    def test_save_error_propagates_and_closes(self):
        with tempfile.TemporaryDirectory() as root:
            doc = backend.CameraTrackDocument('test', tags_root=root, game='reach')
            with patch.object(doc, 'save', side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    with doc:
                        doc.replace_control_points(POINTS)
            self.assertFalse(doc.valid)

    def test_missing_and_outside_paths(self):
        with tempfile.TemporaryDirectory() as root:
            args = dict(tags_root=root, game='reach')
            with self.assertRaises(FileNotFoundError):
                backend.CameraTrackDocument('missing', must_exist=True, **args)
            with self.assertRaises(ValueError):
                backend.CameraTrackDocument('../outside', **args)


if __name__ == '__main__':
    unittest.main()

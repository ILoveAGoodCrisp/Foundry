"""Prevent the extension packager from deleting or omitting the local wheel."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_extension', ROOT / 'blender/addons/io_scene_foundry/build_extension.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class PackagingTests(unittest.TestCase):
    def test_local_wheel_is_required_and_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            wheels = Path(folder)
            for name, version in build.REQUIRED_WHEELS:
                (wheels / f'{name}-{version}-py3-none-any.whl').touch()
            with self.assertRaisesRegex(RuntimeError, 'blam-tags'):
                build.collect_required_wheels(wheels)
            local = wheels / 'blam_tags-0.1.0-cp38-abi3-win_amd64.whl'
            local.touch()
            self.assertIn(local.name, build.collect_required_wheels(wheels))
            build.clear_existing_wheels(wheels)
            self.assertEqual(list(wheels.iterdir()), [local])


if __name__ == '__main__':
    unittest.main()

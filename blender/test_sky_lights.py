"""Classic sky light tag round trips; run with ordinary Python."""

import math
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from zipfile import ZipFile


ADDON = Path(__file__).parent / 'addons/io_scene_foundry'
wheel_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
with ZipFile(next((ADDON / 'wheels').glob('blam_tags-*.whl'))) as archive:
    archive.extractall(wheel_dir.name)
sys.path.insert(0, wheel_dir.name)

package = ModuleType('io_scene_foundry')
package.__path__ = [str(ADDON)]
sys.modules[package.__name__] = package
from io_scene_foundry.tags.sky import MAX_SKY_LIGHTS, SkyDocument, SkyLightRecord


class SkyLightsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        self.tags_root = Path(directory.name)
        self.path = self.tags_root / 'test.sky'

    def document(self, game):
        return SkyDocument(self.path, tags_root=self.tags_root, game=game)

    def test_round_trip_and_existing_fields(self):
        lights = [
            SkyLightRecord((1, 0, 0), (0.8, 0.4, 0.2), 1.1),
            SkyLightRecord((-0.5, -0.5, math.sqrt(0.5)), (0.1, 0.2, 0.3), 0.5),
        ]
        for game in ('halo1', 'halo2'):
            with self.subTest(game=game):
                self.path.unlink(missing_ok=True)
                with self.document(game) as sky:
                    sky.set_sky_lights(lights)
                with self.document(game) as sky:
                    actual = sky.sky_lights()
                    self.assertEqual(len(actual), 2)
                    for expected, result in zip(lights, actual):
                        for a, b in zip(expected.direction, result.direction):
                            self.assertAlmostEqual(a, b, places=5)
                        for a, b in zip(expected.color, result.color):
                            self.assertAlmostEqual(a, b, places=5)
                        self.assertAlmostEqual(expected.power, result.power, places=5)
                    first = sky.block(sky.tag.root(), 'lights')[0]
                    radiosity = (sky.required_field(first, 'radiosity').as_struct()
                                 if game == 'halo1' else sky.block(first, 'radiosity')[0])
                    self.assertTrue(sky.required_field(radiosity, 'flags').get_flag('affects exteriors'))
                    sky.set_sky_lights(lights[:1])
                with self.document(game) as sky:
                    self.assertEqual(len(sky.sky_lights()), 1)

    def test_limit_leaves_tag_unchanged(self):
        for game in ('halo1', 'halo2'):
            with self.subTest(game=game):
                self.path.unlink(missing_ok=True)
                with self.document(game) as sky:
                    with self.assertRaisesRegex(ValueError, 'at most 8'):
                        sky.set_sky_lights([SkyLightRecord((1, 0, 0), (1, 1, 1), 1)] * (MAX_SKY_LIGHTS + 1))
                    self.assertEqual(len(sky.block(sky.tag.root(), 'lights')), 0)
                    sky.set_sky_lights([SkyLightRecord((1, 0, 0), (1, 1, 1), 1)] * MAX_SKY_LIGHTS)
                with self.document(game) as sky:
                    self.assertEqual(len(sky.sky_lights()), MAX_SKY_LIGHTS)


if __name__ == '__main__':
    unittest.main()

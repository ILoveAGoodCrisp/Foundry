"""Run with Blender --background --python-exit-code 1 --python this_file."""
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np

path = Path(__file__).parent / 'addons/io_scene_foundry/legacy/portal_geometry.py'
spec = importlib.util.spec_from_file_location('portal_geometry', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@dataclass
class Vertex:
    position: tuple


def asset(error=.005, version=8200):
    return SimpleNamespace(version=version,
        vertices=[Vertex((15000, -38400, 1000)), Vertex((16000, -38400, 1000)),
                  Vertex((16000, -38400 + error, 2000)), Vertex((15000, -38400, 2000))],
        materials=[SimpleNamespace(name='+portal'), SimpleNamespace(name='wall')],
        triangles=[SimpleNamespace(material=0, vertices=(0, 1, 2)),
                   SimpleNamespace(material=0, vertices=(0, 2, 3))])


class PortalExportTests(unittest.TestCase):
    def test_roundoff_is_planarized_with_bounded_movement(self):
        value = asset()
        before = np.array([v.position for v in value.vertices])
        self.assertEqual(module.planarize_halo1_portals(value), 1)
        after = np.array([v.position for v in value.vertices])
        self.assertLess(np.max(np.linalg.norm(after-before, axis=1)), .025)
        self.assertLess(np.linalg.svd(after-after.mean(axis=0))[1][-1], 1e-8)

    def test_authored_warp_is_not_flattened(self):
        value = asset(error=10)
        before = list(value.vertices)
        self.assertEqual(module.planarize_halo1_portals(value), 0)
        self.assertEqual(value.vertices, before)

    def test_later_games_are_unchanged(self):
        self.assertEqual(module.planarize_halo1_portals(asset(version=8210)), 0)

    def test_structure_vertices_are_not_moved(self):
        value = asset()
        value.triangles.append(SimpleNamespace(material=1, vertices=(0, 1, 2)))
        before = list(value.vertices)
        self.assertEqual(module.planarize_halo1_portals(value), 0)
        self.assertEqual(value.vertices, before)

    def test_exact_plane_is_unchanged(self):
        self.assertEqual(module.planarize_halo1_portals(asset(error=0)), 0)


if __name__ == '__main__':
    result = unittest.main(argv=[__file__], exit=False).result
    if not result.wasSuccessful():
        raise AssertionError('Portal export regression tests failed')

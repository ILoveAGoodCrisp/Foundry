"""Run with Python; no Blender installation required."""
import importlib.util
from pathlib import Path
from math import sqrt
import unittest

path = Path(__file__).parent / 'addons/io_scene_foundry/tags/collision_patches.py'
spec = importlib.util.spec_from_file_location('collision_patches', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# c10_interiorb's WRL-marked quad: its triangle normals straddle X/Z dominance.
POINTS = [(-20.147918701171875, 80.25456237792969, .6285809874534607),
          (-20.152700424194336, 79.52304077148438, .6285809874534607),
          (-19.84789276123047, 79.52304077148438, .9333809614181519),
          (-19.843917846679688, 80.25456237792969, .9333809614181519)]
FACES = [(0, 1, 2), (0, 2, 3), (1, 0, 3), (1, 3, 2)]


def record(points, prop='collision'):
    a, b, c = points[:3]
    u = [b[i]-a[i] for i in range(3)]
    v = [c[i]-a[i] for i in range(3)]
    n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
    length = sqrt(sum(x*x for x in n))
    return tuple(points), tuple(x/length for x in n), prop


class CollisionPatchTests(unittest.TestCase):
    def test_c10_warped_quad_different_diagonals(self):
        records = [record([POINTS[i] for i in face]) for face in FACES]
        matches = module.opposite_patches(records)
        self.assertEqual(len(matches), 1)
        keep, remove = matches[0]
        self.assertEqual({frozenset(keep), frozenset(remove)}, {frozenset((0, 1)), frozenset((2, 3))})

    def test_distinct_face_properties_are_preserved(self):
        records = [record([POINTS[i] for i in face], 'a' if j < 2 else 'b') for j, face in enumerate(FACES)]
        self.assertEqual(module.opposite_patches(records), [])

    def test_offset_surface_is_preserved(self):
        records = [record([tuple(p[k] + (.01 if j >= 2 else 0) for k in range(3))
                           for i in face for p in [POINTS[i]]]) for j, face in enumerate(FACES)]
        self.assertEqual(module.opposite_patches(records), [])

    def test_same_facing_surfaces_are_not_two_sided(self):
        records = [record([POINTS[i] for i in (face if j < 2 else tuple(reversed(face)))])
                   for j, face in enumerate(FACES)]
        self.assertEqual(module.opposite_patches(records), [])

    def test_planar_quad_still_matches_once(self):
        points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        records = [record([points[i] for i in face]) for face in FACES]
        self.assertEqual(len(module.opposite_patches(records)), 1)


if __name__ == '__main__':
    unittest.main()

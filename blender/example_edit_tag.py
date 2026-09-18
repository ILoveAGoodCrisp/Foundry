"""Run with the blam_tags wheel installed: python example_edit_tag.py TAG MASS.

Edits the stored mass of the first rigid body in an existing physics_model tag.
Engine use of the value also depends on body flags. Try it on a working copy.
"""
import argparse
from pathlib import Path
from math import isfinite
from blam_tags import TagFile


def update_mass(path, mass):
    if not isfinite(mass) or mass < 0:
        raise ValueError('Mass must be finite and non-negative')
    path = Path(path)
    tag = TagFile.read(path)
    bodies = tag.root().field('rigid bodies').as_block()
    if not len(bodies):
        raise ValueError('This tag has no rigid bodies')
    field = bodies[0].field('mass')
    previous = field.value
    field.set(mass)
    tag.write_atomic(path)
    return previous


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    parser.add_argument('mass', type=float)
    args = parser.parse_args()
    print(f'Mass: {update_mass(args.path, args.mass)} -> {args.mass}')

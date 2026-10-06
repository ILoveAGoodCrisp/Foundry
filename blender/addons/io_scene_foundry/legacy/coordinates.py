"""Coordinate changes that preserve legacy structure boundaries."""
from math import pi

from mathutils import Matrix


def axis_rotation(angle):
    """Use exact signed axis permutations for Foundry's forward directions.

    Trigonometric roundoff at a quarter turn can become a visible gap when
    applied to large BSP translations, even after the inverse axis change.
    """
    turns = round(angle / (pi / 2))
    if abs(angle - turns * (pi / 2)) > 1e-10:
        return Matrix.Rotation(angle, 4, 'Z')
    cosine, sine = ((1, 0), (0, 1), (-1, 0), (0, -1))[turns % 4]
    return Matrix(((cosine, -sine, 0, 0), (sine, cosine, 0, 0),
                   (0, 0, 1, 0), (0, 0, 0, 1)))

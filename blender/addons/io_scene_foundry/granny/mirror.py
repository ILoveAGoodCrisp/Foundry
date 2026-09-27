"""Reflect GR2 export data across Y before Granny's basis conversion.

Use M T M for transforms and M v for geometry, as in the legacy exporters.
Keep source arrays untouched: linked meshes and PCA frames share them.
"""

from mathutils import Matrix
import numpy as np


REFLECTION = Matrix.Diagonal((1.0, -1.0, 1.0, 1.0))


def mirror_matrix(matrix):
    return REFLECTION @ matrix @ REFLECTION


def mirror_vectors(values):
    result = values.copy()
    result[:, 1] *= -1
    return result


def mirror_indices(indices):
    return indices.reshape(-1, 3)[:, (0, 2, 1)].reshape(-1).copy()


def mirror_tracks(tracks):
    """Reflect position/quaternion/scale-shear sample triplets in place."""
    for i in range(0, len(tracks), 3):
        positions = np.ctypeslib.as_array(tracks[i]).reshape(-1, 3)
        orientations = np.ctypeslib.as_array(tracks[i + 1]).reshape(-1, 4)
        scales = np.ctypeslib.as_array(tracks[i + 2]).reshape(-1, 9)
        positions[:, 1] *= -1
        orientations[:, (0, 2)] *= -1
        scales[:, (1, 3, 5, 7)] *= -1

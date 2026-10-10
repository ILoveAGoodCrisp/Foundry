"""Per-vertex compression/stretch using the H4 Maya tension-node convention.

Use the evaluated rest mesh's edges, before Foundry adds triangulation. Each
endpoint receives its edge's positive shortening and lengthening separately,
normalized by the sum of its incident rest lengths. Maya's default gain is 3.
RGB is (compression, 0, stretch); values are linear floats and are not clamped.
"""
import numpy as np


class TensionBasis:
    def __init__(self, positions, edges):
        positions = np.asarray(positions, dtype=np.float64)
        edges = np.asarray(edges, dtype=np.int32).reshape(-1, 2)
        if positions.ndim != 2 or positions.shape[1] != 3 or not np.isfinite(positions).all():
            raise ValueError('PCA tension requires finite three-dimensional rest positions')
        if edges.size and (edges.min() < 0 or edges.max() >= len(positions)):
            raise ValueError('PCA tension has an invalid reference edge')
        self.vertex_count = len(positions)
        self.edges = edges.copy()
        self.endpoints = self.edges.ravel()
        self.rest_lengths = np.linalg.norm(positions[edges[:, 1]] - positions[edges[:, 0]], axis=1)
        self.divisors = np.bincount(self.endpoints, weights=np.repeat(self.rest_lengths, 2),
                                   minlength=self.vertex_count)

    @classmethod
    def from_mesh(cls, mesh):
        positions = np.empty((len(mesh.vertices), 3), dtype=np.float64)
        edges = np.empty((len(mesh.edges), 2), dtype=np.int32)
        mesh.vertices.foreach_get('co', positions.ravel())
        mesh.edges.foreach_get('vertices', edges.ravel())
        return cls(positions, edges)

    def calculate(self, positions):
        positions = np.asarray(positions, dtype=np.float64)
        if positions.shape != (self.vertex_count, 3) or not np.isfinite(positions).all():
            raise ValueError('PCA tension sample does not match its reference vertices')
        lengths = np.linalg.norm(positions[self.edges[:, 1]] - positions[self.edges[:, 0]], axis=1)
        difference = lengths - self.rest_lengths
        result = np.zeros((self.vertex_count, 3), dtype=np.float64)
        for channel, change in ((0, -difference), (2, difference)):
            sums = np.bincount(self.endpoints, weights=np.repeat(np.maximum(change, 0), 2),
                               minlength=self.vertex_count)
            # Isolated vertices and wholly degenerate rest edges remain neutral.
            np.divide(3.0 * sums, self.divisors, out=result[:, channel], where=self.divisors > 0)
        return result.astype(np.float32)

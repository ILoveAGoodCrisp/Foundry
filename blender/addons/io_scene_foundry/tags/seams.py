"""Structure seam geometry read directly from native tag fields."""
from dataclasses import dataclass
from math import isfinite
from .backend import TagDocument


@dataclass(frozen=True)
class SeamGeometry:
    index: int
    vertices: tuple
    triangles: tuple


class StructureSeamsDocument(TagDocument):
    tag_ext = 'structure_seams'

    def matches_triangles(self, triangles):
        from ..legacy.seam_geometry import seam_surface

        original_points = []
        for element in self.block(self.tag.root(), 'seams'):
            original = self.required_field(element, 'original').as_struct()
            original_points.extend(tuple(self.value(p, 'original vertex').to_array())
                                   for p in self.block(original, 'original vertices'))
        compiled = [tuple(seam.vertices[index] for index in triangle)
                    for seam in self.read_geometry() for triangle in seam.triangles]
        return seam_surface(triangles) == seam_surface(compiled, original_points)

    def read_geometry(self):
        result = []
        for index, element in enumerate(self.block(self.tag.root(), 'seams')):
            final = self.required_field(element, 'final').as_struct()
            vertices = tuple(tuple(self.value(p, 'final point').to_array())
                             for p in self.block(final, 'points'))
            triangles = tuple(tuple(self.value(t, f'final point{i}') for i in range(3))
                              for t in self.block(final, 'triangles'))
            if any(not isfinite(v) for point in vertices for v in point):
                raise ValueError(f'Seam {index} has non-finite coordinates')
            if any(v < 0 or v >= len(vertices) for triangle in triangles for v in triangle):
                raise ValueError(f'Seam {index} has an invalid triangle point index')
            if any(len(set(triangle)) != 3 for triangle in triangles):
                raise ValueError(f'Seam {index} has a degenerate triangle')
            result.append(SeamGeometry(index, vertices, triangles))
        return result

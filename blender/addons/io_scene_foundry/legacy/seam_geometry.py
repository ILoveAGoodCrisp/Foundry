"""Compare authored ASS seams with native Tool geometry, without a build cache."""
from collections import Counter, defaultdict
from math import sqrt
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .ass_format import ASS
from ..seam_materials import seam_material_name


@contextmanager
def fresh_structure_seams(path):
    """Regenerate seams without Tool reusing old planes; roll back failures."""
    path = Path(path)
    backup = path.with_name(path.name + '.rebuild-' + uuid4().hex) if path.is_file() else None
    if backup is not None:
        path.rename(backup)
    try:
        yield
    except BaseException:
        path.unlink(missing_ok=True)
        if backup is not None:
            backup.rename(path)
        raise
    else:
        if backup is not None:
            backup.unlink()


@contextmanager
def structure_seam_sources(sources):
    """Expose only BSP sources to Tool's folder-wide seam compilation.

    Design meshes contribute planes even without seam faces. Keep their ASS
    files out of this pass, then restore them for the structure-design import.
    """
    allowed = {Path(source).resolve() for source in sources}
    moved = []
    try:
        for directory in sorted({source.parent for source in allowed}):
            for source in directory.iterdir():
                if source.suffix.casefold() != '.ass' or source.resolve() in allowed or not source.is_file():
                    continue
                temporary = source.with_name(source.name + '.seams-' + uuid4().hex)
                source.rename(temporary)
                moved.append((source, temporary))
        yield
    finally:
        for source, temporary in reversed(moved):
            temporary.rename(source)


def _transform_point(point, transform):
    x, y, z, w = transform.rotation
    norm = sqrt(x*x + y*y + z*z + w*w)
    x, y, z, w = (v / norm for v in (x, y, z, w))
    a, b, c = (p * s for p, s in zip(point, transform.scale))
    return (
        (1-2*y*y-2*z*z)*a + (2*x*y-2*z*w)*b + (2*x*z+2*y*w)*c + transform.translation[0],
        (2*x*y+2*z*w)*a + (1-2*x*x-2*z*z)*b + (2*y*z-2*x*w)*c + transform.translation[1],
        (2*x*z-2*y*w)*a + (2*y*z+2*x*w)*b + (1-2*x*x-2*y*y)*c + transform.translation[2],
    )


def ass_seam_triangles(path):
    """Only instantiated faces count; unused materials and seam sealers do not."""
    asset = ASS.from_file(path)
    materials = {index for index, material in enumerate(asset.materials)
                 if seam_material_name(material.name) or material.name.strip().casefold() == '+seam'}
    if not materials:
        return []
    triangles = []
    for instance in asset.instances:
        if instance.geometry < 0:
            continue
        geometry = asset.geometries[instance.geometry]
        faces = [face for face in geometry.triangles if face.material in materials]
        if not faces:
            continue
        transforms = [instance.pivot, instance.local]
        parent = instance.parent
        while parent != -1:
            transforms.append(asset.instances[parent].local)
            parent = asset.instances[parent].parent
        points = {}
        for index in {index for face in faces for index in face.vertices}:
            point = geometry.vertices[index].position
            for transform in transforms:
                point = _transform_point(point, transform)
            # Tool's native coordinates are 1/100 of ASS coordinates.
            points[index] = tuple(v / 100 for v in point)
        triangles.extend(tuple(points[index] for index in face.vertices) for face in faces)
    return triangles


def seam_surface(triangles, original_points=None):
    """Ignore winding, duplicate sides and coplanar triangulation diagonals.

    Keep authored points as well as planar boundaries: Tool uses the original
    points to identify seams. Rounding only absorbs native float32 noise. If
    Tool has substantially rebuilt a surface, equality is deliberately not
    assumed and the caller regenerates it.
    """
    def point_key(point):
        return tuple(round(v, 5) for v in point)

    faces = {tuple(sorted(point_key(point) for point in face)) for face in triangles}
    planes = defaultdict(Counter)
    for a, b, c in faces:
        u = tuple(y-x for x, y in zip(a, b))
        v = tuple(y-x for x, y in zip(a, c))
        normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        length = sqrt(sum(n*n for n in normal))
        if length == 0:
            raise ValueError('Degenerate seam triangle')
        normal = tuple(n / length for n in normal)
        if next(n for n in normal if abs(n) > 1e-8) < 0:
            normal = tuple(-n for n in normal)
        plane = tuple(round(n, 5) for n in (*normal, sum(n*p for n, p in zip(normal, a))))
        planes[plane].update((tuple(sorted(edge)) for edge in ((a,b), (b,c), (c,a))))
    points = (frozenset(point_key(point) for point in original_points)
              if original_points is not None else frozenset(point for face in faces for point in face))
    boundaries = frozenset((plane, edge, count) for plane, edges in planes.items()
                           for edge, count in edges.items() if count != 2)
    return points, boundaries

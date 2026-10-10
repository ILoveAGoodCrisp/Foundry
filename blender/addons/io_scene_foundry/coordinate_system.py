"""Foundry's authoring units and Z-up coordinate conventions.

Geometry files use legacy authoring units; tag positions use world units.
Object scale is dimensionless. Placement conversion scales translation, while
geometry conversion scales the actual points (or a complete geometry matrix).
"""
from dataclasses import dataclass
from math import pi

from mathutils import Matrix, Vector

METERS_PER_HALO_UNIT = 0.03048
METERS_PER_WORLD_UNIT = 3.048
WORLD_UNITS_PER_METER = 1 / METERS_PER_WORLD_UNIT
FORWARD_ANGLES = {'x': 0., 'y': pi / 2, 'x-': pi, 'y-': -pi / 2}
FORWARD_ITEMS = (
    ('y-', '-Y', 'Scene forward is negative Y'),
    ('y', 'Y', 'Scene forward is positive Y'),
    ('x-', '-X', 'Scene forward is negative X'),
    ('x', 'X', 'Scene forward is positive X'),
)


def axis_rotation(angle):
    """Exact signed axis permutations avoid gaps in large BSP coordinates."""
    turns = round(angle / (pi / 2))
    if abs(angle - turns * (pi / 2)) > 1e-10:
        return Matrix.Rotation(angle, 4, 'Z')
    cosine, sine = ((1, 0), (0, 1), (-1, 0), (0, -1))[turns % 4]
    return Matrix(((cosine, -sine, 0, 0), (sine, cosine, 0, 0),
                   (0, 0, 1, 0), (0, 0, 0, 1)))


def rotation_between(old_forward, new_forward):
    angle = FORWARD_ANGLES[new_forward] - FORWARD_ANGLES[old_forward]
    return (angle + pi) % (2 * pi) - pi


def placement_matrix(matrix, factor, angle=0., *, marker=False):
    """Convert a placement; preserve its dimensionless scale components."""
    result = matrix.copy()
    result.translation *= factor
    result = axis_rotation(angle) @ result
    return local_marker_axes(result, angle) if marker else result


def geometry_matrix(matrix, factor, angle=0., *, marker=False):
    """Convert a complete geometry matrix, including its linear dimensions."""
    result = axis_rotation(angle) @ Matrix.Scale(factor, 4) @ matrix
    return local_marker_axes(result, angle) if marker else result


def local_marker_axes(matrix, angle):
    return matrix @ axis_rotation(-angle)


@dataclass(frozen=True)
class CoordinateSystem:
    scale: str = 'blender'
    forward: str = 'y-'

    def __post_init__(self):
        if self.scale not in {'blender', 'max'} or self.forward not in FORWARD_ANGLES:
            raise ValueError(f'Invalid scene convention: {self.scale}, {self.forward}')

    @classmethod
    def from_scene(cls, scene_nwo):
        return cls(scene_nwo.scale, scene_nwo.forward_direction)

    @property
    def meters_per_unit(self):
        return 1. if self.scale == 'blender' else METERS_PER_HALO_UNIT

    @property
    def from_halo_scale(self):
        return METERS_PER_HALO_UNIT / self.meters_per_unit

    @property
    def to_halo_scale(self):
        return 1 / self.from_halo_scale

    @property
    def to_world_scale(self):
        return self.meters_per_unit / METERS_PER_WORLD_UNIT

    @property
    def from_halo_rotation(self):
        return rotation_between('x', self.forward)

    @property
    def to_halo_rotation(self):
        return rotation_between(self.forward, 'x')

    def conversion_to(self, destination):
        return (self.meters_per_unit / destination.meters_per_unit,
                rotation_between(self.forward, destination.forward))

    def display_scale(self, world_units=False):
        return self.to_world_scale if world_units else self.meters_per_unit

    def distance(self, value, *, world_units=False):
        meters = METERS_PER_WORLD_UNIT if world_units else METERS_PER_HALO_UNIT
        return float(value) * meters / self.meters_per_unit

    def position(self, values, *, world_units=False):
        return self.direction(values) * self.distance(1, world_units=world_units)

    def direction(self, values):
        return axis_rotation(self.from_halo_rotation).to_3x3() @ Vector(values)

    def placement(self, matrix, *, marker=False, root=True):
        return placement_matrix(matrix, self.from_halo_scale,
                                self.from_halo_rotation if root else 0., marker=marker)

    def joint_frame(self, matrix, *, root=True):
        return self.placement(matrix, root=root)

    def bone_matrix(self, matrix, *, root=False):
        return self.placement(matrix, root=root)

from mathutils import Euler, Matrix, Quaternion, Vector

from . import utils, marker_axis
from .coordinate_system import CoordinateSystem, axis_rotation, geometry_matrix, placement_matrix


def scale_factor(scene_nwo=None) -> float:
    scene_nwo = scene_nwo or utils.get_scene_props()
    return CoordinateSystem.from_scene(scene_nwo).from_halo_scale


def rotation(scene_nwo=None) -> float:
    scene_nwo = scene_nwo or utils.get_scene_props()
    return CoordinateSystem.from_scene(scene_nwo).from_halo_rotation


def rotation_matrix(scene_nwo=None) -> Matrix:
    return axis_rotation(rotation(scene_nwo))


def scale_matrix(scene_nwo=None) -> Matrix:
    return Matrix.Scale(scale_factor(scene_nwo), 4)


def signature(scene_nwo=None) -> tuple[float, float]:
    return scale_factor(scene_nwo), rotation(scene_nwo)


def distance(value: float, unit_scale: float = 100.0, scene_nwo=None) -> float:
    return float(value) * unit_scale * scale_factor(scene_nwo)


def position(values, unit_scale: float = 100.0, scene_nwo=None, rotate=True) -> Vector:
    vector = Vector(values) * unit_scale * scale_factor(scene_nwo)
    if rotate:
        vector = rotation_matrix(scene_nwo) @ vector
    return vector


def direction(values, scene_nwo=None) -> Vector:
    return rotation_matrix(scene_nwo).to_3x3() @ Vector(values)


def quaternion(value, scene_nwo=None) -> Quaternion:
    quat = value.copy() if isinstance(value, Quaternion) else Quaternion(value)
    quat.rotate(rotation_matrix(scene_nwo))
    return quat


def matrix_from_axes(forward, left, up, pos, unit_scale: float = 100.0, scene_nwo=None, rotate=True) -> Matrix:
    loc = Vector(pos) * unit_scale * scale_factor(scene_nwo)
    matrix = Matrix((
        (forward[0], left[0], up[0], loc[0]),
        (forward[1], left[1], up[1], loc[1]),
        (forward[2], left[2], up[2], loc[2]),
        (0, 0, 0, 1),
    ))
    if rotate:
        matrix = rotation_matrix(scene_nwo) @ matrix
    return matrix


def object_matrix(matrix: Matrix, scene_nwo=None, rotate=True) -> Matrix:
    return placement_matrix(matrix, scale_factor(scene_nwo), rotation(scene_nwo) if rotate else 0.)


def cinematic_anchor_matrix(position, facing, scene_nwo=None) -> Matrix:
    """A native cutscene flag (world units/radians) moves scenery into shot space."""
    yaw, pitch, roll = facing
    matrix = Matrix.LocRotScale(Vector(position) * 100,
        Euler((roll, -pitch, yaw), 'XYZ'), Vector((1, 1, 1)))
    # Scenery already has Blender axes: change both sides of the basis.
    return object_matrix(matrix.inverted_safe(), scene_nwo) @ rotation_matrix(scene_nwo).inverted_safe()


def marker_local_axes(matrix: Matrix, scene_nwo=None) -> Matrix:
    """Convert Halo local marker axes to the scene forward convention."""
    return marker_axis.local_axes(matrix, rotation(scene_nwo))


def marker_matrix(matrix: Matrix, scene_nwo=None) -> Matrix:
    return placement_matrix(matrix, scale_factor(scene_nwo), rotation(scene_nwo), marker=True)


def transform_matrix(matrix: Matrix, scene_nwo=None, rotate=True) -> Matrix:
    return geometry_matrix(matrix, scale_factor(scene_nwo), rotation(scene_nwo) if rotate else 0.)


def loc_rot_scale(loc, rot, scale, unit_scale: float = 100.0, scene_nwo=None, rotate=True) -> Matrix:
    matrix = Matrix.LocRotScale(Vector(loc) * unit_scale, rot, scale)
    matrix = scale_matrix(scene_nwo) @ matrix
    if rotate:
        matrix = rotation_matrix(scene_nwo) @ matrix
    return matrix


def armature_bone_matrix(matrix: Matrix, scene_nwo=None, root=False) -> Matrix:
    return CoordinateSystem.from_scene(scene_nwo or utils.get_scene_props()).bone_matrix(matrix, root=root)


def mesh_matrix(scene_nwo=None) -> Matrix:
    return scale_matrix(scene_nwo)

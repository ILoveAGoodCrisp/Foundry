from mathutils import Matrix, Quaternion, Vector

from .. import utils


def scale_factor(scene_nwo=None) -> float:
    scene_nwo = scene_nwo or utils.get_scene_props()
    return 0.03048 if scene_nwo.scale == 'blender' else 1.0


def rotation(scene_nwo=None) -> float:
    scene_nwo = scene_nwo or utils.get_scene_props()
    return utils.rotation_diff_from_forward('x', scene_nwo.forward_direction)


def rotation_matrix(scene_nwo=None) -> Matrix:
    return Matrix.Rotation(rotation(scene_nwo), 4, Vector((0, 0, 1)))


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
    result = matrix.copy()
    result.translation = result.translation * scale_factor(scene_nwo)
    if rotate:
        result = rotation_matrix(scene_nwo) @ result
    return result


def keep_marker_axis(matrix: Matrix, scene_nwo=None) -> Matrix:
    scene_nwo = scene_nwo or utils.get_scene_props()
    if not scene_nwo.maintain_marker_axis:
        return matrix
    return matrix @ Matrix.Rotation(-rotation(scene_nwo), 4, 'Z')


def marker_matrix(matrix: Matrix, scene_nwo=None) -> Matrix:
    return keep_marker_axis(object_matrix(matrix, scene_nwo), scene_nwo)


def transform_matrix(matrix: Matrix, scene_nwo=None, rotate=True) -> Matrix:
    result = scale_matrix(scene_nwo) @ matrix
    if rotate:
        result = rotation_matrix(scene_nwo) @ result
    return result


def loc_rot_scale(loc, rot, scale, unit_scale: float = 100.0, scene_nwo=None, rotate=True) -> Matrix:
    matrix = Matrix.LocRotScale(Vector(loc) * unit_scale, rot, scale)
    matrix = scale_matrix(scene_nwo) @ matrix
    if rotate:
        matrix = rotation_matrix(scene_nwo) @ matrix
    return matrix


def armature_bone_matrix(matrix: Matrix, scene_nwo=None, root=False) -> Matrix:
    result = matrix.copy()
    result.translation = result.translation * scale_factor(scene_nwo)
    if root:
        result = rotation_matrix(scene_nwo) @ result
    return result


def mesh_matrix(scene_nwo=None) -> Matrix:
    return scale_matrix(scene_nwo)

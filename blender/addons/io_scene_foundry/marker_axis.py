"""Markers use the scene's forward convention for their local reference axes.

Geometry changes world basis on the left. A marker also changes its local
basis on the right, so an already converted collection can be instanced by it.
Joint frames are explicit physical coordinate systems, not marker references.
"""
from .coordinate_system import axis_rotation, local_marker_axes


LEGACY_CONSTRAINT_MARKER_TYPES = {
    "_connected_geometry_marker_type_physics_hinge_constraint",
    "_connected_geometry_marker_type_physics_socket_constraint",
}


def is_joint_frame(marker_type, game):
    return (game in {'halo2', 'halo3', 'halo3odst'}
            and marker_type in LEGACY_CONSTRAINT_MARKER_TYPES)


def uses_scene_axes(ob, game):
    if ob.type != 'EMPTY' or ob.empty_display_type == 'IMAGE' or ob.nwo.is_frame:
        return False
    marker_type = ob.nwo.marker_type
    if marker_type == '_connected_geometry_marker_type_physics_constraint':
        marker_type = ob.nwo.physics_constraint_type
    return not is_joint_frame(marker_type, game)


def local_axes(matrix, rotation):
    """Convert local reference axes after the world basis has been converted."""
    return local_marker_axes(matrix, rotation)


def change_basis(matrix, rotation):
    """Convert both the world and local reference basis of a marker."""
    return local_axes(axis_rotation(rotation) @ matrix, rotation)

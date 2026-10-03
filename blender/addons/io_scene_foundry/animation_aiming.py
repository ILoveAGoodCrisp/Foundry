"""Legacy aiming-screen policy, shared by import and pose generation."""
from math import isfinite


LEGACY_AIMING_MODE_ITEMS = (
    ('AUTO', 'Auto', 'Use source circular aiming metadata, otherwise the authored yaw coverage'),
    ('PLANAR', 'Planar', 'Add aim/look wrap events beyond 90 degrees'),
    ('CIRCULAR', 'Circular', 'Allow aim/look screens to rotate freely without wrap events'),
)


def blend_screen_yaw_span(screen) -> float:
    """Measure authored degrees before rotations are reduced to matrices."""
    right = -screen.right_yaw_per_frame * screen.right_frame_count
    left = screen.left_yaw_per_frame * screen.left_frame_count
    if not all(isfinite(value) for value in (right, left)):
        return 0.0
    return max(right, left, 0.0) - min(right, left, 0.0)


def aiming_screen_is_planar(wrap_mode='AUTO', circular_aiming=None, yaw_span=0.0) -> bool:
    """Explicit choices and known unit metadata take precedence over coverage."""
    if wrap_mode == 'PLANAR':
        return True
    if wrap_mode == 'CIRCULAR':
        return False
    if circular_aiming is not None:
        return not circular_aiming
    return not (isfinite(yaw_span) and yaw_span >= 360.0 - 1e-3)


def animation_aiming_is_planar(animation, screen=None, *, circular_aiming=None,
                              wrap_mode=None) -> bool:
    """Use retained metadata when reconverting or generating derived screens."""
    if circular_aiming is None:
        circular_aiming = {'PLANAR': False, 'CIRCULAR': True}.get(
            getattr(animation, 'pose_overlay_aiming_source', 'UNKNOWN'))
    span = (blend_screen_yaw_span(screen) if screen is not None
            else getattr(animation, 'pose_overlay_yaw_span', 0.0))
    return aiming_screen_is_planar(
        wrap_mode or getattr(animation, 'pose_overlay_wrap_mode', 'AUTO'),
        circular_aiming, span)

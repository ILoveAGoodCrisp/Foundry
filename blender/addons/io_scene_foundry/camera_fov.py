"""Halo 3/ODST observer and cinematic projection, with angles in radians.

The observer uses 4:3, then render_camera_build scales the vertical angle by
0.785. Cinematic widescreen correction restores the 4:3 horizontal extent;
ordinary debug/game cameras instead use the actual viewport aspect.
"""
from math import atan, degrees, isfinite, pi, radians, tan
from pathlib import Path

H3_CAMERA_GAMES = frozenset({'halo3', 'halo3odst'})
OBSERVER_ASPECT = 4.0 / 3.0
RENDER_FOV_SCALE = 0.785
MIN_OBSERVER_HFOV = radians(1.0)
MAX_OBSERVER_HFOV = radians(150.0)
H3_CINEMATIC_FILM_APERTURE = 76.0


def _positive(*values):
    if not all(isfinite(value) and value > 0 for value in values):
        raise ValueError('Camera lens, film aperture and aspect must be finite and positive')


def render_hfov_from_observer_hfov(hfov: float, aspect: float) -> float:
    """Final horizontal view of an ordinary H3/ODST camera command."""
    _positive(aspect)
    if not isfinite(hfov):
        raise ValueError('Camera field of view must be finite')
    hfov = min(max(hfov, MIN_OBSERVER_HFOV), MAX_OBSERVER_HFOV)
    half_vertical = atan(tan(hfov / 2) / OBSERVER_ASPECT) * RENDER_FOV_SCALE
    return 2 * atan(aspect * tan(half_vertical))


def observer_hfov_from_render_hfov(hfov: float, aspect: float) -> float:
    """Invert ordinary camera projection before the engine's command clamp."""
    _positive(aspect)
    if not isfinite(hfov) or not 0 < hfov < pi:
        raise ValueError('Camera field of view must be between 0 and 180 degrees')
    half_vertical = atan(tan(hfov / 2) / aspect) / RENDER_FOV_SCALE
    if half_vertical >= pi / 2:
        raise ValueError('Camera field of view exceeds the Halo projection range')
    return 2 * atan(OBSERVER_ASPECT * tan(half_vertical))


MIN_CINEMATIC_HFOV = render_hfov_from_observer_hfov(MIN_OBSERVER_HFOV, OBSERVER_ASPECT)
MAX_CINEMATIC_HFOV = render_hfov_from_observer_hfov(MAX_OBSERVER_HFOV, OBSERVER_ASPECT)


def final_hfov_from_tag_focal(focal_length: float, film_aperture: float = H3_CINEMATIC_FILM_APERTURE) -> float:
    """Rendered cinematic horizontal FOV, including the observer's 1–150° clamp.

Per-frame horizontal FOV/aperture metadata does not participate in playback.
This describes the default cinematic correction and the authored 16:9 frame.
"""
    _positive(film_aperture)
    if not isfinite(focal_length):
        raise ValueError('Camera focal length must be finite')
    # Native float division by zero produces +infinity, then the observer
    # clamps its 180° result. Preserve that for empty/default tag records.
    tag_hfov = pi if focal_length == 0 else 2 * atan(film_aperture / (2 * focal_length))
    return render_hfov_from_observer_hfov(tag_hfov, OBSERVER_ASPECT)


def tag_focal_from_final_hfov(hfov: float, film_aperture: float = H3_CINEMATIC_FILM_APERTURE) -> float:
    """Focal length for a representable cinematic horizontal FOV."""
    _positive(film_aperture)
    if not isfinite(hfov) or not MIN_CINEMATIC_HFOV <= hfov <= MAX_CINEMATIC_HFOV:
        raise ValueError(f'Cinematic camera projection range is {degrees(MIN_CINEMATIC_HFOV):.3f}–'
                         f'{degrees(MAX_CINEMATIC_HFOV):.3f} degrees horizontally')
    tag_hfov = observer_hfov_from_render_hfov(hfov, OBSERVER_ASPECT)
    return film_aperture / (2 * tan(tag_hfov / 2))


def default_cinematic_film_aperture(game: str) -> float:
    if game in H3_CAMERA_GAMES:
        return H3_CINEMATIC_FILM_APERTURE
    return 22.5 if game in {'halo4', 'halo2a', 'corinth'} else 45.0


def read_cinematic_film_aperture(game: str, globals_path, tag_factory, warn) -> float:
    """Prefer project globals; use the game's default if unavailable or invalid.

The supplied tag factory keeps this module independent of Blender/tag handles.
"""
    aperture = None
    try:
        if Path(globals_path).is_file():
            with tag_factory(path=globals_path) as tag:
                aperture = tag.cinematic_film_aperture()
    except (OSError, RuntimeError, ValueError, TypeError):
        pass
    if aperture is not None and isfinite(aperture) and aperture > 0:
        return aperture
    fallback = default_cinematic_film_aperture(game)
    warn(f'Failed to read a valid globals cinematic film aperture. Using {fallback:g} mm for {game}')
    return fallback

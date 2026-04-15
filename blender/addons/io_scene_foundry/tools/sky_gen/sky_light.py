from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

TWO_PI = 2.0 * math.pi
HALF_PI = 0.5 * math.pi
EPSILON = 1.0e-5
NORMALIZATION_FACTOR = 0.0175
SUN_SOLID_ANGLE = 0.00001 * TWO_PI
MIN_SPLITABLE_BOX_SIZE = 4
LUMINANCE_WEIGHTS = np.array((0.212656, 0.715158, 0.0721856), dtype=np.float32)
RGB_TO_XYZ = np.array(
    (
        (0.412424, 0.357579, 0.180464),
        (0.212656, 0.715158, 0.0721856),
        (0.0193324, 0.119193, 0.950444),
    ),
    dtype=np.float32,
)
XYZ_TO_RGB = np.array(
    (
        (3.240479, -1.537150, -0.498535),
        (-0.969256, 1.875991, 0.041556),
        (0.055648, -0.204043, 1.057311),
    ),
    dtype=np.float32,
)

# Distribution coefficients for the luminance(Y) distribution function
YDC = np.array(
    (
        (0.1787, -1.4630),
        (-0.3554, 0.4275),
        (-0.0227, 5.3251),
        (0.1206, -2.5771),
        (-0.0670, 0.3703),
    ),
    dtype=np.float32,
)

# Distribution coefficients for the x distribution function
XDC = np.array(
    (
        (-0.0193, -0.2592),
        (-0.0665, 0.0008),
        (-0.0004, 0.2125),
        (-0.0641, -0.8989),
        (-0.0033, 0.0452),
    ),
    dtype=np.float32,
)

# Distribution coefficients for the y distribution function
Y_CHROMA_DC = np.array(
    (
        (-0.0167, -0.2608),
        (-0.0950, 0.0092),
        (-0.0079, 0.2102),
        (-0.0441, -1.6537),
        (-0.0109, 0.0529),
    ),
    dtype=np.float32,
)

# Zenith x value
XZC = np.array(
    (
        (0.00166, -0.00375, 0.00209, 0.0),
        (-0.02903, 0.06377, -0.03203, 0.00394),
        (0.11693, -0.21196, 0.06052, 0.25886),
    ),
    dtype=np.float32,
)

# Zenith y value
YZC = np.array(
    (
        (0.00275, -0.00610, 0.00317, 0.0),
        (-0.04214, 0.08970, -0.04153, 0.00516),
        (0.15346, -0.26756, 0.06670, 0.26688),
    ),
    dtype=np.float32,
)

# Original CIE sky coefficients
CIE_SKY_COEFFICIENTS = np.array(
    (
        (4.00, -0.70, 0.00, -1.00, 0.00),
        (4.00, -0.70, 2.00, -1.50, 0.15),
        (1.10, -0.80, 0.00, -1.00, 0.00),
        (1.10, -0.80, 2.00, -1.50, 0.15),
        (0.00, -1.00, 0.00, -1.00, 0.00),
        (0.00, -1.00, 2.00, -1.50, 0.15),
        (0.00, -1.00, 5.00, -2.50, 0.30),
        (0.00, -1.00, 10.0, -3.00, 0.45),
        (-1.0, -0.55, 2.00, -1.50, 0.15),
        (-1.0, -0.55, 5.00, -2.50, 0.30),
        (-1.0, -0.55, 10.0, -3.00, 0.45),
        (-1.0, -0.32, 10.0, -3.00, 0.45),
        (-1.0, -0.32, 16.0, -3.00, 0.30),
        (-1.0, -0.15, 16.0, -3.00, 0.30),
        (-1.0, -0.15, 24.0, -2.80, 0.15),
    ),
    dtype=np.float32,
)

K_O_WAVELENGTHS = np.array(
    (
        300.0, 305.0, 310.0, 315.0, 320.0, 325.0, 330.0, 335.0, 340.0, 345.0, 350.0, 355.0,
        445.0, 450.0, 455.0, 460.0, 465.0, 470.0, 475.0, 480.0, 485.0, 490.0, 495.0,
        500.0, 505.0, 510.0, 515.0, 520.0, 525.0, 530.0, 535.0, 540.0, 545.0, 550.0,
        555.0, 560.0, 565.0, 570.0, 575.0, 580.0, 585.0, 590.0, 595.0, 600.0, 605.0,
        610.0, 620.0, 630.0, 640.0, 650.0, 660.0, 670.0, 680.0, 690.0, 700.0, 710.0,
        720.0, 730.0, 740.0, 750.0, 760.0, 770.0, 780.0, 790.0,
    ),
    dtype=np.float32,
)
K_O_AMPLITUDES = np.array(
    (
        10.0, 4.8, 2.7, 1.35, 0.8, 0.38, 0.16, 0.075, 0.04, 0.019, 0.007, 0.0,
        0.003, 0.003, 0.004, 0.006, 0.008, 0.009, 0.012, 0.014, 0.017, 0.021, 0.025,
        0.03, 0.035, 0.04, 0.045, 0.048, 0.057, 0.063, 0.07, 0.075, 0.08, 0.085, 0.095,
        0.103, 0.11, 0.12, 0.122, 0.12, 0.118, 0.115, 0.12, 0.125, 0.13, 0.12, 0.105,
        0.09, 0.079, 0.067, 0.057, 0.048, 0.036, 0.028, 0.023, 0.018, 0.014, 0.011,
        0.01, 0.009, 0.007, 0.004, 0.0, 0.0,
    ),
    dtype=np.float32,
)
K_G_WAVELENGTHS = np.array((759.0, 760.0, 770.0, 771.0), dtype=np.float32)
K_G_AMPLITUDES = np.array((0.0, 3.0, 0.21, 0.0), dtype=np.float32)
K_WA_WAVELENGTHS = np.array(
    (689.0, 690.0, 700.0, 710.0, 720.0, 730.0, 740.0, 750.0, 760.0, 770.0, 780.0, 790.0, 800.0),
    dtype=np.float32,
)
K_WA_AMPLITUDES = np.array(
    (0.0, 0.016, 0.024, 0.0125, 1.0, 0.87, 0.061, 0.001, 0.0001, 0.0001, 0.006, 0.0175, 0.036),
    dtype=np.float32,
)
SOLAR_WAVELENGTHS = np.arange(380.0, 760.0, 10.0, dtype=np.float32)
SOLAR_AMPLITUDES = np.array(
    (
        165.5, 162.3, 211.2, 258.8, 258.2, 242.3, 267.6, 296.6, 305.4, 300.6,
        306.6, 288.3, 287.1, 278.2, 271.0, 272.3, 263.6, 255.0, 250.6, 253.1,
        253.5, 251.3, 246.3, 241.7, 236.8, 232.1, 228.2, 223.4, 219.7, 215.3,
        211.0, 207.3, 202.4, 198.7, 194.3, 190.7, 186.3, 182.6,
    ),
    dtype=np.float32,
)
SUN_ARTIFICIAL_TWEAK_CURVE = np.full(16, 6.2, dtype=np.float32)


@dataclass(frozen=True)
class SkyAtmosphereParameters:
    sun_theta: float
    sun_phi: float
    turbidity: float
    sky_type: int
    cie_sky_number: int
    sky_intensity: float
    sun_intensity: float
    luminance_only: bool
    exposure: float
    sun_cone_angle: float
    custom_sun_color_override: bool
    sun_color_override: tuple[float, float, float]
    sky_dome_radius: float
    zenith_color: tuple[float, float, float]
    haze_color: tuple[float, float, float]
    override_zenith_color: bool
    override_horizon_color: bool
    horizon_haze_height: float
    sun_blur: float


@dataclass(frozen=True)
class SkyLightSample:
    color: tuple[float, float, float]
    direction: tuple[float, float, float]
    solid_angle: float


@dataclass(frozen=True)
class LightBox:
    x0: int
    y0: int
    w: int
    h: int
    mean_square_error: float

    def is_splitable(self) -> bool:
        return self.w >= MIN_SPLITABLE_BOX_SIZE or self.h >= MIN_SPLITABLE_BOX_SIZE


def clamp_positive(value: float) -> float:
    return max(value, 0.0)


def linear_color_luminance(colors):
    colors = np.asarray(colors, dtype=np.float32)
    return colors[..., 0] * LUMINANCE_WEIGHTS[0] + colors[..., 1] * LUMINANCE_WEIGHTS[1] + colors[..., 2] * LUMINANCE_WEIGHTS[2]


def gamma_correct(colors):
    colors = np.asarray(colors, dtype=np.float32)
    return np.power(np.maximum(colors, 1.0e-4), 1.0 / 2.2)


def clamp_color(colors):
    return np.clip(np.asarray(colors, dtype=np.float32), 0.0, 1.0)


def _rgb_to_xyY(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float32)
    xyz = RGB_TO_XYZ @ rgb
    total = float(xyz.sum())
    if total <= EPSILON:
        return np.array((0.3127, 0.3290, 0.0), dtype=np.float32)
    return np.array((xyz[0] / total, xyz[1] / total, xyz[1]), dtype=np.float32)


def _xyY_to_rgb(x, y, Y):
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    Y = np.asarray(Y, dtype=np.float32)
    safe_y = np.where(np.abs(y) <= EPSILON, EPSILON, y)
    X = x * (Y / safe_y)
    Z = (1.0 - x - y) * (Y / safe_y)
    stacked = np.stack((X, Y, Z), axis=-1)
    rgb = np.tensordot(stacked, XYZ_TO_RGB.T, axes=1)
    return np.maximum(rgb, 0.0)


def _calculate_angle(theta_v, phi_v, theta, phi):
    cospsi = np.sin(theta_v) * math.sin(theta) * np.cos(phi - phi_v) + np.cos(theta_v) * math.cos(theta)
    return np.arccos(np.clip(cospsi, -1.0, 1.0))


def _perez_function(A, B, C, D, E, theta, gamma):
    cos_theta = np.maximum(np.cos(theta), 1.0e-4)
    cos_gamma = np.cos(gamma)
    return (1.0 + A * np.exp(B / cos_theta)) * (1.0 + C * np.exp(D * gamma) + E * cos_gamma * cos_gamma)


def _calculate_distribution(coeffs: np.ndarray, turbidity: float, theta, gamma, sun_theta: float):
    A = coeffs[0, 0] * turbidity + coeffs[0, 1]
    B = coeffs[1, 0] * turbidity + coeffs[1, 1]
    C = coeffs[2, 0] * turbidity + coeffs[2, 1]
    D = coeffs[3, 0] * turbidity + coeffs[3, 1]
    E = coeffs[4, 0] * turbidity + coeffs[4, 1]
    top = _perez_function(A, B, C, D, E, theta, gamma)
    bottom = _perez_function(A, B, C, D, E, 0.0, sun_theta)
    return top / max(float(bottom), EPSILON)


def _calculate_chromaticity(coefficients: np.ndarray, sun_theta: float, turbidity: float) -> float:
    t2 = sun_theta * sun_theta
    t3 = t2 * sun_theta
    turbidity2 = turbidity * turbidity
    return (
        (coefficients[0, 0] * t3 + coefficients[0, 1] * t2 + coefficients[0, 2] * sun_theta + coefficients[0, 3]) * turbidity2
        + (coefficients[1, 0] * t3 + coefficients[1, 1] * t2 + coefficients[1, 2] * sun_theta + coefficients[1, 3]) * turbidity
        + (coefficients[2, 0] * t3 + coefficients[2, 1] * t2 + coefficients[2, 2] * sun_theta + coefficients[2, 3])
    )


def _calculate_base_sky_rgb(theta, phi, params: SkyAtmosphereParameters):
    theta = np.asarray(theta, dtype=np.float32)
    phi = np.asarray(phi, dtype=np.float32)
    turbidity = float(np.clip(params.turbidity, 2.0, 6.0))

    if params.sky_type == 1:
        coefficients = CIE_SKY_COEFFICIENTS[int(np.clip(params.cie_sky_number, 0, len(CIE_SKY_COEFFICIENTS) - 1))]
        zenith_angle = np.minimum(theta, HALF_PI - 0.01)
        zenith_angle_sun = min(params.sun_theta, HALF_PI - 0.01)
        gamma = _calculate_angle(theta, phi, params.sun_theta, params.sun_phi)
        phi_z = 1.0 + coefficients[0] * np.exp(coefficients[1] / np.maximum(np.cos(zenith_angle), 1.0e-4))
        phi_0 = 1.0 + coefficients[0] * np.exp(coefficients[1])
        f_x = 1.0 + coefficients[2] * (np.exp(coefficients[3] * gamma) - math.exp(coefficients[3] * HALF_PI)) + coefficients[4] * np.cos(gamma) ** 2
        f_0 = 1.0 + coefficients[2] * (math.exp(coefficients[3] * zenith_angle_sun) - math.exp(coefficients[3] * HALF_PI)) + coefficients[4] * math.cos(zenith_angle_sun) ** 2
        relative_luminance = (phi_z * f_x) / max(float(phi_0 * f_0), EPSILON)

        chi = (4.0 / 9.0 - turbidity / 120.0) * (math.pi - 2.0 * params.sun_theta)
        zenith_Y = (4.0453 * turbidity - 4.9710) * math.tan(chi) - 0.2155 * turbidity + 2.4192
        zenith_Y = abs(zenith_Y) * (1000.0 / 683.0)
        luminance = zenith_Y * relative_luminance
        rgb = np.stack((luminance, luminance, luminance), axis=-1)
        return rgb * NORMALIZATION_FACTOR

    gamma = _calculate_angle(theta, phi, params.sun_theta, params.sun_phi)
    chi = (4.0 / 9.0 - turbidity / 120.0) * (math.pi - 2.0 * params.sun_theta)
    zenith_Y = (4.0453 * turbidity - 4.9710) * math.tan(chi) - 0.2155 * turbidity + 2.4192
    zenith_Y = abs(zenith_Y) * (1000.0 / 683.0)

    sky_Y = zenith_Y * _calculate_distribution(YDC, turbidity, theta, gamma, params.sun_theta)
    if params.luminance_only:
        rgb = np.stack((sky_Y, sky_Y, sky_Y), axis=-1)
        return rgb * NORMALIZATION_FACTOR

    if params.sky_type == 3:
        if params.override_zenith_color:
            zenith_xyY = _rgb_to_xyY(np.array(params.zenith_color, dtype=np.float32))
            zenith_x = float(zenith_xyY[0])
            zenith_y = float(zenith_xyY[1])
        else:
            zenith_x = _calculate_chromaticity(XZC, params.sun_theta, turbidity)
            zenith_y = _calculate_chromaticity(YZC, params.sun_theta, turbidity)
    else:
        zenith_x = _calculate_chromaticity(XZC, params.sun_theta, turbidity)
        zenith_y = _calculate_chromaticity(YZC, params.sun_theta, turbidity)

    sky_x = zenith_x * _calculate_distribution(XDC, turbidity, theta, gamma, params.sun_theta)
    sky_y = zenith_y * _calculate_distribution(Y_CHROMA_DC, turbidity, theta, gamma, params.sun_theta)

    if params.sky_type == 3 and params.override_horizon_color:
        A = YDC[0, 0] * turbidity + YDC[0, 1]
        B = YDC[1, 0] * turbidity + YDC[1, 1]
        cos_theta = np.maximum(np.cos(theta), 1.0e-5)
        horizon_haze = np.power(np.maximum(1.0 + A * np.exp(B / cos_theta), 0.0), params.horizon_haze_height)
        horizon_haze = np.clip(horizon_haze, 0.0, 1.0)
        haze_xyY = _rgb_to_xyY(np.array(params.haze_color, dtype=np.float32))
        sky_x = sky_x * (1.0 - horizon_haze) + haze_xyY[0] * horizon_haze
        sky_y = sky_y * (1.0 - horizon_haze) + haze_xyY[1] * horizon_haze

    rgb = _xyY_to_rgb(sky_x, sky_y, sky_Y)
    return rgb * NORMALIZATION_FACTOR


def calculate_sky_color(theta: float, phi: float, params: SkyAtmosphereParameters) -> np.ndarray:
    return np.asarray(_calculate_base_sky_rgb(theta, phi, params), dtype=np.float32).reshape(3)


def build_analytic_sky_image(width: int, height: int, params: SkyAtmosphereParameters) -> np.ndarray:
    theta = (np.arange(height, dtype=np.float32) + 0.5) * (math.pi / height)
    phi = (np.arange(width, dtype=np.float32) + 0.5) * (TWO_PI / width)
    theta_grid, phi_grid = np.meshgrid(theta, phi, indexing="ij")
    return _calculate_base_sky_rgb(theta_grid, phi_grid, params) * params.sky_intensity


def _wavelength_to_rgb_linear(wavelength: float) -> np.ndarray:
    if wavelength < 380.0 or wavelength > 780.0:
        return np.zeros(3, dtype=np.float32)

    if wavelength < 440.0:
        red = -(wavelength - 440.0) / 60.0
        green = 0.0
        blue = 1.0
    elif wavelength < 490.0:
        red = 0.0
        green = (wavelength - 440.0) / 50.0
        blue = 1.0
    elif wavelength < 510.0:
        red = 0.0
        green = 1.0
        blue = -(wavelength - 510.0) / 20.0
    elif wavelength < 580.0:
        red = (wavelength - 510.0) / 70.0
        green = 1.0
        blue = 0.0
    elif wavelength < 645.0:
        red = 1.0
        green = -(wavelength - 645.0) / 65.0
        blue = 0.0
    else:
        red = 1.0
        green = 0.0
        blue = 0.0

    if wavelength < 420.0:
        factor = 0.3 + 0.7 * (wavelength - 380.0) / 40.0
    elif wavelength <= 700.0:
        factor = 1.0
    else:
        factor = 0.3 + 0.7 * (780.0 - wavelength) / 80.0

    return np.array((red, green, blue), dtype=np.float32) * factor

def get_sun_light_rgb(params: SkyAtmosphereParameters) -> np.ndarray:
    wavelengths = np.arange(350.0, 805.0, 5.0, dtype=np.float32)
    beta = 0.04608365822050 * params.turbidity - 0.04586025928522
    theta_clamped = float(np.clip(params.sun_theta, 0.0, 1.5))
    tweak_scale = float(np.interp(theta_clamped, np.linspace(0.0, 1.5, SUN_ARTIFICIAL_TWEAK_CURVE.size), SUN_ARTIFICIAL_TWEAK_CURVE))
    m = 1.0 / (math.cos(params.sun_theta) + 0.15 * pow(93.885 - params.sun_theta / math.pi * 180.0, -1.253))

    spectral = np.empty_like(wavelengths)
    for index, wavelength in enumerate(wavelengths):
        tau_r = math.exp(-m * 0.008735 * pow(wavelength / 1000.0, -4.08))
        tau_a = math.exp(-m * beta * pow(wavelength / 1000.0, -1.3))
        tau_o = math.exp(-m * clamp_positive(float(np.interp(wavelength, K_O_WAVELENGTHS, K_O_AMPLITUDES))) * 0.35)
        kg = clamp_positive(float(np.interp(wavelength, K_G_WAVELENGTHS, K_G_AMPLITUDES)))
        tau_g = math.exp(-1.41 * kg * m / pow(1.0 + 118.93 * kg * m, 0.45))
        wa = clamp_positive(float(np.interp(wavelength, K_WA_WAVELENGTHS, K_WA_AMPLITUDES)))
        tau_wa = math.exp(-0.2385 * wa * 2.0 * m / pow(1.0 + 20.07 * wa * 2.0 * m, 0.45))
        solar = clamp_positive(float(np.interp(wavelength, SOLAR_WAVELENGTHS, SOLAR_AMPLITUDES)))
        spectral[index] = 100.0 * solar * tau_r * tau_a * tau_o * tau_g * tau_wa * tweak_scale

    rgb_weights = np.stack([_wavelength_to_rgb_linear(float(wavelength)) for wavelength in wavelengths], axis=0)
    rgb = (rgb_weights * spectral[:, None]).sum(axis=0)

    if params.custom_sun_color_override:
        override = np.array(params.sun_color_override, dtype=np.float32)
        override_luma = float(linear_color_luminance(override))
        base_luma = float(linear_color_luminance(rgb))
        if override_luma > EPSILON:
            rgb = override * (base_luma / override_luma)

    return np.maximum(rgb, 0.0) * NORMALIZATION_FACTOR

def get_sun_light(params: SkyAtmosphereParameters) -> SkyLightSample:
    direction = (
        math.sin(params.sun_theta) * math.cos(params.sun_phi),
        math.sin(params.sun_theta) * math.sin(params.sun_phi),
        math.cos(params.sun_theta),
    )
    color = get_sun_light_rgb(params) * params.sun_intensity
    return SkyLightSample(tuple(color.tolist()), direction, SUN_SOLID_ANGLE * max(params.sun_blur, EPSILON))

def _pixel_directions(width: int, height: int) -> np.ndarray:
    theta = (np.arange(height, dtype=np.float32) + 0.5) * (math.pi / height)
    phi = (np.arange(width, dtype=np.float32) + 0.5) * (TWO_PI / width)
    theta_grid, phi_grid = np.meshgrid(theta, phi, indexing="ij")
    sin_theta = np.sin(theta_grid)
    return np.stack(
        (
            sin_theta * np.cos(phi_grid),
            sin_theta * np.sin(phi_grid),
            np.cos(theta_grid),
        ),
        axis=-1,
    )

def _pixel_weights(width: int, height: int) -> np.ndarray:
    theta = (np.arange(height, dtype=np.float32) + 0.5) * (math.pi / height)
    phi_step = TWO_PI / width
    theta_step = math.pi / height
    row_weights = np.sin(theta) * theta_step * phi_step
    return np.broadcast_to(row_weights[:, None], (height, width)).copy()

def _build_light_box(colors: np.ndarray, directions: np.ndarray, weights: np.ndarray, x0: int, y0: int, w: int, h: int) -> LightBox:
    region_colors = colors[y0 : y0 + h, x0 : x0 + w]
    region_weights = weights[y0 : y0 + h, x0 : x0 + w]
    center_direction = directions[y0 + h // 2, x0 + w // 2]
    weight_sum = float(region_weights.sum())
    if weight_sum <= EPSILON:
        return LightBox(x0, y0, w, h, 0.0)

    average_color = (region_colors * region_weights[..., None]).sum(axis=(0, 1)) / weight_sum
    region_directions = directions[y0 : y0 + h, x0 : x0 + w]
    angle_diff = 1.0 - np.clip((region_directions * center_direction).sum(axis=-1), -1.0, 1.0)
    color_diff = np.abs(region_colors - average_color)
    luminance_diff = linear_color_luminance(color_diff)
    error = float((region_weights * angle_diff * luminance_diff).sum())
    return LightBox(x0, y0, w, h, error)


def _split_light_box(box: LightBox, colors: np.ndarray, weights: np.ndarray) -> tuple[LightBox, LightBox]:
    region_colors = colors[box.y0 : box.y0 + box.h, box.x0 : box.x0 + box.w]
    region_weights = weights[box.y0 : box.y0 + box.h, box.x0 : box.x0 + box.w]
    region_luminance = linear_color_luminance(region_colors) * region_weights
    half_luminance = float(region_luminance.sum()) * 0.5

    if box.w > box.h:
        cumulative = region_luminance.sum(axis=0).cumsum()
        split_offset = int(np.searchsorted(cumulative, half_luminance, side="left"))
        split_offset = min(max(split_offset, 0), box.w - 2)
        first = _build_light_box(colors, _DIRECTIONS_CACHE[(colors.shape[1], colors.shape[0])], weights, box.x0, box.y0, split_offset + 1, box.h)
        second = _build_light_box(colors, _DIRECTIONS_CACHE[(colors.shape[1], colors.shape[0])], weights, box.x0 + split_offset + 1, box.y0, box.w - split_offset - 1, box.h)
        return first, second

    cumulative = region_luminance.sum(axis=1).cumsum()
    split_offset = int(np.searchsorted(cumulative, half_luminance, side="left"))
    split_offset = min(max(split_offset, 0), box.h - 2)
    first = _build_light_box(colors, _DIRECTIONS_CACHE[(colors.shape[1], colors.shape[0])], weights, box.x0, box.y0, box.w, split_offset + 1)
    second = _build_light_box(colors, _DIRECTIONS_CACHE[(colors.shape[1], colors.shape[0])], weights, box.x0, box.y0 + split_offset + 1, box.w, box.h - split_offset - 1)
    return first, second


def _box_best_center(box: LightBox, colors: np.ndarray, directions: np.ndarray, weights: np.ndarray):
    x_slice = slice(box.x0, box.x0 + box.w)
    y_slice = slice(box.y0, box.y0 + box.h)
    region_colors = colors[y_slice, x_slice]
    region_weights = weights[y_slice, x_slice]
    region_luminance = linear_color_luminance(region_colors)
    average_color = (region_colors * region_weights[..., None]).sum(axis=(0, 1)) / max(float(region_weights.sum()), EPSILON)
    luminance_weights = region_weights * region_luminance
    luminance_sum = float(luminance_weights.sum())

    if luminance_sum <= EPSILON:
        center_x = box.x0 + box.w // 2
        center_y = box.y0 + box.h // 2
    else:
        x_coords = np.arange(box.x0, box.x0 + box.w, dtype=np.float32)[None, :]
        y_coords = np.arange(box.y0, box.y0 + box.h, dtype=np.float32)[:, None]
        center_x = int(np.clip((x_coords * luminance_weights).sum() / luminance_sum, box.x0, box.x0 + box.w - 1))
        center_y = int(np.clip((y_coords * luminance_weights).sum() / luminance_sum, box.y0, box.y0 + box.h - 1))

    return center_x, center_y, average_color, float(region_weights.sum()), directions[center_y, center_x]


_DIRECTIONS_CACHE: dict[tuple[int, int], np.ndarray] = {}
_WEIGHTS_CACHE: dict[tuple[int, int], np.ndarray] = {}


def generate_sky_lights(colors: np.ndarray, params: SkyAtmosphereParameters, light_count: int, vertical_fov: float) -> list[SkyLightSample]:
    colors = np.asarray(colors, dtype=np.float32)
    height, width = colors.shape[:2]
    cache_key = (width, height)
    directions = _DIRECTIONS_CACHE.setdefault(cache_key, _pixel_directions(width, height))
    weights = _WEIGHTS_CACHE.setdefault(cache_key, _pixel_weights(width, height))
    weight_unify_scalar = TWO_PI / max(float(weights.sum()), EPSILON)

    actual_vertical_percentage = float(np.clip(vertical_fov / math.pi, 0.03, 1.0))
    initial_height = max(1, min(height, int(height * actual_vertical_percentage)))
    boxes = [_build_light_box(colors, directions, weights, 0, 0, width, initial_height)]

    while len(boxes) < max(light_count, 1):
        worst_index = None
        worst_error = -1.0
        for index, box in enumerate(boxes):
            if box.is_splitable() and box.mean_square_error > worst_error:
                worst_error = box.mean_square_error
                worst_index = index

        if worst_index is None:
            break

        first, second = _split_light_box(boxes[worst_index], colors, weights)
        boxes[worst_index] = first
        boxes.append(second)

    result = []
    for box in boxes[:light_count]:
        center_x, center_y, average_color, solid_angle, direction = _box_best_center(box, colors, directions, weights)
        del center_x, center_y
        light_color = average_color * params.sky_intensity
        result.append(
            SkyLightSample(
                tuple(np.asarray(light_color, dtype=np.float32).tolist()),
                tuple(np.asarray(direction, dtype=np.float32).tolist()),
                solid_angle * weight_unify_scalar,
            )
        )
    return result


def sample_sky_image(theta: float, phi: float, image: np.ndarray, sample_radius: int = 5) -> np.ndarray:
    image = np.asarray(image, dtype=np.float32)
    height, width = image.shape[:2]
    phi_step = TWO_PI / max(width - 1, 1)
    theta_step = HALF_PI / max(height - 1, 1)
    phi = float(np.clip(phi, 0.0, TWO_PI))
    theta = float(np.clip(theta, 0.0, HALF_PI))
    center_x = int(phi / phi_step) if phi_step > EPSILON else 0
    center_y = int(theta / theta_step) if theta_step > EPSILON else 0

    sample_color = np.zeros(3, dtype=np.float32)
    sample_weight = 0.0
    for dx in range(-sample_radius, sample_radius + 1):
        xx = min(max(center_x + dx, 0), width - 1)
        for dy in range(-sample_radius, sample_radius + 1):
            yy = min(max(center_y + dy, 0), height - 1)
            weight = 1.0 / (dx * dx + dy * dy + 1.0)
            sample_color += image[yy, xx] * weight
            sample_weight += weight

    if sample_weight <= EPSILON:
        return image[min(max(center_y, 0), height - 1), min(max(center_x, 0), width - 1)].copy()
    return sample_color / sample_weight


def build_sky_dome_data(
    image: np.ndarray,
    params: SkyAtmosphereParameters,
    latitude_slices: int,
    longitude_slices: int,
    horizontal_fov: float,
    vertical_fov: float,
    clamp: bool = True,
):
    latitude_slices = max(2, int(latitude_slices))
    longitude_slices = max(2, int(longitude_slices))
    theta_step = vertical_fov / max(latitude_slices - 1, 1)
    phi_step = horizontal_fov / max(longitude_slices - 1, 1)
    radius = max(params.sky_dome_radius, EPSILON)

    vertices = []
    colors = []
    texcoords = []
    for latitude in range(latitude_slices):
        theta = latitude * theta_step
        for longitude in range(longitude_slices):
            phi = longitude * phi_step
            vertices.append(
                (
                    radius * math.sin(theta) * math.cos(phi),
                    radius * math.sin(theta) * math.sin(phi),
                    radius * math.cos(theta),
                )
            )
            color = sample_sky_image(theta, phi, image) * (params.sky_intensity * params.exposure)
            color = gamma_correct(color)
            if clamp:
                color = clamp_color(color)
            colors.append(tuple(np.asarray(color, dtype=np.float32).tolist()))
            u = 0.0 if horizontal_fov <= EPSILON else phi / horizontal_fov
            v = 0.0 if vertical_fov <= EPSILON else 1.0 - theta / vertical_fov
            texcoords.append((u, v))

    faces = []
    for latitude in range(latitude_slices - 1):
        for longitude in range(longitude_slices - 1):
            faces.append(
                (
                    latitude * longitude_slices + longitude,
                    latitude * longitude_slices + longitude + 1,
                    (latitude + 1) * longitude_slices + longitude,
                )
            )
            faces.append(
                (
                    latitude * longitude_slices + longitude + 1,
                    (latitude + 1) * longitude_slices + longitude + 1,
                    (latitude + 1) * longitude_slices + longitude,
                )
            )

    return vertices, faces, colors, texcoords


def modifier_apply_sky_color(positions: np.ndarray, params: SkyAtmosphereParameters, clamp: bool = False) -> np.ndarray:
    positions = np.asarray(positions, dtype=np.float32)
    magnitudes = np.linalg.norm(positions, axis=1)
    magnitudes = np.where(magnitudes <= EPSILON, 1.0, magnitudes)
    phi = np.arctan2(positions[:, 1], positions[:, 0])
    phi = np.where(phi < 0.0, phi + TWO_PI, phi)
    theta = np.arccos(np.clip(positions[:, 2] / magnitudes, -1.0, 1.0))
    colors = _calculate_base_sky_rgb(theta, phi, params) * (params.sky_intensity * params.exposure)
    colors = gamma_correct(colors)
    return clamp_color(colors) if clamp else colors


def modifier_apply_sun_lighting(normals: np.ndarray, params: SkyAtmosphereParameters, clamp: bool = False) -> np.ndarray:
    normals = np.asarray(normals, dtype=np.float32)
    sun_direction = np.array(
        (
            math.sin(params.sun_theta) * math.cos(params.sun_phi),
            math.sin(params.sun_theta) * math.sin(params.sun_phi),
            math.cos(params.sun_theta),
        ),
        dtype=np.float32,
    )
    sun_rgb = get_sun_light_rgb(params) * params.sun_intensity
    dots = np.maximum(normals @ sun_direction, 0.0)
    colors = dots[:, None] * sun_rgb[None, :] * (params.exposure * SUN_SOLID_ANGLE / math.pi)
    colors = gamma_correct(colors)
    return clamp_color(colors) if clamp else colors


def modifier_apply_sky_lighting(normals: np.ndarray, params: SkyAtmosphereParameters, sky_lights: list[SkyLightSample], clamp: bool = False) -> np.ndarray:
    normals = np.asarray(normals, dtype=np.float32)
    if not sky_lights:
        return np.zeros((len(normals), 3), dtype=np.float32)

    directions = np.array([sample.direction for sample in sky_lights], dtype=np.float32)
    colors = np.array([sample.color for sample in sky_lights], dtype=np.float32)
    solid_angles = np.array([sample.solid_angle for sample in sky_lights], dtype=np.float32)
    dots = np.maximum(normals @ directions.T, 0.0)
    weighted_colors = colors * solid_angles[:, None]
    result = dots @ weighted_colors
    result *= params.exposure / math.pi
    result = gamma_correct(result)
    return clamp_color(result) if clamp else result

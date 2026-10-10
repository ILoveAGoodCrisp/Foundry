"""Decode sampled, constant, and quantized Granny animation curves."""
import struct

import numpy as np

from .container import UnsupportedGrannyFormat, count
from .records import Array


def scalars(value):
    if isinstance(value, Array):
        count(len(value), 1_600_000)
    return np.asarray(value.scalar() if isinstance(value, Array) else value, dtype=np.float64)


def quaternion_controls(data, packed, bits):
    """Three quantized components, cyclic omitted axis, and its sign bit.

    Each output component selects one of eight ranges within +/-sqrt(1/2);
    table entries 8..15 reverse the corresponding range. These ranges and
    bit assignments are checked against both SDK runtimes in codec tests.
    """
    if packed.size % 4:
        raise ValueError('Invalid GR2 quaternion knot/control count')
    n = count(packed.size // 4, 100_000)
    inverse_scale = data.get('OneOverKnotScale')
    if not np.isfinite(inverse_scale) or inverse_scale <= 0:
        raise ValueError('Invalid GR2 quaternion knot scale')
    knots = (packed[:n] / inverse_scale).astype(np.float32).astype(np.float64)
    raw = packed[n:].reshape(n, 3).astype(np.uint32)
    omitted = ((raw[:, 1] >> (bits - 2)) & 2) | (raw[:, 2] >> (bits - 1))
    columns = (omitted[:, None] + 1 + np.arange(3)) % 4
    entries = (data.get('ScaleOffsetTableEntries') >> (columns * 4)) & 15
    base = np.float32(2 ** -.5)
    lows = np.array((-1, -.5, -.75, -.25, .25, -.25, -.125, 0), dtype=np.float32) * base
    widths = np.array((2, 1, .5, .5, .5, .25, .25, .25), dtype=np.float32) * base
    signs = np.where(entries < 8, 1, -1).astype(np.float32)
    mask = (1 << (bits - 1)) - 1
    values = (raw & mask).astype(np.float32) * (widths[entries & 7] / np.float32(mask) * signs) + lows[entries & 7] * signs
    remaining = 1 - np.sum(values * values, axis=1)
    if np.any(remaining < -1e-5):
        raise ValueError('Invalid compressed GR2 quaternion')
    missing = np.sqrt(np.maximum(remaining, 0)) * np.where(raw[:, 0] >> (bits - 1), -1, 1)
    controls = np.empty((n, 4), dtype=np.float64)
    controls[np.arange(n)[:, None], columns] = values
    controls[np.arange(n), omitted] = missing
    return knots, controls


def decode(curve, dimension, identity):
    data = curve.get('CurveData') if curve else None
    if data is None:
        # Older files store the degree/knots/controls directly in the curve.
        data = curve
        if data is None:
            return 0, None, np.asarray([identity], dtype=np.float64), False
        name, degree = 'DaK32fC32f', data.get('Degree', 0)
    else:
        headers = [m.name for m in data.owner.layout(data.dtype)[0] if m.name.startswith('CurveDataHeader_')]
        if len(headers) != 1:
            raise UnsupportedGrannyFormat('Unrecognized GR2 curve schema')
        name = headers[0].removeprefix('CurveDataHeader_')
        degree = data.get(headers[0]).get('Degree')
    if not 0 <= degree <= 3:
        raise UnsupportedGrannyFormat(f'Unsupported GR2 spline degree {degree}')
    keyframes = name == 'DaKeyframes32f'
    if name == 'DaIdentity':
        return degree, None, np.asarray([identity], dtype=np.float64), False
    if keyframes or 'Constant32f' in name:
        values = scalars(data.get('Controls'))
        if keyframes and data.get('Dimension') != dimension:
            raise ValueError('Invalid GR2 animation curve dimension')
        if not values.size or values.size % dimension:
            raise ValueError('Invalid GR2 animation controls')
        controls = values.reshape(-1, dimension)
        if not keyframes and len(controls) != 1:
            raise ValueError('Invalid GR2 constant curve dimension')
        knots = None
    elif name == 'DaK32fC32f':
        knots, values = scalars(data.get('Knots')), scalars(data.get('Controls'))
        if not knots.size:
            return degree, None, np.asarray([identity], dtype=np.float64), False
        if values.size != knots.size * dimension:
            raise ValueError('Invalid GR2 spline dimension')
        controls = values.reshape(-1, dimension)
    elif name in ('D4nK16uC15u', 'D4nK8uC7u'):
        if dimension != 4:
            raise ValueError('Invalid GR2 quaternion curve dimension')
        knots, controls = quaternion_controls(data, scalars(data.get('KnotsControls')), 16 if '16u' in name else 8)
        if not len(controls):
            return degree, None, np.asarray([identity], dtype=np.float64), False
    else:
        packed = scalars(data.get('KnotsControls'))
        if name in ('DaK16uC16u', 'DaK8uC8u'):
            offsets = scalars(data.get('ControlScaleOffsets'))
            if offsets.size != 2 * dimension:
                raise ValueError('Invalid GR2 quantized curve dimension')
            scales, offsets = offsets[:dimension], offsets[dimension:]
            stored = dimension
        elif name in ('D3K16uC16u', 'D3K8uC8u', 'D9I3K16uC16u', 'D9I3K8uC8u',
                      'D3I1K32fC32f', 'D3I1K16uC16u', 'D3I1K8uC8u'):
            scales, offsets = scalars(data.get('ControlScales')), scalars(data.get('ControlOffsets'))
            stored = 1 if name.startswith('D3I1') else 3
        elif name in ('D9I1K16uC16u', 'D9I1K8uC8u'):
            scales, offsets = data.get('ControlScale'), data.get('ControlOffset')
            stored = 1
        else:
            raise UnsupportedGrannyFormat(f'Unsupported GR2 curve codec {name}')
        if packed.size % (stored + 1):
            raise ValueError('Invalid GR2 quantized knot/control count')
        n = packed.size // (stored + 1)
        count(n, 100_000)
        if not n:
            return degree, None, np.asarray([identity], dtype=np.float64), False
        inverse_scale = 1. if name == 'D3I1K32fC32f' else struct.unpack('<f', struct.pack('<I', data.get('OneOverKnotScaleTrunc') << 16))[0]
        if not np.isfinite(inverse_scale) or inverse_scale <= 0:
            raise ValueError('Invalid GR2 quantized knot scale')
        knots = (packed[:n] / inverse_scale).astype(np.float32).astype(np.float64)
        controls = packed[n:].reshape(n, stored) * scales + offsets
        if name.startswith('D9I'):
            matrix = np.zeros((n, 9))
            matrix[:, (0, 4, 8)] = controls
            controls = matrix
        if controls.shape[1] != dimension:
            raise ValueError('Invalid GR2 quantized curve dimension')
    count(len(controls), 100_000)
    if not np.isfinite(controls).all() or (knots is not None and (not np.isfinite(knots).all() or np.any(np.diff(knots) < 0))):
        raise ValueError('Invalid GR2 animation controls or knot order')
    return degree, knots, controls, keyframes


def sample(curve, dimension, times, identity, normalize=False):
    degree, knots, controls, keyframes = decode(curve, dimension, identity)
    if keyframes:
        if len(controls) < len(times):
            raise ValueError('GR2 keyframe curve has fewer samples than the animation')
        result = controls[:len(times)].copy()
    elif knots is None or len(controls) == 1:
        result = np.repeat(controls[:1], len(times), axis=0)
    else:
        times = np.asarray(times, dtype=np.float32).astype(np.float64)
        indices = np.searchsorted(knots, times, side='right')
        indices = np.minimum(indices, len(knots) - 1)
        if degree == 0:
            result = controls[indices].copy()
        else:
            # Granny stores one knot per control. Repeated endpoints supply
            # the missing non-looping controls and knots for de Boor evaluation.
            work = np.stack([controls[np.clip(indices - degree + j, 0, len(knots) - 1)] for j in range(degree + 1)], axis=1)
            for level in range(1, degree + 1):
                for j in range(degree, level - 1, -1):
                    lo = knots[np.clip(indices - degree + j - 1, 0, len(knots) - 1)]
                    hi = knots[np.clip(indices + j - level, 0, len(knots) - 1)]
                    alpha = np.divide(times - lo, hi - lo, out=np.zeros_like(times), where=hi != lo)
                    work[:, j] = (1 - alpha[:, None]) * work[:, j - 1] + alpha[:, None] * work[:, j]
            result = work[:, degree]
            result[times <= knots[0]] = controls[0]
            # Quantized final knots can precede the animation duration. Granny
            # extrapolates that last span; clamping it changes the final pose.
    if normalize:
        lengths = np.linalg.norm(result, axis=1, keepdims=True)
        if np.any(lengths < 1e-10):
            raise ValueError('Invalid GR2 animation orientation')
        result /= lengths
    if not np.isfinite(result).all():
        raise ValueError('Non-finite GR2 animation sample')
    return result

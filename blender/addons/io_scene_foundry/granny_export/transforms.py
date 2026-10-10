"""Owned affine conversion and packed Granny transform math, without a runtime.

Authored matrices use rows and column vectors. Granny's inverse-world 4x4
storage uses columns; its scale/shear 3x3 storage uses rows.
"""
from __future__ import annotations

from math import hypot, isfinite, sqrt
from functools import lru_cache
import struct

from .binary import BinaryWriteError
from .model import IDENTITY, Attribute, Buffer, Scalar

IDENTITY3 = tuple(row[:3] for row in IDENTITY[:3])
_MIRROR = ((1., 0., 0.), (0., -1., 0.), (0., 0., 1.))
_SPATIAL = frozenset(('Position', 'Normal', 'Tangent', 'Binormal'))
_ARRAY_BATCH_SIZE = 65536
_COMPENSATED_SUM = sum((1e16, 1., -1e16)) == 1.


@lru_cache(maxsize=1)
def _numpy_module():
    """Acceleration is optional and never imported during package preparation."""
    try:
        import numpy
    except ImportError:
        return None
    return numpy


def _array_vectors(values, matrix, np):
    """Batch three-term products in the scalar reference's accumulation order."""
    result = np.empty_like(values)
    for axis, coefficients in enumerate(matrix):
        total = np.zeros(len(values), dtype=np.float64)
        correction = np.zeros_like(total) if _COMPENSATED_SUM else None
        for column, coefficient in enumerate(coefficients):
            term = values[:, column] * coefficient
            updated = total + term
            if correction is not None:
                correction += np.where(np.abs(total) >= np.abs(term),
                    (total - updated) + term, (term - updated) + total)
            total = updated
        if correction is not None:
            total = np.where((correction != 0.) & np.isfinite(correction), total + correction, total)
        result[:, axis] = total
    return result


def _array_vertex_buffer(attribute, stages, data_is_deltas, np):
    """Bound temporary storage and round to float32 after every original stage."""
    source = np.frombuffer(attribute.buffer.data, dtype='<f4').reshape(-1, 3)
    output = bytearray(len(attribute.buffer.data))
    operations = []
    for transform, translation, renormalize in stages:
        operation = (transpose(transform) if data_is_deltas else transpose(inverse(transform))) if attribute.name == 'Normal' else transform
        operations.append((operation, translation, renormalize))
    with np.errstate(over='ignore', invalid='ignore', divide='ignore', under='ignore'):
        for start in range(0, len(source), _ARRAY_BATCH_SIZE):
            values = source[start:start + _ARRAY_BATCH_SIZE].astype(np.float64)
            for operation, translation, renormalize in operations:
                values = _array_vectors(values, operation, np)
                if attribute.name == 'Position' and not data_is_deltas:
                    values += translation
                elif attribute.name != 'Position' and renormalize:
                    lengths = np.hypot(np.hypot(values[:, 0], values[:, 1]), values[:, 2])
                    np.divide(values, lengths[:, None], out=values, where=lengths[:, None] != 0.)
                narrowed = values.astype('<f4')
                if not np.isfinite(narrowed).all():
                    raise BinaryWriteError('Transform result is outside finite float32 range')
                values = narrowed.astype(np.float64)
            encoded = narrowed.tobytes()
            output[start * 12:start * 12 + len(encoded)] = encoded
    return bytes(output)


def transpose(matrix):
    return tuple(zip(*matrix))


def multiply(left, right):
    columns = transpose(right)
    return tuple(tuple(sum(a * b for a, b in zip(row, column)) for column in columns) for row in left)


def vector(matrix, value):
    return tuple(sum(a * b for a, b in zip(row, value)) for row in matrix)


def determinant(matrix):
    a, b, c = matrix
    return (a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0]))


def inverse(matrix):
    """Invert a 3x3 with a relative singularity check, independent of units."""
    scale = max(abs(v) for row in matrix for v in row)
    if not isfinite(scale) or scale == 0:
        raise BinaryWriteError('Singular or nonfinite linear transform')
    a, b, c = tuple(tuple(v / scale for v in row) for row in matrix)
    normalized = (a, b, c)
    det = determinant(normalized)
    if abs(det) < 1e-12:
        raise BinaryWriteError('Singular or ill-conditioned linear transform')
    cofactors = ((b[1]*c[2]-b[2]*c[1], b[2]*c[0]-b[0]*c[2], b[0]*c[1]-b[1]*c[0]),
                 (c[1]*a[2]-c[2]*a[1], c[2]*a[0]-c[0]*a[2], c[0]*a[1]-c[1]*a[0]),
                 (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]))
    return tuple(tuple(v / det / scale for v in row) for row in transpose(cofactors))


def affine(matrix):
    try:
        rows = tuple(tuple(float(v) for v in row) for row in matrix)
    except (TypeError, ValueError, OverflowError) as error:
        raise BinaryWriteError('Expected a finite affine 4x4 matrix') from error
    if (len(rows) != 4 or any(len(row) != 4 for row in rows)
            or any(not isfinite(v) for row in rows for v in row)):
        raise BinaryWriteError('Expected a finite affine 4x4 matrix')
    if any(abs(a - b) > 1e-7 for a, b in zip(rows[3], (0., 0., 0., 1.))):
        raise BinaryWriteError('Projective matrices are not supported')
    linear, position = tuple(row[:3] for row in rows[:3]), tuple(row[3] for row in rows[:3])
    inverse(linear)
    return linear, position


def matrix4(linear, position):
    return tuple((*row, position[i]) for i, row in enumerate(linear)) + ((0., 0., 0., 1.),)


def float32(value):
    try:
        result = struct.unpack('<f', struct.pack('<f', value))[0]
    except (OverflowError, struct.error, TypeError, ValueError) as error:
        raise BinaryWriteError('Transform result is outside finite float32 range') from error
    if not isfinite(result):
        raise BinaryWriteError('Transform result is outside finite float32 range')
    return result


def quaternion(rotation):
    """Convert a proper orthogonal row matrix to a normalized XYZW quaternion."""
    m = rotation
    trace = sum(m[i][i] for i in range(3))
    if trace > 0:
        s = sqrt(max(0., trace + 1.)) * 2
        q = ((m[2][1]-m[1][2])/s, (m[0][2]-m[2][0])/s, (m[1][0]-m[0][1])/s, s/4)
    else:
        i = max(range(3), key=lambda axis: m[axis][axis])
        j, k = (i + 1) % 3, (i + 2) % 3
        s = sqrt(max(0., 1 + m[i][i] - m[j][j] - m[k][k])) * 2
        components = [0.] * 4
        components[i], components[j], components[k] = s/4, (m[j][i]+m[i][j])/s, (m[k][i]+m[i][k])/s
        components[3] = (m[k][j]-m[j][k])/s
        q = tuple(components)
    length = sqrt(sum(v*v for v in q))
    sign = -1 if q[3] < 0 else 1
    return tuple(sign*v/length for v in q)


def decompose(matrix):
    """Polar decomposition retains all nine scale/shear entries and reflections.

    A negative determinant moves the reflection into all three scale axes,
    matching Blender's signed-scale convention for ordinary TRS matrices.
    """
    linear, position = affine(matrix)
    magnitude = max(abs(v) for row in linear for v in row)
    rotation = tuple(tuple(v/magnitude for v in row) for row in linear)
    for _ in range(64):
        inv_transpose = transpose(inverse(rotation))
        updated = tuple(tuple((a+b)/2 for a, b in zip(row, other))
                        for row, other in zip(rotation, inv_transpose))
        error = max(abs(a-b) for row, other in zip(rotation, updated) for a, b in zip(row, other))
        rotation = updated
        if error < 1e-12:
            break
    else:
        raise BinaryWriteError('Transform polar decomposition did not converge')
    if determinant(rotation) < 0:
        rotation = tuple(tuple(-v for v in row) for row in rotation)
    shear = multiply(transpose(rotation), linear)
    # Remove numerical decomposition noise at identity.
    shear = tuple(tuple(0. if abs(v) < 1e-14 else v for v in row) for row in shear)
    return position, quaternion(rotation), shear


def packed_transform(matrix):
    position, orientation, shear = decompose(matrix)
    values = tuple(float32(v) for v in (*position, *orientation, *(v for row in shear for v in row)))
    p, q, s = values[:3], values[3:7], values[7:]
    inverse(tuple(tuple(s[i*3:i*3+3]) for i in range(3)))
    flags = (int(p != (0., 0., 0.)) | (int(q != (0., 0., 0., 1.)) << 1)
             | (int(s != tuple(v for row in IDENTITY3 for v in row)) << 2))
    return flags, values


def _basis(right, up, back):
    try:
        rows = tuple(tuple(float32(v) for v in row) for row in (right, up, back))
    except TypeError as error:
        raise BinaryWriteError('Coordinate basis requires three orthonormal axes') from error
    if (any(len(row) != 3 for row in rows)
            or any(abs(sum(a*b for a, b in zip(rows[i], rows[j])) - int(i == j)) > 1e-5
                   for i in range(3) for j in range(3))):
        raise BinaryWriteError('Coordinate basis requires three orthonormal axes')
    return transpose(rows)


class TransformContext:
    """Read-only context applies each pending operation once per written object."""
    def __init__(self, art, conversion):
        if art.pointer_size != 64 or conversion.state not in ('authored', 'converted'):
            raise BinaryWriteError('GR2 writing requires a 64-bit basis with a known conversion state')
        source_units, target_units = float32(art.units_per_meter), float32(conversion.target_units_per_meter)
        if source_units <= 0 or target_units <= 0:
            raise BinaryWriteError('Coordinate units per meter must be positive')
        source = _basis(art.right, art.up, art.back)
        target = _basis(conversion.right, conversion.up, conversion.back)
        try:
            origin = tuple(float32(v) for v in art.origin)
        except TypeError as error:
            raise BinaryWriteError('Coordinate origin requires three components') from error
        if len(origin) != 3:
            raise BinaryWriteError('Coordinate origin requires three components')
        if conversion.state == 'converted' and (conversion.reflect_y or source != target
                or source_units != target_units or origin != (0., 0., 0.)):
            raise BinaryWriteError('Converted input still declares a pending basis or reflection')
        rotation = IDENTITY3 if source == target else multiply(target, transpose(source))
        scale = target_units/source_units
        self.linear = tuple(tuple(float32(v*scale) for v in row) for row in rotation)
        self.rotation = rotation
        self.handedness = -1 if determinant(rotation) < 0 else 1
        self.inverse = inverse(self.linear)
        # GrannyComputeBasisConversion subtracts the stored origin directly;
        # it does not rotate/scale that offset through ResultLinear3x3.
        self.translation = tuple(-v for v in origin)
        self.reflect_y = conversion.reflect_y
        self.reorder_winding = determinant(self.linear) < 0
        self.art = art
        self.conversion = conversion

    def similarity(self, matrix, *, reflect=None):
        linear, position = affine(matrix)
        mirror = self.reflect_y if reflect is None else reflect
        if mirror:
            linear = multiply(multiply(_MIRROR, linear), _MIRROR)
            position = vector(_MIRROR, position)
        linear = multiply(multiply(self.linear, linear), self.inverse)
        position = tuple(a+b for a, b in zip(vector(self.linear, position), self.translation))
        return matrix4(linear, position)

    def transform(self, matrix):
        return packed_transform(self.similarity(matrix))

    def inverse_world(self, matrix):
        linear, position = affine(matrix)
        inv = inverse(linear)
        inverted = matrix4(inv, tuple(-v for v in vector(inv, position)))
        result = self.similarity(inverted)
        return tuple(float32(v) for row in transpose(result) for v in row)

    def bounds(self, minimum, maximum):
        low, high = [], []
        for row, shift in zip(self.linear, self.translation):
            pairs = [(coefficient*a, coefficient*b) for coefficient, a, b in zip(row, minimum, maximum)]
            low.append(float32(shift+sum(min(pair) for pair in pairs)))
            high.append(float32(shift+sum(max(pair) for pair in pairs)))
        return tuple(low), tuple(high)

    def sampled_buffer(self, controls, role):
        """Convert raw samples while retaining quaternion sign and scale/shear."""
        width = {'position': 3, 'orientation': 4, 'scale_shear': 9}.get(role)
        if controls.scalar is not Scalar.REAL32 or controls.width != width:
            raise BinaryWriteError('Unsupported sampled transform component')
        output = bytearray(len(controls.data))
        for index, row in enumerate(struct.iter_unpack('<'+'f'*width, controls.data)):
            if role == 'position':
                value = vector(_MIRROR, row) if self.reflect_y else row
                value = tuple(a+b for a, b in zip(vector(self.linear, value), self.translation))
            elif role == 'orientation':
                xyz = tuple((-v if i != 1 else v) for i, v in enumerate(row[:3])) if self.reflect_y else row[:3]
                value = (*(self.handedness*v for v in vector(self.rotation, xyz)), row[3])
            else:
                shear = tuple(tuple(row[i*3:i*3+3]) for i in range(3))
                if self.reflect_y:
                    shear = multiply(multiply(_MIRROR, shear), _MIRROR)
                shear = multiply(multiply(self.linear, shear), self.inverse)
                value = tuple(v for matrix_row in shear for v in matrix_row)
            struct.pack_into('<'+'f'*width, output, index*width*4, *(float32(v) for v in value))
        return Buffer(Scalar.REAL32, width, controls.count, output)

    def vertices(self, data):
        linear, position = affine(data.placement)
        if data.reflect_y:
            linear = multiply(multiply(_MIRROR, linear), _MIRROR)
            position = vector(_MIRROR, position)
        stages = []
        if data.reflect_y:
            stages.append((_MIRROR, (0., 0., 0.), False))
        if data.placement != IDENTITY:
            stages.append((linear, position, True))
        stages.append((self.linear, self.translation, True))
        np = _numpy_module() if data.count >= 32 else None
        attributes = []
        for attribute in data.attributes:
            if attribute.name not in _SPATIAL:
                attributes.append(attribute)
                continue
            if attribute.buffer.scalar is not Scalar.REAL32 or attribute.buffer.width != 3:
                raise BinaryWriteError('Spatial vertex attributes require three float32 components')
            if np is not None:
                content = _array_vertex_buffer(attribute, stages, data.data_is_deltas, np)
                attributes.append(Attribute(attribute.name, attribute.component_name,
                    Buffer(Scalar.REAL32, 3, attribute.buffer.count, content)))
                continue
            content = attribute.buffer.data
            for transform, translation, renormalize in stages:
                normal = attribute.name == 'Normal'
                operation = (transpose(transform) if data.data_is_deltas else transpose(inverse(transform))) if normal else transform
                output = bytearray(len(content))
                for index, row in enumerate(struct.iter_unpack('<3f', content)):
                    value = vector(operation, row)
                    if attribute.name == 'Position' and not data.data_is_deltas:
                        value = tuple(a+b for a, b in zip(value, translation))
                    elif attribute.name != 'Position' and renormalize:
                        length = hypot(*value)
                        if length:
                            value = tuple(v/length for v in value)
                    struct.pack_into('<3f', output, index*12, *(float32(v) for v in value))
                content = bytes(output)
            attributes.append(Attribute(attribute.name, attribute.component_name,
                Buffer(Scalar.REAL32, 3, attribute.buffer.count, content)))
        return tuple(attributes)

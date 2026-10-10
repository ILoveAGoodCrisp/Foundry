"""Granny transform composition and Foundry's import coordinate conversion."""
from math import isclose

import numpy as np

from .container import UnsupportedGrannyFormat


def finite(values, label):
    values = np.asarray(values, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError(f'Non-finite GR2 {label}')
    return values


def transform_matrix(values):
    flags, *components = values
    components = finite(components, 'transform')
    # Composite transforms always use position/orientation, including small
    # authored values whose corresponding optimization flags were cleared.
    position = components[:3]
    x, y, z, w = components[3:7]
    rotation = np.array(((1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w),
                         (2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w),
                         (2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y)))
    shear = components[7:].reshape(3, 3) if flags & 4 else np.eye(3)
    result = np.eye(4, dtype=np.float32)
    result[:3, :3] = rotation @ shear
    result[:3, 3] = position
    return result


class Basis:
    def __init__(self, tool, skeletons, source_game, convert_scale):
        units = tool.get('UnitsPerMeter') if tool else float(np.float32(1 / .03048))
        if not np.isfinite(units) or units <= 0:
            raise ValueError('Invalid GR2 units per meter')
        self.info = dict(art_tool=tool.get('FromArtToolName', '') if tool else 'Foundry defaults',
                         units_per_meter=units, effective_units_per_meter=units, unit_correction=1.,
                         origin=tool.get('Origin') if tool else [0, 0, 0],
                         right=tool.get('RightVector') if tool else [0, -1, 0],
                         up=tool.get('UpVector') if tool else [0, 0, 1],
                         back=tool.get('BackVector') if tool else [-1, 0, 0], convert_scale=convert_scale)
        if tool is None:
            self.info['coordinate_defaults'] = True
        if convert_scale and 'maya' in self.info['art_tool'].casefold() and isclose(units, 100, rel_tol=1e-5):
            corinth = source_game in {'halo4', 'halo2a', 'corinth'}
            for skeleton in skeletons:
                if skeleton.get('Name', '').casefold() != 'bungieexportinfo':
                    continue
                bones = skeleton.get('Bones', ())
                pending = [bones[0].owner.detach(bones[0].get('ExtendedData'))] if bones else []
                while pending:
                    node = pending.pop()
                    corinth |= str(node.get('bungie_export_toolset', '')).casefold() in {'343', '343i'}
                    corinth |= 'corinth' in str(node.get('bungie_export_granny_settings_file', '')).casefold()
                    pending.extend(v for v in node.values() if isinstance(v, dict))
            if corinth:
                self.info.update(effective_units_per_meter=1 / .3048, unit_correction=units * .3048)
        source = finite([self.info[k] for k in ('right', 'up', 'back')], 'coordinate basis').T
        if source.shape != (3, 3) or not np.allclose(source.T @ source, np.eye(3), rtol=1e-5, atol=1e-5):
            raise UnsupportedGrannyFormat('GR2 coordinate basis must be orthonormal')
        target = np.array(((0, 0, -1), (-1, 0, 0), (0, 1, 0)))
        self.rotation = target @ source.T
        target_units = float(np.float32(1 / .03048)) if convert_scale else units
        self.linear = self.rotation * (target_units / float(np.float32(self.info['effective_units_per_meter'])))
        self.inverse = np.linalg.inv(self.linear)
        self.affine = -self.linear @ finite(self.info['origin'], 'coordinate origin')
        self.reflected = np.linalg.det(self.rotation) < 0

    def matrix(self, matrix):
        matrix = finite(matrix, 'matrix')
        result = np.eye(4, dtype=np.float32)
        result[:3, :3] = self.linear @ matrix[:3, :3] @ self.inverse
        result[:3, 3] = self.linear @ matrix[:3, 3] + self.affine
        return result

    def vertices(self, vertices):
        result = {}
        for name, values in vertices.items():
            values = values.astype(np.float32, copy=True)
            if name in ('Position', 'Normal', 'Tangent', 'Binormal'):
                if values.shape[1] != 3:
                    raise ValueError(f'Invalid GR2 {name} component width')
                operation = self.inverse.T if name == 'Normal' else self.linear
                values = values @ operation.T
                if name == 'Position':
                    values += self.affine
                else:
                    lengths = np.linalg.norm(values, axis=1, keepdims=True)
                    np.divide(values, lengths, out=values, where=lengths != 0.)
                values = values.astype(np.float32)
            if not name.startswith(('TextureCoordinates', 'lighting')) and not np.isfinite(values).all():
                raise ValueError('Non-finite GR2 vertex data')
            result[name] = values
        return result

    def tracks(self, positions, orientations, scales):
        positions = np.asarray(positions) @ self.linear.T + self.affine
        orientations = np.array(orientations, dtype=np.float64, copy=True)
        orientations[:, :3] = orientations[:, :3] @ self.rotation.T * (-1 if self.reflected else 1)
        scales = self.rotation @ np.asarray(scales).reshape(-1, 3, 3) @ self.rotation.T
        return positions.tolist(), orientations.tolist(), scales.reshape(-1, 9).tolist()

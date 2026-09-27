"""Bake converted textures to TIFFs that the Halo shader exporter can read.

Packed masks stay linear. Color expressions are evaluated in scene-linear RGB
and written as sRGB. Resampling supports static affine 2D UV mappings only;
unsupported inputs raise instead of leaving a misleading exportable graph.
"""
from hashlib import sha256
from pathlib import Path
import os
import re

import bpy
import numpy as np
from .bitmap_tiff import write_image_tiff


def _input(socket):
    return socket.links[0].from_socket if socket.is_linked else socket.default_value


def _linear(rgb):
    return np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)


def _srgb(rgb):
    return np.where(rgb <= .0031308, rgb * 12.92, 1.055 * np.maximum(rgb, 0) ** (1 / 2.4) - .055)


def _to_linear(rgb, space):
    if space in {'Non-Color', 'Raw', 'Linear Rec.709'}:
        return rgb
    if space == 'sRGB':
        return _linear(rgb)
    # Imported TIFFs can be assigned ACEScg or another configured working space.
    # Use Blender's OCIO configuration rather than treating those as sRGB/data.
    try:
        import PyOpenColorIO as ocio
    except ImportError as exc:
        raise ValueError(f'Blender OCIO Python support is required to bake {space}') from exc
    config_path = os.environ.get('OCIO') or str(Path(bpy.utils.resource_path('LOCAL')) /
                                               'datafiles/colormanagement/config.ocio')
    config = ocio.Config.CreateFromFile(config_path)
    result = np.ascontiguousarray(rgb, dtype=np.float32)
    config.getProcessor(space, 'Linear Rec.709').getDefaultCPUProcessor().applyRGB(result)
    return result


def _uv_transform(node):
    """Return the UV set and a matrix mapping mesh UVs to texture UVs."""
    def walk(socket):
        if not socket.is_linked:
            if socket.node.type == 'TEX_IMAGE':
                return '', np.eye(3)
            raise ValueError('Unconnected mapping coordinates cannot be resampled')
        link = socket.links[0]
        source = link.from_node
        if source.type == 'REROUTE':
            return walk(source.inputs[0])
        if source.type == 'TEX_COORD' and link.from_socket.name == 'UV':
            return '', np.eye(3)
        if source.type == 'UVMAP':
            return source.uv_map, np.eye(3)
        if source.type != 'MAPPING' or source.vector_type != 'POINT':
            raise ValueError('Resampling requires UV coordinates and static Point mapping nodes')
        if any(s.is_linked for s in source.inputs if s.name != 'Vector'):
            raise ValueError('Animated/procedural texture transforms cannot be resampled')
        animation = source.id_data.animation_data
        if animation and (animation.action or animation.drivers):
            raise ValueError('Animated texture transforms cannot be resampled')
        if any(abs(v) > 1e-7 for v in source.inputs['Rotation'].default_value):
            raise ValueError('Rotated texture mapping is not supported by shader export')
        uv, matrix = walk(source.inputs['Vector'])
        scale = source.inputs['Scale'].default_value
        offset = source.inputs['Location'].default_value
        transform = np.array([[scale[0], 0, offset[0]], [0, scale[1], offset[1]], [0, 0, 1]])
        return uv, transform @ matrix
    return walk(node.inputs['Vector'])


class DataTextureBaker:
    # Bound combined color bakes, not lossless single-image channel extraction.
    max_resampled_size = 4096

    def __init__(self, tree, data_directory):
        self.tree = tree
        self.directory = Path(data_directory) if data_directory else None
        self.cache = {}
        self.notes = set()

    def evaluate(self, value, alpha=None, *, color=False, resample=False, reference=None):
        sources, visited = [], set()

        def collect(value):
            if not hasattr(value, 'is_output') or value in visited:
                return
            visited.add(value)
            node = value.node
            if node.type == 'TEX_IMAGE':
                if node not in sources:
                    sources.append(node)
                return
            for socket in node.inputs:
                if socket.is_linked:
                    collect(socket.links[0].from_socket)

        collect(value)
        collect(alpha)
        anchor = reference.node if hasattr(reference, 'is_output') and reference.node.type == 'TEX_IMAGE' else None
        if anchor is None:
            anchor = sources[0] if sources else None

        def sampling(node):
            socket = node.inputs['Vector']
            vector = socket.links[0].from_socket.as_pointer() if socket.is_linked else None
            return tuple(node.image.size), vector, node.interpolation, node.extension, node.projection

        for node in sources:
            if node.image is None or node.image.source not in {'FILE', 'GENERATED'}:
                raise ValueError('Animated, tiled or missing texture cannot be baked')
            if min(node.image.size) <= 0:
                raise ValueError('Texture has no pixels')
        size = tuple(anchor.image.size) if anchor else (1, 1)
        transforms = {}
        if sources and any(sampling(node) != sampling(anchor) for node in sources):
            if not resample:
                raise ValueError('Packed channels use different dimensions or UV sampling')
            uv, anchor_matrix = _uv_transform(anchor)
            inverse = np.linalg.inv(anchor_matrix)
            desired = np.array(size, dtype=float)
            for node in sources:
                source_uv, matrix = _uv_transform(node)
                if source_uv != uv or node.projection != 'FLAT':
                    raise ValueError('Different UV sets or non-flat projection need a mesh bake')
                relative = matrix @ inverse
                transforms[node] = relative
                desired = np.maximum(desired, np.abs(relative[:2, :2]).T @ np.array(node.image.size))
            desired = np.ceil(desired).astype(int)
            size = tuple(np.maximum(1, np.minimum(desired, self.max_resampled_size)))
            if np.any(desired > self.max_resampled_size):
                self.notes.add(f'Combined texture bake limited to {size[0]} x {size[1]} pixels')

        memo = {}

        def image_pixels(node):
            image = node.image
            pixels = np.empty(image.size[0] * image.size[1] * 4, dtype=np.float32)
            image.pixels.foreach_get(pixels)
            pixels = pixels.reshape(-1, 4)
            if color:
                pixels[:, :3] = _to_linear(pixels[:, :3], image.colorspace_settings.name)
            if node not in transforms:
                return pixels
            width, height = size
            u, v = np.meshgrid((np.arange(width) + .5) / width, (np.arange(height) + .5) / height)
            matrix = transforms[node]
            x = matrix[0, 0] * u + matrix[0, 1] * v + matrix[0, 2]
            y = matrix[1, 0] * u + matrix[1, 1] * v + matrix[1, 2]
            sw, sh = image.size
            x, y = x.ravel() * sw - .5, y.ravel() * sh - .5
            data = pixels.reshape(sh, sw, 4)

            def fetch(ix, iy):
                if node.extension == 'REPEAT':
                    return data[iy % sh, ix % sw]
                if node.extension == 'MIRROR':
                    ix, iy = ix % (2 * sw), iy % (2 * sh)
                    return data[np.minimum(iy, 2 * sh - 1 - iy), np.minimum(ix, 2 * sw - 1 - ix)]
                result = data[np.clip(iy, 0, sh - 1), np.clip(ix, 0, sw - 1)]
                if node.extension == 'CLIP':
                    result = result * ((ix >= 0) & (ix < sw) & (iy >= 0) & (iy < sh))[:, None]
                return result

            if node.interpolation == 'Closest':
                return fetch(np.floor(x + .5).astype(int), np.floor(y + .5).astype(int))
            if node.interpolation != 'Linear':
                raise ValueError('Resampling supports Linear and Closest interpolation only')
            ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)
            fx, fy = (x - ix)[:, None], (y - iy)[:, None]
            return ((fetch(ix, iy) * (1 - fx) + fetch(ix + 1, iy) * fx) * (1 - fy)
                    + (fetch(ix, iy + 1) * (1 - fx) + fetch(ix + 1, iy + 1) * fx) * fy)

        def evaluate(value):
            if not hasattr(value, 'is_output'):
                a = np.asarray(value, dtype=np.float32).reshape(1, -1)
                return a[:, :3] if a.shape[1] == 4 else a
            if value in memo:
                return memo[value]
            node = value.node
            if node.type == 'TEX_IMAGE':
                space = node.image.colorspace_settings.name
                if value.name != 'Alpha' and space not in {'Non-Color', 'Raw'}:
                    if not color:
                        raise ValueError(f'Unsupported texture color space: {space}')
                pixels = image_pixels(node)
                result = pixels[:, 3:4] if value.name == 'Alpha' else pixels[:, :3]
            elif node.type == 'REROUTE':
                result = evaluate(_input(node.inputs[0]))
            elif node.type in {'RGB', 'VALUE'}:
                result = evaluate(value.default_value)
            elif node.type == 'SEPARATE_COLOR' and node.mode == 'RGB':
                rgb = evaluate(_input(node.inputs[0]))
                channel = list(node.outputs).index(value)
                result = rgb[:, channel:channel + 1] if rgb.shape[1] > 1 else rgb
            elif node.type == 'COMBINE_COLOR' and node.mode == 'RGB':
                channels = [evaluate(_input(s)) for s in node.inputs[:3]]
                if any(c.shape[1] != 1 for c in channels):
                    raise ValueError('RGB-to-value conversion requires an explicit channel')
                result = np.concatenate(np.broadcast_arrays(*channels), axis=1)
            elif node.type == 'MATH':
                a, b = (evaluate(_input(s)) for s in node.inputs[:2])
                operations = {'MULTIPLY': np.multiply, 'SUBTRACT': np.subtract, 'ADD': np.add}
                if node.operation not in operations or a.shape[1] != 1 or b.shape[1] != 1:
                    raise ValueError('Unsupported mask arithmetic')
                result = operations[node.operation](a, b)
                if node.use_clamp:
                    result = np.clip(result, 0, 1)
            elif node.type == 'MIX_RGB':
                factor, a, b = (evaluate(_input(s)) for s in node.inputs)
                factor = np.clip(factor, 0, 1)
                operations = {'MIX': lambda a, b: b, 'MULTIPLY': np.multiply,
                              'ADD': np.add, 'SUBTRACT': np.subtract}
                if node.blend_type not in operations or node.use_alpha:
                    raise ValueError('Unsupported color blend')
                result = a * (1 - factor) + operations[node.blend_type](a, b) * factor
                if node.use_clamp:
                    result = np.clip(result, 0, 1)
            else:
                raise ValueError(f'{node.type} needs a mesh/shader bake')
            memo[value] = result
            return result

        rgb = evaluate(value)
        opacity = evaluate(alpha) if alpha is not None else (rgb if rgb.shape[1] == 1 else np.ones((1, 1)))
        if opacity.shape[1] != 1:
            raise ValueError('Packed alpha must be a scalar channel')
        return rgb, opacity, size, anchor

    def bake(self, value, name, alpha=None, *, color=False, resample=False, reference=None, usage='Material Map'):
        if self.directory is None:
            raise ValueError('Current project has no data directory')
        rgb, opacity, size, anchor = self.evaluate(value, alpha, color=color, resample=resample, reference=reference)
        pixels = np.empty((size[0] * size[1], 4), dtype=np.float32)
        if np.any(rgb > 1) or np.any(rgb < 0):
            self.notes.add(f'{name}: out-of-range texture colors were clamped to the TIFF range')
        pixels[:, :3] = _srgb(np.clip(rgb, 0, 1)) if color else rgb
        pixels[:, 3:4] = opacity
        pixels = np.clip(pixels, 0, 1)
        name = re.sub(r'[^a-z0-9_]+', '_', name.lower()).strip('_')
        space = 'sRGB' if color else 'Non-Color'
        digest = sha256(str((size, space)).encode() + pixels.tobytes()).hexdigest()[:16]
        path = self.directory / 'foundry_material_conversions' / f'{name}_{digest}.tif'
        key = str(path), anchor.as_pointer() if anchor else None
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        path.parent.mkdir(parents=True, exist_ok=True)
        image = bpy.data.images.new(path.stem, width=size[0], height=size[1], alpha=True)
        image.colorspace_settings.name = space
        image.alpha_mode = 'CHANNEL_PACKED'
        image.pixels.foreach_set(pixels.ravel())
        image.filepath_raw = str(path)
        image.file_format = 'TIFF'
        try:
            # Image.save uses Adobe Deflate, unsupported by the Halo TIFF reader.
            write_image_tiff(image, path)
            # Persist the saved pixels when the .blend is reopened.
            image.source = 'FILE'
            image.reload()
        except Exception:
            bpy.data.images.remove(image)
            raise
        if hasattr(image, 'nwo'):
            image.nwo.filepath = str(path.relative_to(self.directory))
            image.nwo.source_name = path.name
            image.nwo.bitmap_type = usage
        image['foundry_channel_conversion'] = True
        node = self.tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        node.label = name.replace('_', ' ').title()
        if anchor:
            node.interpolation = anchor.interpolation
            node.extension = anchor.extension
            node.projection = anchor.projection
            node.projection_blend = anchor.projection_blend
            if anchor.inputs['Vector'].is_linked:
                self.tree.links.new(anchor.inputs['Vector'].links[0].from_socket, node.inputs['Vector'])
        self.cache[key] = node
        return node

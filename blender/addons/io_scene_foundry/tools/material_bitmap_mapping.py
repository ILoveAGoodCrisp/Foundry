"""Bake channel-only texture expressions to lossless target-project TIFFs.

This is intentionally not a general shader baker. It evaluates data textures
only, with identical dimensions and sampling/UV inputs. Unsupported expressions
stay procedural and are reported rather than flattening the wrong UV mapping.
"""

from hashlib import sha256
from pathlib import Path

import bpy
import numpy as np


class DataTextureBaker:
    def __init__(self, tree, data_directory):
        self.tree = tree
        self.directory = Path(data_directory) if data_directory else None
        self.cache = {}

    def bake(self, value, name, alpha=None):
        if self.directory is None:
            raise ValueError('Current project has no data directory')
        sources = []
        memo = {}

        def input_value(socket):
            return socket.links[0].from_socket if socket.is_linked else socket.default_value

        def evaluate(value):
            if not hasattr(value, 'is_output'):
                a = np.asarray(value, dtype=np.float32).reshape(1, -1)
                return a[:, :3] if a.shape[1] == 4 else a
            if value in memo:
                return memo[value]
            node = value.node
            if node.type == 'TEX_IMAGE':
                image = node.image
                if image is None or image.source not in {'FILE', 'GENERATED'}:
                    raise ValueError('Animated, tiled or missing data texture')
                if image.colorspace_settings.name not in {'Non-Color', 'Raw'}:
                    raise ValueError('Color-managed texture requires a color bake')
                if node not in sources:
                    sources.append(node)
                count = image.size[0] * image.size[1]
                if count == 0:
                    raise ValueError('Data texture has no pixels')
                pixels = np.empty(count * 4, dtype=np.float32)
                image.pixels.foreach_get(pixels)
                pixels = pixels.reshape(-1, 4)
                result = pixels[:, 3:4] if value.name == 'Alpha' else pixels[:, :3]
            elif node.type == 'SEPARATE_COLOR' and node.mode == 'RGB':
                rgb = evaluate(input_value(node.inputs[0]))
                channel = list(node.outputs).index(value)
                result = rgb[:, channel:channel + 1]
            elif node.type == 'COMBINE_COLOR' and node.mode == 'RGB':
                channels = [evaluate(input_value(s)) for s in node.inputs[:3]]
                if any(c.shape[1] != 1 for c in channels):
                    raise ValueError('RGB-to-value conversion requires a color bake')
                result = np.concatenate(np.broadcast_arrays(*channels), axis=1)
            elif node.type == 'MATH':
                a, b = (evaluate(input_value(s)) for s in node.inputs[:2])
                operations = {'MULTIPLY': np.multiply, 'SUBTRACT': np.subtract, 'ADD': np.add}
                if node.operation not in operations or a.shape[1] != 1 or b.shape[1] != 1:
                    raise ValueError('Unsupported mask arithmetic')
                result = operations[node.operation](a, b)
                if node.use_clamp:
                    result = np.clip(result, 0, 1)
            else:
                raise ValueError(f'{node.type} needs a shader bake')
            memo[value] = result
            return result

        rgb = evaluate(value)
        opacity = evaluate(alpha) if alpha is not None else (rgb if rgb.shape[1] == 1 else np.ones((1, 1)))
        if not sources:
            return None
        reference = sources[0]

        def sampling(node):
            vector = node.inputs['Vector']
            uv = vector.links[0].from_socket.as_pointer() if vector.is_linked else None
            return (tuple(node.image.size), uv, node.interpolation, node.extension, node.projection)

        if any(sampling(node) != sampling(reference) for node in sources[1:]):
            raise ValueError('Packed channels use different dimensions or UV sampling')
        count = reference.image.size[0] * reference.image.size[1]
        pixels = np.empty((count, 4), dtype=np.float32)
        pixels[:, :3] = rgb
        pixels[:, 3:4] = opacity
        pixels = np.clip(pixels, 0, 1)
        digest = sha256(pixels.tobytes()).hexdigest()[:16]
        relative = Path('foundry_material_conversions', f'{name}_{digest}.tif')
        path = self.directory / relative
        key = str(path), sampling(reference)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        path.parent.mkdir(parents=True, exist_ok=True)
        image = bpy.data.images.new(path.stem, width=reference.image.size[0],
                                    height=reference.image.size[1], alpha=True)
        image.colorspace_settings.name = 'Non-Color'
        image.alpha_mode = 'CHANNEL_PACKED'
        image.pixels.foreach_set(pixels.ravel())
        image.filepath_raw = str(path)
        image.file_format = 'TIFF'
        try:
            # Image.save (not save_render) avoids display/view transforms and
            # preserves the independent packed alpha channel.
            image.save()
        except Exception:
            bpy.data.images.remove(image)
            raise
        if hasattr(image, 'nwo'):
            image.nwo.filepath = str(relative)
            image.nwo.source_name = path.name
            image.nwo.bitmap_type = 'Material Map'
        image['foundry_channel_conversion'] = True
        node = self.tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        node.label = name.replace('_', ' ').title()
        node.interpolation = reference.interpolation
        node.extension = reference.extension
        node.projection = reference.projection
        node.projection_blend = reference.projection_blend
        if reference.inputs['Vector'].is_linked:
            self.tree.links.new(reference.inputs['Vector'].links[0].from_socket, node.inputs['Vector'])
        else:
            node.inputs['Vector'].default_value = reference.inputs['Vector'].default_value
        self.cache[key] = node
        return node

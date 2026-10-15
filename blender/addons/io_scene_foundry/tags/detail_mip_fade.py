"""Distance-based H3/ODST detail previews using the bitmap's stored mip chain.

This approximates LOD with camera distance, not screen derivatives. Mip 1 is
selected at the exposed distance, mip 2 at twice that distance, etc. The
original image and mapping stay upstream of the helper for shader export.
"""
from hashlib import sha256
from pathlib import Path

import bpy
import numpy as np

from .. import utils
from ..coordinate_system import CoordinateSystem
from .backend import read_only_tags
from .bitmap import BitmapTag
from .halo3_odst_io import _remember

REVISION = 1


def _level_bytes(format_name, width, height):
    if format_name in {'dxt1', 'dxt3', 'dxt5', 'dxn'}:
        return ((width + 3) // 4) * ((height + 3) // 4) * (8 if format_name == 'dxt1' else 16)
    if format_name in {'a8r8g8b8', 'x8r8g8b8'}:
        return width * height * 4
    return None


def authored_mips(bitmap):
    """Decode lower PC mips without modifying or saving the source document.

    The native TIFF API currently exposes mip 0 only. A detached tag clone
    selects each mip by its validated dimensions and byte offset. Unsupported
    layouts keep their existing preview; no lower levels are synthesized.
    """
    if bitmap.game not in {'halo3', 'halo3odst'} or len(bitmap.block_bitmaps) != 1:
        return []
    usage = bitmap.longenum_usage.options().current_name or ''
    if usage != 'Detail Map' and not usage.startswith('Detail Bump Map'):
        return []
    entry = bitmap.block_bitmaps[0]
    if (bitmap.required_field(entry, 'type').options().current_name != '2D texture'
            or int(bitmap.value(entry, 'depth')) != 1):
        return []
    width, height = (int(bitmap.value(entry, key)) for key in ('width', 'height'))
    count = int(bitmap.value(entry, 'mipmap count')) + 1
    if min(width, height) <= 0 or count <= 1:
        return []
    if count > max(width, height).bit_length():
        raise ValueError('Invalid authored mip count')
    format_name = bitmap.required_field(entry, 'format').options().current_name.lower()
    if _level_bytes(format_name, width, height) is None:
        return []
    pixels = bitmap.required_field(bitmap.tag.root(), 'processed pixel data').as_data()
    if not pixels:  # Pageable/Xbox layouts need a different decoder.
        return []
    offset = int(bitmap.value(entry, 'pixels offset'))
    layout = []
    for level in range(count):
        size = _level_bytes(format_name, width, height)
        if offset < 0 or offset + size > len(pixels):
            raise ValueError(f'Truncated authored mip {level}')
        layout.append((width, height, offset))
        offset += size
        width, height = max(1, width // 2), max(1, height // 2)

    serialized = bitmap.tag.write_to_bytes()
    result = []
    for width, height, offset in layout[1:]:
        clone = bitmap.api.TagFile.read_from_bytes(serialized)
        for key, value in (('width', width), ('height', height),
                           ('pixels offset', offset), ('mipmap count', 0)):
            clone.root().field('bitmaps').as_block()[0].field(key).set(value)
        w, h, rgba = BitmapTag._uncompressed_rgba_tiff(clone.bitmap_tiff(0))
        if (w, h) != (width, height):
            raise ValueError('Authored mip decoder returned unexpected dimensions')
        result.append((width, height, rgba))
    return result


def _linear_pixels(rgba, bitmap):
    pixels = np.frombuffer(rgba, dtype=np.uint8).reshape(-1, 4).astype(np.float32) / 255
    # Float preview images contain linear RGB, independent of extraction prefs.
    # Alpha and normal components must never receive a colour transfer curve.
    if not bitmap.used_as_normal_map():
        rgb = pixels[:, :3]
        if bitmap.get_gamma_name() == 'srgb':
            pixels[:, :3] = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
        else:
            pixels[:, :3] = rgb ** bitmap.get_gamma_value()
    return pixels


def _math(tree, operation, a, b, location):
    node = tree.nodes.new('ShaderNodeMath')
    node.operation = operation
    node.location = location
    for socket, value in zip(node.inputs, (a, b)):
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return node.outputs[0]


def _mix(tree, kind, a, b, factor, location):
    node = tree.nodes.new('ShaderNodeMix')
    node.data_type = kind
    node.clamp_factor = True
    node.clamp_result = False
    node.location = location
    tree.links.new(factor, node.inputs[0])
    sockets = node.inputs[6:8] if kind == 'RGBA' else node.inputs[2:4]
    for socket, value in zip(sockets, (a, b)):
        if isinstance(value, bpy.types.NodeSocket):
            tree.links.new(value, socket)
        else:
            socket.default_value = value
    return node.outputs[2 if kind == 'RGBA' else 0]


def _build_group(name, bitmap, mips, texture):
    group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
    for label, kind in (('Original Color', 'Color'), ('Original Alpha', 'Float'),
                        ('Vector', 'Vector'), ('Mip 1 Distance', 'Float'), ('Fade Amount', 'Float')):
        socket = group.interface.new_socket(label, in_out='INPUT', socket_type='NodeSocket' + kind)
        if label == 'Mip 1 Distance':
            socket.subtype = 'DISTANCE'
            socket.default_value = 1
            socket.min_value = .0001
            socket.description = 'Preview distance for mip 1; each further mip doubles this distance'
        elif label == 'Fade Amount':
            socket.default_value = 1
            socket.min_value, socket.max_value = 0, 1
            socket.description = 'Preview only: zero keeps the original full-detail image'
    for label, kind in (('Color', 'Color'), ('Alpha', 'Float')):
        group.interface.new_socket(label, in_out='OUTPUT', socket_type='NodeSocket' + kind)
    source = group.nodes.new('NodeGroupInput'); source.location = (-1100, 0)
    camera = group.nodes.new('ShaderNodeCameraData'); camera.location = (-1100, 300)
    distance = _math(group, 'MAXIMUM', source.outputs['Mip 1 Distance'], .0001, (-900, 100))
    ratio = _math(group, 'DIVIDE', camera.outputs['View Distance'], distance, (-700, 300))
    ratio = _math(group, 'MAXIMUM', ratio, .5, (-500, 300))
    lod = _math(group, 'LOGARITHM', ratio, 2, (-300, 300))
    lod = _math(group, 'ADD', lod, 1, (-100, 300))
    color, alpha = source.outputs['Original Color'], source.outputs['Original Alpha']
    normal = bitmap.used_as_normal_map()
    for level, (width, height, rgba) in enumerate(mips, 1):
        pixels = _linear_pixels(rgba, bitmap)
        if np.all(pixels == pixels[0]):
            mip_color, mip_alpha = tuple(pixels[0]), float(pixels[0, 3])
        else:
            image = bpy.data.images.new(f'{name} mip {level}', width=width, height=height, float_buffer=True)
            image.colorspace_settings.name = 'Non-Color' if normal else 'Linear Rec.709'
            image.alpha_mode = 'CHANNEL_PACKED'
            image.nwo.export = False
            image['foundry_preview_mip'] = level
            # Native TIFF rows are top-down; Blender's pixel buffer is bottom-up.
            image.pixels.foreach_set(pixels.reshape(height, width, 4)[::-1].copy().ravel())
            image.pack()
            sample = group.nodes.new('ShaderNodeTexImage')
            sample.image = image
            sample.extension = texture.extension
            sample.interpolation = texture.interpolation
            sample.location = (level * 260, -300)
            group.links.new(source.outputs['Vector'], sample.inputs['Vector'])
            mip_color, mip_alpha = sample.outputs['Color'], sample.outputs['Alpha']
        factor = _math(group, 'SUBTRACT', lod, level - 1, (level * 260, 300))
        color = _mix(group, 'RGBA', color, mip_color, factor, (level * 260, 0))
        alpha = _mix(group, 'FLOAT', alpha, mip_alpha, factor, (level * 260, -600))
    x = (len(mips) + 1) * 260
    color = _mix(group, 'RGBA', source.outputs['Original Color'], color, source.outputs['Fade Amount'], (x, 0))
    alpha = _mix(group, 'FLOAT', source.outputs['Original Alpha'], alpha, source.outputs['Fade Amount'], (x, -300))
    output = group.nodes.new('NodeGroupOutput'); output.location = (x + 250, 0)
    group.links.new(color, output.inputs['Color'])
    group.links.new(alpha, output.inputs['Alpha'])
    group['foundry_detail_mip_fade'] = REVISION
    return group


def setup_detail_fade(shader, tree, root):
    """Wrap direct static detail samples after coordinate/address setup."""
    if shader.game not in {'halo3', 'halo3odst'}:
        return
    textures = {}
    for port in root.inputs:
        parameter = port.name.partition('.')[0]
        if 'detail' not in parameter.lower() or not port.is_linked:
            continue
        texture = port.links[0].from_node
        if texture.type == 'TEX_IMAGE':
            textures.setdefault(texture, parameter)
    for texture, parameter in textures.items():
        image = texture.image
        if image is None or image.source != 'FILE' or texture.projection != 'FLAT':
            continue
        path = image.get('foundry_source_bitmap_path')
        if not path:
            continue
        name = None
        try:
            full_path = (Path(shader.tags_dir) / path).resolve()
            stat = full_path.stat()
            identity = (REVISION, shader.game, str(full_path), stat.st_mtime_ns, stat.st_size,
                        texture.extension, texture.interpolation)
            key = sha256(repr(identity).encode()).hexdigest()[:16]
            name = f'Halo Detail Fade {key}'
            group = bpy.data.node_groups.get(name)
            if group is None:
                with read_only_tags(), BitmapTag(path=path) as bitmap:
                    mips = authored_mips(bitmap)
                    if not mips:
                        continue
                    group = _build_group(name, bitmap, mips, texture)
        except (OSError, ValueError, RuntimeError) as error:
            incomplete = bpy.data.node_groups.get(name) if name else None
            if incomplete is not None and not incomplete.get('foundry_detail_mip_fade') and not incomplete.users:
                bpy.data.node_groups.remove(incomplete)
            utils.print_warning(f'Detail mip preview unavailable for {path}: {error}')
            continue

        # Capture consumers first so the original-to-helper links cannot loop.
        consumers = [(link.from_socket.name, link.to_socket)
                     for output in texture.outputs for link in output.links]
        helper = tree.nodes.new('ShaderNodeGroup'); helper.node_tree = group
        helper.label = parameter + ' - detail fade'
        helper.location = (texture.location.x + 300, texture.location.y)
        helper.inputs['Mip 1 Distance'].default_value = 1 / CoordinateSystem.from_scene(utils.get_scene_props()).meters_per_unit
        tree.links.new(texture.outputs['Color'], helper.inputs['Original Color'])
        tree.links.new(texture.outputs['Alpha'], helper.inputs['Original Alpha'])
        vector = texture.inputs['Vector']
        if vector.is_linked:
            tree.links.new(vector.links[0].from_socket, helper.inputs['Vector'])
        else:
            uv = tree.nodes.new('ShaderNodeTexCoord')
            tree.links.new(uv.outputs['UV'], helper.inputs['Vector'])
        for channel, destination in consumers:
            tree.links.new(helper.outputs[channel], destination)
        # Existing export resolution follows this source through the helper's
        # inputs. It also respects direct replacement/relinking by the user.
        _remember(root, texture, parameter)

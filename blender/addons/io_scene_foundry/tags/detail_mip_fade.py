"""Distance-based Halo detail previews using stored bitmap mips.

This approximates LOD with camera distance, not screen derivatives. Mip 1 is
selected at the exposed distance, mip 2 at twice that distance, etc. The
original image and mapping stay upstream of the helper for shader export.
"""
from hashlib import sha256
import json
from pathlib import Path

import bpy
import numpy as np

from .. import utils
from ..coordinate_system import CoordinateSystem
from .backend import read_only_tags
from .bitmap import BitmapTag
from .halo3_odst_io import _remember
from .halo3_shader_io import render_method_family

REVISION = 4
CLASSIC_GAMES = frozenset({'halo1', 'halo2'})
GAMES = CLASSIC_GAMES | {'halo3', 'halo3odst', 'reach'}

# These are surface colour/normal samples, not any parameter containing
# "detail". In particular, masks, emission, water and screen-space lookups
# must not acquire a camera-distance fade merely because of their name.
SURFACE_FAMILIES = frozenset({
    'shader', 'shader_custom', 'shader_skin', 'shader_foliage', 'shader_glass',
    'shader_mux', 'shader_mux_material', 'shader_halogram',
})
SURFACE_DETAILS = frozenset({
    'detail_map', 'detail_map2', 'detail_map3', 'detail_map_overlay',
    'bump_detail_map', 'bump_detail_map0', 'bump_detail_map2', 'bump_detail_map3',
    'bump_detail_masked_map',
})
TERRAIN_DETAILS = frozenset(
    f'{role}_m_{layer}' for layer in range(4)
    for role in ('detail_map', 'detail_bump')
)
H1_DETAILS = {
    'shader_model': frozenset({'Detail Map'}),
    'shader_environment': frozenset({'Primary Detail Map', 'Secondary Detail Map', 'Micro Detail Map'}),
}
H2_DETAILS = frozenset({
    'detail_map', 'secondary_detail_map', 'detail_map_a', 'detail_map_b', 'detail_map_c',
    'blend_detail_map_1', 'blend_detail_map_2', 'overlay_detail_map',
})


def detail_parameters(shader, root=None):
    """Return the surface detail roles supported by this render-method family.

    Terrain's material blending, base-distance blending and four-material
    detail-bump switch remain in the shader group, downstream of these samples.
    """
    if shader.game not in GAMES:
        return frozenset()
    if shader.game == 'halo1':
        return H1_DETAILS.get(shader.system_path.suffix[1:].lower(), frozenset())
    if shader.game == 'halo2':
        # Template role matters: detail_map also occurs in sky, scope and
        # emission-only shaders. Only reviewed surface templates participate.
        path = root.node_tree.get('h2_template_path', '') if root else ''
        path = path.replace('\\', '/').lower()
        folder, _, name = path.rpartition('/')
        surface = (folder.endswith('/opaque') and (
            (name.startswith('tex_') and name not in {'tex_illum', 'tex_illum_bloom'})
            or name in {'prt_simple', 'prt_lightmap', 'prt_scarab'}))
        glass = folder.endswith('/transparent') and name in {'two_alpha_env_detail', 'two_alpha_env_multichannel'}
        return H2_DETAILS if surface or glass else frozenset()
    family = render_method_family(shader)
    if family == 'shader_terrain':
        return TERRAIN_DETAILS
    return SURFACE_DETAILS if family in SURFACE_FAMILIES else frozenset()


def _detail_inputs(shader, root):
    if shader.game == 'halo1' and shader.system_path.suffix.lower() == '.shader_transparent_glass':
        # Glass sockets are bound to schema paths, independently of UI labels.
        bindings = json.loads(root.node_tree.get('h1_socket_bindings', '{}'))
        for identifier, binding in bindings.items():
            if binding.get('path') == ['diffuse', 'diffuse detail map'] and binding.get('role') == 'bitmap':
                port = root.inputs.get(identifier)
                if port is not None:
                    yield port, port.name
        return
    parameters = detail_parameters(shader, root)
    for port in root.inputs:
        parameter = port.name.partition('.')[0]
        if shader.game == 'halo1':
            parameter = parameter.removesuffix(' Alpha')
        if parameter in parameters:
            yield port, parameter


def original_texture(port):
    """Resolve preview wrappers without searching their atlas or UV inputs."""
    seen = set()
    while port.is_linked:
        node = port.links[0].from_node
        if node in seen:
            return None
        seen.add(node)
        if node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'}:
            return node
        if node.type == 'REROUTE':
            port = node.inputs[0]
        elif node.type == 'GROUP' and node.node_tree and node.node_tree.get('foundry_detail_mip_fade'):
            port = node.inputs['Original Color']
        else:
            return None
    return None


def _level_bytes(format_name, width, height):
    if format_name in {'dxt1', 'dxt3', 'dxt5', 'dxn'}:
        return ((width + 3) // 4) * ((height + 3) // 4) * (8 if format_name == 'dxt1' else 16)
    if format_name in {'a8r8g8b8', 'x8r8g8b8'}:
        return width * height * 4
    if format_name in {'r5g6b5', 'a1r5g5b5', 'a4r4g4b4'}:
        return width * height * 2
    return None


def authored_mips(bitmap):
    """Decode lower PC mips without modifying or saving the source document.

    The native TIFF API currently exposes mip 0 only. A detached tag clone
    selects each mip by its validated dimensions and byte offset. Unsupported
    layouts keep their existing preview; no lower levels are synthesized.
    Eligibility is decided by the shader role at the call site. Terrain often
    places ordinary Diffuse/Bump bitmaps in its detail slots.
    """
    if bitmap.game not in GAMES or len(bitmap.block_bitmaps) != 1:
        return []
    entry = bitmap.block_bitmaps[0]
    if (bitmap.required_field(entry, 'type').options().current_name.lower() != '2d texture'
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
    offset_name = 'pixel data offset' if bitmap.game == 'halo1' else 'pixels offset'
    offset = int(bitmap.value(entry, offset_name))
    layout = []
    for level in range(count):
        size = _level_bytes(format_name, width, height)
        if offset < 0 or offset + size > len(pixels):
            raise ValueError(f'Truncated authored mip {level}')
        layout.append((width, height, offset))
        offset += size
        width, height = max(1, width // 2), max(1, height // 2)

    classic = bitmap.game in CLASSIC_GAMES
    if classic:
        # Classic tags have no read_from_bytes API. Re-open a detached handle,
        # then select validated slices in memory; never save either document.
        schema = bitmap.definitions / bitmap.definitions_profile / 'bitmap.json'
        clone = bitmap.api.TagFile.read_classic(bitmap.system_path, schema)
    else:
        serialized = bitmap.tag.write_to_bytes()
    result = []
    for width, height, offset in layout[1:]:
        if not classic:
            clone = bitmap.api.TagFile.read_from_bytes(serialized)
        for key, value in (('width', width), ('height', height),
                           (offset_name, 0 if classic else offset), ('mipmap count', 0)):
            clone.root().field('bitmaps').as_block()[0].field(key).set(value)
        if classic:
            size = _level_bytes(format_name, width, height)
            clone.root().field('processed pixel data').set(pixels[offset:offset+size])
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


def _atlas_sample(group, image, uv, rect, interpolation, bounded):
    """Filter texel-centre reads at mip 0, avoiding automatic atlas mip bleed.

    Closest image sampling disables Eevee's automatic mip chain. Linear and
    cubic filtering are reconstructed explicitly; all reads share one sampler.
    """
    x, y, width, height = rect
    split = group.nodes.new('ShaderNodeSeparateXYZ')
    group.links.new(uv, split.inputs[0])
    cubic = interpolation in {'Cubic', 'Smart'}
    nearest = interpolation == 'Closest'
    positions, weights = [], []
    for axis, size in enumerate((width, height)):
        pos = _math(group, 'MULTIPLY', split.outputs[axis], size, (0, -900))
        if not nearest:
            pos = _math(group, 'SUBTRACT', pos, .5, (0, -900))
        # Keep outside Extend/Clip coordinates within the repeated/transparent
        # gutter, while retaining cubic weights near the image boundary.
        if bounded:
            pos = _math(group, 'MAXIMUM', pos, -2, (0, -900))
            pos = _math(group, 'MINIMUM', pos, size+1, (0, -900))
        positions.append(_math(group, 'FLOOR', pos, 0, (0, -900)))
        t = _math(group, 'FRACT', pos, 0, (0, -900))
        if cubic:
            # Uniform cubic B-spline, matching Image Texture's Cubic filter.
            t2 = _math(group, 'MULTIPLY', t, t, (0, -900))
            t3 = _math(group, 'MULTIPLY', t2, t, (0, -900))
            def polynomial(a, b, c, d):
                total = d
                for coefficient, power in ((a,t3), (b,t2), (c,t)):
                    if coefficient:
                        total = _math(group, 'ADD', total, _math(group, 'MULTIPLY', power, coefficient, (0,-900)), (0,-900))
                return _math(group, 'DIVIDE', total, 6, (0,-900))
            weights.append([polynomial(-1,3,-3,1), polynomial(3,-6,0,4),
                            polynomial(-3,3,3,1), polynomial(1,0,0,0)])
        else:
            weights.append(t)
    base = group.nodes.new('ShaderNodeCombineXYZ')
    for axis in range(2): group.links.new(positions[axis], base.inputs[axis])
    offsets = (-1,0,1,2) if cubic else (0,) if nearest else (0,1)
    rows = []
    for dy in offsets:
        row = []
        for dx in offsets:
            vector = group.nodes.new('ShaderNodeVectorMath'); vector.operation = 'ADD'
            group.links.new(base.outputs[0], vector.inputs[0])
            vector.inputs[1].default_value = (dx, dy, 0)
            # Nearest at UV=1 and far-out clip coordinates must stay inside
            # their own rectangle/gutter rather than reading another mip.
            low, high = (-2,-2,0), (width+1,height+1,0)
            for operation, bound in (('MAXIMUM', low), ('MINIMUM', high)):
                clamp = group.nodes.new('ShaderNodeVectorMath'); clamp.operation = operation
                group.links.new(vector.outputs[0], clamp.inputs[0]); clamp.inputs[1].default_value = bound
                vector = clamp
            mapped = group.nodes.new('ShaderNodeVectorMath'); mapped.operation = 'MULTIPLY_ADD'
            group.links.new(vector.outputs[0], mapped.inputs[0])
            mapped.inputs[1].default_value = (1/image.size[0], 1/image.size[1], 0)
            mapped.inputs[2].default_value = ((x+.5)/image.size[0], (y+.5)/image.size[1], 0)
            sample = group.nodes.new('ShaderNodeTexImage'); sample.image = image
            sample.extension = 'EXTEND'; sample.interpolation = 'Closest'
            group.links.new(mapped.outputs[0], sample.inputs['Vector'])
            row.append((sample.outputs['Color'], sample.outputs['Alpha']))
        rows.append(row)

    def blend(samples, weight):
        if nearest: return samples[0]
        if not cubic:
            return (_mix(group, 'RGBA', samples[0][0], samples[1][0], weight, (0,-900)),
                    _mix(group, 'FLOAT', samples[0][1], samples[1][1], weight, (0,-900)))
        color, alpha = None, 0
        for (rgb, a), w in zip(samples, weight):
            scale = group.nodes.new('ShaderNodeVectorMath'); scale.operation = 'SCALE'
            group.links.new(rgb, scale.inputs[0]); group.links.new(w, scale.inputs['Scale'])
            if color is None: color = scale.outputs[0]
            else:
                add = group.nodes.new('ShaderNodeVectorMath'); add.operation = 'ADD'
                group.links.new(color, add.inputs[0]); group.links.new(scale.outputs[0], add.inputs[1])
                color = add.outputs[0]
            alpha = _math(group, 'ADD', alpha, _math(group, 'MULTIPLY', a, w, (0,-900)), (0,-900))
        return color, alpha
    return blend([blend(row, weights[0]) for row in rows], weights[1])


def _mip_samples(group, source, bitmap, mips, texture):
    """Share one atlas sampler across authored levels to fit layered Eevee materials.

    Each rectangle has a two-texel gutter for linear/cubic filtering. Address
    the UV inside its own rectangle before mapping into the atlas, so wrapping
    never crosses into another mip. Uniform levels still use constants.
    """
    samples, tiles = {}, []
    for level, (width, height, rgba) in enumerate(mips, 1):
        pixels = _linear_pixels(rgba, bitmap)
        if texture.extension != 'CLIP' and np.all(pixels == pixels[0]):
            samples[level] = tuple(pixels[0]), float(pixels[0, 3])
        else:
            tiles.append((level, pixels.reshape(height, width, 4)[::-1]))

    if tiles:
        pad = 2
        width = max(p.shape[1] for _, p in tiles) + 2 * pad
        height = sum(p.shape[0] + 2 * pad for _, p in tiles)
        atlas = np.zeros((height, width, 4), dtype=np.float32)
        rects, y = {}, 0
        mode = {'REPEAT': 'wrap', 'MIRROR': 'symmetric', 'CLIP': 'constant'}.get(texture.extension, 'edge')
        for level, pixels in tiles:
            h, w = pixels.shape[:2]
            atlas[y:y+h+2*pad, :w+2*pad] = np.pad(pixels, ((pad,pad),(pad,pad),(0,0)), mode=mode)
            rects[str(level)] = [pad, y+pad, w, h]
            y += h + 2 * pad
        image = bpy.data.images.new(group.name + ' mip atlas', width=width, height=height, float_buffer=True)
        image.colorspace_settings.name = 'Non-Color' if bitmap.used_as_normal_map() else 'Linear Rec.709'
        image.alpha_mode = 'CHANNEL_PACKED'
        image.nwo.export = False
        image['foundry_preview_mip'] = True
        image['foundry_mip_rects'] = rects
        image.pixels.foreach_set(atlas.ravel())
        image.pack()

        split = group.nodes.new('ShaderNodeSeparateXYZ')
        group.links.new(source.outputs['Vector'], split.inputs[0])
        combine = group.nodes.new('ShaderNodeCombineXYZ')
        for axis in range(2):
            coordinate = split.outputs[axis]
            if texture.extension == 'REPEAT':
                coordinate = _math(group, 'FRACT', coordinate, 0, (-600, -900-axis*160))
            elif texture.extension == 'MIRROR':
                coordinate = _math(group, 'PINGPONG', coordinate, 1, (-600, -900-axis*160))
            group.links.new(coordinate, combine.inputs[axis])
        for level, _ in tiles:
            samples[level] = _atlas_sample(group, image, combine.outputs[0], rects[str(level)],
                                          texture.interpolation, texture.extension in {'EXTEND', 'CLIP'})
    return samples


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
    samples = _mip_samples(group, source, bitmap, mips, texture)
    for level in range(1, len(mips) + 1):
        mip_color, mip_alpha = samples[level]
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
    textures = {}
    for port, parameter in _detail_inputs(shader, root):
        if not port.is_linked:
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

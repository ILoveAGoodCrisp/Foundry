"""Reach water's independent painted UVs and precomputed slope-array samples.

water_shading.fx uses base_tex for color/shoreline paint and texcoord for
waves/foam. Array layers are precomputed assets, not a runtime FFT simulation.
"""
import bpy
import numpy as np
from pathlib import Path
from uuid import uuid4
from .halo3_odst_io import (_put, _value, _texture, _mapping, _set_coordinates,
                           _remember, _vector, source_texture)

SAMPLER_CONTROLS = ('time_warp', 'time_warp_aux', 'detail', 'detail_slope_scale_x',
                    'detail_slope_scale_y', 'detail_slope_scale_z', 'detail_slope_steepness')
TRANSFORM_CONTROLS = ('Scale X', 'Scale Y', 'Scale Multiplier', 'Translate X', 'Translate Y')


def sync_water_sampling(tree):
    """Keep imported helper controls following edits to the public water node."""
    if not tree.is_editable:
        return 0
    owners = {n.get('reach_water_owner'): n for n in tree.nodes if n.get('reach_water_owner')}
    changes = 0
    def copy(source, destination):
        nonlocal changes
        value = _value(source)
        if isinstance(value, bpy.types.NodeSocket):
            if not destination.is_linked or destination.links[0].from_socket != value:
                tree.links.new(value, destination); changes += 1
        elif destination.is_linked or destination.default_value != value:
            for link in list(destination.links): tree.links.remove(link)
            destination.default_value = value; changes += 1
    for sampler in tree.nodes:
        root = owners.get(sampler.get('reach_water_sampler_owner'))
        if root is None: continue
        for key in SAMPLER_CONTROLS: copy(root.inputs[key], sampler.inputs[key])
        for parameter, prefix in [('wave_displacement_array', 'Main'), ('wave_slope_array', 'Aux')]:
            texture = source_texture(root, root.inputs[parameter + '.rgb']) or _texture(root, parameter)
            mapping = _mapping(texture)
            if mapping:
                for key in TRANSFORM_CONTROLS: copy(mapping.inputs[key], sampler.inputs[prefix + ' ' + key])
    return changes


def padded_slope_atlas(image):
    """Pad every slice independently so linear filtering wraps within it."""
    shape = image.get('foundry_bitmap_shape')
    if not shape or len(shape) != 3:
        return None
    width, height, depth = map(int, shape)
    if depth < 2 or tuple(image.size) != (width, height * depth):
        return None
    name = image.name + ' - Reach water padded slices'
    atlas = bpy.data.images.get(name)
    file = Path(bpy.path.abspath(image.filepath)) if image.filepath else None
    signature = str((tuple(shape), file.stat().st_mtime_ns if file and file.is_file() else None))
    if atlas is not None and atlas.get('reach_water_source_signature') == signature and not image.is_dirty:
        return atlas
    # Read encoded normal channels directly, without a color transfer curve.
    source = image
    if image.colorspace_settings.name != 'Non-Color':
        source = image.copy()
        source.colorspace_settings.name = 'Non-Color'
    pixels = np.empty(width * height * depth * 4, np.float32)
    source.pixels.foreach_get(pixels)
    # TIFF has slice 0 at the top; Blender pixel rows start at the bottom.
    layers = pixels.reshape(depth, height, width, 4)[::-1]
    layers = np.pad(layers, ((0, 0), (1, 1), (1, 1), (0, 0)), mode='wrap')
    if atlas is None:
        atlas = bpy.data.images.new(name, width=width + 2,
                                    height=(height + 2) * depth, float_buffer=True)
    elif tuple(atlas.size) != (width + 2, (height + 2) * depth):
        atlas.scale(width + 2, (height + 2) * depth)
    atlas.colorspace_settings.name = 'Non-Color'
    atlas.alpha_mode = 'CHANNEL_PACKED'
    atlas.pixels.foreach_set(layers.reshape(-1))
    atlas.pack()
    atlas['foundry_bitmap_shape'] = shape
    atlas['reach_water_source_signature'] = signature
    if source != image:
        bpy.data.images.remove(source)
    return atlas


def _slope_closure(tree, image):
    start = tree.nodes.new('NodeClosureInput')
    end = tree.nodes.new('NodeClosureOutput')
    start.pair_with_output(end)
    end.define_signature = True
    end.input_items.new('VECTOR', 'Vector')
    end.output_items.new('VECTOR', 'Color')
    sample = tree.nodes.new('ShaderNodeTexImage')
    sample.image = image
    sample.interpolation = 'Linear'
    tree.links.new(start.outputs['Vector'], sample.inputs['Vector'])
    tree.links.new(sample.outputs['Color'], end.inputs['Color'])
    start.label = 'Water array coordinates'
    sample.label = 'Padded precomputed water slopes'
    end.label = 'Water slope sampler'
    for n, x in [(start, 0), (sample, 220), (end, 490)]:
        n.location = (x, -600)
    return end.outputs['Closure']


def setup_water_sampling(shader, tree, root):
    coordinates = shader._add_group_node(tree, tree.nodes, 'foundry_reach.shader_water - texture coordinates')
    coordinates.label = 'Water: separate wave and painted UVs'
    coordinates.location = (-1100, 0)
    for name in ('wave_displacement_array', 'wave_slope_array', 'bump_map',
                 'bump_detail_map', 'foam_texture', 'foam_texture_detail',
                 'watercolor_texture', 'global_shape_texture'):
        texture = _texture(root, name)
        if texture:
            output = 'Paint UV' if name in {'watercolor_texture', 'global_shape_texture'} else 'Wave UV'
            _set_coordinates(tree, texture, coordinates.outputs[output])

    texture = _texture(root, 'wave_slope_array')
    if texture is None or texture.image is None:
        return
    atlas = padded_slope_atlas(texture.image)
    if atlas is None:
        return
    sampler = shader._add_group_node(tree, tree.nodes, '.Reach water animated slopes')
    sampler.location = (-450, -750)
    sampler.label = 'Reach main, auxiliary and detail waves'
    root['reach_water_owner'] = uuid4().hex
    sampler['reach_water_sampler_owner'] = root['reach_water_owner']
    _put(tree, sampler.inputs['Texture'], _slope_closure(tree, atlas))
    for key in SAMPLER_CONTROLS:
        _put(tree, sampler.inputs[key], _value(root.inputs[key]))
    for key, value in zip(('Width', 'Height', 'Layers'), atlas['foundry_bitmap_shape']):
        sampler.inputs[key].default_value = value
    _put(tree, sampler.inputs['UV'], coordinates.outputs['Wave UV'])
    for parameter, prefix in [('wave_displacement_array', 'Main'), ('wave_slope_array', 'Aux')]:
        original = _texture(root, parameter)
        mapping = _mapping(original)
        if mapping:
            for suffix in TRANSFORM_CONTROLS:
                _put(tree, sampler.inputs[prefix + ' ' + suffix], _value(mapping.inputs[suffix]))
        if original:
            _remember(root, original, parameter)
    # Keep the authored image and transform upstream for bitmap/tag export.
    result = _vector(tree, 'ADD', sampler.outputs['Encoded slope'],
                     _vector(tree, 'SCALE', texture.outputs['Color'], 0),
                     'Composed slope with original bitmap ownership')
    tree.links.new(result, root.inputs['wave_slope_array.rgb'])
    tree.links.new(sampler.outputs['Choppiness'], root.inputs['wave_slope_array.a'])

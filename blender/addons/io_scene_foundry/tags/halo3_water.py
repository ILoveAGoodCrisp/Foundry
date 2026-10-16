"""Halo 3 water coordinates and precomputed, temporally interpolated slopes.

water_shading.fx samples main, auxiliary and detail waves from the SAME slope
array, with independent transforms/phases and sqrt(height) amplitude. Painted
bank/color/foam masks instead use base_tex, without a texture transform.
"""
from uuid import uuid4

import bpy

from .halo3_odst_io import _mapping, _put, _set_coordinates, _value
from .halo3_sampling import _ensure_texture, _ensure_value
from .reach_water import padded_slope_atlas, _slope_closure, TRANSFORM_CONTROLS
from .water_coordinates import texture, add_uv_nodes

SAMPLER_CONTROLS = (
    'time_warp', 'time_warp_aux', 'wave_height', 'wave_height_aux',
    'slope_range_x', 'slope_range_y', 'detail_slope_scale_x',
    'detail_slope_scale_y', 'detail_slope_scale_z', 'detail_slope_steepness',
)
WAVE_TEXTURES = ('wave_displacement_array', 'wave_slope_array', 'bump_map',
                 'bump_detail_map', 'foam_texture', 'foam_texture_detail')
PAINT_TEXTURES = ('watercolor_texture', 'global_shape_texture')


def sync_water_sampling(tree):
    if not tree.is_editable:
        return 0
    owners = {n.get('h3_water_owner'): n for n in tree.nodes if n.get('h3_water_owner')}
    changes = 0

    def copy(source, destination, default=0.0):
        nonlocal changes
        value = _value(source) if source is not None else default
        if isinstance(value, bpy.types.NodeSocket):
            if not destination.is_linked or destination.links[0].from_socket != value:
                tree.links.new(value, destination)
                changes += 1
        elif destination.is_linked or destination.default_value != value:
            for link in list(destination.links):
                tree.links.remove(link)
            destination.default_value = value
            changes += 1

    for sampler in tree.nodes:
        root = owners.get(sampler.get('h3_water_sampler_owner'))
        if root is None:
            continue
        for key in SAMPLER_CONTROLS:
            copy(root.inputs.get(key), sampler.inputs[key])
        for parameter, prefix in (('wave_displacement_array', 'Main'), ('wave_slope_array', 'Aux')):
            mapping = _mapping(texture(root, parameter))
            for key in TRANSFORM_CONTROLS:
                copy(mapping.inputs[key] if mapping else None, sampler.inputs[prefix + ' ' + key],
                     0.0 if key.startswith('Translate') else 1.0)
    return changes


def setup_water_sampling(shader, tree, root, *, wave_uv=None, paint_uv=None):
    """Keep wave and painted coordinates separate, with authored tiling only."""
    if root.get('h3_water_owner'):
        return
    for key in SAMPLER_CONTROLS:
        _ensure_value(shader, root, key)
    # Displacement supplies the main transform even without mesh displacement.
    for key in ('wave_displacement_array', 'wave_slope_array'):
        _ensure_texture(shader, tree, root, key)

    wave, paint = add_uv_nodes(tree, wave_uv=wave_uv, paint_uv=paint_uv)
    for key in WAVE_TEXTURES:
        sample = texture(root, key)
        if sample:
            _set_coordinates(tree, sample, wave)
    for key in PAINT_TEXTURES:
        sample = texture(root, key)
        if sample:
            _set_coordinates(tree, sample, paint, transformed=False)

    sample = texture(root, 'wave_slope_array')
    if sample is None or sample.image is None:
        return
    atlas = padded_slope_atlas(sample.image, label='Halo 3 water')
    if atlas is None:
        return
    # Old locally appended libraries can still use the coordinate repair.
    if root.inputs.get('Preview wave slope') is None:
        from .. import utils
        utils.print_warning('Reload h3_nodes.blend to enable interpolated Halo 3 water waves.')
        return
    sampler = shader._add_group_node(tree, tree.nodes, '.H3 water animated slopes')
    sampler.label = 'Halo 3 main, auxiliary and detail waves'
    sampler.location = (-500, -750)
    root['h3_water_owner'] = uuid4().hex
    sampler['h3_water_sampler_owner'] = root['h3_water_owner']
    _put(tree, sampler.inputs['Texture'], _slope_closure(tree, atlas))
    _put(tree, sampler.inputs['UV'], wave)
    for key, value in zip(('Width', 'Height', 'Layers'), atlas['foundry_bitmap_shape']):
        sampler.inputs[key].default_value = value
    tree.links.new(sampler.outputs['Slope'], root.inputs['Preview wave slope'])
    root.inputs['Preview animated waves'].default_value = True
    sync_water_sampling(tree)

"""Translate imported material graphs without changing the source tag context.

The source reader owns bitmap extraction, UVs and animation. This module only
replaces surface groups, reusing their upstream sockets. See
docs/material_game_mapping.md for the mappings and approximation boundaries.
"""

from collections import defaultdict

from .. import utils
from .material_bitmap_mapping import DataTextureBaker


GAME_LIBRARIES = {
    'halo1': ('h1_nodes', 'foundry_h1.'),
    'halo3': ('h3_nodes', 'foundry_h3.'),
    'halo3odst': ('h3_nodes', 'foundry_h3.'),
    'reach': ('reach_nodes', 'foundry_reach.'),
    'halo4': ('h4_nodes', ''),
    'halo2a': ('h4_nodes', ''),
}
MODERN_GAMES = {'halo3', 'halo3odst', 'reach'}

# Equivalent parameter names, not just similarly named texture sockets. Alpha
# is deliberately separate: packing conventions differ between generations.
PARAMETER_ALIASES = (
    ('base_map.rgb', 'color_map', 'Base Map'),
    ('base_map.a', 'color_map_alpha', 'Base Map Alpha'),
    ('detail_map.rgb', 'color_detail_map', 'Detail Map', 'Primary Detail Map'),
    ('detail_map.a', 'color_detail_map_alpha', 'Detail Map Alpha', 'Primary Detail Map Alpha'),
    ('detail_map2.rgb', 'Secondary Detail Map'),
    ('detail_map3.rgb', 'Micro Detail Map'),
    ('bump_map', 'normal_map', 'Bump Map'),
    ('bump_detail_map', 'detail_normal_map', 'normal_detail_map'),
    ('albedo_color', 'albedo_tint'),
    ('albedo_color_alpha', 'diffuse_alpha'),
    ('diffuse_contribution', 'diffuse_coefficient', 'diffuse_intensity'),
    ('normal_specular_color', 'normal_specular_tint', 'specular_tint', 'specular_color', 'Perpendicular Color', 'Perpendicular Tint Color'),
    ('glancing_specular_color', 'glancing_specular_tint', 'Parallel Color', 'Parallel Tint Color'),
    ('specular_coefficient', 'specular_intensity', 'Brightness'),
    ('point_specular_contribution', 'analytical_specular_contribution'),
    ('wide_specular_contribution', 'area_specular_contribution'),
    ('point_light_roughness', 'roughness'),
    ('environment_map.rgb', 'reflection_map', 'Reflection Cube Map'),
    ('environment_map.a', 'reflection_map_alpha'),
    ('env_tint_color', 'reflection_color'),
    ('environment_map_specular_contribution', 'reflection_intensity', 'Perpendicular Brightness'),
    ('self_illum_map.rgb', 'selfillum_map', 'Self-Illumination Map'),
    ('self_illum_color', 'si_color'),
    ('self_illum_intensity', 'si_intensity'),
    ('blend_mode', 'blend mode'),
    ('material is two-sided', 'Two-Sided'),
    ('Primary Color', 'Primary Change Color'),
)


def _name(node):
    name = node.node_tree.name if node.type == 'GROUP' else node.type
    base, dot, suffix = name.rpartition('.')
    return base if dot and suffix.isdigit() else name


def _family(node):
    name = _name(node)
    if name.startswith('foundry_'):
        return name.partition('.')[2]
    if 'layered_three' in name:
        return 'shader_terrain'
    if 'glass' in name:
        return 'shader_glass'
    if 'foliage' in name:
        return 'shader_foliage'
    if 'constant' in name:
        return 'shader_halogram'
    return 'shader'


def _value(node, name, default=None):
    socket = node.inputs.get(name)
    return socket.default_value if socket is not None else default


def _linked(node, name):
    socket = node.inputs.get(name)
    return socket is not None and socket.is_linked


def _signal(socket):
    if socket.is_linked:
        return socket.links[0].from_socket
    value = socket.default_value
    return tuple(value) if socket.type in {'RGBA', 'VECTOR'} else value


def _put(tree, socket, value):
    if hasattr(value, 'is_output'):
        tree.links.new(value, socket)
    else:
        if socket.type == 'RGBA' and isinstance(value, (float, int)):
            value = (value, value, value, 1.0)
        socket.default_value = value


class Mapping:
    def __init__(self, tree, source, target, notes, baker):
        self.tree, self.source, self.target, self.notes = tree, source, target, notes
        self.baker = baker

    def get(self, name, default=0.0):
        socket = self.source.inputs.get(name)
        return _signal(socket) if socket is not None else default

    def set(self, name, value):
        socket = self.target.inputs.get(name)
        if socket is None:
            return False
        try:
            _put(self.tree, socket, value)
        except (TypeError, ValueError) as exc:
            if socket.type != 'MENU':
                raise
            self.notes.add(f'{name}={value!r} is unavailable; using {socket.default_value!r}')
            return False
        return True

    def bitmap(self, name, value, alpha=None):
        """Materialize packed masks so export sees the correct image channels."""
        if name not in self.target.inputs:
            return None
        try:
            node = self.baker.bake(value, name.replace('.', '_'), alpha)
        except (ValueError, OSError, RuntimeError) as exc:
            self.notes.add(f'{name}: automatic bitmap conversion unavailable ({exc}); retaining node calculation')
            node = None
        if node is None:
            self.set(name, value)
        else:
            self.set(name, node.outputs['Alpha' if name.endswith('.a') else 'Color'])
        return node

    def copy(self, source, target=None):
        socket = self.source.inputs.get(source)
        if socket is not None:
            return self.set(target or source, _signal(socket))
        return False

    def mix(self, a, b, factor=1.0, mode='MULTIPLY', label=''):
        node = self.tree.nodes.new('ShaderNodeMixRGB')
        node.blend_type = mode
        node.label = label
        for socket, value in zip(node.inputs, (factor, a, b)):
            _put(self.tree, socket, value)
        return node.outputs[0]

    def math(self, operation, a, b):
        node = self.tree.nodes.new('ShaderNodeMath')
        node.operation = operation
        _put(self.tree, node.inputs[0], a)
        _put(self.tree, node.inputs[1], b)
        return node.outputs[0]

    def split(self, color):
        node = self.tree.nodes.new('ShaderNodeSeparateColor')
        node.mode = 'RGB'
        _put(self.tree, node.inputs[0], color)
        return tuple(node.outputs[:3])

    def combine(self, red, green, blue):
        node = self.tree.nodes.new('ShaderNodeCombineColor')
        node.mode = 'RGB'
        for socket, value in zip(node.inputs, (red, green, blue)):
            _put(self.tree, socket, value)
        return node.outputs[0]

    def mask(self, value):
        if hasattr(value, 'is_output'):
            return self.split(value)[0] if value.type == 'RGBA' else value
        return value[0] if isinstance(value, (tuple, list)) else value

    def matching_inputs(self):
        # Several resource groups have duplicate names for different material
        # models. Preserve their occurrence order instead of repeatedly copying
        # the first socket returned by inputs.get().
        source_inputs = defaultdict(list)
        for socket in self.source.inputs:
            source_inputs[(socket.name, socket.type)].append(socket)
        counts = defaultdict(int)
        copied = set()
        for socket in self.target.inputs:
            key = (socket.name, socket.type)
            index = counts[key]
            counts[key] += 1
            candidates = source_inputs.get(key, ())
            if not candidates:
                aliases = next((a for a in PARAMETER_ALIASES if socket.name in a), ())
                candidates = next((source_inputs[(name, socket.type)] for name in aliases
                                   if (name, socket.type) in source_inputs), ())
            if not candidates:
                continue
            source = candidates[min(index, len(candidates) - 1)]
            try:
                _put(self.tree, socket, _signal(source))
                copied.add(source.identifier)
            except (TypeError, ValueError):
                if socket.type != 'MENU':
                    raise
                self.notes.add(f'{socket.name}={source.default_value!r} is unavailable; using {socket.default_value!r}')
        return copied


def _halo1_to_modern(m):
    """Decode classic packing before assigning independent modern channels."""
    s = m.source
    model = _family(s) == 'shader_model'
    m.set('albedo', 'default')
    m.set('detail_map.rgb', (0.5, 0.5, 0.5, 1.0))
    m.set('bump_mapping', 'standard' if _linked(s, 'Bump Map') else 'off')
    m.set('alpha_test', 'simple' if (not _value(s, 'Not Alpha-Tested', True) if model
                                   else _value(s, 'Alpha Tested', False)) else 'none')
    m.copy('Base Map Alpha', 'alpha_test_map.a')
    m.set('blend_mode', 'alpha_blend' if _value(s, 'Alpha-Blended Decal', False) else 'opaque')
    m.set('material_model', 'two_lobe_phong')
    m.set('point_specular_contribution', 0.5)
    m.set('analytical_specular_contribution', 0.5)
    m.set('environment_mapping', 'per_pixel' if _linked(s, 'Reflection Cube Map') else 'none')
    m.copy('Perpendicular Tint Color' if model else 'Perpendicular Color', 'env_tint_color')
    base = m.get('Base Map', (1, 1, 1, 1))

    if model:
        red, green, blue = m.split(m.get('Multipurpose Map', (1, 0, 1, 1)))
        alpha = m.get('Multipurpose Map Alpha', 1.0)
        xbox = _value(s, 'Multipurpose Map Uses OG Xbox Channel Order', False)
        auxiliary, reflection, change = (alpha, red, blue) if xbox else (red, blue, alpha)
        m.set('specular_mask', 'specular_mask_from_texture')
        m.bitmap('specular_mask_texture.a', reflection)
        if _linked(s, 'Primary Change Color'):
            m.set('albedo', 'two_change_color')
            m.bitmap('change_color_map.rgb', m.combine(change, 0.0, 0.0))
            m.copy('Primary Change Color', 'Primary Color')
        emission = m.mix(m.get('Animation Color Lower Bound'),
                         m.get('Animation Color Upper Bound'),
                         m.get('Animation Color Bound Factor'), 'MIX')
        m.set('self_illumination', 'simple')
        m.bitmap('self_illum_map.rgb', green)
        m.set('self_illum_color', emission)
        masks = {'none': 1.0, 'reflection mask': reflection,
                 'self-illumination mask': green, 'change-color mask': change,
                 'multipurpose map alpha': auxiliary}
        mask_name = _value(s, 'Detail Mask', 'none')
        mask = masks.get(mask_name.removesuffix(' inverse'), 1.0)
        if mask_name.endswith(' inverse'):
            mask = m.math('SUBTRACT', 1.0, mask)
        details = [('Detail Map', 'Detail Function', mask)]
        if _value(s, 'Detail After Reflections', False):
            m.notes.add('Halo 1 detail-after-reflection ordering is approximated in albedo')
    else:
        details = [('Primary Detail Map', 'Detail Map Function', 1.0)]
        if _linked(s, 'Secondary Detail Map'):
            # Primary/secondary detail are interpolated by base alpha in the
            # common classic environment mode, retaining each texture's UVs.
            primary = m.get('Primary Detail Map', (0.5, 0.5, 0.5, 1))
            secondary = m.get('Secondary Detail Map')
            detail = m.mix(primary, secondary, m.get('Base Map Alpha', 1), 'MIX')
            details = [(detail, 'Detail Map Function', 1.0)]
            m.notes.add('Halo 1 environment detail blend is approximated using base alpha')
        details.append(('Micro Detail Map', 'Micro Detail Map Function', 1.0))
        channels = m.split(m.get('Self-Illumination Map', (1, 1, 1, 1)))
        emission = (0, 0, 0, 1)
        for layer, channel in zip(('Primary', 'Secondary', 'Plasma'), channels):
            tint = m.mix(m.get(f'{layer} Off Color'), m.get(f'{layer} On Color'),
                         m.get(f'{layer} Self-Illumination Activation Level'), 'MIX')
            emission = m.mix(emission, m.mix(tint, channel), mode='ADD')
        m.set('self_illumination', 'simple')
        m.set('self_illum_map.rgb', emission)
        m.set('self_illum_color', (1, 1, 1, 1))
        m.set('specular_mask', 'specular_mask_from_diffuse')
        m.copy('Brightness', 'specular_coefficient')

    for detail, function, mask in details:
        if isinstance(detail, str):
            if not _linked(s, detail):
                continue
            detail = m.get(detail)
        mode = _value(s, function, 'double/biased multiply')
        if mode == 'double/biased add':
            blended = m.mix(m.mix(base, detail, mode='ADD'), (0.5, 0.5, 0.5, 1), mode='SUBTRACT')
        else:
            blended = m.mix(base, detail)
            if mode == 'double/biased multiply':
                blended = m.mix(blended, (2, 2, 2, 1))
        base = m.mix(base, blended, mask, 'MIX', 'Halo 1 detail blend')
    m.set('base_map.rgb', base)
    m.notes.add('Classic lighting, reflection brightness and animation are approximate; composed textures need baking for tag export')


def _modern_to_modern(m):
    # Shared families mostly transfer verbatim. The lighting models changed in
    # Reach, so their closest named controls are handled by PARAMETER_ALIASES.
    if _family(m.source) != _family(m.target):
        m.set('albedo', 'default')
        if _family(m.source) == 'shader_glass':
            m.set('blend_mode', 'alpha_blend')
            m.set('material_model', 'two_lobe_phong')
        elif _family(m.source) == 'shader_foliage':
            m.set('material_model', 'foliage')
            m.set('alpha_test', 'simple')
        m.notes.add(f'{_family(m.source)} uses the closest {_family(m.target)} family')
    if _name(m.source).startswith('foundry_reach.') and _name(m.target).startswith('foundry_h3.'):
        if _value(m.source, 'specular_mask') == 'specular_mask_mult_diffuse':
            m.set('specular_mask', 'specular_mask_from_texture')
            m.bitmap('specular_mask_texture.a', m.math('MULTIPLY', m.get('base_map.a', 1),
                                                     m.get('specular_mask_mult_texture.a', 1)))
        if _value(m.source, 'alpha_blend_source', 'from_albedo_alpha_without_fresnel') != 'from_albedo_alpha_without_fresnel':
            m.notes.add('Reach opacity/fresnel source has no direct H3 equivalent')
    m.notes.add('H3/Reach lighting-model controls use nearest equivalents')


def _h4_to_modern(m):
    s = m.source
    m.set('albedo', 'default')
    m.set('detail_map.rgb', m.get('color_detail_map', (0.5, 0.5, 0.5, 1)))
    m.set('material_model', 'two_lobe_phong')
    m.set('bump_mapping', 'detail' if _linked(s, 'detail_normal_map') else
          'standard' if _linked(s, 'normal_map') else 'off')
    m.set('environment_mapping', 'per_pixel' if _linked(s, 'reflection_map') else 'none')
    m.set('self_illumination', 'simple' if 'si_color' in s.inputs else 'off')
    if 'clip' in _name(s):
        m.set('alpha_test', 'simple')
        m.copy('color_map_alpha', 'alpha_test_map.a')
    controls = next((name for name in ('control_map_spglrfsi', 'control_map_spglsi',
                                       'control_map_spglrf', 'control_map_spgltr') if name in s.inputs), None)
    if controls:
        specular, gloss, extra = m.split(m.get(controls))
        m.set('specular_mask', 'specular_mask_from_texture')
        m.bitmap('specular_mask_texture.a', specular)
        # Gloss is not roughness. Invert it rather than treating green as a
        # tangent-space normal or passing it straight to a roughness input.
        m.set('point_light_roughness', m.math('SUBTRACT', 1, gloss))
        if controls == 'control_map_spglsi':
            m.bitmap('self_illum_map.rgb', extra)
        elif controls == 'control_map_spglrfsi':
            m.set('environment_map_specular_contribution', extra)
            m.bitmap('self_illum_map.rgb', m.get(controls + '_alpha', 0))
        elif controls == 'control_map_spglrf':
            m.set('environment_map_specular_contribution', extra)
    elif 'specular_map' in s.inputs:
        m.set('specular_mask', 'specular_mask_from_texture')
        m.set('specular_mask_texture.a', m.get('specular_map'))
    if _family(s) == 'shader_terrain':
        m.copy('blend_map', 'blend_map.rgb')
        m.copy('blend_map_alpha', 'blend_map.a')
        for index, channel in enumerate('rgb'):
            m.copy(f'{channel}_color', f'base_map_m_{index}.rgb')
            m.copy(f'{channel}_normal', f'bump_map_m_{index}')
    m.notes.add('H4 control maps are unpacked; gloss, lighting and specialized effects are approximate')


def _modern_to_h4(m):
    s = m.source
    m.set('cull shadows', _value(s, 'cull shadows', False))
    m.set('specular_intensity', 0.0 if _value(s, 'material_model') == 'diffuse_only'
          else m.get('specular_coefficient', 1.0))
    m.set('reflection_intensity', 0.0 if _value(s, 'environment_mapping', 'none') == 'none'
          else m.get('environment_map_specular_contribution', 1.0))
    spec_mode = _value(s, 'specular_mask', 'no_specular_mask')
    specular = m.get('specular_mask_texture.a', 1.0)
    if spec_mode == 'no_specular_mask':
        specular = 1.0
    elif spec_mode == 'specular_mask_from_diffuse':
        specular = m.get('base_map.a', 1.0)
    elif spec_mode == 'specular_mask_mult_diffuse':
        specular = m.math('MULTIPLY', m.get('base_map.a', 1), m.get('specular_mask_mult_texture.a', 1))
    roughness = m.get('point_light_roughness', m.get('roughness', 0.5))
    gloss = m.math('SUBTRACT', 1.0, roughness)
    m.set('specular_map', specular)
    illum_mode = _value(s, 'self_illumination', 'off')
    emission = m.get('self_illum_map.rgb', (1, 1, 1, 1))
    if illum_mode == 'off':
        m.set('si_intensity', 0.0)
    elif illum_mode in {'from_diffuse', 'self_illum_times_diffuse'}:
        emission = m.get('base_map.rgb') if illum_mode == 'from_diffuse' else m.mix(emission, m.get('base_map.rgb'))
    # The character reflection/self-illumination family packs specular, gloss,
    # reflection and self illumination into RGBA. Emission color can be an RGB
    # graph here, avoiding lossy conversion of colored emission into one mask.
    # Keep monochrome self illumination in the packed alpha when possible.
    # RGB self illumination remains a color expression and is reported below.
    emission_mask = m.mask(emission)
    packed = m.bitmap('control_map_spglrfsi', m.combine(specular, gloss, 1.0),
                      emission_mask if illum_mode != 'off' else 0.0)
    m.set('control_map_spglrfsi_alpha', packed.outputs['Alpha'] if packed else 1.0)
    if illum_mode != 'off':
        m.set('si_color', m.get('self_illum_color', (1, 1, 1, 1)) if packed else
              m.mix(emission, m.get('self_illum_color', (1, 1, 1, 1))))
    if _linked(s, 'detail_map.rgb') and 'color_detail_map' not in m.target.inputs:
        m.set('color_map', m.mix(m.mix(m.get('base_map.rgb'), m.get('detail_map.rgb')), (2, 2, 2, 1)))
    if _family(s) == 'shader_terrain':
        m.copy('blend_map.rgb', 'blend_map')
        m.copy('blend_map.a', 'blend_map_alpha')
        for index, channel in enumerate('rgb'):
            m.copy(f'base_map_m_{index}.rgb', f'{channel}_color')
            m.copy(f'bump_map_m_{index}', f'{channel}_normal')
            m.copy(f'specular_tint_m_{index}', f'{channel}_spec')
        if _value(s, 'material_3', 'off') != 'off':
            m.notes.add('H4 three-layer terrain omits the fourth terrain layer')
    if _value(s, 'alpha_test', 'none') != 'none':
        m.notes.add('Alpha testing is approximated with alpha blending in the selected H4 family')
        m.set('blend mode', 'alpha_blend')
        m.copy('alpha_test_map.a', 'color_map_alpha')
    m.notes.add('H4 lighting uses Blinn equivalents; composed color/control maps need baking for tag export')


def _modern_to_halo1(m):
    s = m.source
    m.set('Alpha Tested', _value(s, 'alpha_test', 'none') != 'none')
    m.set('Not Alpha-Tested', _value(s, 'alpha_test', 'none') == 'none')
    m.set('Alpha-Blended Decal', _value(s, 'blend_mode', 'opaque') != 'opaque')
    m.set('Bump Strength', 1.0 if _linked(s, 'bump_map') else 0.0)
    illum_mode = _value(s, 'self_illumination', 'off')
    emission = m.get('self_illum_map.rgb', (1, 1, 1, 1))
    tint = m.get('self_illum_color', (1, 1, 1, 1))
    intensity = m.get('self_illum_intensity', 1.0) if illum_mode != 'off' else 0.0
    m.set('Primary On Color', m.mix(tint, intensity))
    m.set('Primary Self-Illumination Activation Level', 1.0)
    m.bitmap('Self-Illumination Map', m.combine(m.mask(emission), 0, 0))
    m.set('Brightness', 0.0 if _value(s, 'material_model') == 'diffuse_only' else m.get('specular_coefficient', 1))
    reflection = m.get('specular_mask_texture.a', 1)
    if _value(s, 'specular_mask') == 'specular_mask_from_diffuse':
        reflection = m.get('base_map.a', 1)
    packed = m.bitmap('Multipurpose Map', m.combine(1, m.mask(emission) if illum_mode != 'off' else 0, reflection), 0.0)
    m.set('Multipurpose Map Alpha', packed.outputs['Alpha'] if packed else 0.0)
    m.set('Animation Color Upper Bound', m.mix(tint, intensity))
    m.set('Animation Color Bound Factor', 1.0)
    m.notes.add('Halo 1 has fewer lighting and layer options; modern material effects are approximated')


def _principled_to_modern(m):
    # Classic transparent families and H2 already have source-reader previews.
    # Preserve their composited albedo rather than guessing template parameters.
    m.copy('Base Color', 'base_map.rgb')
    m.copy('Alpha', 'base_map.a')
    m.copy('Alpha', 'alpha_test_map.a')
    m.set('detail_map.rgb', (0.5, 0.5, 0.5, 1))
    m.set('material_model', 'two_lobe_phong')
    m.copy('Roughness', 'point_light_roughness')
    m.copy('Metallic', '0_plastic_1_metal')
    m.copy('Emission Color', 'self_illum_map.rgb')
    m.copy('Emission Strength', 'self_illum_intensity')
    m.set('self_illumination', 'simple')
    m.set('self_illum_color', (1, 1, 1, 1))
    if _linked(m.source, 'Alpha') or _value(m.source, 'Alpha', 1) < 1:
        m.set('blend_mode', 'alpha_blend')
    normal = m.source.inputs.get('Normal')
    if normal is not None and normal.is_linked:
        node = normal.links[0].from_node
        if node.type == 'NORMAL_MAP':
            m.set('bump_map', _signal(node.inputs['Color']))
            m.set('bump_mapping', 'standard')
        else:
            m.notes.add('Procedural bump/normal chain has no direct normal-map equivalent')
    m.notes.add('Source Principled preview converted approximately; template-specific effects are unavailable')


def _new_group(tree, library, name):
    group_tree = utils.add_node_from_resources(library, name)
    if group_tree is None:
        raise ValueError(f'Missing material node resource {library}/{name}')
    group = tree.nodes.new('ShaderNodeGroup')
    group.node_tree = group_tree
    return group


def _target_group(tree, source, target_game):
    library, prefix = GAME_LIBRARIES[target_game]
    family = _family(source)
    if target_game == 'halo1':
        return _new_group(tree, library, prefix + ('shader_environment' if _linked(source, 'bump_map')
                                                  or family == 'shader_terrain' else 'shader_model'))
    if target_game in {'halo4', 'halo2a'}:
        name = {'shader_terrain': 'srf_layered_three', 'shader_glass': 'srf_glass',
                'shader_foliage': 'srf_foliage', 'shader_halogram': 'srf_constant'}.get(family)
        if name is None:
            if _value(source, 'self_illumination', 'off') != 'off' or _value(source, 'environment_mapping', 'none') != 'none':
                name = 'srf_char_blinn_reflection_selfillum'
            elif _linked(source, 'detail_map.rgb'):
                name = 'srf_blinn_detail'
            else:
                name = 'srf_blinn'
        return _new_group(tree, library, name)
    available = {'shader', 'shader_custom', 'shader_decal', 'shader_halogram', 'shader_terrain'}
    if target_game == 'reach':
        available.update({'shader_glass', 'shader_foliage'})
    return _new_group(tree, library, prefix + (family if family in available else 'shader'))


def _surface_nodes(tree):
    """Find supported surfaces through wrappers (e.g. shield/add shaders)."""
    pending = [link.from_node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL'
               for socket in node.inputs if socket.name == 'Surface' for link in socket.links]
    seen = set()
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        name = _name(node)
        if node.type == 'BSDF_PRINCIPLED' or (node.type == 'GROUP' and
                (name.startswith(('foundry_h1.', 'foundry_h3.', 'foundry_reach.', 'srf_')))):
            yield node
            continue
        pending.extend(link.from_node for socket in node.inputs for link in socket.links)


def convert_material_game(material, source_game, target_game):
    """Return whether a material was converted; failures retain the source graph.

    H2 is supported as a source via its existing Principled preview, but is not
    a target because Foundry has no H2 custom surface groups.
    """
    if source_game == target_game or (source_game in GAME_LIBRARIES and target_game in GAME_LIBRARIES
                                    and GAME_LIBRARIES[source_game] == GAME_LIBRARIES[target_game]):
        return False
    if target_game not in GAME_LIBRARIES:
        utils.print_warning(f'{material.name}: current-project materials are unavailable for {target_game}; keeping source nodes')
        return False
    tree = material.node_tree
    if tree is None:
        return False
    sources = list(_surface_nodes(tree))
    if not sources:
        utils.print_warning(f'{material.name}: no supported source surface; keeping source nodes')
        return False
    original_nodes = set(tree.nodes)
    replacements = []
    notes = set()
    project = utils.get_project(use_external=False)
    baker = DataTextureBaker(tree, project.data_directory if project else None)
    try:
        for source in sources:
            current = source
            # A Reach surface is the common semantic bridge for classic/H4
            # graphs. Intermediate groups are removed after final wiring.
            intermediates = []
            if source_game not in MODERN_GAMES or source.type == 'BSDF_PRINCIPLED':
                current = _target_group(tree, source, 'reach')
                m = Mapping(tree, source, current, notes, baker)
                m.matching_inputs()
                if source.type == 'BSDF_PRINCIPLED':
                    _principled_to_modern(m)
                elif _name(source).startswith('foundry_h1.'):
                    _halo1_to_modern(m)
                else:
                    _h4_to_modern(m)
                intermediates.append(current)
            if target_game == 'reach' and current is not source:
                target = current
                intermediates.remove(current)
            else:
                target = _target_group(tree, current, target_game)
                m = Mapping(tree, current, target, notes, baker)
                m.matching_inputs()
                if target_game in MODERN_GAMES:
                    _modern_to_modern(m)
                elif target_game == 'halo1':
                    _modern_to_halo1(m)
                else:
                    _modern_to_h4(m)
            target.location = source.location
            target.label = f'{target_game}: {_family(target)}'
            replacements.append((source, target, intermediates))
    except Exception as exc:
        for node in list(tree.nodes):
            if node not in original_nodes:
                tree.nodes.remove(node)
        utils.print_warning(f'{material.name}: material conversion failed ({exc}); keeping source nodes')
        return False

    for source, target, intermediates in replacements:
        shader_output = next(socket for socket in target.outputs if socket.type == 'SHADER')
        for socket in source.outputs:
            for link in list(socket.links):
                if socket.type == 'SHADER':
                    tree.links.new(shader_output, link.to_socket)
        tree.nodes.remove(source)
        for node in intermediates:
            tree.nodes.remove(node)
    material['foundry_material_source_game'] = source_game
    material['foundry_material_target_game'] = target_game
    material['foundry_material_conversion_notes'] = '\n'.join(sorted(notes))
    for note in sorted(notes):
        utils.print_warning(f'{material.name}: {note}')
    return True

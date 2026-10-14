"""Translate imported material graphs without changing the source tag context.

The source reader owns bitmap extraction, UVs and animation. This module only
replaces surface groups, reusing their upstream sockets. See
blender/material_game_mapping.md for the mappings and approximation boundaries.
"""

from collections import defaultdict
import re

from .. import utils
from .material_bitmap_mapping import DataTextureBaker


GAME_LIBRARIES = {
    'halo1': ('h1_nodes', 'foundry_h1.'),
    'halo3': ('h3_nodes', 'foundry_h3.'),
    'halo3odst': ('h3_nodes', 'foundry_h3odst.'),
    'reach': ('reach_nodes', 'foundry_reach.'),
    'halo4': ('h4_nodes', ''),
    'halo2a': ('h2amp_nodes', ''),
}
MODERN_GAMES = {'halo3', 'halo3odst', 'reach'}

# Equivalent parameter names, not just similarly named texture sockets. Alpha
# is deliberately separate: packing conventions differ between generations.
PARAMETER_ALIASES = (
    ('base_map.rgb', 'color_map', 'Base Map', 'base_color'),
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
    ('Secondary Color', 'Secondary Change Color'),
    ('0_plastic_1_metal', 'metallicness'),
)


def _name(node):
    if node.type == 'GROUP' and node.node_tree:
        source = node.node_tree.get('foundry_material_shader')
        if source:
            return source.rsplit('/', 1)[-1]
    name = node.node_tree.name if node.type == 'GROUP' and node.node_tree else node.type
    base, dot, suffix = name.rpartition('.')
    return base if dot and suffix.isdigit() else name


def _family(node):
    name = _name(node)
    if name.startswith('foundry_'):
        return name.partition('.')[2]
    if 'layered_three' in name or 'pbr_ca_terrain' in name:
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
        # Changing the default does not override an existing Blender link.
        for link in list(socket.links):
            tree.links.remove(link)
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

    def bitmap(self, name, value, alpha=None, *, color=False, reference=None, usage='Material Map'):
        """Materialize packed masks so export sees the correct image channels."""
        if name not in self.target.inputs:
            return None
        node = self.baker.bake(value, name.replace('.', '_'), alpha, color=color,
                               resample=True, reference=reference, usage=usage)
        self.set(name, node.outputs['Alpha' if name.endswith('.a') else 'Color'])
        return node

    def copy(self, source, target=None):
        socket = self.source.inputs.get(source)
        if socket is not None:
            return self.set(target or source, _signal(socket))
        return False

    def mix(self, a, b, factor=1.0, mode='MULTIPLY'):
        if not any(hasattr(value, 'is_output') for value in (a, b, factor)):
            def rgb(value):
                return tuple(value[:3]) if isinstance(value, (tuple, list)) else (value,) * 3
            blend = {'MIX': lambda x, y: y, 'MULTIPLY': lambda x, y: x * y,
                     'ADD': lambda x, y: x + y, 'SUBTRACT': lambda x, y: x - y}[mode]
            factor = max(0, min(1, factor))
            return tuple(x * (1 - factor) + blend(x, y) * factor for x, y in zip(rgb(a), rgb(b))) + (1,)
        node = self.tree.nodes.new('ShaderNodeMixRGB')
        node.blend_type = mode
        for socket, value in zip(node.inputs, (factor, a, b)):
            _put(self.tree, socket, value)
        return node.outputs[0]

    def math(self, operation, a, b):
        if not any(hasattr(value, 'is_output') for value in (a, b)):
            return {'MULTIPLY': lambda: a * b, 'SUBTRACT': lambda: a - b, 'ADD': lambda: a + b}[operation]()
        node = self.tree.nodes.new('ShaderNodeMath')
        node.operation = operation
        _put(self.tree, node.inputs[0], a)
        _put(self.tree, node.inputs[1], b)
        return node.outputs[0]

    def split(self, color):
        if not hasattr(color, 'is_output'):
            return color[:3] if isinstance(color, (tuple, list)) else (color,) * 3
        node = self.tree.nodes.new('ShaderNodeSeparateColor')
        node.mode = 'RGB'
        _put(self.tree, node.inputs[0], color)
        return tuple(node.outputs[:3])

    def combine(self, red, green, blue):
        if not any(hasattr(value, 'is_output') for value in (red, green, blue)):
            return (red, green, blue, 1)
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
    m.bitmap('detail_map.rgb', (0.5, 0.5, 0.5, 1.0), usage='Detail Map')
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
        m.bitmap('self_illum_map.rgb', emission, color=True, usage='Self-Illum Map')
        m.set('self_illum_color', (1, 1, 1, 1))
        m.set('specular_mask', 'specular_mask_from_diffuse')
        m.copy('Brightness', 'specular_coefficient')

    active_details = [(detail, function, mask) for detail, function, mask in details
                      if not isinstance(detail, str) or _linked(s, detail)]
    effective_detail = (0.5, 0.5, 0.5, 1)
    bake_base = False
    for detail, function, mask in active_details:
        if isinstance(detail, str):
            detail = m.get(detail)
        mode = _value(s, function, 'double/biased multiply')
        if len(active_details) == 1 and mode == 'double/biased multiply' and not hasattr(mask, 'is_output') and mask == 1:
            # Reach natively multiplies base by twice the detail map. Keep both
            # original texture nodes and their independent tiling in this case.
            m.set('detail_map.rgb', detail)
            break
        if mode == 'double/biased add':
            blended = m.mix(m.mix(base, detail, mode='ADD'), (0.5, 0.5, 0.5, 1), mode='SUBTRACT')
            bake_base = True
        else:
            blended = m.mix(base, detail)
            if mode == 'double/biased multiply':
                blended = m.mix(blended, (2, 2, 2, 1))
            # Fold masked detail into a TIFF, not the base-map input graph.
            # Native default albedo applies the resulting detail exactly once.
            detail_factor = m.mix(detail, (2, 2, 2, 1)) if mode == 'double/biased multiply' else detail
            effective_detail = m.mix(effective_detail, m.mix((1, 1, 1, 1), detail_factor, mask, 'MIX'))
        base = m.mix(base, blended, mask, 'MIX')
    else:
        if active_details:
            if bake_base:
                baked = m.bitmap('base_map.rgb', base, m.get('Base Map Alpha', 1), color=True,
                                  reference=m.get('Base Map'), usage='Diffuse Map')
                m.set('base_map.a', baked.outputs['Alpha'])
            else:
                m.bitmap('detail_map.rgb', effective_detail, color=True,
                         reference=m.get('Base Map'), usage='Detail Map')
    m.notes.add('Classic lighting, reflection brightness and animation use closest native shader equivalents')


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
    if _name(m.source).startswith('foundry_reach.') and _name(m.target).startswith(('foundry_h3.', 'foundry_h3odst.')):
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
        m.bitmap('specular_mask_texture.a', m.mask(m.get('specular_map')))
    if _family(s) == 'shader_terrain':
        m.copy('blend_map', 'blend_map.rgb')
        m.copy('blend_map_alpha', 'blend_map.a')
        for index, channel in enumerate('rgb'):
            if 'pbr_ca_terrain' in _name(s):
                # H2AMP's terrain layers run in the opposite order to Reach.
                layer = 2 - index
                m.copy(f'layer{layer}_coMap', f'base_map_m_{index}.rgb')
                m.copy(f'layer_{layer}_normal_map', f'bump_map_m_{index}')
            else:
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
        if not _name(m.target).endswith('_clip'):
            m.notes.add('Alpha testing is approximated with alpha blending in the selected H4 family')
            m.set('blend mode', 'alpha_blend')
        m.copy('alpha_test_map.a', 'color_map_alpha')
        if _name(m.target) == 'srf_char_blinn_clip':
            m.notes.add('Character clip shader preserves alpha testing; separate reflection and self-illumination controls are unavailable')
    m.notes.add('H4 lighting uses Blinn equivalents; composed color/control maps are baked for export')


def _modern_to_halo1(m):
    s = m.source
    if _family(s) == 'shader_terrain':
        channels = m.split(m.get('blend_map.rgb', (1, 0, 0, 1)))
        color = (0, 0, 0, 1)
        for index, channel in enumerate(channels):
            layer = m.get(f'base_map_m_{index}.rgb', (1, 1, 1, 1))
            if _linked(s, f'detail_map_m_{index}.rgb'):
                layer = m.mix(m.mix(layer, m.get(f'detail_map_m_{index}.rgb')), (2, 2, 2, 1))
            color = m.mix(color, m.mix(layer, channel), mode='ADD')
        m.set('Base Map', color)
        m.copy('bump_map_m_0', 'Bump Map')
        m.set('Bump Strength', 1.0 if _linked(s, 'bump_map_m_0') else 0.0)
        m.notes.add('Terrain uses a baked three-layer color blend and the first normal layer in Halo 1')
    m.set('Alpha Tested', _value(s, 'alpha_test', 'none') != 'none')
    m.set('Not Alpha-Tested', _value(s, 'alpha_test', 'none') == 'none')
    m.set('Alpha-Blended Decal', _value(s, 'blend_mode', 'opaque') != 'opaque')
    if _family(s) != 'shader_terrain':
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
    change = m.mask(m.get('change_color_map.rgb', 0)) if 'change_color' in _value(s, 'albedo', '') else 0.0
    packed = m.bitmap('Multipurpose Map', m.combine(1, m.mask(emission) if illum_mode != 'off' else 0, reflection), change)
    m.set('Multipurpose Map Alpha', packed.outputs['Alpha'] if packed else change)
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
        environment = (_linked(source, 'bump_map') or family == 'shader_terrain') and _value(source, 'blend_mode', 'opaque') == 'opaque'
        return _new_group(tree, library, prefix + ('shader_environment' if environment else 'shader_model'))
    if target_game in {'halo4', 'halo2a'}:
        alpha_test = _value(source, 'alpha_test', 'none') != 'none'
        name = {'shader_terrain': 'srf_layered_three', 'shader_glass': 'srf_glass',
                'shader_foliage': 'srf_foliage_clip' if alpha_test else 'srf_foliage',
                'shader_halogram': 'srf_constant_clip' if alpha_test else 'srf_constant'}.get(family)
        if name is None:
            if _value(source, 'self_illumination', 'off') != 'off' or _value(source, 'environment_mapping', 'none') != 'none':
                name = 'srf_char_blinn_clip' if alpha_test else 'srf_char_blinn_reflection_selfillum'
            elif _linked(source, 'detail_map.rgb'):
                name = 'srf_blinn_clip' if alpha_test else 'srf_blinn_detail'
            else:
                name = 'srf_blinn_clip' if alpha_test else 'srf_blinn'
        return _new_group(tree, library, name)
    available = {'shader', 'shader_custom', 'shader_decal', 'shader_halogram', 'shader_terrain'}
    if target_game == 'reach':
        available.update({'shader_glass', 'shader_foliage'})
    elif target_game in {'halo3', 'halo3odst'}:
        available.update({'shader_foliage', 'shader_cortana', 'shader_water', 'shader_skin'})
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
                (name.startswith(('foundry_h1.', 'foundry_h3.', 'foundry_h3odst.', 'foundry_reach.', 'srf_')))):
            yield node
            continue
        pending.extend(link.from_node for socket in node.inputs for link in socket.links)


def _texture_parameter(name):
    """Recognize resource bitmap inputs and their shared RGB/alpha parameter."""
    lower = name.lower()
    if lower.endswith(('.rgb', '.a')):
        return name.rpartition('.')[0], lower.endswith('.a')
    if lower.endswith('_alpha') and ('map' in lower or 'texture' in lower):
        return name[:-6], True
    if lower.endswith(' map alpha'):
        return name[:-6], True
    if (lower.endswith(('map', 'texture')) or re.search(r'_map_m_\d+$', lower)
            or re.fullmatch(r'control_map_[a-z0-9]+', lower) or lower in
            {'r_color', 'g_color', 'b_color', 'r_normal', 'g_normal', 'b_normal', 'r_spec', 'g_spec', 'b_spec'}):
        return name, False
    return None


def _prepare_shader_export(tree, group, baker, notes):
    """No generated pixel calculations may remain between maps and the group.

    The exporter finds an image upstream; it does not evaluate Blender shader
    math. Likewise scalar/color tag parameters use socket defaults, not links.
    """
    parameters = defaultdict(dict)
    for socket in group.inputs:
        if socket.type not in {'RGBA', 'VALUE'}:
            continue
        parameter = _texture_parameter(socket.name)
        if parameter:
            name, alpha = parameter
            parameters[name]['alpha' if alpha else 'rgb'] = socket
    for name, sockets in parameters.items():
        rgb, alpha = sockets.get('rgb'), sockets.get('alpha')
        if not any(s.is_linked for s in sockets.values()):
            continue
        color_signal = _signal(rgb) if rgb is not None else _signal(alpha)
        alpha_signal = _signal(alpha) if alpha is not None and alpha.is_linked else None
        if (hasattr(color_signal, 'is_output') and color_signal.node.type in {'TEX_IMAGE', 'TEX_ENVIRONMENT'}
                and color_signal.name == ('Color' if rgb is not None else 'Alpha')
                and (alpha_signal is None or (hasattr(alpha_signal, 'is_output')
                     and alpha_signal.node == color_signal.node and alpha_signal.name == 'Alpha'))):
            if rgb is not None and alpha is not None and color_signal.node.outputs.get('Alpha'):
                _put(tree, alpha, color_signal.node.outputs['Alpha'])
            continue
        data_map = any(word in name.lower() for word in
                       ('normal', 'bump', 'mask', 'control', 'multipurpose', 'specular', 'material_texture', 'change_color', 'blend_map'))
        color = rgb is not None and not data_map
        usage = 'Diffuse Map' if color else 'Material Map'
        if 'detail' in name.lower() and color:
            usage = 'Detail Map'
        node = baker.bake(color_signal, name, alpha_signal, color=color, resample=True, usage=usage)
        if rgb is not None:
            _put(tree, rgb, node.outputs['Color'])
        if alpha is not None:
            _put(tree, alpha, node.outputs['Alpha'])

    for socket in group.inputs:
        if not socket.is_linked or socket.type not in {'RGBA', 'VALUE'} or _texture_parameter(socket.name):
            continue
        if socket.name in {'Primary Color', 'Secondary Color', 'Tertiary Color', 'Quaternary Color',
                           'Primary Change Color', 'Secondary Change Color'}:
            continue
        values, _, _, _ = baker.evaluate(_signal(socket), color=True, resample=True)
        value = values.mean(axis=0)
        if len(values) > 1:
            notes.add(f'{socket.name} uses the texture average because the target tag parameter is constant')
        if socket.type == 'RGBA':
            if len(value) == 1:
                value = list(value) * 3
            _put(tree, socket, tuple(float(v) for v in value) + (1.0,))
        else:
            _put(tree, socket, float(value.mean()))
    notes.update(baker.notes)


def _remove_unused_nodes(tree):
    pending = [node for node in tree.nodes if node.type == 'OUTPUT_MATERIAL']
    keep = set()
    while pending:
        node = pending.pop()
        if node in keep:
            continue
        keep.add(node)
        pending.extend(link.from_node for socket in node.inputs for link in socket.links)
        if node.parent is not None:
            pending.append(node.parent)
    for node in list(tree.nodes):
        if node not in keep:
            tree.nodes.remove(node)


def convert_material_game(material, source_game, target_game, *, layout=True):
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
    if any(source.type == 'GROUP' and source.node_tree.get('foundry_source_compiled') for source in sources):
        # These templates contain independent image samples inside the group.
        # The generic socket mapper cannot see them and would silently replace
        # their textures with defaults. Keep the usable source material intact.
        reason = 'Source-built material textures require an explicit target-game mapping'
        material['foundry_material_conversion_error'] = reason
        utils.print_warning(f'{material.name}: {reason}; keeping source nodes')
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
            _prepare_shader_export(tree, target, baker, notes)
            replacements.append((source, target, intermediates))
    except Exception as exc:
        for node in list(tree.nodes):
            if node not in original_nodes:
                tree.nodes.remove(node)
        material['foundry_material_conversion_error'] = str(exc)
        utils.print_warning(f'{material.name}: material conversion failed ({exc}); keeping source nodes. Material is not ready for target-game shader export')
        return False

    material.surface_render_method = 'DITHERED'
    for source, target, intermediates in replacements:
        shader_output = next(socket for socket in target.outputs if socket.type == 'SHADER')
        for socket in source.outputs:
            for link in list(socket.links):
                if socket.type == 'SHADER':
                    tree.links.new(shader_output, link.to_socket)
        tree.nodes.remove(source)
        for node in intermediates:
            tree.nodes.remove(node)
        blend = _value(target, 'blend_mode', _value(target, 'blend mode', 'opaque'))
        if blend != 'opaque' or _value(target, 'Alpha-Blended Decal', False):
            material.surface_render_method = 'BLENDED'
    _remove_unused_nodes(tree)
    if 'foundry_material_conversion_error' in material:
        del material['foundry_material_conversion_error']
    material['foundry_material_source_game'] = source_game
    material['foundry_material_target_game'] = target_game
    utils.update_foundry_material(material, target_game, arrange_nodes=False)
    if layout:
        from .node_layout import layout_nodes
        layout_nodes(tree)
    for note in sorted(notes):
        utils.print_warning(f'{material.name}: {note}')
    return True

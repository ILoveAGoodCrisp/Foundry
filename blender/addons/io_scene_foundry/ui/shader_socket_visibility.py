"""Hide group inputs which cannot affect the selected shader branches.

Socket visibility is per group instance. Interface sockets, values and links
are never removed. Only menu/bool controls are specialized; ordinary numeric
defaults remain unknown so a zero coefficient cannot hide its own controls.
Unknown or externally linked selectors keep both branches available.
"""
from dataclasses import dataclass
import json
import math

import bpy
from bpy.app.handlers import persistent

VERSION = 1
MARKER = 'foundry_socket_visibility_version'
UNKNOWN = object()


@dataclass(frozen=True)
class _Value:
    value: object = UNKNOWN
    used: frozenset = frozenset()


def _combine(values, value=UNKNOWN):
    return _Value(value, frozenset().union(*(v.used for v in values)))


def _default(socket):
    value = getattr(socket, 'default_value', UNKNOWN)
    if socket.type in {'RGBA', 'VECTOR'} and value is not UNKNOWN:
        return tuple(value)
    return value


def _available(socket):
    return socket.enabled and not socket.is_unavailable and socket.bl_idname != 'NodeSocketVirtual'


def _control(socket):
    return socket.type in {'MENU', 'BOOLEAN', 'BOOL'}


def managed(group):
    if group is None or group.bl_idname != 'ShaderNodeTree':
        return False
    # Recognize pre-update material copies too; appended/linked groups carry
    # the marker. H4/shared libraries are not opted in by this change.
    return bool(group.get(MARKER)) or group.name.startswith((
        'foundry_h1.', 'foundry_h3.', 'foundry_h3odst.', 'foundry_reach.',
        'foundry_h3 - ', 'foundry_h3odst - ', 'foundry_reach - ',
        'Basic H2 shader', 'Basic H2 environment_map reflector')) or bool(group.get('h2_template') or group.get('h2_source_revision'))


class _Graph:
    def __init__(self, group, bindings, ancestors=()):
        self.group = group
        self.bindings = bindings
        self.ancestors = (*ancestors, group.as_pointer())
        self.incoming = {link.to_socket.as_pointer(): link.from_socket for link in group.links if link.is_valid}
        self.memo = {}
        self.children = {}
        self.visiting = set()

    def input(self, socket):
        source = self.incoming.get(socket.as_pointer())
        result = self.output(source) if source else _Value(_default(socket))
        if socket.type == 'VECTOR' and result.value is not UNKNOWN:
            if isinstance(result.value,tuple):return _Value(result.value[:3],result.used)
            if isinstance(result.value,(int,float)):return _Value((result.value,)*3,result.used)
        return result

    def result(self, identifier):
        output = next((n for n in self.group.nodes if n.type == 'GROUP_OUTPUT' and n.is_active_output), None)
        if output is None:
            output = next((n for n in self.group.nodes if n.type == 'GROUP_OUTPUT'), None)
        if output is None:
            return _combine(self.bindings.values())
        port = next((s for s in output.inputs if s.identifier == identifier), None)
        return self.input(port) if port else _combine(self.bindings.values())

    def output(self, socket):
        key = socket.as_pointer()
        if key in self.memo:
            return self.memo[key]
        if key in self.visiting:
            return _combine(self.bindings.values())
        self.visiting.add(key)
        try:
            result = self._output(socket)
            self.memo[key] = result
            return result
        finally:
            self.visiting.remove(key)

    def _output(self, socket):
        node = socket.node
        if node.type == 'GROUP_INPUT':
            return self.bindings.get(socket.identifier, _Value())
        if node.type == 'REROUTE':
            return self.input(node.inputs[0])
        if node.bl_idname == 'NodeCombineBundle':
            fields = tuple((s.name, self.input(s)) for s in node.inputs if _available(s))
            return _combine([value for _, value in fields], fields)
        if node.bl_idname == 'NodeSeparateBundle':
            bundle = self.input(node.inputs[0])
            if isinstance(bundle.value, tuple) and all(isinstance(field, tuple) and len(field) == 2 and isinstance(field[1], _Value) for field in bundle.value):
                fields = dict(bundle.value)
                field = fields.get(socket.name)
                if field is not None:
                    selectors = bundle.used - frozenset().union(*(value.used for value in fields.values()))
                    return _combine([field, _Value(UNKNOWN, selectors)], field.value)
            return bundle
        if node.mute:
            for link in node.internal_links:
                if link.to_socket == socket:
                    return self.input(link.from_socket)
        if node.type == 'GROUP' and node.node_tree:
            child = self.children.get(node.as_pointer())
            if child is None:
                bindings = {s.identifier: self.input(s) for s in node.inputs}
                if node.node_tree.as_pointer() in self.ancestors or len(self.ancestors) > 40:
                    return _combine(bindings.values())
                child = self.children[node.as_pointer()] = _Graph(node.node_tree, bindings, self.ancestors)
            return child.result(socket.identifier)
        if node.bl_idname == 'GeometryNodeMenuSwitch':
            selector = self.input(node.inputs[0])
            options = list(node.enum_items)
            selected = next((i for i, option in enumerate(options) if option.name == selector.value), None)
            index = next(i for i, port in enumerate(node.outputs) if port == socket)
            if index:
                # Blender 5.2 additionally exposes a bool for every choice.
                value = selected == index - 1 if selected is not None else UNKNOWN
                return _Value(value, selector.used)
            if selected is not None:
                return _combine([selector, self.input(node.inputs[selected + 1])], self.input(node.inputs[selected + 1]).value)
            return _combine([selector, *(self.input(s) for s in node.inputs[1:] if _available(s))])
        if node.bl_idname == 'GeometryNodeSwitch':
            selector = self.input(node.inputs[0])
            if selector.value is not UNKNOWN:
                branch = self.input(node.inputs[2 if bool(selector.value) else 1])
                return _combine([selector, branch], branch.value)
        if node.type in {'MIX_SHADER', 'MIX_RGB', 'MIX'}:
            return self._mix(node)
        if node.type == 'VECT_MATH':
            return self._vector_math(node)
        values = [self.input(s) for s in node.inputs if _available(s)]
        if node.type in {'VALUE', 'RGB'}:
            return _Value(_default(socket))
        if node.type == 'MATH':
            return self._math(node, values)
        if node.bl_idname == 'FunctionNodeBooleanMath':
            return self._boolean(node.operation, values)
        if node.type in {'SEPXYZ', 'SEPARATE_COLOR'} and values and isinstance(values[0].value, tuple):
            index = next(i for i, port in enumerate(node.outputs) if port == socket)
            return _combine(values, values[0].value[index])
        if node.type in {'COMBXYZ', 'COMBINE_COLOR'} and all(v.value is not UNKNOWN for v in values):
            return _combine(values, tuple(v.value for v in values))
        # Inputs on unfamiliar nodes remain visible rather than risking a
        # false hide. No sampled texture, normal or scene value is inferred.
        return _combine(values)

    def _vector_math(self,node):
        op=node.operation
        if op=='SCALE':
            scale=self.input(node.inputs[3])
            if scale.value==0:return _Value((0,0,0),scale.used)
            values=[self.input(node.inputs[0]),scale]
        else:
            values=[self.input(s) for s in node.inputs if _available(s)]
        if op=='MULTIPLY':
            for value in values:
                if value.value==(0,0,0):return _Value((0,0,0),value.used)
        if any(value.value is UNKNOWN for value in values):return _combine(values)
        args=[value.value for value in values]
        try:
            a=args[0];b=args[1] if len(args)>1 else None
            if op=='ADD':result=tuple(x+y for x,y in zip(a,b))
            elif op=='SUBTRACT':result=tuple(x-y for x,y in zip(a,b))
            elif op=='MULTIPLY':result=tuple(x*y for x,y in zip(a,b))
            elif op=='SCALE':result=tuple(x*b for x in a)
            elif op=='DOT_PRODUCT':result=sum(x*y for x,y in zip(a,b))
            elif op=='LENGTH':result=math.sqrt(sum(x*x for x in a))
            elif op=='NORMALIZE':
                length=math.sqrt(sum(x*x for x in a));result=tuple(x/length if length else 0 for x in a)
            else:return _combine(values)
            return _combine(values,result)
        except (TypeError,ValueError,OverflowError):return _combine(values)

    def _mix(self, node):
        if node.type == 'MIX':
            indices = {'FLOAT': (2, 3), 'VECTOR': (4, 5), 'RGBA': (6, 7)}.get(node.data_type)
            if indices is None or getattr(node, 'factor_mode', 'UNIFORM') != 'UNIFORM':
                return _combine(self.input(s) for s in node.inputs if _available(s))
            factor = self.input(node.inputs[0]); ai, bi = indices
        else:
            factor = self.input(node.inputs[0]); ai, bi = 1, 2
        if factor.value == 0:
            a = self.input(node.inputs[ai])
            return _combine([factor, a], a.value)
        if factor.value == 1 and (node.type == 'MIX_SHADER' or getattr(node, 'blend_type', 'MIX') == 'MIX'):
            b = self.input(node.inputs[bi])
            return _combine([factor, b], b.value)
        a, b = self.input(node.inputs[ai]), self.input(node.inputs[bi])
        if factor.value is not UNKNOWN and a.value is not UNKNOWN and b.value is not UNKNOWN and node.type != 'MIX_SHADER' and getattr(node, 'blend_type', 'MIX') == 'MIX':
            try:
                value = ((1 - factor.value) * a.value + factor.value * b.value)
                return _combine([factor, a, b], value)
            except (TypeError, ValueError):
                pass
        return _combine([factor, a, b])

    def _math(self, node, values):
        op = node.operation
        a = values[0] if values else _Value()
        b = values[1] if len(values) > 1 else _Value()
        if op == 'MULTIPLY':
            for zero in [a, b]:
                if zero.value == 0:
                    return _Value(0, zero.used)
        if op == 'MULTIPLY_ADD' and len(values) > 2:
            for zero in [a, b]:
                if zero.value == 0:
                    return _combine([zero, values[2]], values[2].value)
        if any(v.value is UNKNOWN for v in values):
            return _combine(values)
        args = [v.value for v in values]
        operations = {
            'ADD': lambda a, b: a + b, 'SUBTRACT': lambda a, b: a - b,
            'MULTIPLY': lambda a, b: a * b, 'DIVIDE': lambda a, b: a / b if b else 0,
            'MULTIPLY_ADD': lambda a, b, c: a * b + c,
            'POWER': lambda a, b: a ** b, 'MINIMUM': min, 'MAXIMUM': max,
            'LESS_THAN': lambda a, b: float(a < b), 'GREATER_THAN': lambda a, b: float(a > b),
            'COMPARE': lambda a, b, c: float(abs(a - b) <= max(c, 1e-5)),
            'ABSOLUTE': abs, 'SQRT': lambda a: math.sqrt(max(a, 0)),
            'SINE': math.sin, 'COSINE': math.cos, 'TANGENT': math.tan,
            'FLOOR': math.floor, 'CEIL': math.ceil, 'ROUND': lambda a: math.floor(a + .5),
            'TRUNC': math.trunc, 'FRACT': lambda a: a - math.floor(a),
            'SIGN': lambda a: 1 if a > 0 else -1 if a < 0 else 0,
        }
        try:
            value = operations[op](*args)
            if isinstance(value, complex) or not math.isfinite(value):
                return _combine(values)
            if node.use_clamp:
                value = max(0, min(1, value))
            return _combine(values, value)
        except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            return _combine(values)

    def _boolean(self, operation, values):
        a = values[0]
        b = values[1] if len(values) > 1 else _Value()
        if operation == 'AND':
            for v in [a, b]:
                if v.value is not UNKNOWN and not bool(v.value):return _Value(False, v.used)
        if operation == 'OR':
            for v in [a, b]:
                if v.value is not UNKNOWN and bool(v.value):return _Value(True, v.used)
        if any(v.value is UNKNOWN for v in values):return _combine(values)
        args = [bool(v.value) for v in values]
        operations = {'AND': lambda a,b:a and b, 'OR':lambda a,b:a or b,
                      'NOT':lambda a:not a, 'XOR':lambda a,b:a != b,
                      'NAND':lambda a,b:not(a and b), 'NOR':lambda a,b:not(a or b),
                      'XNOR':lambda a,b:a == b, 'IMPLY':lambda a,b:not a or b,
                      'NIMPLY':lambda a,b:a and not b}
        try:return _combine(values, operations[operation](*args))
        except (KeyError, TypeError):return _combine(values)


def _state(node):
    return tuple((s.identifier, UNKNOWN if s.is_linked else _default(s)) for s in node.inputs if _control(s)), tuple(s.identifier for s in node.outputs if s.is_linked)


_cache = {}
_enabled = False
_refresh_all = False


def _external_inputs(node):
    """Parameters consumed by the importer's coordinate/sampling helpers.

    These live outside the main group and cannot be inferred from its shader
    output. Keep only the selected sampler's controls, not every tag option.
    """
    if not node.node_tree.name.startswith(('foundry_h3.', 'foundry_h3odst.', 'foundry_reach.')):
        return frozenset()
    names = set()
    def choices(category):
        port = node.inputs.get(category)
        if port is None:return ()
        if not port.is_linked:return (port.default_value,)
        # A linked selector cannot be evaluated safely from its socket default.
        menus = [n for n in node.node_tree.nodes if n.bl_idname == 'GeometryNodeMenuSwitch']
        return tuple(item.name for n in menus for item in n.enum_items)
    parallax = choices('parallax')
    if any(mode in parallax for mode in ['simple','interpolated','simple_detail']):
        names.update(['height_map.rgb','height_scale'])
    if 'simple_detail' in parallax:names.add('height_scale_map.rgb')
    if any(mode in choices('environment_mapping') for mode in ['from_flat_texture','from_flat_exture_as_cubemap','from_flat_texture_as_cubemap']):
        names.update(['flat_envmap_matrix_x','flat_envmap_matrix_y','flat_envmap_matrix_z','hemisphere_percentage'])
    illumination = choices('self_illumination')
    if 'multilayer_additive' in illumination:
        names.update(['layers_of_4','layer_depth','texcoord_aspect_ratio','depth_darken'])
    if 'window_room' in illumination:names.update(['transform.rgb','distance_fade_scale'])
    if 'palettized_plasma' in illumination:
        helper = bpy.data.node_groups.get('foundry_h3odst.shader_halogram - palette vector')
        if helper:names.update(s.name for s in helper.interface.items_tree if s.item_type=='SOCKET' and s.in_out=='INPUT')
    family = node.node_tree.name.split('.',1)[1].split('.',1)[0].split(' - ',1)[0]
    if family == 'shader_water' and node.node_tree.name.startswith('foundry_reach.') and 'default' in choices('waveshape'):
        names.update(['wave_displacement_array.rgb', 'wave_slope_array.rgb', 'time_warp', 'time_warp_aux'])
        if 'repeat' in choices('detail'):
            names.update(['detail_slope_scale_x', 'detail_slope_scale_y', 'detail_slope_scale_z', 'detail_slope_steepness'])
    if family == 'shader_cortana':
        names.update(['layer_depth','layer_count','texcoord_aspect_ratio','depth_darken'])
    if family == 'shader_fur':
        names.update(['layers_of_4','layer_depth','texcoord_aspect_ratio','depth_darken','fur_fix','fur_shear_x','fur_shear_y'])
    if family in {'shader_fur','shader_halogram'} and 'from_texture' in choices('warp'):
        names.update(['warp_map.rgb','warp_amount_x','warp_amount_y'])
    if family == 'shader_screen':
        if any(mode != 'none' for mode in choices('warp')):names.update(['warp_map.rgb','warp_amount'])
        if any(mode.startswith('normal_map') for mode in choices('base')):names.update(['normal_map.rgb','palette_v'])
        if 'palette_lookup' in choices('overlay_a'):names.update(['intensity_color_u','intensity_color_v'])
    return frozenset(s.identifier for s in node.inputs if s.name in names)


def used_inputs(node):
    """Public for the library updater and tests; requires no rendering."""
    bindings = {s.identifier: _Value(UNKNOWN if s.is_linked or not _control(s) else _default(s), frozenset({s.identifier})) for s in node.inputs}
    graph = _Graph(node.node_tree, bindings)
    outputs = [s for s in node.outputs if s.is_linked] or list(node.outputs)
    return frozenset().union(*(graph.result(s.identifier).used for s in outputs), _external_inputs(node))


def refresh_node(node):
    if node.type != 'GROUP' or node.node_tree is None or not node.id_data.is_editable:
        return 0
    hidden = set(json.loads(node.node_tree.get('foundry_hidden_inputs', '[]')))
    changes = 0
    for socket in node.inputs:
        if socket.name in hidden and not socket.is_linked and not socket.hide:
            socket.hide = True
            changes += 1
    if not managed(node.node_tree):
        return changes
    key = (node.node_tree.as_pointer(), _state(node))
    needed = _cache.get(key)
    if needed is None:
        needed = _cache[key] = used_inputs(node)
    categories = set()
    for name in node.node_tree.keys():
        if name.endswith('_option_choices'):
            categories.update(json.loads(node.node_tree[name]))
    toggles = {s.identifier for s in node.node_tree.interface.items_tree if s.item_type=='SOCKET' and s.is_panel_toggle}
    for socket in node.inputs:
        # Keep main tag-category menus and stage/map panel toggles accessible.
        # Submenus inside a disabled stage can disappear with its parameters.
        keep = socket.name in categories and socket.type == 'MENU' or socket.identifier in toggles
        # Blender refuses hide=True on linked sockets. Do not repeatedly try
        # to set it: that would trigger redraw/dependency updates every tick.
        hide = not socket.is_linked and (socket.name in hidden or (not keep and socket.identifier not in needed))
        if socket.hide != hide:
            socket.hide = hide
            changes += 1
    return changes


def shader_trees():
    seen = set()
    for collection in [bpy.data.materials, bpy.data.worlds, bpy.data.lights, bpy.data.node_groups]:
        for owner in collection:
            tree = owner if isinstance(owner, bpy.types.NodeTree) else getattr(owner, 'node_tree', None)
            if tree and tree.bl_idname == 'ShaderNodeTree' and tree.as_pointer() not in seen:
                seen.add(tree.as_pointer())
                yield tree


def refresh_tree(tree):
    changes = 0
    if any(node.get('reach_water_sampler_owner') for node in tree.nodes):
        from ..tags.reach_water import sync_water_sampling
        changes = sync_water_sampling(tree)
    return changes + sum(refresh_node(node) for node in tree.nodes if node.type == 'GROUP')


@persistent
def _prepare_water_render(*_):
    from ..tags.reach_water import sync_water_sampling
    for material in bpy.data.materials:
        if material.node_tree and any(n.get('reach_water_sampler_owner') for n in material.node_tree.nodes):
            sync_water_sampling(material.node_tree)


def refresh_all():
    _cache.clear()
    return sum(refresh_tree(tree) for tree in shader_trees())


@persistent
def _loaded(*_):
    global _refresh_all
    _cache.clear()
    _refresh_all = True


@persistent
def _updated(scene, depsgraph):
    global _refresh_h1_areas
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.NodeTree):
            _cache.clear()


def _tick():
    global _refresh_all
    if not _enabled or bpy.app.background:
        return None
    if _refresh_all:
        _refresh_all = False
        refresh_all()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'NODE_EDITOR':continue
            tree = area.spaces.active.edit_tree
            if tree and tree.bl_idname == 'ShaderNodeTree' and refresh_tree(tree):
                area.tag_redraw()
    # Limit caching to a reasonable working set while users browse options.
    if len(_cache) > 512:_cache.clear()
    return .25


def register():
    global _enabled, _refresh_all
    _enabled = True
    _refresh_all = True
    for handlers, callback in [(bpy.app.handlers.load_post,_loaded),
                               (bpy.app.handlers.blend_import_post,_loaded),
                               (bpy.app.handlers.depsgraph_update_post,_updated),
                               (bpy.app.handlers.render_pre,_prepare_water_render)]:
        if callback not in handlers:handlers.append(callback)
    if not bpy.app.background and not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick,first_interval=.25,persistent=True)


def unregister():
    global _enabled
    _enabled = False
    for handlers, callback in [(bpy.app.handlers.load_post,_loaded),
                               (bpy.app.handlers.blend_import_post,_loaded),
                               (bpy.app.handlers.depsgraph_update_post,_updated),
                               (bpy.app.handlers.render_pre,_prepare_water_render)]:
        if callback in handlers:handlers.remove(callback)
    if bpy.app.timers.is_registered(_tick):bpy.app.timers.unregister(_tick)
    _cache.clear()

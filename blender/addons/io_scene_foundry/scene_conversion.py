"""Scene-scoped coordinate conversion, including referenced collection definitions."""
from collections import defaultdict
from math import isclose
import re

import bpy
from mathutils import Matrix, Vector

from .coordinate_system import CoordinateSystem, axis_rotation, placement_matrix
from . import marker_axis


def _geometry_node_modifier_inputs(modifier):
    """Read Geometry Nodes inputs through Blender's modifier interface."""
    inputs = modifier.properties.inputs
    for prop in inputs.bl_rna.properties:
        if prop.type == 'POINTER' and prop.identifier != 'rna_type':
            socket = getattr(inputs, prop.identifier)
            yield socket, getattr(socket, 'value', None)


def _collect_scope(scene):
    collections, objects, trees = set(), set(), set()

    def visit_tree(tree):
        if tree in trees:
            return
        trees.add(tree)
        for node in tree.nodes:
            for socket in node.inputs:
                value = getattr(socket, 'default_value', None)
                if isinstance(value, bpy.types.Object):
                    visit_object(value)
                elif isinstance(value, bpy.types.Collection):
                    visit(value)
            nested = getattr(node, 'node_tree', None)
            if nested:
                visit_tree(nested)

    def visit_object(ob):
        if ob in objects:
            return
        objects.add(ob)
        if ob.parent:
            visit_object(ob.parent)
        if ob.instance_type == 'COLLECTION' and ob.instance_collection:
            visit(ob.instance_collection)
        constraints = list(ob.constraints)
        if ob.pose:
            constraints.extend(constraint for bone in ob.pose.bones for constraint in bone.constraints)
        for constraint in constraints:
            for prop in constraint.bl_rna.properties:
                if prop.type == 'POINTER':
                    value = getattr(constraint, prop.identifier, None)
                    if isinstance(value, bpy.types.Object):
                        visit_object(value)
        for modifier in ob.modifiers:
            for prop in modifier.bl_rna.properties:
                if prop.type == 'POINTER':
                    value = getattr(modifier, prop.identifier, None)
                    if isinstance(value, bpy.types.Object):
                        visit_object(value)
            if modifier.type == 'NODES' and modifier.node_group:
                visit_tree(modifier.node_group)
                for socket, value in _geometry_node_modifier_inputs(modifier):
                    if isinstance(value, bpy.types.Object):
                        visit_object(value)
                    elif isinstance(value, bpy.types.Collection):
                        visit(value)

    def visit(collection):
        if collection in collections:
            return
        collections.add(collection)
        for child in collection.children:
            visit(child)
        for ob in collection.objects:
            visit_object(ob)

    visit(scene.collection)
    return objects, collections


def collect_collections(scene):
    return _collect_scope(scene)[1]


def collect_objects(scene):
    return _collect_scope(scene)[0]


def _remap_geometry_nodes(objects, mapping):
    """Privatize Geometry Nodes definitions whose object/collection inputs changed."""
    trees = {}

    def remap_tree(tree):
        if tree in trees:
            return trees[tree]
        result = tree.copy()
        trees[tree] = result
        changed = False
        for node in result.nodes:
            for socket in node.inputs:
                value = getattr(socket, 'default_value', None)
                if isinstance(value, bpy.types.ID) and value in mapping and mapping[value] != value:
                    socket.default_value = mapping[value]
                    changed = True
            nested = getattr(node, 'node_tree', None)
            if nested:
                replacement = remap_tree(nested)
                if replacement != nested:
                    node.node_tree = replacement
                    changed = True
        if not changed:
            trees[tree] = tree
            bpy.data.node_groups.remove(result)
            return tree
        return result

    for ob in objects:
        for modifier in ob.modifiers:
            if modifier.type == 'NODES' and modifier.node_group:
                modifier.node_group = remap_tree(modifier.node_group)
                for socket, value in _geometry_node_modifier_inputs(modifier):
                    if isinstance(value, bpy.types.ID) and value in mapping:
                        socket.value = mapping[value]


def _remap_pointers(owner, mapping, visited=None):
    """Remap references inside this scene only, including Foundry action tracks."""
    if visited is None:
        visited = set()
    pointer = owner.as_pointer()
    if pointer in visited:
        return
    visited.add(pointer)
    for prop in owner.bl_rna.properties:
        if prop.identifier in {'rna_type', 'id_data'}:
            continue
        if prop.type == 'POINTER':
            value = getattr(owner, prop.identifier, None)
            if value is None:
                continue
            if isinstance(value, bpy.types.ID):
                if not prop.is_readonly and value in mapping:
                    setattr(owner, prop.identifier, mapping[value])
            elif isinstance(value, bpy.types.PropertyGroup):
                _remap_pointers(value, mapping, visited)
        elif prop.type == 'COLLECTION':
            for value in getattr(owner, prop.identifier):
                if isinstance(value, bpy.types.PropertyGroup):
                    _remap_pointers(value, mapping, visited)


def isolate_scope(scene, objects=None, *, copy_data=True):
    """Copy shared objects, collections and datablocks before changing their units."""
    collections = collect_collections(scene)
    targets = collect_objects(scene) if objects is None else set(objects)
    affected_collections = {collection for collection in collections
                            if any(ob in targets for ob in collection.all_objects)}
    protected_collections = set()
    protected_objects = set()
    for other in bpy.data.scenes:
        if other != scene:
            protected_collections.update(collect_collections(other))
            protected_objects.update(collect_objects(other))
    # Unused definitions and objects outside this conversion also retain their units.
    protected_objects.update(ob for ob in targets
                             if any(coll not in collections for coll in ob.users_collection))
    object_map = {ob: ob.copy() for ob in targets if ob.library or ob in protected_objects}
    collection_map = {}

    def isolate_collection(collection):
        if collection in collection_map:
            return collection_map[collection]
        if collection not in affected_collections:
            collection_map[collection] = collection
            return collection
        if collection != scene.collection and (collection.library or collection in protected_collections):
            result = collection.copy()
            collection_map[collection] = result
            for ob in list(result.objects):
                result.objects.unlink(ob)
            for child in list(result.children):
                result.children.unlink(child)
            for ob in collection.objects:
                result.objects.link(object_map.get(ob, ob))
            for child in collection.children:
                result.children.link(isolate_collection(child))
        else:
            result = collection
            collection_map[collection] = result
            for ob in list(result.objects):
                if ob in object_map:
                    result.objects.unlink(ob)
                    result.objects.link(object_map[ob])
            for child in list(result.children):
                replacement = isolate_collection(child)
                if replacement != child:
                    result.children.unlink(child)
                    result.children.link(replacement)
        return result

    isolate_collection(scene.collection)
    for collection in collections:
        isolate_collection(collection)
    targets = {object_map.get(ob, ob) for ob in targets}
    for ob in targets:
        if ob.instance_collection in collection_map:
            ob.instance_collection = collection_map[ob.instance_collection]
    # Preserve sharing within the conversion, but not with any outside object.
    data_map = {}
    outside_data = {ob.data for ob in bpy.data.objects if ob not in targets and ob.data}
    for ob in targets:
        data = ob.data
        if copy_data and data and (data.library or data in outside_data):
            if data not in data_map:
                data_map[data] = data.copy()
            ob.data = data_map[data]
    mapping = object_map | data_map | collection_map
    _remap_pointers(scene.nwo, mapping)
    for ob in targets:
        _remap_pointers(ob, mapping)
        for modifier in ob.modifiers:
            _remap_pointers(modifier, mapping)
        for constraint in ob.constraints:
            _remap_pointers(constraint, mapping)
        if ob.pose:
            for bone in ob.pose.bones:
                for constraint in bone.constraints:
                    _remap_pointers(constraint, mapping)
        for owner in (ob, ob.data, getattr(ob.data, 'shape_keys', None)):
            ad = getattr(owner, 'animation_data', None)
            if ad:
                for driver in ad.drivers:
                    for variable in driver.driver.variables:
                        for target in variable.targets:
                            if target.id in mapping:
                                target.id = mapping[target.id]
    _remap_geometry_nodes(targets, mapping)
    return targets, object_map


def _bindings(scene, objects):
    """Return every action assignment that contributes to this scene's objects."""
    bindings = []
    for ob in objects:
        for owner in (ob, ob.data, getattr(ob.data, 'shape_keys', None)):
            ad = getattr(owner, 'animation_data', None)
            if not ad:
                continue
            if ad.action:
                bindings.append((owner, ad, ad.action, ad.action_slot))
            for track in ad.nla_tracks:
                for strip in track.strips:
                    if strip.action:
                        bindings.append((owner, strip, strip.action, strip.action_slot))
    for animation in scene.nwo.animations:
        for track in animation.action_tracks:
            if track.object in objects and track.action and not track.is_shape_key_action:
                slot = track.action.slots.active or next(iter(track.action.slots), None)
                bindings.append((track.object, track, track.action, slot))
    return bindings


def private_actions(scene, objects):
    """Each owner gets private curves; other scenes and differently based owners keep theirs."""
    copies, channels = {}, {}
    for owner, assignment, action, slot in _bindings(scene, objects):
        key = action, owner
        if key not in copies:
            copies[key] = action.copy()
        copied = copies[key]
        assignment.action = copied
        if slot is not None:
            copied_slot = copied.slots.get(slot.identifier)
            if hasattr(assignment, 'action_slot'):
                assignment.action_slot = copied_slot
            channels[copied, copied_slot.handle] = owner, copied_slot
    return channels


def _axis_mapping(rotation):
    result = []
    for axis in range(3):
        column = rotation.to_3x3().col[axis]
        destination = max(range(3), key=lambda i: abs(column[i]))
        if not isclose(abs(column[destination]), 1., abs_tol=1e-6):
            raise ValueError('Marker coordinate conversion requires a cardinal forward direction')
        result.append((destination, column[destination]))
    return result


def _permute(values, mapping, factor=1., *, signs=True):
    result = Vector((0, 0, 0))
    for source, (destination, sign) in enumerate(mapping):
        result[destination] = values[source] * factor * (sign if signs else 1.)
    return result


def _scale_curve(curve, factor):
    for key in curve.keyframe_points:
        left, right = key.handle_left.copy(), key.handle_right.copy()
        key.co[1] *= factor
        key.handle_left = (left[0], left[1] * factor)
        key.handle_right = (right[0], right[1] * factor)
    for point in curve.sampled_points:
        point.co[1] *= factor
    for modifier in curve.modifiers:
        if modifier.type == 'NOISE':
            if modifier.blend_type != 'MULTIPLY':
                modifier.strength *= factor
        elif modifier.type == 'GENERATOR':
            modifier.coefficients = [value * factor for value in modifier.coefficients]
        elif modifier.type == 'FNGENERATOR':
            modifier.amplitude *= factor
            modifier.value_offset *= factor
        elif modifier.type == 'ENVELOPE':
            modifier.default_min, modifier.default_max = sorted(
                (modifier.default_min * factor, modifier.default_max * factor))
            modifier.reference_value *= factor
            for point in modifier.control_points:
                point.min, point.max = sorted((point.min * factor, point.max * factor))
        elif modifier.type == 'LIMITS':
            minimum, maximum = modifier.min_y * factor, modifier.max_y * factor
            use_min, use_max = modifier.use_min_y, modifier.use_max_y
            if factor < 0:
                modifier.min_y, modifier.max_y = maximum, minimum
                modifier.use_min_y, modifier.use_max_y = use_max, use_min
            else:
                modifier.min_y, modifier.max_y = minimum, maximum
    curve.update()


def _channel_transform(path, index, factor, mapping, marker, root, physical_scale=False):
    multiplier, destination = 1., index
    if path in {'location', 'delta_location'}:
        multiplier = factor
        if marker or root:
            destination, sign = mapping[index]
            multiplier *= sign
    elif path.endswith('.location'):
        multiplier = factor  # Pose channels remain in their bone-local frame.
    elif marker and path in {'rotation_euler', 'delta_rotation_euler'}:
        destination, multiplier = mapping[index]
    elif marker and path in {'rotation_quaternion', 'delta_rotation_quaternion', 'rotation_axis_angle'}:
        if index:
            destination, multiplier = mapping[index - 1]
            destination += 1
    elif marker and path in {'scale', 'delta_scale'}:
        destination, _ = mapping[index]
    elif physical_scale and path == 'scale':
        multiplier = factor
    return destination, multiplier


def _driver_expression(driver):
    if driver.type == 'SCRIPTED':
        return driver.expression
    if not driver.variables:
        return '0.0'
    values = ', '.join(variable.name for variable in driver.variables)
    operation = {'AVERAGE': 'sum', 'SUM': 'sum', 'MIN': 'min', 'MAX': 'max'}[driver.type]
    expression = f'{operation}(({values},))'
    if driver.type == 'AVERAGE':
        expression += f' / {max(1, len(driver.variables))}'
    return expression


def _retarget_driver_variables(drivers, objects, markers, factor, mapping):
    """Expressions read source values in their original units before output conversion."""
    for curve in drivers:
        driver = curve.driver
        expression = _driver_expression(driver)
        changed = False
        for variable in driver.variables:
            target = variable.targets[0]
            if target.id not in objects:
                continue
            multiplier = 1.
            if variable.type == 'SINGLE_PROP':
                match = re.fullmatch(r'([a-z_]+)\[([0-3])\]', target.data_path)
                if match:
                    path, index = match[1], int(match[2])
                    destination, multiplier = _channel_transform(path, index, factor, mapping,
                        target.id in markers, target.id.parent is None,
                        target.id.type in {'LIGHT', 'LATTICE'})
                    target.data_path = f'{path}[{destination}]'
            elif (variable.type == 'TRANSFORMS' and target.transform_type.startswith('LOC_')
                  and target.transform_space == 'WORLD_SPACE'):
                destination, sign = mapping['XYZ'.index(target.transform_type[-1])]
                target.transform_type = f'LOC_{"XYZ"[destination]}'
                multiplier = sign * factor
            if multiplier != 1.:
                expression = re.sub(r'\b' + re.escape(variable.name) + r'\b',
                                    f'({variable.name} / {multiplier!r})', expression)
                changed = True
        if changed:
            driver.type = 'SCRIPTED'
            driver.expression = expression


def _transform_curves(curves, factor, mapping, marker, root, physical_scale=False):
    for curve in curves:
        destination, multiplier = _channel_transform(curve.data_path, curve.array_index,
                                                     factor, mapping, marker, root, physical_scale)
        if multiplier != 1.:
            if isinstance(curve, bpy.types.FCurve) and curve.driver:
                driver = curve.driver
                expression = _driver_expression(driver)
                driver.type = 'SCRIPTED'
                driver.expression = f'({multiplier!r}) * ({expression})'
            else:
                _scale_curve(curve, multiplier)
        curve.array_index = destination


def _rotation_channels(ob, rotation, mapping, marker, root):
    mode = ob.rotation_mode
    if marker:
        if mode not in {'QUATERNION', 'AXIS_ANGLE'}:
            new_mode = ''.join('XYZ'[mapping['XYZ'.index(axis)][0]] for axis in mode)
            main = _permute(ob.rotation_euler, mapping)
            delta = _permute(ob.delta_rotation_euler, mapping)
            ob.rotation_mode = new_mode
            ob.rotation_euler = main
            ob.delta_rotation_euler = delta
        else:
            q = rotation.to_quaternion()
            ob.rotation_quaternion = q @ ob.rotation_quaternion @ q.conjugated()
            ob.delta_rotation_quaternion = q @ ob.delta_rotation_quaternion @ q.conjugated()
            if mode == 'AXIS_ANGLE':
                ob.delta_rotation_euler = _permute(ob.delta_rotation_euler, mapping)
            aa = ob.rotation_axis_angle
            axis = _permute(aa[1:], mapping)
            ob.rotation_axis_angle = (aa[0], *axis)
        ob.scale = _permute(ob.scale, mapping, signs=False)
        ob.delta_scale = _permute(ob.delta_scale, mapping, signs=False)
    elif root:
        # A constant delta rotation preserves Euler/quaternion curve interpolation.
        q = rotation.to_quaternion()
        if mode == 'QUATERNION':
            ob.delta_rotation_quaternion = q @ ob.delta_rotation_quaternion
        else:
            order = 'XYZ' if mode == 'AXIS_ANGLE' else mode
            ob.delta_rotation_euler = (q @ ob.delta_rotation_euler.to_quaternion()).to_euler(order)


def convert_scene(context, destination):
    """Convert coordinates while retaining the user's selection and auto-key setting."""
    from . import utils
    selection, active = list(context.selected_objects), context.view_layer.objects.active
    auto_key = context.scene.tool_settings.use_keyframe_insert_auto
    mapping = {}
    context.scene.tool_settings.use_keyframe_insert_auto = False
    try:
        return _convert_scene(context, destination, mapping)
    finally:
        context.scene.tool_settings.use_keyframe_insert_auto = auto_key
        utils.deselect_all_objects()
        for ob in selection:
            ob = mapping.get(ob, ob)
            if ob.name in context.view_layer.objects:
                ob.select_set(True)
        active = mapping.get(active, active)
        if active is not None and active.name in context.view_layer.objects:
            context.view_layer.objects.active = active


def _convert_scene(context, destination, object_map):
    """Preserve exported placement while changing the active scene's convention."""
    from . import utils
    scene = context.scene
    source = CoordinateSystem.from_scene(scene.nwo)
    factor, angle = source.conversion_to(destination)
    if factor == 1. and angle == 0.:
        return False
    objects, mapping = isolate_scope(scene)
    object_map.update(mapping)
    channels = private_actions(scene, objects)
    context.view_layer.update()
    rotation = axis_rotation(angle)
    mapping = _axis_mapping(rotation)
    game = utils.get_game(scene.nwo.scene_project)
    markers = {ob for ob in objects if marker_axis.uses_scene_axes(ob, game)}
    world = {ob: ob.matrix_world.copy() for ob in objects}
    properties = ('location', 'delta_location', 'rotation_euler', 'delta_rotation_euler',
                  'rotation_quaternion', 'delta_rotation_quaternion', 'rotation_axis_angle',
                  'scale', 'delta_scale')
    authored = {ob: {name: tuple(getattr(ob, name)) for name in properties} for ob in objects}
    child_of_bindings = {constraint: constraint.inverse_matrix.copy()
                         for ob in objects for constraint in ob.constraints if constraint.type == 'CHILD_OF'}
    animated_deltas = set()
    for (action, _), (owner, slot) in channels.items():
        curves = utils.get_fcurves(action, slot)
        if isinstance(owner, bpy.types.Object) and curves and any(
                curve.data_path.startswith('delta_rotation') for curve in curves):
            animated_deltas.add(owner)
    for ob in objects:
        if ob.animation_data and any(curve.data_path.startswith('delta_rotation')
                                     for curve in ob.animation_data.drivers):
            animated_deltas.add(ob)
    # Reuse Foundry's distance, modifier, light and rest-bone scaling. Rotations
    # belong to object placement; pose rotations remain in their rest-bone frame.
    utils.transform_scene(context, factor, 0., source.forward, source.forward,
                          objects=objects, actions=[], marker_objects=(), scale_light_energy=True)
    for ob in objects:
        for name, value in authored[ob].items():
            setattr(ob, name, value)
        marker, root = ob in markers, ob.parent is None
        if root and not marker and angle and (ob.rotation_mode == 'AXIS_ANGLE' or ob in animated_deltas):
            # Blender has no axis-angle delta rotation. A constant parent frame
            # preserves the original curve interpolation without sampling it.
            frame = bpy.data.objects.new(f'{ob.name} Coordinates', None)
            for collection in ob.users_collection:
                collection.objects.link(frame)
            frame.nwo.is_frame = True
            frame.nwo.export_this = False
            frame.rotation_mode = 'QUATERNION'
            frame.rotation_quaternion = rotation.to_quaternion()
            ob.parent = frame
            ob.matrix_parent_inverse = Matrix.Identity(4)
            root = False
        _rotation_channels(ob, rotation, mapping, marker, root)
        for name in ('location', 'delta_location'):
            value = getattr(ob, name)
            setattr(ob, name, _permute(value, mapping, factor) if marker or root else value * factor)
        if ob.type in {'LIGHT', 'LATTICE'}:
            ob.scale *= factor
        ob.nwo.water_volume_flow_direction += angle
    for constraint, inverse in child_of_bindings.items():
        inverse.translation *= factor
        if constraint.owner_space == 'WORLD' and constraint.target_space == 'WORLD':
            if constraint.target in markers and not constraint.subtarget:
                inverse = rotation @ inverse
            inverse = inverse @ rotation.transposed()
        constraint.set_inverse_pending = False
        constraint.inverse_matrix = inverse
    for ob in objects:
        if ob.animation_data:
            _retarget_driver_variables(ob.animation_data.drivers, objects, markers, factor, mapping)
            _transform_curves(ob.animation_data.drivers, factor, mapping, ob in markers,
                              ob.parent is None, ob.type in {'LIGHT', 'LATTICE'})
    for (action, _), (owner, slot) in channels.items():
        curves = utils.get_fcurves(action, slot)
        if curves:
            _transform_curves(curves, factor, mapping, owner in markers,
                              isinstance(owner, bpy.types.Object) and owner.parent is None,
                              isinstance(owner, bpy.types.Object) and owner.type in {'LIGHT', 'LATTICE'})
    scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)
    # Parent inverses absorb the differing local conventions of markers, frames,
    # bones and geometry, without rewriting their children's animation curves.
    levels = defaultdict(list)
    for ob in objects:
        levels[utils.parentage_depth(ob)].append(ob)
    for depth in sorted(levels):
        for ob in levels[depth]:
            if ob.parent is not None:
                basis = ob.matrix_basis.copy()
                effective_parent = (ob.matrix_world @ basis.inverted_safe()
                                    @ ob.matrix_parent_inverse.inverted_safe())
                target = placement_matrix(world[ob], factor, angle, marker=ob in markers)
                if ob.type in {'LIGHT', 'LATTICE'}:
                    target = axis_rotation(angle) @ Matrix.Scale(factor, 4) @ world[ob]
                ob.matrix_parent_inverse = effective_parent.inverted_safe() @ target @ basis.inverted_safe()
        context.view_layer.update()
    scene.nwo.forward_direction = destination.forward
    scene.nwo.scale = destination.scale
    for collection in collect_collections(scene):
        collection.instance_offset = rotation @ (collection.instance_offset * factor)
    # View distances follow the converted geometry, only in the invoking screen.
    if context.screen:
        for area in context.screen.areas:
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.clip_start *= factor
                    space.clip_end *= factor
                    space.region_3d.view_distance *= factor
                    space.region_3d.view_location = rotation @ (space.region_3d.view_location * factor)
    return True

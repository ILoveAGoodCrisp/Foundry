"""Scenario Object export, refresh and child-scenario selection."""
from pathlib import Path
from math import pi
from types import SimpleNamespace
import bpy
from mathutils import Euler, Matrix, Vector

from ... import utils, import_transform
from ...props.scenario_objects import authored_options
from ...tags.backend import read_only_tags
from ...tags.scenario import ScenarioDocument
from ...tags.scenario_objects import (ObjectExport, object_types, object_fields, native_field,
    placement_path, replace_objects, authoring_property, supports_child_scenarios, bsp_references)
from .targets import scenario_targets

SCENARIO_OBJECT = '_connected_geometry_marker_type_scenario_object'


def scenario_object_orientation(matrix, game, *, importing=False):
    if game not in {'halo3', 'halo3odst'}:
        return matrix
    # H3/ODST scenario headings need a quarter turn to align with imported object geometry.
    # Rotate the heading around the placement itself, preserving its world position.
    result = Matrix.Rotation(pi / 2 if importing else -pi / 2, 4, 'Z') @ matrix
    result.translation = matrix.translation
    return result


def gather_scenario_objects(context):
    objects = []
    mapping = utils.create_parent_mapping(context)
    with utils.DepsgraphRead():
        for instance in context.evaluated_depsgraph_get().object_instances:
            original = (instance.instance_object if instance.is_instance else instance.object).original
            parent = instance.parent if instance.is_instance else original
            if original.type != 'EMPTY' or original.nwo.marker_type != SCENARIO_OBJECT or utils.ignore_for_export_fast(original, mapping, parent):
                continue
            objects.append(SimpleNamespace(name=original.name, nwo=original.nwo,
                parent=original.parent, matrix_world=instance.matrix_world.copy()))
    return objects


def object_placement(ob, game, scenario):
    matrix = scenario_object_orientation(utils.halo_transforms_matrix(ob.matrix_world, marker=True), game)
    scale = ob.matrix_world.to_scale()
    if game != 'halo1' and max(abs(value) for value in scale) - min(abs(value) for value in scale) > 0.0001:
        raise ValueError(f'{ob.name}: scenario objects require uniform scale')
    nwo = ob.nwo
    region = utils.true_region(nwo)
    origin = next((i for i, row in enumerate(scenario.block(scenario.tag.root(), 'structure bsps'))
                   if (ref := scenario.reference(row, 'structure bsp')) is not None and ref.ShortName == region), -1)
    parent = ob.parent
    parent_name = parent.name if game not in {'halo1', 'halo2'} and parent is not None and parent.nwo.marker_type == SCENARIO_OBJECT else ''
    if parent_name and parent.nwo.scenario_child_scenario != nwo.scenario_child_scenario:
        raise ValueError(f'{ob.name}: scenario object attachments must use the same scenario')
    position, rotation, _ = matrix.decompose()
    sign = -1 if ob.matrix_world.determinant() < 0 else 1
    placement = Matrix.LocRotScale(position, rotation, Vector(tuple(sign * abs(value) for value in scale)))
    if parent_name:
        if not parent.nwo.scenario_object_unique_name:
            raise ValueError(f'{ob.name}: the parent Scenario Object must have Unique Name enabled')
        parent_matrix = scenario_object_orientation(utils.halo_transforms_matrix(parent.matrix_world, marker=True), game)
        parent_position, parent_rotation, _ = parent_matrix.decompose()
        parent_sign = -1 if parent.matrix_world.determinant() < 0 else 1
        parent_placement = Matrix.LocRotScale(parent_position, parent_rotation,
            Vector(tuple(parent_sign * abs(value) for value in parent.matrix_world.to_scale())))
        placement = parent_placement.inverted_safe() @ placement
    position, rotation, scale = placement.decompose()
    euler = rotation.to_euler('ZYX')
    return ObjectExport(nwo.scenario_object_type, ob.name, utils.relative_path(nwo.marker_game_instance_tag_name.strip()),
        tuple(position), (euler.z, -euler.y, euler.x), abs(scale.x), nwo.scenario_object_unique_name,
        authored_options(nwo, game), origin_bsp=origin, mirrored=placement.determinant() < 0,
        parent_name=parent_name, editor_folder=nwo.scenario_editor_folder)


def export_scenario_objects(*, context=None, objects=None, scenario_path=None, tags_root=None, game=None):
    settings = utils.get_scene_props()
    game = game or utils.get_project(settings.scene_project).game
    enabled = {block for block, *_ in object_types(game) if getattr(settings, authoring_property(block))}
    if not enabled:
        return 0
    if objects is None:
        objects = gather_scenario_objects(context or bpy.context)
    objects = [ob for ob in objects if ob.nwo.scenario_object_type in enabled]
    with scenario_targets(objects, scenario_path=scenario_path or utils.get_asset_tag('.scenario', True),
            tags_root=tags_root or utils.get_tags_path(), game=game, include_existing_children=True) as targets:
        ids = set()
        if game != 'halo1':
            for scenario, _ in targets:
                for block, *_ in object_types(game):
                    if block not in enabled:
                        ids.update(native_field(row, ('object data', 'object id', 'unique id')).value
                                   for row in scenario.block(scenario.tag.root(), block))
        for scenario, objects_ in targets:
            replace_objects(scenario, [object_placement(ob, game, scenario) for ob in objects_], enabled, ids)
    return len(objects)


def read_scenario_objects(scenario, inherited_bsps=()):
    """Keep native authored settings for every supported placement category."""
    from ...tags.scenario_markers import editor_folder_name
    result = []
    names = [str(scenario.value(row, 'name')) for row in scenario.block(scenario.tag.root(), 'object names')]
    for block, palette, extension, _ in object_types(scenario.game):
        definitions = [scenario.reference(row, 'name') for row in scenario.block(scenario.tag.root(), palette)]
        for index, row in enumerate(scenario.block(scenario.tag.root(), block)):
            type_index = scenario.value(row, 'type')
            if type_index == -1:
                continue # Sapien keeps unassigned rows; these are not object placements.
            if not 0 <= type_index < len(definitions) or definitions[type_index] is None:
                raise ValueError(f'{scenario.path}: {block}[{index}] has an invalid palette index')
            definition = definitions[type_index].RelativePathWithExtension
            name_index = scenario.value(row, 'name')
            unique_name = 0 <= name_index < len(names) and bool(names[name_index])
            name = names[name_index] if unique_name else f'{Path(definition).stem}:{index}'
            transform = placement_path(scenario.game, block)
            position = tuple(native_field(row, (*transform, 'position')).value.to_array())
            rotation = native_field(row, (*transform, 'rotation')).value
            scale = 1. if scenario.game == 'halo1' else native_field(row, ('object data', 'scale')).value or 1.
            options = {}
            for field in object_fields(scenario.game, block):
                native = native_field(row, field.path, required=False)
                if native is None:
                    continue
                value = native.value
                catalog = native.options()
                if catalog is not None:
                    value = sum(1 << bit for bit, _, enabled in catalog.flags if enabled) if catalog.is_flags else catalog.current
                elif field.kind == 'rgb_color':
                    value = tuple((value.value >> bit & 255) / 255 for bit in (16, 8, 0))
                elif field.kind == 'real_rgb_color':
                    value = (value.red, value.green, value.blue)
                elif field.kind in {'real_bounds', 'angle_bounds'}:
                    value = (value.lower, value.upper)
                elif hasattr(value, 'to_array'):
                    value = tuple(value.to_array())
                options[field.path] = value
            parent_index = -1
            mirrored = False
            folder = ''
            if scenario.game != 'halo1':
                owner = row.field('object data').as_struct()
                transform_flags = owner.field('transform flags')
                if transform_flags is not None:
                    mirrored = transform_flags.get_flag('mirrored')
                elif scenario.game == 'halo2':
                    mirrored = any(field.get_flag('mirrored') for field in owner.fields_all()
                        if field.type_name == 'word flags' and field.options() and any(name == 'mirrored' for _, name, _ in field.options().flags))
                if owner.field('parent id') is not None:
                    parent_index = owner.field('parent id').as_struct().field('parent object').value
                folder_field = owner.field('editor folder')
                if folder_field is not None:
                    folder = editor_folder_name(scenario, folder_field.value)
            result.append((ObjectExport(block, name, definition, position,
                (rotation.yaw, rotation.pitch, rotation.roll), scale, unique_name, options,
                mirrored=mirrored, editor_folder=folder), parent_index, name_index))
    return result


def apply_object_properties(nwo, point, game):
    """Share authoring settings between the full importer and placement refresh."""
    nwo.marker_type = SCENARIO_OBJECT
    nwo.scenario_object_type = point.block
    nwo.marker_game_instance_tag_name = point.definition
    nwo.scenario_object_unique_name = point.unique_name
    nwo.scenario_editor_folder = point.editor_folder
    for field in object_fields(game, point.block):
        if field.path not in point.options:
            continue
        value = point.options[field.path]
        if field.kind.endswith('_flags'):
            for i, name in enumerate(field.options):
                if not name.lower().startswith(('unused', 'obsolete')):
                    setattr(nwo, field.property_name(name), bool(value & (1 << i)))
        else:
            try:
                setattr(nwo, field.property_name(), str(value) if field.kind.endswith('_enum') else value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f'{point.block}: cannot import {field.path}: {value!r}') from exc
    nwo.marker_game_instance_tag_variant_name = next(
        (value for path, value in point.options.items() if path[-1] == 'variant name'), '')


def object_import_matrix(point, parent_index, named, game):
    def native_world(point, parent_index, ancestors=()):
        yaw, pitch, roll = point.rotation
        local = Matrix.LocRotScale(Vector(point.position), Euler((roll, -pitch, yaw), 'ZYX'),
            Vector.Fill(3, -point.scale if point.mirrored else point.scale))
        if parent_index in named:
            if parent_index in ancestors:
                raise ValueError('Scenario object attachments contain a parent cycle')
            parent, grandparent = named[parent_index]
            return native_world(parent, grandparent, (*ancestors, parent_index)) @ local
        return local
    world = scenario_object_orientation(native_world(point, parent_index), game, importing=True)
    world.translation *= 100
    return import_transform.marker_matrix(world)


def refresh_scenario_objects(context, *, scenario_path=None, tags_root=None, game=None):
    settings = utils.get_scene_props()
    game = game or utils.get_project(settings.scene_project).game
    tags_root = Path(tags_root or utils.get_tags_path())
    scenario_path = Path(scenario_path or utils.get_asset_tag('.scenario', True))
    # Read everything before deleting any Blender placement. A broken tag leaves the scene intact.
    records = []
    visited = set()
    def read(path, child_name='', inherited_bsps=()):
        full_path = (tags_root / path).resolve()
        if full_path in visited:
            return
        visited.add(full_path)
        with ScenarioDocument(full_path, tags_root=tags_root, game=game, must_exist=True) as scenario:
            references = bsp_references(scenario) or inherited_bsps
            records.append((child_name, read_scenario_objects(scenario, references)))
            if supports_child_scenarios(game):
                key = 'child scenario' if game == 'halo1' else 'tag'
                for row in scenario.block(scenario.tag.root(), 'child scenarios'):
                    ref = scenario.reference(row, key)
                    if ref is not None and Path(ref.Filename).parent == (tags_root / scenario_path).resolve().parent:
                        read(Path(ref.RelativePathWithExtension), ref.ShortName, references)
    with read_only_tags():
        read(scenario_path)
    old = {ob for ob in context.scene.objects if ob.type == 'EMPTY' and ob.nwo.marker_type == SCENARIO_OBJECT}
    # Collection instances are also placements even when their source objects are not linked to the scene.
    with utils.DepsgraphRead():
        for instance in context.evaluated_depsgraph_get().object_instances:
            original = (instance.instance_object if instance.is_instance else instance.object).original
            if original.type == 'EMPTY' and original.nwo.marker_type == SCENARIO_OBJECT:
                old.add(original)
    old_collections = [collection for collection in context.scene.collection.children_recursive
                       if collection.get('nwo_scenario_object_placements')]
    generated = []
    try:
        collection = bpy.data.collections.new('Scenario Objects')
        collection['nwo_scenario_object_placements'] = True
        context.scene.collection.children.link(collection)
        for child_name, placements in records:
            named = {}
            parents = []
            native_named = {name_index: (point, parent_index) for point, parent_index, name_index in placements if point.unique_name}
            for point, parent_index, name_index in placements:
                ob = bpy.data.objects.new(point.name, None)
                generated.append(ob)
                ob.empty_display_type = 'ARROWS'
                apply_object_properties(ob.nwo, point, game)
                ob.nwo.scenario_child_scenario = child_name
                ob.matrix_world = object_import_matrix(point, parent_index, native_named, game)
                collection.objects.link(ob)
                if point.unique_name:
                    named[name_index] = ob
                parents.append((ob, parent_index))
            for ob, parent_index in parents:
                if parent_index in named:
                    world = ob.matrix_world.copy()
                    ob.parent = named[parent_index]
                    ob.matrix_world = world
    except Exception:
        for ob in generated:
            bpy.data.objects.remove(ob, do_unlink=True)
        if 'collection' in locals():
            bpy.data.collections.remove(collection)
        raise
    # Free original names before giving the imported objects their exact scripted names.
    for ob in old:
        bpy.data.objects.remove(ob, do_unlink=True)
    for old_collection in old_collections:
        if not old_collection.all_objects:
            bpy.data.collections.remove(old_collection)
    for ob, point in zip(generated, (p for _, placements in records for p, _, _ in placements)):
        ob.name = point.name
    return generated


class NWO_OT_RefreshScenarioObjects(bpy.types.Operator):
    bl_idname = 'nwo.refresh_scenario_objects'
    bl_label = 'Update Scenario Objects From Tag'
    bl_description = 'Replace all Blender Scenario Object placements with placements and settings from the asset scenario and its child scenarios'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.asset_type == 'scenario' and utils.valid_nwo_asset(context) and utils.get_project() is not None

    def execute(self, context):
        try:
            objects = refresh_scenario_objects(context)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Updated {len(objects)} scenario object placements')
        return {'FINISHED'}


_child_items = []
_airprobe_items = []


class NWO_OT_GetScenarioAirprobes(bpy.types.Operator):
    bl_idname = 'nwo.get_scenario_airprobes'
    bl_label = 'Scenario Airprobes'
    bl_description = 'Select a light airprobe from the asset scenario'
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return utils.poll_project(cls) and context.object is not None

    def items(self, context):
        global _airprobe_items
        if not utils.current_project_valid():
            _airprobe_items = [('', 'None', 'Use automatic lighting')]
            return _airprobe_items
        names = []
        project = utils.get_project()
        path = utils.get_asset_tag('.scenario', True)
        if project and path and (Path(utils.get_tags_path()) / path).is_file():
            with read_only_tags(), ScenarioDocument(path, tags_root=utils.get_tags_path(),
                    game=project.game, must_exist=True) as scenario:
                block = scenario.tag.root().field('airprobes')
                if block is not None:
                    names = sorted({str(scenario.value(row, 'airprobe name')) for row in block.as_block()
                                    if scenario.value(row, 'airprobe name')})
        _airprobe_items = [('', 'None', 'Use automatic lighting')] + [(name, name, '') for name in names]
        return _airprobe_items

    airprobe: bpy.props.EnumProperty(name='Light Airprobe', items=items)

    def execute(self, context):
        if not utils.require_project(self):
            return {'CANCELLED'}
        nwo = context.object.nwo
        for field in object_fields(utils.get_project().game, nwo.scenario_object_type):
            if field.path[-1] == 'light airprobe name':
                setattr(nwo, field.property_name(), self.airprobe)
        return {'FINISHED'}


class NWO_OT_SelectChildScenario(bpy.types.Operator):
    bl_idname = 'nwo.select_child_scenario'
    bl_label = 'Select Child Scenario'
    bl_description = 'Search scenario tags in the asset scenario folder'
    bl_options = {'UNDO'}
    bl_property = 'child_scenario'

    @classmethod
    def poll(cls, context):
        return utils.poll_project(cls) and utils.valid_nwo_asset(context)

    def items(self, context):
        if not utils.current_project_valid():
            return []
        return _child_items

    child_scenario: bpy.props.EnumProperty(name='Child Scenario', items=items)
    scene_property: bpy.props.StringProperty(options={'HIDDEN'})

    def invoke(self, context, event):
        if not utils.require_project(self):
            return {'CANCELLED'}
        global _child_items
        main = Path(utils.get_asset_tag('.scenario', True))
        folder = Path(utils.get_tags_path()) / main.parent
        _child_items = [(path.stem, path.stem, str(path)) for path in sorted(folder.glob('*.scenario')) if path.name.casefold() != main.name.casefold()]
        if not _child_items:
            self.report({'INFO'}, 'No child scenario tags found in the asset scenario folder')
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context):
        if not utils.require_project(self):
            return {'CANCELLED'}
        if self.scene_property:
            setattr(utils.get_scene_props(), self.scene_property, self.child_scenario)
        else:
            if context.object is None:
                return {'CANCELLED'}
            context.object.nwo.scenario_child_scenario = self.child_scenario
        return {'FINISHED'}


def draw_child_scenario(layout, nwo, game):
    if supports_child_scenarios(game):
        row = layout.row(align=True)
        row.prop(nwo, 'scenario_child_scenario')
        row.operator('nwo.select_child_scenario', text='', icon='VIEWZOOM')


def draw_scenario_object(layout, nwo, game):
    from ...ui.panel import draw_tag_path
    layout.prop(nwo, 'scenario_object_type')
    layout.prop(utils.get_scene_props(), authoring_property(nwo.scenario_object_type))
    draw_tag_path(layout, nwo, 'scenario_object_tag_name')
    layout.operator('nwo.import_game_instance_tag', text='Import Object Geometry', icon='IMPORT')
    layout.prop(nwo, 'scenario_object_unique_name')
    if game != 'halo1':
        layout.prop(nwo, 'scenario_editor_folder')
    groups = {}
    for field in object_fields(game, nwo.scenario_object_type):
        heading = ' / '.join(name.replace('_', ' ').removesuffix(' data').title() for name in field.path[:-1]) or 'Placement'
        box = groups.get(heading)
        if box is None:
            box = layout.box().column(align=True)
            box.label(text=heading)
            groups[heading] = box
        if field.kind.endswith('_flags'):
            flags = box.box().column(align=True)
            flags.label(text=field.path[-1].title())
            for name in field.options:
                if not name.lower().startswith(('unused', 'obsolete')):
                    flags.prop(nwo, field.property_name(name))
        else:
            row = box.row(align=True)
            row.prop(nwo, field.property_name())
            if field.path[-1] == 'variant name' and bpy.ops.nwo.get_model_variants.poll():
                row.operator_menu_enum('nwo.get_model_variants', 'variant', text='', icon='DOWNARROW_HLT')
            elif field.path[-1] == 'light airprobe name':
                row.operator_menu_enum('nwo.get_scenario_airprobes', 'airprobe', text='', icon='DOWNARROW_HLT')

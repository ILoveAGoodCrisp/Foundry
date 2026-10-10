"""Authored scenario object fields, derived from the native engine schemas."""
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha1

from .scenario_markers import scenario_schema, block_definition, field_name

# Placement block, palette block, object tag extension, native object type.
OBJECT_TYPES = (
    ('scenery', 'scenery palette', 'scenery', 'scenery'),
    ('bipeds', 'biped palette', 'biped', 'biped'),
    ('vehicles', 'vehicle palette', 'vehicle', 'vehicle'),
    ('equipment', 'equipment palette', 'equipment', 'equipment'),
    ('weapons', 'weapon palette', 'weapon', 'weapon'),
    ('machines', 'machine palette', 'device_machine', 'machine'),
    ('controls', 'control palette', 'device_control', 'control'),
    ('light fixtures', 'light fixtures palette', 'device_light_fixture', 'light_fixture'),
    ('sound scenery', 'sound scenery palette', 'sound_scenery', 'sound_scenery'),
    ('crates', 'crate palette', 'crate', 'crate'),
    ('creatures', 'creature palette', 'creature', 'creature'),
    ('giants', 'giant palette', 'giant', 'giant'),
    ('effect scenery', 'effect scenery palette', 'effect_scenery', 'effect_scenery'),
    ('terminals', 'terminal palette', 'device_terminal', 'terminal'),
    ('dispensers', 'dispenser palette', 'device_dispenser', 'dispenser'),
    ('spawners', 'spawner palette', 'spawner', 'spawner'),
)


@lru_cache(maxsize=7)
def root_fields(game):
    schema = scenario_schema(game)
    return {field_name(f.get('name')): f for f in
            schema['structs'][schema['blocks'][schema['block']]['struct']]['fields'] if f.get('name')}


@lru_cache(maxsize=7)
def object_types(game):
    fields = root_fields(game)
    specs = tuple((block, 'light fixture palette' if game == 'halo1' and block == 'light fixtures' else palette,
                   extension, type_) for block, palette, extension, type_ in OBJECT_TYPES)
    return tuple(row for row in specs if row[0] in fields and row[1] in fields)


def supports_child_scenarios(game):
    # H2's obsolete @child scenarios field is hidden and has no supported editor workflow.
    return 'child scenarios' in root_fields(game)


@dataclass(frozen=True)
class ObjectField:
    path: tuple[str, ...]
    kind: str
    options: tuple[str, ...] = ()
    string_length: int = 0
    index_block: str = ''

    def property_name(self, flag=None):
        key = '/'.join(self.path) + ':' + self.kind + (':' + flag if flag is not None else '')
        return 'scenario_option_' + sha1(key.encode()).hexdigest()[:20]


# These values describe generated editor/runtime state, rather than placement settings.
GENERATED = {'object id', 'parent object', 'editor folder', 'runtimeObjectHandle',
             'havok mopp index', 'ai spawning squad', "DON'T TOUCH THIS", 'no name',
             'pah pah', 'Entity Placeholder', 'Spawner Placeholder',
             'manual bsp flags', 'can attach to bsp flags', 'bsp indices', 'bsp policy',
             'position', 'rotation', 'scale', 'transform flags'}


@lru_cache(maxsize=None)
def object_fields(game, block):
    schema = scenario_schema(game)
    result = []
    def walk(struct, path=()):
        for field in schema['structs'][struct]['fields']:
            name = field_name(field.get('name'))
            kind = field['type']
            if not name or name in GENERATED or not path and name in {'type', 'name'}:
                continue
            if kind == 'struct':
                walk(field['definition'], (*path, name))
            elif kind in {'string', 'string_id', 'real', 'angle', 'real_rgb_color', 'rgb_color',
                          'real_bounds', 'angle_bounds', 'real_point_3d', 'real_vector_3d',
                          'char_integer', 'short_integer', 'long_integer', 'char_block_index',
                          'short_block_index', 'long_block_index'} or kind.endswith(('_enum', '_flags')):
                options = tuple(schema['enums_flags'][field['definition']]['options']) if kind.endswith(('_enum', '_flags')) else ()
                index_block = next((n for n, f in root_fields(game).items()
                                    if kind.endswith('block_index') and f.get('definition') == field.get('definition')), '')
                if 'group' in name and kind in {'short_integer', 'char_integer'}:
                    index_block = 'device groups'
                result.append(ObjectField((*path, name), kind, options,
                    field.get('definition', 32) if kind == 'string' else 0, index_block))
    walk(block_definition(game, block)['struct'])
    return tuple(result)


def native_field(row, path, *, required=True):
    for name in path[:-1]:
        field = row.field(name)
        if field is None:
            if not required:
                return None
            raise ValueError(f'{row.path}: missing {name!r} in {path}, available: {row.field_names()}')
        row = field.as_struct()
    return row.field(path[-1])


def authored_default(field):
    if field.kind.endswith('_flags'):
        return 0
    if field.kind.endswith('_enum'):
        return field.options.index('neutral') if 'neutral' in field.options else 0
    if field.kind in {'string', 'string_id'}:
        return ''
    if field.kind in {'rgb_color', 'real_rgb_color'}:
        return (1., 1., 1.)
    if field.kind in {'real_bounds', 'angle_bounds', 'real_point_3d', 'real_vector_3d'}:
        return (0.,) * (2 if 'bounds' in field.kind else 3)
    if field.kind in {'real', 'angle'}:
        return 1. if field.path[-1] in {'body vitality', 'effect size scale', 'intensity', 'Directional Acceleration Mult. '} else 0.
    return -1 if 'block_index' in field.kind or 'group' in field.path[-1] else 0


def placement_path(game, block):
    return (('properties', 'placement') if block in {'bipeds', 'vehicles'} else ('placement',)) if game == 'halo1' else ('object data',)


def native_object_type(game, block):
    spec = next(row for row in object_types(game) if row[0] == block)
    schema = scenario_schema(game)
    if game == 'halo1':
        field = next(f for f in schema['structs'][block_definition(game, 'object names')['struct']]['fields']
                     if field_name(f.get('name')) == 'object type')
        name = {'machine': 'device machine', 'control': 'device control',
                'light_fixture': 'device light fixture', 'sound_scenery': 'sound scenery'}.get(spec[3], spec[3])
    else:
        struct = block_definition(game, block)['struct']
        for name in ('object data', 'object id'):
            struct = next(f['definition'] for f in schema['structs'][struct]['fields'] if field_name(f.get('name')) == name)
        field = next(f for f in schema['structs'][struct]['fields'] if field_name(f.get('name')) == 'type')
        name = spec[3]
    return schema['enums_flags'][field['definition']]['options'].index(name)


def authoring_property(block):
    return block.replace(' ', '_') + '_from_blender'


def context_block(document, name):
    block = document.block(document.tag.root(), name)
    parent = getattr(document, 'authoring_context', None)
    if not len(block) and parent is not None and parent is not document:
        return context_block(parent, name)
    return block


def bsp_references(document):
    block = context_block(document, 'structure bsps')
    return [document.reference(row, 'structure bsp') for row in block]


@dataclass(frozen=True)
class ObjectExport:
    block: str
    name: str
    definition: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    scale: float
    unique_name: bool
    options: dict
    manual_bsps: tuple[int, ...] = ()
    attach_bsps: tuple[int, ...] = ()
    origin_bsp: int = -1
    mirrored: bool = False
    parent_name: str = ''
    editor_folder: str = ''


def name_metadata(row, game):
    if game == 'halo1':
        return row.field('object type'), row.field('object index')
    if game == 'halo2':
        fields = tuple(field for field in row.fields_all() if field.type_name == 'short integer')
        if len(fields) != 2:
            raise ValueError(f'Unexpected Halo 2 object name fields: {[(f.name, f.type_name) for f in row.fields_all()]}')
        return fields
    return row.field('object_type'), row.field('scenario_datum_index')


def replace_objects(document, placements, authored_blocks, reserved_ids=None):
    """Replace enabled categories; keep other categories and their name indices intact."""
    from math import isfinite
    import struct
    import zlib
    from pathlib import Path
    placements = list(placements)
    game = document.game
    authored_blocks = set(authored_blocks)
    specs = {row[0]: row for row in object_types(game)}
    if not authored_blocks <= specs.keys():
        raise ValueError('Unsupported scenario object authoring type')
    if any(point.block not in authored_blocks for point in placements):
        raise ValueError('Scenario object type is not enabled for authoring')
    root = document.tag.root()
    existing_definitions = {block: {
        ref.RelativePathWithExtension.replace('\\', '/').casefold()
        for row in document.block(root, spec[1])
        if (ref := document.reference(row, 'name')) is not None}
        for block, spec in specs.items()}
    from .scenario_markers import editor_folder_index
    folder_indices = {name: editor_folder_index(document, name)
                      for name in {point.editor_folder for point in placements}}
    bsp_refs = bsp_references(document)
    bsp_count = len(bsp_refs)
    owned_names, protected_names = set(), set()
    for block in specs:
        indices = owned_names if block in authored_blocks else protected_names
        indices.update(index for row in document.block(root, block)
                       if isinstance(index := document.value(row, 'name'), int) and index >= 0)
    named = [point.name for point in placements if point.unique_name]
    if len(set(named)) != len(named):
        raise ValueError('Named scenario objects must have unique names')
    for point in placements:
        if point.unique_name and (not point.name.strip() or game in {'halo1', 'halo2', 'halo3', 'halo3odst'} and len(point.name.encode('utf-8')) > 31):
            raise ValueError(f'{point.name}: scenario object name exceeds the engine name limit')
        path = Path(point.definition.replace('\\', '/'))
        if path.is_absolute() or '..' in path.parts or path.suffix.lower() != '.' + specs[point.block][2]:
            raise ValueError(f'{point.name}: invalid {point.block} tag path')
        # Some stock scenarios reference tags omitted from the editing kit.
        # Keep existing references without accepting new mistyped tag paths.
        if not (document.tags_root / path).is_file() and path.as_posix().casefold() not in existing_definitions[point.block]:
            raise FileNotFoundError(document.tags_root / path)
        try:
            values = struct.unpack('<7f', struct.pack('<7f', *point.position, *point.rotation, point.scale))
        except (struct.error, OverflowError) as exc:
            raise ValueError(f'{point.name}: invalid object transform') from exc
        if not all(isfinite(value) for value in values) or point.scale <= 0:
            raise ValueError(f'{point.name}: invalid object transform or scale')
        if any(not 0 <= index < bsp_count for index in (*point.manual_bsps, *point.attach_bsps)) or point.origin_bsp != -1 and not 0 <= point.origin_bsp < bsp_count:
            raise ValueError(f'{point.name}: invalid BSP index')
        if game not in {'halo4', 'halo2a'} and any(index >= 16 for index in (*point.manual_bsps, *point.attach_bsps)):
            raise ValueError(f'{point.name}: this engine supports BSP masks 0 through 15')
        if game in {'halo4', 'halo2a'} and len(point.manual_bsps) > 32:
            raise ValueError(f'{point.name}: manual BSP placement supports at most 32 references')
        fields = {field.path: field for field in object_fields(game, point.block)}
        for path, value in point.options.items():
            field = fields.get(path)
            if field is None:
                raise ValueError(f'{point.name}: invalid authored field {path}')
            if field.kind.endswith('_enum') and not 0 <= value < len(field.options):
                raise ValueError(f'{point.name}: invalid {path[-1]} option')
            if field.kind == 'string' and len(value.encode('utf-8')) >= field.string_length:
                raise ValueError(f'{point.name}: {path[-1]} exceeds the engine string limit')
            if field.index_block and value != -1 and not 0 <= value < len(context_block(document, field.index_block)):
                raise ValueError(f'{point.name}: invalid {path[-1]} index')
            components = value if isinstance(value, tuple) else (value,)
            if any(isinstance(v, float) and not isfinite(v) for v in components):
                raise ValueError(f'{point.name}: invalid {path[-1]}')
        if point.parent_name and point.parent_name not in named:
            unmodified_parent = any(i in protected_names and str(document.value(row, 'name')) == point.parent_name
                                    for i, row in enumerate(document.block(root, 'object names')))
            if not unmodified_parent:
                raise ValueError(f'{point.name}: parent must be a named Scenario Object in the same scenario')
    for block in authored_blocks:
        points = [point for point in placements if point.block == block]
        if len(points) > block_definition(game, block)['max_count']:
            raise ValueError(f'Too many {block} placements')
        if len({point.definition.casefold() for point in points}) > block_definition(game, specs[block][1])['max_count']:
            raise ValueError(f'Too many {block} palette entries')
    names = document.block(root, 'object names')
    existing_names = {str(document.value(row, 'name')): i for i, row in enumerate(names) if document.value(row, 'name')}
    affected_types = {native_object_type(game, block) for block in authored_blocks}
    free_names = []
    for i, row in enumerate(names):
        type_field, index_field = name_metadata(row, game)
        type_value = type_field.options().current if type_field.options() is not None else type_field.value
        name = str(document.value(row, 'name'))
        if i not in protected_names and (i in owned_names or type_value in affected_types):
            index_field.set(-1)
            if name not in named:
                # Keep other categories' indices stable while removing stale authored names.
                document._set_value(row, 'name', '')
                type_field.set(-1)
                existing_names.pop(name, None)
                free_names.append(i)
        elif not name and index_field.value == -1:
            free_names.append(i)
        elif name in named and (i in protected_names or index_field.value >= 0):
            raise ValueError('A scenario object name is already used by a category that is not authored from Blender')
    if len(names) + max(0, len(set(named) - existing_names.keys()) - len(free_names)) > block_definition(game, 'object names')['max_count']:
        raise ValueError('Too many scenario object names')
    # Mutations below are committed only if the whole export succeeds.
    for block in authored_blocks:
        document.block(root, block).clear()
        document.block(root, specs[block][1]).clear()
    for name in named:
        if name not in existing_names:
            index = free_names.pop(0) if free_names else document.block(root, 'object names').add()
            document._set_value(document.block(root, 'object names')[index], 'name', name)
            existing_names[name] = index
    used_ids = set() if reserved_ids is None else reserved_ids
    if game != 'halo1':
        for block in specs.keys() - authored_blocks:
            for row in document.block(root, block):
                used_ids.add(native_field(row, ('object data', 'object id', 'unique id')).value)
    palettes = {block: {} for block in authored_blocks}
    for point in placements:
        palette = palettes[point.block]
        key = point.definition.casefold()
        if key not in palette:
            index = document.block(root, specs[point.block][1]).add()
            document.set_reference(document.block(root, specs[point.block][1])[index], 'name', point.definition)
            palette[key] = index
        index = document.block(root, point.block).add()
        def row():
            return document.block(document.tag.root(), point.block)[index]
        document._set_value(row(), 'type', palette[key])
        document._set_value(row(), 'name', existing_names[point.name] if point.unique_name else -1)
        transform_path = placement_path(game, point.block)
        for field_name_, values in (('position', point.position), ('rotation', point.rotation)):
            field = native_field(row(), (*transform_path, field_name_))
            field.set(type(field.value)(*values))
        for path, value in point.options.items():
            authored_field = next(f for f in object_fields(game, point.block) if f.path == path)
            field = native_field(row(), path, required=False)
            if field is None:
                if value != authored_default(authored_field):
                    raise ValueError(f'{point.name}: this scenario tag layout does not support {" / ".join(path)}')
                continue
            options = field.options()
            if options is not None and options.is_flags:
                for bit, flag, _ in options.flags:
                    field.set_flag(flag, bool(value & (1 << bit)))
            elif authored_field.kind == 'rgb_color':
                red, green, blue = (max(0, min(255, round(component * 255))) for component in value)
                field.set(type(field.value)((red << 16) | (green << 8) | blue))
            elif isinstance(value, tuple):
                field.set(type(field.value)(*value))
            else:
                field.set(value)
        if point.unique_name:
            name_row = document.block(root, 'object names')[existing_names[point.name]]
            type_field, index_field = name_metadata(name_row, game)
            type_field.set(native_object_type(game, point.block))
            index_field.set(index)
        if game != 'halo1':
            owner = row().field('object data').as_struct()
            document._set_value(owner, 'scale', point.scale)
            id_ = zlib.crc32((document.path + '/' + point.block + '/' + point.name + '/' + str(index)).encode()) & 0x7fffffff
            while id_ in used_ids:
                id_ = (id_ + 1) & 0x7fffffff
            used_ids.add(id_)
            object_id = owner.field('object id').as_struct()
            document._set_value(object_id, 'unique id', id_)
            document._set_value(object_id, 'type', native_object_type(game, point.block))
            document._set_value(object_id, 'source', 'editor')
            document._set_value(object_id, 'origin bsp index', point.origin_bsp)
            if owner.field('editor folder') is not None:
                document._set_value(owner, 'editor folder', folder_indices[point.editor_folder])
            if owner.field('transform flags') is not None:
                document._set_value(owner, 'transform flags', int(point.mirrored))
            elif game == 'halo2':
                for field in owner.fields_all():
                    if field.type_name == 'word flags' and field.options() and any(name == 'mirrored' for _, name, _ in field.options().flags):
                        field.set_flag('mirrored', point.mirrored)
            if owner.field('parent id') is not None:
                parent = owner.field('parent id').as_struct()
                document._set_value(parent, 'parent object', existing_names[point.parent_name] if point.parent_name else -1)
            for field_name_, indices in (('manual bsp flags', point.manual_bsps), ('can attach to bsp flags', point.attach_bsps)):
                field = native_field(row(), ('object data', field_name_), required=False)
                if field is None:
                    continue
                if field.as_struct() is None:
                    mask = sum(1 << i for i in indices)
                    field.set(mask if game != 'halo2' or mask < 32768 else mask - 65536)
                else:
                    for bsp in indices:
                        references = native_field(row(), ('object data', field_name_)).as_struct().field('references block').as_block()
                        ri = references.add()
                        reference = native_field(row(), ('object data', field_name_)).as_struct().field('references block').as_block()[ri]
                        bsp_reference = bsp_refs[bsp]
                        document.set_reference(reference, reference.fields()[0].clean_name, bsp_reference)
                    mask = (1 << len(indices)) - 1
                    native_field(row(), ('object data', field_name_)).as_struct().field('flags').set(mask if mask < 0x80000000 else mask - 0x100000000)
        elif row().field('bsp indices') is not None:
            mask = sum(1 << i for i in point.manual_bsps)
            document._set_value(row(), 'bsp indices', mask if mask < 32768 else mask - 65536)
    document.tag_has_changes = bool(authored_blocks)

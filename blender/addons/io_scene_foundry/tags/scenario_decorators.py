"""Native decorator source placement writers for Halo 2 and later engines."""
from collections import defaultdict
from math import atan2, floor, isfinite, sqrt, tau
from pathlib import Path

from .backend import TagDocument
from .halo1_detail_objects import signed
from .scenario_markers import scenario_schema


def _validate(scenario, sets):
    for record in sets:
        path = Path(record.definition.replace('\\', '/'))
        if path.suffix.lower() != '.decorator_set' or path.is_absolute() or '..' in path.parts:
            raise ValueError(f'Invalid decorator set: {record.definition!r}')
        if not (scenario.tags_root / path).is_file():
            raise FileNotFoundError(scenario.tags_root / path)
        for p in record.placements:
            if not all(isfinite(v) for v in (*p.position, *p.rotation, p.scale, *p.tint)) or p.scale <= 0:
                raise ValueError('Invalid decorator transform or tint')
            if sum(v * v for v in p.rotation) < 1e-12:
                raise ValueError('Invalid decorator quaternion')
            if scenario.game in {'halo3', 'halo3odst'} and p.bsp_index != -1 and not 0 <= p.bsp_index < len(scenario.block(scenario.tag.root(), 'structure bsps')):
                raise ValueError('Invalid decorator editor BSP index')


def replace_decorators(scenario, sets):
    """Replace authored source placements, leaving cache generation to Sapien."""
    sets = list(sets)
    _validate(scenario, sets)
    if scenario.game == 'halo2':
        return _replace_halo2(scenario, sets)
    if scenario.game == 'halo1':
        raise ValueError('Halo 1 detail objects belong to the structure BSP')
    limits = scenario_schema(scenario.game)['blocks']
    if (len(sets) > limits['decorator_scenario_set_block']['max_count'] or
            any(len(record.placements) > limits['global_decorator_placement_block']['max_count'] for record in sets)):
        raise ValueError('Too many decorator sets or placements')
    for record in sets:
        with TagDocument(record.definition, tags_root=scenario.tags_root, game=scenario.game, must_exist=True) as definition:
            count = len(definition.block(definition.tag.root(), 'decorator types'))
            if any(not 0 <= p.type_index < count for p in record.placements):
                raise ValueError(f'{record.definition}: invalid decorator type index')
    root = scenario.tag.root()
    decorators = scenario.block(root, 'decorators')
    if not len(decorators):
        decorators.add()
    def sets_block():
        return scenario.block(scenario.block(root, 'decorators')[0], 'sets')
    sets_block().clear()
    for record in sets:
        set_index = sets_block().add()
        scenario.set_reference(sets_block()[set_index], 'decorator set', record.definition)
        def placements():
            return scenario.block(sets_block()[set_index], 'placements')
        for p in record.placements:
            index = placements().add()
            row = placements()[index]
            for name, values in (('position', p.position), ('rotation', p.rotation), ('tint color', p.tint)):
                field = scenario.required_field(row, name)
                field.set(type(field.value)(*values))
            for name, value in (('scale', p.scale), ('type index', p.type_index),
                                ('motion scale', p.motion_scale if scenario.game in {'halo4', 'halo2a'} else signed(p.motion_scale, 8)),
                                ('ground tint', p.ground_tint if scenario.game in {'halo4', 'halo2a'} else signed(p.ground_tint, 8)),
                                ('cluster index', -1), ('cluster decorator set index', -1),
                                ('bsp index', -1), ('runtime bsp index', -1), ('editor bound to bsp', p.bsp_index)):
                field = row.field(name)
                if field is not None:
                    field.set(value)
    scenario.tag_has_changes = True


def _packed_rotation(p, bounds):
    x, y, z, w = p.rotation
    length = sqrt(x*x + y*y + z*z + w*w)
    x, y, z, w = (v / length for v in (x, y, z, w))
    normal = (2*(x*z + w*y), 2*(y*z - w*x), 1 - 2*(x*x + y*y))
    nx, ny, nz = normal
    if nz <= -0.999999:
        ax, ay, az, aw = 1., 0., 0., 0.
    else:
        factor = sqrt(2 * (1 + nz))
        ax, ay, az, aw = -ny/factor, nx/factor, 0., factor/2
    # The local Z twist is align.inverse() * rotation.
    twist_z = aw*z - ax*y + ay*x - az*w
    twist_w = aw*w + ax*x + ay*y + az*z
    angle = round((2 * atan2(twist_z, twist_w) % tau) / tau * 15) & 15
    lower, upper = bounds
    fraction = (p.scale - lower) / (upper - lower) if upper > lower else 0.
    scale = max(0, min(15, round(fraction * 15)))
    packed = p.type_index | (p.permutation_index << 3) | (angle << 9) | (scale << 16)
    for value, shift in zip(normal, (20, 24, 28)):
        packed |= max(0, min(15, round((value + 1) * 7.5))) << shift
    return signed(packed, 32)


def _replace_halo2(scenario, sets):
    # H2 stores source placements in 8-unit octree leaves, grouped by shader.
    # Runtime vertex caches are rebuilt by Sapien's decorator_rebuild_all.
    definitions = {}
    metadata = {}
    for record in sets:
        key = record.definition.replace('\\', '/').casefold()
        set_index = definitions.setdefault(key, len(definitions))
        with TagDocument(record.definition, tags_root=scenario.tags_root, game='halo2', must_exist=True) as tag:
            classes = tag.block(tag.tag.root(), 'classes')
            for p in record.placements:
                if not 0 <= p.type_index < min(8, len(classes)):
                    raise ValueError('Invalid Halo 2 decorator class')
                row = classes[p.type_index]
                permutations = tag.block(row, 'permutations')
                if not 0 <= p.permutation_index < min(64, len(permutations)):
                    raise ValueError('Invalid Halo 2 decorator permutation')
                permutation = permutations[p.permutation_index]
                bounds = tag.value(permutation, 'scale')
                if bounds.upper > bounds.lower and not bounds.lower <= p.scale <= bounds.upper:
                    raise ValueError(f'{record.definition}: scale is outside the selected permutation bounds')
                kind = tag.required_field(row, 'type').options().current
                shader = int(tag.value(permutation, 'shader'))
                metadata[set_index, p.type_index, p.permutation_index] = (kind, shader, (float(bounds.lower), float(bounds.upper)))
    if len(definitions) > 32:
        raise ValueError('Halo 2 supports at most 32 decorator sets')
    points = [p.position for record in sets for p in record.placements]
    minimum = tuple(floor(min(p[a] for p in points) / 8) for a in range(3)) if points else (0, 0, 0)
    maximum = tuple(floor(max(p[a] for p in points) / 8) for a in range(3)) if points else (0, 0, 0)
    depth = (max(maximum[a] - minimum[a] for a in range(3))).bit_length()
    if depth > 28:
        raise ValueError('Halo 2 decorators exceed the supported world range')
    cell_count = 1 << depth
    grouped = defaultdict(list)
    paths = {()}
    for record in sets:
        set_index = definitions[record.definition.replace('\\', '/').casefold()]
        for p in record.placements:
            cell = tuple(floor(v / 8) for v in p.position)
            indices = tuple(cell[a] - minimum[a] for a in range(3))
            path = tuple(sum(((indices[a] >> bit) & 1) << (2-a) for a in range(3)) for bit in reversed(range(depth)))
            paths.update(path[:length] for length in range(depth + 1))
            kind, shader, bounds = metadata[set_index, p.type_index, p.permutation_index]
            quant = [max(0, min(1023, round((p.position[a] / 8 - cell[a]) * 1023))) for a in range(3)]
            position = signed(quant[0] | quant[1] << 10 | quant[2] << 22, 32)
            tint = [max(0, min(255, round(c * 255))) for c in p.tint]
            color = tint[0] << 16 | tint[1] << 8 | tint[2]
            grouped[path, set_index, kind, shader, p.cluster_index].append((_packed_rotation(p, bounds), position, color))
    paths = sorted(paths, key=lambda path: (len(path), path))
    if len(paths) > 32767:
        raise ValueError('Too many Halo 2 decorator octree cells')
    plans = [(key, values[start:start+32767]) for key, values in sorted(grouped.items())
             for start in range(0, len(values), 32767)]
    if len(plans) > 4096:
        raise ValueError('Too many Halo 2 decorator cache groups')
    root = scenario.tag.root()
    scenario.block(root, 'decorators').clear()
    scenario.block(root, 'decorator palette').clear()
    for key in definitions:
        block = scenario.block(root, 'decorator palette')
        index = block.add()
        original = next(record.definition for record in sets if record.definition.replace('\\', '/').casefold() == key)
        scenario.set_reference(scenario.block(root, 'decorator palette')[index], 'decorator set', original)
    scenario.block(root, 'decorators').add()
    def definition():
        return scenario.block(root, 'decorators')[0]
    origin = scenario.required_field(definition(), 'grid origin')
    origin.set(type(origin.value)(*((minimum[a] + cell_count/2) * 8 for a in range(3))))
    scenario._set_value(definition(), 'cell count per dimension', cell_count)
    def add(block_name, values, parent=None):
        parent = definition() if parent is None else parent
        block = scenario.block(parent, block_name)
        index = block.add()
        row = scenario.block(parent, block_name)[index]
        for name, value in values.items():
            field = scenario.required_field(row, name)
            field.set(type(field.value)(value) if name.endswith('color') and not isinstance(field.value, int) else value)
        return index
    path_indices = {path: index for index, path in enumerate(paths)}
    group_indices = defaultdict(list)
    for key, values in plans:
        path, set_index, kind, shader, cluster = key
        cache = add('cache blocks', {})
        cache_row = scenario.block(definition(), 'cache blocks')[cache]
        data_index = add('cache block data', {}, cache_row)
        for internal, position, color in values:
            data = scenario.block(scenario.block(definition(), 'cache blocks')[cache], 'cache block data')[data_index]
            add('placements', {'internal data 1': internal, 'compressed position': position,
                'tint color': color, 'lightmap color': 0xffffff,
                'compressed light direction': 0, 'compressed light 2 direction': 0}, data)
        group_index = add('groups', {'decorator set': set_index, 'decorator_type': kind,
            'shader index': shader, 'cluster': cluster, 'cache block': cache,
            'decorator start index': 0, 'decorator count': len(values)})
        group_indices[path].append(group_index)
    for path in paths:
        groups = group_indices[path]
        index = add('cells', {'cache block index': -1, 'group count': len(groups),
                             'group start index': groups[0] if groups else 0})
        children = scenario.required_field(scenario.block(definition(), 'cells')[index], 'child indices').as_array()
        for octant in range(8):
            scenario.required_field(children[octant], 'child index').set(path_indices.get(path + (octant,), -1))
    scenario.tag_has_changes = True

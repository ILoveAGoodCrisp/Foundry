"""Halo 1 detail-object placements in scenario palettes and packed BSP cells.

The MCC Sapien encoder stores unsigned XY coordinates over 255 steps in an
8-unit cell. Z is relative to a per-layer fitted plane and residual range:
8 * (cell_z + offset_z/255 + i*x/255 + j*y/255 + l + k*z/255).
The instance data byte holds a type in its high nibble and a sprite in its low
nibble; lighting is RGB565. Authoring uses a flat reference plane per layer.
"""
from collections import defaultdict
from contextlib import ExitStack
from dataclasses import dataclass
from math import floor, isfinite
from pathlib import Path

from .backend import TagDocument


@dataclass(frozen=True)
class DetailObjectPlacement:
    definition: str
    position: tuple[float, float, float]
    type_index: int
    sprite_index: int
    color: int
    bsp_index: int


@dataclass(frozen=True)
class DetailObjectSprite:
    type_index: int
    type_name: str
    sprite_index: int
    bitmap: str
    bitmap_index: int
    uv_bounds: tuple[float, float, float, float]
    width: float
    height: float
    z_offset: float


def read_detail_object_sprites(collection, single_type=None, sprite_index=None):
    """Resolve loose-tag sequences, not the cache-only first/count fields.

    Detail-object size is world units per pixel. Unlike particles, these
    sprites rest on their bottom edge; the bitmap registration point is not
    their ground anchor. Placement tint already includes the type's lighting.
    """
    root = collection.tag.root()
    plate = collection.reference(root, 'sprite plate')
    if plate is None:
        return []
    result = []
    with TagDocument(plate, tags_root=collection.tags_root, game='halo1', must_exist=True) as bitmap:
        sequences = bitmap.block(bitmap.tag.root(), 'sequences')
        pages = bitmap.block(bitmap.tag.root(), 'bitmaps')
        for type_index, row in enumerate(collection.block(root, 'types')):
            name = str(collection.value(row, 'name')) or str(type_index)
            if single_type is not None and name.casefold() != single_type.casefold():
                continue
            sequence_index = int(collection.value(row, 'sequence index')) & 255
            if sequence_index >= len(sequences):
                raise ValueError(f'{collection.path}: detail type {name!r} has invalid sequence {sequence_index}')
            sprites = bitmap.block(sequences[sequence_index], 'sprites')
            if sprite_index is not None and not 0 <= sprite_index < len(sprites):
                raise ValueError(f'{collection.path}: detail type {name!r} has no sprite {sprite_index}')
            size = float(collection.value(row, 'size'))
            z_offset = float(collection.value(root, 'global z offset'))
            for index, sprite in enumerate(sprites):
                if sprite_index is not None and index != sprite_index:
                    continue
                page_index = int(bitmap.value(sprite, 'bitmap index'))
                if not 0 <= page_index < len(pages):
                    raise ValueError(f'{plate.RelativePathWithExtension}: invalid sprite bitmap {page_index}')
                left, right, top, bottom = (float(bitmap.value(sprite, key))
                                            for key in ('left', 'right', 'top', 'bottom'))
                width = (right - left) * int(bitmap.value(pages[page_index], 'width')) * size
                height = (bottom - top) * int(bitmap.value(pages[page_index], 'height')) * size
                if not all(isfinite(v) for v in (left, right, top, bottom, width, height, z_offset)) or width <= 0 or height <= 0:
                    raise ValueError(f'{collection.path}: detail type {name!r} has invalid sprite dimensions')
                result.append(DetailObjectSprite(type_index, name, index, plate.RelativePathWithExtension,
                    page_index, (left, right, top, bottom), width, height, z_offset))
    return result


def signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def decode_position(cell, instance, reference):
    cx, cy, cz, offset = cell
    x, y, z = (v & 255 for v in instance)
    i, j, k, l = reference
    return ((cx + x / 255) * 8, (cy + y / 255) * 8,
            (cz + offset / 255 + i * x / 255 + j * y / 255 + l + k * z / 255) * 8)


def read_detail_objects(scenario):
    palette = [scenario.reference(row, 'reference') for row in
               scenario.block(scenario.tag.root(), 'detail object collection palette')]
    placements = []
    for bsp_index, row in enumerate(scenario.block(scenario.tag.root(), 'structure bsps')):
        bsp_ref = scenario.reference(row, 'structure bsp')
        if bsp_ref is None:
            continue
        with TagDocument(bsp_ref, tags_root=scenario.tags_root, game='halo1', must_exist=True) as bsp:
            details = bsp.block(bsp.tag.root(), 'detail objects')
            if not len(details):
                continue
            data = details[0]
            counts = bsp.block(data, 'counts')
            instances = bsp.block(data, 'instances')
            references = bsp.block(data, 'z reference vectors')
            for cell in bsp.block(data, 'cells'):
                start = int(bsp.value(cell, 'start index'))
                count_index = int(bsp.value(cell, 'count index'))
                flags = int(bsp.value(cell, 'valid layers flags')) & 0xffffffff
                coords = tuple(int(bsp.value(cell, name)) for name in ('cell x', 'cell y', 'cell z', 'offset z'))
                for layer in range(32):
                    if not flags & (1 << layer):
                        continue
                    if not 0 <= count_index < min(len(counts), len(references)):
                        raise ValueError(f'{bsp.path}: invalid detail-object count index')
                    count = int(bsp.value(counts[count_index], 'count')) & 0xffff
                    if not 0 <= start <= start + count <= len(instances):
                        raise ValueError(f'{bsp.path}: invalid detail-object instance range')
                    z = tuple(float(bsp.value(references[count_index], 'z reference ' + c)) for c in 'ijkl')
                    definition = palette[layer] if layer < len(palette) else None
                    for index in range(start, start + count):
                        instance = instances[index]
                        if definition is None:
                            continue
                        point = tuple(int(bsp.value(instance, 'position ' + c)) for c in 'xyz')
                        data_byte = int(bsp.value(instance, 'data')) & 255
                        placements.append(DetailObjectPlacement(definition.RelativePathWithExtension,
                            decode_position(coords, point, z), data_byte >> 4, data_byte & 15,
                            int(bsp.value(instance, 'color')) & 0xffff, bsp_index))
                    start += count
                    count_index += 1
    return placements


def replace_detail_objects(scenario, placements, bsp_indices=None):
    """Validate all placements before replacing any BSP detail-object block."""
    placements = list(placements)
    root = scenario.tag.root()
    bsp_refs = [scenario.reference(row, 'structure bsp') for row in scenario.block(root, 'structure bsps')]
    selected = set(range(len(bsp_refs))) if bsp_indices is None else set(bsp_indices)
    if not selected <= set(range(len(bsp_refs))):
        raise ValueError('Invalid detail-object BSP index')
    palette = scenario.block(root, 'detail object collection palette')
    definitions = [scenario.reference(row, 'reference') for row in palette]
    indices = {ref.RelativePathWithExtension.replace('\\', '/').casefold(): i for i, ref in enumerate(definitions) if ref is not None}
    additions = []
    groups = defaultdict(lambda: defaultdict(list))
    for placement in placements:
        path = placement.definition.replace('\\', '/')
        if (Path(path).is_absolute() or '..' in Path(path).parts or
                not path.lower().endswith('.detail_object_collection') or not (scenario.tags_root / path).is_file()):
            raise ValueError(f'Invalid detail object collection: {placement.definition}')
        if placement.bsp_index not in selected:
            raise ValueError('Detail object belongs to a BSP outside this export')
        if not 0 <= placement.type_index < 16 or not 0 <= placement.sprite_index < 16:
            raise ValueError('Halo 1 detail object types and sprites must fit in four bits')
        if not all(isfinite(v) for v in placement.position):
            raise ValueError('Invalid detail object position')
        key = path.casefold()
        if key not in indices:
            indices[key] = len(definitions) + len(additions)
            additions.append(path)
        layer = indices[key]
        if layer >= 32:
            raise ValueError('Halo 1 supports at most 32 detail object collections')
        cell = [floor(v / 8) for v in placement.position]
        xy = [round((placement.position[i] / 8 - cell[i]) * 255) for i in range(2)]
        for axis in range(2):
            if xy[axis] == 255:
                cell[axis] += 1
                xy[axis] = 0
        if any(not -32768 <= v <= 32767 for v in cell):
            raise ValueError('Detail object is outside the supported cell range')
        groups[placement.bsp_index][tuple(cell), layer].append((placement, *xy))
    cell_layers = defaultdict(lambda: defaultdict(dict))
    for bsp_index, layers in groups.items():
        for (cell, layer), rows in layers.items():
            cell_layers[bsp_index][cell][layer] = rows
    for bsp_index in selected:
        if bsp_refs[bsp_index] is None or not scenario.path_exists(bsp_refs[bsp_index]):
            raise ValueError('Detail object export requires an existing structure BSP')
        cells = {cell for cell, layer in groups[bsp_index]}
        if len(cells) > 262144 or sum(len(rows) for rows in groups[bsp_index].values()) > 2097152:
            raise ValueError('Too many Halo 1 detail-object cells or placements')
        if any(sum(len(rows) for rows in layers.values()) > 4000 for layers in cell_layers[bsp_index].values()):
            raise ValueError('Halo 1 supports at most 4000 detail objects in a cell')
    # Keep existing palette indices stable for BSPs outside a partial export.
    for path in additions:
        palette = scenario.block(root, 'detail object collection palette')
        index = palette.add()
        palette = scenario.block(root, 'detail object collection palette')
        scenario.set_reference(palette[index], 'reference', path)
    with ExitStack() as stack:
        bsps = {index: stack.enter_context(TagDocument(bsp_refs[index], tags_root=scenario.tags_root,
            game='halo1', must_exist=True)) for index in sorted(selected)}
        for bsp_index, bsp in bsps.items():
            details = bsp.block(bsp.tag.root(), 'detail objects')
            if not len(details):
                details.add()
            for block in ('cells', 'instances', 'counts', 'z reference vectors'):
                bsp.block(bsp.block(bsp.tag.root(), 'detail objects')[0], block).clear()
            def add(block, values):
                block_handle = bsp.block(bsp.block(bsp.tag.root(), 'detail objects')[0], block)
                index = block_handle.add()
                row = bsp.block(bsp.block(bsp.tag.root(), 'detail objects')[0], block)[index]
                for name, value in values.items():
                    bsp.required_field(row, name).set(value)
                return index
            cursor = count_cursor = 0
            for cell, rows_by_layer in sorted(cell_layers[bsp_index].items()):
                layers = sorted(rows_by_layer)
                add('cells', dict(zip(('cell x', 'cell y', 'cell z'), cell)) | {
                    'offset z': 0, 'valid layers flags': signed(sum(1 << layer for layer in layers), 32),
                    'start index': cursor, 'count index': count_cursor})
                for layer in layers:
                    rows = rows_by_layer[layer]
                    lower = min(row[0].position[2] for row in rows)
                    upper = max(row[0].position[2] for row in rows)
                    add('counts', {'count': len(rows)})
                    add('z reference vectors', {'z reference i': 0., 'z reference j': 0.,
                        'z reference k': (upper - lower) / 8, 'z reference l': lower / 8 - cell[2]})
                    for placement, x, y in rows:
                        z = round((placement.position[2] - lower) * 255 / (upper - lower)) if upper > lower else 0
                        add('instances', {'position x': signed(x, 8), 'position y': signed(y, 8),
                            'position z': signed(z, 8), 'data': signed(placement.type_index << 4 | placement.sprite_index, 8),
                            'color': signed(placement.color, 16)})
                    cursor += len(rows)
                    count_cursor += 1
            bsp.tag_has_changes = True

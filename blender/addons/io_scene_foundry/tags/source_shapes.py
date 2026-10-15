"""Optional Halo 4 authoring identities retained in compiled render geometry.

Keep full keys: key1 is not a position or a source vertex array index. Names
are keyed by key2, including namespaces. Missing/ambiguous identities stay on
the ordinary import path, independently of other meshes in the same tag.
"""
from dataclasses import replace


def attach_source_shapes(records, geometry, game):
    if game != 'halo4':
        return records
    field = geometry.field('shapeNames')
    names_block = None if field is None else field.as_block()
    if not names_block:
        return records
    names = {}
    ambiguous = set()
    for entry in names_block:
        key, name = int(entry.field('key').value), str(entry.field('name').value)
        if key in names and names[key] != name:
            ambiguous.add(key)
        names[key] = name
    names = tuple((key, name) for key, name in names.items() if name and key not in ambiguous)
    if not names:
        return records
    known_keys = {key for key, name in names}
    meshes = geometry.field('meshes').as_block()
    result = []
    for record in records:
        field = meshes[record.index].field('vertex keys')
        keys_block = None if field is None else field.as_block()
        if not keys_block or len(keys_block) != len(record.positions):
            result.append(record)
            continue
        keys = tuple((int(e.field('key1').value), int(e.field('key2').value)) for e in keys_block)
        if any(key2 in known_keys for key1, key2 in keys):
            result.append(replace(record, source_shape_names=names, source_vertex_keys=keys))
        else:
            result.append(record)
    return result

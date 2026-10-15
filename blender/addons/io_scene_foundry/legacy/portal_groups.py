"""Editable portal group indices for the Halo 2/3 ASS pipeline."""
import re


def portal_material_name(name):
    """Strip flag suffixes, keeping the authored portal material identity."""
    match = re.match(r'^\+portal\w*', name, re.IGNORECASE)
    return match[0].casefold() if match else None


def indexed_portal_name(index):
    return '+portal' if index == 0 else f'+portal{index}'


def portal_material_indices(names, reserved=()):
    """Keep canonical numeric names; give other identities unused indices.

    +portal_door is just a material identity, not a door flag. Likewise,
    +portal0 and +portal02 must not collapse into +portal and +portal2.
    """
    names = dict.fromkeys(portal_material_name(value) or value.casefold() for value in names)
    indices = {}
    used = set(reserved)
    for name in names:
        suffix = name[len('+portal'):] if name.startswith('+portal') else ''
        if name == '+portal':
            indices[name] = 0
        elif suffix.isascii() and suffix.isdecimal() and suffix == str(int(suffix)) and int(suffix) > 0:
            indices[name] = int(suffix)
    used.update(indices.values())
    candidate = 1
    for name in names:
        if name in indices:
            continue
        while candidate in used:
            candidate += 1
        indices[name] = candidate
        used.add(candidate)
    return indices


def allocate_portal_materials(records):
    """Resolve (key, index, shader names) using only the object's Portal Index.

    Index -1 allocates a distinct group per object, avoiding explicit indices.
    Every material on an object uses the same index, regardless of its name.
    """
    records = list(records)
    used = {index for _, index, _ in records if index >= 0}
    result = {}
    candidate = 1
    for key, index, names in records:
        if index < 0:
            while candidate in used:
                candidate += 1
            index = candidate
            used.add(index)
        result[key] = dict.fromkeys(names, indexed_portal_name(index))
    return result

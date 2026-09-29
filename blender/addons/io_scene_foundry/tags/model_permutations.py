"""Select collision and physics permutations independently of render geometry."""


def select_model_records(records, selection):
    """Keep matching permutations, falling back to each region's default.

    Render and collision/physics tags need not use the same permutation names.
    Prefer an explicitly named default, or the first available permutation when
    the tag uses a different name (for example Halo 1's ``base00``).
    """
    if not selection or selection == 'all_permutations':
        return records

    requested = {}
    if not isinstance(selection, str):
        for region, permutation in selection:
            requested.setdefault(region, set()).add(permutation)

    available = {}
    for record in records:
        available.setdefault(record.region, {}).setdefault(record.permutation, None)

    allowed = set()
    for region, permutations in available.items():
        names = {selection} if isinstance(selection, str) else requested.get(region, set())
        matches = names.intersection(permutations)
        default = 'default' if 'default' in permutations else next(iter(permutations))
        allowed.update((region, name) for name in (matches or {default}))

    return [record for record in records if (record.region, record.permutation) in allowed]

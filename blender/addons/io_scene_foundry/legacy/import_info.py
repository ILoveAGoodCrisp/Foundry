"""Select the export hierarchy retained in embedded authoring sources."""

BSP_TAG_KINDS = frozenset({'scenario_structure_bsp', 'structure_design', 'prefab'})
MODEL_TAG_KINDS = frozenset({'render_model', 'collision_model', 'physics_model',
                           'model', 'gbxmodel', 'sky', 'particle_model', 'decorator_set'})
FRAME_PREFIXES = ('frame_', 'frame ', 'bip_', 'bip ', 'b_', 'b ')


def bsp_shader_paths(document):
    """Include collision-only shaders absent from the BSP's render materials."""
    field_name = 'shader' if document.game == 'halo2' else 'render method'
    paths = {}
    for block_name in ('materials', 'collision materials'):
        for element in document.block(document.tag.root(), block_name):
            if document.game == 'halo2' and block_name == 'collision materials':
                reference = (document.reference(element, 'new shader')
                             or document.reference(element, 'old shader'))
            else:
                reference = document.reference(element, field_name)
            if reference is None:
                continue
            name = reference.ShortName.casefold()
            path = reference.RelativePathWithExtension
            paths[name] = path if paths.get(name, path) == path else ''
    return paths


def bsp_game_object_paths(document):
    """Retain ASS BSP reference types even when their target tags are absent."""
    if document.game not in {'halo2', 'halo3', 'halo3odst'}:
        return ()
    return tuple(reference.RelativePathWithExtension
                 for element in document.block(document.tag.root(), 'environment object palette')
                 if (reference := document.reference(element, 'definition')) is not None)


def main_frame_scope(names, parents, order, identifiers=None):
    """Return the main frame's descendants, excluding scene wrappers and guides.

    ASS exporters can add several sentinel frames above the actual export frame.
    Their transforms still contribute to world matrices, but their other children
    are outside the asset. Files without an authored frame use their first root.
    """
    frames = {i for i in order if names[i].casefold() == 'frame'
              or names[i].casefold().startswith(FRAME_PREFIXES)}
    authored = frames if identifiers is None else {i for i in frames if identifiers[i] != -1}
    candidates = authored or frames
    has_frame_ancestor = {}
    roots = []
    for i in order:
        parent = parents[i]
        has_frame_ancestor[i] = parent in candidates or has_frame_ancestor.get(parent, False)
        if i in candidates and not has_frame_ancestor[i]:
            roots.append(i)
    if not roots:
        roots = [i for i in order if parents[i] == -1]
    if not roots:
        return None
    root = roots[0]
    included = set()
    for i in order:
        if i == root or parents[i] in included:
            included.add(i)
    return included

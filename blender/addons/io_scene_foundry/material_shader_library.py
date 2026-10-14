"""H4/H2AMP resource identities shared by import, export and the shader picker.

Keep this module independent of add-on registration and native tag readers.
"""
from pathlib import Path
import re

MATERIAL_LIBRARIES = {'halo4': 'h4_nodes', 'halo2a': 'h2amp_nodes'}
LONG_NAMES = (
    'srf_pbr_ca_terrain_macrocolor_vertalpha_clip_paintrough_on_alpha',
    'srf_pbr_ca_terrain_macrocolor_vertalpha_clip_paintrough_on_alpha_blend',
)
# These source files have different implementations despite sharing a basename.
PATH_GROUPS = {
    'special/srf_constant_meter': 'srf_constant_meter [special]',
    'special/srf_energy_sword': 'srf_energy_sword [H2AMP]',
}
LEGACY_NAMES = {
    'srf_ca_blinn_diffspec_reflection_clip': 'srf_ca_blinn_diffspec_clip_reflection',
    **{name[8:]: name for name in LONG_NAMES},
}
COLLIDING_NAMES = {'srf_constant_meter', 'srf_energy_sword'}


def parameter_key(name):
    return re.sub(r'[\s_\-()\'\"]', '', name).casefold()


def shader_key(path):
    """Canonical source path relative to materials/, retaining special/ etc."""
    name = str(path).replace('\\', '/').strip('/').casefold()
    name = name.removesuffix('.material_shader').removesuffix('.fx')
    marker = 'shaders/material_shaders/'
    if marker in name:
        name = name.partition(marker)[2]
    return name.removeprefix('materials/')


def group_name(shader_path):
    key = shader_key(shader_path)
    if key in PATH_GROUPS:
        return PATH_GROUPS[key]
    name = key.rsplit('/', 1)[-1]
    return name[8:] if name in LONG_NAMES else LEGACY_NAMES.get(name, name)


def source_shader(group):
    """Reverse resource aliases, including local Blender duplicate suffixes."""
    if not isinstance(group, str):
        source = group.get('foundry_material_shader')
        if source:
            return source
        name = group.get('foundry_resource_name', group.name)
    else:
        name = group
    name = re.sub(r'\.\d{3,}$', '', name)
    reverse = {value.casefold(): key for key, value in PATH_GROUPS.items()}
    return reverse.get(name.casefold(), LEGACY_NAMES.get(name.casefold(), name.casefold()))


def resolve_group_name(available, shader_path, *, fallback=False):
    """Resolve a resource name without confusing root and special variants."""
    names = {name.casefold(): name for name in available}
    requested = str(shader_path).casefold()
    if requested in names:
        return names[requested]
    key = shader_key(shader_path)
    name = group_name(shader_path)
    if name.casefold() in names:
        return names[name.casefold()]
    if fallback and key.rsplit('/', 1)[-1] not in COLLIDING_NAMES:
        while len(name) >= 7:
            name = name[:-1]
            if name.casefold() in names:
                return names[name.casefold()]
    return None


def find_shader_tag(tags_dir, source):
    """Prefer the full source path; never guess between same-basename shaders."""
    root = Path(tags_dir)
    source_path = str(source).replace('\\', '/')
    direct = root / (source_path if source_path.endswith('.material_shader') else source_path + '.material_shader')
    if direct.is_file() and direct.resolve().is_relative_to(root.resolve()):
        return str(direct.relative_to(root))
    key = shader_key(source)
    basename = key.rsplit('/', 1)[-1]
    candidates = [p for p in (root / 'shaders').rglob('*.material_shader')
                  if p.stem.casefold() == basename]
    exact = [p for p in candidates if shader_key(p.relative_to(root)) == key]
    if len(exact) == 1:
        return str(exact[0].relative_to(root))
    if not exact and len(candidates) == 1 and basename not in COLLIDING_NAMES:
        return str(candidates[0].relative_to(root))
    return ''


def load_group(library, shader_path, *, link=False, fallback=False):
    """Use the loaded datablock, scoped to its game, instead of a global name."""
    import bpy
    library = Path(library)
    game = next(game for game, name in MATERIAL_LIBRARIES.items() if name == library.stem)

    def cached(names):
        for group in bpy.data.node_groups:
            if (group.get('foundry_material_game') == game
                    and not group.get('foundry_source_instance')
                    and group.get('foundry_resource_name', '').casefold() in names):
                if group.library and Path(bpy.path.abspath(group.library.filepath)).resolve() != library.resolve():
                    continue
                return group
        return None

    existing = cached({str(shader_path).casefold(), group_name(shader_path).casefold()})
    if existing is not None:
        return existing
    with bpy.data.libraries.load(str(library), link=link) as (source, destination):
        name = resolve_group_name(source.node_groups, shader_path, fallback=fallback)
        if name is None:
            return None
        existing = cached({name.casefold()})
        if existing is not None:
            return existing
        destination.node_groups = [name]
    # Appended groups can be renamed by Blender when another game is loaded.
    return destination.node_groups[0]

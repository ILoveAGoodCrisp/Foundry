"""Sync Foundry material emission with Halo 1 and Halo 2 shader tags."""

from pathlib import Path
from filecmp import cmp
from shutil import copy2

from blam_tags import RealRgbColor

from .backend import TagDocument, read_only_tags


HALO1_EMISSIVE_SHADER_EXTENSIONS = frozenset({
    '.shader_environment', '.shader_model', '.shader_transparent_generic',
    '.shader_transparent_chicago', '.shader_transparent_chicago_extended',
    '.shader_transparent_glass', '.shader_transparent_meter',
    '.shader_transparent_plasma', '.shader_transparent_water',
})


def asset_shader_folder(sidecar_path: str | Path, data_root: str | Path,
                        tags_root: str | Path) -> Path:
    """Resolve the current asset's shader folder only after setup is complete."""
    data_root = Path(data_root).resolve()
    tags_root = Path(tags_root).resolve()
    marker = (data_root / sidecar_path).resolve()
    if (not marker.is_relative_to(data_root) or not marker.is_file() or
            not marker.name.endswith('.sidecar.xml') or marker.parent == data_root):
        raise ValueError('Set up the asset before updating shader emission')
    expected = tags_root / marker.parent.relative_to(data_root) / 'shaders'
    folder = expected.resolve()
    if not folder.is_relative_to(tags_root) or folder != expected:
        raise ValueError('The asset shader folder redirects outside this asset')
    return folder


def localize_shader_environment(source: Path, folder: Path,
                                tags_root: str | Path, game='halo1') -> tuple[Path, bool]:
    """Copy a shader into the asset without replacing a different local tag."""
    tags_root = Path(tags_root).resolve()
    source = shader_environment_path(source, tags_root, game)
    folder = folder.resolve()
    if not folder.is_relative_to(tags_root):
        raise ValueError('The asset shader folder is outside the tags directory')
    if source.parent == folder:
        return source, False

    destination = folder / source.name
    index = 1
    while destination.exists():
        if destination.resolve().parent != folder:
            raise ValueError(f'Asset shader path redirects outside its folder: {destination}')
        if cmp(source, destination, shallow=False):
            break
        destination = folder / f'{source.stem}_{index:02d}{source.suffix}'
        index += 1
    folder.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        copy2(source, destination)
        return destination, True
    return destination, False


def shader_environment_path(tag_path: str | Path, tags_root: str | Path, game='halo1') -> Path:
    root = Path(tags_root).resolve()
    path = (root / tag_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Shader path is outside the tags directory: {tag_path}')
    extensions = HALO1_EMISSIVE_SHADER_EXTENSIONS if game == 'halo1' else {'.shader'}
    if path.suffix.lower() not in extensions:
        raise ValueError(f'Expected a {game} shader tag with emission properties: {tag_path}')
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _emissive_fields(shader, create=False):
    root = shader.tag.root()
    if shader.game == 'halo1':
        radiosity = shader.required_field(root, 'radiosity').as_struct()
        return [(shader.required_field(radiosity, 'power'),
                 shader.required_field(radiosity, 'color of emitted light'))]

    block = shader.block(root, 'parameters')
    parameters = {str(shader.value(item, 'name')): item for item in block}
    names = ('lightmap_emissive_power', 'lightmap_emissive_color')
    if create:
        for name, kind in zip(names, (1, 2)):
            if name not in parameters:
                item = block[block.add()]
                shader.required_field(item, 'name').set(name)
                shader.required_field(item, 'type').set(kind)
                parameters[name] = item
                shader.tag_has_changes = True
        parameters = {str(shader.value(item, 'name')): item for item in block}
    pairs = []
    if all(name in parameters for name in names):
        pairs.append((shader.required_field(parameters[names[0]], 'const value'),
                      shader.required_field(parameters[names[1]], 'const color')))
    # Keep existing compiled properties in sync without inventing an otherwise
    # empty runtime record. Tool compiles authored parameters when needed.
    for item in shader.block(root, 'runtime properties'):
        pairs.append((shader.required_field(item, 'lightmap emissive power'),
                      shader.required_field(item, 'lightmap emissive color')))
    return pairs


@read_only_tags()
def read_material_emissive(tag_path, tags_root, game='halo1'):
    path = shader_environment_path(tag_path, tags_root, game)
    with TagDocument(path, tags_root=tags_root, game=game, must_exist=True) as shader:
        pairs = _emissive_fields(shader)
        if not pairs:
            return 0.0, (1.0, 1.0, 1.0)
        power, color = pairs[0]
        color = color.value
        return float(power.value), tuple(max(0.0, float(v)) ** 2.2
                                         for v in (color.red, color.green, color.blue))


def _matches(pair, power, color):
    old_color = pair[1].value
    return (abs(float(pair[0].value) - power) <= 1e-5 and
            all(abs(float(current) - wanted) <= 1e-5 for current, wanted in
                zip((old_color.red, old_color.green, old_color.blue), color)))


def write_material_emissive(tag_path: str | Path, tags_root: str | Path,
                            power: float, linear_color, game='halo1') -> bool:
    """Write base shader power/color. Surface power scale is exported separately."""
    path = shader_environment_path(tag_path, tags_root, game)
    power = float(power)
    if power < 0:
        raise ValueError('Emissive power cannot be negative')
    color = tuple(max(0.0, min(1.0, float(v))) ** (1 / 2.2) for v in linear_color[:3])
    if len(color) != 3:
        raise ValueError('Emissive color needs three channels')
    with TagDocument(path, tags_root=tags_root, game=game, must_exist=True) as shader:
        pairs = _emissive_fields(shader, create=True)
        for pair in pairs:
            if not _matches(pair, power, color):
                pair[0].set(power)
                pair[1].set(RealRgbColor(*color))
                shader.tag_has_changes = True
        changed = shader.tag_has_changes
    return changed

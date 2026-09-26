"""Sync a Foundry material's emission with its Halo 1 environment shader."""

from pathlib import Path

from blam_tags import RealRgbColor

from .backend import TagDocument


def shader_environment_path(tag_path: str | Path, tags_root: str | Path) -> Path:
    root = Path(tags_root).resolve()
    path = (root / tag_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f'Shader path is outside the tags directory: {tag_path}')
    if path.suffix.lower() != '.shader_environment':
        raise ValueError(f'Expected a Halo 1 shader_environment tag: {tag_path}')
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def write_material_emissive(tag_path: str | Path, tags_root: str | Path,
                            power: float, linear_color) -> bool:
    """Write changed radiosity values only; return whether the tag changed."""
    path = shader_environment_path(tag_path, tags_root)
    power = float(power)
    if power < 0:
        raise ValueError('Emissive power cannot be negative')
    color = tuple(max(0.0, min(1.0, float(value))) ** (1 / 2.2)
                  for value in linear_color[:3])
    if len(color) != 3:
        raise ValueError('Emissive color needs three channels')

    with TagDocument(path, tags_root=tags_root, game='halo1', must_exist=True) as shader:
        radiosity = shader.required_field(shader.tag.root(), 'radiosity').as_struct()
        if radiosity is None:
            raise ValueError(f'{path}: shader has no radiosity struct')
        power_field = shader.required_field(radiosity, 'power')
        color_field = shader.required_field(radiosity, 'color of emitted light')
        old_color = color_field.value
        changed = (abs(float(power_field.value) - power) > 1e-5 or
                   any(abs(float(current) - wanted) > 1e-5 for current, wanted in
                       zip((old_color.red, old_color.green, old_color.blue), color)))
        if changed:
            power_field.set(power)
            color_field.set(RealRgbColor(*color))
            shader.tag_has_changes = True
    return changed


def material_emissive_matches(tag_path: str | Path, tags_root: str | Path,
                              power: float, linear_color) -> bool:
    """Check whether a protected shader already has the material's values."""
    path = shader_environment_path(tag_path, tags_root)
    color = tuple(max(0.0, min(1.0, float(value))) ** (1 / 2.2)
                  for value in linear_color[:3])
    with TagDocument(path, tags_root=tags_root, game='halo1', must_exist=True) as shader:
        radiosity = shader.required_field(shader.tag.root(), 'radiosity').as_struct()
        if radiosity is None:
            raise ValueError(f'{path}: shader has no radiosity struct')
        old_color = shader.value(radiosity, 'color of emitted light')
        return (abs(float(shader.value(radiosity, 'power')) - float(power)) <= 1e-5 and
                all(abs(float(current) - wanted) <= 1e-5 for current, wanted in
                    zip((old_color.red, old_color.green, old_color.blue), color)))

"""Preserve selected H1 shader paths across Tool's basename-only lookup."""
from contextlib import contextmanager
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

from blam_tags import RealRgbColor

from .backend import TagDocument


INVALID_SHADER_PATH = Path('shaders/invalid.shader_environment')


def ensure_invalid_shader(tags_root):
    """Use one grey environment shader for both BSP and model fallbacks."""
    path = Path(tags_root) / INVALID_SHADER_PATH
    if not path.is_file():
        with TagDocument(path, tags_root=tags_root, game='halo1') as shader:
            diffuse = shader.required_field(shader.tag.root(), 'diffuse').as_struct()
            channel = 80 / 255
            shader.required_field(diffuse, 'material color').set(
                RealRgbColor(channel, channel, channel))
            shader.tag_has_changes = True
    return path


@contextmanager
def shader_import_paths(tags_root, expected):
    """Provide aliases only for names that cannot select an original tag.

    Distinct JMS names prevent Tool from merging different shaders sharing a
    basename. Aliases live until their compiled references have been repaired.
    """
    tags_root = Path(tags_root).resolve()
    aliases = [(name, tags_root / path) for name, path in expected.items()
               if name.casefold() != Path(path).stem.casefold()]
    if not aliases:
        yield expected
        return
    folder = tags_root / 'shaders'
    folder.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='foundry_import_', dir=folder) as temporary:
        for name, source in aliases:
            copy2(source, Path(temporary) / (name + source.suffix))
        yield expected


def repair_shader_references(path, tags_root, expected):
    """Check native BSP/model shader references and save only mismatches."""
    changed = 0
    with TagDocument(path, tags_root=tags_root, game='halo1', must_exist=True) as tag:
        root = tag.tag.root()
        if tag.system_path.suffix == '.scenario_structure_bsp':
            records = list(tag.block(root, 'collision materials'))
            for lightmap in tag.block(root, 'lightmaps'):
                records.extend(tag.block(lightmap, 'materials'))
        elif tag.system_path.suffix in {'.model', '.gbxmodel'}:
            records = list(tag.block(root, 'shaders'))
        else:
            raise ValueError(f'Unsupported H1 geometry tag: {path}')
        for record in records:
            reference = tag.reference(record, 'shader')
            # Special BSP materials such as +sky have no shader reference.
            if reference is None:
                continue
            name = reference.ShortName.casefold()
            if name not in expected:
                raise ValueError(f'{path}: cannot identify compiled shader {reference.RelativePathWithExtension}')
            wanted = expected[name]
            current = reference.RelativePathWithExtension.replace('/', '\\').casefold()
            if current != str(wanted).replace('/', '\\').casefold():
                tag.set_reference(record, 'shader', wanted)
                changed += 1
    return changed

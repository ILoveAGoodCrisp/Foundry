"""Preserve selected H1 shader paths across Tool's basename-only lookup."""
from contextlib import contextmanager
from pathlib import Path
from shutil import copy2
from tempfile import TemporaryDirectory

from blam_tags import RealArgbColor, RealRgbColor

from .backend import TagDocument


INVALID_SHADER_PATH = Path('shaders/invalid.shader_transparent_generic')


def ensure_invalid_shader(tags_root):
    """Use a grey, opaque generic shader valid for both BSPs and models."""
    path = Path(tags_root) / INVALID_SHADER_PATH
    if not path.is_file():
        with TagDocument(path, tags_root=tags_root, game='halo1') as shader:
            root = shader.tag.root()
            channel = 80 / 255
            radiosity = shader.required_field(root, 'radiosity').as_struct()
            shader.required_field(radiosity, 'tint color').set(
                RealRgbColor(channel, channel, channel))
            shader.required_field(radiosity, 'flags').set_flag('transparent lit', True)
            properties = shader.required_field(root, 'properties').as_struct()
            shader.required_field(properties, 'framebuffer blend function').set('alpha blend')
            stages = shader.block(root, 'stages')
            stage = stages[stages.add()]
            color = RealArgbColor(1., channel, channel, channel)
            for name in ('color0 animation lower bound', 'color0 animation upper bound'):
                shader.required_field(stage, name).set(color)
            shader.required_field(stage, 'color0 animation function').set('one')
            shader.required_field(stage, 'input a').set('constant color 0')
            shader.required_field(stage, 'input b').set('vertex color 0 diffuse light')
            shader.required_field(stage, 'input a alpha').set('one')
            shader.required_field(stage, 'input b alpha').set('one')
            # Output 1 is scratch register 0, the final color/alpha output.
            shader.required_field(stage, 'output ab').set(1)
            shader.required_field(stage, 'output ab alpha').set(1)
            shader.tag_has_changes = True
    # Retire old shared fallbacks without destroying their saved contents.
    # Their common basename would let Tool select the wrong shader class.
    for extension in ('.shader_environment', '.shader_model'):
        old = path.with_suffix(extension)
        if old.is_file():
            backup = old.with_name(old.name + '.foundry-backup')
            index = 1
            while backup.exists():
                backup = old.with_name(old.name + f'.foundry-backup-{index}')
                index += 1
            old.rename(backup)
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

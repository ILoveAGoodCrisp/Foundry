"""Convert H1's opaque shader classes for the geometry being exported."""
from pathlib import Path

from .backend import TagDocument


SHARED_SHADER_TYPES = frozenset({
    '.shader_transparent_generic', '.shader_transparent_chicago',
    '.shader_transparent_chicago_extended', '.shader_transparent_glass',
    '.shader_transparent_meter', '.shader_transparent_plasma',
    '.shader_transparent_water',
})


def required_shader_type(asset_type):
    """Scenarios preserve shader classes; model-family assets need models."""
    if asset_type in {'model', 'sky', 'animation'}:
        return '.shader_model'
    return None


def shader_path_warning(shader_path, asset_type):
    """Return an asset compatibility warning, independent of tag existence."""
    required = required_shader_type(asset_type)
    if not required or not shader_path.strip():
        return None
    suffix = Path(shader_path.strip().strip('"')).suffix.lower()
    if suffix in SHARED_SHADER_TYPES or suffix == required:
        return None
    if suffix in {'.shader_model', '.shader_environment'}:
        return (f'{suffix} cannot be used for {asset_type} assets\n'
                f'Export will create a {required}')
    return f'Invalid H1 shader type for {asset_type} assets\nUse {required} or a transparent shader'


def convert_shader(path, tags_root, required_type):
    """Create a new tag, keeping the original and any existing destination intact.

    Give the new shader a distinct basename so Tool cannot select the original
    class through its basename-only shader search.
    """
    tags_root = Path(tags_root).resolve()
    source_path = (tags_root / path).resolve()
    if not source_path.is_relative_to(tags_root):
        raise ValueError(f'Shader path is outside the tags directory: {path}')
    suffix = source_path.suffix.lower()
    opaque = {'.shader_model', '.shader_environment'}
    if suffix not in opaque or required_type not in opaque or suffix == required_type:
        return source_path.relative_to(tags_root)
    label = required_type.removeprefix('.shader_')
    stem = f'{source_path.stem}_{label}'
    target_path = source_path.with_name(stem + required_type)
    index = 1
    # Avoid every shader class with this basename, not just our destination type.
    while any(item.stem.casefold() == target_path.stem.casefold()
              and item.suffix.lower().startswith('.shader')
              for item in target_path.parent.iterdir()):
        target_path = source_path.with_name(f'{stem}_{index:02d}{required_type}')
        index += 1

    with TagDocument(source_path, tags_root=tags_root, game='halo1', must_exist=True) as source:
        with TagDocument(target_path, tags_root=tags_root, game='halo1') as target:
            _convert_fields(source, target, suffix == '.shader_model')
    return target_path.relative_to(tags_root)


def _convert_fields(source, target, model_to_environment):
    from blam_tags import RealRgbColor

    src, dst = source.tag.root(), target.tag.root()

    def struct(document, root, name):
        return document.required_field(root, name).as_struct()

    def copy(source_struct, source_name, target_struct, target_name=None):
        source_field = source.required_field(source_struct, source_name)
        target_field = target.required_field(target_struct, target_name or source_name)
        if source_field.type_name == 'tag reference':
            target.set_reference(target_struct, target_name or source_name,
                                 source.reference(source_struct, source_name))
        elif source_field.type_name.endswith(' enum'):
            target_field.set(source_field.options().current_name)
        else:
            target_field.set(source_field.value)

    def common(source_struct, target_struct, skip=()):
        for field in source_struct.fields():
            if field.type_name in {'pad', 'skip', 'terminator', 'explanation'} or field.clean_name in skip:
                continue
            other = target_struct.field(field.clean_name)
            if other is None or other.type_name != field.type_name:
                continue
            if field.as_struct() is not None:
                common(field.as_struct(), other.as_struct())
            elif field.type_name.endswith(' flags'):
                for name in set(field.options().names) & set(other.options().names):
                    other.set_flag(name, field.get_flag(name))
            else:
                copy(source_struct, field.clean_name, target_struct)

    for name in ('radiosity', 'physics', 'texture scrolling animation'):
        # The physics type is a compiled shader class identifier.
        common(struct(source, src, name), struct(target, dst, name), skip=('type',))
    src_properties = struct(source, src, 'properties')
    dst_properties = struct(target, dst, 'properties')
    common(src_properties, dst_properties)
    src_flags = source.required_field(src_properties, 'flags')
    dst_flags = target.required_field(dst_properties, 'flags')
    dst_flags.set_flag('alpha tested' if model_to_environment else 'not alpha tested',
                       not src_flags.get_flag('not alpha tested' if model_to_environment else 'alpha tested'))

    src_maps = struct(source, src, 'maps' if model_to_environment else 'diffuse')
    dst_maps = struct(target, dst, 'diffuse' if model_to_environment else 'maps')
    copy(src_maps, 'base map', dst_maps)
    for model_name, environment_name in (
            ('detail map', 'primary detail map'),
            ('detail map scale', 'primary detail map scale'),
            ('detail function', 'detail map function')):
        copy(src_maps, model_name if model_to_environment else environment_name,
             dst_maps, environment_name if model_to_environment else model_name)
    if model_to_environment:
        target.required_field(dst_maps, 'material color').set(RealRgbColor(1., 1., 1.))
    else:
        for name in ('map u scale', 'map v scale', 'detail map v scale'):
            target.required_field(dst_maps, name).set(1.)

    src_illumination = struct(source, src, 'self-illumination')
    dst_illumination = struct(target, dst, 'self-illumination')
    for model_name, environment_name in (
            ('animation function', 'primary animation function'),
            ('animation period', 'primary animation period'),
            ('animation color lower bound', 'primary off color'),
            ('animation color upper bound', 'primary on color')):
        copy(src_illumination, model_name if model_to_environment else environment_name,
             dst_illumination, environment_name if model_to_environment else model_name)

    src_reflection = struct(source, src, 'reflection')
    dst_reflection = struct(target, dst, 'reflection')
    src_specular = (struct(source, src_reflection, 'cube map properties')
                    if model_to_environment else src_reflection)
    dst_specular = (dst_reflection if model_to_environment else
                    struct(target, dst_reflection, 'cube map properties'))
    for name in ('perpendicular brightness', 'parallel brightness'):
        copy(src_specular, name, dst_specular)
    copy(src_reflection, 'cube map' if model_to_environment else 'reflection cube map',
         dst_reflection, 'reflection cube map' if model_to_environment else 'cube map')
    src_colors = src_specular if model_to_environment else struct(source, src, 'specular')
    dst_colors = struct(target, dst, 'specular') if model_to_environment else dst_specular
    for side in ('perpendicular', 'parallel'):
        copy(src_colors, side + (' tint color' if model_to_environment else ' color'),
             dst_colors, side + (' color' if model_to_environment else ' tint color'))
    target.tag_has_changes = True

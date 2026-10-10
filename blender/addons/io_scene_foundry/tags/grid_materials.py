"""Minimal diffuse grid shaders, authored with each game's native schema."""
from functools import lru_cache
from pathlib import Path

from .. import utils
from .backend import PROFILES, TagDocument


def _struct_layout(struct):
    """Compare embedded layouts too: modern titles share the same header."""
    fields = []
    for field in struct.fields():
        child, block, array = field.as_struct(), field.as_block(), field.as_array()
        if child is not None:
            layout = _struct_layout(child)
        elif block is not None:
            layout = block.element_size
        elif array is not None:
            layout = (len(array), _struct_layout(array[0]) if len(array) else None)
        else:
            layout = None
        fields.append((field.name, field.type_name, layout))
    return struct.size, tuple(fields)


def _tag_layout(tag):
    engine = tag.classic_engine
    if engine is not None and engine.startswith('Halo2'):
        engine = 'Halo2'  # Different classic H2 container revisions are supported.
    # The reader reports zero for classic group versions, including stock tags.
    version = tag.group_version if engine is None else None
    return engine, tag.group_tag, version, _struct_layout(tag.root())


@lru_cache(maxsize=32)
def _expected_grid_tag_layout(game, extension):
    import blam_tags
    schema = Path(__file__).parent / 'definitions' / PROFILES[game] / (extension + '.json')
    tag = (blam_tags.TagFile.new_classic(schema, game) if game in {'halo1', 'halo2'}
           else blam_tags.TagFile.new(schema))
    return _tag_layout(tag)


def remove_incompatible_grid_tag(path, game):
    """Remove foreign or unreadable grid tags so they can be rebuilt."""
    import blam_tags
    tags = Path(utils.get_tags_path())
    path = tags / path
    if not path.is_file():
        return
    # Resolve the current schema first. Missing runtimes/schemas and filesystem
    # errors are setup problems, not reasons to replace an existing tag.
    expected = _expected_grid_tag_layout(game, path.suffix[1:])
    try:
        with TagDocument(path, tags_root=tags, game=game, must_exist=True) as tag:
            if _tag_layout(tag.tag) == expected:
                return
    except blam_tags.TagReadError:
        pass

    path.unlink()
    utils.print_warning(f'Rebuilding incompatible Grid Materials tag {path.name}')


def grid_shader_path(name, game, asset_type):
    if game not in PROFILES:
        raise ValueError(f'Unsupported Grid Materials game: {game}')
    if game == 'halo1':
        extension = 'shader_environment' if asset_type == 'scenario' else 'shader_model'
    else:
        extension = 'material' if game in {'halo4', 'halo2a'} else 'shader'
    return Path('shaders', 'foundry', 'shaders', name + '.' + extension)


def create_grid_shader(path, bitmap_path, game):
    tags = Path(utils.get_tags_path())
    if game == 'halo1':
        # Older Foundry copied a Reach .shader here. Retire that incompatible
        # file as well when creating the proper environment/model shader.
        remove_incompatible_grid_tag(path.with_suffix('.shader'), game)
    remove_incompatible_grid_tag(path, game)
    modern_shader = game in {'halo3', 'halo3odst', 'reach'}
    if not (tags / path).exists():
        if modern_shader:
            from .shader_converter import ShaderTag
            # Initialize options from this kit's render-method definition.
            # H3, ODST and Reach do not have the same option count/layout.
            with ShaderTag(path=path, tag_must_exist=False) as shader:
                method = shader.required_field(shader.tag.root(), 'render_method').as_struct()
                parameter = shader.block(method, 'parameters')
                parameter = parameter[parameter.add()]
                shader.required_field(parameter, 'parameter name').set('base_map')
                shader.required_field(parameter, 'parameter type').set('bitmap')
                shader.set_reference(parameter, 'bitmap', bitmap_path)
                shader.required_field(parameter, 'bitmap flags').set(1)
                shader.required_field(parameter, 'bitmap filter mode').set(6)
        else:
            with TagDocument(path, tags_root=tags, game=game) as shader:
                root = shader.tag.root()
                if game == 'halo1':
                    _halo1_shader(shader, root, bitmap_path)
                elif game == 'halo2':
                    template = Path('shaders/shader_templates/opaque/tex_bump.shader_template')
                    if not (tags / template).is_file():
                        raise FileNotFoundError(f'Grid Materials require {template}')
                    shader.set_reference(root, 'template', template)
                    parameters = shader.block(root, 'parameters')
                    parameter = parameters[parameters.add()]
                    shader.required_field(parameter, 'name').set('base_map')
                    shader.required_field(parameter, 'type').set('bitmap')
                    shader.set_reference(parameter, 'bitmap', bitmap_path)
                    # A flat, matte surface using the template's neutral bump.
                    for name in ('specular_color', 'specular_glancing_color'):
                        parameter = parameters[parameters.add()]
                        shader.required_field(parameter, 'name').set(name)
                        shader.required_field(parameter, 'type').set('color')
                else:
                    material_shader = Path('shaders/material_shaders/materials/srf_lambert.material_shader')
                    if not (tags / material_shader).is_file():
                        raise FileNotFoundError(f'Grid Materials require {material_shader}')
                    shader.set_reference(root, 'material shader', material_shader)
                    parameters = shader.block(root, 'material parameters')
                    parameter = parameters[parameters.add()]
                    shader.required_field(parameter, 'parameter name').set('color_map')
                    shader.required_field(parameter, 'parameter type').set('bitmap')
                    shader.set_reference(parameter, 'bitmap', bitmap_path)
                    shader.required_field(parameter, 'bitmap flags').set(1)
                    shader.required_field(parameter, 'bitmap filter mode').set(6)
                    shader.required_field(root, 'sort layer').set('normal')

    if modern_shader:
        from .shader_converter import ShaderTag, build_templates
        build_templates([str(path)], from_options=True)
        with ShaderTag(path=path) as shader:
            template = shader._template_path(from_options=True)
            if template is None or not template.is_file():
                raise RuntimeError(f'{path}: could not build the grid shader template')


def _halo1_shader(shader, root, bitmap_path):
    def child(name):
        return shader.required_field(root, name).as_struct()

    def white(struct, name):
        field = shader.required_field(struct, name)
        field.set(type(field.value)(1., 1., 1.))

    white(child('radiosity'), 'tint color')
    if shader.system_path.suffix == '.shader_environment':
        diffuse = child('diffuse')
        shader.set_reference(diffuse, 'base map', bitmap_path)
        white(diffuse, 'material color')
    else:
        maps = child('maps')
        shader.set_reference(maps, 'base map', bitmap_path)
        shader.required_field(maps, 'map u scale').set(1.)
        shader.required_field(maps, 'map v scale').set(1.)
        shader.required_field(child('properties'), 'flags').set_flag('not alpha tested', True)

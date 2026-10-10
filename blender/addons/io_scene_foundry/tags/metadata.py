"""Native tag readers used by Foundry's material and shader workflows.

Results are Python values detached from the file, so callers can cache them
after the document closes. No positional field indexes or .NET objects.
"""
from types import SimpleNamespace
from pathlib import Path
import warnings
from .backend import TagDocument

OPTION_TYPES = ('bitmap', 'color', 'real', 'int', 'bool', 'argb color')
MATERIAL_TYPES = ('bitmap', 'real', 'int', 'bool', 'color')


def enum_index(value, names):
    if isinstance(value, int):
        if 0 <= value < len(names):
            return value
    elif value in names:
        return names.index(value)
    raise ValueError(f'Unsupported parameter type: {value!r}')


def argb_components(color):
    if hasattr(color, 'alpha'):
        return color.alpha, color.red, color.green, color.blue
    if hasattr(color, 'value'):
        return tuple((color.value >> shift) & 255 for shift in (24, 16, 8, 0))
    return tuple(color)


def rgba(color):
    a, r, g, b = argb_components(color)
    return r, g, b, a


def option_rgba(color):
    # blam-tags exposes the actual packed unsigned ARGB bytes. The old CLR
    # signed-channel workaround must not be applied to this representation.
    return tuple(c / 255 for c in rgba(color))


class RenderMethodOptionDocument(TagDocument):
    tag_ext = 'render_method_option'

    def parameters(self):
        return self.block(self.tag.root(), 'parameters')

    def ui_name(self, element):
        field = element.field('parameter ui override name')
        return field.value if field is not None else ''

    def parameter(self, element):
        get = lambda name: self.value(element, name)
        name = get('parameter name')
        ui_name = self.ui_name(element) or name
        if ui_name == 'point_specular_contribtuion':
            ui_name = 'point_specular_contribution'
        kind = enum_index(get('parameter type'), OPTION_TYPES)
        bitmap = self.reference(element, 'default bitmap')
        real = get('default real value')
        integer = get('default int/bool value')
        color = option_rgba(get('default color'))
        default = (bitmap, color, real, integer, integer, (color, real))[kind]
        address = element.field('default address mode')
        address_mode = enum_index(address.value, ('wrap', 'clamp', 'mirror', 'black border',
                                  'mirror once', 'mirror once border')) if address is not None else 0
        return SimpleNamespace(name=name, ui_name=ui_name, type=kind, default=default,
                               default_bitmap=bitmap, default_real=real,
                               default_int=integer, default_color=color,
                               default_address_mode=address_mode)

    def get_option_parameters(self):
        result = {}
        for element in self.parameters():
            parameter = self.parameter(element)
            result[parameter.name] = parameter
        return result

    def read_options(self):
        return {self.value(e, 'parameter name'):
                [self.ui_name(e),
                 enum_index(self.value(e, 'parameter type'), OPTION_TYPES)]
                for e in self.parameters()}

    def read_parameter_types(self):
        return {name: value[1] for name, value in self.read_options().items()}

    def read_parameter_names(self):
        return {value[0] or name: name for name, value in self.read_options().items()}

    def read_defaults(self):
        defaults = {}
        for element in self.parameters():
            parameter = self.parameter(element)
            color = list(argb_components(self.value(element, 'default color')))
            default = parameter.default
            if parameter.type == 1:
                default = color
            elif parameter.type == 5:
                default = (color, parameter.default_real)
            defaults[parameter.name] = default
        return defaults


class RenderMethodDefinitionDocument(TagDocument):
    tag_ext = 'render_method_definition'

    def get_defaults(self):
        result = {}
        for category in self.block(self.tag.root(), 'categories'):
            options = {}
            for option in self.block(category, 'options'):
                path = self.reference(option, 'option')
                parameters = {}
                if path is not None:
                    if path.IsTagFileAccessible():
                        with RenderMethodOptionDocument(path, tags_root=self.tags_root,
                                                        game=self.game, must_exist=True,
                                                        definitions=self.definitions) as doc:
                            parameters = doc.get_option_parameters()
                    else:
                        # Some shipped definitions reference absent option tags,
                        # including options the material does not select.
                        warnings.warn(f'Missing shader option defaults: {path.Filename} '
                                      '(using empty defaults for this option)',
                                      RuntimeWarning, stacklevel=2)
                options[self.value(option, 'option name')] = parameters
            result[self.value(category, 'category name')] = options
        return result

    def get_categories(self):
        return self.get_defaults()


class MaterialShaderDocument(TagDocument):
    tag_ext = 'material_shader'

    def parameters(self):
        return self.block(self.tag.root(), 'material parameters')

    def display_name(self, element):
        value = self.value(element, 'display name')
        return value.decode('utf-8').rstrip('\0') if isinstance(value, bytes) else value

    def read_parameters(self):
        return {self.value(e, 'parameter name'):
                [self.display_name(e), MATERIAL_TYPES[enum_index(self.value(e, 'parameter type'), MATERIAL_TYPES)]]
                for e in self.parameters()}

    def read_parameters_list(self):
        return [self.value(e, 'parameter name') for e in self.parameters()]

    def get_defaults(self):
        result = {}
        for element in self.parameters():
            get = lambda name: self.value(element, name)
            name = get('parameter name')
            kind = enum_index(get('parameter type'), MATERIAL_TYPES)
            bitmap = None
            tif = get('bitmap path')
            if tif.strip():
                path = (self.tags_root / tif).with_suffix('.bitmap')
                if path.is_file():
                    bitmap = self.reference_from_path(path)
            color = rgba(get('color'))
            real, integer = get('real'), get('int/bool')
            vector = get('vector')
            vector = tuple(vector.to_array())
            result[name] = SimpleNamespace(name=name, ui_name=self.display_name(element) or name,
                type=kind, type_name=MATERIAL_TYPES[kind], default=(bitmap, real, integer, integer, color)[kind],
                default_bitmap=bitmap, default_color=color, default_real=real,
                default_vector=vector, default_int=integer)
        return result


class GlobalsDocument(TagDocument):
    tag_ext = 'globals'

    def fp_player_representation(self, index: int):
        """Select the weapon's human/elite slot, including ODST's model choices."""
        if index not in (0, 1):
            return None
        if self.game == 'halo1':
            block = self.block(self.tag.root(), 'first person interface')
            return block[0] if index == 0 and len(block) else None
        block = self.block(self.tag.root(), '@player representation')
        if self.game in {'halo3', 'halo3odst'}:
            choice = ('spartan', 'elite')[index]
            for element in block:
                value = self.value(element, 'model choice')
                if value in (index, choice) and self.reference(element, 'first person hands'):
                    return element
            return None
        return block[index] if index < len(block) else None

    def get_fp_arms_references(self, index: int):
        """Return independent hands and optional third-person colour references."""
        element = self.fp_player_representation(index)
        if element is None:
            return None
        hands_field = 'first person hands model' if self.game in {'halo4', 'halo2a'} else 'first person hands'
        hands = self.reference(element, hands_field)
        if hands is None:
            return None
        if self.game == 'halo1':
            # H1 references can name the abstract model group while the file
            # on disk is the compiled gbxmodel.
            if hands.Extension == 'model' and not Path(hands.Filename).is_file():
                compiled = self.reference_from_path(Path(hands.Filename).with_suffix('.gbxmodel'))
                if Path(compiled.Filename).is_file():
                    hands = compiled
            players = self.block(self.tag.root(), 'player information')
            unit = self.reference(players[0], 'unit') if len(players) else None
        else:
            unit = self.reference(element, 'third person unit')
        return hands, unit

    def get_global_materials(self):
        return [self.value(e, 'name') for e in self.block(self.tag.root(), 'materials')]

    def get_camera_fov(self):
        field = self.tag.root().field('camera')
        block = field.as_block() if field is not None else None
        # H3 stores a FOV scale, not an angle. Let the caller use its default.
        field = block[0].field('field of view') if block is not None and len(block) else None
        return field.value if field is not None else None

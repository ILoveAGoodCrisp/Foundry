"""Detached scalar expressions shared by object and bitmap-sequence drivers."""
from dataclasses import dataclass
import ast
import hashlib


CHANGE_COLOR_PROPERTIES = ('Primary Color', 'Secondary Color', 'Tertiary Color', 'Quaternary Color')


def refresh_driver_dependencies(owner, *sources):
    """Expose newly written custom properties to evaluated shader attributes."""
    import bpy
    for data in dict.fromkeys((*sources, owner)):
        if data is not None:
            if isinstance(data, bpy.types.Object):
                data.update_tag(refresh={'DATA'})
            else:
                # Scene and NodeTree IDs do not accept Object's DATA flag.
                data.update_tag()


def bind_property_driver(owner, source, name, source_name=None):
    """Bind scalar or array properties after refreshing the source ID's data."""
    import bpy
    path = f'["{bpy.utils.escape_identifier(name)}"]'
    source_path = f'["{bpy.utils.escape_identifier(source_name or name)}"]'
    # Refresh before binding: otherwise a newly created property can remain
    # absent from the evaluated target until an unrelated shader edit.
    refresh_driver_dependencies(source)
    curves = owner.driver_add(path)
    is_array = isinstance(curves, list)
    for index, curve in enumerate(curves if is_array else [curves]):
        driver = curve.driver
        driver.type = 'SCRIPTED'
        while driver.variables:
            driver.variables.remove(driver.variables[0])
        variable = driver.variables.new()
        variable.name = 'var'
        variable.type = 'SINGLE_PROP'
        variable.targets[0].id_type = 'SCENE' if isinstance(source, bpy.types.Scene) else 'OBJECT'
        variable.targets[0].id = source
        variable.targets[0].data_path = source_path + (f'[{index}]' if is_array else '')
        driver.expression = variable.name
    refresh_driver_dependencies(owner)


def set_scalar_driver_expression(owner, curve, expression):
    """Write only simple expressions, splitting at Blender's driver limit."""
    bindings = {var.name: (var.targets[0].id_type, var.targets[0].id, var.targets[0].data_path)
                for var in curve.driver.variables}
    refresh_driver_dependencies(owner, *(target for _, target, _ in bindings.values()))
    prefix = '_foundry_driver_' + hashlib.sha1(curve.data_path.encode()).hexdigest()[:10]
    for name in list(owner.keys()):
        if name.startswith(prefix + '_'):
            owner.driver_remove(f'["{name}"]')
            del owner[name]
    counter = 0

    def configure(driver, text):
        driver.type = 'SCRIPTED'
        while driver.variables:
            driver.variables.remove(driver.variables[0])
        for name in dict.fromkeys(node.id for node in ast.walk(ast.parse(text, mode='eval'))
                                  if isinstance(node, ast.Name) and node.id in bindings):
            kind, target, path = bindings[name]
            var = driver.variables.new()
            var.name = name
            var.type = 'SINGLE_PROP'
            var.targets[0].id_type = kind
            var.targets[0].id = target
            var.targets[0].data_path = path
        driver.expression = text
        if not driver.is_simple_expression:
            # Never leave a Python-only expression attached, even if a future
            # function generator accidentally introduces unsupported syntax.
            driver.expression = '0.0'
            raise ValueError(f'Scalar driver requires Python execution: {text}')

    def shorten(node):
        nonlocal counter
        while len(ast.unparse(node)) > 240:
            children = [(field, index, child) for field, value in ast.iter_fields(node)
                        for index, child in (enumerate(value) if isinstance(value, list) else [(None, value)])
                        if isinstance(child, ast.expr)]
            if not children:
                raise ValueError('Scalar function expression cannot fit in a Blender driver')
            field, index, child = max(children, key=lambda entry: len(ast.unparse(entry[2])))
            child = shorten(child)
            name = f'p{counter}'
            property_name = f'{prefix}_{counter}'
            counter += 1
            owner[property_name] = 0.0
            path = f'["{property_name}"]'
            helper = owner.driver_add(path)
            configure(helper.driver, ast.unparse(child))
            bindings[name] = ('NODETREE' if owner.bl_rna.identifier.endswith('NodeTree') else 'OBJECT', owner, path)
            replacement = ast.Name(id=name, ctx=ast.Load())
            if index is None:
                setattr(node, field, replacement)
            else:
                getattr(node, field)[index] = replacement
        return node

    expression_node = shorten(ast.parse(expression, mode='eval').body)
    configure(curve.driver, ast.unparse(expression_node))
    refresh_driver_dependencies(owner)


class ObjectFunctions(dict):
    def __init__(self, *args, decoded=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.decoded = decoded or {}


@dataclass
class Halo1NumericCounter:
    limit: int
    permutation: int

    def driver_expression(self, variable, time='frame/30'):
        # Numeric H1 shaders read object function A. Each model shader
        # permutation selects a decimal place (zero is the ones digit).
        # Object function properties are evaluated as 32-bit floats. Recover
        # integer counts such as 13/60 without rounding down to 12.
        if self.permutation > 2:
            return '0.0'  # The tag's counter limit is an unsigned byte.
        value = f'floor(min(max({variable("a out")},0),1)*{self.limit}+0.0001)'
        place = 10 ** self.permutation
        return f'(floor(({value})/{place})-10*floor(({value})/{place*10}))'


def linear_expression(points, value):
    """Piecewise linear interpolation, clamped at the authored endpoints."""
    points = sorted(dict(points).items())
    if not points:
        return '0.0'
    simplified = []
    for point in points:
        simplified.append(point)
        while len(simplified) > 2:
            a, b, c = simplified[-3:]
            if abs((b[1]-a[1])*(c[0]-b[0])-(c[1]-b[1])*(b[0]-a[0])) > 1e-7:
                break
            simplified.pop(-2)
    points = simplified
    terms = [f'{float(points[0][1]):.9g}']
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if y1 != y0 and x1 > x0:
            terms.append(f'{(y1-y0)/(x1-x0):.9g}*min(max(({value})-{x0:.9g},0),{x1-x0:.9g})')
    return '(' + '+'.join(terms) + ')'


def periodic_expression(name, value):
    name = name.replace(' (variable period)', '').replace(' variable period', '')
    if name == 'one':
        return '1.0'
    if name == 'zero':
        return '0.0'
    if name == 'cosine':
        return f'(0.5-0.5*cos(2*pi*({value})))'
    if name == 'diagonal wave':
        return f'(1-abs(2*{fraction_expression(value)}-1))'
    if name == 'slide':
        return fraction_expression(value)
    # Deterministic previews for the stochastic waveform types. These remain
    # editable through the imported function's input properties.
    noise = fraction_expression(f'sin(floor(({value})*30)*12.9898)*43758.5453')
    if name in {'noise', 'jitter', 'wander'}:
        return noise
    if name == 'spark':
        return f'({noise}>0.95)'
    raise ValueError(f'Unsupported periodic function: {name}')


def fraction_expression(value):
    """Positive fractional part, including negative phases, without Python %."""
    return f'(({value})-floor({value}))'


@dataclass
class Halo1Function:
    values: dict
    flags: set
    inputs: dict

    @classmethod
    def read(cls, document, element, inputs):
        names = ('period', 'scale period by', 'function', 'scale function by',
                 'wobble function', 'wobble period', 'wobble magnitude',
                 'square wave threshold', 'step count', 'map to', 'sawtooth count',
                 'add', 'scale result by', 'bounds mode', 'bounds', 'turn off with', 'scale by')
        values = {name: document.value(element, name) for name in names}
        bounds = values['bounds']
        values['bounds'] = (float(bounds.lower), float(bounds.upper))
        flags = document.required_field(element, 'flags')
        return cls(values, {name for name in ('invert', 'additive', 'always active')
                            if flags.get_flag(name)}, inputs)

    def driver_expression(self, variable, time='frame/30'):
        v = self.values

        def source(name, default='1.0'):
            name = str(v[name])
            if name == 'none':
                return default
            name = self.inputs.get(name, name)
            return default if name == 'none' else variable(name)

        period = float(v['period']) or 1.0
        phase = f'({time})/({period:.9g}*max({source("scale period by")},0.000001))'
        if v['wobble magnitude']:
            wobble = periodic_expression(str(v['wobble function']),
                                         f'({time})/{float(v["wobble period"]) or 1:.9g}')
            phase = f'({phase}+{float(v["wobble magnitude"]):.9g}*{wobble})'
        value = periodic_expression(str(v['function']), phase)
        value = f'({value}*{source("scale function by")})'
        if v['square wave threshold']:
            value = f'({value}>{float(v["square wave threshold"]):.9g})'
        steps = int(v['step count'])
        if steps > 1:
            value = f'(floor({value}*{steps-1})/{steps-1})'
        mapping = str(v['map to'])
        if mapping in {'early', 'very early', 'late', 'very late'}:
            power = {'early': 0.5, 'very early': 1/3, 'late': 2, 'very late': 3}[mapping]
            value = f'pow(max({value},0),{power:.9g})'
        elif mapping == 'cosine':
            value = f'(0.5-0.5*cos(pi*{value}))'
        if int(v['sawtooth count']) > 1:
            value = fraction_expression(f'{value}*{int(v["sawtooth count"])}')
        value = f'({value}+{source("add", "0.0")})'
        lower, upper = v['bounds']
        # Loose HEK tags leave both values at zero for the default 0..1 bounds.
        if lower == upper == 0:
            lower, upper = 0.0, 1.0
        if str(v['bounds mode']) == 'scale to fit':
            value = f'({lower:.9g}+{upper-lower:.9g}*{value})'
        else:
            value = f'min(max({value},{lower:.9g}),{upper:.9g})'
            if str(v['bounds mode']) == 'clip and normalize' and upper != lower:
                value = f'(({value}-{lower:.9g})/{upper-lower:.9g})'
        if 'invert' in self.flags:
            value = f'(1-{value})'
        value = f'({value}*{source("scale result by")})'
        turn_off = int(v['turn off with'])
        if 0 <= turn_off < 4:
            value = f'({value} if {variable(chr(97+turn_off)+" out")} else 0)'
        return value

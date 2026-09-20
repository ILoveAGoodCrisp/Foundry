"""Native light-mapping decoding shared by the light tag importers."""
from contextlib import contextmanager
from ..managed_blam.connected_material import Function
from math import isfinite


def constant_light_value(function):
    """Resolve scalar mappings that do not depend on changing light inputs."""
    if function.is_color or function.output_modifier_type.value:
        return None
    if function.is_basic_function and not function.is_ranged:
        result = function.clamp_min
    elif function.clamp_min == function.clamp_max:
        result = function.clamp_min
    elif (getattr(function, 'native_function_type', None) in {0, 1, 2, 8, 9}
          and not function.uses_input and not (function.is_ranged and function.range)):
        # Match Function.to_blend_nodes: missing input is "one", missing range is zero.
        # Identity, constant, transition, MultiSpline and exponent are deterministic.
        # Periodic functions can include noise and are deliberately excluded.
        result = function.editor.evaluate(1., 0.)
    else:
        return None
    return result if isfinite(result) else None


@contextmanager
def light_functions(document, names):
    functions = []
    for name in names:
        element = document.required_field(document.tag.root(), name).as_struct()
        function = Function()
        function.from_native_light(document, element)
        functions.append(function)
    yield functions

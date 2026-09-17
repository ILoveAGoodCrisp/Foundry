"""Light mapping decoding; the legacy editor is used only for unsupported shapes."""
from contextlib import contextmanager
from .connected_material import Function


@contextmanager
def light_functions(document, names):
    try:
        functions = []
        for name in names:
            element = document.required_field(document.tag.root(), name).as_struct()
            function = Function()
            function.from_native_light(document, element)
            functions.append(function)
    except ValueError:
        # Keep the legacy document alive while its editors build Blender nodes.
        from . import Tag
        with Tag(path=document.path, tag_must_exist=True) as legacy:
            functions = []
            for name in names:
                function = Function()
                function.from_element(legacy.tag.SelectField('Struct:' + name).Elements[0], 'Mapping')
                functions.append(function)
            yield functions
    else:
        yield functions

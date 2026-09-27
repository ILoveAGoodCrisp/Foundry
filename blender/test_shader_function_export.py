"""Run with Blender --background --factory-startup --python-exit-code 1 --python this_file.py.

Exercise the shader writer with native tag blocks and serialized functions.
No editing kit or installed add-on is required.
"""
import ast
from enum import Enum
import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
import zipfile

import bpy

ADDON = Path(__file__).resolve().parent / 'addons/io_scene_foundry'
TEMP = tempfile.TemporaryDirectory(prefix='foundry_shader_functions_', ignore_cleanup_errors=True)
ROOT = Path(TEMP.name)
zipfile.ZipFile(next((ADDON / 'wheels').glob('blam_tags*'))).extractall(ROOT / 'python')
sys.path.insert(0, str(ROOT / 'python'))

package = types.ModuleType('shader_function_test_foundry')
package.__path__ = [str(ADDON)]
sys.modules[package.__name__] = package
backend = importlib.import_module(package.__name__ + '.tags.backend')
fields = importlib.import_module(package.__name__ + '.tags.field_view')

# Load the production writing methods without initializing unrelated Blender UI
# and shader-reading modules; all tag fields and function bytes are native.
scope = {'Enum': Enum, 'bpy': bpy, 'NativeTagStruct': fields.NativeTagStruct}
connected = ast.parse((ADDON / 'tags/connected_material.py').read_text())
enum = next(n for n in connected.body if isinstance(n, ast.ClassDef) and n.name == 'AnimatedParameterType')
exec(compile(ast.Module(body=[enum], type_ignores=[]), 'connected_material.py', 'exec'), scope)
AnimatedParameterType = scope['AnimatedParameterType']
source = ast.parse((ADDON / 'tags/shader_converter.py').read_text())
shader_class = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'ShaderTag')
methods = {
    '_Element_from_field_value', '_EnumIntValue', '_setup_parameter',
    '_function_parameters_from_node', '_animated_parameter_enum_value',
    '_animated_parameter_value_is_default', '_set_animated_parameter_type',
    '_setup_function_parameters', '_FunctionEditorMasterType',
}
shader_class.bases = []
shader_class.body = [n for n in shader_class.body if isinstance(n, ast.FunctionDef) and n.name in methods]
exec(compile(ast.Module(body=[shader_class], type_ignores=[]), 'shader_converter.py', 'exec'), scope)
Writer = scope['ShaderTag']
Writer.function_parameters = 'animated parameters'
Writer.animated_function = 'animation function'
Writer.scale_u, Writer.scale_v = 'scale x', 'scale y'
Writer.translation_u, Writer.translation_v = 'translation x', 'translation y'


class ShaderFunctionTests(unittest.TestCase):
    def writer(self, document):
        writer = Writer()
        root = fields.NativeTagStruct(document, document.tag.root())
        writer.block_parameters = root.SelectField('Struct:render_method[0]/Block:parameters')
        return writer

    def assert_constant(self, parameter, expected):
        functions = parameter.SelectField('animated parameters').Elements
        self.assertEqual(len(functions), 1)
        self.assertEqual(functions[0].SelectField('type').Value, 0)
        function = functions[0].SelectField('animation function').Value
        self.assertEqual(function.MasterType, 0)
        self.assertAlmostEqual(function.ClampRangeMin, expected)

    def test_scalar_functions_survive_creation_update_and_roundtrip(self):
        names = ('analytical_specular_contribution', 'area_specular_contribution',
                 'environment_map_specular_contribution')
        for game in ('reach', 'halo3'):
            with self.subTest(game=game):
                path = game + '.shader'
                with backend.TagDocument(path, tags_root=ROOT, game=game) as document:
                    writer = self.writer(document)
                    for name, initial, final in zip(names, (0.0, 1.0, 0.5), (1.0, 0.0, 1.0)):
                        parameter = writer._setup_parameter(initial, name, 'real')
                        writer._setup_function_parameters(initial, parameter, 'real')
                        self.assert_constant(parameter, initial)
                        writer._setup_parameter(final, name, 'real')
                        writer._setup_function_parameters(final, parameter, 'real')
                        self.assert_constant(parameter, final)
                with backend.TagDocument(path, tags_root=ROOT, game=game, must_exist=True) as document:
                    parameters = self.writer(document).block_parameters.Elements
                    self.assertEqual(len(parameters), 3)
                    for parameter, name, expected in zip(parameters, names, (1.0, 0.0, 1.0)):
                        self.assertEqual(parameter.SelectField('parameter name').Value, name)
                        self.assertAlmostEqual(parameter.SelectField('real').Data, expected)
                        self.assert_constant(parameter, expected)

    def test_identity_texture_transforms_are_still_omitted(self):
        transforms = (
            (AnimatedParameterType.SCALE_UNIFORM, 1),
            (AnimatedParameterType.SCALE_X, 1),
            (AnimatedParameterType.SCALE_Y, 1),
            (AnimatedParameterType.TRANSLATION_X, 0),
            (AnimatedParameterType.TRANSLATION_Y, 0),
        )
        with backend.TagDocument('transforms.shader', tags_root=ROOT, game='reach') as document:
            writer = self.writer(document)
            parameter = writer.block_parameters.AddElement()
            parameter.SelectField('parameter name').SetStringData('base_map')
            parameter.SelectField('parameter type').SetValue('bitmap')
            for kind, identity in transforms:
                with self.subTest(transform=kind):
                    writer._function_parameters_from_node = lambda source, _: {kind: source}
                    writer._setup_function_parameters(identity, parameter, 'bitmap')
                    self.assertEqual(len(parameter.SelectField('animated parameters').Elements), 0)
                    # Zero scale and unit translation must remain explicit.
                    writer._setup_function_parameters(1 - identity, parameter, 'bitmap')
                    self.assertEqual(len(parameter.SelectField('animated parameters').Elements), 1)
                    writer._setup_function_parameters(identity, parameter, 'bitmap')
                    self.assertEqual(len(parameter.SelectField('animated parameters').Elements), 0)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])

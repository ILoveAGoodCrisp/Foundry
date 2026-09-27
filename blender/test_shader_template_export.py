"""Run in background Blender. Uses native shader tags and a simulated Tool process."""
import ast
import multiprocessing
from pathlib import Path
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_shader_function_export as native

source = ast.parse((native.ADDON / 'tags/shader_converter.py').read_text())
shader_class = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'ShaderTag')
shader_class.bases = []
shader_class.body = [n for n in shader_class.body if isinstance(n, ast.FunctionDef)
                     and n.name in {'_template_path', '_option_value_from_index', 'get_path_str'}]
scope = dict(native.scope, Path=Path, TagReference=native.backend.TagReference,
             multiprocessing=multiprocessing, subprocess=subprocess, time=time)
exec(compile(ast.Module(body=[shader_class], type_ignores=[]), 'shader_converter.py', 'exec'), scope)
TemplateMethods = scope['ShaderTag']


class Shader(TemplateMethods, native.backend.TagDocument):
    def __init__(self, path):
        super().__init__(path, tags_root=ROOT, game='reach', must_exist=True)
        self.corinth = False
        self._native_root = native.fields.NativeTagStruct(self, self.tag.root())
        self.definition = self._native_root.SelectField('Struct:render_method/Reference:definition')
        self.reference = self._native_root.SelectField('Struct:render_method/Reference:reference')
        self.block_options = self._native_root.SelectField('Struct:render_method/Block:options')


scope['ShaderTag'] = Shader
scope['RenderMethodDefinitionTag'] = lambda path: native.backend.TagDocument(
    path, tags_root=ROOT, game='reach', must_exist=True)
build = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'build_templates')
exec(compile(ast.Module(body=[build], type_ignores=[]), 'shader_converter.py', 'exec'), scope)
build_templates = scope['build_templates']
ROOT = native.ROOT


class TemplateExportTests(unittest.TestCase):
    def setUp(self):
        global ROOT
        ROOT = native.ROOT / self._testMethodName
        ROOT.mkdir()
        self.commands = []
        self.warnings = []
        self.exit_code = 0
        self.create_output = True
        scope['utils'] = types.SimpleNamespace(run_tool=self.run_tool, print_warning=self.warnings.append)

    def run_tool(self, args, **kwargs):
        self.commands.append(args)
        self.assertEqual(args[:2], ['generate-specified-template', 'win'])
        self.assertTrue(kwargs['in_background'])
        output = ROOT / (args[2] + '_templates') / (args[3] + '.render_method_template')
        if self.create_output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.touch()
        return types.SimpleNamespace(wait=lambda **kw: self.exit_code)

    def shader(self, name='new', family='shader', options=(2, -1), template=None, parent=None):
        definition_path = f'shaders/{family}.render_method_definition'
        if not (ROOT / definition_path).exists():
            with native.backend.TagDocument(definition_path, tags_root=ROOT, game='reach') as document:
                categories = native.fields.NativeTagStruct(document, document.tag.root()).SelectField('categories')
                for _ in range(2):
                    categories.AddElement()
        path = name + ('.shader' if family == 'shader' else '.shader_custom')
        with native.backend.TagDocument(path, tags_root=ROOT, game='reach') as document:
            root = native.fields.NativeTagStruct(document, document.tag.root())
            root.SelectField('Struct:render_method/Reference:definition').Path = document.reference_from_path(definition_path)
            block = root.SelectField('Struct:render_method/Block:options')
            for option in options:
                block.AddElement().SelectField('short').SetStringData(str(option))
            if template is not None:
                element = root.SelectField('Struct:render_method/Block:postprocess').AddElement()
                element.SelectField('shader template').Path = document.reference_from_path(template)
            if parent is not None:
                root.SelectField('Struct:render_method/Reference:reference').Path = document.reference_from_path(parent)
        return path

    def test_fresh_shader_generates_template_and_existing_template_is_skipped(self):
        shader = self.shader()
        self.assertEqual(build_templates([shader], from_options=True), 1)
        self.assertEqual(self.commands[0][2:], [r'shaders\shader', '_2_0'])
        self.assertEqual(build_templates([shader], from_options=True), 0)
        self.assertEqual(len(self.commands), 1)
        self.assertEqual(self.warnings, [])

    def test_manual_tool_handles_fresh_tags_and_preserves_explicit_references(self):
        self.assertEqual(build_templates([self.shader()]), 1)
        template = 'shaders/shader_templates/_1_1.render_method_template'
        self.assertEqual(build_templates([self.shader('stored', template=template)]), 1)
        self.assertEqual(self.commands[-1][-1], '_1_1')

    def test_automatic_check_uses_updated_options_instead_of_stale_reference(self):
        stale = 'shaders/shader_templates/_0_0.render_method_template'
        shader = self.shader(template=stale)
        self.assertEqual(build_templates([shader], from_options=True), 1)
        self.assertEqual(self.commands[0][-1], '_2_0')

    def test_inherited_options(self):
        parent = self.shader('parent', options=(1, 2))
        child = self.shader('child', options=(-1,), parent=parent)
        self.assertEqual(build_templates([child], from_options=True), 1)
        self.assertEqual(self.commands[0][-1], '_1_2')

    def test_batch_limit_and_deduplication_across_families(self):
        shaders = [self.shader(), self.shader('duplicate'), self.shader('custom', family='custom')]
        with patch.object(multiprocessing, 'cpu_count', return_value=1):
            self.assertEqual(build_templates(shaders), 2)
        self.assertEqual(len(self.commands), 2)
        self.assertNotEqual(self.commands[0][2], self.commands[1][2])

    def test_failed_or_missing_output_is_not_reported_as_generated(self):
        shader = self.shader()
        self.create_output = False
        for code in (0, 1):
            with self.subTest(exit_code=code):
                self.exit_code = code
                self.assertEqual(build_templates([shader]), 0)
                self.assertIn('Failed to build', self.warnings[-1])

    def test_timeout_stops_process_and_warns(self):
        shader = self.shader()
        killed = []

        def wait(timeout=None):
            if timeout is not None:
                raise subprocess.TimeoutExpired('tool', timeout)
            return -9

        scope['utils'].run_tool = lambda *args, **kwargs: types.SimpleNamespace(
            wait=wait, kill=lambda: killed.append(True))
        self.assertEqual(build_templates([shader]), 0)
        self.assertEqual(killed, [True])
        self.assertIn('Timed out', self.warnings[0])

    def test_shader_creation_checks_templates_after_saving_with_or_without_nodes(self):
        source = ast.parse((native.ADDON / 'tools/shader_builder.py').read_text())
        method = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == 'build_shader')
        for use_nodes in (True, False):
            with self.subTest(use_nodes=use_nodes):
                events = []

                class Tag:
                    def __init__(self, **kwargs):
                        self.tag_path = types.SimpleNamespace(RelativePathWithExtension='new.shader')

                    def __enter__(self):
                        events.append('initialized')
                        return self

                    def write_tag(self, *args):
                        return self.tag_path.RelativePathWithExtension

                    def __exit__(self, *args):
                        events.append('saved')

                def check_templates(paths, *, from_options):
                    self.assertEqual(events, ['initialized', 'saved'])
                    self.assertEqual(paths, ['new.shader'])
                    self.assertTrue(from_options)
                    events.append('templates checked')

                properties = types.SimpleNamespace(shader_path='new.shader', shader_type='.shader', uses_blender_nodes=use_nodes)
                material = types.SimpleNamespace(name='new', name_full='new', nwo=properties, get=lambda key: None)
                utils = types.SimpleNamespace(get_asset_path=lambda: '', get_shader_name=lambda mat: 'new',
                                              material_read_only=lambda path: False)
                namespace = dict(Path=Path, utils=utils, EmptyShaderTag=None,
                                 REACH_SUFFIX_TO_CLASS={'.shader': (Tag, '.shader')},
                                 _resolve_reach_shader_class=lambda *args: (Tag, '.shader'),
                                 build_templates=check_templates)
                exec(compile(ast.Module(body=[method], type_ignores=[]), 'shader_builder.py', 'exec'), namespace)
                self.assertEqual(namespace['build_shader'](material, False), {'FINISHED'})
                self.assertEqual(events[-1], 'templates checked')


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]])

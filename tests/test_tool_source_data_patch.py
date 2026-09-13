"""Tool source-data patch checks, runnable without Blender or the editing kits."""
import ast
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]

# Instruction windows from the six supported executables. The expected edit
# starts after the parent_file_index store (and any call argument setup).
FIXTURES = [
    ('reach', 'tool.exe', 0x270E0F, '41 89 81 44 01 00 00 e8 25 10 90 00', 7),
    ('reach', 'tool_fast.exe', 0x1DC954, '41 89 80 44 01 00 00 45 39 65 00 7e 12', 7),
    ('h4', 'tool.exe', 0x1FD799, '41 89 81 44 01 00 00 8b d7 49 8b cc e8 b6 67 6c 00', 12),
    ('h4', 'tool_fast.exe', 0x1E3CE7, '89 82 44 01 00 00 8b d7 49 8b cf e8 e1 42 51 00', 11),
    ('h2amp', 'tool.exe', 0x1FE919, '41 89 81 44 01 00 00 8b d7 49 8b cc e8 c6 fa 6e 00', 12),
    ('h2amp', 'tool_fast.exe', 0x1E4277, '89 82 44 01 00 00 8b d7 49 8b cf e8 5d 8e 51 00', 11),
]


class SourceDataPatchTests(unittest.TestCase):
    def setUp(self):
        self.prefs = SimpleNamespace(allow_tool_patches=True, patch_tool_skip_import_source_data=True)
        bpy = SimpleNamespace(context=SimpleNamespace(preferences=SimpleNamespace(
            addons={'_patch_tests': SimpleNamespace(preferences=self.prefs)})))
        spec = importlib.util.spec_from_file_location(
            '_patch_tests.patches', ROOT / 'blender/addons/io_scene_foundry/patches.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'bpy': bpy}):
            spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_all_variants_preserve_metadata_and_restore(self):
        for game, name, offset, signature, prefix in FIXTURES:
            with self.subTest(game=game, name=name):
                path = Path(self.temp.name, name)
                original = bytes.fromhex(signature)
                with path.open('wb') as stream:
                    stream.seek(offset)
                    stream.write(original + b'following instructions')
                before = path.read_bytes()
                patcher = self.module.ToolPatcher(path)
                records = patcher.skip_import_source_data(return_patches=True)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(len(records), 1)
                address, replacement, expected = records[0]
                self.assertEqual((address, expected), (offset, original))
                self.assertEqual(replacement[:prefix], original[:prefix])
                self.assertEqual(len(replacement), len(original))
                if game == 'reach' and name == 'tool_fast.exe':
                    jump = replacement[prefix:]
                    self.assertEqual(jump[0], 0xE9)
                    self.assertEqual(offset + prefix + 5 + struct.unpack('<i', jump[1:5])[0], 0x1DCD05)
                    self.assertEqual(jump[5:], b'\x90')
                else:
                    self.assertEqual(replacement[prefix:], b'\x90' * 5)
                patcher.skip_import_source_data()
                after = path.read_bytes()
                self.assertEqual(after[:offset], before[:offset])
                self.assertEqual(after[offset:offset + len(original)], replacement)
                self.assertEqual(after[offset + len(original):], before[offset + len(original):])
                patcher.skip_import_source_data()  # Idempotent and recognized after patching.
                self.assertEqual(path.read_bytes(), after)
                self.assertEqual(patcher.skip_import_source_data(return_patches=True), records)
                patcher.skip_import_source_data(enabled=False)
                self.assertEqual(path.read_bytes(), before)

    def test_disabled_patches_do_not_open_executable(self):
        patcher = self.module.ToolPatcher(Path(self.temp.name, 'missing.exe'))
        self.assertEqual(patcher.skip_import_source_data(enabled=False, return_patches=True), [])
        self.prefs.patch_tool_skip_import_source_data = False
        self.assertEqual(patcher.skip_import_source_data(return_patches=True), [])
        self.prefs.allow_tool_patches = False
        self.assertEqual(patcher.skip_import_source_data(enabled=True, return_patches=True), [])

    def test_unknown_binary_is_rejected_without_writing(self):
        path = Path(self.temp.name, 'tool.exe')
        path.write_bytes(b'unsupported executable')
        patcher = self.module.ToolPatcher(path)
        with self.assertRaisesRegex(RuntimeError, 'Unsupported Tool'):
            patcher.skip_import_source_data(return_patches=True)
        self.assertEqual(path.read_bytes(), b'unsupported executable')

    def test_export_includes_patch_for_reach_and_corinth(self):
        source = ast.parse((ROOT / 'blender/addons/io_scene_foundry/export/process.py').read_text())
        method = next(node for node in ast.walk(source)
                      if isinstance(node, ast.FunctionDef) and node.name == '_memory_tool_patches')
        patcher = Mock()
        record = (123, b'patched', b'original')
        patcher.skip_import_source_data.return_value = [record]
        patcher.reach_uncompressed_vertex_weights.return_value = []
        patcher.reach_skip_vertex_compression.return_value = []
        namespace = dict(Path=Path, ToolPatcher=Mock(return_value=patcher),
                         utils=SimpleNamespace(get_tool_type=lambda: 'tool'),
                         AssetType=SimpleNamespace(SCENARIO='scenario'))
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<export patch method>', 'exec'), namespace)
        for corinth in (False, True):
            with self.subTest(corinth=corinth):
                patcher.reset_mock()
                exporter = SimpleNamespace(corinth=corinth, project_root=self.temp.name,
                                           asset_type=SimpleNamespace(supports_animations=False))
                self.assertEqual(namespace['_memory_tool_patches'](exporter), [record])
                patcher.skip_import_source_data.assert_called_once_with(return_patches=True)
                self.assertEqual(patcher.reach_skip_vertex_compression.call_count, int(not corinth))


if __name__ == '__main__':
    unittest.main()

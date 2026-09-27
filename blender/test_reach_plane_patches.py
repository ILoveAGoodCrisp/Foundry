"""Run without Blender: python blender/test_reach_plane_patches.py."""
import ast
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest


# Instruction windows captured from Reach's July 16 2023 executables at the
# assertion descriptors for connected_geometry_plane_builder.cpp:967-969.
# The final byte is the instruction at the original successful branch target.
WINDOWS = {
    'tool.exe': [
        (0x220CE5, '77 1b 48 8d 0d da c7 9f 01 e8 cd 83 5d 00 f3 0f 10 5e 38 f3 0f 10 56 30 f3 0f 10 66 34 48'),
        (0x220D55, '77 1b 48 8d 0d ea c7 9f 01 e8 5d 83 5d 00 f3 0f 10 5e 38 f3 0f 10 56 30 f3 0f 10 66 34 f3'),
        (0x220DBB, '77 0c 48 8d 0d 04 c8 9f 01 e8 f7 82 5d 00 80'),
    ],
    'tool_fast.exe': [
        (0x19A9B3, '77 1e 48 8d 0d fc 82 36 01 e8 93 d4 1e 00 f3 41 0f 10 5e 38 f3 41 0f 10 56 30 f3 41 0f 10 66 34 48'),
        (0x19AA27, '77 1e 48 8d 0d 70 82 36 01 e8 1f d4 1e 00 f3 41 0f 10 5e 38 f3 41 0f 10 56 30 f3 41 0f 10 66 34 f3'),
        (0x19AA91, '77 0c 48 8d 0d 4e 82 36 01 e8 b5 d3 1e 00 41'),
    ],
}


class ReachPlanePatchTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parent / 'addons/io_scene_foundry/patches.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        self.prefs = SimpleNamespace(allow_tool_patches=True)
        namespace = dict(Path=Path, __package__='test', bpy=SimpleNamespace(
            context=SimpleNamespace(preferences=SimpleNamespace(addons={
                'test': SimpleNamespace(preferences=self.prefs)}))))
        nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ToolPatcher']
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        self.patcher = namespace['ToolPatcher']

    def test_all_three_assertion_calls_are_skipped_in_both_tools(self):
        for name, windows in WINDOWS.items():
            with self.subTest(tool=name):
                records = self.patcher(name).reach_plane_builder(return_patches=True)
                for start, hex_bytes in windows:
                    original = bytes.fromhex(hex_bytes)
                    patched = bytearray(original)
                    for offset, replacement, expected in records:
                        if start <= offset < start + len(original):
                            index = offset - start
                            self.assertEqual(patched[index:index + len(expected)], expected)
                            patched[index:index + len(replacement)] = replacement
                    self.assertEqual(patched[0], 0xEB, f'{name}: assertion at {start:#x} still reachable')
                    self.assertEqual(patched[1:], original[1:])
                    self.assertEqual(2 + patched[1], len(patched) - 1)

    def test_disabled_patch_returns_no_memory_writes(self):
        for name in WINDOWS:
            self.assertEqual(self.patcher(name).reach_plane_builder(False, return_patches=True), [])
        self.prefs.allow_tool_patches = False
        for name in WINDOWS:
            self.assertEqual(self.patcher(name).reach_plane_builder(return_patches=True), [])

    def test_disk_toggle_is_reversible_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in WINDOWS:
                path = Path(directory) / name
                patcher = self.patcher(path)
                records = patcher.reach_plane_builder(return_patches=True)
                data = bytearray(max(offset + len(original) for offset, _, original in records))
                for offset, _, original in records:
                    data[offset:offset + len(original)] = original
                path.write_bytes(data)
                patcher.reach_plane_builder()
                first = path.read_bytes()
                for offset, replacement, _ in records:
                    self.assertEqual(first[offset:offset + len(replacement)], replacement)
                patcher.reach_plane_builder()
                self.assertEqual(path.read_bytes(), first)
                patcher.reach_plane_builder(False)
                self.assertEqual(path.read_bytes(), data)


if __name__ == '__main__':
    unittest.main()

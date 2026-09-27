"""Run without Blender: python blender/test_export_output.py."""
import ast
from contextlib import nullcontext
import ctypes
from ctypes import wintypes
from pathlib import Path
import re
import runpy
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


ADDON = Path(__file__).resolve().parent / 'addons/io_scene_foundry'


def legacy_api(namespace):
    path = ADDON / 'export/legacy.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    methods = {'legacy_shader_name', 'ensure_halo1_shaders'}
    functions = {'filename', 'write_outputs'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in functions]
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == 'LegacyExportScene':
            nodes.extend(method for method in node.body if isinstance(method, ast.FunctionDef) and method.name in methods)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return SimpleNamespace(**namespace)


class ShaderOutputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = Mock()
        self.utils = SimpleNamespace(relative_path=lambda p: str(Path(p).relative_to(self.root))
                                     if Path(p).is_absolute() else p,
                                     copy_file=Mock(side_effect=shutil.copyfile))
        self.api = legacy_api(dict(Path=Path, re=re, utils=self.utils, print=self.log,
                                   ExportCancelled=ValueError))
        self.scene = SimpleNamespace(tags_dir=self.root, target_game='halo1',
                                     shader_name_cache={}, warned_shader_paths=set(), warnings=[],
                                     shader_collections=SimpleNamespace(material_name=lambda p: Path(p).stem))

    def test_virtual_shader_classes_are_validated_and_cached_separately(self):
        for shader_type in ('shader_environment', 'shader_transparent_water', 'shader_transparent_glass'):
            (self.root / ('water.' + shader_type)).touch()
            mat = SimpleNamespace(name='water', shader_path='water', shader_type=shader_type)
            self.assertEqual(self.api.legacy_shader_name(self.scene, mat), 'water')
        self.assertEqual(self.scene.warnings, [])
        self.assertEqual(len(self.scene.shader_name_cache), 3)
        missing = SimpleNamespace(name='water', shader_path='water', shader_type='shader_model')
        self.api.legacy_shader_name(self.scene, missing)
        self.api.legacy_shader_name(self.scene, missing)
        self.assertEqual(len(self.scene.warnings), 1)

    def test_copy_logged_once_only_when_source_differs(self):
        source = self.root / 'original.shader_environment'
        source.write_text('shader bytes')
        mat = SimpleNamespace(name='original', nwo=SimpleNamespace(shader_path=source.name))
        self.scene.asset_path_relative = 'asset'
        self.scene.ob_halo_data = [SimpleNamespace(material_slots=[SimpleNamespace(material=mat)])]
        # Both BSPs reference the same shader.
        self.api.ensure_halo1_shaders.__globals__['jms'] = SimpleNamespace(JMS=SimpleNamespace(
            from_file=lambda _: SimpleNamespace(materials=[SimpleNamespace(name='original')])) )
        self.api.ensure_halo1_shaders(self.scene, [Path('a.jms'), Path('b.jms')], 'shader_environment')
        self.assertEqual(self.utils.copy_file.call_count, 1)
        self.assertEqual(self.log.call_count, 1)
        self.log.reset_mock()
        self.api.ensure_halo1_shaders(self.scene, [Path('a.jms')], 'shader_environment')
        self.log.assert_not_called()
        self.assertEqual(self.scene.warnings, [])


class IntermediaryOutputTests(unittest.TestCase):
    def test_validation_failure_preserves_existing_batch_and_reports_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory, name) for name in ('a.jms', 'b.jms')]
            for path in paths:
                path.write_text('original')
            messages = []

            class JMS:
                @staticmethod
                def from_file(path):
                    self.assertEqual(messages[-1][0], '--- Writing Intermediary Files')
                    self.assertEqual(path.read_text(), 'new')
                    if path.name.startswith('b.jms.'):
                        raise ValueError('invalid geometry')

            def write_jms(asset, stream, **kwargs):
                self.assertEqual(messages[-1][0], '--- Writing Intermediary Files')
                stream.write('new')

            api = legacy_api(dict(Path=Path, NamedTemporaryFile=tempfile.NamedTemporaryFile,
                jms=SimpleNamespace(JMS=JMS), ass=SimpleNamespace(ASS=type('ASS', (), {})),
                write_jms=write_jms, print=Mock(),
                foundry_output=SimpleNamespace(_raise_if_cancel_requested=Mock()),
                utils=SimpleNamespace(Spinner=nullcontext,
                    update_job_count=lambda *args: messages.append(args))))
            with self.assertRaisesRegex(ValueError, 'invalid geometry'):
                api.write_outputs([(path, JMS()) for path in paths])
            self.assertTrue(all(path.read_text() == 'original' for path in paths))
            self.assertEqual(set(Path(directory).iterdir()), set(paths))
            self.assertEqual(messages, [
                ('--- Writing Intermediary Files', '', 0, 2),
                ('--- Writing Intermediary Files', '', 1, 2),
            ])
            api.print.assert_not_called()

    def test_cancel_during_final_validation_preserves_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory, name) for name in ('a.jms', 'b.jms')]
            for path in paths:
                path.write_text('original')
            cancelled = False

            class JMS:
                @staticmethod
                def from_file(path):
                    nonlocal cancelled
                    if path.name.startswith('b.jms.'):
                        cancelled = True

            def check_cancel():
                if cancelled:
                    raise KeyboardInterrupt

            api = legacy_api(dict(Path=Path, NamedTemporaryFile=tempfile.NamedTemporaryFile,
                jms=SimpleNamespace(JMS=JMS), ass=SimpleNamespace(ASS=type('ASS', (), {})),
                write_jms=lambda asset, stream, **kw: stream.write('new'),
                foundry_output=SimpleNamespace(_raise_if_cancel_requested=check_cancel),
                utils=SimpleNamespace(Spinner=nullcontext, update_job_count=Mock())))
            with self.assertRaises(KeyboardInterrupt):
                api.write_outputs([(path, JMS()) for path in paths])
            self.assertTrue(all(path.read_text() == 'original' for path in paths))
            self.assertEqual(set(Path(directory).iterdir()), set(paths))


@unittest.skipUnless(sys.platform == 'win32', 'Native Windows output viewer')
class CancellationStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = SimpleNamespace(**runpy.run_path(str(ADDON / 'foundry_output_viewer.pyw')))

    def test_unicode_export_banner_is_active(self):
        status = self.v.ExportStatus()
        status.feed('\u25ba\u25ba\u25ba SCENARIO EXPORT \u25c4\u25c4\u25c4\n')
        self.assertEqual(status.state, 'active')

    def test_progress_without_newline_is_active(self):
        for stage in ('Preparing', 'Writing'):
            status = self.v.ExportStatus()
            # Feed in small chunks, as the viewer's file tailer can do.
            for character in f'\r--- {stage} Intermediary Files (8 / 13)|':
                status.feed(character)
            self.assertEqual(status.state, 'active')
            status.feed('\r--- Other phase')
            self.assertEqual(status.state, 'active')

    def test_cancel_reads_pending_progress_and_requests_cancellation(self):
        v = self.v
        window = v.FoundryOutputWindow.__new__(v.FoundryOutputWindow)
        window.export_status = v.ExportStatus()
        window.output = v.BonoboOutput()
        window._update_output = lambda: window.export_status.feed(
            '\r--- Preparing Intermediary Files (8 / 13)|')
        window._render_output = Mock()
        window._update_status_controls = Mock()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'cancel.request')
            window.arguments = SimpleNamespace(parent_pid=0, cancel=str(path))
            window._window_proc(0, v.WM_COMMAND, v.BUTTON_CANCEL, 0)
            self.assertTrue(path.read_text())
            self.assertIn('Cancelling', window.export_status.status)

    def test_clear_keeps_active_export_cancellable(self):
        v = self.v
        window = v.FoundryOutputWindow.__new__(v.FoundryOutputWindow)
        window.export_status = v.ExportStatus()
        window.export_status.feed('>>> SCENARIO EXPORT <<<\n')
        window.output = v.BonoboOutput()
        window.collapsed_message_nodes = set()
        window._render_output = Mock()
        window._update_status_controls = Mock()
        window._window_proc(0, v.WM_COMMAND, v.BUTTON_CLEAR, 0)
        self.assertEqual(window.export_status.state, 'active')


@unittest.skipUnless(sys.platform == 'win32', 'Native Windows output control')
class ScrollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v = SimpleNamespace(**runpy.run_path(str(ADDON / 'foundry_output_viewer.pyw')))

    def setUp(self):
        v = self.v
        self.parent = v.user32.CreateWindowExW(0, 'STATIC', '', v.WS_OVERLAPPEDWINDOW,
                                               0, 0, 400, 200, None, None, None, None)
        self.addCleanup(v.user32.DestroyWindow, self.parent)
        self.window = v.FoundryOutputWindow.__new__(v.FoundryOutputWindow)
        w = self.window
        w.edit = v.user32.CreateWindowExW(0, v.OUTPUT_CONTROL_CLASS, '',
            v.WS_CHILD | v.WS_VISIBLE | v.WS_VSCROLL | v.WS_HSCROLL | v.ES_MULTILINE |
            v.ES_AUTOVSCROLL | v.ES_AUTOHSCROLL | v.ES_READONLY,
            0, 0, 380, 150, self.parent, None, None, None)
        self.assertTrue(w.edit)
        w.output = v.BonoboOutput()
        w.output.feed(''.join(f'Line {i}\n' for i in range(200)))
        w.enabled_levels = {'message', 'warning', 'error'}
        w.show_messages = False
        w.collapsed_message_nodes = set()
        w._update_filter_summary = Mock()
        w._render_output(scroll_to_end=True)

    def position(self):
        point = wintypes.POINT()
        self.v.user32.SendMessageW(self.window.edit, self.v.EM_GETSCROLLPOS, 0, ctypes.addressof(point))
        return point.x, point.y

    def test_scrolled_view_and_selection_survive_new_output(self):
        w, v = self.window, self.v
        v.user32.SendMessageW(w.edit, v.EM_SETSEL, 20, 30)
        point = wintypes.POINT(0, 100)
        v.user32.SendMessageW(w.edit, v.EM_SETSCROLLPOS, 0, ctypes.addressof(point))
        before = self.position()
        w.output.feed('Additional output\n')
        w._render_output()
        self.assertEqual(self.position(), before)
        start, end = wintypes.DWORD(), wintypes.DWORD()
        v.user32.SendMessageW(w.edit, v.EM_GETSEL, ctypes.addressof(start), ctypes.addressof(end))
        self.assertEqual((start.value, end.value), (20, 30))

    def test_bottom_follows_new_output(self):
        before = self.position()[1]
        self.window.output.feed(''.join(f'New line {i}\n' for i in range(20)))
        self.window._render_output()
        self.assertGreater(self.position()[1], before)

    def test_scrolled_view_without_selection_stays_put(self):
        v, w = self.v, self.window
        point = wintypes.POINT(0, 100)
        v.user32.SendMessageW(w.edit, v.EM_SETSCROLLPOS, 0, ctypes.addressof(point))
        before = self.position()
        w.output.feed('More output\n')
        w._render_output()
        self.assertEqual(self.position(), before)

    def test_refresh_waits_until_drag_released(self):
        v, w = self.v, self.window
        w.sources = SimpleNamespace(read_new=Mock(side_effect=[ [('Foundry', 'new output\n')], [] ]))
        w.export_status = v.ExportStatus()
        w._update_status_controls = Mock()
        w._render_output = Mock()
        w.output_dirty = False
        v.user32.SetCapture.argtypes = [wintypes.HWND]
        v.user32.SetCapture.restype = wintypes.HWND
        v.user32.SetCapture(w.edit)
        try:
            w._update_output()
            w._render_output.assert_not_called()
            self.assertTrue(w.output_dirty)
        finally:
            v.user32.ReleaseCapture()
        w._update_output()
        w._render_output.assert_called_once()


if __name__ == '__main__':
    unittest.main()

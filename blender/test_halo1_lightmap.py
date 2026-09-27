"""Run without Blender: python blender/test_halo1_lightmap.py."""

import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import importlib.util
import os
from pathlib import Path
import math
import subprocess
import sys
import tempfile
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ADDON = Path(__file__).resolve().parent / 'addons/io_scene_foundry'


def load_functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(tree, str(path), 'exec'), namespace)
    return SimpleNamespace(**{name: namespace[name] for name in names})


class LightmapTests(unittest.TestCase):
    def setUp(self):
        self.utils = SimpleNamespace(run_tool=Mock(), prepare_tool=Mock(), print_error=Mock())
        self.cpu_count = Mock(return_value=2)
        self.api = load_functions(ADDON / 'tools/scenario/lightmap.py', {
            'halo1_lightmap_commands', 'run_halo1_lightmapper',
            'tool_error_code', 'ulong_to_long_sub',
        }, dict(math=math, utils=self.utils, os=SimpleNamespace(cpu_count=self.cpu_count),
                ThreadPoolExecutor=ThreadPoolExecutor, as_completed=as_completed,
                CalledProcessError=subprocess.CalledProcessError, print=Mock()))
        self.settings = SimpleNamespace(lightmap_quality_h1='1',
                                        lightmap_stop_threshold_h1=0.01,
                                        lightmap_noassert_h1=True, event_level='DEFAULT')

    def run_lightmap(self, bsps):
        self.api.run_halo1_lightmapper(r'levels\test\test', bsps, self.settings)

    def test_jobs_overlap_and_prepare_on_main_thread(self):
        barrier = threading.Barrier(2)
        lock = threading.Lock()
        completed = []
        prepared = []
        active = 0
        peak = 0

        def prepare(command, **kwargs):
            self.assertIs(threading.current_thread(), threading.main_thread())
            self.assertEqual(kwargs, dict(force_tool=True, console_output=True, event_level='DEFAULT'))
            self.assertEqual(command, ['lightmaps', r'levels\test\test', command[2], '1', '0.01', '-noassert'])
            prepared.append(command[2])

            def run():
                nonlocal active, peak
                self.assertIsNot(threading.current_thread(), threading.main_thread())
                self.assertEqual(len(prepared), 4)
                with lock:
                    active += 1
                    peak = max(peak, active)
                barrier.wait(timeout=5)
                with lock:
                    completed.append(command[2])
                    active -= 1
            return run

        self.utils.prepare_tool.side_effect = prepare
        self.run_lightmap(['a', 'b', 'c', 'd'])
        self.assertCountEqual(completed, ['a', 'b', 'c', 'd'])
        self.assertEqual(peak, 2)
        self.utils.run_tool.assert_not_called()

    def test_single_bsp_keeps_foreground_runner(self):
        self.run_lightmap(['a'])
        self.utils.run_tool.assert_called_once_with(
            ['lightmaps', r'levels\test\test', 'a', '1', '0.01', '-noassert'],
            force_tool=True, console_output=True, event_level='DEFAULT')
        self.utils.prepare_tool.assert_not_called()

    def test_failure_propagates_and_running_job_finishes(self):
        barrier = threading.Barrier(2)
        finished = threading.Event()
        error = subprocess.CalledProcessError(7, ['tool.exe', 'lightmaps'])

        def prepare(command, **kwargs):
            def run():
                barrier.wait(timeout=5)
                if command[2] == 'bad':
                    raise error
                finished.set()
            return run

        self.utils.prepare_tool.side_effect = prepare
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            self.run_lightmap(['bad', 'good'])
        self.assertIs(caught.exception, error)
        self.assertTrue(finished.is_set())
        self.assertIn('BSP bad', self.utils.print_error.call_args.args[0])

    def test_unknown_cpu_count_runs_all_jobs(self):
        self.cpu_count.return_value = None
        runners = [Mock(), Mock()]
        self.utils.prepare_tool.side_effect = runners
        self.run_lightmap(['a', 'b'])
        for runner in runners:
            runner.assert_called_once_with()

    def test_invalid_selection_does_not_launch_tool(self):
        for bsps in ([], ['a', '']):
            with self.subTest(bsps=bsps), self.assertRaises(ValueError):
                self.run_lightmap(bsps)
        self.utils.prepare_tool.assert_not_called()
        self.utils.run_tool.assert_not_called()


class ToolPreparationTests(unittest.TestCase):
    def test_console_is_deferred_but_run_tool_still_runs_immediately(self):
        console = ModuleType('_lightmap_prepare_test.console_process')
        console.run_console_command = Mock(return_value=0)
        api = load_functions(ADDON / 'utils.py', {'run_tool', 'prepare_tool'}, dict(
            __package__='_lightmap_prepare_test',
            os=SimpleNamespace(name='nt', chdir=Mock()), Path=Path, partial=partial,
            get_project_path=Mock(return_value='/kit'), is_corinth=Mock(return_value=False),
            foundry_output=SimpleNamespace(child_stream=Mock(return_value='output'))))
        with patch.dict(sys.modules, {'_lightmap_prepare_test.console_process': console}):
            run = api.prepare_tool(['lightmaps', 'scenario', 'bsp', '0', '0.1'],
                                   force_tool=True, console_output=True)
            console.run_console_command.assert_not_called()
            self.assertEqual(run(), 0)
            console.run_console_command.assert_called_once_with(
                [str(Path('/kit/tool.exe')), 'lightmaps', 'scenario', 'bsp', '0', '0.1'],
                '/kit', 'output')
            console.run_console_command.reset_mock()
            self.assertEqual(api.run_tool(['lightmaps'], force_tool=True, console_output=True), 0)
            console.run_console_command.assert_called_once()

    def test_prepared_runner_uses_captured_settings(self):
        fake_os = SimpleNamespace(name='posix', chdir=Mock())
        project = Mock(return_value='/kit')
        corinth = Mock(return_value=False)
        output = SimpleNamespace(child_stream=Mock(return_value='output'))
        event_level = Mock()
        check_call = Mock(return_value=0)
        api = load_functions(ADDON / 'utils.py', {
            'run_tool', 'prepare_tool', '_run_prepared_tool',
        }, dict(os=fake_os, Path=Path, partial=partial, tempfile=tempfile,
                get_project_path=project, is_corinth=corinth,
                foundry_output=output, set_tool_event_level=event_level,
                _check_call_tool=check_call))
        command = ['lightmaps', 'scenario', 'bsp', '0', '0.1']
        run = api.prepare_tool(command, force_tool=True, event_level='WARNING')
        check_call.assert_not_called()
        event_level.assert_called_once_with('WARNING')
        command[2] = 'changed'
        project.side_effect = AssertionError('Worker accessed Blender')
        corinth.side_effect = AssertionError('Worker accessed Blender')
        with ThreadPoolExecutor(max_workers=1) as executor:
            self.assertEqual(executor.submit(run).result(timeout=5), 0)
        check_call.assert_called_once_with(
            [str(Path('/kit/tool.exe')), 'lightmaps', 'scenario', 'bsp', '0', '0.1'],
            '/kit', stdout='output', stderr='output', tool_patches=None, input_data=None)
        fake_os.chdir.assert_called_once_with('/kit')


@unittest.skipUnless(os.name == 'nt', 'Windows console integration')
class ConsoleTests(unittest.TestCase):
    def test_concurrent_console_processes_keep_output_and_exit_codes(self):
        package = ModuleType('_lightmap_console_test')
        package.__path__ = [str(ADDON)]
        package.foundry_output = SimpleNamespace(register_tool_process_handle=Mock())
        spec = importlib.util.spec_from_file_location(
            '_lightmap_console_test.console_process', ADDON / 'console_process.py')
        console = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'_lightmap_console_test': package}):
            spec.loader.exec_module(console)

        # Each child must observe the other child running before it can finish.
        script = (
            'from pathlib import Path; import sys, time\n'
            'own, other, result = sys.argv[1:]\n'
            'Path(own).touch()\n'
            'deadline = time.monotonic() + 10\n'
            'while not Path(other).exists():\n'
            '    if time.monotonic() > deadline: sys.exit(99)\n'
            '    time.sleep(0.01)\n'
            'with open("CONOUT$", "w") as console:\n'
            '    print("finished-" + own, file=console, flush=True)\n'
            'sys.exit(int(result))\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            with tempfile.TemporaryFile() as output:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    success = executor.submit(console.run_console_command,
                        [sys.executable, '-c', script, 'a', 'b', '0'], directory, output)
                    failure = executor.submit(console.run_console_command,
                        [sys.executable, '-c', script, 'b', 'a', '7'], directory, output)
                    self.assertEqual(success.result(timeout=20), 0)
                    with self.assertRaises(subprocess.CalledProcessError) as caught:
                        failure.result(timeout=20)
                    self.assertEqual(caught.exception.returncode, 7)
                output.seek(0)
                text = output.read()
                self.assertIn(b'finished-a', text)
                self.assertIn(b'finished-b', text)
        self.assertEqual(package.foundry_output.register_tool_process_handle.call_count, 2)


if __name__ == '__main__':
    unittest.main()

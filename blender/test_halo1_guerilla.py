"""Run without Blender: python blender/test_halo1_guerilla.py."""

import ast
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


TOOLS = Path(__file__).resolve().parent / "addons/io_scene_foundry/tools"
spec = importlib.util.spec_from_file_location("halo1_guerilla", TOOLS / "halo1_guerilla.py")
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)
MAIN = struct.pack("<11i", 44, 0, 1, -1, -1, -1, -1, 204, 184, 2124, 1207)
CHILD = struct.pack("<11i", 44, 0, 1, -1, -1, -1, -1, 0, 0, 670, 960)
PATH_A = r"C:\kit\tags\levels\a30\a30_a.bitmap"
PATH_B = r"C:\kit\tags\levels\a30\a30_b.scenario_structure_bsp"
END = b"\0" * 4


def record(path, state=(0, -1, 0), unicode=False):
    text = (b"\xff\xfe\xff" + bytes([len(path)]) + path.encode("utf-16-le")
            if unicode else bytes([len(path)]) + path.encode("ascii"))
    return (b"\x01\0\0\0" + CHILD + text + struct.pack("<iiH", 7, 11, len(state))
            + struct.pack("<" + "i" * len(state), *state))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.a = record(PATH_A)
        self.b = record(PATH_B, (0, -1) * 26 + (0,))
        self.original = MAIN + self.a + self.b + END

    def test_exact_round_trip(self):
        self.assertEqual(cfg.build_config(self.original, [PATH_A, PATH_B]), self.original)

    def test_reorder_remove_and_deduplicate(self):
        self.assertEqual(cfg.build_config(self.original, [PATH_B, PATH_B.upper()]), MAIN + self.b + END)
        self.assertEqual(cfg.build_config(self.original, [PATH_B, PATH_A]), MAIN + self.b + self.a + END)

    def test_clear_list(self):
        self.assertEqual(cfg.build_config(self.original, []), MAIN + END)

    def test_new_tag(self):
        data = cfg.build_config(None, [PATH_A])
        self.assertEqual(struct.unpack_from("<I", data)[0], 44)
        self.assertEqual(data[44:48], b"\x01\0\0\0")
        self.assertEqual(data[92], len(PATH_A))
        self.assertEqual(data[93:93 + len(PATH_A)], PATH_A.encode("ascii"))
        self.assertEqual(data[93 + len(PATH_A):], b"\0" * 14)

    def test_path_length_boundaries(self):
        for length, prefix in [(254, b"\xfe"), (255, b"\xff\xff\x00"),
                               (65533, b"\xff\xfd\xff"),
                               (65534, b"\xff\xff\xff\xfe\xff\0\0")]:
            with self.subTest(length=length):
                path = "C:\\" + "a" * (length - 3)
                data = cfg.build_config(None, [path])
                self.assertEqual(data[92:92 + len(prefix)], prefix)
                self.assertEqual(cfg.build_config(data, [path]), data)

    def test_unicode_saved_record(self):
        path = r"C:\kit\tags\café.bitmap"
        data = MAIN + record(path, unicode=True) + END
        self.assertEqual(cfg.build_config(data, [path]), data)

    def test_unrepresentable_path(self):
        with patch.object(cfg, "_PATH_ENCODING", "ascii"), self.assertRaises(UnicodeError):
            cfg.build_config(None, ["C:\\café.bitmap"])

    def test_truncation(self):
        for end in range(len(self.original)):
            with self.subTest(end=end), self.assertRaises(ValueError):
                cfg.build_config(self.original[:end], [PATH_A])

    def test_corruption(self):
        for data in [b"\0" * 44 + END, MAIN + struct.pack("<I", 2),
                     self.original + b"extra",
                     MAIN + self.a[:4] + b"\0" * 44 + self.a[48:] + END,
                     MAIN + self.a[:-14] + struct.pack("<H", 257) + END]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                cfg.build_config(data, [PATH_A])


class FileTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        (self.root / "guerilla.exe").touch()
        self.tag = self.root / "test.bitmap"
        self.tag.touch()
        self.config = self.root / "guerilla.cfg"
        self.backup = self.root / "guerilla.cfg.bak"
        self.config.write_bytes(MAIN + END)
        patcher = patch.object(cfg, "_guerilla_running", return_value=False)
        self.running = patcher.start()
        self.addCleanup(patcher.stop)

    def test_write_and_backup(self):
        cfg.prepare_guerilla_config(self.root, ["", self.tag, self.tag])
        self.assertEqual(self.backup.read_bytes(), MAIN + END)
        self.assertEqual(self.config.read_bytes(), cfg.build_config(MAIN + END, [self.tag]))
        self.assertEqual(len(list(self.root.glob("guerilla.cfg.*"))), 1)

    def test_no_previous_config(self):
        self.config.unlink()
        cfg.prepare_guerilla_config(self.root, [self.tag])
        self.assertTrue(self.config.is_file())
        self.assertFalse(self.backup.exists())

    def test_running_editor(self):
        self.running.return_value = True
        with self.assertRaisesRegex(OSError, "Close this project's Guerilla"):
            cfg.prepare_guerilla_config(self.root, [self.tag])
        self.assertEqual(self.config.read_bytes(), MAIN + END)
        self.assertFalse(self.backup.exists())

    def test_invalid_input_preserves_files(self):
        for contents, tag in [(b"broken", self.tag), (MAIN + END, self.root / "missing.bitmap")]:
            self.config.write_bytes(contents)
            with self.assertRaises((ValueError, OSError)):
                cfg.prepare_guerilla_config(self.root, [tag])
            self.assertEqual(self.config.read_bytes(), contents)
            self.assertFalse(self.backup.exists())

    def test_failed_replacement(self):
        with patch.object(cfg.os, "replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                cfg.prepare_guerilla_config(self.root, [self.tag])
        self.assertEqual(self.config.read_bytes(), MAIN + END)
        self.assertEqual(list(self.root.glob("guerilla.cfg.*")), [])


class LaunchTests(unittest.TestCase):
    def setUp(self):
        # Exercise the real routing function without importing Blender's UI.
        tree = ast.parse((TOOLS / "halo_launcher.py").read_text(encoding="utf-8"))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "_run_tag_editor")
        self.prepare, self.run, self.report = Mock(), Mock(), Mock()
        self.game = Mock(return_value="Halo1")
        namespace = dict(prepare_guerilla_config=self.prepare, run_ek_cmd=self.run,
                         project_game_for_mcc=self.game, get_project_path=lambda: "kit")
        exec(compile(ast.Module(body=[function], type_ignores=[]), "halo_launcher.py", "exec"), namespace)
        self.launch = namespace["_run_tag_editor"]

    def test_halo1_arguments_and_order(self):
        calls = Mock()
        calls.attach_mock(self.prepare, "prepare")
        calls.attach_mock(self.run, "run")
        self.assertTrue(self.launch(["guerilla.exe", PATH_A], None, self.report))
        self.prepare.assert_called_once_with("kit", [PATH_A])
        self.run.assert_called_once_with(["guerilla.exe"], True)
        self.assertEqual([call[0] for call in calls.mock_calls], ["prepare", "run"])

    def test_default_launch(self):
        self.launch(["guerilla.exe"], None, self.report, load_tags=False)
        self.prepare.assert_not_called()
        self.run.assert_called_once_with(["guerilla.exe"], True)

    def test_empty_asset_selection(self):
        self.launch(["guerilla.exe", ""], None, self.report)
        self.prepare.assert_called_once_with("kit", [""])

    def test_write_failure_cancels_launch(self):
        self.prepare.side_effect = ValueError("bad config")
        self.assertFalse(self.launch(["guerilla.exe", PATH_A], None, self.report))
        self.run.assert_not_called()
        self.report.assert_called_once_with({"ERROR"}, "Could not prepare Guerilla: bad config")

    def test_other_games(self):
        for game, executable in [("Halo2", "guerilla.exe"), ("Halo3", "guerilla.exe"),
                                 ("Halo3ODST", "guerilla.exe"), ("HaloReach", "Foundation.exe")]:
            with self.subTest(game=game):
                self.game.return_value = game
                args = [executable, PATH_A]
                self.assertTrue(self.launch(args, None, self.report))
                self.run.assert_called_with(args, True)
        self.prepare.assert_not_called()


class MaterialLaunchTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        (self.root / "guerilla.exe").touch()
        self.tag = self.root / "test.shader_environment"
        self.tag.touch()
        self.config = self.root / "guerilla.cfg"
        self.config.write_bytes(MAIN + record(PATH_A) + END)
        self.original = self.config.read_bytes()
        patcher = patch.object(cfg, "_guerilla_running", return_value=False)
        self.running = patcher.start()
        self.addCleanup(patcher.stop)
        self.game = Mock(return_value="Halo1")
        self.run = Mock()

        # Use the actual material operator and shared launch functions. Only
        # Blender registration, process lookup and process launch are replaced.
        launcher = ModuleType("test_foundry.tools.halo_launcher")
        launcher.__dict__.update(
            prepare_guerilla_config=cfg.prepare_guerilla_config,
            project_game_for_mcc=self.game, get_project_path=lambda: self.root,
            run_ek_cmd=self.run, GUERILLA_GAMES={"Halo1", "Halo2", "Halo3", "Halo3ODST"},
        )
        tree = ast.parse((TOOLS / "halo_launcher.py").read_text(encoding="utf-8"))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in {"tag_editor_executable", "_run_tag_editor", "open_tag_in_editor"}]
        exec(compile(ast.Module(body=functions, type_ignores=[]), "halo_launcher.py", "exec"), launcher.__dict__)
        modules = patch.dict(sys.modules, {launcher.__name__: launcher})
        modules.start()
        self.addCleanup(modules.stop)
        material_path = TOOLS.parent / "ui/panel/material.py"
        tree = ast.parse(material_path.read_text(encoding="utf-8"))
        operator = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                        and node.name == "NWO_OT_MaterialOpenTag")
        namespace = dict(
            __package__="test_foundry.ui.panel", Path=Path,
            bpy=SimpleNamespace(types=SimpleNamespace(Operator=object)),
            utils=SimpleNamespace(get_tags_path=lambda: self.root, is_corinth=lambda context: False),
        )
        exec(compile(ast.Module(body=[operator], type_ignores=[]), str(material_path), "exec"), namespace)
        self.operator = namespace[operator.name]()
        self.operator.report = Mock()
        self.context = Mock()
        self.context.object.active_material.nwo.shader_path = self.tag.name

    def test_shader_button_writes_config_before_launch(self):
        expected = cfg.build_config(self.original, [self.tag])
        self.run.side_effect = lambda *args: self.assertEqual(self.config.read_bytes(), expected)
        self.assertEqual(self.operator.execute(self.context), {"FINISHED"})
        self.run.assert_called_once_with(["guerilla.exe"], True)
        self.assertNotEqual(self.config.read_bytes(), self.original)
        self.assertEqual((self.root / "guerilla.cfg.bak").read_bytes(), self.original)

    def test_running_guerilla_reports_and_cancels(self):
        self.running.return_value = True
        self.assertEqual(self.operator.execute(self.context), {"CANCELLED"})
        self.run.assert_not_called()
        self.assertEqual(self.config.read_bytes(), self.original)
        self.operator.report.assert_called_once()
        self.assertIn("Close this project's Guerilla", self.operator.report.call_args.args[1])

    def test_other_games_preserve_launch_arguments(self):
        for game, args in [("Halo2", ["guerilla.exe", str(self.tag)]),
                           ("HaloReach", ["Foundation.exe", "/dontloadlastopenedwindows", str(self.tag)])]:
            with self.subTest(game=game):
                self.game.return_value = game
                self.assertEqual(self.operator.execute(self.context), {"FINISHED"})
                self.run.assert_called_with(args, True)
                self.assertEqual(self.config.read_bytes(), self.original)


class Halo1AssetOptionsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.scene = SimpleNamespace(asset_directory="", asset_name="test", output_biped=True,
                                     output_crate=True, output_giant=True)
        tree = ast.parse((TOOLS / "halo_launcher.py").read_text(encoding="utf-8"))
        names = {"halo1_tag_editor_options", "_halo1_asset_tags", "get_tag_if_exists"}
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = dict(Path=Path, get_tags_path=lambda: self.root)
        exec(compile(ast.Module(body=functions, type_ignores=[]), "halo_launcher.py", "exec"), namespace)
        self.options = namespace["halo1_tag_editor_options"]
        self.collect = namespace["_halo1_asset_tags"]

    def test_model_options_open_h1_files_and_ignore_obsolete_flags(self):
        options = self.options("model", self.scene)
        extensions = [entry[2] for entry in options]
        self.assertEqual(extensions, ["model", "gbxmodel", "model_collision_geometry",
                                      "physics", "model_animations", "biped"])
        for extension in extensions + ["frame_event_list", "render_model", "crate", "giant"]:
            (self.root / f"test.{extension}").touch()
        settings = SimpleNamespace(**{prop: True for prop, _, _ in options},
                                   open_frame_event_list=True, open_crate=True, open_giant=True)
        self.assertEqual({Path(path).suffix[1:] for path in self.collect(settings, self.scene, "model")},
                         set(extensions))

    def test_sky_and_animation_extensions(self):
        for asset_type, expected in [("sky", ["model", "gbxmodel", "sky"]),
                                     ("animation", ["model_animations"])]:
            options = self.options(asset_type, self.scene)
            self.assertEqual([entry[2] for entry in options], expected)
            for extension in expected:
                (self.root / f"test.{extension}").touch()
            settings = SimpleNamespace(**{prop: True for prop, _, _ in options})
            self.assertEqual({Path(path).suffix[1:] for path in self.collect(settings, self.scene, asset_type)},
                             set(expected))

    def test_scenario_bsp_selection(self):
        for name in ["test.scenario", "a.scenario_structure_bsp", "b.scenario_structure_bsp",
                     "test.scenario_lightmap_bsp_data"]:
            (self.root / name).touch()
        settings = SimpleNamespace(open_scenario=True, open_scenario_structure_bsp=True, bsp_name="",
                                   open_scenario_lightmap_bsp_data=True)
        paths = self.collect(settings, self.scene, "scenario")
        self.assertEqual({Path(path).name for path in paths},
                         {"test.scenario", "a.scenario_structure_bsp", "b.scenario_structure_bsp"})
        settings.bsp_name = "b"
        self.assertEqual({Path(path).name for path in self.collect(settings, self.scene, "scenario")},
                         {"test.scenario", "b.scenario_structure_bsp"})


if __name__ == "__main__":
    unittest.main()

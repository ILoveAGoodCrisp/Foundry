import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import bpy


_CREATE_NO_WINDOW = 0x08000000
_SW_RESTORE = 9
_SESSION_DIRECTORY = Path(tempfile.gettempdir(), "foundry_output", str(os.getpid()))
_LOG_PATH = _SESSION_DIRECTORY / "foundry.log"
_WATCH_PATH = _SESSION_DIRECTORY / "watched_logs.jsonl"
_CANCEL_PATH = _SESSION_DIRECTORY / "cancel.request"
_VIEWER_PATH = Path(__file__).with_name("foundry_output_viewer.pyw")
_WINDOW_TITLE = f"Foundry - {os.getpid()}"
_TOOL_JOB_NAME = f"Foundry.ToolProcesses.{os.getpid()}"

_log_stream = None
_stdout_proxy = None
_stderr_proxy = None
_viewer_process = None
_write_lock = threading.RLock()
_watched_paths = set()
_mute_depth = 0
_tool_job_handle = None
_tool_kernel32 = None
_cancel_monitor = None


def _ensure_tool_job():
    global _tool_job_handle, _tool_kernel32
    if os.name != "nt":
        return None
    with _write_lock:
        if _tool_job_handle:
            return _tool_job_handle
        if _tool_kernel32 is None:
            _tool_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _tool_kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            _tool_kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            _tool_kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            _tool_kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            _tool_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        _tool_job_handle = _tool_kernel32.CreateJobObjectW(None, _TOOL_JOB_NAME)
        return _tool_job_handle


def register_tool_process_handle(process_handle):
    """Place a Tool process in the cancelable job shared with the output viewer."""
    if os.name != "nt" or not process_handle:
        return False
    job_handle = _ensure_tool_job()
    if not job_handle:
        return False
    return bool(_tool_kernel32.AssignProcessToJobObject(job_handle, wintypes.HANDLE(process_handle)))


def register_tool_process(process):
    process_handle = getattr(process, "_process_handle", None)
    if process_handle is None:
        process_handle = getattr(process, "_handle", None)
    return register_tool_process_handle(process_handle)


def _consume_cancel_request():
    with _write_lock:
        try:
            requested = _CANCEL_PATH.read_text(encoding="utf-8").strip()
            if not requested:
                return False
            _CANCEL_PATH.write_text("", encoding="utf-8")
        except OSError:
            return False
    return True


def _clear_cancel_request():
    with _write_lock:
        try:
            _CANCEL_PATH.write_text("", encoding="utf-8")
        except OSError:
            pass


class CancelMonitor:
    """Interrupt a main-thread import even when it produces no console output."""

    def __init__(self):
        self._thread = None
        self._state = "stopped"
        self._cancelled = False
        self._interrupt_failed = False
        self._target_ident = None
        # PYFUNCTYPE keeps the GIL while calling the Python C API. Blender's
        # native SIGINT handler is not a Python handler, so interrupt_main()
        # would not reliably raise KeyboardInterrupt in its embedded Python.
        self._set_async_exception = ctypes.PYFUNCTYPE(
            ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p,
        )(("PyThreadState_SetAsyncExc", ctypes.pythonapi))

    def start(self):
        global _cancel_monitor
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("Cancellation monitoring must start on Blender's main thread")
        if _cancel_monitor is not None:
            raise RuntimeError("Another import is already monitoring cancellation")
        _clear_cancel_request()
        self._target_ident = threading.get_ident()
        _cancel_monitor = self
        self._state = "starting"
        self._thread = threading.Thread(
            target=self._watch, name="Foundry import cancellation", daemon=True,
        )
        self._thread.start()
        self._state = "running"

    def _watch(self):
        while True:
            time.sleep(0.05)
            if self._state == "stopped":
                return
            if self._state != "running" or not _consume_cancel_request():
                continue
            # Only deliver one interrupt. Further clicks must not interrupt
            # the import's cancellation reporting or undo cleanup.
            self._cancelled = True
            affected = self._set_async_exception(self._target_ident, id(KeyboardInterrupt))
            if affected != 1:
                if affected > 1:
                    self._set_async_exception(self._target_ident, None)
                self._interrupt_failed = True
                try:
                    _CANCEL_PATH.write_text("cancel", encoding="utf-8")
                except OSError:
                    pass
            return

    def stop(self):
        """Disarm and join the watcher; return whether cancellation was requested."""
        # An interrupt can arrive just as normal work finishes. Complete the
        # shutdown before the caller reports cancellation, including in this race.
        # Do not acquire a watcher-owned lock here: interruption while acquiring
        # one can strand the lock and deadlock shutdown.
        while True:
            try:
                self._state = "stopped"
                if self._thread is not None and self._thread.ident is not None:
                    self._thread.join()
                return self._cancelled
            except KeyboardInterrupt:
                self._cancelled = True


    def close(self):
        """Release the cancellation guard after the import finishes reporting."""
        global _cancel_monitor
        while True:
            try:
                cancelled = self.stop()
                if _cancel_monitor is self:
                    _clear_cancel_request()
                    _cancel_monitor = None
                return cancelled
            except KeyboardInterrupt:
                self._cancelled = True


def _raise_if_cancel_requested():
    if threading.current_thread() is not threading.main_thread():
        return
    # The watcher owns the request during imports. Console writes must not race
    # it and deliver a second KeyboardInterrupt. Keep the fallback for exports.
    if _cancel_monitor is not None and not _cancel_monitor._interrupt_failed:
        return
    if _consume_cancel_request():
        if _cancel_monitor is not None:
            _cancel_monitor._interrupt_failed = False
        raise KeyboardInterrupt


class _BinaryOutputProxy:
    def __init__(self, owner, original):
        self.owner = owner
        self.original = original

    def write(self, data):
        if not data:
            return 0
        if not is_muted():
            if self.original is not None:
                try:
                    self.original.write(data)
                except (OSError, ValueError):
                    pass
            _write_bytes(bytes(data))
            _raise_if_cancel_requested()
        return len(data)

    def flush(self):
        if self.original is not None:
            try:
                self.original.flush()
            except (OSError, ValueError):
                pass

    def fileno(self):
        if self.original is None:
            raise OSError("Foundry output has no native file descriptor")
        return self.original.fileno()

    def writable(self):
        return True


class _OutputProxy:
    _foundry_output_proxy = True

    def __init__(self, original):
        self.original = original
        original_buffer = getattr(original, "buffer", None) if original is not None else None
        self.buffer = _BinaryOutputProxy(self, original_buffer)
        self.encoding = getattr(original, "encoding", None) or "utf-8"
        self.errors = getattr(original, "errors", None) or "replace"

    def write(self, text):
        if not text:
            return 0
        if not isinstance(text, str):
            text = str(text)
        if not is_muted():
            if self.original is not None:
                try:
                    self.original.write(text)
                except (OSError, ValueError):
                    pass
            _write_bytes(text.encode("utf-8", errors="replace"))
            _raise_if_cancel_requested()
        return len(text)

    def flush(self):
        if self.original is not None:
            try:
                self.original.flush()
            except (OSError, ValueError):
                pass

    def fileno(self):
        if self.original is None:
            raise OSError("Foundry output has no native file descriptor")
        return self.original.fileno()

    def isatty(self):
        return bool(self.original is not None and self.original.isatty())

    def writable(self):
        return True

    def __getattr__(self, name):
        if self.original is None:
            raise AttributeError(name)
        return getattr(self.original, name)


class NWO_OT_ShowFoundryOutput(bpy.types.Operator):
    bl_idname = "nwo.show_foundry_output"
    bl_label = "Foundry Output"
    bl_description = "Open the Foundry output window"

    def execute(self, context):
        show()
        return {"FINISHED"}


def _write_bytes(data):
    if not data:
        return
    with _write_lock:
        if _log_stream is not None:
            try:
                _log_stream.write(data)
            except (OSError, ValueError):
                pass


def _unwrap_proxy(stream):
    while getattr(stream, "_foundry_output_proxy", False):
        stream = stream.original
    return stream


def _find_python_executable():
    prefix = Path(sys.prefix)
    binary_directory = Path(bpy.app.binary_path).parent
    version_directory = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
    candidates = (
        prefix / "bin" / "pythonw.exe",
        prefix / "pythonw.exe",
        binary_directory / version_directory / "python" / "bin" / "pythonw.exe",
        prefix / "bin" / "python.exe",
        prefix / "python.exe",
        binary_directory / version_directory / "python" / "bin" / "python.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    for executable_name in ("pythonw.exe", "python.exe"):
        candidate = shutil.which(executable_name)
        if candidate:
            return Path(candidate)
    return None


def _bring_viewer_to_front():
    try:
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.c_void_p
        window = user32.FindWindowW(None, _WINDOW_TITLE)
        if window:
            user32.ShowWindow(window, _SW_RESTORE)
            user32.SetForegroundWindow(window)
            return True
    except (AttributeError, OSError):
        pass
    return False


def _close_viewer():
    try:
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.c_void_p
        window = user32.FindWindowW(None, _WINDOW_TITLE)
        if window:
            user32.PostMessageW(window, 0x0010, 0, 0)
    except (AttributeError, OSError):
        pass


def register():
    global _log_stream, _stdout_proxy, _stderr_proxy
    _SESSION_DIRECTORY.mkdir(parents=True, exist_ok=True)
    _watched_paths.clear()
    _WATCH_PATH.write_text("", encoding="utf-8")
    _CANCEL_PATH.write_text("", encoding="utf-8")
    _log_stream = open(_LOG_PATH, "wb", buffering=0)
    _ensure_tool_job()

    original_stdout = _unwrap_proxy(sys.stdout)
    original_stderr = _unwrap_proxy(sys.stderr)
    _stdout_proxy = _OutputProxy(original_stdout)
    _stderr_proxy = _OutputProxy(original_stderr)
    sys.stdout = _stdout_proxy
    sys.stderr = _stderr_proxy
    bpy.utils.register_class(NWO_OT_ShowFoundryOutput)


def unregister():
    global _log_stream, _stdout_proxy, _stderr_proxy, _viewer_process, _mute_depth, _tool_job_handle
    if _cancel_monitor is not None:
        _cancel_monitor.close()
    try:
        bpy.utils.unregister_class(NWO_OT_ShowFoundryOutput)
    except RuntimeError:
        pass

    _close_viewer()
    if sys.stdout is _stdout_proxy:
        sys.stdout = _stdout_proxy.original
    if sys.stderr is _stderr_proxy:
        sys.stderr = _stderr_proxy.original

    with _write_lock:
        if _log_stream is not None:
            try:
                _log_stream.close()
            except OSError:
                pass
        _log_stream = None

    _stdout_proxy = None
    _stderr_proxy = None
    _viewer_process = None
    _mute_depth = 0
    _watched_paths.clear()
    if _tool_job_handle:
        _tool_kernel32.CloseHandle(_tool_job_handle)
        _tool_job_handle = None


def show():
    global _viewer_process
    if _bring_viewer_to_front():
        return True

    if _viewer_process is not None and _viewer_process.poll() is None:
        return True

    python_executable = _find_python_executable()
    if python_executable is None or not _VIEWER_PATH.is_file():
        _write_bytes(b"Unable to launch Foundry Output: bundled Python or viewer script was not found.\n")
        return False

    command = [
        str(python_executable),
        str(_VIEWER_PATH),
        "--log",
        str(_LOG_PATH),
        "--watch",
        str(_WATCH_PATH),
        "--cancel",
        str(_CANCEL_PATH),
        "--parent-pid",
        str(os.getpid()),
        "--title",
        _WINDOW_TITLE,
    ]
    try:
        _viewer_process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=_VIEWER_PATH.parent,
            creationflags=_CREATE_NO_WINDOW,
            close_fds=True,
        )
    except OSError as error:
        _write_bytes(f"Unable to launch Foundry Output: {error}\n".encode("utf-8", errors="replace"))
        return False
    return True


def clear():
    """Start a fresh visible output session without replacing the underlying file."""
    try:
        _CANCEL_PATH.write_text("", encoding="utf-8")
    except OSError:
        pass
    _write_bytes(b"\x0c")


def child_stream():
    """Return the binary session stream suitable for subprocess stdout/stderr."""
    return _log_stream


def watch_file(path, label=None):
    """Ask the viewer to tail a child-process log that must remain a separate file."""
    if not path:
        return
    resolved_path = str(Path(path).resolve())
    _watched_paths.add(resolved_path)
    entry = json.dumps({"path": resolved_path, "label": label or Path(path).name}, ensure_ascii=False)
    try:
        with open(_WATCH_PATH, "a", encoding="utf-8", newline="\n") as watch_stream:
            watch_stream.write(entry + "\n")
    except OSError:
        pass


def mute():
    global _mute_depth
    _mute_depth += 1


def unmute():
    global _mute_depth
    _mute_depth = max(0, _mute_depth - 1)


def is_muted():
    return _mute_depth > 0

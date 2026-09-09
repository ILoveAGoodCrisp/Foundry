"""Small native Windows viewer for Foundry's redirected output.

This script intentionally uses only ctypes and the Python standard library so it
can run under Blender's bundled pythonw.exe without adding another dependency.
"""

import argparse
import codecs
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET


WM_CREATE = 0x0001
WM_DESTROY = 0x0002
WM_SIZE = 0x0005
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_VSCROLL = 0x0115
WM_LBUTTONUP = 0x0202
WM_CTLCOLORBTN = 0x0135
WM_CTLCOLORSTATIC = 0x0138
WM_SETICON = 0x0080
WM_SETFONT = 0x0030
WM_COPY = 0x0301
EM_GETSEL = 0x00B0
EM_SETSEL = 0x00B1
EM_LINESCROLL = 0x00B6
EM_SCROLLCARET = 0x00B7
EM_GETFIRSTVISIBLELINE = 0x00CE
EM_SETLIMITTEXT = 0x00C5
EM_SETREADONLY = 0x00CF
WM_USER = 0x0400
EM_SETBKGNDCOLOR = WM_USER + 67
EM_SETCHARFORMAT = WM_USER + 68

WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_VSCROLL = 0x00200000
WS_HSCROLL = 0x00100000
WS_TABSTOP = 0x00010000
WS_GROUP = 0x00020000
WS_EX_CLIENTEDGE = 0x00000200
GWLP_WNDPROC = -4
ES_MULTILINE = 0x0004
ES_AUTOVSCROLL = 0x0040
ES_AUTOHSCROLL = 0x0080
ES_READONLY = 0x0800
SS_RIGHT = 0x0002
SS_CENTERIMAGE = 0x0200
SS_ENDELLIPSIS = 0x4000
BS_PUSHBUTTON = 0x00000000
BS_AUTOCHECKBOX = 0x00000003
BS_AUTORADIOBUTTON = 0x00000009
BS_PUSHLIKE = 0x00001000
SW_SHOW = 5
CW_USEDEFAULT = -2147483648
COLOR_WINDOW = 5
OPAQUE = 2
DEFAULT_CHARSET = 1
FIXED_PITCH = 1
FF_MODERN = 48
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
ICON_SMALL = 0
ICON_BIG = 1
BM_GETCHECK = 0x00F0
BM_SETCHECK = 0x00F1
BST_CHECKED = 1
SB_BOTTOM = 7
WPARAM_MINUS_ONE = ctypes.c_size_t(-1).value
SCF_SELECTION = 0x0001
CFM_BOLD = 0x00000001
CFE_BOLD = 0x00000001
CFM_BACKCOLOR = 0x04000000
CFM_COLOR = 0x40000000

RDW_INVALIDATE = 0x0001
RDW_ERASE = 0x0004
RDW_ALLCHILDREN = 0x0080

DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36

ICON_PATH = Path(__file__).parent / "icons" / "foundry.png"

THEME_WINDOW = (32, 34, 35)
THEME_SURFACE = (45, 47, 49)
THEME_LOG = (24, 25, 26)
THEME_BORDER = (72, 75, 78)
THEME_TEXT = (224, 226, 228)
THEME_MUTED_TEXT = (153, 157, 160)
THEME_ACCENT = (242, 243, 244)
THEME_STATE_COLORS = {
    "idle": THEME_BORDER,
    "active": (230, 169, 50),
    "failed": (178, 55, 55),
    "success": (47, 125, 62),
}

BUTTON_CLEAR = 1001
BUTTON_COPY = 1002
BUTTON_OUTPUT = 1003
BUTTON_MESSAGES = 1004
FILTER_MESSAGE = 1005
FILTER_WARNING = 1006
FILTER_ERROR = 1007
BUTTON_CANCEL = 1008
TIMER_ID = 1
MAX_DISPLAY_CHARACTERS = 2_000_000
MAX_DISPLAY_LINES = 100_000

ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")

EXPORT_BANNER_LINE = re.compile(r"^>{3}\s+.*\bEXPORT\b.*<{3}$", re.IGNORECASE)
EXPORT_COMPLETE_LINE = re.compile(r"^(?:Export|Import) Completed in\s+(.+)$", re.IGNORECASE)
CANCELLED_LINE = re.compile(r"^(?:EXPORT|IMPORT) CANCELLED(?: BY USER)?$", re.IGNORECASE)
FAILURE_LINE = re.compile(
    r"(?:^(?:EXPORT|IMPORT)\s+(?:CANCELLED|FAILED)\b|FAILED TO CREATE TAGS|### ASSERTION FAILED|"
    r"FATAL ERROR!|Export crashed and burned|Import failed spectacularly|Tool exited with code|"
    r"Lightmapping aborted|Lightmapper did not run|Exception hit|No Folders/Filepaths supplied)",
    re.IGNORECASE,
)
SECTION_LINE = re.compile(r"^[-=]{8,}$")
WARNING_LINE = re.compile(r"^(?:\[?warning\]?|warn)\s*[:\-]", re.IGNORECASE)
ERROR_LINE = re.compile(r"^(?:\[?error\]?|fatal(?: error)?|critical|traceback|exception)\b", re.IGNORECASE)
TRACEBACK_START_LINE = re.compile(
    r"(?:^|:\s*)[+|]?\s*(?:Exception Group )?Traceback \(most recent call last\):$",
    re.IGNORECASE,
)
TRACEBACK_CHAIN_LINE = re.compile(
    r"^(?:During handling of the above exception, another exception occurred:|"
    r"The above exception was the direct cause of the following exception:)$",
    re.IGNORECASE,
)
TRACEBACK_END_LINE = re.compile(
    r"^(?:[+|]\s*)*(?:[A-Za-z_][\w.]*\.)*(?:[A-Za-z_]\w*(?:Error|Exception|Interrupt)|"
    r"KeyboardInterrupt|SystemExit|GeneratorExit|ExceptionGroup|BaseExceptionGroup|"
    r"StopIteration|StopAsyncIteration)(?::|$)",
)
FATAL_PYTHON_LINE = re.compile(r"^Fatal Python error:\s*", re.IGNORECASE)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
gdiplus = ctypes.windll.gdiplus
shell32 = ctypes.windll.shell32
dwmapi = ctypes.windll.dwmapi
uxtheme = ctypes.windll.uxtheme
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.LoadCursorW.restype = wintypes.HANDLE
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.OpenProcess.restype = wintypes.HANDLE
gdi32.CreateFontW.restype = wintypes.HFONT
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", wintypes.UINT),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", wintypes.BOOL),
        ("SuppressExternalCodecs", wintypes.BOOL),
    ]

class CHARFORMAT2W(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwMask", wintypes.DWORD),
        ("dwEffects", wintypes.DWORD),
        ("yHeight", wintypes.LONG),
        ("yOffset", wintypes.LONG),
        ("crTextColor", wintypes.DWORD),
        ("bCharSet", wintypes.BYTE),
        ("bPitchAndFamily", wintypes.BYTE),
        ("szFaceName", wintypes.WCHAR * 32),
        ("wWeight", wintypes.WORD),
        ("sSpacing", ctypes.c_short),
        ("crBackColor", wintypes.DWORD),
        ("lcid", wintypes.DWORD),
        ("dwReserved", wintypes.DWORD),
        ("sStyle", ctypes.c_short),
        ("wKerning", wintypes.WORD),
        ("bUnderlineType", wintypes.BYTE),
        ("bAnimation", wintypes.BYTE),
        ("bRevAuthor", wintypes.BYTE),
        ("bUnderlineColor", wintypes.BYTE),
    ]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, ctypes.c_void_p, wintypes.HINSTANCE, ctypes.c_void_p]
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.SetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPCWSTR]
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
user32.SetWindowLongPtrW.restype = ctypes.c_void_p
user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.CallWindowProcW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.LoadLibraryW.argtypes = [wintypes.LPCWSTR]
kernel32.LoadLibraryW.restype = wintypes.HMODULE
kernel32.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.OpenJobObjectW.restype = wintypes.HANDLE
kernel32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
kernel32.QueryInformationJobObject.restype = wintypes.BOOL
kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateJobObject.restype = wintypes.BOOL
RICHEDIT_MODULE = kernel32.LoadLibraryW("Msftedit.dll")
OUTPUT_CONTROL_CLASS = "RICHEDIT50W" if RICHEDIT_MODULE else "EDIT"
gdi32.CreateFontW.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR]
gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
gdi32.CreateSolidBrush.argtypes = [wintypes.DWORD]
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.DWORD]
gdi32.SetBkColor.argtypes = [wintypes.HDC, wintypes.DWORD]
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
user32.DestroyIcon.argtypes = [wintypes.HICON]
gdiplus.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(GdiplusStartupInput), ctypes.c_void_p]
gdiplus.GdipCreateBitmapFromFile.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
gdiplus.GdipCreateHICONFromBitmap.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.HICON)]
gdiplus.GdipDisposeImage.argtypes = [ctypes.c_void_p]
gdiplus.GdiplusShutdown.argtypes = [ctypes.c_size_t]
shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
dwmapi.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
uxtheme.SetWindowTheme.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
uxtheme.SetWindowTheme.restype = ctypes.c_long


def colorref(rgb):
    red, green, blue = rgb
    return red | (green << 8) | (blue << 16)


def enable_dark_app_mode():
    try:
        preferred_app_mode = uxtheme[135]
        preferred_app_mode.argtypes = [ctypes.c_int]
        preferred_app_mode.restype = ctypes.c_int
        preferred_app_mode(2)
    except (AttributeError, OSError, TypeError, ValueError):
        pass


def apply_dark_title_bar(hwnd):
    enabled = ctypes.c_int(1)
    result = dwmapi.DwmSetWindowAttribute(
        hwnd,
        DWMWA_USE_IMMERSIVE_DARK_MODE,
        ctypes.byref(enabled),
        ctypes.sizeof(enabled),
    )
    if result != 0:
        dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(enabled), ctypes.sizeof(enabled))

    for attribute, rgb in (
        (DWMWA_BORDER_COLOR, THEME_BORDER),
        (DWMWA_CAPTION_COLOR, THEME_WINDOW),
        (DWMWA_TEXT_COLOR, THEME_ACCENT),
    ):
        value = wintypes.DWORD(colorref(rgb))
        dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))


def load_png_icon(path):
    if not path.is_file():
        return None
    token = ctypes.c_size_t()
    startup = GdiplusStartupInput(1, None, False, False)
    if gdiplus.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None) != 0:
        return None
    try:
        bitmap = ctypes.c_void_p()
        if gdiplus.GdipCreateBitmapFromFile(str(path), ctypes.byref(bitmap)) != 0:
            return None
        try:
            icon = wintypes.HICON()
            if gdiplus.GdipCreateHICONFromBitmap(bitmap, ctypes.byref(icon)) != 0:
                return None
            return icon.value
        finally:
            gdiplus.GdipDisposeImage(bitmap)
    finally:
        gdiplus.GdiplusShutdown(token)


def cancel_active_tool_processes(parent_pid):
    job_name = f"Foundry.ToolProcesses.{parent_pid}"
    job_handle = kernel32.OpenJobObjectW(0x000C, False, job_name)
    if not job_handle:
        return 0
    try:
        accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        if not kernel32.QueryInformationJobObject(job_handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None):
            return 0
        active_processes = accounting.ActiveProcesses
        if not active_processes:
            return 0
        if not kernel32.TerminateJobObject(job_handle, 1223):
            return 0
        return active_processes
    finally:
        kernel32.CloseHandle(job_handle)


def request_cooperative_cancel(path):
    if not path:
        return False
    try:
        Path(path).write_text(str(time.time_ns()), encoding="utf-8")
    except OSError:
        return False
    return True


class TailSource:
    def __init__(self, path, label=""):
        self.path = Path(path)
        self.label = label
        self.position = 0
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def read_new(self):
        try:
            size = self.path.stat().st_size
            if size < self.position:
                self.position = 0
                self.decoder.reset()
            if size == self.position:
                return ""
            with open(self.path, "rb") as stream:
                stream.seek(self.position)
                data = stream.read()
                self.position = stream.tell()
        except OSError:
            return ""
        return self.decoder.decode(data, final=False)


class OutputSources:
    def __init__(self, log_path, watch_path):
        primary_path = str(Path(log_path).resolve())
        primary_source = TailSource(primary_path, "Foundry")
        self.sources = [primary_source]
        self.source_by_path = {primary_path: primary_source}
        self.watch_path = Path(watch_path)
        self.watch_position = 0
        self.watch_remainder = ""

    def _load_watched_sources(self):
        try:
            size = self.watch_path.stat().st_size
            if size < self.watch_position:
                self.watch_position = 0
                self.watch_remainder = ""
            if size == self.watch_position:
                return
            with open(self.watch_path, "r", encoding="utf-8", errors="replace") as stream:
                stream.seek(self.watch_position)
                text = self.watch_remainder + stream.read()
                self.watch_position = stream.tell()
        except OSError:
            return

        lines = text.split("\n")
        self.watch_remainder = lines.pop()
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                path = str(Path(entry["path"]).resolve())
            except (KeyError, TypeError, ValueError, OSError):
                continue
            source = self.source_by_path.get(path)
            if source is not None:
                source.position = 0
                source.decoder.reset()
                source.label = str(entry.get("label") or Path(path).name)
                continue
            source = TailSource(path, str(entry.get("label") or Path(path).name))
            self.sources.append(source)
            self.source_by_path[path] = source

    def read_new(self):
        self._load_watched_sources()
        chunks = []
        for source in self.sources:
            text = source.read_new()
            if text:
                chunks.append((source.label, text))
        return chunks


class LogEntry:
    __slots__ = ("text", "level", "context", "message", "foreground", "bold", "has_newline", "toggle_key")

    def __init__(self, text, level="message", context=(), message=None, foreground=None, bold=False, has_newline=True, toggle_key=None):
        self.text = text
        self.level = level
        self.context = tuple(context)
        self.message = text if message is None else message
        self.foreground = foreground
        self.bold = bold
        self.has_newline = has_newline
        self.toggle_key = toggle_key


class BonoboOutput:
    def __init__(self):
        self.clear()

    def clear(self):
        self.entries = []
        self.current_line = ""
        self.pending_carriage_return = False
        self.last_source = ""
        self.current_section = "General"
        self.traceback_active = False
        self.traceback_chain_pending = False
        self.has_traceback = False
        self.traceback_number = 0
        self.traceback_label = "Traceback"
        self.total_characters = 0

    @staticmethod
    def _tool_text(value):
        result = []
        escaped = False
        for character in value or "":
            if escaped:
                result.append({"n": "\n", "r": "\r", "t": "\t"}.get(character, character))
                escaped = False
            elif character == "\\":
                escaped = True
            else:
                result.append(character)
        return "".join(result)

    @staticmethod
    def _parse_color(value):
        try:
            values = tuple(max(0, min(255, round(float(component.strip()) * 255))) for component in value.split(","))
        except (AttributeError, TypeError, ValueError):
            return None
        return values if len(values) == 3 else None

    @staticmethod
    def _plain_context(text):
        match = re.match(r"^((?:[A-Za-z0-9_.-]+:){1,8})\s*(.*)$", text)
        if not match:
            return (), text
        context = tuple(part for part in match.group(1).strip(":").split(":") if part)
        if context[0].lower() in {"warning", "warn", "error", "fatal", "critical"}:
            return (), text
        return context, match.group(2) or text

    @staticmethod
    def _plain_level(raw_text, text):
        lowered = text.lower()
        if "\x1b[91m" in raw_text or "\x1b[31m" in raw_text or ERROR_LINE.match(text):
            return "error"
        if "\x1b[93m" in raw_text or "\x1b[33m" in raw_text or WARNING_LINE.match(text):
            return "warning"
        if EXPORT_COMPLETE_LINE.match(text) or lowered in {"succeeded.", "success"}:
            return "success"
        if SECTION_LINE.match(text) or EXPORT_BANNER_LINE.match(text):
            return "status"
        return "message"

    @staticmethod
    def _display_section(title):
        title = title.strip()
        return {"writing tags": "Tool Import"}.get(title.casefold(), title)

    def _diagnostic_context(self, context):
        section = self.current_section or "General"
        context = tuple(context)
        if context and context[0] == section:
            return context
        return (section, *context)

    def _entries_from_text(self, text, level="message", context=(), message=None, foreground=None, bold=False, add_newline=True):
        normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        parts = normalized.split("\n")
        if len(parts) > 1 and parts[-1] == "" and add_newline:
            parts.pop()
        if not parts:
            parts = [""]
        entries = []
        for index, part in enumerate(parts):
            part_message = part if message is None or len(parts) > 1 else message
            entries.append(LogEntry(part, level, context, part_message, foreground, bold, add_newline if index == len(parts) - 1 else True))
        return entries

    def _parse_structured(self, raw_text):
        text = raw_text.strip()
        if not text.startswith("<"):
            return None
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return None
        tag = root.tag.rpartition("}")[2]
        attributes = root.attrib
        if tag in {"block_begin", "block_end", "modify", "wait_for_keypress"}:
            return []
        if tag == "output":
            message = self._tool_text(attributes.get("message", ""))
            add_newline = attributes.get("newline", "1") == "1"
            return self._entries_from_text(message, foreground=self._parse_color(attributes.get("color")), add_newline=add_newline)
        if tag == "debug":
            return self._entries_from_text(self._tool_text(attributes.get("message", "")))
        if tag in {"error", "alert"}:
            level = "error" if tag == "error" else "warning"
            return self._entries_from_text(self._tool_text(attributes.get("message", "")), level, ("Tool",))
        if tag == "event":
            level = attributes.get("level", "message").lower()
            if level not in {"verbose", "status", "message", "warning", "error", "critical"}:
                level = "message"
            context = tuple(part for part in attributes.get("context", "").split(":") if part)
            category = attributes.get("category", "").strip(": ")
            message = attributes.get("message", "")
            body = ": ".join(part for part in (category, message) if part)
            prefix = ":".join(context)
            display = f"{prefix}: {body}" if prefix else body
            return [LogEntry(display, level, context, body, self._parse_color(attributes.get("color")))]
        if tag == "progress_begin":
            return self._entries_from_text(self._tool_text(attributes.get("message", "")), "status", bold=True)
        if tag == "progress_update":
            description = self._tool_text(attributes.get("description", ""))
            optional = self._tool_text(attributes.get("optional_description", ""))
            progress = attributes.get("progress", "")
            message = " ".join(part for part in (description, optional, f"({progress}%)" if progress else "") if part)
            return self._entries_from_text(message, "status")
        if tag == "progress_end":
            message = self._tool_text(attributes.get("message", ""))
            return self._entries_from_text(message, "success" if message else "status", bold=True)
        if tag == "ask_user":
            caption = self._tool_text(attributes.get("caption", ""))
            message = self._tool_text(attributes.get("message", ""))
            return self._entries_from_text(": ".join(part for part in (caption, message) if part), "warning", ("Tool",))
        return []

    def feed(self, text, source=""):
        if source and source != self.last_source:
            if self.last_source and (self.entries or self.current_line):
                self._add_entry(LogEntry(f"[{source}]", "status", bold=True))
            self.last_source = source
        for character in text:
            if self.pending_carriage_return:
                self.pending_carriage_return = False
                if character == "\n":
                    self._finish_line()
                    continue
                self.current_line = ""
            if character == "\f":
                self.clear()
            elif character == "\r":
                self.pending_carriage_return = True
            elif character == "\n":
                self._finish_line()
            elif character == "\b":
                self.current_line = self.current_line[:-1]
            elif character != "\x00":
                self.current_line += character

    def _finish_line(self):
        raw_text = self.current_line
        self.current_line = ""
        structured_entries = self._parse_structured(raw_text)
        if structured_entries is not None:
            for entry in structured_entries:
                if self._filter_level(entry.level) in {"warning", "error"}:
                    entry.context = self._diagnostic_context(entry.context)
                self._add_entry(entry)
            return
        clean_text = ANSI_ESCAPE.sub("", raw_text)
        stripped_text = clean_text.strip()
        traceback_start = bool(TRACEBACK_START_LINE.search(stripped_text))
        traceback_chain = bool(TRACEBACK_CHAIN_LINE.match(stripped_text))
        fatal_python = bool(FATAL_PYTHON_LINE.match(stripped_text))

        if traceback_start or fatal_python:
            self.traceback_active = True
            self.traceback_chain_pending = False
            self.has_traceback = True
            self.traceback_number += 1
            self.traceback_label = "Traceback" if self.traceback_number == 1 else f"Traceback {self.traceback_number}"
        elif self.traceback_chain_pending:
            if not stripped_text:
                self._add_entry(LogEntry(clean_text))
                return
            if traceback_chain:
                self._add_entry(LogEntry(
                    clean_text, "error", self._diagnostic_context((self.traceback_label,))
                ))
                return
            self.traceback_chain_pending = False

        if self.traceback_active:
            if not stripped_text:
                self._add_entry(LogEntry(clean_text))
            else:
                self._add_entry(LogEntry(
                    clean_text, "error", self._diagnostic_context((self.traceback_label,))
                ))
                if TRACEBACK_END_LINE.match(stripped_text):
                    self.traceback_active = False
                    self.traceback_chain_pending = True
            return
        level = self._plain_level(raw_text, clean_text)
        context, message = self._plain_context(clean_text)
        if SECTION_LINE.match(clean_text) and self.entries:
            previous = self.entries[-1]
            heading = previous.text.strip()
            if heading and not SECTION_LINE.match(heading):
                terminal_heading = EXPORT_COMPLETE_LINE.match(heading) or FAILURE_LINE.search(heading)
                if not terminal_heading:
                    previous.level = "status"
                    previous.context = ()
                    previous.message = heading
                    previous.bold = True
                    if heading.casefold() != "error log":
                        self.current_section = self._display_section(heading)
        if self._filter_level(level) in {"warning", "error"}:
            context = self._diagnostic_context(context)
        self._add_entry(LogEntry(clean_text, level, context, message, bold=level in {"status", "success"}))

    def _add_entry(self, entry):
        if self.entries and not self.entries[-1].has_newline:
            previous = self.entries[-1]
            previous.text += entry.text
            previous.message += entry.message
            previous.has_newline = entry.has_newline
            if entry.level not in {"message", "verbose"}:
                previous.level = entry.level
            self.total_characters += len(entry.text)
            return
        if self.entries and entry.text == self.entries[-1].text and entry.level == self.entries[-1].level and entry.context == self.entries[-1].context:
            return
        self.entries.append(entry)
        self.total_characters += len(entry.text) + 2
        while self.entries and (len(self.entries) > MAX_DISPLAY_LINES or self.total_characters > MAX_DISPLAY_CHARACTERS):
            removed = self.entries.pop(0)
            self.total_characters -= len(removed.text) + 2

    @staticmethod
    def _filter_level(level):
        if level == "warning" or level == "warning_header":
            return "warning"
        if level in {"error", "critical", "error_header", "critical_header"}:
            return "error"
        return "message"

    def filtered_entries(self, enabled_levels):
        return [entry for entry in self.entries if self._filter_level(entry.level) in enabled_levels]

    def counts(self):
        counts = {"message": 0, "warning": 0, "error": 0}
        for entry in self.entries:
            counts[self._filter_level(entry.level)] += 1
        return counts

    def grouped_entries(self, enabled_levels, collapsed_keys=()):
        collapsed_keys = set(collapsed_keys)
        unique = {}
        for entry in self.entries:
            filter_level = self._filter_level(entry.level)
            if filter_level not in {"warning", "error"} or filter_level not in enabled_levels:
                continue
            key = (entry.level, entry.context or ("General",), entry.message)
            unique[key] = unique.get(key, 0) + 1
        if not unique:
            return [LogEntry("No warnings or errors.", "status", bold=True)]

        def message_count(node):
            total = sum(count for _, count in node.get("_messages", []))
            for name, child in node.items():
                if name != "_messages":
                    total += message_count(child)
            return total

        result = []
        severity_groups = (("critical", "Critical Errors"), ("error", "Errors"), ("warning", "Warnings"))
        for severity, title in severity_groups:
            items = [(key, count) for key, count in unique.items() if key[0] == severity]
            if not items:
                continue
            total = sum(count for _, count in items)
            severity_key = ("severity", severity)
            severity_collapsed = severity_key in collapsed_keys
            arrow = "▶" if severity_collapsed else "▼"
            result.append(LogEntry(
                f"{arrow} {title} ({total})",
                f"{severity}_header",
                bold=True,
                toggle_key=severity_key,
            ))
            if severity_collapsed:
                continue

            tree = {}
            for (level, context, message), count in items:
                node = tree
                for part in context:
                    node = node.setdefault(part, {"_messages": []})
                node.setdefault("_messages", []).append((message, count))

            def append_node(node, depth, path):
                for name, child in node.items():
                    if name == "_messages":
                        continue
                    child_path = (*path, name)
                    node_key = ("context", severity, *child_path)
                    collapsed = node_key in collapsed_keys
                    arrow = "▶" if collapsed else "▼"
                    result.append(LogEntry(
                        f"{'  ' * depth}{arrow} {name} ({message_count(child)})",
                        f"{severity}_header",
                        bold=True,
                        toggle_key=node_key,
                    ))
                    if not collapsed:
                        append_node(child, depth + 1, child_path)
                for message, count in node.get("_messages", []):
                    suffix = f" (x{count})" if count > 1 else ""
                    result.append(LogEntry(f"{'  ' * depth}- {message}{suffix}", severity))

            append_node(tree, 1, ())
        return result

class ExportStatus:
    def __init__(self):
        self.clear()

    def clear(self):
        self.status = "Ready"
        self.state = "idle"
        self.started_at = None
        self.completed_duration = None
        self.finished = False
        self.current_line = ""
        self.previous_line = ""
        self.pending_carriage_return = False

    def feed(self, text):
        text = ANSI_ESCAPE.sub("", text)
        for character in text:
            if self.pending_carriage_return:
                self.pending_carriage_return = False
                if character == "\n":
                    self._finish_line()
                    continue
                self.current_line = ""

            if character == "\f":
                self.clear()
            elif character == "\r":
                self.pending_carriage_return = True
            elif character == "\n":
                self._finish_line()
            elif character == "\b":
                self.current_line = self.current_line[:-1]
            elif character != "\x00":
                self.current_line += character

    def _finish_line(self):
        line = self.current_line.strip()
        self.current_line = ""
        if TRACEBACK_START_LINE.search(line) or FATAL_PYTHON_LINE.match(line):
            self.status = "Python crash / traceback — see Messages"
            self.state = "failed"
            self.finished = True
        elif FAILURE_LINE.search(line):
            self.status = line.title() if CANCELLED_LINE.match(line) else line
            self.state = "failed"
            self.finished = True
        if EXPORT_BANNER_LINE.match(line) and not self.finished:
            if self.started_at is None:
                self.started_at = time.monotonic()
            self.state = "active"
        if SECTION_LINE.match(line):
            heading = self.previous_line.strip()
            if heading and not SECTION_LINE.match(heading):
                completed = EXPORT_COMPLETE_LINE.match(heading)
                if completed and not self.finished:
                    self.status = f"{heading} at {time.strftime('%H:%M:%S')}"
                    self.completed_duration = completed.group(1)
                    self.state = "success"
                    self.finished = True
                elif not self.finished:
                    if self.started_at is None:
                        self.started_at = time.monotonic()
                    self.status = heading
                    self.state = "active"
        self.previous_line = line

class FoundryOutputWindow:
    def __init__(self, arguments):
        self.arguments = arguments
        self.parent_process = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, self.arguments.parent_pid
        )
        self.parent_exit_handled = False
        self.sources = OutputSources(arguments.log, arguments.watch)
        self.output = BonoboOutput()
        self.export_status = ExportStatus()
        self.hwnd = None
        self.edit = None
        self.clear_button = None
        self.copy_button = None
        self.cancel_button = None
        self.output_button = None
        self.messages_button = None
        self.show_label = None
        self.filter_message = None
        self.filter_warning = None
        self.filter_error = None
        self.filter_summary = None
        self.status_border = None
        self.status_label = None
        self.rendered_status = None
        self.show_messages = False
        self.enabled_levels = {"message", "warning", "error"}
        self.collapsed_message_nodes = set()
        self.message_toggle_ranges = []
        self.original_edit_window_proc = None
        self.edit_window_proc = WNDPROC(self._edit_window_proc)
        self.font = None
        self.icon = load_png_icon(ICON_PATH)
        self.window_brush = gdi32.CreateSolidBrush(colorref(THEME_WINDOW))
        self.surface_brush = gdi32.CreateSolidBrush(colorref(THEME_SURFACE))
        self.status_brushes = {
            state: gdi32.CreateSolidBrush(colorref(rgb)) for state, rgb in THEME_STATE_COLORS.items()
        }
        self.window_proc = WNDPROC(self._window_proc)

    def _parent_exit_code(self):
        if not self.parent_process:
            return None
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(self.parent_process, ctypes.byref(exit_code)):
            return None
        return exit_code.value

    def _create_controls(self, hwnd):
        self.edit = user32.CreateWindowExW(
            WS_EX_CLIENTEDGE,
            OUTPUT_CONTROL_CLASS,
            "",
            WS_CHILD | WS_VISIBLE | WS_VSCROLL | WS_HSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_AUTOHSCROLL | ES_READONLY,
            8,
            8,
            780,
            480,
            hwnd,
            None,
            None,
            None,
        )
        self.original_edit_window_proc = user32.SetWindowLongPtrW(
            self.edit, GWLP_WNDPROC, ctypes.cast(self.edit_window_proc, ctypes.c_void_p)
        )
        user32.SendMessageW(self.edit, EM_SETLIMITTEXT, MAX_DISPLAY_CHARACTERS, 0)
        user32.SendMessageW(self.edit, EM_SETBKGNDCOLOR, 0, colorref(THEME_LOG))
        self.output_button = user32.CreateWindowExW(
            0, "BUTTON", "Output",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | WS_GROUP | BS_AUTORADIOBUTTON | BS_PUSHLIKE,
            8, 496, 78, 26, hwnd, BUTTON_OUTPUT, None, None,
        )
        self.messages_button = user32.CreateWindowExW(
            0, "BUTTON", "Messages",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_AUTORADIOBUTTON | BS_PUSHLIKE,
            86, 496, 90, 26, hwnd, BUTTON_MESSAGES, None, None,
        )
        self.show_label = user32.CreateWindowExW(
            0, "STATIC", "Show:", WS_CHILD | WS_VISIBLE | SS_CENTERIMAGE,
            188, 496, 45, 26, hwnd, None, None, None,
        )
        self.filter_message = user32.CreateWindowExW(
            0, "BUTTON", "Message", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_AUTOCHECKBOX,
            236, 496, 88, 26, hwnd, FILTER_MESSAGE, None, None,
        )
        self.filter_warning = user32.CreateWindowExW(
            0, "BUTTON", "Warning", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_AUTOCHECKBOX,
            324, 496, 88, 26, hwnd, FILTER_WARNING, None, None,
        )
        self.filter_error = user32.CreateWindowExW(
            0, "BUTTON", "Error", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_AUTOCHECKBOX,
            412, 496, 72, 26, hwnd, FILTER_ERROR, None, None,
        )
        self.filter_summary = user32.CreateWindowExW(
            0, "STATIC", "Messages: 0   Warnings: 0   Errors: 0",
            WS_CHILD | WS_VISIBLE | SS_RIGHT | SS_CENTERIMAGE,
            492, 496, 390, 26, hwnd, None, None, None,
        )
        self.clear_button = user32.CreateWindowExW(
            0, "BUTTON", "Clear", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            8, 536, 90, 28, hwnd, BUTTON_CLEAR, None, None,
        )
        self.copy_button = user32.CreateWindowExW(
            0, "BUTTON", "Copy All", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            106, 536, 90, 28, hwnd, BUTTON_COPY, None, None,
        )
        self.cancel_button = user32.CreateWindowExW(
            0, "BUTTON", "Cancel", WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            204, 536, 100, 28, hwnd, BUTTON_CANCEL, None, None,
        )
        self.status_border = user32.CreateWindowExW(
            0, "STATIC", "", WS_CHILD | WS_VISIBLE,
            312, 536, 570, 28, hwnd, None, None, None,
        )
        self.status_label = user32.CreateWindowExW(
            0, "STATIC", "Ready", WS_CHILD | WS_VISIBLE | SS_CENTERIMAGE | SS_ENDELLIPSIS,
            314, 538, 566, 24, hwnd, None, None, None,
        )
        self.font = gdi32.CreateFontW(
            -16, 0, 0, 0, 400, False, False, False, DEFAULT_CHARSET,
            0, 0, 0, FIXED_PITCH | FF_MODERN, "Consolas",
        )
        for control in (
            self.edit, self.output_button, self.messages_button, self.show_label,
            self.filter_message, self.filter_warning, self.filter_error, self.filter_summary,
            self.clear_button, self.copy_button, self.cancel_button, self.status_label,
        ):
            user32.SendMessageW(control, WM_SETFONT, self.font, True)
            uxtheme.SetWindowTheme(control, "DarkMode_Explorer", None)
        user32.SendMessageW(self.output_button, BM_SETCHECK, BST_CHECKED, 0)
        user32.SendMessageW(self.filter_message, BM_SETCHECK, BST_CHECKED, 0)
        user32.SendMessageW(self.filter_warning, BM_SETCHECK, BST_CHECKED, 0)
        user32.SendMessageW(self.filter_error, BM_SETCHECK, BST_CHECKED, 0)
        user32.SetTimer(hwnd, TIMER_ID, 100, None)

    def _resize_controls(self, width, height):
        button_height = 30
        filter_height = 26
        margin = 8
        control_top = max(margin, height - margin - button_height)
        filter_top = max(margin, control_top - margin - filter_height)
        edit_height = max(80, filter_top - margin * 2)
        user32.MoveWindow(self.edit, margin, margin, max(100, width - margin * 2), edit_height, True)
        user32.MoveWindow(self.output_button, margin, filter_top, 78, filter_height, True)
        user32.MoveWindow(self.messages_button, margin + 78, filter_top, 90, filter_height, True)
        user32.MoveWindow(self.show_label, margin + 180, filter_top, 45, filter_height, True)
        user32.MoveWindow(self.filter_message, margin + 228, filter_top, 88, filter_height, True)
        user32.MoveWindow(self.filter_warning, margin + 316, filter_top, 88, filter_height, True)
        user32.MoveWindow(self.filter_error, margin + 404, filter_top, 72, filter_height, True)
        summary_left = margin + 484
        user32.MoveWindow(self.filter_summary, summary_left, filter_top, max(80, width - summary_left - margin), filter_height, True)
        user32.MoveWindow(self.clear_button, margin, control_top, 90, button_height, True)
        user32.MoveWindow(self.copy_button, margin + 98, control_top, 90, button_height, True)
        user32.MoveWindow(self.cancel_button, margin + 196, control_top, 100, button_height, True)
        status_left = margin + 304
        status_width = max(80, width - status_left - margin)
        user32.MoveWindow(self.status_border, status_left, control_top, status_width, button_height, True)
        user32.MoveWindow(self.status_label, status_left + 2, control_top + 2, max(76, status_width - 4), button_height - 4, True)
        user32.RedrawWindow(self.hwnd, None, None, RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN)

    def _update_status_controls(self):
        rendered_status = (self.export_status.status, self.export_status.state)
        if rendered_status == self.rendered_status:
            return
        self.rendered_status = rendered_status
        user32.SetWindowTextW(self.status_label, self.export_status.status)
        flags = RDW_INVALIDATE | RDW_ERASE
        user32.RedrawWindow(self.status_border, None, None, flags)
        user32.RedrawWindow(self.status_label, None, None, flags)

    @staticmethod
    def _colorref(rgb):
        return colorref(rgb)

    def _enabled_levels(self):
        return set(self.enabled_levels)

    def _entry_format(self, entry):
        styles = {
            "message": (THEME_TEXT, THEME_LOG, False),
            "verbose": (THEME_MUTED_TEXT, THEME_LOG, False),
            "status": (THEME_ACCENT, THEME_SURFACE, True),
            "warning": ((24, 25, 26), (230, 169, 50), False),
            "warning_header": ((24, 25, 26), (230, 169, 50), True),
            "error": ((255, 245, 245), (178, 55, 55), False),
            "error_header": ((255, 245, 245), (178, 55, 55), True),
            "critical": ((255, 245, 245), (115, 35, 35), False),
            "critical_header": ((255, 245, 245), (115, 35, 35), True),
            "success": ((245, 255, 245), (47, 125, 62), True),
        }
        foreground, background, bold = styles.get(entry.level, styles["message"])
        if entry.foreground:
            foreground = entry.foreground
        format_value = CHARFORMAT2W()
        format_value.cbSize = ctypes.sizeof(CHARFORMAT2W)
        format_value.dwMask = CFM_COLOR | CFM_BACKCOLOR | CFM_BOLD
        format_value.dwEffects = CFE_BOLD if entry.bold or bold else 0
        format_value.crTextColor = self._colorref(foreground)
        format_value.crBackColor = self._colorref(background)
        return format_value

    def _update_filter_summary(self):
        counts = self.output.counts()
        summary = f"Messages: {counts['message']}   Warnings: {counts['warning']}   Errors: {counts['error']}"
        user32.SetWindowTextW(self.filter_summary, summary)

    def _render_output(self, scroll_to_end=True):
        first_visible_line = 0
        if not scroll_to_end:
            first_visible_line = user32.SendMessageW(self.edit, EM_GETFIRSTVISIBLELINE, 0, 0)

        enabled_levels = self._enabled_levels()
        entries = (
            self.output.grouped_entries(enabled_levels, self.collapsed_message_nodes)
            if self.show_messages
            else self.output.filtered_entries(enabled_levels)
        )
        self.message_toggle_ranges = []

        user32.SendMessageW(self.edit, EM_SETREADONLY, 0, 0)
        rendered = "\r".join(entry.text for entry in entries)
        if entries:
            rendered += "\r"
        user32.SetWindowTextW(self.edit, rendered)
        position = 0
        for entry in entries:
            end = position + len(entry.text)
            if entry.toggle_key is not None:
                self.message_toggle_ranges.append((position, end, entry.toggle_key))
            user32.SendMessageW(self.edit, EM_SETSEL, position, end)
            format_value = self._entry_format(entry)
            user32.SendMessageW(self.edit, EM_SETCHARFORMAT, SCF_SELECTION, ctypes.addressof(format_value))
            position = end + 1
        user32.SendMessageW(self.edit, EM_SETREADONLY, 1, 0)

        if scroll_to_end:
            user32.SendMessageW(self.edit, EM_SETSEL, WPARAM_MINUS_ONE, -1)
            user32.SendMessageW(self.edit, EM_SCROLLCARET, 0, 0)
            user32.SendMessageW(self.edit, WM_VSCROLL, SB_BOTTOM, 0)
        else:
            current_first_line = user32.SendMessageW(self.edit, EM_GETFIRSTVISIBLELINE, 0, 0)
            line_delta = first_visible_line - current_first_line
            if line_delta:
                user32.SendMessageW(self.edit, EM_LINESCROLL, 0, line_delta)
        self._update_filter_summary()

    def _toggle_message_node_at(self, character_index):
        for start, end, toggle_key in self.message_toggle_ranges:
            if start <= character_index <= end:
                if toggle_key in self.collapsed_message_nodes:
                    self.collapsed_message_nodes.remove(toggle_key)
                else:
                    self.collapsed_message_nodes.add(toggle_key)
                self._render_output(scroll_to_end=False)
                return True
        return False

    def _edit_window_proc(self, hwnd, message, wparam, lparam):
        if not self.original_edit_window_proc:
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)
        result = user32.CallWindowProcW(self.original_edit_window_proc, hwnd, message, wparam, lparam)
        if message == WM_LBUTTONUP and self.show_messages:
            selection_start = wintypes.DWORD()
            selection_end = wintypes.DWORD()
            user32.SendMessageW(
                hwnd,
                EM_GETSEL,
                ctypes.addressof(selection_start),
                ctypes.addressof(selection_end),
            )
            if selection_start.value == selection_end.value:
                self._toggle_message_node_at(selection_start.value)
        return result
    def _update_output(self):
        chunks = self.sources.read_new()
        for source, text in chunks:
            self.output.feed(text, source)
            if source == "Foundry":
                self.export_status.feed(text)
        if self.output.has_traceback and self.export_status.state != "failed":
            self.export_status.status = "Python crash / traceback — see Messages"
            self.export_status.state = "failed"
            self.export_status.finished = True
        if chunks:
            self._render_output()
        self._update_status_controls()

    def _window_proc(self, hwnd, message, wparam, lparam):
        if message in {WM_CTLCOLORBTN, WM_CTLCOLORSTATIC}:
            control = int(lparam)
            if control == self.status_border:
                state_color = THEME_STATE_COLORS.get(self.export_status.state, THEME_BORDER)
                brush = self.status_brushes.get(self.export_status.state, self.status_brushes["idle"])
                background = state_color
            else:
                surface_controls = {self.status_label}
                brush = self.surface_brush if message == WM_CTLCOLORBTN or control in surface_controls else self.window_brush
                background = THEME_SURFACE if brush == self.surface_brush else THEME_WINDOW
            foreground = THEME_MUTED_TEXT if control in {self.show_label, self.filter_summary} else THEME_TEXT
            gdi32.SetTextColor(wparam, colorref(foreground))
            gdi32.SetBkColor(wparam, colorref(background))
            gdi32.SetBkMode(wparam, OPAQUE)
            return brush
        if message == WM_CREATE:
            self.hwnd = hwnd
            self._create_controls(hwnd)
            return 0
        if message == WM_SIZE:
            self._resize_controls(lparam & 0xFFFF, (lparam >> 16) & 0xFFFF)
            return 0
        if message == WM_COMMAND:
            command = wparam & 0xFFFF
            if command == BUTTON_CLEAR:
                self.output.clear()
                self.export_status.clear()
                self.collapsed_message_nodes.clear()
                self._render_output()
                self._update_status_controls()
                return 0
            if command == BUTTON_COPY:
                user32.SendMessageW(self.edit, EM_SETSEL, 0, -1)
                user32.SendMessageW(self.edit, WM_COPY, 0, 0)
                return 0
            if command == BUTTON_CANCEL:
                process_count = cancel_active_tool_processes(self.arguments.parent_pid)
                blender_phase_active = self.export_status.state == "active"
                cancellation_requested = False
                if process_count or blender_phase_active:
                    cancellation_requested = request_cooperative_cancel(self.arguments.cancel)
                if process_count or cancellation_requested:
                    suffix = "es" if process_count != 1 else ""
                    detail = f" ({process_count} Tool process{suffix})" if process_count else ""
                    message = f"Cancelling import / export{detail}..."
                else:
                    message = "No active import / export to cancel"
                self.export_status.status = message
                self.output._add_entry(LogEntry(message, "status", bold=True))
                self._render_output()
                self._update_status_controls()
                return 0
            if command == BUTTON_OUTPUT:
                self.show_messages = False
                user32.SendMessageW(self.output_button, BM_SETCHECK, BST_CHECKED, 0)
                user32.SendMessageW(self.messages_button, BM_SETCHECK, 0, 0)
                self._render_output()
                return 0
            if command == BUTTON_MESSAGES:
                self.show_messages = True
                user32.SendMessageW(self.output_button, BM_SETCHECK, 0, 0)
                user32.SendMessageW(self.messages_button, BM_SETCHECK, BST_CHECKED, 0)
                self._render_output()
                return 0
            if command in {FILTER_MESSAGE, FILTER_WARNING, FILTER_ERROR}:
                control, level = {
                    FILTER_MESSAGE: (self.filter_message, "message"),
                    FILTER_WARNING: (self.filter_warning, "warning"),
                    FILTER_ERROR: (self.filter_error, "error"),
                }[command]
                if user32.SendMessageW(control, BM_GETCHECK, 0, 0) == BST_CHECKED:
                    self.enabled_levels.add(level)
                else:
                    self.enabled_levels.discard(level)
                self._render_output()
                return 0
        if message == WM_TIMER and wparam == TIMER_ID:
            self._update_output()
            exit_code = self._parent_exit_code()
            if exit_code == STILL_ACTIVE:
                return 0
            self._update_output()
            if exit_code not in {None, 0}:
                if not self.parent_exit_handled:
                    self.parent_exit_handled = True
                    crash_message = f"Blender exited unexpectedly (exit code 0x{exit_code:08X})"
                    self.export_status.status = crash_message
                    self.export_status.state = "failed"
                    self.export_status.finished = True
                    self.output._add_entry(LogEntry(crash_message, "error", ("Blender",)))
                    self._render_output()
                    self._update_status_controls()
                    user32.EnableWindow(self.cancel_button, False)
                    user32.KillTimer(hwnd, TIMER_ID)
                return 0
            user32.DestroyWindow(hwnd)
            return 0
        if message == WM_DESTROY:
            user32.KillTimer(hwnd, TIMER_ID)
            if self.parent_process:
                kernel32.CloseHandle(self.parent_process)
                self.parent_process = None
            if self.font:
                gdi32.DeleteObject(self.font)
            if self.icon:
                user32.DestroyIcon(self.icon)
                self.icon = None
            for brush_name in ("window_brush", "surface_brush"):
                brush = getattr(self, brush_name, None)
                if brush:
                    gdi32.DeleteObject(brush)
                    setattr(self, brush_name, None)
            for brush in self.status_brushes.values():
                if brush:
                    gdi32.DeleteObject(brush)
            self.status_brushes.clear()
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def run(self):
        enable_dark_app_mode()
        shell32.SetCurrentProcessExplicitAppUserModelID("Foundry.Output")
        instance = kernel32.GetModuleHandleW(None)
        class_name = f"FoundryOutputWindow{self.arguments.parent_pid}"
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = ctypes.cast(self.window_proc, ctypes.c_void_p).value
        window_class.hInstance = instance
        window_class.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))
        window_class.hIcon = self.icon
        window_class.hbrBackground = self.window_brush
        window_class.lpszClassName = class_name
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            return 1

        self.hwnd = user32.CreateWindowExW(
            0,
            class_name,
            self.arguments.title,
            WS_OVERLAPPEDWINDOW | WS_VISIBLE,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            900,
            650,
            None,
            None,
            instance,
            None,
        )
        if not self.hwnd:
            return 1
        apply_dark_title_bar(self.hwnd)
        uxtheme.SetWindowTheme(self.hwnd, "DarkMode_Explorer", None)
        if self.icon:
            user32.SendMessageW(self.hwnd, WM_SETICON, ICON_BIG, self.icon)
            user32.SendMessageW(self.hwnd, WM_SETICON, ICON_SMALL, self.icon)
        user32.ShowWindow(self.hwnd, SW_SHOW)
        user32.UpdateWindow(self.hwnd)

        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        return int(message.wParam)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--watch", required=True)
    parser.add_argument("--cancel", default="")
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--title", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(FoundryOutputWindow(parse_arguments()).run())

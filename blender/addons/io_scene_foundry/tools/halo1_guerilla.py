"""Halo 1 Guerilla's MFC startup archive (guerilla.cfg).

The archive contains a WINDOWPLACEMENT followed by marker-delimited document
records, not a document count. Each record has its own placement, CString path,
scroll position and a uint16-sized array of editor-state int32s.
"""

import ctypes
from ctypes import wintypes
import ntpath
import os
from pathlib import Path
import struct
import tempfile


_PATH_ENCODING = "mbcs" if os.name == "nt" else "cp1252"
_PLACEMENT = struct.Struct("<III8i")
_DEFAULT_MAIN = _PLACEMENT.pack(44, 0, 1, -1, -1, -1, -1, 100, 100, 1124, 868)
_DEFAULT_CHILD = _PLACEMENT.pack(44, 0, 1, -1, -1, -1, -1, 0, 0, 800, 600)


class _Reader:
    def __init__(self, data):
        self.data = data
        self.offset = 0

    def read(self, size):
        end = self.offset + size
        if end > len(self.data):
            raise ValueError("Truncated Guerilla configuration")
        value = self.data[self.offset:end]
        self.offset = end
        return value

    def integer(self, format):
        return struct.unpack(format, self.read(struct.calcsize(format)))[0]

    def placement(self):
        value = self.read(44)
        if struct.unpack_from("<I", value)[0] != 44:
            raise ValueError("Unsupported Guerilla window placement")
        return value

    def string(self):
        length = self.integer("<B")
        unicode = False
        if length == 0xFF:
            length = self.integer("<H")
            if length == 0xFFFE:
                unicode = True
                length = self.integer("<B")
                if length == 0xFF:
                    length = self.integer("<H")
            if length == 0xFFFF:
                length = self.integer("<I")
                if length == 0xFFFFFFFF:
                    length = self.integer("<Q")
        value = self.read(length * (2 if unicode else 1))
        return value.decode("utf-16-le" if unicode else _PATH_ENCODING)


def _path_key(path):
    return ntpath.normcase(ntpath.normpath(str(path)))


def _write_path(path):
    if not path or "\0" in path:
        raise ValueError("Invalid Guerilla tag path")
    # Guerilla uses ANSI paths. Refuse unrepresentable names instead of silently
    # replacing characters and opening the wrong file.
    data = path.encode(_PATH_ENCODING)
    length = len(data)
    if length < 0xFF:
        prefix = struct.pack("<B", length)
    elif length < 0xFFFE:
        prefix = struct.pack("<BH", 0xFF, length)
    else:
        prefix = struct.pack("<BHI", 0xFF, 0xFFFF, length)
    return prefix + data


def build_config(previous, tag_paths):
    """Build an archive, preserving complete records for matching saved tags.

    New tags start at scroll position zero with no saved field selections.
    Unknown or damaged archives are rejected rather than overwritten.
    """
    records = {}
    main = _DEFAULT_MAIN
    if previous is not None:
        reader = _Reader(previous)
        main = reader.placement()
        while True:
            start = reader.offset
            marker = reader.integer("<I")
            if marker == 0:
                break
            if marker != 1:
                raise ValueError("Unsupported Guerilla document marker")
            reader.placement()
            path = reader.string()
            if not path or "\0" in path:
                raise ValueError("Invalid saved Guerilla tag path")
            reader.read(8)  # Scroll position.
            count = reader.integer("<H")
            # The editor loads these into a fixed array of 256 int32s.
            if count > 256:
                raise ValueError("Invalid Guerilla editor-state count")
            reader.read(count * 4)
            records[_path_key(path)] = previous[start:reader.offset]
        if reader.offset != len(previous):
            raise ValueError("Unexpected data after Guerilla document list")

    output = bytearray(main)
    seen = set()
    for path in tag_paths:
        path = str(path)
        key = _path_key(path)
        if key in seen:
            continue
        seen.add(key)
        record = records.get(key)
        if record is None:
            record = (struct.pack("<I", 1) + _DEFAULT_CHILD + _write_path(path)
                      + struct.pack("<iiH", 0, 0, 0))
        output.extend(record)
    output.extend(struct.pack("<I", 0))
    return bytes(output)


def _guerilla_running(executable):
    """Check the executable path so other editing kits can remain open."""
    class ProcessEntry(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = kernel.Process32FirstW.argtypes
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            if entry.szExeFile.casefold() == executable.name.casefold():
                process = kernel.OpenProcess(0x1000, False, entry.th32ProcessID)
                if not process:
                    raise OSError("Cannot inspect a running Guerilla; close it and try again")
                try:
                    name = ctypes.create_unicode_buffer(32768)
                    size = wintypes.DWORD(len(name))
                    if not kernel.QueryFullProcessImageNameW(process, 0, name, ctypes.byref(size)):
                        raise ctypes.WinError(ctypes.get_last_error())
                    if _path_key(Path(name.value).resolve()) == _path_key(executable):
                        return True
                finally:
                    kernel.CloseHandle(process)
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(error)
        return False
    finally:
        kernel.CloseHandle(snapshot)


def _atomic_write(path, data):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare_guerilla_config(project_path, tag_paths):
    """Replace the startup tag list, backing up an existing cfg before writing."""
    project = Path(project_path).resolve()
    executable = project / "guerilla.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"Guerilla executable does not exist: {executable}")
    if _guerilla_running(executable):
        raise OSError("Close this project's Guerilla before opening tags from Foundry")
    paths = []
    for value in tag_paths:
        if not value:
            continue  # Asset launchers use empty strings for unavailable tags.
        path = Path(value).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Tag does not exist: {path}")
        paths.append(path)
    config = project / "guerilla.cfg"
    try:
        previous = config.read_bytes()
    except FileNotFoundError:
        previous = None
    updated = build_config(previous, paths)
    if updated == previous:
        return
    if previous is not None:
        _atomic_write(config.with_suffix(".cfg.bak"), previous)
    _atomic_write(config, updated)

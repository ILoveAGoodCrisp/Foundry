"""Run a Windows console program with live output in Foundry Output."""

import ctypes
from ctypes import wintypes
import subprocess
import threading

from . import foundry_output


_PSEUDOCONSOLE_ATTRIBUTE = 0x00020016
_EXTENDED_STARTUPINFO_PRESENT = 0x00080000


class _Coord(ctypes.Structure):
    _fields_ = (("X", ctypes.c_short), ("Y", ctypes.c_short))


class _StartupInfo(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD), ("reserved", wintypes.LPWSTR),
        ("desktop", wintypes.LPWSTR), ("title", wintypes.LPWSTR),
        ("x", wintypes.DWORD), ("y", wintypes.DWORD),
        ("x_size", wintypes.DWORD), ("y_size", wintypes.DWORD),
        ("x_count_chars", wintypes.DWORD), ("y_count_chars", wintypes.DWORD),
        ("fill_attribute", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("show_window", wintypes.WORD), ("reserved2", wintypes.WORD),
        ("reserved2_pointer", ctypes.c_void_p), ("stdin", wintypes.HANDLE),
        ("stdout", wintypes.HANDLE), ("stderr", wintypes.HANDLE),
    )


class _StartupInfoEx(ctypes.Structure):
    _fields_ = (("startup_info", _StartupInfo), ("attribute_list", ctypes.c_void_p))


class _ProcessInfo(ctypes.Structure):
    _fields_ = (("process", wintypes.HANDLE), ("thread", wintypes.HANDLE),
                ("process_id", wintypes.DWORD), ("thread_id", wintypes.DWORD))


def run_console_command(command, cwd, output_stream):
    """Attach Tool to ConPTY so its progress is flushed as console output."""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreatePipe.argtypes = (ctypes.POINTER(wintypes.HANDLE),
                                    ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p,
                                    wintypes.DWORD)
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.CreatePseudoConsole.argtypes = (_Coord, wintypes.HANDLE,
                                              wintypes.HANDLE, wintypes.DWORD,
                                              ctypes.POINTER(ctypes.c_void_p))
    kernel32.CreatePseudoConsole.restype = ctypes.c_long
    kernel32.ClosePseudoConsole.argtypes = (ctypes.c_void_p,)
    kernel32.InitializeProcThreadAttributeList.argtypes = (
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t))
    kernel32.UpdateProcThreadAttribute.argtypes = (
        ctypes.c_void_p, wintypes.DWORD, ctypes.c_size_t, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p)
    kernel32.CreateProcessW.argtypes = (
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(_StartupInfoEx), ctypes.POINTER(_ProcessInfo))
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p)
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.DeleteProcThreadAttributeList.argtypes = (ctypes.c_void_p,)

    input_read = wintypes.HANDLE()
    input_write = wintypes.HANDLE()
    output_read = wintypes.HANDLE()
    output_write = wintypes.HANDLE()
    pseudo_console = ctypes.c_void_p()
    attributes = None
    attributes_ready = False
    process_info = _ProcessInfo()
    reader = None
    try:
        if not kernel32.CreatePipe(ctypes.byref(input_read), ctypes.byref(input_write), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.CreatePipe(ctypes.byref(output_read), ctypes.byref(output_write), None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        result = kernel32.CreatePseudoConsole(_Coord(120, 40), input_read,
                                              output_write, 0,
                                              ctypes.byref(pseudo_console))
        if result:
            raise OSError(f"CreatePseudoConsole failed: 0x{result & 0xffffffff:08x}")
        size = ctypes.c_size_t()
        kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        attributes = ctypes.create_string_buffer(size.value)
        if not kernel32.InitializeProcThreadAttributeList(attributes, 1, 0,
                                                            ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        attributes_ready = True
        if not kernel32.UpdateProcThreadAttribute(
                attributes, 0, _PSEUDOCONSOLE_ATTRIBUTE,
                pseudo_console, ctypes.sizeof(pseudo_console), None, None):
            raise ctypes.WinError(ctypes.get_last_error())
        startup = _StartupInfoEx()
        startup.startup_info.cb = ctypes.sizeof(startup)
        startup.attribute_list = ctypes.cast(attributes, ctypes.c_void_p)
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
        if not kernel32.CreateProcessW(
                str(command[0]), command_line, None, None, False,
                _EXTENDED_STARTUPINFO_PRESENT, None, str(cwd),
                ctypes.byref(startup), ctypes.byref(process_info)):
            raise ctypes.WinError(ctypes.get_last_error())
        foundry_output.register_tool_process_handle(process_info.process)
        # Keep the pipe ends passed to ConPTY open through CreateProcess.
        kernel32.CloseHandle(input_read)
        input_read = wintypes.HANDLE()
        kernel32.CloseHandle(output_write)
        output_write = wintypes.HANDLE()

        def read_output():
            data = ctypes.create_string_buffer(4096)
            count = wintypes.DWORD()
            while kernel32.ReadFile(output_read, data, len(data), ctypes.byref(count), None):
                if count.value and output_stream is not None:
                    output_stream.write(data.raw[:count.value])

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        kernel32.WaitForSingleObject(process_info.process, 0xffffffff)
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(process_info.process, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        kernel32.ClosePseudoConsole(pseudo_console)
        pseudo_console = ctypes.c_void_p()
        reader.join()
        if exit_code.value:
            raise subprocess.CalledProcessError(exit_code.value, command)
        return 0
    finally:
        if process_info.thread:
            kernel32.CloseHandle(process_info.thread)
        if process_info.process:
            kernel32.CloseHandle(process_info.process)
        if attributes_ready:
            kernel32.DeleteProcThreadAttributeList(attributes)
        if pseudo_console:
            kernel32.ClosePseudoConsole(pseudo_console)
        for handle in (input_read, input_write, output_read, output_write):
            if handle:
                kernel32.CloseHandle(handle)

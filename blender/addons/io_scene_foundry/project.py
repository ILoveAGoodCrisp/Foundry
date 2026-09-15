"""Identify Halo projects from the tool executable's version resource."""
import ctypes
from ctypes import wintypes


# Identifier, display name, MCC name, icon, legacy datastore server.
GAMES = {
    "H1": ("halo1", "Halo 1", "Halo1", "halo_asset", ""),
    "H2": ("halo2", "Halo 2", "Halo2", "halo_asset", ""),
    "H3": ("halo3", "Halo 3", "Halo3", "halo_asset", ""),
    "H3ODST": ("halo3odst", "Halo 3 ODST", "Halo3ODST", "halo_asset", ""),
    "HR": ("reach", "Halo Reach", "HaloReach", "halo_reach", "bngtoolsql"),
    "H4": ("halo4", "Halo 4", "Halo4", "halo_4", "metawins"),
    "H2A": ("halo2a", "Halo 2AMP", "Halo2A", "halo_2amp", "episql.343i.selfhost.corp.microsoft.com"),
}
GAME_INFO = {info[0]: info for info in GAMES.values()}


def read_file_description(path):
    """Read FileDescription without launching the executable."""
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    version.VerQueryValueW.restype = wintypes.BOOL
    unused = wintypes.DWORD()
    size = version.GetFileVersionInfoSizeW(str(path), ctypes.byref(unused))
    if not size:
        raise OSError(f"No version information in {path}")
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, data):
        raise ctypes.WinError(ctypes.get_last_error())

    def query(key):
        value = ctypes.c_void_p()
        length = wintypes.UINT()
        if version.VerQueryValueW(data, key, ctypes.byref(value), ctypes.byref(length)):
            return value, length.value
        return None, 0

    value, length = query(r"\VarFileInfo\Translation")
    translations = []
    if value and length:
        words = ctypes.cast(value, ctypes.POINTER(wintypes.WORD))
        translations = [(words[i], words[i + 1]) for i in range(0, length // 2 - 1, 2)]
    for language, codepage in translations + [(0x0409, 0x04B0), (0x0409, 0x04E4)]:
        value, length = query(f"\\StringFileInfo\\{language:04x}{codepage:04x}\\FileDescription")
        if value and length:
            return ctypes.wstring_at(value, length).rstrip("\0").strip()
    raise OSError(f"No FileDescription in {path}")


def identify_game(tool_path):
    description = read_file_description(tool_path)
    for prefix, info in GAMES.items():
        if description == f"{prefix} Game Asset Compiler":
            return info[0]
    raise ValueError(f"Unsupported tool.exe description: {description!r}")

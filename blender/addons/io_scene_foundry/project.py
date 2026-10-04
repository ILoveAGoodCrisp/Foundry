"""Identify Halo projects from the tool executable's version resource."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


# Identifier, display name, MCC name, icon.
GAMES = {
    "H1": ("halo1", "Halo 1", "Halo1", "halo_1"),
    "H2": ("halo2", "Halo 2", "Halo2", "halo_2"),
    "H3": ("halo3", "Halo 3", "Halo3", "halo_3"),
    "H3ODST": ("halo3odst", "Halo 3 ODST", "Halo3ODST", "halo_odst"),
    "HR": ("reach", "Halo Reach", "HaloReach", "halo_reach"),
    "H4": ("halo4", "Halo 4", "Halo4", "halo_4"),
    "H2A": ("halo2a", "Halo 2AMP", "Halo2A", "halo_2amp"),
}
GAME_INFO = {info[0]: info for info in GAMES.values()}


@dataclass(frozen=True, slots=True)
class ExternalProject:
    """Ephemeral project context for a tag outside Foundry preferences."""

    name: str
    project_name: str
    project_path: str
    tags_directory: str
    data_directory: str
    game: str
    corinth: bool
    image_path: str = ""
    project_id: str = ""
    use_project_thumbnail: bool = False


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


def identify_game_from_tag(path: str | Path) -> str | None:
    """Return a title only when the tag container identifies it unambiguously."""
    try:
        with Path(path).open('rb') as stream:
            stream.seek(60)
            signature = stream.read(4)
    except OSError:
        return None
    if signature == b'blam':
        return 'halo1'
    if signature in {b'lbma', b'BMAL', b'BALM', b'!MLB'}:
        return 'halo2'

    try:
        import blam_tags

        tag = blam_tags.TagFile.read(path)
        game = blam_tags.Game.of(tag)
    except Exception:
        return None
    if game == blam_tags.Game.Halo1:
        return "halo1"
    if game == blam_tags.Game.Halo2:
        return "halo2"
    # H3, ODST, Reach, H4 and H2AMP intentionally share Game.Halo3.
    return None


def external_project_from_tag(path: str | Path, tags_root=None, data_root=None) -> ExternalProject:
    """Discover the owning editing kit without adding it to preferences."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    tags_directory = Path(tags_root).resolve() if tags_root else next(
        (parent for parent in path.parents if parent.name.casefold() == "tags"),
        None,
    )
    if tags_directory is None:
        raise ValueError(f"Choose the source tags folder for this tag: {path}")
    if not path.is_relative_to(tags_directory):
        raise ValueError(f"Tag is outside the selected source tags folder: {path}")

    game = identify_game_from_tag(path)
    tool_path = next((parent / 'tool.exe' for parent in tags_directory.parents
                      if (parent / 'tool.exe').is_file()), None)
    if game is None:
        if tool_path is None:
            raise RuntimeError(
                f"The tag container does not identify a specific MCC title and no tool.exe "
                f"was found above {path}"
            )
        game = identify_game(tool_path)

    project_path = tool_path.parent if tool_path is not None else tags_directory.parent
    project_name = project_path.name or game
    return ExternalProject(
        name=f"External {project_name}",
        project_name=project_name,
        project_path=str(project_path),
        tags_directory=str(tags_directory),
        data_directory=str(Path(data_root).resolve() if data_root else project_path / "data"),
        game=game,
        corinth=game in {"halo4", "halo2a"},
    )


def external_project_from_source(path, tags_root, data_root=None) -> ExternalProject:
    """An explicit folder pair for source formats which cannot identify a title."""
    tags = Path(tags_root).resolve()
    tool = next((parent / 'tool.exe' for parent in tags.parents
                 if (parent / 'tool.exe').is_file()), None)
    if tool is None:
        raise ValueError('Register the source editing kit as a Foundry project to identify this source asset\'s game')
    root = tool.parent
    data = Path(data_root).resolve() if data_root else root / 'data'
    if not Path(path).resolve().is_relative_to(data):
        raise ValueError('The source asset is outside Source Data Folder')
    game = identify_game(tool)
    return ExternalProject(
        name=f'External {root.name}', project_name=root.name, project_path=str(root),
        tags_directory=str(tags), data_directory=str(data), game=game,
        corinth=game in {'halo4', 'halo2a'})

"""Resolve full legacy shader paths to Tool material names.

Halo 1 finds shader tags by simple name.  Halo 2, Halo 3 and ODST use a
shader-collection prefix to constrain that lookup to the selected tag folder.
"""
from ..exceptions import ExportCancelled
from hashlib import sha1
from pathlib import Path, PureWindowsPath


COLLECTION_PATHS = {
    "halo2": PureWindowsPath("scenarios/shaders/shader_collections.shader_collections"),
    "halo3": PureWindowsPath("levels/shader_collections.txt"),
    "halo3odst": PureWindowsPath("levels/shader_collections.txt"),
}
FOUNDRY_HEADING = "; Foundry shader collections (generated from full shader paths)"


def _tag_path(value) -> PureWindowsPath:
    return PureWindowsPath(str(value).strip(" '\"").replace("/", "\\"))


def _directory_key(value) -> str:
    text = str(_tag_path(value)).rstrip("\\")
    return "" if text == "." else text.casefold()


class ShaderCollections:
    """An in-memory, append-only view of a Tool shader collection file."""

    def __init__(self, tags_dir, game):
        self.game = game
        relative_path = COLLECTION_PATHS.get(game)
        self.path = (Path(tags_dir).joinpath(*relative_path.parts)
                     if relative_path is not None else None)
        self.original = ""
        self.prefix_directories = {}
        self.used_prefixes = set()
        self.pending = {}
        if self.path is not None and self.path.is_file():
            self.original = self.path.read_text(encoding="utf-8-sig")
            self._parse(self.original)

    def _parse(self, text):
        entries = {}
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            fields = stripped.split(None, 1)
            if len(fields) == 2:
                prefix, directory = fields
                key = prefix.casefold()
                self.used_prefixes.add(key)
                original, directories = entries.setdefault(key, (prefix, set()))
                directories.add(_directory_key(directory))
        # Some stock files reuse an abbreviation for different folders. Such a
        # prefix is ambiguous regardless of Tool's first/last-entry behavior.
        self.prefix_directories = {
            key: (prefix, next(iter(directories)))
            for key, (prefix, directories) in entries.items()
            if len(directories) == 1
        }

    def material_name(self, shader_path) -> str:
        path = _tag_path(shader_path)
        if ".." in path.parts:
            raise ExportCancelled(f"Shader tag path cannot leave the tags directory: {shader_path}")
        suffix = path.suffix.casefold()
        shader_name = path.stem if self.game == "halo1" or suffix.startswith(".shader") else path.name
        if self.game == "halo1" or self.path is None or str(path.parent) == ".":
            return shader_name

        directory = str(path.parent)
        key = _directory_key(directory)
        for prefix, existing_directory in self.prefix_directories.values():
            if existing_directory == key:
                return shader_name if prefix == "*" else f"{prefix} {shader_name}"
        for prefix, pending_directory in self.pending.items():
            if _directory_key(pending_directory) == key:
                return f"{prefix} {shader_name}"

        digest = sha1(key.encode("utf-8")).hexdigest()
        length = 10
        prefix = "f_" + digest[:length]
        used = self.used_prefixes | {p.casefold() for p in self.pending}
        while prefix.casefold() in used:
            length += 1
            if length > len(digest):
                raise ExportCancelled(f"Could not allocate a shader collection prefix for {directory}")
            prefix = "f_" + digest[:length]
        self.pending[prefix] = directory
        return f"{prefix} {shader_name}"

    @property
    def dirty(self):
        return bool(self.pending)

    def text(self) -> str:
        if not self.pending:
            return self.original
        result = self.original.rstrip("\r\n")
        if FOUNDRY_HEADING not in self.original:
            result += ("\n\n" if result else "") + FOUNDRY_HEADING
        for prefix, directory in sorted(self.pending.items(), key=lambda item: item[0].casefold()):
            result += f"\n{prefix}\t{directory}"
        return result + "\n"

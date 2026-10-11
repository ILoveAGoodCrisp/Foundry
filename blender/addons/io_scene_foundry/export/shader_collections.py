"""Resolve full legacy shader paths to Tool material names.

Halo 1 finds shader tags by simple name.  Halo 2, Halo 3 and ODST use a
shader-collection prefix to constrain that lookup to the selected tag folder.
"""
from ..exceptions import ExportCancelled
from hashlib import sha1
from pathlib import Path, PureWindowsPath
import re


COLLECTION_PATHS = {
    "halo2": PureWindowsPath("scenarios/shaders/shader_collections.shader_collections"),
    "halo3": PureWindowsPath("levels/shader_collections.txt"),
    "halo3odst": PureWindowsPath("levels/shader_collections.txt"),
}
FOUNDRY_HEADING = "; Foundry shader collections (generated from full shader paths)"
MAX_PREFIX_LENGTH = 32
HALO1_MATERIAL_LENGTH = 31
HALO1_BSP_FLAGS = '%#!@*$^-&'


def halo1_shader_lookup(material_name, *, model=False):
    """Match H1 Tool's JMS string buffer, BSP flags and numeric suffix removal.

    Tool first truncates to 31 characters, removes BSP flags, then removes
    trailing digits (Max material-instance numbers). Dots are retained, as are
    later games' symbols. Model import does not remove BSP flags.
    """
    name = material_name[:HALO1_MATERIAL_LENGTH].lower()
    if not model:
        name = name.rstrip(HALO1_BSP_FLAGS)
    return name.rstrip('0123456789').rstrip()


def halo1_export_shader_name(name, identity=None):
    """Allocate a filename that survives both H1 compilers unchanged.

    Leave room for every BSP flag. Alphabetic hashes cannot themselves be
    interpreted as numeric instance suffixes, unlike a hexadecimal digest.
    """
    limit = HALO1_MATERIAL_LENGTH - len(HALO1_BSP_FLAGS)
    if (name and len(name) <= limit and not name.endswith((' ', '.'))
            and re.fullmatch(r'[A-Za-z0-9_ .()]+', name)
            and halo1_shader_lookup(name) == name.lower()):
        return name.lower()
    base = re.sub(r'[^A-Za-z0-9_]', '_', name).strip('_') or 'shader'
    digest = sha1((identity or name).casefold().encode('utf-8')).hexdigest()
    digest = digest.translate(str.maketrans('0123456789abcdef', 'abcdefghijklmnop'))[:10]
    return base[:limit - 11].lower() + '_' + digest


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
        self.halo1_names = {}
        self.halo1_names_reserved = False
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

    def reserve_halo1_paths(self, shader_paths) -> None:
        """Allocate stable names when H1's basename lookup is ambiguous.

        Reserve the export's paths together before writing material records so
        no earlier face is assigned a name that a later shader makes ambiguous.
        Ordinary unique names stay unchanged. Tool uses temporary alias tags
        for ambiguous names; compiled references are restored to full paths.
        """
        if self.game != 'halo1':
            return
        paths, groups = {}, {}
        for value in shader_paths:
            path = _tag_path(value)
            if '..' in path.parts or not path.suffix.casefold().startswith('.shader'):
                continue
            key = str(path).casefold()
            paths.setdefault(key, path)
            groups.setdefault(halo1_export_shader_name(path.stem, key).casefold(), set()).add(key)
        names = {key: halo1_export_shader_name(paths[key].stem, key)
                 for keys in groups.values() if len(keys) == 1 for key in keys}
        used = set(groups)
        for basename, keys in sorted(groups.items()):
            if len(keys) == 1:
                continue
            for key in sorted(keys):
                digest = sha1(key.encode('utf-8')).hexdigest()
                length = 10
                name = halo1_export_shader_name(paths[key].stem + '_' + digest[:length], key)
                while name.casefold() in used:
                    length += 1
                    if length > len(digest):
                        raise ExportCancelled(f'Could not allocate a Halo 1 shader name for {paths[key]}')
                    name = halo1_export_shader_name(paths[key].stem + '_' + digest[:length], key + digest[:length])
                names[key] = name
                used.add(name.casefold())
        self.halo1_names = names
        self.halo1_names_reserved = True

    def material_name(self, shader_path) -> str:
        path = _tag_path(shader_path)
        if ".." in path.parts:
            raise ExportCancelled(f"Shader tag path cannot leave the tags directory: {shader_path}")
        suffix = path.suffix.casefold()
        shader_name = path.stem if self.game == "halo1" or suffix.startswith(".shader") else path.name
        if self.game == 'halo1':
            return self.halo1_names.get(str(path).casefold(), halo1_export_shader_name(shader_name, str(path)))
        if self.path is None or str(path.parent) == ".":
            return shader_name

        directory = str(path.parent)
        key = _directory_key(directory)
        for prefix, existing_directory in self.prefix_directories.values():
            if existing_directory == key:
                return shader_name if prefix == "*" else f"{prefix} {shader_name}"
        for prefix, pending_directory in self.pending.items():
            if _directory_key(pending_directory) == key:
                return f"{prefix} {shader_name}"

        # Use the closest asset folder, skipping generic shader folders. Prefixes
        # are whitespace-delimited in the collection file, so normalize spaces.
        asset_name = next((part for part in reversed(_tag_path(key).parts)
                           if part != "shaders"), "collection")
        asset_name = "_".join(asset_name.split())
        prefix = asset_name[:MAX_PREFIX_LENGTH]
        used = self.used_prefixes | {p.casefold() for p in self.pending}
        duplicate = 0
        while prefix.casefold() in used:
            duplicate += 1
            number = duplicate
            letters = ""
            while number:
                number, remainder = divmod(number - 1, 26)
                letters = chr(ord("a") + remainder) + letters
            suffix = "_" + letters
            if len(suffix) >= MAX_PREFIX_LENGTH:
                raise ExportCancelled(f"Could not allocate a shader collection prefix for {directory}")
            prefix = asset_name[:MAX_PREFIX_LENGTH - len(suffix)] + suffix
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

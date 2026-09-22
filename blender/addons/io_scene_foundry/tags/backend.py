"""Typed blam-tags lifecycle without Blender or ManagedBlam dependencies."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
import importlib
import json
from os import PathLike
from dataclasses import dataclass
from functools import lru_cache
from types import TracebackType
from typing import TYPE_CHECKING, Protocol, Self, cast, runtime_checkable

if TYPE_CHECKING:
    import blam_tags


class BlamTagsModule(Protocol):
    """Runtime module surface used by the backend's lazy wheel import."""

    TagFile: type[blam_tags.TagFile]

    def format_group_tag(self, tag: int) -> str: ...

    def parse_group_tag(self, value: str) -> int | None: ...


@runtime_checkable
class RelativeTagPath(Protocol):
    """Path surface shared by native references and remaining legacy callers."""

    @property
    def RelativePathWithExtension(self) -> str: ...


class ArrayValue(Protocol):
    """Native blam-tags numeric value that exposes its components."""

    def to_array(self) -> Sequence[float]: ...


TagPathInput = str | PathLike[str] | RelativeTagPath
ControlPoint = tuple[tuple[float, float, float], tuple[float, float, float, float]]

PROFILES: dict[str, str] = {
    'halo1': 'haloce_mcc', 'halo2': 'halo2_mcc', 'halo3': 'halo3_mcc',
    'halo3odst': 'halo3odst_mcc', 'reach': 'haloreach_mcc',
    'halo4': 'halo4_mcc', 'halo2a': 'halo2amp_mcc',
}


@dataclass(frozen=True)
class TagReference:
    """Project-bound reference. Names match existing Foundry consumers during migration."""
    root: Path
    RelativePath: str
    Extension: str

    @property
    def RelativePathWithExtension(self) -> str:
        return f'{self.RelativePath}.{self.Extension}'

    @property
    def Filename(self) -> str:
        return str(self.root / self.RelativePathWithExtension)

    @property
    def ShortName(self) -> str:
        return Path(self.RelativePath).name

    @property
    def ShortNameWithExtension(self) -> str:
        return f'{self.ShortName}.{self.Extension}'

    def ToString(self) -> str:
        return self.RelativePathWithExtension

    def IsTagFileAccessible(self) -> bool:
        return Path(self.Filename).is_file()


@lru_cache(maxsize=32)
def group_names(metadata_path: str | PathLike[str]) -> dict[str, str]:
    names = cast(dict[str, str],
                 json.loads(Path(metadata_path).read_text(encoding='utf-8'))['tag_index'])
    # blam-tags formats integer group codes without their trailing space padding.
    return {group.rstrip(): extension for group, extension in names.items()}


class TagDocument:
    """Explicit change tracking; failed operations never implicitly save."""

    def __init__(self, path: TagPathInput, *, tags_root: str | PathLike[str], game: str,
                 extension: str | None = None, must_exist: bool = False,
                 always_save: bool = False,
                 definitions: str | PathLike[str] | None = None) -> None:
        self.valid: bool = False
        self._tag: blam_tags.TagFile | None = None
        self.tag_has_changes: bool = False
        self.always_save: bool = always_save
        if game not in PROFILES:
            raise ValueError(f'Unsupported Foundry game: {game!r}')
        self.game: str = game
        self.definitions: Path = Path(definitions) if definitions is not None else Path(__file__).parent / 'definitions'
        self.definitions_profile: str = PROFILES[game]
        self.tags_root: Path = Path(tags_root).resolve()
        if isinstance(path, RelativeTagPath):
            path = path.RelativePathWithExtension
        path = Path(path)
        if extension:
            path = path.with_suffix('.' + extension)
        self.system_path: Path = (self.tags_root / path).resolve()
        try:
            self.path: str = str(self.system_path.relative_to(self.tags_root))
        except ValueError as exc:
            raise ValueError(f'Tag must be inside {self.tags_root}: {path}') from exc
        try:
            self.api: BlamTagsModule = cast(
                BlamTagsModule, importlib.import_module('blam_tags'))
        except ImportError as exc:
            raise RuntimeError('blam-tags is unavailable. Install Foundry with its blam-tags wheel.') from exc
        self.tag_is_new: bool = not self.system_path.exists()
        schema = self.definitions / self.definitions_profile / (self.system_path.suffix[1:] + '.json')
        if self.tag_is_new:
            if must_exist:
                raise FileNotFoundError(self.system_path)
            if not schema.is_file():
                raise FileNotFoundError(f'Missing blam-tags schema: {schema}')
            if game in {'halo1', 'halo2'}:
                self._tag = self.api.TagFile.new_classic(schema, game)
                self.tag_has_changes = True
                self.valid = True
                return
            self._tag = self.api.TagFile.new(schema)
            self.tag_has_changes = True
        else:
            if game in {'halo1', 'halo2'}:
                if not schema.is_file():
                    raise FileNotFoundError(f'Missing blam-tags schema: {schema}')
                self._tag = self.api.TagFile.read_classic(self.system_path, schema)
            else:
                self._tag = self.api.TagFile.read(self.system_path)
        self.valid = True

    @property
    def tag(self) -> blam_tags.TagFile:
        """Return the open wheel handle, preserving its concrete type for callers."""
        if self._tag is None:
            raise RuntimeError('Tag document is closed')
        return self._tag

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_value: BaseException | None,
                 traceback: TracebackType | None) -> None:
        try:
            if exc_type is None and self.valid and (self.tag_has_changes or self.always_save):
                self.save()
        finally:
            self._tag = None
            self.valid = False

    def save(self) -> None:
        if not self.valid:
            raise RuntimeError('Cannot save a closed tag')
        self.system_path.parent.mkdir(parents=True, exist_ok=True)
        self.tag.write_atomic(self.system_path)
        self.tag_has_changes = False

    def required_field(self, struct: blam_tags.TagStruct, name: str) -> blam_tags.TagField:
        field = struct.field(name)
        if field is None:
            raise ValueError(f'{self.path}: missing field {name!r} in {struct.path!r}')
        return field

    def value(self, struct: blam_tags.TagStruct, name: str) -> object:
        return self.required_field(struct, name).value

    def block(self, struct: blam_tags.TagStruct, name: str) -> blam_tags.TagBlock:
        block = self.required_field(struct, name).as_block()
        if block is None:
            raise TypeError(f'{self.path}: {name!r} is not a block')
        return block

    def reference(self, struct: blam_tags.TagStruct, name: str) -> TagReference | None:
        value = self.value(struct, name)
        if value is None:
            return None
        group, path = cast(tuple[int, str], value)
        if not path:
            return None
        group = self.api.format_group_tag(group)
        extension = group_names(str(self.definitions / PROFILES[self.game] / '_meta.json')).get(group)
        if extension is None:
            raise ValueError(f'{self.path}: unknown tag group {group!r}')
        return TagReference(self.tags_root, path.replace('/', '\\'), extension)

    def reference_from_path(self, path: str | PathLike[str]) -> TagReference:
        path = (self.tags_root / Path(path)).resolve().relative_to(self.tags_root)
        if not path.suffix:
            raise ValueError(f'Tag reference needs an extension: {path}')
        return TagReference(self.tags_root, str(path.with_suffix('')), path.suffix[1:])

    def set_reference(self, struct: blam_tags.TagStruct, name: str,
                      path: TagPathInput | None) -> None:
        value: tuple[int, str] | None = None
        if path is not None:
            if isinstance(path, RelativeTagPath):
                path = path.RelativePathWithExtension
            reference = self.reference_from_path(path)
            names = group_names(str(self.definitions / PROFILES[self.game] / '_meta.json'))
            groups = [group for group, extension in names.items() if extension == reference.Extension]
            if len(groups) != 1:
                raise ValueError(f'Unknown or ambiguous tag extension: {reference.Extension}')
            group = self.api.parse_group_tag(groups[0])
            if group is None:
                raise ValueError(f'Invalid tag group: {groups[0]!r}')
            value = group, reference.RelativePath
        field = self.required_field(struct, name)
        if field.value != value:
            field.set(value)
            self.tag_has_changes = True

    @staticmethod
    def path_exists(path: TagReference | None) -> bool:
        return path is not None and Path(path.Filename).is_file()


class ReferenceField:
    """Small compatibility boundary for callers using model.reference_*.Path."""
    def __init__(self, document: TagDocument, name: str) -> None:
        self.document, self.name = document, name

    @property
    def Path(self) -> TagReference | None:
        return self.document.reference(self.document.tag.root(), self.name)

    @Path.setter
    def Path(self, value: TagPathInput | None) -> None:
        self.document.set_reference(self.document.tag.root(), self.name, value)


class CameraTrackDocument(TagDocument):
    """Control points are (position xyz, quaternion ijkw) pairs."""

    def __init__(self, path: TagPathInput, *, tags_root: str | PathLike[str],
                 game: str, must_exist: bool = False, always_save: bool = False,
                 definitions: str | PathLike[str] | None = None) -> None:
        super().__init__(path, tags_root=tags_root, game=game,
                         extension='camera_track', must_exist=must_exist,
                         always_save=always_save, definitions=definitions)

    def control_points(self) -> list[ControlPoint]:
        block = self.block(self.tag.root(), 'control points')
        points: list[ControlPoint] = []
        for index in range(len(block)):
            element = block[index]
            position = cast(ArrayValue, self.required_field(element, 'position').value)
            orientation = cast(ArrayValue, self.required_field(element, 'orientation').value)
            points.append((tuple(position.to_array()), tuple(orientation.to_array())))
        return points

    def replace_control_points(self, points: Iterable[ControlPoint]) -> None:
        points = list(points)
        if not 1 <= len(points) <= 16:
            raise ValueError('Camera tracks require between 1 and 16 control points')
        if any(len(p) != 3 or len(q) != 4 for p, q in points):
            raise ValueError('Expected position xyz and quaternion ijkw')
        block = self.block(self.tag.root(), 'control points')
        block.clear()
        for position, orientation in points:
            # Adding invalidates element handles; fetch after each addition.
            element = block[block.add()]
            for name, value in (('position', position), ('orientation', orientation)):
                field = self.required_field(element, name)
                field.set(type(field.value)(*value))
        self.tag_has_changes = True

"""Tag lifecycle without Blender or ManagedBlam dependencies."""
from pathlib import Path
import importlib
import json
from dataclasses import dataclass
from functools import lru_cache

PROFILES = {'halo1': 'haloce_mcc', 'halo2': 'halo2_mcc', 'halo3': 'halo3_mcc',
            'halo3odst': 'halo3odst_mcc', 'reach': 'haloreach_mcc',
            'halo4': 'halo4_mcc', 'halo2a': 'halo2amp_mcc'}


@dataclass(frozen=True)
class TagReference:
    """Project-bound reference. Names match existing Foundry consumers during migration."""
    root: Path
    RelativePath: str
    Extension: str

    @property
    def RelativePathWithExtension(self):
        return f'{self.RelativePath}.{self.Extension}'

    @property
    def Filename(self):
        return str(self.root / self.RelativePathWithExtension)

    @property
    def ShortName(self):
        return Path(self.RelativePath).name

    def ToString(self):
        return self.RelativePathWithExtension

    def IsTagFileAccessible(self):
        return Path(self.Filename).is_file()


@lru_cache(maxsize=32)
def group_names(metadata_path):
    return json.loads(Path(metadata_path).read_text(encoding='utf-8'))['tag_index']


class TagDocument:
    """Explicit change tracking; failed operations never implicitly save."""

    def __init__(self, path, *, tags_root, game, extension=None,
                 must_exist=False, always_save=False, definitions=None):
        self.valid = False
        self.tag = None
        self.tag_has_changes = False
        self.always_save = always_save
        if game not in PROFILES:
            raise ValueError(f'Unsupported Foundry game: {game!r}')
        self.game = game
        self.definitions = Path(definitions) if definitions is not None else Path(__file__).parent / 'definitions'
        self.tags_root = Path(tags_root).resolve()
        if hasattr(path, 'RelativePathWithExtension'):
            path = path.RelativePathWithExtension
        path = Path(path)
        if extension:
            path = path.with_suffix('.' + extension)
        self.system_path = (self.tags_root / path).resolve()
        try:
            self.path = str(self.system_path.relative_to(self.tags_root))
        except ValueError as exc:
            raise ValueError(f'Tag must be inside {self.tags_root}: {path}') from exc
        try:
            self.api = importlib.import_module('blam_tags')
        except ImportError as exc:
            raise RuntimeError('blam-tags is unavailable. Install Foundry with its blam-tags wheel.') from exc
        self.tag_is_new = not self.system_path.exists()
        if self.tag_is_new:
            if must_exist:
                raise FileNotFoundError(self.system_path)
            schema = self.definitions / PROFILES[game] / (self.system_path.suffix[1:] + '.json')
            if not schema.is_file():
                raise FileNotFoundError(f'Missing blam-tags schema: {schema}')
            self.tag = self.api.TagFile.new(schema)
            self.tag_has_changes = True
        else:
            self.tag = self.api.TagFile.read(self.system_path)
        self.valid = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None and self.valid and (self.tag_has_changes or self.always_save):
                self.save()
        finally:
            self.tag = None
            self.valid = False

    def save(self):
        if not self.valid:
            raise RuntimeError('Cannot save a closed tag')
        self.system_path.parent.mkdir(parents=True, exist_ok=True)
        self.tag.write_atomic(self.system_path)
        self.tag_has_changes = False

    def required_field(self, struct, name):
        field = struct.field(name)
        if field is None:
            raise ValueError(f'{self.path}: missing field {name!r} in {struct.path!r}')
        return field

    def value(self, struct, name):
        return self.required_field(struct, name).value

    def block(self, struct, name):
        block = self.required_field(struct, name).as_block()
        if block is None:
            raise TypeError(f'{self.path}: {name!r} is not a block')
        return block

    def reference(self, struct, name):
        value = self.value(struct, name)
        if value is None:
            return None
        group, path = value
        group = self.api.format_group_tag(group)
        extension = group_names(str(self.definitions / PROFILES[self.game] / '_meta.json')).get(group)
        if extension is None:
            raise ValueError(f'{self.path}: unknown tag group {group!r}')
        return TagReference(self.tags_root, path.replace('/', '\\'), extension)

    def reference_from_path(self, path):
        path = (self.tags_root / Path(path)).resolve().relative_to(self.tags_root)
        if not path.suffix:
            raise ValueError(f'Tag reference needs an extension: {path}')
        return TagReference(self.tags_root, str(path.with_suffix('')), path.suffix[1:])

    def set_reference(self, struct, name, path):
        value = None
        if path is not None:
            if hasattr(path, 'RelativePathWithExtension'):
                path = path.RelativePathWithExtension
            reference = self.reference_from_path(path)
            names = group_names(str(self.definitions / PROFILES[self.game] / '_meta.json'))
            groups = [group for group, extension in names.items() if extension == reference.Extension]
            if len(groups) != 1:
                raise ValueError(f'Unknown or ambiguous tag extension: {reference.Extension}')
            value = self.api.parse_group_tag(groups[0]), reference.RelativePath
        field = self.required_field(struct, name)
        if field.value != value:
            field.set(value)
            self.tag_has_changes = True

    @staticmethod
    def path_exists(path):
        return path is not None and Path(path.Filename).is_file()


class ReferenceField:
    """Small compatibility boundary for callers using model.reference_*.Path."""
    def __init__(self, document, name):
        self.document, self.name = document, name

    @property
    def Path(self):
        return self.document.reference(self.document.tag.root(), self.name)

    @Path.setter
    def Path(self, value):
        self.document.set_reference(self.document.tag.root(), self.name, value)


class CameraTrackDocument(TagDocument):
    """Control points are (position xyz, quaternion ijkw) pairs."""

    def __init__(self, path, **kwargs):
        if kwargs.get('game') in {'halo1', 'halo2'}:
            raise NotImplementedError(
                'The camera-track pilot supports H3 through H2AMP. H1/H2 need '
                'Python bindings for classic tag reading and creation first.')
        super().__init__(path, extension='camera_track', **kwargs)

    def control_points(self):
        block = self.required_field(self.tag.root(), 'control points').as_block()
        points = []
        for index in range(len(block)):
            element = block[index]
            position = self.required_field(element, 'position').value
            orientation = self.required_field(element, 'orientation').value
            points.append((tuple(position.to_array()), tuple(orientation.to_array())))
        return points

    def replace_control_points(self, points):
        points = list(points)
        if not 1 <= len(points) <= 16:
            raise ValueError('Camera tracks require between 1 and 16 control points')
        if any(len(p) != 3 or len(q) != 4 for p, q in points):
            raise ValueError('Expected position xyz and quaternion ijkw')
        block = self.required_field(self.tag.root(), 'control points').as_block()
        block.clear()
        for position, orientation in points:
            # Adding invalidates element handles; fetch after each addition.
            element = block[block.add()]
            for name, value in (('position', position), ('orientation', orientation)):
                field = self.required_field(element, name)
                field.set(type(field.value)(*value))
        self.tag_has_changes = True

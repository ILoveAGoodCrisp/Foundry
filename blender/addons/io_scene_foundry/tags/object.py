"""Object metadata using native field names, without Blender or .NET."""
from __future__ import annotations

from typing import TYPE_CHECKING
from pathlib import Path

from .backend import TagDocument, TagPathInput
from .model import ModelDocument
from dataclasses import dataclass
from .backend import TagReference

if TYPE_CHECKING:
    import blam_tags


@dataclass(frozen=True)
class ObjectAttachment:
    reference: TagReference | None
    marker: str
    primary_scale: str
    secondary_scale: str


class CinematicCopyUnsupported(RuntimeError):
    """The source layout cannot be copied losslessly to the scenery schema."""


class ObjectModelReference:
    def __init__(self, document: ObjectDocument) -> None:
        self.document = document

    @property
    def Path(self) -> TagReference | None:
        return self.document.reference(self.document.object_struct(), 'model')

    @Path.setter
    def Path(self, path: TagPathInput | None) -> None:
        self.document.set_reference(self.document.object_struct(), 'model', path)


class ObjectDocument(TagDocument):
    reference_model = property(lambda self: ObjectModelReference(self))

    def nested(self, struct: blam_tags.TagStruct, name: str) -> blam_tags.TagStruct:
        result = self.required_field(struct, name).as_struct()
        if result is None:
            raise TypeError(f'{self.path}: {name!r} is not a struct')
        return result

    def object_struct(self) -> blam_tags.TagStruct:
        struct = self.tag.root()
        for _ in range(4):
            if struct.field('model') is not None:
                return struct
            for name in ('object', 'unit', 'item', 'device'):
                if struct.field(name) is not None:
                    struct = self.nested(struct, name)
                    break
            else:
                break
        raise ValueError(f'{self.path}: no inherited object struct')

    def get_default_variant(self):
        field = self.object_struct().field('default model variant')
        return '' if field is None else field.value

    def get_model_tag_path(self):
        ref = self.reference_model.Path
        return ref.RelativePathWithExtension if ref else None

    def get_model_tag_path_full(self):
        ref = self.reference_model.Path
        return ref.Filename if ref else None

    def get_halo1_model_paths(self, optional_tag_root: str | Path | None = None) -> tuple[str, str, str, str]:
        """Return H1 render, collision and animation references.

        H1's ``physics`` reference is an object-properties tag, not the geometric
        ``physics_model`` consumed by the Blender physics importer.
        """
        struct = self.object_struct()
        paths = []
        for name in ('model', 'collision model', 'animation graph'):
            reference = self.reference(struct, name)
            if reference is None or not reference.RelativePath:
                paths.append('')
            elif optional_tag_root is None:
                paths.append(reference.Filename)
            else:
                paths.append(str(Path(optional_tag_root) / reference.RelativePathWithExtension))
        return paths[0], paths[1], paths[2], ''

    def set_model_tag_path(self, path):
        self.reference_model.Path = path

    def set_halo1_model_paths(self, model: TagPathInput,
                              collision: TagPathInput | None = None,
                              animation: TagPathInput | None = None,
                              physics: TagPathInput | None = None) -> None:
        """Set the four independent model references used by H1 objects."""
        if self.game != 'halo1':
            raise ValueError('Independent model references are specific to Halo 1')
        struct = self.object_struct()
        for field_name, path in (
            ('model', model), ('collision model', collision),
            ('animation graph', animation), ('physics', physics),
        ):
            if path is not None:
                self.set_reference(struct, field_name, path)

    def get_variants(self):
        ref = self.reference_model.Path
        if not self.path_exists(ref):
            return []
        with ModelDocument(ref, tags_root=self.tags_root, game=self.game,
                           definitions=self.definitions, must_exist=True) as model:
            return model.get_model_variants()

    def get_change_colors(self, variant=''):
        colors = self.block(self.object_struct(), 'change colors')
        if not len(colors):
            return None
        result = [(1.0, 1.0, 1.0, 1.0)] * 4
        variant = variant or self.get_default_variant()
        if not variant:
            return result
        has_data = False
        for index, color in enumerate(colors):
            for permutation in self.block(color, 'initial permutations'):
                has_data = True
                name = self.value(permutation, 'variant name')
                if name == variant or (variant == 'default' and not name):
                    rgb = self.value(permutation, 'color upper bound')
                    if index < len(result):
                        result[index] = [rgb.red, rgb.green, rgb.blue, 1.0]
                    break
        return result if has_data else None

    def weapon_value(self, method, find_weapon, default):
        if self.system_path.suffix == '.weapon':
            return method(self)
        sibling = self.system_path.with_suffix('.weapon')
        if find_weapon and sibling.is_file():
            with ObjectDocument(sibling, tags_root=self.tags_root, game=self.game,
                                definitions=self.definitions, must_exist=True) as weapon:
                return method(weapon)
        return default

    def get_magazine_size(self, find_weapon=False):
        def read(doc):
            magazines = doc.block(doc.tag.root(), 'magazines')
            return doc.value(magazines[0], 'rounds loaded maximum') if len(magazines) else 0
        return self.weapon_value(read, find_weapon, 0)

    def get_uses_tether(self, find_weapon=False):
        def read(doc):
            if doc.game == 'halo1':
                return False
            for trigger in doc.block(doc.tag.root(), 'new triggers'):
                value = doc.value(trigger, 'behavior')
                if (value == 3 and doc.game not in {'halo3', 'halo3odst'}) or str(value).split('#', 1)[0] == 'latch-tether':
                    return True
            return False
        return self.weapon_value(read, find_weapon, False)

    def get_function_names(self):
        return [self.value(e, 'export name') for e in self.block(self.object_struct(), 'functions')]

    def get_attachments(self):
        """Detached records remain usable after the tag is closed."""
        return [ObjectAttachment(self.reference(e, 'type'), self.value(e, 'marker'),
                                 self.value(e, 'primary scale'), self.value(e, 'secondary scale'))
                for e in self.block(self.object_struct(), 'attachments')]

    def get_seat_names(self):
        return [self.value(e, 'label') for e in self.block(self.nested(self.tag.root(), 'unit'), 'seats')]

    def get_weapon_names(self):
        return self.value(self.tag.root(), 'weapon class'), self.value(self.tag.root(), 'weapon name')

    def get_unit_weapons(self):
        unit = self.nested(self.tag.root(), 'unit')
        if unit.field('weapons') is None:
            return []
        return [ref for e in self.block(unit, 'weapons') if (ref := self.reference(e, 'weapon'))]

    def get_weapon_markers(self):
        unit = self.nested(self.tag.root(), 'unit')
        return (self.value(unit, 'right_hand_node'),
                self.value(self.nested(unit, 'more damn nodes'), 'preferred_gun_node'))

    def first_person(self):
        return self.block(self.nested(self.tag.root(), 'player interface'), 'first person')

    def get_fp_animation(self, index):
        block = self.first_person()
        return self.reference(block[index], 'first person animations') if 0 <= index < len(block) else None

    def set_fp_weapon_render_model(self, path):
        ref = self.reference_from_path(path)
        if not self.path_exists(ref):
            return
        block = self.first_person()
        while len(block) < 2:
            block.add()
            self.tag_has_changes = True
        for element in block:
            self.set_reference(element, 'first person model', ref)

    def set_structure_lighting(self, path):
        self.set_reference(self.tag.root(), 'Structure Lighting Tag', path)

    def copy_cinematic_object(self, source, ammo_functions=()):
        """Populate scenery from a same-project object; save only on successful context exit."""
        if self.system_path.suffix != '.scenery' or self.game != source.game or self.tags_root != source.tags_root:
            raise ValueError('Cinematic copying requires scenery in the source project and game')
        target = self.object_struct()
        original = source.object_struct()
        if not hasattr(self.required_field(target, 'model'), 'copy_value_from'):
            raise RuntimeError('Rebuild the blam-tags wheel: cinematic copying needs native copy APIs')
        source_flags = source.required_field(original, 'flags')
        target_flags = self.required_field(target, 'flags')
        for name in ('does not cast shadow', 'search cardinal direction lightmaps on failure',
                     'object scales attachments', 'sample enviroment lighting only ignore object lighting'):
            try:
                enabled = source_flags.get_flag(name)
            except KeyError:
                continue  # These flags do not exist in every title.
            target_flags.set_flag(name, enabled)
        for name in ('model', 'bounding radius', 'bounding offset', 'lightmap shadow mode',
                     'sweetener size', 'dynamic light sphere radius', 'dynamic light sphere offset',
                     'default model variant', 'crate object', 'creation effect', 'material effects',
                     'simulation_interpolation'):
            if original.field(name) is None:
                continue
            self.required_field(target, name).copy_value_from(source.required_field(original, name))
        for name in ('functions', 'attachments', 'hull surfaces', 'jetwash', 'widgets',
                     'change colors', 'spawn effects'):
            if original.field(name) is None and target.field(name) is None:
                continue
            source_block = source.block(original, name)
            target_block = self.block(target, name)
            if not len(source_block):
                target_block.clear()
                continue
            try:
                target_block.copy_from(source_block)
            except ValueError as error:
                if name == 'change colors' and self.game == 'halo3' and self._copy_h3_colors(source_block, target_block):
                    continue
                raise CinematicCopyUnsupported(f'{source.path}: {name}: {error}') from error
        functions = self.block(target, 'functions')
        names = set()
        for element in functions:
            self.required_field(element, 'import name').set('zero')
            names.add(self.value(element, 'export name'))
        if source.system_path.suffix == '.weapon':
            for name in ammo_functions:
                if name in names:
                    continue
                element = functions[functions.add()]
                self.required_field(element, 'import name').set('zero')
                self.required_field(element, 'export name').set(name)
                names.add(name)
        self.tag_has_changes = True

    @staticmethod
    def _h3_color_function_fields(element):
        """Accept only known fields and zero-filled gaps in the two known H3 layouts."""
        expected = [('scale flags', 'long flags', 4), ('color lower bound', 'real rgb color', 12),
                    ('color upper bound', 'real rgb color', 12), ('darken by', 'string id', 4),
                    ('scale by', 'string id', 4)]
        if not hasattr(element, 'raw_bytes'):
            raise RuntimeError('Rebuild the blam-tags wheel: H3 color conversion needs layout-byte access')
        raw = element.raw_bytes
        if element.size not in (36, 40) or len(raw) != element.size:
            return None
        fields = [f for f in element.fields() if f.type_name not in ('pad', 'skip')
                  and not (f.type_name == 'custom' and f.value in (None, b''))]
        if [(f.clean_name, f.type_name, f.wire_width) for f in fields] != expected:
            return None
        covered = set()
        for field in fields:
            offsets = set(range(field.offset, field.offset + field.wire_width))
            if field.offset + field.wire_width > len(raw) or covered.intersection(offsets):
                return None
            covered.update(offsets)
        if any(value for offset, value in enumerate(raw) if offset not in covered):
            return None
        return fields

    def _copy_h3_colors(self, source, target):
        """Rebuild H3 colors when the only discarded function bytes are zero padding."""
        expected = [('initial permutations', 'block'), ('functions', 'block')]
        def fields(element):
            # Shipped layouts include an empty editor marker before these blocks.
            return [(f.clean_name, f.type_name) for f in element.fields()
                    if not (f.type_name == 'custom' and f.value in (None, b''))]
        for element in source:
            if fields(element) != expected:
                return False
            for function in self.block(element, 'functions'):
                if self._h3_color_function_fields(function) is None:
                    return False
        target.clear()
        for element in source:
            copied = target[target.add()]
            if fields(copied) != expected:
                raise CinematicCopyUnsupported('Unexpected H3 change-color container layout')
            try:
                self.block(copied, 'initial permutations').copy_from(self.block(element, 'initial permutations'))
            except ValueError as error:
                raise CinematicCopyUnsupported(f'Incompatible H3 color permutations: {error}') from error
            functions = self.block(copied, 'functions')
            for function in self.block(element, 'functions'):
                converted = functions[functions.add()]
                if self._h3_color_function_fields(converted) is None:
                    raise CinematicCopyUnsupported('Unexpected destination H3 color-function layout')
                for field in self._h3_color_function_fields(function):
                    self.required_field(converted, field.clean_name).copy_value_from(field)
        return True

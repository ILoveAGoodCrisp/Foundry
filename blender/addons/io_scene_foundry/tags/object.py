"""Object metadata using native field names, without Blender or .NET."""
from .backend import TagDocument
from .model import ModelDocument
from dataclasses import dataclass
from .backend import TagReference


@dataclass(frozen=True)
class ObjectAttachment:
    reference: TagReference | None
    marker: str
    primary_scale: str
    secondary_scale: str


class ObjectModelReference:
    def __init__(self, document):
        self.document = document

    @property
    def Path(self):
        return self.document.reference(self.document.object_struct(), 'model')

    @Path.setter
    def Path(self, path):
        self.document.set_reference(self.document.object_struct(), 'model', path)


class ObjectDocument(TagDocument):
    reference_model = property(lambda self: ObjectModelReference(self))

    def nested(self, struct, name):
        result = self.required_field(struct, name).as_struct()
        if result is None:
            raise TypeError(f'{self.path}: {name!r} is not a struct')
        return result

    def object_struct(self):
        struct = self.tag.root()
        for _ in range(4):
            if struct.field('default model variant') is not None and struct.field('model') is not None:
                return struct
            for name in ('object', 'unit', 'item', 'device'):
                if struct.field(name) is not None:
                    struct = self.nested(struct, name)
                    break
            else:
                break
        raise ValueError(f'{self.path}: no inherited object struct')

    def get_default_variant(self):
        return self.value(self.object_struct(), 'default model variant')

    def get_model_tag_path(self):
        ref = self.reference_model.Path
        return ref.RelativePathWithExtension if ref else None

    def get_model_tag_path_full(self):
        ref = self.reference_model.Path
        return ref.Filename if ref else None

    def set_model_tag_path(self, path):
        self.reference_model.Path = path

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

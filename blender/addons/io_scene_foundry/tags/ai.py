"""Resolve AI tags to the unit and appearance used by the object importer."""
from dataclasses import dataclass
from pathlib import Path

from .backend import TagDocument, TagReference


AI_TAG_EXTENSIONS = ('.actor', '.actor_variant', '.character')


@dataclass(frozen=True)
class AIUnitImport:
    unit: TagReference
    change_colors: tuple = ()
    forced_shader_permutation: int | None = None
    actor_variant: TagReference | None = None
    weapon: TagReference | None = None

    def override_change_colors(self, colors):
        """Override authored slots only; retain the unit's other color slots."""
        if not self.change_colors:
            return colors
        result = list(colors) if colors is not None else [(1.0, 1.0, 1.0, 1.0)] * 4
        for index, color in enumerate(self.change_colors[:4]):
            result[index] = color
        return result


class AIUnitDocument(TagDocument):
    def resolve_import(self, visited=None):
        visited = set() if visited is None else visited
        if self.system_path in visited:
            raise ValueError(f'Circular AI tag reference: {self.path}')
        visited.add(self.system_path)
        extension = self.system_path.suffix.lower()
        if extension in {'.actor', '.actor_variant'} and self.game != 'halo1':
            raise ValueError('Actor and actor_variant tags are specific to Halo 1')
        if extension == '.character' and self.game == 'halo1':
            raise ValueError('Halo 1 uses actor and actor_variant tags')
        if extension == '.actor':
            return self._resolve_actor(visited)
        if extension not in AI_TAG_EXTENSIONS:
            raise ValueError(f'Unsupported AI tag: {self.path}')

        root = self.tag.root()
        unit = self.reference(root, 'unit')
        if unit is not None:
            if unit.Extension not in {'biped', 'vehicle', 'creature', 'giant'}:
                raise ValueError(f'{self.path}: unsupported unit tag {unit.RelativePathWithExtension}')
            if not self.path_exists(unit):
                raise FileNotFoundError(unit.Filename)
            if extension == '.actor_variant':
                properties = self.required_field(root, 'unit properties').as_struct()
                colors = []
                for color in self.block(properties, 'change colors'):
                    rgb = self.value(color, 'color upper bound')
                    colors.append((rgb.red, rgb.green, rgb.blue, 1.0))
                return AIUnitImport(
                    unit, tuple(colors), int(self.value(properties, 'forced shader permutation')),
                    self.reference_from_path(self.path),
                    self.reference(self.required_field(root, 'ranged combat').as_struct(), 'weapon'))
            return AIUnitImport(unit)

        if extension == '.character':
            parent = self.reference(root, 'parent character')
            if parent is not None:
                with AIUnitDocument(parent, tags_root=self.tags_root, game=self.game,
                                    definitions=self.definitions, must_exist=True) as document:
                    return document.resolve_import(visited)
        raise ValueError(f'{self.path}: no unit reference to import')

    def _resolve_actor(self, visited):
        # H1 actors contain behavior, not a unit reference. Find a variant
        # that actually references this actor, preferring the same filename.
        sibling = self.system_path.with_suffix('.actor_variant')
        local = sorted(self.system_path.parent.rglob('*.actor_variant'))
        candidates = [sibling] if sibling.is_file() else []
        candidates.extend(path for path in local if path != sibling)
        tried = set()
        for search in (candidates, None):
            paths = (sorted(self.tags_root.rglob('*.actor_variant'))
                     if search is None else search)
            for path in paths:
                if path in tried:
                    continue
                tried.add(path)
                with AIUnitDocument(path, tags_root=self.tags_root, game=self.game,
                                    definitions=self.definitions, must_exist=True) as variant:
                    actor = variant.reference(variant.tag.root(), 'actor definition')
                    if actor is not None and Path(actor.Filename).resolve() == self.system_path:
                        return variant.resolve_import(visited)
        raise ValueError(f'{self.path}: no actor_variant references this actor')

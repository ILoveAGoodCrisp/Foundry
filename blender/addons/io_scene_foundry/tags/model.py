"""Model references and variant selection through native blam-tags fields."""
from __future__ import annotations

from enum import Enum
from pathlib import Path
import random
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from .backend import TagDocument, ReferenceField, TagReference
from .metadata import enum_index

if TYPE_CHECKING:
    import blam_tags

ChildObject = SimpleNamespace


class RenderModelOverrideType(Enum):
    campaign = 0
    multiplayer = 1
    firefight = 2
    mainmenu = 3


class ModelDocument(TagDocument):
    tag_ext = 'model'
    reference_render_model = property(lambda self: ReferenceField(self, 'render model'))
    reference_collision_model = property(lambda self: ReferenceField(self, 'collision model'))
    reference_animation = property(lambda self: ReferenceField(self, 'animation'))
    reference_physics_model = property(lambda self: ReferenceField(self, 'physics_model'))

    def variants(self) -> blam_tags.TagBlock:
        return self.block(self.tag.root(), 'variants')

    def get_model_variants(self) -> list[str]:
        if self.game == 'halo1':
            return []
        return [cast(str, self.value(e, 'name')) for e in self.variants()]

    def get_model_permutations(self) -> list[str]:
        """Return the render permutation names exposed directly by an H1 model."""
        if self.game != 'halo1':
            return []
        names = (
            cast(str, self.value(permutation, 'name'))
            for region in self.block(self.tag.root(), 'regions')
            for permutation in self.block(region, 'permutations')
        )
        return list(dict.fromkeys(name for name in names if name))

    def get_variant_value(self, selection: str) -> float:
        """Map the selected variant (or H1 permutation) to a 0..1 factor."""
        names = self.get_model_permutations() if self.game == 'halo1' else self.get_model_variants()
        if not selection or selection not in names or len(names) < 2:
            return 0.0
        return names.index(selection) / (len(names) - 1)

    def get_halo1_region_permutations(self, selected_permutation: str) -> set[tuple[str, str]]:
        """Resolve one H1 permutation for every region in the model.

        Halo 1 exposes permutation names globally in the import UI, but a name
        need not exist in every region. In that case the engine-style fallback
        is the region's first permutation rather than omitting the region.
        """
        if self.game != 'halo1' or not selected_permutation or selected_permutation == 'all_permutations':
            return set()

        selected = []
        for region in self.block(self.tag.root(), 'regions'):
            permutations = list(self.block(region, 'permutations'))
            if not permutations:
                continue
            permutation = next(
                (entry for entry in permutations
                 if self.value(entry, 'name') == selected_permutation),
                permutations[0],
            )
            selected.append((
                cast(str, self.value(region, 'name')),
                cast(str, self.value(permutation, 'name')),
            ))
        return set(selected)

    def get_render_model(self, optional_tag_root=None, override_type=None):
        reference = self.reference_render_model.Path
        if self.game in {'halo4', 'halo2a'} and override_type is not None:
            for element in self.block(self.tag.root(), 'game mode render model override'):
                kind = enum_index(self.value(element, 'game mode'), tuple(e.name for e in RenderModelOverrideType))
                if kind == override_type.value:
                    reference = self.reference(element, 'render model override')
                    break
        return self.reference_filename(reference, optional_tag_root)

    @staticmethod
    def reference_filename(reference: TagReference | None,
                           root: str | Path | None = None) -> str:
        if reference is None:
            return ''
        return str(Path(root) / reference.RelativePathWithExtension) if root else reference.Filename

    def get_model_paths(self, optional_tag_root=None, override_type=None):
        return (self.get_render_model(optional_tag_root, override_type),
                *(self.reference_filename(reference.Path, optional_tag_root) for reference in
                  (self.reference_collision_model, self.reference_animation, self.reference_physics_model)))

    def get_lighting_info(self):
        return self.reference(self.tag.root(), 'Lighting Info') if self.game in {'halo4', 'halo2a'} else None

    def assign_lighting_info_tag(self, path):
        if self.game in {'halo4', 'halo2a'}:
            self.set_reference(self.tag.root(), 'Lighting Info', path)

    def model_materials(self):
        name = 'materials' if self.game in {'halo3', 'halo3odst'} else 'model materials'
        return {self.value(e, 'material name'): self.value(e, 'global material name') or self.value(e, 'material name')
                for e in self.block(self.tag.root(), name) if self.value(e, 'material name')}

    def set_asset_paths(self, preserve_missing=False, allowed_components: set[str] | None = None):
        for field, extension in (('render model', 'render_model'), ('collision model', 'collision_model'),
                                 ('animation', 'model_animation_graph'), ('physics_model', 'physics_model')):
            path = Path(self.asset_dir) / (self.asset_name + '.' + extension)
            if (allowed_components is None or extension in allowed_components) and (self.tags_root / path).is_file():
                self.set_reference(self.tag.root(), field, path)
            elif not preserve_missing:
                self.set_reference(self.tag.root(), field, None)

    def set_model_overrides(self, render_model, collision_model, model_animation_graph, physics_model):
        # Export creates local copies of the chosen templates before this call.
        for source, field, extension in zip(
                (render_model, collision_model, model_animation_graph, physics_model),
                ('render model', 'collision model', 'animation', 'physics_model'),
                ('render_model', 'collision_model', 'model_animation_graph', 'physics_model')):
            if source and (self.tags_root / source).is_file():
                self.set_reference(self.tag.root(), field, Path(self.asset_dir) / (self.asset_name + '.' + extension))

    def get_variant_children(self, variant):
        result = []
        if not variant:
            return result
        for element in self.variants():
            if self.value(element, 'name') == variant:
                for child in self.block(element, 'objects'):
                    variant_field = child.field('child variant name')
                    result.append(SimpleNamespace(parent_marker=self.value(child, 'parent marker'),
                        child_marker=self.value(child, 'child marker'),
                        child_variant_name=variant_field.value if variant_field is not None else '',
                        child_object=self.reference(child, 'child object')))
        return result

    def render_regions(self):
        reference = self.reference_render_model.Path
        if not self.path_exists(reference):
            return {}
        with TagDocument(reference, tags_root=self.tags_root, game=self.game, must_exist=True,
                         definitions=self.definitions) as render:
            return {render.value(region, 'name'):
                    [render.value(p, 'name') for p in render.block(region, 'permutations')]
                    for region in render.block(render.tag.root(), 'regions')}

    def is_sky(self):
        # This render-model flag was introduced in Reach; H3/ODST do not define it.
        if self.game != 'reach' or not self.path_exists(self.reference_render_model.Path):
            return False
        with TagDocument(self.reference_render_model.Path, tags_root=self.tags_root, game=self.game,
                         must_exist=True, definitions=self.definitions) as render:
            return render.required_field(render.tag.root(), 'flags').get_flag('this is supposed to be a sky')

    def variant_region_options(self, variant, state=-1, render_regions=None):
        if not variant:
            return {}
        if render_regions is None:
            render_regions = self.render_regions()
        default_region = 'default' if 'default' in render_regions else next(iter(render_regions), 'default')
        for element in self.variants():
            if self.value(element, 'name') != variant:
                continue
            result = {}
            for region in self.block(element, 'regions'):
                name = self.value(region, 'region name')
                if name == 'default':
                    name = default_region
                options = result.setdefault(name, [])
                permutations = self.block(region, 'permutations')
                if not len(permutations):
                    options.append('default')
                for permutation in permutations:
                    name_in_render = self.value(permutation, 'permutation name')
                    if not name_in_render:
                        continue
                    if state == 0:
                        options.append(name_in_render)
                        continue
                    state_options = []
                    for state_element in self.block(permutation, 'states'):
                        kind = enum_index(self.value(state_element, 'state'),
                                          ('default', 'minor damage', 'medium damage', 'major damage', 'destroyed'))
                        if state == -1 or kind == state:
                            state_name = self.value(state_element, 'permutation name')
                            if state_name:
                                state_options.append(state_name)
                    # Damage states replace the base permutation. Only the
                    # all-states selection includes both base and damaged meshes.
                    if state == -1:
                        options.append(name_in_render)
                    options.extend(state_options or [name_in_render])
                # Preserve "default" as a sentinel even when no such render permutation exists.
                result[name] = list(dict.fromkeys(p for p in options if p))
            for name, permutations in render_regions.items():
                # Unspecified regions use their default, not a random damage mesh.
                default = 'default' if 'default' in permutations else next(iter(permutations), 'default')
                result.setdefault(name, list(permutations) if state == -1 else [default])
            return result
        return {}

    def get_variant_regions_and_permutations(self, variant, state):
        if self.game == 'halo1':
            return set()
        if not self.path_exists(self.reference_render_model.Path):
            return set()
        region_options = self.variant_region_options(variant, state)
        if state == -1:
            return {(region, permutation) for region, options in region_options.items()
                    for permutation in options}
        return {(region, random.choice(options)) for region, options in
                region_options.items() if options}

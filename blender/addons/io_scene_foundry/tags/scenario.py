"""Native scenario metadata and lightweight editor operations."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import cos, pi, sin, sqrt
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from .backend import TagDocument, TagPathInput, TagReference
from .blender import BlenderTag

if TYPE_CHECKING:
    import blam_tags


ScenarioTransform = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
]


@dataclass(frozen=True)
class ScenarioEditorFolder:
    name: str
    parent_index: int


@dataclass(frozen=True)
class ScenarioObjectPlacement:
    block_name: str
    name: str
    name_index: int
    definition: str | None
    variant: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float]
    scale: float
    folder_index: int
    parent_index: int
    bsps: frozenset[int]


@dataclass(frozen=True)
class ScenarioDecalPlacement:
    name: str
    definition: str | None
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    scale: tuple[float, float]
    bsps: frozenset[int]


@dataclass(frozen=True)
class ScenarioDecoratorPlacement:
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    scale: float
    type_index: int
    motion_scale: int
    ground_tint: int
    tint: tuple[float, float, float]


@dataclass(frozen=True)
class ScenarioDecoratorSet:
    definition: str
    name: str
    placements: tuple[ScenarioDecoratorPlacement, ...]


class ScenarioDocument(TagDocument):
    """Game-independent scenario operations used by import and export."""

    def _set_value(self, struct, name: str, value: object) -> None:
        self.required_field(struct, name).set(value)
        self.tag_has_changes = True

    def ensure_environment_object_palettes(self) -> int:
        """Preload Reach BSP objects before Sapien starts switching BSPs.

        Loading an environment object's definition for the first time during
        the initial BSP switch can assert in breakable-surface redirection.
        Palette references load the definitions with the scenario; placements
        and their IDs remain owned by the BSP.
        """
        if self.game != 'reach':
            return 0
        palettes = {
            'scenery': 'scenery palette', 'crate': 'crate palette',
            'biped': 'biped palette', 'vehicle': 'vehicle palette',
            'equipment': 'equipment palette', 'weapon': 'weapon palette',
            'device_machine': 'machine palette', 'device_control': 'control palette',
            'device_terminal': 'terminal palette',
            'sound_scenery': 'sound scenery palette', 'effect_scenery': 'effect scenery palette',
            'creature': 'creature palette', 'giant': 'giant palette',
        }
        references = {}
        for element in self.block(self.tag.root(), 'structure bsps'):
            bsp_path = self.reference(element, 'structure bsp')
            if not self.path_exists(bsp_path):
                continue
            with TagDocument(bsp_path, tags_root=self.tags_root, game=self.game,
                             must_exist=True, definitions=self.definitions) as bsp:
                palette = bsp.block(bsp.tag.root(), 'environment object palette')
                for instance in bsp.block(bsp.tag.root(), 'environment objects'):
                    index = int(bsp.value(instance, 'palette_index'))
                    if not 0 <= index < len(palette):
                        continue
                    reference = bsp.reference(palette[index], 'definition')
                    if reference is not None and reference.Extension in palettes:
                        references[reference.RelativePathWithExtension.casefold()] = reference

        added = 0
        for extension, block_name in palettes.items():
            wanted = [reference for reference in references.values()
                      if reference.Extension == extension]
            if not wanted:
                continue
            palette = self.block(self.tag.root(), block_name)
            existing = {
                reference.RelativePathWithExtension.casefold()
                for element in palette
                if (reference := self.reference(element, 'name')) is not None
            }
            for reference in wanted:
                key = reference.RelativePathWithExtension.casefold()
                if key in existing:
                    continue
                index = palette.add()
                self.set_reference(palette[index], 'name', reference)
                existing.add(key)
                added += 1
        return added

    def ensure_structure_bsps(self, paths: Iterable[TagPathInput]) -> None:
        """Append missing structure BSP references while preserving existing entries."""
        block = self.block(self.tag.root(), 'structure bsps')
        existing = {
            reference.RelativePath.casefold()
            for element in block
            if (reference := self.reference(element, 'structure bsp')) is not None
        }
        for path in paths:
            reference = self.reference_from_path(path)
            key = reference.RelativePath.casefold()
            if key in existing:
                continue
            index = block.add()
            self.set_reference(block[index], 'structure bsp', reference)
            existing.add(key)

    def retain_structure_bsps(self, paths: Iterable[TagPathInput]) -> int:
        """Remove BSP references outside the exported asset, keeping retained rows."""
        wanted = {
            self.reference_from_path(path).RelativePathWithExtension.casefold()
            for path in paths
        }
        block = self.block(self.tag.root(), 'structure bsps')
        removed = 0
        for index in range(len(block) - 1, -1, -1):
            reference = self.reference(block[index], 'structure bsp')
            if reference is None or reference.RelativePathWithExtension.casefold() not in wanted:
                block.delete(index)
                removed += 1
        if removed:
            self.tag_has_changes = True
        return removed

    def scenario_type(self) -> int:
        field = self.required_field(self.tag.root(), 'type')
        value = field.value
        if isinstance(value, int):
            return value
        normalized = str(value).strip().casefold().replace('_', ' ')
        options = field.options()
        if options is not None:
            for index, name in enumerate(options.names):
                if name.strip().casefold().replace('_', ' ') == normalized:
                    return index
        raise ValueError(f'{self.path}: unknown scenario type {value!r}')

    read_scenario_type = scenario_type

    def set_scenario_type(self, value: str | int) -> None:
        if self.game == 'halo1' and isinstance(value, str):
            value = {'solo': 'singleplayer', 'main menu': 'user interface'}.get(
                value, value)
        self._set_value(self.tag.root(), 'type', value)

    def create_default_profile(self) -> None:
        root = self.tag.root()
        self.block(root, 'player starting locations').add()

        profiles = self.block(root, 'player starting profile')
        profile_index = profiles.add()
        profile = profiles[profile_index]
        self._set_value(profile, 'name', 'default_single')

        defaults: dict[str, TagReference] = {}
        object_types_path = self.tags_root / 'multiplayer/globals.multiplayer_object_type_list'
        if object_types_path.is_file():
            with TagDocument(object_types_path, tags_root=self.tags_root,
                             game=self.game, must_exist=True) as object_types:
                block = object_types.block(object_types.tag.root(), 'object types')
                wanted = {
                    'assault_rifle': 'primary weapon',
                    'magnum': 'secondary weapon',
                    'sprint_equipment': 'starting equipment',
                }
                for element in block:
                    field = wanted.get(object_types.value(element, 'name'))
                    if field is not None:
                        reference = object_types.reference(element, 'object')
                        if reference is not None:
                            defaults[field] = reference

        for name in ('primary weapon', 'secondary weapon'):
            reference = defaults.get(name)
            if reference is None:
                continue
            self.set_reference(profile, name, reference)
            prefix = 'primary' if name.startswith('primary') else 'secondary'
            self._set_value(profile, f'{prefix}rounds loaded', -1)
            self._set_value(profile, f'{prefix}rounds total', -1)
        equipment = profile.field('starting equipment')
        if equipment is not None and defaults.get('starting equipment') is not None:
            self.set_reference(profile, 'starting equipment', defaults['starting equipment'])
        self.tag_has_changes = True


class ScenarioMetadataTag(BlenderTag, ScenarioDocument):
    tag_ext = 'scenario'

    OBJECT_BLOCKS = (
        ('scenery', 'scenery palette'),
        ('bipeds', 'biped palette'),
        ('vehicles', 'vehicle palette'),
        ('equipment', 'equipment palette'),
        ('weapons', 'weapon palette'),
        ('machines', 'machine palette'),
        ('terminals', 'terminal palette'),
        ('controls', 'control palette'),
        ('giants', 'giant palette'),
        ('crates', 'crate palette'),
    )

    TEMPLATE_PALETTES = (
        'scenery palette', 'biped palette', 'vehicle palette',
        'equipment palette', 'weapon palette', 'machine palette',
        'terminal palette', 'control palette', 'dispenser palette',
        'spawner palette', 'bink palette', 'sound scenery palette',
        'giant palette', 'effect scenery palette', 'map variant palettes',
        'map variant palettes compatibility', 'Playtest req palette',
        'decal palette', 'detail object collection palette',
        'style pallette', 'character palette', 'acoustics palette',
        'atmosphere', 'camera fx palette', 'weather palette', 'crate palette',
        'flock palette', 'creature palette', 'big battle creature palette',
        'neuticle palette', 'cinematic lighting palette',
    )
    GLOBAL_TAGS = (
        ('camera effects', 'camera_fx_settings'),
        ('global screen effect', 'area_screen_effect'),
        ('global ssao', 'ssao_definition'),
        ('atmosphere globals', 'atmosphere_globals'),
        ('old atmosphere', 'sky_atm_parameters'),
        ('chocalate mountain', 'chocolate_mountain_new'),
    )

    def _blocks(self):
        root = self.tag.root()
        designs_field = root.field('structure designs')
        designs = designs_field.as_block() if designs_field is not None else None
        return root, self.block(root, 'structure bsps'), designs

    def _bsp(self, name):
        _, bsps, _ = self._blocks()
        for index in range(len(bsps)):
            reference = self.reference(bsps[index], 'structure bsp')
            if reference is not None and Path(reference.RelativePath).name == name:
                return bsps[index]

    def _sky_name(self, element):
        root = self.tag.root()
        object_names = self.block(root, 'object names')
        index = self.value(element, 'name')
        if isinstance(index, int) and 0 <= index < len(object_names):
            name = self.value(object_names[index], 'name')
            if name:
                return name
        reference = self.reference(element, 'sky')
        return reference.ShortName if reference is not None else None

    @staticmethod
    def _active_indices(mask, count):
        return {index for index in range(min(count, 32)) if int(mask) & (1 << index)}

    @staticmethod
    def _optional_block(struct, name):
        field = struct.field(name)
        return field.as_block() if field is not None else None

    def copy_template_data(self, template):
        root = self.tag.root()
        template_root = template.tag.root()

        skies = self._optional_block(root, 'skies')
        template_skies = self._optional_block(template_root, 'skies')
        if skies is not None and template_skies is not None and not len(skies) and len(template_skies):
            skies.copy_from(template_skies)
            template_names = template.block(template_root, 'object names')
            for sky_index in range(len(template_skies)):
                name_index = template.value(template_skies[sky_index], 'name')
                root = self.tag.root()
                skies = self.block(root, 'skies')
                if not isinstance(name_index, int) or not 0 <= name_index < len(template_names):
                    self._set_value(skies[sky_index], 'name', -1)
                    continue
                snapshot = template_names.snapshot(name_index)
                object_names = self.block(root, 'object names')
                new_name_index = object_names.paste(len(object_names), snapshot)
                root = self.tag.root()
                skies = self.block(root, 'skies')
                self._set_value(skies[sky_index], 'name', new_name_index)
            self.tag_has_changes = True

        for name in self.TEMPLATE_PALETTES:
            root = self.tag.root()
            destination = self._optional_block(root, name)
            source = self._optional_block(template_root, name)
            if destination is None or source is None or len(destination) or not len(source):
                continue
            destination.copy_from(source)
            self.tag_has_changes = True

        root = self.tag.root()
        decorators = self._optional_block(root, 'decorators')
        template_decorators = self._optional_block(template_root, 'decorators')
        if (decorators is not None and template_decorators is not None
                and not len(decorators) and len(template_decorators)):
            decorator_index = decorators.add()
            root = self.tag.root()
            decorators = self.block(root, 'decorators')
            sets = self.block(decorators[decorator_index], 'sets')
            template_sets = template.block(template_decorators[0], 'sets')
            for template_set in template_sets:
                reference = template.reference(template_set, 'decorator set')
                set_index = sets.add()
                root = self.tag.root()
                decorators = self.block(root, 'decorators')
                sets = self.block(decorators[decorator_index], 'sets')
                if reference is not None:
                    self.set_reference(sets[set_index], 'decorator set', reference)
            self.tag_has_changes = True

    def copy_template_globals(self, template):
        root = self.tag.root()
        template_root = template.tag.root()
        for field_name, extension in self.GLOBAL_TAGS:
            if root.field(field_name) is None or template_root.field(field_name) is None:
                continue
            source = template.reference(template_root, field_name)
            current = self.reference(root, field_name)
            if not template.path_exists(source) or self.path_exists(current):
                continue
            destination = self.system_path.with_suffix('.' + extension)
            source_path = Path(source.Filename)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source_path.resolve() != destination.resolve():
                shutil.copy2(source_path, destination)
            self.set_reference(root, field_name, destination)

    def ensure_global_tags(self):
        root = self.tag.root()
        for field_name, extension in self.GLOBAL_TAGS:
            if root.field(field_name) is None:
                continue
            current = self.reference(root, field_name)
            if self.path_exists(current):
                continue
            destination = self.system_path.with_suffix('.' + extension)
            if not destination.is_file():
                with TagDocument(destination, tags_root=self.tags_root, game=self.game,
                                 extension=extension, definitions=self.definitions):
                    pass
            self.set_reference(root, field_name, destination)

    def survival_mode(self):
        if self.game in {'halo1', 'halo2'}:
            return False
        return self.scenario_type() == 0 and self.required_field(self.tag.root(), 'flags').get_flag('survival')

    def get_bsp_names(self):
        _, bsps, _ = self._blocks()
        names = []
        for element in bsps:
            reference = self.reference(element, 'structure bsp')
            if reference is not None:
                names.append(reference.ShortName)
        return names

    def get_sky_indices(self):
        root, bsps, _ = self._blocks()
        skies = self._optional_block(root, 'skies')
        fallback = 0 if skies is not None and len(skies) else -1
        return [
            self.value(element, 'default sky')
            if element.field('default sky') is not None else fallback
            for element in bsps
        ]

    def _zone_mask(self, zone_set, name):
        if not zone_set:
            return None
        root = self.tag.root()
        zone_sets = self._optional_block(root, 'zone sets')
        if zone_sets is None:
            return None
        for element in zone_sets:
            if self.value(element, 'name') == zone_set:
                return int(self.value(element, name))
        return None

    def get_bsp_paths(self, zone_set=''):
        _, bsps, _ = self._blocks()
        mask = self._zone_mask(zone_set, 'bsp zone flags')
        active = self._active_indices(mask, len(bsps)) if mask else None
        paths = []
        for index, element in enumerate(bsps):
            if active is not None and index not in active:
                continue
            reference = self.reference(element, 'structure bsp')
            if self.path_exists(reference):
                paths.append(reference.Filename)
        return paths

    def get_design_paths(self, zone_set=''):
        _, _, designs = self._blocks()
        if designs is None:
            return []
        mask = self._zone_mask(zone_set, 'structure design zone flags')
        active = self._active_indices(mask, len(designs)) if mask else None
        paths = []
        for index, element in enumerate(designs):
            if active is not None and index not in active:
                continue
            reference = self.reference(element, 'structure design')
            if self.path_exists(reference):
                paths.append(reference.Filename)
        return paths

    def zone_set_names(self) -> list[str]:
        root = self.tag.root()
        zone_sets = self._optional_block(root, 'zone sets')
        if zone_sets is None:
            return []
        return [name for element in zone_sets
                if isinstance(name := self.value(element, 'name'), str)]

    def required_resources(self) -> TagReference | None:
        return self.reference(self.tag.root(), 'required resources')

    def set_required_resources(self, path: TagPathInput) -> None:
        self.set_reference(self.tag.root(), 'required resources', path)

    def has_child_scenarios(self) -> bool:
        children = self._optional_block(self.tag.root(), 'child scenarios')
        return children is not None and len(children) > 0

    def ensure_scenery_palette_reference(self, path: TagPathInput) -> tuple[int, bool]:
        """Return the palette index for *path*, adding it when absent."""
        wanted = self.reference_from_path(path)
        palette = self.block(self.tag.root(), 'scenery palette')
        for index, element in enumerate(palette):
            reference = self.reference(element, 'name')
            if (reference is not None
                    and reference.RelativePathWithExtension.casefold()
                    == wanted.RelativePathWithExtension.casefold()):
                return index, False

        index = palette.add()
        palette = self.block(self.tag.root(), 'scenery palette')
        self.set_reference(palette[index], 'name', wanted)
        return index, True

    def has_scenery_placement(self, palette_index: int) -> bool:
        scenery = self.block(self.tag.root(), 'scenery')
        return any(self.value(element, 'type') == palette_index for element in scenery)

    def player_starting_transforms(self) -> list[ScenarioTransform]:
        transforms: list[ScenarioTransform] = []
        locations = self.block(self.tag.root(), 'player starting locations')
        for element in locations:
            point = self.value(element, 'position')
            transforms.append((
                (float(point.x), float(point.y), float(point.z)),
                (float(self.value(element, 'facing')),
                 float(self.value(element, 'pitch')), 0.0),
            ))
        return transforms

    def add_scenery_placement(
        self,
        palette_index: int,
        transform: ScenarioTransform,
        unique_id: int,
    ) -> None:
        scenery = self.block(self.tag.root(), 'scenery')
        index = scenery.add()
        scenery = self.block(self.tag.root(), 'scenery')
        element = scenery[index]
        self._set_value(element, 'type', palette_index)

        object_data = self.required_field(element, 'object data').as_struct()
        if object_data is None:
            raise TypeError(f'{self.path}: scenery[{index}] object data is not a struct')
        position, rotation = transform
        self._set_vector(object_data, 'position', position)
        self._set_vector(object_data, 'rotation', rotation)

        object_id = self.required_field(object_data, 'object id').as_struct()
        if object_id is None:
            raise TypeError(f'{self.path}: scenery[{index}] object id is not a struct')
        self._set_value(object_id, 'unique id', unique_id)
        self._set_value(object_id, 'type', 'scenery')
        self._set_value(object_id, 'source', 'editor')

        multiplayer_data = self.required_field(element, 'multiplayer data').as_struct()
        if multiplayer_data is None:
            raise TypeError(f'{self.path}: scenery[{index}] multiplayer data is not a struct')
        self._set_value(multiplayer_data, 'owner team', 'neutral')

    def _set_vector(
        self,
        struct: blam_tags.TagStruct,
        name: str,
        value: tuple[float, float, float],
    ) -> None:
        field = self.required_field(struct, name)
        field.set(type(field.value)(*value))
        self.tag_has_changes = True

    def get_zone_sets_dict(self):
        root, bsps, _ = self._blocks()
        zone_sets = self._optional_block(root, 'zone sets')
        if zone_sets is None:
            return {}
        bsp_names = []
        for element in bsps:
            reference = self.reference(element, 'structure bsp')
            bsp_names.append(reference.ShortName if reference is not None else '')
        result = {}
        for element in zone_sets:
            mask = self.value(element, 'bsp zone flags')
            result[self.value(element, 'name')] = [
                bsp_names[index] for index in self._active_indices(mask, len(bsps))
                if bsp_names[index]
            ]
        return result

    def write_foundry_zone_set(self):
        root, bsps, designs = self._blocks()
        zone_sets = self.block(root, 'zone sets')
        index = None
        for candidate in range(len(zone_sets)):
            if self.value(zone_sets[candidate], 'name') == 'foundry_debug_zone_set':
                index = candidate
                break
        if index is None:
            index = zone_sets.add()
            zone_sets = self.block(root, 'zone sets')
            self._set_value(zone_sets[index], 'name', 'foundry_debug_zone_set')
        element = zone_sets[index]
        bsp_count = len(bsps)
        design_count = len(designs) if designs is not None else 0
        if bsp_count > 32 or design_count > 32:
            raise ValueError(f'{self.path}: debug zone set block flags support at most 32 entries')
        self._set_value(element, 'bsp zone flags', (1 << bsp_count) - 1)
        if element.field('structure design zone flags') is not None:
            self._set_value(element, 'structure design zone flags', (1 << design_count) - 1)

    def get_skies_mapping(self):
        root = self.tag.root()
        return [name for element in self.block(root, 'skies')
                if (name := self._sky_name(element)) is not None]

    def get_sky_paths(self):
        root = self.tag.root()
        return [reference.RelativePathWithExtension for element in self.block(root, 'skies')
                if (reference := self.reference(element, 'sky')) is not None
                and self.path_exists(reference)]

    def get_sky_references(self):
        """Return every sky slot in tag order, including unresolved references."""
        return [reference.RelativePathWithExtension if reference is not None else ""
                for element in self.block(self.tag.root(), 'skies')
                for reference in (self.reference(element, 'sky'),)]

    def child_scenario_paths(self):
        root = self.tag.root()
        children = self._optional_block(root, 'child scenarios')
        if children is None:
            return []
        return [reference for element in children
                if (reference := self.reference(element, 'tag')) is not None
                and self.path_exists(reference)]

    def object_placements(self):
        root = self.tag.root()
        object_names = [self.value(element, 'name') for element in self.block(root, 'object names')]
        folders = []
        for element in self._optional_block(root, 'editor folders') or ():
            parent_index = self.value(element, 'parent folder')
            folders.append(ScenarioEditorFolder(
                self.value(element, 'name') or '',
                parent_index if isinstance(parent_index, int) else -1,
            ))
        placements = []

        for block_name, palette_name in self.OBJECT_BLOCKS:
            block = self._optional_block(root, block_name)
            palette_block = self._optional_block(root, palette_name)
            if block is None or palette_block is None:
                continue
            palette = [self.reference(element, 'name') for element in palette_block]
            for element_index, element in enumerate(block):
                type_index = self.value(element, 'type')
                reference = palette[type_index] if isinstance(type_index, int) and 0 <= type_index < len(palette) else None
                definition = reference.RelativePathWithExtension if self.path_exists(reference) else None
                name_index = self.value(element, 'name')
                if isinstance(name_index, int) and 0 <= name_index < len(object_names):
                    name = object_names[name_index]
                elif reference is not None:
                    name = f'{reference.ShortName}:{element_index}'
                else:
                    name = 'object'

                # Halo 1 keeps placement in a separate struct, nested under
                # unit properties for bipeds and vehicles. It has no scale,
                # editor folders, object IDs, or parent attachments.
                placement_owner = element
                placement_field = 'object data'
                if self.game == 'halo1':
                    placement_field = 'placement'
                    if block_name in {'bipeds', 'vehicles'}:
                        placement_owner = self.required_field(element, 'properties').as_struct()
                object_data = self.required_field(placement_owner, placement_field).as_struct()
                if object_data is None:
                    raise TypeError(f'{self.path}: {block_name}[{element_index}] {placement_field} is not a struct')
                position = self.value(object_data, 'position')
                rotation = self.value(object_data, 'rotation')
                scale = 1.0 if self.game == 'halo1' else self.value(object_data, 'scale') or 1.0
                folder_field = object_data.field('editor folder')
                folder_index = folder_field.value if folder_field is not None else -1
                if not isinstance(folder_index, int):
                    folder_index = -1

                parent_index = -1
                parent_field = object_data.field('parent id')
                parent = parent_field.as_struct() if parent_field is not None else None
                if parent is not None:
                    parent_index = self.value(parent, 'parent object')
                    if not isinstance(parent_index, int):
                        parent_index = -1

                bsps = set()
                object_id_field = object_data.field('object id')
                object_id = object_id_field.as_struct() if object_id_field is not None else None
                if object_id is not None:
                    origin_bsp = self.value(object_id, 'origin bsp index')
                    if isinstance(origin_bsp, int) and origin_bsp >= 0:
                        bsps.add(origin_bsp)
                if not self.corinth and not bsps:
                    for flag_name in ('manual bsp flags', 'can attach to bsp flags'):
                        field = object_data.field(flag_name)
                        if field is not None:
                            bsps.update(self._active_indices(field.value, 32))

                permutation_field = element.field('permutation data')
                permutation = permutation_field.as_struct() if permutation_field is not None else None
                variant = self.value(permutation, 'variant name') if permutation is not None else ''
                placements.append(ScenarioObjectPlacement(
                    block_name=block_name,
                    name=name or 'object',
                    name_index=name_index,
                    definition=definition,
                    variant=variant or '',
                    position=tuple(position.to_array()),
                    rotation=(rotation.yaw, rotation.pitch, rotation.roll),
                    scale=scale,
                    folder_index=folder_index,
                    parent_index=parent_index,
                    bsps=frozenset(bsps),
                ))
        return len(object_names), folders, placements

    def decal_placements(self) -> list[ScenarioDecalPlacement]:
        root = self.tag.root()
        palette_block = self._optional_block(root, 'decal palette')
        decal_block = self._optional_block(root, 'decals')
        if palette_block is None or decal_block is None:
            return []
        palette = [self.reference(element, 'reference') for element in palette_block]
        classic_sizes: dict[str, float] = {}

        def classic_size(reference: TagReference | None) -> float:
            if reference is None or not self.path_exists(reference):
                return 1.0
            key = reference.RelativePathWithExtension.casefold()
            if key in classic_sizes:
                return classic_sizes[key]
            size = 1.0
            with TagDocument(reference.Filename, tags_root=self.tags_root,
                             game=self.game, must_exist=True) as decal:
                decal_root = decal.tag.root()
                radius_container = decal_root
                if self.game == 'halo1':
                    appearance = decal.required_field(decal_root, 'appearance').as_struct()
                    if appearance is not None:
                        radius_container = appearance
                radius = decal.value(radius_container, 'radius')
                upper = float(getattr(radius, 'upper', 0.0))
                lower = float(getattr(radius, 'lower', 0.0))
                diameter = max(abs(lower), abs(upper)) * 2.0
                if diameter > 0.0:
                    size = diameter
            classic_sizes[key] = size
            return size

        def classic_rotation(
            yaw_value: object, pitch_value: object,
        ) -> tuple[float, float, float, float]:
            # Classic scenarios store both angles as signed normalized bytes.
            yaw = max(-127, min(127, int(yaw_value))) * pi / 127.0
            pitch = max(-127, min(127, int(pitch_value))) * pi / 127.0
            cy, sy = cos(yaw * 0.5), sin(yaw * 0.5)
            cp, sp = cos(pitch * 0.5), sin(pitch * 0.5)
            return (-sy * sp, cy * sp, sy * cp, cy * cp)

        placements = []
        for element in decal_block:
            classic = self.game in {'halo1', 'halo2'}
            palette_index = self.value(
                element, 'decal type' if classic else 'decal palette index')
            reference = palette[palette_index] if isinstance(palette_index, int) and 0 <= palette_index < len(palette) else None
            definition = reference.RelativePathWithExtension if self.path_exists(reference) else None
            position = self.value(element, 'position')
            if classic:
                yaw_field = element.field('yaw[-127,127]')
                if yaw_field is None:
                    yaw_field = element.field('yaw')
                pitch_field = element.field('pitch[-127,127]')
                if pitch_field is None:
                    pitch_field = element.field('pitch')
                rotation_values = classic_rotation(
                    0 if yaw_field is None else yaw_field.value,
                    0 if pitch_field is None else pitch_field.value)
                size = classic_size(reference)
                scale = (size, size)
            else:
                rotation = self.value(element, 'rotation')
                rotation_values = (rotation.i, rotation.j, rotation.k, rotation.w)
                scale_x_field = element.field('scale x')
                if scale_x_field is not None:
                    scale = (scale_x_field.value, self.value(element, 'scale y'))
                else:
                    uniform_scale = self.value(element, 'scale')
                    scale = (uniform_scale, uniform_scale)
            bsps = set()
            flags = element.field('manual bsp flags')
            if flags is not None and not self.corinth:
                bsps.update(self._active_indices(flags.value, 32))
            placements.append(ScenarioDecalPlacement(
                name=reference.ShortName if reference is not None else 'decal',
                definition=definition,
                position=(
                    float(getattr(position, 'x', getattr(position, 'i', 0.0))),
                    float(getattr(position, 'y', getattr(position, 'j', 0.0))),
                    float(getattr(position, 'z', getattr(position, 'k', 0.0))),
                ),
                rotation=rotation_values,
                scale=scale,
                bsps=frozenset(bsps),
            ))
        return placements

    def decorator_sets(self):
        root = self.tag.root()
        if self.game == 'halo2':
            return self._halo2_decorator_sets(root)
        decorators = self._optional_block(root, 'decorators')
        if decorators is None or not len(decorators):
            return []
        sets = self._optional_block(decorators[0], 'sets')
        if sets is None:
            return []
        result = []
        for element in sets:
            reference = self.reference(element, 'decorator set')
            if not self.path_exists(reference):
                continue
            placement_block = self.block(element, 'placements')
            placements = []
            for placement in placement_block:
                position = self.value(placement, 'position')
                rotation = self.value(placement, 'rotation')
                tint = self.value(placement, 'tint color')
                motion_scale = int(self.value(placement, 'motion scale'))
                ground_tint = int(self.value(placement, 'ground tint'))
                if not self.corinth:
                    motion_scale &= 0xFF
                    ground_tint &= 0xFF
                placements.append(ScenarioDecoratorPlacement(
                    position=(position.x, position.y, position.z),
                    rotation=(rotation.i, rotation.j, rotation.k, rotation.w),
                    scale=float(self.value(placement, 'scale')),
                    type_index=int(self.value(placement, 'type index')),
                    motion_scale=motion_scale,
                    ground_tint=ground_tint,
                    tint=(tint.x, tint.y, tint.z),
                ))
            result.append(ScenarioDecoratorSet(
                definition=reference.RelativePathWithExtension,
                name=reference.ShortName,
                placements=tuple(placements),
            ))
        return result

    @staticmethod
    def _halo2_decorator_cell_paths(
        cells: blam_tags.TagBlock,
    ) -> dict[int, tuple[int, ...]]:
        """Map a decorator group to its sparse octree path."""
        if not len(cells):
            return {}
        paths: dict[int, tuple[int, ...]] = {}
        visited: set[int] = set()

        def visit(cell_index: int, path: tuple[int, ...]) -> None:
            if cell_index in visited or not 0 <= cell_index < len(cells):
                return
            visited.add(cell_index)
            cell = cells[cell_index]
            group_start = int(cell.field('group start index').value)
            group_count = int(cell.field('group count').value)
            for group_index in range(group_start, group_start + group_count):
                paths[group_index] = path
            children_field = cell.field('child indices')
            if children_field is None:
                return
            children = children_field.as_array()
            for octant in range(len(children)):
                child_field = children[octant].field('child index')
                if child_field is None:
                    continue
                child_index = int(child_field.value)
                if child_index >= 0:
                    visit(child_index, path + (octant,))

        visit(0, ())
        return paths

    @staticmethod
    def _halo2_decorator_position(
        packed: int, path: tuple[int, ...],
        grid_origin: tuple[float, float, float], cell_count: int,
    ) -> tuple[float, float, float]:
        """Expand H2's cell-relative 10/10/10-bit decorator position."""
        root_size = float(cell_count) * 8.0
        cell_size = root_size / float(1 << len(path))
        root_min = tuple(value - root_size * 0.5 for value in grid_origin)
        cell_indices = [0, 0, 0]
        # H2 octants store Z, Y, X in bits 0, 1, 2 respectively.
        for octant in path:
            for axis, bit in enumerate((2, 1, 0)):
                cell_indices[axis] = (cell_indices[axis] << 1) | ((octant >> bit) & 1)
        packed &= 0xFFFFFFFF
        quantized = (packed & 0x3FF, (packed >> 10) & 0x3FF,
                     (packed >> 22) & 0x3FF)
        return tuple(
            root_min[axis] + cell_indices[axis] * cell_size
            + quantized[axis] * cell_size / 1023.0
            for axis in range(3)
        )

    @staticmethod
    def _halo2_decorator_tint(value: object) -> tuple[float, float, float]:
        packed = int(getattr(value, 'value', value)) & 0xFFFFFF
        return (((packed >> 16) & 0xFF) / 255.0,
                ((packed >> 8) & 0xFF) / 255.0,
                (packed & 0xFF) / 255.0)

    @staticmethod
    def _halo2_decorator_rotation(
        packed: int,
    ) -> tuple[float, float, float, float]:
        """Decode H2's 4/4/4-bit surface normal and 4-bit axial angle."""
        packed &= 0xFFFFFFFF
        normal = [
            (((packed >> shift) & 0xF) / 15.0) * 2.0 - 1.0
            for shift in (20, 24, 28)
        ]
        length = sqrt(sum(value * value for value in normal))
        if length <= 1e-8:
            normal = [0.0, 0.0, 1.0]
        else:
            normal = [value / length for value in normal]
        nx, ny, nz = normal

        # Align local +Z with the stored surface normal. H2 then applies the
        # quantized angle around that normal.
        if nz <= -0.999999:
            align = (1.0, 0.0, 0.0, 0.0)
        else:
            factor = sqrt(2.0 * (1.0 + nz))
            align = (-ny / factor, nx / factor, 0.0, factor * 0.5)
        half_angle = (((packed >> 9) & 0xF) / 15.0) * pi
        twist = (nx * sin(half_angle), ny * sin(half_angle),
                 nz * sin(half_angle), cos(half_angle))
        tx, ty, tz, tw = twist
        ax, ay, az, aw = align
        return (
            tw * ax + tx * aw + ty * az - tz * ay,
            tw * ay - tx * az + ty * aw + tz * ax,
            tw * az + tx * ay - ty * ax + tz * aw,
            tw * aw - tx * ax - ty * ay - tz * az,
        )

    def _halo2_decorator_scale_bounds(
        self, palette: blam_tags.TagBlock,
    ) -> dict[tuple[int, int, int], tuple[float, float]]:
        """Read the permutation bounds addressed by packed H2 placements."""
        result: dict[tuple[int, int, int], tuple[float, float]] = {}
        for set_index, palette_element in enumerate(palette):
            reference = self.reference(palette_element, 'decorator set')
            if not self.path_exists(reference):
                continue
            with TagDocument(reference, tags_root=self.tags_root,
                             game=self.game, must_exist=True) as decorator_set:
                classes = decorator_set.block(
                    decorator_set.tag.root(), 'classes')
                for class_index, class_element in enumerate(classes):
                    permutations = decorator_set.block(
                        class_element, 'permutations')
                    for permutation_index, permutation in enumerate(permutations):
                        bounds = decorator_set.value(permutation, 'scale')
                        result[set_index, class_index, permutation_index] = (
                            float(bounds.lower), float(bounds.upper))
        return result

    @staticmethod
    def _halo2_decorator_scale(
        packed: int, bounds: tuple[float, float] | None,
    ) -> float:
        if bounds is None or bounds == (0.0, 0.0):
            return 1.0
        fraction = ((packed >> 16) & 0xF) / 15.0
        return bounds[0] + (bounds[1] - bounds[0]) * fraction

    def _halo2_decorator_sets(
        self, root: blam_tags.TagStruct,
    ) -> list[ScenarioDecoratorSet]:
        decorators = self._optional_block(root, 'decorators')
        palette = self._optional_block(root, 'decorator palette')
        if decorators is None or not len(decorators) or palette is None:
            return []
        definition = decorators[0]
        groups = self._optional_block(definition, 'groups')
        cache_blocks = self._optional_block(definition, 'cache blocks')
        cells = self._optional_block(definition, 'cells')
        if groups is None or cache_blocks is None or cells is None:
            return []
        origin = self.value(definition, 'grid origin')
        grid_origin = (float(origin.x), float(origin.y), float(origin.z))
        cell_count = int(self.value(definition, 'cell count per dimension'))
        if cell_count <= 0:
            return []
        group_paths = self._halo2_decorator_cell_paths(cells)
        scale_bounds = self._halo2_decorator_scale_bounds(palette)
        placements_by_set: dict[int, list[ScenarioDecoratorPlacement]] = {}
        for group_index, group in enumerate(groups):
            path = group_paths.get(group_index)
            if path is None:
                continue
            set_index = int(self.value(group, 'decorator set'))
            cache_index = int(self.value(group, 'cache block'))
            start = int(self.value(group, 'decorator start index'))
            count = int(self.value(group, 'decorator count'))
            if not (0 <= set_index < len(palette) and
                    0 <= cache_index < len(cache_blocks) and count > 0):
                continue
            data = self._optional_block(cache_blocks[cache_index], 'cache block data')
            if data is None or not len(data):
                continue
            native_placements = self._optional_block(data[0], 'placements')
            if native_placements is None:
                continue
            end = min(start + count, len(native_placements))
            output = placements_by_set.setdefault(set_index, [])
            for placement_index in range(max(0, start), end):
                placement = native_placements[placement_index]
                internal_data = int(self.value(placement, 'internal data 1')) & 0xFFFFFFFF
                type_index = internal_data & 0x7
                permutation_index = (internal_data >> 3) & 0x3F
                output.append(ScenarioDecoratorPlacement(
                    position=self._halo2_decorator_position(
                        int(self.value(placement, 'compressed position')),
                        path, grid_origin, cell_count),
                    rotation=self._halo2_decorator_rotation(internal_data),
                    scale=self._halo2_decorator_scale(
                        internal_data,
                        scale_bounds.get((set_index, type_index,
                                          permutation_index))),
                    type_index=type_index,
                    motion_scale=255,
                    ground_tint=255,
                    tint=self._halo2_decorator_tint(
                        self.value(placement, 'tint color')),
                ))
        result = []
        for set_index, placements in placements_by_set.items():
            reference = self.reference(palette[set_index], 'decorator set')
            if not self.path_exists(reference):
                continue
            result.append(ScenarioDecoratorSet(
                definition=reference.RelativePathWithExtension,
                name=reference.ShortName,
                placements=tuple(placements),
            ))
        return result

    @staticmethod
    def _set_point(field, point):
        field.set(type(field.value)(*point))

    def cubemap_positions(self):
        root = self.tag.root()
        positions = []
        for element in self.block(root, 'cubemaps'):
            point = self.value(element, 'cubemap position')
            positions.append((point.x, point.y, point.z))
        return positions

    def ensure_default_cubemap(self, point=(0.0, 0.0, 0.6)):
        root = self.tag.root()
        cubemaps = self.block(root, 'cubemaps')
        if len(cubemaps):
            return False
        index = cubemaps.add()
        cubemaps = self.block(root, 'cubemaps')
        self._set_point(self.required_field(cubemaps[index], 'cubemap position'), point)
        self.tag_has_changes = True

        resources = self.block(root, 'scenario resources')
        if not len(resources):
            return True
        split_resources = self.block(resources[0], 'new split resources')
        if not len(split_resources):
            return True
        reference = self.reference(split_resources[0], 'cubemap reference resource')
        if not self.path_exists(reference):
            return True
        with TagDocument(reference, tags_root=self.tags_root, game=self.game,
                         must_exist=True) as resource:
            resource_root = resource.tag.root()
            resource_cubemaps = resource.block(resource_root, 'cubemaps')
            resource_index = resource_cubemaps.add()
            resource_cubemaps = resource.block(resource_root, 'cubemaps')
            self._set_point(resource.required_field(
                resource_cubemaps[resource_index], 'cubemap position'), point)
            resource.tag_has_changes = True
        return True

    def set_cubemap_bitmap_references(self):
        root, bsps, _ = self._blocks()
        scenario_name = self.tag_path.ShortName
        scenario_dir = Path(self.tag_path.RelativePath).parent
        field_name = 'bsp specific cubemap' if self.corinth else 'cubemap bitmap group reference'
        records = []
        for index in range(len(bsps)):
            element = bsps[index]
            bsp = self.reference(element, 'structure bsp')
            if bsp is None:
                continue
            bitmap = scenario_dir / f'{scenario_name}_{bsp.ShortName}_cubemaps.bitmap'
            self.set_reference(element, field_name, bitmap)
            records.append((index, bsp.ShortName, self.reference(element, field_name)))
        return records

    def cutscene_anchor(self, name):
        root = self.tag.root()
        for element in self.block(root, 'cutscene flags'):
            if self.value(element, 'name') != name:
                continue
            point = self.value(element, 'position')
            angles = self.value(element, 'facing')
            return ((point.x, point.y, point.z),
                    (angles.yaw, angles.pitch, getattr(angles, 'roll', 0.0)))

    def add_new_sky(self, path):
        root = self.tag.root()
        skies = self.block(root, 'skies')
        sky_index = skies.add()
        skies = self.block(root, 'skies')
        self.set_reference(skies[sky_index], 'sky', path)

        object_names = self.block(root, 'object names')
        name_index = object_names.add()
        object_names = self.block(root, 'object names')
        sky_name = Path(path).stem
        self._set_value(object_names[name_index], 'name', sky_name)
        skies = self.block(root, 'skies')
        self._set_value(skies[sky_index], 'name', name_index)

        if self.corinth and sky_index == 0:
            bsps = self.block(root, 'structure bsps')
            for element in bsps:
                if self.value(element, 'default sky') == -1:
                    self._set_value(element, 'default sky', sky_index)
        return sky_name, sky_index

    def set_skies(self, paths):
        """Replace the ordered skies block while preserving other object-name indices."""
        paths = list(paths)
        for path in paths:
            if not path or Path(path).suffix.lower() not in {'.sky', '.scenery'} or Path(path).is_absolute() or '..' in Path(path).parts:
                raise ValueError(f'Invalid sky tag path: {path!r}')
        root = self.tag.root()
        skies = self.block(root, 'skies')
        object_names = self.block(root, 'object names')
        name_indices = [self.value(element, 'name') for element in skies]
        if len(skies):
            self.tag_has_changes = True
        skies.clear()
        for sky_index, path in enumerate(paths):
            skies = self.block(root, 'skies')
            skies.add()
            skies = self.block(root, 'skies')
            self.set_reference(skies[sky_index], 'sky', path)
            name_index = name_indices[sky_index] if sky_index < len(name_indices) else -1
            if not isinstance(name_index, int) or not 0 <= name_index < len(object_names):
                name_index = object_names.add()
                object_names = self.block(root, 'object names')
            self._set_value(object_names[name_index], 'name', Path(path).stem)
            self._set_value(skies[sky_index], 'name', name_index)
        if self.corinth and paths:
            for element in self.block(root, 'structure bsps'):
                if self.value(element, 'default sky') == -1:
                    self._set_value(element, 'default sky', 0)

    def set_bsp_default_sky(self, bsp_name, sky_index):
        element = self._bsp(bsp_name)
        if element is None:
            return None
        self._set_value(element, 'default sky', sky_index)
        root = self.tag.root()
        skies = self.block(root, 'skies')
        return self._sky_name(skies[sky_index]) if 0 <= sky_index < len(skies) else 'None'

    def set_bsp_lightmap_res(self, bsp_name, size_class, refinement_class):
        element = self._bsp(bsp_name)
        if element is None:
            return False
        self._set_value(element, 'size class', size_class)
        if self.corinth:
            self._set_value(element, 'refinement size class', refinement_class)
        options = self.required_field(element, 'size class').options()
        return options.current_name if options is not None else str(size_class)

    def get_bsp_info(self, bsp_name):
        element = self._bsp(bsp_name)
        if element is None:
            return None
        size_field = element.field('size class')
        if size_field is None:
            return None
        size = size_field.options()
        result = {'Lightmapper Size Class': size.current_name if size else str(size_field.value)}
        if self.corinth:
            refinement = self.required_field(element, 'refinement size class').options()
            result['Lightmapper Refinement Class'] = refinement.current_name if refinement else str(self.value(element, 'refinement size class'))
        sky_field = element.field('default sky')
        sky_index = sky_field.value if sky_field is not None else -1
        if sky_index < 0:
            result['Default Sky'] = 'None'
        else:
            skies = self.block(self.tag.root(), 'skies')
            result['Default Sky'] = self._sky_name(skies[sky_index]) if sky_index < len(skies) else 'None'
        return result

    def get_info(self, bsp_index):
        if self.corinth:
            return None
        _, bsps, _ = self._blocks()
        if not 0 <= bsp_index < len(bsps):
            return None
        if bsps[bsp_index].field('structure lighting_info') is None:
            return None
        reference = self.reference(bsps[bsp_index], 'structure lighting_info')
        return Path(reference.Filename) if self.path_exists(reference) else None

    def collect_cutscene_titles(self):
        root = self.tag.root()
        titles = [(text, text, '') for element in self.block(root, 'cutscene titles')
                  if (text := self.value(element, 'name'))]
        if not self.corinth:
            return titles
        for element in self.block(root, 'child scenarios'):
            reference = self.reference(element, 'tag')
            if not self.path_exists(reference):
                continue
            with ScenarioMetadataTag(reference) as child:
                child_titles = child.collect_cutscene_titles()
            if child_titles:
                titles.append(('', reference.ShortName, ''))
                titles.extend(child_titles)
        return titles

    def save_copy_as_solo(self, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.system_path, destination)
        with ScenarioMetadataTag(destination) as copy:
            copy.set_scenario_type(0)

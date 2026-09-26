"""Native model-animation-graph metadata used outside the legacy graph editor."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import degrees, radians
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from .backend import RelativeTagPath, TagDocument, TagPathInput, TagReference
from .blender import BlenderTag
from .animation_names import (
    DIRECTIONS,
    REGIONS,
    convert_animation_name_for_project,
    renames_from_paths,
)

if TYPE_CHECKING:
    import blam_tags
    import bpy
    from .frame_event_list import AnimationEvent


@dataclass(frozen=True)
class AnimationGraphNode:
    name: str
    parent_index: int


@dataclass(frozen=True)
class AnimationGraphDefaultNode:
    name: str
    rotation: tuple[float, float, float, float]
    translation: tuple[float, float, float]
    scale: float


@dataclass(frozen=True)
class AnimationGraphEventName:
    tag_name: str
    data_name: str


@dataclass(frozen=True)
class AnimationGraphEventAnimation:
    name: AnimationGraphEventName
    frame_count: int


@dataclass(frozen=True)
class AnimationGraphIkChain:
    name: str
    start_node: str
    effector_node: str


class AnimationGraphIkChainInput(Protocol):
    name: str
    start_node: str
    effector_node: str


class AnimationCompressionInput(Protocol):
    name: str
    compression: str


class ArrayValue(Protocol):
    def to_array(self) -> list[float]: ...


class AnimationSettingsInput(Protocol):
    name: str
    weight: float
    loop_frame_index: int
    disable_interpolation_in: bool
    disable_interpolation_out: bool
    disable_mode_ik: bool
    disable_weapon_ik: bool
    disable_weapon_aim: bool
    disable_look_screen: bool
    disable_transition_adjustment: bool
    force_weapon_ik_on: bool
    enable_animated_source_interpolation: bool
    disable_ik_sets: bool
    disable_ik_chains: bool
    translate_and_scale_root_only: bool
    enable_blend_out_on_replacement_anims: bool
    override_player_input_with_motion: bool
    disable_subframe_interp_on_loop: bool
    override_blend_in_time: float
    override_blend_out_time: float
    pca_group_name: str
    pca_best_quality: bool


@dataclass(frozen=True)
class AnimationImportSettings:
    weight: float
    loop_frame_index: int
    disable_interpolation_in: bool
    disable_interpolation_out: bool
    disable_mode_ik: bool
    disable_weapon_ik: bool
    disable_weapon_aim: bool
    disable_look_screen: bool
    disable_transition_adjustment: bool
    force_weapon_ik_on: bool
    enable_animated_source_interpolation: bool
    disable_ik_sets: bool
    disable_ik_chains: bool
    translate_and_scale_root_only: bool
    enable_blend_out_on_replacement_anims: bool
    override_player_input_with_motion: bool
    disable_subframe_interp_on_loop: bool
    override_blend_in_time: float
    override_blend_out_time: float
    pca_group_name: str


@dataclass(frozen=True)
class AnimationGraphPcaData:
    path: TagReference | None
    groups: dict[int, str]


@dataclass(frozen=True)
class AnimationGraphImportMetadata:
    nodes: tuple[AnimationGraphNode, ...]
    additional_nodes: tuple[AnimationGraphDefaultNode, ...]
    node_usages: dict[str, int]
    settings: dict[str, AnimationImportSettings]
    pca: AnimationGraphPcaData


@dataclass(frozen=True)
class VehicleSuspensionUpdate:
    marker_name: str
    extension_depth: float
    compression_depth: float
    destroyed_region_name: str = ''
    destroyed_extension_depth: float = 0.0
    destroyed_compression_depth: float = 0.0


@dataclass(frozen=True)
class AnimationBlendScreen:
    label: str
    right_yaw_per_frame: float
    left_yaw_per_frame: float
    right_frame_count: int
    left_frame_count: int
    down_pitch_per_frame: float
    up_pitch_per_frame: float
    down_pitch_frame_count: int
    up_pitch_frame_count: int


class AnimationGraphTag(BlenderTag, TagDocument):
    """Read common graph metadata without starting ManagedBlam."""

    tag_ext = 'model_animation_graph'

    def __init__(self, path: TagPathInput = '', *, tag_must_exist: bool = True,
                 always_save: bool = False, hide_prints: bool = False,
                 raise_on_error: bool = True) -> None:
        super().__init__(path, tag_must_exist=tag_must_exist,
                         always_save=always_save, hide_prints=hide_prints,
                         raise_on_error=raise_on_error)
        if not self.valid:
            return
        if self.tag_is_new:
            codec = self._definitions().field('animation codec pack')
            if codec is not None:
                codec.set(6)
            self.tag_has_changes = True

    def _definitions(self) -> blam_tags.TagStruct:
        root = self.tag.root()
        if self.game == 'halo1':
            return root
        field_name = 'resources' if self.game == 'halo2' else 'definitions'
        definitions = self.required_field(root, field_name).as_struct()
        if definitions is None:
            raise TypeError(f'{self.path}: {field_name} is not a structure')
        return definitions

    def animation_names(self, contains: str = '') -> list[str]:
        animations = self.block(self._definitions(), 'animations')
        names = [str(self.value(animation, 'name')) for animation in animations]
        if contains:
            return [name for name in names if contains in name]
        return names

    def _animation_path_index(self, element: blam_tags.TagStruct) -> int:
        animation = self.required_field(element, 'animation').as_struct()
        if animation is None:
            raise TypeError(f'{self.path}: animation graph entry has no animation structure')
        return int(self.value(animation, 'animation'))

    def _halo1_animation_state_paths(self) -> dict[str, list[str]]:
        """Map Halo 1's positional animation tables to Foundry graph paths."""
        root = self.tag.root()
        animation_names = self.animation_names()
        name_to_paths: dict[str, list[str]] = {}

        def add_index(index: int, tokens: Iterable[str]) -> None:
            if index < 0:
                return
            if index >= len(animation_names):
                raise ValueError(
                    f'{self.path}: graph animation index {index} is outside the '
                    f'{len(animation_names)} local animations')
            source_name = animation_names[index].replace(' ', ':')
            path = ':'.join(token for token in tokens if token)
            if path:
                name_to_paths.setdefault(source_name, []).append(path)

        def add_entries(entries: Iterable[blam_tags.TagStruct],
                        prefix: Iterable[str]) -> None:
            """Use the authored terminal state with a table's current labels."""
            for entry in entries:
                index = int(self.value(entry, 'animation'))
                if index < 0:
                    continue
                if index >= len(animation_names):
                    raise ValueError(
                        f'{self.path}: graph animation index {index} is outside '
                        f'the {len(animation_names)} local animations')
                name_tokens = animation_names[index].split()
                if not name_tokens:
                    raise ValueError(
                        f'{self.path}: graph animation index {index} has an '
                        'empty animation name')
                state = name_tokens[-1]
                add_index(index, (*prefix, state))

        # Object, weapon, vehicle, device and first-person tables have no
        # authored mode label of their own. Their animation name supplies the
        # terminal state while the table supplies the canonical Foundry mode.
        add_entries(self.block(root, 'objects'), ('object',))
        for block_name, mode in (
                ('weapons', 'weapon'), ('vehicles', 'vehicle'),
                ('devices', 'device'), ('first person weapons', 'first_person')):
            for group in self.block(root, block_name):
                add_entries(self.block(group, 'animations'), (mode,))

        # Unit blocks carry the seat/mode and nested weapon labels. Halo 1
        # commonly reuses a stand animation in alert/crouch or vehicle seats;
        # retaining each table path is what produces the required renames.
        for unit in self.block(root, 'units'):
            mode = str(self.value(unit, 'label'))
            add_entries(self.block(unit, 'animations'), (mode,))
            for weapon in self.block(unit, 'weapons'):
                weapon_class = str(self.value(weapon, 'name'))
                add_entries(self.block(weapon, 'animations'),
                            (mode, weapon_class))
                for weapon_type in self.block(weapon, 'weapon types'):
                    type_name = str(self.value(weapon_type, 'label'))
                    add_entries(self.block(weapon_type, 'animations'),
                                (mode, weapon_class, type_name))

        # The unit-damage table is a dense state/direction/region cube in this
        # on-disk order. Unlike action names, Foundry spells damage states and
        # limb regions with underscores.
        damage_states = ('s_ping', 'h_ping', 's_kill', 'h_kill')
        damage_entries = self.block(root, 'unit damage')
        expected_damage_count = len(damage_states) * len(DIRECTIONS) * len(REGIONS)
        if len(damage_entries) not in {0, expected_damage_count}:
            raise ValueError(
                f'{self.path}: expected 0 or {expected_damage_count} Halo 1 '
                f'unit-damage entries, found {len(damage_entries)}')
        for index, entry in enumerate(damage_entries):
            animation_index = int(self.value(entry, 'animation'))
            region_index = index % len(REGIONS)
            direction_index = (index // len(REGIONS)) % len(DIRECTIONS)
            state_index = index // (len(DIRECTIONS) * len(REGIONS))
            add_index(animation_index, (
                damage_states[state_index], DIRECTIONS[direction_index],
                REGIONS[region_index]))
        return name_to_paths

    def animation_state_paths(self) -> dict[str, list[str]]:
        """Map each local animation name to its authored mode/state graph paths."""
        if self.game == 'halo1':
            return self._halo1_animation_state_paths()
        animation_names = self.animation_names()
        name_to_paths: dict[str, list[str]] = {}

        def add_path(element: blam_tags.TagStruct, tokens: list[str]) -> None:
            index = self._animation_path_index(element)
            if index < 0:
                return
            if index >= len(animation_names):
                raise ValueError(
                    f'{self.path}: graph animation index {index} is outside the '
                    f'{len(animation_names)} local animations')
            source_name = animation_names[index].replace(' ', ':')
            name_to_paths.setdefault(source_name, []).append(':'.join(tokens))

        content = self.required_field(self.tag.root(), 'content').as_struct()
        if content is None:
            raise TypeError(f'{self.path}: content is not a structure')
        for mode in self.block(content, 'modes'):
            mode_tokens = [str(self.value(mode, 'label'))]
            for weapon_class in self.block(mode, 'weapon class'):
                class_tokens = mode_tokens + [str(self.value(weapon_class, 'label'))]
                for weapon_type in self.block(weapon_class, 'weapon type'):
                    type_tokens = class_tokens + [str(self.value(weapon_type, 'label'))]
                    sets_field = weapon_type.field('sets')
                    sets = None if sets_field is None else sets_field.as_block()
                    if sets is None:
                        set_records = ((weapon_type, type_tokens),)
                    else:
                        set_records = tuple(
                            (animation_set,
                             type_tokens + [str(self.value(animation_set, 'label'))])
                            for animation_set in sets
                        )

                    for animation_set, set_tokens in set_records:
                        overlay_name = ('overlays' if self.game in {'halo2', 'halo3', 'halo3odst'}
                                        else 'overlay animations')
                        for block_name in ('actions', overlay_name):
                            field = animation_set.field(block_name)
                            entries = None if field is None else field.as_block()
                            if entries is None:
                                continue
                            for entry in entries:
                                add_path(entry, set_tokens + [str(self.value(entry, 'label'))])

                        for damage in self.block(animation_set, 'death and damage'):
                            damage_tokens = set_tokens + [str(self.value(damage, 'label'))]
                            for direction_index, direction in enumerate(
                                    self.block(damage, 'directions')):
                                if direction_index >= len(DIRECTIONS):
                                    raise ValueError(
                                        f'{self.path}: unsupported damage direction index '
                                        f'{direction_index}')
                                for region_index, region in enumerate(
                                        self.block(direction, 'regions')):
                                    if region_index >= len(REGIONS):
                                        raise ValueError(
                                            f'{self.path}: unsupported damage region index '
                                            f'{region_index}')
                                    add_path(region, damage_tokens + [
                                        DIRECTIONS[direction_index], REGIONS[region_index]])

                        for transition in self.block(animation_set, 'transitions'):
                            if self.game in {'halo2', 'halo3', 'halo3odst'}:
                                source_state = str(self.value(transition, 'full name'))
                            else:
                                source_state = str(self.value(transition, 'state name'))
                            for destination in self.block(transition, 'destinations'):
                                if self.game in {'halo2', 'halo3', 'halo3odst'}:
                                    destination_mode = str(self.value(destination, 'full name'))
                                    destination_state = str(self.value(destination, 'mode'))
                                else:
                                    destination_mode = str(self.value(destination, 'mode name'))
                                    destination_state = str(self.value(destination, 'state name'))
                                add_path(destination, set_tokens + [source_state, '2',
                                                                    destination_mode,
                                                                    destination_state])
        return name_to_paths

    def animation_renames(self) -> list[tuple[str, str]]:
        return renames_from_paths(self.animation_state_paths())

    def generate_renames(
            self, contains: str = '', convert_names=False,
            target_game: str = '') -> tuple[int, int]:
        """Add mode/state aliases from this graph to matching Blender animations."""
        blender_animations = {
            animation.name.replace(' ', ':'): animation
            for animation in self.scene_nwo.animations
        }
        renames = self.animation_renames()
        applied = 0
        for source_name, rename in renames:
            converted_source = (convert_animation_name_for_project(
                source_name, self.game, target_game) if convert_names else source_name)
            converted_rename = (convert_animation_name_for_project(
                rename, self.game, target_game) if convert_names else rename)
            if (contains and contains not in source_name and
                    contains not in converted_source):
                continue
            animation = blender_animations.get(converted_source.replace(' ', ':'))
            if animation is None:
                continue
            existing = {entry.name.replace(' ', ':')
                        for entry in animation.animation_renames}
            converted_rename = converted_rename.replace(' ', ':')
            if converted_rename not in existing:
                animation.animation_renames.add().name = converted_rename.replace(':', ' ')
            applied += 1
            print(f'renamed "{converted_source}" ==> "{converted_rename}"')
        print(f'Generated {len(renames)} renames from tag and applied these to '
              f'{applied} Blender animation entries')
        return len(renames), applied

    def event_animations(self) -> list[AnimationGraphEventAnimation]:
        animations: list[AnimationGraphEventAnimation] = []
        for element in self.block(self._definitions(), 'animations'):
            name = str(self.value(element, 'name'))
            frame_count = self._local_frame_count(element)
            if frame_count is None:
                raise ValueError(
                    f'{self.path}: animation {name!r} has no local frame-count data')
            animations.append(AnimationGraphEventAnimation(
                name=AnimationGraphEventName(
                    tag_name=name.replace(' ', ':'),
                    data_name=name.replace(':', ' '),
                ),
                frame_count=frame_count,
            ))
        return animations

    def blend_screens(self) -> dict[str, AnimationBlendScreen]:
        definitions = self._definitions()
        if self.game == 'halo1':
            animations = self.block(definitions, 'animations')
            result: dict[str, AnimationBlendScreen] = {}
            priorities: dict[str, bool] = {}

            def screen(element: blam_tags.TagStruct,
                       label: str) -> AnimationBlendScreen:
                return AnimationBlendScreen(
                    label=label,
                    right_yaw_per_frame=degrees(float(
                        self.value(element, 'right yaw per frame'))),
                    left_yaw_per_frame=degrees(float(
                        self.value(element, 'left yaw per frame'))),
                    right_frame_count=int(self.value(element, 'right frame count')),
                    left_frame_count=int(self.value(element, 'left frame count')),
                    down_pitch_per_frame=degrees(float(
                        self.value(element, 'down pitch per frame'))),
                    up_pitch_per_frame=degrees(float(
                        self.value(element, 'up pitch per frame'))),
                    down_pitch_frame_count=int(self.value(
                        element, 'down pitch frame count')),
                    up_pitch_frame_count=int(self.value(
                        element, 'up pitch frame count')),
                )

            def assign(index: int, record: AnimationBlendScreen,
                       authored_prefix: str) -> None:
                if index < 0:
                    return
                if index >= len(animations):
                    raise ValueError(
                        f'{self.path}: blend-screen animation index {index} is '
                        f'outside the {len(animations)} local animations')
                name = str(self.value(animations[index], 'name')).replace(' ', ':')
                preferred = name.startswith(authored_prefix + ':')
                if name not in result or preferred and not priorities[name]:
                    result[name] = record
                    priorities[name] = preferred

            def animation_index(entries: blam_tags.TagBlock, index: int) -> int:
                if index >= len(entries):
                    return -1
                return int(self.value(entries[index], 'animation'))

            # Unit slot 9 is the look overlay. Weapon slots 25 and 26 are the
            # two aim overlays. Their screen dimensions live directly on the
            # owning H1 unit/weapon record rather than on the animation.
            for unit in self.block(definitions, 'units'):
                mode = str(self.value(unit, 'label'))
                unit_screen = screen(unit, f'{mode}:look')
                assign(animation_index(self.block(unit, 'animations'), 9),
                       unit_screen, mode)
                for weapon in self.block(unit, 'weapons'):
                    weapon_class = str(self.value(weapon, 'name'))
                    prefix = f'{mode}:{weapon_class}'
                    weapon_screen = screen(weapon, f'{prefix}:aim')
                    entries = self.block(weapon, 'animations')
                    assign(animation_index(entries, 25), weapon_screen, prefix)
                    assign(animation_index(entries, 26), weapon_screen, prefix)
            return result

        screens, assignments = self.blend_screen_entries()
        return {name: screens[index] for name, index in assignments.items()}

    def blend_screen_entries(self) -> tuple[list[AnimationBlendScreen], dict[str, int]]:
        """Read every classic screen, including screens without an animation."""
        if self.game == 'halo1':
            assigned = self.blend_screens()
            screens: list[AnimationBlendScreen] = []
            for unit in self.block(self._definitions(), 'units'):
                mode = str(self.value(unit, 'label'))
                entries = [(unit, f'{mode}:look')]
                entries.extend((weapon, f'{mode}:{self.value(weapon, "name")}:aim')
                               for weapon in self.block(unit, 'weapons'))
                for holder, label in entries:
                    screens.append(AnimationBlendScreen(
                        label=label,
                        right_yaw_per_frame=degrees(float(self.value(holder, 'right yaw per frame'))),
                        left_yaw_per_frame=degrees(float(self.value(holder, 'left yaw per frame'))),
                        right_frame_count=int(self.value(holder, 'right frame count')),
                        left_frame_count=int(self.value(holder, 'left frame count')),
                        down_pitch_per_frame=degrees(float(self.value(holder, 'down pitch per frame'))),
                        up_pitch_per_frame=degrees(float(self.value(holder, 'up pitch per frame'))),
                        down_pitch_frame_count=int(self.value(holder, 'down pitch frame count')),
                        up_pitch_frame_count=int(self.value(holder, 'up pitch frame count')),
                    ))
            indices_by_label = {screen.label: index for index, screen in enumerate(screens)}
            return screens, {name: indices_by_label[screen.label]
                             for name, screen in assigned.items()}
        definitions = self._definitions()
        screens: list[AnimationBlendScreen] = []
        for element in self.block(definitions, 'blend screens'):
            aiming = self.required_field(element, 'aiming screen').as_struct()
            if aiming is None:
                raise TypeError(f'{self.path}: aiming screen is not a structure')
            screens.append(AnimationBlendScreen(
                label=str(self.value(element, 'label')),
                right_yaw_per_frame=degrees(float(self.value(aiming, 'right yaw per frame'))),
                left_yaw_per_frame=degrees(float(self.value(aiming, 'left yaw per frame'))),
                right_frame_count=int(self.value(aiming, 'right frame count')),
                left_frame_count=int(self.value(aiming, 'left frame count')),
                down_pitch_per_frame=degrees(float(self.value(aiming, 'down pitch per frame'))),
                up_pitch_per_frame=degrees(float(self.value(aiming, 'up pitch per frame'))),
                down_pitch_frame_count=int(self.value(aiming, 'down pitch frame count')),
                up_pitch_frame_count=int(self.value(aiming, 'up pitch frame count')),
            ))
        assignments: dict[str, int] = {}
        for animation in self.block(definitions, 'animations'):
            field = animation.field('blend screen')
            if field is None:
                continue
            index = int(field.value)
            if 0 <= index < len(screens):
                assignments[str(self.value(animation, 'name'))] = index
        return screens, assignments

    def blend_screens_to_blender(self) -> dict[str, str]:
        """Store every classic screen and return animation-to-screen names."""
        screens, assignments = self.blend_screen_entries()
        collection = self.scene_nwo.blend_screens
        collection.clear()
        names = []
        for screen in screens:
            item = collection.add()
            item.name = screen.label
            for field in ('right_yaw_per_frame', 'left_yaw_per_frame',
                          'right_frame_count', 'left_frame_count',
                          'down_pitch_per_frame', 'up_pitch_per_frame',
                          'down_pitch_frame_count', 'up_pitch_frame_count'):
                value = getattr(screen, field)
                setattr(item, field, radians(value) if 'per_frame' in field else value)
            names.append(item.name)
        self.scene_nwo.blend_screens_active_index = 0
        return {name: names[index] for name, index in assignments.items()}

    @staticmethod
    def _screen_name(name: str) -> str:
        return name.replace(':', ' ').casefold()

    def _write_screen_values(self, holder: blam_tags.TagStruct, screen: object | None) -> None:
        for field in ('right yaw per frame', 'left yaw per frame', 'right frame count',
                      'left frame count', 'down pitch per frame', 'up pitch per frame',
                      'down pitch frame count', 'up pitch frame count'):
            attribute = field.replace(' ', '_')
            value = getattr(screen, attribute) if screen is not None else 0
            self.required_field(holder, field).set(value)
        self.tag_has_changes = True

    def blend_screens_from_blender(self, blender_screens, blender_animations) -> int:
        """Replace classic screens and assign them to compiled overlays."""
        screens = list(blender_screens)
        labels: set[str] = set()
        for screen in screens:
            name = screen.name.strip()
            if not name or name.casefold() in labels:
                raise ValueError(f'{self.path}: blend screen labels must be unique and nonempty')
            labels.add(name.casefold())
        choices = {
            self._screen_name(animation.name): animation.blend_screen.strip()
            for animation in blender_animations
            if animation.animation_type == 'overlay'
        }
        for name, choice in choices.items():
            if choice and choice.casefold() not in labels:
                raise ValueError(f'{self.path}: animation {name!r} references missing blend screen {choice!r}')

        indices = {screen.name.strip().casefold(): index for index, screen in enumerate(screens)}

        definitions = self._definitions()
        animations = self.block(definitions, 'animations')
        animation_indices = {
            self._screen_name(str(self.value(animation, 'name'))): index
            for index, animation in enumerate(animations)
        }
        if self.game == 'halo1':
            known_labels = set()
            for unit in self.block(definitions, 'units'):
                mode = str(self.value(unit, 'label'))
                known_labels.add(f'{mode}:look'.casefold())
                known_labels.update(
                    f'{mode}:{self.value(weapon, "name")}:aim'.casefold()
                    for weapon in self.block(unit, 'weapons')
                )
            unknown_labels = set(indices) - known_labels
            if unknown_labels:
                raise ValueError(
                    f'{self.path}: H1 blend screens must match a unit or weapon: '
                    f'{", ".join(sorted(unknown_labels))}')
            selected: dict[str, list[int]] = {}
            for name, choice in choices.items():
                if choice and name in animation_indices:
                    selected.setdefault(choice.casefold(), []).append(animation_indices[name])
            def retain_unedited(slots, label: str, slot_indices: tuple[int, ...]) -> None:
                if label not in indices:
                    return
                for slot_index in slot_indices:
                    if slot_index >= len(slots):
                        continue
                    index = int(self.value(slots[slot_index], 'animation'))
                    if 0 <= index < len(animations):
                        name = self._screen_name(str(self.value(animations[index], 'name')))
                        if name not in choices:
                            selected.setdefault(label, []).append(index)
            for unit in self.block(definitions, 'units'):
                mode = str(self.value(unit, 'label'))
                label = f'{mode}:look'.casefold()
                screen = screens[indices[label]] if label in indices else None
                self._write_screen_values(unit, screen)
                slots = self.block(unit, 'animations')
                retain_unedited(slots, label, (9,))
                if len(slots) > 9:
                    matches = selected.get(label, [])
                    self.required_field(slots[9], 'animation').set(matches[0] if matches else -1)
                for weapon in self.block(unit, 'weapons'):
                    label = f'{mode}:{self.value(weapon, "name")}:aim'.casefold()
                    screen = screens[indices[label]] if label in indices else None
                    self._write_screen_values(weapon, screen)
                    slots = self.block(weapon, 'animations')
                    retain_unedited(slots, label, (25, 26))
                    matches = selected.get(label, [])
                    for slot_index in (25, 26):
                        if len(slots) > slot_index:
                            position = slot_index - 25
                            self.required_field(slots[slot_index], 'animation').set(
                                matches[position] if len(matches) > position else -1)
            self.tag_has_changes = True
            return len(screens)

        previous_screens, previous_assignments = self.blend_screen_entries()
        previous_choices = {
            self._screen_name(name): previous_screens[index].label
            for name, index in previous_assignments.items()
        }
        # Classic H2/H3 graphs allow at most 64 blend screen records. Preserve
        # labels used by animations, then share records for unassigned screens
        # with identical settings. The Blender scene retains every label.
        preferred = {choice.casefold() for choice in (*choices.values(), *previous_choices.values())
                     if choice}
        screen_fields = ('right_yaw_per_frame', 'left_yaw_per_frame', 'right_frame_count',
                         'left_frame_count', 'down_pitch_per_frame', 'up_pitch_per_frame',
                         'down_pitch_frame_count', 'up_pitch_frame_count')
        compiled_screens = []
        value_indices = {}
        indices = {}
        max_screens = 64 if self.game in {'halo2', 'halo3', 'halo3odst'} else 1024
        ordered_screens = ([screen for screen in screens if screen.name.strip().casefold() in preferred]
                           + [screen for screen in screens if screen.name.strip().casefold() not in preferred])
        for screen in ordered_screens:
            label = screen.name.strip().casefold()
            values = tuple(getattr(screen, field) for field in screen_fields)
            existing = value_indices.get(values)
            if existing is not None and (label not in preferred or len(compiled_screens) >= max_screens):
                indices[label] = existing
                continue
            if len(compiled_screens) >= max_screens:
                raise ValueError(f'{self.path}: {len(screens)} Blender blend screens need more than '
                                 f'{max_screens} distinct compiled entries')
            index = len(compiled_screens)
            compiled_screens.append(screen)
            value_indices.setdefault(values, index)
            indices[label] = index
        block = self.block(definitions, 'blend screens')
        block.clear()
        for screen in compiled_screens:
            block = self.block(definitions, 'blend screens')
            element = block[block.add()]
            self.required_field(element, 'label').set(screen.name)
            aiming = self.required_field(element, 'aiming screen').as_struct()
            if aiming is None:
                raise TypeError(f'{self.path}: aiming screen is not a structure')
            self._write_screen_values(aiming, screen)
        for animation in self.block(definitions, 'animations'):
            field = animation.field('blend screen')
            if field is None:
                continue
            name = self._screen_name(str(self.value(animation, 'name')))
            choice = choices.get(name, previous_choices.get(name, ''))
            field.set(indices.get(choice.casefold(), -1) if choice else -1)
        self.tag_has_changes = True
        return len(compiled_screens)

    def nodes(self) -> list[AnimationGraphNode]:
        definitions = self._definitions()
        nodes = self.block(definitions, 'nodes' if self.game == 'halo1' else 'skeleton nodes')
        return [AnimationGraphNode(
            name=str(self.value(node, 'name')),
            parent_index=int(self.value(node, 'parent node' if self.game == 'halo1' else 'parent node index')),
        ) for node in nodes]

    def get_nodes(self) -> list[str]:
        """Compatibility name for callers that only need skeleton ordering."""
        return [node.name for node in self.nodes()]

    def additional_nodes(self) -> list[AnimationGraphDefaultNode]:
        records: list[AnimationGraphDefaultNode] = []
        field = self.tag.root().field('additional node data')
        block = None if field is None else field.as_block()
        if block is None:
            return records
        for element in block:
            rotation = cast(
                ArrayValue, self.required_field(element, 'default rotation').value)
            translation = cast(
                ArrayValue, self.required_field(element, 'default translation').value)
            records.append(AnimationGraphDefaultNode(
                name=str(self.value(element, 'node name')),
                rotation=tuple(rotation.to_array()),
                translation=tuple(translation.to_array()),
                scale=float(self.value(element, 'default scale')),
            ))
        return records

    def node_usages(self) -> dict[str, int]:
        usages: dict[str, int] = {}
        field = self._definitions().field('node usage')
        block = None if field is None else field.as_block()
        if block is None:
            return usages
        for element in block:
            usage = self.required_field(element, 'usage')
            options = usage.options()
            name = options.current_name if options is not None else None
            if name:
                usages[name] = int(self.value(element, 'node to use'))
        return usages

    def animation_import_settings(self) -> dict[str, AnimationImportSettings]:
        records: dict[str, AnimationImportSettings] = {}
        for element in self.block(self._definitions(), 'animations'):
            flags = (element.field('user flags') or element.field('playback flags') or
                     element.field('flags'))
            if flags is None:
                raise ValueError(f'{self.path}: animation has no playback flags')
            options = flags.options()
            if options is None:
                raise TypeError(f'{self.path}: animation playback flags are not flags')
            enabled = {name for _bit, name, is_set in options.flags if is_set}

            def has(*names: str) -> bool:
                return any(name in enabled for name in names)

            blend_in = element.field('override blend in time')
            blend_out = element.field('override blend out time')
            pca_group = element.field('pca group name')
            name = str(self.value(element, 'name')).replace(' ', ':')
            records[name] = AnimationImportSettings(
                weight=float(self.value(element, 'weight')),
                loop_frame_index=int(self.value(element, 'loop frame index')),
                disable_interpolation_in=has('disable interpolation in',
                                             'disable interpolation_in'),
                disable_interpolation_out=has('disable interpolation out',
                                              'disable interpolation_out'),
                disable_mode_ik=has('disable mode ik'),
                disable_weapon_ik=has('disable weapon ik'),
                disable_weapon_aim=has('disable weapon aim/1st person'),
                disable_look_screen=has('disable look screen'),
                disable_transition_adjustment=has('disable transition adjustment'),
                force_weapon_ik_on=has('force weapon ik on'),
                enable_animated_source_interpolation=has(
                    'enable animated source interpolation'),
                disable_ik_sets=has('disable ik sets'),
                disable_ik_chains=has('disable ik chains'),
                translate_and_scale_root_only=has('translate and scale root only'),
                enable_blend_out_on_replacement_anims=has(
                    'enable blend-out on replacement anims', 'enable blend out'),
                override_player_input_with_motion=has(
                    'override player input with motion'),
                disable_subframe_interp_on_loop=has(
                    'disable subframe interp on loop'),
                override_blend_in_time=0.0 if blend_in is None else float(blend_in.value),
                override_blend_out_time=0.0 if blend_out is None else float(blend_out.value),
                pca_group_name='' if pca_group is None else str(pca_group.value),
            )
        return records

    def pca_import_data(self) -> AnimationGraphPcaData:
        field = self._definitions().field('pca data')
        pca_data = None if field is None else field.as_struct()
        if pca_data is None:
            return AnimationGraphPcaData(None, {})
        path = self.reference(pca_data, 'pca animation')
        groups: dict[int, str] = {}
        mesh_index = 0
        for element in self.block(pca_data, 'PCA Groups'):
            mesh_count = int(self.value(element, 'Desired Mesh Count'))
            if mesh_count < 1:
                continue
            groups[mesh_index] = str(self.value(element, 'Group Name'))
            mesh_index += mesh_count
        return AnimationGraphPcaData(path, groups)

    def import_metadata(self) -> AnimationGraphImportMetadata:
        return AnimationGraphImportMetadata(
            nodes=tuple(self.nodes()),
            additional_nodes=tuple(self.additional_nodes()),
            node_usages=self.node_usages(),
            settings=self.animation_import_settings(),
            pca=self.pca_import_data(),
        )

    def ik_chains(self) -> list[AnimationGraphIkChain]:
        field = self._definitions().field('ik chains')
        block = None if field is None else field.as_block()
        if block is None:
            return []
        node_names = self.get_nodes()
        chains: list[AnimationGraphIkChain] = []
        seen: set[str] = set()
        for index, element in enumerate(block):
            name = str(self.value(element, 'name'))
            if name in seen:
                continue
            seen.add(name)
            start = int(self.value(element, 'start node'))
            effector = int(self.value(element, 'effector node'))
            if not 0 <= start < len(node_names) or not 0 <= effector < len(node_names):
                raise ValueError(
                    f'{self.path}: IK chain {index} has invalid node indices '
                    f'{start}, {effector}')
            chains.append(AnimationGraphIkChain(name, node_names[start], node_names[effector]))
        return chains

    @staticmethod
    def _ik_target_bone_name(chain_name: str, target_kind: str) -> str:
        return f'{chain_name}_{target_kind}_target'

    def _ensure_ik_target_bones(
        self,
        armature: bpy.types.Object,
        target_helpers: list[tuple[str, str]],
    ) -> None:
        import bpy
        from .. import utils

        if armature is None or armature.type != 'ARMATURE' or not target_helpers:
            return
        unique_helpers = list(dict.fromkeys(target_helpers))
        missing: list[tuple[str, str, str]] = []
        for chain_name, target_kind in unique_helpers:
            bone_name = self._ik_target_bone_name(chain_name, target_kind)
            existing = armature.data.bones.get(bone_name)
            if existing is None:
                missing.append((chain_name, target_kind, bone_name))
            else:
                existing.use_deform = False
        if not missing:
            return

        context = bpy.context
        previous_active = utils.get_active_object()
        previous_mode = context.mode
        try:
            utils.set_object_mode(context)
            utils.set_active_object(armature)
            if not bpy.ops.object.mode_set.poll():
                return
            bpy.ops.object.mode_set(mode='EDIT', toggle=False)
            edit_bones = armature.data.edit_bones
            if not edit_bones:
                raise ValueError(f'{self.path}: cannot create IK helpers without a root bone')
            root_bone = edit_bones[0]
            for _, _, bone_name in missing:
                if edit_bones.get(bone_name) is not None:
                    continue
                helper = edit_bones.new(bone_name)
                helper.head = root_bone.head
                helper.tail = root_bone.tail
                helper.roll = root_bone.roll
                helper.use_deform = False
                helper.parent = root_bone
            bpy.ops.object.mode_set(mode='OBJECT', toggle=False)
            for _, _, bone_name in missing:
                bone = armature.data.bones.get(bone_name)
                if bone is not None:
                    bone.use_deform = False
        finally:
            if context.mode != 'OBJECT':
                utils.set_object_mode(context)
            if previous_active is not None and previous_active.name in bpy.data.objects:
                utils.set_active_object(previous_active)
            if previous_active is not None and previous_mode != 'OBJECT':
                utils.restore_mode(previous_mode)

    def ik_chains_to_blender(self, armature: bpy.types.Object) -> int:
        from .. import utils

        records = self.ik_chains()
        node_names = self.get_nodes()
        node_bones = {
            node: bone
            for bone in armature.pose.bones
            for node in node_names
            if utils.remove_node_prefix(bone.name) == utils.remove_node_prefix(node)
        }
        helpers: list[tuple[str, str]] = []
        for record in records:
            start_bone = node_bones.get(record.start_node)
            effector_bone = node_bones.get(record.effector_node)
            if start_bone is None or effector_bone is None:
                raise ValueError(
                    f'{self.path}: IK chain {record.name!r} nodes are absent from the armature')
            chain = self.scene_nwo.ik_chains.get(record.name)
            if chain is None:
                chain = self.scene_nwo.ik_chains.add()
            chain.name = record.name
            chain.start_node = start_bone.name
            chain.effector_node = effector_bone.name
            helpers.extend(((record.name, 'proxy'), (record.name, 'pole')))
        self._ensure_ik_target_bones(armature, helpers)
        return len(records)

    def parent_graph(self) -> TagReference | None:
        return self.reference(self._definitions(), 'parent animation graph')

    def frame_event_list(self) -> TagReference | None:
        if self._definitions().field('imported events') is None:
            return None
        return self.reference(self._definitions(), 'imported events')

    def events_from_blender(self, blender_animations: dict[str, object] | None = None) -> None:
        definitions = self._definitions()
        if self.game in {'halo1', 'halo2', 'halo3', 'halo3odst'}:
            if blender_animations is None:
                blender_animations = {
                    animation.name: animation
                    for animation in self.scene_nwo.animations if animation.export_this
                }
            self.inline_events_from_blender(blender_animations)
            return
        if definitions.field('imported events') is None:
            raise NotImplementedError(
                f'{self.path}: imported frame-event lists are unavailable in this graph layout')
        from .frame_event_list import FrameEventListTag

        event_list_path = Path(self.tag_path.RelativePath).with_suffix('.frame_event_list')
        with FrameEventListTag(path=event_list_path) as events:
            events.from_blender(self.event_animations(), blender_animations)
            self.set_reference(definitions, 'imported events', events.tag_path)

    @staticmethod
    def _event_key(value: str) -> str:
        return value.partition('{')[0].strip().replace('_', ' ').casefold()

    def _set_event_enum(self, element: blam_tags.TagStruct,
                        name: str, value: str) -> None:
        field = self.required_field(element, name)
        options = field.options()
        matches = [] if options is None else [
            index for index, label in enumerate(options.names)
            if self._event_key(label) == self._event_key(value)
        ]
        if len(matches) != 1:
            raise ValueError(f'{self.path}: unsupported {name}: {value!r}')
        field.set(matches[0])

    @staticmethod
    def _blender_marker_name(data: object) -> str:
        name = str(getattr(data, 'marker_name', '')).strip()
        if name:
            return name
        marker = getattr(data, 'marker', None)
        return '' if marker is None else str(marker.nwo.marker_model_group)

    @staticmethod
    def _classic_reference_key(data: object, kind: str) -> tuple[object, ...]:
        path = str(getattr(data, f'event_{kind}_tag', '')).strip()
        if not path:
            raise ValueError(f'Classic {kind} animation event has no tag path')
        flags = tuple(bool(getattr(data, 'flag_' + attribute)) for attribute in (
            'allow_on_player', 'left_arm_only', 'right_arm_only',
            'first_person_only', 'forward_only', 'reverse_only',
        ))
        unsupported = [
            attribute for attribute in ('third_person_only', 'fp_no_aged_weapons')
            if bool(getattr(data, 'flag_' + attribute, False))
        ]
        if unsupported:
            raise ValueError(
                f'Classic {kind} animation references do not support flags: '
                + ', '.join(name.replace('_', ' ') for name in unsupported))
        if str(getattr(data, 'event_model', '')).strip() or str(
                getattr(data, 'variant', '')).strip():
            raise ValueError(
                f'Classic {kind} animation references do not support model variants')
        return (path.replace('/', '\\').casefold(), *flags)

    def _inline_reference_key(self, data: object, kind: str) -> tuple[object, ...]:
        if self.game in {'halo1', 'halo2'}:
            return self._classic_reference_key(data, kind)
        path = str(getattr(data, f'event_{kind}_tag', '')).strip()
        if not path:
            raise ValueError(f'{self.game} {kind} animation event has no tag path')
        if bool(getattr(data, 'flag_third_person_only', False)):
            raise ValueError(f'{self.game} {kind} references do not support third-person only')
        if str(getattr(data, 'event_model', '')).strip() or str(
                getattr(data, 'variant', '')).strip():
            raise ValueError(f'{self.game} {kind} references do not support model variants')
        flags = tuple(bool(getattr(data, 'flag_' + attribute)) for attribute in (
            'allow_on_player', 'left_arm_only', 'right_arm_only',
            'first_person_only', 'forward_only', 'reverse_only',
            'fp_no_aged_weapons',
        ))
        return (path.replace('/', '\\').casefold(), *flags)

    def _classic_reference_indices(
        self, kind: str, keys: set[tuple[object, ...]],
    ) -> dict[tuple[object, ...], int]:
        from .frame_event_list import FrameEventListTag

        definitions = self._definitions()
        block = self.block(definitions, kind + ' references')
        flag_names = FrameEventListTag.reference_flags[:4] + \
            FrameEventListTag.reference_flags[5:7]
        if self.game in {'halo3', 'halo3odst'}:
            flag_names += FrameEventListTag.reference_flags[7:8]
        existing: dict[tuple[object, ...], int] = {}
        for index, element in enumerate(block):
            reference = self.reference(element, kind)
            path = '' if reference is None else reference.RelativePathWithExtension
            if self.game == 'halo1':
                existing.setdefault((path.replace('/', '\\').casefold(),
                                     *([False] * len(flag_names))), index)
                continue
            flags = self.required_field(element, 'flags')
            options = flags.options()
            available = set() if options is None else set(options.names)
            key = (path.replace('/', '\\').casefold(), *(
                flags.get_flag(flag_name) if flag_name in available else False
                for _, flag_name in flag_names
            ))
            existing.setdefault(key, index)
        for key in sorted(keys):
            if key in existing:
                continue
            block = self.block(self._definitions(), kind + ' references')
            index = block.add()
            element = block[index]
            self.set_reference(element, kind, str(key[0]))
            if self.game == 'halo1':
                existing[key] = index
                continue
            flags = self.required_field(element, 'flags')
            options = flags.options()
            available = set() if options is None else set(options.names)
            for (_, flag_name), enabled in zip(flag_names, key[1:]):
                if flag_name in available:
                    flags.set_flag(flag_name, bool(enabled))
            existing[key] = index
        return existing

    def inline_events_from_blender(
        self, blender_animations: dict[str, object],
    ) -> int:
        """Write Tool's inline animation events for Halo 1 through ODST."""
        from .. import utils

        if self.game not in {'halo1', 'halo2', 'halo3', 'halo3odst'}:
            raise NotImplementedError(
                f'{self.path}: inline event writing is only for Halo 1 through ODST')

        animations = self.block(self._definitions(), 'animations')
        compiled_names = [str(self.value(element, 'name')) for element in animations]
        name_indices: dict[str, int] = {}
        for index, name in enumerate(compiled_names):
            for candidate in (name, name.replace(':', ' '), name.replace(' ', ':')):
                key = candidate.casefold()
                if key in name_indices and name_indices[key] != index:
                    raise ValueError(
                        f'{self.path}: ambiguous compiled animation name {candidate!r}')
                name_indices[key] = index

        owned: list[tuple[int, object, dict[str, object]]] = []
        sound_keys: set[tuple[object, ...]] = set()
        effect_keys: set[tuple[object, ...]] = set()
        for supplied_name, blender_animation in blender_animations.items():
            index = next((name_indices[candidate.casefold()] for candidate in (
                supplied_name, supplied_name.replace(':', ' '),
                supplied_name.replace(' ', ':'),
            ) if candidate.casefold() in name_indices), None)
            if index is None:
                raise ValueError(
                    f'{self.path}: Tool did not create animation {supplied_name!r}')
            record: dict[str, object] = {
                'left foot': 0, 'right foot': 0,
                'frames': [], 'sounds': [], 'effects': [], 'dialogues': [],
            }
            for blender_event in blender_animation.animation_events:
                if blender_event.event_type != '_connected_geometry_animation_event_type_frame':
                    utils.print_warning(
                        f'{supplied_name}: {blender_event.event_type} cannot be stored '
                        f'in a {self.game} animation graph. Skipping event')
                    continue
                start = utils.game_frame(
                    blender_event.frame_frame - blender_animation.frame_start)
                end = (utils.game_frame(
                    blender_event.frame_range - blender_animation.frame_start)
                    if blender_event.multi_frame == 'range' else start)
                if start < 0 or end < start:
                    raise ValueError(
                        f'{supplied_name}: invalid animation event frames '
                        f'{start}..{end}')
                event_name = self._event_key(blender_event.frame_name)
                if self.game == 'halo1':
                    if event_name not in {'none', 'left foot', 'right foot'}:
                        raise ValueError(
                            f'{supplied_name}: Halo 1 cannot store frame event '
                            f'{blender_event.frame_name!r}')
                    if event_name != 'none':
                        if start != end:
                            raise ValueError(
                                f'{supplied_name}: Halo 1 foot events cannot span a range')
                        if record[event_name]:
                            raise ValueError(
                                f'{supplied_name}: Halo 1 stores only one {event_name} event')
                        # Halo 1 foot slots are one-based because zero is the
                        # empty sentinel. Sound-frame indices remain zero-based.
                        record[event_name] = start + 1
                elif event_name != 'none':
                    frames = cast(list[tuple[str, int]], record['frames'])
                    frames.extend((event_name, frame) for frame in range(start, end + 1))

                for data in blender_event.event_data:
                    kind = str(data.data_type).casefold()
                    frame = start + int(data.frame_offset)
                    if frame < 0:
                        raise ValueError(
                            f'{supplied_name}: invalid {kind} event frame {frame}')
                    if kind not in ({'sound', 'effect', 'dialogue'}
                                     if self.game in {'halo3', 'halo3odst'}
                                     else {'sound', 'effect'}):
                        raise ValueError(
                            f'{supplied_name}: {self.game} cannot store {kind} '
                            f'animation-event data')
                    if kind == 'dialogue':
                        cast(list[tuple[str, int]], record['dialogues']).append((
                            str(data.dialogue_event), frame))
                        continue
                    if self.game == 'halo1' and kind != 'sound':
                        raise ValueError(
                            f'{supplied_name}: Halo 1 cannot store {kind} animation events')
                    key = self._inline_reference_key(data, kind)
                    marker = self._blender_marker_name(data)
                    if self.game == 'halo1':
                        if marker or any(bool(value) for value in key[1:]):
                            raise ValueError(
                                f'{supplied_name}: Halo 1 sound events do not support '
                                'markers or reference flags')
                        sounds = cast(list[tuple[tuple[object, ...], int, str]],
                                      record['sounds'])
                        if sounds:
                            raise ValueError(
                                f'{supplied_name}: Halo 1 stores only one sound event')
                        sounds.append((key, frame, ''))
                    elif kind == 'sound':
                        cast(list[tuple[tuple[object, ...], int, str]],
                             record['sounds']).append((key, frame, marker))
                        sound_keys.add(key)
                    else:
                        if self.game == 'halo2' and marker:
                            raise ValueError(
                                f'{supplied_name}: Halo 2 effect events do not support markers')
                        reporting = self._event_key(
                            str(getattr(data, 'damage_effect_reporting_type', 'unknown')))
                        if self.game != 'halo3odst' and reporting != 'unknown':
                            raise ValueError(
                                f'{supplied_name}: {self.game} effect events do not store a '
                                'damage reporting type')
                        cast(list[tuple[tuple[object, ...], int, str, str]],
                             record['effects']).append((key, frame, marker, reporting))
                        effect_keys.add(key)
                    if self.game == 'halo1':
                        sound_keys.add(key)
            owned.append((index, blender_animation, record))

        sound_indices = self._classic_reference_indices('sound', sound_keys)
        effect_indices = (self._classic_reference_indices('effect', effect_keys)
                          if self.game != 'halo1' else {})
        for index, _, record in owned:
            animation = self.block(self._definitions(), 'animations')[index]
            if self.game == 'halo1':
                self.required_field(animation, 'left foot frame index').set(
                    record['left foot'])
                self.required_field(animation, 'right foot frame index').set(
                    record['right foot'])
                sounds = cast(list[tuple[tuple[object, ...], int, str]],
                              record['sounds'])
                self.required_field(animation, 'sound').set(
                    sound_indices[sounds[0][0]] if sounds else -1)
                self.required_field(animation, 'sound frame index').set(
                    sounds[0][1] if sounds else 0)
                continue
            block_names = ['frame events', 'sound events', 'effect events']
            if self.game in {'halo3', 'halo3odst'}:
                block_names.append('dialogue events')
            for block_name in block_names:
                self.block(animation, block_name).clear()
                animation = self.block(self._definitions(), 'animations')[index]
            for event_name, frame in cast(list[tuple[str, int]], record['frames']):
                block = self.block(animation, 'frame events')
                element = block[block.add()]
                self._set_event_enum(element, 'type', event_name)
                self.required_field(element, 'frame').set(frame)
                animation = self.block(self._definitions(), 'animations')[index]
            for key, frame, marker in cast(
                    list[tuple[tuple[object, ...], int, str]], record['sounds']):
                block = self.block(animation, 'sound events')
                element = block[block.add()]
                self.required_field(element, 'sound').set(sound_indices[key])
                self.required_field(element, 'frame').set(frame)
                self.required_field(element, 'marker name').set(marker)
                animation = self.block(self._definitions(), 'animations')[index]
            for key, frame, marker, reporting in cast(
                    list[tuple[tuple[object, ...], int, str, str]], record['effects']):
                block = self.block(animation, 'effect events')
                element = block[block.add()]
                self.required_field(element, 'effect').set(effect_indices[key])
                self.required_field(element, 'frame').set(frame)
                if self.game in {'halo3', 'halo3odst'}:
                    self.required_field(element, 'marker name').set(marker)
                if self.game == 'halo3odst' and reporting != 'unknown':
                    if element.field('damage effect reporting type') is None:
                        raise ValueError(
                            f'{self.path}: this ODST animation graph cannot store '
                            'effect damage reporting types')
                    self._set_event_enum(element, 'damage effect reporting type', reporting)
                animation = self.block(self._definitions(), 'animations')[index]
            for dialogue, frame in cast(list[tuple[str, int]], record['dialogues']):
                block = self.block(animation, 'dialogue events')
                element = block[block.add()]
                self._set_event_enum(element, 'dialogue event', dialogue)
                self.required_field(element, 'frame').set(frame)
                animation = self.block(self._definitions(), 'animations')[index]
        if owned:
            self.tag_has_changes = True
        return len(owned)

    @staticmethod
    def _event_enum(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError(f'Unknown animation-event enum value {value!r}')
        return value.partition('{')[0].strip().replace('_', ' ')

    def _event_reference(self, element: blam_tags.TagStruct, kind: str):
        from .frame_event_list import FrameEventListTag, Reference

        reference = Reference()
        path = self.reference(element, kind)
        reference.tag = path.RelativePathWithExtension if path is not None else ''
        flags = self.required_field(element, 'flags')
        options = flags.options()
        available = set() if options is None else set(options.names)
        for attribute, flag_name in FrameEventListTag.reference_flags:
            setattr(reference, attribute,
                    flags.get_flag(flag_name) if flag_name in available else False)
        if self.corinth:
            model = self.reference(element, 'model')
            reference.model_tag = model.RelativePathWithExtension if model is not None else ''
            reference.variant = str(self.value(element, 'variant'))
        return reference

    def inline_events(self) -> dict[str, list[AnimationEvent]]:
        from .frame_event_list import (
            AnimationEvent, DialogueEvent, EffectEvent, Reference, SoundEvent,
            collapse_events,
        )
        from .. import utils

        definitions = self._definitions()
        if self.game == 'halo1':
            sound_references: list[Reference] = []
            for element in self.block(definitions, 'sound references'):
                reference = Reference()
                path = self.reference(element, 'sound')
                reference.tag = path.RelativePathWithExtension if path is not None else ''
                sound_references.append(reference)
            result: dict[str, list[AnimationEvent]] = {}
            for animation in self.block(definitions, 'animations'):
                name = str(self.value(animation, 'name'))
                events: list[AnimationEvent] = []
                for field_name, event_type in (
                        ('left foot frame index', 'left foot'),
                        ('right foot frame index', 'right foot')):
                    frame = int(self.value(animation, field_name))
                    # Halo 1 reserves zero for "no foot event".
                    if frame <= 0:
                        continue
                    event = AnimationEvent()
                    event.frame = utils.blender_frame(frame - 1)
                    event.end_frame = event.frame
                    event.type = event_type
                    events.append(event)
                sound_index = int(self.value(animation, 'sound'))
                if 0 <= sound_index < len(sound_references):
                    event = AnimationEvent()
                    event.frame = utils.blender_frame(
                        int(self.value(animation, 'sound frame index')))
                    event.end_frame = event.frame
                    sound = SoundEvent()
                    sound.sound_reference = sound_references[sound_index]
                    event.sound_events.append(sound)
                    events.append(event)
                result[name] = collapse_events(events)
            return result
        references = {
            kind: [self._event_reference(element, kind)
                   for element in self.block(definitions, kind + ' references')]
            for kind in ('sound', 'effect')
        }
        result: dict[str, list[AnimationEvent]] = {}
        for animation in self.block(definitions, 'animations'):
            name = str(self.value(animation, 'name'))
            holder = animation
            if animation.field('frame events') is None:
                shared_field = animation.field('shared animation data')
                shared = None if shared_field is None else shared_field.as_block()
                if shared is None or not len(shared):
                    result[name] = []
                    continue
                holder = shared[0]

            events: list[AnimationEvent] = []
            for element in self.block(holder, 'frame events'):
                event = AnimationEvent()
                event.frame = utils.blender_frame(int(self.value(element, 'frame')))
                event.end_frame = event.frame
                event.type = self._event_enum(self.value(element, 'type'))
                if event.type in {'jetpack closed', 'jetpack open', 'sound event', 'effect event'}:
                    event.type = 'none'
                events.append(event)

            unbound: AnimationEvent | None = None
            for kind, cls in (
                ('sound', SoundEvent), ('effect', EffectEvent),
                ('dialogue', DialogueEvent),
            ):
                event_field = holder.field(kind + ' events')
                event_block = None if event_field is None else event_field.as_block()
                if event_block is None:
                    continue
                for element in event_block:
                    record = cls()
                    record.frame_offset = int(self.value(element, 'frame'))
                    if kind == 'dialogue':
                        record.dialogue_type = self._event_enum(
                            self.value(element, 'dialogue event'))
                    else:
                        reference_index = int(self.value(element, kind))
                        if reference_index < 0:
                            continue
                        if reference_index >= len(references[kind]):
                            raise ValueError(
                                f'{self.path}: invalid {kind} reference index '
                                f'{reference_index} in animation {name!r}')
                        setattr(record, kind + '_reference', references[kind][reference_index])
                        marker = element.field('marker name')
                        record.marker_name = '' if marker is None else str(marker.value)
                        if kind == 'effect' and element.field('damage effect reporting type') is not None:
                            record.damage_effect_reporting_type = self._event_enum(
                                self.value(element, 'damage effect reporting type'))
                    if unbound is None:
                        unbound = AnimationEvent()
                        events.append(unbound)
                    getattr(unbound, kind + '_events').append(record)
            result[name] = collapse_events(events)
        return result

    def events_to_blender(
            self, imported_animations, convert_names=False,
            target_game: str = '') -> int:
        from .frame_event_list import FrameEventListTag, apply_event_map_to_blender
        from .. import utils

        if not imported_animations:
            return 0
        events = self.inline_events()
        reference_field = self._definitions().field('imported events')
        event_list = self.frame_event_list()
        if reference_field is not None:
            if event_list is None:
                utils.print_warning('Animation graph contains no reference to a frame event list')
            elif not self.path_exists(event_list):
                utils.print_warning(
                    f'Frame events list tag does not exist: {event_list.Filename}')
            else:
                imported_names = {
                    animation.name.replace(':', ' ')
                    for animation in imported_animations if animation.export_this
                }
                animation_names = set()
                for source_name in self.animation_names():
                    converted_name = (convert_animation_name_for_project(
                        source_name, self.game, target_game)
                        if convert_names else source_name)
                    if converted_name.replace(':', ' ') in imported_names:
                        animation_names.add(source_name)
                with FrameEventListTag(path=event_list) as external:
                    external_events = external.collect_events(animation_names)
                for name, list_events in external_events.items():
                    graph_events = events.get(name, [])
                    events[name] = list_events + [
                        event for event in graph_events
                        if not any(event == external_event for external_event in list_events)
                    ]
        if convert_names:
            converted_events = {}
            for name, animation_events in events.items():
                converted_name = convert_animation_name_for_project(
                    name, self.game, target_game)
                converted_events.setdefault(converted_name, []).extend(animation_events)
            events = converted_events
        return apply_event_map_to_blender(events, imported_animations)

    @staticmethod
    def _blend_screen_settings(
        state: str,
    ) -> tuple[str, str, str, float, tuple[str, ...]]:
        yaw = pitch = weight = 'none'
        rate = 0.0
        flags: list[str] = []
        if 'aim' in state:
            yaw, pitch = 'aim yaw', 'aim pitch'
        elif 'look' in state:
            yaw, pitch = 'look yaw', 'look pitch'
            flags.append('allow parent adjustment')
        elif 'steer' in state:
            yaw = pitch = 'steering'
        elif 'acc' in state:
            yaw, pitch, weight, rate = (
                'acceleration yaw', 'acceleration pitch',
                'acceleration magnitude', 0.333,
            )
        elif 'pitch' in state and 'turn' in state:
            yaw, pitch = 'first person turn', 'first person pitch'
        elif 'defense' in state:
            yaw, pitch, weight, rate = 'defense yaw', 'defense pitch', 'defense', 0.25
        elif 'pain' in state:
            rate = 0.333
            for suffix, label in (
                ('gut', 'gut'), ('chest', 'chest'), ('head', 'head'),
                ('left_shoulder', 'left shoulder'), ('left_arm', 'left arm'),
                ('left_leg', 'left leg'), ('left_foot', 'left foot'),
                ('right_shoulder', 'right shoulder'), ('right_arm', 'right arm'),
                ('right_leg', 'right leg'), ('right_foot', 'right foot'),
            ):
                if state.endswith(suffix):
                    yaw = f'damage {label} yaw'
                    pitch = f'damage {label} pitch'
                    weight = f'damage {label}'
                    break
        if state.endswith('_down'):
            flags.append('active only when weapon down')
        elif state == 'aiming':
            flags.append('attempt piece-wise blending')
        return yaw, pitch, weight, rate, tuple(flags)

    def setup_blend_screens(self, animation_names: Iterable[str]) -> None:
        definitions = self._definitions()
        screens_field = definitions.field('NEW blend screens')
        screens = None if screens_field is None else screens_field.as_block()
        if screens is None:
            raise NotImplementedError(
                f'{self.path}: pose-overlay blend screens are unavailable in this graph layout')

        animations = self.block(definitions, 'animations')
        animation_name_by_index = {
            index: str(self.value(element, 'name'))
            for index, element in enumerate(animations)
        }
        animation_index_by_name = {
            name: index for index, name in animation_name_by_index.items()
        }
        missing = {name.replace(' ', ':') for name in animation_names}
        remove: list[int] = []
        for index, element in enumerate(screens):
            animation = self.required_field(element, 'animation').as_struct()
            if animation is None:
                raise TypeError(f'{self.path}: blend screen {index} animation is not a struct')
            animation_index = int(self.value(animation, 'animation'))
            if animation_index < 0:
                remove.append(index)
                continue
            name = animation_name_by_index.get(animation_index)
            if name is not None:
                missing.discard(name)

        for index in reversed(remove):
            screens.delete(index)
            self.tag_has_changes = True

        functions = {
            str(self.value(element, 'name')): index
            for index, element in enumerate(self.block(definitions, 'functions'))
        }
        for name in sorted(missing):
            animation_index = animation_index_by_name.get(name)
            if animation_index is None:
                continue
            index = screens.add()
            screens = self.block(definitions, 'NEW blend screens')
            element = screens[index]
            self.required_field(element, 'name').set(name)
            animation = self.required_field(element, 'animation').as_struct()
            if animation is None:
                raise TypeError(f'{self.path}: blend screen {index} animation is not a struct')
            self.required_field(animation, 'animation').set(animation_index)

            state = name.rsplit(':', 1)[-1]
            yaw, pitch, weight, rate, flag_names = self._blend_screen_settings(state)
            for field_name, value in (
                ('yaw source', yaw), ('pitch source', pitch),
                ('weight source', weight), ('interpolation rate', rate),
            ):
                self.required_field(element, field_name).set(value)
            function_index = functions.get(state)
            if function_index is not None:
                self.required_field(element, 'weight function').set(function_index)
            flags = self.required_field(element, 'flags')
            for flag_name in flag_names:
                flags.set_flag(flag_name, True)
            self.tag_has_changes = True

    def set_parent_graph(self, path: TagPathInput | None) -> None:
        if isinstance(path, RelativeTagPath):
            path = path.RelativePathWithExtension
        parent = None if not path else Path(path).with_suffix('.model_animation_graph')
        self.set_reference(self._definitions(), 'parent animation graph', parent)

    def set_node_usages(self, node_names: list[str],
                        usages_by_node: dict[str, list[str]]) -> None:
        definitions = self._definitions()
        usage_field = definitions.field('node usage')
        usage_block = None if usage_field is None else usage_field.as_block()
        if usage_block is None:
            if usages_by_node:
                raise NotImplementedError(
                    f'{self.path}: node usages are unavailable in this graph layout')
            return
        skeleton = self.block(definitions, 'skeleton nodes')
        if len(skeleton) != len(node_names):
            skeleton.clear()
            for name in node_names:
                node = skeleton[skeleton.add()]
                self.required_field(node, 'name').set(name)

        node_indices = {node.name: index for index, node in enumerate(self.nodes())}
        usages = usage_block
        usages.clear()
        for node_name, usage_names in usages_by_node.items():
            node_index = node_indices.get(node_name)
            if node_index is None:
                continue
            for usage_name in usage_names:
                element = usages[usages.add()]
                self.required_field(element, 'usage').set(usage_name)
                self.required_field(element, 'node to use').set(node_index)
        self.tag_has_changes = True

    def set_data_driven(self, enabled: bool = True) -> None:
        flags = self.required_field(self._definitions(), 'private flags')
        flags.set_flag('uses data driven animation', enabled)
        self.tag_has_changes = True

    def set_ik_chains(self, node_names: list[str],
                      chains: Iterable[AnimationGraphIkChainInput]) -> None:
        definitions = self._definitions()
        chains = list(chains)
        chains_field = definitions.field('ik chains')
        chains_block = None if chains_field is None else chains_field.as_block()
        if chains_block is None:
            if chains:
                raise NotImplementedError(
                    f'{self.path}: IK chains are unavailable in this graph layout')
            return
        skeleton = self.block(definitions, 'skeleton nodes')
        if len(skeleton) != len(node_names):
            skeleton.clear()
            for name in node_names:
                node = skeleton[skeleton.add()]
                self.required_field(node, 'name').set(name)

        node_indices = {node.name: index for index, node in enumerate(self.nodes())}
        valid = [chain for chain in chains
                 if chain.start_node in node_indices and chain.effector_node in node_indices]
        ik_chains = chains_block
        ik_chains.clear()
        count = len(valid)
        for chain_index, chain in enumerate(valid):
            element = ik_chains[ik_chains.add()]
            self.required_field(element, 'name').set(chain.name)
            self.required_field(element, 'start node').set(node_indices[chain.start_node])
            self.required_field(element, 'effector node').set(node_indices[chain.effector_node])
            self.required_field(element, 'rank').set(count - 1 - chain_index)
            self.required_field(element, 'antecedents').set(1 << chain_index)
        self.tag_has_changes = True

    def set_compression(self, animations: Iterable[AnimationCompressionInput],
                        forced: str) -> None:
        requested = {animation.name.replace(' ', ':'): animation.compression
                     for animation in animations}
        compression_values = {'Medium': 0, 'Rough': 1, 'Uncompressed': 2}
        for element in self.block(self._definitions(), 'animations'):
            compression = requested.get(str(self.value(element, 'name')))
            target = compression_values.get(compression)
            if target is None:
                continue
            shared_field = element.field('shared animation data')
            shared = None if shared_field is None else shared_field.as_block()
            if shared is None:
                field = self.required_field(element, 'desired compression')
            elif len(shared):
                field = self.required_field(shared[0], 'desired compression')
            else:
                continue
            options = field.options()
            if options is None or options.current != target:
                field.set(target)
                self.tag_has_changes = True

        self.set_forced_compression(forced)

    def set_forced_compression(self, forced: str | int) -> None:
        forced_values = {'none': 0, 'medium': 1, 'rough': 2, 'uncompressed': 3}
        target = forced_values.get(forced) if isinstance(forced, str) else forced
        if target not in forced_values.values():
            raise ValueError(f'Unknown forced animation compression: {forced!r}')
        field = self._definitions().field('force compression setting')
        if field is None:
            if target != 0:
                raise NotImplementedError(
                    f'{self.path}: forced compression is unavailable in this graph layout')
            return
        options = field.options()
        if options is None or options.current != target:
            field.set(target)
            self.tag_has_changes = True

    def force_uncompressed_for_import(self) -> tuple[int, bool]:
        field = self._definitions().field('force compression setting')
        if field is None:
            return 0, False
        options = field.options()
        original = int(field.value) if options is None else options.current
        if self.corinth or original == 3:
            return original, False
        field.set(3)
        self.tag_has_changes = True
        return original, True

    def restore_forced_compression(self, value: int) -> None:
        field = self._definitions().field('force compression setting')
        if field is None:
            if value:
                raise NotImplementedError(
                    f'{self.path}: forced compression is unavailable in this graph layout')
            return
        options = field.options()
        current = int(field.value) if options is None else options.current
        if current != value:
            field.set(value)
            self.tag_has_changes = True

    def _set_supported_flag(self, field: blam_tags.TagField,
                            names: tuple[str, ...], enabled: bool) -> None:
        options = field.options()
        available = set() if options is None else set(options.names)
        name = next((candidate for candidate in names if candidate in available), None)
        if name is None:
            if enabled:
                raise NotImplementedError(
                    f'{self.path}: animation flag {names[0]!r} is unavailable')
            return
        field.set_flag(name, enabled)

    def _local_frame_count(self, animation: blam_tags.TagStruct) -> int | None:
        direct = animation.field('frame count')
        if direct is not None:
            return int(direct.value)
        shared_field = animation.field('shared animation data')
        shared = None if shared_field is None else shared_field.as_block()
        if shared is not None and len(shared):
            return int(self.value(shared[0], 'frame count'))
        return None

    def set_animation_settings(
            self, animations: Iterable[AnimationSettingsInput]) -> None:
        requested = {
            animation.name.lower().replace(':', ' '): animation
            for animation in animations
        }
        definitions = self._definitions()
        pca_data_field = definitions.field('pca data')
        pca_data = None if pca_data_field is None else pca_data_field.as_struct()
        for element in self.block(definitions, 'animations'):
            name = str(self.value(element, 'name'))
            settings = requested.get(name.lower().replace(':', ' '))
            if settings is None:
                continue
            self.required_field(element, 'weight').set(settings.weight)
            self.required_field(element, 'loop frame index').set(
                settings.loop_frame_index)
            # Halo 1 calls its small playback bitfield simply ``flags``.  It
            # only exposes compression/world-relative/PAL bits, so the shared
            # flag writer below will still reject any enabled setting that the
            # classic layout cannot represent while allowing common metadata
            # such as weight and loop frame to be written.
            flags = (element.field('user flags') or
                     element.field('playback flags') or
                     element.field('flags'))
            if flags is None:
                raise ValueError(f'{self.path}: animation {name!r} has no flags field')
            for names, enabled in (
                    (('disable interpolation in', 'disable interpolation_in'), settings.disable_interpolation_in),
                    (('disable interpolation out', 'disable interpolation_out'), settings.disable_interpolation_out),
                    (('disable mode ik',), settings.disable_mode_ik),
                    (('disable weapon ik',), settings.disable_weapon_ik),
                    (('disable weapon aim/1st person',), settings.disable_weapon_aim),
                    (('disable look screen',), settings.disable_look_screen),
                    (('disable transition adjustment',), settings.disable_transition_adjustment),
                    (('force weapon ik on',), settings.force_weapon_ik_on),
                    (('enable animated source interpolation',), settings.enable_animated_source_interpolation),
                    (('disable ik sets',), settings.disable_ik_sets),
                    (('disable ik chains',), settings.disable_ik_chains),
                    (('translate and scale root only',), settings.translate_and_scale_root_only),
                    (('enable blend-out on replacement anims', 'enable blend out'), settings.enable_blend_out_on_replacement_anims),
                    (('override player input with motion',), settings.override_player_input_with_motion),
                    (('disable subframe interp on loop',), settings.disable_subframe_interp_on_loop)):
                self._set_supported_flag(flags, names, enabled)

            for field_name, flag_names, value in (
                    ('override blend in time', ('use custom blend-in time', 'override default blend time'), settings.override_blend_in_time),
                    ('override blend out time', ('use custom blend-out time', 'override default blend out time'), settings.override_blend_out_time)):
                enabled = value > 0.0
                self._set_supported_flag(flags, flag_names, enabled)
                field = element.field(field_name)
                if field is None:
                    if enabled:
                        raise NotImplementedError(
                            f'{self.path}: {field_name!r} is unavailable')
                elif enabled:
                    field.set(value)

            pca_group = element.field('pca group name')
            if pca_group is not None:
                group_name = name if settings.pca_best_quality else settings.pca_group_name
                pca_group.set(group_name)
                if settings.pca_best_quality:
                    if pca_data is None:
                        raise NotImplementedError(
                            f'{self.path}: PCA groups are unavailable')
                    frame_count = self._local_frame_count(element)
                    if frame_count is None:
                        raise NotImplementedError(
                            f'{self.path}: PCA animation {name!r} has no local frame data')
                    groups = self.block(pca_data, 'PCA Groups')
                    group = next((item for item in groups
                                  if self.value(item, 'Group Name') == name), None)
                    if group is None:
                        group = groups[groups.add()]
                        self.required_field(group, 'Group Name').set(name)
                    self.required_field(group, 'Desired Mesh Count').set(frame_count)
            self.tag_has_changes = True

    def set_world_animations(self, animation_names: Iterable[str]) -> None:
        # Sidecar/export names use colon-separated graph paths, while H1 Tool
        # writes the same names with spaces into model_animations.
        targets = {name.replace(' ', ':') for name in animation_names}
        for element in self.block(self._definitions(), 'animations'):
            if str(self.value(element, 'name')).replace(' ', ':') not in targets:
                continue
            shared_field = element.field('shared animation data')
            shared = None if shared_field is None else shared_field.as_block()
            if shared is None:
                flags = (element.field('internal flags') or
                         element.field('flags'))
                if flags is None:
                    raise ValueError(
                        f'{self.path}: animation {self.value(element, "name")!r} '
                        'has no world-relative flags field')
            elif len(shared):
                flags = self.required_field(shared[0], 'internal flags')
            else:
                continue
            flags.set_flag('world relative', True)
            self.tag_has_changes = True

    def update_vehicle_suspension(
            self, updates: dict[str, VehicleSuspensionUpdate]) -> None:
        content = self.required_field(self.tag.root(), 'content').as_struct()
        if content is None:
            raise TypeError(f'{self.path}: content is not a structure')
        for element in self.block(content, 'vehicle suspension'):
            update = updates.get(str(self.value(element, 'label')))
            if update is None:
                continue
            self.required_field(element, 'marker name').set(update.marker_name)
            self.required_field(element, 'full extension ground_depth').set(
                update.extension_depth)
            self.required_field(element, 'full compression ground_depth').set(
                update.compression_depth)
            if update.destroyed_region_name:
                self.required_field(element, 'region name').set(
                    update.destroyed_region_name)
                self.required_field(element, 'destroyed full extension ground_depth').set(
                    update.destroyed_extension_depth)
                self.required_field(element, 'destroyed full compression ground_depth').set(
                    update.destroyed_compression_depth)
            self.tag_has_changes = True

    def copy_skeleton_from(self, source: AnimationGraphTag) -> None:
        """Replace this graph's skeleton with another graph's compatible block."""
        destination = self.block(self._definitions(), 'skeleton nodes')
        source_nodes = source.block(source._definitions(), 'skeleton nodes')
        destination.copy_from(source_nodes)
        self.tag_has_changes = True

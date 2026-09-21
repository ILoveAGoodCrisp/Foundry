"""Native model-animation-graph metadata used outside the legacy graph editor."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import degrees
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from .backend import RelativeTagPath, TagDocument, TagPathInput, TagReference
from .blender import BlenderTag

if TYPE_CHECKING:
    import blam_tags


@dataclass(frozen=True)
class AnimationGraphNode:
    name: str
    parent_index: int


class AnimationGraphIkChainInput(Protocol):
    name: str
    start_node: str
    effector_node: str


class AnimationCompressionInput(Protocol):
    name: str
    compression: str


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
        definitions = self.required_field(self.tag.root(), 'definitions').as_struct()
        if definitions is None:
            raise TypeError(f'{self.path}: definitions is not a structure')
        return definitions

    def animation_names(self, contains: str = '') -> list[str]:
        animations = self.block(self._definitions(), 'animations')
        names = [str(self.value(animation, 'name')) for animation in animations]
        if contains:
            return [name for name in names if contains in name]
        return names

    def blend_screens(self) -> dict[str, AnimationBlendScreen]:
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
        result: dict[str, AnimationBlendScreen] = {}
        for animation in self.block(definitions, 'animations'):
            field = animation.field('blend screen')
            if field is None:
                continue
            index = int(field.value)
            if 0 <= index < len(screens):
                result[str(self.value(animation, 'name'))] = screens[index]
        return result

    def nodes(self) -> list[AnimationGraphNode]:
        nodes = self.block(self._definitions(), 'skeleton nodes')
        return [AnimationGraphNode(
            name=str(self.value(node, 'name')),
            parent_index=int(self.value(node, 'parent node index')),
        ) for node in nodes]

    def get_nodes(self) -> list[str]:
        """Compatibility name for callers that only need skeleton ordering."""
        return [node.name for node in self.nodes()]

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

    def parent_graph(self) -> TagReference | None:
        return self.reference(self._definitions(), 'parent animation graph')

    def frame_event_list(self) -> TagReference | None:
        if self._definitions().field('imported events') is None:
            return None
        return self.reference(self._definitions(), 'imported events')

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

        forced_values = {'none': 0, 'medium': 1, 'rough': 2, 'uncompressed': 3}
        target = forced_values.get(forced)
        if target is None:
            raise ValueError(f'Unknown forced animation compression: {forced!r}')
        field = self._definitions().field('force compression setting')
        if field is None:
            if forced != 'none':
                raise NotImplementedError(
                    f'{self.path}: forced compression is unavailable in this graph layout')
            return
        options = field.options()
        if options is None or options.current != target:
            field.set(target)
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
            flags = element.field('user flags') or element.field('playback flags')
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
        targets = set(animation_names)
        for element in self.block(self._definitions(), 'animations'):
            if str(self.value(element, 'name')) not in targets:
                continue
            shared_field = element.field('shared animation data')
            shared = None if shared_field is None else shared_field.as_block()
            if shared is None:
                flags = self.required_field(element, 'internal flags')
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

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
    import bpy
    from .frame_event_list import AnimationEvent


@dataclass(frozen=True)
class AnimationGraphNode:
    name: str
    parent_index: int


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
        if definitions.field('imported events') is None:
            raise NotImplementedError(
                f'{self.path}: imported frame-event lists are unavailable in this graph layout')
        from .frame_event_list import FrameEventListTag

        event_list_path = Path(self.tag_path.RelativePath).with_suffix('.frame_event_list')
        with FrameEventListTag(path=event_list_path) as events:
            events.from_blender(self.event_animations(), blender_animations)
            self.set_reference(definitions, 'imported events', events.tag_path)

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
            AnimationEvent, DialogueEvent, EffectEvent, SoundEvent,
            collapse_events,
        )
        from .. import utils

        definitions = self._definitions()
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
                for element in self.block(holder, kind + ' events'):
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
                        record.marker_name = str(self.value(element, 'marker name'))
                        if kind == 'effect' and element.field('damage effect reporting type') is not None:
                            record.damage_effect_reporting_type = self._event_enum(
                                self.value(element, 'damage effect reporting type'))
                    if unbound is None:
                        unbound = AnimationEvent()
                        events.append(unbound)
                    getattr(unbound, kind + '_events').append(record)
            result[name] = collapse_events(events)
        return result

    def events_to_blender(self, imported_animations) -> int:
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
                animation_names = {
                    animation.name for animation in imported_animations
                    if animation.export_this
                }
                with FrameEventListTag(path=event_list) as external:
                    external_events = external.collect_events(animation_names)
                for name, list_events in external_events.items():
                    graph_events = events.get(name, [])
                    events[name] = list_events + [
                        event for event in graph_events
                        if not any(event == external_event for external_event in list_events)
                    ]
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

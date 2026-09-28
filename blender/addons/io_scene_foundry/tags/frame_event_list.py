from pathlib import Path
import random
import bpy

from .blender import BlenderTag
from .backend import TagDocument
from .. import utils
from ..animation_events import canonical_frame_event

import json
from bpy.types import PropertyGroup, bpy_prop_collection

FRAME_EVENT_TYPE = "_connected_geometry_animation_event_type_frame"

def propgroup_to_dict(pg: PropertyGroup) -> dict:
    data = {}

    for prop in pg.bl_rna.properties:
        key = prop.identifier

        if key == "rna_type" or prop.is_readonly:
            continue
        if key == "marker":
            marker = getattr(pg, key, None)
            data["marker_name"] = getattr(pg, "marker_name", "") or (marker.nwo.marker_model_group if marker else "")
            continue
        if key == "marker_name" and hasattr(pg, "marker"):
            marker = pg.marker
            data[key] = pg.marker_name or (marker.nwo.marker_model_group if marker else "")
            continue

        value = getattr(pg, key)

        if isinstance(value, PropertyGroup):
            data[key] = propgroup_to_dict(value)
        elif isinstance(value, bpy_prop_collection):
            data[key] = [
                propgroup_to_dict(item)
                for item in value
            ]

        else:
            try:
                json.dumps(value)
                data[key] = value
            except TypeError:
                try:
                    data[key] = list(value)
                except Exception:
                    pass

    return data

def animation_event_to_dict(event: PropertyGroup) -> dict:
    data = propgroup_to_dict(event)
    if hasattr(event, "event_data"):
        data["event_data"] = [
            propgroup_to_dict(item)
            for item in event.event_data
        ]

    return data

def apply_dict_to_propgroup(pg: PropertyGroup, data: dict):
    for key, value in data.items():
        if key == "marker_name":
            if hasattr(pg, "marker_name"):
                pg.marker_name = value
            elif hasattr(pg, "marker"):
                pg.marker = bpy.data.objects.get(value) if value else None
            continue

        if not hasattr(pg, key):
            continue

        if key == "frame_name":
            value = canonical_frame_event(value)
        current = getattr(pg, key)

        if isinstance(current, PropertyGroup):
            apply_dict_to_propgroup(current, value)
        elif isinstance(current, bpy_prop_collection):
            current.clear()

            for item_data in value:
                item = current.add()
                apply_dict_to_propgroup(item, item_data)
        else:
            try:
                setattr(pg, key, value)
            except Exception:
                pass


def dump_frame_animation_events(
    animation_events,
    filepath: str | Path,
):
    filepath = Path(filepath)

    data = [
        animation_event_to_dict(event)
        for event in animation_events
        if getattr(event, "event_type", None) == FRAME_EVENT_TYPE
    ]
    
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def import_frame_animation_events(
    animation_events,
    filepath: str | Path,
):
    filepath = Path(filepath)

    with filepath.open("r", encoding="utf-8") as f:
        data = json.load(f)
        
    for event_data in data:
        event = animation_events.add()
        event.event_type = FRAME_EVENT_TYPE
        apply_dict_to_propgroup(event, event_data)

class Reference:
    def __init__(self):
        self.tag = ""
        self.allow_on_player = False
        self.left_arm_only = False
        self.right_arm_only = False
        self.first_person_only = False
        self.third_person_only = False
        self.forward_only = False
        self.reverse_only = False
        self.fp_no_aged_weapons = False
        
        self.model_tag = ""
        self.variant = ""
        self.index = -1
        
class SoundEvent:
    def __init__(self):
        self.animation_event_index = -1
        self.frame_offset = 0
        self.sound_reference: Reference = None
        self.marker_name = ""
    
    def __hash__(self):
        return hash((self.frame_offset, self.sound_reference.__dict__.values(), self.marker_name))
    
class EffectEvent:
    def __init__(self):
        self.animation_event_index = -1
        self.frame_offset = 0
        self.effect_reference: Reference = None
        self.marker_name = ""
        self.damage_effect_reporting_type = "unknown"
    
    def __hash__(self):
        return hash((self.frame_offset, self.effect_reference.__dict__.values(), self.marker_name, self.damage_effect_reporting_type))
    
class DialogueEvent:
    def __init__(self):
        self.animation_event_index = -1
        self.frame_offset = 0
        self.dialogue_type = "bump"
    
    def __hash__(self):
        return hash((self.frame_offset, self.dialogue_type))
    
class AnimationEvent:
    def __init__(self):
        self.sound_events: list[SoundEvent] = []
        self.effect_events: list[EffectEvent] = []
        self.dialogue_events: list[DialogueEvent] = []
        
        self.frame = 0
        self.type = "none"
        self.name = ""
        self.end_frame = 0
        self.unique_id = random.randint(0, 2147483647)
        
    def from_blender(self, blender_animation, blender_animation_event, unique_sounds: dict, unique_effects: dict):
        self.frame = utils.game_frame(blender_animation_event.frame_frame - blender_animation.frame_start)
        self.type = blender_animation_event.frame_name
        self.name = blender_animation_event.frame_name.replace(" ", "_")
        self.unique_id = blender_animation_event.event_id
        if blender_animation_event.multi_frame == 'range':
            self.end_frame = utils.game_frame(blender_animation_event.frame_range - blender_animation.frame_start)
        
        for data in blender_animation_event.event_data:
            match data.data_type:
                case 'SOUND':
                    sound = SoundEvent()
                    sound.frame_offset = data.frame_offset
                    if data.marker_name:
                        sound.marker_name = data.marker_name
                    else:
                        if data.marker is not None:
                            sound.marker_name = data.marker.nwo.marker_model_group
                    sound.sound_reference = unique_sounds.get((data.event_sound_tag, data.flag_allow_on_player, data.flag_left_arm_only, data.flag_right_arm_only, data.flag_first_person_only, data.flag_third_person_only, data.flag_forward_only, data.flag_reverse_only, data.flag_fp_no_aged_weapons, data.event_model, data.variant))
                    if sound.sound_reference is not None:
                        self.sound_events.append(sound)
                case 'EFFECT':
                    effect = EffectEvent()
                    effect.frame_offset = data.frame_offset
                    if data.marker_name:
                        effect.marker_name = data.marker_name
                    else:
                        if data.marker is not None:
                            effect.marker_name = data.marker.nwo.marker_model_group
                    effect.effect_reference = unique_effects.get((data.event_effect_tag, data.flag_allow_on_player, data.flag_left_arm_only, data.flag_right_arm_only, data.flag_first_person_only, data.flag_third_person_only, data.flag_forward_only, data.flag_reverse_only, data.flag_fp_no_aged_weapons, data.event_model, data.variant))
                    effect.damage_effect_reporting_type = data.damage_effect_reporting_type
                    if effect.effect_reference is not None:
                        self.effect_events.append(effect)
                case 'DIALOGUE':
                    dialogue = DialogueEvent()
                    dialogue.frame_offset = data.frame_offset
                    dialogue.dialogue_type = data.dialogue_event
                    self.dialogue_events.append(dialogue)
    
    def __eq__(self, value):
        return isinstance(value, AnimationEvent) and self.frame == value.frame and self.type == value.type
        # if not isinstance(value, AnimationEvent) and self.frame == value.frame and self.type == value.type and self.end_frame == value.end_frame:
        #     return False
        # if [s.__hash__() for s in self.sound_events] != [s.__hash__() for s in value.sound_events]:
        #     return False
        # if [e.__hash__() for e in self.effect_events] != [e.__hash__() for e in value.effect_events]:
        #     return False
        # if [d.__hash__() for d in self.dialogue_events] != [d.__hash__() for d in value.dialogue_events]:
        #     return False
        

def collapse_events(events: list[AnimationEvent]) -> list[AnimationEvent]:
    ordered = sorted(events, key=lambda event: event.frame, reverse=True)
    collapsed: list[AnimationEvent] = []
    end = ordered[0].frame if ordered else 0
    for index, current in enumerate(ordered):
        following = ordered[index + 1] if index + 1 < len(ordered) else None
        if (following is not None and following.frame == current.frame - 1
                and current.type == following.type
                and not (current.sound_events or current.effect_events
                         or current.dialogue_events)):
            continue
        current.end_frame = end
        collapsed.append(current)
        end = following.frame if following is not None else 0
    return collapsed


def apply_event_map_to_blender(
    events_by_animation: dict[str, list[AnimationEvent]],
    imported_animations,
) -> int:
    blender_animations = {
        animation.name.replace(':', ' '): animation
        for animation in imported_animations if animation.export_this
    }
    blender_markers = {
        ob.nwo.marker_model_group: ob
        for ob in bpy.data.objects if ob.type == 'EMPTY'
    }

    def apply_flags(blender_data_event, reference: Reference) -> None:
        blender_data_event.flag_allow_on_player = reference.allow_on_player
        blender_data_event.flag_left_arm_only = reference.left_arm_only
        blender_data_event.flag_right_arm_only = reference.right_arm_only
        blender_data_event.flag_first_person_only = reference.first_person_only
        blender_data_event.flag_third_person_only = reference.third_person_only
        blender_data_event.flag_forward_only = reference.forward_only
        blender_data_event.flag_reverse_only = reference.reverse_only
        blender_data_event.flag_fp_no_aged_weapons = reference.fp_no_aged_weapons

    event_count = 0
    for name, animation_events in events_by_animation.items():
        blender_animation = blender_animations.get(name.replace(':', ' '))
        if blender_animation is None:
            blender_animation = blender_animations.get(name)
        if blender_animation is None or not animation_events:
            continue
        utils.print_bullet(f'Getting events for {blender_animation.name}')
        remove = [index for index, event in enumerate(blender_animation.animation_events)
                  if event.event_type == FRAME_EVENT_TYPE]
        for index in reversed(remove):
            blender_animation.animation_events.remove(index)

        for event in sorted(animation_events, key=lambda value: value.frame):
            blender_event = blender_animation.animation_events.add()
            blender_event.frame_frame = blender_animation.frame_start + event.frame
            if event.end_frame > event.frame:
                blender_event.multi_frame = 'range'
                blender_event.frame_range = blender_animation.frame_start + event.end_frame
            blender_event.frame_name = canonical_frame_event(event.type)
            blender_event.event_id = event.unique_id
            data_events = event.sound_events + event.effect_events + event.dialogue_events
            data_events.sort(key=lambda value: value.frame_offset)
            for data_event in data_events:
                blender_data_event = blender_event.event_data.add()
                blender_data_event.frame_offset = data_event.frame_offset
                if isinstance(data_event, SoundEvent):
                    blender_data_event.data_type = 'SOUND'
                    blender_data_event.marker = blender_markers.get(data_event.marker_name)
                    blender_data_event.event_sound_tag = data_event.sound_reference.tag
                    apply_flags(blender_data_event, data_event.sound_reference)
                elif isinstance(data_event, EffectEvent):
                    blender_data_event.data_type = 'EFFECT'
                    blender_data_event.marker = blender_markers.get(data_event.marker_name)
                    blender_data_event.event_effect_tag = data_event.effect_reference.tag
                    apply_flags(blender_data_event, data_event.effect_reference)
                    blender_data_event.damage_effect_reporting_type = data_event.damage_effect_reporting_type
                else:
                    blender_data_event.data_type = 'DIALOGUE'
                    blender_data_event.dialogue_event = data_event.dialogue_type
        event_count += len(animation_events)
    return event_count


class FrameEventListTag(BlenderTag, TagDocument):
    """Native event-list reads and edits; shared graph readers remain separate."""
    tag_ext = 'frame_event_list'
    reference_flags = (
        ('allow_on_player', 'allow on player'), ('left_arm_only', 'left arm only'),
        ('right_arm_only', 'right arm only'), ('first_person_only', 'first-person only'),
        ('third_person_only', 'third-person only'), ('forward_only', 'forward only'),
        ('reverse_only', 'reverse only'), ('fp_no_aged_weapons', 'fp no aged weapons'),
    )

    def __init__(self, path='', **kwargs):
        kwargs.setdefault('tag_must_exist', False)
        super().__init__(path, **kwargs)

    def _root_block(self, name):
        return self.block(self.tag.root(), name)

    def clear(self):
        for name in ('frame events', 'sound references', 'effect references'):
            self._root_block(name).clear()
        self.tag_has_changes = True

    @staticmethod
    def _enum_label(value):
        return value.partition('{')[0].strip()

    def _enum(self, element, name):
        value = self.value(element, name)
        if not isinstance(value, str):
            raise ValueError(f'{self.path}: unknown {name} enum value {value!r}')
        return self._enum_label(value)

    def _set_enum(self, element, name, value):
        field = self.required_field(element, name)
        key = canonical_frame_event if name == 'type' else self._enum_label
        matches = [i for i, label in enumerate(field.options().names)
                   if key(label) == key(value)]
        if len(matches) != 1:
            raise ValueError(f'{self.path}: unsupported {name}: {value!r}')
        field.set(matches[0])

    def _read_reference(self, element, kind):
        reference = Reference()
        path = self.reference(element, kind)
        reference.tag = path.RelativePathWithExtension if path else ''
        flags = self.required_field(element, 'flags')
        for attr, bit in self.reference_flags:
            setattr(reference, attr, flags.get_flag(bit))
        if self.corinth:
            path = self.reference(element, 'model')
            reference.model_tag = path.RelativePathWithExtension if path else ''
            reference.variant = self.value(element, 'variant')
        return reference

    def _reference_key(self, reference):
        values = [reference.tag.replace('/', '\\').lower()]
        values.extend(getattr(reference, attr) for attr, _ in self.reference_flags)
        if self.corinth:
            values.extend((reference.model_tag.replace('/', '\\').lower(), reference.variant))
        return tuple(values)

    def _write_references(self, kind, references):
        block = self._root_block(kind + ' references')
        existing = [self._reference_key(self._read_reference(e, kind)) for e in block]
        for reference in sorted(references.values(), key=self._reference_key):
            key = self._reference_key(reference)
            if key in existing:
                reference.index = existing.index(key)
                continue
            reference.index = block.add()
            element = block[reference.index]
            self.set_reference(element, kind, reference.tag or None)
            flags = self.required_field(element, 'flags')
            for attr, bit in self.reference_flags:
                flags.set_flag(bit, getattr(reference, attr))
            if self.corinth:
                self.set_reference(element, 'model', reference.model_tag or None)
                self.required_field(element, 'variant').set(reference.variant)
            existing.append(key)

    def from_blender(self, animations: list, blender_animations=None):
        # Child blends only own a subset of the graph. Keep other animations and
        # their reference indices intact when updating this blend's events.
        if blender_animations is None:
            blender_animations = {a.name.replace(":", " "): a for a in self.scene_nwo.animations if a.export_this}
        
        unique_sounds_set = set()
        unique_effects_set = set()

        for b_animation in blender_animations.values():
            if getattr(b_animation, "external", False):
                
                to_remove = []
                for i, e in enumerate(b_animation.animation_events):
                    if e.event_type == FRAME_EVENT_TYPE:
                        to_remove.append(i)
                        
                for i in reversed(to_remove):
                    b_animation.animation_events.remove(i)
                
                gr2_path = utils.relative_path(b_animation.gr2_path)
                json_path = Path(utils.get_data_path(), gr2_path).with_suffix(".json")
                if json_path.exists():
                    import_frame_animation_events(b_animation.animation_events, json_path)
                
            for event in b_animation.animation_events:
                for data in event.event_data:
                    match data.data_type:
                        case 'SOUND':
                            if data.event_sound_tag.strip():
                                unique_sounds_set.add((data.event_sound_tag, data.flag_allow_on_player, data.flag_left_arm_only, data.flag_right_arm_only, data.flag_first_person_only, data.flag_third_person_only, data.flag_forward_only, data.flag_reverse_only, data.flag_fp_no_aged_weapons, data.event_model, data.variant))
                        case 'EFFECT':
                            if data.event_effect_tag.strip():
                                unique_effects_set.add((data.event_effect_tag, data.flag_allow_on_player, data.flag_left_arm_only, data.flag_right_arm_only, data.flag_first_person_only, data.flag_third_person_only, data.flag_forward_only, data.flag_reverse_only, data.flag_fp_no_aged_weapons, data.event_model, data.variant))
            
        unique_sounds = {}
        unique_effects = {}
        
        for u in unique_sounds_set:
            sound = Reference()
            sound.tag = u[0]
            sound.allow_on_player = u[1]
            sound.left_arm_only = u[2]
            sound.right_arm_only = u[3]
            sound.first_person_only = u[4]
            sound.third_person_only = u[5]
            sound.forward_only = u[6]
            sound.reverse_only = u[7]
            sound.fp_no_aged_weapons = u[8]
            sound.model_tag = u[9]
            sound.variant = u[10]
            unique_sounds[u] = sound
            
        for u in unique_effects_set:
            effect = Reference()
            effect.tag = u[0]
            effect.allow_on_player = u[1]
            effect.left_arm_only = u[2]
            effect.right_arm_only = u[3]
            effect.first_person_only = u[4]
            effect.third_person_only = u[5]
            effect.forward_only = u[6]
            effect.reverse_only = u[7]
            effect.fp_no_aged_weapons = u[8]
            effect.model_tag = u[9]
            effect.variant = u[10]
            unique_effects[u] = effect
            

        owned = []
        for animation in animations:
            blender_animation = blender_animations.get(animation.name.data_name)
            if blender_animation is None:
                blender_animation = blender_animations.get(animation.name.tag_name)
            if blender_animation is not None:
                owned.append((animation, blender_animation))
        owned_names = {animation.name.tag_name for animation, _ in owned}
        rows = self._root_block('frame events')
        existing = {}
        # Refuse unrepresented script events before changing any tag data.
        for index, row in enumerate(rows):
            name = self.value(row, 'animation name')
            if name not in owned_names:
                continue
            if name in existing:
                raise ValueError(f'{self.path}: duplicate animation row {name!r}')
            self._check_scripts(row)
            existing[name] = index
        self._write_references('sound', unique_sounds)
        self._write_references('effect', unique_effects)
        for animation, blender_animation in owned:
            index = existing.get(animation.name.tag_name)
            if index is None:
                index = rows.add()
                existing[animation.name.tag_name] = index
            row = rows[index]
            self.required_field(row, 'animation name').set(animation.name.tag_name)
            self.required_field(row, 'animation frame count').set(animation.frame_count)
            for name in ('animation events', 'sound events', 'effect events', 'dialogue events'):
                self.block(row, name).clear()
            for blender_event in blender_animation.animation_events:
                if blender_event.event_type != FRAME_EVENT_TYPE:
                    continue
                event = AnimationEvent()
                event.from_blender(blender_animation, blender_event, unique_sounds, unique_effects)
                event_index = -1
                if event.type != 'none':
                    block = self.block(row, 'animation events')
                    end = event.end_frame if blender_event.multi_frame == 'range' else event.frame
                    if end < event.frame:
                        raise ValueError(f'{self.path}: event range ends before it starts')
                    for frame in range(event.frame, end + 1):
                        index = block.add()
                        if event_index == -1:
                            event_index = index
                        element = block[index]
                        for name, value in (('event name', event.name), ('animation name', animation.name.tag_name),
                                            ('frame', frame), ('frame offset', 0), ('unique ID', event.unique_id)):
                            self.required_field(element, name).set(value)
                        self._set_enum(element, 'type', event.type)
                for kind, records in (('sound', event.sound_events), ('effect', event.effect_events),
                                      ('dialogue', event.dialogue_events)):
                    for record in records:
                        block = self.block(row, kind + ' events')
                        element = block[block.add()]
                        self.required_field(element, 'frame event').set(event_index)
                        offset = record.frame_offset + (event.frame if event_index == -1 else 0)
                        self.required_field(element, 'frame offset').set(offset)
                        if kind == 'dialogue':
                            self._set_enum(element, 'dialogue event', record.dialogue_type)
                        else:
                            reference = getattr(record, kind + '_reference')
                            self.required_field(element, kind).set(reference.index)
                            self.required_field(element, 'marker name').set(record.marker_name)
                            if kind == 'effect':
                                self._set_enum(element, 'damage effect reporting type', record.damage_effect_reporting_type)
        self.tag_has_changes = True

    def _check_scripts(self, row):
        scripts = row.field('script events')
        if scripts is not None and len(scripts.as_block()):
            name = self.value(row, 'animation name')
            raise NotImplementedError(f'{self.path}: script events for {name!r} have no Blender mapping')

    def collect_events(self, animation_names: set[str] | None = None):
        references = {kind: [self._read_reference(e, kind) for e in self._root_block(kind + ' references')]
                      for kind in ('sound', 'effect')}
        result = {}
        for row in self._root_block('frame events'):
            name = self.value(row, 'animation name')
            if animation_names is None:
                animation = self.scene_nwo.animations.get(name.replace(':', ' '))
                if animation is None:
                    animation = self.scene_nwo.animations.get(name)
                if animation is None:
                    continue
            elif name not in animation_names and name.replace(':', ' ') not in animation_names:
                continue
            self._check_scripts(row)
            events = []
            for element in self.block(row, 'animation events'):
                event = AnimationEvent()
                event.frame = utils.blender_frame(self.value(element, 'frame') + self.value(element, 'frame offset'))
                event.end_frame = event.frame
                event.name = self.value(element, 'event name')
                identifier = self.value(element, 'unique ID')
                if identifier:
                    event.unique_id = identifier
                event.type = canonical_frame_event(self._enum(element, 'type'))
                if event.type in {'jetpack closed', 'jetpack open', 'sound event', 'effect event'}:
                    event.type = 'none'
                events.append(event)
            event_count = len(events)
            unbound = None
            for kind, cls in (('sound', SoundEvent), ('effect', EffectEvent), ('dialogue', DialogueEvent)):
                for element in self.block(row, kind + ' events'):
                    record = cls()
                    record.animation_event_index = self.value(element, 'frame event')
                    record.frame_offset = self.value(element, 'frame offset')
                    if kind == 'dialogue':
                        record.dialogue_type = self._enum(element, 'dialogue event')
                    else:
                        reference_index = self.value(element, kind)
                        if reference_index == -1:
                            continue
                        if not 0 <= reference_index < len(references[kind]):
                            raise ValueError(f'{self.path}: invalid {kind} reference index {reference_index}')
                        setattr(record, kind + '_reference', references[kind][reference_index])
                        record.marker_name = self.value(element, 'marker name')
                        if kind == 'effect':
                            record.damage_effect_reporting_type = self._enum(element, 'damage effect reporting type')
                    index = record.animation_event_index
                    if index == -1:
                        if unbound is None:
                            unbound = AnimationEvent()
                            events.append(unbound)
                        target = unbound
                    elif 0 <= index < event_count:
                        target = events[index]
                    else:
                        raise ValueError(f'{self.path}: invalid frame event index {index}')
                    getattr(target, kind + '_events').append(record)
            result[name] = collapse_events(events)
        return result

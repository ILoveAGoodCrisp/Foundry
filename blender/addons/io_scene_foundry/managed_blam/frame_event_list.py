

from collections import defaultdict
from pathlib import Path
import random
from typing import cast
import bpy

from .Tags import TagFieldBlockElement, TagPath

from .render_model import RenderModelTag
from . import Tag, tag_path_from_string
from .. import utils

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
        
    def from_element(self, element: TagFieldBlockElement, corinth: bool):
        tag_path = element.Fields[0].Path
        if tag_path is not None:
            self.tag = tag_path.RelativePathWithExtension
        
        flags = element.SelectField("WordFlags:flags")
        self.allow_on_player = flags.TestBit("allow on player")
        self.left_arm_only = flags.TestBit("left arm only")
        self.right_arm_only = flags.TestBit("right arm only")
        self.first_person_only = flags.TestBit("first-person only")
        self.third_person_only = flags.TestBit("third-person only")
        self.forward_only = flags.TestBit("forward only")
        self.reverse_only = flags.TestBit("reverse only")
        self.fp_no_aged_weapons = flags.TestBit("fp no aged weapons")
        
        if corinth:
            model_path = element.SelectField("Reference:model").Path
            if model_path is not None:
                self.model_tag = model_path.RelativePathWithExtension
            self.variant = element.SelectField("StringId:variant").GetStringData()
    
    def to_element(self, element: TagFieldBlockElement, corinth: bool):
        element.Fields[0].Path = tag_path_from_string(self.tag) if self.tag else None
        flags = element.Fields[1]
        flags.SetBit("allow on player", self.allow_on_player)
        flags.SetBit("left arm only", self.left_arm_only)
        flags.SetBit("right arm only", self.right_arm_only)
        flags.SetBit("first-person only", self.first_person_only)
        flags.SetBit("third-person only", self.third_person_only)
        flags.SetBit("forward only", self.forward_only)
        flags.SetBit("reverse only", self.reverse_only)
        flags.SetBit("fp no aged weapons", self.fp_no_aged_weapons)
        if corinth:
            element.Fields[3].Path = tag_path_from_string(self.model_tag) if self.model_tag else None
            element.Fields[4].SetStringData(self.variant)
    
class SoundEvent:
    def __init__(self):
        self.animation_event_index = -1
        self.frame_offset = 0
        self.sound_reference: Reference = None
        self.marker_name = ""
    
    def from_element(self, element: TagFieldBlockElement, sounds: list[Reference], graph=False):
        if not graph:
            self.animation_event_index = element.SelectField("ShortBlockIndex:frame event").Value
            self.frame_offset = element.SelectField("ShortInteger:frame offset").Data
        else:
            self.frame_offset = element.SelectField("ShortInteger:frame").Data
        self.marker_name = element.SelectField("StringId:marker name").GetStringData()
        sound_index = element.SelectField("ShortBlockIndex:sound").Value
        if sound_index > -1 and sound_index < len(sounds):
            self.sound_reference = sounds[sound_index]
    
    def to_element(self, element: TagFieldBlockElement):
        pass
    
    def __hash__(self):
        return hash((self.frame_offset, self.sound_reference.__dict__.values(), self.marker_name))
    
class EffectEvent:
    def __init__(self):
        self.animation_event_index = -1
        self.frame_offset = 0
        self.effect_reference: Reference = None
        self.marker_name = ""
        self.damage_effect_reporting_type = "unknown"
    
    def from_element(self, element: TagFieldBlockElement, effects: list[Reference], graph=False):
        if not graph:
            self.animation_event_index = element.SelectField("ShortBlockIndex:frame event").Value
            self.frame_offset = element.SelectField("ShortInteger:frame offset").Data
        else:
            self.frame_offset = element.SelectField("ShortInteger:frame").Data
        self.marker_name = element.SelectField("StringId:marker name").GetStringData()
        effect_index = element.SelectField("ShortBlockIndex:effect").Value
        if effect_index > -1 and effect_index < len(effects):
            self.effect_reference = effects[effect_index]
            
        damage_items = element.SelectField("CharEnum:damage effect reporting type").Items
        self.damage_effect_reporting_type = damage_items[element.SelectField("CharEnum:damage effect reporting type").Value].DisplayName
    
    def to_element(self, element: TagFieldBlockElement):
        pass
    
    def __hash__(self):
        return hash((self.frame_offset, self.effect_reference.__dict__.values(), self.marker_name, self.damage_effect_reporting_type))
    
class DialogueEvent:
    def __init__(self):
        self.animation_event_index = -1
        self.frame_offset = 0
        self.dialogue_type = "bump"
    
    def from_element(self, element: TagFieldBlockElement, graph=False):
        if not graph:
            self.animation_event_index = element.SelectField("ShortBlockIndex:frame event").Value
            self.frame_offset = element.SelectField("ShortInteger:frame offset").Data
        else:
            self.frame_offset = element.SelectField("ShortInteger:frame").Data
        dialogue_items = element.SelectField("ShortEnum:dialogue event").Items
        self.dialogue_type = dialogue_items[element.SelectField("ShortEnum:dialogue event").Value].DisplayName
        
    def to_element(self, element: TagFieldBlockElement):
        pass
    
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
        
    def from_element(self, element: TagFieldBlockElement, graph=False):
        if graph:
            self.frame = element.SelectField("ShortInteger:frame").Data
        else:
            self.frame = element.SelectField("ShortInteger:frame").Data + element.SelectField("ShortInteger:frame offset").Data
            self.name = element.SelectField("StringId:event name").GetStringData()
            id = element.SelectField("LongInteger:unique ID").Data
            if id != 0:
                self.unique_id = id
            
        self.end_frame = self.frame
        type_items = element.SelectField("ShortEnum:type").Items
        self.type = type_items[element.SelectField("ShortEnum:type").Value].DisplayName
        if self.type in {'jetpack closed', 'jetpack open', 'sound event', 'effect event'}:
            self.type = 'none'
            
    
    def to_element(self, element: TagFieldBlockElement):
        pass
    
    def from_blender(self, blender_animation, blender_animation_event, unique_sounds: dict, unique_effects: dict):
        self.frame = blender_animation_event.frame_frame - blender_animation.frame_start
        self.type = blender_animation_event.frame_name
        self.name = blender_animation_event.frame_name.replace(" ", "_")
        self.unique_id = blender_animation_event.event_id
        if blender_animation_event.multi_frame == 'range':
            self.end_frame = blender_animation_event.frame_range - blender_animation.frame_start
        
        for data in blender_animation_event.event_data:
            match data.data_type:
                case 'SOUND':
                    sound = SoundEvent()
                    sound.frame_offset = data.frame_offset
                    if data.marker is not None:
                        sound.marker_name = data.marker.nwo.marker_model_group
                    sound.sound_reference = unique_sounds.get((data.event_sound_tag, data.flag_allow_on_player, data.flag_left_arm_only, data.flag_right_arm_only, data.flag_first_person_only, data.flag_third_person_only, data.flag_forward_only, data.flag_reverse_only, data.flag_fp_no_aged_weapons, data.event_model, data.variant))
                    if sound.sound_reference is not None:
                        self.sound_events.append(sound)
                case 'EFFECT':
                    effect = EffectEvent()
                    effect.frame_offset = data.frame_offset
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
        
        
        

class FrameEventListTag(Tag):
    tag_ext = 'frame_event_list'

    def _read_fields(self):
        self.block_sound_references = self.tag.SelectField("Block:sound references")
        self.block_effect_references = self.tag.SelectField("Block:effect references")
        self.block_frame_events = self.tag.SelectField("Block:frame events")
        
    def clear(self):
        self.block_frame_events.RemoveAllElements()
        self.block_sound_references.RemoveAllElements()
        self.block_effect_references.RemoveAllElements()
            
    def from_blender(self, animations: list):
        self.block_sound_references.RemoveAllElements()
        self.block_effect_references.RemoveAllElements()
        self.block_frame_events.RemoveAllElements()
        
        blender_animations = {a.name.replace(":", " "): a for a in self.context.scene.nwo.animations if a.export_this}
        
        unique_sounds_set = set()
        unique_effects_set = set()
        
        for b_animation in blender_animations.values():
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
            
        for idx, sound in enumerate(sorted(unique_sounds.values(), key=lambda x: Path(x.tag).with_suffix("").name)):
            sound.index = idx
            sound.to_element(self.block_sound_references.AddElement(), self.corinth)
            
        for idx, effect in enumerate(sorted(unique_effects.values(), key=lambda x: Path(x.tag).with_suffix("").name)):
            effect.index = idx
            effect.to_element(self.block_effect_references.AddElement(), self.corinth)
        
        for animation in animations:
            frame_event = self.block_frame_events.AddElement()
            frame_event.Fields[0].SetStringData(animation.name)
            name_with_spaces = animation.name.replace(":", " ")
            blender_animation = blender_animations.get(name_with_spaces)
            if blender_animation is None:
                blender_animation = blender_animations.get(animation.name)
                if not blender_animation:
                    # utils.print_warning(f"--- Animation Graph contains animation {name_with_spaces} but Blender does not (or it is not set to export)")
                    continue
                
            if not blender_animation.animation_events:
                continue
            
            frame_event.Fields[1].Data = animation.frame_count

            for blender_event in blender_animation.animation_events:
                animation_event = AnimationEvent()
                animation_event.from_blender(blender_animation, blender_event, unique_sounds, unique_effects)
                
                data_only_event = animation_event.type == "none"
                
                if not data_only_event:
                    event = frame_event.Fields[2].AddElement()
                    event.Fields[0].SetStringData(animation_event.name)
                    event.Fields[1].SetStringData(animation.name)
                    event.Fields[2].Data = animation_event.frame
                    for idx, item in enumerate(event.Fields[4].Items):
                        if item.DisplayName == animation_event.type:
                            event.Fields[4].Value = idx
                            break
                        
                    event.Fields[5].Data = animation_event.unique_id
                            
                for sound in animation_event.sound_events:
                    sound_event = frame_event.Fields[3].AddElement()
                    if not data_only_event:
                        sound_event.Fields[0].Value = event.ElementIndex
                        sound_event.Fields[2].Data = sound.frame_offset
                    else:
                        sound_event.Fields[2].Data = sound.frame_offset + animation_event.frame
                        
                    sound_event.Fields[1].Value = sound.sound_reference.index
                    sound_event.Fields[4].SetStringData(sound.marker_name)
                    
                for effect in animation_event.effect_events:
                    effect_event = frame_event.Fields[4].AddElement()
                    if not data_only_event:
                        effect_event.Fields[0].Value = event.ElementIndex
                        effect_event.Fields[2].Data = effect.frame_offset
                    else:
                        effect_event.Fields[2].Data = effect.frame_offset + animation_event.frame
                        
                    effect_event.Fields[1].Value = effect.effect_reference.index
                    effect_event.Fields[4].SetStringData(effect.marker_name)
                    for idx, item in enumerate(effect_event.Fields[5].Items):
                        if item.DisplayName == effect.damage_effect_reporting_type:
                            effect_event.Fields[5].Value = idx
                            break
                        
                for dialogue in animation_event.dialogue_events:
                    dialogue_event = frame_event.Fields[5].AddElement()
                    if not data_only_event:
                        dialogue_event.Fields[0].Value = event.ElementIndex
                        dialogue_event.Fields[2].Data = dialogue.frame_offset
                    else:
                        dialogue_event.Fields[2].Data = dialogue.frame_offset + animation_event.frame
                        
                    for idx, item in enumerate(dialogue_event.Fields[1].Items):
                        if item.DisplayName == dialogue.dialogue_type:
                            dialogue_event.Fields[1].Value = idx
                            break

        self.tag_has_changes = True
            
    def collect_events(self):
        
        unique_sounds = []
        for element in self.block_sound_references.Elements:
            ref = Reference()
            ref.from_element(element, self.corinth)
            unique_sounds.append(ref)
            
        unique_effects = []
        for element in self.block_effect_references.Elements:
            ref = Reference()
            ref.from_element(element, self.corinth)
            unique_effects.append(ref)
        
        blender_animations = self.context.scene.nwo.animations
        
        animation_name_events = {}
        
        for frame_event in self.block_frame_events.Elements:
            name = frame_event.SelectField("StringId:animation name").GetStringData()
            name_with_spaces = name.replace(":", " ")
            blender_animation = blender_animations.get(name_with_spaces)
            if blender_animation is None:
                blender_animation = blender_animations.get(name)
                if not blender_animation:
                    # utils.print_warning(f"--- Frame Events List contains animation {name_with_spaces} but Blender does not")
                    continue
                
            print(f"--- Getting events for {blender_animation.name}")
            
            animation_events: list[AnimationEvent] = []
            
            for element in frame_event.SelectField("Block:animation events").Elements:
                event = AnimationEvent()
                event.from_element(element)
                animation_events.append(event)
                
            none_event = None
            
            def make_none_event():
                none_event = AnimationEvent()
                animation_events.append(none_event)
                return none_event
            
            for element in frame_event.SelectField("Block:sound events").Elements:
                if element.SelectField("ShortBlockIndex:sound").Value > -1:
                    sound_event = SoundEvent()
                    sound_event.from_element(element, unique_sounds)
                    
                    if sound_event.sound_reference is None:
                        continue
                    
                    if sound_event.animation_event_index > -1 and sound_event.animation_event_index < len(animation_events):
                        animation_events[sound_event.animation_event_index].sound_events.append(sound_event)
                    elif none_event is not None:
                        none_event.sound_events.append(sound_event)
                    else:
                        none_event = make_none_event()
                        none_event.sound_events.append(sound_event)
                    
            for element in frame_event.SelectField("Block:effect events").Elements:
                if element.SelectField("ShortBlockIndex:effect").Value > -1:
                    effect_event = EffectEvent()
                    effect_event.from_element(element, unique_effects)
                    
                    if effect_event.effect_reference is None:
                        continue
                    
                    if effect_event.animation_event_index > -1 and effect_event.animation_event_index < len(animation_events):
                        animation_events[effect_event.animation_event_index].effect_events.append(effect_event)
                    elif none_event is not None:
                        none_event.effect_events.append(effect_event)
                    else:
                        none_event = make_none_event()
                        none_event.effect_events.append(effect_event)
                        
            for element in frame_event.SelectField("Block:dialogue events").Elements:
                dialogue_event = DialogueEvent()
                dialogue_event.from_element(element)
                if dialogue_event.animation_event_index > -1 and dialogue_event.animation_event_index < len(animation_events):
                    animation_events[dialogue_event.animation_event_index].dialogue_events.append(dialogue_event)
                elif none_event is not None:
                    none_event.dialogue_events.append(dialogue_event)
                else:
                    none_event = make_none_event()
                    none_event.dialogue_events.append(dialogue_event)
                    
            # See if we can make any ranged frame events
            def collapse_events(aes):
                aes.sort(key=lambda x: x.frame, reverse=True)
                result = []
                group_end_frame = aes[0].frame
                
                for curr, next in zip(aes, aes[1:] + [None]):
                    if next:
                        if next.frame == curr.frame - 1 and curr.type == next.type and not (curr.sound_events or curr.effect_events or curr.dialogue_events):
                            continue

                    # Finalize current group
                    curr.end_frame = group_end_frame
                    group_end_frame = next.frame if next else 0
                    result.append(curr)
                        
                return result

            if len(animation_events) > 1:
                animation_events = collapse_events(animation_events)
            
            animation_name_events[name] = animation_events
            
        return animation_name_events
                    


from collections import defaultdict
from pathlib import Path
from typing import cast
import bpy

from .Tags import TagFieldBlockElement, TagPath

from .render_model import RenderModelTag
from . import Tag
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
            self.variant = element.SelectField("StringId:variant")
    
    def to_element(self, element: TagFieldBlockElement):
        pass
    
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
        if sound_index > -1:
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
        if effect_index > -1:
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
        
    def from_element(self, element: TagFieldBlockElement, graph=False):
        if graph:
            self.frame = element.SelectField("ShortInteger:frame").Data
        else:
            self.frame = element.SelectField("ShortInteger:frame").Data + element.SelectField("ShortInteger:frame offset").Data
            self.name = element.SelectField("StringId:event name").GetStringData()
            
        self.end_frame = self.frame
        type_items = element.SelectField("ShortEnum:type").Items
        self.type = type_items[element.SelectField("ShortEnum:type").Value].DisplayName
    
    def to_element(self, element: TagFieldBlockElement):
        pass
    
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
        
        return True
        
        
        

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
            
    def from_blender(self):
        sorted_animations = sorted(list(self.context.scene.nwo.animations), key=lambda a: a.name)
        
        for animation in sorted_animations:
            if not animation.animation_events:
                continue
            frame_event = self.block_frame_events.AddElement()
            frame_event.SelectField("StringId:animation name").SetStringData(animation.name)
            frame_event.SelectField("LongInteger:animation frame count").Data = animation.frame_end - animation.frame_start + 1
            
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
                    utils.print_warning(f"--- Frame Events List contains animation {name_with_spaces} but Blender does not")
                    continue
                
            print(f"--- Getting events for {blender_animation.name}")
            
            animation_events: list[AnimationEvent] = []
            
            for element in frame_event.SelectField("Block:animation events").Elements:
                event = AnimationEvent()
                event.from_element(element)
                animation_events.append(event)
                
            # See if we can make any ranged frame events
            def collapse_events(aes):
                aes.sort(key=lambda x: x.frame, reverse=True)
                result = []
                group_end_frame = aes[0].frame
                
                for curr, next in zip(aes, aes[1:] + [None]):
                    if next:
                        if next.frame == curr.frame - 1 and curr.type == next.type:
                            continue

                    # Finalize current group
                    curr.end_frame = group_end_frame
                    group_end_frame = next.frame if next else 0
                    result.append(curr)
                        
                return result

            if len(animation_events) > 1:
                animation_events = collapse_events(animation_events)
                
            if name == "panic:unarmed:move_front":
                utils.print_error("WAHHH")
                print(len(animation_events))
            
            for element in frame_event.SelectField("Block:sound events").Elements:
                if element.SelectField("ShortBlockIndex:sound").Value > -1:
                    sound_event = SoundEvent()
                    sound_event.from_element(element, unique_sounds)
                    if sound_event.animation_event_index > -1:
                        animation_events[sound_event.animation_event_index].sound_events.append(sound_event)
                    elif animation_events:
                        closest_animation_event = min(animation_events, key=lambda ae: abs(ae.frame - sound_event.frame_offset))
                        sound_event.frame_offset = sound_event.frame_offset - closest_animation_event.frame
                        closest_animation_event.sound_events.append(sound_event)
                    else:
                        animation_event_sound = AnimationEvent()
                        animation_event_sound.frame = sound_event.frame_offset
                        sound_event.frame_offset = 0
                        animation_event_sound.sound_events.append(sound_event)
                        animation_events.append(animation_event_sound)
                    
            for element in frame_event.SelectField("Block:effect events").Elements:
                if element.SelectField("ShortBlockIndex:effect").Value > -1:
                    effect_event = EffectEvent()
                    effect_event.from_element(element, unique_effects)
                    if effect_event.animation_event_index > -1:
                        animation_events[effect_event.animation_event_index].effect_events.append(effect_event)
                    elif animation_events:
                        closest_animation_event = min(animation_events, key=lambda ae: abs(ae.frame - effect_event.frame_offset))
                        effect_event.frame_offset = effect_event.frame_offset - closest_animation_event.frame
                        closest_animation_event.effect_events.append(effect_event)
                    else:
                        animation_event_effect = AnimationEvent()
                        animation_event_effect.frame = effect_event.frame_offset
                        effect_event.frame_offset = 0
                        animation_event_effect.effect_events.append(effect_event)
                        animation_events.append(animation_event_effect)
                        
            for element in frame_event.SelectField("Block:dialogue events").Elements:
                dialogue_event = DialogueEvent()
                dialogue_event.from_element(element)
                if dialogue_event.animation_event_index > -1:
                    animation_events[dialogue_event.animation_event_index].dialogue_events.append(dialogue_event)
                elif animation_events:
                    closest_animation_event = min(animation_events, key=lambda ae: abs(ae.frame - dialogue_event.frame_offset))
                    dialogue_event.frame_offset = dialogue_event.frame_offset - closest_animation_event.frame
                    closest_animation_event.dialogue_events.append(dialogue_event)
                else:
                    animation_event_dialogue = AnimationEvent()
                    animation_event_dialogue.frame = dialogue_event.frame_offset
                    dialogue_event.frame_offset = 0
                    animation_event_dialogue.dialogue_events.append(dialogue_event)
                    animation_events.append(animation_event_dialogue)
            
            animation_name_events[name] = animation_events
            
        return animation_name_events
                    
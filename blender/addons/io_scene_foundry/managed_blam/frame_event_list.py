

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
    
    def from_element(self, element: TagFieldBlockElement, sounds: list[Reference]):
        self.animation_event_index = element.SelectField("ShortBlockIndex:frame event").Value
        self.frame_offset = element.SelectField("ShortInteger:frame offset").Data
        self.marker_name = element.SelectField("StringId:marker name").GetStringData()
        sound_index = element.SelectField("ShortBlockIndex:sound").Value
        if sound_index > -1:
            self.sound_reference = sounds[sound_index]
    
    def to_element(self, element: TagFieldBlockElement):
        pass
    
class EffectEvent:
    def __init__(self):
        self.animation_event_index = -1
        self.frame_offset = 0
        self.effect_reference: Reference = None
        self.marker_name = ""
        self.damage_effect_reporting_type = "unknown"
    
    def from_element(self, element: TagFieldBlockElement, effects: list[Reference]):
        self.animation_event_index = element.SelectField("ShortBlockIndex:frame event").Value
        self.frame_offset = element.SelectField("ShortInteger:frame offset").Data
        self.marker_name = element.SelectField("StringId:marker name").GetStringData()
        effect_index = element.SelectField("ShortBlockIndex:effect").Value
        if effect_index > -1:
            self.effect_reference = effects[effect_index]
            
        damage_items = element.SelectField("CharEnum:damage effect reporting type").Items
        self.damage_effect_reporting_type = damage_items[element.SelectField("CharEnum:damage effect reporting type").Value].DisplayName
    
    def to_element(self, element: TagFieldBlockElement):
        pass
    
class DialogueEvent:
    def __init__(self):
        self.animation_event_index = -1
        self.frame_offset = 0
        self.dialogue_type = "bump"
    
    def from_element(self, element: TagFieldBlockElement):
        self.animation_event_index = element.SelectField("ShortBlockIndex:frame event").Value
        self.frame_offset = element.SelectField("ShortInteger:frame offset").Data
        dialogue_items = element.SelectField("ShortEnum:dialogue event").Items
        self.dialogue_type = dialogue_items[element.SelectField("ShortEnum:dialogue event").Value].DisplayName
        
    
    def to_element(self, element: TagFieldBlockElement):
        pass
    
class AnimationEvent:
    def __init__(self):
        self.sound_events: list[SoundEvent] = []
        self.effect_events: list[EffectEvent] = []
        self.dialogue_events: list[DialogueEvent] = []
        
        self.frame = 0
        self.type = "none"
        self.name = ""
        self.end_frame = 0
        
    def from_element(self, element: TagFieldBlockElement):
        self.frame = element.SelectField("ShortInteger:frame").Data + element.SelectField("ShortInteger:frame offset").Data
        self.end_frame = self.frame
        self.name = element.SelectField("StringId:event name").GetStringData()
        type_items = element.SelectField("ShortEnum:type").Items
        self.type = type_items[element.SelectField("ShortEnum:type").Value].DisplayName
    
    def to_element(self, element: TagFieldBlockElement):
        pass

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
            
    def to_blender(self):
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
        blender_markers = {ob.nwo.marker_model_group: ob for ob in bpy.data.objects if ob.type == 'EMPTY'}
        
        event_count = 0
        
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
                    group_end_frame = curr.frame
                    result.append(curr)
                        
                return result

            if len(animation_events) > 1:
                animation_events = collapse_events(animation_events)
            
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
            
            # Apply to blender
            def apply_flags(blender_data_event, reference: Reference):
                blender_data_event.flag_allow_on_player = reference.allow_on_player
                blender_data_event.flag_left_arm_only = reference.left_arm_only
                blender_data_event.flag_right_arm_only = reference.right_arm_only
                blender_data_event.flag_first_person_only = reference.first_person_only
                blender_data_event.flag_third_person_only = reference.third_person_only
                blender_data_event.flag_forward_only = reference.forward_only
                blender_data_event.flag_reverse_only = reference.reverse_only
                blender_data_event.flag_fp_no_aged_weapons = reference.fp_no_aged_weapons
            
            blender_animation.animation_events.clear()     
            for event in sorted(animation_events, key=lambda x: x.frame):
                blender_event = blender_animation.animation_events.add()
                blender_event.name = event.name
                blender_event.frame_frame = event.frame
                if event.end_frame > event.frame:
                    blender_event.multi_frame = 'range'
                    blender_event.frame_range = event.end_frame
                blender_event.frame_name = event.type
                
                data_events = event.sound_events + event.effect_events + event.dialogue_events
                data_events.sort(key=lambda x: x.frame_offset)
                
                for data_event in data_events:
                    blender_data_event = blender_event.event_data.add()
                    blender_data_event.frame_offset = data_event.frame_offset
                    if isinstance(data_event, SoundEvent):
                        blender_data_event.data_type = 'SOUND'
                        blender_data_event.frame_offset = data_event.frame_offset
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
                    
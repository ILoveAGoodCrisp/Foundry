

from collections import defaultdict
from pathlib import Path
from typing import cast
import bpy

from ..managed_blam.Tags import TagFieldElement, TagPath

from ..managed_blam.render_model import RenderModelTag
from ..managed_blam import Tag
from .. import utils

class Reference:
    def __init__(self):
        self.tag: TagPath = None
        self.flag_allow_on_player = False
        self.left_arm_only = False
        self.right_arm_only = False
        self.first_person_only = False
        self.third_person_only = False
        self.forward_only = False
        self.reverse_only = False
        self.fp_no_aged_weapons = False
        
        self.model_tag: TagPath = None
        self.variant = ""
        
    def from_element(self, element: TagFieldElement):
        pass
    
    def to_element(self, element: TagFieldElement):
        pass
        
class AnimationEvent:
    def __init__(self):
        self.sound_events = []
        self.effect_events = []
        self.dialogue_events = []
        
        self.frame = 0
        self.type = ""
        
    def from_element(self, element: TagFieldElement):
        pass
    
    def to_element(self, element: TagFieldElement):
        pass
    
class SoundEvent:
    def __init__(self):
        pass
    
    def from_element(self, element: TagFieldElement):
        pass
    
    def to_element(self, element: TagFieldElement):
        pass
    
class EffectEvent:
    def __init__(self):
        pass
    
    def from_element(self, element: TagFieldElement):
        pass
    
    def to_element(self, element: TagFieldElement):
        pass

class FrameEventsListTag(Tag):
    tag_ext = 'frame_events_list'

    def _read_fields(self):
        self.block_sound_references = self.tag.SelectField("Block:sound references")
        self.block_effect_references = self.tag.SelectField("Block:effect references")
        self.block_frame_events = self.tag.SelectField("Block:frame events")
        
    def clear(self):
        self.block_frame_events.RemoveAllElements()
        self.block_sound_references.RemoveAllElements()
        self.block_effect_references.RemoveAllElements()\
            
    def from_blender(self):
        sorted_animations = sorted(list(self.context.scene.nwo.animations), key=lambda a: a.name)
        
        for animation in sorted_animations:
            if not animation.animation_events:
                continue
            frame_event = self.block_frame_events.AddElement()
            frame_event.SelectField("StringId:animation name").SetStringData(animation.name)
            frame_event.SelectField("LongInteger:animation frame count").Data = animation.frame_end - animation.frame_start + 1
            
    def to_blender(self):
        unique_sounds = [Reference(element) for element in self.block_sound_references.Elements]
        unique_effects = [Reference(element) for element in self.block_effect_references.Elements]
        
        blender_animations = self.context.scene.nwo.animations
        
        for frame_event in self.block_frame_events.Elements:
            name = frame_event.SelectField("StringId:animation name").GetStringData()
            name_with_spaces = name.replace(":", " ")
            blender_animation = blender_animations.get(name_with_spaces)
            if blender_animation is None:
                blender_animation = blender_animations.get(name)
                if not blender_animation:
                    print(f"Frame Events List contains animation {name_with_spaces} but Blender does not")
                    continue
                
            animation_events = [AnimationEvent(element) for element in frame_event.SelectField("Block:animation events").Elements]
            
            standalone_sound_events = []
            
            for element in frame_event.SelectField("Block:sound events").Elements:
                if element.SelectField("ShortBlockIndex:sound").Value > -1:
                    sound_event = SoundEvent()
                    sound_event.from_element(element)
                    if sound_event.animation_event_index > -1:
                        animation_events.sound_events.append(sound_event)
                    else:
                        animation_event_sound = AnimationEvent()
                        animation_event_sound.frame = sound_event.frame_offset
                        sound_event.frame_offset = 0
                        animation_event_sound.sound_events.append(sound_event)
                    
            standalone_effect_events = []
                    
            for element in frame_event.SelectField("Block:effect events").Elements:
                if element.SelectField("ShortBlockIndex:effect").Value > -1:
                    effect_event = EffectEvent()
                    effect_event.from_element(element)
                    if effect_event.animation_event_index > -1:
                        animation_events.effect_events.append(effect_event)
                    else:
                        animation_event_effect = AnimationEvent()
                        animation_event_effect.frame = effect_event.frame_offset
                        effect_event.frame_offset = 0
                        animation_event_effect.effect_events.append(effect_event)
                    
            standalone_dialogue_events = []
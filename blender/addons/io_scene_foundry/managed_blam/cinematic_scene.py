from .. import utils
from ..props.scene import NWO_CinematicEvent
from . import Tag, tag_path_from_string
from .Tags import TagFieldBlock, TagFieldBlockElement, TagPath

def get_subject_name(subject_index: int, object_block: TagFieldBlock) -> str:
    if subject_index != -1 and object_block.Elements.Count > subject_index:
        return object_block.Elements[subject_index].Fields[0].GetStringData()
    else:
        return ""
    
def get_subject_index(subject_name: str, object_block: TagFieldBlock) -> int:
    for element in object_block.Elements:
        if element.Fields[0].GetStringData() == subject_name:
            return element.ElementIndex
    
    return -1

class CinematicLighting:
    def __init__(self):
        self.persists_across_shots = False
        self.lighting: TagPath = None
        self.subject = ""
        self.marker = ""
        
    def from_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock) -> bool:
        self.persists_across_shots = element.SelectField("flags").TestBit("persists across shots")
        self.lighting = element.SelectField("lighting").Path
        self.subject = get_subject_name(element.SelectField("subject").Value, object_block)
        self.marker = element.SelectField("marker").GetStringData()
        return bool(self.subject)
        
    def to_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock):
        element.SelectField("flags").SetBit("persists across shots", self.persists_across_shots)
        element.SelectField("lighting").Path = self.lighting
        element.SelectField("subject").Value = get_subject_index(self.subject, object_block)
        element.SelectField("marker").SetStringData(self.marker)
        
class CinematicClip:
    def __init__(self):
        self.plane_center = 0, 0, 0
        self.plane_direction = 0, 0, 0
        self.frame_start = 0
        self.frame_end = 0
        self.subject_objects: list[str] = []
        
    def from_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock) -> bool:
        self.plane_center = element.SelectField("plane center").Data
        self.plane_direction = element.SelectField("plane direction").Data
        self.frame_start = element.SelectField("frame start").Data
        self.frame_end = element.SelectField("frame end").Data
        for sub_element in element.SelectField("subject objects").Elements:
            subject = get_subject_name(sub_element.Fields[0].Value, object_block)
            if subject:
                self.subject_objects.append(subject)
                
        return bool(self.subject_objects)
    
    def to_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock):
        element.SelectField("plane center").Data = self.plane_center
        element.SelectField("plane direction").Data = self.plane_direction
        element.SelectField("frame start").Data = self.frame_start
        element.SelectField("frame end").Data = self.frame_end
        subject_block = element.SelectField("subject objects")
        for subject in self.subject_objects:
            subject_index = get_subject_index(subject, object_block)
            if subject_index != -1:
                subject_block.AddElement().Fields[0].Value = subject_index
        
class CinematicDialogue:
    def __init__(self):
        self.dialogue: TagPath = None
        self.female_dialogue: TagPath = None
        self.frame = 0
        self.scale = 1
        self.lipsync_actor = ""
        self.default_sound_effect = ""
        self.subtitle = ""
        self.female_subtitle = ""
        self.character = ""
    
    # Dialog is always sourced from Blender
    # def from_element(self, element: TagFieldBlockElement): 
    #     pass
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("dialogue").Path = self.dialogue
        element.SelectField("female dialogue").Path = self.female_dialogue
        element.SelectField("frame").Data = self.frame
        element.SelectField("scale").Data = self.scale
        element.SelectField("lipsync actor").SetStringData(self.lipsync_actor)
        element.SelectField("default sound effect").SetStringData(self.default_sound_effect)
        element.SelectField("subtitle").SetStringData(self.subtitle)
        element.SelectField("female subtitle").SetStringData(self.female_subtitle)
        element.SelectField("character").SetStringData(self.character)
        
    def from_event(self, event: NWO_CinematicEvent):
        if event.sound_tag.strip():
            self.dialogue = tag_path_from_string(event.sound_tag)
        if event.female_sound_tag.strip():
            self.female_dialogue = tag_path_from_string(event.female_sound_tag)
            if self.dialogue is None:
                self.dialogue = self.female_dialogue
        else:
            self.female_dialogue = self.dialogue
            
        self.scale = event.sound_scale
        self.lipsync_actor = "" if event.lipsync_actor is None else event.lipsync_actor.name
        self.default_sound_effect = event.default_sound_effect
        self.subtitle = event.subtitle
        self.female_subtitle = event.female_subtitle if event.female_subtitle.strip() else self.subtitle
        self.character = event.subtitle_character

class CinematicMusic:
    def __init__(self):
        self.stops_music_at_frame = False
        self.music: TagPath = None
        self.frame = 0
        
    def from_element(self, element: TagFieldBlockElement) -> bool:
        self.stops_music_at_frame = element.SelectField("flags").TestBit("Stop Music At Frame (rather than starting it)")
        self.music = element.SelectField(r"music\foley").Path
        self.frame = element.SelectField("frame").Data
        return self.music is not None
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("flags").SetBit("Stop Music At Frame (rather than starting it)", self.stops_music_at_frame)
        element.SelectField(r"music\foley").Path = self.music
        element.SelectField("frame").Data = self.frame
        
class CinematicEffect:
    def __init__(self):
        self.use_maya_value = False
        self.looping = False
        self.state = 0
        self.effect: TagPath = None
        self.size_scale = 1
        self.frame = 0
        self.marker_name = ""
        self.marker_parent = ""
        self.function_a = ""
        self.function_b = ""
        self.node_id = 0
        self.sequence_id = 0
        
    def from_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock, corinth: bool) -> bool:
        self.use_maya_value = element.SelectField("flags").TestBit("use maya value")
        self.effect = element.SelectField("effect").Path
        self.frame = element.SelectField("frame").Data
        self.marker_name = element.SelectField("marker name").GetStringData()
        self.marker_parent = get_subject_name(element.SelectField("marker parent").Value, object_block)
        self.node_id = element.SelectField("node id").Data
        self.sequence_id = element.SelectField("sequence id").Data
        if corinth:
            self.looping = element.SelectField("flags").TestBit("looping")
            self.state = element.SelectField("state").Value
            self.size_scale = element.SelectField("size scale").Value
            self.function_a = element.SelectField("function a").GetStringData()
            self.function_b = element.SelectField("function b").GetStringData()
            
        return self.effect is not None
        
    
    def to_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock, corinth: bool):
        element.SelectField("flags").SetBit("use maya value", self.use_maya_value)
        element.SelectField("effect").Path = self.effect
        element.SelectField("frame").Data = self.frame
        element.SelectField("marker name").SetStringData(self.marker_name)
        element.SelectField("marker parent").Value = get_subject_index(self.marker_parent, object_block)
        element.SelectField("node id").Data = self.node_id
        element.SelectField("sequence id").Data = self.sequence_id
        if corinth:
            element.SelectField("flags").SetBit("looping", self.looping) 
            element.SelectField("state").Value = self.state
            element.SelectField("size scale").Value = self.size_scale
            element.SelectField("function a").SetStringData(self.function_a)
            element.SelectField("function b").SetStringData(self.function_b)
            
    def from_event(self, event: NWO_CinematicEvent):
        self.use_maya_value = True
        if event.effect is not None:
            self.effect = tag_path_from_string(event.effect)
        
        ob = event.marker
        if ob is None or ob.type != 'EMPTY':
            self.marker_name = event.marker_name
        else:
            self.marker_name = event.marker.nwo.marker_model_group
            
        if ob is not None:
            actor = utils.ultimate_armature_parent(ob)
            if actor is not None:
                self.marker_parent = actor.name
                
        self.function_a = event.function_a
        self.function_b = event.function_b
        self.looping = event.looping
            
        
class CinematicObjectFunctionKeyframe:
    def __init__(self, ob: str, func: str):
        self.clear_function = False
        self.frame = 0
        self.value = 0
        self.interpolation_time = 0
        self.object = ob
        self.function_name = func
        
    def from_element(self, element: TagFieldBlockElement):
        self.clear_function = element.SelectField("flags").TestBit("clear function (Value and Interpolation time are unused)")
        self.frame = element.SelectField("frame").Data
        self.value = element.SelectField("value").Data
        self.interpolation_time = element.SelectField("interpolation time").Data
    
    def to_element(self, block: TagFieldBlock, object_block: TagFieldBlock):
        for element in block.Elements:
            if self.function_name == element.SelectField("function name").GetStringData() and get_subject_name(element.SelectField("object").Value, object_block) == self.object:
                break
        else:
            element = block.AddElement()
            element.SelectField("object").Value = get_subject_index(self.object, object_block)
            element.SelectField("function name").SetStringData(self.function_name)
        
        sub_element = element.SelectField("keyframes").AddElement()    
        sub_element.SelectField("flags").SetBit("clear function (Value and Interpolation time are unused)", self.clear_function)
        sub_element.SelectField("frame").Data = self.frame
        sub_element.SelectField("value").Data = self.value
        sub_element.SelectField("interpolation time").Data = self.interpolation_time

class CinematicObjectFunction:
    def __init__(self):
        self.object = ""
        self.function_name = ""
        self.keyframes: list[CinematicObjectFunctionKeyframe]  = []
        
    def from_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock) -> bool:
        self.object = get_subject_name(element.SelectField("object").Value, object_block)
        self.function_name = element.SelectField("function name").GetStringData()
        
        for sub_element in element.SelectField("keyframes").Elements:
            keyframe = CinematicObjectFunctionKeyframe(self.object, self.function_name)
            keyframe.from_element(sub_element)
            self.keyframes.append(keyframe)
            
        return bool(self.keyframes)
    
    # def to_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock):
    #     element.SelectField("object").Value = get_subject_index(self.object, object_block)
    #     element.SelectField("function name").SetStringData()
    #     keyframes_block = element.SelectField("keyframes")
    #     for keyframe in self.keyframes:
    #         keyframe.to_element(keyframes_block.AddElement())
        
class CinematicScreenEffect:
    def __init__(self):
        self.screen_effect: TagPath = None
        self.frame = 0
        self.stop_frame = 0
        self.persist_entire_shot = False
        
    def from_element(self, element: TagFieldBlockElement, corinth: bool):
        self.screen_effect = element.SelectField("screen effect").Path
        self.frame = element.SelectField("frame").Data
        self.stop_frame = element.SelectField("stop frame").Data
        if corinth:
            self.persist_entire_shot = element.SelectField("flags").TestBit("Persist Entire Shot")
    
    def to_element(self, element: TagFieldBlockElement, corinth: bool):
        element.SelectField("screen effect").Path = self.screen_effect
        element.SelectField("frame").Data = self.frame
        element.SelectField("stop frame").Data = self.stop_frame
        if corinth:
            element.SelectField("flags").SetBit("Persist Entire Shot", self.persist_entire_shot)
        
        
class CinematicCustomScript:
    def __init__(self):
        self.use_maya_value = False
        self.frame = 0
        self.script = ""
        self.node_id = 0
        self.sequence_id = 0
        
    def from_element(self, element: TagFieldBlockElement):
        self.use_maya_value = element.SelectField("flags").TestBit("use maya value")
        self.frame = element.SelectField("frame").Data
        self.script = element.SelectField("script").Elements[0].Fields[0].DataAsText
        self.node_id = element.SelectField("node id").Data
        self.sequence_id = element.SelectField("sequence id").Data
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("flags").SetBit("use maya value", self.use_maya_value)
        element.SelectField("frame").Data = self.frame
        element.SelectField("script").Elements[0].Fields[0].DataAsText = self.script
        element.SelectField("node id").Data = self.node_id
        element.SelectField("sequence id").Data = self.sequence_id
        
    def from_event(self, event: NWO_CinematicEvent, object_tag_weapon_names: dict):
        self.use_maya_value = True
        match event.script_type:
            case 'CUSTOM':
                if event.text is None:
                    self.script = event.script
                else:
                    self.script = event.text.as_string()
            case 'WEAPON_TRIGGER_START' | 'WEAPON_TRIGGER_STOP':
                if event.script_object is not None:
                    weapon_name = object_tag_weapon_names.get(utils.relative_path(event.script_object.nwo.cinematic_object))
                    if weapon_name is not None:
                        self.script = f'weapon_set_primary_barrel_firing (cinematic_weapon_get "{weapon_name}") {int(event.script_type == "WEAPON_TRIGGER_START")}'
            case 'SET_VARIANT':
                if event.script_object is not None:
                    self.script = f'object_set_variant (cinematic_object_get "{event.script_object.name}") {event.script_variant}'
            case 'SET_PERMUTATION':
                if event.script_object is not None:
                    self.script = f'object_set_permutation (cinematic_object_get "{event.script_object.name}") {event.script_region} {event.script_permutation}'
            case 'SET_REGION_STATE':
                if event.script_object is not None:
                    self.script = f'object_set_region_state (cinematic_object_get "{event.script_object.name}") {event.script_region} {event.script_state}'
            case 'SET_MODEL_STATE_PROPERTY':
                if event.script_object is not None:
                    self.script = f'object_set_model_state_property (cinematic_object_get "{event.script_object.name}") {int(event.script_state_property)} {event.script_bool}'
            case 'HIDE' | 'UNHIDE':
                if event.script_object is not None:
                    self.script = f'object_hide (cinematic_object_get "{event.script_object.name}") {int(event.script_type == "HIDE")}'
            case 'DESTROY':
                if event.script_object is not None:
                    self.script = f'object_destroy (cinematic_object_get "{event.script_object.name}")'
            case 'FADE_IN':
                red, green, blue = event.script_color
                self.script = f'fade_in {red} {green} {blue} {int(event.script_seconds * 30)}'
            case 'FADE_OUT':
                red, green, blue = event.script_color
                self.script = f'fade_out {red} {green} {blue} {int(event.script_seconds * 30)}'
            case 'SET_TITLE':
                self.script = f'cinematic_set_title {self.script_text}'
            case 'SHOW_HUD':
                self.script = 'chud_cinematic_fade 0 0\nchud_show_cinematics 1'
            case 'HIDE_HUD':
                self.script = f'chud_cinematic_fade 1 0\nchud_show_cinematics 0'
            case 'OBJECT_CANNOT_DIE' | 'OBJECT_CAN_DIE':
                if event.script_object is not None:
                    self.script = f'object_cannot_die (cinematic_object_get "{event.script_object.name}") {int(event.script_type == "OBJECT_CANNOT_DIE")}'
        
class CinematicUserInputConstraints:
    def __init__(self):
        self.frame = 0
        self.ticks = 0
        self.maximum_look_angles = 0, 0, 0, 0
        self.frictional_force = 0
        
    def from_element(self, element: TagFieldBlockElement):
        self.frame = element.SelectField("frame").Data
        self.ticks = element.SelectField("ticks").Data
        self.maximum_look_angles = element.SelectField("maximum look angles").Data
        self.frictional_force = element.SelectField("frictional force").Data
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("frame").Data = self.frame
        element.SelectField("ticks").Data = self.ticks
        element.SelectField("maximum look angles").Data = self.maximum_look_angles
        element.SelectField("frictional force").Data = self.frictional_force
        
    
class CinematicTextureMovie:
    def __init__(self):
        self.stop_movie_at_frame = False
        self.frame = 0
        self.bink_movie: TagPath = None
        
    def from_element(self, element: TagFieldBlockElement) -> bool:
        self.stop_movie_at_frame = element.SelectField("flags").TestBit("Stop Movie At Frame (rather than starting it)")
        self.frame = element.SelectField("frame").Data
        self.bink_movie = element.SelectField("bink movie").Path
        
        return self.bink_movie is not None
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("flags").SetBit("Stop Movie At Frame (rather than starting it)", self.stop_movie_at_frame)
        element.SelectField("frame").Data = self.frame
        element.SelectField("bink movie").Path = self.bink_movie

class CinematicSceneTag(Tag):
    tag_ext = 'cinematic_scene'
    
    def _read_fields(self):
        self.scene_playback = self.tag.SelectField("Custom:loop now")
    
    def get_loop_text(self) -> str:
        return self.scene_playback.GetLoopText()
    


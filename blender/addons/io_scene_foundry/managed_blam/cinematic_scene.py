from collections import defaultdict
import math
from typing import cast
from mathutils import Matrix, Vector

from .cinematic_lighting import CinematicLightingTag

from .lisp_to_corinth import script_from_text

from .cinematic_scene_data import CinematicSceneDataTag
from .. import utils
from ..props.scene import NWO_CinematicEvent
from . import Tag, tag_path_from_string
from . import import_transform
from .Tags import TagFieldBlock, TagFieldBlockElement, TagPath
import bpy
from ..managed_blam.camera_track import camera_correction_matrix

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
        self.actor = ""
        self.default_sound_effect = ""
        self.subtitle = ""
        self.female_subtitle = ""
        self.character = ""
    
    def from_element(self, element: TagFieldBlockElement): 
        self.dialogue = element.SelectField("dialogue").Path
        self.female_dialogue = element.SelectField("female dialogue").Path
        self.frame = element.SelectField("frame").Data
        self.scale = element.SelectField("scale").Data
        self.actor = element.SelectField("lipsync actor").GetStringData()
        self.default_sound_effect = element.SelectField("default sound effect").GetStringData()
        self.subtitle = element.SelectField("subtitle").GetStringData()
        self.female_subtitle = element.SelectField("female subtitle").GetStringData()
        self.character = element.SelectField("character").GetStringData()
    
    def to_event(self, nwo, corinth: bool): 
        event = cast(NWO_CinematicEvent, nwo.cinematic_events.add())
        event.type = 'DIALOGUE'
        if self.dialogue is not None:
            event.sound_tag = self.dialogue.RelativePathWithExtension
        if self.female_dialogue is not None:
            event.female_sound_tag = self.female_dialogue.RelativePathWithExtension
            
        event.frame = utils.blender_frame(self.frame + int((not corinth)))
        event.sound_scale = self.scale
        event.default_sound_effect = self.default_sound_effect
        event.subtitle = self.subtitle
        event.female_subtitle = self.female_subtitle
        event.subtitle_character = self.character
        
        return event
        
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("dialogue").Path = self.dialogue
        element.SelectField("female dialogue").Path = self.female_dialogue
        element.SelectField("frame").Data = self.frame
        element.SelectField("scale").Data = self.scale
        element.SelectField("lipsync actor").SetStringData(self.actor)
        element.SelectField("default sound effect").SetStringData(self.default_sound_effect)
        element.SelectField("subtitle").SetStringData(self.subtitle)
        element.SelectField("female subtitle").SetStringData(self.female_subtitle)
        element.SelectField("character").SetStringData(self.character)
        
    def from_event(self, event: NWO_CinematicEvent, actor_objects: set):
        if event.sound_tag.strip():
            self.dialogue = tag_path_from_string(event.sound_tag)
        if event.female_sound_tag.strip():
            self.female_dialogue = tag_path_from_string(event.female_sound_tag)
            if self.dialogue is None:
                self.dialogue = self.female_dialogue
        else:
            self.female_dialogue = self.dialogue
            
        self.scale = event.sound_scale
        self.actor = actor_objects.get(event.actor, "")
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
        self.frame = element.SelectField("LongInteger:frame").Data
        return self.music is not None
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("flags").SetBit("Stop Music At Frame (rather than starting it)", self.stops_music_at_frame)
        element.SelectField(r"music\foley").Path = self.music
        element.SelectField("LongInteger:frame").Data = self.frame
        
    def to_event(self, nwo, corinth: bool):
        event = cast(NWO_CinematicEvent, nwo.cinematic_events.add())
        event.type = 'MUSIC'
        event.stop = self.stops_music_at_frame
        event.sound_tag = self.music.RelativePathWithExtension
        event.frame = utils.blender_frame(self.frame + int((not corinth)))
        return event
        
    def from_event(self, event: NWO_CinematicEvent):
        self.stops_music_at_frame = event.stop
        self.music = event.sound_tag
        
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
        self.frame = element.SelectField("LongInteger:frame").Data
        self.marker_name = element.SelectField("marker name").GetStringData()
        self.marker_parent = get_subject_name(element.SelectField("marker parent").Value, object_block)
        self.node_id = element.SelectField("node id").Data
        self.sequence_id = element.SelectField("sequence id").Data
        if corinth:
            self.looping = element.SelectField("flags").TestBit("looping")
            self.state = element.SelectField("state").Value
            self.size_scale = element.SelectField("size scale").Data
            self.function_a = element.SelectField("function a").GetStringData()
            self.function_b = element.SelectField("function b").GetStringData()
            
        return self.effect is not None
        
    
    def to_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock, corinth: bool):
        element.SelectField("flags").SetBit("use maya value", self.use_maya_value)
        element.SelectField("effect").Path = self.effect
        element.SelectField("LongInteger:frame").Data = self.frame
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
            
    def to_event(self, nwo, corinth: bool):
        event = cast(NWO_CinematicEvent, nwo.cinematic_events.add())
        event.type = 'EFFECT'
        event.effect = self.effect.RelativePathWithExtension
        event.marker_name = self.marker_name
        event.function_a = self.function_a
        event.function_b = self.function_b
        event.looping = self.looping
        event.effect_state = str(self.state)
        
        event.frame = utils.blender_frame(self.frame + int((not corinth)))
        return event
            
    def from_event(self, event: NWO_CinematicEvent, actor_objects: dict):
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
            actor_name = actor_objects.get(actor, "")
            self.marker_parent = actor_name
                
        self.function_a = event.function_a
        self.function_b = event.function_b
        self.looping = event.looping
        self.state = int(event.effect_state)
            
        
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
    
    def to_element(self, block: TagFieldBlock, frame: int):
        element = block.AddElement()
        element.SelectField("flags").SetBit("clear function (Value and Interpolation time are unused)", self.clear_function)
        element.SelectField("frame").Data = frame
        element.SelectField("value").Data = self.value
        element.SelectField("interpolation time").Data = self.interpolation_time
        
    def from_event(self, event: NWO_CinematicEvent, actor_objects: dict):
        self.clear_function = event.clear_function
        self.value = event.value
        self.interpolation_time = int(event.interpolation_time * 30)
        self.object = actor_objects.get(event.actor, "")
        self.function_name = event.function_name
        
        return event
        
    def to_event(self, nwo, corinth: bool):
        event = cast(NWO_CinematicEvent, nwo.cinematic_events.add())
        event.type = 'FUNCTION'
        event.clear_function = self.clear_function
        event.value = self.value
        event.interpolation_time = float(self.interpolation_time / 30)
        event.function_name = self.function_name
        event.frame = utils.blender_frame(self.frame + int((not corinth)))
        
        return event

class CinematicObjectFunction:
    def __init__(self):
        self.object = ""
        self.function_name = ""
        self.keyframes: dict[int: CinematicObjectFunctionKeyframe]  = {}
        
    def from_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock) -> bool:
        self.object = get_subject_name(element.SelectField("object").Value, object_block)
        self.function_name = element.SelectField("function name").GetStringData()
        
        for sub_element in element.SelectField("keyframes").Elements:
            keyframe = CinematicObjectFunctionKeyframe(self.object, self.function_name)
            keyframe.from_element(sub_element)
            self.keyframes.append(keyframe)
            
        return bool(self.keyframes)
    
    def to_element(self, element: TagFieldBlockElement, object_block: TagFieldBlock):
        element.SelectField("object").Value = get_subject_index(self.object, object_block)
        element.SelectField("function name").SetStringData()
        keyframes_block = element.SelectField("keyframes")
        for frame, keyframe in self.keyframes.items():
            keyframe.to_element(keyframes_block, frame)
        
class CinematicScreenEffect:
    def __init__(self):
        self.screen_effect: TagPath = None
        self.frame = 0
        self.stop_frame = 0
        self.persist_entire_shot = False
        
    def from_element(self, element: TagFieldBlockElement, corinth: bool):
        self.screen_effect = element.SelectField("screen effect").Path
        self.frame = element.SelectField("LongInteger:frame").Data
        self.stop_frame = element.SelectField("stop frame").Data
        if corinth:
            self.persist_entire_shot = element.SelectField("flags").TestBit("Persist Entire Shot")
    
    def to_element(self, element: TagFieldBlockElement, corinth: bool):
        element.SelectField("screen effect").Path = self.screen_effect
        element.SelectField("LongInteger:frame").Data = self.frame
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
        self.frame = element.SelectField("LongInteger:frame").Data
        self.script = element.SelectField("script").Elements[0].Fields[0].DataAsText
        self.node_id = element.SelectField("node id").Data
        self.sequence_id = element.SelectField("sequence id").Data
    
    def to_element(self, element: TagFieldBlockElement, corinth: bool):
        element.SelectField("flags").SetBit("use maya value", self.use_maya_value)
        element.SelectField("LongInteger:frame").Data = self.frame
        element.SelectField("script").Elements[0].Fields[0].DataAsText = script_from_text(corinth, self.script)
        element.SelectField("node id").Data = self.node_id
        element.SelectField("sequence id").Data = self.sequence_id
        
    def to_event(self, nwo):
        event = cast(NWO_CinematicEvent, nwo.cinematic_events.add())
        event.type = 'SCRIPT'
        event.script_type = 'CUSTOM'
        event.script = self.script
        
        return event
        
    def from_event(self, event: NWO_CinematicEvent, object_tag_weapon_names: dict, actor_objects: set, corinth: bool):
        self.use_maya_value = True
        actor_name = actor_objects.get(event.actor, "")
        obj_text = f'(cinematic_object_get "{actor_name}")' if actor_name else 'None'
        match event.script_type:
            case 'CUSTOM':
                if event.text is None:
                    self.script = event.script
                else:
                    self.script = event.text.as_string()
            case 'WEAPON_TRIGGER_START' | 'WEAPON_TRIGGER_STOP':
                if actor_name:
                    weapon_name = object_tag_weapon_names.get(event.actor, "")
                    if weapon_name:
                        self.script = f'weapon_set_primary_barrel_firing (cinematic_weapon_get "{weapon_name}") {int(event.script_type == "WEAPON_TRIGGER_START")}'
            case 'SET_VARIANT':
                if actor_name and event.script_variant:
                    self.script = f'object_set_variant {obj_text} "{event.script_variant}"'
            case 'SET_PERMUTATION':
                if actor_name and event.script_permutation:
                    self.script = f'object_set_permutation {obj_text} "{event.script_region}" "{event.script_permutation}"'
            case 'SET_REGION_STATE':
                if actor_name:
                    self.script = f'object_set_region_state {obj_text} "{event.script_region}" {event.script_state}'
            case 'SET_MODEL_STATE_PROPERTY':
                if actor_name:
                    self.script = f'object_set_model_state_property {obj_text} {int(event.script_state_property)} {event.script_bool}'
            case 'HIDE' | 'UNHIDE':
                if actor_name:
                    self.script = f'object_hide {obj_text} {int(event.script_type == "HIDE")}'
            case 'DESTROY':
                if actor_name:
                    self.script = f'object_destroy {obj_text}'
            case 'FADE_IN':
                red, green, blue = event.script_color
                self.script = f'fade_in {red} {green} {blue} {int(event.script_seconds * 30)}'
            case 'FADE_OUT':
                red, green, blue = event.script_color
                self.script = f'fade_out {red} {green} {blue} {int(event.script_seconds * 30)}'
            case 'SET_TITLE':
                self.script = f'cinematic_set_title {event.script_text}'
            case 'SHOW_HUD':
                if not corinth:
                    self.script = 'chud_cinematic_fade 0 0\nchud_show_cinematics 1'
            case 'HIDE_HUD':
                if not corinth:
                    self.script = f'chud_cinematic_fade 1 0\nchud_show_cinematics 0'
            case 'OBJECT_CANNOT_DIE' | 'OBJECT_CAN_DIE':
                if actor_name:
                    self.script = f'object_cannot_die {obj_text} {int(event.script_type == "OBJECT_CANNOT_DIE")}'
            case 'OBJECT_PROJECTILE_COLLISION_ON' | 'OBJECT_PROJECTILE_COLLISION_OFF':
                if actor_name:
                    # weird script function, setting this to false makes the object had projectile collision
                    self.script = f'object_cinematic_visibility {obj_text} {int(event.script_type == "OBJECT_PROJECTILE_COLLISION_OFF")}'
            case 'DAMAGE_OBJECT':
                if actor_name:
                    self.script = f'damage_object {obj_text} "{event.script_region}" {event.script_damage}'
            case 'PLAY_SOUND':
                if event.sound_tag.strip():
                    self.script = f'sound_impulse_start {event.sound_tag} {obj_text} {event.script_factor}'
        
class CinematicUserInputConstraints:
    def __init__(self):
        self.frame = 0
        self.ticks = 0
        self.maximum_look_angles = 0, 0, 0, 0
        self.frictional_force = 0
        
    def from_element(self, element: TagFieldBlockElement):
        self.frame = element.SelectField("LongInteger:frame").Data
        self.ticks = element.SelectField("ticks").Data
        self.maximum_look_angles = element.SelectField("maximum look angles").Data
        self.frictional_force = element.SelectField("frictional force").Data
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("LongInteger:frame").Data = self.frame
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
        self.frame = element.SelectField("LongInteger:frame").Data
        self.bink_movie = element.SelectField("bink movie").Path
        
        return self.bink_movie is not None
    
    def to_element(self, element: TagFieldBlockElement):
        element.SelectField("flags").SetBit("Stop Movie At Frame (rather than starting it)", self.stop_movie_at_frame)
        element.SelectField("LongInteger:frame").Data = self.frame
        element.SelectField("bink movie").Path = self.bink_movie
        
class CamFrame:
    def __init__(self):
        self.matrix = None
        self.lens = 0

class CinObject():
    def __init__(self):
        self.name = ""
        self.variant = ""
        self.graph_path = ""
        self.object_path = ""
        self.armature = None
        self.animations = None
        self.cameras = {}
        self.cinematic_lighting: CinematicLighting = None
        self.events = []
    
class CinematicSceneTag(Tag):
    tag_ext = 'cinematic_scene'
    
    def _read_fields(self):
        self.scene_playback = self.tag.SelectField("Custom:loop now")
        self.cam_position_path = "Struct:camera frame[0]/Struct:dynamic data[0]/RealPoint3d:camera position" if self.corinth else "Struct:camera frame[0]/RealPoint3d:camera position"
        self.cam_forward_path = "Struct:camera frame[0]/Struct:dynamic data[0]/RealVector3d:camera forward" if self.corinth else "Struct:camera frame[0]/RealVector3d:camera forward"
        self.cam_up_path = "Struct:camera frame[0]/Struct:dynamic data[0]/RealVector3d:camera up" if self.corinth else "Struct:camera frame[0]/RealVector3d:camera up"
        self.cam_focal_length_path = "Struct:camera frame[0]/Struct:constant data[0]/Real:focal length" if self.corinth else "Struct:camera frame[0]/Real:focal length"
    
    def get_loop_text(self) -> str:
        return self.scene_playback.GetLoopText()
    
    def to_blender(self, film_aperture: float, cinematic_name: str, data: CinematicSceneDataTag):
        camera_objects = []
        object_animations = []
        frame = 1
        actions = []
        shot_frames = []
        
        scene_id = self.tag_path.ShortName[(len(cinematic_name) + 1):]
        cin_scene = self.scene_nwo.cinematic_scenes.get(scene_id)
        if cin_scene is None:
            cin_scene = self.scene_nwo.cinematic_scenes.add()
        
        cin_scene.name = scene_id
        blender_scene = bpy.data.scenes.get(self.tag_path.ShortName)
        if blender_scene is None:
            blender_scene = bpy.data.scenes.new(self.tag_path.ShortName)
            blender_scene.nwo.is_main_scene = False

        cin_scene.scene = blender_scene
        cin_scene_nwo = blender_scene.nwo
        
        utils.print_tag(f"Importing cinematic scene: {self.tag_path.ShortName}")
        
        scene_shots = self.tag.SelectField("shots")
        data_shots = data.tag.SelectField("shots")
        scene_objects = self.tag.SelectField("Block:objects")
        data_objects = data.tag.SelectField("Block:objects")
        
        object_count = scene_objects.Elements.Count
        
        object_lighting = defaultdict(list)
        object_events = defaultdict(list) # object name: event
        camera_events = defaultdict(list) # shot index: class instance
        
        for scene_element, data_element in zip(scene_shots.Elements, data_shots.Elements):
            utils.print_step(f"Importing cinematic events for shot: {scene_element.ElementIndex + 1}")
            main_screen_effect = None
            main_user_constraint = None
            
            for dialogue_element in data_element.SelectField("dialogue").Elements:
                dialogue = CinematicDialogue()
                dialogue.from_element(dialogue_element)
                dialogue.to_event(cin_scene_nwo, self.corinth)
                object_events[dialogue.actor].append(len(cin_scene_nwo.cinematic_events) - 1)
                
            for music_element in scene_element.SelectField("music").Elements:
                music = CinematicMusic()
                music.from_element(music_element)
                music.to_event(cin_scene_nwo, self.corinth)
                
            for effect_element in data_element.SelectField("effects").Elements:
                effect = CinematicEffect()
                effect.from_element(effect_element, data_objects, self.corinth)
                effect.to_event(cin_scene_nwo, self.corinth)
                object_events[effect.marker_parent].append(len(cin_scene_nwo.cinematic_events) - 1)
                
            for object_functions_element in scene_element.SelectField("object functions").Elements:
                object_function = CinematicObjectFunction()
                object_function.from_element(object_functions_element, scene_objects)
                for keyframe in object_function.keyframes:
                    keyframe.to_event(cin_scene_nwo, self.corinth)
                    object_events[object_function.object].append(len(cin_scene_nwo.cinematic_events) - 1)
                
            for screen_effects_element in scene_element.SelectField("screen effects").Elements:
                screen_effect = CinematicScreenEffect()
                screen_effect.from_element(screen_effects_element, self.corinth)
                main_screen_effect = screen_effect
                
            for script_element in data_element.SelectField("custom script").Elements:
                script = CinematicCustomScript()
                script.from_element(script_element)
                script.to_event(cin_scene_nwo)
                
            for user_element in data_element.SelectField("user input constraints").Elements:
                user = CinematicUserInputConstraints()
                user.from_element(user_element)
                main_user_constraint = user
            
            utils.print_step(f"Importing cinematic lighting for shot: {scene_element.ElementIndex + 1}")
            for light_element in scene_element.SelectField("Block:lighting").Elements:
                cin_lighting_path = light_element.SelectField("Reference:lighting").Path
                if not self.path_exists(cin_lighting_path):
                    continue
                
                subject = light_element.SelectField("subject").Value
                
                if subject < 0 or subject >= object_count:
                    continue
                
                marker = light_element.SelectField("marker").GetStringData()
                persist = light_element.SelectField("flags").TestBit("persists across shots")
                with CinematicLightingTag(path=cin_lighting_path) as lighting_tag:
                    object_lighting[subject].append(lighting_tag.to_cinematic_lighting(marker, persist, data_element.ElementIndex))
            
            utils.print_step(f"Creating camera data for shot: {data_element.ElementIndex + 1}")
            shot_camera_name = f"{self.tag_path.ShortName}_shot{data_element.ElementIndex + 1}"
            shot_camera_data = bpy.data.cameras.new(shot_camera_name)
            shot_camera = bpy.data.objects.new(shot_camera_name, shot_camera_data)
            shot_camera_data.display_size *= (1 / 0.03048) * import_transform.scale_factor()
            shot_camera_data.clip_end = 100000
            camera_objects.append(shot_camera)
            
            if main_screen_effect is not None:
                shot_camera.nwo.screen_effect = main_screen_effect.screen_effect.RelativePathWithExtension
            
            if main_user_constraint is not None:
                shot_camera.nwo.user_input_bounds = main_user_constraint.maximum_look_angles
            
            cam_frames = []
            
            timeline_marker = blender_scene.timeline_markers.new(shot_camera.name, frame=frame)
            timeline_marker.camera = shot_camera
            
            for frame_element in data_element.SelectField("Block:frame data").Elements:
                cam_position = Vector([n for n in frame_element.SelectField(self.cam_position_path).Data]) * 100
                cam_forward = Vector([n for n in frame_element.SelectField(self.cam_forward_path).Data]).normalized()
                cam_up = Vector([n for n in frame_element.SelectField(self.cam_up_path).Data]).normalized()
                focal_length = frame_element.SelectField(self.cam_focal_length_path).Data
                
                cam_left = cam_up.cross(cam_forward).normalized()
                
                matrix = Matrix((
                    (cam_forward[0], cam_left[0], cam_up[0], cam_position[0]),
                    (cam_forward[1], cam_left[1], cam_up[1], cam_position[1]),
                    (cam_forward[2], cam_left[2], cam_up[2], cam_position[2]),
                    (0, 0, 0, 1),
                ))
                
                cam_frame = CamFrame()
                cam_frame.matrix = import_transform.object_matrix(matrix @ camera_correction_matrix.to_4x4())
                cam_frame.lens = focal_length
                cam_frames.append(cam_frame)
            
            matrices = [cf.matrix.freeze() for cf in cam_frames]
            keyframe_matrices = len(set(matrices)) > 1
            camera_data_action = None
            camera_action = None
            shot_camera.matrix_world = matrices[0]
            if keyframe_matrices:
                camera_action = bpy.data.actions.new(f"{shot_camera.name}")
                slot = camera_action.slots.new('OBJECT', shot_camera.name)
                actions.append(camera_action)
                
                shot_camera.animation_data_create()
                shot_camera.animation_data.action = camera_action
                shot_camera.animation_data.last_slot_identifier = slot.identifier
                
                camera_fcurves = utils.get_fcurves(camera_action, slot)
                loc_curves = [camera_fcurves.new(data_path="location", index=i) for i in range(3)]

                shot_camera.rotation_mode = 'QUATERNION'
                rot_curves = [camera_fcurves.new(data_path="rotation_quaternion", index=i) for i in range(4)]
                
            fovs = [cf.lens for cf in cam_frames]
            keyframe_fovs = len(set(fovs)) > 1
            shot_camera_data.lens = fovs[0]
            shot_camera_data.sensor_width = film_aperture
            if keyframe_fovs:
                camera_data_action = bpy.data.actions.new(f"{shot_camera.name}_data")
                slot = camera_data_action.slots.new('CAMERA', shot_camera_data.name)
                
                shot_camera_data.animation_data_create()
                shot_camera_data.animation_data.action = camera_data_action
                shot_camera_data.animation_data.last_slot_identifier = slot.identifier
                
                camera_data_fcurves = utils.get_fcurves(camera_data_action, slot)
                lens_curve = camera_data_fcurves.new(data_path="lens")
                
            if keyframe_matrices or keyframe_fovs:
                shot_frame = frame
                for cf in cam_frames:
                    if keyframe_matrices:
                        loc, rot, _ = cf.matrix.decompose()
                        for i in range(3):
                            loc_curves[i].keyframe_points.insert(shot_frame, loc[i], options={'FAST'})

                        for i in range(4):
                            rot_curves[i].keyframe_points.insert(shot_frame, rot[i], options={'FAST'})
                        
                    if keyframe_fovs:
                        lens_curve.keyframe_points.insert(shot_frame, cf.lens, options={'FAST'})
                        
                    shot_frame += 1

            shot_frames.append(frame)
            frame += data_element.SelectField("frame count").Data
            
        blender_scene.frame_start = 1
        blender_scene.frame_end = frame
        
        utils.print_tag("Cinematic Objects")
        
        scene_objects = self.tag.SelectField("Block:objects")
        data_objects = data.tag.SelectField("Block:objects")
        
        for scene_element, data_element in zip(scene_objects.Elements, data_objects.Elements):
            name = scene_element.SelectField("name").GetStringData()
            variant = scene_element.SelectField("variant name").GetStringData()
            graph = data_element.SelectField("model animation graph").Path
            obj = data_element.SelectField("object type").Path
            
            if self.path_exists(obj) and self.path_exists(graph):
                cin_object = CinObject()
                cin_object.name = name
                cin_object.variant = variant
                cin_object.graph_path = graph.Filename
                cin_object.object_path = obj.Filename
                cin_object.cinematic_lighting = object_lighting.get(scene_element.ElementIndex)
                cin_object.events = object_events.get(name, [])
                object_animations.append(cin_object)
                flags = data_element.SelectField("shots active flags")
                shots = []
                if self.corinth:
                    flags.RefreshShots()
                    for idx in range(flags.ShotCount):
                        if flags.GetShotChecked(idx):
                            shots.append(idx + 1)
                            cin_object.cameras[idx] = camera_objects[idx]
                else:
                    for idx, item in enumerate(flags.Items):
                        if item.IsSet:
                            shots.append(idx + 1)
                            cin_object.cameras[idx] = camera_objects[idx]
                        
                utils.print_step(f"{name} is present in shots {shots}")
        
        light_tags = []
        if self.corinth:
            for element in self.tag.SelectField("Block:lights").Elements:
                info_path = element.Fields[0].Path
                if self.path_exists(info_path):
                    light_tags.append(info_path.Filename)
            
        return self.tag_path.ShortName, blender_scene, camera_objects, object_animations, self.tag.SelectField("anchor").GetStringData(), actions, shot_frames, light_tags

from mathutils import Matrix, Vector
from .. import utils
from ..props.scene import NWO_CinematicEvent
from . import Tag, tag_path_from_string
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
        self.lipsync_actor = ""
        if event.lipsync_actor is not None and event.lipsync_actor in actor_objects:
            self.lipsync_actor = event.lipsync_actor.name
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
            
    def from_event(self, event: NWO_CinematicEvent, actor_objects: set):
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
            if actor is not None and actor in actor_objects:
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
        
    def from_event(self, event: NWO_CinematicEvent, object_tag_weapon_names: dict, actor_objects: set):
        self.use_maya_value = True
        valid_object = event.script_object is not None and event.script_object in actor_objects
        obj_text = f'(cinematic_object_get "{event.script_object.name}")' if valid_object else 'None'
        match event.script_type:
            case 'CUSTOM':
                if event.text is None:
                    self.script = event.script
                else:
                    self.script = event.text.as_string()
            case 'WEAPON_TRIGGER_START' | 'WEAPON_TRIGGER_STOP':
                if valid_object:
                    weapon_name = object_tag_weapon_names.get(utils.relative_path(event.script_object.nwo.cinematic_object))
                    if weapon_name is not None:
                        self.script = f'weapon_set_primary_barrel_firing (cinematic_weapon_get "{weapon_name}") {int(event.script_type == "WEAPON_TRIGGER_START")}'
            case 'SET_VARIANT':
                if valid_object:
                    self.script = f'object_set_variant {obj_text} {event.script_variant}'
            case 'SET_PERMUTATION':
                if valid_object:
                    self.script = f'object_set_permutation {obj_text} {event.script_region} {event.script_permutation}'
            case 'SET_REGION_STATE':
                if valid_object:
                    self.script = f'object_set_region_state {obj_text} {event.script_region} {event.script_state}'
            case 'SET_MODEL_STATE_PROPERTY':
                if valid_object:
                    self.script = f'object_set_model_state_property {obj_text} {int(event.script_state_property)} {event.script_bool}'
            case 'HIDE' | 'UNHIDE':
                if valid_object:
                    self.script = f'object_hide {obj_text} {int(event.script_type == "HIDE")}'
            case 'DESTROY':
                if valid_object:
                    self.script = f'object_destroy {obj_text}'
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
                if valid_object:
                    self.script = f'object_cannot_die {obj_text} {int(event.script_type == "OBJECT_CANNOT_DIE")}'
            case 'OBJECT_PROJECTILE_COLLISION_ON' | 'OBJECT_PROJECTILE_COLLISION_OFF':
                if valid_object:
                    # weird script function, setting this to false makes the object had projectile collision
                    self.script = f'object_cinematic_visibility {obj_text} {int(event.script_type == "OBJECT_PROJECTILE_COLLISION_OFF")}'
            case 'DAMAGE_OBJECT':
                if valid_object:
                    self.script = f'damage_object {obj_text} {event.script_region} {event.script_damage}'
            case 'PLAY_SOUND':
                self.script = f'sound_impulse_start {event.sound_tag} {obj_text} {event.script_factor}'
        
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
        self.actions = None
    
class CinematicSceneTag(Tag):
    tag_ext = 'cinematic_scene'
    
    def _read_fields(self):
        self.scene_playback = self.tag.SelectField("Custom:loop now")
    
    def get_loop_text(self) -> str:
        return self.scene_playback.GetLoopText()
    
    def to_blender(self):
        camera_objects = []
        object_animations = []
        frame = 1
        actions = []
        shot_frames = []
        
        blender_scene = bpy.context.scene
        
        print(f"Importing cinematic scene: {self.tag_path.ShortName}")
        
        for element in self.tag.SelectField("Block:objects").Elements:
            name = element.SelectField("name").GetStringData()
            variant = element.SelectField("variant name").GetStringData()
            graph = element.SelectField("model animation graph").Path
            obj = element.SelectField("object type").Path
            
            if self.path_exists(obj) and self.path_exists(graph):
                cin_object = CinObject()
                cin_object.name = name
                cin_object.variant = variant
                cin_object.graph_path = graph.Filename
                cin_object.object_path = obj.Filename
                object_animations.append(cin_object)
        
        for element in self.tag.SelectField("shots").Elements:
            print(f"--- Creating camera data for shot: {element.ElementIndex + 1}")
            shot_camera_name = f"{self.tag_path.ShortName}_shot{element.ElementIndex + 1}"
            shot_camera_data = bpy.data.cameras.new(shot_camera_name)
            shot_camera = bpy.data.objects.new(shot_camera_name, shot_camera_data)
            shot_camera_data.display_size *= (1 / 0.03048)
            camera_objects.append(shot_camera)
            
            cam_frames = []
            
            timeline_marker = blender_scene.timeline_markers.new(shot_camera.name, frame=frame)
            timeline_marker.camera = shot_camera
            
            for frame_element in element.SelectField("Block:frame data").Elements:
                cam_position = Vector([n for n in frame_element.SelectField("Struct:camera frame[0]/RealPoint3d:camera position").Data]) * 100
                cam_forward = Vector([n for n in frame_element.SelectField("Struct:camera frame[0]/RealVector3d:camera forward").Data]).normalized()
                cam_up = Vector([n for n in frame_element.SelectField("Struct:camera frame[0]/RealVector3d:camera up").Data]).normalized()
                focal_length = frame_element.SelectField("Struct:camera frame[0]/Real:focal length").Data
                
                cam_left = cam_up.cross(cam_forward).normalized()
                
                matrix = Matrix((
                    (cam_forward[0], cam_left[0], cam_up[0], cam_position[0]),
                    (cam_forward[1], cam_left[1], cam_up[1], cam_position[1]),
                    (cam_forward[2], cam_left[2], cam_up[2], cam_position[2]),
                    (0, 0, 0, 1),
                ))
                
                cam_frame = CamFrame()
                cam_frame.matrix = matrix @ camera_correction_matrix.to_4x4()
                cam_frame.lens = focal_length / (0.5 if self.corinth else 1.25)
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
            frame += element.SelectField("frame count").Data
            
        return self.tag_path.ShortName, blender_scene, camera_objects, object_animations, self.tag.SelectField("anchor").GetStringData(), actions, shot_frames
                    
from collections import defaultdict
from typing import cast
from mathutils import Matrix, Vector

from .cinematic_lighting import CinematicLightingTag

from .cinematic import CinematicCameraDocument, CinematicSceneDataTag
from .blender import BlenderTag
from .. import utils
from ..props.scene import NWO_CinematicEvent
from .. import import_transform
from .backend import TagReference
import bpy
from .camera_track import camera_correction_matrix


class CinematicDialogue:
    @classmethod
    def from_native(cls, record):
        result = cls()
        for name, value in vars(record).items():
            setattr(result, name, value)
        return result

    def __init__(self):
        self.dialogue: TagReference | str | None = None
        self.female_dialogue: TagReference | str | None = None
        self.frame = 0
        self.scale = 1
        self.actor = ""
        self.default_sound_effect = ""
        self.subtitle = ""
        self.female_subtitle = ""
        self.character = ""
    
    
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
        
    
        
    def from_event(self, event: NWO_CinematicEvent, actor_objects: set):
        if event.sound_tag.strip():
            self.dialogue = utils.relative_path(event.sound_tag)
        if event.female_sound_tag.strip():
            self.female_dialogue = utils.relative_path(event.female_sound_tag)
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
    @classmethod
    def from_native(cls, record):
        result = cls()
        result.music = record.music
        result.frame = record.frame
        result.stops_music_at_frame = record.stops_music_at_frame
        return result

    def __init__(self):
        self.stops_music_at_frame = False
        self.music: TagReference | str | None = None
        self.frame = 0
        
    
        
    def to_event(self, nwo, corinth: bool):
        event = cast(NWO_CinematicEvent, nwo.cinematic_events.add())
        event.type = 'MUSIC'
        event.stop = self.stops_music_at_frame
        event.music = self.music.RelativePathWithExtension
        event.frame = utils.blender_frame(self.frame + int((not corinth)))
        return event
        
    def from_event(self, event: NWO_CinematicEvent):
        self.stops_music_at_frame = event.stop
        self.music = utils.relative_path(event.music)
        
class CinematicEffect:
    @classmethod
    def from_native(cls, record):
        result = cls()
        for name, value in vars(record).items():
            setattr(result, name, value)
        return result

    def __init__(self):
        self.use_maya_value = False
        self.looping = False
        self.state = 0
        self.effect: TagReference | str | None = None
        self.size_scale = 1
        self.frame = 0
        self.marker_name = ""
        self.marker_parent = ""
        self.function_a = ""
        self.function_b = ""
        self.node_id = 0
        self.sequence_id = 0
        
        
    
            
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
            self.effect = utils.relative_path(event.effect)
        
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
    @classmethod
    def from_native(cls, record):
        result = cls()
        for name, value in vars(record).items():
            setattr(result, name, value)
        return result

    def __init__(self, ob: str = "", func: str = ""):
        self.clear_function = False
        self.frame = 0
        self.value = 0
        self.interpolation_time = 0
        self.object = ob
        self.function_name = func
        
    
        
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

        
        
class CinematicCustomScript:
    @classmethod
    def from_native(cls, record):
        result = cls()
        for name, value in vars(record).items():
            setattr(result, name, value)
        return result

    def __init__(self):
        self.use_maya_value = False
        self.frame = 0
        self.script = ""
        self.weapon_name = ""
        self.node_id = 0
        self.sequence_id = 0

    def set_weapon_trigger_script(self, weapon_name: str, firing: bool):
        self.use_maya_value = True
        self.weapon_name = weapon_name
        self.script = f'weapon_set_primary_barrel_firing (cinematic_weapon_get "{weapon_name}") {int(firing)}'
        
    
        
    def to_event(self, nwo):
        event = cast(NWO_CinematicEvent, nwo.cinematic_events.add())
        event.type = 'SCRIPT'
        event.script_type = 'CUSTOM'
        event.script = self.script
        
        return event
        
    def from_event(self, event: NWO_CinematicEvent, object_tag_weapon_names: dict, actor_objects: set, corinth: bool, actor_attachment_names: dict | None = None, actor_attachment_weapon_names: dict | None = None):
        self.use_maya_value = True
        actor_name = actor_objects.get(event.actor, "")
        actor_attachment_names = actor_attachment_names or {}
        actor_attachment_weapon_names = actor_attachment_weapon_names or {}
        attachment_name = ""
        attachment_key = event.script_attachment
        if attachment_key and attachment_key != "NONE":
            attachment_name = actor_attachment_names.get(event.actor, {}).get(attachment_key, "")

        target_name = attachment_name or actor_name
        obj_text = f'(cinematic_object_get "{target_name}")' if target_name else 'None'
        match event.script_type:
            case 'CUSTOM':
                if event.script_use_text:
                    if event.text is not None:
                        self.script = event.text.as_string()
                else:
                    self.script = event.script
            case 'WEAPON_TRIGGER_START' | 'WEAPON_TRIGGER_STOP':
                if actor_name:
                    if attachment_key and attachment_key != "NONE":
                        weapon_name = actor_attachment_weapon_names.get(event.actor, {}).get(attachment_key, "")
                    else:
                        weapon_name = object_tag_weapon_names.get(event.actor, "")
                    if weapon_name:
                        self.set_weapon_trigger_script(weapon_name, event.script_type == "WEAPON_TRIGGER_START")
                    elif event.actor:
                        utils.print_warning(f"Event at frame {event.frame} tries to fire a weapon but actor {event.actor.name} is not an weapon tag or does not use a weapon tag attachment")
                            
            case 'SET_VARIANT':
                if target_name and event.script_variant:
                    self.script = f'object_set_variant {obj_text} "{event.script_variant}"'
            case 'SET_PERMUTATION':
                if target_name and event.script_permutation:
                    self.script = f'object_set_permutation {obj_text} "{event.script_region}" "{event.script_permutation}"'
            case 'SET_REGION_STATE':
                if target_name:
                    self.script = f'object_set_region_state {obj_text} "{event.script_region}" {int(event.script_state)}'
            case 'SET_MODEL_STATE_PROPERTY':
                if target_name:
                    self.script = f'object_set_model_state_property {obj_text} {int(event.script_state_property)} {event.script_bool}'
            case 'HIDE' | 'UNHIDE':
                if target_name:
                    self.script = f'object_hide {obj_text} {int(event.script_type == "HIDE")}'
            case 'DESTROY':
                if target_name:
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
                if target_name:
                    self.script = f'object_cannot_die {obj_text} {int(event.script_type == "OBJECT_CANNOT_DIE")}'
            case 'OBJECT_PROJECTILE_COLLISION_ON' | 'OBJECT_PROJECTILE_COLLISION_OFF':
                if target_name:
                    # weird script function, setting this to false makes the object had projectile collision
                    self.script = f'object_cinematic_visibility {obj_text} {int(event.script_type == "OBJECT_PROJECTILE_COLLISION_OFF")}'
            case 'DAMAGE_OBJECT':
                if target_name:
                    self.script = f'damage_object {obj_text} "{event.script_region}" {event.script_damage}'
            case 'PLAY_SOUND':
                if event.sound_tag.strip():
                    self.script = f'sound_impulse_start {utils.relative_path(event.sound_tag)} {obj_text} {event.script_factor}'
            case 'SOUND_CLASS_GAIN':
                self.script = f'sound_class_set_gain_db "{event.script_text}" {event.script_float} {int(event.script_seconds * utils.real_frame_rate())}'
            case 'SOUND_ENABLE_DUCKER':
                self.script = f'sound_class_enable_ducker "{event.script_text}" 1'
            case 'SOUND_DISABLE_DUCKER':
                self.script = f'sound_class_enable_ducker "{event.script_text}" 0'
            case 'START_GLOBAL_EFFECT':
                if self.script_text.strip():
                    if self.script_seconds > 0.0:
                        self.script = f'sound_start_timed_global_effect "{event.script_text}" {self.script_factor} {event.script_seconds}'
                    else:
                        self.script = f'sound_start_global_effect "{event.script_text}" {self.script_factor}'
            case 'STOP_GLOBAL_EFFECT':
                if self.script_text.strip():
                    self.script = f'sound_stop_global_effect "{event.script_text}"'
            case 'SET_GRAVITY':
                self.script = f'physics_set_gravity {event.script_float}'
        
        
    
        
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
        self.cinematic_lighting: object | None = None
        self.events = []
    
class NativeCinematicSceneTag(BlenderTag, CinematicCameraDocument):
    """Native cinematic-scene import entry point."""
    tag_ext = 'cinematic_scene'

    def _set_value(self, element, name, value):
        self.required_field(element, name).set(value)
        self.tag_has_changes = True

    def _set_script(self, root, name, text):
        script = self.required_field(root, name).as_struct()
        if script is None:
            raise TypeError(f'{self.path}: {name!r} is not a script structure')
        self._set_value(script, 'script', text.encode('utf-8'))

    def write_export_header(self, name, reset_object_lighting, header, footer,
                            data_path=None):
        root = self.tag.root()
        self._set_value(root, 'name', name)
        self._set_value(root, 'anchor', f'{name}_anchor')
        self._set_value(root, 'reset object lighting', int(reset_object_lighting))
        self._set_script(root, 'header', header)
        self._set_script(root, 'footer', footer)
        if data_path is not None:
            self.set_reference(root, 'data', data_path)

    def _set_shot_flags(self, element, name, indices, document=None):
        document = document or self
        field = document.required_field(element, name)
        if field.type_name == 'long block flags':
            mask = sum(1 << index for index in indices if 0 <= index < 32)
            if mask & 0x80000000:
                mask -= 0x100000000
            field.set(mask)
        elif field.type_name == 'array':
            chunks = field.as_array()
            masks = [0] * len(chunks)
            for index in indices:
                if 0 <= index < len(chunks) * 32:
                    masks[index // 32] |= 1 << (index % 32)
            for chunk, mask in zip(chunks, masks):
                document.required_field(chunk, 'shot flag data').set(mask)
        else:
            raise TypeError(f'{self.path}: {name!r} is not a supported shot-flags field')
        document.tag_has_changes = True

    @staticmethod
    def _set_available_flag(field, name, value):
        if name in field.options().names:
            field.set_flag(name, value)

    def _add_export_attachment(self, block, invisible, marker_name, object_name,
                               attachment_marker_name, attachment_type):
        element = block[block.add()]
        flags = element.field('flags')
        if flags is not None:
            flags.set_flag('invisible', invisible)
        self._set_value(element, 'object marker name', marker_name)
        self._set_value(element, 'attachment object name', object_name)
        self._set_value(element, 'attachment marker name', attachment_marker_name)
        self.set_reference(element, 'attachment type', attachment_type)

    def write_export_objects(self, actors, script_from_text, data=None):
        objects = self.block(self.tag.root(), 'objects')
        objects.clear()
        data_objects = None
        if data is not None:
            data_objects = data.block(data.tag.root(), 'objects')
            data_objects.clear()

        for actor in actors:
            element = objects[objects.add()]
            self._set_value(element, 'name', actor.name)
            self._set_value(element, 'variant name', actor.variant)
            actor_nwo = actor.ob.nwo
            attachments = self.block(element, 'attachments')
            if actor.weapon_tag is not None:
                self._add_export_attachment(attachments, True, 'primary_trigger',
                    f'{actor.name}_weapon', 'primary_trigger', actor.weapon_tag)
            for index, attachment in enumerate(actor_nwo.attachments):
                attachment_type = attachment.attachment_type.strip()
                if not attachment_type:
                    continue
                attachment_type = utils.relative_path(attachment_type)
                marker_name = utils.clean_text(attachment.marker_name, empty_string_allowed=True)
                attachment_marker = utils.clean_text(
                    attachment.attachment_marker_name or attachment.marker_name,
                    empty_string_allowed=True)
                base_name = Path(attachment_type).with_suffix('').name or 'attachment'
                object_name = utils.clean_text(
                    f'{actor.name}_{base_name}_{index + 1}', replace_spaces=True)
                self._add_export_attachment(attachments, attachment.invisible,
                    marker_name, object_name, attachment_marker, attachment_type)

            flags = self.required_field(element, 'flags')
            special_case = actor.name in {'player0', 'player1', 'player2', 'player3'}
            self._set_available_flag(flags, 'Special Case (like player0)', special_case)
            self._set_available_flag(flags, 'Placed Manually in Sapien',
                not special_case and actor_nwo.object_source == 'CREATE_ANEW')
            self._set_available_flag(flags, 'Object Comes From Game',
                not special_case and actor_nwo.object_source == 'USE')
            for name, value in (
                    ('Effect Object', actor_nwo.effect_object),
                    ('No Lightmap Shadow', actor_nwo.no_lightmap_shadow),
                    ('Apply Player Customization', actor_nwo.apply_player_customization),
                    ('Apply First Person Player Customization', actor_nwo.apply_first_person_player_customization),
                    ('I will animate the English lipsync manually', actor_nwo.english_lipsync_manual)):
                self._set_available_flag(flags, name, value)
            if self.corinth:
                self._set_available_flag(flags, 'Primary Cortana', actor_nwo.primary_cortana)
                self._set_available_flag(flags, 'Preload Textures', actor_nwo.preload_textures)

            overrides = self.required_field(element, 'override creation flags')
            for name, value in (
                    ('single player', not actor_nwo.override_1_player),
                    ('2 player co-op', not actor_nwo.override_2_player),
                    ('3 player co-op', not actor_nwo.override_3_player),
                    ('4 player co-op', not actor_nwo.override_4_player)):
                overrides.set_flag(name, value)
            self._set_script(element, 'custom don\'t create condition', script_from_text(
                self.corinth, actor_nwo.override_script, actor_nwo.override_script_text,
                actor_nwo.override_script_use_text))

            if data_objects is None:
                self._set_value(element, 'identifier', actor.name)
                self.set_reference(element, 'model animation graph', actor.graph or None)
                self.set_reference(element, 'object type', actor.tag or None)
                self._set_shot_flags(element, 'shots active flags', actor.shots_active)
                lightmap = element.field('lightmap shadow flags')
                if lightmap is not None:
                    self._set_shot_flags(element, 'lightmap shadow flags', actor.shots_lightmap)
            else:
                self._set_shot_flags(element, 'lightmap shadow flags', actor.shots_lightmap)
                self._set_shot_flags(element, 'high res flags', actor.shots_high_res)
                data_element = data_objects[data_objects.add()]
                data.required_field(data_element, 'name').set(actor.name)
                data.required_field(data_element, 'identifier').set(actor.name)
                data.set_reference(data_element, 'model animation graph', actor.graph or None)
                data.set_reference(data_element, 'object type', actor.tag or None)
                self._set_shot_flags(data_element, 'shots active flags',
                    actor.shots_active, data)
        self.tag_has_changes = True
        if data is not None:
            data.tag_has_changes = True
    
    def to_blender(self, film_aperture: float, cinematic_name: str, data: CinematicSceneDataTag):
        with CinematicCameraDocument(data.tag_path.Filename, tags_root=utils.get_tags_path(),
                                     game=utils.get_project().game, must_exist=True) as native:
            camera_shots = native.camera_shots()
            frame_counts = native.shot_frame_counts()
            scene_metadata = native.scene_metadata() if not self.corinth else None
            dialogue_shots = native.dialogue_shots()
            effect_shots = native.effect_shots()
            script_shots = native.script_shots()
            native_data_objects = native.object_records()
            native_scene_objects = native_data_objects if not self.corinth else None
            music_shots = native.music_shots() if not self.corinth else None
            function_shots = native.object_function_shots() if not self.corinth else None
            screen_effect_shots = native.screen_effect_shots() if not self.corinth else None
            user_constraint_shots = native.user_constraint_shots() if not self.corinth else None
            lighting_shots = native.lighting_shots() if not self.corinth else None
        if self.corinth:
            with CinematicCameraDocument(self.tag_path.Filename, tags_root=utils.get_tags_path(),
                                         game=utils.get_project().game, must_exist=True) as native_scene:
                music_shots = native_scene.music_shots()
                function_shots = native_scene.object_function_shots()
                screen_effect_shots = native_scene.screen_effect_shots()
                user_constraint_shots = native_scene.user_constraint_shots()
                lighting_shots = native_scene.lighting_shots()
                native_scene_objects = native_scene.object_records()
                scene_metadata = native_scene.scene_metadata()
        if len(music_shots) != len(camera_shots):
            raise ValueError('Cinematic scene and camera-data shot counts differ')
        if len(native_scene_objects) != len(native_data_objects):
            raise ValueError('Cinematic scene and data object counts differ')
        if any(record.active_shots is None for record in native_data_objects):
            raise ValueError('Unsupported cinematic shot-visibility layout')
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
        
        object_count = len(native_scene_objects)
        
        object_lighting = defaultdict(list)
        object_events = defaultdict(list) # object name: event
        camera_events = defaultdict(list) # shot index: class instance
        
        for shot_index in range(len(camera_shots)):
            utils.print_step(f"Importing cinematic events for shot: {shot_index + 1}")
            main_screen_effect = None
            main_user_constraint = None
            
            for dialogue_record in dialogue_shots[shot_index]:
                dialogue = CinematicDialogue.from_native(dialogue_record)
                dialogue.to_event(cin_scene_nwo, self.corinth)
                object_events[dialogue.actor].append(len(cin_scene_nwo.cinematic_events) - 1)
                
            for music_record in music_shots[shot_index]:
                music = CinematicMusic.from_native(music_record)
                music.to_event(cin_scene_nwo, self.corinth)
                
            for effect_record in effect_shots[shot_index]:
                effect = CinematicEffect.from_native(effect_record)
                effect.to_event(cin_scene_nwo, self.corinth)
                object_events[effect.marker_parent].append(len(cin_scene_nwo.cinematic_events) - 1)
                
            for function_record in function_shots[shot_index]:
                keyframe = CinematicObjectFunctionKeyframe.from_native(function_record)
                keyframe.to_event(cin_scene_nwo, self.corinth)
                object_events[keyframe.object].append(len(cin_scene_nwo.cinematic_events) - 1)
                
            for screen_effect in screen_effect_shots[shot_index]:
                main_screen_effect = screen_effect
                
            for script_record in script_shots[shot_index]:
                script = CinematicCustomScript.from_native(script_record)
                script.to_event(cin_scene_nwo)
                
            for user in user_constraint_shots[shot_index]:
                main_user_constraint = user
            
            utils.print_step(f"Importing cinematic lighting for shot: {shot_index + 1}")
            for assignment in lighting_shots[shot_index]:
                cin_lighting_path = assignment.lighting
                if not self.path_exists(cin_lighting_path):
                    continue
                
                subject = assignment.subject
                
                if subject < 0 or subject >= object_count:
                    continue
                
                marker = assignment.marker
                persist = assignment.persist
                with CinematicLightingTag(path=cin_lighting_path) as lighting_tag:
                    object_lighting[subject].append(lighting_tag.to_cinematic_lighting(marker, persist, shot_index))
            
            utils.print_step(f"Creating camera data for shot: {shot_index + 1}")
            shot_camera_name = f"{self.tag_path.ShortName}_shot{shot_index + 1}"
            shot_camera_data = bpy.data.cameras.new(shot_camera_name)
            shot_camera = bpy.data.objects.new(shot_camera_name, shot_camera_data)
            shot_camera_data.display_size *= (1 / 0.03048) * import_transform.scale_factor()
            shot_camera_data.clip_end = 100000
            camera_objects.append(shot_camera)
            
            if main_screen_effect is not None:
                shot_camera.nwo.screen_effect = main_screen_effect.screen_effect.RelativePathWithExtension
            
            if main_user_constraint is not None:
                t, l, b, r,  = main_user_constraint.maximum_look_angles
                shot_camera.nwo.user_input_bounds_t = abs(t)
                shot_camera.nwo.user_input_bounds_l = abs(l)
                shot_camera.nwo.user_input_bounds_b = abs(b)
                shot_camera.nwo.user_input_bounds_r = abs(r)
            
            cam_frames = []
            
            timeline_marker = blender_scene.timeline_markers.new(shot_camera.name, frame=frame)
            timeline_marker.camera = shot_camera
            
            for camera_frame in camera_shots[shot_index]:
                cam_position = Vector(camera_frame.position) * 100
                cam_forward = Vector(camera_frame.forward).normalized()
                cam_up = Vector(camera_frame.up).normalized()
                focal_length = camera_frame.lens
                
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
            frame += frame_counts[shot_index]
            
        blender_scene.frame_start = 1
        blender_scene.frame_end = frame
        
        utils.print_tag("Cinematic Objects")
        
        for scene_record, data_record in zip(native_scene_objects, native_data_objects):
            name, variant = scene_record.name, scene_record.variant
            graph, obj = data_record.graph, data_record.object_type
            
            if self.path_exists(obj) and self.path_exists(graph):
                cin_object = CinObject()
                cin_object.name = name
                cin_object.variant = variant
                cin_object.graph_path = graph.Filename
                cin_object.object_path = obj.Filename
                cin_object.cinematic_lighting = object_lighting.get(scene_record.index)
                cin_object.events = object_events.get(name, [])
                object_animations.append(cin_object)
                shots = []
                for idx in data_record.active_shots:
                    shots.append(idx + 1)
                    cin_object.cameras[idx] = camera_objects[idx]
                        
                utils.print_step(f"{name} is present in shots {shots}")
        
        light_tags = [path.Filename for path in scene_metadata.lights if self.path_exists(path)]
            
        return self.tag_path.ShortName, blender_scene, camera_objects, object_animations, scene_metadata.anchor, actions, shot_frames, light_tags

"""Native cinematic camera and event records, detached from their tag handles."""
from math import degrees, isfinite
from types import SimpleNamespace
from .backend import TagDocument
from .blender import BlenderTag
from .cinematic_script import encode_script_data


# Playback derives FOV from globals and lens. After the observer's 4:3
# conversion, the cinematic renderer applies a separate widescreen/letterbox
# adjustment. The normal 16:9 projection therefore uses globals as its
# horizontal aperture directly, not globals * 4/3.
CINEMATIC_REFERENCE_ASPECT = 4 / 3
CINEMATIC_WIDESCREEN_ASPECT = 16 / 9
CINEMATIC_LETTERBOX_ASPECT = 2.35


def cinematic_runtime_aperture(film_aperture: float, render_aspect: float, *, game: str = 'halo3') -> float:
    """Default widescreen H3 letterbox projection, including its final fit.

    Between 16:9 and the cinematic gate, letterbox fitting preserves horizontal
    FOV. Beyond that gate it preserves vertical FOV; a narrower widescreen
    viewport likewise retains the 16:9 vertical gate.
    """
    # ODST gates the extra 0.75 correction separately. Keep its existing
    # observer conversion until its active render configuration is verified.
    if game == 'halo3odst':
        return film_aperture * render_aspect / CINEMATIC_REFERENCE_ASPECT
    if render_aspect < CINEMATIC_WIDESCREEN_ASPECT:
        return film_aperture * render_aspect / CINEMATIC_WIDESCREEN_ASPECT
    return film_aperture * max(1.0, render_aspect / CINEMATIC_LETTERBOX_ASPECT)


class CinematicCameraDocument(TagDocument):
    def shot_frame_counts(self):
        counts = [self.value(shot, 'frame count') for shot in self.block(self.tag.root(), 'shots')]
        if any(count < 0 for count in counts):
            raise ValueError('Negative cinematic shot frame count')
        return counts

    def _write_value(self, element, name, value):
        self.required_field(element, name).set(value)
        self.tag_has_changes = True

    def _write_script(self, element, name, text):
        script = self.required_field(element, name).as_struct()
        if script is None:
            raise TypeError(f'{self.path}: {name!r} is not a script structure')
        self._write_value(script, 'script', encode_script_data(text))

    def _write_vector(self, element, name, value):
        field = self.required_field(element, name)
        field.set(type(field.value)(*value))
        self.tag_has_changes = True

    def _shot_elements(self, shots, rebuild=False):
        elements = self.block(self.tag.root(), 'shots')
        if rebuild:
            elements.clear()
            for _ in shots:
                elements.add()
        if len(elements) != len(shots):
            raise ValueError(
                f'{self.path}: expected {len(shots)} shot records, found {len(elements)}')
        return elements

    def write_shot_settings(self, shots, corinth, script_from_text, rebuild=False):
        for element, shot in zip(self._shot_elements(shots, rebuild), shots):
            if not shot.frames:
                continue
            camera = shot.camera.nwo
            self._write_script(element, 'header', script_from_text(
                corinth, camera.header, camera.header_text, camera.header_use_text))
            self._write_script(element, 'footer', script_from_text(
                corinth, camera.footer, camera.footer_text, camera.footer_use_text))
            for name, value in (('environment darken', camera.environment_darken),
                                ('forced exposure', camera.forced_exposure)):
                if element.field(name) is not None:
                    self._write_value(element, name, value)
            flags = self.required_field(element, 'flags')
            for name, enabled in (('Instant Auto-Exposure', camera.instant_auto_exposure),
                                  ('Force Exposure', camera.force_exposure),
                                  ('Generate Looping Script', camera.generate_looping_script)):
                if name in flags.options().names:
                    flags.set_flag(name, enabled)

            if corinth:
                settings = self.required_field(element, 'settings flags')

                def set_option(name, option):
                    settings.set_flag(f'{name} - clear', option == 'CLEAR')
                    settings.set_flag(f'{name} - persist across shots', option == 'PERSIST')

                set_scalars = camera.lightmap_direct_scalar != 1.0 or camera.lightmap_indirect_scalar != 1.0
                settings.set_flag('Lightmap Scalars - set', set_scalars)
                self._write_value(element, 'Lightmap Direct Scalar', camera.lightmap_direct_scalar)
                self._write_value(element, 'Lightmap Indirect Scalar', camera.lightmap_indirect_scalar)
                set_option('Lightmap Scalars', camera.lightmap_scalar_option)
                settings.set_flag('Sun Scalar - set', camera.sun_scalar != 1.0)
                self._write_value(element, 'Sun Scalar', camera.sun_scalar)
                set_option('Sun Scalar', camera.sun_scalar_option)
                for field_name, path, option in (
                        ('Atmosphere Fog', camera.atmosphere_fog, camera.atmosphere_fog_option),
                        ('Camera Effects', camera.camera_effects, camera.camera_effects_option),
                        ('Cubemap', camera.cubemap, camera.cubemap_option)):
                    if path.strip():
                        self.set_reference(element, field_name, path)
                    set_option(field_name, option)
                settings.set_flag('Disable All Lightmap Shadows', camera.disable_all_lightmap_shadows)
            self.tag_has_changes = True

    def write_camera_frames(self, shots, corinth, rebuild=False):
        for element, shot in zip(self._shot_elements(shots, rebuild), shots):
            if not getattr(shot, 'in_scope', True):
                continue
            self._write_value(element, 'frame count', shot.frame_count)
            frame_data = self.block(element, 'frame data')
            frame_data.clear()
            for frame in shot.frames:
                frame_element = frame_data[frame_data.add()]
                camera_frame = self.required_field(frame_element, 'camera frame').as_struct()
                if camera_frame is None:
                    raise TypeError(f'{self.path}: camera frame is not a struct')
                self._write_camera_payload(camera_frame, frame, corinth)
            self.tag_has_changes = True

    def _write_camera_payload(self, camera, frame, corinth):
        dynamic = self.required_field(camera, 'dynamic data').as_struct() if corinth else camera
        constant = self.required_field(camera, 'constant data').as_struct() if corinth else camera
        if dynamic is None or constant is None:
            raise TypeError(f'{self.path}: camera data is not a struct')
        for name, value in (('camera position', frame.position),
                            ('camera forward', frame.forward), ('camera up', frame.up)):
            self._write_vector(dynamic, name, value)
        names = ('focal length', 'depth of field', 'near focal plane distance', 'far focal plane distance')
        names += (('near focal depth', 'far focal depth', 'near blur amount', 'far blur amount')
                  if corinth else ('focal depth', 'blur amount'))
        if self.game in {'halo3', 'halo3odst'}:
            names += ('horizontal field of view', 'horizontal film aperture')
        for name in names:
            attribute = {'horizontal field of view': 'horizontal_fov',
                         'horizontal film aperture': 'film_aperture'}.get(name, name.replace(' ', '_'))
            self._write_value(constant, name, getattr(frame, attribute))

    def validate_extra_camera_frames(self, tracks, shots, rebuild=True):
        """Validate everything before changing either main or extra shot arrays."""
        field = self.tag.root().field('extra camera frame data')
        if field is None:
            if tracks:
                raise ValueError(f'{self.path}: extra cameras are unavailable in this tag layout')
            return
        if rebuild and tracks and any(not getattr(shot, 'in_scope', True) for shot in shots):
            raise ValueError('Rebuilding extra camera tracks requires exporting all shots')
        names = [track.name for track in tracks]
        if any(not name.strip() for name in names) or len(set(names)) != len(names):
            raise ValueError('Extra camera export names must be nonempty and unique')
        for track in tracks:
            if not track.camera_type.strip() or len(track.shots) != len(shots):
                raise ValueError(f'Extra camera {track.name}: invalid type or shot count')
            for shot, frames in zip(shots, track.shots):
                if getattr(shot, 'in_scope', True) and len(frames) != shot.frame_count:
                    raise ValueError(f'Extra camera {track.name}: frame count differs from the main shot')
                for frame in frames:
                    axes = (*frame.position, *frame.forward, *frame.up, frame.focal_length)
                    if not all(isfinite(v) for v in axes) or frame.focal_length <= 0:
                        raise ValueError(f'Extra camera {track.name}: invalid camera values')
                    cross = tuple(frame.forward[(i+1)%3] * frame.up[(i+2)%3]
                                  - frame.forward[(i+2)%3] * frame.up[(i+1)%3] for i in range(3))
                    if sum(v*v for v in cross) < 1e-12:
                        raise ValueError(f'Extra camera {track.name}: degenerate camera axes')
        if rebuild:
            return
        existing = field.as_block()
        identities = [(self.value(e, 'name'), self.value(e, 'type')) for e in existing]
        if len(identities) != len(tracks) or set(identities) != {(t.name, t.camera_type) for t in tracks}:
            raise ValueError('Extra cameras were added, renamed, or removed; export all shots first')
        if self.shot_frame_counts() != [s.frame_count for s in shots]:
            raise ValueError('Cinematic shot boundaries changed; export all shots first')
        for extra in existing:
            extra_shots = self.block(extra, 'shots')
            if len(extra_shots) != len(shots) or any(
                    len(self.block(e, 'frame data')) != s.frame_count for e, s in zip(extra_shots, shots)):
                raise ValueError('Extra camera shot layout changed; export all shots first')

    def write_extra_camera_frames(self, tracks, shots, corinth, rebuild=True):
        self.validate_extra_camera_frames(tracks, shots, rebuild)
        field = self.tag.root().field('extra camera frame data')
        if field is None:
            return
        extras = field.as_block()
        if rebuild:
            extras.clear()
            for track in tracks:
                extra = extras[extras.add()]
                self._write_value(extra, 'name', track.name)
                self._write_value(extra, 'type', track.camera_type)
                for _ in shots:
                    self.block(extra, 'shots').add()
        by_name = {self.value(extra, 'name'): extra for extra in extras}
        for track in tracks:
            extra_shots = self.block(by_name[track.name], 'shots')
            for shot, extra_shot, frames in zip(shots, extra_shots, track.shots):
                if not getattr(shot, 'in_scope', True):
                    continue
                block = self.block(extra_shot, 'frame data')
                block.clear()
                for frame in frames:
                    element = block[block.add()]
                    self.required_field(element, 'flags').set_flag('enabled', bool(frame.enabled))
                    self._write_camera_payload(self.required_field(element, 'frame data').as_struct(), frame, corinth)
        self.tag_has_changes = True

    def extra_camera_tracks(self):
        """Detach auxiliary frames from the tag, including inactive samples."""
        field = self.tag.root().field('extra camera frame data')
        if field is None:
            return []
        counts = self.shot_frame_counts()
        tracks = []
        for extra in field.as_block():
            shots = []
            for shot in self.block(extra, 'shots'):
                frames = []
                for element in self.block(shot, 'frame data'):
                    camera = self.required_field(element, 'frame data').as_struct()
                    dynamic = camera.field('dynamic data')
                    constant = camera.field('constant data')
                    dynamic = dynamic.as_struct() if dynamic is not None else camera
                    constant = constant.as_struct() if constant is not None else camera
                    frame = SimpleNamespace(enabled=self.required_field(element, 'flags').get_flag('enabled'))
                    for name, attribute in (('camera position', 'position'), ('camera forward', 'forward'), ('camera up', 'up')):
                        setattr(frame, attribute, tuple(self.value(dynamic, name).to_array()))
                    for name in ('focal length', 'depth of field', 'near focal plane distance', 'far focal plane distance',
                                 'focal depth', 'blur amount', 'near focal depth', 'far focal depth',
                                 'near blur amount', 'far blur amount'):
                        item = constant.field(name)
                        setattr(frame, name.replace(' ', '_'), item.value if item is not None else 0)
                    for name, attribute in (('horizontal field of view', 'horizontal_fov'), ('horizontal film aperture', 'film_aperture')):
                        item = constant.field(name)
                        setattr(frame, attribute, item.value if item is not None else None)
                    frame.lens = frame.focal_length
                    frames.append(frame)
                shots.append(frames)
            if len(shots) != len(counts) or any(len(frames) != count for frames, count in zip(shots, counts)):
                raise ValueError(f'{self.path}: extra camera shots do not match the main camera')
            tracks.append(SimpleNamespace(name=self.value(extra, 'name'), camera_type=self.value(extra, 'type'), shots=shots))
        return tracks

    def write_camera_shots(self, shots, corinth, script_from_text, rebuild=False):
        self.write_shot_settings(shots, corinth, script_from_text, rebuild)
        self.write_camera_frames(shots, corinth)

    def write_camera_events(self, shots, corinth, game_frame):
        for element, shot in zip(self._shot_elements(shots), shots):
            camera = shot.camera.nwo
            screen_effect = camera.screen_effect.strip()
            screen_field = element.field('screen effects')
            if screen_effect:
                if screen_field is None:
                    raise ValueError(f'{self.path}: screen effects are unavailable in this tag layout')
                block = screen_field.as_block()
                block.clear()
                record = block[block.add()]
                self.set_reference(record, 'screen effect', screen_effect)
                frame = game_frame(camera.screen_effect_delay) + int(corinth)
                self._write_value(record, 'frame', frame)
                if camera.screen_effect_time > 0:
                    self._write_value(record, 'stop frame',
                                      frame + game_frame(camera.screen_effect_time))
                elif corinth:
                    self._write_value(record, 'stop frame', 1)
                    self.required_field(record, 'flags').set_flag('Persist Entire Shot', True)
                else:
                    self._write_value(record, 'stop frame', shot.frame_count - 1)
            elif screen_field is not None:
                screen_field.as_block().clear()

            has_constraints = any((camera.user_input_bounds_t,
                                   camera.user_input_bounds_l,
                                   camera.user_input_bounds_b,
                                   camera.user_input_bounds_r))
            constraint_field = element.field('user input constraints')
            if has_constraints:
                if constraint_field is None:
                    raise ValueError(
                        f'{self.path}: user-input constraints are unavailable in this tag layout')
                block = constraint_field.as_block()
                block.clear()
                record = block[block.add()]
                self._write_value(record, 'frame',
                                  game_frame(camera.user_input_bounds_delay) + int(corinth))
                self._write_value(record, 'ticks', game_frame(camera.user_input_bounds_time))
                self._write_vector(record, 'maximum look angles', (
                    int(degrees(camera.user_input_bounds_t)),
                    int(degrees(-camera.user_input_bounds_l)),
                    int(degrees(-camera.user_input_bounds_b)),
                    int(degrees(camera.user_input_bounds_r))))
                self._write_value(record, 'frictional force', camera.frictional_force)
            elif constraint_field is not None:
                constraint_field.as_block().clear()
        self.tag_has_changes = True

    def write_timeline_events(self, music, function_keyframes, locate_frame):
        shots = self.block(self.tag.root(), 'shots')
        for shot in shots:
            self.block(shot, 'music').clear()
            functions = shot.field('object functions')
            if functions is not None:
                functions.as_block().clear()

        for event, frame_index in music.items():
            shot_index, shot_frame = locate_frame(frame_index)
            if shot_index is None:
                continue
            block = self.block(shots[shot_index], 'music')
            element = block[block.add()]
            flags = element.field('flags')
            if flags is not None:
                flags.set_flag('Stop Music At Frame (rather than starting it)',
                               event.stops_music_at_frame)
            elif event.stops_music_at_frame:
                raise ValueError(f'{self.path}: stopping music is unavailable in this tag layout')
            self.set_reference(element, r'music\foley', event.music)
            self._write_value(element, 'frame', shot_frame)

        object_indices = {
            self.value(element, 'name'): index
            for index, element in enumerate(self.block(self.tag.root(), 'objects'))
        }
        groups = {}
        for event, frame_index in function_keyframes.items():
            shot_index, shot_frame = locate_frame(frame_index)
            if shot_index is None:
                continue
            groups.setdefault(
                (shot_index, event.function_name, event.object), []).append(
                    (event, shot_frame))

        for (shot_index, function_name, object_name), keyframes in groups.items():
            block = self.block(shots[shot_index], 'object functions')
            element = block[block.add()]
            self._write_value(element, 'object', object_indices.get(object_name, -1))
            self._write_value(element, 'function name', function_name)
            keys = self.block(element, 'keyframes')
            for event, shot_frame in keyframes:
                key = keys[keys.add()]
                flags = key.field('flags')
                if flags is not None:
                    flags.set_flag('clear function (Value and Interpolation time are unused)',
                                   event.clear_function)
                elif event.clear_function:
                    raise ValueError(f'{self.path}: clearing object functions is unavailable in this tag layout')
                self._write_value(key, 'frame', shot_frame)
                self._write_value(key, 'value', event.value)
                if key.field('interpolation time') is not None:
                    self._write_value(key, 'interpolation time', event.interpolation_time)
        self.tag_has_changes = True

    def write_script_events(self, scripts, locate_frame, corinth, script_from_text):
        shots = self.block(self.tag.root(), 'shots')
        for shot in shots:
            self.block(shot, 'custom script').clear()
        for event, frame_index in scripts.items():
            if not event.script:
                continue
            shot_index, shot_frame = locate_frame(frame_index)
            if shot_index is None:
                continue
            block = self.block(shots[shot_index], 'custom script')
            element = block[block.add()]
            flags = element.field('flags')
            if flags is not None:
                flags.set_flag('use maya value', event.use_maya_value)
            self._write_value(element, 'frame', shot_frame)
            self._write_script(element, 'script',
                               script_from_text(corinth, event.script))
            node_id = element.field('node id')
            if node_id is not None:
                node_id.set(event.node_id)
                self.required_field(element, 'sequence id').set(event.sequence_id)
        self.tag_has_changes = True

    def write_content_events(self, dialogue, effects, locate_frame):
        shots = self.block(self.tag.root(), 'shots')
        for shot in shots:
            self.block(shot, 'dialogue').clear()
            self.block(shot, 'effects').clear()

        for event, frame_index in dialogue.items():
            shot_index, shot_frame = locate_frame(frame_index)
            if shot_index is None:
                continue
            block = self.block(shots[shot_index], 'dialogue')
            element = block[block.add()]
            self.set_reference(element, 'dialogue', event.dialogue)
            if element.field('female dialogue') is not None:
                self.set_reference(element, 'female dialogue', event.female_dialogue)
            for name, value in (
                    ('frame', shot_frame), ('scale', event.scale),
                    ('lipsync actor', event.actor),
                    ('default sound effect', event.default_sound_effect),
                    ('subtitle', event.subtitle),
                    ('female subtitle', event.female_subtitle),
                    ('character', event.character)):
                if element.field(name) is not None:
                    self._write_value(element, name, value)

        object_indices = {
            self.value(element, 'name'): index
            for index, element in enumerate(self.block(self.tag.root(), 'objects'))
        }
        for event, frame_index in effects.items():
            shot_index, shot_frame = locate_frame(frame_index)
            if shot_index is None:
                continue
            block = self.block(shots[shot_index], 'effects')
            element = block[block.add()]
            flags = element.field('flags')
            if flags is not None:
                flags.set_flag('use maya value', event.use_maya_value)
                if 'looping' in flags.options().names:
                    flags.set_flag('looping', event.looping)
            self.set_reference(element, 'effect', event.effect)
            for name, value in (
                    ('frame', shot_frame), ('marker name', event.marker_name),
                    ('marker parent', object_indices.get(event.marker_parent, -1)),
                    ('size scale', event.size_scale), ('state', event.state),
                    ('function a', event.function_a), ('function b', event.function_b),
                    ('node id', event.node_id), ('sequence id', event.sequence_id)):
                if element.field(name) is not None:
                    if name == 'marker parent' and element.field(name).type_name == 'string id':
                        value = event.marker_parent
                    self._write_value(element, name, value)
        self.tag_has_changes = True

    def write_lighting_events(self, assignments):
        shots = self.block(self.tag.root(), 'shots')
        for shot in shots:
            lighting = shot.field('lighting')
            if lighting is not None:
                lighting.as_block().clear()
        for shot_index, subject, lighting, marker, persist in assignments:
            if not 0 <= shot_index < len(shots):
                raise ValueError(f'{self.path}: lighting assignment has invalid shot {shot_index}')
            block = self.block(shots[shot_index], 'lighting')
            element = block[block.add()]
            flags = element.field('flags')
            if flags is None:
                if persist:
                    raise ValueError(
                        f'{self.path}: persistent lighting is unavailable in this tag layout')
            else:
                flags.set_flag('persists across shots', persist)
            self.set_reference(element, 'lighting', lighting)
            self._write_value(element, 'subject', subject)
            self._write_value(element, 'marker', marker)
        self.tag_has_changes = True


    def scene_metadata(self):
        root = self.tag.root()
        lights = root.field('lights')
        references = []
        for element in lights.as_block() if lights is not None else ():
            reference = self.reference(element, 'structure lighting info')
            if reference is not None:
                references.append(reference)
        return SimpleNamespace(anchor=self.value(root, 'anchor'), lights=references)

    def object_records(self):
        records = []
        shot_count = len(self.block(self.tag.root(), 'shots'))
        for index, element in enumerate(self.block(self.tag.root(), 'objects')):
            flags = element.field('shots active flags')
            active_shots = None
            if flags is not None and flags.type_name == 'long block flags':
                mask = flags.value & 0xffffffff
                active_shots = [i for i in range(min(shot_count, 32)) if mask & (1 << i)]
            elif flags is not None and flags.type_name == 'array':
                chunks = flags.as_array()
                active_shots = []
                for chunk_index, chunk in enumerate(chunks):
                    mask = self.value(chunk, 'shot flag data') & 0xffffffff
                    active_shots.extend(chunk_index * 32 + bit for bit in range(32)
                                        if chunk_index * 32 + bit < shot_count and mask & (1 << bit))
            attachments = []
            attachment_field = element.field('attachments')
            for attachment in attachment_field.as_block() if attachment_field is not None else ():
                attachment_flags = attachment.field('flags')
                attachments.append(SimpleNamespace(
                    name=self.value(attachment, 'attachment object name'),
                    parent_marker=self.value(attachment, 'object marker name'),
                    child_marker=self.value(attachment, 'attachment marker name'),
                    object_type=self.reference(attachment, 'attachment type'),
                    invisible=attachment_flags.get_flag('invisible') if attachment_flags is not None else False))
            object_flags = element.field('flags')
            actor_settings = {}
            for flag, prop in (
                    ('Effect Object', 'effect_object'), ('No Lightmap Shadow', 'no_lightmap_shadow'),
                    ('Apply Player Customization', 'apply_player_customization'),
                    ('Use Master Chief player appearance', 'apply_player_customization'),
                    ('Apply First Person Player Customization', 'apply_first_person_player_customization'),
                    ('I will animate the English lipsync manually', 'english_lipsync_manual')):
                if object_flags is not None and flag in object_flags.options().names:
                    actor_settings[prop] = object_flags.get_flag(flag)
            actor_settings['object_source'] = ('CREATE_ANEW' if object_flags is not None
                and 'Placed Manually in Sapien' in object_flags.options().names
                and object_flags.get_flag('Placed Manually in Sapien') else 'CREATE')
            if (object_flags is not None and 'Object Comes From Game' in object_flags.options().names
                    and object_flags.get_flag('Object Comes From Game')):
                actor_settings['object_source'] = 'USE'
            overrides = element.field('override creation flags')
            if overrides is not None:
                for player_index, flag in enumerate(('single player', '2 player co-op', '3 player co-op', '4 player co-op'), 1):
                    actor_settings[f'override_{player_index}_player'] = not overrides.get_flag(flag)
            condition = element.field("custom don't create condition")
            if condition is not None:
                actor_settings['override_script'] = bytes(self.value(condition.as_struct(), 'script')).rstrip(b'\x00').decode('utf-8-sig')
            records.append(SimpleNamespace(index=index, name=self.value(element, 'name'),
                settings=actor_settings,
                identifier=self.value(element, 'identifier') if element.field('identifier') is not None else '',
                attachments=attachments,
                placed_manually=object_flags.get_flag('Placed Manually in Sapien')
                    if object_flags is not None and 'Placed Manually in Sapien' in object_flags.options().names else False,
                active_shots=active_shots,
                variant=self.value(element, 'variant name') if element.field('variant name') is not None else '',
                graph=self.reference(element, 'model animation graph') if element.field('model animation graph') is not None else None,
                object_type=self.reference(element, 'object type') if element.field('object type') is not None else None))
        return records

    def script_shots(self):
        shots = []
        for shot in self.block(self.tag.root(), 'shots'):
            records = []
            for element in self.block(shot, 'custom script'):
                script = self.required_field(element, 'script').as_struct()
                raw = bytes(self.value(script, 'script'))
                text = raw.rstrip(b'\x00').decode('utf-8-sig')
                flags = element.field('flags')
                records.append(SimpleNamespace(script=text, frame=self.value(element, 'frame'),
                    use_maya_value=flags.get_flag('use maya value') if flags is not None else False,
                    node_id=self.value(element, 'node id') if element.field('node id') is not None else 0,
                    sequence_id=self.value(element, 'sequence id') if element.field('sequence id') is not None else 0))
            shots.append(records)
        return shots


    def lighting_shots(self):
        object_count = len(self.block(self.tag.root(), 'objects'))
        shots = []
        for shot in self.block(self.tag.root(), 'shots'):
            records = []
            for element in self.block(shot, 'lighting'):
                reference = self.reference(element, 'lighting')
                subject = self.value(element, 'subject')
                if reference is None or not 0 <= subject < object_count:
                    continue
                flags = element.field('flags')
                records.append(SimpleNamespace(lighting=reference, subject=subject,
                    marker=self.value(element, 'marker'),
                    persist=flags.get_flag('persists across shots') if flags is not None else False))
            shots.append(records)
        return shots

    def user_constraint_shots(self):
        shots = []
        for shot in self.block(self.tag.root(), 'shots'):
            records = []
            block = shot.field('user input constraints')
            for element in block.as_block() if block is not None else ():
                angles = self.value(element, 'maximum look angles')
                angles = (angles.top, angles.left, angles.bottom, angles.right)
                friction = self.value(element, 'frictional force')
                if not all(isfinite(v) for v in (*angles, friction)):
                    raise ValueError('Non-finite cinematic user-input constraint')
                records.append(SimpleNamespace(frame=self.value(element, 'frame'),
                    ticks=self.value(element, 'ticks'), maximum_look_angles=angles,
                    frictional_force=friction))
            shots.append(records)
        return shots

    def screen_effect_shots(self):
        shots = []
        for shot in self.block(self.tag.root(), 'shots'):
            records = []
            block = shot.field('screen effects')
            for element in block.as_block() if block is not None else ():
                reference = self.reference(element, 'screen effect')
                if reference is None:
                    continue
                flags = element.field('flags')
                records.append(SimpleNamespace(screen_effect=reference,
                    frame=self.value(element, 'frame'), stop_frame=self.value(element, 'stop frame'),
                    persist_entire_shot=flags.get_flag('Persist Entire Shot') if flags is not None else False))
            shots.append(records)
        return shots

    def object_function_shots(self):
        objects = [self.value(e, 'name') for e in self.block(self.tag.root(), 'objects')]
        shots = []
        for shot in self.block(self.tag.root(), 'shots'):
            records = []
            for element in self.block(shot, 'object functions'):
                index = self.value(element, 'object')
                name = objects[index] if 0 <= index < len(objects) else ''
                function = self.value(element, 'function name')
                keyframes = {}
                for key in self.block(element, 'keyframes'):
                    frame = self.value(key, 'frame')
                    value = self.value(key, 'value')
                    if not isfinite(value):
                        raise ValueError('Non-finite cinematic object-function value')
                    keyframes[frame] = SimpleNamespace(object=name, function_name=function,
                        frame=frame, value=value, interpolation_time=self.value(key, 'interpolation time'),
                        clear_function=self.required_field(key, 'flags').get_flag(
                            'clear function (Value and Interpolation time are unused)'))
                records.extend(keyframes.values())
            shots.append(records)
        return shots

    def music_shots(self):
        shots = []
        for shot in self.block(self.tag.root(), 'shots'):
            records = []
            for element in self.block(shot, 'music'):
                music = self.reference(element, r'music\foley')
                if music is None:
                    continue
                records.append(SimpleNamespace(music=music, frame=self.value(element, 'frame'),
                    stops_music_at_frame=self.required_field(element, 'flags').get_flag(
                        'Stop Music At Frame (rather than starting it)')))
            shots.append(records)
        return shots

    def effect_shots(self):
        objects = [self.value(e, 'name') for e in self.block(self.tag.root(), 'objects')]
        shots = []
        for shot in self.block(self.tag.root(), 'shots'):
            records = []
            for element in self.block(shot, 'effects'):
                effect = self.reference(element, 'effect')
                if effect is None:
                    continue
                parent = self.value(element, 'marker parent')
                flags = element.field('flags')
                later = element.field('state') is not None
                state = self.value(element, 'state') if later else 0
                if isinstance(state, str):
                    state = {'start': 0, 'stop': 1, 'kill': 2}[state]
                scale = self.value(element, 'size scale') if later else 1.0
                if not isfinite(scale):
                    raise ValueError('Non-finite cinematic effect scale')
                records.append(SimpleNamespace(effect=effect, frame=self.value(element, 'frame'),
                    marker_name=self.value(element, 'marker name'),
                    marker_parent=objects[parent] if 0 <= parent < len(objects) else '',
                    use_maya_value=flags.get_flag('use maya value') if flags is not None else False,
                    looping=flags.get_flag('looping') if later else False, state=state, size_scale=scale,
                    function_a=self.value(element, 'function a') if later else '',
                    function_b=self.value(element, 'function b') if later else '',
                    node_id=self.value(element, 'node id') if element.field('node id') is not None else 0,
                    sequence_id=self.value(element, 'sequence id') if element.field('sequence id') is not None else 0))
            shots.append(records)
        return shots

    def dialogue_shots(self):
        shots = []
        for shot in self.block(self.tag.root(), 'shots'):
            records = []
            for element in self.block(shot, 'dialogue'):
                scale = self.value(element, 'scale')
                if not isfinite(scale):
                    raise ValueError('Non-finite cinematic dialogue scale')
                records.append(SimpleNamespace(
                    dialogue=self.reference(element, 'dialogue'),
                    female_dialogue=self.reference(element, 'female dialogue') if element.field('female dialogue') is not None else None,
                    frame=self.value(element, 'frame'), scale=scale,
                    actor=self.value(element, 'lipsync actor'),
                    default_sound_effect=self.value(element, 'default sound effect'),
                    subtitle=self.value(element, 'subtitle'),
                    female_subtitle=self.value(element, 'female subtitle') if element.field('female subtitle') is not None else '',
                    character=self.value(element, 'character') if element.field('character') is not None else ''))
            shots.append(records)
        return shots

    def camera_shots(self):
        shots = []
        for shot_index, shot in enumerate(self.block(self.tag.root(), 'shots')):
            frames = []
            for frame in self.block(shot, 'frame data'):
                camera = self.required_field(frame, 'camera frame').as_struct()
                dynamic = camera.field('dynamic data')
                constant = camera.field('constant data')
                dynamic = dynamic.as_struct() if dynamic is not None else camera
                constant = constant.as_struct() if constant is not None else camera
                position = tuple(self.value(dynamic, 'camera position').to_array())
                forward = tuple(self.value(dynamic, 'camera forward').to_array())
                up = tuple(self.value(dynamic, 'camera up').to_array())
                lens = self.value(constant, 'focal length')
                fov_field = constant.field('horizontal field of view')
                aperture_field = constant.field('horizontal film aperture')
                if not all(isfinite(v) for v in (*position, *forward, *up, lens)) or lens <= 0:
                    raise ValueError(f'Cinematic shot {shot_index}: invalid camera values')
                cross = tuple(forward[(i+1)%3]*up[(i+2)%3] - forward[(i+2)%3]*up[(i+1)%3] for i in range(3))
                if not any(cross):
                    raise ValueError(f'Cinematic shot {shot_index}: degenerate camera axes')
                dof = {}
                for key in ('depth of field', 'near focal plane distance', 'far focal plane distance',
                            'focal depth', 'blur amount', 'near focal depth', 'far focal depth',
                            'near blur amount', 'far blur amount'):
                    field = constant.field(key) or dynamic.field(key)
                    if field is not None:
                        dof['enabled' if key == 'depth of field' else key.replace(' ', '_')] = field.value
                frames.append(SimpleNamespace(position=position, forward=forward, up=up, lens=lens,
                    dof=dof,
                    horizontal_fov=fov_field.value if fov_field is not None else None,
                    film_aperture=aperture_field.value if aperture_field is not None else None))
            if not frames:
                raise ValueError(f'Cinematic shot {shot_index}: no camera frames')
            shots.append(frames)
        return shots


class CinematicSceneDataTag(BlenderTag, CinematicCameraDocument):
    tag_ext = 'cinematic_scene_data'

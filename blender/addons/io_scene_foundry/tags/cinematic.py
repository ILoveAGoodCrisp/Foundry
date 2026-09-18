"""Native cinematic camera and event records, detached from their tag handles."""
from math import isfinite
from types import SimpleNamespace
from .backend import TagDocument


class CinematicCameraDocument(TagDocument):
    def shot_frame_counts(self):
        counts = [self.value(shot, 'frame count') for shot in self.block(self.tag.root(), 'shots')]
        if any(count < 0 for count in counts):
            raise ValueError('Negative cinematic shot frame count')
        return counts

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
            records.append(SimpleNamespace(index=index, name=self.value(element, 'name'),
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
                if not all(isfinite(v) for v in (*position, *forward, *up, lens)) or lens <= 0:
                    raise ValueError(f'Cinematic shot {shot_index}: invalid camera values')
                cross = tuple(forward[(i+1)%3]*up[(i+2)%3] - forward[(i+2)%3]*up[(i+1)%3] for i in range(3))
                if not any(cross):
                    raise ValueError(f'Cinematic shot {shot_index}: degenerate camera axes')
                frames.append(SimpleNamespace(position=position, forward=forward, up=up, lens=lens))
            if not frames:
                raise ValueError(f'Cinematic shot {shot_index}: no camera frames')
            shots.append(frames)
        return shots

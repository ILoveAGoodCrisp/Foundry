"""Native cinematic camera records, detached from their tag handles."""
from math import isfinite
from types import SimpleNamespace
from .backend import TagDocument


class CinematicCameraDocument(TagDocument):
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

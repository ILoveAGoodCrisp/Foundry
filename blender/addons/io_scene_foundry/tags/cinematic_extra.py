"""Blender reconstruction of detached auxiliary camera tracks."""
from math import isfinite
import re

import bpy
from mathutils import Matrix, Vector

from .. import import_transform, utils
from .camera_track import camera_correction_matrix


def read_texture_camera_settings(scene, header):
    """Recognize literal feed settings while retaining the source script."""
    number = r'([0-9]+(?:\.[0-9]+)?)'
    aspect = re.findall(r'texture_camera_set_aspect_ratio\s*(?:\(\s*)?' + number, header)
    resolution = re.findall(r'texture_camera_set_resolution\s*(?:\(\s*)?' + number + r'[\s,]+' + number, header)
    if aspect and 0.1 <= float(aspect[-1]) <= 10:
        scene.nwo.texture_camera_aspect_ratio = float(aspect[-1])
    if resolution:
        width, height = map(float, resolution[-1])
        if 16 <= width <= 4096 and 16 <= height <= 4096:
            scene.nwo.texture_camera_resolution_x = int(width)
            scene.nwo.texture_camera_resolution_y = int(height)
    scene.nwo.texture_camera_override_settings = False


def _valid_frame(frame):
    return (all(isfinite(v) for v in (*frame.position, *frame.forward, *frame.up, frame.lens))
            and frame.lens > 0 and Vector(frame.forward).cross(Vector(frame.up)).length > 1e-8)


def import_extra_camera_tracks(scene, tracks, film_aperture, shot_starts, scene_nwo=None):
    """Return unlinked cameras/actions, as the main cinematic importer does."""
    cameras, actions = [], []
    scene.nwo.cinematic_extra_cameras.clear()
    scene_nwo = scene_nwo or utils.get_scene_props()
    for track in tracks:
        samples = [(start + offset, frame) for start, frames in zip(shot_starts, track.shots)
                   for offset, frame in enumerate(frames)]
        fallback = next((frame for _, frame in samples if _valid_frame(frame)), None)
        if fallback is None and any(frame.enabled for _, frame in samples):
            raise ValueError(f'Extra camera {track.name}: invalid active camera frames')
        data = bpy.data.cameras.new(f'{scene.name}_{track.name}')
        data.sensor_width = film_aperture * scene.nwo.texture_camera_aspect_ratio
        data.sensor_height = film_aperture
        data.sensor_fit = 'VERTICAL'
        data.clip_end = 100000
        camera = bpy.data.objects.new(data.name, data)
        camera.rotation_mode = 'QUATERNION'
        item = scene.nwo.cinematic_extra_cameras.add()
        item.name, item.camera, item.camera_type = track.name, camera, track.camera_type
        cameras.append(camera)
        for owner, id_type, properties in (
                (camera, 'OBJECT', [('location', 3), ('rotation_quaternion', 4), ('nwo.cinematic_extra_camera_enabled', 1)]),
                (data, 'CAMERA', [('lens', 1)])):
            action = bpy.data.actions.new(owner.name + ('_data' if id_type == 'CAMERA' else ''))
            slot = action.slots.new(id_type, owner.name)
            owner.animation_data_create()
            owner.animation_data.action = action
            owner.animation_data.last_slot_identifier = slot.identifier
            actions.append(action)
            curves = utils.get_fcurves(action, slot)
            for path, count in properties:
                for index in range(count):
                    curves.new(data_path=path, index=index)
        object_curves = utils.get_fcurves(camera.animation_data.action, camera.animation_data.action_slot)
        lens_curve = utils.get_fcurves(data.animation_data.action, data.animation_data.action_slot).find('lens')
        previous_rotation = None
        for frame_number, raw in samples:
            frame = raw
            if not _valid_frame(frame):
                if frame.enabled:
                    raise ValueError(f'Extra camera {track.name}: invalid active frame {frame_number}')
                frame = fallback
            if frame is not None:
                fallback = frame
                forward, up = Vector(frame.forward).normalized(), Vector(frame.up).normalized()
                left = up.cross(forward).normalized()
                position = Vector(frame.position) * 100
                matrix = Matrix(((forward.x, left.x, up.x, position.x),
                                 (forward.y, left.y, up.y, position.y),
                                 (forward.z, left.z, up.z, position.z), (0, 0, 0, 1)))
                matrix = import_transform.object_matrix(matrix @ camera_correction_matrix.to_4x4(), scene_nwo)
                location, rotation, _ = matrix.decompose()
                if previous_rotation is not None and previous_rotation.dot(rotation) < 0:
                    rotation.negate()
                previous_rotation = rotation.copy()
                camera.location, camera.rotation_quaternion = location, rotation
                data.lens = frame.lens
            camera.nwo.cinematic_extra_camera_enabled = raw.enabled
            for path, values in (('location', camera.location), ('rotation_quaternion', camera.rotation_quaternion),
                                 ('nwo.cinematic_extra_camera_enabled', [float(raw.enabled)])):
                for index, value in enumerate(values):
                    key = object_curves.find(path, index=index).keyframe_points.insert(frame_number, value, options={'FAST'})
                    key.interpolation = 'CONSTANT' if path.endswith('enabled') else 'LINEAR'
            lens_curve.keyframe_points.insert(frame_number, data.lens, options={'FAST'}).interpolation = 'LINEAR'
        for owner in (camera, data):
            for curve in utils.get_fcurves(owner.animation_data.action, owner.animation_data.action_slot):
                curve.update()
    return cameras, actions

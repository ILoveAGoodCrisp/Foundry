

from math import radians
import bpy
import os
from mathutils import Matrix, Quaternion, Vector
from ..tags.backend import CameraTrackDocument
from .. import utils
from . import import_transform

#  This matrix corrects for the camera's forward direction
camera_correction_matrix = Matrix(((-0, 0, -1), (-1, -0, 0), (-0, 1, 0)))

class ControlPoint:
    pi: float
    pj: float
    pk: float
    
    oi: float
    oj: float
    ok: float
    ow: float
    
    def __init__(self, index):
        self.index = index
        
    def orientation_to_wxyz(self) -> list:
        return [self.ow, self.oi, self.oj, self.ok]
    
    def position_to_xyz(self) -> list:
        return [self.pi, self.pj, self.pk]
    
    def set_ijk_from_location(self, location: Vector):
        self.pi = location[0]
        self.pj = location[1]
        self.pk = location[2]
        
    def set_ijkw_from_rotation(self, rotation: Quaternion):
        self.oi = rotation[1]
        self.oj = rotation[2]
        self.ok = rotation[3]
        self.ow = rotation[0]
        
class CameraTrackTag(CameraTrackDocument):
    tag_ext = 'camera_track'
    
    def __init__(self, path="", *, tag_must_exist=False, always_save=False):
        self.scene_nwo = utils.get_scene_props()
        project = utils.get_project(self.scene_nwo.scene_project)
        if project is None:
            raise RuntimeError('Select a Halo project before opening a camera track')
        if not path:
            asset = utils.get_asset_path()
            path = os.path.join(asset, os.path.basename(asset) + '.camera_track')
        super().__init__(path, tags_root=utils.get_tags_path(), game=project.game,
                         must_exist=tag_must_exist, always_save=always_save)
        
    def get_control_points(self) -> list[ControlPoint]:
        control_points = []
        for index, (position, orientation) in enumerate(self.control_points()):
            control_point = ControlPoint(index)
            control_point.pi, control_point.pj, control_point.pk = position
            control_point.oi, control_point.oj, control_point.ok, control_point.ow = orientation
            control_points.append(control_point)
            
        return control_points
    
    def to_blender_animation(self, context: bpy.types.Context, animation_scale=1):
        control_points = self.get_control_points()
        if not control_points:
            raise ValueError(f'Camera track has no control points: {self.path}')
        track_name = os.path.splitext(os.path.basename(self.path))[0]
        camera_ob = utils.get_camera_track_camera(context)
        if camera_ob is None:
            camera_name = 'camera_' + track_name
            camera_data = bpy.data.cameras.new(camera_name)
            camera_ob = bpy.data.objects.new('camera', camera_data)
            context.scene.collection.objects.link(camera_ob)
            camera_ob.rotation_euler = [radians(90), 0, radians(-90)]
        action = bpy.data.actions.new(track_name)
        if not camera_ob.animation_data:
            camera_ob.animation_data_create()
        camera_ob.data.display_size = 50 * import_transform.scale_factor()
        camera_ob.data.clip_end = 1000
        camera_ob.animation_data.action = action
        
        for idx, control_point in enumerate(control_points):
            loc = Vector(control_point.position_to_xyz()) * 100
            game_orientation_matrix = Quaternion(control_point.orientation_to_wxyz()).to_matrix()
            final_matrix = game_orientation_matrix @ camera_correction_matrix
            rot = final_matrix.to_quaternion()
            camera_ob.rotation_mode = 'QUATERNION'
            camera_ob.matrix_world = import_transform.object_matrix(Matrix.LocRotScale(loc, rot, Vector.Fill(3, 1)))
            camera_ob.keyframe_insert(data_path='rotation_quaternion', frame=idx + 1)
            camera_ob.keyframe_insert(data_path='location', frame=idx + 1)
            
        action.use_fake_user = True
        action.use_frame_range = True
        action.frame_start = 1
        action.frame_end = (idx + 1) * animation_scale - animation_scale + 1 
            
        if animation_scale > 1:
            fcurves = utils.get_fcurves(action, camera_ob)
            for idx, fcurve in enumerate(fcurves):
                for kfp in fcurve.keyframe_points:
                    kfp.co_ui.x *= animation_scale
                    kfp.co_ui.x  -= animation_scale - 1 
                    kfp.interpolation = 'BEZIER'
                    kfp.easing = 'AUTO'
                    
        animation = self.scene_nwo.animations.add()
        animation.name = action.name
        animation.frame_start = int(action.frame_start)
        animation.frame_end = int(action.frame_end)
        track = animation.action_tracks.add()
        track.object = camera_ob
        track.action = action
        
        return camera_ob, action

    def to_tag(self, context: bpy.types.Context, animation, ob: bpy.types.Object):
        current_frame = int(context.scene.frame_current)
        # verify no. of fcurves, must be 16 or less
        scene = context.scene
        if animation.frame_end - animation.frame_start > 15:
            utils.print_warning("Camera animation has more than 16 frames. Only using the first 16 frames for camera track")
        control_points = []
        frame = animation.frame_start
        idx = 0
        try:
            while frame <= animation.frame_end and idx < 16:
                scene.frame_set(frame)
                control_point = ControlPoint(idx)
                matrix = utils.halo_transforms_matrix(ob.matrix_world)
                loc, rot, _ = matrix.decompose()
                control_point.set_ijk_from_location(loc)
                blender_orientation_matrix = rot.to_matrix()
                camera_matrix_fixed = blender_orientation_matrix @ camera_correction_matrix.inverted_safe()
                control_point.set_ijkw_from_rotation(camera_matrix_fixed.to_quaternion())
                control_points.append(control_point)
                frame += 1
                idx += 1
            self.replace_control_points([(cp.position_to_xyz(), (cp.oi, cp.oj, cp.ok, cp.ow))
                                         for cp in control_points])
        finally:
            scene.frame_set(current_frame)

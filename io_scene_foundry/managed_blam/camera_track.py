# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

from math import radians
import bpy
from mathutils import Matrix, Quaternion, Vector, Euler
from io_scene_foundry.managed_blam import Tag
from io_scene_foundry.utils import nwo_utils

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

class CameraTrackTag(Tag):
    tag_ext = 'camera_track'
    
    def _read_fields(self):
        self.block_control_points = self.tag.SelectField('Block:control points')
        
    def get_control_points(self) -> list[ControlPoint]:
        control_points = []
        for element in self.block_control_points.Elements:
            control_point = ControlPoint(element.ElementIndex)
            control_point.pi, control_point.pj, control_point.pk = [float(n) for n in element.Fields[0].GetStringData()]
            control_point.oi, control_point.oj, control_point.ok, control_point.ow = [float(n) for n in element.Fields[1].GetStringData()]
            control_points.append(control_point)
            
        return control_points
    
    def to_blender_animation(self, context: bpy.types.Context, animation_scale=1):
        scene_nwo = context.scene.nwo
        control_points = self.get_control_points()
        # arm_data = bpy.data.armatures.new('camera_track')
        # arm_ob = bpy.data.objects.new('camera_track', arm_data)
        # context.scene.collection.objects.link(arm_ob)
        # context.view_layer.objects.active = arm_ob
        # bpy.ops.object.editmode_toggle()
        # bone_name = 'camera_bone'
        # pedestal = arm_data.edit_bones.new(bone_name)
        # pedestal.head = [0, 0, 0]
        # pedestal.tail = [0, 1, 0]
        # bpy.ops.object.editmode_toggle()
        camera_data = bpy.data.cameras.new('camera')
        camera_ob = bpy.data.objects.new('camera', camera_data)
        context.scene.collection.objects.link(camera_ob)
        camera_ob.rotation_euler = [radians(90), 0, radians(-90)]
        camera_data.display_size = 50
        camera_data.clip_end = 1000
        action = bpy.data.actions.new('camera_track')
        camera_ob.animation_data_create().action = action
        for idx, control_point in enumerate(control_points):
            loc = Vector(control_point.position_to_xyz()) * 100
            game_orientation_matrix = Quaternion(control_point.orientation_to_wxyz()).to_matrix()
            final_matrix = game_orientation_matrix @ camera_correction_matrix
            rot = final_matrix.to_quaternion()
            camera_ob.rotation_mode = 'QUATERNION'
            camera_ob.matrix_world = Matrix.LocRotScale(loc, rot, Vector.Fill(3, 1))
            camera_ob.keyframe_insert(data_path='rotation_quaternion', frame=idx + 1)
            camera_ob.keyframe_insert(data_path='location', frame=idx + 1)
            
        action.use_fake_user = True
        action.use_frame_range = True
        action.frame_start = 1
        action.frame_end = (idx + 1) * animation_scale - animation_scale + 1 
            
        if animation_scale > 1:
            for idx, fcurve in enumerate(action.fcurves):
                for kfp in fcurve.keyframe_points:
                    kfp.co_ui.x *= animation_scale
                    kfp.co_ui.x  -= animation_scale - 1 
                    kfp.interpolation = 'BEZIER'
                    kfp.easing = 'AUTO'
        
        return [camera_ob]

    def to_camera_track(self):
        pass
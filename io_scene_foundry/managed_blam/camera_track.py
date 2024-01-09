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
from io_scene_foundry.managed_blam import Tag

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
    
    def to_blender_animation(self, context: bpy.types.Context):
        control_points = self.get_control_points()
        arm_data = bpy.data.armatures.new('camera_track')
        arm_ob = bpy.data.objects.new('camera_track', arm_data)
        context.scene.collection.objects.link(arm_ob)
        context.view_layer.objects.active = arm_ob
        bpy.ops.object.editmode_toggle()
        pedestal = arm_data.edit_bones.new('b_pedestal')
        tail_scale = 1 if context.scene.nwo.scale == 'max' else 0.03048
        pedestal.head = [0, 0, 0]
        pedestal.tail = [0, tail_scale, 0]
        bpy.ops.object.editmode_toggle()
        camera_data = bpy.data.cameras.new('camera')
        camera_ob = bpy.data.objects.new('camera', camera_data)
        context.scene.collection.objects.link(camera_ob)
        camera_ob.rotation_euler = [radians(90), 0, radians(-90)]
        camera_data.display_size *= (1 / 0.03048)
        camera_con = camera_ob.constraints.new('CHILD_OF')
        camera_con.target = arm_ob
        camera_con.subtarget = 'b_pedestal'
        action = bpy.data.actions.new('camera_track')
        arm_ob.animation_data_create().action = action
        bpy.ops.object.posemode_toggle()
        pose_bone = arm_ob.pose.bones.get('b_pedestal')
        for idx, control_point in enumerate(control_points):
            pose_bone.location = control_point.position_to_xyz()
            pose_bone.location *=  100
            pose_bone.rotation_quaternion = control_point.orientation_to_wxyz()
            pose_bone.keyframe_insert(data_path='rotation_quaternion', frame=idx + 1, group='b_pedestal')
            pose_bone.keyframe_insert(data_path='location', frame=idx + 1, group='b_pedestal')
            
        
        
    def to_camera_track(self):
        pass
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
import os
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
    
    def set_ijk_from_location(self, location: Vector):
        self.pi = location[0]
        self.pj = location[1]
        self.pk = location[2]
        
    def set_ijkw_from_rotation(self, rotation: Quaternion):
        self.oi = rotation[1]
        self.oj = rotation[2]
        self.ok = rotation[3]
        self.ow = rotation[0]
        
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
        control_points = self.get_control_points()
        track_name = os.path.basename(nwo_utils.dot_partition(self.tag_path.ToString()))
        camera_ob = nwo_utils.get_camera_track_camera(context)
        if camera_ob is None:
            camera_name = 'camera_' + track_name
            camera_data = bpy.data.cameras.new(camera_name)
            camera_ob = bpy.data.objects.new('camera', camera_data)
            context.scene.collection.objects.link(camera_ob)
            camera_ob.rotation_euler = [radians(90), 0, radians(-90)]
            camera_data.display_size = 50
            camera_data.clip_end = 1000
        action = bpy.data.actions.new(track_name)
        if not camera_ob.animation_data:
            camera_ob.animation_data_create()
        camera_ob.animation_data.action = action
        
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
        
        return camera_ob

    def to_tag(self, context: bpy.types.Context, action: bpy.types.Action, ob: bpy.types.Object):
        current_frame = int(context.scene.frame_current)
        # verify no. of fcurves, must be 16 or less
        scene = context.scene
        fcurves = [fc for fc in action.fcurves]
            
        keyframes = [[],[],[],[],[],[],[],[],[],[],[],[],[],[],[],[]]
            
        for fc in fcurves:
            if fc.data_path.endswith(('location', 'rotation_euler', 'rotation_quaternion')):
                for idx, kfp in enumerate(fc.keyframe_points):
                    if idx > 15:
                        nwo_utils.print_warning(f"Camera track action fcurve ({action.name}, {fc.data_path}[{fc.array_index}]) has more than 16 keyframes. Only using the first 16 to write camera_track tag")
                        break
                    keyframes[idx].append(kfp)
                    
        valid_keyframes = [k for k in keyframes if len(k) > 1]
        control_points = []
        for idx, k in enumerate(valid_keyframes):
            frame = int(k[0].co[0])
            scene.frame_set(frame)
            control_point = ControlPoint(idx)
            loc = ob.location / 100
            control_point.set_ijk_from_location(loc)
            
            if ob.rotation_mode == 'EULER':
                rotation = ob.rotation_euler.to_quaternion()
            else:
                rotation = ob.rotation_quaternion
                
            blender_orientation_matrix = rotation.to_matrix()
            camera_matrix_fixed = blender_orientation_matrix @ camera_correction_matrix.inverted()
            control_point.set_ijkw_from_rotation(camera_matrix_fixed.to_quaternion())
            
            control_points.append(control_point)
        
        if self.block_control_points.Elements.Count:
            self.block_control_points.RemoveAllElements()
        
        for cp in control_points:
            e = self.block_control_points.AddElement()
            e.Fields[0].SetStringData([str(cp.pi), str(cp.pj), str(cp.pk)])
            e.Fields[1].SetStringData([str(cp.oi), str(cp.oj), str(cp.ok), str(cp.ow)])
            
        self.tag_has_changes = True
        
        context.scene.frame_current = current_frame
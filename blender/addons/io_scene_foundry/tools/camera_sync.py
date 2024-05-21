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

import math
import struct
import time
import bpy
from mathutils import Vector
import numpy as np
from io_scene_foundry.utils.nwo_constants import WU_SCALAR
from io_scene_foundry.utils import nwo_utils
import pymem

class NWO_OT_CameraSync(bpy.types.Operator):
    bl_idname = "nwo.camera_sync"
    bl_label = "Camera Sync"
    bl_description = ""
    bl_options = {'REGISTER'}
    
    cancel_sync: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return nwo_utils.valid_nwo_asset(context)
    
    def execute(self, context):
        if self.cancel_sync:
            context.scene.nwo.camera_sync_active = False
            return {'CANCELLED'}
        context.scene.nwo.camera_sync_active = True
        wm = context.window_manager
        self.timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        nwo = context.scene.nwo
        if not nwo.camera_sync_active:
            return self.cancel(context)
        if event.type == 'TIMER':
            if context.space_data and context.space_data.type == 'VIEW_3D':
                sync_camera_to_game(context)
                return {'PASS_THROUGH'}
                
        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self.timer)
        return {'FINISHED'}
    
def resolve_pointer_chain(pm, base, offsets):
    addr = pm.read_int(base)
    for offset in offsets[:-1]:
        addr = pm.read_int(addr + offset)
    return addr + offsets[-1]

def write_rot(pm, address, floats):
    byte_array = struct.pack('3f', *floats)
    pm.write_bytes(address, byte_array, len(byte_array))
    
def write_loc(pm, address, floats):
    byte_array = struct.pack('3f', *floats)
    pm.write_bytes(address, byte_array, len(byte_array))
    
def quaternion_to_euler(q):
    """
    Convert a quaternion into euler angles (yaw, pitch, roll)
    yaw is the rotation around the z axis
    pitch is the rotation around the y axis
    roll is the rotation around the x axis
    """
    w, x, y, z = q.w, q.x, q.y, q.z
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    pitch = math.atan2(t0, t1)

    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    roll = math.asin(t2)

    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(t3, t4)

    return yaw, pitch, roll
    
def sync_camera_to_game(context: bpy.types.Context):
    scale = 1
    if context.scene.nwo.scale == 'max':
        scale = 0.03048
        
    r3d = context.space_data.region_3d
    # matrix = nwo_utils.halo_transform_matrix(view_matrix)
    matrix = r3d.view_matrix
    location = matrix.inverted().translation * WU_SCALAR
    yaw, pitch, roll = quaternion_to_euler(r3d.view_rotation)
    
    in_camera = r3d.view_perspective == 'CAMERA' and context.scene.camera
    if not in_camera:
        roll = 0
    
    print(location, "location")
    print(yaw, pitch, roll)
    pm = pymem.Pymem('reach_tag_test.exe')
    base = pymem.process.module_from_name(pm.process_handle, 'reach_tag_test.exe').lpBaseOfDll + 0x01D2C0A0

    offsets_loc = [0xA8, 0x568, 0x2C4, 0x58, 0x28]
    loc_address = resolve_pointer_chain(pm, base, offsets_loc)
    
    offsets_rot = [0xA8, 0x568, 0x1D4, 0x2C]
    rot_address = resolve_pointer_chain(pm, base, offsets_rot)
    
    write_loc(pm, loc_address, (location[0], location[1], location[2]))
    write_rot(pm, rot_address, (yaw + math.radians(90), pitch - math.radians(90), roll))
    
    if in_camera:
        fov = np.median([math.degrees(context.scene.camera.data.angle), 1, 150])
        pm.write_float(0x141EFA350, fov)


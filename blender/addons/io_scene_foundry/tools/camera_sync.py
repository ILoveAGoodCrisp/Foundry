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

import ctypes
import math
from pathlib import Path
import struct
import subprocess
import sys
import bpy
import numpy as np
from io_scene_foundry.utils import nwo_utils
pymem_installed = False
try:
    import pymem
    pymem_installed = True
except:
    pass

r90 = math.radians(90)

class NWO_OT_CameraSync(bpy.types.Operator):
    bl_idname = "nwo.camera_sync"
    bl_label = "Camera Sync"
    bl_description = "Syncs the in game camera with the Blender viewport camera."
    bl_options = {'REGISTER'}
    
    cancel_sync: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    # @classmethod
    # def poll(cls, context):
    #     return nwo_utils.valid_nwo_asset(context)
    
    def execute(self, context):
        if self.cancel_sync:
            context.scene.nwo.camera_sync_active = False
            return {'CANCELLED'}
        if not pymem_installed:
            pymem_install()
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
                try:
                    sync_camera_to_game(context)
                except:
                    pass
                return {'PASS_THROUGH'}
                
        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self.timer)
    
    @classmethod
    def description(cls, context, properties) -> str:
        desc = "Syncs the in game camera with the Blender viewport camera\n\nHow to Use:\n"
        if nwo_utils.is_corinth(context):
            desc += "Ensure Sapien is running (do not use the sapien_play)\nPress this button while in control of the editor camera to let Blender take control"
        else:
            desc += "Ensure TagTest is running (do not use tag_play)\nIn the in game console enter 'DisablePauseOnDefocus 1'. This will allow the game to run when the game window is not in focus\nPress this button while in control of the director camera to let Blender take control. To switch from the player camera to director camera press BACKSPACE"
        
        return desc
    
def resolve_pointer_chain(pm, base, offsets):
    addr = pm.read_int(base)
    for offset in offsets[:-1]:
        addr = pm.read_int(addr + offset)
    return addr + offsets[-1]

def write_rot(pm, address, floats):
    byte_array = struct.pack('3f', *floats)
    pm.write_bytes(address, byte_array, len(byte_array))
    
def write_camera(pm, address, floats):
    byte_array = struct.pack('6f', *floats)
    pm.write_bytes(address, byte_array, len(byte_array))
    
def quaternion_to_ypr(q):
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

def sync_reach_tag_test(pm, exe_name, location, yaw, pitch, roll, in_camera, context, default_fov=78.0):
    base = pymem.process.module_from_name(pm.process_handle, exe_name).lpBaseOfDll
    try:
        camera_address = resolve_pointer_chain(pm, base + 0x01D2C0A0, [0xA8, 0x568, 0x2C4, 0x58, 0x28])
        write_camera(pm, camera_address, (location[0], location[1], location[2], yaw + r90, pitch - r90, roll))
    except:
        try:
            camera_address = resolve_pointer_chain(pm, base + 0x01431D6C, [0x468, 0x0, 0x5F0, 0x58, 0x28])
            write_camera(pm, camera_address, (location[0], location[1], location[2], yaw + r90, pitch - r90, roll))
        except:
            pass
    
    if in_camera:
        fov = np.median([math.degrees(context.scene.camera.data.angle), 1, 150])
        pm.write_float(0x141EFA350, fov)
    else:
        pm.write_float(0x141EFA350, default_fov)
    
def sync_corinth_sapien(pm, exe_name, location, yaw, pitch, roll, in_camera, context, default_fov=78.0):
    base = pymem.process.module_from_name(pm.process_handle, exe_name).lpBaseOfDll + 0x0227F5C0
    camera_address = resolve_pointer_chain(pm, base, [0x1A0, 0x8, 0x20])
    write_camera(pm, camera_address, (location[0], location[1], location[2], yaw + r90, pitch - r90, roll))
    if in_camera:
        fov = np.median([math.degrees(context.scene.camera.data.angle), 1, 150])
        pm.write_float(0x1425F5A50, fov)
    else:
        pm.write_float(0x1425F5A50, default_fov)

    
def sync_camera_to_game(context: bpy.types.Context):
    import pymem
    r3d = context.space_data.region_3d
    # matrix = nwo_utils.halo_transform_matrix(view_matrix)
    matrix = nwo_utils.halo_transform_matrix(r3d.view_matrix.inverted())
    location = matrix.translation
    yaw, pitch, roll = quaternion_to_ypr(matrix.to_quaternion())
    in_camera = r3d.view_perspective == 'CAMERA' and context.scene.camera
    if not in_camera:
        roll = 0
    
    # print(location, "location")
    # print(roll)
    exe_name = ""
    if nwo_utils.is_corinth(context):
        exe_name = Path(nwo_utils.get_exe("sapien")).name
        sync_corinth_sapien(pymem.Pymem(exe_name), exe_name, location, yaw, pitch, roll, in_camera, context)
    else:
        exe_name = Path(nwo_utils.get_exe("tag_test")).name
        sync_reach_tag_test(pymem.Pymem(exe_name), exe_name, location, yaw, pitch, roll, in_camera, context)
                
                
# pymem install handler
def pymem_install():
    print("Couldn't find pymem module, attempting pymem install")
    install = ctypes.windll.user32.MessageBoxW(
        0,
        "Camera Sync requires the pymem module to be installed for Blender.\n\nInstall pymem now?",
        f"Pymem Install Required",
        4,
    )
    if install != 6:
        return {"CANCELLED"}
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--ignore-installed", "pymem"])
        print("Succesfully installed necessary modules")

        shutdown = ctypes.windll.user32.MessageBoxW(
            0,
            "Pymem module installed for Blender. Please restart Blender to use Camera Sync.\n\nRestart Blender now?",
            f"Pymem Installed for Blender",
            4,
        )
        if shutdown != 6:
            return {"CANCELLED"}
        
        nwo_utils.restart_blender()

    except:
        print("Failed to install pymem")
        return {"CANCELLED"}

    



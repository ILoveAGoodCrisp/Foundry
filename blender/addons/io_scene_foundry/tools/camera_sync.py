

import ctypes
import math
from pathlib import Path
import struct
import subprocess
import sys
import bpy
import numpy as np
from .. import utils

pymem_installed = False
try:
    import pymem
    pymem_installed = True
except:
    pass

r90 = math.radians(90)

pm = None
base = None

class NWO_OT_CameraSync(bpy.types.Operator):
    bl_idname = "nwo.camera_sync"
    bl_label = "Camera Sync"
    bl_description = "Syncs the in game camera with the Blender viewport camera."
    bl_options = {'REGISTER'}
    
    cancel_sync: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    # @classmethod
    # def poll(cls, context):
    #     return utils.valid_nwo_asset(context)
    
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
                # try:
                sync_camera_to_game(context)
                # except:
                #     pass
                return {'PASS_THROUGH'}
                
        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self.timer)
        global pm
        global base
        pm = None
        base = None
        
        return {'CANCELLED'}
    
    @classmethod
    def description(cls, context, properties) -> str:
        desc = "Syncs the in game camera with the Blender viewport camera\n\nHow to Use:\n"
        if utils.is_corinth(context):
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

def sync_reach_tag_test(location, yaw, pitch, roll, in_camera, context):
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
    else:
        fov = np.median([math.degrees(2 * math.atan(74 /(2 * context.space_data.lens))), 1, 150])
        
    pm.write_float(0x141EFA350, fov)
    
def sync_corinth_sapien(location, yaw, pitch, roll, in_camera, context):
    camera_address = resolve_pointer_chain(pm, base, [0x1A0, 0x8, 0x20])
    write_camera(pm, camera_address, (location[0], location[1], location[2], yaw + r90, pitch - r90, roll))
    if in_camera:
        fov = np.median([math.degrees(context.scene.camera.data.angle), 1, 150])
    else:
        fov = np.median([math.degrees(2 * math.atan(36 /(2 * context.space_data.lens))), 1, 150])
        
    pm.write_float(0x1425F5A50, fov)
    
def sync_camera_to_game(context: bpy.types.Context):
    r3d = context.space_data.region_3d
    # matrix = utils.halo_transform_matrix(view_matrix)
    matrix = utils.halo_transform_matrix(r3d.view_matrix.inverted_safe())
    location = [round(t, 3) for t in matrix.translation]
    yaw, pitch, roll = utils.quaternion_to_ypr(matrix.to_quaternion())
    in_camera = r3d.view_perspective == 'CAMERA' and context.scene.camera
    if not in_camera:
        roll = 0
    
    # print(location, "location")
    # print(roll)
    exe_name = ""
    global pm
    global base
    if utils.is_corinth(context):
        exe_name = Path(utils.get_exe("sapien")).name
        if not base:
            pm = pymem.Pymem(exe_name)
            base = pymem.process.module_from_name(pm.process_handle, exe_name).lpBaseOfDll + 0x0227F5C0
        sync_corinth_sapien(location, yaw, pitch, roll, in_camera, context)
    else:
        exe_name = Path(utils.get_exe("tag_test")).name
        if not base:
            pm = pymem.Pymem(exe_name)
            base = pymem.process.module_from_name(pm.process_handle, exe_name).lpBaseOfDll
        sync_reach_tag_test(location, yaw, pitch, roll, in_camera, context)
                
                
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
    
    py_exe = sys.executable
    python_dir = Path(py_exe).parent.parent
    site_packages = Path(python_dir, "lib", "site-packages")
    test_file = Path(site_packages, "foundry_test.txt")
    try:
        # check if folder writable
        with open(test_file, mode="w") as _: pass
        test_file.unlink(missing_ok=True)
    except:
        shutdown = ctypes.windll.user32.MessageBoxW(
            0,
            "Blender does not have sufficient privilege to install new python modules. Launch Blender with admin priviledges and re-attempt install\n\nQuit Blender now?",
            f"Could not install python module",
            4,
        )
        if shutdown != 6:
            return {"CANCELLED"}
        
        bpy.ops.wm.quit_blender()
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
        
        utils.restart_blender()

    except:
        print("Failed to install pymem")
        return {"CANCELLED"}

    



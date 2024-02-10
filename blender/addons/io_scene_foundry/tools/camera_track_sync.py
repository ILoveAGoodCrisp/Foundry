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

import os
import bpy
from io_scene_foundry.utils import nwo_utils
from io_scene_foundry.managed_blam.camera_track import CameraTrackTag

def export_current_action_as_camera_track(context):
    print("Running export!")
    camera = nwo_utils.get_camera_track_camera(context)
    action = camera.animation_data.action
    asset_path = nwo_utils.get_asset_path()
    tag_path = os.path.join(asset_path, action.name + '.camera_track')
    
    with CameraTrackTag(path=tag_path) as camera_track:
        print(tag_path)
        camera_track.to_tag(context, action, camera)

class NWO_CameraTrackSync(bpy.types.Operator):
    bl_idname = "nwo.camera_track_sync"
    bl_label = "Camera Track Sync"
    bl_description = "Updates the camera track tag on new keyframes"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        camera = nwo_utils.get_camera_track_camera(context)
        return camera and camera.animation_data and camera.animation_data.action and nwo_utils.valid_nwo_asset(context)
    
    def execute(self, context):
        if context.scene.nwo.camera_track_syncing:
            self.cancel(context)
            return {'FINISHED'}
        camera = nwo_utils.get_camera_track_camera(context)
        self.action = camera.animation_data.action
        
        self.kfp_coords = []
        for fc in self.action.fcurves:
            for kfp in fc.keyframe_points:
                self.kfp_coords.extend(kfp.co)
                
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        context.scene.nwo.camera_track_syncing = True
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type_prev == 'ESC' or not context.scene.nwo.camera_track_syncing:
            self.cancel(context)
            return {'CANCELLED'}
        
        new_coords = []
        for fc in self.action.fcurves:
            for kfp in fc.keyframe_points:
                new_coords.extend(kfp.co)
                
        if event.type == 'TIMER' and self.kfp_coords != new_coords:
            self.kfp_coords = new_coords
            export_current_action_as_camera_track(context)

        return {'PASS_THROUGH'}
    
    def cancel(self, context):
        context.scene.nwo.camera_track_syncing = False

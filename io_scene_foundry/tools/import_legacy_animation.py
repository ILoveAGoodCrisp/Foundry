# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
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
from io_scene_halo.file_jma.import_jma import load_file

pose_hints = ['aim', 'look', 'acc', 'steer']

def import_legacy_animations(context, filepaths, report):
    """Imports all legacy animation files supplied"""
    for path in filepaths:
        import_legacy_animation(context, path, report)
        
    
def import_legacy_animation(context, filepath, report):
    load_file(context, filepath, 'halo3', False, False, "", "", report)
    filename = os.path.basename(filepath)
    anim_name, extension = filename.split('.')
    anim = bpy.data.actions.get(anim_name, 0)
    nwo = anim.nwo
    if anim:
        anim.use_fake_user = True
        anim.use_frame_range = True
        match extension.lower():
            case 'jmm':
                nwo.animation_type = 'base'
                nwo.animation_movement_data = 'none'
            case 'jma':
                nwo.animation_type = 'base'
                nwo.animation_movement_data = 'xy'
            case 'jmt':
                nwo.animation_type = 'base'
                nwo.animation_movement_data = 'xyyaw'
            case 'jmz':
                nwo.animation_type = 'base'
                nwo.animation_movement_data = 'xyzyaw'
            case 'jmv':
                nwo.animation_type = 'base'
                nwo.animation_movement_data = 'full'
            case 'jmw':
                nwo.animation_type = 'world'
            case 'jmo':
                nwo.animation_type = 'overlay'
                nwo.animation_is_pose = any(hint in anim_name.lower() for hint in pose_hints)
            case 'jmr':
                nwo.animation_type = 'replacement'
            case 'jmrx':
                nwo.animation_type = 'replacement'
                nwo.animation_space = 'local'
 

    
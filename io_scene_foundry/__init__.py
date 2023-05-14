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

# Don't edit the version or build version here or it will break CI
# Need to do this because of Blender parsing the plugin init code instead of actually executing it when getting bl_info

import ctypes
import bpy
from bpy.types import AddonPreferences, Operator
from bpy.props import StringProperty, EnumProperty, BoolProperty
from bpy.app.handlers import persistent
import os

from io_scene_foundry.utils.nwo_utils import formalise_game_version, get_ek_path, managed_blam_active, valid_nwo_asset

bl_info = {
    "name": "Foundry - Halo Blender Creation Kit",
    "author": "Crisp",
    "version": (117, 343, 65521),
    "blender": (3, 5, 0),
    "location": "File > Export",
    "description": "Asset Exporter and Toolset for Halo Reach, Halo 4, and Halo 2 Aniversary Multiplayer: BUILD_VERSION_STR",
    "warning": "",
    # "wiki_url": "",
    "support": 'COMMUNITY',
    "category": "Export"}

from . import icons
from . import tools
from . import ui
from . import export
from . import managed_blam


modules = [
    icons,
    tools,
    managed_blam,
    ui,
    export,
]

class HREKLocationPath(Operator):
    """Set the path to your Halo Reach Editing Kit"""
    bl_idname = "nwo.hrek_path"
    bl_label = "Find"
    bl_options = {'REGISTER'}

    filter_folder: BoolProperty(
        default=True, 
        options={'HIDDEN'},
    )

    directory: StringProperty(
        name="hrek_path",
        description="Set the path to your Halo Reach Editing Kit",
    )

    def execute(self, context):
        context.preferences.addons[__package__].preferences.hrek_path = self.directory.strip('"\\')

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class H4EKLocationPath(Operator):
    """Set the path to your Halo 4 Editing Kit"""
    bl_idname = "nwo.h4ek_path"
    bl_label = "Find"
    bl_options = {'REGISTER'}

    filter_folder: BoolProperty(
        default=True, 
        options={'HIDDEN'},
    )

    directory: StringProperty(
        name="h4ek_path",
        description="Set the path to your Halo 4 Editing Kit",
    )

    def execute(self, context):
        context.preferences.addons[__package__].preferences.h4ek_path = self.directory.strip('"\\')

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}

class H2AMPEKLocationPath(Operator):
    """Set the path to your Halo 2 Anniversary Multiplayer Editing Kit"""
    bl_idname = "nwo.h2aek_path"
    bl_label = "Find"
    bl_options = {'REGISTER'}

    filter_folder: BoolProperty(
        default=True, 
        options={'HIDDEN'},
    )

    directory: StringProperty(
        name="h2aek_path",
        description="Set the path to your Halo 2 Anniversary Multiplayer Editing Kit",
    )

    def execute(self, context):
        context.preferences.addons[__package__].preferences.h2aek_path = self.directory.strip('"\\')

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {'RUNNING_MODAL'}
 
class ToolkitLocationPreferences(AddonPreferences):
    bl_idname = __package__

    def clean_hrek_path(self, context):
        self['hrek_path'] = self['hrek_path'].strip('"\\')
        
    
    hrek_path: StringProperty(
        name="HREK Path",
        description="Specify the path to your Halo Reach Editing Kit folder containing tool / tool_fast",
        default="",
        update=clean_hrek_path,
    )

    def clean_h4ek_path(self, context):
        self['h4ek_path'] = self['h4ek_path'].strip('"\\')

    h4ek_path: StringProperty(
        name="H4EK Path",
        description="Specify the path to your Halo 4 Editing Kit folder containing tool / tool_fast",
        default="",
        update=clean_h4ek_path,
    )

    def clean_h2aek_path(self, context):
        self['h2aek_path'] = self['h2aek_path'].strip('"\\')

    h2aek_path: StringProperty(
        name="H2AMPEK Path",
        description="Specify the path to your Halo 2 Anniversary MP Editing Kit folder containing tool / tool_fast",
        default="",
        update=clean_h2aek_path,
    )

    tool_type: EnumProperty(
        name="Tool Type",
        description="Specify whether the add on should use Tool or Tool Fast",
        default="tool_fast",
        items=[('tool_fast', 'Tool Fast', ''), ('tool', 'Tool', '')]
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.label(text='Halo Reach Editing Kit Path')
        row = layout.row()
        row.prop(self, 'hrek_path', text='')
        row.scale_x = 0.25
        row.operator('nwo.hrek_path')
        row = layout.row()
        row.label(text='Halo 4 Editing Kit Path')
        row = layout.row()
        row.prop(self, 'h4ek_path', text='')
        row.scale_x = 0.25
        row.operator('nwo.h4ek_path')
        row = layout.row()
        row.label(text='Halo 2 Anniversary Multiplayer Editing Kit Path')
        row = layout.row()
        row.prop(self, 'h2aek_path', text='')
        row.scale_x = 0.25
        row.operator('nwo.h2aek_path')
        row = layout.row()
        row.label(text='Tool Type')
        row.prop(self, 'tool_type', expand=True)

@persistent
def load_handler(dummy):
    # Set game version from file
    context = bpy.context
    game_version_txt_path = os.path.join(bpy.app.tempdir, 'game_version.txt')
    # only do this if the scene is not an asset
    if not valid_nwo_asset(context) and os.path.exists(game_version_txt_path):
        with open(game_version_txt_path, 'r') as temp_file:
            bpy.context.scene.nwo_global.game_version = temp_file.read()

    # run ManagedBlam on startup if enabled
    if bpy.context.scene.nwo_global.mb_startup:
        bpy.ops.managed_blam.init()

    # create warning if current game_version is incompatible with loaded managedblam.dll
    if os.path.exists(os.path.join(bpy.app.tempdir, 'blam.txt')):
        with open(os.path.join(bpy.app.tempdir, 'blam.txt'), 'r') as blam_txt:
            mb_path = blam_txt.read()
        
        if not mb_path.startswith(get_ek_path()):
            game = formalise_game_version(bpy.context.scene.nwo_global.game_version)
            result = ctypes.windll.user32.MessageBoxW(0, f"{game} incompatible with loaded ManagedBlam version: {mb_path + '.dll'}. Please restart Blender or switch to a {game} asset.\n\nClose Blender?", f"ManagedBlam / Game Mismatch", 4)
            if result == 6:
                bpy.ops.wm.quit_blender()

def register():
    bpy.utils.register_class(ToolkitLocationPreferences)
    bpy.utils.register_class(HREKLocationPath)
    bpy.utils.register_class(H4EKLocationPath)
    bpy.utils.register_class(H2AMPEKLocationPath)
    bpy.app.handlers.load_post.append(load_handler)
    for module in modules:
        module.register()

def unregister():
    bpy.app.handlers.load_post.remove(load_handler)
    bpy.utils.unregister_class(ToolkitLocationPreferences)
    bpy.utils.unregister_class(HREKLocationPath)
    bpy.utils.unregister_class(H4EKLocationPath)
    bpy.utils.unregister_class(H2AMPEKLocationPath)
    for module in reversed(modules):
        module.unregister()

if __name__ == '__main__':
    register()

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

from bpy.types import Operator, AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty

from io_scene_foundry.utils import nwo_globals

class HREKLocationPath(Operator):
    """Set the path to your Halo Reach Editing Kit"""

    bl_idname = "nwo.hrek_path"
    bl_label = "Select Folder"

    filter_folder: BoolProperty(
        default=True,
        options={"HIDDEN"},
    )

    directory: StringProperty(
        name="hrek_path",
        description="Set the path to your Halo Reach Editing Kit",
    )

    def execute(self, context):
        context.preferences.addons[
            "io_scene_foundry"
        ].preferences.hrek_path = self.directory.strip('"\\')

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class H4EKLocationPath(Operator):
    """Set the path to your Halo 4 Editing Kit"""

    bl_idname = "nwo.h4ek_path"
    bl_label = "Select Folder"

    filter_folder: BoolProperty(
        default=True,
        options={"HIDDEN"},
    )

    directory: StringProperty(
        name="h4ek_path",
        description="Set the path to your Halo 4 Editing Kit",
    )

    def execute(self, context):
        context.preferences.addons[
            "io_scene_foundry"
        ].preferences.h4ek_path = self.directory.strip('"\\')

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class H2AMPEKLocationPath(Operator):
    """Set the path to your Halo 2 Anniversary Multiplayer Editing Kit"""

    bl_idname = "nwo.h2aek_path"
    bl_label = "Select Folder"

    filter_folder: BoolProperty(
        default=True,
        options={"HIDDEN"},
    )

    directory: StringProperty(
        name="h2aek_path",
        description="Set the path to your Halo 2 Anniversary Multiplayer Editing Kit",
    )

    def execute(self, context):
        context.preferences.addons[
            "io_scene_foundry"
        ].preferences.h2aek_path = self.directory.strip('"\\')

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}


class ToolkitLocationPreferences(AddonPreferences):
    bl_idname = "io_scene_foundry"

    def clean_hrek_path(self, context):
        self["hrek_path"] = self["hrek_path"].strip('"\\')

    hrek_path: StringProperty(
        name="HREK Path",
        description="Specify the path to your Halo Reach Editing Kit folder containing tool / tool_fast",
        default="",
        update=clean_hrek_path,
    )

    def clean_h4ek_path(self, context):
        self["h4ek_path"] = self["h4ek_path"].strip('"\\')

    h4ek_path: StringProperty(
        name="H4EK Path",
        description="Specify the path to your Halo 4 Editing Kit folder containing tool / tool_fast",
        default="",
        update=clean_h4ek_path,
    )

    def clean_h2aek_path(self, context):
        self["h2aek_path"] = self["h2aek_path"].strip('"\\')

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
        items=[("tool_fast", "Tool Fast", ""), ("tool", "Tool", "")],
    )

    default_game_version: EnumProperty(
        name="Default Game",
        description="Specify the game Foundry should select by default on new scenes",
        default="reach",
        items=[("reach", "Halo Reach", ""), ("h4", "Halo 4", ""), ("h2a", "Halo 2 Anniversary Multiplayer", "")],
    )

    def draw(self, context):
        layout = self.layout
        if not nwo_globals.clr_installed:
            row = layout.row(align=True)
            row.scale_y = 1.5
            row.operator("managed_blam.init", text="Install ManagedBlam Dependancy", icon='IMPORT').install_only = True
        row = layout.row(align=True)
        row.label(text="Halo Reach Editing Kit Path")
        row = layout.row(align=True)
        row.prop(self, "hrek_path", text="")
        row.operator("nwo.hrek_path", text="", icon='FILE_FOLDER')
        row = layout.row(align=True)
        row.label(text="Halo 4 Editing Kit Path")
        row = layout.row(align=True)
        row.prop(self, "h4ek_path", text="")
        row.operator("nwo.h4ek_path", text="", icon='FILE_FOLDER')
        row = layout.row(align=True)
        row.label(text="Halo 2 Anniversary Multiplayer Editing Kit Path")
        row = layout.row(align=True)
        row.prop(self, "h2aek_path", text="")
        row.operator("nwo.h2aek_path", text="", icon='FILE_FOLDER')
        row = layout.row(align=True)
        row.label(text="Default Game")
        row = layout.row(align=True)
        row.prop(self, "default_game_version", expand=True)
        row = layout.row(align=True)
        row.label(text="Tool Version")
        row = layout.row(align=True)
        row.prop(self, "tool_type", expand=True)
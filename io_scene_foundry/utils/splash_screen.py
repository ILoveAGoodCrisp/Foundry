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

from bpy.types import Menu

class FoundrySplashScreen(Menu):
    bl_label = "Splash"

    def draw(self, context):
        #TODO System for setting the default game in other startup apps
        from io_scene_foundry.icons import get_icon_id
        layout = self.layout
        layout.operator_context = 'EXEC_DEFAULT'
        layout.emboss = 'PULLDOWN_MENU'
        header = layout.row()
        header.prop(context.scene.nwo_global, "game_version", text='')
        header.scale_x = 2
        header.scale_y = 1.5
        split = layout.split()

        # Templates
        col1 = split.column()
        col1.label(text="New Asset")
        #col1.scale_y = 0.8

        # bpy.types.TOPBAR_MT_file_new.draw_ex(col1, context, use_splash=True)
        col1.operator("wm.read_homefile", text="Model", icon_value=get_icon_id("model")).app_template = "Model"
        col1.operator("wm.read_homefile", text="Scenario", icon_value=get_icon_id("scenario")).app_template = "Scenario"
        col1.operator("wm.read_homefile", text="Sky", icon_value=get_icon_id("sky")).app_template = "Sky"
        col1.operator("wm.read_homefile", text="Decorator Set", icon_value=get_icon_id("decorator")).app_template = "Decorator Set"
        col1.operator("wm.read_homefile", text="Particle Model", icon_value=get_icon_id("particle_model")).app_template = "Particle Model"
        col1.operator("wm.read_homefile", text="Prefab", icon_value=get_icon_id("prefab")).app_template = "Prefab"
        col1.operator("wm.read_homefile", text="First Person Animation", icon_value=get_icon_id("animation")).app_template = "First Person Animation"
        # Recent
        col2 = split.column()
        col2_title = col2.row()

        found_recent = col2.template_recent_files()

        if found_recent:
            col2_title.label(text="Recent Files")
        else:

            # Links if no recent files
            col2_title.label(text="Getting Started")

            col2.operator("wm.url_open_preset", text="Manual", icon='URL').type = 'MANUAL'
            col2.operator("wm.url_open_preset", text="Blender Website", icon='URL').type = 'BLENDER'
            col2.operator("wm.url_open_preset", text="Credits", icon='URL').type = 'CREDITS'

        layout.separator()

        split = layout.split()

        col1 = split.column()
        sub = col1.row()
        sub.operator_context = 'INVOKE_DEFAULT'
        sub.operator("wm.open_mainfile", text="Open...", icon='FILE_FOLDER')
        col1.operator("wm.recover_last_session", icon='RECOVER_LAST')

        col2 = split.column()

        col2.operator("wm.url_open", text="Github", icon_value=get_icon_id("github")).url = r"https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit"
        col2.operator("wm.url_open", text="Documentation", icon_value=get_icon_id("c20_reclaimers")).url = r"https://c20.reclaimers.net/"

        layout.separator()
        layout.separator()
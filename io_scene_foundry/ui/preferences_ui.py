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
from bpy.types import Operator, AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty, CollectionProperty
from io_scene_foundry.icons import get_icon_id, get_icon_id_in_directory
from io_scene_foundry.utils.nwo_utils import foundry_update_check, get_prefs, read_projects_list, setup_projects_list, write_projects_list
from io_scene_foundry.utils import nwo_globals
FOUNDRY_GITHUB = r"https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit"
update_str, update_needed = foundry_update_check(nwo_globals.version)
import bpy
import xml.etree.ElementTree as ET

from io_scene_foundry.utils import nwo_globals

class NWO_Project_ListItems(bpy.types.PropertyGroup):
    project_path: StringProperty()
    project_name: StringProperty()
    project_display_name: StringProperty()
    project_xml: StringProperty()
    project_corinth: BoolProperty()
    project_remote_server_name: StringProperty()
    project_image_path: StringProperty()

class NWO_UL_Projects(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if item:
            thumbnail = os.path.join(item.project_path, item.project_image_path)
            if os.path.exists(thumbnail):
                icon_id = get_icon_id_in_directory(thumbnail)
            elif item.project_remote_server_name == "bngtoolsql":
                icon_id = get_icon_id("halo_reach")
            elif item.project_remote_server_name == "metawins":
                icon_id = get_icon_id("halo_4")
            elif item.project_remote_server_name == "episql.343i.selfhost.corp.microsoft.com":
                icon_id = get_icon_id("halo_2amp")
            else:
                icon_id = get_icon_id("tag_test")
            layout.label(text=item.project_display_name, icon_value=icon_id)
            layout.label(text=item.project_path)
        else:
            layout.label(text="", translate=False, icon_value=icon)

class NWO_ProjectAdd(Operator):
    bl_label = "Add Project"
    bl_idname = "nwo.project_add"
    bl_description = "Add a new project"

    filepath: StringProperty(
        name="path", description="Set the path to your project", subtype="FILE_PATH"
    )

    filter_folder: BoolProperty(
        default=True,
        options={"HIDDEN"},
    )

    set_scene_project: BoolProperty(options={"HIDDEN"})

    def execute(self, context):
        # validate new_project_path
        new_project_path = self.filepath
        if os.path.isfile(new_project_path):
            new_project_path = os.path.dirname(new_project_path)
        new_project_path = new_project_path.strip('"\'\\ ')
        if not os.path.exists(os.path.join(new_project_path, "project.xml")):
            new_project_path = os.path.dirname(new_project_path)
            new_project_path = new_project_path.strip('"\'\\ ')
            if not os.path.exists(os.path.join(new_project_path, "project.xml")):
                self.report({'WARNING'}, f"{new_project_path} is not a path to a valid Halo project. Expected project root directory to contain project.xml")
                return {'CANCELLED'}
        
        projects_list = read_projects_list()
        if projects_list is None:
            projects_list = []
        projects_list.append(new_project_path)
        projects_list = list(dict.fromkeys(projects_list))

        write_projects_list(projects_list)
        projects = setup_projects_list(report=self.report)

        if self.set_scene_project:
            nwo = context.scene.nwo
            nwo.scene_project = projects[-1].project_display_name

        context.area.tag_redraw()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        self.filepath = os.path.dirname(self.filepath)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}
    
class NWO_ProjectRemove(Operator):
    bl_label = "Remove Project"
    bl_idname = "nwo.project_remove"

    @classmethod
    def poll(self, context):
        prefs = get_prefs()
        return prefs.projects

    def execute(self, context):
        prefs = get_prefs()
        current_project = prefs.projects[prefs.current_project_index].project_path
        projects_list = read_projects_list()
        if current_project in projects_list:
            projects_list.remove(current_project)

        write_projects_list(projects_list)

        prefs.projects.remove(prefs.current_project_index)
        if prefs.current_project_index > len(prefs.projects) - 1:
            prefs.current_project_index += -1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_ProjectMove(Operator):
    bl_label = "Move Project"
    bl_idname = "nwo.project_move"

    @classmethod
    def poll(self, context):
        prefs = get_prefs()
        return len(prefs.projects) > 1
    
    direction: StringProperty()

    def execute(self, context):
        prefs = get_prefs()
        projects = prefs.projects
        current_index = prefs.current_project_index
        delta = {
            "down": 1,
            "up": -1,
        }[self.direction]

        to_index = (current_index + delta) % len(projects)

        projects.move(current_index, to_index)
        prefs.current_project_index = to_index
        new_projects_list = []
        for p in projects:
            new_projects_list.append(p.project_path)

        write_projects_list(new_projects_list)
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_ProjectEditDisplayName(Operator):
    bl_label = "Edit Project Display name"
    bl_idname = "nwo.project_edit_display_name"

    new_display_name: StringProperty(name="Display Name")

    @classmethod
    def poll(cls, context):
        prefs = get_prefs()
        return prefs.projects

    def execute(self, context):
        prefs = get_prefs()
        active_project = prefs.projects[prefs.current_project_index]
        project_xml = active_project.project_xml
        if not os.path.exists(project_xml):
            self.report({'WARNING'}, "No active project")
            return {'CANCELLED'}
        with open(project_xml, 'r+') as file:
            xml = file.read()
            root = ET.fromstring(xml)
            if not root.get('displayName', 0):
                self.report({'WARNING'}, "Project XML does not contain displayName variable")
                return {'CANCELLED'}
            root.attrib['displayName'] = self.new_display_name
            xml.seek(0)
            xml.truncate()
            xml.write(ET.tostring(root, encoding='utf-8'))
        
        active_project.project_display_name = self.new_display_name

        return {'FINISHED'}

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

    current_project : StringProperty()
    current_project_index : bpy.props.IntProperty()

    projects : CollectionProperty(type=NWO_Project_ListItems)

    toolbar_icons_only : BoolProperty(name="Toolbar Icons Only", description="Toggle whether the Foundry Toolbar should only show icons")

    apply_materials : BoolProperty(
        name="Apply Types Operator sets materials",
        description="Sets whether the apply types operator will apply special materials",
        default=True,
    )

    def draw(self, context):
        prefs = self
        layout = self.layout
        box = layout.box()
        box.label(text=update_str, icon_value=get_icon_id("foundry"))
        if update_needed:
            box.operator("nwo.open_url", text="Get Latest", icon_value=get_icon_id("github")).url = FOUNDRY_GITHUB

        if not nwo_globals.clr_installed:
            box = layout.box()
            box.label(text="Install required to use Halo Tag API (ManagedBlam)")
            row = box.row(align=True)
            row.scale_y = 1.5
            row.operator("managed_blam.init", text="Install ManagedBlam Dependency", icon='IMPORT').install_only = True
        
        box = layout.box()
        row = box.row()
        row.label(text="Projects")
        row = box.row()
        rows = 3
        row.template_list(
            "NWO_UL_Projects",
            "",
            self,
            "projects",
            self,
            "current_project_index",
            rows=rows,
        )
        col = row.column(align=True)
        col.operator("nwo.project_add", text="", icon="ADD")
        col.operator("nwo.project_remove", icon="REMOVE", text="")
        col.separator()
        col.operator("nwo.project_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.project_move", icon="TRIA_DOWN", text="").direction = 'down'
        row = box.row(align=True, heading="Tool Version")
        row.prop(prefs, "tool_type", expand=True)
        row = box.row(align=True)
        row.prop(prefs, "apply_materials", text="Apply Types Operator Updates Materials")
        row = box.row(align=True)
        row.prop(prefs, "toolbar_icons_only", text="Foundry Toolbar Icons Only")
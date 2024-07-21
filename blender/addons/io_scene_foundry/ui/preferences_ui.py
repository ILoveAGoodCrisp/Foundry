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
from pathlib import Path
from bpy.types import Operator, AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty, CollectionProperty
from io_scene_foundry.icons import get_icon_id
from io_scene_foundry.utils.nwo_utils import ProjectXML, foundry_update_check, get_prefs, get_tags_path, is_corinth, project_game_icon, project_icon, read_projects_list, relative_path, setup_projects_list, write_projects_list
from io_scene_foundry.utils import nwo_globals
FOUNDRY_GITHUB = r"https://github.com/ILoveAGoodCrisp/Foundry-Halo-Blender-Creation-Kit"
update_str, update_needed = foundry_update_check(nwo_globals.version)
import bpy
import xml.etree.ElementTree as ET

from io_scene_foundry.utils import nwo_globals

class NWO_Project_ListItems(bpy.types.PropertyGroup):
    project_path: StringProperty()
    project_name: StringProperty()
    name: StringProperty()
    project_xml: StringProperty()
    corinth: BoolProperty()
    remote_server_name: StringProperty()
    image_path: StringProperty()
    default_material: StringProperty()
    default_water: StringProperty()
    tags_directory: StringProperty()
    data_directory: StringProperty()

class NWO_UL_Projects(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if item:
            layout.label(text=item.name, icon_value=project_game_icon(context, item))
            if Path(item.project_path, item.image_path).exists():
                layout.label(text="", icon_value=project_icon(context, item))
            # layout.label(text=item.project_path)
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
        new_project_path = Path(self.filepath)
        if new_project_path.is_file():
            new_project_path = new_project_path.parent
        if not Path(new_project_path, "project.xml").exists():
            new_project_path = new_project_path.parent
            if not Path(new_project_path, "project.xml").exists():
                self.report({'WARNING'}, f"{new_project_path} is not a path to a valid Halo project. Expected project root directory to contain project.xml")
                return {'CANCELLED'}
        
        projects_list = read_projects_list()
        if projects_list is None:
            projects_list = []
        projects_list.append(str(new_project_path))
        projects_list = list(dict.fromkeys(projects_list))

        write_projects_list(projects_list)
        projects = setup_projects_list(report=self.report)

        if self.set_scene_project:
            nwo = context.scene.nwo
            nwo.scene_project = projects[-1].name

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
    
class NWO_OT_ProjectEdit(Operator):
    bl_label = "Edit Project Settings"
    bl_idname = "nwo.project_edit"

    display_name: StringProperty(name="Display Name")
    material_path: StringProperty(name="Default Material/Shader Tag")
    water_path: StringProperty(name="Default Water Shader/Material Tag")

    @classmethod
    def poll(cls, context):
        prefs = get_prefs()
        return prefs.projects

    def execute(self, context):
        prefs = get_prefs()
        active_project = prefs.projects[prefs.current_project_index]
        project_xml = Path(active_project.project_xml)
        if not project_xml.exists():
            self.report({'WARNING'}, "No active project")
            return {'CANCELLED'}
        
        xml = ProjectXML()
        name = self.display_name.strip(" '\"")
        xml.display_name = name
        if is_corinth(context):
            xml.name = name
        default_material = relative_path(self.material_path.strip(" '\""))
        if Path(get_tags_path(), default_material).exists():
            xml.default_material = default_material
        default_water = relative_path(self.water_path.strip(" '\""))
        if Path(get_tags_path(), default_water).exists():
            xml.default_water = default_water
        xml.parse(project_xml.parent)
        
        active_project.name = xml.display_name
        active_project.project_name = xml.name
        active_project.default_material = xml.default_material
        active_project.default_water = xml.default_water

        context.area.tag_redraw()
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        prefs = get_prefs()
        active_project = prefs.projects[prefs.current_project_index]
        self.display_name = active_project.name
        self.material_path = active_project.default_material
        self.water_path = active_project.default_water
        return context.window_manager.invoke_props_dialog(self, width=800)
        
    def draw(self, context):
        layout = self.layout
        shader_name = "Material" if is_corinth(context) else "Shader"
        layout.prop(self, "display_name")
        layout.prop(self, "material_path", text=f"Default {shader_name} Tag")
        layout.prop(self, "water_path", text=f"Default Water {shader_name} Tag")
        

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
        name="Apply Materials on Setting Mesh Type",
        description="",
        default=True,
    )
    
    apply_empty_display : BoolProperty(
        name="Change Empty Display on Setting Marker Type",
        description="",
        default=True,
    )

    apply_prefix : EnumProperty(
        name="Object Prefixes",
        description='Sets the prefixes to apply when applying a mesh or marker type to an object. Object prefixes are convention only and do not dictate the type. Mesh/Marker type can be verified via Object Properties in the Foundry Panel',
        default='none',
        items=[
            ("none", "None", "Does not apply object prefixes"),
            ("full", "Full", "Applies object prefixes that specify the object type"),
            ("legacy", "Legacy", "Applies legacy object prefixes as you would see in the Halo 3 Editing Kit"),
        ]
    )
    
    protect_materials: BoolProperty(
        name="Protect Default Materials",
        description="Prevents the material/shader tags that come bundeled with the Halo Editing Kits from being edited by Foundry",
        default=True,
    )
    
    update_materials_on_shader_path: BoolProperty(
        name="Update Blender Materials from Shader Path",
        description="Enable to automatically generate new Material Nodes whenever a valid Material Shader Path is set",
        default=False,
    )
    
    sync_timeline_range: BoolProperty(
        name="Update Timeline Range on Switching Animation",
        description="Sets the scene timeline to match the start and end frame range of the current animation if using the Foundry Animation Panel to switch animations",
        default=True,
    )
    
    def scene_matrix_items(self, context):
        return [
            ("scene", "Use Scene", "", "", 0),
            ("blender", "Blender", "", "BLENDER", 1),
            ("halo", "Halo", "", get_icon_id('halo_scale'), 2),
        ]
    
    scene_matrix: EnumProperty(
        name="Default Scene Matrix",
        description="When creating a new asset sets the default scene scale and forward direction",
        items=scene_matrix_items,
    )
    
    debug_menu_on_export: BoolProperty(
        name="Update Debug Menu on Export",
        description="Updates the debug menu at export with the current scene asset (if it is a model)",
        default=True,
    )
    debug_menu_on_launch: BoolProperty(
        name="Update Debug Menu on Game Launch",
        description="Updates the debug menu at game launch (sapien or tagtest) with the current scene asset (if it is a model)",
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
            row.operator("managed_blam.init", text="Install Tag API Dependency", icon='IMPORT').install_only = True
        
        box = layout.box()
        row = box.row()
        row.label(text="Projects")
        row = box.row()
        rows = 5
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
        col.operator("nwo.project_edit", icon="SETTINGS", text="")
        col.separator()
        col.operator("nwo.project_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.project_move", icon="TRIA_DOWN", text="").direction = 'down'
        row = box.row(align=True, heading="Tool Version")
        row.prop(prefs, "tool_type", expand=True)
        row = box.row(align=True, heading="Default Scene Matrix")
        row.prop(prefs, "scene_matrix", expand=True)
        row = box.row(align=True, heading="Default Object Prefixes")
        row.prop(prefs, "apply_prefix", expand=True)
        row = box.row(align=True)
        row.prop(prefs, "apply_materials", text="Apply Types Operator Updates Materials")
        row = box.row(align=True)
        row.prop(prefs, "apply_empty_display")
        # row = box.row(align=True)
        # row.prop(prefs, "poop_default")
        row = box.row(align=True)
        row.prop(prefs, "toolbar_icons_only", text="Foundry Toolbar Icons Only")
        row = box.row(align=True)
        row.prop(prefs, "protect_materials")
        row = box.row(align=True)
        row.prop(prefs, "update_materials_on_shader_path")
        row = box.row(align=True)
        row.prop(prefs, "sync_timeline_range")
        row = box.row(align=True)
        row.prop(prefs, "debug_menu_on_export")
        row = box.row(align=True)
        row.prop(prefs, "debug_menu_on_launch")
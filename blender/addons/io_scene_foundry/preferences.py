

import os
import re
import subprocess
import tempfile
from pathlib import Path
from bpy.types import Operator, AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty, CollectionProperty

from . import startup
from .constants import IMPORT_TEMPLATE_DEFAULT, IMPORT_TEMPLATE_ITEMS
from .utils import ProjectXML, get_prefs, get_scene_props, get_tags_path, is_corinth, project_game_icon, project_icon, read_projects_list, relative_path, setup_projects_list, write_projects_list, addon_root, formalise_string
FOUNDRY_GITHUB = r"https://github.com/ILoveAGoodCrisp/Foundry"
import bpy

class NWO_Project_ListItems(bpy.types.PropertyGroup):
    project_path: StringProperty()
    project_name: StringProperty()
    name: StringProperty()
    project_xml: StringProperty()
    corinth: BoolProperty()
    game: StringProperty()
    remote_server_name: StringProperty()
    image_path: StringProperty()
    default_material: StringProperty()
    default_water: StringProperty()
    tags_directory: StringProperty()
    data_directory: StringProperty()
    last_scenario: StringProperty()

class NWO_UL_Projects(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        if item:
            layout.label(text=item.name, icon_value=project_game_icon(context, item))
            if Path(item.project_path, item.image_path).is_file():
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
        if not Path(new_project_path, "tool.exe").is_file():
            new_project_path = new_project_path.parent
            if not Path(new_project_path, "tool.exe").is_file():
                self.report({'WARNING'}, f"{new_project_path} is not a path to a valid Halo project. Expected project root directory to contain tool.exe")
                return {'CANCELLED'}

        xml = ProjectXML()
        if not xml.parse(new_project_path):
            self.report({'WARNING'}, "Could not load project. Check tool.exe and project.xml; see console for details")
            return {'CANCELLED'}
        
        projects_list = read_projects_list()
        if projects_list is None:
            projects_list = []
        had_no_projects = not projects_list
        projects_list.append(str(new_project_path))
        projects_list = list(dict.fromkeys(projects_list))

        write_projects_list(projects_list)
        projects = setup_projects_list(report=self.report)

        if projects and (self.set_scene_project or had_no_projects):
            nwo = get_scene_props()
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

    @classmethod
    def poll(cls, context):
        prefs = get_prefs()
        return prefs.projects

    def execute(self, context):
        prefs = get_prefs()
        active_project = prefs.projects[prefs.current_project_index]
        project_xml = Path(active_project.project_xml)
        if not Path(active_project.project_path, "tool.exe").is_file():
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
        if not xml.parse(project_xml.parent):
            self.report({'WARNING'}, "Could not update project settings; see console for details")
            return {'CANCELLED'}
        
        active_project.name = xml.display_name
        active_project.project_name = xml.name
        active_project.default_material = xml.default_material

        context.area.tag_redraw()
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        prefs = get_prefs()
        active_project = prefs.projects[prefs.current_project_index]
        self.display_name = active_project.name
        self.material_path = active_project.default_material
        return context.window_manager.invoke_props_dialog(self, width=800)
        
    def draw(self, context):
        layout = self.layout
        shader_name = "Material" if is_corinth(context) else "Shader"
        layout.prop(self, "display_name")
        layout.prop(self, "material_path", text=f"Default {shader_name} Tag")

class NWO_OT_InstallXRGBColorspace(Operator):
    bl_label = "Install xRGB Color Space"
    bl_idname = "nwo.install_xrgb_colorspace"
    bl_description = "Install Foundry's xRGB color space into Blender's active OCIO config. This will use a powershell script and may request elevated (admin) permissions. This is necessary because the file this operator edits is usually stored within a protected folder e.g. program files"

    @staticmethod
    def _ocio_path() -> Path:
        blender_path = Path(bpy.app.binary_path)
        version_dir = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
        return blender_path.parent / version_dir / "datafiles" / "colormanagement" / "config.ocio"

    @staticmethod
    def _xrgb_block(newline: str) -> str:
        lines = [
            "",
            "  - !<ColorSpace>",
            "    name: xRGB",
            "    aliases: [Halo xRGB, Halo xRGB 1.95]",
            "    family: Halo",
            "    equalitygroup:",
            "    bitdepth: 8ui",
            "    description: |",
            "      Halo xRGB texture encoding using Rec.709 primaries, D65 white point,",
            "      and a pure 1.95 exponent.",
            "    isdata: false",
            "    encoding: sdr-video",
            "    to_scene_reference: !<GroupTransform>",
            "      children:",
            "        - !<ExponentTransform> {value: [1.95, 1.95, 1.95, 1]}",
            "        - !<ColorSpaceTransform> {src: Linear Rec.709, dst: Linear CIE-XYZ E}",
        ]
        return newline.join(lines) + newline

    @staticmethod
    def _quote_ps(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    @classmethod
    def _patch_ocio_config(cls, text: str) -> tuple[str, bool]:
        exact_name = re.compile(r"(?m)^\s*name:\s*xRGB\s*$")
        if exact_name.search(text):
            return text, False

        existing_case_variant = re.compile(r"(?m)^(\s*name:\s*)xrgb\s*$", re.IGNORECASE)
        if existing_case_variant.search(text):
            return existing_case_variant.sub(r"\1xRGB", text, count=1), True

        newline = "\r\n" if "\r\n" in text else "\n"
        block = cls._xrgb_block(newline)

        linear_marker = f"{newline}  - !<ColorSpace>{newline}    name: Linear Rec.709"
        start = text.find(linear_marker)
        if start >= 0:
            next_start = text.find(f"{newline}  - !<ColorSpace>", start + len(linear_marker))
            if next_start >= 0:
                return text[:next_start] + block + text[next_start:], True

        colorspaces_marker = f"colorspaces:{newline}"
        start = text.find(colorspaces_marker)
        if start >= 0:
            insert_at = start + len(colorspaces_marker)
            return text[:insert_at] + block.lstrip(newline) + text[insert_at:], True

        raise RuntimeError("Could not find the colorspaces section in Blender's OCIO config")

    @classmethod
    def _write_with_elevation(cls, ocio_path: Path, patched_path: Path, backup_path: Path):
        temp_dir = Path(tempfile.gettempdir()) / "Foundry"
        temp_dir.mkdir(parents=True, exist_ok=True)
        script_path = temp_dir / "install_xrgb_ocio.ps1"
        log_path = temp_dir / "install_xrgb_ocio.log"
        ps_script = "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$OcioPath = {cls._quote_ps(str(ocio_path))}",
                f"$PatchedPath = {cls._quote_ps(str(patched_path))}",
                f"$BackupPath = {cls._quote_ps(str(backup_path))}",
                f"$LogPath = {cls._quote_ps(str(log_path))}",
                "try {",
                "    if (!(Test-Path -LiteralPath $OcioPath)) { throw \"OCIO config was not found: $OcioPath\" }",
                "    if (!(Test-Path -LiteralPath $BackupPath)) { Copy-Item -LiteralPath $OcioPath -Destination $BackupPath }",
                "    Copy-Item -LiteralPath $PatchedPath -Destination $OcioPath -Force",
                "    Set-Content -LiteralPath $LogPath -Value 'OK'",
                "    exit 0",
                "} catch {",
                "    Set-Content -LiteralPath $LogPath -Value $_.Exception.Message",
                "    exit 1",
                "}",
            ]
        )
        script_path.write_text(ps_script, encoding="utf-8")

        elevated_args = f"-NoProfile -ExecutionPolicy Bypass -File \"{script_path}\""
        command = (
            "$p = Start-Process -FilePath 'powershell.exe' "
            f"-ArgumentList {cls._quote_ps(elevated_args)} "
            "-Verb RunAs -Wait -PassThru; exit $p.ExitCode"
        )
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
        ), log_path

    def execute(self, context):
        ocio_path = self._ocio_path()
        if not ocio_path.exists():
            self.report({'ERROR'}, f"Blender OCIO config not found: {ocio_path}")
            return {'CANCELLED'}

        original_text = ocio_path.read_text(encoding="utf-8")
        try:
            patched_text, changed = self._patch_ocio_config(original_text)
        except RuntimeError as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}

        if not changed:
            self.report({'INFO'}, "xRGB color space is already installed")
            return {'FINISHED'}

        backup_path = ocio_path.with_name(f"{ocio_path.name}.foundry_backup")
        try:
            if not backup_path.exists():
                backup_path.write_text(original_text, encoding="utf-8")
            ocio_path.write_text(patched_text, encoding="utf-8")
        except PermissionError:
            temp_dir = Path(tempfile.gettempdir()) / "Foundry"
            temp_dir.mkdir(parents=True, exist_ok=True)
            patched_path = temp_dir / "config.ocio.xrgb"
            patched_path.write_text(patched_text, encoding="utf-8")
            result, log_path = self._write_with_elevation(ocio_path, patched_path, backup_path)
            if result.returncode != 0:
                if log_path.exists():
                    details = log_path.read_text(encoding="utf-8").strip()
                else:
                    details = (result.stderr or result.stdout or "Windows cancelled or denied the elevated write").strip()
                self.report({'ERROR'}, f"Failed to install xRGB color space: {details}")
                return {'CANCELLED'}
        except OSError as ex:
            self.report({'ERROR'}, f"Failed to install xRGB color space: {ex}")
            return {'CANCELLED'}

        self.report({'INFO'}, "Installed xRGB color space. Restart Blender to load the updated OCIO config")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(
            self,
            event,
            title="Install xRGB color space?",
            confirm_text="Install",
        )

def _settings_box(layout, title: str):
    box = layout.box()
    box.label(text=title)
    return box

def draw_foundry_preferences(layout, prefs, context=None, show_save_button=False):
    box = _settings_box(layout, "Projects")
    row = box.row()
    rows = 5
    row.template_list(
        "NWO_UL_Projects",
        "",
        prefs,
        "projects",
        prefs,
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

    box = _settings_box(layout, "Halo Tools")
    row = box.row(align=True, heading="Tool Version")
    row.prop(prefs, "tool_type", expand=True)
    row = box.row(align=True)
    row.prop(prefs, "allow_tool_patches")
    row = box.row(align=True)
    row.enabled = prefs.allow_tool_patches
    row.prop(prefs, "patch_tool_node_depth_sort")
    row = box.row(align=True)
    row.enabled = prefs.allow_tool_patches
    row.prop(prefs, "patch_tool_uncompressed_vertex_weights")
    row = box.row(align=True)
    row.enabled = prefs.allow_tool_patches
    row.prop(prefs, "patch_tool_skip_vertex_compression")
    row = box.row(align=True)
    row.enabled = prefs.allow_tool_patches
    row.prop(prefs, "patch_tool_skip_import_source_data")
    row = box.row(align=True)
    row.prop(prefs, "allow_foundation_plugin_install")
    row = box.row(align=True)
    row.prop(prefs, "granny_viewer_path")

    box = _settings_box(layout, "Import & Bitmaps")
    row = box.row(align=True)
    row.prop(prefs, "default_import_template")
    row = box.row(align=True)
    row.prop(prefs, "default_scale_model")
    row = box.row(align=True)
    row.prop(prefs, "import_shaders_with_time_period")
    row = box.row(align=True)
    row.prop(prefs, "link_resource_nodes")
    row = box.row(align=True)
    row.prop(prefs, "bitmap_color_space_conversion")
    row.operator("nwo.install_xrgb_colorspace", text="Install xRGB")

    box = _settings_box(layout, "Objects & Materials")
    row = box.row(align=True, heading="Default Object Prefixes")
    row.prop(prefs, "apply_prefix", expand=True)
    row = box.row(align=True)
    row.prop(prefs, "apply_materials", text="Update Materials on Object Type Change")
    row = box.row(align=True)
    row.prop(prefs, "apply_empty_display")
    row = box.row(align=True)
    row.prop(prefs, "protect_materials")
    row = box.row(align=True)
    row.prop(prefs, "update_materials_on_shader_path")
    row = box.row(align=True)
    row.prop(prefs, "import_classic_shader_emission")
    row = box.row(align=True)
    row.prop(prefs, "rename_halo_collections")
    row = box.row(align=True)
    row.prop(prefs, "rename_material")

    box = _settings_box(layout, "Animation & Debug")
    row = box.row(align=True)
    row.prop(prefs, "sync_timeline_range")
    row = box.row(align=True)
    row.prop(prefs, "animation_switch_frame")
    row = box.row(align=True)
    row.prop(prefs, "load_animation_snapshots")
    row = box.row(align=True)
    row.prop(prefs, "ignore_final_frame")
    row = box.row(align=True)
    row.prop(prefs, "debug_menu_on_export")
    row = box.row(align=True)
    row.prop(prefs, "debug_menu_on_launch")

    box = _settings_box(layout, "Interface")
    row = box.row(align=True)
    row.prop(prefs, "toolbar_icons_only", text="Foundry Toolbar Icons Only")

    if not show_save_button or context is None:
        return

    blend_prefs = context.preferences
    if blend_prefs.use_preferences_save and (not bpy.app.use_userpref_skip_save_on_exit):
        return

    box = layout.box()
    row = box.row()
    row.operator("wm.save_userpref", text=("Save Foundry Settings") + (" *" if blend_prefs.is_dirty else ""))

class FoundryPreferences(AddonPreferences):
    bl_idname = __package__

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
    
    import_classic_shader_emission: BoolProperty(
        name="Import H1/H2 Shader Emission",
        description="Import Halo 1 and Halo 2 shader emission as a material attribute and add Halo emission to the Blender shader when converting materials",
        default=True,
    )

    sync_timeline_range: BoolProperty(
        name="Update Timeline Range on Switching Animation",
        description="Sets the scene timeline to match the start and end frame range of the current animation if using the Foundry Animation Panel to switch animations. On switching to a base, replacement, or world animation the timeline range is purposely set 1 frame short of the animation's final frame. This is to mimic how the game will slice off the final frame of a base, replacement, or world animation",
        default=True,
    )

    animation_switch_frame: EnumProperty(
        name="Animation Switch Frame",
        description="Controls which frame is selected when switching animations",
        default="CURRENT",
        items=[
            ("LAST", "Last frame used", "Return to the frame last used for that animation, or its first frame if it has not been used yet"),
            ("FIRST", "First frame", "Always jump to the animation's first frame"),
            ("CURRENT", "Current frame", "Do not change the current frame when switching animations"),
        ],
    )

    load_animation_snapshots: BoolProperty(
        name="Load Pose Snapshot on Switching Animation",
        description="Restores the saved bone pose and CTRL_settings pose controls when switching back to an animation",
        default=True,
    )
    
    ignore_final_frame: BoolProperty(
        name="Update Timeline Range Ignore Last Frame",
        description="Sets the timeline range 1 frame less than the frame count for base and world animations. This is to mimic the game import behavior for base animations where the final frame is cut and to ensure proper looping of the animation in the Blender viewport",
        default=True,
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
    
    import_shaders_with_time_period: BoolProperty(
        name="Import Game Shader/Materials with Animated Functions",
        default=True,
        description="Allows importing of animated functions when importing a Halo shader or material tag into Blender. Animated shaders can be taxing on Blender when the timeline is playing"
    )

    link_resource_nodes: BoolProperty(
        name="Link Resource Nodes",
        default=True,
        description="Link Foundry node groups from bundled resource blend files instead of appending them"
    )

    bitmap_color_space_conversion: BoolProperty(
        name="Bitmap Color Space Conversion",
        default=True,
        description="Convert extracted xRGB bitmap pixels to sRGB for Blender. Disable to leave extracted xRGB pixel values unchanged"
    )

    default_import_template: EnumProperty(
        name="Default Import Template",
        description="The preset selected by default in the Foundry drag and drop importer",
        default=IMPORT_TEMPLATE_DEFAULT,
        items=IMPORT_TEMPLATE_ITEMS,
    )
    
    allow_tool_patches: BoolProperty(
        name="Allow Tool Patches",
        description="Allow Foundry to patch tool.exe and tool_fast.exe. Disabling this means some features may be fail",
        default=True,
    )

    patch_tool_node_depth_sort: BoolProperty(
        name="Ignore Node Depth Sort",
        description="Patch Reach tool_fast.exe so render and animation nodes sort by Frame ID instead of hierarchy depth first",
        default=False,
    )

    patch_tool_uncompressed_vertex_weights: BoolProperty(
        name="Uncompressed Vertex Weights",
        description="Patch Reach tool.exe and tool_fast.exe to use uncompressed vertex weights",
        default=False,
    )

    patch_tool_skip_vertex_compression: BoolProperty(
        name="Skip Vertex Compression",
        description="Patch Reach tool.exe and tool_fast.exe to skip vertex welding and degenerate triangle compression passes",
        default=False,
    )

    patch_tool_skip_import_source_data: BoolProperty(
        name="Skip Import Source Data",
        description="Skip embedding zipped geometry source files in tags when exporting with Reach, Halo 4, or Halo 2 Anniversary Tool. Import file metadata is retained",
        default=False,
    )
    
    granny_viewer_path: StringProperty(
        name="Granny Viewer Path",
        description="Full system path to granny viewer. Having this allows Foundry to open gr2 files in the viewer",
        subtype='FILE_PATH',
    )
    
    allow_foundation_plugin_install: BoolProperty(
        name="Enable Foundation Plugin",
        default=True,
        description="By default when launching Foundation with Foundry, the Foundry Plugin will be installed for Foundation if it does not already exist (or is out of date). Toggle this off to prevent this behaviour. Launching Foundation with this disabled will also disable the plugin"
    )
    
    rename_halo_collections: BoolProperty(
        name="Rename Halo Collections",
        default=True,
        description="Renames any collection converted to a halo collection with their respective region/permutation/bsp/layer name"
    )
    
    rename_material: BoolProperty(
        name="Rename Material on New Shader Path",
        description="Renames the active material after settings its shader path"
    )
    
    def default_scale_model_items(self, context):
        items = []
        scale_models = Path(addon_root(), "resources", "scale_models")

        root_files = [f for f in scale_models.iterdir() if f.is_file()]
        if root_files:
            for file in sorted(root_files, key=lambda f: f.name):
                if file.suffix.lower() == '.bmf':
                    items.append((str(file), formalise_string(file.with_suffix("").name), str(file)))

        for folder in sorted([f for f in scale_models.iterdir() if f.is_dir()], key=lambda f: f.name):
            files = [f for f in folder.iterdir() if f.is_file()]
            if not files:
                continue

            items.append(("", formalise_string(folder.name), ""))

            for file in sorted(files, key=lambda f: f.name):
                if file.suffix.lower() == '.bmf':
                    items.append((
                        str(file),
                        formalise_string(file.with_suffix("").name),
                        str(file)
                    ))

        return items
    
    default_scale_model: EnumProperty(
        name="Default Scale Model",
        description="The default scale model to create using the Add > Mesh > Halo Scale Model operator",
        items=default_scale_model_items,
    )

    def draw(self, context):
        prefs = self
        layout = self.layout
        if not startup.load_handler_complete:
            return layout.operator("nwo.launch_foundry")
        draw_foundry_preferences(layout, prefs)
        
classes = [
    NWO_Project_ListItems,
    NWO_UL_Projects,
    NWO_ProjectAdd,
    NWO_ProjectRemove,
    NWO_ProjectMove,
    NWO_OT_ProjectEdit,
    NWO_OT_InstallXRGBColorspace,
    FoundryPreferences,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

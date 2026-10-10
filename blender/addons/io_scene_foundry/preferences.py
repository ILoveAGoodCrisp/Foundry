

import os
import re
import subprocess
import tempfile
from pathlib import Path
from .icons import get_icon_id
from bpy.types import Operator, AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty, CollectionProperty

from . import startup
from .constants import IMPORT_TEMPLATE_DEFAULT, IMPORT_TEMPLATE_ITEMS
from .utils import ProjectJSON, get_prefs, get_scene_props, get_tags_path, is_corinth, project_icon, read_projects_list, relative_path, setup_projects_list, write_projects_list, addon_root, formalise_string
from .utils import set_scene_project, set_project_list_index, project_selection_updates_suspended
from .project_config import (CUSTOM_DIRECTORY_GAMES, DEFAULT_PROJECT_IMAGE, PROJECT_FIELDS, configuration_key,
                             directory_path, new_project_record, project_image_path, project_record,
                             stored_directory, unique_project_name)
FOUNDRY_GITHUB = r"https://github.com/ILoveAGoodCrisp/Foundry"
FOUNDRY_GUIDANCE = "https://halomods.com/Tools/Foundry"
HALO_MODS_DISCORD = "https://discord.gg/mWY6SMr5z"
import bpy

def update_selected_project(self, context):
    if project_selection_updates_suspended():
        return
    scene = getattr(context, 'scene', None)
    if scene is not None and hasattr(scene, 'nwo') and 0 <= self.current_project_index < len(self.projects):
        set_scene_project(scene.nwo, self.projects[self.current_project_index])


def update_sidebar_icons_only(self, context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


class NWO_Project_ListItems(bpy.types.PropertyGroup):
    project_id: StringProperty()
    available: BoolProperty(default=True)
    project_path: StringProperty()
    project_name: StringProperty()
    name: StringProperty()
    project_json: StringProperty()
    corinth: BoolProperty()
    game: StringProperty()
    image_path: StringProperty(default=DEFAULT_PROJECT_IMAGE)
    use_project_thumbnail: BoolProperty(default=False)
    tags_directory: StringProperty()
    data_directory: StringProperty()
    last_scenario: StringProperty()

class NWO_UL_Projects(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_daata, active_propname
    ):
        if item:
            layout.label(text=item.name, icon_value=project_icon(context, item))
            if not item.available:
                layout.label(text="Unavailable", icon='ERROR')
            # layout.label(text=item.project_path)
        else:
            layout.label(text="", translate=False, icon_value=icon)

def draw_project_directory(layout, settings, field):
    row = layout.row(align=True)
    row.context_pointer_set('project_directory_settings', settings)
    row.prop(settings, field)
    row.operator('nwo.project_directory_browse', text='', icon='FILE_FOLDER').field = field


class NWO_OT_ProjectDirectoryBrowse(Operator):
    bl_label = 'Choose Content Folder'
    bl_idname = 'nwo.project_directory_browse'
    bl_description = 'Choose a tags or data folder, starting in the editing kit'

    field: EnumProperty(items=[('tags_directory', 'Tags Folder', ''),
                               ('data_directory', 'Data Folder', '')], options={'HIDDEN'})
    directory: StringProperty(subtype='DIR_PATH')
    filter_folder: BoolProperty(default=True, options={'HIDDEN'})

    def invoke(self, context, event):
        settings = context.project_directory_settings
        self._editing = settings.bl_rna.identifier == 'NWO_OT_project_edit'
        fields = ('display_name', 'project_path', 'image_path', 'use_project_thumbnail', 'tags_directory',
                  'data_directory', 'duplicate') if self._editing else (
                  'display_name', 'filepath', 'tags_directory', 'data_directory', 'set_scene_project')
        # The file browser closes the settings dialog. Keep its unsaved values
        # and restore them when browsing completes or is cancelled.
        self._values = {name: getattr(settings, name) for name in fields}
        root = Path(bpy.path.abspath(settings.project_path if self._editing else settings.filepath))
        if root.is_file():
            root = root.parent
        self._root = root
        self.directory = str(root) + os.sep
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def _restore(self):
        operator = bpy.ops.nwo.project_edit if self._editing else bpy.ops.nwo.project_add
        operator('INVOKE_DEFAULT', resume_settings=True, **self._values)

    def execute(self, context):
        self._values[self.field] = stored_directory(self._root, bpy.path.abspath(self.directory))
        self._restore()
        return {'FINISHED'}

    def cancel(self, context):
        self._restore()


class NWO_OT_ProjectImageBrowse(Operator):
    bl_label = 'Choose Project Image'
    bl_idname = 'nwo.project_image_browse'
    bl_description = 'Choose an image inside the editing kit folder'

    filepath: StringProperty(subtype='FILE_PATH')
    directory: StringProperty(subtype='DIR_PATH')
    filter_image: BoolProperty(default=True, options={'HIDDEN'})
    filter_glob: StringProperty(default='*.jpg;*.jpeg;*.png;*.bmp;*.tif;*.tiff;*.tga;*.webp;*.exr;*.hdr',
                                options={'HIDDEN'})

    def invoke(self, context, event):
        # Share the content-folder browser's unsaved-settings capture and root.
        self.filepath = ''
        return NWO_OT_ProjectDirectoryBrowse.invoke(self, context, event)

    _restore = NWO_OT_ProjectDirectoryBrowse._restore
    cancel = NWO_OT_ProjectDirectoryBrowse.cancel

    def execute(self, context):
        try:
            image = Path(bpy.path.abspath(self.filepath))
            relative = project_image_path(self._root, image)
            if not image.is_file():
                raise ValueError('Select an existing image file')
        except (OSError, ValueError) as error:
            self.report({'WARNING'}, str(error))
            self._restore()
            return {'CANCELLED'}
        self._values['image_path'] = relative
        self._restore()
        return {'FINISHED'}


class NWO_ProjectAdd(Operator):
    bl_label = "Add Project"
    bl_idname = "nwo.project_add"
    bl_description = "Choose the main folder of a Halo editing kit, containing tool.exe, to add a project"

    filepath: StringProperty(
        name="path", description="Set the path to your project", subtype="FILE_PATH"
    )

    filter_folder: BoolProperty(
        default=True,
        options={"HIDDEN"},
    )

    set_scene_project: BoolProperty(options={"HIDDEN"})
    display_name: StringProperty(name="Display Name")
    resume_settings: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})
    tags_directory: StringProperty(name="Tags Folder", default="tags",
                                  description="Halo 1/2 tags folder, absolute or relative to the editing kit")
    data_directory: StringProperty(name="Data Folder", default="data",
                                  description="Halo 1/2 data folder, absolute or relative to the editing kit")

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

        metadata = ProjectJSON()
        if not metadata.parse(new_project_path):
            self.report({'WARNING'}, "Could not load project. Check tool.exe and project.json; see console for details")
            return {'CANCELLED'}
        
        projects_list = read_projects_list()
        if projects_list is None:
            self.report({'ERROR'}, 'Could not read project settings. The existing settings have been preserved')
            return {'CANCELLED'}
        had_no_projects = not projects_list
        name = self.display_name.strip() or unique_project_name(metadata.display_name, get_prefs().projects)
        record = new_project_record(new_project_path, name, self.tags_directory, self.data_directory,
                                    **{field: str(getattr(metadata, 'name' if field == 'project_name' else field, '') or '')
                                       if field != 'image_path' else DEFAULT_PROJECT_IMAGE
                                       for field in PROJECT_FIELDS})
        error = validate_project_configuration(record, projects_list)
        if error:
            self.report({'WARNING'}, error)
            return {'CANCELLED'}
        projects_list.append(record)
        try:
            write_projects_list(projects_list)
        except (OSError, ValueError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        projects = setup_projects_list(report=self.report)

        if projects and (self.set_scene_project or had_no_projects):
            nwo = get_scene_props()
            set_scene_project(nwo, projects[-1])
        if projects and not startup.load_handler_complete:
            startup.initialize_foundry(context)

        if context.area:
            context.area.tag_redraw()
        if had_no_projects and projects:
            self.report({'INFO'}, f'{projects[-1].name} is ready. Create an asset in its data folder to start exporting')
        return {'FINISHED'}
    
    def invoke(self, context, event):
        if not self.resume_settings:
            self.filepath = os.path.dirname(self.filepath)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def draw(self, context):
        self.layout.label(text='Choose the editing kit folder containing tool.exe')
        self.layout.prop(self, 'display_name', text='Display Name (Optional)')
        self.layout.label(text='Halo 1 / Halo 2 content folders')
        self.layout.label(text='Keep tags and data for the standard folders')
        # Do not launch a second file selector from inside the project browser.
        self.layout.prop(self, 'tags_directory')
        self.layout.prop(self, 'data_directory')


def validate_project_configuration(record, records, exclude_id=''):
    root = record['project_path']
    key = configuration_key(record)
    if not record['name'].strip():
        return 'Enter a display name for this project'
    for other in records:
        if other['id'] == exclude_id:
            continue
        if configuration_key(other) == key:
            return 'This editing kit and tags/data folder pair already has a project configuration'
        if other.get('name', '').casefold() == record['name'].casefold():
            return 'A project with this display name already exists'
    for field, default in (('tags_directory', 'tags'), ('data_directory', 'data')):
        path = directory_path(root, record.get(field), default)
        if record.get('game') not in CUSTOM_DIRECTORY_GAMES and path != directory_path(root, default, default):
            return 'Custom tags/data folders are supported by the MCC Halo 1 and Halo 2 editing kits'
        if not path.is_dir():
            return f'{default.title()} folder not found: {path}'
    return None
    
class NWO_ProjectRemove(Operator):
    bl_label = "Remove Project"
    bl_idname = "nwo.project_remove"

    @classmethod
    def poll(self, context):
        prefs = get_prefs()
        return prefs.projects

    def execute(self, context):
        prefs = get_prefs()
        current_project = prefs.projects[prefs.current_project_index].project_id
        projects_list = read_projects_list()
        if projects_list is None:
            self.report({'ERROR'}, 'Could not read project settings')
            return {'CANCELLED'}
        try:
            write_projects_list([record for record in projects_list if record['id'] != current_project])
        except (OSError, ValueError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

        prefs.projects.remove(prefs.current_project_index)
        if prefs.current_project_index > len(prefs.projects) - 1:
            # Removing a configuration must not redirect its scene to another.
            set_project_list_index(prefs, len(prefs.projects) - 1)
        if context.area:
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

        records = read_projects_list()
        if records is None:
            self.report({'ERROR'}, 'Could not read project settings')
            return {'CANCELLED'}
        records.insert(to_index, records.pop(current_index))
        try:
            write_projects_list(records)
        except (OSError, ValueError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        projects.move(current_index, to_index)
        prefs.current_project_index = to_index
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_ProjectEdit(Operator):
    bl_label = "Edit Project Settings"
    bl_idname = "nwo.project_edit"

    display_name: StringProperty(name="Display Name")
    use_project_thumbnail: BoolProperty(name='Use Project Thumbnail', default=False,
                                       description='Use the project image when available instead of the game engine icon')
    image_path: StringProperty(name='Project Image', default=DEFAULT_PROJECT_IMAGE,
                              description='Image inside the editing kit, used when Use Project Thumbnail is enabled')
    project_path: StringProperty(name='Editing Kit Folder', subtype='DIR_PATH')
    tags_directory: StringProperty(name='Tags Folder',
                                  description='Absolute path or folder relative to the editing kit')
    data_directory: StringProperty(name='Data Folder',
                                  description='Absolute path or folder relative to the editing kit')
    duplicate: BoolProperty(options={'HIDDEN'})
    resume_settings: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        return ('Create another project configuration using this editing kit' if properties.duplicate
                else 'Edit this configuration\'s name, editing kit, content folders and image')

    @classmethod
    def poll(cls, context):
        prefs = get_prefs()
        return prefs.projects

    def execute(self, context):
        prefs = get_prefs()
        active_project = prefs.projects[prefs.current_project_index]
        metadata = ProjectJSON()
        root = Path(bpy.path.abspath(self.project_path)).resolve()
        if not metadata.parse(root):
            self.report({'WARNING'}, "Could not update project settings; see console for details")
            return {'CANCELLED'}
        if active_project.game and active_project.game != metadata.game:
            self.report({'WARNING'}, 'The new editing kit must be for the same Halo game')
            return {'CANCELLED'}
        records = read_projects_list()
        if records is None:
            self.report({'ERROR'}, 'Could not read project settings')
            return {'CANCELLED'}
        record = dict(next(entry for entry in records if entry['id'] == active_project.project_id))
        record.update(project_record(active_project))
        record.update(project_path=str(root), name=self.display_name.strip(), game=metadata.game,
                      tags_directory=self.tags_directory, data_directory=self.data_directory,
                      use_project_thumbnail=self.use_project_thumbnail)
        image = self.image_path.strip().strip('"')
        if image.startswith('//'):
            image = bpy.path.abspath(image)
        try:
            record['image_path'] = project_image_path(root, image)
        except (OSError, ValueError) as error:
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
        if self.duplicate:
            record['id'] = new_project_record(root)['id']
            record['last_scenario'] = ''
        error = validate_project_configuration(record, records, '' if self.duplicate else active_project.project_id)
        if error:
            self.report({'WARNING'}, error)
            return {'CANCELLED'}
        old_id, old_name = active_project.project_id, active_project.name
        if self.duplicate:
            records.append(record)
        else:
            records = [record if entry['id'] == old_id else entry for entry in records]
        try:
            write_projects_list(records)
        except (OSError, ValueError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        projects = setup_projects_list(report=self.report)
        if not self.duplicate:
            project = next(project for project in projects if project.project_id == old_id)
            for scene in bpy.data.scenes:
                if scene.nwo.scene_project_id == old_id or (not scene.nwo.scene_project_id and scene.nwo.scene_project == old_name):
                    set_scene_project(scene.nwo, project)
        else:
            prefs.current_project_index = len(projects) - 1
        if context.area:
            context.area.tag_redraw()
        
        return {'FINISHED'}
    
    def invoke(self, context, event):
        prefs = get_prefs()
        active_project = prefs.projects[prefs.current_project_index]
        if not self.resume_settings:
            self.display_name = unique_project_name(active_project.name, prefs.projects) if self.duplicate else active_project.name
            self.image_path = active_project.image_path
            self.use_project_thumbnail = active_project.use_project_thumbnail
            self.project_path = active_project.project_path
            self.tags_directory = stored_directory(active_project.project_path, active_project.tags_directory)
            self.data_directory = stored_directory(active_project.project_path, active_project.data_directory)
        return context.window_manager.invoke_props_dialog(self, width=800,
            title='Duplicate Project' if self.duplicate else 'Edit Project Settings')
        
    def draw(self, context):
        layout = self.layout
        project = get_prefs().projects[get_prefs().current_project_index]
        layout.prop(self, "display_name")
        layout.prop(self, 'project_path')
        layout.prop(self, 'use_project_thumbnail')
        row = layout.row(align=True)
        row.context_pointer_set('project_directory_settings', self)
        row.prop(self, 'image_path')
        row.operator('nwo.project_image_browse', text='', icon='FILE_FOLDER')
        if project.game in CUSTOM_DIRECTORY_GAMES:
            draw_project_directory(layout, self, 'tags_directory')
            draw_project_directory(layout, self, 'data_directory')

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

def _settings_box(layout, title: str, prefs, property_name):
    box = layout.box()
    expanded = getattr(prefs, property_name)
    box.row().prop(prefs, property_name, text=title, icon='TRIA_DOWN' if expanded else 'TRIA_RIGHT', emboss=False)
    return box if expanded else None

def _welcome_text_width(context):
    region = context.region
    if region is None:
        return 300
    scale = context.preferences.system.ui_scale
    # Sidebar zoom is independent of Blender's interface scale.
    if region.type == 'UI':
        view = region.view2d
        zoom = view.region_to_view(1, 0)[0] - view.region_to_view(0, 0)[0]
    else:
        zoom = 1
    # Leave room for the panel margins, box padding and sidebar tabs.
    return max(40, region.width * zoom / scale - 64)


def _welcome_text_lines(text, width, measure):
    lines = []
    line = ''
    for word in text.split():
        candidate = f'{line} {word}' if line else word
        if line and measure(candidate) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def draw_first_project_setup(layout):
    if startup.load_handler_complete:
        return
    import blf
    context = bpy.context
    blf.size(0, context.preferences.ui_styles[0].widget.points)
    width = _welcome_text_width(context)

    def text(layout, message):
        for line in _welcome_text_lines(message, width, lambda value: blf.dimensions(0, value)[0]):
            layout.label(text=line)

    box = layout.box()
    box.label(text='Welcome to Foundry', icon_value=get_icon_id('foundry'))
    col = box.column(align=True)
    text(col, 'Connect an editing kit (project) to enable exporting')
    col.operator('wm.url_open', text='Halo Editing Kits', icon_value=get_icon_id('c20_reclaimers')).url = "https://c20.reclaimers.net/general/mod-tools/"
    text(col, '1. Install your preferred Halo editing kit')
    text(col, '2. Add your project folder using the "Add First Project" button')
    text(col, '3. Use the New Asset button to get started with creating')
    row = box.row(align=True)
    row.operator_context = 'INVOKE_DEFAULT'
    row.operator('nwo.project_add', text='Add First Project', icon='ADD').set_scene_project = True
    # row.operator('wm.url_open', text='Setup Guide', icon='HELP').url = FOUNDRY_GITHUB + '#installation'
    col = box.column(align=True)
    text(col, 'Getting started? Learn about Foundry here')
    col.operator('wm.url_open', text='Foundry Documentation', icon='HELP').url = FOUNDRY_GUIDANCE
    col.separator()
    text(col, 'Specific questions? Use the dedicated Foundry forum in the Halo Mods Discord server')
    col.separator()
    col.operator('wm.url_open', text='Join Discord', icon_value=get_icon_id('discord')).url = HALO_MODS_DISCORD
    # row.operator('wm.url_open', text='Foundry Forum', icon='HELP').url = FOUNDRY_DISCORD_FORUM
    col = box.column(align=True)
    text(col, 'Add a project or load the Foundry panel to begin')
    col = layout.column(align=True)
    text(col, 'Adjust settings now or revisit them later in Foundry Preferences.')
    draw_foundry_preferences(layout, get_prefs(), context, show_setup=False, show_projects=False)


def draw_foundry_preferences(layout, prefs, context=None, show_save_button=False, show_setup=True, show_projects=True):
    if show_setup and not prefs.projects and not startup.load_handler_complete:
        draw_first_project_setup(layout)
        return

    box = _settings_box(layout, "Interface", prefs, 'settings_interface_expanded')
    if box is not None:
        row = box.row(align=True)
        row.prop(prefs, "toolbar_icons_only", text="Toolbar Icons Only")
        row = box.row(align=True)
        row.prop(prefs, "sidebar_icons_only")

    box = _settings_box(layout, "Projects", prefs, 'settings_projects_expanded') if show_projects else None
    if box is not None:
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
        col.operator("nwo.project_edit", icon="DUPLICATE", text="").duplicate = True
        col.separator()
        col.operator("nwo.project_move", text="", icon="TRIA_UP").direction = 'up'
        col.operator("nwo.project_move", icon="TRIA_DOWN", text="").direction = 'down'
        if prefs.projects and 0 <= prefs.current_project_index < len(prefs.projects):
            project = prefs.projects[prefs.current_project_index]
            box.label(text=f'Editing Kit: {project.project_path}')
            if project.game in CUSTOM_DIRECTORY_GAMES:
                box.label(text=f'Tags: {project.tags_directory}')
                box.label(text=f'Data: {project.data_directory}')

    box = _settings_box(layout, "Halo Tools", prefs, 'settings_tools_expanded')
    if box is not None:
        row = box.row(align=True)
        row.label(text="Tag Editor")
        row.prop(prefs, "tag_editor", expand=True)
        if prefs.tag_editor == "baboon":
            row = box.row(align=True)
            row.prop(prefs, "baboon_path")
        row = box.row(align=True, heading="Tool Version")
        row.prop(prefs, "tool_type", expand=True)
        row = box.row(align=True)
        row.prop(prefs, "granny_viewer_path")
        row = box.row(align=True)
        row.prop(prefs, "copy_scenario_path_on_sapien_launch")

    box = _settings_box(layout, "Import & Bitmaps", prefs, 'settings_import_expanded')
    if box is not None:
        row = box.row(align=True)
        row.prop(prefs, "default_import_template")
        row = box.row(align=True)
        row.prop(prefs, "default_dragged_object_type")
        row = box.row(align=True)
        row.prop(prefs, "default_scale_model")
        row = box.row(align=True)
        row.prop(prefs, "import_shaders_with_time_period")
        row = box.row(align=True)
        row.prop(prefs, "link_resource_nodes")
        row = box.row(align=True)
        row.prop(prefs, "bitmap_color_space_conversion")
        row.operator("nwo.install_xrgb_colorspace", text="Install xRGB")

    box = _settings_box(layout, "Objects & Materials", prefs, 'settings_objects_expanded')
    if box is not None:
        row = box.row(align=True, heading="Default Object Prefixes")
        row.prop(prefs, "apply_prefix", expand=True)
        row = box.row(align=True)
        row.prop(prefs, "apply_materials", text="Update Materials on Object Type Change")
        row = box.row(align=True)
        row.prop(prefs, "apply_empty_display")
        row = box.row(align=True)
        row.prop(prefs, "update_materials_on_shader_path")
        row = box.row(align=True)
        row.prop(prefs, "import_classic_shader_emission")
        row = box.row(align=True)
        row.prop(prefs, "rename_halo_collections")
        row = box.row(align=True)
        row.prop(prefs, "rename_material")

    box = _settings_box(layout, "Animation", prefs, 'settings_animation_expanded')
    if box is not None:
        row = box.row(align=True)
        row.prop(prefs, "sync_timeline_range")
        row = box.row(align=True)
        row.prop(prefs, "animation_switch_frame")
        row = box.row(align=True)
        row.prop(prefs, "load_animation_snapshots")
        row = box.row(align=True)
        row.prop(prefs, "ignore_final_frame")
    box = _settings_box(layout, "Advanced", prefs, 'settings_advanced_expanded')
    if box is not None:
        from .utils import get_project
        project = get_project(use_external=False)
        box.prop(prefs, 'allow_tool_patches')
        patches = box.column()
        patches.enabled = prefs.allow_tool_patches
        if project and project.game == 'reach':
            patches.prop(prefs, 'patch_tool_node_depth_sort')
            patches.prop(prefs, 'patch_tool_uncompressed_vertex_weights')
            patches.prop(prefs, 'patch_tool_skip_vertex_compression')
        if project and project.game in {'reach', 'halo4', 'halo2a'}:
            patches.prop(prefs, 'patch_tool_skip_import_source_data')
        box.prop(prefs, 'allow_foundation_plugin_install')
        row = box.row(align=True)
        row.prop(prefs, "debug_menu_on_export")
        row = box.row(align=True)
        row.prop(prefs, "debug_menu_on_launch")

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

    copy_scenario_path_on_sapien_launch: BoolProperty(
        name="Copy Scenario Path on Sapien Launch",
        description="Copy the full scenario tag path to the clipboard when launching Halo 1, Halo 2, Halo 3, or ODST Sapien with an asset scenario",
        default=True,
    )

    tag_editor: EnumProperty(
        name="Tag Editor",
        description="Choose the editor used to open tags",
        default="default",
        items=[
            ("default", "Editing Kit Default", "Use the tag editor included with the current game's editing kit"),
            ("baboon", "Baboon", "Use Baboon when its executable path is valid and its preferences contain a matching editing kit, otherwise use the editing kit's tag editor"),
        ],
    )

    baboon_path: StringProperty(
        name="Baboon Path",
        description="Path to Baboon's executable. An invalid path or no matching editing kit in Baboon's prefs.json falls back to the editing kit's tag editor",
        subtype='FILE_PATH',
    )

    tool_type: EnumProperty(
        name="Tool Type",
        description="Specify whether the add on should use Tool or Tool Fast",
        default="tool_fast",
        items=[("tool_fast", "Tool Fast", ""), ("tool", "Tool", "")],
    )

    current_project : StringProperty()
    current_project_index : bpy.props.IntProperty(update=update_selected_project)

    projects : CollectionProperty(type=NWO_Project_ListItems)

    toolbar_icons_only : BoolProperty(name="Toolbar Icons Only", description="Toggle whether the Foundry Toolbar should only show icons")
    sidebar_icons_only: BoolProperty(
        name="Sidebar Icons Only",
        description="Show only icons in the Foundry sidebar; disable to show panel names beside them",
        default=False,
        update=update_sidebar_icons_only,
    )
    settings_projects_expanded: BoolProperty(default=False)
    settings_tools_expanded: BoolProperty(default=False)
    settings_import_expanded: BoolProperty(default=False)
    settings_objects_expanded: BoolProperty(default=False)
    settings_animation_expanded: BoolProperty(default=False)
    settings_interface_expanded: BoolProperty(default=True)
    settings_advanced_expanded: BoolProperty(default=False)

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

    default_dragged_object_type: EnumProperty(
        name="Dragged Scenario Objects",
        description="Default type for object tags dragged into scenario assets. Object types unsupported as game objects use scenario objects when available",
        default='game_object',
        items=[
            ('game_object', "Game Object", "Use game objects when supported by the destination game"),
            ('scenario_object', "Scenario Object", "Use scenario objects for tags with a scenario placement category"),
        ],
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
            if not prefs.projects:
                draw_first_project_setup(layout)
            return layout.operator("nwo.launch_foundry")
        draw_foundry_preferences(layout, prefs)
        
classes = [
    NWO_Project_ListItems,
    NWO_UL_Projects,
    NWO_OT_ProjectDirectoryBrowse,
    NWO_OT_ProjectImageBrowse,
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

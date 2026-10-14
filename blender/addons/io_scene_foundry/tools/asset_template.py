"""Tag pickers and import-dialog handoff for the New Asset wizard."""
import json
from pathlib import Path

import bpy

from .. import utils
from .asset_creation import MODEL_OUTPUTS, template_tag_extensions, resolve_template_tag
from .asset_types import SUPPORTED_ASSETS
from .get_tag_list import walk_tags_dir

_search_items = {}


def picker_source(settings):
    project = utils.get_project(settings['template_project'], use_external=False)
    if project is None:
        raise ValueError('Choose a valid source project for the asset tag.')
    outputs = tuple(name for name in MODEL_OUTPUTS if settings.get('output_' + name))
    extensions = template_tag_extensions(project.game, settings['asset_type'], settings['object_type'], outputs)
    if settings['asset_type'] not in SUPPORTED_ASSETS.get(project.game, set()):
        extensions = ()
    if not extensions:
        raise ValueError('This asset type has no matching tag in the selected source project.')
    return project, extensions


def remember_picker(self, context):
    # RNA survives Blender's search-popup operator copies; Python attributes do not.
    self.return_window = str(context.window.as_pointer())
    self.return_area = str(context.area.as_pointer())
    settings = json.loads(self.wizard_settings)
    project, extensions = picker_source(settings)
    return settings, project, extensions


def restore_picker(self, settings=None):
    from .asset_creator import _reopen_wizard
    window = next((win for win in bpy.context.window_manager.windows
                   if str(win.as_pointer()) == self.return_window), None)
    if window is None:
        return
    area = next((area for area in window.screen.areas
                 if str(area.as_pointer()) == self.return_area), None)
    settings = settings or json.loads(self.wizard_settings)
    from .asset_wizard_ui import _active
    wizard = next((ui for ui in _active if ui.window == window and ui.area == area), None)
    if wizard is not None:
        wizard.set_field('template_tag', settings['template_tag'])
        wizard.area.tag_redraw()
    else:
        _reopen_wizard(settings, window, area)


def choose_tag(self, value):
    settings = json.loads(self.wizard_settings)
    try:
        project, extensions = picker_source(settings)
        tag = resolve_template_tag(project.tags_directory, value, extensions)
        settings['template_tag'] = str(tag.relative_to(Path(project.tags_directory).resolve()))
    except (ValueError, OSError) as exc:
        self.report({'WARNING'}, str(exc))
    restore_picker(self, settings)
    return {'FINISHED'}


class NWO_OT_AssetWizardTagBrowse(bpy.types.Operator):
    bl_idname = 'nwo.asset_wizard_tag_browse'
    bl_label = 'Choose existing asset tag'
    bl_options = {'INTERNAL'}
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'})
    wizard_settings: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    return_window: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    return_area: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def invoke(self, context, event):
        try:
            settings, project, extensions = remember_picker(self, context)
        except (ValueError, OSError) as exc:
            self.report({'WARNING'}, str(exc))
            restore_picker(self)
            return {'CANCELLED'}
        self.filter_glob = ';'.join('*' + extension for extension in extensions)
        self.filepath = str(Path(project.tags_directory)) + '/'
        if settings['template_tag']:
            try:
                self.filepath = str(resolve_template_tag(project.tags_directory, settings['template_tag'], extensions))
            except (ValueError, OSError):
                pass
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        return choose_tag(self, self.filepath)

    def cancel(self, context):
        restore_picker(self)


class NWO_OT_AssetWizardTagSearch(bpy.types.Operator):
    bl_idname = 'nwo.asset_wizard_tag_search'
    bl_label = 'Search existing asset tags'
    bl_description = 'Search matching tags in the selected source project'
    bl_property = 'tag_list'
    bl_options = {'INTERNAL'}
    wizard_settings: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    return_window: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})
    return_area: bpy.props.StringProperty(options={'HIDDEN', 'SKIP_SAVE'})

    def tag_list_items(self, context):
        try:
            project, extensions = picker_source(json.loads(self.wizard_settings))
        except (ValueError, KeyError, OSError):
            return []
        key = (project.tags_directory, extensions)
        if key not in _search_items:
            _search_items[key] = [(path, path, '') for path in
                                 walk_tags_dir(project.tags_directory, extensions, source_project=project)]
        return _search_items[key]

    tag_list: bpy.props.EnumProperty(name='Tags', items=tag_list_items)

    def invoke(self, context, event):
        try:
            _, project, extensions = remember_picker(self, context)
        except (ValueError, OSError) as exc:
            self.report({'WARNING'}, str(exc))
            restore_picker(self)
            return {'CANCELLED'}
        _search_items.pop((project.tags_directory, extensions), None)
        if not self.tag_list_items(context):
            self.report({'WARNING'}, 'No matching asset tags were found in the source project.')
            restore_picker(self)
            return {'CANCELLED'}
        context.window_manager.invoke_search_popup(self)
        return {'FINISHED'}

    def execute(self, context):
        return choose_tag(self, self.tag_list)

    def cancel(self, context):
        restore_picker(self)


def open_template_import(operator, context, scene):
    source = utils.get_project(operator.template_project, use_external=False)
    tag = operator.template_path()
    convert = source.project_id != operator.project
    options = dict(filepath=str(tag), files=[], directory='', scope='',
                   source_tags_directory=source.tags_directory,
                   source_data_directory=source.data_directory, from_file_browser=True,
                   source_project_id=source.project_id,
                   from_asset_wizard=True, build_materials_for_project=convert,
                   convert_animations=convert)
    window, area = context.window, context.area
    def open_dialog():
        if not any(win == window for win in bpy.context.window_manager.windows):
            return
        target = next((item for item in window.screen.areas if item == area), None)
        if target is None:
            target = next((item for item in window.screen.areas if item.type == 'VIEW_3D'), None)
        if target is not None:
            window.scene = scene
            with bpy.context.temp_override(window=window, area=target):
                bpy.ops.nwo.import_from_drop('INVOKE_DEFAULT', **options)
    # Let the modal wizard finish before the import dialog receives input.
    bpy.app.timers.register(open_dialog, first_interval=.05)

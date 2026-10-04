"""Session-only first-project testing, exposed through operator search."""
from pathlib import Path
import tempfile

import bpy

from .. import startup, utils


_session = None
_selection_fields = ('scene_project', 'scene_project_id', 'scene_project_snapshot')


def restore_new_user_debug():
    """Restore without rewriting the user's persisted project settings."""
    global _session
    if _session is None:
        return False
    session = _session
    prefs = utils.get_prefs()
    utils._projects_settings_override = session['settings_override']
    prefs.projects.clear()
    for values in session['projects']:
        project = prefs.projects.add()
        for field, value in values.items():
            setattr(project, field, value)
    for scene in bpy.data.scenes:
        selection = session['selections'].get(scene.session_uid)
        if selection is not None:
            for field, value in zip(_selection_fields, selection):
                setattr(scene.nwo, field, value)
            scene.nwo.is_main_scene = session['main_scenes'][scene.session_uid]
        else:
            scene.nwo.is_main_scene = False
            project = utils.resolve_scene_project(prefs.projects, scene.nwo.scene_project_id,
                                                  scene.nwo.scene_project, scene.nwo.scene_project_snapshot)
            if project is None:
                scene.nwo.scene_project = ''
            else:
                utils.set_scene_project(scene.nwo, project)
    scenes = {scene.session_uid: scene for scene in bpy.data.scenes}
    for window in bpy.context.window_manager.windows:
        scene = scenes.get(session['window_scenes'].get(window.as_pointer()))
        if scene is not None:
            window.scene = scene
    utils.set_project_list_index(prefs, session['index'])
    startup.load_handler_complete = session['loaded']
    utils.clear_external_project()
    debug_scene = scenes.get(session['debug_scene'])
    # Keep any work created while testing. An untouched empty scene is disposable.
    if debug_scene is not None and not debug_scene.objects and len(bpy.data.scenes) > 1:
        bpy.data.scenes.remove(debug_scene)
    _session = None
    session['temporary'].cleanup()
    return True


def start_new_user_debug(context):
    global _session
    if _session is not None:
        return False
    prefs = utils.get_prefs()
    temporary = tempfile.TemporaryDirectory(prefix='foundry_new_user_', ignore_cleanup_errors=True)
    _session = {
        'temporary': temporary,
        'settings_override': utils._projects_settings_override,
        'projects': [{prop.identifier: getattr(project, prop.identifier)
                      for prop in project.bl_rna.properties if not prop.is_readonly}
                     for project in prefs.projects],
        'index': prefs.current_project_index,
        'selections': {scene.session_uid: tuple(getattr(scene.nwo, field) for field in _selection_fields)
                       for scene in bpy.data.scenes},
        'main_scenes': {scene.session_uid: scene.nwo.is_main_scene for scene in bpy.data.scenes},
        'window_scenes': {window.as_pointer(): window.scene.session_uid
                          for window in context.window_manager.windows},
        'loaded': startup.load_handler_complete,
        'debug_scene': None,
    }
    try:
        utils._projects_settings_override = Path(temporary.name, 'projects.json')
        prefs.projects.clear()
        utils.set_project_list_index(prefs, 0)
        utils.clear_external_project()
        scene = bpy.data.scenes.new('Foundry New User Debug')
        _session['debug_scene'] = scene.session_uid
        for existing in bpy.data.scenes:
            existing.nwo.is_main_scene = existing == scene
        context.window.scene = scene
        startup.load_handler_complete = False
    except Exception:
        restore_new_user_debug()
        raise
    return True


class NWO_OT_DebugNewUserExperience(bpy.types.Operator):
    bl_idname = 'nwo.debug_new_user_experience'
    bl_label = 'Debug New User Experience'
    bl_options = set()
    bl_description = ('Toggle a fresh scene and temporary project list to test Foundry setup; '
                      'run again to restore your projects and previous scene')

    @classmethod
    def poll(cls, context):
        return context.window is not None and context.scene is not None and hasattr(context.scene, 'nwo')

    def execute(self, context):
        try:
            if _session is None:
                start_new_user_debug(context)
                message = 'New-user debug started. Use Load Foundry Panel or add a project; run this operator again to restore'
            else:
                restore_new_user_debug()
                message = 'Original Foundry projects and scene restored; any debug scene containing objects was kept'
        except (OSError, ValueError, RuntimeError) as error:
            self.report({'ERROR'}, f'Could not toggle new-user debug: {error}')
            return {'CANCELLED'}
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
        self.report({'INFO'}, message)
        return {'FINISHED'}

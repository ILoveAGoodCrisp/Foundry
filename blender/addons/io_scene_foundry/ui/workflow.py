"""Shared workflow guidance and explicit, cached asset checks.

Drawing never scans scene objects. Checks run on request; dependency updates,
file loads, undo, and relevant RNA changes invalidate their session cache.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import textwrap
import time

import bpy
from bpy.app.handlers import persistent

from .. import utils
from ..constants import VALID_MESHES

GAME_NAMES = {'halo1': 'Halo 1', 'halo2': 'Halo 2', 'halo3': 'Halo 3',
              'halo3odst': 'Halo 3 ODST', 'reach': 'Halo Reach',
              'halo4': 'Halo 4', 'halo2a': 'Halo 2 Anniversary MP'}
PANEL_NAMES = {'scene_properties': 'Scene', 'asset_editor': 'Asset',
               'sets_manager': 'Sets', 'object_properties': 'Object',
               'material_properties': 'Material', 'animation_manager': 'Animation',
               'tools': 'Tools', 'help': 'Help', 'settings': 'Settings'}


@dataclass(frozen=True)
class Finding:
    level: str
    message: str
    panel: str = 'asset_editor'
    object_name: str = ''
    material_name: str = ''


_checks = {}
_visibility = {}
_owner = object()


def draw_text(layout, message, context=None, icon='NONE'):
    """Wrap guidance and paths at the available sidebar or dialog width."""
    context = context or bpy.context
    region = getattr(context, 'region', None)
    width = getattr(region, 'width', 360)
    if region is not None and region.type == 'UI':
        width *= abs(region.view2d.region_to_view(1, 0)[0] - region.view2d.region_to_view(0, 0)[0])
    scale = context.preferences.system.ui_scale or 1.0
    columns = max(18, min(95, int((width / scale - 64) / 7)))
    for index, line in enumerate(textwrap.wrap(str(message), columns) or ['']):
        layout.label(text=line, icon=icon if index == 0 else 'NONE', translate=False)






def asset_destination(nwo, project):
    if project is None:
        return None
    raw = nwo.parent_sidecar if nwo.is_child_asset and nwo.parent_sidecar else nwo.sidecar_path
    if raw:
        path = Path(bpy.path.abspath(raw))
        return (path if path.is_absolute() else Path(project.data_directory, path)).parent
    legacy_path = getattr(nwo, 'legacy_asset_path', '')
    # Legacy export stores its destination on the export settings.
    owner_scene = getattr(nwo, 'id_data', None)
    if owner_scene is not None and hasattr(owner_scene, 'nwo_export'):
        legacy_path = owner_scene.nwo_export.legacy_asset_path or legacy_path
    if legacy_path:
        return Path(bpy.path.abspath(legacy_path))
    if nwo.asset_type == 'single_animation' and bpy.data.filepath:
        return Path(bpy.data.filepath).parent
    return None


def export_scope_lines(nwo, settings):
    mode = {'FULL': 'Intermediate files and game tags', 'GRANNY': 'Intermediate files only',
            'TAGS': 'Game tags from existing intermediate files'}.get(settings.export_mode, settings.export_mode)
    lines = [mode]
    asset_type = nwo.asset_type
    if asset_type in {'model', 'sky'}:
        components = [label for name, label in (('export_render', 'Render'), ('export_collision', 'Collision'),
                                                ('export_physics', 'Physics')) if getattr(settings, name, False)]
        lines.append('Geometry: ' + (', '.join(components) or 'None'))
    elif asset_type in {'scenario', 'prefab'}:
        components = [label for name, label in (('export_structure', 'Structure'), ('export_design', 'Design'))
                      if getattr(settings, name, False)]
        lines.append('Geometry: ' + (', '.join(components) or 'None'))
    if asset_type in {'model', 'sky', 'scenario', 'prefab'}:
        noun = 'layers' if asset_type in {'scenario', 'prefab'} else 'permutations'
        lines.append(f'All {noun}' if settings.export_all_permutations
                     else f'{noun.title()}: {settings.export_specific_perm or "None selected"}')
    if asset_type == 'scenario':
        lines.append('All BSPs' if settings.lightmap_all_bsps else f'BSP: {settings.lightmap_specific_bsp or "None selected"}')
    if asset_type in {'model', 'animation', 'single_animation'}:
        scope = getattr(settings, 'export_animations', 'ALL')
        lines.append('Animations: ' + {'ALL': 'All enabled', 'ACTIVE': 'Active only', 'NONE': 'None'}.get(scope, scope))
    if asset_type in {'model', 'animation'}:
        lines.append('Skeleton: ' + ('Enabled' if settings.export_skeleton else 'Off'))
    if asset_type == 'cinematic':
        scope = getattr(settings, 'cinematic_scope', 'BOTH')
        lines.append('Cinematic: ' + {'BOTH': 'Cameras and actors', 'CAMERA': 'Cameras only',
                                      'OBJECT': 'Actors only'}.get(scope, scope.title()))
        if getattr(settings, 'current_scene_only', False):
            lines.append('Current cinematic scene only')
        if getattr(settings, 'current_shot_only', False):
            lines.append('Current shot only')
        if settings.selected_cinematic_objects_only:
            lines.append('Selected actors only')
    if asset_type == 'camera_track_set':
        lines.append('Camera tracks: ' + getattr(settings, 'camera_track_scope', 'ALL').title())
    if asset_type in {'multi_model', 'multi_prefab'}:
        lines.append('Selected collections only' if settings.active_collections_only else 'All asset collections')
    if asset_type in {'scenario', 'model', 'sky'}:
        lines.append('Lighting: ' + ('Enabled' if settings.lightmap_structure else 'Off'))
    return lines


def draw_export_scope(layout, nwo, settings, context=None):
    layout.label(text='Next Export', icon='EXPORT')
    for line in export_scope_lines(nwo, settings):
        draw_text(layout, line, context)


def draw_export_controls(layout, nwo, settings, context=None):
    """Use identical names and semantics in both export entry points."""
    layout.prop(settings, 'export_quick', text='Use Saved Settings')
    layout.prop(settings, 'show_output', text='Open Output on Export')
    layout.operator('nwo.show_foundry_output', text='Open Foundry Output', icon='CONSOLE')
    layout.prop(nwo, 'workflow_export_scope_expanded', text='Export Scope',
                icon='TRIA_DOWN' if nwo.workflow_export_scope_expanded else 'TRIA_RIGHT', emboss=False)
    if nwo.workflow_export_scope_expanded:
        draw_export_scope(layout, nwo, settings, context)
        destination = asset_destination(nwo, utils.get_project(use_external=False))
        if destination:
            draw_text(layout, f'Destination: {destination}', context)
            layout.operator('nwo.workflow_open_destination', text='Open Asset Folder', icon='FILE_FOLDER')
    if nwo.workflow_export_result:
        layout.prop(nwo, 'workflow_export_result_expanded', text='Last Export: ' + nwo.workflow_export_result.replace('_', ' ').title(),
                    icon='TRIA_DOWN' if nwo.workflow_export_result_expanded else 'TRIA_RIGHT', emboss=False)
        if nwo.workflow_export_result_expanded:
            draw_text(layout, f'{nwo.workflow_export_time} · {nwo.workflow_export_seconds:.1f}s', context)
            draw_text(layout, nwo.workflow_export_message, context)
            layout.operator('nwo.workflow_copy_diagnostics', text='Copy Export Details', icon='COPYDOWN')


def _fingerprint(context):
    nwo = utils.get_scene_props()
    project = utils.get_project(use_external=False)
    settings = utils.get_export_props()
    return (context.view_layer.name, bpy.data.filepath, nwo.scene_project, nwo.asset_type,
            nwo.sidecar_path, nwo.parent_sidecar, nwo.parent_asset, nwo.is_child_asset,
            settings.legacy_asset_path, tuple(export_scope_lines(nwo, settings)),
            tuple(getattr(project, name, '') for name in ('project_path', 'tags_directory', 'data_directory', 'game', 'available')))


def checked_state(context):
    state = _checks.get(context.scene.as_pointer())
    if state is not None and state['fingerprint'] != _fingerprint(context):
        state['stale'] = True
    return state


def check_asset(context):
    """Read existing export rules without altering geometry or writing tags."""
    nwo = utils.get_scene_props()
    settings = utils.get_export_props()
    project = utils.get_project(use_external=False)
    findings = []
    def add(level, message, panel='asset_editor', ob=None, mat=None):
        findings.append(Finding(level, message, panel, ob.name if ob else '', mat.name if mat else ''))

    error = utils.validate_ek()
    if error:
        add('ERROR', error, 'settings')
    if nwo.asset_type == 'resource':
        add('INFO', 'Resource scenes are reusable authoring data and do not export directly.')
    elif nwo.asset_type == 'single_animation' and not bpy.data.filepath:
        add('ERROR', 'Save this animation blend file before exporting.')
    elif not nwo.is_valid_asset and not (nwo.is_child_asset and nwo.asset_type in {'animation', 'single_animation'}):
        add('ERROR', 'Create an asset in the project data folder before using saved export settings.')
    destination = asset_destination(nwo, project)
    if destination is not None and project is not None:
        if not destination.resolve().is_relative_to(Path(project.data_directory).resolve()):
            add('ERROR', 'The asset destination is outside this project data folder.')
    if nwo.is_child_asset and not (nwo.parent_asset or nwo.parent_sidecar):
        add('ERROR', 'This child asset needs a parent asset path.')

    objects = list(context.view_layer.objects)
    disabled_count = sum(not ob.nwo.export_this for ob in objects)
    if disabled_count:
        add('INFO', f'{disabled_count} objects are explicitly excluded from export.', 'object_properties')
    exportable = []
    materials = set()
    for ob in objects:
        if not ob.nwo.export_this or ob.nwo.ignore_for_export:
            if ob.nwo.export_this and ob.nwo.ignore_for_export:
                add('INFO', f'{ob.name}: excluded by the export rules; inspect its parent or collection.',
                    'object_properties', ob)
            continue
        exportable.append(ob)
        if ob.type in VALID_MESHES:
            materials.update(slot.material for slot in ob.material_slots if slot.material)
        if ob.type == 'ARMATURE':
            game = project.game if project else 'reach'
            # Use the existing rig warning flags for limits rather than imposing
            # a different bone-count convention on control rigs.
            if nwo.too_many_bones:
                add('WARNING', f'{ob.name}: rig exceeds this game\'s bone limit.', 'tools', ob)
            long_names = [bone.name for bone in ob.data.bones if bone.use_deform and len(bone.name) > 31]
            if long_names:
                add('WARNING', f'{ob.name}: {len(long_names)} deform bone names exceed 31 characters.', 'tools', ob)
    if not exportable and nwo.asset_type not in {'resource', 'cinematic', 'camera_track_set'} and settings.export_mode != 'TAGS':
        add('WARNING', 'No objects are currently eligible for export.', 'object_properties')
    for mat in sorted(materials, key=lambda item: item.name.casefold()):
        if mat.nwo.SpecialMaterial or mat.nwo.ConventionMaterial:
            continue
        path = mat.nwo.shader_path.strip()
        if not path:
            add('WARNING', f'{mat.name}: no game shader or material tag is assigned.', 'material_properties', mat=mat)
        elif project is not None:
            tag_path = (Path(project.tags_directory) / path).resolve()
            if not tag_path.is_relative_to(Path(project.tags_directory).resolve()):
                add('WARNING', f'{mat.name}: the assigned tag is outside this project tags folder.', 'material_properties', mat=mat)
            elif not tag_path.is_file():
                add('WARNING', f'{mat.name}: the assigned game tag was not found.', 'material_properties', mat=mat)
    for line in export_scope_lines(nwo, settings):
        if line == 'Geometry: None' and settings.export_mode != 'TAGS':
            add('WARNING', 'No geometry components are enabled in the export scope.')
        elif 'None selected' in line:
            add('ERROR', line + '. Choose an export scope.')
    if settings.export_mode == 'TAGS':
        add('INFO', 'Tags Only uses existing intermediate files; scene geometry is not rebuilt.')
    if nwo.asset_type in {'model', 'animation'}:
        enabled = [anim for anim in nwo.animations if anim.export_this]
        names = set()
        for anim in enabled:
            if anim.name in names:
                add('WARNING', f'{anim.name}: duplicate animation name.', 'animation_manager')
            names.add(anim.name)
            if anim.frame_end < anim.frame_start:
                add('ERROR', f'{anim.name}: end frame is before start frame.', 'animation_manager')
            if anim.external and (not anim.gr2_path or not Path(bpy.path.abspath(anim.gr2_path)).is_file()):
                add('WARNING', f'{anim.name}: external animation file was not found.', 'animation_manager')
    for prop, message in (('invalid_root_bone', 'The root bone needs repair.'),
                          ('pose_bones_bad_transforms', 'Pose bones have invalid transforms.')):
        if getattr(nwo, prop, False):
            add('WARNING', message, 'tools')
    state = dict(findings=findings, fingerprint=_fingerprint(context), stale=False,
                 checked_at=time.strftime('%H:%M:%S'), objects=len(exportable), materials=len(materials))
    _checks[context.scene.as_pointer()] = state
    return state


def record_export(nwo, outcome, message, elapsed):
    nwo.workflow_export_result = outcome
    nwo.workflow_export_message = message
    nwo.workflow_export_seconds = elapsed
    nwo.workflow_export_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    _checks.pop(nwo.id_data.as_pointer(), None)


def draw_asset_checks(layout, context):
    nwo = utils.get_scene_props()
    box = layout.box()
    row = box.row(align=True)
    row.prop(nwo, 'workflow_checks_expanded', text='Asset Check',
             icon='TRIA_DOWN' if nwo.workflow_checks_expanded else 'TRIA_RIGHT', emboss=False)
    if not nwo.workflow_checks_expanded:
        return
    box.operator('nwo.check_asset', text='Check Asset', icon='CHECKMARK')
    state = checked_state(context)
    if state is None:
        box.label(text='Readiness not checked')
    elif state['stale']:
        box.label(text='Asset changed · check again', icon='FILE_REFRESH')
    else:
        errors = sum(item.level == 'ERROR' for item in state['findings'])
        warnings = sum(item.level == 'WARNING' for item in state['findings'])
        box.label(text=f'{errors} required fixes · {warnings} warnings', icon='ERROR' if errors else 'CHECKMARK')
        draw_findings(box, state, context)


def draw_findings(layout, state, context):
    for level, title in (('ERROR', 'Required Fixes'), ('WARNING', 'Warnings'), ('INFO', 'Information')):
        findings = [(i, item) for i, item in enumerate(state['findings']) if item.level == level]
        if not findings:
            continue
        section = layout.box()
        section.label(text=f'{title} ({len(findings)})')
        for index, item in findings[:20]:
            draw_text(section, item.message, context, 'ERROR' if level == 'ERROR' else 'NONE')
            section.operator('nwo.workflow_focus_finding', text='Select and Inspect' if item.object_name or item.material_name else 'Go to Setting', icon='VIEWZOOM').index = index
        if len(findings) > 20:
            section.label(text=f'{len(findings) - 20} more; see Foundry Output')


def controlling_collection(ob, kind):
    collections = tuple(bpy.context.scene.collection.children_recursive)
    matches, preferred = [], []
    for coll in ob.users_collection:
        for chain in utils.get_collection_parent_chains(coll, collections):
            owner = next((item for item in chain if item.nwo.type == kind), None)
            if owner is not None:
                matches.append(owner)
                if bpy.context.collection in chain:
                    preferred.append(owner)
    return (preferred or matches or [None])[-1]


def has_visibility_snapshot(context):
    return (context.scene.as_pointer(), context.view_layer.name) in _visibility


class NWO_OT_WorkflowVisibility(bpy.types.Operator):
    bl_idname = 'nwo.workflow_visibility'
    bl_label = 'Manage Viewport Visibility'
    bl_description = 'Show or isolate objects in this view layer, then restore the previous visibility; export settings stay unchanged'
    bl_options = {'UNDO'}
    action: bpy.props.EnumProperty(items=[('SHOW', 'Show All', ''), ('ISOLATE', 'Isolate Selected', ''), ('RESTORE', 'Restore Visibility', '')])

    def execute(self, context):
        from ..tools.object_visibility import visibility_items
        key = (context.scene.as_pointer(), context.view_layer.name)
        nwo = utils.get_scene_props()
        project = utils.get_project(use_external=False)
        if self.action == 'RESTORE':
            state = _visibility.pop(key, None)
            if state is None:
                self.report({'INFO'}, 'There is no saved visibility to restore')
                return {'CANCELLED'}
            for name, value in state['types'].items():
                setattr(nwo, name, value)
            for table, values in state['sets'].items():
                for item in getattr(nwo, table):
                    if item.name in values:
                        item.hidden = values[item.name]
            for ob in context.view_layer.objects:
                if ob.name in state['objects']:
                    ob.hide_set(state['objects'][ob.name])
            return {'FINISHED'}
        if self.action == 'ISOLATE' and not context.selected_objects:
            self.report({'WARNING'}, 'Select objects to isolate first')
            return {'CANCELLED'}
        types = {f'{kind[1:]}_visible': getattr(nwo, f'{kind[1:]}_visible')
                 for kind, _, _ in visibility_items(nwo.asset_type, project.game if project else 'reach')}
        _visibility.setdefault(key, dict(objects={ob.name: ob.hide_get() for ob in context.view_layer.objects},
            types=types, sets={table: {item.name: item.hidden for item in getattr(nwo, table)}
                               for table in ('regions_table', 'permutations_table')}))
        if self.action == 'SHOW':
            for name in types:
                setattr(nwo, name, True)
            for table in ('regions_table', 'permutations_table'):
                for item in getattr(nwo, table):
                    item.hidden = False
        selected = set(context.selected_objects)
        for ob in context.view_layer.objects:
            ob.hide_set(self.action == 'ISOLATE' and ob not in selected)
        return {'FINISHED'}


class NWO_OT_WorkflowSelectCollection(bpy.types.Operator):
    bl_idname = 'nwo.workflow_select_collection'
    bl_label = 'Inspect Controlling Collection'
    collection_name: bpy.props.StringProperty()

    def execute(self, context):
        def find(layer):
            if layer.collection.name == self.collection_name:
                return layer
            for child in layer.children:
                match = find(child)
                if match:
                    return match
        layer = find(context.view_layer.layer_collection)
        if layer is None:
            self.report({'WARNING'}, 'This collection is not in the active view layer')
            return {'CANCELLED'}
        context.view_layer.active_layer_collection = layer
        utils.get_scene_props().sets_manager_active = True
        utils.get_scene_props().sets_manager_expanded = True
        self.report({'INFO'}, f'Active collection: {self.collection_name}. Edit its assignments in the Outliner Halo Collection menu')
        return {'FINISHED'}


class NWO_OT_WorkflowResetFilters(bpy.types.Operator):
    bl_idname = 'nwo.workflow_reset_filters'
    bl_label = 'Reset List Filters'

    def execute(self, context):
        ui_list = getattr(context, 'foundry_ui_list', None)
        if ui_list is None:
            return {'CANCELLED'}
        ui_list.filter_name = ''
        for prop in ui_list.bl_rna.properties:
            if prop.identifier.startswith('use_filter_') and prop.identifier != 'use_filter_show' and not prop.is_readonly:
                setattr(ui_list, prop.identifier, prop.default)
        return {'FINISHED'}


class NWO_OT_WorkflowJumpEvent(bpy.types.Operator):
    bl_idname = 'nwo.workflow_jump_event'
    bl_label = 'Jump to Event'
    frame: bpy.props.IntProperty()

    def execute(self, context):
        context.scene.frame_set(self.frame)
        return {'FINISHED'}


class NWO_OT_CheckAsset(bpy.types.Operator):
    bl_idname = 'nwo.check_asset'
    bl_label = 'Check Asset'
    bl_description = 'Check the active view layer and connected asset settings, including project, destination, materials and animation references, without writing tags'

    @classmethod
    def poll(cls, context):
        return context.scene is not None and not utils.get_scene_props().export_in_progress

    def execute(self, context):
        # Flush pending updates before storing the cache so the check does not
        # immediately invalidate itself on the next redraw.
        context.view_layer.update()
        state = check_asset(context)
        utils.get_scene_props().workflow_checks_expanded = True
        for item in state['findings']:
            print(f'Asset check [{item.level}]: {item.message}')
        errors = sum(item.level == 'ERROR' for item in state['findings'])
        warnings = sum(item.level == 'WARNING' for item in state['findings'])
        self.report({'WARNING'} if errors else {'INFO'}, f'Asset check: {errors} required fixes, {warnings} warnings')
        return {'FINISHED'}


class NWO_OT_WorkflowFocusFinding(bpy.types.Operator):
    bl_idname = 'nwo.workflow_focus_finding'
    bl_label = 'Inspect Asset Finding'
    bl_description = 'Select the affected object or material and open the related Foundry panel'
    index: bpy.props.IntProperty()

    def execute(self, context):
        state = checked_state(context)
        if state is None or state['stale'] or not 0 <= self.index < len(state['findings']):
            self.report({'WARNING'}, 'Run Check Asset again before inspecting this result')
            return {'CANCELLED'}
        item = state['findings'][self.index]
        ob = context.view_layer.objects.get(item.object_name) if item.object_name else None
        if item.material_name:
            ob = next((candidate for candidate in context.view_layer.objects
                       if any(slot.material and slot.material.name == item.material_name for slot in candidate.material_slots)), ob)
        if ob:
            if context.object and context.object.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            for selected in context.selected_objects:
                selected.select_set(False)
            ob.hide_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
            if item.material_name:
                ob.active_material_index = next(i for i, slot in enumerate(ob.material_slots)
                                                if slot.material and slot.material.name == item.material_name)
        nwo = utils.get_scene_props()
        setattr(nwo, item.panel + '_active', True)
        setattr(nwo, item.panel + '_expanded', True)
        return {'FINISHED'}


class NWO_OT_WorkflowProjectSettings(bpy.types.Operator):
    bl_idname = 'nwo.workflow_project_settings'
    bl_label = 'Edit Scene Project'
    bl_description = 'Edit the project connected to this asset'

    def execute(self, context):
        project = utils.get_project(use_external=False)
        prefs = utils.get_prefs()
        if project is None:
            return bpy.ops.nwo.project_add('INVOKE_DEFAULT', set_scene_project=True)
        # Changing this index ordinarily switches projects, so only select the
        # already active project here.
        index = next((i for i, item in enumerate(prefs.projects) if item.project_id == project.project_id), -1)
        if index < 0:
            self.report({'WARNING'}, 'Select an available project first')
            return {'CANCELLED'}
        utils.set_project_list_index(prefs, index)
        return bpy.ops.nwo.project_edit('INVOKE_DEFAULT')


class NWO_OT_WorkflowOpenDestination(bpy.types.Operator):
    bl_idname = 'nwo.workflow_open_destination'
    bl_label = 'Open Asset Folder'

    def execute(self, context):
        path = asset_destination(utils.get_scene_props(), utils.get_project(use_external=False))
        if path is None or not path.is_dir():
            self.report({'WARNING'}, 'The asset folder does not exist yet. Create the asset first')
            return {'CANCELLED'}
        return bpy.ops.wm.path_open(filepath=str(path))


class NWO_OT_WorkflowCopyDiagnostics(bpy.types.Operator):
    bl_idname = 'nwo.workflow_copy_diagnostics'
    bl_label = 'Copy Export Details'

    def execute(self, context):
        nwo = utils.get_scene_props()
        project = utils.get_project(use_external=False)
        context.window_manager.clipboard = '\n'.join((
            f'Foundry {utils.get_version_string()} / Blender {bpy.app.version_string}',
            f'Project: {project.name if project else "Unavailable"}',
            f'Asset: {nwo.asset_name} ({nwo.asset_type})',
            f'Export: {nwo.workflow_export_result} / {nwo.workflow_export_seconds:.1f}s / {nwo.workflow_export_time}',
            nwo.workflow_export_message, 'Scope: ' + '; '.join(export_scope_lines(nwo, utils.get_export_props())),
            'Use Copy All in Foundry Output to include the complete log.'))
        self.report({'INFO'}, 'Export details copied')
        return {'FINISHED'}




@persistent
def invalidate_checks(*args):
    for state in _checks.values():
        state['stale'] = True


@persistent
def clear_checks(*args):
    _checks.clear()
    _visibility.clear()


@persistent
def reload_checks(*args):
    clear_checks()
    subscribe_checks()


def register():
    for handlers, callback in ((bpy.app.handlers.depsgraph_update_post, invalidate_checks),
                               (bpy.app.handlers.undo_post, clear_checks),
                               (bpy.app.handlers.redo_post, clear_checks),
                               (bpy.app.handlers.load_post, reload_checks)):
        if callback not in handlers:
            handlers.append(callback)
    subscribe_checks()


def subscribe_checks():
    bpy.msgbus.clear_by_owner(_owner)
    # Property-group changes do not always produce a dependency update. The
    # message bus covers those changes without walking objects during draw.
    from ..props import object, mesh, material, collection, scene
    from ..preferences import NWO_Project_ListItems
    from .bar import NWO_HaloExportPropertiesGroup
    for cls in (object.NWO_ObjectPropertiesGroup, mesh.NWO_MeshPropertiesGroup,
                material.NWO_MaterialPropertiesGroup, collection.NWO_CollectionPropertiesGroup,
                scene.NWO_ScenePropertiesGroup, scene.NWO_AnimationPropertiesGroup,
                NWO_Project_ListItems, NWO_HaloExportPropertiesGroup):
        for prop in cls.bl_rna.properties:
            name = prop.identifier
            if name == 'rna_type' or name.startswith('workflow_') or name.endswith(('_active', '_expanded', '_pinned', '_index')):
                continue
            bpy.msgbus.subscribe_rna(key=(cls, name), owner=_owner, args=(), notify=invalidate_checks)


def unregister():
    bpy.msgbus.clear_by_owner(_owner)
    for handlers, callback in ((bpy.app.handlers.depsgraph_update_post, invalidate_checks),
                               (bpy.app.handlers.undo_post, clear_checks),
                               (bpy.app.handlers.redo_post, clear_checks),
                               (bpy.app.handlers.load_post, reload_checks)):
        if callback in handlers:
            handlers.remove(callback)
    _checks.clear()
    _visibility.clear()


classes = (NWO_OT_CheckAsset, NWO_OT_WorkflowFocusFinding, NWO_OT_WorkflowProjectSettings,
           NWO_OT_WorkflowOpenDestination, NWO_OT_WorkflowCopyDiagnostics,
           NWO_OT_WorkflowVisibility, NWO_OT_WorkflowSelectCollection, NWO_OT_WorkflowResetFilters, NWO_OT_WorkflowJumpEvent)

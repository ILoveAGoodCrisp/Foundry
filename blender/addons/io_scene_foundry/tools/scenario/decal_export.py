"""Export existing Halo 1 decal controls without rebuilding the scenario."""
from pathlib import Path
import shutil
import struct

import bpy
from bpy_extras.io_utils import ExportHelper

from ... import import_transform, utils
from ...tags.halo1_decals import placement_values
from ...tags.scenario import ScenarioDecalUpdate, ScenarioDocument


def decal_controls(context):
    """Selected controls or previews take priority; otherwise use the scene."""
    selected = []
    for ob in context.selected_objects:
        control = ob.parent if ob.get('halo1_decal_preview') else ob
        if control is not None and control.get('halo1_decal_placement') and control not in selected:
            selected.append(control)
    return selected or [ob for ob in context.scene.objects if ob.get('halo1_decal_placement')]


def source_scenario(controls, tags_root):
    sources = {str(ob['halo1_source_scenario']).replace('\\', '/') for ob in controls}
    if len(sources) != 1:
        raise ValueError('Select decal controls from one imported scenario')
    path = (Path(tags_root) / sources.pop()).resolve()
    if path.suffix.lower() != '.scenario' or not path.is_relative_to(Path(tags_root).resolve()):
        raise ValueError('The controls do not identify a scenario inside the current tags folder')
    for control in controls:
        root = control.get('halo1_source_tags_root')
        if root is not None and Path(root).resolve() != Path(tags_root).resolve():
            raise ValueError('These decals were imported from a different project')
    return path


def export_decal_placements(controls, destination, *, tags_root):
    """Save validated placement edits, retaining every other scenario row.

    A new destination starts from the imported scenario. An existing target
    supplies its own non-decal data. All rows are validated before writing.
    """
    controls = list(controls)
    if not controls:
        raise ValueError('No imported Halo 1 decal controls are available')
    tags_root = Path(tags_root).resolve()
    source = source_scenario(controls, tags_root)
    destination = (tags_root / Path(destination)).resolve()
    if destination.suffix.lower() != '.scenario' or not destination.is_relative_to(tags_root):
        raise ValueError('Choose a .scenario file inside the current project tags folder')
    base = destination if destination.is_file() else source
    updates = []
    for control in controls:
        values = placement_values(control)
        prefix = 'halo1_source'
        previous = control.get('halo1_last_export_scenario')
        if previous is not None and Path(previous).resolve() == base:
            prefix = 'halo1_last_export'
        # Match the actual float32 values written by the tag API, including
        # repeat exports without movement and original untouched positions.
        position = struct.unpack('<3f', struct.pack('<3f', *values['position']))
        updates.append(ScenarioDecalUpdate(
            source_index=values['source_index'], palette_index=values['palette_index'],
            definition=values['definition'],
            expected_position=tuple(control[prefix + '_position']),
            expected_yaw=int(control[prefix + '_yaw']), expected_pitch=int(control[prefix + '_pitch']),
            position=position, yaw=values['yaw'], pitch=values['pitch']))
    with ScenarioDocument(base, tags_root=tags_root, game='halo1', must_exist=True) as scenario:
        if scenario.read_only:
            raise RuntimeError('Cannot export decals during a read-only tag operation')
        # This document is staging data. Only the explicit destination below
        # may be written; context exit must never save changes to the source.
        scenario.read_only = True
        changed = scenario.update_halo1_decal_placements(updates)
        if changed:
            destination.parent.mkdir(parents=True, exist_ok=True)
            scenario.tag.write_atomic(destination)
        elif destination != base:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base, destination)
    for control, update in zip(controls, updates):
        control['halo1_last_export_scenario'] = str(destination)
        control['halo1_last_export_position'] = update.position
        control['halo1_last_export_yaw'] = update.yaw
        control['halo1_last_export_pitch'] = update.pitch
        control['halo1_last_export_world_position'] = tuple(control.matrix_world.translation)
        control['halo1_last_export_import_transform'] = import_transform.signature()
    return changed


class NWO_OT_ExportHalo1DecalPlacements(bpy.types.Operator, ExportHelper):
    bl_idname = 'nwo.export_halo1_decal_placements'
    bl_label = 'Export Decal Placements'
    bl_description = ('Write selected imported Halo 1 decal placements, or all placements when none are selected. '
                      'Move or rotate the placement controls to edit them')
    filename_ext = '.scenario'
    filter_glob: bpy.props.StringProperty(default='*.scenario', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        project = utils.get_project(context.scene.nwo.scene_project)
        return project is not None and project.game == 'halo1' and bool(decal_controls(context))

    def invoke(self, context, event):
        self._controls = decal_controls(context)
        try:
            source = source_scenario(self._controls, utils.get_tags_path())
        except (KeyError, ValueError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.filepath = str(source.with_name(source.stem + '_decals.scenario'))
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            changed = export_decal_placements(getattr(self, '_controls', decal_controls(context)),
                                              self.filepath, tags_root=utils.get_tags_path())
        except (OSError, KeyError, ValueError, RuntimeError, OverflowError, struct.error) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Saved decal placements ({changed} changed) to {Path(self.filepath).name}')
        return {'FINISHED'}

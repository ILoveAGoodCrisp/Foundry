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
    with ScenarioDocument(base, tags_root=tags_root, game='halo1', must_exist=True) as scenario:
        root = scenario.tag.root()
        rows = scenario.block(root, 'decals')
        palette = scenario.block(root, 'decal palette')
        updates = []
        for control in controls:
            values = placement_values(control)
            index = values['source_index']
            row = rows[index] if 0 <= index < len(rows) else None
            palette_index = scenario.value(row, 'decal type') if row is not None else -1
            reference = scenario.reference(palette[palette_index], 'reference') if 0 <= palette_index < len(palette) else None
            definition = reference.RelativePathWithExtension if reference is not None else ''
            if row is None or palette_index != values['palette_index'] or definition.replace('\\', '/') != values['definition'].replace('\\', '/'):
                raise ValueError(f'{control.name}: the destination decal row no longer matches its reference')
            position = struct.unpack('<3f', struct.pack('<3f', *values['position']))
            updates.append(ScenarioDecalUpdate(
                source_index=values['source_index'], palette_index=values['palette_index'],
                definition=values['definition'], expected_position=tuple(scenario.value(row, 'position').to_array()),
                expected_yaw=scenario.value(row, 'yaw'), expected_pitch=scenario.value(row, 'pitch'),
                position=position, yaw=values['yaw'], pitch=values['pitch']))
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

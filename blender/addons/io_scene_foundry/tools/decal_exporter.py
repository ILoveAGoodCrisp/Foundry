"""Scenario decals authored as game object markers.

Gathering and opt-in are shared by games; Halo 1 is the first writer.
"""
from math import asin, atan2, isfinite, pi
from types import SimpleNamespace

import bpy
from mathutils import Vector

from .. import utils
from ..tags.scenario import ScenarioDecalExport, ScenarioDocument


def gather_decals(context):
    collection_map = utils.create_parent_mapping(context)
    decals = []
    with utils.DepsgraphRead():
        for inst in context.evaluated_depsgraph_get().object_instances:
            original = (inst.instance_object if inst.is_instance else inst.object).original
            parent = inst.parent if inst.is_instance else original
            nwo = original.nwo
            if (original.type != 'EMPTY' or
                    nwo.marker_type != '_connected_geometry_marker_type_game_instance' or
                    not nwo.marker_game_instance_tag_name.strip().lower().endswith('.decal') or
                    utils.ignore_for_export_fast(original, collection_map, parent)):
                continue
            decals.append(SimpleNamespace(name=original.name, nwo=nwo,
                                          matrix_world=inst.matrix_world.copy()))
    return decals


def decal_placement(ob):
    matrix = utils.halo_transforms_matrix(ob.matrix_world)
    direction = matrix.to_3x3() @ Vector((1, 0, 0))
    if not all(isfinite(v) for v in direction) or direction.length_squared < 1e-12:
        raise ValueError(f'{ob.name}: invalid decal projection direction')
    direction.normalize()
    # Halo 1 projects along local +X, with full yaw and half pitch in signed bytes.
    yaw = max(-127, min(127, round(atan2(direction.y, direction.x) * 127 / pi)))
    pitch = max(-127, min(127, round(asin(max(-1., min(1., direction.z))) * 254 / pi)))
    return ScenarioDecalExport(utils.relative_path(ob.nwo.marker_game_instance_tag_name.strip()),
                              tuple(matrix.translation), yaw, pitch)


def export_decals(decal_objects=None, *, scenario_path=None, tags_root=None, game=None):
    settings = utils.get_scene_props()
    if not settings.decals_from_blender:
        return 0
    game = game or utils.get_project(settings.scene_project).game
    if game != 'halo1':
        raise ValueError('Scenario decal export is currently supported for Halo 1')
    if decal_objects is None:
        decal_objects = gather_decals(bpy.context)
    placements = [decal_placement(ob) for ob in decal_objects]
    scenario_path = scenario_path or utils.get_asset_tag('.scenario', True)
    tags_root = tags_root or utils.get_tags_path()
    with ScenarioDocument(scenario_path, tags_root=tags_root, game=game, must_exist=True) as scenario:
        if scenario.read_only:
            raise RuntimeError('Cannot export decals during a read-only tag operation')
        scenario.replace_decals(placements)
    return len(placements)


class NWO_OT_ExportDecals(bpy.types.Operator):
    bl_idname = 'nwo.export_decals'
    bl_label = 'Export Decals'
    bl_description = 'Replace the scenario decal palette and placements with exported game object markers'

    @classmethod
    def poll(cls, context):
        project = utils.get_project()
        return (utils.valid_nwo_asset(context) and context.scene.nwo.asset_type == 'scenario' and
                context.scene.nwo.decals_from_blender and project is not None and project.game == 'halo1')

    def execute(self, context):
        try:
            count = export_decals()
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Exported {count} decal placements')
        return {'FINISHED'}

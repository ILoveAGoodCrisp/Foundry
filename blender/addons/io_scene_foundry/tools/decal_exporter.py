"""Opt-in scenario decals authored as dedicated decal markers."""
from math import asin, atan2, isfinite, pi
from types import SimpleNamespace

import bpy
from mathutils import Vector

from .. import utils
from ..tags.scenario import ScenarioDecalExport, ScenarioDocument
from .scenario.targets import scenario_targets


def gather_decals(context):
    collection_map = utils.create_parent_mapping(context)
    decals = []
    with utils.DepsgraphRead():
        for inst in context.evaluated_depsgraph_get().object_instances:
            original = (inst.instance_object if inst.is_instance else inst.object).original
            parent = inst.parent if inst.is_instance else original
            nwo = original.nwo
            if (original.type != 'EMPTY' or
                    nwo.marker_type != '_connected_geometry_marker_type_decal' or
                    utils.ignore_for_export_fast(original, collection_map, parent)):
                continue
            decals.append(SimpleNamespace(name=original.name, nwo=nwo,
                                          matrix_world=inst.matrix_world.copy()))
    return decals


def decal_placement(ob, game='halo1'):
    matrix = utils.halo_transforms_matrix(ob.matrix_world)
    direction = matrix.to_3x3() @ Vector((1, 0, 0))
    if not all(isfinite(v) for v in direction) or direction.length_squared < 1e-12:
        raise ValueError(f'{ob.name}: invalid decal projection direction')
    direction.normalize()
    # Halo 1 projects along local +X, with full yaw and half pitch in signed bytes.
    yaw = max(-127, min(127, round(atan2(direction.y, direction.x) * 127 / pi)))
    pitch = max(-127, min(127, round(asin(max(-1., min(1., direction.z))) * (254 if game == 'halo1' else 127) / pi)))
    if game == 'halo2':
        pitch = -pitch
    q = matrix.to_quaternion()
    scale = ob.matrix_world.to_scale()
    bsps = frozenset(int(value.strip()) for value in ob.nwo.decal_manual_bsps.split(',') if value.strip())
    return ScenarioDecalExport(utils.relative_path(ob.nwo.marker_decal_tag_name.strip()),
                              tuple(matrix.translation), yaw, pitch, (q.x, q.y, q.z, q.w),
                              (abs(scale.x), abs(scale.y)), bsps, int(ob.nwo.decal_force_planar),
                              ob.nwo.decal_cull_angle, ob.nwo.scenario_bsp_index)


def export_decals(decal_objects=None, *, scenario_path=None, tags_root=None, game=None):
    settings = utils.get_scene_props()
    if not settings.decals_from_blender:
        return 0
    game = game or utils.get_project(settings.scene_project).game
    if decal_objects is None:
        decal_objects = gather_decals(bpy.context)
    scenario_path = scenario_path or utils.get_asset_tag('.scenario', True)
    tags_root = tags_root or utils.get_tags_path()
    count = 0
    with scenario_targets(decal_objects, scenario_path=scenario_path, tags_root=tags_root, game=game,
            include_existing_children=True) as targets:
        for scenario, objects in targets:
            placements = [decal_placement(ob, game) for ob in objects]
            scenario.replace_decals(placements)
            count += len(placements)
    return count


class NWO_OT_ExportDecals(bpy.types.Operator):
    bl_idname = 'nwo.export_decals'
    bl_label = 'Export Decals'
    bl_description = 'Replace the scenario decal palette and placements with exported decal markers'

    @classmethod
    def poll(cls, context):
        project = utils.get_project()
        return (utils.valid_nwo_asset(context) and context.scene.nwo.asset_type == 'scenario' and
                context.scene.nwo.decals_from_blender and project is not None)

    def execute(self, context):
        try:
            count = export_decals()
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Exported {count} decal placements')
        return {'FINISHED'}

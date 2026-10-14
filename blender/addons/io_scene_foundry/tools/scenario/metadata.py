"""Standalone and on-save exports of authored scenario metadata."""
import bpy

from ... import utils
from ...props.scenario_authoring import scenario_metadata_enabled
from ...tags.scenario_markers import MARKER_PREFIX
from .markers import gather_scenario_markers, export_scenario_markers, export_camera_points


def export_scenario_metadata(*, context=None, scenario_path=None, tags_root=None, game=None):
    context = context or bpy.context
    settings = utils.get_scene_props()
    if not scenario_metadata_enabled(settings):
        return 0
    scenario_path = scenario_path if scenario_path is not None else utils.get_asset_tag('.scenario', True)
    tags_root = tags_root if tags_root is not None else utils.get_tags_path()
    game = game or utils.get_game(settings.scene_project, use_external=False)
    count = 0
    if settings.player_starts_from_blender or settings.cutscene_flags_from_blender:
        kinds = set()
        if settings.player_starts_from_blender:
            kinds.add(MARKER_PREFIX + 'player_start')
        if settings.cutscene_flags_from_blender:
            kinds.add(MARKER_PREFIX + 'cutscene_flag')
        markers = [ob for ob in gather_scenario_markers(context) if ob.nwo.marker_type in kinds]
        count += export_scenario_markers(markers, scenario_path=scenario_path,
            tags_root=tags_root, game=game, clear_player_starts=settings.player_starts_from_blender,
            clear_cutscene_flags=settings.cutscene_flags_from_blender)
    if settings.camera_points_from_blender:
        count += export_camera_points(context=context, scenario_path=scenario_path,
            tags_root=tags_root, game=game)
    return count


class NWO_OT_ExportScenarioMetadata(bpy.types.Operator):
    bl_idname = 'nwo.export_scenario_metadata'
    bl_label = 'Export Scenario Metadata'
    bl_description = 'Export enabled player starts, cutscene flags and camera points at the current frame'

    @classmethod
    def poll(cls, context):
        return (utils.valid_nwo_asset(context) and context.scene.nwo.asset_type == 'scenario'
                and scenario_metadata_enabled(context.scene.nwo))

    def execute(self, context):
        try:
            count = export_scenario_metadata(context=context)
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Exported {count} scenario metadata placements')
        return {'FINISHED'}

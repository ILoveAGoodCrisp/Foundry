"""Read-only preview of the same overlay plan used by the exporter."""
import json
from pathlib import Path

import bpy

from ... import utils
from ...tags.animation_graph import AnimationGraphTag
from ...tags.animation_overlay_groups import load_state


class NWO_OT_PreviewOverlayGroups(bpy.types.Operator):
    bl_idname = 'nwo.preview_overlay_groups'
    bl_label = 'Preview Overlay Group Changes'
    bl_description = 'Show proposed changes and validation notices for the compiled graph without saving it'

    @classmethod
    def poll(cls, context):
        project = utils.get_project()
        return bool(project and project.game in {'reach', 'halo4', 'halo2a'}
                    and utils.get_asset_animation_graph())

    def execute(self, context):
        nwo = utils.get_scene_props()
        try:
            overrides = None
            if nwo.overlay_group_overrides:
                overrides = json.loads(Path(bpy.path.abspath(nwo.overlay_group_overrides)).read_text(encoding='utf-8'))
            with AnimationGraphTag(utils.get_asset_animation_graph()) as graph:
                state_path = Path(utils.get_data_path(), graph.path).with_suffix('.overlay_groups.generated.json')
                previous = load_state(state_path, graph.path, graph.game)
                plan = graph.setup_overlay_groups(
                    (a.name for a in nwo.animations if a.pose_overlay and a.animation_type == 'overlay'),
                    profile=nwo.overlay_group_profile, previous=previous,
                    overrides=overrides, dry_run=True)
            text = bpy.data.texts.get('Overlay Group Preview') or bpy.data.texts.new('Overlay Group Preview')
            text.clear()
            text.write('\n'.join([f'{len(plan.messages)} proposed changes', *plan.messages,
                                  '', f'{len(plan.warnings)} validation notices', *plan.warnings]))
            self.report({'INFO'}, f'{len(plan.messages)} changes, {len(plan.warnings)} notices. See Overlay Group Preview in the Text Editor')
        except (ValueError, OSError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        return {'FINISHED'}

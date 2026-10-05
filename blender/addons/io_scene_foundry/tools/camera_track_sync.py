

from pathlib import Path
import bpy
from .. import utils
from ..tags.camera_track import CameraTrackTag

def export_current_action_as_camera_track(context, asset_path, scope='ACTIVE'):
    camera = utils.get_camera_track_camera(context)
    if not camera:
        return print(f"\nNo Camera in Scene. Export Cancelled")
    
    if not camera.animation_data:
        return print(f"\nCamera [{camera.name}] has no animation data. Export Cancelled")
    
    scene_nwo =utils.get_scene_props()
    animations = scene_nwo.animations
    if len(animations) < 1:
         return print("\nNo animations in scene. Please ensure atleast one camera animation is set up in the Foundry animation panel")
     
    if scope == 'ACTIVE':
        if not 0 <= scene_nwo.active_animation_index < len(animations):
            return print("\nNo active camera animation. Export Cancelled")
        animations = [animations[scene_nwo.active_animation_index]]

    animation_data = camera.animation_data
    original_action = animation_data.action
    original_slot = animation_data.action_slot
    original_frame = context.scene.frame_current
    try:
        for animation in animations:
            track = next((track for track in animation.action_tracks if track.object == camera), None)
            if track is None or not track.action:
                utils.print_warning(f"Animation {animation.name} has no action for camera {camera.name}. Skipping")
                continue

            slot_id = ""
            if track.action.slots:
                slot = track.action.slots.active or track.action.slots[0]
                slot_id = slot.identifier
            animation_data.last_slot_identifier = slot_id
            animation_data.action = track.action

            tag_path = Path(utils.relative_path(asset_path), animation.name + '.camera_track')
            with CameraTrackTag(path=tag_path) as camera_track:
                camera_track.to_tag(context, animation, camera)
            print(f"\nCamera Track [{animation.name}] exported to {camera_track.path}")
    finally:
        animation_data.action = original_action
        if original_action is not None:
            animation_data.action_slot = original_slot
        context.scene.frame_set(original_frame)

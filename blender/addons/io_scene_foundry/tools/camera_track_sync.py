

from pathlib import Path
import bpy
from .. import utils
from ..managed_blam.camera_track import CameraTrackTag

def export_current_action_as_camera_track(context, asset_path):
    camera = utils.get_camera_track_camera(context)
    if not camera:
        return print(f"\nNo Camera in Scene. Export Cancelled")
    
    if not camera.animation_data:
        return print(f"\nCamera [{camera.name}] has no animation data. Export Cancelled")
    
    scene_nwo =utils.get_scene_props()
    animations = scene_nwo.animations
    if len(animations) < 1:
         return print("\nNo animations in scene. Please ensure atleast one camera animation is set up in the Foundry animation panel")
     
    animation = animations[scene_nwo.active_animation_index]
    
    if not animation.action_tracks:
        return print(f"\nAnimation {animation.name} has no action tracks. Please add one for the camera")
    
    track = animation.action_tracks[0]
    
    if track.object != camera:
        return print(f"\nAnimation action track object {track.object} is not a camera")
    
    if not track.action:
        return print(f"\nAction track for animation {animation.name} has no action")
    
    slot_id = ""
    if track.action.slots:
        if track.action.slots.active:
            slot_id = track.action.slots.active.identifier
        else:
            slot_id = track.action.slots[0].identifier
            
    track.object.animation_data.last_slot_identifier = slot_id
    track.object.animation_data.action = track.action

    
    tag_path = Path(asset_path, animation.name + '.camera_track')
    
    with CameraTrackTag(path=tag_path) as camera_track:
        camera_track.to_tag(context, animation, camera)
        print(f"\nCamera Track [{animation.name}] exported to {camera_track.tag_path.RelativePathWithExtension}")
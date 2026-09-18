from ..tags.blender import BlenderTag
from ..tags.cinematic import CinematicCameraDocument
    
class CinematicSceneDataTag(BlenderTag, CinematicCameraDocument):
    tag_ext = 'cinematic_scene_data'

from . import Tag

class CinematicSceneTag(Tag):
    tag_ext = 'cinematic_scene'
    
    def _read_fields(self):
        self.scene_playback = self.tag.SelectField("Custom:loop now")
    
    def get_loop_text(self) -> str:
        return self.scene_playback.GetLoopText()
    


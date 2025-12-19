from ..utils import get_scene_props
from ..icons import get_icon_id


def draw_cinematic_info(self, context):
    nwo = context.scene.nwo
    if get_scene_props().asset_type != "cinematic":
        return
    layout = self.layout
    layout.label(text="", icon_value=get_icon_id("foundry"))
    row = layout.row()
    row.scale_x = 0.8
    row.prop(nwo, "game_frame", text="Frame")
    row = layout.row(align=True)
    row.scale_x = 0.8
    row.prop(nwo, "current_shot", text="Shot")
    row.prop(nwo, "shot_frame")
    row = layout.row(align=True)
    row.operator("object.select_camera", icon='OUTLINER_OB_CAMERA', text="")


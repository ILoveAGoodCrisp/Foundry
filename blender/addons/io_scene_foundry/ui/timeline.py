def draw_cinematic_info(self, context):
    nwo = context.scene.nwo
    layout = self.layout
    layout.separator()
    layout.label(text="Halo Cinematic:")
    row = layout.row()
    row.scale_x = 0.8
    row.prop(nwo, "current_shot", text="Shot")
    row = layout.row(align=True)
    row.scale_x = 0.8
    row.prop(nwo, "game_frame", text="Frame")
    row.prop(nwo, "shot_frame")

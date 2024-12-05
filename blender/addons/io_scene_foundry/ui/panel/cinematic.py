import bpy

class NWO_UL_CinematicShots(bpy.types.UIList):
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        layout.label(text=f"Shot {index + 1}")
        layout.prop(item, "frame_count", emboss=False)
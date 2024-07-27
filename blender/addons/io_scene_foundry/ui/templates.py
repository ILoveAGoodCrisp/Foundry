from bpy.types import Panel, Operator

class NWO_PropPanel(Panel):
    bl_label = ""
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    @classmethod
    def poll(cls, context):
        return context.object


class NWO_Op(Operator):
    bl_label = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object

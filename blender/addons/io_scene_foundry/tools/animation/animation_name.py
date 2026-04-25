import bpy

MODES = {
    'device': "Used by devices as their default mode",
    'vehicle': "Used by vehicles as their default mode",
    'combat': "The default mode for bipeds",
    'crouch': "Active when a biped is crouching",
    'sprint': "Active when a biped is sprinting",
}

SETS = {
    'sync_actions': "Used when an object is executing a sync action, such as assassinations"
}

MODES_DEVICE = {'device'}
MODES_VEHICLE = {'vehicle', 'combat'}
MODES_UNIT = {'combat', 'crouch'}
MODES_CHARACTER = {''}

class NWO_OT_SetAnimationName(bpy.types.Operator):
    bl_idname = "nwo.set_animation_name"
    bl_label = "Set Animation Name"
    bl_description = "Creates a valid animation name"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        
        return {"FINISHED"}

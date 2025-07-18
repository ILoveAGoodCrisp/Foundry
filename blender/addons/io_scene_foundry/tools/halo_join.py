

import bpy


class NWO_JoinHalo(bpy.types.Operator):
    bl_idname = "nwo.join_halo"
    bl_label = "Join two or more halo mesh objects"
    bl_description = "Joins objects and face layer properties"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "MESH"
            and context.object.mode == "OBJECT"
        )

    def execute(self, context):
        active = context.object
        non_active_objects = (ob for ob in context.selected_objects if ob != active and ob.type == 'MESH')
        face_attributes = yield_face_attributes(non_active_objects)
        for old_layer in face_attributes:
            new_layer = active.data.nwo.face_props.add()
            update_layer_props(new_layer, old_layer)

        bpy.ops.object.join()

        return {"FINISHED"}
    
def yield_face_attributes(objects):
    for ob in objects:
        for layer in ob.data.nwo.face_props:
            yield layer

def update_layer_props(new_layer, old_layer):
    for k,v in old_layer.items():
        new_layer[k] = v


import bpy
from .. import face_attributes


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
        objects = [active, *(ob for ob in context.selected_objects if ob != active and ob.type == 'MESH')]
        try:
            for ob in objects:
                face_attributes.resolved_masks(ob.data, strict=True)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        # Never rewrite the assignments of an unselected linked duplicate.
        for ob in objects:
            if ob.data.users > 1:
                ob.data = ob.data.copy()
        face_attributes.prepare_join([ob.data for ob in objects])
        bpy.ops.object.join()
        face_attributes.refresh_counts(active.data)

        return {"FINISHED"}
    
def yield_face_attributes(objects):
    for ob in objects:
        for layer in ob.data.nwo.face_props:
            yield layer

def update_layer_props(new_layer, old_layer):
    for k,v in old_layer.items():
        new_layer[k] = v

import bpy
from ... import utils
        
class NWO_UL_CameraActors(bpy.types.UIList):
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.actor.name if item.actor else "NONE", icon='OUTLINER_OB_ARMATURE')
        
class NWO_OT_CameraActorRemove(bpy.types.Operator):
    bl_idname = "nwo.camera_actor_remove"
    bl_label = "Remove Camera Actor"
    bl_description = "Removes the highlighted actor from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CAMERA' and context.object.nwo.actors

    def execute(self, context):
        nwo = context.object.nwo
        table = nwo.actors
        table.remove(nwo.active_actor_index)
        if nwo.active_actor_index > len(table) - 1:
            nwo.active_actor_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_CameraActorAdd(bpy.types.Operator):
    bl_idname = "nwo.camera_actor_add"
    bl_label = "Add Camera Actor"
    bl_description = "Adds selected actors to the list"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CAMERA'
    
    def add_entry(self, table, ob: bpy.types.Object | None):
        item = table.add()
        item.actor = ob
    
    def execute(self, context):
        nwo = context.object.nwo
        table = nwo.actors
        actor_count = 0
        skip_actors = set()
        for ob in context.selected_objects:
            if ob == context.object: # camera selected
                continue
            actor = utils.ultimate_armature_parent(ob)
            if actor is None:
                continue
            if not actor.nwo.cinematic_object:
                self.report({'WARNING'}, f"Skipping {actor.name} because it has no cinematic object path")
                continue
            if actor in skip_actors:
                continue
            self.add_entry(table, actor)
            actor_count += 1
            skip_actors.add(actor)
                
        if actor_count == 0:
            self.add_entry(table, None)
            actor_count += 1
        
        if actor_count == 1:
            self.report({'INFO'}, f"Added 1 entry")
        else:
            self.report({'INFO'}, f"Added {actor_count} entries")
                
        nwo.active_actor_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
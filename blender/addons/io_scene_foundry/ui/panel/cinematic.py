from pathlib import Path
import bpy

from ...managed_blam.model import ModelTag
from ...managed_blam.object import ObjectTag
from ...managed_blam import Tag
from ...icons import get_icon_id
from ... import utils

SOUND_FX_TAG = r"sound\global_fx.sound_effect_collection"

# CINEMATIC EVENTS
class NWO_UL_CinematicEvents(bpy.types.UIList):
    
    use_filter_sort_frame: bpy.props.BoolProperty(
        name="Sort By Frame",
        default=True,
    )
    
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        match item.type:
            case 'DIALOGUE':
                layout.label(text=item.name, icon='PLAY_SOUND')
            case 'EFFECT':
                layout.label(text=item.name, icon_value=get_icon_id("effects"))
            case 'SCRIPT':
                layout.label(text=item.name, icon='TEXT')
        
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=str(item.frame))
        
    def draw_filter(self, context, layout):
        if self.use_filter_show:
            row = layout.row(align=True)
            row.prop(self, "filter_name", text="")
            row.prop(self, "use_filter_invert", text="", icon='ARROW_LEFTRIGHT')
            row.separator()
            row.prop(self, "use_filter_sort_frame", text="", icon='KEYFRAME_HLT')
            row.prop(self, "use_filter_sort_reverse", text="", icon="SORT_ASC")

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        if self.filter_name:
            flt_flags = bpy.types.UI_UL_list.filter_items_by_name(self.filter_name, self.bitflag_filter_item, items, "name", reverse=False)
        else:
            flt_flags = [self.bitflag_filter_item] * len(items)
        
        order = None
        sort = []
        sequences = context.scene.sequence_editor.sequences_all
        if self.use_filter_sort_frame:
            for idx, item in enumerate(items):
                if item.type == 'DIALOGUE' and item.sound_strip:
                    strip = sequences.get(item.sound_strip)
                    if strip is not None:
                        sort.append(int(strip.frame_start))
                        continue
                    
                sort.append(item.frame)
                        
            order = bpy.types.UI_UL_list.sort_items_helper(sort, key=lambda i: i[1], reverse=False)


        return flt_flags, order

class NWO_OT_CinematicEventAdd(bpy.types.Operator):
    bl_idname = "nwo.cinematic_event_add"
    bl_label = "Add Cinematic Event"
    bl_description = "Adds a new cinematic event"
    bl_options = {"UNDO"}
    
    def execute(self, context):
        events = context.scene.nwo.cinematic_events
        event = events.add()
        event.name = "EVENT"
        event.frame = context.scene.frame_current
        ob = context.object
        active_cinematic_object = utils.ultimate_armature_parent(ob)
        cinematic_object_valid = active_cinematic_object is not None and active_cinematic_object.nwo.cinematic_object
        if ob is not None and ob.type == 'EMPTY' and cinematic_object_valid:
            event.marker = ob
            
        if cinematic_object_valid:
            event.lipsync_actor = active_cinematic_object
            if event.marker is None:
                event.marker = active_cinematic_object 
        
        context.scene.nwo.active_cinematic_event_index = len(events) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_CinematicEventRemove(bpy.types.Operator):
    bl_idname = "nwo.cinematic_event_remove"
    bl_label = "Remove Cinematic Event"
    bl_description = "Removes the highlighted cinematic event"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1
    
    def execute(self, context):
        nwo = context.scene.nwo
        events = nwo.cinematic_events
        events.remove(nwo.active_cinematic_event_index)
        if nwo.active_cinematic_event_index > len(events) - 1:
            nwo.active_cinematic_event_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_CinematicEventSetFrame(bpy.types.Operator):
    bl_idname = "nwo.cinematic_event_set_frame"
    bl_label = "Set Event Frame"
    bl_description = "Sets the event frame to the current timeline frame"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1

    def execute(self, context):
        nwo = context.scene.nwo
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        event.frame = int(context.scene.frame_current)
        return {"FINISHED"}
    
class NWO_OT_GetSoundEffects(bpy.types.Operator):
    bl_label = "Get Sound Effects"
    bl_idname = 'nwo.get_sound_effects'
    bl_description = f"Returns a searchable list of sound effects from {SOUND_FX_TAG}"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1
    
    def fx_items(self, context):
        items = []
        if not Path(utils.get_tags_path(), SOUND_FX_TAG).exists():
            return items
        
        with Tag(path=SOUND_FX_TAG) as fx:
            for element in fx.tag.SelectField("Block:sound effects").Elements:
                name = element.SelectField("StringId:name").GetStringData()
                if not name:
                    continue
                if element.SelectField("Struct:playback[0]/Reference:radio effect").Path is not None or element.SelectField("Struct:playback[0]/Block:sound components").Elements.Count > 0:
                    items.append((name, name, ""))

        return items
    
    fx: bpy.props.EnumProperty(
        name="Sound Effect",
        items=fx_items,
    )
    
    def execute(self, context):
        if not Path(utils.get_tags_path(), SOUND_FX_TAG).exists():
            self.report({'WARNING'}, f"Could not find tag {SOUND_FX_TAG}")
            return {'CANCELLED'}
        nwo = context.scene.nwo
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        event.default_sound_effect = self.fx
        return {'FINISHED'}
    
class NWO_OT_CinematicItemSearch(bpy.types.Operator):
    bl_label = "Get item"
    bl_idname = 'nwo.get_cinematic_item'
    bl_description = "Returns a searchable list of cinematic items"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1
    
    def items(self, context):
        items = []
        relative_tag_path = utils.relative_path(self.tag)
        if not Path(utils.get_tags_path(), relative_tag_path).exists():
            return items
        
        with ObjectTag(path=relative_tag_path) as obj:
            model_path = obj.get_model_tag_path()
            with ModelTag(path=model_path) as model:
                match self.type:
                    case 'VARIANT':
                        variants = model.get_model_variants()
                        for v in variants:
                            items.append((v, v, ""))
                    case 'REGION':
                        pass
                    case 'PERMUTATION':
                        pass
                    case 'STATE':
                        pass

        return items
    
    item: bpy.props.EnumProperty(
        name="Item",
        items=items,
    )
    
    type: bpy.props.StringProperty(
        options={'HIDDEN', 'SKIP_SAVE'}
    )
    
    def execute(self, context):
        if not Path(utils.get_tags_path(), SOUND_FX_TAG).exists():
            self.report({'WARNING'}, f"Could not find tag {SOUND_FX_TAG}")
            return {'CANCELLED'}
        nwo = context.scene.nwo
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        event.default_sound_effect = self.fx
        return {'FINISHED'}
        
# CAMERA STUFF
        
class NWO_UL_CameraActors(bpy.types.UIList):
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.actor.name if item.actor else "NONE", icon='OUTLINER_OB_ARMATURE')
        
class NWO_OT_CameraActorsClear(bpy.types.Operator):
    bl_idname = "nwo.camera_actor_clear"
    bl_label = "Clear Camera Actors"
    bl_description = "Removes all entries from the list"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CAMERA' and context.object.nwo.actors
    
    def execute(self, context):
        nwo = context.object.nwo
        nwo.active_actor_index = 0
        nwo.actors.clear()
        context.area.tag_redraw()
        return {'FINISHED'}
        
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
    
class NWO_OT_SelectCameraActors(bpy.types.Operator):
    bl_idname = "nwo.camera_actors_select"
    bl_label = "Select Camera Actor Objects"
    bl_description = "Selects actors which are active for this shot"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CAMERA'
    
    def execute(self, context):
        nwo = context.object.nwo
        if nwo.actors_type == 'exclude':
            excluded_objects = {item.actor for item in nwo.actors if item.actor is not None}
            for ob in context.view_layer.objects:
                if ob.type == 'ARMATURE' and ob not in excluded_objects:
                    ob.select_set(True)
        else:
            for item in nwo.actors:
                if item.actor is not None:
                    item.actor.select_set(True)
                    
        return {'FINISHED'}
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
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        match item.type:
            case 'DIALOGUE':
                layout.prop(item, "name", icon='PLAY_SOUND', text="", emboss=False)
            case 'EFFECT':
                layout.prop(item, "name", icon_value=get_icon_id("effects"), text="", emboss=False)
            case 'SCRIPT':
                layout.prop(item, "name", icon='TEXT', text="", emboss=False)
                
        layout.label(text=str(item.frame))

class NWO_OT_CinematicEventAdd(bpy.types.Operator):
    bl_idname = "nwo.cinematic_event_add"
    bl_label = "Add Cinematic Event"
    bl_description = "Adds a new cinematic event"
    bl_options = {"UNDO"}
    
    def execute(self, context):
        events = context.scene.nwo.cinematic_events
        event = events.add()
        event.name = event.type
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
        nwo = context.object.nwo
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
    
class NWO_OT_CinematicScriptTemplate(bpy.types.Operator):
    bl_idname = "nwo.cinematic_script_template"
    bl_label = "Template Script"
    bl_description = "Adds a template cinematic script"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1

    option: bpy.props.EnumProperty(
        name="Option",
        description="Type of cinematic script template to add",
        items=[
            ("WEAPON_TRIGGER_START", "Start Firing Weapon", "Causes a weapon to start shooting"),
            ("WEAPON_TRIGGER_STOP", "Stop Firing Weapon", "Causes a weapon to stop shooting"),
            ("SET_VARIANT", "Set Object Variant", "Sets an object variant to the named variant"),
            ("SET_PERMUTATION", "Set Object Permutation", "Sets an objects permutation(s)"),
        ]
    )
    
    arg_1: bpy.props.StringProperty()
    arg_2: bpy.props.StringProperty()
    
    def execute(self, context):
        nwo = context.scene.nwo
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        active_cinematic_object = utils.ultimate_armature_parent(context.object)
        if active_cinematic_object is None or not active_cinematic_object.nwo.cinematic_object:
            ob_name = "REPLACE_WITH_OBJECT_NAME"
        else:
            ob_name = active_cinematic_object.name.replace(".", "_")
        match self.option:
            case 'WEAPON_TRIGGER_START':
                event.script = f'weapon_set_primary_barrel_firing (cinematic_weapon_get "{ob_name}_weapon") 1'
            case 'WEAPON_TRIGGER_STOP':
                event.script = f'weapon_set_primary_barrel_firing (cinematic_weapon_get "{ob_name}_weapon") 0'
            case 'SET_VARIANT':
                event.script = f'object_set_variant (cinematic_object_get "{ob_name}") {self.arg_1}'
            case 'SET_PERMUTATION':
                event.script = f'object_set_permutation  (cinematic_object_get "{ob_name}") {self.arg_1} {self.arg_2}'
            case 'SET_REGION_STATE':
                event.script = f'object_set_region_state (cinematic_object_get "{ob_name}") {self.arg_1} {self.script_dynamic_enum}'
            case 'SET_MODEL_STATE_PROPERTY':
                event.script = f'object_set_model_state_property  (cinematic_object_get "{ob_name}") {self.script_dynamic_enum} {self.script_arg_bool}'
            case 'HIDE':
                event.script = f'object_hide (cinematic_object_get "{ob_name}") 1'
            case 'UNHIDE':
                event.script = f'object_hide (cinematic_object_get "{ob_name}") Fals0e'
            case 'DESTROY':
                event.script = f'object_destroy (cinematic_object_get "{ob_name}")'
            case 'SET_TITLE':
                event.script = f'cinematic_set_title {self.script_arg_1}'
            case 'SHOW_HUD':
                event.script = f'chud_cinematic_fade 0 0\nchud_show_cinematics 1'
            case 'HIDE_HUD':
                event.script = f'chud_cinematic_fade 1 0\nchud_show_cinematics 0'
            case 'OBJECT_CANNOT_DIE':
                event.script = f'object_cannot_die (cinematic_object_get "{ob_name}") 1'
            case 'OBJECT_CAN_DIE':
                event.script = f'object_cannot_die (cinematic_object_get "{ob_name}") 0'
        

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
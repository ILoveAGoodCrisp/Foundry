from pathlib import Path
from typing import cast
import bpy
from mathutils import Euler, Matrix, Vector

from ...managed_blam.render_model import RenderModelTag
from ...managed_blam.model import ModelTag
from ...managed_blam.object import ObjectTag
from ...managed_blam import Tag
from ...icons import get_icon_id
from ... import utils

SOUND_FX_TAG = r"sound\global_fx.sound_effect_collection"

variants = {}
regions = {}
permutations = {}

class NWO_OT_CinematicAnchorOffset(bpy.types.Operator):
    bl_idname = "nwo.cinematic_anchor_offset"
    bl_label = "Offset Anchor from 3D Cursor"
    bl_description = "Offsets the cinematic anchor by the current position of the 3D cursor. The effect of this means the level geometry (assuming it is parented to the anchor) will be moved in such a way that the position of the 3D cursor becomes the new center of the blender scene. For example if you had your characters animated in the middle of your blender scene, and you wanted them to animate on a platform in your level using the anchor, this would move the platform to your characters"
    bl_options = {'UNDO'}
    
    use_location: bpy.props.BoolProperty(
        name="Use 3D Cursor Location",
        default=True,
    )
    use_rotation: bpy.props.BoolProperty(
        name="Use 3D Cursor Rotation",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.asset_type == 'cinematic' and utils.pointer_ob_valid(context.scene.nwo.cinematic_anchor)

    def execute(self, context):
        if not self.use_location and not self.use_rotation:
            self.report({'WARNING'}, "Location and/or rotation must be used")
            return {'CANCELLED'}
        
        cursor = context.scene.cursor
        
        cloc, crot, csca = cast(Matrix, context.scene.cursor.matrix).decompose()
        
        euler = cast(Euler, crot.to_euler())
        
        if self.use_location and self.use_rotation:
            matrix = Matrix.LocRotScale(cloc, Euler((0, 0, euler.z)), csca)
        elif self.use_location:
            matrix = Matrix.LocRotScale(cloc, Euler((0, 0, 0)), csca)
        else:
            matrix = Matrix.LocRotScale(Vector.Fill(3, 0), Euler((0, 0, euler.z)), csca)
            
        if hasattr(context.space_data, "region_3d"):
            context.space_data.region_3d.view_matrix = context.space_data.region_3d.view_matrix @ matrix
            
        matrix.invert_safe()
        
        anchor = context.scene.nwo.cinematic_anchor
        anchor.matrix_world = matrix @ anchor.matrix_world
        
        cursor.location = 0, 0, 0

        return {"FINISHED"}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_location")
        layout.prop(self, "use_rotation")


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
        bit = self.bitflag_filter_item

        if self.filter_name:
            name_flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name, bit, items, "name", reverse=False
            )
            visible_by_name = [(f & bit) != 0 for f in name_flags]
        else:
            name_flags = [bit] * len(items)
            visible_by_name = [True] * len(items)

        visible_by_custom = [True] * len(items)

        flt_flags = [0] * len(items)
        for i in range(len(items)):
            final_visible = visible_by_name[i] and visible_by_custom[i]

            if self.use_filter_invert:
                final_visible = not final_visible

            base_flag = name_flags[i] if self.filter_name else bit
            base_flag &= ~bit
            if final_visible:
                base_flag |= bit
            flt_flags[i] = base_flag

        order = []
        sequences = getattr(context.scene, "sequence_editor", None)
        sequences_all = getattr(sequences, "strips_all", None) if sequences else None

        if self.use_filter_sort_frame:
            sort = []
            for idx, item in enumerate(items):
                frame_val = getattr(item, "frame", 0)

                if getattr(item, "type", "") == 'DIALOGUE' and getattr(item, "sound_strip", ""):
                    if sequences_all:
                        strip = sequences_all.get(item.sound_strip)
                        if strip is not None:
                            frame_val = int(strip.frame_start)
                sort.append((idx, frame_val))

            order = bpy.types.UI_UL_list.sort_items_helper(sort, key=lambda i: i[1], reverse=False)

        return flt_flags, order


class NWO_OT_CinematicEventAdd(bpy.types.Operator):
    bl_idname = "nwo.cinematic_event_add"
    bl_label = "Add Cinematic Event"
    bl_description = "Adds a new cinematic event"
    bl_options = {"UNDO"}
    
    def execute(self, context):
        events = context.scene.nwo.cinematic_events
        event_data = None
        current_event = None
        if events and context.scene.nwo.active_cinematic_event_index > -1 and context.scene.nwo.active_cinematic_event_index < len(events):
            current_event = events[context.scene.nwo.active_cinematic_event_index]
            if current_event.type != 'DIALOGUE': # don't copy dialogue data
                event_data = current_event.items()
                
        event = events.add()
        if event_data is not None:
            for key, value in event_data:
                event[key] = value
                
        event.frame = context.scene.frame_current
        ob = context.object
        active_cinematic_object = utils.ultimate_armature_parent(ob)
        cinematic_object_valid = active_cinematic_object is not None and active_cinematic_object.nwo.cinematic_object
        set_marker = False
        if ob is not None and ob.type == 'EMPTY' and cinematic_object_valid:
            set_marker = True
            event.marker = ob
            
        if cinematic_object_valid:
            event.lipsync_actor = active_cinematic_object
            if not set_marker:
                event.marker = active_cinematic_object
        
        if current_event is not None:
            if event.marker != current_event.marker:
                event.marker_name = ""
                
            if event.script_object != current_event.script_object:
                event.script_variant = ""
                event.script_region = ""
                event.script_permutation = ""
        
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
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1 and context.scene.nwo.active_cinematic_event_index < len(context.scene.nwo.cinematic_events)
    
    def execute(self, context):
        nwo = context.scene.nwo
        events = nwo.cinematic_events
        events.remove(nwo.active_cinematic_event_index)
        if nwo.active_cinematic_event_index > len(events) - 1:
            nwo.active_cinematic_event_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_CinematicEventsClear(bpy.types.Operator):
    bl_idname = "nwo.cinematic_events_clear"
    bl_label = "Clear Cinematic Events"
    bl_description = "Removes all cinematic events"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1 and context.scene.nwo.active_cinematic_event_index < len(context.scene.nwo.cinematic_events)
    
    def execute(self, context):
        context.scene.nwo.active_cinematic_event_index = 0
        context.scene.nwo.cinematic_events.clear()
        context.area.tag_redraw()
        return {'FINISHED'}
        
    def invoke(self, context: bpy.types.Context, event):
        return context.window_manager.invoke_confirm(self, event, title="Clear all events?", confirm_text="Yes", icon='WARNING')
    
class NWO_OT_CinematicEventSetFrame(bpy.types.Operator):
    bl_idname = "nwo.cinematic_event_set_frame"
    bl_label = "Set Event Frame"
    bl_description = "Sets the event frame to the current timeline frame"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1 and context.scene.nwo.active_cinematic_event_index < len(context.scene.nwo.cinematic_events)

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
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1 and context.scene.nwo.active_cinematic_event_index < len(context.scene.nwo.cinematic_events)
    
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
    
class GetCinematicBase(bpy.types.Operator):
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.cinematic_events and context.scene.nwo.active_cinematic_event_index > -1 and context.scene.nwo.active_cinematic_event_index < len(context.scene.nwo.cinematic_events)
    
    def items(self, context):
        global variants
        global regions
        global permutations
        event = context.scene.nwo.cinematic_events[context.scene.nwo.active_cinematic_event_index]
        relative_tag_path = utils.relative_path(event.script_object.nwo.cinematic_object)
        match self.get_type:
            case 'script_variant':
                items = variants.get(relative_tag_path)
            case 'script_region':
                items = regions.get(relative_tag_path)
            case 'script_permutation':
                items = permutations.get(f"{relative_tag_path}::{event.script_region}")
                
        if items is None:
            items = []
        else:
            return items
        
        with ObjectTag(path=relative_tag_path) as obj:
            model_path = obj.get_model_tag_path()
            with ModelTag(path=model_path) as model:
                if self.get_type == 'script_variant':
                    print(model.get_model_variants())
                    for v in model.get_model_variants():
                        items.append((v, v, ""))
                else:
                    render_path = model.get_model_paths()[0]
                    with RenderModelTag(path=render_path) as render:
                        if self.get_type == 'script_region':
                            for r in render.get_regions():
                                items.append((r, r, ""))
                        else:
                            for p in render.get_permutations(event.script_region):
                                items.append((p, p, ""))

        match self.get_type:
            case 'script_variant':
                variants[relative_tag_path] = items
            case 'script_region':
                regions[relative_tag_path] = items
            case 'script_permutation':
                permutations[f"{relative_tag_path}::{event.script_region}"] = items

        return items
    
    item: bpy.props.EnumProperty(
        name="Item",
        items=items,
    )
    
    def execute(self, context):
        nwo = context.scene.nwo
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        setattr(event, self.get_type, self.item)
        return {'FINISHED'}

class NWO_OT_GetCinematicVariant(GetCinematicBase):
    bl_label = "Get Variant"
    bl_idname = 'nwo.get_cinematic_variant'
    bl_description = "Returns a searchable list of variants"
    
    get_type: bpy.props.StringProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        default="script_variant"
    )
    
class NWO_OT_GetCinematicRegion(GetCinematicBase):
    bl_label = "Get Region"
    bl_idname = 'nwo.get_cinematic_region'
    bl_description = "Returns a searchable list of regions"
    
    get_type: bpy.props.StringProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        default="script_region"
    )
    
class NWO_OT_GetCinematicPermutation(GetCinematicBase):
    bl_label = "Get Permuation"
    bl_idname = 'nwo.get_cinematic_permutation'
    bl_description = "Returns a searchable list of permutations"
    
    get_type: bpy.props.StringProperty(
        options={'HIDDEN', 'SKIP_SAVE'},
        default="script_permutation"
    )

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
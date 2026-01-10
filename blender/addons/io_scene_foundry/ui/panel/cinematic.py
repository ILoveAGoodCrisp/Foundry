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

nudge = Vector.Fill(3, 0)
rotation = 0

def clear_vis_keyframes(context, do_viewport=True, do_render=True, set_visible=True):
    corinth = utils.is_corinth(context)
    view_objects = context.view_layer.objects

    for ob in view_objects:
        if ob.type == 'ARMATURE':
            if ob.nwo.cinematic_object:
                pass
            continue
        if corinth and ob.type == 'LIGHT' and ob.nwo.is_cinematic_light:
            pass
        elif utils.ultimate_armature_parent(ob) is not None:
            pass
        else:
            continue
        
        ad = ob.animation_data
        if ad is None:
            continue
        
        action = ad.action
        if action is None:
            continue
        
        fcurves = utils.get_fcurves(action, ob)
        if fcurves is None:
            continue
        
        if do_viewport:
            fc = fcurves.find('hide_viewport')
            if fc is not None:
                fcurves.remove(fc)
                if set_visible:
                    ob.hide_viewport = False
                    ob.hide_set(False)
                
        if do_render:
            fc = fcurves.find('hide_render')
            if fc is not None:
                fcurves.remove(fc)
                if set_visible:
                    ob.hide_render = False
                    
        if not fcurves:
            ad.action = None
            bpy.data.actions.remove(action)

def bake_vis_to_keyframes(context, do_viewport=True, do_render=True):
    count = 0
    def set_fcurves():
        def find_and_set(dp, hide_bool):
            nonlocal count
            fc = fcurves.find(dp)
            if fc is None:
                fc = fcurves.new(data_path=dp)
            fc.keyframe_points.insert(frame, hide_bool, options={'FAST'})
            fc.keyframe_points.insert(end_frame, hide_bool, options={'FAST'})
            count += 1

        for ob in camera_target_set:
            ad = ob.animation_data
            if ad is None:
                ad = ob.animation_data_create()
            
            action = ad.action
            if action is None:
                action = bpy.data.actions.new("test")
                slot = action.slots.new('OBJECT', ob.name)
                ad.last_slot_identifier = slot.identifier
                ad.action = action
                
            fcurves = utils.get_fcurves(action, ob)
            if do_viewport:
                find_and_set('hide_viewport', hide_cam)
            if do_render:
                find_and_set('hide_render', hide_cam)
            
        for ob in non_camera_targets:
            ad = ob.animation_data
            if ad is None:
                ad = ob.animation_data_create()
            
            action = ad.action
            if action is None:
                action = bpy.data.actions.new("test")
                slot = action.slots.new('OBJECT', ob.name)
                ad.last_slot_identifier = slot.identifier
                ad.action = action
                
            fcurves = utils.get_fcurves(action, ob)
            if do_viewport:
                find_and_set('hide_viewport', hide_non)
            if do_render:
                find_and_set('hide_render', hide_non)
            
    scene = context.scene
    corinth = utils.is_corinth(context)
    
    camera_frames = {m.frame: m.camera for m in utils.get_timeline_markers(scene)}
    frame_list = list(camera_frames)
    
    for idx, (frame, cam) in enumerate(camera_frames.items()):
        if cam is None:
            return

        cam_nwo = cam.nwo

        view_objects = context.view_layer.objects

        actors = set()
        geometry = set()
        lights = set()
        
        if idx == len(frame_list) - 1:
            end_frame = int(scene.frame_end)
        else:
            end_frame = frame_list[idx + 1] - 1

        for ob in view_objects:
            if ob.type == 'ARMATURE':
                if ob.nwo.cinematic_object:
                    actors.add(ob)
                continue
            if corinth and ob.type == 'LIGHT' and ob.nwo.is_cinematic_light:
                lights.add(ob)
            elif utils.ultimate_armature_parent(ob) is not None:
                geometry.add(ob)

        if actors:
            camera_targets = {a.actor for a in cam_nwo.actors if a.actor is not None}
            do_exclusion = (cam_nwo.actors_type == 'exclude')

            camera_target_set = set(camera_targets)
            non_camera_targets = actors - camera_target_set

            for ob in geometry:
                parent = utils.ultimate_armature_parent(ob)
                if parent in camera_target_set:
                    camera_target_set.add(ob)
                elif parent in non_camera_targets:
                    non_camera_targets.add(ob)

            hide_cam = do_exclusion
            hide_non = not do_exclusion
            
            set_fcurves()
            
        if lights:
            camera_targets = {a.light for a in cam_nwo.cinematic_lights if a.light is not None}
            do_exclusion = (cam_nwo.cinematic_lights_type == 'exclude')

            camera_target_set = set(camera_targets)
            non_camera_targets = lights - camera_target_set

            hide_cam = do_exclusion
            hide_non = not do_exclusion

            set_fcurves()
            
    return count

class NWO_OT_ClearVisibilityKeyframes(bpy.types.Operator):
    bl_idname = "nwo.clear_visibility_keyframes"
    bl_label = "Clear Visibility Keyframes"
    bl_description = "Clears all hide viewport and render keyframes for in scope actors and lights"
    bl_options = {"UNDO", 'REGISTER'}
    
    do_viewport: bpy.props.BoolProperty(
        name="Clear Viewport",
        description="Clears keyframes for hide_viewport",
        default=True,
    )
    do_render: bpy.props.BoolProperty(
        name="Clear Render",
        description="Clears keyframes for hide_render",
        default=True,
    )
    
    make_visible: bpy.props.BoolProperty(
        name="Make Visible",
        description="After clearing keyframes, sets each object to be visible in viewport / render",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return utils.get_scene_props().asset_type == 'cinematic'
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "do_viewport")
        layout.prop(self, "do_render")
        layout.prop(self, "make_visible")
        
    def execute(self, context):
        if not (self.do_render or self.do_viewport):
            self.report({'WARNING'}, "Select at least one of viewport or render")
            return {"CANCELLED"}
        
        clear_vis_keyframes(context, self.do_viewport, self.do_render, self.make_visible)
        self.report({'INFO'}, f"Complete")
        return {"FINISHED"}


class NWO_OT_BakeVisibilityToKeyframes(bpy.types.Operator):
    bl_idname = "nwo.bake_visibility_to_keyframes"
    bl_label = "Bake Shot Visibility to Keyframes"
    bl_description = "Bakes the status of whether an object is hidden per shot to the hide_render and hide_viewport properties. This is done for every shot camera, not just the currently selected one"
    bl_options = {"UNDO", 'REGISTER'}
    
    do_viewport: bpy.props.BoolProperty(
        name="Keyframe Viewport",
        description="Keyframes the hide_viewport property to hide/unhide objects in the 3D viewport",
        default=True,
    )
    do_render: bpy.props.BoolProperty(
        name="Keyframe Render",
        description="Keyframes the hide_render property to hide/unhide objects during render",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return utils.get_scene_props().asset_type == 'cinematic'
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "do_viewport")
        layout.prop(self, "do_render")

    def execute(self, context):
        if not (self.do_render or self.do_viewport):
            self.report({'WARNING'}, "Select at least one of viewport or render baking")
            return {"CANCELLED"}
        
        count = bake_vis_to_keyframes(context, self.do_viewport, self.do_render)
        self.report({'INFO'}, f"Created {count} keyframes")
        return {"FINISHED"}

def run_anchor_offset():
    bpy.ops.nwo.cinematic_anchor_offset_main()

class NWO_OT_CinematicAnchorOffset(bpy.types.Operator):
    bl_idname = "nwo.cinematic_anchor_offset"
    bl_label = "Offset Anchor from 3D Cursor"
    bl_description = "Offsets the cinematic anchor by the current position of the 3D cursor. The effect of this means the level geometry (assuming it is parented to the anchor) will be moved in such a way that the position of the 3D cursor becomes the new center of the blender scene. For example if you had your characters animated in the middle of your blender scene, and you wanted them to animate on a platform in your level using the anchor, this would move the platform to your characters"
    bl_options = {'UNDO' , 'REGISTER'}
    
    nudge: bpy.props.FloatVectorProperty(
        name="Nudge",
        size=3,
        subtype='TRANSLATION'
    )
    rotation: bpy.props.FloatProperty(
        name="Rotation",
        subtype='ANGLE'
    )
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.asset_type == 'cinematic' and utils.pointer_ob_valid(context.scene.nwo.cinematic_anchor) # scene specific prop
    
    def execute(self, context):
        global nudge
        global rotation
        nudge = Vector(self.nudge)

        rotation = self.rotation
        
        loc, rot, sca = cast(Matrix, context.scene.cursor.matrix).decompose()
        matrix = Matrix.LocRotScale(loc + nudge, Euler((0, 0, 0)), sca)
            
        if hasattr(context.space_data, "region_3d"):
            r3d = context.space_data.region_3d
            r3d.view_matrix = r3d.view_matrix @ matrix
            r3d.view_location = r3d.view_location @ matrix
            
        bpy.app.timers.register(run_anchor_offset, first_interval=0.02)
        return {"FINISHED"}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self, width=500)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "nudge")
        layout.prop(self, "rotation")

class NWO_OT_CinematicAnchorOffsetMain(bpy.types.Operator):
    bl_idname = "nwo.cinematic_anchor_offset_main"
    bl_label = "Offset Anchor from 3D Cursor"
    bl_description = "Offsets the cinematic anchor by the current position of the 3D cursor. The effect of this means the level geometry (assuming it is parented to the anchor) will be moved in such a way that the position of the 3D cursor becomes the new center of the blender scene. For example if you had your characters animated in the middle of your blender scene, and you wanted them to animate on a platform in your level using the anchor, this would move the platform to your characters"
    bl_options = {'UNDO', 'INTERNAL'}

    def execute(self, context):
        cursor = context.scene.cursor
        
        loc, rot, sca = cast(Matrix, context.scene.cursor.matrix).decompose()

        matrix = Matrix.LocRotScale(loc + nudge, Euler((0, 0, rotation)), sca)
            
        matrix.invert_safe()
        
        anchor = context.scene.nwo.cinematic_anchor # scene specific
        anchor.matrix_world = matrix @ anchor.matrix_world
        
        cursor.location = -nudge

        return {"FINISHED"}


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
        scene_nwo = context.scene.nwo # scene specific
        events = scene_nwo.cinematic_events
        event_data = None
        current_event = None
        if events and scene_nwo.active_cinematic_event_index > -1 and scene_nwo.active_cinematic_event_index < len(events):
            current_event = events[scene_nwo.active_cinematic_event_index]
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
        
        scene_nwo.active_cinematic_event_index = len(events) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_CinematicEventRemove(bpy.types.Operator):
    bl_idname = "nwo.cinematic_event_remove"
    bl_label = "Remove Cinematic Event"
    bl_description = "Removes the highlighted cinematic event"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = context.scene.nwo # scene specific
        return scene_nwo.cinematic_events and scene_nwo.active_cinematic_event_index > -1 and scene_nwo.active_cinematic_event_index < len(scene_nwo.cinematic_events)
    
    def execute(self, context):
        nwo = context.scene.nwo # scene specific
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
        scene_nwo = context.scene.nwo # scene specific
        return scene_nwo.cinematic_events and scene_nwo.active_cinematic_event_index > -1 and scene_nwo.active_cinematic_event_index < len(scene_nwo.cinematic_events)
    
    def execute(self, context):
        scene_nwo = context.scene.nwo # scene specific
        scene_nwo.active_cinematic_event_index = 0
        scene_nwo.cinematic_events.clear()
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
        scene_nwo = context.scene.nwo # scene specific
        return scene_nwo.cinematic_events and scene_nwo.active_cinematic_event_index > -1 and scene_nwo.active_cinematic_event_index < len(scene_nwo.cinematic_events)

    def execute(self, context):
        nwo = context.scene.nwo # scene specific
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
        scene_nwo = context.scene.nwo # scene specific
        return scene_nwo.cinematic_events and scene_nwo.active_cinematic_event_index > -1 and scene_nwo.active_cinematic_event_index < len(scene_nwo.cinematic_events)
    
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
        nwo = utils.get_scene_props()
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        event.default_sound_effect = self.fx
        return {'FINISHED'}
    
class GetCinematicBase(bpy.types.Operator):
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = context.scene.nwo # scene specific
        return scene_nwo.cinematic_events and scene_nwo.active_cinematic_event_index > -1 and scene_nwo.active_cinematic_event_index < len(scene_nwo.cinematic_events)
    
    def items(self, context):
        global variants
        global regions
        global permutations
        scene_nwo = context.scene.nwo # scene specific
        event = scene_nwo.cinematic_events[scene_nwo.active_cinematic_event_index]
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
        nwo = utils.get_scene_props()
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
    
# LIGHTS, camera, action!

class NWO_UL_CameraLights(bpy.types.UIList):
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index):
        layout.label(text=item.light.name if item.light else "NONE", icon='OUTLINER_OB_LIGHT')
        
class NWO_OT_CameraLightsClear(bpy.types.Operator):
    bl_idname = "nwo.camera_light_clear"
    bl_label = "Clear Camera Lights"
    bl_description = "Removes all entries from the list"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CAMERA' and context.object.nwo.cinematic_lights
    
    def execute(self, context):
        nwo = context.object.nwo
        nwo.active_cinematic_light_index = 0
        nwo.cinematic_lights.clear()
        context.area.tag_redraw()
        return {'FINISHED'}
        
class NWO_OT_CameraLightRemove(bpy.types.Operator):
    bl_idname = "nwo.camera_light_remove"
    bl_label = "Remove Camera Light"
    bl_description = "Removes the highlighted light from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CAMERA' and context.object.nwo.cinematic_lights

    def execute(self, context):
        nwo = context.object.nwo
        table = nwo.cinematic_lights
        table.remove(nwo.active_cinematic_light_index)
        if nwo.active_cinematic_light_index > len(table) - 1:
            nwo.active_cinematic_light_index -= 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_CameraLightAdd(bpy.types.Operator):
    bl_idname = "nwo.camera_light_add"
    bl_label = "Add Camera Light"
    bl_description = "Adds selected lights to the list"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CAMERA'
    
    def add_entry(self, table, ob: bpy.types.Object | None):
        item = table.add()
        item.actor = ob
    
    def execute(self, context):
        nwo = context.object.nwo
        table = nwo.cinematic_lights
        light_count = 0
        for ob in context.selected_objects:
            if ob == context.object: # camera selected
                continue
            
            if not utils.is_halo_light(ob):
                continue
            
            self.add_entry(table, ob)
            light_count += 1
                
        if light_count == 0:
            self.add_entry(table, None)
            light_count += 1
        
        if light_count == 1:
            self.report({'INFO'}, f"Added 1 entry")
        else:
            self.report({'INFO'}, f"Added {light_count} entries")
                
        nwo.active_cinematic_light_index = len(table) - 1
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_SelectCameraLights(bpy.types.Operator):
    bl_idname = "nwo.camera_lights_select"
    bl_label = "Select Camera Light Objects"
    bl_description = "Selects lights which are active for this shot"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'CAMERA'
    
    def execute(self, context):
        nwo = context.object.nwo
        if nwo.cinematic_lights_type == 'exclude':
            excluded_objects = {item.light for item in nwo.cinematic_lights if item.light is not None}
            for ob in context.view_layer.objects:
                if ob.type == 'ARMATURE' and ob not in excluded_objects:
                    ob.select_set(True)
        else:
            for item in nwo.actors:
                if item.actor is not None:
                    item.actor.select_set(True)
                    
        return {'FINISHED'}
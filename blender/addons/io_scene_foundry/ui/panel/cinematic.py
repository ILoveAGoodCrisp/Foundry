from pathlib import Path
from typing import cast
import blf
import bpy
from mathutils import Euler, Matrix, Vector

from ...managed_blam.scenario import ScenarioTag
from ...managed_blam.render_model import RenderModelTag
from ...managed_blam.model import ModelTag
from ...managed_blam.object import ObjectTag
from ...managed_blam import Tag
from ...icons import get_icon_id
from ... import utils

SOUND_FX_TAG = r"sound\global_fx.sound_effect_collection"
MIN_CINEMATIC_EVENT_FRAME = 0
MAX_CINEMATIC_EVENT_FRAME = 2_147_483_647
MAX_CINEMATIC_EVENT_SCALE = 10_000.0

variants = {}
regions = {}
permutations = {}

nudge = Vector.Fill(3, 0)
rotation = 0

def _tag_redraw_areas(context: bpy.types.Context):
    screen = getattr(context, "screen", None)
    if screen is None:
        if context.area is not None:
            context.area.tag_redraw()
        return

    for area in screen.areas:
        area.tag_redraw()

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
            case 'MUSIC':
                layout.label(text=item.name, icon='SOUND')
            case 'FUNCTION':
                layout.label(text=item.name, icon='FCURVE')
        
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
            event.actor = active_cinematic_object
            if not set_marker:
                event.marker = active_cinematic_object
        
        if current_event is not None:
            if event.marker != current_event.marker:
                event.marker_name = ""
                
            if event.actor != current_event.actor:
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
        return context.window_manager.invoke_confirm(self, event, title="Clear all events?", confirm_text="Yes", icon='ERROR')
    
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
    
class NWO_OT_UpdateActor(bpy.types.Operator):
    bl_idname = "nwo.update_actor"
    bl_label = "Update Actor"
    bl_description = "Replaces this armature and its child meshes / markers with the model and variant set"
    bl_options = {"UNDO"}

    import_biped_weapon: bpy.props.BoolProperty(
        name="Import Biped Weapons",
        description="Imports all weapons referenced by the biped tag",
    )

    def items_biped_weapon_source(self, context):
        from ...tools.importer import biped_weapon_source_items
        return biped_weapon_source_items(self, context)

    biped_weapon_source: bpy.props.EnumProperty(
        name="Biped Weapon",
        description="Weapon source to import when importing biped weapons",
        items=items_biped_weapon_source,
    )

    tag_import_attachments: bpy.props.BoolProperty(
        name="Attachments",
        description="Import object tag attachments. Currently supports lights and cheap lights",
    )

    build_blender_materials: bpy.props.BoolProperty(
        name="Generate Materials",
        description="Build Blender material nodes from shader/material tags",
        default=True,
    )

    always_extract_bitmaps: bpy.props.BoolProperty(
        name="Always Extract Bitmaps",
        description="Always re-extract bitmap files while generating materials",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        ob = context.object
        return bool(context.scene.nwo.asset_type == 'cinematic' and ob is not None and ob.type == 'ARMATURE' and ob.nwo.cinematic_object.strip())

    def _tag_is_biped(self, context: bpy.types.Context):
        ob = context.object
        return ob is not None and Path(utils.relative_path(ob.nwo.cinematic_object)).suffix.lower() == ".biped"

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if not self._tag_is_biped(context):
            self.import_biped_weapon = False
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.use_property_split = True
        layout.label(text=f"Updating: {Path(context.object.nwo.cinematic_object).name}")
        if self._tag_is_biped(context):
            layout.prop(self, "import_biped_weapon")
            if self.import_biped_weapon:
                layout.prop(self, "biped_weapon_source")
        layout.prop(self, "tag_import_attachments")
        layout.prop(self, "build_blender_materials")
        layout.prop(self, "always_extract_bitmaps")

    def _delete_child_objects(self, armature: bpy.types.Object):
        objects_to_delete = set(armature.children_recursive)
        changed = True
        while changed:
            changed = False
            for ob in bpy.data.objects:
                if ob == armature or ob in objects_to_delete:
                    continue
                has_deleted_parent = ob.parent in objects_to_delete
                has_deleted_constraint_target = any(getattr(constraint, "target", None) in objects_to_delete for constraint in ob.constraints)
                if has_deleted_parent or has_deleted_constraint_target:
                    objects_to_delete.add(ob)
                    objects_to_delete.update(ob.children_recursive)
                    changed = True

        for child in sorted(objects_to_delete, key=lambda ob: len(ob.children_recursive)):
            if child.name in bpy.data.objects:
                bpy.data.objects.remove(child, do_unlink=True)

        return len(objects_to_delete)

    def _clear_armature_bones(self, context: bpy.types.Context, armature: bpy.types.Object):
        utils.deselect_all_objects()
        armature.select_set(True)
        utils.set_active_object(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        for bone in list(armature.data.edit_bones):
            armature.data.edit_bones.remove(bone)
        bpy.ops.object.mode_set(mode='OBJECT')

    def execute(self, context: bpy.types.Context):
        from ...tools.importer import NWOImporter, clear_path_cache, setup_materials

        armature = context.object
        if armature is None or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "Select a cinematic actor armature")
            return {'CANCELLED'}

        nwo = armature.nwo
        tag_path = nwo.cinematic_object.strip()
        if not tag_path:
            self.report({'WARNING'}, "Set a cinematic object tag first")
            return {'CANCELLED'}

        tag_path_rel = utils.relative_path(tag_path)
        tag_path_full = Path(utils.get_tags_path(), tag_path_rel)
        if not tag_path_full.exists():
            self.report({'WARNING'}, f"Cinematic object tag does not exist: {tag_path_rel}")
            return {'CANCELLED'}

        scene_nwo = context.scene.nwo
        variant = nwo.cinematic_variant.strip().lower()
        is_biped_tag = tag_path_full.suffix.lower() == ".biped"
        with ObjectTag(path=tag_path_rel, raise_on_error=False) as object_tag:
            if not object_tag.valid:
                self.report({'WARNING'}, f"Could not read cinematic object tag: {tag_path_rel}")
                return {'CANCELLED'}

            model_path = object_tag.get_model_tag_path_full()
            if not model_path or not Path(model_path).exists():
                self.report({'WARNING'}, f"Cinematic object has no valid model tag: {tag_path_rel}")
                return {'CANCELLED'}

            if variant:
                with ModelTag(path=model_path, raise_on_error=False) as model_tag:
                    if not model_tag.valid:
                        self.report({'WARNING'}, f"Could not read model tag: {Path(model_path).name}")
                        return {'CANCELLED'}
                    variant_names = {name.lower(): name for name in model_tag.get_model_variants()}
                if variant not in variant_names:
                    self.report({'WARNING'}, f"Variant '{variant}' does not exist on {Path(model_path).name}")
                    return {'CANCELLED'}
                variant = variant_names[variant]

        armature_name = armature.name
        armature_pose_position = armature.data.pose_position
        transformed_for_import = False
        imported_objects = []
        starting_materials = set(bpy.data.materials)
        if self.always_extract_bitmaps:
            clear_path_cache()

        utils.set_object_mode(context)
        utils.deselect_all_objects()
        armature.select_set(True)
        utils.set_active_object(armature)
        armature.data.pose_position = 'REST'
        context.view_layer.update()

        importer = NWOImporter(context, [str(tag_path_full)], ['object'])
        importer.tag_render = True
        importer.tag_markers = True
        importer.tag_variant = variant
        importer.import_variant_children = True
        importer.import_biped_weapon = bool(self.import_biped_weapon and is_biped_tag)
        importer.biped_weapon_source = self.biped_weapon_source
        importer.import_biped_weapon_non_export = False
        importer.tag_import_attachments = self.tag_import_attachments

        try:
            if importer.needs_scaling:
                utils.transform_scene(context, (1 / importer.scale_factor), importer.to_x_rot, scene_nwo.forward_direction, 'x', objects=[armature], actions=[])
                transformed_for_import = True

            deleted_count = self._delete_child_objects(armature)
            self._clear_armature_bones(context, armature)

            imported_objects, imported_armature, _render, _model_collection = importer.import_object([str(tag_path_full)], armature, return_cin_stuff=True)
            if imported_armature is not None:
                armature = imported_armature
            if armature not in imported_objects:
                imported_objects.append(armature)

            if importer.needs_scaling:
                utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', scene_nwo.forward_direction, objects=imported_objects, actions=[])
                transformed_for_import = False

            setup_materials(context, importer, starting_materials, imported_objects, self.build_blender_materials, self.always_extract_bitmaps, importer.emissive_meshes)

        finally:
            utils.set_object_mode(context)
            if transformed_for_import:
                utils.transform_scene(context, importer.scale_factor, importer.from_x_rot, 'x', scene_nwo.forward_direction, objects=[armature], actions=[])
            if armature.name in bpy.data.objects:
                armature.name = armature_name
                armature.data.pose_position = armature_pose_position
                nwo = armature.nwo
                nwo.cinematic_object = tag_path_rel
                if importer.tag_variant:
                    nwo.cinematic_variant = importer.tag_variant
                utils.deselect_all_objects()
                armature.select_set(True)
                utils.set_active_object(armature)
            context.view_layer.update()

        new_child_count = len(armature.children_recursive)
        self.report({'INFO'}, f"Updated actor from {tag_path_full.name}: removed {deleted_count}, added {new_child_count}")
        return {'FINISHED'}

class NWO_OT_TransformCinematicEventFrames(bpy.types.Operator):
    bl_idname = "nwo.transform_cinematic_event_frames"
    bl_label = "Transform Event Frames"
    bl_description = "Bulk move and scale the cinematic event frames"
    bl_options = {"UNDO"}

    operation: bpy.props.EnumProperty(
        name="Operation",
        description="How to transform the cinematic event frames",
        options={'HIDDEN', 'SKIP_SAVE'},
        items=[
            ('MOVE', "Move", "Move event frames by a frame offset"),
            ('SCALE', "Scale", "Scale event frames around the current timeline frame"),
        ],
        default='MOVE',
    )

    scope: bpy.props.EnumProperty(
        name="Scope",
        description="Which event frames are affected by the transform",
        options={'SKIP_SAVE'},
        items=[
            ('ALL', "All Frames", "Transform all cinematic event frames"),
            ('BEFORE', "Before Current Frame", "Transform event frames before the current timeline frame"),
            ('AFTER', "After Current Frame", "Transform event frames after the current timeline frame"),
        ],
        default='ALL',
    )

    _event_data = None
    _pivot_frame = 0
    _current_offset = 0
    _current_scale = 1.0
    _target_count = 0
    _last_mouse_x = 0
    _last_mouse_y = 0
    _mouse_delta_x = 0
    _draw_handle = None

    @classmethod
    def poll(cls, context):
        scene_nwo = context.scene.nwo # scene specific
        return bool(scene_nwo.cinematic_events)

    @classmethod
    def description(cls, context, properties) -> str:
        operation = getattr(properties, "operation", 'MOVE')
        verb = "Move" if operation == 'MOVE' else "Scale"
        if operation == 'MOVE':
            detail = "Drag left or right to offset frames."
        else:
            detail = "Drag left or right to scale frames around the current timeline frame."

        return f"{verb} cinematic event frames. {detail} Press A/B/F during the transform to affect all, before, or after the current frame."

    def _sequence_strips(self, scene):
        sequence_editor = getattr(scene, "sequence_editor", None)
        if sequence_editor is None:
            return None

        return getattr(sequence_editor, "strips_all", None)

    def _strip_from_name(self, scene, strip_name):
        if not strip_name:
            return None

        strips = self._sequence_strips(scene)
        if strips is None:
            return None

        return strips.get(strip_name)

    def _effective_event_frame(self, scene, event):
        strip_name = ""
        strip_frame = None
        if event.type == 'DIALOGUE' and event.sound_strip:
            strip = self._strip_from_name(scene, event.sound_strip)
            if strip is not None:
                strip_name = event.sound_strip
                strip_frame = int(strip.frame_start)
                return strip_frame, strip_name, strip_frame

        return int(event.frame), strip_name, strip_frame

    def _collect_event_data(self, context):
        scene = context.scene
        event_data = []
        for index, event in enumerate(scene.nwo.cinematic_events):
            frame, strip_name, strip_frame = self._effective_event_frame(scene, event)
            event_data.append({
                "index": index,
                "frame": frame,
                "event_frame": int(event.frame),
                "strip_name": strip_name,
                "strip_frame": strip_frame,
            })

        return event_data

    def _entry_in_scope(self, entry):
        if self.scope == 'BEFORE':
            return entry["frame"] < self._pivot_frame
        if self.scope == 'AFTER':
            return entry["frame"] > self._pivot_frame

        return True

    def _clamp_frame(self, frame):
        try:
            frame = int(round(frame))
        except OverflowError:
            frame = MAX_CINEMATIC_EVENT_FRAME if frame > 0 else MIN_CINEMATIC_EVENT_FRAME

        return min(MAX_CINEMATIC_EVENT_FRAME, max(MIN_CINEMATIC_EVENT_FRAME, frame))

    def _set_entry_frame(self, context, entry, frame):
        event = context.scene.nwo.cinematic_events[entry["index"]]
        event.frame = self._clamp_frame(frame)

        strip = self._strip_from_name(context.scene, entry["strip_name"])
        if strip is not None:
            strip.frame_start = event.frame

    def _restore_original_frames(self, context):
        for entry in self._event_data:
            event = context.scene.nwo.cinematic_events[entry["index"]]
            event.frame = entry["event_frame"]

            strip = self._strip_from_name(context.scene, entry["strip_name"])
            if strip is not None and entry["strip_frame"] is not None:
                strip.frame_start = entry["strip_frame"]

    def _transformed_frame(self, original_frame):
        if self.operation == 'MOVE':
            return original_frame + self._current_offset

        return round(self._pivot_frame + ((original_frame - self._pivot_frame) * self._current_scale))

    def _mouse_wrap_bounds(self, context):
        window = getattr(context, "window", None)
        width = getattr(window, "width", 0)
        height = getattr(window, "height", 0)
        if width > 0 and height > 0:
            return 0, width - 1, 0, height - 1

        area = getattr(context, "area", None)
        if area is not None:
            return area.x, area.x + area.width - 1, area.y, area.y + area.height - 1

        return None

    def _wrap_cursor(self, context, event):
        window = getattr(context, "window", None)
        if window is None or not hasattr(window, "cursor_warp"):
            return

        bounds = self._mouse_wrap_bounds(context)
        if bounds is None:
            return

        min_x, max_x, min_y, max_y = bounds
        margin = 8
        left = min_x + margin
        right = max_x - margin
        bottom = min_y + margin
        top = max_y - margin
        if left >= right or bottom >= top:
            return

        warp_x = event.mouse_x
        warp_y = event.mouse_y

        if event.mouse_x <= left:
            warp_x = right
        elif event.mouse_x >= right:
            warp_x = left

        if event.mouse_y <= bottom:
            warp_y = top
        elif event.mouse_y >= top:
            warp_y = bottom

        if warp_x != event.mouse_x or warp_y != event.mouse_y:
            window.cursor_warp(warp_x, warp_y)
            self._last_mouse_x = warp_x
            self._last_mouse_y = warp_y

    def _update_mouse_delta(self, context, event):
        self._mouse_delta_x += event.mouse_x - self._last_mouse_x
        self._last_mouse_x = event.mouse_x
        self._last_mouse_y = event.mouse_y
        self._wrap_cursor(context, event)

    def _update_transform_values(self, event):
        delta_x = self._mouse_delta_x
        if self.operation == 'MOVE':
            pixels_per_frame = 18 if event.shift else 6
            self._current_offset = int(round(delta_x / pixels_per_frame))
        else:
            pixels_per_scale = 600 if event.shift else 200
            scale_delta = delta_x / pixels_per_scale
            if scale_delta >= 0:
                scale = 1.0 + scale_delta
            else:
                scale = 1.0 / (1.0 + abs(scale_delta))

            self._current_scale = min(MAX_CINEMATIC_EVENT_SCALE, max(0.01, scale))

    def _apply_transform(self, context):
        self._restore_original_frames(context)
        self._target_count = 0
        for entry in self._event_data:
            if not self._entry_in_scope(entry):
                continue

            self._set_entry_frame(context, entry, self._transformed_frame(entry["frame"]))
            self._target_count += 1

        self._set_status_text(context)
        _tag_redraw_areas(context)

    def _scope_label(self):
        match self.scope:
            case 'BEFORE':
                return "Before"
            case 'AFTER':
                return "After"
            case _:
                return "All"

    def _set_status_text(self, context):
        workspace = getattr(context, "workspace", None)
        if workspace is None or not hasattr(workspace, "status_text_set"):
            return

        workspace.status_text_set(
            "[LMB] Confirm   [RMB]/[Esc] Cancel   [A] All   [B] Before   [F] After   [Shift] Precision"
        )

    def _clear_status_text(self, context):
        workspace = getattr(context, "workspace", None)
        if workspace is not None and hasattr(workspace, "status_text_set"):
            workspace.status_text_set(None)

    def _transform_value_text(self):
        if self.operation == 'MOVE':
            return f"Move: {self._current_offset:+d} frames"

        return f"Scale: {self._current_scale:.3f}x"

    def _draw_transform_value(self):
        region = getattr(bpy.context, "region", None)
        if region is None:
            return

        text = self._transform_value_text()
        font_id = 0
        font_size = 12
        blf.size(font_id, font_size)
        width, height = blf.dimensions(font_id, text)
        x = (region.width - width) / 2
        y = max(48, region.height - 88)

        if hasattr(blf, "SHADOW"):
            blf.enable(font_id, blf.SHADOW)
            blf.shadow(font_id, 3, 0, 0, 0, 0.85)
            blf.shadow_offset(font_id, 1, -1)

        blf.position(font_id, x, y, 0)
        blf.color(font_id, 1, 1, 1, 1)
        blf.draw(font_id, text)

        if hasattr(blf, "SHADOW"):
            blf.disable(font_id, blf.SHADOW)

    def _add_draw_handler(self, context):
        if self._draw_handle is None:
            self._draw_handle = bpy.types.SpaceView3D.draw_handler_add(
                self._draw_transform_value,
                (),
                'WINDOW',
                'POST_PIXEL',
            )

        _tag_redraw_areas(context)

    def _remove_draw_handler(self, context):
        if self._draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_handle, 'WINDOW')
            self._draw_handle = None

        _tag_redraw_areas(context)

    def _reset_cursor(self, context):
        window = getattr(context, "window", None)
        if window is not None and hasattr(window, "cursor_set"):
            window.cursor_set('DEFAULT')

    def _set_modal_cursor(self, context):
        window = getattr(context, "window", None)
        if window is None or not hasattr(window, "cursor_set"):
            return

        cursor = 'MOVE_X' if self.operation == 'MOVE' else 'SCROLL_X'
        try:
            window.cursor_set(cursor)
        except TypeError:
            window.cursor_set('MOVE_X')

    def invoke(self, context, event):
        self._event_data = self._collect_event_data(context)
        if not self._event_data:
            self.report({'WARNING'}, "No cinematic event frames to transform")
            return {'CANCELLED'}
        self._set_modal_cursor(context)
        self._add_draw_handler(context)

        self._pivot_frame = int(context.scene.frame_current)
        self._current_offset = 0
        self._current_scale = 1.0
        self._target_count = 0
        self._last_mouse_x = event.mouse_x
        self._last_mouse_y = event.mouse_y
        self._mouse_delta_x = 0
        self._apply_transform(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            self._update_mouse_delta(context, event)
            self._update_transform_values(event)
            self._apply_transform(context)
            return {'RUNNING_MODAL'}

        if event.value == 'PRESS':
            match event.type:
                case 'A':
                    self.scope = 'ALL'
                    self._apply_transform(context)
                    return {'RUNNING_MODAL'}
                case 'B':
                    self.scope = 'BEFORE'
                    self._apply_transform(context)
                    return {'RUNNING_MODAL'}
                case 'F':
                    self.scope = 'AFTER'
                    self._apply_transform(context)
                    return {'RUNNING_MODAL'}
                case 'LEFTMOUSE' | 'RET' | 'NUMPAD_ENTER' | 'SPACE':
                    self._clear_status_text(context)
                    self._remove_draw_handler(context)
                    if self._target_count == 0:
                        self.report({'WARNING'}, "No cinematic event frames in scope")
                    else:
                        self.report({'INFO'}, f"Transformed {self._target_count} cinematic event frame{'s' if self._target_count != 1 else ''}")
                    _tag_redraw_areas(context)
                    self._reset_cursor(context)
                    return {'FINISHED'}
                case 'RIGHTMOUSE' | 'ESC':
                    self._restore_original_frames(context)
                    self._clear_status_text(context)
                    self._remove_draw_handler(context)
                    _tag_redraw_areas(context)
                    self._reset_cursor(context)
                    return {'CANCELLED'}

        return {'RUNNING_MODAL'}


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
        relative_tag_path = utils.relative_path(event.actor.nwo.cinematic_object)
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
    
class NWO_GetScenarioCustsceneTitles(bpy.types.Operator):
    bl_idname = "nwo.get_scenario_cutscene_titles"
    bl_label = "Cutscene Titles"
    bl_description = "Returns a list of scenario cutscene titles"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        nwo = utils.get_scene_props()
        if nwo.asset_type == 'cinematic':
            tag_path = Path(utils.get_tags_path(), utils.relative_path(nwo.cinematic_scenario))
            if tag_path.is_absolute() and tag_path.exists() and tag_path.is_file():
                scene_nwo = context.scene.nwo # scene specific
                return scene_nwo.cinematic_events and scene_nwo.active_cinematic_event_index > -1 and scene_nwo.active_cinematic_event_index < len(scene_nwo.cinematic_events)
        
        return False
    
    def title_items(self, context):
        nwo = utils.get_scene_props()
        items = []
        with ScenarioTag(path=nwo.cinematic_scenario) as scenario:
            items = scenario.collect_cutscene_titles()

        if not items:
            return [("none", "none", "No cinematic titles found")]

        return items
    
    cutscene_title: bpy.props.EnumProperty(
        name="Variant",
        items=title_items,
    )
    
    def execute(self, context):
        nwo = context.scene.nwo # scene specific
        event = nwo.cinematic_events[nwo.active_cinematic_event_index]
        event.script_text = self.cutscene_title
        return {'FINISHED'}

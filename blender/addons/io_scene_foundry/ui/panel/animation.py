"""Animation sub-panel specific operators"""

from collections import defaultdict
from pathlib import Path
import random
from typing import cast
import bpy

from ...managed_blam.animation import AnimationTag

from ...props.scene import NWO_AnimationBlendAxisItems, NWO_AnimationGroupItems, NWO_AnimationLeavesItems, NWO_AnimationPhaseSetsItems, NWO_AnimationPropertiesGroup
from ... import utils
from ...icons import get_icon_id

class NWO_OT_ExportFrameEvents(bpy.types.Operator):
    bl_idname = "nwo.export_animation_frame_events"
    bl_label = "Export Events"
    bl_description = "Exports animation frame events to the asset frame_event_list tag. Requires the animation graph tag to exist"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        tag_path = utils.get_asset_tag(".model_animation_graph", True)
        return tag_path is not None and Path(tag_path).exists()
    
    def execute(self, context):
        graph_path = utils.get_asset_tag(".model_animation_graph")
        with AnimationTag(path=graph_path) as graph:
            graph.events_from_blender()
            
        self.report({'INFO'}, "Frame events export complete")
        return {'FINISHED'}

class NWO_UL_AnimProps_EventsData(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        match item.data_type:
            case 'SOUND':
                layout.label(text=f'{data.frame_frame + item.frame_offset} - {Path(item.event_sound_tag).with_suffix("").name if item.event_sound_tag.strip(". ") else "NONE"}', icon='SOUND')
            case 'EFFECT':
                layout.label(text=f'{data.frame_frame + item.frame_offset} - {Path(item.event_effect_tag).with_suffix("").name if item.event_effect_tag.strip(". ") else "NONE"}', icon_value=get_icon_id("effects"))
            case 'DIALOGUE':
                layout.label(text=f'{data.frame_frame + item.frame_offset} - {item.dialogue_event}', icon='PLAY_SOUND')
                
class NWO_OT_AddAnimationEventData(bpy.types.Operator):
    bl_idname = "nwo.add_animation_event_data"
    bl_label = "Add"
    bl_description = "Add a new animation event data item"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        event = animation.animation_events[animation.active_animation_event_index]
        event.event_data.add()
        event.active_event_data_index = len(event.event_data) - 1
        context.area.tag_redraw()
        return {"FINISHED"}


class NWO_OT_RemoveAnimationEventData(bpy.types.Operator):
    bl_idname = "nwo.remove_animation_event_data"
    bl_label = "Remove"
    bl_description = "Remove an animation event data item from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1 and context.scene.nwo.animations[context.scene.nwo.active_animation_index].animation_events

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        event = animation.animation_events[animation.active_animation_event_index]
        index = event.active_event_data_index
        event.event_data.remove(index)
        if event.active_event_data_index > len(event.event_data) - 1:
            event.active_event_data_index += -1
        context.area.tag_redraw()
        return {"FINISHED"}
            
class NWO_UL_AnimProps_Events(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        match item.event_type:
            case '_connected_geometry_animation_event_type_frame':
                if item.frame_name == 'none' and item.event_data:
                    data_types = {d.data_type for d in item.event_data}
                    layout.label(text=f"{item.frame_frame} - {', '.join(data_types).title().strip(', ')}", icon_value=get_icon_id("animation_event"))
                else:
                    layout.label(text=f"{item.frame_frame} - {item.frame_name.title()}", icon_value=get_icon_id("animation_event"))
            case '_connected_geometry_animation_event_type_object_function':
                layout.label(text=item.object_function_name.rpartition("_")[2].upper())
            case '_connected_geometry_animation_event_type_import':
                layout.label(text=f"{item.frame_frame} - {item.import_name}", icon_value=get_icon_id("anim_overlay"))
            case '_connected_geometry_animation_event_type_wrinkle_map':
                layout.label(text=item.wrinkle_map_face_region, icon='MOD_NORMALEDIT')
            case '_connected_geometry_animation_event_type_ik_active':
                layout.label(text=f"{item.ik_target_usage.replace('_', ' ').title()} - Active", icon='CON_KINEMATIC')
            case '_connected_geometry_animation_event_type_ik_passive':
                layout.label(text=f"{item.ik_target_usage} - Passive", icon='CON_KINEMATIC')
            
class NWO_OT_ClearAnimations(bpy.types.Operator):
    bl_label = "Clear Animations"
    bl_idname = "nwo.clear_animations"
    bl_description = "Clears animations, optionally only clearing those that include strings from the filter. "
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations
    
    filter: bpy.props.StringProperty(
        name="Filter",
        description="Filter to test animations for before deleting them. Leave blank to clear all animations"
    )
    
    delete_actions: bpy.props.BoolProperty(
        name="Delete Actions",
        description="Enable to delete actions used by animations"
    )
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "filter")
        layout.prop(self, "delete_actions")
        
    def action_map(self, all_animations):    
        self.action_animations = defaultdict(list)
        for anim in all_animations:
            for track in anim.action_tracks:
                if track.action is not None:
                    self.action_animations[track.action].append(anim)
            
    def clear_actions(self):
        for action, animations in self.action_animations.items():
            if all(not a.name for a in animations):
                bpy.data.actions.remove(action)
                
    def execute(self, context):
        animations = context.scene.nwo.animations
        if self.delete_actions:
            self.action_map(animations)
            
        if self.filter:
            filtered_animations = [idx for idx, a in enumerate(animations) if self.filter.lower() in a.name.lower()]
            total_animations = len(filtered_animations)
            if total_animations == 0:
                self.report({'WARNING'}, f"No animations found that match filter: {self.filter}")
                return {'CANCELLED'}
            
            if total_animations == len(animations):
                animations.clear()
            else:
                for idx in reversed(filtered_animations):
                    animations.remove(idx)
                
        else:
            total_animations = len(animations)
            animations.clear()
            
        if self.delete_actions:
            self.clear_actions()
            
        context.scene.nwo.active_animation_index = len(animations) - 1
            
        self.report({'INFO'}, f"Cleared {total_animations} animations")
        return {"FINISHED"}

class NWO_OT_DeleteAnimation(bpy.types.Operator):
    bl_label = "Delete Animation"
    bl_idname = "nwo.delete_animation"
    bl_description = "Deletes a Halo Animation from the blend file"
    bl_options = {'UNDO'}
    
    delete_actions: bpy.props.BoolProperty(
        name="Delete Actions",
        description="Enable to delete actions used by this animation"
    )
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1
    
    def action_map(self, all_animations):    
        self.action_animations = defaultdict(list)
        for anim in all_animations:
            for track in anim.action_tracks:
                if track.action is not None:
                    self.action_animations[track.action].append(anim)
            
    def clear_actions(self) -> bool:
        for action, animations in self.action_animations.items():
            if all(not a.name for a in animations):
                bpy.data.actions.remove(action)
                
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "delete_actions")

    def execute(self, context):
        context.scene.tool_settings.use_keyframe_insert_auto = False
        current_animation_index = context.scene.nwo.active_animation_index
        animation = context.scene.nwo.animations[current_animation_index]
        if animation:
            if self.delete_actions:
                self.action_map(context.scene.nwo.animations)
            utils.clear_animation(animation)
            name = animation.name
            context.scene.nwo.animations.remove(current_animation_index)
            new_index = context.scene.nwo.active_animation_index - 1
            if new_index < 0 and context.scene.nwo.animations:
                new_index = 0
            context.scene.nwo.active_animation_index = new_index
            self.report({"INFO"}, f"Deleted animation: {name}")
        
        return {"FINISHED"}
    
class NWO_OT_UnlinkAnimation(bpy.types.Operator):
    bl_label = "Unlink Animation"
    bl_idname = "nwo.unlink_animation"
    bl_description = "Unlinks a Halo Animation"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1

    def execute(self, context):
        context.scene.tool_settings.use_keyframe_insert_auto = False
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        context.scene.nwo.active_animation_index = -1
        
        utils.clear_animation(animation)
                    
        return {"FINISHED"}
    
class NWO_OT_AnimationsFromBlend(bpy.types.Operator):
    bl_label = "Animations from Blend"
    bl_idname = "nwo.animations_from_blend"
    bl_description = "Imports animations from the selected blend file"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(
        name="Blend File", description="Path to a blend file", subtype="FILE_PATH"
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.blend",
        options={"HIDDEN"},
        maxlen=1024,
    )
    
    use_existing_actions: bpy.props.BoolProperty(name="Use Existing Actions", default=False, description="Tries to link to an existing action rather than using the imported one")
    import_events: bpy.props.BoolProperty(name="Import Events", default=True)
    import_renames: bpy.props.BoolProperty(name="Import Renames", default=True)
    animation_filter: bpy.props.StringProperty(
        name="Filter",
        description="Filter for the animations to import. Animations that don't contain the specified strings (space or colon delimited) will be skipped"
    )
    
    def execute(self, context):
        current_scenes = set(bpy.data.scenes)
        current_animations = context.scene.nwo.animations
        with bpy.data.libraries.load(self.filepath, link=False) as (data_from, data_to):
            data_to.scenes = data_from.scenes
            
        new_scenes = [s for s in bpy.data.scenes if s not in current_scenes]
        
        new_anim_count = 0
        
        filter = self.animation_filter.replace(" ", ":")
        
        for scene in new_scenes:
            for anim in scene.nwo.animations:
                colon_name = anim.name.replace(" ", ":")
                
                if filter and filter not in colon_name:
                    continue
                
                if current_animations.get(anim.name) is None:
                    new_anim = current_animations.add()
                    new_anim_count += 1
                    for key, value in anim.items():
                        new_anim[key] = value
                        
                    if not self.import_events:
                        new_anim.animation_events.clear()
                        
                    if not self.import_renames:
                        new_anim.animation_renames.clear()
                        
                    for track in new_anim.action_tracks:
                        ob = track.object
                        if ob is not None:
                            original_name = utils.reduce_suffix(ob.name)
                            potential_ob = bpy.data.objects.get(original_name)
                            if potential_ob:
                                track.object = potential_ob
                            else:
                                track.object = None
                        
                        if self.use_existing_actions:
                            action = track.action
                            if action is not None:
                                original_name = utils.reduce_suffix(action.name)
                                potential_action = bpy.data.actions.get(original_name)
                                if potential_action:
                                    track.action = potential_action
                        
        for scene in new_scenes:
            bpy.data.scenes.remove(scene)
        
        self.report({'INFO'}, f"Imported {new_anim_count} animations")
        return {'FINISHED'}
    
    def invoke(self, context, _):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "use_existing_actions")
        layout.prop(self, "import_events")
        layout.prop(self, "import_renames")
        layout.prop(self, "animation_filter")

class NWO_OT_OpenExternalAnimationBlend(bpy.types.Operator):
    bl_label = "Open Blend"
    bl_idname = "nwo.open_external_animation_blend"
    bl_description = "Opens the blend file for this GR2 file (it it exists)"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1
    
    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        
        if not animation.external:
            self.report({'WARNING'}, "Animation is not external. No blend to open")
            return {'CANCELLED'}
            
        root_asset = Path(animation.gr2_path).parent.parent.parent
        blend = Path(utils.get_data_path(), root_asset, "animations", animation.name).with_suffix(".blend")
        
        if blend.exists():
            bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
            bpy.ops.wm.open_mainfile(filepath=str(blend))
        else:
            self.report({'WARNING'}, f"No blender file associated with this GR2. Expected: {blend}")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Loaded blend: {blend}")
        return {'FINISHED'}

class NWO_OT_AnimationMoveToOwnBlend(bpy.types.Operator):
    bl_label = "Move to Own Blend"
    bl_idname = "nwo.animation_move_to_own_blend"
    bl_description = "Moves this animation to its own blend file"
    bl_options = {'UNDO'}
    
    pca: bpy.props.BoolProperty(
        name="PCA",
        description="Animation has PCA (shape key) data"
    )
    
    pose_overlay: bpy.props.BoolProperty(
        name="Pose Overlay",
        description="Animation has pose overlay data"
    )
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1 and utils.valid_nwo_asset(context)
    
    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        rel_path = ""
        if bpy.data.filepath:
            rel_path = utils.relative_path(bpy.data.filepath)
            
        sidecar_path = context.scene.nwo.sidecar_path
        
        asset_path = utils.get_asset_path_full()
        blend_path = Path(utils.get_asset_path_full(), "animations", animation.name).with_suffix(".blend")
        gr2_path = Path(asset_path, "export", "animations", animation.name).with_suffix(".gr2")
        animation.external = True
        animation.gr2_path = utils.relative_path(gr2_path)
        
        bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
        
        frame_start, frame_end = animation.frame_start, animation.frame_end
        
        if not blend_path.parent.exists():
            blend_path.parent.mkdir(parents=True)
            
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False, compress=context.preferences.filepaths.use_file_compression)
        
        scene = bpy.context.scene
        scene.frame_start, scene.frame_end = frame_start, frame_end
        scene.nwo.animations.clear()
        
        scene.nwo.asset_type = 'single_animation'
        if rel_path:
            scene.nwo.is_child_asset = True
            scene.nwo.parent_asset = rel_path
            scene.nwo.parent_sidecar = sidecar_path
        
        bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
        self.report({'INFO'}, f"Loaded new blend: {blend_path}")
        return {'FINISHED'}
    
    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pose_overlay")
        if utils.is_corinth(context):
            layout.prop(self, "pca")

class NWO_OT_AnimationLinkToGR2(bpy.types.Operator):
    bl_label = "Link to GR2"
    bl_idname = "nwo.animation_link_to_gr2"
    bl_description = "Links this animation directly to a gr2 file"
    bl_options = {'UNDO'}
    
    filepath: bpy.props.StringProperty(
        name="path", description="Path to a gr2 file", subtype="FILE_PATH"
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.gr2",
        options={"HIDDEN"},
        maxlen=1024,
    )
    
    pca: bpy.props.BoolProperty(
        name="PCA",
        description="Animation has PCA (shape key) data"
    )
    
    pose_overlay: bpy.props.BoolProperty(
        name="Pose Overlay",
        description="Animation has pose overlay data"
    )
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1
    
    def execute(self, context):
        
        path = Path(self.filepath)
        
        if path.exists():
            animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
            animation.external = True
            animation.gr2_path = utils.relative_path(self.filepath)
            animation.pose_overlay = self.pose_overlay
            animation.has_pca = utils.is_corinth(context) and self.pca
        
        return {'FINISHED'}
    
    def invoke(self, context, _):
        asset_path = utils.get_asset_path_full()
        
        if Path(asset_path).exists():
            self.filepath = asset_path
            animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
            expected_path = Path(self.filepath, "export", "animations", animation.name).with_suffix(".gr2")
            if expected_path.exists():
                self.filepath = str(expected_path)
        
        elif bpy.data.filepath and Path(bpy.data.filepath).exists():
            self.filepath = str(Path(bpy.data.filepath).parent)
            
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "pose_overlay")
        if utils.is_corinth(context):
            layout.prop(self, "pca")
    
class NWO_OT_AnimationsFromActions(bpy.types.Operator):
    bl_label = "Animations from Actions"
    bl_idname = "nwo.animations_from_actions"
    bl_description = "Creates new animations from every action in this blend file. This will add action tracks for currently selected animated objects"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.object and bpy.data.actions
    
    def execute(self, context):
        objects = [ob for ob in context.selected_objects if ob.animation_data]
        if not objects:
            arm = utils.get_rig(context)
            if arm is not None:
                objects = [arm]
        scene_nwo = context.scene.nwo
        current_animation_names = {animation.name for animation in context.scene.nwo.animations}
        used_actions = set()
        for animation in context.scene.nwo.animations:
            for track in animation.action_tracks:
                if track.action:
                    used_actions.add(action)
                    
        for action in bpy.data.actions:
            if action in used_actions:
                continue
            # action_nwo = action.nwo
            # name = action_nwo.name_override if action_nwo.name_override else action.name
            name = action.name
            if name in current_animation_names:
                continue
            
            animation = scene_nwo.animations.add()
            animation: NWO_AnimationPropertiesGroup

            for ob in objects:
                group = animation.action_tracks.add()
                group.object = ob
                group.action = action
            
            animation.name = name
            animation.frame_start = int(action.frame_start)
            animation.frame_end = int(action.frame_end)
            animation.export_this = action.use_frame_range
            # for key, value in action_nwo.items():
            #     animation[key] = value
            
        context.area.tag_redraw()
            
        return {'FINISHED'}
    
animation_event_data = []
    
class NWO_OT_CopyEvents(bpy.types.Operator):
    bl_label = "Copy Events"
    bl_idname = "nwo.copy_events"
    bl_description = "Copies Animation events"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        if context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1:
            animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
            return animation.animation_events
        
        return False
    
    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        global animation_event_data
        animation_event_data = [event.items() for event in animation.animation_events]
        return {'FINISHED'}
        
class NWO_OT_PasteEvents(bpy.types.Operator):
    bl_label = "Paste Events"
    bl_idname = "nwo.paste_events"
    bl_description = "Pastes Animation events"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1 and animation_event_data
    
    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        for event_data in animation_event_data:
            event = animation.animation_events.add()
            animation.active_animation_event_index  = len(animation.animation_events) - 1
            for key, value in event_data:
                event[key] = value
                
        return {'FINISHED'}
    
class NWO_MT_AnimationTools(bpy.types.Menu):
    bl_label = "Animation Tools"
    bl_idname = "NWO_MT_AnimationTools"
    
    def draw(self, context):
        layout = self.layout
        layout.operator("nwo.animations_from_actions", icon='UV_SYNC_SELECT')
        layout.operator("nwo.animations_from_blend", icon='IMPORT')
        layout.operator("nwo.clear_animations", icon='CANCEL')
        layout.operator("nwo.clear_renames", icon='CANCEL')
        layout.operator("nwo.clear_events", icon='CANCEL')
        
class NWO_OT_ClearRenames(bpy.types.Operator):
    bl_label = "Clear Renames"
    bl_idname = "nwo.clear_renames"
    bl_description = "Clears all animation renames from all animations"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations
    
    def execute(self, context):
        rename_count = 0
        for animation in context.scene.nwo.animations:
            rename_count += len(animation.animation_renames)
            animation.animation_renames.clear()
            
        self.report({'INFO'}, f"Removed {rename_count} animation renames")
        return {'FINISHED'}
    
class NWO_OT_ClearEvents(bpy.types.Operator):
    bl_label = "Clear Events"
    bl_idname = "nwo.clear_events"
    bl_description = "Clears all animation events from all animations"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations
    
    def execute(self, context):
        event_count = 0
        for animation in context.scene.nwo.animations:
            event_count += len(animation.animation_events)
            animation.animation_events.clear()
            
        self.report({'INFO'}, f"Removed {event_count} animation events")
        return {'FINISHED'}
    
class NWO_OT_SetTimeline(bpy.types.Operator):
    bl_label = "Sync Timeline"
    bl_idname = "nwo.set_timeline"
    bl_description = "Sets the scene timeline to match the current animation's frame range"
    bl_options = {'REGISTER', 'UNDO'}
    
    exclude_first_frame: bpy.props.BoolProperty()
    exclude_last_frame: bpy.props.BoolProperty()
    use_self_props: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.active_animation_index > -1
    
    def execute(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        
        if animation.animation_type == 'composite':
            return {'FINISHED'}
        
        actions = []
        start_frame = animation.frame_start
        if self.use_self_props:
            final_start_frame = start_frame + self.exclude_first_frame
            scene_nwo.exclude_first_frame = self.exclude_first_frame
        else:
            final_start_frame = start_frame + scene_nwo.exclude_first_frame
            
        end_frame = animation.frame_end
        if self.use_self_props:
            final_end_frame = end_frame + self.exclude_last_frame
            scene_nwo.exclude_last_frame = self.exclude_last_frame
        else:
            final_end_frame = end_frame + scene_nwo.exclude_last_frame
        
        if (end_frame - start_frame) > 0:
            scene.frame_start = final_start_frame
            scene.frame_end = final_end_frame
            scene.frame_current = final_start_frame
            
        return {'FINISHED'}
    
    def invoke(self, context, _):
        self.use_self_props = True
        return self.execute(context)
        
    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'exclude_first_frame', text="Exclude First Frame")
        layout.prop(self, 'exclude_last_frame', text="Exclude Last Frame")

class NWO_OT_NewAnimation(bpy.types.Operator):
    bl_label = "New Animation"
    bl_idname = "nwo.new_animation"
    bl_description = "Creates a new Halo Animation"
    bl_options = {'REGISTER', "UNDO"}

    frame_start: bpy.props.IntProperty(name="First Frame", default=1)
    frame_end: bpy.props.IntProperty(name="Last Frame", default=30)
    copy: bpy.props.BoolProperty(name="Is Copy")
            
    animation_type: bpy.props.EnumProperty(
        name="Type",
        description="Set the type of Halo animation you want this action to be",
        items=[
            ("base", "Base", "Defines a base animation. Allows for varying levels of root bone movement (or none). Useful for cinematic animations, idle animations, turn and movement animations"),
            ("overlay","Overlay", "Animations that overlay on top of a base animation (or none). Supports keyframe and pose overlays. Useful for animations that should overlay on top of base animations, such as vehicle steering or weapon aiming. Supports object functions to define how these animations blend with others\nLegacy format: JMO\nExamples: fire_1, reload_1, device position"),
            ("replacement", "Replacement", "Animations that fully replace base animated nodes, provided those bones are animated. Useful for animations that should completely overrule a certain set of bones, and don't need any kind of blending influence. Can be set to either object or local space"),
            ("world", "World", "Animations that play relative to the world rather than an objects current position"),
            ("composite", "Composite", "Composite animation. Has no animation data itself but references other animations. Halo 4 and Halo 2AMP only")
        ],
    )
    
    animation_movement_data: bpy.props.EnumProperty(
        name='Movement',
        description='Set how this animations moves the object in the world',
        default="none",
        items=[
            (
                "none",
                "None",
                "Object will not physically move from its position. The standard for cinematic animation.\nLegacy format: JMM\nExamples: enter, exit, idle",
            ),
            (
                "xy",
                "Horizontal",
                "Object can move on the XY plane. Useful for horizontal movement animations.\nLegacy format: JMA\nExamples: move_front, walk_left, h_ping front gut",
            ),
            (
                "xyyaw",
                "Horizontal & Yaw",
                "Object can turn on its Z axis and move on the XY plane. Useful for turning movement animations.\nLegacy format: JMT\nExamples: turn_left, turn_right",
            ),
            (
                "xyzyaw",
                "Full & Yaw",
                "Object can turn on its Z axis and move in any direction. Useful for jumping animations.\nLegacy format: JMZ\nExamples: climb, jump_down_long, jump_forward_short",
            ),
            (
                "full",
                "Full (Vehicle Only)",
                "Full movement and rotation. Useful for vehicle animations that require multiple dimensions of rotation. Do not use on bipeds.\nLegacy format: JMV\nExamples: climb, vehicle roll_left, vehicle roll_right_short",
            ),
        ]
    )
    
    animation_space: bpy.props.EnumProperty(
        name="Space",
        description="Set whether the animation is in object or local space",
        items=[
            ('object', 'Object', 'Replacement animation in object space.\nLegacy format: JMR\nExamples: revenant_p, sword put_away'),
            ('local', 'Local', 'Replacement animation in local space.\nLegacy format: JMRX\nExamples: combat pistol any grip, combat rifle sr grip'),
        ]
    )

    # animation_is_pose: bpy.props.BoolProperty(
    #     name='Pose Overlay',
    #     description='Tells the exporter to compute aim node directions for this overlay. These allow animations to be affected by the aiming direction of the animated object. You must set the pedestal, pitch, and yaw usages in the Foundry armature properties to use this correctly\nExamples: aim_still_up, acc_up_down, vehicle steering'
    # )

    state_type: bpy.props.EnumProperty(
        name="State Type",
        items=[
            ("action", "Action / Overlay", ""),
            ("transition", "Transition", ""),
            ("damage", "Death & Damage", ""),
            ("custom", "Custom", ""),
        ],
    )

    mode: bpy.props.StringProperty(
        name="Mode",
        description="The mode the object must be in to use this animation. Use 'any' for all modes. Other valid inputs include but are not limited to: 'crouch' when a unit is crouching,  'combat' when a unit is in combat. Modes can also refer to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more information refer to existing model_animation_graph tags. Can be empty",
    )

    weapon_class: bpy.props.StringProperty(
        name="Weapon Class",
        description="The weapon class this unit must be holding to use this animation. Weapon class is defined per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty",
    )
    weapon_type: bpy.props.StringProperty(
        name="Weapon Name",
        description="The weapon type this unit must be holding to use this animation.  Weapon name is defined per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty",
    )
    set: bpy.props.StringProperty(
        name="Set", description="The set this animation is a part of. Can be empty"
    )
    state: bpy.props.StringProperty(
        name="State",
        description="The state this animation plays in. States can refer to hardcoded properties or be entirely custom. You should refer to existing model_animation_graph tags for more information. Examples include: 'idle' for  animations that should play when the object is inactive, 'move-left', 'move-front' for moving. 'put-away' for an animation that should play when putting away a weapon. Must not be empty",
    )

    destination_mode: bpy.props.StringProperty(
        name="Destination Mode",
        description="The mode to put this object in when it finishes this animation. Can be empty",
    )
    destination_state: bpy.props.StringProperty(
        name="Destination State",
        description="The state to put this object in when it finishes this animation. Must not be empty",
    )

    damage_power: bpy.props.EnumProperty(
        name="Power",
        items=[
            ("hard", "Hard", ""),
            ("soft", "Soft", ""),
        ],
    )
    damage_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ("ping", "Ping", ""),
            ("kill", "Kill", ""),
        ],
    )
    damage_direction: bpy.props.EnumProperty(
        name="Direction",
        items=[
            ("front", "Front", ""),
            ("left", "Left", ""),
            ("right", "Right", ""),
            ("back", "Back", ""),
        ],
    )
    damage_region: bpy.props.EnumProperty(
        name="Region",
        items=[
            ("gut", "Gut", ""),
            ("chest", "Chest", ""),
            ("head", "Head", ""),
            ("leftarm", "Left Arm", ""),
            ("lefthand", "Left Hand", ""),
            ("leftleg", "Left Leg", ""),
            ("leftfoot", "Left Foot", ""),
            ("rightarm", "Right Arm", ""),
            ("righthand", "Right Hand", ""),
            ("rightleg", "Right Leg", ""),
            ("rightfoot", "Right Foot", ""),
        ],
    )

    variant: bpy.props.IntProperty(
        min=0,
        soft_max=3,
        name="Variant",
        description="""The variation of this animation. Variations can have different weightings
            to determine whether they play. 0 = no variation
                                    """,
    )

    custom: bpy.props.StringProperty(name="Custom")

    fp_animation: bpy.props.BoolProperty()
    
    # keep_current_pose: bpy.props.BoolProperty(
    #     name="Keep Current Pose",
    #     description="Keeps the current pose of the object instead of resetting it to the models rest pose",
    # )

    state_preset: bpy.props.EnumProperty(
        name="State Preset",
        description="Animation States which execute in specific hard-coded contexts. Item descriptions describe their use. Setting a preset will update the state field and animation type",
        items=[
            ("none", "None", ""),
            ("airborne", "airborne", "Base animation with no root movement that plays when the object is midair"),
        ]
    )
    
    create_new_actions: bpy.props.BoolProperty(
        name="Create New Actions",
        description="Creates new actions for this animation instead of using the current action (if active). Actions will be created for selected objects",
        default=True,
    )
    
    composite_mode: bpy.props.StringProperty(
        name="Mode",
        description="The mode the object must be in to use this animation. Use 'any' for all modes. Other valid inputs include but are not limited to: 'crouch' when a unit is crouching, 'combat' when a unit is in combat, 'sprint' when a unit is sprinting. Modes can also refer to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more information refer to existing model_animation_graph tags. Can be empty",
        default="combat"
    )

    composite_weapon_class: bpy.props.StringProperty(
        name="Weapon Class",
        default="any",
        description="The weapon class this unit must be holding to use this animation. Weapon class is defined per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty",
    )
    composite_state: bpy.props.EnumProperty(
        name="State",
        description="Animation state. You can rename this after creating the composite if you would like a state not listed below",
        items=[
            ("locomote", "locomote", ""),
            ("aim_locomote_up", "aim_locomote_up", ""),
            ("turn_left_composite", "turn_left_composite", ""),
            ("turn_right_composite", "turn_right_composite", ""),
            ("jump", "jump", ""),
        ]
    )
    
    composite_use_preset: bpy.props.BoolProperty(
        name="Use Preset",
        default=True,
        description="Adds default fields for the selected state"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fp_animation = utils.poll_ui(("animation",)) and bpy.context.scene.nwo.asset_animation_type == 'first_person'
        if self.fp_animation:
            self.mode = "first_person"

    def execute(self, context):
        scene_nwo = context.scene.nwo
        # Create the animation
        current_animation = None
        
        if scene_nwo.active_animation_index > -1:
            current_animation = scene_nwo.animations[scene_nwo.active_animation_index]
            utils.clear_animation(current_animation)
        
        animation = scene_nwo.animations.add()
        
        if self.copy and current_animation:
            for key, value in current_animation.items():
                animation[key] = value
            animation.name += "_copy"
            # animation.animation_renames.clear()
            for track in animation.action_tracks:
                if track.action:
                    track.action = track.action.copy()
            scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
            return {'FINISHED'}
        
        if self.animation_type == 'composite':
            self.execute_composite(animation)
            full_name = self.build_name()
            scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
        else:
            full_name = self.create_name()
            scene_nwo.active_animation_index = len(scene_nwo.animations) - 1
            if context.object:
                if self.create_new_actions:
                    for ob in context.selected_objects:
                        if not ob.animation_data:
                            ob.animation_data_create()
                        action = bpy.data.actions.new(full_name)
                        ob.animation_data.action = action
                        action_group = animation.action_tracks.add()
                        action_group.action = action
                        action_group.object = ob
                        
                else:
                    for ob in context.selected_objects:
                        if not ob.animation_data or not ob.animation_data.action:
                            continue
                        
                        action_group = animation.action_tracks.add()
                        action_group.action = ob.animation_data.action
                        action_group.object = ob
                        
            if animation.action_tracks:       
                animation.active_action_group_index = len(animation.action_tracks) - 1
        
        animation.name = full_name
        animation.frame_start = self.frame_start
        animation.frame_end = self.frame_end
        animation.animation_type = self.animation_type
        animation.animation_movement_data = self.animation_movement_data
        # animation.animation_is_pose = self.animation_is_pose
        animation.animation_space = self.animation_space

        # record the inputs from this operator
        animation.state_type = self.state_type
        animation.custom = self.custom
        animation.mode = self.mode
        animation.weapon_class = self.weapon_class
        animation.weapon_type = self.weapon_type
        animation.set = self.set
        animation.state = self.state
        animation.destination_mode = self.destination_mode
        animation.destination_state = self.destination_state
        animation.damage_power = self.damage_power
        animation.damage_type = self.damage_type
        animation.damage_direction = self.damage_direction
        animation.damage_region = self.damage_region
        animation.variant = self.variant

        animation.created_with_foundry = True
        if self.animation_type != 'composite':
            bpy.ops.nwo.set_timeline()
        self.report({"INFO"}, f"Created animation: {full_name}")
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.use_property_split = True
        col.prop(self, "copy")
        if self.copy:
            return
        
        col.label(text="Animation Format")
        row = col.row()
        row.use_property_split = True
        row.prop(self, "animation_type")
        if self.animation_type != 'world':
            row = col.row()
            row.use_property_split = True
            if self.animation_type == 'base':
                row.prop(self, 'animation_movement_data')
            # elif self.animation_type == 'overlay':
            #     row.prop(self, 'animation_is_pose')
            elif self.animation_type == 'replacement':
                row.prop(self, 'animation_space', expand=True)
        
        if self.animation_type == 'composite':
            return self.draw_composite(context)
        
        col.prop(self, "create_new_actions")
        col.prop(self, "frame_start", text="First Frame")
        col.prop(self, "frame_end", text="Last Frame")
        # col.prop(self, "keep_current_pose")
        self.draw_name(layout)

    def draw_name(self, layout, ignore_fp=False):
        if self.fp_animation and not ignore_fp:
            layout.prop(self, "state", text="State")
            layout.prop(self, "variant")
        else:
            layout.label(text="Animation Name")
            col = layout.column()
            col.use_property_split = True
            col.prop(self, "state_type", text="State Type")
            is_damage = self.state_type == "damage"
            if self.state_type == "custom":
                col.prop(self, "custom")
            else:
                col.prop(self, "mode")
                col.prop(self, "weapon_class")
                col.prop(self, "weapon_type")
                col.prop(self, "set")
                if not is_damage:
                    col.prop(self, "state", text="State")

                if self.state_type == "transition":
                    col.prop(self, "destination_mode")
                    col.prop(self, "destination_state", text="Destination State")
                elif is_damage:
                    col.prop(self, "damage_power")
                    col.prop(self, "damage_type")
                    col.prop(self, "damage_direction")
                    col.prop(self, "damage_region")

                col.prop(self, "variant")

    def create_name(self):
        bad_chars = " :_,-"
        # Strip bad chars from inputs
        mode = self.mode.strip(bad_chars)
        weapon_class = self.weapon_class.strip(bad_chars)
        weapon_type = self.weapon_type.strip(bad_chars)
        set = self.set.strip(bad_chars)
        state = self.state.strip(bad_chars)
        destination_mode = self.destination_mode.strip(bad_chars)
        destination_state = self.destination_state.strip(bad_chars)
        custom = self.custom.strip(bad_chars)

        # Get the animation name from user inputs
        if self.state_type != "custom":
            is_damage = self.state_type == "damage"
            is_transition = self.state_type == "transition"
            full_name = ""
            if mode:
                full_name = mode
            else:
                full_name = "any"

            if weapon_class:
                full_name += f" {weapon_class}"
            elif weapon_type:
                full_name += " any"

            if weapon_type:
                full_name += f" {weapon_type}"
            elif set:
                full_name += " any"

            if set:
                full_name += f" {set}"
            elif is_transition:
                full_name += " any"

            if state and not is_damage:
                full_name += f" {state}"
            elif not is_damage:
                self.report({"WARNING"}, "No state defined. Setting to idle")
                full_name += " idle"

            if is_transition:
                full_name += " 2"
                if destination_mode:
                    full_name += f" {destination_mode}"
                else:
                    full_name += " any"

                if destination_state:
                    full_name += f" {destination_state}"
                else:
                    self.report(
                        {"WARNING"}, "No destination state defined. Setting to idle"
                    )
                    full_name += " idle"

            elif is_damage:
                full_name += f" {self.damage_power[0]}"
                full_name += f"_{self.damage_type}"
                full_name += f" {self.damage_direction}"
                full_name += f" {self.damage_region}"

            if self.variant:
                full_name += f" var{self.variant}"

        else:
            if custom:
                full_name = custom
            else:
                self.report({"WARNING"}, "Animation name empty. Setting to idle")
                full_name = "idle"

        return full_name.lower().strip(bad_chars)
    
    def build_name(self):
        name = ""
        name += self.composite_mode.strip() if self.composite_mode.strip() else "any"
        name += " "
        name += self.composite_weapon_class.strip() if self.composite_weapon_class.strip() else "any"
        name += " "
        name += self.composite_state
        return name

    def execute_composite(self, animation):
        
        if self.composite_use_preset:
            match self.composite_state:
                case 'locomote':
                    if self.composite_mode == 'sprint':
                        self.preset_sprint(animation)
                    else:
                        self.preset_locomote(animation)
                case 'aim_locomote_up':
                    if self.composite_mode == 'crouch':
                        self.preset_crouch_aim(animation)
                    else:
                        self.preset_aim_locomote_up(animation)
                case 'turn_left_composite':
                    self.preset_turn_left(animation)
                case 'turn_right_composite':
                    self.preset_turn_right(animation)
                case 'jump':
                    self.preset_jump(animation)
            
        # context.area.tag_redraw()
        # return {'FINISHED'}
    
    def draw_composite(self, context):
        layout = self.layout
        layout.label(text="Animation Name")
        col = layout.column()
        col.use_property_split = True
        col.prop(self, "composite_mode")
        col.prop(self, "composite_weapon_class")
        col.prop(self, "composite_state", text="State")
        col.prop(self, "composite_use_preset")
        
    def preset_jump(self, composite):
        composite.timing_source = f"{self.composite_mode} {self.composite_weapon_class} jump_forward_long"
        
        vertical_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        vertical_blend_axis.name = "vertical"
        vertical_blend_axis.adjusted = 'on_start'
        
        horizontal_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        
        horizontal_blend_axis.name = "horizontal"
        horizontal_blend_axis.adjusted = 'on_start'
        
        jump_phase_set = cast(NWO_AnimationPhaseSetsItems, horizontal_blend_axis.phase_sets.add())
        jump_phase_set.name = "jump"
        jump_phase_set.key_primary_keyframe = True
        jump_phase_set.key_tertiary_keyframe = True
        
        jump_phase_set.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_forward_long"
        jump_phase_set.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_forward_short"
        jump_phase_set.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_up_long"
        jump_phase_set.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_up_short"
        jump_phase_set.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_down_long"
        jump_phase_set.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_down_short"
        
        horizontal_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_down_forward"
        horizontal_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_up_forward"
        horizontal_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_short"
        horizontal_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_up"
        horizontal_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} jump_down"
        
        
    def preset_turn_left(self, composite):
        composite.timing_source = f"{self.composite_mode} {self.composite_weapon_class} turn_left_90"
        
        turn_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        turn_blend_axis.name = "turn_angle"
        turn_blend_axis.animation_source_bounds_manual = True
        turn_blend_axis.animation_source_bounds = 0, 180
        turn_blend_axis.animation_source_limit = 0
        turn_blend_axis.runtime_source_bounds_manual = True
        turn_blend_axis.runtime_source_bounds = 0, 180
        turn_blend_axis.runtime_source_clamped = False
        
        turn_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} turn_left_0"
        turn_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} turn_left_90"
        turn_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} turn_left_180"
        
    def preset_turn_right(self, composite):
        composite.timing_source = f"{self.composite_mode} {self.composite_weapon_class} turn_right_90"
        
        turn_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        turn_blend_axis.name = "turn_angle"
        turn_blend_axis.animation_source_bounds_manual = True
        turn_blend_axis.animation_source_bounds = 0, 180
        turn_blend_axis.animation_source_limit = 0
        turn_blend_axis.runtime_source_bounds_manual = True
        turn_blend_axis.runtime_source_bounds = 0, 180
        turn_blend_axis.runtime_source_clamped = False
        
        turn_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} turn_right_0"
        turn_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} turn_right_90"
        turn_blend_axis.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} turn_right_180"
        
    def preset_crouch_aim(self, composite):
        composite.timing_source = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_front_up"
        composite.overlay = True
        
        angle_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        angle_blend_axis.name = "movement_angles"
        angle_blend_axis.animation_source_bounds_manual = True
        angle_blend_axis.animation_source_bounds = 0, 360
        angle_blend_axis.animation_source_limit = 90
        angle_blend_axis.runtime_source_bounds_manual = True
        angle_blend_axis.runtime_source_bounds = 0, 360
        angle_blend_axis.runtime_source_clamped = False
        
        run_front_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_front_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_front_up"
        run_front_up.manual_blend_axis_0 = True
        run_front_up.blend_axis_0 = 0
        run_front_up.manual_blend_axis_1 = True
        run_front_up.blend_axis_1 = 0.9
        
        run_left_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_left_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_left_up"
        run_left_up.manual_blend_axis_0 = True
        run_left_up.blend_axis_0 = 90
        run_left_up.manual_blend_axis_1 = True
        run_left_up.blend_axis_1 = 0.9
    
        run_back_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_back_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_back_up"
        run_back_up.manual_blend_axis_0 = True
        run_back_up.blend_axis_0 = 180
        run_back_up.manual_blend_axis_1 = True
        run_back_up.blend_axis_1 = 0.9
        
        run_right_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_right_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_right_up"
        run_right_up.manual_blend_axis_0 = True
        run_right_up.blend_axis_0 = 270
        run_right_up.manual_blend_axis_1 = True
        run_right_up.blend_axis_1 = 0.9
        
        run_360_up = cast(NWO_AnimationLeavesItems, angle_blend_axis.leaves.add())
        run_360_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_front_up"
        run_360_up.manual_blend_axis_0 = True
        run_360_up.blend_axis_0 = 360
        run_360_up.manual_blend_axis_1 = True
        run_360_up.blend_axis_1 = 0.9
        
    def preset_aim_locomote_up(self, composite):
        composite.timing_source = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_front_up"
        composite.overlay = True
        
        angle_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        angle_blend_axis.name = "movement_angles"
        angle_blend_axis.animation_source_bounds_manual = True
        angle_blend_axis.animation_source_bounds = 0, 360
        angle_blend_axis.animation_source_limit = 90
        angle_blend_axis.runtime_source_bounds_manual = True
        angle_blend_axis.runtime_source_bounds = 0, 360
        angle_blend_axis.runtime_source_clamped = False
        
        speed_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        speed_blend_axis.name = "movement_speed"
        speed_blend_axis.animation_source_bounds_manual = True
        speed_blend_axis.animation_source_bounds = 0, 1
        speed_blend_axis.runtime_source_bounds_manual = True
        speed_blend_axis.runtime_source_bounds = 0, 1
        speed_blend_axis.runtime_source_clamped = True
        
        walk_front_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_front_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_walk_front_up"
        walk_front_up.manual_blend_axis_0 = True
        walk_front_up.blend_axis_0 = 0
        walk_front_up.manual_blend_axis_1 = True
        walk_front_up.blend_axis_1 = 0.5
        
        run_front_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_front_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_front_up"
        run_front_up.manual_blend_axis_0 = True
        run_front_up.blend_axis_0 = 0
        run_front_up.manual_blend_axis_1 = True
        run_front_up.blend_axis_1 = 0.9
        
        walk_left_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_left_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_walk_left_up"
        walk_left_up.manual_blend_axis_0 = True
        walk_left_up.blend_axis_0 = 90
        walk_left_up.manual_blend_axis_1 = True
        walk_left_up.blend_axis_1 = 0.5
        
        run_left_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_left_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_left_up"
        run_left_up.manual_blend_axis_0 = True
        run_left_up.blend_axis_0 = 90
        run_left_up.manual_blend_axis_1 = True
        run_left_up.blend_axis_1 = 0.9
        
        walk_back_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_back_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_walk_back_up"
        walk_back_up.manual_blend_axis_0 = True
        walk_back_up.blend_axis_0 = 180
        walk_back_up.manual_blend_axis_1 = True
        walk_back_up.blend_axis_1 = 0.5
        
        run_back_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_back_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_back_up"
        run_back_up.manual_blend_axis_0 = True
        run_back_up.blend_axis_0 = 180
        run_back_up.manual_blend_axis_1 = True
        run_back_up.blend_axis_1 = 0.9
        
        walk_right_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_right_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_walk_right_up"
        walk_right_up.manual_blend_axis_0 = True
        walk_right_up.blend_axis_0 = 270
        walk_right_up.manual_blend_axis_1 = True
        walk_right_up.blend_axis_1 = 0.5
        
        run_right_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_right_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_right_up"
        run_right_up.manual_blend_axis_0 = True
        run_right_up.blend_axis_0 = 270
        run_right_up.manual_blend_axis_1 = True
        run_right_up.blend_axis_1 = 0.9
        
        walk_360_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        walk_360_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_walk_front_up"
        walk_360_up.manual_blend_axis_0 = True
        walk_360_up.blend_axis_0 = 360
        walk_360_up.manual_blend_axis_1 = True
        walk_360_up.blend_axis_1 = 0.5
        
        run_360_up = cast(NWO_AnimationLeavesItems, speed_blend_axis.leaves.add())
        run_360_up.animation = f"{self.composite_mode} {self.composite_weapon_class} aim_locomote_run_front_up"
        run_360_up.manual_blend_axis_0 = True
        run_360_up.blend_axis_0 = 360
        run_360_up.manual_blend_axis_1 = True
        run_360_up.blend_axis_1 = 0.9
        
    def preset_sprint(self, composite):
        composite.timing_source = f"sprint {self.composite_weapon_class} move_front_fast"
        
        speed_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        speed_blend_axis.name = "movement_speed"
        speed_blend_axis.animation_source_bounds_manual = True
        speed_blend_axis.animation_source_bounds = 0, 1
        speed_blend_axis.runtime_source_bounds_manual = True
        speed_blend_axis.runtime_source_bounds = 0, 1
        speed_blend_axis.runtime_source_clamped = True
        
        speed_blend_axis.leaves.add().animation = f"sprint {self.composite_weapon_class} move_front_fast"
        speed_blend_axis.leaves.add().animation = f"sprint {self.composite_weapon_class} move_front_fast"
        
    def preset_locomote(self, composite):
        composite.timing_source = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_front"
        angle_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        angle_blend_axis.name = "movement_angles"
        angle_blend_axis.animation_source_bounds_manual = True
        angle_blend_axis.animation_source_bounds = 0, 360
        angle_blend_axis.animation_source_limit = 45
        angle_blend_axis.runtime_source_bounds_manual = True
        angle_blend_axis.runtime_source_bounds = 0, 360
        angle_blend_axis.runtime_source_clamped = False
        
        # dead_zone_0 = cast(NWO_AnimationDeadZonesItems, angle_blend_axis.dead_zones.add())
        # dead_zone_0.name = "deadzone0"
        # dead_zone_0.bounds = 45, 90
        # dead_zone_0.rate = 90
        
        # dead_zone_1 = cast(NWO_AnimationDeadZonesItems, angle_blend_axis.dead_zones.add())
        # dead_zone_1.name = "deadzone1"
        # dead_zone_1.bounds = 225, 270
        # dead_zone_1.rate = 90
        
        speed_blend_axis = cast(NWO_AnimationBlendAxisItems, composite.blend_axis.add())
        speed_blend_axis.name = "movement_speed"
        speed_blend_axis.runtime_source_bounds_manual = True
        speed_blend_axis.runtime_source_bounds = 0, 1
        speed_blend_axis.runtime_source_clamped = True
        
        group_0 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_0.name = "Front"
        group_0.manual_blend_axis_0 = True
        group_0.blend_axis_0 = 0
        group_0.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_0.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walkslow_front"
        group_0.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_front"
        group_0.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_front"
        
        group_45 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_45.name = "Front Left"
        group_45.manual_blend_axis_0 = True
        group_45.blend_axis_0 = 45
        group_45.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_45.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_frontleft"
        group_45.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_frontleft"
        
        group_90 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_90.name = "Left"
        group_90.manual_blend_axis_0 = True
        group_90.blend_axis_0 = 90
        group_90.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_90.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_left"
        group_90.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_left"
        
        group_135 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_135.name = "Back Left"
        group_135.manual_blend_axis_0 = True
        group_135.blend_axis_0 = 135
        group_135.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_135.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_backleft"
        group_135.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_backleft"
        
        group_180 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_180.name = "Back"
        group_180.manual_blend_axis_0 = True
        group_180.blend_axis_0 = 180
        group_180.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_180.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_back"
        group_180.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_back"
        
        group_225 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_225.name = "Back Right"
        group_225.manual_blend_axis_0 = True
        group_225.blend_axis_0 = 225
        group_225.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_225.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_backright"
        group_225.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_backright"
        
        group_270 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_270.name = "Right"
        group_270.manual_blend_axis_0 = True
        group_270.blend_axis_0 = 270
        group_270.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_270.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_right"
        group_270.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_right"
        
        group_315 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_315.name = "Front Right"
        group_315.manual_blend_axis_0 = True
        group_315.blend_axis_0 = 315
        group_315.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_315.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_frontright"
        group_315.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_frontright"
        
        group_360 = cast(NWO_AnimationGroupItems, speed_blend_axis.groups.add())
        group_360.name = "360 Front"
        group_360.manual_blend_axis_0 = True
        group_360.blend_axis_0 = 360
        group_360.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_inplace"
        group_360.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walkslow_front"
        group_360.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_walk_front"
        group_360.leaves.add().animation = f"{self.composite_mode} {self.composite_weapon_class} locomote_run_front"


class NWO_OT_List_Add_Animation_Rename(bpy.types.Operator):
    bl_label = "New Animation Rename"
    bl_idname = "nwo.animation_rename_add"
    bl_description = "Creates a new Halo Animation Rename"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1
    
    def execute(self, context):
        # full_name = self.create_name()
        # animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        # if full_name == animation.name:
        #     self.report(
        #         {"WARNING"},
        #         f"Rename entry not created. Rename cannot match animation name",
        #     )
        #     return {"CANCELLED"}

        # Create the rename
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        rename = animation.animation_renames.add()
        animation.active_animation_rename_index = len(animation.animation_renames) - 1
        rename.name = animation.name
        context.area.tag_redraw()

        return {"FINISHED"}

class NWO_OT_List_Remove_Animation_Rename(bpy.types.Operator):
    """Remove an Item from the UIList"""

    bl_idname = "nwo.animation_rename_remove"
    bl_label = "Remove"
    bl_description = "Remove an animation rename from the list"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1:
            animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
            return len(animation.animation_renames) > 0
        
        return False

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        animation.animation_renames.remove(animation.active_animation_rename_index)
        if animation.active_animation_rename_index > len(animation.animation_renames) - 1:
            animation.active_animation_rename_index += -1
        return {"FINISHED"}
    
class NWO_OT_AnimationRenameMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_rename_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        table = animation.animation_renames
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = animation.active_animation_rename_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        animation.active_animation_rename_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}


class NWO_UL_AnimationRename(bpy.types.UIList):
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        layout.prop(item, "name", text="", emboss=False, icon_value=get_icon_id("animation_rename"))
        
class NWO_OT_SetActionTracksActive(bpy.types.Operator):
    bl_label = "Make Tracks Active"
    bl_idname = "nwo.action_tracks_set_active"
    bl_description = "Sets all actions in the current action track list to be active on their respective objects"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        if context.scene.nwo.animations and context.scene.nwo.active_animation_index >= 0:
            return context.scene.nwo.animations[context.scene.nwo.active_animation_index].action_tracks
        return False
    
    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        for track in animation.action_tracks:
            if track.object and track.action:
                if track.is_shape_key_action:
                    if track.object.type == 'MESH' and track.object.data.shape_keys and track.object.data.shape_keys.animation_data:
                        track.object.data.shape_keys.animation_data.action = track.action
                else:
                    if track.object.animation_data:
                        track.object.animation_data.action = track.action
                        
        return {"FINISHED"}
        
class NWO_OT_AddActionTrack(bpy.types.Operator):
    bl_label = "New Action Track"
    bl_idname = "nwo.action_track_add"
    bl_description = "Adds new action tracks based on current object selection and their active actions"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        if not context.scene.nwo.animations or context.scene.nwo.active_animation_index == -1:
            return False
        ob = context.object
        if not ob:
            return False
        
        has_action = context.object.animation_data and context.object.animation_data.action
        if has_action:
            return True
        
        is_mesh = context.object and context.object.type == 'MESH'
        if is_mesh:
            return context.object.data.shape_keys and context.object.data.shape_keys.animation_data and context.object.data.shape_keys.animation_data.action
        else:
            return False
    
    def execute(self, context):
        if not context.selected_objects:
            self.report({'WARNING'}, "No active object, cannot add action track")
            return {'CANCELLED'}
        
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        
        for ob in context.selected_objects:
            self.add_track(animation, ob)
            
        context.area.tag_redraw()
        return {"FINISHED"}

    def add_track(self, animation, ob):
        if ob.animation_data is not None and ob.animation_data.action is not None:
            for track in animation.action_tracks:
                if track.action == ob.animation_data.action:
                    return
            group = animation.action_tracks.add()
            group.object = ob
            group.action = ob.animation_data.action
            # if group.object.animation_data.use_nla and group.object.animation_data.nla_tracks and group.object.animation_data.nla_tracks.active:
            #     group.nla_uuid = str(uuid4())
            #     group.object.animation_data.nla_tracks.active
            animation.active_action_group_index = len(animation.action_tracks) - 1
        else:
            return self.report({'WARNING'}, f"No active action for object [{ob.name}], cannot add action track")
        if ob.type == 'MESH' and ob.data.shape_keys and ob.data.shape_keys.animation_data and ob.data.shape_keys.animation_data.action:
            for track in animation.action_tracks:
                if track.action == ob.data.shape_keys.animation_data.action:
                    return
            group = animation.action_tracks.add()
            group.object = ob
            group.action = ob.data.shape_keys.animation_data.action
            group.is_shape_key_action = True
        

class NWO_OT_RemoveActionTrack(bpy.types.Operator):
    """Remove an Item from the UIList"""

    bl_idname = "nwo.action_track_remove"
    bl_label = "Remove Action Track"
    bl_description = "Remove an action track from the list"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.scene.nwo.animations and context.scene.nwo.active_animation_index >= 0:
            return context.scene.nwo.animations[context.scene.nwo.active_animation_index].action_tracks
        return False

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        animation.action_tracks.remove(animation.active_action_group_index)
        if animation.active_action_group_index > len(animation.action_tracks) - 1:
            animation.active_action_group_index += -1
        return {"FINISHED"}
    
class NWO_OT_ActionTrackMove(bpy.types.Operator):
    bl_label = "Move Action Track"
    bl_idname = "nwo.action_track_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()
    
    @classmethod
    def poll(cls, context):
        if context.scene.nwo.animations and context.scene.nwo.active_animation_index >= 0:
            return context.scene.nwo.animations[context.scene.nwo.active_animation_index].action_tracks
        return False

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        table = animation.action_tracks
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = animation.active_action_group_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        animation.active_action_group_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}


class NWO_UL_ActionTrack(bpy.types.UIList):
    def draw_item(
        self,
        context,
        layout,
        data,
        item,
        icon,
        active_data,
        active_propname,
        index,
    ):
        name = ""
        icon = 'SHAPEKEY_DATA' if item.is_shape_key_action else 'ACTION'
        if item.object:
            name += f"{item.object.name} -> "
            if item.action:
                name += item.action.name
            else:
                name += "NONE"
                icon = 'WARNING'
                
        layout.label(text=name, icon=icon)

class NWO_UL_AnimationList(bpy.types.UIList):
    
    use_filter_sort_frame: bpy.props.BoolProperty(
        name="Sort By Frame Count",
        default=False,
    )
    
    use_filter_event: bpy.props.BoolProperty(
        name="Has Events",
        default=False,
    )
    
    use_filter_rename: bpy.props.BoolProperty(
        name="Has Renames",
        default=False,
    )
    
    use_filter_base_none: bpy.props.BoolProperty(
        name="Base None",
        default=True,
    )
    use_filter_base_xy: bpy.props.BoolProperty(
        name="Base Horizonta",
        default=True,
    )
    use_filter_base_xyyaw: bpy.props.BoolProperty(
        name="Base Horizontal and Yaw",
        default=True,
    )
    use_filter_base_xyzyaw: bpy.props.BoolProperty(
        name="Base Full & Yaw",
        default=True,
    )
    use_filter_base_full: bpy.props.BoolProperty(
        name="Base Full",
        default=True,
    )
    use_filter_world: bpy.props.BoolProperty(
        name="World",
        default=True,
    )
    use_filter_overlay: bpy.props.BoolProperty(
        name="Overlay",
        default=True,
    )
    use_filter_replacement_local: bpy.props.BoolProperty(
        name="Replacement Local",
        default=True,
    )
    use_filter_replacement_object: bpy.props.BoolProperty(
        name="Replacement Object",
        default=True,
    )
    use_filter_composite: bpy.props.BoolProperty(
        name="Composite",
        default=True,
    )
    use_filter_export: bpy.props.BoolProperty(
        name="Export Enabled Only",
        default=False,
    )

    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index, flt_flag):
        match item.animation_type:
            case 'base':
                if item.animation_movement_data == 'none':
                    icon_str = "anim_base"
                else:
                    icon_str = f"anim_base_{item.animation_movement_data}"
            case 'overlay':
                icon_str = "anim_overlay"
            case 'replacement':
                icon_str = f'anim_replacement_{item.animation_space}'
            case 'world':
                icon_str = 'anim_world'
            case 'composite':
                icon_str = 'anim_composite'
            
        layout.prop(item, "name", text="", emboss=False, icon_value=get_icon_id(icon_str))
        layout.prop(item, 'export_this', text="", icon='CHECKBOX_HLT' if item.export_this else 'CHECKBOX_DEHLT', emboss=False)
        
    def draw_filter(self, context, layout):
        if self.use_filter_show:
            row = layout.row(align=True)
            row.prop(self, "filter_name", text="")
            row.prop(self, "use_filter_sort_alpha", text="")
            row.prop(self, "use_filter_invert", text="", icon='ARROW_LEFTRIGHT')
            row.separator()
            row.prop(self, "use_filter_sort_frame", text="", icon='KEYFRAME_HLT')
            row.separator()
            row.prop(self, "use_filter_event", text="", icon_value=get_icon_id("animation_event"))
            row.prop(self, "use_filter_rename", text="", icon_value=get_icon_id("animation_rename"))
            row.prop(self, "use_filter_export", text="", icon='CHECKBOX_HLT')
            row.separator()
            row.prop(self, "use_filter_sort_reverse", text="", icon="SORT_ASC")
            layout.separator()
            row = layout.row(align=True, heading="Types Filter")
            row.prop(self, "use_filter_base_none", text="", icon_value=get_icon_id("anim_base"))
            row.prop(self, "use_filter_base_xy", text="", icon_value=get_icon_id("anim_base_xy"))
            row.prop(self, "use_filter_base_xyyaw", text="", icon_value=get_icon_id("anim_base_xyyaw"))
            row.prop(self, "use_filter_base_xyzyaw", text="", icon_value=get_icon_id("anim_base_xyzyaw"))
            row.prop(self, "use_filter_base_full", text="", icon_value=get_icon_id("anim_base_full"))
            row.prop(self, "use_filter_world", text="", icon_value=get_icon_id("anim_world"))
            row.separator()
            row.prop(self, "use_filter_overlay", text="", icon_value=get_icon_id("anim_overlay"))
            row.prop(self, "use_filter_replacement_local", text="", icon_value=get_icon_id("anim_replacement_local"))
            row.prop(self, "use_filter_replacement_object", text="", icon_value=get_icon_id("anim_replacement_object"))
            row.separator()
            row.prop(self, "use_filter_composite", text="", icon_value=get_icon_id("anim_composite"))
            row.separator()

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        bit = self.bitflag_filter_item

        if self.filter_name:
            name_flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name, bit, items, "name", reverse=False
            )
            visible_by_name = [(f & bit) != 0 for f in name_flags]
        else:
            visible_by_name = [True] * len(items)

        visible_by_custom = [True] * len(items)
        for i, item in enumerate(items):
            ok = True
            if self.use_filter_event:
                ok = ok and bool(item.animation_events)
            if self.use_filter_rename:
                ok = ok and bool(item.animation_renames)
            if self.use_filter_export:
                ok = ok and item.export_this
            visible_by_custom[i] = ok

        visible_by_type = [True] * len(items)
        for i, item in enumerate(items):
            anim_type = item.animation_type
            move_data = item.animation_movement_data
            space = item.animation_space

            ok = False

            if anim_type == "base":
                match move_data:
                    case "none":
                        ok = self.use_filter_base_none
                    case "xy":
                        ok = self.use_filter_base_xy
                    case "xyyaw":
                        ok = self.use_filter_base_xyyaw
                    case "xyzyaw":
                        ok = self.use_filter_base_xyzyaw
                    case "full":
                        ok = self.use_filter_base_full
            elif anim_type == "world":
                ok = self.use_filter_world
            elif anim_type == "overlay":
                ok = self.use_filter_overlay
            elif anim_type == "replacement":
                if space == "local":
                    ok = self.use_filter_replacement_local
                elif space == "object":
                    ok = self.use_filter_replacement_object
            elif anim_type == "composite":
                ok = self.use_filter_composite

            visible_by_type[i] = ok

        flt_flags = [0] * len(items)
        for i in range(len(items)):
            final_visible = visible_by_name[i] and visible_by_custom[i] and visible_by_type[i]

            if self.use_filter_invert:
                final_visible = not final_visible

            base_flag = name_flags[i] if self.filter_name else bit
            base_flag &= ~bit
            if final_visible:
                base_flag |= bit

            flt_flags[i] = base_flag

        order = []
        if self.use_filter_sort_frame:
            sort = [(idx, item.frame_end - item.frame_start) for idx, item in enumerate(items)]
            order = bpy.types.UI_UL_list.sort_items_helper(sort, key=lambda i: i[1], reverse=True)
            return flt_flags, order
        elif self.use_filter_sort_alpha:
            sort = [(idx, item.name.lower()) for idx, item in enumerate(items)]
            order = bpy.types.UI_UL_list.sort_items_helper(sort, key=lambda i: i[1])

        return flt_flags, order
    
class NWO_OT_AnimationEventSetFrame(bpy.types.Operator):
    bl_idname = "nwo.animation_event_set_frame"
    bl_label = "Set Event Frame"
    bl_description = "Sets the event frame to the current timeline frame"
    bl_options = {"UNDO"}
    
    prop_to_set: bpy.props.StringProperty(options={'SKIP_SAVE', 'HIDDEN'})
    
    @classmethod
    def poll(cls, context) -> bool:
        return context.scene.nwo.active_animation_index > -1

    def execute(self, context):
        if not self.prop_to_set:
            print("Operator requires prop_to_set specified")
            return {"CANCELLED"}
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        if not animation.animation_events:
            return {"CANCELLED"}
        event = animation.animation_events[animation.active_animation_event_index]
        if not event:
            self.report({"WARNING"}, "No active event")
            return {"CANCELLED"}
        
        current_frame = context.scene.frame_current
        setattr(event, self.prop_to_set, int(current_frame))
        return {"FINISHED"}
    
class NWO_OT_AnimationFramesSyncToKeyFrames(bpy.types.Operator):
    bl_idname = "nwo.animation_frames_sync_to_keyframes"
    bl_label = "Sync Frame Range with Keyframes"
    bl_description = "Sets the frame range for this animation to the length of the keyframes"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.active_animation_index > -1

    _timer = None
    _current_animation_index = -1
    
    def update_frame_range_from_keyframes(self, context: bpy.types.Context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        old_start = animation.frame_start
        old_end = animation.frame_end
        actions = {track.action for track in animation.action_tracks if track.action is not None}
        if not actions:
            self.report({'WARNING'}, "Cannot update frame range, animation has no action tracks")
        frames = set()
        for action in actions:
            for fcurve in action.fcurves:
                for kfp in fcurve.keyframe_points:
                    frames.add(kfp.co[0])
                
        if len(frames) > 1:
            animation.frame_start = int(min(*frames))
            animation.frame_end = int(max(*frames))
        
        if old_start != animation.frame_start or old_end != animation.frame_end:
            bpy.ops.nwo.set_timeline()

    def modal(self, context, event):
        if context.scene.nwo.active_animation_index != self._current_animation_index or context.scene.nwo.export_in_progress or not context.scene.nwo.keyframe_sync_active:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            self.update_frame_range_from_keyframes(context)

        return {'PASS_THROUGH'}

    def execute(self, context):
        if context.scene.nwo.keyframe_sync_active:
            context.scene.nwo.keyframe_sync_active = False
            return {"CANCELLED"}
        context.scene.nwo.keyframe_sync_active = True
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        self._current_animation_index = context.scene.nwo.active_animation_index
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.scene.nwo.keyframe_sync_active = False
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        
class NWO_OT_List_Add_Animation_Event(bpy.types.Operator):
    """Add an Item to the UIList"""

    bl_idname = "nwo.animation_event_list_add"
    bl_label = "Add"
    bl_description = "Add a new animation event"
    filename_ext = ""
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        event = animation.animation_events.add()
        animation.active_animation_event_index = len(animation.animation_events) - 1
        event.frame_frame = context.scene.frame_current
        event.event_id = random.randint(0, 2147483647)
        event.name = f"event_{len(animation.animation_events)}"

        context.area.tag_redraw()

        return {"FINISHED"}


class NWO_OT_List_Remove_Animation_Event(bpy.types.Operator):
    """Remove an Item from the UIList"""

    bl_idname = "nwo.animation_event_list_remove"
    bl_label = "Remove"
    bl_description = "Remove an animation event from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1 and len(context.scene.nwo.animations[context.scene.nwo.active_animation_index].animation_events) > 0

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        index = animation.active_animation_event_index
        animation.animation_events.remove(index)
        if animation.active_animation_event_index > len(animation.animation_events) - 1:
            animation.active_animation_event_index += -1
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_AnimationEventMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_event_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        table = animation.animation_events
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = animation.active_animation_event_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        animation.active_animation_event_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
    
class NWO_OT_SingleList_Add_Animation_Event(bpy.types.Operator):
    """Add an Item to the UIList"""

    bl_idname = "nwo.single_animation_event_list_add"
    bl_label = "Add"
    bl_description = "Add a new animation event"
    filename_ext = ""
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene

    def execute(self, context):
        animation = context.scene.nwo
        event = animation.animation_events.add()
        animation.active_animation_event_index = len(animation.animation_events) - 1
        event.frame_frame = context.scene.frame_current
        event.event_id = random.randint(0, 2147483647)
        event.name = f"event_{len(animation.animation_events)}"

        context.area.tag_redraw()

        return {"FINISHED"}


class NWO_OT_SingleList_Remove_Animation_Event(bpy.types.Operator):
    """Remove an Item from the UIList"""

    bl_idname = "nwo.single_animation_event_list_remove"
    bl_label = "Remove"
    bl_description = "Remove an animation event from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene and context.scene.nwo.animation_events

    def execute(self, context):
        animation = context.scene.nwo
        index = animation.active_animation_event_index
        animation.animation_events.remove(index)
        if animation.active_animation_event_index > len(animation.animation_events) - 1:
            animation.active_animation_event_index += -1
        context.area.tag_redraw()
        return {"FINISHED"}
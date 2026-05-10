"""Animation sub-panel specific operators"""

from collections import defaultdict
from pathlib import Path
import random
from typing import cast
import bpy
from mathutils import Matrix

from ...managed_blam.animation import AnimationTag

from ...props.scene import NWO_AnimationBlendAxisItems, NWO_AnimationGroupItems, NWO_AnimationLeavesItems, NWO_AnimationPhaseSetsItems, NWO_AnimationPropertiesGroup
from ... import utils
from ...icons import get_icon_id

pose_hints = 'aim', 'look', 'acc', 'steer', 'pain'
IK_PREVIEW_CONSTRAINT_NAME = "Foundry IK Preview"


def _get_animation_event_owner(scene_nwo, single_animation: bool):
    if single_animation:
        return scene_nwo

    if not scene_nwo.animations or scene_nwo.active_animation_index < 0:
        return None

    if scene_nwo.active_animation_index >= len(scene_nwo.animations):
        return None

    return scene_nwo.animations[scene_nwo.active_animation_index]


def _get_active_animation_event(scene_nwo, single_animation: bool):
    owner = _get_animation_event_owner(scene_nwo, single_animation)
    if owner is None or not owner.animation_events:
        return owner, None

    event_index = owner.active_animation_event_index
    if event_index < 0 or event_index >= len(owner.animation_events):
        return owner, None

    return owner, owner.animation_events[event_index]


def _find_animation_armature(context: bpy.types.Context, animation, single_animation: bool) -> bpy.types.Object | None:
    if not single_animation and animation is not None:
        for track in animation.action_tracks:
            if track.object and track.object.type == 'ARMATURE':
                return track.object

    rig = utils.get_rig_prioritize_active(context)
    if rig is not None:
        return rig

    if context.object is not None:
        if context.object.type == 'ARMATURE':
            return context.object
        return utils.ultimate_armature_parent(context.object)

    return None


def _get_ik_chain(scene_nwo, chain_name: str):
    if not chain_name or chain_name == "none":
        return None

    for chain in scene_nwo.ik_chains:
        if chain.name == chain_name:
            return chain

    return None


def _ik_chain_count(armature: bpy.types.Object, start_node: str, effector_node: str) -> int:
    effector_bone = armature.pose.bones.get(effector_node)
    if effector_bone is None:
        return 0

    chain_count = 0
    current_bone = effector_bone
    while current_bone is not None:
        chain_count += 1
        if current_bone.name == start_node:
            return chain_count
        current_bone = current_bone.parent

    return 0


def _iter_ik_preview_constraints(armature: bpy.types.Object):
    for pose_bone in armature.pose.bones:
        for constraint in pose_bone.constraints:
            if constraint.type == 'IK' and constraint.name.startswith(IK_PREVIEW_CONSTRAINT_NAME):
                yield pose_bone, constraint


def _clear_ik_preview_constraints(armature: bpy.types.Object) -> int:
    removed = 0
    for pose_bone, constraint in list(_iter_ik_preview_constraints(armature)):
        try:
            constraint.driver_remove("influence")
        except (TypeError, ValueError, RuntimeError):
            pass
        pose_bone.constraints.remove(constraint)
        removed += 1

    return removed


def _ik_preview_constraint_name(chain_name: str) -> str:
    return f"{IK_PREVIEW_CONSTRAINT_NAME} [{chain_name}]"


def _ik_preview_target_name(armature: bpy.types.Object, chain_name: str) -> str:
    return f"{armature.name}_ik_preview_target_{chain_name}"


def _clear_ik_preview_targets(armature: bpy.types.Object) -> int:
    removed = 0
    prefix = f"{armature.name}_ik_preview_target_"
    for obj in [ob for ob in bpy.data.objects if ob.name.startswith(prefix)]:
        bpy.data.objects.remove(obj, do_unlink=True)
        removed += 1

    return removed


def _copy_property_group(source, target):
    for prop in source.bl_rna.properties:
        identifier = prop.identifier
        if identifier == "rna_type" or prop.is_readonly:
            continue

        try:
            if prop.type == 'COLLECTION':
                _copy_property_collection(getattr(source, identifier), getattr(target, identifier))
            else:
                setattr(target, identifier, getattr(source, identifier))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            pass


def _copy_property_collection(source, target):
    target.clear()
    for source_item in source:
        target_item = target.add()
        _copy_property_group(source_item, target_item)


def _action_slot_identifier(action: bpy.types.Action) -> str:
    try:
        slots = action.slots
    except AttributeError:
        return ""

    if not slots:
        return ""

    if slots.active:
        return slots.active.identifier

    return slots[0].identifier


def _set_animation_data_action(animation_data, action: bpy.types.Action, slot_id: str):
    if animation_data is None:
        return

    if slot_id:
        try:
            animation_data.last_slot_identifier = slot_id
        except (AttributeError, TypeError, ValueError):
            pass

    animation_data.action = action


def _set_animation_tracks_active(animation, object_map: dict[bpy.types.Object, bpy.types.Object] | None = None):
    if object_map is None:
        object_map = {}

    for track in animation.action_tracks:
        if track.object is None or track.action is None:
            continue

        ob = object_map.get(track.object, track.object)
        slot_id = _action_slot_identifier(track.action)
        if track.is_shape_key_action:
            if ob.type != 'MESH' or ob.data.shape_keys is None:
                continue

            shape_keys = ob.data.shape_keys
            _set_animation_data_action(shape_keys.animation_data_create(), track.action, slot_id)
        else:
            _set_animation_data_action(ob.animation_data_create(), track.action, slot_id)
            if ob.data is not None and ob.data.animation_data is not None:
                _set_animation_data_action(ob.data.animation_data, track.action, slot_id)


def _snapshot_animation_owner(owner):
    animation_data = owner.animation_data
    had_animation_data = animation_data is not None
    action = animation_data.action if had_animation_data else None
    use_nla = animation_data.use_nla if had_animation_data else False
    slot_id = ""
    if had_animation_data:
        try:
            slot_id = animation_data.last_slot_identifier
        except AttributeError:
            pass

    return owner, had_animation_data, action, slot_id, use_nla


def _affected_animation_owners(animations):
    owners = set()
    for animation in animations:
        for track in animation.action_tracks:
            if track.object is None:
                continue

            owners.add(track.object)
            if track.object.data is not None:
                owners.add(track.object.data)
            if track.object.type == 'MESH' and track.object.data.shape_keys is not None:
                owners.add(track.object.data.shape_keys)

    return owners


def _snapshot_animation_state(animations):
    return [_snapshot_animation_owner(owner) for owner in _affected_animation_owners(animations)]


def _restore_animation_state(snapshots):
    for owner, had_animation_data, action, slot_id, use_nla in snapshots:
        if not had_animation_data:
            if owner.animation_data is not None:
                owner.animation_data_clear()
            continue

        animation_data = owner.animation_data_create()
        _set_animation_data_action(animation_data, action, slot_id)
        animation_data.use_nla = use_nla


def _animation_action_datablocks(animations, object_map: dict[bpy.types.Object, bpy.types.Object] | None = None) -> set[bpy.types.ID]:
    if object_map is None:
        object_map = {}

    datablocks = set()
    for animation in animations:
        for track in animation.action_tracks:
            if track.object is not None:
                datablocks.add(object_map.get(track.object, track.object))
            if track.action is not None:
                datablocks.add(track.action)

    return datablocks


def _scene_animation_owners(scene: bpy.types.Scene):
    owners = set()
    for ob in scene.objects:
        owners.add(ob)
        if ob.data is not None:
            owners.add(ob.data)
        if ob.type == 'MESH' and ob.data.shape_keys is not None:
            owners.add(ob.data.shape_keys)

    return owners


def _clear_unmatched_animation_data_actions(owners, allowed_actions: set[bpy.types.Action]):
    for owner in owners:
        animation_data = owner.animation_data
        if animation_data is None:
            continue

        if animation_data.action not in allowed_actions:
            animation_data.action = None
            animation_data.use_nla = False


def _safe_blend_path_part(value: str, fallback: str) -> str:
    value = value.strip().replace(":", " ")
    for char in '<>:"/\\|?*':
        value = value.replace(char, "_")

    value = " ".join(value.split())
    return value or fallback


def _parent_animation_gr2_path(parent_asset_path: Path, animation) -> Path:
    return Path(parent_asset_path, "export", "animations", animation.name).with_suffix(".gr2")


def _configure_single_animation_scene(scene: bpy.types.Scene, animation, parent_blend: str, parent_sidecar: str):
    scene.frame_start = animation.frame_start
    scene.frame_end = animation.frame_end
    scene_nwo = scene.nwo
    scene_nwo.asset_type = 'single_animation'
    scene_nwo.is_child_asset = True
    scene_nwo.parent_asset = parent_blend
    scene_nwo.parent_sidecar = parent_sidecar
    scene_nwo.animation_overlay = animation.animation_type == 'overlay'
    scene_nwo.animations.clear()
    _copy_property_collection(animation.animation_events, scene_nwo.animation_events)
    _copy_property_collection(animation.animation_nodes, scene_nwo.animation_nodes)
    scene_nwo.active_animation_event_index = min(animation.active_animation_event_index, len(scene_nwo.animation_events) - 1) if scene_nwo.animation_events else 0
    scene_nwo.active_animation_node_index = min(animation.active_animation_node_index, len(scene_nwo.animation_nodes) - 1) if scene_nwo.animation_nodes else 0


def _configure_child_animation_scene(scene: bpy.types.Scene, animations, parent_blend: str, parent_sidecar: str):
    scene_nwo = scene.nwo
    scene_nwo.asset_type = 'animation'
    scene_nwo.asset_animation_type = 'standalone'
    scene_nwo.is_child_asset = True
    scene_nwo.parent_asset = parent_blend
    scene_nwo.parent_sidecar = parent_sidecar

    animation_names = {animation.name for animation in animations}
    for idx in reversed(range(len(scene_nwo.animations))):
        if scene_nwo.animations[idx].name not in animation_names:
            scene_nwo.animations.remove(idx)

    for animation in scene_nwo.animations:
        animation.external = False
        animation.gr2_path = ""
        animation.blend_path = ""

    scene_nwo.active_animation_index = 0 if scene_nwo.animations else -1
    scene.frame_start = min(animation.frame_start for animation in animations)
    scene.frame_end = max(animation.frame_end for animation in animations)


def _write_animation_asset_blend(context: bpy.types.Context, blend_path: Path, animations, asset_type: str, parent_blend: str, parent_sidecar: str):
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    temp_scene = context.scene.copy()
    temp_scene.name = f"{context.scene.name}_animation_split"
    owners = _scene_animation_owners(context.scene)
    snapshots = [_snapshot_animation_owner(owner) for owner in owners]
    try:
        if asset_type == 'single_animation':
            _configure_single_animation_scene(temp_scene, animations[0], parent_blend, parent_sidecar)
        else:
            _configure_child_animation_scene(temp_scene, animations, parent_blend, parent_sidecar)

        allowed_actions = {track.action for animation in animations for track in animation.action_tracks if track.action is not None}
        _clear_unmatched_animation_data_actions(owners, allowed_actions)
        for animation in animations:
            _set_animation_tracks_active(animation)

        datablocks = {temp_scene}
        datablocks.update(_animation_action_datablocks(animations))
        bpy.data.libraries.write(
            str(blend_path),
            datablocks,
            compress=context.preferences.filepaths.use_file_compression,
        )
    finally:
        _restore_animation_state(snapshots)
        bpy.data.scenes.remove(temp_scene)


def _write_all_animations_child_copy(context: bpy.types.Context, blend_path: Path, parent_blend: str, parent_sidecar: str):
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    scene_nwo = utils.get_scene_props()
    restore = {
        "asset_type": scene_nwo.asset_type,
        "asset_animation_type": scene_nwo.asset_animation_type,
        "is_child_asset": scene_nwo.is_child_asset,
        "parent_asset": scene_nwo.parent_asset,
        "parent_sidecar": scene_nwo.parent_sidecar,
    }
    try:
        scene_nwo.asset_type = 'animation'
        scene_nwo.asset_animation_type = 'standalone'
        scene_nwo.is_child_asset = True
        scene_nwo.parent_asset = parent_blend
        scene_nwo.parent_sidecar = parent_sidecar
        bpy.ops.wm.save_as_mainfile(
            filepath=str(blend_path),
            check_existing=False,
            copy=True,
            compress=context.preferences.filepaths.use_file_compression,
        )
    finally:
        for key, value in restore.items():
            setattr(scene_nwo, key, value)


def _delete_actions_from_main_blend(actions: set[bpy.types.Action], scene_nwo):
    actions_in_internal_animations = set()
    for animation in scene_nwo.animations:
        if animation.external:
            continue

        for track in animation.action_tracks:
            if track.action is not None:
                actions_in_internal_animations.add(track.action)

    for action in actions:
        if action is not None and action.name in bpy.data.actions and action not in actions_in_internal_animations:
            try:
                bpy.data.actions.remove(action, do_unlink=True)
            except RuntimeError:
                pass


def _ik_event_value_data_path(scene_nwo, single_animation: bool) -> str | None:
    if single_animation:
        event_index = scene_nwo.active_animation_event_index
        if event_index < 0:
            return None
        return f"nwo.animation_events[{event_index}].event_value"

    animation_index = scene_nwo.active_animation_index
    if animation_index < 0 or animation_index >= len(scene_nwo.animations):
        return None

    animation = scene_nwo.animations[animation_index]
    event_index = animation.active_animation_event_index
    if event_index < 0:
        return None

    return f"nwo.animations[{animation_index}].animation_events[{event_index}].event_value"


def _tag_redraw_areas(context: bpy.types.Context):
    for area in context.screen.areas:
        area.tag_redraw()

class NWO_UL_AnimProps_Node(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        layout.label(text=f"{item.name if item.name else 'NONE'} -> {item.node_type}", icon='BONE_DATA')
                
class NWO_OT_AddAnimationNode(bpy.types.Operator):
    bl_idname = "nwo.add_animation_node"
    bl_label = "Add"
    bl_description = "Add a new animation node item"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        animation.animation_nodes.add()
        animation.active_animation_node_index = len(animation.animation_nodes) - 1
        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_RemoveAnimationNode(bpy.types.Operator):
    bl_idname = "nwo.remove_animation_node"
    bl_label = "Remove"
    bl_description = "Remove an animation node item from the list"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1 and scene_nwo.animations[scene_nwo.active_animation_index].animation_nodes

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        index = animation.active_animation_node_index
        animation.animation_nodes.remove(index)
        if animation.active_animation_node_index > len(animation.animation_nodes) - 1:
            animation.active_animation_node_index += -1
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_SingleAddAnimationNode(bpy.types.Operator):
    bl_idname = "nwo.single_add_animation_node"
    bl_label = "Add"
    bl_description = "Add a new animation node item"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo
        animation.animation_nodes.add()
        animation.active_animation_node_index = len(animation.animation_nodes) - 1
        context.area.tag_redraw()
        return {"FINISHED"}

class NWO_OT_SingleRemoveAnimationNode(bpy.types.Operator):
    bl_idname = "nwo.single_remove_animation_node"
    bl_label = "Remove"
    bl_description = "Remove an animation node item from the list"
    bl_options = {"UNDO"}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return context.scene and scene_nwo.animation_nodes

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo
        index = animation.active_animation_node_index
        animation.animation_nodes.remove(index)
        if animation.active_animation_node_index > len(animation.animation_nodes) - 1:
            animation.active_animation_node_index += -1
        context.area.tag_redraw()
        return {"FINISHED"}

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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1 and scene_nwo.animations[scene_nwo.active_animation_index].animation_events

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
                layout.label(text=f"Event Function {item.object_function_name.rpartition('_')[2].upper()}", icon='GRAPH')
            case '_connected_geometry_animation_event_type_import':
                layout.label(text=f"{item.frame_frame} - {item.import_name}", icon_value=get_icon_id("anim_overlay"))
            case '_connected_geometry_animation_event_type_wrinkle_map':
                layout.label(text=item.wrinkle_map_face_region, icon='MOD_NORMALEDIT')
            case '_connected_geometry_animation_event_type_ik_active':
                layout.label(text=f"{item.ik_target_usage.replace('_', ' ').title()} - Active - {item.ik_chain if item.ik_chain else ''}", icon='CON_KINEMATIC')
            case '_connected_geometry_animation_event_type_ik_passive':
                layout.label(text=f"{item.ik_target_usage.replace('_', ' ').title()} - Passive - {item.ik_chain if item.ik_chain else ''}", icon='CON_KINEMATIC')
            
class NWO_OT_ClearAnimations(bpy.types.Operator):
    bl_label = "Clear Animations"
    bl_idname = "nwo.clear_animations"
    bl_description = "Clears animations, optionally only clearing those that include strings from the filter. "
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations
    
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
        scene_nwo = utils.get_scene_props()
        animations = scene_nwo.animations
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
            
        scene_nwo.active_animation_index = len(animations) - 1
            
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1
    
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
        scene_nwo = utils.get_scene_props()
        context.scene.tool_settings.use_keyframe_insert_auto = False
        current_animation_index = scene_nwo.active_animation_index
        animation = scene_nwo.animations[current_animation_index]
        if animation:
            if self.delete_actions:
                self.action_map(scene_nwo.animations)
            utils.clear_animation(animation)
            name = animation.name
            scene_nwo.animations.remove(current_animation_index)
            new_index = scene_nwo.active_animation_index - 1
            if new_index < 0 and scene_nwo.animations:
                new_index = 0
            scene_nwo.active_animation_index = new_index
            self.report({"INFO"}, f"Deleted animation: {name}")
        
        return {"FINISHED"}
    
class NWO_OT_UnlinkAnimation(bpy.types.Operator):
    bl_label = "Unlink Animation"
    bl_idname = "nwo.unlink_animation"
    bl_description = "Unlinks a Halo Animation"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        context.scene.tool_settings.use_keyframe_insert_auto = False
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        scene_nwo.active_animation_index = -1
        
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
    
    prioritise_selected_armature: bpy.props.BoolProperty(
        name="Prioritise Selected Armature",
        description="Imports animations using armature animation onto the selected armature rather than looking for a matching name"
    )
    
    use_external_gr2: bpy.props.BoolProperty(
        name="Link to existing GR2 Files",
        description="Links the animation to an already existing GR2 file from the blend the animations are being imported from. If no GR2 exists, then the animations will be kept internal"
    )
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        armature = None
        if self.prioritise_selected_armature:
            armature = utils.get_rig_prioritize_active(context)
        
        current_scenes = set(bpy.data.scenes)
        current_animations = scene_nwo.animations
        with bpy.data.libraries.load(self.filepath, link=False) as (data_from, data_to):
            
            scope_objects = set(data_from.objects)
            scope_actions = set(data_from.actions)

            data_to.scenes = data_from.scenes
            
        new_scenes = [s for s in bpy.data.scenes if s not in current_scenes]

        new_anim_count = 0
        
        filter = self.animation_filter.replace(" ", ":")
        
        export_animations_path = None
        
        data_path = utils.get_data_path()
        
        for scene in new_scenes:
            if scene.nwo.sidecar_path:
                export_animations_path = Path(data_path, Path(utils.relative_path(scene.nwo.sidecar_path)).parent, "export", "animations")
                
            for anim in scene.nwo.animations:
                colon_name = anim.name.replace(" ", ":")
                
                if filter and filter not in colon_name:
                    continue
                
                if current_animations.get(anim.name) is None:
                    new_anim = current_animations.add()
                    new_anim_count += 1
                    for key, value in anim.items():
                        new_anim[key] = value
                        
                    if self.use_external_gr2 and export_animations_path is not None and not anim.external:
                        expected_gr2_path = Path(export_animations_path, f"{anim.name}.gr2")
                        # print(expected_gr2_path)
                        if expected_gr2_path.exists():
                            new_anim.external = True
                            new_anim.gr2_path = utils.relative_path(expected_gr2_path)
                        
                    if not self.import_events:
                        new_anim.animation_events.clear()
                        
                    if not self.import_renames:
                        new_anim.animation_renames.clear()
                        
                    for track in new_anim.action_tracks:
                        ob = track.object
                        if ob is not None:
                            if armature is not None and ob.type == 'ARMATURE':
                                track.object = armature
                                continue
                            last_potential_name = ""
                            while True:
                                potential_name = utils.reduce_suffix(ob.name)
                                if potential_name in scope_objects:
                                    potential_ob = bpy.data.objects.get(potential_name)
                                    if potential_ob:
                                        track.object = potential_ob
                                    else:
                                        track.object = None
                                    break
                                
                                if potential_name == last_potential_name:
                                    break

                                last_potential_name = potential_name
                                
                        if self.use_existing_actions:
                            action = track.action
                            if action is not None:
                                last_potential_name = ""
                                while True:
                                    potential_name = utils.reduce_suffix(action.name)
                                    if potential_name in scope_actions:
                                        potential_action = bpy.data.objects.get(potential_name)
                                        if potential_action:
                                            track.action = potential_action
                                        else:
                                            track.action = None
                                        break
                                    
                                    if potential_name == last_potential_name:
                                        break

                                    last_potential_name = potential_name
                                    
                                    
                        for event in new_anim.animation_events:
                            ob = event.ik_target_marker
                            last_potential_name = ""
                            if ob is not None:
                                while True:
                                    potential_name = utils.reduce_suffix(ob.name)
                                    if potential_name in scope_objects:
                                        potential_ob = bpy.data.objects.get(potential_name)
                                        if potential_ob:
                                            event.ik_target_marker = potential_ob
                                        else:
                                            event.ik_target_marker = None
                                        break
                                    
                                    if potential_name == last_potential_name:
                                        break

                                    last_potential_name = potential_name
                                
                            ob = event.ik_pole_vector
                            last_potential_name = ""
                            if ob is not None:
                                while True:
                                    potential_name = utils.reduce_suffix(ob.name)
                                    if potential_name in scope_objects:
                                        potential_ob = bpy.data.objects.get(potential_name)
                                        if potential_ob:
                                            event.ik_pole_vector = potential_ob
                                        else:
                                            event.ik_pole_vector = None
                                        break
                                    
                                    if potential_name == last_potential_name:
                                        break

                                    last_potential_name = potential_name
                                    
            export_animations_path = None
                        
        for scene in new_scenes:
            bpy.data.scenes.remove(scene)
            
        bpy.ops.outliner.orphans_purge(do_recursive=True)
        
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
        layout.prop(self, "prioritise_selected_armature")
        layout.prop(self, "use_external_gr2")
        layout.prop(self, "animation_filter")

class NWO_OT_OpenExternalAnimationBlend(bpy.types.Operator):
    bl_label = "Open Blend"
    bl_idname = "nwo.open_external_animation_blend"
    bl_description = "Opens the blend file for this GR2 file (it it exists)"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        
        if not animation.external:
            self.report({'WARNING'}, "Animation is not external. No blend to open")
            return {'CANCELLED'}

        blend_path = animation.blend_path.strip()
        if blend_path:
            blend = Path(blend_path)
            if not blend.is_absolute():
                blend = Path(utils.get_data_path(), blend)
        else:
            root_asset = Path(animation.gr2_path).parent.parent.parent
            blend = Path(utils.get_data_path(), root_asset, "animations", animation.name).with_suffix(".blend")
        
        if not blend.exists():
            root_asset = Path(animation.gr2_path).parent.parent.parent
            sidecar = Path(utils.get_data_path(), root_asset, f"{root_asset.name}.sidecar.xml")
            blend = utils.source_blend_from_sidecar(sidecar)
            
            if blend is None or not Path(blend).exists():
                self.report({'WARNING'}, f"No blender file associated with this GR2. Expected: {blend}")
                return {'CANCELLED'}
            
        bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1 and utils.valid_nwo_asset(context)
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        rel_path = ""
        if bpy.data.filepath:
            rel_path = utils.relative_path(bpy.data.filepath)
            
        sidecar_path = scene_nwo.sidecar_path
        
        asset_path = utils.get_asset_path_full()
        blend_path = Path(utils.get_asset_path_full(), "animations", animation.name).with_suffix(".blend")
        gr2_path = Path(asset_path, "export", "animations", animation.name).with_suffix(".gr2")
        is_overlay = animation.animation_type == 'overlay'
        animation.external = True
        animation.gr2_path = utils.relative_path(gr2_path)
        animation.blend_path = utils.relative_path(blend_path)
        animation.pose_overlay = self.pose_overlay
        animation.has_pca = utils.is_corinth(context) and self.pca
        
        bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
        
        frame_start, frame_end = animation.frame_start, animation.frame_end
        
        if not blend_path.parent.exists():
            blend_path.parent.mkdir(parents=True)
            
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False, compress=context.preferences.filepaths.use_file_compression)
        
        scene = bpy.context.scene
        scene.frame_start, scene.frame_end = frame_start, frame_end
        _copy_property_collection(animation.animation_events, scene_nwo.animation_events)
        _copy_property_collection(animation.animation_nodes, scene_nwo.animation_nodes)
        scene_nwo.active_animation_event_index = min(animation.active_animation_event_index, len(scene_nwo.animation_events) - 1) if scene_nwo.animation_events else 0
        scene_nwo.active_animation_node_index = min(animation.active_animation_node_index, len(scene_nwo.animation_nodes) - 1) if scene_nwo.animation_nodes else 0
        scene_nwo.animations.clear()
        
        scene_nwo.asset_type = 'single_animation'
        if rel_path:
            scene_nwo.is_child_asset = True
            scene_nwo.parent_asset = rel_path
            scene_nwo.parent_sidecar = sidecar_path
            scene_nwo.animation_overlay = is_overlay
        
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


class NWO_OT_AnimationsMoveToAssetBlends(bpy.types.Operator):
    bl_label = "Bulk Move to Blends"
    bl_idname = "nwo.animations_move_to_asset_blends"
    bl_description = "Moves animations into external animation blend files and links them back to this parent asset"
    bl_options = {'UNDO'}

    split_type: bpy.props.EnumProperty(
        name="Split Type",
        items=[
            (
                'SINGLE_ANIMATION',
                "Single Animation Assets",
                "Create one single-animation child blend for every animation",
            ),
            (
                'CHILD_ANIMATION',
                "Standalone Child Asset",
                "Create one standalone animation child blend containing all animations",
            ),
            (
                'MODE',
                "Mode Child Assets",
                "Create standalone animation child blends grouped by animation mode",
            ),
            (
                'WEAPON_CLASS',
                "Weapon Class Child Assets",
                "Create standalone animation child blends grouped by animation mode and weapon class",
            ),
            (
                'WEAPON_TYPE',
                "Weapon Type Child Assets",
                "Create standalone animation child blends grouped by animation mode, weapon class, and weapon type",
            ),
        ],
    )

    overwrite_existing: bpy.props.BoolProperty(
        name="Overwrite Existing",
        description="Replace existing animation blend files at the generated paths",
        default=True,
    )

    delete_actions: bpy.props.BoolProperty(
        name="Delete Actions from Parent",
        description="Delete actions used by the moved animations from this parent blend after the child blends are written",
    )

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return bool(bpy.data.filepath and scene_nwo.animations and utils.valid_nwo_asset(context))

    def _eligible_animations(self, scene_nwo):
        return [
            animation
            for animation in scene_nwo.animations
            if animation.name.strip() and not animation.external and animation.animation_type != 'composite'
        ]

    def _animation_groups(self, asset_path: Path, animations):
        if self.split_type == 'SINGLE_ANIMATION':
            return [
                (Path(asset_path, "animations", animation.name).with_suffix(".blend"), [animation])
                for animation in animations
            ]

        if self.split_type == 'CHILD_ANIMATION':
            return [(Path(asset_path, "animations", f"{asset_path.name}_animations").with_suffix(".blend"), animations)]

        groups = defaultdict(list)
        for animation in animations:
            animation_name = utils.AnimationName(animation.name)
            mode = _safe_blend_path_part(animation_name.mode if animation_name.valid else "any", "any")
            weapon_class = _safe_blend_path_part(animation_name.weapon_class if animation_name.valid else "any", "any")
            groups[(mode, weapon_class)].append(animation)

        return [
            (Path(asset_path, "animations", mode, weapon_class).with_suffix(".blend"), group)
            for (mode, weapon_class), group in groups.items()
        ]

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        asset_path = utils.get_asset_path_full()
        if asset_path is None:
            self.report({'WARNING'}, "No valid parent asset path found")
            return {'CANCELLED'}

        animations = self._eligible_animations(scene_nwo)
        if not animations:
            self.report({'WARNING'}, "No internal non-composite animations to move")
            return {'CANCELLED'}

        asset_path = Path(asset_path)
        parent_blend = utils.relative_path(bpy.data.filepath)
        parent_sidecar = scene_nwo.sidecar_path
        child_asset_type = 'single_animation' if self.split_type == 'SINGLE_ANIMATION' else 'animation'
        jobs = self._animation_groups(asset_path, animations)

        bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)

        written = []
        skipped_existing = 0
        snapshots = _snapshot_animation_state(animations)
        try:
            for blend_path, group in jobs:
                if blend_path.exists() and not self.overwrite_existing:
                    skipped_existing += len(group)
                    continue

                if self.split_type == 'CHILD_ANIMATION':
                    _write_all_animations_child_copy(context, blend_path, parent_blend, parent_sidecar)
                elif len(group) == 1:
                    _set_animation_tracks_active(group[0])
                    _write_animation_asset_blend(context, blend_path, group, child_asset_type, parent_blend, parent_sidecar)
                else:
                    _write_animation_asset_blend(context, blend_path, group, child_asset_type, parent_blend, parent_sidecar)
                written.extend((animation, blend_path) for animation in group)
        finally:
            _restore_animation_state(snapshots)

        if not written:
            self.report({'WARNING'}, "No animation blend files were written")
            return {'CANCELLED'}

        moved_actions = set()
        for animation, blend_path in written:
            for track in animation.action_tracks:
                if track.action is not None:
                    moved_actions.add(track.action)

        if self.delete_actions:
            for animation, _ in written:
                utils.clear_animation(animation)

        for animation, blend_path in written:
            animation.external = True
            animation.gr2_path = utils.relative_path(_parent_animation_gr2_path(asset_path, animation))
            animation.blend_path = utils.relative_path(blend_path)

        if self.delete_actions:
            _delete_actions_from_main_blend(moved_actions, scene_nwo)

        bpy.ops.wm.save_mainfile(compress=context.preferences.filepaths.use_file_compression)
        if context.area is not None:
            context.area.tag_redraw()

        blend_count = len({str(blend_path) for _, blend_path in written})
        message = f"Moved {len(written)} animations into {blend_count} blend file{'s' if blend_count != 1 else ''}"
        if skipped_existing:
            message += f"; skipped {skipped_existing} because files already existed"
        self.report({'INFO'}, message)
        return {'FINISHED'}

    def invoke(self, context, _):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "split_type")
        layout.prop(self, "overwrite_existing")
        layout.prop(self, "delete_actions")


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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        path = Path(self.filepath)
        
        if path.exists():
            animation = scene_nwo.animations[scene_nwo.active_animation_index]
            animation.external = True
            animation.gr2_path = utils.relative_path(self.filepath)
            animation.pose_overlay = self.pose_overlay
            animation.has_pca = utils.is_corinth(context) and self.pca
        
        return {'FINISHED'}
    
    def invoke(self, context, _):
        asset_path = utils.get_asset_path_full()
        scene_nwo = utils.get_scene_props()
        if Path(asset_path).exists():
            self.filepath = asset_path
            animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        current_animation_names = {animation.name for animation in scene_nwo.animations}
        used_actions = set()
        for animation in scene_nwo.animations:
            for track in animation.action_tracks:
                if track.action:
                    used_actions.add(track.action)
                    
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
            if action.use_frame_range:
                animation.frame_start = int(action.frame_start)
                animation.frame_end = int(action.frame_end)
            else:
                frames = set()
                slot = utils.get_slot_from_id(action, group.object)
                if slot is None:
                    animation.export_this = False
                else:
                    for fcurve in utils.get_fcurves(action, slot):
                        for kfp in fcurve.keyframe_points:
                            frames.add(kfp.co[0])
                        
                    if len(frames) > 1:
                        animation.frame_start = int(min(*frames))
                        animation.frame_end = int(max(*frames))
                        
            anim_name = utils.AnimationName(action.name)
            if any((h in anim_name.state) for h in pose_hints):
                animation.animation_type = 'overlay'
                        
            # animation.export_this = action.use_frame_range
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
        scene_nwo = utils.get_scene_props()
        if scene_nwo.animations and scene_nwo.active_animation_index > -1:
            animation = scene_nwo.animations[scene_nwo.active_animation_index]
            return animation.animation_events
        
        return False
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1 and animation_event_data
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        layout.separator()
        layout.operator("nwo.animations_move_to_asset_blends", icon='EXPORT')
        layout.separator()
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations
    
    def execute(self, context):
        rename_count = 0
        scene_nwo = utils.get_scene_props()
        for animation in scene_nwo.animations:
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations
    
    def execute(self, context):
        event_count = 0
        scene_nwo = utils.get_scene_props()
        for animation in scene_nwo.animations:
            event_count += len(animation.animation_events)
            animation.animation_events.clear()
            
        self.report({'INFO'}, f"Removed {event_count} animation events")
        return {'FINISHED'}
    
class NWO_OT_SetTimeline(bpy.types.Operator):
    bl_label = "Sync Timeline"
    bl_idname = "nwo.set_timeline"
    bl_description = "Sets the scene timeline to match the current animation's frame range"
    bl_options = {'UNDO'}
    
    # exclude_first_frame: bpy.props.BoolProperty()
    # exclude_last_frame: bpy.props.BoolProperty()
    # use_self_props: bpy.props.BoolProperty(options={'HIDDEN', 'SKIP_SAVE'})
    
    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.active_animation_index > -1
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        scene = context.scene
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        
        if animation.animation_type == 'composite':
            return {'FINISHED'}
        
        start_frame = animation.frame_start
        end_frame = animation.frame_end - int(utils.get_prefs().ignore_final_frame and animation.animation_type in ('base', 'world'))
        
        scene.frame_start = start_frame
        scene.frame_end = end_frame
        scene.frame_current = start_frame
            
        return {'FINISHED'}
    
    # def invoke(self, context, _):
    #     self.use_self_props = True
    #     return self.execute(context)
        
    # def draw(self, context):
    #     layout = self.layout
    #     layout.prop(self, 'exclude_first_frame', text="Exclude First Frame")
    #     layout.prop(self, 'exclude_last_frame', text="Exclude Last Frame")

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
        self.fp_animation = utils.poll_ui(("animation",)) and utils.get_scene_props().asset_animation_type == 'first_person'
        if self.fp_animation:
            self.mode = "first_person"

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        # Create the animation
        current_animation = None
        
        if scene_nwo.active_animation_index > -1:
            current_animation = scene_nwo.animations[scene_nwo.active_animation_index]
            utils.clear_animation(current_animation)
        
        animation = scene_nwo.animations.add()
        
        if self.copy and current_animation:
            for key, value in current_animation.items():
                if key == "name":
                    animation[key] = f"{current_animation.name}_copy"
                elif key == "name_old":
                    animation[key] = f"{current_animation.name}_copy"
                else:
                    animation[key] = value
            # animation.animation_renames.clear()
            for track in animation.action_tracks:
                if track.action:
                    if self.create_new_actions:
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
            col.prop(self, "create_new_actions", text="Duplicate Actions")
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        # Create the rename
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        if scene_nwo.animations and scene_nwo.active_animation_index > -1:
            animation = scene_nwo.animations[scene_nwo.active_animation_index]
            return len(animation.animation_renames) > 0
        
        return False

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        if scene_nwo.animations and scene_nwo.active_animation_index >= 0:
            return scene_nwo.animations[scene_nwo.active_animation_index].action_tracks
        return False
    
    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        if not scene_nwo.animations or scene_nwo.active_animation_index == -1:
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
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        
        for ob in context.selected_objects:
            self.add_track(animation, ob)
            
        context.area.tag_redraw()
        return {"FINISHED"}

    def add_track(self, animation, ob):
        has_shape_key_data = ob.type == 'MESH' and ob.data.shape_keys and ob.data.shape_keys.animation_data and ob.data.shape_keys.animation_data.action
        if ob.animation_data is not None and ob.animation_data.action is not None:
            for track in animation.action_tracks:
                if track.action == ob.animation_data.action and track.object == ob:
                    break
            else:
                group = animation.action_tracks.add()
                group.object = ob
                group.action = ob.animation_data.action
                # if group.object.animation_data.use_nla and group.object.animation_data.nla_tracks and group.object.animation_data.nla_tracks.active:
                #     group.nla_uuid = str(uuid4())
                #     group.object.animation_data.nla_tracks.active
                animation.active_action_group_index = len(animation.action_tracks) - 1
        elif not has_shape_key_data:
            return self.report({'WARNING'}, f"No active action for object [{ob.name}], cannot add action track")
        
        if has_shape_key_data:
            for track in animation.action_tracks:
                if track.is_shape_key_action and track.action == ob.data.shape_keys.animation_data.action:
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
        scene_nwo = utils.get_scene_props()
        if scene_nwo.animations and scene_nwo.active_animation_index >= 0:
            return scene_nwo.animations[scene_nwo.active_animation_index].action_tracks
        return False

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        if scene_nwo.animations and scene_nwo.active_animation_index >= 0:
            return scene_nwo.animations[scene_nwo.active_animation_index].action_tracks
        return False

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
                icon = 'ERROR'
        
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
        name="Base Horizontal",
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.active_animation_index > -1

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        if not self.prop_to_set:
            print("Operator requires prop_to_set specified")
            return {"CANCELLED"}
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        if not animation.animation_events:
            return {"CANCELLED"}
        event = animation.animation_events[animation.active_animation_event_index]
        if not event:
            self.report({"WARNING"}, "No active event")
            return {"CANCELLED"}
        
        current_frame = context.scene.frame_current
        setattr(event, self.prop_to_set, int(current_frame))
        return {"FINISHED"}


class NWO_OT_PreviewIKEvent(bpy.types.Operator):
    bl_idname = "nwo.preview_ik_event"
    bl_label = "Toggle IK Preview"
    bl_description = "Creates or removes a temporary Blender IK constraint using the active IK event's target, pole vector, and influence"
    bl_options = {"UNDO"}

    single_animation: bpy.props.BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})

    @classmethod
    def poll(cls, context) -> bool:
        scene_nwo = utils.get_scene_props()
        for single_animation in (False, True):
            _, event = _get_active_animation_event(scene_nwo, single_animation)
            if event is not None and event.event_type.startswith('_connected_geometry_animation_event_type_ik'):
                return True

        return False

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation, event = _get_active_animation_event(scene_nwo, self.single_animation)
        if event is None or not event.event_type.startswith('_connected_geometry_animation_event_type_ik'):
            self.report({'WARNING'}, "No active IK event to preview")
            return {'CANCELLED'}

        armature = _find_animation_armature(context, animation, self.single_animation)
        if armature is None or armature.type != 'ARMATURE':
            self.report({'WARNING'}, "Could not resolve an armature for this animation")
            return {'CANCELLED'}

        chain = _get_ik_chain(scene_nwo, event.ik_chain)
        if chain is None or not chain.start_node or not chain.effector_node:
            self.report({'WARNING'}, "This IK event does not reference a valid IK chain")
            return {'CANCELLED'}

        effector_bone = armature.pose.bones.get(chain.effector_node)
        if effector_bone is None:
            self.report({'WARNING'}, f"Effector bone [{chain.effector_node}] was not found on armature [{armature.name}]")
            return {'CANCELLED'}

        chain_count = _ik_chain_count(armature, chain.start_node, chain.effector_node)
        if chain_count == 0:
            self.report({'WARNING'}, f"IK chain [{chain.name}] could not be resolved from [{chain.start_node}] to [{chain.effector_node}]")
            return {'CANCELLED'}

        event_data_path = _ik_event_value_data_path(scene_nwo, self.single_animation)
        preview_constraint_name = _ik_preview_constraint_name(chain.name)
        existing_preview = any(
            constraint.name == preview_constraint_name
            for _, constraint in _iter_ik_preview_constraints(armature)
        )

        _clear_ik_preview_constraints(armature)
        _clear_ik_preview_targets(armature)
        if existing_preview:
            context.view_layer.update()
            _tag_redraw_areas(context)
            self.report({'INFO'}, "Cleared IK preview")
            return {'FINISHED'}

        if event.ik_target_marker is None:
            self.report({'WARNING'}, "IK event has no proxy target to preview against")
            return {'CANCELLED'}

        proxy_target = event.ik_target_marker
        proxy_target_bone = None
        proxy_target_matrix = proxy_target.matrix_world
        if proxy_target.type == 'ARMATURE' and event.ik_target_marker_bone:
            proxy_target_bone = proxy_target.pose.bones.get(event.ik_target_marker_bone)
            if proxy_target_bone is not None:
                proxy_target_matrix = proxy_target.matrix_world @ proxy_target_bone.matrix

        preview_target = bpy.data.objects.new(_ik_preview_target_name(armature, chain.name), None)
        preview_target.empty_display_type = 'PLAIN_AXES'
        preview_target.empty_display_size = 0.02
        preview_target.hide_select = True
        preview_target.nwo.export_this = False
        preview_target.nwo.is_frame = True
        target_collection = proxy_target.users_collection[0] if proxy_target.users_collection else context.scene.collection
        target_collection.objects.link(preview_target)
        preview_target.rotation_mode = 'QUATERNION'
        preview_target.parent = proxy_target
        if proxy_target_bone is not None:
            preview_target.parent_type = 'BONE'
            preview_target.parent_bone = proxy_target_bone.name
        preview_target.matrix_parent_inverse = Matrix.Identity(4)
        offset_matrix = proxy_target_matrix.inverted_safe() @ (armature.matrix_world @ effector_bone.matrix)
        offset_location, offset_rotation, offset_scale = offset_matrix.decompose()
        preview_target.location = offset_location
        preview_target.rotation_quaternion = offset_rotation
        preview_target.scale = offset_scale

        constraint = effector_bone.constraints.new('IK')
        constraint.name = preview_constraint_name
        constraint.target = preview_target
        constraint.chain_count = chain_count
        constraint.use_stretch = False
        constraint.use_tail = False
        constraint.influence = event.event_value

        if event.ik_pole_vector is not None:
            constraint.pole_target = event.ik_pole_vector
            if event.ik_pole_vector.type == 'ARMATURE' and getattr(event, "ik_pole_vector_bone", ""):
                pole_target_bone = event.ik_pole_vector.pose.bones.get(event.ik_pole_vector_bone)
                if pole_target_bone is not None:
                    constraint.pole_subtarget = pole_target_bone.name

        if event_data_path:
            fcurve = constraint.driver_add("influence")
            driver = fcurve.driver
            driver.type = 'SCRIPTED'
            driver.expression = "ik_influence"
            variable = driver.variables.new()
            variable.name = "ik_influence"
            target = variable.targets[0]
            target.id_type = 'SCENE'
            target.id = context.scene
            target.data_path = event_data_path

        context.view_layer.update()
        _tag_redraw_areas(context)
        self.report({'INFO'}, f"Previewing IK event [{event.name}]")
        return {'FINISHED'}
    
class NWO_OT_AnimationFramesSyncToKeyFrames(bpy.types.Operator):
    bl_idname = "nwo.animation_frames_sync_to_keyframes"
    bl_label = "Sync Frame Range with Keyframes"
    bl_description = "Sets the frame range for this animation to the length of the keyframes"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, context):
        scene_nwo = utils.get_scene_props()
        return scene_nwo.active_animation_index > -1

    _timer = None
    _current_animation_index = -1
    
    def update_frame_range_from_keyframes(self, context: bpy.types.Context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        old_start = animation.frame_start
        old_end = animation.frame_end
        actions = {track.action for track in animation.action_tracks if track.action is not None}
        if not actions:
            self.report({'WARNING'}, "Cannot update frame range, animation has no action tracks")
        frames = set()
        for action in actions:
            for slot in action.slots:
                for fcurve in utils.get_fcurves(action, slot):
                    for kfp in fcurve.keyframe_points:
                        frames.add(kfp.co[0])
                
        if len(frames) > 1:
            animation.frame_start = int(min(*frames))
            animation.frame_end = int(max(*frames))
        
        if old_start != animation.frame_start or old_end != animation.frame_end:
            bpy.ops.nwo.set_timeline()

    def modal(self, context, event):
        scene_nwo = utils.get_scene_props()
        if scene_nwo.active_animation_index != self._current_animation_index or scene_nwo.export_in_progress or not scene_nwo.keyframe_sync_active:
            self.cancel(context)
            return {'CANCELLED'}

        if event.type == 'TIMER':
            self.update_frame_range_from_keyframes(context)

        return {'PASS_THROUGH'}

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        if scene_nwo.keyframe_sync_active:
            scene_nwo.keyframe_sync_active = False
            return {"CANCELLED"}
        scene_nwo.keyframe_sync_active = True
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        self._current_animation_index = scene_nwo.active_animation_index
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        scene_nwo = utils.get_scene_props()
        scene_nwo.keyframe_sync_active = False
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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
        event = animation.animation_events.add()
        animation.active_animation_event_index = len(animation.animation_events) - 1
        event.frame_frame = context.scene.frame_current
        event.event_id = random.randint(0, 2147483647)
        # event.name = f"event_{len(animation.animation_events)}"

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
        scene_nwo = utils.get_scene_props()
        return scene_nwo.animations and scene_nwo.active_animation_index > -1 and len(scene_nwo.animations[scene_nwo.active_animation_index].animation_events) > 0

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo
        event = animation.animation_events.add()
        animation.active_animation_event_index = len(animation.animation_events) - 1
        event.frame_frame = context.scene.frame_current
        event.event_id = random.randint(0, 2147483647)
        # event.name = f"event_{len(animation.animation_events)}"

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
        scene_nwo = utils.get_scene_props()
        return context.scene and scene_nwo.animation_events

    def execute(self, context):
        scene_nwo = utils.get_scene_props()
        animation = scene_nwo
        index = animation.active_animation_event_index
        animation.animation_events.remove(index)
        if animation.active_animation_event_index > len(animation.animation_events) - 1:
            animation.active_animation_event_index += -1
        context.area.tag_redraw()
        return {"FINISHED"}

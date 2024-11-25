"""Animation sub-panel specific operators"""

import math
import random
from uuid import uuid4
import bpy

from ...props.scene import NWO_AnimationPropertiesGroup
from ... import utils
from ...icons import get_icon_id

class NWO_UL_AnimProps_Events(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        animation = item
        if animation:
            layout.prop(animation, "name", text="", emboss=False, icon_value=get_icon_id("animation_event"))
        else:
            layout.label(text="", translate=False, icon_value=icon)

class NWO_OT_DeleteAnimation(bpy.types.Operator):
    bl_label = "Delete Animation"
    bl_idname = "nwo.delete_animation"
    bl_description = "Deletes a Halo Animation from the blend file"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.active_animation_index > -1

    def execute(self, context):
        context.scene.tool_settings.use_keyframe_insert_auto = False
        current_animation_index = context.scene.nwo.active_animation_index
        animation = context.scene.nwo.animations[current_animation_index]
        if animation:
            utils.clear_animation(animation)
            name = animation.name
            context.scene.nwo.animations.remove(current_animation_index)
            context.scene.nwo.active_animation_index -= 1
            self.report({"INFO"}, f"Deleted animation: {name}")
        
        return {"FINISHED"}
    
class NWO_OT_UnlinkAnimation(bpy.types.Operator):
    bl_label = "Unlink Animation"
    bl_idname = "nwo.unlink_animation"
    bl_description = "Unlinks a Halo Animation"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.active_animation_index > -1

    def execute(self, context):
        context.scene.tool_settings.use_keyframe_insert_auto = False
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        context.scene.nwo.active_animation_index = -1
        
        utils.clear_animation(animation)
                    
        return {"FINISHED"}
    
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
        scene_nwo = context.scene.nwo
        current_animation_names = {animation.name for animation in context.scene.nwo.animations}
        for action in bpy.data.actions:
            action_nwo = action.nwo
            name = action_nwo.name_override if action_nwo.name_override else action.name
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
            for key, value in action_nwo.items():
                animation[key] = value
            
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
    
    def animation_type_items(self, context):
        items = [
            (
                "base",
                "Base",
                "Defines a base animation. Allows for varying levels of root bone movement (or none). Useful for cinematic animations, idle animations, and any animations that effect a full skeleton or are expected to be overlayed on top of",
                '',
                0,
            ),
            (
                "overlay",
                "Overlay",
                "Animations that overlay on top of a base animation (or none). Supports keyframe and pose overlays. Useful for animations that should overlay on top of base animations, such as vehicle steering or weapon aiming. Supports object functions to define how these animations blend with others\nLegacy format: JMO\nExamples: fire_1, reload_1, device position",
                '',
                1,
            ),
            (
                "replacement",
                "Replacement",
                "Animations that fully replace base animated nodes, provided those bones are animated. Useful for animations that should completely overrule a certain set of bones, and don't need any kind of blending influence. Can be set to either object or local space",
                '',
                2,
            ),
        ]
        
        if utils.is_corinth(context):
            items.append(
            (
                "world",
                "World",
                "Animations that play relative to the world rather than an objects current position",
                '',
                3,
            ))
        
        return items
    
    def get_animation_type(self):
        max_int = 2
        if utils.is_corinth():
            max_int = 3
        if self.animation_type_help > max_int:
            return 0
        return self.animation_type_help

    def set_animation_type(self, value):
        self["animation_type"] = value

    def update_animation_type(self, context):
        self.animation_type_help = self["animation_type"]
        
    animation_type_help: bpy.props.IntProperty()
            
    animation_type: bpy.props.EnumProperty(
        name="Type",
        description="Set the type of Halo animation you want this action to be",
        items=animation_type_items,
        get=get_animation_type,
        set=set_animation_type,
        update=update_animation_type,
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

    animation_is_pose: bpy.props.BoolProperty(
        name='Pose Overlay',
        description='Tells the exporter to compute aim node directions for this overlay. These allow animations to be affected by the aiming direction of the animated object. You must set the pedestal, pitch, and yaw usages in the Foundry armature properties to use this correctly\nExamples: aim_still_up, acc_up_down, vehicle steering'
    )

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
        description="The mode the object must be in to use this animation. Use 'any' for all modes. Other valid inputs inlcude but are not limited to: 'crouch' when a unit is crouching,  'combat' when a unit is in combat. Modes can also refer to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more information refer to existing model_animation_graph tags. Can be empty",
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

    def __init__(self):
        self.fp_animation = utils.poll_ui(("animation"))
        if self.fp_animation:
            self.mode = "first_person"

    def execute(self, context):
        full_name = self.create_name()
        scene_nwo = context.scene.nwo
        # Create the animation
        if scene_nwo.active_animation_index > -1:
            current_animation = scene_nwo.animations[scene_nwo.active_animation_index]
            utils.clear_animation(current_animation)
        
        animation = scene_nwo.animations.add()
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
        animation.animation_is_pose = self.animation_is_pose
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
        col.prop(self, "create_new_actions")
        col.prop(self, "frame_start", text="First Frame")
        col.prop(self, "frame_end", text="Last Frame")
        # col.prop(self, "keep_current_pose")
        layout.label(text="Animation Format")
        row = layout.row()
        row.use_property_split = True
        row.prop(self, "animation_type")
        if self.animation_type != 'world':
            row = layout.row()
            row.use_property_split = True
            if self.animation_type == 'base':
                row.prop(self, 'animation_movement_data')
            elif self.animation_type == 'overlay':
                row.prop(self, 'animation_is_pose')
            elif self.animation_type == 'replacement':
                row.prop(self, 'animation_space', expand=True)
        self.draw_name(layout)

    def draw_name(self, layout):
        if self.fp_animation:
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
            elif weapon_type or is_transition:
                full_name += f" any"

            if weapon_type:
                full_name += f" {weapon_type}"
            elif set or is_transition:
                full_name += f" any"

            if set:
                full_name += f" {set}"
            elif is_transition:
                full_name += f" any"

            if state and not is_damage:
                full_name += f" {state}"
            elif not is_damage:
                self.report({"WARNING"}, "No state defined. Setting to idle")
                full_name += f" idle"

            if is_transition:
                if destination_mode:
                    full_name += f" {destination_mode}"
                else:
                    full_name += f" any"

                if destination_state:
                    full_name += f" {destination_state}"
                else:
                    self.report(
                        {"WARNING"}, "No destination state defined. Setting to idle"
                    )
                    full_name += f" idle"

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


class NWO_OT_List_Add_Animation_Rename(NWO_OT_NewAnimation):
    bl_label = "New Animation Rename"
    bl_idname = "nwo.animation_rename_add"
    bl_description = "Creates a new Halo Animation Rename"
    bl_options = {"REGISTER", "UNDO"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations and context.scene.nwo.active_animation_index > -1

    def __init__(self):
        animation = bpy.context.scene.nwo.animations[bpy.context.scene.nwo.active_animation_index]
        state = animation.state.lower().strip(" :_,-")
        state = "idle" if state == "" else state
        if animation.created_with_foundry and state in animation.name:
            self.state_type = animation.state_type
            self.custom = animation.custom
            self.mode = animation.mode
            self.weapon_class = animation.weapon_class
            self.weapon_type = animation.weapon_type
            self.set = animation.set
            self.state = animation.state
            self.destination_mode = animation.destination_mode
            self.destination_state = animation.destination_state
            self.damage_power = animation.damage_power
            self.damage_type = animation.damage_type
            self.damage_direction = animation.damage_direction
            self.damage_region = animation.damage_region
            self.variant = animation.variant

        else:
            self.state_type = "custom"
            self.custom = animation.name

    def draw(self, context):
        self.draw_name(self.layout)

    def execute(self, context):
        full_name = self.create_name()
        animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        if full_name == animation.name:
            self.report(
                {"WARNING"},
                f"Rename entry not created. Rename cannot match animation name",
            )
            return {"CANCELLED"}

        # Create the rename
        rename = animation.animation_renames.add()
        animation.active_animation_rename_index = len(animation.animation_renames) - 1
        rename.name = full_name
        context.area.tag_redraw()

        self.report({"INFO"}, f"Created rename: {full_name}")
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
        if not (context.scene.nwo.animations and context.scene.nwo.active_animation_index) > -1:
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
        
        current_track_objects = {track.object for track in animation.action_tracks}
        
        for ob in context.selected_objects:
            if ob not in current_track_objects:
                self.add_track(animation, ob)
            elif ob.animation_data and ob.animation_data.action:
                self.report({'WARNING'}, f"Action '{ob.animation_data.action.name}' for object '{ob.name}' already set as track")
            
        context.area.tag_redraw()
        return {"FINISHED"}

    def add_track(self, animation, ob):
        if ob.animation_data is not None and ob.animation_data.action is not None:
            group = animation.action_tracks.add()
            group.object = ob
            group.action = ob.animation_data.action
            # if group.object.animation_data.use_nla and group.object.animation_data.nla_tracks and group.object.animation_data.nla_tracks.active:
            #     group.nla_uuid = str(uuid4())
            #     group.object.animation_data.nla_tracks.active
            animation.active_action_group_index = len(animation.action_tracks) - 1
        if ob.type == 'MESH' and ob.data.shape_keys and ob.data.shape_keys.animation_data and ob.data.shape_keys.animation_data.action:
            group = animation.action_tracks.add()
            group.object = ob
            group.action = ob.data.shape_keys.animation_data.action
            group.is_shape_key_action = True
        else:
            return self.report({'WARNING'}, f"No active action for object [{ob.name}], cannot add action track")
        

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
    # Constants (flags)
    # Be careful not to shadow FILTER_ITEM (i.e. UIList().bitflag_filter_item)!
    # E.g. VGROUP_EMPTY = 1 << 0

    # Custom properties, saved with .blend file. E.g.
    # use_filter_empty = bpy.props.BoolProperty(name="Filter Empty", default=False, options=set(),
    #                                           description="Whether to filter empty vertex groups")

    # Called for each drawn item.
    def draw_item(self, context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname, index, flt_flag):
        layout.prop(item, "name", text="", emboss=False, icon='ANIM')
        row = layout.row()
        row.alignment = 'RIGHT'
        row.label(text=str((item.frame_end + 1) - item.frame_start), icon='KEYFRAME_HLT')
        num_action_tracks = len([track for track in item.action_tracks if not track.is_shape_key_action])
        num_shape_key_tracks = len(item.action_tracks) - num_action_tracks
        row.label(text=str(num_action_tracks), icon='ACTION')
        if num_shape_key_tracks:
            row.label(text=str(num_shape_key_tracks), icon='SHAPEKEY_DATA')
        if item.animation_renames:
            row.label(text=str(len(item.animation_renames)), icon_value=get_icon_id("animation_rename"))
        else:
            row.label(text=' ', icon='BLANK1')
        if item.animation_events:
            row.label(text=str(len(item.animation_events)), icon_value=get_icon_id("animation_event"))
        else:
            row.label(text=' ', icon='BLANK1')
        anim_type_display = item.animation_type
        if anim_type_display == 'base' and item.animation_movement_data != 'none':
            anim_type_display += f'[{item.animation_movement_data}]'
        elif anim_type_display == 'overlay' and item.animation_is_pose:
            anim_type_display += '[pose]'
        elif anim_type_display == 'replacement':
            anim_type_display += f'[{item.animation_space}]'
        row.label(text=anim_type_display)
        layout.prop(item, 'export_this', text="", icon='CHECKBOX_HLT' if item.export_this else 'CHECKBOX_DEHLT', emboss=False)
    
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

    bl_idname = "animation_event.list_add"
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

    bl_idname = "animation_event.list_remove"
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
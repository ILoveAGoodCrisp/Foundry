"""Animation sub-panel specific operators"""

import math
import random
import bpy
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
        return context.scene.nwo.active_action_index > -1

    def execute(self, context):
        context.scene.tool_settings.use_keyframe_insert_auto = False
        current_action_index = context.scene.nwo.active_action_index
        action = bpy.data.actions[current_action_index]
        if action:
            name = str(action.name)
            bpy.data.actions.remove(action)
            utils.reset_to_basis(context)
            self.report({"INFO"}, f"Deleted animation: {name}")
            
        new_action_index = len(bpy.data.actions) - 1 if current_action_index >= len(bpy.data.actions) else current_action_index
        context.scene.nwo.active_action_index = new_action_index
        
        return {"FINISHED"}
    
class NWO_OT_UnlinkAnimation(bpy.types.Operator):
    bl_label = "Unlink Animation"
    bl_idname = "nwo.unlink_animation"
    bl_description = "Unlinks a Halo Animation"
    bl_options = {'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.active_action_index > -1

    def execute(self, context):
        context.scene.tool_settings.use_keyframe_insert_auto = False
        context.scene.nwo.active_action_index = -1
        utils.reset_to_basis(context)
                    
        return {"FINISHED"}
    
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
        return context.scene.nwo.active_action_index > -1
    
    def execute(self, context):
        scene = context.scene
        scene_nwo = scene.nwo
        action = bpy.data.actions[scene_nwo.active_action_index]
        
        start_frame = int(action.frame_start)
        if self.use_self_props:
            final_start_frame = start_frame + self.exclude_first_frame
            scene_nwo.exclude_first_frame = self.exclude_first_frame
        else:
            final_start_frame = start_frame + scene_nwo.exclude_first_frame
            
        end_frame = int(action.frame_end)
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
    
    keep_current_pose: bpy.props.BoolProperty(
        name="Keep Current Pose",
        description="Keeps the current pose of the object instead of resetting it to the models rest pose",
    )
    
    state_preset: bpy.props.EnumProperty(
        name="State Preset",
        description="Animation States which execute in specific hard-coded contexts. Item descriptions describe their use. Setting a preset will update the state field and animation type",
        items=[
            ("none", "None", ""),
            ("airborne", "airborne", "Base animation with no root movement that plays when the object is midair"),
        ]
    )

    def __init__(self):
        self.fp_animation = utils.poll_ui(("animation"))
        if self.fp_animation:
            self.mode = "first_person"

    def execute(self, context):
        full_name = self.create_name()
        # Create the animation
        if not self.keep_current_pose:
            utils.reset_to_basis(context)
        animation = bpy.data.actions.new(full_name)
        animation.use_frame_range = True
        animation.use_fake_user = True
        animation.frame_start = self.frame_start
        animation.frame_end = self.frame_end
        ob = context.object
        if not ob.animation_data:
            ob.animation_data_create()
        ob.animation_data.action = animation
        nwo = animation.nwo
        nwo.animation_type = self.animation_type
        nwo.animation_movement_data = self.animation_movement_data
        nwo.animation_is_pose = self.animation_is_pose
        nwo.animation_space = self.animation_space
        # Blender animations have a max 64 character limit
        # on action names, so apply the full animation name to
        # the name_override field if this limit is breached
        if animation.name < full_name:
            nwo.name_override = full_name

        # record the inputs from this operator
        nwo.state_type = self.state_type
        nwo.custom = self.custom
        nwo.mode = self.mode
        nwo.weapon_class = self.weapon_class
        nwo.weapon_type = self.weapon_type
        nwo.set = self.set
        nwo.state = self.state
        nwo.destination_mode = self.destination_mode
        nwo.destination_state = self.destination_state
        nwo.damage_power = self.damage_power
        nwo.damage_type = self.damage_type
        nwo.damage_direction = self.damage_direction
        nwo.damage_region = self.damage_region
        nwo.variant = self.variant

        nwo.created_with_foundry = True
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
        col.prop(self, "frame_start", text="First Frame")
        col.prop(self, "frame_end", text="Last Frame")
        col.prop(self, "keep_current_pose")
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
        return bpy.data.actions and context.scene.nwo.active_action_index > -1

    def __init__(self):
        action = bpy.data.actions[bpy.context.scene.nwo.active_action_index]
        nwo = action.nwo
        state = nwo.state.lower().strip(" :_,-")
        state = "idle" if state == "" else state
        animation_name = nwo.name_override if nwo.name_override else action.name
        if nwo.created_with_foundry and state in action.name:
            self.state_type = nwo.state_type
            self.custom = nwo.custom
            self.mode = nwo.mode
            self.weapon_class = nwo.weapon_class
            self.weapon_type = nwo.weapon_type
            self.set = nwo.set
            self.state = nwo.state
            self.destination_mode = nwo.destination_mode
            self.destination_state = nwo.destination_state
            self.damage_power = nwo.damage_power
            self.damage_type = nwo.damage_type
            self.damage_direction = nwo.damage_direction
            self.damage_region = nwo.damage_region
            self.variant = nwo.variant

        else:
            self.state_type = "custom"
            self.custom = animation_name

    def draw(self, context):
        self.draw_name(self.layout)

    def execute(self, context):
        full_name = self.create_name()
        action = bpy.data.actions[context.scene.nwo.active_action_index]
        nwo = action.nwo
        animation_name = nwo.name_override if nwo.name_override else action.name
        if full_name == animation_name:
            self.report(
                {"WARNING"},
                f"Rename entry not created. Rename cannot match animation name",
            )
            return {"CANCELLED"}

        # Create the rename
        rename = nwo.animation_renames.add()
        nwo.animation_renames_index = len(nwo.animation_renames) - 1
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
        if not bpy.data.actions:
            return
        action_index = context.scene.nwo.active_action_index
        if action_index < 0:
            return
        action = bpy.data.actions[action_index]
        return len(action.nwo.animation_renames) > 0

    def execute(self, context):
        action = bpy.data.actions[context.scene.nwo.active_action_index]
        nwo = action.nwo
        nwo.animation_renames.remove(nwo.animation_renames_index)
        if nwo.animation_renames_index > len(nwo.animation_renames) - 1:
            nwo.animation_renames_index += -1
        return {"FINISHED"}
    
class NWO_OT_AnimationRenameMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_rename_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        action = bpy.data.actions[bpy.context.scene.nwo.active_action_index]
        action_nwo = action.nwo
        table = action_nwo.animation_renames
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = action_nwo.animation_renames_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        action_nwo.animation_renames_index = to_index
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

class NWO_UL_AnimationList(bpy.types.UIList):
    # Constants (flags)
    # Be careful not to shadow FILTER_ITEM (i.e. UIList().bitflag_filter_item)!
    # E.g. VGROUP_EMPTY = 1 << 0

    # Custom properties, saved with .blend file. E.g.
    # use_filter_empty = bpy.props.BoolProperty(name="Filter Empty", default=False, options=set(),
    #                                           description="Whether to filter empty vertex groups")

    # Called for each drawn item.
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index, flt_flag):
        if not item.use_fake_user:
            row = layout.row()
            row.alert = True
            row.label(icon='ERROR')
            
        nwo = item.nwo
        row = layout.row()
        row.scale_x = 1.5
        row.prop(item, "name", text="", emboss=False, icon='ACTION')
        row = layout.row()
        if item.use_frame_range:
            row.label(text=str(math.floor(item.frame_end + 1) - math.floor(item.frame_start)), icon='KEYFRAME_HLT')
        else:
            row.label(text=' ', icon='BLANK1')
        if item.nwo.animation_renames:
            row.label(text=str(len(item.nwo.animation_renames)), icon_value=get_icon_id("animation_rename"))
        else:
            row.label(text=' ', icon='BLANK1')
        if item.nwo.animation_events:
            row.label(text=str(len(item.nwo.animation_events)), icon_value=get_icon_id("animation_event"))
        else:
            row.label(text=' ', icon='BLANK1')
        anim_type_display = nwo.animation_type
        if anim_type_display == 'base' and nwo.animation_movement_data != 'none':
            anim_type_display += f'[{nwo.animation_movement_data}]'
        elif anim_type_display == 'overlay' and nwo.animation_is_pose:
            anim_type_display += '[pose]'
        elif anim_type_display == 'replacement':
            anim_type_display += f'[{nwo.animation_space}]'
        row.label(text=anim_type_display)
        row.prop(item, 'use_frame_range', text="", icon='CHECKBOX_HLT' if item.use_frame_range else 'CHECKBOX_DEHLT', emboss=False)
    
class NWO_OT_AnimationEventSetFrame(bpy.types.Operator):
    bl_idname = "nwo.animation_event_set_frame"
    bl_label = "Set Event Frame"
    bl_description = "Sets the event frame to the current timeline frame"
    bl_options = {"UNDO"}
    
    prop_to_set: bpy.props.StringProperty(options={'SKIP_SAVE', 'HIDDEN'})
    
    @classmethod
    def poll(cls, context) -> bool:
        return context.scene.nwo.active_action_index > -1

    def execute(self, context):
        if not self.prop_to_set:
            print("Operator requires prop_to_set specified")
            return {"CANCELLED"}
        action = bpy.data.actions[context.scene.nwo.active_action_index]
        if not action.nwo.animation_events:
            return {"CANCELLED"}
        event = action.nwo.animation_events[action.nwo.animation_events_index]
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
        return context.scene.nwo.active_action_index > -1

    _timer = None
    _current_action_index = -1
    
    def update_frame_range_from_keyframes(self, context: bpy.types.Context):
        action: bpy.types.Action = bpy.data.actions[context.scene.nwo.active_action_index]
        if not action.use_frame_range:
            action.use_frame_range = True
        old_start = int(action.frame_start)
        old_end = int(action.frame_end)
        frames = set()
        for fcurve in action.fcurves:
            for kfp in fcurve.keyframe_points:
                frames.add(kfp.co[0])
                
        if len(frames) > 1:
            action.frame_start = int(min(*frames))
            action.frame_end = int(max(*frames))
        
        if old_start != int(action.frame_start) or old_end != int(action.frame_end):
            bpy.ops.nwo.set_timeline()

    def modal(self, context, event):
        if context.scene.nwo.active_action_index != self._current_action_index or context.scene.nwo.export_in_progress or not context.scene.nwo.keyframe_sync_active:
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
        self._current_action_index = int(context.scene.nwo.active_action_index)
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
        return bpy.data.actions and context.scene.nwo.active_action_index > -1

    def execute(self, context):
        action = bpy.data.actions[bpy.context.scene.nwo.active_action_index]
        nwo = action.nwo
        event = nwo.animation_events.add()
        nwo.animation_events_index = len(nwo.animation_events) - 1
        event.frame_frame = context.scene.frame_current
        event.event_id = random.randint(0, 2147483647)
        event.name = f"event_{len(nwo.animation_events)}"

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
        return bpy.data.actions and context.scene.nwo.active_action_index > -1 and len(bpy.data.actions[context.scene.nwo.active_action_index].nwo.animation_events) > 0

    def execute(self, context):
        action = bpy.data.actions[bpy.context.scene.nwo.active_action_index]
        action_nwo = action.nwo
        index = action_nwo.animation_events_index
        action_nwo.animation_events.remove(index)
        if action_nwo.animation_events_index > len(action_nwo.animation_events) - 1:
            action_nwo.animation_events_index += -1
        context.area.tag_redraw()
        return {"FINISHED"}
    
class NWO_OT_AnimationEventMove(bpy.types.Operator):
    bl_label = ""
    bl_idname = "nwo.animation_event_move"
    bl_options = {'UNDO'}
    
    direction: bpy.props.StringProperty()

    def execute(self, context):
        action = bpy.data.actions[bpy.context.scene.nwo.active_action_index]
        action_nwo = action.nwo
        table = action_nwo.animation_events
        delta = {"down": 1, "up": -1,}[self.direction]
        current_index = action_nwo.animation_events_index
        to_index = (current_index + delta) % len(table)
        table.move(current_index, to_index)
        action_nwo.animation_events_index = to_index
        context.area.tag_redraw()
        return {'FINISHED'}
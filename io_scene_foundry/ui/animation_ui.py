# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

from bpy.types import Context, Event

from io_scene_foundry.utils.nwo_utils import poll_ui
from .templates import NWO_Op, NWO_PropPanel
import bpy


# ACTION PROPERTIES
class NWO_ActionProps(NWO_PropPanel):
    bl_label = "Halo Animation Properties"
    bl_idname = "NWO_PT_ActionDetailsPanel"
    bl_space_type = "DOPESHEET_EDITOR"
    bl_region_type = "UI"
    bl_context = "Action"
    bl_parent_id = "DOPESHEET_PT_action"

    @classmethod
    def poll(cls, context):
        return context.object.animation_data.action

    def draw_header(self, context):
        action = context.active_object.animation_data.action
        action_nwo = action.nwo
        self.layout.prop(action_nwo, "export_this", text="")

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        flow = layout.grid_flow(
            row_major=True,
            columns=0,
            even_columns=True,
            even_rows=False,
            align=False,
        )

        action = context.object.animation_data.action
        action_nwo = action.nwo

        if not action_nwo.export_this:
            layout.label(text="Animation is excluded from export")
            layout.active = False

        else:
            col = flow.column()
            col.prop(action_nwo, "name_override")
            col.prop(action_nwo, "animation_type")

class NWO_DeleteAnimation(NWO_Op):
    bl_label = "Delete Animation"
    bl_idname = "nwo.delete_animation"
    bl_description = "Deletes a Halo Animation from the blend file"

    def execute(self, context):
        action = context.object.animation_data.action
        name = str(action.name)
        bpy.data.actions.remove(action)
        self.report({'INFO'}, f"Deleted animation: {name}")
        return {'FINISHED'}

class NWO_NewAnimation(NWO_Op):
    bl_label = "New Animation"
    bl_idname = "nwo.new_animation"
    bl_description = "Creates a new Halo Animation"

    frame_start : bpy.props.IntProperty(name="First Frame", default=0)
    frame_end : bpy.props.IntProperty(name="Last Frame", default=29)
    animation_type : bpy.props.EnumProperty(
        name="Animation Type",
        items=[
            (
                "JMM",
                "Base (JMM)",
                "Full skeleton animation. Has no physics movement. Examples: enter, exit, idle",
            ),
            (
                "JMA",
                "Base - Horizontal Movement (JMA)",
                "Full skeleton animation with physics movement on the X-Y plane. Examples: move_front, walk_left, h_ping front gut",
            ),
            (
                "JMT",
                "Base - Yaw Rotation (JMT)",
                "Full skeleton animation with physics rotation on the yaw axis. Examples: turn_left, turn_right",
            ),
            (
                "JMZ",
                "Base - Full Movement / Yaw Rotation (JMZ)",
                "Full skeleton animation with physics movement on the X-Y-Z axis and yaw rotation. Examples: climb, jump_down_long, jump_forward_short",
            ),
            (
                "JMV",
                "Base - Full Movement & Rotation (JMV)",
                "Full skeleton animation for vehicles. Has full roll / pitch / yaw rotation and angular velocity. Do not use for bipeds. Examples: vehicle roll_left, vehicle roll_right_short",
            ),
            (
                "JMO",
                "Overlay - Keyframe (JMO)",
                "Overlays animation on top of others. Use on animations that aren't controlled by a function. Use this type for animating device_machines. Examples: fire_1, reload_1, device position",
            ),
            (
                "JMOX",
                "Overlay - Pose (JMOX)",
                "Overlays animation on top of others. Use on animations that rely on functions like aiming / steering / accelaration. These animations require pitch & yaw bones to be animated and defined in the animation graph. Examples: aim_still_up, acc_up_down, vehicle steering",
            ),
            (
                "JMR",
                "Replacement - Object Space (JMR)",
                "Replaces animation only on the bones animated in the replacement animation. Examples: combat pistol hp melee_strike_2, revenant_p sword put_away",
            ),
            (
                "JMRX",
                "Replacement - Local Space (JMRX)",
                "Replaces animation only on the bones animated in the replacement animation. Examples: combat pistol any grip, combat rifle sr grip",
            ),
        ],
    )
    
    state_type : bpy.props.EnumProperty(
        name="State Type",
        items=[
            ("action", "Action / Overlay", ""),
            ("transition", "Transition", ""),
            ("damage", "Death & Damage", ""),
            ("custom", "Custom", ""),
        ]
    )

    mode : bpy.props.StringProperty(
        name="Mode",
        description="""The mode the object must be in to use this animation. Use 'any' for all modes. Other valid
        inputs inlcude but are not limited to: 'crouch' when a unit is crouching, 
        'combat' when a unit is in combat. Modes can also refer
        to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more
        information refer to existing model_animation_graph tags. Can be empty"""
        )
    
    weapon_class : bpy.props.StringProperty(
        name="Weapon Class",
        description="""The weapon class this unit must be holding to use this animation. Weapon class is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty"""
        )
    weapon_type : bpy.props.StringProperty(
        name="Weapon Name",
        description="""The weapon type this unit must be holding to use this animation.  Weapon name is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty"""
        )
    set : bpy.props.StringProperty(
        name="Set",
        description="The set this animtion is a part of. Can be empty"
        )
    state : bpy.props.StringProperty(
        name="State",
        description="""The state this animation plays in. States can refer to hardcoded properties or be entirely
        custom. You should refer to existing model_animation_graph tags for more information. Examples include: 'idle' for 
        animations that should play when the object is inactive, 'move-left', 'move-front' for moving. 'put-away' for
        an animation that should play when putting away a weapon. Must not be empty"""
        )

    destination_mode : bpy.props.StringProperty(
        name="Destination Mode",
        description="The mode to put this object in when it finishes this animation. Can be empty"
    )
    destination_state : bpy.props.StringProperty(
        name="Destination State",
        description="The state to put this object in when it finishes this animation. Must not be empty"
    )

    damage_power : bpy.props.EnumProperty(
        name="Power",
        items=[
            ("hard", "Hard", ""),
            ("soft", "Soft", ""),
        ]
    )
    damage_type : bpy.props.EnumProperty(
        name="Type",
        items=[
            ("ping", "Ping", ""),
            ("kill", "Kill", ""),
        ]
    )
    damage_direction : bpy.props.EnumProperty(
        name="Direction",
        items=[
            ("front", "Front", ""),
            ("left", "Left", ""),
            ("right", "Right", ""),
            ("back", "Back", ""),
        ]
    )
    damage_region : bpy.props.EnumProperty(
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
        ]
    )

    variant : bpy.props.IntProperty(min=0, soft_max=3, name="Variant", 
            description="""The variation of this animation. Variations can have different weightings
            to determine whether they play. 0 = no variation
                                    """)

    custom : bpy.props.StringProperty(name="Custom")

    fp_animation : bpy.props.BoolProperty()

    def __init__(self):
        self.fp_animation = poll_ui("FP ANIMATION")
        if self.fp_animation:
            self.mode = "first_person"

    def execute(self, context):
        full_name = self.create_name()
        # Create the animation
        animation = bpy.data.actions.new(full_name)
        animation.use_frame_range = True
        animation.use_fake_user = True
        animation.frame_start = self.frame_start
        animation.frame_end = self.frame_end
        ob = context.object
        ob.animation_data_create()
        ob.animation_data.action = animation
        nwo = animation.nwo
        nwo.animation_type = self.animation_type
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

        self.report({'INFO'}, f"Created animation: {full_name}")
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "frame_start", text="First Frame")
        layout.prop(self, "frame_end", text="Last Frame")
        layout.label(text="Animation Type")
        layout.prop(self, "animation_type", text="")
        layout.separator()
        self.draw_name(layout)

    def draw_name(self, layout):
        if self.fp_animation:
            layout.label(text="* Denotes required fields")
            layout.prop(self, "state", text="*State")
            layout.prop(self, "variant")
        else:
            layout.label(text="Animation State Type")
            layout.prop(self, "state_type", text="")
            layout.label(text="* Denotes required fields")
            is_damage = self.state_type == "damage"
            col = layout.column()
            col.use_property_split = True
            if self.state_type == "custom":
                col.prop(self, "custom")
            else:
                col.prop(self, "mode")
                col.prop(self, "weapon_class")
                col.prop(self, "weapon_type")
                col.prop(self, "set")
                if not is_damage:
                    col.prop(self, "state", text="*State")

                if self.state_type == "transition":
                    col.prop(self, "destination_mode")
                    col.prop(self, "destination_state", text="*Destination State")
                elif is_damage:
                    col.prop(self, "damage_power")
                    col.prop(self, "damage_type")
                    col.prop(self, "damage_direction")
                    col.prop(self, "damage_region")
                
                col.prop(self, "variant")

    def create_name(self):
        bad_chars = ' :_,-'
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
        if self.state_type != 'custom':
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
                self.report({'WARNING'}, "No state defined. Setting to idle")
                full_name += f" idle"

            if is_transition:
                if destination_mode:
                    full_name += f" {destination_mode}"
                else:
                    full_name += f" any"

                if destination_state:
                    full_name += f" {destination_state}"
                else:
                    self.report({'WARNING'}, "No destination state defined. Setting to idle")
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
                self.report({'WARNING'}, "Animation name empty. Setting to idle")
                full_name = "idle"

        return full_name.lower().strip(bad_chars)

class NWO_List_Add_Animation_Rename(NWO_NewAnimation):
    bl_label = "New Animation Rename"
    bl_idname = "nwo.animation_rename_add"
    bl_description = "Creates a new Halo Animation Rename"

    def __init__(self):
        action = bpy.context.object.animation_data.action
        nwo = action.nwo
        state = nwo.state.lower().strip(' :_,-')
        state = "idle" if state == "" else state
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
            self.custom = action.name

    def draw(self, context):
        self.draw_name(self.layout)

    def execute(self, context):
        full_name = self.create_name()
        action = context.active_object.animation_data.action
        nwo = action.nwo
        if full_name == action.name:
            self.report({'WARNING'}, f"Rename entry not created. Rename cannot match animation name")
            return {'CANCELLED'}
        
        # Create the rename
        bpy.ops.uilist.entry_add(
            list_path="object.animation_data.action.nwo.animation_renames",
            active_index_path="object.animation_data.action.nwo.animation_renames_index",
        )
        rename = nwo.animation_renames[nwo.animation_renames_index]
        rename.rename_name = full_name
        context.area.tag_redraw()

        self.report({'INFO'}, f"Created rename: {full_name}")
        return {'FINISHED'}
    
class NWO_List_Remove_Animation_Rename(NWO_Op):
    """Remove an Item from the UIList"""
    bl_idname = "nwo.animation_rename_remove"
    bl_label = "Remove"
    bl_description = "Remove an animation event from the list."

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "ARMATURE"
            and context.object.animation_data
            and context.object.animation_data.action
            and len(context.object.animation_data.action.nwo.animation_renames)
            > 0
        )

    def execute(self, context):
        action = context.active_object.animation_data.action
        nwo = action.nwo
        nwo.animation_renames.remove(nwo.animation_renames_index)
        if nwo.animation_renames_index > len(nwo.animation_renames) - 1:
            nwo.animation_renames_index += -1
        return {"FINISHED"}
    
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
        layout.prop(item, "rename_name", text="")
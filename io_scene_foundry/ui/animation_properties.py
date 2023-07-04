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

from bpy.types import PropertyGroup, Panel, UIList, Operator
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    CollectionProperty,
    IntProperty,
    FloatProperty,
)
import random
import bpy

from io_scene_foundry.icons import get_icon_id

from ..utils.nwo_utils import dot_partition


class NWO_UL_AnimProps_Events(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname
    ):
        animation = item
        if animation:
            layout.prop(animation, "name", text="", emboss=False, icon_value=get_icon_id("animation_event"))
        else:
            layout.label(text="", translate=False, icon_value=icon)

    # def draw_item(self, _context, layout, _data, item, icon, _active_data, _active_propname, _index):
    #     if self.layout_type in {'DEFAULT', 'COMPACT'}:
    #         layout.prop(item, "name", text="", emboss=False, icon='GROUP_UVS')
    #         icon = 'RESTRICT_RENDER_OFF' if item.active_render else 'RESTRICT_RENDER_ON'
    #         layout.prop(item, "active_render", text="", icon=icon, emboss=False)
    #     elif self.layout_type == 'GRID':
    #         layout.alignment = 'CENTER'
    #         layout.label(text="", icon_value=icon)


#############################################################
# ANIMATION RENAMES
#############################################################


class NWO_AnimationRenamesItems(PropertyGroup):
    rename_name: StringProperty(name="Name")


#############################################################
# ANIMATION EVENTS
#############################################################


class NWO_List_Add_Animation_Event(Operator):
    """Add an Item to the UIList"""

    bl_idname = "animation_event.list_add"
    bl_label = "Add"
    bl_description = "Add a new animation event to the list."
    filename_ext = ""
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "ARMATURE"
            and context.object.animation_data
            and context.object.animation_data.action
        )

    def execute(self, context):
        action = context.active_object.animation_data.action
        nwo = action.nwo
        bpy.ops.uilist.entry_add(
            list_path="object.animation_data.action.nwo.animation_events",
            active_index_path="object.animation_data.action.nwo.animation_events_index",
        )
        event = nwo.animation_events[nwo.animation_events_index]
        event.frame_frame = context.scene.frame_current
        event.event_id = random.randint(0, 2147483647)
        event.name = f"event_{len(nwo.animation_events)}"

        context.area.tag_redraw()

        return {"FINISHED"}


class NWO_List_Remove_Animation_Event(Operator):
    """Remove an Item from the UIList"""

    bl_idname = "animation_event.list_remove"
    bl_label = "Remove"
    bl_description = "Remove an animation event from the list."
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.object
            and context.object.type == "ARMATURE"
            and context.object.animation_data
            and context.object.animation_data.action
            and len(context.object.animation_data.action.nwo.animation_events) > 0
        )

    def execute(self, context):
        action = context.active_object.animation_data.action
        action_nwo = action.nwo
        index = action_nwo.animation_events_index
        action_nwo.animation_events.remove(index)
        return {"FINISHED"}


class NWO_Animation_ListItems(PropertyGroup):
    event_id: IntProperty()

    multi_frame: EnumProperty(
        name="Usage",
        description="Toggle whether this animation event should trigger on a single frame, or occur over a range",
        default="single",
        options=set(),
        items=[("single", "Single", ""), ("range", "Range", "")],
    )

    frame_range: IntProperty(
        name="Frame Range",
        description="Enter the number of frames this event should last",
        default=1,
        min=1,
        soft_max=10,
    )

    name: StringProperty(
        name="Event Name",
        default="new_event",
    )

    event_type: EnumProperty(
        name="Type",
        default="_connected_geometry_animation_event_type_frame",
        options=set(),
        items=[
            ("_connected_geometry_animation_event_type_custom", "Custom", ""),
            ("_connected_geometry_animation_event_type_loop", "Loop", ""),
            ("_connected_geometry_animation_event_type_sound", "Sound", ""),
            ("_connected_geometry_animation_event_type_effect", "Effect", ""),
            (
                "_connected_geometry_animation_event_type_ik_active",
                "IK Active",
                "",
            ),
            (
                "_connected_geometry_animation_event_type_ik_passive",
                "IK Passive",
                "",
            ),
            ("_connected_geometry_animation_event_type_text", "Text", ""),
            (
                "_connected_geometry_animation_event_type_wrinkle_map",
                "Wrinkle Map",
                "",
            ),
            (
                "_connected_geometry_animation_event_type_footstep",
                "Footstep",
                "",
            ),
            (
                "_connected_geometry_animation_event_type_cinematic_effect",
                "Cinematic Effect",
                "",
            ),
            (
                "_connected_geometry_animation_event_type_object_function",
                "Object Function",
                "",
            ),
            ("_connected_geometry_animation_event_type_frame", "Frame", ""),
            ("_connected_geometry_animation_event_type_import", "Import", ""),
        ],
    )

    frame_start: FloatProperty(
        name="Frame Start",
        default=0,
        options=set(),
    )

    frame_end: FloatProperty(
        name="Frame End",
        default=0,
        options=set(),
    )

    wrinkle_map_face_region: StringProperty(
        name="Wrinkle Map Face Region",
        default="",
        options=set(),
    )

    wrinkle_map_effect: IntProperty(
        name="Wrinkle Map Effect",
        default=0,
        options=set(),
    )

    footstep_type: StringProperty(
        name="Footstep Type",
        default="",
        options=set(),
    )

    footstep_effect: IntProperty(
        name="Footstep Effect",
        default=0,
        options=set(),
    )

    ik_chain: StringProperty(
        name="IK Chain",
        default="",
        options=set(),
    )

    ik_active_tag: StringProperty(
        name="IK Active Tag",
        default="",
        options=set(),
    )

    ik_target_tag: StringProperty(
        name="IK Target Tag",
        default="",
        options=set(),
    )

    ik_target_marker: StringProperty(
        name="IK Target Marker",
        default="",
        options=set(),
    )

    ik_target_usage: StringProperty(
        name="IK Target Usage",
        default="",
        options=set(),
    )

    ik_proxy_target_id: IntProperty(
        name="IK Proxy Target ID",
        default=0,
        options=set(),
    )

    ik_pole_vector_id: IntProperty(
        name="IK Pole Vector ID",
        default=0,
        options=set(),
    )

    ik_effector_id: IntProperty(
        name="IK Effector ID",
        default=0,
        options=set(),
    )

    cinematic_effect_tag: StringProperty(
        name="Cinematic Effect Tag",
        default="",
        options=set(),
    )

    cinematic_effect_effect: IntProperty(
        name="Cinematic Effect",
        default=0,
        options=set(),
    )

    cinematic_effect_marker: StringProperty(
        name="Cinematic Effect Marker",
        default="",
        options=set(),
    )

    object_function_name: StringProperty(
        name="Object Function Name",
        default="",
        options=set(),
    )

    object_function_effect: IntProperty(
        name="Object Function Effect",
        default=0,
        options=set(),
    )

    frame_frame: IntProperty(
        name="Event Frame",
        default=0,
        options=set(),
    )

    frame_name: EnumProperty(
        name="Frame Name",
        default="primary keyframe",
        options=set(),
        items=[
            ("none", "None", ""),
            ("primary keyframe", "Primary Keyframe", ""),
            ("secondary keyframe", "Secondary Keyframe", ""),
            ("tertiary keyframe", "Tertiary Keyframe", ""),
            ("left foot", "Left Foot", ""),
            ("right foot", "Right Foot", ""),
            ("allow interruption", "Allow Interruption", ""),
            ("do not allow interruption", "Do Not Allow Interruption", ""),
            ("both-feet shuffle", "Both-Feet Shuffle", ""),
            ("body impact", "Body Impact", ""),
            ("left foot lock", "Left Foot Lock", ""),
            ("left foot unlock", "Left Foot Unlock", ""),
            ("right foot lock", "Right Foot Lock", ""),
            ("right foot unlock", "Right Foot Unlock", ""),
            ("blend range marker", "Blend Range Marker", ""),
            ("stride expansion", "Stride Expansion", ""),
            ("stride contraction", "Stride Contraction", ""),
            ("ragdoll keyframe", "Ragdoll Keyframe", ""),
            ("drop weapon keyframe", "Drop Weapon Keyframe", ""),
            ("match a", "Match A", ""),
            ("match b", "Match B", ""),
            ("match c", "Match C", ""),
            ("match d", "Match D", ""),
            ("jetpack closed", "Jetpack Closed", ""),
            ("jetpack open", "Jetpack Open", ""),
            ("sound event", "Sound Event", ""),
            ("effect event", "Effect Event", ""),
        ],
    )

    frame_trigger: BoolProperty(
        name="Frame Trigger",
        default=False,
        options=set(),
    )

    import_frame: IntProperty(
        name="Import Frame",
        default=0,
        options=set(),
    )

    import_name: StringProperty(
        name="Import Name",
        default="",
        options=set(),
    )

    text: StringProperty(
        name="Text",
        default="",
        options=set(),
    )


class NWO_ActionPropertiesGroup(PropertyGroup):
    def update_name_override(self, context):
        if self.name_override.rpartition(".")[2] != self.animation_type:
            match self.name_override.rpartition(".")[2].upper():
                case "JMA":
                    self.animation_type = "JMA"
                case "JMT":
                    self.animation_type = "JMT"
                case "JMZ":
                    self.animation_type = "JMZ"
                case "JMV":
                    self.animation_type = "JMV"
                case "JMO":
                    self.animation_type = "JMO"
                case "JMOX":
                    self.animation_type = "JMOX"
                case "JMR":
                    self.animation_type = "JMR"
                case "JMRX":
                    self.animation_type = "JMRX"
                case _:
                    self.animation_type = "JMM"

    name_override: StringProperty(
        name="Name Override",
        # update=update_name_override,
        description="Overrides the action name when setting exported animation name. Use this if the action field is too short for your animation name",
        default="",
    )

    export_this: BoolProperty(
        name="Export",
        default=True,
        description="Controls whether this animation is exported or not",
        options=set(),
    )

    def update_animation_type(self, context):
        action_name = (
            str(self.id_data.name)
            if self.id_data.nwo.name_override == ""
            else str(self.id_data.nwo.name_override)
        )
        action_name = dot_partition(action_name)
        action_name = f"{action_name}.{self.animation_type}"
        if self.id_data.nwo.name_override != "":
            self.id_data.nwo.name_override = action_name
        else:
            if self.id_data.name.rpartition(".")[0] != "":
                self.id_data.name = action_name
        # Set the name override if the action name is out of characters
        if (
            dot_partition(action_name) != dot_partition(self.id_data.name)
            and self.id_data.nwo.name_override == ""
        ):
            self.id_data.nwo.name_override = action_name
            self.id_data.name = dot_partition(self.id_data.name)

    animation_type: EnumProperty(
        name="Type",
        # update=update_animation_type,
        description="Set the type of Halo animation you want this action to be.",
        default="JMM",
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

    animation_events: CollectionProperty(
        type=NWO_Animation_ListItems,
    )

    animation_events_index: IntProperty(
        name="Index for Animation Event",
        default=0,
        min=0,
    )

    animation_renames: CollectionProperty(
        type=NWO_AnimationRenamesItems,
    )

    animation_renames_index: IntProperty(
        name="Index for Animation Event",
        default=0,
        min=0,
    )

    # NOT VISIBLE TO USER, USED FOR ANIMATION RENAMES
    state_type: EnumProperty(
        name="State Type",
        items=[
            ("action", "Action / Overlay", ""),
            ("transition", "Transition", ""),
            ("damage", "Death & Damage", ""),
            ("custom", "Custom", ""),
        ],
    )

    mode: StringProperty(
        name="Mode",
        description="""The mode the object must be in to use this animation. Use 'any' for all modes. Other valid
        inputs inlcude but are not limited to: 'crouch' when a unit is crouching, 
        'combat' when a unit is in combat. Modes can also refer
        to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more
        information refer to existing model_animation_graph tags. Can be empty""",
    )

    weapon_class: StringProperty(
        name="Weapon Class",
        description="""The weapon class this unit must be holding to use this animation. Weapon class is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty""",
    )
    weapon_type: StringProperty(
        name="Weapon Name",
        description="""The weapon type this unit must be holding to use this animation.  Weapon name is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty""",
    )
    set: StringProperty(
        name="Set", description="The set this animtion is a part of. Can be empty"
    )
    state: StringProperty(
        name="State",
        description="""The state this animation plays in. States can refer to hardcoded properties or be entirely
        custom. You should refer to existing model_animation_graph tags for more information. Examples include: 'idle' for 
        animations that should play when the object is inactive, 'move-left', 'move-front' for moving. 'put-away' for
        an animation that should play when putting away a weapon. Must not be empty""",
    )

    destination_mode: StringProperty(
        name="Destination Mode",
        description="The mode to put this object in when it finishes this animation. Can be empty",
    )
    destination_state: StringProperty(
        name="Destination State",
        description="The state to put this object in when it finishes this animation. Must not be empty",
    )

    damage_power: EnumProperty(
        name="Power",
        items=[
            ("hard", "Hard", ""),
            ("soft", "Soft", ""),
        ],
    )
    damage_type: EnumProperty(
        name="Type",
        items=[
            ("ping", "Ping", ""),
            ("kill", "Kill", ""),
        ],
    )
    damage_direction: EnumProperty(
        name="Direction",
        items=[
            ("front", "Front", ""),
            ("left", "Left", ""),
            ("right", "Right", ""),
            ("back", "Back", ""),
        ],
    )
    damage_region: EnumProperty(
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

    variant: IntProperty(
        min=0,
        soft_max=3,
        name="Variant",
        description="""The variation of this animation. Variations can have different weightings
            to determine whether they play. 0 = no variation
                                    """,
    )

    custom: StringProperty(name="Custom")

    created_with_foundry: BoolProperty()

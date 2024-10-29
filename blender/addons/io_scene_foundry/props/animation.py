import bpy
from ..utils import is_marker

#############################################################
# ANIMATION RENAMES
#############################################################


class NWO_AnimationRenamesItems(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")


#############################################################
# ANIMATION EVENTS
#############################################################

class NWO_Animation_ListItems(bpy.types.PropertyGroup):
    event_id: bpy.props.IntProperty()

    multi_frame: bpy.props.EnumProperty(
        name="Usage",
        description="Toggle whether this animation event should trigger on a single frame, or occur over a range",
        default="single",
        options=set(),
        items=[("single", "Single", ""), ("range", "Range", "")],
    )
    
    def update_frame_range(self, context):
        if self.frame_range < self.frame_frame:
            self.frame_range = self.frame_frame

    frame_range: bpy.props.IntProperty(
        name="Frame Range",
        description="Enter the number of frames this event should last",
        default=1,
        update=update_frame_range,
    )

    name: bpy.props.StringProperty(
        name="Event Name",
        default="new_event",
    )
    
    event_type: bpy.props.EnumProperty(
        name="Type",
        options=set(),
        items=[
            ("_connected_geometry_animation_event_type_frame", "Frame", ""),
            # NOTE temp commenting these out until I can figure out how to implement them correctly
            # ("_connected_geometry_animation_event_type_object_function", "Object Function", ""),
            # ("_connected_geometry_animation_event_type_import", "Import", ""),
            ("_connected_geometry_animation_event_type_wrinkle_map", "Wrinkle Map", ""),
            ("_connected_geometry_animation_event_type_ik_active", "IK Active", ""),
            ("_connected_geometry_animation_event_type_ik_passive", "IK Passive", ""),
        ]
    )

    # event_type: bpy.props.EnumProperty(
    #     name="Type",
    #     default="_connected_geometry_animation_event_type_frame",
    #     options=set(),
    #     items=[
            # ("_connected_geometry_animation_event_type_custom", "Custom", ""),
            # ("_connected_geometry_animation_event_type_loop", "Loop", ""),
            # ("_connected_geometry_animation_event_type_sound", "Sound", ""),
            # ("_connected_geometry_animation_event_type_effect", "Effect", ""),
            # ("_connected_geometry_animation_event_type_text", "Text", ""),
            # (
            #     "_connected_geometry_animation_event_type_footstep",
            #     "Footstep",
            #     "",
            # ),
            # (
            #     "_connected_geometry_animation_event_type_cinematic_effect",
            #     "Cinematic Effect",
            #     "",
            # ),
            
    #     ],
    # )
    #     items=[
    #         ("frame", "Frame", ""),
    #         ("trigger", "Frame", ""),
    #         ("navigation", "Frame", ""),
    #         ("sync_action", "Frame", ""),
    #         ("sound", "Frame", ""),
    #         ("effect", "Frame", ""),
    #         ("cinematic_effect", "Frame", ""),
    #         ("object_function", "Frame", ""),
    #         ("wrinkle_map", "Frame", ""),
    #         ("ik_active", "Frame", ""),
    #         ("ik_passive", "Frame", ""),
    #     ]
    # )

    # TODO
    # Revised event list = sound, effect, import, trigger, navigation, sync action, ik active, ik passive, wrinkle map, object function, cinematic effect

    # non_sound_frame_types = ['primary keyframe', 
    #                'secondary keyframe', 
    #                'tertiary keyframe',                    
    #                'allow interruption',                   
    #                'blend range marker',
    #                'stride expansion',
    #                'stride contraction',
    #                'ragdoll keyframe',
    #                'drop weapon keyframe',
    #                'match a',
    #                'match b',
    #                'match c',
    #                'match d',
    #                'right foot lock',
    #                'right foot unlock',
    #                'left foot lock',
    #                'left foot unlock']
    # sound_frame_types = ['left foot', 'right foot', 'both-feet shuffle', 'body impact']
    # import_event_types = ['Wrapped Left', 'Wrapped Right']    
    # frame_event_types = { 'Trigger Events':['primary keyframe', 'secondary keyframe', 'tertiary keyframe'],
    #                       'Navigation Events':['match a', 'match b', 'match c', 'match d', 'stride expansion',
    #                                            'stride contraction', 'right foot lock', 'right foot unlock', 'left foot lock',
    #                                            'left foot unlock'],
    #                       'Sync Action Events':['ragdoll keyframe', 'drop weapon keyframe', 'allow interruption', 'blend range marker'],
    #                       'Sound Events':['left foot', 'right foot', 'body impact', 'both-feet shuffle'],
    #                       'Import Events':['Wrapped Left', 'Wrapped Right']}

    frame_start: bpy.props.FloatProperty(
        name="Frame Start",
        default=0,
        options=set(),
    )

    frame_end: bpy.props.FloatProperty(
        name="Frame End",
        default=0,
        options=set(),
    )

    wrinkle_map_face_region: bpy.props.EnumProperty(
        name="Wrinkle Map Face Region",
        options=set(),
        items=[
            ('Upper Brow', 'Upper Brow', ''),
            ('Center Brow', 'Center Brow', ''),
            ('Left Squint', 'Left Squint', ''),
            ('Right Squint', 'Right Squint', ''),
            ('Right Smile', 'Right Smile', ''),
            ('Left Smile', 'Left Smile', ''),
            ('Right Sneer', 'Right Sneer', ''),
            ('Left Sneer', 'Left Sneer', ''),
        ]
    )

    wrinkle_map_effect: bpy.props.FloatProperty(
        name="Wrinkle Map Effect",
        default=1,
        options=set(),
    )

    footstep_type: bpy.props.StringProperty(
        name="Footstep Type",
        default="",
        options=set(),
    )

    footstep_effect: bpy.props.IntProperty(
        name="Footstep Effect",
        default=0,
        options=set(),
    )
    
    def ik_chain_items(self, context):
        items = []
        items.append(("none", "None", ''))
        valid_chains = [chain for chain in context.scene.nwo.ik_chains if chain.start_node and chain.effector_node]
        for chain in valid_chains:
            items.append((chain.name, chain.name, ''))
            
        return items

    ik_chain: bpy.props.EnumProperty(
        name="IK Chain",
        options=set(),
        items=ik_chain_items,
    )

    ik_active_tag: bpy.props.StringProperty(
        name="IK Active Tag",
        default="",
        options=set(),
    )

    ik_target_tag: bpy.props.StringProperty(
        name="IK Target Tag",
        default="",
        options=set(),
    )
    
    def poll_ik_target_marker(self, object):
        return is_marker(object) and object.nwo.marker_type == '_connected_geometry_marker_type_model'
    
    ik_target_marker: bpy.props.PointerProperty(
        name="Proxy Target",
        type=bpy.types.Object,
        # poll=poll_ik_target_marker,
        options=set(),
    )
    
    ik_target_marker_name_override: bpy.props.StringProperty(
        name="Target Marker Name",
        description="Name of the in game marker to use as the IK target. If left blank, the name of the proxy target will be used",
        options=set(),
    )

    ik_target_usage: bpy.props.EnumProperty(
        name="Target Usage",
        options=set(),
        items=[
            # ('world', 'World', ''),
            ('self', 'Self', ''),
            ('primary_weapon', 'Primary Weapon', ''),
            ('secondary_weapon', 'Secondary Weapon', ''),
            ('parent', 'Parent', ''),
            ('assassination', 'Assassination', ''),
        ]
    )
    
    ik_influence: bpy.props.FloatProperty(
        name="Influence",
        options=set(),
        default=1,
        min=0,
        max=1,
        subtype='FACTOR',
    )

    ik_proxy_target_id: bpy.props.IntProperty(
        name="IK Proxy Target ID",
        default=0,
        options={'HIDDEN'},
    )

    ik_pole_vector_id: bpy.props.IntProperty(
        name="IK Pole Vector ID",
        default=0,
        options={'HIDDEN'},
    )

    ik_effector_id: bpy.props.IntProperty(
        name="IK Effector ID",
        default=0,
        options={'HIDDEN'},
    )
    
    ik_pole_vector: bpy.props.PointerProperty(
        name="Pole Target",
        type=bpy.types.Object,
        description="Pole target for this IK to use. Optional",
        options=set(),
    )

    cinematic_effect_tag: bpy.props.StringProperty(
        name="Cinematic Effect Tag",
        default="",
        options=set(),
    )

    cinematic_effect_effect: bpy.props.IntProperty(
        name="Cinematic Effect",
        default=0,
        options=set(),
    )

    cinematic_effect_marker: bpy.props.StringProperty(
        name="Cinematic Effect Marker",
        default="",
        options=set(),
    )

    object_function_name: bpy.props.EnumProperty(
        name="Object Function Name",
        options=set(),
        items=[
            ('animation_object_function_a', 'A', ''),
            ('animation_object_function_b', 'B', ''),
            ('animation_object_function_c', 'C', ''),
            ('animation_object_function_d', 'D', ''),
        ]
    )

    object_function_effect: bpy.props.FloatProperty(
        name="Object Function Effect",
        default=1,
        options=set(),
    )

    frame_frame: bpy.props.IntProperty(
        name="Event Frame",
        description="The timeline frame this event should occur on",
        default=0,
        options=set(),
        update=update_frame_range,
    )

    frame_name: bpy.props.EnumProperty(
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
            # ("jetpack closed", "Jetpack Closed", ""),
            # ("jetpack open", "Jetpack Open", ""),
            # ("sound event", "Sound Event", ""),
            # ("effect event", "Effect Event", ""),
        ],
    )

    frame_trigger: bpy.props.BoolProperty(
        name="Frame Trigger",
        default=False,
        options=set(),
    )

    import_frame: bpy.props.IntProperty(
        name="Import Frame",
        default=0,
        options=set(),
    )

    import_name: bpy.props.StringProperty(
        name="Import Name",
        default="",
        options=set(),
    )

    # TODO
    # IMPORT NAMES: "Wrapped Left", "Wrapped Right"

    text: bpy.props.StringProperty(
        name="Text",
        default="",
        options=set(),
    )


class NWO_ActionPropertiesGroup(bpy.types.PropertyGroup):
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

    name_override: bpy.props.StringProperty(
        name="Name Override",
        # update=update_name_override,
        description="If this field is not empty, the exporter will use the animation given here instead of relying on the action name. Use this if the action name field is too short for your animation name",
        default="",
    )

    export_this: bpy.props.BoolProperty(
        name="Export",
        default=True,
        description="Controls whether this animation is exported or not",
        options=set(),
    )

    compression : bpy.props.EnumProperty(
        name="Compression",
        description="Level of compression to apply to animations",
        items=[
            ("Default", "Default", "Animation compression is determined by the value set in the asset editor panel"),
            ("Uncompressed", "Uncompressed", "No compression"),
            ("Medium", "Medium", "Medium compression"),
            ("Rough", "Rough", "Highest level of compression"),
        ],
    )

    def animation_type_items(self, context):
        items = [
            (
                "base",
                "Base",
                "Defines a base animation. Allows for varying levels of root bone movement (or none). Useful for cinematic animations, idle animations, turn and movement animations",
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
            (
                "world",
                "World",
                "Animations that play relative to the world rather than an objects current position",
                '',
                3,
            )
        ]
        # NOTE Need to add support for composites
        # items.append(
        # (
        #     "composite",
        #     "Composite",
        #     "",
        # ))
        # items.append(
        # (
        #     "composite_overlay",
        #     "Composite Overlay",
        #     "",
        # ))
        
        return items
    
    def get_animation_type(self):
        max_int = 3
        # if is_corinth():
        #     max_int = 5
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
        description='Set how this animation moves the object in worldspace',
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

    animation_events: bpy.props.CollectionProperty(
        type=NWO_Animation_ListItems,
    )

    animation_events_index: bpy.props.IntProperty(
        name="Index for Animation Event",
        default=0,
        min=0,
    )

    animation_renames: bpy.props.CollectionProperty(
        type=NWO_AnimationRenamesItems,
    )

    animation_renames_index: bpy.props.IntProperty(
        name="Index for Animation Renames",
        default=0,
        min=0,
    )

    # NOT VISIBLE TO USER, USED FOR ANIMATION RENAMES
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
        description="""The mode the object must be in to use this animation. Use 'any' for all modes. Other valid
        inputs inlcude but are not limited to: 'crouch' when a unit is crouching, 
        'combat' when a unit is in combat. Modes can also refer
        to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more
        information refer to existing model_animation_graph tags. Can be empty""",
    )

    weapon_class: bpy.props.StringProperty(
        name="Weapon Class",
        description="""The weapon class this unit must be holding to use this animation. Weapon class is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty""",
    )
    weapon_type: bpy.props.StringProperty(
        name="Weapon Name",
        description="""The weapon type this unit must be holding to use this animation.  Weapon name is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty""",
    )
    set: bpy.props.StringProperty(
        name="Set", description="The set this animtion is a part of. Can be empty"
    )
    state: bpy.props.StringProperty(
        name="State",
        description="""The state this animation plays in. States can refer to hardcoded properties or be entirely
        custom. You should refer to existing model_animation_graph tags for more information. Examples include: 'idle' for 
        animations that should play when the object is inactive, 'move-left', 'move-front' for moving. 'put-away' for
        an animation that should play when putting away a weapon. Must not be empty""",
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

    created_with_foundry: bpy.props.BoolProperty(options={'HIDDEN'})

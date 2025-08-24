from math import radians
from pathlib import Path
import bpy
from bpy.types import PropertyGroup
from mathutils import Matrix

from ..tools.asset_types import asset_type_items
from ..managed_blam.scenario import ScenarioTag

from ..icons import get_icon_id
from .. import utils

script_object_types = ('WEAPON_TRIGGER_START', 'WEAPON_TRIGGER_STOP', 'SET_VARIANT', 'SET_PERMUTATION', 'SET_REGION_STATE', 'SET_MODEL_STATE_PROPERTY', 'HIDE', 'UNHIDE', 'DESTROY', 'OBJECT_CANNOT_DIE', 'OBJECT_CAN_DIE', 'OBJECT_PROJECTILE_COLLISION_ON', 'OBJECT_PROJECTILE_COLLISION_OFF', 'DAMAGE_OBJECT')


def poll_armature(self, object: bpy.types.Object):
    return object.type == 'ARMATURE'

def poll_empty(self, object: bpy.types.Object):
    return object.type == 'EMPTY'

#############################################################
# ANIMATION COPIES
#############################################################

class NWO_AnimationCopiesItems(PropertyGroup):
    name: bpy.props.StringProperty(name="Copy Name", options=set())
    source_name: bpy.props.StringProperty(name="Source Name", options=set())

#############################################################
# ANIMATION COMPOSITES
#############################################################

class NWO_AnimationLeavesItems(PropertyGroup):
    animation: bpy.props.StringProperty(name="Animation")
    # animation: bpy.props.PointerProperty(name="Animation", type=bpy.types.Action)
    
    manual_blend_axis_1: bpy.props.BoolProperty(
        name="Manual Blend Axis 1",
        description="Manually assign a value to this blend axix instead of allowing it to be calculated"
    )
    manual_blend_axis_2: bpy.props.BoolProperty(
        name="Manual Blend Axis 2",
        description="Manually assign a value to this blend axix instead of allowing it to be calculated"
    )
    blend_axis_1: bpy.props.FloatProperty(
        name="Blend Axis Value 1",
        description="Value of this blend axis"
    )
    blend_axis_2: bpy.props.FloatProperty(
        name="Blend Axis Value 2",
        description="Value of this blend axis"
    )
    
class NWO_AnimationGroupItems(PropertyGroup):
    name: bpy.props.StringProperty(name="Name", options=set())
    manual_blend_axis_1: bpy.props.BoolProperty(
        name="Manual Blend Axis 1",
        description="Manually assign a value to this blend axix instead of allowing it to be calculated"
    )
    manual_blend_axis_2: bpy.props.BoolProperty(
        name="Manual Blend Axis 2",
        description="Manually assign a value to this blend axix instead of allowing it to be calculated"
    )
    blend_axis_1: bpy.props.FloatProperty(
        name="Blend Axis Value 1",
        description="Value of this blend axis"
    )
    blend_axis_2: bpy.props.FloatProperty(
        name="Blend Axis Value 2",
        description="Value of this blend axis"
    )
    leaves_active_index: bpy.props.IntProperty(options=set())
    leaves: bpy.props.CollectionProperty(name="Animations", options=set(), type=NWO_AnimationLeavesItems)
    
class NWO_AnimationPhaseSetsItems(PropertyGroup):
    name: bpy.props.StringProperty(name="Name", options=set())
    priority: bpy.props.EnumProperty(
        name="Priority",
        options=set(),
        items=[
            ("default", "Default", ""),
            ("current", "Current", ""),
            ("cycle", "Cycle", ""),
            ("alternate", "Alternate", ""),
        ]
    )
    leaves_active_index: bpy.props.IntProperty(options=set())
    leaves: bpy.props.CollectionProperty(name="Animations", options=set(), type=NWO_AnimationLeavesItems)
    
    key_primary_keyframe: bpy.props.BoolProperty(name="Primary Keyframe", options=set())
    key_secondary_keyframe: bpy.props.BoolProperty(name="Secondary Keyframe", options=set())
    key_tertiary_keyframe: bpy.props.BoolProperty(name="Tertiary Keyframe", options=set())
    key_left_foot: bpy.props.BoolProperty(name="Left Foot", options=set())
    key_right_foot: bpy.props.BoolProperty(name="Right Foot", options=set())
    key_body_impact: bpy.props.BoolProperty(name="Body Impact", options=set())
    key_left_foot_lock: bpy.props.BoolProperty(name="Left Foot Lock", options=set())
    key_left_foot_unlock: bpy.props.BoolProperty(name="Left Foot Unlock", options=set())
    key_right_foot_lock: bpy.props.BoolProperty(name="Right Foot Lock", options=set())
    key_right_foot_unlock: bpy.props.BoolProperty(name="Right Foot Unlock", options=set())
    key_blend_range_marker: bpy.props.BoolProperty(name="Blend Range Marker", options=set())
    key_stride_expansion: bpy.props.BoolProperty(name="Stride Expansion", options=set())
    key_stride_contraction: bpy.props.BoolProperty(name="Stride Contraction", options=set())
    key_ragdoll_keyframe: bpy.props.BoolProperty(name="Ragdoll Keyframe", options=set())
    key_drop_weapon_keyframe: bpy.props.BoolProperty(name="Drop Weapon Keyframe", options=set())
    key_match_a: bpy.props.BoolProperty(name="Match A", options=set())
    key_match_b: bpy.props.BoolProperty(name="Match B", options=set())
    key_match_c: bpy.props.BoolProperty(name="Match C", options=set())
    key_match_d: bpy.props.BoolProperty(name="Match D", options=set())
    key_jetpack_closed: bpy.props.BoolProperty(name="Jetpack Closed", options=set())
    key_jetpack_open: bpy.props.BoolProperty(name="Jetpack Open", options=set())
    key_sound_event: bpy.props.BoolProperty(name="Sound Event", options=set())
    key_effect_event: bpy.props.BoolProperty(name="Effect Event", options=set())

class NWO_AnimationDeadZonesItems(PropertyGroup):
    name: bpy.props.StringProperty(name="Name")
    bounds: bpy.props.FloatVectorProperty(name="Dead Zone Bounds", options=set(), size=2, subtype='COORDINATES', min=0)
    rate: bpy.props.FloatProperty(name="Dead Zone Rate", options=set(), min=0, default=90)

class NWO_AnimationSubBlendAxisItems(PropertyGroup):
    name: bpy.props.EnumProperty(
        name="Type",
        options=set(),
        description="What kind of data this composite relies on",
        items=[
            ("movement_angles", "Movement Angles", ""), # linear_movement_angle get_move_angle
            ("movement_speed", "Movement Speed", ""), # linear_movement_speed get_move_speed
            ("turn_rate", "Turn Rate", ""), # average_angular_rate get_turn_rate
            ("turn_angle", "Turn Angle", ""), # total_angular_offset get_turn_angle
            ("vertical", "Vertical", ""), # translation_offset_z get_destination_vertical
            ("horizontal", "Horizontal", ""), # translation_offset_horizontal get_destination_forward
        ]
    )
    
    animation_source_bounds_manual: bpy.props.BoolProperty(name="Animation Manual Bounds", options=set(), description="Manually define the bounds of the animation axis")
    animation_source_bounds: bpy.props.FloatVectorProperty(name="Animation Source Bounds", options=set(), size=2, subtype='COORDINATES', min=0, description="Manual animation bounds")
    animation_source_limit: bpy.props.FloatProperty(name="Animation Source Limit", options=set(), description="The limit between each animation on an axis. For example on an angle axis with animtions for every 90 degrees, you'd use 90")
    
    runtime_source_bounds_manual: bpy.props.BoolProperty(name="Input Manual Bounds", options=set(), description="Define the input bounds manually")
    runtime_source_bounds: bpy.props.FloatVectorProperty(name="Input Source Bounds", options=set(), size=2, subtype='COORDINATES', min=0, description="Manual input bounds")
    runtime_source_clamped: bpy.props.BoolProperty(name="Input Source Clamped", options=set(), description="Clamps input to within this range")
    
    adjusted: bpy.props.EnumProperty(
        name="Adjustment",
        options=set(),
        items=[
            ("none", "None", ""),
            ("on_start", "On Start", ""),
            ("on_loop", "On Loop", ""),
            ("continuous", "Continuous", ""),
        ]
    )

    leaves_active_index: bpy.props.IntProperty(options=set())
    leaves: bpy.props.CollectionProperty(name="Animations", options=set(), type=NWO_AnimationLeavesItems)
    
    dead_zones_active_index: bpy.props.IntProperty(options=set())
    dead_zones: bpy.props.CollectionProperty(name="Blend Axis Dead Zones", options=set(), type=NWO_AnimationDeadZonesItems)
    
    phase_sets_active_index: bpy.props.IntProperty(options=set())
    phase_sets: bpy.props.CollectionProperty(name="Animation Sets", options=set(), type=NWO_AnimationPhaseSetsItems)
    
    groups_active_index: bpy.props.IntProperty(options=set())
    groups: bpy.props.CollectionProperty(name="Animation Groups", options=set(), type=NWO_AnimationGroupItems)

class NWO_AnimationBlendAxisItems(PropertyGroup):
    name: bpy.props.EnumProperty(
        name="Type",
        options=set(),
        items=[
            ("movement_angles", "Movement Angles", ""), # linear_movement_angle get_move_angle
            ("movement_speed", "Movement Speed", ""), # linear_movement_speed get_move_speed
            ("turn_rate", "Turn Rate", ""), # average_angular_rate get_turn_rate
            ("turn_angle", "Turn Angle", ""), # total_angular_offset get_turn_angle
            ("vertical", "Vertical", ""), # translation_offset_z get_destination_vertical
            ("horizontal", "Horizontal", ""), # translation_offset_horizontal get_destination_forward
        ]
    )
    
    animation_source_bounds_manual: bpy.props.BoolProperty(name="Animation Manual Bounds", options=set(), description="Manually define the bounds of the animation axis")
    animation_source_bounds: bpy.props.FloatVectorProperty(name="Animation Source Bounds", options=set(), size=2, subtype='COORDINATES', min=0, description="Manual animation bounds")
    animation_source_limit: bpy.props.FloatProperty(name="Animation Source Limit", options=set(), description="The limit between each animation on an axis. For example on an angle axis with animtions for every 90 degrees, you'd use 90")
    
    runtime_source_bounds_manual: bpy.props.BoolProperty(name="Input Manual Bounds", options=set(), description="Define the input bounds manually")
    runtime_source_bounds: bpy.props.FloatVectorProperty(name="Input Source Bounds", options=set(), size=2, subtype='COORDINATES', min=0, description="Manual input bounds")
    runtime_source_clamped: bpy.props.BoolProperty(name="Input Source Clamped", options=set(), description="Clamps input to within this range")
    
    adjusted: bpy.props.EnumProperty(
        name="Adjustment",
        options=set(),
        items=[
            ("none", "None", ""),
            ("on_start", "On Start", ""),
            ("on_loop", "On Loop", ""),
            ("continuous", "Continuous", ""),
        ]
    )

    leaves_active_index: bpy.props.IntProperty(options=set())
    leaves: bpy.props.CollectionProperty(name="Animations", options=set(), type=NWO_AnimationLeavesItems)
    
    dead_zones_active_index: bpy.props.IntProperty(options=set())
    dead_zones: bpy.props.CollectionProperty(name="Blend Axis Dead Zones", options=set(), type=NWO_AnimationDeadZonesItems)
    
    phase_sets_active_index: bpy.props.IntProperty(options=set())
    phase_sets: bpy.props.CollectionProperty(name="Animation Sets", options=set(), type=NWO_AnimationPhaseSetsItems)
    
    groups_active_index: bpy.props.IntProperty(options=set())
    groups: bpy.props.CollectionProperty(name="Animation Groups", options=set(), type=NWO_AnimationGroupItems)
    
    blend_axis_active_index: bpy.props.IntProperty(options=set())
    blend_axis: bpy.props.CollectionProperty(name="Blend Axis", options=set(), type=NWO_AnimationSubBlendAxisItems)

# class NWO_AnimationCompositesItems(PropertyGroup):
#     name: bpy.props.StringProperty(name="Name", options=set())
#     overlay: bpy.props.BoolProperty(name="Overlay", options=set())
    
#     timing_source: bpy.props.StringProperty(name="Timing Source", description="Name of the animation to use as the timing source")
#     blend_axis_active_index: bpy.props.IntProperty(options=set())
#     blend_axis: bpy.props.CollectionProperty(name="Blend Axis", options=set(), type=NWO_AnimationBlendAxisItems)
    
#############################################################
#############################################################

#############################################################
# ANIMATION RENAMES
#############################################################


class NWO_AnimationRenamesItems(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name")

#############################################################
# ANIMATION EVENTS
#############################################################

# ANIMATION EVENT DATA

class NWO_AnimationEventData_ListItems(bpy.types.PropertyGroup):
    data_type: bpy.props.EnumProperty(
        name="Type",
        options=set(),
        items=[
            ('SOUND', "Sound", ""),
            ('EFFECT', "Effect", ""),
            ('DIALOGUE', "Dialogue", ""),
        ]
    )
    
    frame_offset: bpy.props.IntProperty(
        name="Frame Offset",
        description="Number of frames this data event should be offset from the main event. Where the event is ranged, the offset is from the start frame",
        options=set(),
    )
    
    def sound_clean_tag_path(self, context):
        self["event_sound_tag"] = utils.clean_tag_path(self["event_sound_tag"], "sound").strip('"')
    
    event_sound_tag: bpy.props.StringProperty(
        name="Sound Tag",
        description="Path to the sound tag to play when this event is triggered",
        options=set(),
        update=sound_clean_tag_path,
    )
    
    def effect_clean_tag_path(self, context):
        self["event_effect_tag"] = utils.clean_tag_path(self["event_effect_tag"], "effect").strip('"')
    
    event_effect_tag: bpy.props.StringProperty(
        name="Effect Tag",
        description="Path to the effect tag that should play when this event is triggered",
        options=set(),
        update=effect_clean_tag_path,
    )
    
    dialogue_event: bpy.props.EnumProperty(
        name="Dialogue",
        description="Type of dialogue event that should play when this event is triggered",
        options=set(),
        items=[
            ("bump", "Bump", ""),
            ("dive", "Dive", ""),
            ('evade', "Evade", ""),
            ('lift', "Lift", ""),
            ('sigh', "Sigh", ""),
            ('contempt', "Contempt", ""),
            ('anger', "Anger", ""),
            ('fear', "Fear", ""),
            ('relief', "Relief", ""),
            ('sprint', "Sprint", ""),
            ('sprint_end', "Sprint End", ""),
            ('ass_grabber', "Assassination Grab (Attacker)", ""),
            ('kill_ass', "Assassination Kill (Attacker)", ""),
            ('ass_grabbed', "Assassination Grab (Victim)", ""),
            ('die_ass', "Assassination Kill (Victim)", ""),
        ]
    )
    
    marker: bpy.props.PointerProperty(
        type=bpy.types.Object,
        poll=poll_empty,
        name="Marker",
        options=set(),
        description="Marker that this sound / effect event should play on"
    )
    
    damage_effect_reporting_type: bpy.props.EnumProperty(
        name="Damage Effect Type",
        description="If this effect event does damage, report the following damage type to the game engine. This list is a combined list of Reach, Halo 4, and Halo 2AMP damage reporting types. Please check the description of the type to ensure it is valid for the game you are working in",
        default="unknown",
        options=set(),
        items=[
            ('ai suicide', "AI Suicide", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('airstrike', "Airstrike", "Valid for: Halo Reach"),
            ('armor lock crush', "Armor Lock Crush", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('assault carbine', "Assault Carbine", "Valid for: Halo 2AMP, Halo 4"),
            ('assault rifle', "Assault Rifle", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('ball melee damage', "Ball Melee Damage", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('banshee', "Banshee", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('banshee bomb', "Banshee Bomb", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('battle rifle', "Battle Rifle", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('beam rifle', "Beam Rifle", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('birthday party explosion', "Birthday Party Explosion", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('bishop beam', "Bishop Beam", "Valid for: Halo 2AMP, Halo 4"),
            ('bolt pistol', "Bolt Pistol", "Valid for: Halo 2AMP, Halo 4"),
            ('bomb explosion damage', "Bomb Explosion Damage", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('bomb melee damage', "Bomb Melee Damage", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('broadsword', "Broadsword", "Valid for: Halo 4"),
            ('broadsword missile', "Broadsword Missile", "Valid for: Halo 4"),
            ('brute plasma rifle', "Brute Plasma Rifle", "Valid for: Halo 2AMP"),
            ('brute shot', "Brute Shot", "Valid for: Halo 2AMP, Halo Reach"),
            ('carbine', "Carbine", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('chopper', "Chopper", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('claymore grenade', "Claymore Grenade", "Valid for: Halo Reach"),
            ('concussion rifle', "Concussion Rifle", "Valid for: Halo 2AMP, Halo 4"),
            ('elephant turret', "Elephant Turret", "Valid for: Halo Reach"),
            ('energy sword', "Energy Sword", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('excavator', "Excavator", "Valid for: Halo Reach"),
            ('falcon driver', "Falcon Driver", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('falcon gunner', "Falcon Gunner", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('falling damage', "Falling Damage", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('fire damage', "Fire Damage", "Valid for: Halo 2AMP"),
            ('firebomb grenade', "Firebomb Grenade", "Valid for: Halo Reach"),
            ('flag melee damage', "Flag Melee Damage", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('flak cannon', "Flak Cannon", "Valid for: Halo Reach"),
            ('flame thrower', "Flame Thrower", "Valid for: Halo Reach"),
            ('flood prongs', "Flood Prongs", "Valid for: Halo 2AMP, Halo 4"),
            ('forerunner rifle', "Forerunner Rifle", "Valid for: Halo 2AMP, Halo 4"),
            ('forerunner smg', "Forerunner Smg", "Valid for: Halo 2AMP, Halo 4"),
            ('forerunner sniper', "Forerunner Sniper", "Valid for: Halo 2AMP, Halo 4"),
            ('forerunner turret', "Forerunner Turret", "Valid for: Halo 2AMP, Halo 4"),
            ('forklift', "Forklift", "Valid for: Halo Reach"),
            ('frag grenade', "Frag Grenade", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('fuel rod cannon', "Fuel Rod Cannon", "Valid for: Halo 2AMP, Halo 4"),
            ('fusion coil', "Fusion Coil", "Valid for: Halo 2AMP"),
            ('generic collision damage', "Generic Collision Damage", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('generic explosion', "Generic Explosion", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('generic melee damage', "Generic Melee Damage", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('ghost', "Ghost", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('gravity hammer', "Gravity Hammer", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('grenade launcher', "Grenade Launcher", "Valid for: Halo Reach"),
            ('gun goose', "Gun Goose", "Valid for: Halo 2AMP"),
            ('gun goose gun', "Gun Goose Gun", "Valid for: Halo 2AMP"),
            ('hornet', "Hornet", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('hornet gun', "Hornet Gun", "Valid for: Halo 2AMP"),
            ('hornet rocket', "Hornet Rocket", "Valid for: Halo 2AMP"),
            ('human turret', "Human Turret", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('incineration launcher', "Incineration Launcher", "Valid for: Halo 2AMP, Halo 4"),
            ('lich driver', "Lich Driver", "Valid for: Halo 2AMP, Halo 4"),
            ('lich gunner', "Lich Gunner", "Valid for: Halo 2AMP, Halo 4"),
            ('light machine gun', "Light Machine Gun", "Valid for: Halo 2AMP, Halo 4"),
            ('MAC cannon', "MAC Cannon", "Valid for: Halo 2AMP, Halo 4"),
            ('magnum pistol', "Magnum Pistol", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('magnum pistol ctf', "Magnum Pistol CTF", "Valid for: Halo 2AMP, Halo 4"),
            ('mantis', "Mantis", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('marksman rifle', "Marksman Rifle", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('mauler', "Mauler", "Valid for: Halo Reach"),
            ('mech cannon', "Mech Cannon", "Valid for: Halo 4"),
            ('mech chaingun', "Mech Chaingun", "Valid for: Halo 4"),
            ('mech melee', "Mech Melee", "Valid for: Halo 4"),
            ('mech rocket', "Mech Rocket", "Valid for: Halo 4"),
            ('missile launcher', "Missile Launcher", "Valid for: Halo Reach"),
            ('mongoose', "Mongoose", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('needle rifle', "Needle Rifle", "Valid for: Halo Reach"),
            ('needler', "Needler", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('Orbital cruise missile', "Orbital Cruise Missile", "Valid for: Halo 2AMP, Halo 4"),
            ('Ordnance drop pod', "Ordnance Drop Pod", "Valid for: Halo 2AMP, Halo 4"),
            ('Personal auto turret', "Personal Auto Turret", "Valid for: Halo 2AMP, Halo 4"),
            ('plasma cannon', "Plasma Cannon", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('plasma grenade', "Plasma Grenade", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('plasma launcher', "Plasma Launcher", "Valid for: Halo Reach"),
            ('plasma mortar', "Plasma Mortar", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('plasma pistol', "Plasma Pistol", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('plasma repeater', "Plasma Repeater", "Valid for: Halo Reach"),
            ('plasma rifle', "Plasma Rifle", "Valid for: Halo 2AMP, Halo Reach"),
            ('plasma shot', "Plasma Shot", "Valid for: Halo Reach"),
            ('plasma turret', "Plasma Turret", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('Portable shield', "Portable Shield", "Valid for: Halo 2AMP, Halo 4"),
            ('prox-mine', "Proximity Mine", "Valid for: Halo Reach"),
            ('pulse grenade', "Pulse Grenade", "Valid for: Halo 2AMP, Halo 4"),
            ('rail gun', "Rail Gun", "Valid for: Halo 2AMP, Halo 4"),
            ('revenant deux driver', "Revenant Deux Driver", "Valid for: Halo 2AMP, Halo 4"),
            ('revenant deux gunner', "Revenant Deux Gunner", "Valid for: Halo 2AMP, Halo 4"),
            ('revenant driver', "Revenant Driver", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('revenant gunner', "Revenant Gunner", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('rocket launcher', "Rocket Launcher", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('sabre', "Sabre", "Valid for: Halo Reach"),
            ('scorpion', "Scorpion", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('scorpion gunner', "Scorpion Gunner", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('scripting', "Scripting", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('sentinal gun', "Sentinel Gun", "Valid for: Halo Reach"),
            ('sentinel beam', "Sentinel Beam", "Valid for: Halo 2AMP, Halo Reach"),
            ('sentinel rpg', "Sentinel RPG", "Valid for: Halo Reach"),
            ('seraph', "Seraph", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('shade turret', "Shade Turret", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('shotgun', "Shotgun", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('smg', "SMG", "Valid for: Halo 2AMP, Halo Reach"),
            ('smgs', "Dual SMGs", "Valid for: Halo 2AMP"),
            ('sniper rifle', "Sniper Rifle", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('spartan laser', "Spartan Laser", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('spectre driver', "Spectre Driver", "Valid for: Halo Reach"),
            ('spectre gunner', "Spectre Gunner", "Valid for: Halo Reach"),
            ('spike rifle', "Spike Rifle", "Valid for: Halo Reach"),
            ('spread gun', "Spread Gun", "Valid for: Halo 2AMP, Halo 4"),
            ('stalactice', "Stalactite", "Valid for: Halo 2AMP"),
            ('sticky grenade launcher', "Sticky Grenade Launcher", "Valid for: Halo 2AMP, Halo 4"),
            ('tank', "Tank", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('Target designator', "Target Designator", "Valid for: Halo 2AMP, Halo 4"),
            ('Thruster pack', "Thruster Pack", "Valid for: Halo 2AMP, Halo 4"),
            ('teleporter', "Teleporter", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('teh guardians', "The Guardians", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('tortoise driver', "Tortoise Driver", "Valid for: Halo 4"),
            ('tortoise gunner', "Tortoise Gunner", "Valid for: Halo 4"),
            ('transfer damage', "Transfer Damage", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('unknown', "Unknown", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('warthog driver', "Warthog Driver", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('warthog gunner', "Warthog Gunner", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('warthog gunner gauss', "Warthog Gunner Gauss", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('warthog gunner rocket', "Warthog Gunner Rocket", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('wasp driver', "Wasp Driver", "Valid for: Halo 4"),
            ('wasp gunner', "Wasp Gunner", "Valid for: Halo 4"),
            ('wasp gunner heavy', "Wasp Gunner Heavy", "Valid for: Halo 4"),
            ('wraith', "Wraith", "Valid for: Halo 2AMP, Halo 4, Halo Reach"),
            ('wraith anti-infantry', "Wraith Anti-infantry", "Valid for: Halo 2AMP, Halo 4, Halo Reach")
        ]
    )
    
    
    flag_allow_on_player: bpy.props.BoolProperty(
        options=set(),
        name="Allow on Player"
    )
    flag_left_arm_only: bpy.props.BoolProperty(
        options=set(),
        name="Left Arm Only"
    )
    flag_right_arm_only: bpy.props.BoolProperty(
        options=set(),
        name="Right Arm Only"
    )
    flag_first_person_only: bpy.props.BoolProperty(
        options=set(),
        name="First Person Only"
    )
    flag_third_person_only: bpy.props.BoolProperty(
        options=set(),
        name="Third Person Only"
    )
    flag_forward_only: bpy.props.BoolProperty(
        options=set(),
        name="Forward Only"
    )
    flag_reverse_only: bpy.props.BoolProperty(
        options=set(),
        name="Reverse Only"
    )
    flag_fp_no_aged_weapons: bpy.props.BoolProperty(
        options=set(),
        name="Don't Play on Aged Weapons"
    )
    
    def model_clean_tag_path(self, context):
        self["event_model"] = utils.clean_tag_path(self["event_model"], "model").strip('"')
    
    event_model: bpy.props.StringProperty(
        options=set(),
        name="Limit to Model",
        description="Limits the data event to only play on the given model tag",
        update=model_clean_tag_path
    )
    variant: bpy.props.StringProperty(
        options=set(),
        name="Limit to Variant",
        description="Limits the data event to only play on the given variant"
    )

class NWO_Animation_ListItems(bpy.types.PropertyGroup):
    event_data: bpy.props.CollectionProperty(type=NWO_AnimationEventData_ListItems)
    active_event_data_index: bpy.props.IntProperty()
    
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
        description="The frame this event is duplicated to",
        default=0,
        options=set(),
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
            ("_connected_geometry_animation_event_type_object_function", "Object Function", ""),
            ("_connected_geometry_animation_event_type_import", "Pose Overlay Wrap", ""),
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

    frame_start: bpy.props.IntProperty(
        name="Frame Start",
        default=1,
        options=set(),
    )

    frame_end: bpy.props.IntProperty(
        name="Frame End",
        default=30,
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

    # wrinkle_map_effect: bpy.props.FloatProperty(
    #     name="Wrinkle Map Effect",
    #     default=1,
    #     options=set(),
    # )

    # footstep_type: bpy.props.StringProperty(
    #     name="Footstep Type",
    #     default="",
    #     options=set(),
    # )

    # footstep_effect: bpy.props.IntProperty(
    #     name="Footstep Effect",
    #     default=0,
    #     options=set(),
    # )
    
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

    # ik_active_tag: bpy.props.StringProperty(
    #     name="IK Active Tag",
    #     default="",
    #     options=set(),
    # )

    # ik_target_tag: bpy.props.StringProperty(
    #     name="IK Target Tag",
    #     default="",
    #     options=set(),
    # )
    
    def poll_ik_target_marker(self, object):
        return utils.is_marker(object) and object.nwo.marker_type == '_connected_geometry_marker_type_model'
    
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
    
    # ik_influence: bpy.props.FloatProperty(
    #     name="Influence",
    #     options=set(),
    #     default=1,
    #     min=0,
    #     max=1,
    #     subtype='FACTOR',
    # )

    # ik_proxy_target_id: bpy.props.IntProperty(
    #     name="IK Proxy Target ID",
    #     default=0,
    #     options={'HIDDEN'},
    # )

    # ik_pole_vector_id: bpy.props.IntProperty(
    #     name="IK Pole Vector ID",
    #     default=0,
    #     options={'HIDDEN'},
    # )

    # ik_effector_id: bpy.props.IntProperty(
    #     name="IK Effector ID",
    #     default=0,
    #     options={'HIDDEN'},
    # )
    
    ik_pole_vector: bpy.props.PointerProperty(
        name="Pole Target",
        type=bpy.types.Object,
        description="Pole target for this IK to use. Optional",
        options=set(),
    )

    # cinematic_effect_tag: bpy.props.StringProperty(
    #     name="Cinematic Effect Tag",
    #     default="",
    #     options=set(),
    # )

    # cinematic_effect_effect: bpy.props.IntProperty(
    #     name="Cinematic Effect",
    #     default=0,
    #     options=set(),
    # )

    # cinematic_effect_marker: bpy.props.StringProperty(
    #     name="Cinematic Effect Marker",
    #     default="",
    #     options=set(),
    # )

    object_function_name: bpy.props.EnumProperty(
        name="Object Function",
        options=set(),
        items=[
            ('animation_event_function_a', 'A', ''),
            ('animation_event_function_b', 'B', ''),
            ('animation_event_function_c', 'C', ''),
            ('animation_event_function_d', 'D', ''),
        ]
    )

    event_value: bpy.props.FloatProperty(
        name="Value",
        default=1,
        soft_min=0,
        soft_max=1,
        subtype='FACTOR'
    )

    frame_frame: bpy.props.IntProperty(
        name="Frame",
        description="The frame this event occurs on",
        default=0,
        options=set(),
        update=update_frame_range,
    )

    frame_name: bpy.props.EnumProperty(
        name="Frame Event",
        default="none",
        options=set(),
        items=[
            ("none", "None", "Doesn't trigger any special events in animation, but can be used to play sounds, effects, and dialogue"),
            ("primary keyframe", "Primary Keyframe", "Activates the primary function of an animation, for example:\nCompletes a weapon reload\nApplies damage on melee\nThrows a grenade\nKicks a vehicle occupant when boarding]\nLast frame a biped is on the ground in a ranged action\nPoint in an assassination at which the the victim will die if the animation is interrupted"),
            ("secondary keyframe", "Secondary Keyframe", "Activates the secondary function of an animation, for example:\nTaking over a vehicle seat after boarding and kicking out the occupant\nDoes something with melee strikes but I'm not sure\nApex of a ranged action"),
            ("tertiary keyframe", "Tertiary Keyframe", "Activates the tertiary function of an animation, for example:\nDoes something for sync action assassinations\nFirst frame when a biped lands in a ranged action"),
            ("left foot", "Left Foot", "Point in the animation where the biped's left foot impacts the ground. Used to create footstep effects"),
            ("right foot", "Right Foot", "Point in the animation where the biped's right foot impacts the ground. Used to create footstep effects"),
            ("allow interruption", "Allow Interruption", "Point at which an animation may be interrupted, for example it will allow the player to switch weapon when reloading, meleeing, or throwing a grenade"),
            ("do not allow interruption", "Do Not Allow Interruption", "Prevents an player animation from being interupted by player action... or should do. I haven't found any examples of it being used"),
            ("both-feet shuffle", "Both-Feet Shuffle", "Point in animation where both feet move along the ground"),
            ("body impact", "Body Impact", "Plays body impact effects"),
            ("left foot lock", "Left Foot Lock", "Locks the biped's left foot to the ground"),
            ("left foot unlock", "Left Foot Unlock", "Unlocks the biped's left foot from the ground"),
            ("right foot lock", "Right Foot Lock", "Locks the biped's right foot to the ground"),
            ("right foot unlock", "Right Foot Unlock", "Unlocks the biped's right foot from the ground"),
            ("blend range marker", "Blend Range Marker", "Necessary for ranged actions (where AI jump from point to point). A blend range marker must be added for the primary, secondary, and teritary events of a ranged action"),
            ("stride expansion", "Stride Expansion", "Used in walking/running animations to indicate when the biped's stride begins"),
            ("stride contraction", "Stride Contraction", "Used in walking/running animations to indicate when the biped's stride contracts"),
            ("ragdoll keyframe", "Ragdoll Keyframe", "Makes the biped ragdoll in death and assassination animations"),
            ("drop weapon keyframe", "Drop Weapon Keyframe", "Makes the biped drop their weapons in death and assassination animations"),
            ("match a", "Match A", "Important for walk/run cycles. The point at which the biped's legs are side by side"),
            ("match b", "Match B", "Important for walk/run cycles. After Match A, the point at which the leading foot touches the ground"),
            ("match c", "Match C", "Important for walk/run cycles. After Match B, the point at which the legs are side by side again"),
            ("match d", "Match D", "Important for walk/run cycles. After Match C, the point at which the new leading foot touches the ground"),
            # ("jetpack closed", "Jetpack Closed", ""),
            # ("jetpack open", "Jetpack Open", ""),
            # ("sound event", "Sound Event", ""),
            # ("effect event", "Effect Event", ""),
        ],
    )

    # frame_trigger: bpy.props.BoolProperty(
    #     name="Frame Trigger",
    #     default=False,
    #     options=set(),
    # )

    # import_frame: bpy.props.IntProperty(
    #     name="Wrap Frame",
    #     default=1,
    #     options=set(),
    #     description="Frame that a wrapped event occurs on",
    # )

    import_name: bpy.props.EnumProperty(
        name="Wrap Type",
        options=set(),
        description="Tells the game that the specified pose frame should be from a left/right irrespective of the yaw angle",
        items=[
            ("Wrapped Left", "Wrapped Left", "Tells the game that this pose frame is for a left turn irrespective of yaw angle"),
            ("Wrapped Right", "Wrapped Right", "Tells the game that this pose frame is for a right turn irrespective of yaw angle"),
        ]
    )

    # text: bpy.props.StringProperty(
    #     name="Text",
    #     default="",
    #     options=set(),
    # )

class NWO_ActionGroup(bpy.types.PropertyGroup):
    object: bpy.props.PointerProperty(type=bpy.types.Object)
    action: bpy.props.PointerProperty(type=bpy.types.Action)
    nla_uuid: bpy.props.StringProperty(options={'HIDDEN'})
    is_shape_key_action: bpy.props.BoolProperty(options={'HIDDEN'})

class NWO_AnimationPropertiesGroup(bpy.types.PropertyGroup):
    active_action_group_index: bpy.props.IntProperty()
    
    external: bpy.props.BoolProperty(
        name="External",
        description="Animation data comes from separate GR2 file"
    )
    
    gr2_path: bpy.props.StringProperty(
        name="GR2 Path",
        description="Data relative path to the file that contains animation data"
    )
    
    pose_overlay: bpy.props.BoolProperty(
        name="Pose Overlay",
        description="External animation is a pose overlay"
    )
    
    has_pca: bpy.props.BoolProperty(
        name="PCA",
        description="External animation has PCA (shape key) data"
    )
    
    action_tracks: bpy.props.CollectionProperty(type=NWO_ActionGroup)
    name: bpy.props.StringProperty(
        name="Name",
        options=set(),
    )
    def get_actions(self) -> list[bpy.types.Action]:
        return [group.action for group in self.action_tracks if group.action is not None]
    
    def update_frame_end(self, context):
        if self.frame_end < self.frame_start:
            self.frame_start = self.frame_end
            
    def update_frame_start(self, context):
        if self.frame_start > self.frame_end:
            self.frame_end = self.frame_start

    frame_start: bpy.props.IntProperty(
        name="Frame Start",
        default=1,
        options=set(),
        min=0,
        update=update_frame_start,
    )

    frame_end: bpy.props.IntProperty(
        name="Frame End",
        default=30,
        options=set(),
        min=0,
        update=update_frame_end,
    )
            
    
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

    export_this: bpy.props.BoolProperty(
        name="Export",
        default=True,
        description="Controls whether this animation is exported or not",
        options=set(),
    )

    compression : bpy.props.EnumProperty(
        name="Compression",
        description="Level of compression to apply to animations",
        options=set(),
        items=[
            ("Default", "Default", "Animation compression is determined by the value set in the asset editor panel"),
            ("Uncompressed", "Uncompressed", "No compression"),
            ("Medium", "Medium", "Medium compression"),
            ("Rough", "Rough", "Highest level of compression"),
        ],
    )
            
    animation_type: bpy.props.EnumProperty(
        name="Type",
        description="Set the type of Halo animation you want this action to be",
        options=set(),
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
        description='Set how this animation moves the object in worldspace',
        default="none",
        options=set(),
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
        options=set(),
        items=[
            ('object', 'Object', 'Replacement animation in object space.\nLegacy format: JMR\nExamples: revenant_p, sword put_away'),
            ('local', 'Local', 'Replacement animation in local space.\nLegacy format: JMRX\nExamples: combat pistol any grip, combat rifle sr grip'),
        ]
    )

    # animation_is_pose: bpy.props.BoolProperty(
    #     name='Pose Overlay',
    #     options=set(),
    #     description='Tells the exporter to compute aim node directions for this overlay. These allow animations to be affected by the aiming direction of the animated object. You must set the pedestal, pitch, and yaw usages in the Foundry armature properties to use this correctly\nExamples: aim_still_up, acc_up_down, vehicle steering'
    # )

    animation_events: bpy.props.CollectionProperty(
        type=NWO_Animation_ListItems,
    )

    active_animation_event_index: bpy.props.IntProperty(
        name="Index for Animation Event",
        default=0,
        min=0,
        options=set(),
    )

    animation_renames: bpy.props.CollectionProperty(
        type=NWO_AnimationRenamesItems,
    )

    active_animation_rename_index: bpy.props.IntProperty(
        name="Index for Animation Renames",
        default=0,
        options=set(),
        min=0,
    )
    
    # Suspension Settings, only visible when animation name is prefixed: suspension
    
    suspension_marker: bpy.props.PointerProperty(poll=poll_empty, type=bpy.types.Object, name="Suspension Point", description="Empty whose position marks the midpoint of the suspension (i.e. the midpoint of a wheel). This empty should be parented to the root bone of the armature")
    suspension_contact_marker: bpy.props.PointerProperty(poll=poll_empty, type=bpy.types.Object, name="Ground Point", description="Empty whose position marks the bottom of the object undergoing suspension (i.e. the bottom point of a wheel). This empty should be parented to the same bone that the suspension object is parented / vertex weighted to (usually a wheel or tread). This empty does not need to be exported")
    suspension_destroyed_region_name: bpy.props.StringProperty(name="Destroyed Region Name", description="Optional. Only necessary for suspension with a destroyed state")
    suspension_destroyed_contact_marker: bpy.props.PointerProperty(poll=poll_empty, type=bpy.types.Object, name="Destroyed Ground Point", description="Optional. Empty whose position marks the bottom of the object undergoing suspension (i.e. the bottom point of a wheel) when destroyed. This empty should be parented to the same bone that the suspension object is parented / vertex weighted to (usually a wheel or tread). This empty does not need to be exported")

    # Composites
    timing_source: bpy.props.StringProperty(name="Timing Source", description="Name of the animation to use as the timing source")
    blend_axis_active_index: bpy.props.IntProperty(options=set())
    blend_axis: bpy.props.CollectionProperty(name="Blend Axis", options=set(), type=NWO_AnimationBlendAxisItems)

    # NOT VISIBLE TO USER, USED FOR ANIMATION RENAMES
    state_type: bpy.props.EnumProperty(
        name="State Type",
        options=set(),
        items=[
            ("action", "Action / Overlay", ""),
            ("transition", "Transition", ""),
            ("damage", "Death & Damage", ""),
            ("custom", "Custom", ""),
        ],
    )

    mode: bpy.props.StringProperty(
        name="Mode",
        options=set(),
        description="""The mode the object must be in to use this animation. Use 'any' for all modes. Other valid
        inputs include but are not limited to: 'crouch' when a unit is crouching, 
        'combat' when a unit is in combat. Modes can also refer
        to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more
        information refer to existing model_animation_graph tags. Can be empty""",
    )

    weapon_class: bpy.props.StringProperty(
        name="Weapon Class",
        options=set(),
        description="""The weapon class this unit must be holding to use this animation. Weapon class is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty""",
    )
    weapon_type: bpy.props.StringProperty(
        name="Weapon Name",
        options=set(),
        description="""The weapon type this unit must be holding to use this animation.  Weapon name is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty""",
    )
    set: bpy.props.StringProperty(
        name="Set", description="The set this animtion is a part of. Can be empty", options=set(),
    )
    state: bpy.props.StringProperty(
        name="State",
        options=set(),
        description="""The state this animation plays in. States can refer to hardcoded properties or be entirely
        custom. You should refer to existing model_animation_graph tags for more information. Examples include: 'idle' for 
        animations that should play when the object is inactive, 'move-left', 'move-front' for moving. 'put-away' for
        an animation that should play when putting away a weapon. Must not be empty""",
    )

    destination_mode: bpy.props.StringProperty(
        name="Destination Mode",
        options=set(),
        description="The mode to put this object in when it finishes this animation. Can be empty",
    )
    destination_state: bpy.props.StringProperty(
        name="Destination State",
        options=set(),
        description="The state to put this object in when it finishes this animation. Must not be empty",
    )

    damage_power: bpy.props.EnumProperty(
        name="Power",
        options=set(),
        items=[
            ("hard", "Hard", ""),
            ("soft", "Soft", ""),
        ],
    )
    damage_type: bpy.props.EnumProperty(
        name="Type",
        options=set(),
        items=[
            ("ping", "Ping", ""),
            ("kill", "Kill", ""),
        ],
    )
    damage_direction: bpy.props.EnumProperty(
        name="Direction",
        options=set(),
        items=[
            ("front", "Front", ""),
            ("left", "Left", ""),
            ("right", "Right", ""),
            ("back", "Back", ""),
        ],
    )
    damage_region: bpy.props.EnumProperty(
        name="Region",
        options=set(),
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
        options=set(),
        name="Variant",
        description="""The variation of this animation. Variations can have different weightings
            to determine whether they play. 0 = no variation
                                    """,
    )

    custom: bpy.props.StringProperty(name="Custom")

    created_with_foundry: bpy.props.BoolProperty(options={'HIDDEN'})
    
    gr2_path: bpy.props.StringProperty(
        name="GR2 Path",
        description="Path to a GR2 file containing animation data to use in place of an action in this scene",
    )

class NWO_CinematicShotActor(bpy.types.PropertyGroup):
    active: bpy.props.BoolProperty(
        name="Active",
        description="Actor is active for this shot"
    )
    pca: bpy.props.BoolProperty(
        name="PCA",
        description="Actor uses PCA animation for this shot. This will only have an effect if a mesh parented under this actor has shape keys"
    )
    actor: bpy.props.PointerProperty(
        name="Actor",
        description="The object representing an actor. Must be an armature object",
        type=bpy.types.Object,
        poll=poll_armature,
    )

class NWO_CinematicShot(bpy.types.PropertyGroup):
    frame_count: bpy.props.IntProperty(
        name="Shot Frame Count",
        description="Number of frames that this shot will play for"
    )
    actors: bpy.props.CollectionProperty(
        name="Actors",
        type=NWO_CinematicShotActor,
    )
    active_actor_index: bpy.props.IntProperty()

class NWO_ZoneSets_ListItems(PropertyGroup):
    name: bpy.props.StringProperty()
    bsp_0: bpy.props.BoolProperty()
    bsp_1: bpy.props.BoolProperty()
    bsp_2: bpy.props.BoolProperty()
    bsp_3: bpy.props.BoolProperty()
    bsp_4: bpy.props.BoolProperty()
    bsp_5: bpy.props.BoolProperty()
    bsp_6: bpy.props.BoolProperty()
    bsp_7: bpy.props.BoolProperty()
    bsp_8: bpy.props.BoolProperty()
    bsp_9: bpy.props.BoolProperty()
    bsp_10: bpy.props.BoolProperty()
    bsp_11: bpy.props.BoolProperty()
    bsp_12: bpy.props.BoolProperty()
    bsp_13: bpy.props.BoolProperty()
    bsp_14: bpy.props.BoolProperty()
    bsp_15: bpy.props.BoolProperty()
    bsp_16: bpy.props.BoolProperty()
    bsp_17: bpy.props.BoolProperty()
    bsp_18: bpy.props.BoolProperty()
    bsp_19: bpy.props.BoolProperty()
    bsp_20: bpy.props.BoolProperty()
    bsp_21: bpy.props.BoolProperty()
    bsp_22: bpy.props.BoolProperty()
    bsp_23: bpy.props.BoolProperty()
    bsp_24: bpy.props.BoolProperty()
    bsp_25: bpy.props.BoolProperty()
    bsp_26: bpy.props.BoolProperty()
    bsp_27: bpy.props.BoolProperty()
    bsp_28: bpy.props.BoolProperty()
    bsp_29: bpy.props.BoolProperty()
    bsp_30: bpy.props.BoolProperty()
    bsp_31: bpy.props.BoolProperty()
    # Adding more for structure designs
    bsp_32: bpy.props.BoolProperty()
    bsp_33: bpy.props.BoolProperty()
    bsp_34: bpy.props.BoolProperty()
    bsp_35: bpy.props.BoolProperty()
    bsp_36: bpy.props.BoolProperty()
    bsp_37: bpy.props.BoolProperty()
    bsp_38: bpy.props.BoolProperty()
    bsp_39: bpy.props.BoolProperty()
    
class NWO_MaterialOverrides(PropertyGroup):
    
    def poll_material(self, material: bpy.types.Material):
        return not material.is_grease_pencil
    
    source_material: bpy.props.PointerProperty(
        name="Source Material",
        type=bpy.types.Material,
        poll=poll_material,
        options=set(),
    )
    destination_material: bpy.props.PointerProperty(
        name="Destination Material",
        type=bpy.types.Material,
        poll=poll_material,
        options=set(),
    )
    
    enabled: bpy.props.BoolProperty(
        name="Enabled",
        default=True,
        options=set(),
    )
    
class NWO_PermutationClones(PropertyGroup):
    name: bpy.props.StringProperty(
        name="Name",
        options=set(),
    )
    
    material_overrides: bpy.props.CollectionProperty(
        name="Material Tag Overrides",
        description="Materials to override for this clone",
        type=NWO_MaterialOverrides,
        options=set(),
    )
    
    active_material_override_index: bpy.props.IntProperty(
        options=set(),
    )
    
    enabled: bpy.props.BoolProperty(
        name="Enabled",
        default=True,
        options=set(),
    )

class NWO_Permutations_ListItems(PropertyGroup):

    def update_name(self, context):
        if self.old != self.name:
            i = int(self.path_from_id().rpartition('[')[2].strip(']'))
            bpy.ops.nwo.permutation_rename(new_name=self.name, index=i)

    old: bpy.props.StringProperty(options=set())

    name: bpy.props.StringProperty(
        name="Name",
        update=update_name,
        options=set(),
        )

    def update_hidden(self, context):
        bpy.ops.nwo.permutation_hide(entry_name=self.name)

    hidden: bpy.props.BoolProperty(name="Hidden", update=update_hidden, options=set())

    def update_hide_select(self, context):
        bpy.ops.nwo.permutation_hide_select(entry_name=self.name)

    hide_select: bpy.props.BoolProperty(name="Hide Select", update=update_hide_select, options=set())

    active: bpy.props.BoolProperty(
        name="Active",
        description="If false, this region will not be active in the model tag except if added to a variant",
        default=True,
    )
    
    clones: bpy.props.CollectionProperty(
        name="Permutation Clones",
        description="Clones of this permutation. Tells the game to copy this permutation to the specified name and optionally replace material paths",
        type=NWO_PermutationClones,
    )
    
    active_clone_index: bpy.props.IntProperty(
        options=set(),
    )

class NWO_Regions_ListItems(PropertyGroup):

    def update_name(self, context):
        if self.old != self.name:
            i = int(self.path_from_id().rpartition('[')[2].strip(']'))
            bpy.ops.nwo.region_rename(new_name=self.name, index=i)

    old: bpy.props.StringProperty(options=set())

    name: bpy.props.StringProperty(
        name="Name",
        update=update_name,
        options=set(),
        )

    def update_hidden(self, context):
        bpy.ops.nwo.region_hide(entry_name=self.name)

    hidden: bpy.props.BoolProperty(name="Hidden", update=update_hidden, options=set())

    def update_hide_select(self, context):
        bpy.ops.nwo.region_hide_select(entry_name=self.name)

    hide_select: bpy.props.BoolProperty(name="Hide Select", update=update_hide_select, options=set())

    active: bpy.props.BoolProperty(
        name="Active",
        description="If false, this region will not be active in the model tag except if added to a variant",
        default=True,
    )

class NWO_BSP_ListItems(PropertyGroup):
    name: bpy.props.StringProperty(name="BSP Table", options=set())

class NWO_GlobalMaterial_ListItems(PropertyGroup):
    name: bpy.props.StringProperty(name="Global Material Table", options=set())
    
class NWO_IKChain(PropertyGroup):
    name: bpy.props.StringProperty(name="Name", options=set())
    start_node: bpy.props.StringProperty(name="Start Bone", options=set())
    effector_node: bpy.props.StringProperty(name="Effector Bone", options=set())
    
class NWO_ControlObjects(PropertyGroup):
    ob: bpy.props.PointerProperty(type=bpy.types.Object, options=set())
    
def prefab_warning(self, context):
    self.layout.label(text=f"Halo Reach does not support prefab assets")

# class NWO_Asset_ListItems(PropertyGroup):
#     def GetSharedAssetName(self):
#         name = self.shared_asset_path
#         name = name.rpartition("\\")[2]
#         name = name.rpartition(".sidecar.xml")[0]

#         return name

#     shared_asset_name: bpy.props.StringProperty(
#         get=GetSharedAssetName,
#     )

#     shared_asset_path: bpy.props.StringProperty()

#     shared_asset_types = [
#         ("BipedAsset", "Biped", ""),
#         ("CrateAsset", "Crate", ""),
#         ("CreatureAsset", "Creature", ""),
#         ("Device_ControlAsset", "Device Control", ""),
#         ("Device_MachineAsset", "Device Machine", ""),
#         ("Device_TerminalAsset", "Device Terminal", ""),
#         ("Effect_SceneryAsset", "Effect Scenery", ""),
#         ("EquipmentAsset", "Equipment", ""),
#         ("GiantAsset", "Giant", ""),
#         ("SceneryAsset", "Scenery", ""),
#         ("VehicleAsset", "Vehicle", ""),
#         ("WeaponAsset", "Weapon", ""),
#         ("ScenarioAsset", "Scenario", ""),
#         ("Decorator_SetAsset", "Decorator Set", ""),
#         ("Particle_ModelAsset", "Particle Model", ""),
#     ]

#     shared_asset_type: bpy.props.EnumProperty(
#         name="Type",
#         default="BipedAsset",
#         options=set(),
#         items=shared_asset_types,
#     )

# class NWO_ChildAsset(PropertyGroup):
#     asset_path: bpy.props.StringProperty(options=set())
#     enabled: bpy.props.BoolProperty(name="Enabled", default=True, options=set())
    
def poll_actor(self, object):
    return object.type == 'ARMATURE' and object.nwo.cinematic_object
    
class NWO_CinematicEvent(PropertyGroup):
    def cinematic_event_types(self, context):
        return [
            ("DIALOGUE", "Dialogue", ""),
            ("EFFECT", "Effect", ""),
            ("SCRIPT", "Script", "")
        ]
        
    def get_name(self):
        match self.type:
            case 'DIALOGUE':
                # layout.prop(item, "name", icon='PLAY_SOUND', text="", emboss=False)
                if self.sound_tag.strip():
                    if self.lipsync_actor is None:
                        return f"{Path(self.sound_tag).with_suffix('').name} -> NONE"
                    else:
                        return f"{Path(self.sound_tag).with_suffix('').name} -> {self.lipsync_actor.name}"
                else:
                    return "NONE"
            case 'EFFECT':
                if self.effect.strip():
                    if self.marker is None:
                        return f"{Path(self.effect).with_suffix('').name} -> NONE"
                    else:
                        if self.marker.type == 'EMPTY':
                            arm = utils.ultimate_armature_parent(self.marker)
                            if arm is None:
                                return f"{Path(self.effect).with_suffix('').name} -> NONE -> {self.marker.name}"
                                layout.alert = True
                            else:
                                return f"{Path(self.effect).with_suffix('').name} -> {arm.name} -> {self.marker.name}"
                        else:
                            return f"{Path(self.effect).with_suffix('').name} -> {self.marker.name}"
                else:
                    return "NONE"
            case 'SCRIPT':
                if self.script_type == 'CUSTOM':
                    if self.text is None:
                        if self.script.strip():
                            return self.script
                        else:
                            return "NONE"
                    else:
                        return self.text.name
                else:
                    if self.script_type in script_object_types:
                        if self.script_object is None:
                            return f"{self.script_type.lower()} -> NONE"
                        else:
                            match self.script_type:
                                case 'SET_VARIANT':
                                    return f"{self.script_type.lower()} -> {self.script_object.name} -> {self.script_variant}"
                                case 'SET_PERMUTATION':
                                    return f"{self.script_type.lower()} -> {self.script_object.name} -> {self.script_region} {self.script_permutation}"
                                case 'SET_REGION_STATE':
                                    return f"{self.script_type.lower()} -> {self.script_object.name} -> {self.script_region} {self.script_state}"
                                case 'SET_MODEL_STATE_PROPERTY':
                                    return f"{self.script_type.lower()} -> {self.script_object.name} -> {self.script_state_property} {'on' if self.script_bool else 'off'}"
                                case 'DAMAGE_OBJECT':
                                    return f"{self.script_type.lower()} -> {self.script_object.name} -> {self.script_region} -> {round(self.script_damage, 2)}"
                                case _:
                                    return f"{self.script_type.lower()} -> {self.script_object.name}"
                    else:
                        return self.script_type.lower()
        
    name: bpy.props.StringProperty(
        name="Name",
        get=get_name,
    )
    
    type: bpy.props.EnumProperty(
        name="Type",
        description="Type of cinematic event",
        items=cinematic_event_types,
        options=set(),
    )
    
    frame: bpy.props.IntProperty(
        name="Frame",
        description="Play on which this event plays",
        default=1,
        min=0,
        options=set(),
    )
    
    # Dialogue
    sound_tag: bpy.props.StringProperty(
        name="Sound Tag",
        description="Tag relative path to the sound tag to play"
    )
    female_sound_tag: bpy.props.StringProperty(
        name="Female Sound Tag",
        description="Tag relative path to the sound tag to play instead of the default if the actor making the sound is female (such as a female player). If this is not set, the default sound will always be used"
    )
    
    sound_scale: bpy.props.FloatProperty(
        name="Scale",
        description="Scale to apply to the sound",
        default=1,
        min=0,
        max=1,
        subtype='FACTOR',
        options=set(),
    )
    
    lipsync_actor: bpy.props.PointerProperty(
        name="Lipsync Actor",
        description="The actor who should lipsync to this sound",
        type=bpy.types.Object,
        poll=poll_actor,
        options=set(),
    )
    
    default_sound_effect: bpy.props.StringProperty(
        name="Sound Effect",
        description="The sound effect to play on top of the dialogue. Uses the sound effects defined in sound\global_fx.sound_effect_collection",
        options=set(),
    )
    
    subtitle: bpy.props.StringProperty(
        name="Subtitle",
        description="Name of the subtitle to show for this dialogue",
        options=set(),
    )
    
    female_subtitle: bpy.props.StringProperty(
        name="Female Subtitle",
        description="Name of the subtitle to show for this dialogue if the female sound tag is used",
        options=set(),
    )
    
    subtitle_character: bpy.props.StringProperty(
        name="Subtitle Character",
        description="Reference to character name in globals\globals.globals tag -> cinematic globals -> cinematic characters. Subtitles will use the color set here instead of the default",
        options=set(),
    )
    
    sound_strip: bpy.props.StringProperty(
        name="Sound Strip",
        description="Name of the sound strip to use for this dialogue. When this is set, the frame of this strip will be used instead of the frame declared above",
        options=set(),
    )
    
    # Effect
    effect: bpy.props.StringProperty(
        name="Effect Tag",
        description="Tag relative path to the effect tag this event uses",
        options=set(),
    )
    
    marker: bpy.props.PointerProperty(
        name="Marker Object",
        description="The object to play this effect on. Can be a marker directly or the cinematic actor",
        type=bpy.types.Object,
        options=set(),
    )
    
    marker_name: bpy.props.StringProperty(
        name="Marker Name",
        description="Declare the marker name manually",
        options=set(),
    )
    
    function_a: bpy.props.StringProperty(
        name="Function A",
        options=set(),
    )
    
    function_b: bpy.props.StringProperty(
        name="Function B",
        options=set(),
    )
    
    looping: bpy.props.BoolProperty(
        name="Looping",
        options=set(),
    )
    
    # script
    
    script: bpy.props.StringProperty(
        name="Script",
        description="The script that should be executed at the given frame"
    )
    
    text: bpy.props.PointerProperty(
        name="Script Text",
        type=bpy.types.Text,
        options=set(),
    )
    
    script_type: bpy.props.EnumProperty(
        name="Script Type",
        description="Type of script to execute",
        options=set(),
        items=[
            ("CUSTOM", "Custom", "If this text matches the name of a text file in the Blender text editor, the contents of that file will be used. Otherwise, the text will be used directly"),
            ("WEAPON_TRIGGER_START", "Start Firing Weapon", "Causes a weapon to start shooting"),
            ("WEAPON_TRIGGER_STOP", "Stop Firing Weapon", "Causes a weapon to stop shooting"),
            ("SET_VARIANT", "Set Object Variant", "Sets an object variant to the named variant"),
            ("SET_PERMUTATION", "Set Object Permutation", "Sets an objects permutation(s). Leave the region blank for all regions"),
            ("SET_REGION_STATE", "Set Region State", "Sets a region(s) state. Leave region blank for all regions"),
            ("SET_MODEL_STATE_PROPERTY", "Set Model State Property", ""),
            ('HIDE', "Hide Object", ""),
            ('UNHIDE', "Unhide Object", ""),
            ('DESTROY', "Destroy Object", ""),
            ('FADE_IN', "Fade in from Color", ""),
            ('FADE_OUT', "Fade out to Color", ""),
            ('SET_TITLE', "Set Cinematic Title", ""),
            ('SHOW_HUD', "Show Player HUD", ""),
            ('HIDE_HUD', "Hide Player HUD", ""),
            ('OBJECT_CANNOT_DIE', "Make Object Immortal", ""),
            ('OBJECT_CAN_DIE', "Make Object Mortal", ""),
            ('OBJECT_PROJECTILE_COLLISION_ON', "Projectiles Collide With Object", ""),
            ('OBJECT_PROJECTILE_COLLISION_OFF', "Projectiles Pass Through Object", ""),
            ('DAMAGE_OBJECT', "Damage Object", ""),
        ]
    )
    
    script_text: bpy.props.StringProperty()
    
    script_object: bpy.props.PointerProperty(
        name="Object",
        type=bpy.types.Object,
        poll=poll_actor,
        options=set(),
    )
    
    script_variant: bpy.props.StringProperty(
        name="Script Variant",
    )
    script_region: bpy.props.StringProperty(
        name="Script Region",
    )
    script_permutation: bpy.props.StringProperty(
        name="Script Permutation",
    )
    script_state: bpy.props.EnumProperty(
        name="Script State",
        options=set(),
        items=[
            ("standard", "Standard", ""),
            ("minor_damage", "Minor Damage", ""),
            ("medium_damage", "Medium Damage", ""),
            ("major_damage", "Major Damage", ""),
            ("destroyed", "Destroyed", ""),
        ]
    )
    script_state_property: bpy.props.EnumProperty(
        name="Script State Property",
        options=set(),
        items=[
            ("0", "Blurred", ""),
            ("1", "Hella Blurred", ""),
            ("2", "Unshielded", ""),
            ("3", "Battery Depleted", ""),
        ]
    )
    script_color: bpy.props.FloatVectorProperty( # converted to 3 args of RGB float values
        name="Script Argument Color",
        subtype='COLOR',
        options=set(),
        size=3,
        default=(0.0, 0.0, 0.0),
        min=0,
        max=1,
    )
    script_seconds: bpy.props.FloatProperty( # converted to ticks with seconds * 30 for scripts
        name="Script Argument Seconds",
        options=set(),
        default=1,
        min=0,
    )
    script_damage: bpy.props.FloatProperty(
        name="Script Damage",
        default=50,
        options=set(),
    )
    
    script_bool: bpy.props.BoolProperty(options=set(),)

class NWO_ScenePropertiesGroup(PropertyGroup):
    # CINEMATIC EVENTS
    cinematic_events: bpy.props.CollectionProperty(
        name="Cinematic Events",
        options=set(),
        type=NWO_CinematicEvent,
    )
    
    active_cinematic_event_index: bpy.props.IntProperty(
        name="Active Cinematic Event Index",
        options=set(),
    )
    
    export_version: bpy.props.StringProperty(options={'HIDDEN'})
    
    def get_game_frame(self):
        return self.id_data.frame_current - self.id_data.frame_start + int(utils.is_corinth(bpy.context))
    
    def set_game_frame(self, value):
        # self.id_data.frame_set(value + self.id_data.frame_start)
        self.id_data.frame_current = value + self.id_data.frame_start 
    
    # CINEMATIC SCENE
    game_frame: bpy.props.IntProperty(
        name="Game Frame",
        description="The current blender frame represented as the frame index the game uses",
        get=get_game_frame,
        set=set_game_frame,
        min=0,
    )
    
    def get_current_shot(self):
        scene = self.id_data
        markers = utils.get_timeline_markers(scene)
        frame_current = scene.frame_current
        if frame_current < all([m.frame for m in markers]):
            return 1
        for idx, marker in enumerate(markers):
            if marker.frame <= frame_current and (len(markers) - 1 == idx or markers[idx + 1].frame > frame_current):
                return idx + 2
            
        return 1
    
    def set_current_shot(self, value):
        scene = self.id_data
        if value == 1:
            scene.frame_current = scene.frame_start
            return
        markers = utils.get_timeline_markers(scene)
        marker_index = value - 2
        scene.frame_current = markers[marker_index].frame
    
    current_shot: bpy.props.IntProperty(
        name="Current Shot",
        description="Current cinematic shot indicated by the current frame",
        get=get_current_shot,
        set=set_current_shot,
        min=1,
        max=65,
    )
    
    def get_shot_frame(self):
        scene = self.id_data
        marker_index = self.current_shot - 2
        if marker_index < 0:
            return scene.frame_current - scene.frame_start
        markers = utils.get_timeline_markers(scene) 
        marker_frame = markers[marker_index].frame
        return scene.frame_current - marker_frame + int(utils.is_corinth(bpy.context))
        
    def set_shot_frame(self, value):
        scene = self.id_data
        markers = utils.get_timeline_markers(scene)
        marker_index = self.current_shot - 2
        if marker_index < 0:
            frame = scene.frame_start + value
        else:
            frame = markers[marker_index].frame + value
            
        # check that frame is in current shot
        if len(markers) > marker_index + 1:
            next_marker_frame = markers[marker_index + 1].frame
            if frame >= next_marker_frame:
                scene.frame_current = next_marker_frame - 1
                return
            
        scene.frame_current = min(frame, scene.frame_end)
    
    shot_frame: bpy.props.IntProperty(
        name="Shot Frame",
        description="Current game frame of the current shot",
        get=get_shot_frame,
        set=set_shot_frame,
        min=0,
    )
    
    # CHILD ASSET
    # child_assets: bpy.props.CollectionProperty(
    #     name="Child Assets",
    #     type=NWO_ChildAsset,
    #     options=set(),
    # )
    
    # active_child_asset_index: bpy.props.IntProperty(
    #     name="Active Child Asset Index",
    #     options=set(),
    # )
    
    is_child_asset: bpy.props.BoolProperty(
        name="Child Asset",
        description="Mark if this asset is a child of another. Setting this will prevent this file from building tags, instead only building intermediary data for use by its parent file"
    )
    
    parent_asset: bpy.props.StringProperty(
        name="Parent Blend",
        description="Data relative filepath to the parent blend"
    )
    parent_sidecar: bpy.props.StringProperty(
        name="Parent Sidecar",
        description="Data relative filepath to the parent sidecar"
    )

    mod_name: bpy.props.StringProperty(options={'HIDDEN'}, default="")
    
    def cinematic_scenario_clean_tag_path(self, context):
        self["cinematic_scenario"] = utils.clean_tag_path(self["cinematic_scenario"], "scenario").strip('"')
    
    cinematic_scenario: bpy.props.StringProperty(
        name="Scenario",
        description="The tag relative path to the scenario which this cinematic should be added to",
        options=set(),
        update=cinematic_scenario_clean_tag_path,
    )
    
    cinematic_zone_set: bpy.props.StringProperty(
        name="Zone Set",
        description="The name of the zone set which this cinematic should be loaded in. If this zone set doesn't already exist, it will be created for you with all bsps active by default",
        options=set(),
    )
    
    cinematic_anchor: bpy.props.PointerProperty(
        name="Cinematic Anchor",
        description="The object to use as the anchor point (or reference point) of the cinematic scene. On export this anchor point will be added to the specified scenario if you have set one",
        type=bpy.types.Object,
        options=set(),
    )
    
    # ANIMATION
    def update_active_animation_index(self, context):
        previous_animation = None
        if self.active_animation_index > -1:
            animation = self.animations[self.active_animation_index]
            if self.previous_active_animation_index > -1:
                if len(self.animations) > self.previous_active_animation_index:
                    previous_animation = self.animations[self.previous_active_animation_index]
                if previous_animation:
                    utils.clear_animation(previous_animation)
                    
            for track in animation.action_tracks:
                if track.object and track.action:
                    slot_id = ""
                    if track.action.slots:
                        if track.action.slots.active:
                            slot_id = track.action.slots.active.identifier
                        else:
                            slot_id = track.action.slots[0].identifier

                    if track.is_shape_key_action:
                        if track.object.type == 'MESH' and track.object.data.shape_keys and track.object.data.shape_keys.animation_data:
                            track.object.data.shape_keys.animation_data.last_slot_identifier = slot_id
                            track.object.data.shape_keys.animation_data.action = track.action
                    else:
                        if track.object.animation_data:
                            track.object.animation_data.last_slot_identifier = slot_id
                            track.object.animation_data.action = track.action
                        if track.object.data.animation_data:
                            track.object.data.animation_data.last_slot_identifier = slot_id
                            track.object.data.animation_data.action = track.action

            if utils.get_prefs().sync_timeline_range:
                bpy.ops.nwo.set_timeline()
                
        self.previous_active_animation_index = self.active_animation_index
    
    active_animation_index: bpy.props.IntProperty(
        default=-1,
        options=set(),
        update=update_active_animation_index,
    )
    
    previous_active_animation_index: bpy.props.IntProperty(default=-1, options={'HIDDEN'})
    
    animations: bpy.props.CollectionProperty(type=NWO_AnimationPropertiesGroup)
    
    exclude_first_frame: bpy.props.BoolProperty(options=set())
    exclude_last_frame: bpy.props.BoolProperty(options=set())
    
    animation_copies_active_index: bpy.props.IntProperty(options=set())
    animation_copies: bpy.props.CollectionProperty(type=NWO_AnimationCopiesItems, options=set())
    
    # animation_composites_active_index: bpy.props.IntProperty(options=set())
    # animation_composites: bpy.props.CollectionProperty(type=NWO_AnimationCompositesItems, options=set())
    
    # zone_sets_active_index: bpy.props.IntProperty(options=set())
    # zone_sets: bpy.props.CollectionProperty(type=NWO_ZoneSets_ListItems, options=set())
    
    # user_removed_all_zone_set: bpy.props.BoolProperty()

    def items_mesh_type(self, context):
        """Function to handle context for mesh enum lists"""
        h4 = utils.is_corinth(context)
        items = []

        if utils.poll_ui("decorator_set"):
            items.append(
                (
                    "_connected_geometry_mesh_type_decorator",
                    "Decorator",
                    "Decorator mesh type. Supports up to 4 level of detail variants",
                    get_icon_id("decorator"),
                    0,
                )
            )
        elif utils.poll_ui(("model", "sky", "particle_model")):
            items.append(
                (
                    "_connected_geometry_mesh_type_render",
                    "Render",
                    "Render only geometry",
                    get_icon_id("render_geometry"),
                    0,
                )
            )
            if utils.poll_ui("model"):
                items.append(
                    (
                        "_connected_geometry_mesh_type_collision",
                        "Collision",
                        "Collision only geometry. Acts as bullet collision and for scenery also provides player collision",
                        get_icon_id("collider"),
                        1,
                    )
                )
                items.append(
                    (
                        "_connected_geometry_mesh_type_physics",
                        "Physics",
                        "Physics only geometry. Uses havok physics to interact with static and dynamic meshes",
                        get_icon_id("physics"),
                        2,
                    )
                )
                # if not h4: NOTE removing these for now until I figure out how they work
                #     items.append(('_connected_geometry_mesh_type_object_instance', 'Flair', 'Instanced mesh for models. Can be instanced across mutliple permutations', get_icon_id("flair"), 3))
        elif utils.poll_ui("scenario"):
            items.append(
                (
                    "_connected_geometry_mesh_type_structure",
                    "Structure",
                    "Structure bsp geometry. By default provides render and bullet/player collision",
                    get_icon_id("structure"),
                    0,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_poop",
                    "Instance",
                    "Instanced geometry. Geometry capable of cutting through structure mesh",
                    get_icon_id("instance"),
                    1,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_poop_collision",
                    "Collision",
                    "Non rendered geometry which provides collision only",
                    get_icon_id("collider"),
                    2,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_plane",
                    "Plane",
                    "Non rendered geometry which provides various utility functions in a bsp. The planes can cut through bsp geometry. Supports portals, fog planes, and water surfaces",
                    get_icon_id("surface"),
                    3,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_volume",
                    "Volume",
                    "Non rendered geometry which defines regions for special properties",
                    get_icon_id("volume"),
                    4,
                )
            )
        elif utils.poll_ui("prefab"):
            items.append(
                (
                    "_connected_geometry_mesh_type_poop",
                    "Instance",
                    "Instanced geometry. Geometry capable of cutting through structure mesh",
                    get_icon_id("instance"),
                    0,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_poop_collision",
                    "Collision",
                    "Non rendered geometry which provides collision only",
                    get_icon_id("collider"),
                    1,
                )
            )
            items.append(
                (
                    "_connected_geometry_mesh_type_cookie_cutter",
                    "Cookie Cutter",
                    "Non rendered geometry which cuts out the region it defines from the pathfinding grid",
                    get_icon_id("cookie_cutter"),
                    2,
                )
            )

        return items

    def apply_props(self, context):
        for ob in context.scene.objects:
            ob_nwo = ob.data.nwo

            if ob_nwo.mesh_type == "":
                if self.asset_type == "decorator_set":
                    ob_nwo.mesh_type = "_connected_geometry_mesh_type_decorator"
                elif self.asset_type == "scenario":
                    ob_nwo.mesh_type = "_connected_geometry_mesh_type_structure"
                elif self.asset_type == "prefab":
                    ob_nwo.mesh_type = "_connected_geometry_mesh_type_poop"
                else:
                    ob_nwo.mesh_type = "_connected_geometry_mesh_type_render"
    
    def update_asset_type(self, context):
        if self.asset_type == 'animation':
            context.scene.nwo_halo_launcher.open_model_animation_graph = True

    asset_type: bpy.props.EnumProperty(
        name="Asset Type",
        options=set(),
        description="The type of asset you are creating",
        items=asset_type_items,
        update=update_asset_type,
    )
    
    asset_animation_type: bpy.props.EnumProperty(
        name="Animation Type",
        options=set(),
        items=[
            ("first_person", "First Person", "For creating a first person animation graph"),
            ("standalone", "Standalone", "For creating a standalone animation graph, e.g. for use in a vingette"),
        ]
    )

    forward_direction: bpy.props.EnumProperty(
        name="Scene Forward",
        options=set(),
        description="The forward direction you are using for the scene. By default Halo uses X forward. Whichever option is set as the forward direction in Blender will be oriented to X forward in game i.e. a model facing -Y in Blender will face X in game",
        default="y-",
        items=[
            ("y-", "-Y", "Model is facing Y negative"),
            ("y", "Y", "Model is facing Y positive"),
            ("x-", "-X", "Model is facing X negative"),
            ("x", "X", "Model is facing X positive"),   
        ],
    )

    output_biped: bpy.props.BoolProperty(
        name="Biped",
        description="",
        default=False,
        options=set(),
    )
    output_crate: bpy.props.BoolProperty(
        name="Crate",
        description="",
        default=False,
        options=set(),
    )
    output_creature: bpy.props.BoolProperty(
        name="Creature",
        description="",
        default=False,
        options=set(),
    )
    output_device_control: bpy.props.BoolProperty(
        name="Device Control",
        description="",
        default=False,
        options=set(),
    )
    output_device_dispenser: bpy.props.BoolProperty(
        name="Device Dispenser",
        description="",
        default=False,
        options=set(),
    )
    output_device_machine: bpy.props.BoolProperty(
        name="Device Machine",
        description="",
        default=False,
        options=set(),
    )
    output_device_terminal: bpy.props.BoolProperty(
        name="Device Terminal",
        description="",
        default=False,
        options=set(),
    )
    output_effect_scenery: bpy.props.BoolProperty(
        name="Effect Scenery",
        description="",
        default=False,
        options=set(),
    )
    output_equipment: bpy.props.BoolProperty(
        name="Equipment",
        description="",
        default=False,
        options=set(),
    )
    output_giant: bpy.props.BoolProperty(
        name="Giant",
        description="",
        default=False,
        options=set(),
    )
    output_scenery: bpy.props.BoolProperty(
        name="Scenery",
        description="",
        default=True,
        options=set(),
    )
    output_vehicle: bpy.props.BoolProperty(
        name="Vehicle",
        description="",
        default=False,
        options=set(),
    )
    output_weapon: bpy.props.BoolProperty(
        name="Weapon",
        description="",
        default=False,
        options=set(),
    )
    
    use_as_fp_render_model: bpy.props.BoolProperty(
        name="Use Render Model for First Person",
        description="Sets the first person render model reference for this weapon tag to the render model exported by this file",
        default=True,
    )
    
    def template_model_clean_tag_path(self, context):
        self["template_model"] = utils.clean_tag_path(
            self["template_model"],
            "model"
        ).strip('"')
    def template_biped_clean_tag_path(self, context):
        self["template_biped"] = utils.clean_tag_path(
            self["template_biped"],
            "biped"
        ).strip('"')
    def template_crate_clean_tag_path(self, context):
        self["template_crate"] = utils.clean_tag_path(
            self["template_crate"],
            "crate"
        ).strip('"')
    def template_creature_clean_tag_path(self, context):
        self["template_creature"] = utils.clean_tag_path(
            self["template_creature"],
            "creature"
        ).strip('"')
    def template_device_control_clean_tag_path(self, context):
        self["template_device_control"] = utils.clean_tag_path(
            self["template_device_control"],
            "device_control"
        ).strip('"')
    def template_device_dispenser_clean_tag_path(self, context):
        self["template_device_dispenser"] = utils.clean_tag_path(
            self["template_device_dispenser"],
            "device_dispenser"
        ).strip('"')
    def template_device_machine_clean_tag_path(self, context):
        self["template_device_machine"] = utils.clean_tag_path(
            self["template_device_machine"],
            "device_machine"
        ).strip('"')
    def template_device_terminal_clean_tag_path(self, context):
        self["template_device_terminal"] = utils.clean_tag_path(
            self["template_device_terminal"],
            "device_terminal"
        ).strip('"')
    def template_effect_scenery_clean_tag_path(self, context):
        self["template_effect_scenery"] = utils.clean_tag_path(
            self["template_effect_scenery"],
            "effect_scenery"
        ).strip('"')
    def template_equipment_clean_tag_path(self, context):
        self["template_equipment"] = utils.clean_tag_path(
            self["template_equipment"],
            "equipment"
        ).strip('"')
    def template_giant_clean_tag_path(self, context):
        self["template_giant"] = utils.clean_tag_path(
            self["template_giant"],
            "giant"
        ).strip('"')
    def template_scenery_clean_tag_path(self, context):
        self["template_scenery"] = utils.clean_tag_path(
            self["template_scenery"],
            "scenery"
        ).strip('"')
    def template_vehicle_clean_tag_path(self, context):
        self["template_vehicle"] = utils.clean_tag_path(
            self["template_vehicle"],
            "vehicle"
        ).strip('"')
    def template_weapon_clean_tag_path(self, context):
        self["template_weapon"] = utils.clean_tag_path(self["template_weapon"], "weapon").strip('"')
        if utils.get_asset_tag('.weapon'):
            bpy.ops.nwo.update_template().tag_type = 'vehicle'
            
    
    template_model: bpy.props.StringProperty(
        name="Model Template",
        description="Tag relative path to the model tag to use as a base if this asset does not already have one",
        update=template_model_clean_tag_path,
        options=set(),
    )
    template_biped: bpy.props.StringProperty(
        name="Biped Template",
        description="Tag relative path to the biped tag to use as a base if this asset does not already have one",
        update=template_biped_clean_tag_path,
        options=set(),
    )
    template_crate: bpy.props.StringProperty(
        name="Crate Template",
        description="Tag relative path to the crate tag to use as a base if this asset does not already have one",
        update=template_crate_clean_tag_path,
        options=set(),
    )
    template_creature: bpy.props.StringProperty(
        name="Creature Template",
        description="Tag relative path to the creature tag to use as a base if this asset does not already have one",
        update=template_creature_clean_tag_path,
        options=set(),
    )
    template_device_control: bpy.props.StringProperty(
        name="Device Control Template",
        description="Tag relative path to the device_control tag to use as a base if this asset does not already have one",
        update=template_device_control_clean_tag_path,
        options=set(),
    )
    template_device_dispenser: bpy.props.StringProperty(
        name="Device Dispenser Template",
        description="Tag relative path to the device_dispenser tag to use as a base if this asset does not already have one",
        update=template_device_dispenser_clean_tag_path,
        options=set(),
    )
    template_device_machine: bpy.props.StringProperty(
        name="Device Machine Template",
        description="Tag relative path to the device_machine tag to use as a base if this asset does not already have one",
        update=template_device_machine_clean_tag_path,
        options=set(),
    )
    template_device_terminal: bpy.props.StringProperty(
        name="Device Terminal Template",
        description="Tag relative path to the device_terminal tag to use as a base if this asset does not already have one",
        update=template_device_terminal_clean_tag_path,
        options=set(),
    )
    template_effect_scenery: bpy.props.StringProperty(
        name="Effect Scenery Template",
        description="Tag relative path to the effect_scenery tag to use as a base if this asset does not already have one",
        update=template_effect_scenery_clean_tag_path,
        options=set(),
    )
    template_equipment: bpy.props.StringProperty(
        name="Equipment Template",
        description="Tag relative path to the equipment tag to use as a base if this asset does not already have one",
        update=template_equipment_clean_tag_path,
        options=set(),
    )
    template_giant: bpy.props.StringProperty(
        name="Giant Template",
        description="Tag relative path to the giant tag to use as a base if this asset does not already have one",
        update=template_giant_clean_tag_path,
        options=set(),
    )
    template_scenery: bpy.props.StringProperty(
        name="Scenery Template",
        description="Tag relative path to the scenery tag to use as a base if this asset does not already have one",
        update=template_scenery_clean_tag_path,
        options=set(),
    )
    template_vehicle: bpy.props.StringProperty(
        name="Vehicle Template",
        description="Tag relative path to the vehicle tag to use as a base if this asset does not already have one",
        update=template_vehicle_clean_tag_path,
        options=set(),
    )
    template_weapon: bpy.props.StringProperty(
        name="Weapon Template",
        description="Tag relative path to the weapon tag to use as a base if this asset does not already have one",
        update=template_weapon_clean_tag_path,
        options=set(),
    )

    light_tools_active: bpy.props.BoolProperty(options=set())
    light_tools_pinned: bpy.props.BoolProperty(options=set())
    light_tools_expanded: bpy.props.BoolProperty(default=True, options=set())

    object_properties_active: bpy.props.BoolProperty(options=set())
    object_properties_pinned: bpy.props.BoolProperty(options=set())
    object_properties_expanded: bpy.props.BoolProperty(default=True, options=set())

    material_properties_active: bpy.props.BoolProperty(options=set())
    material_properties_pinned: bpy.props.BoolProperty(options=set())
    material_properties_expanded: bpy.props.BoolProperty(default=True, options=set())

    animation_manager_active: bpy.props.BoolProperty(options=set())
    animation_manager_pinned: bpy.props.BoolProperty(options=set())
    animation_manager_expanded: bpy.props.BoolProperty(default=True, options=set())

    scene_properties_active: bpy.props.BoolProperty(default=False, options=set())
    scene_properties_pinned: bpy.props.BoolProperty(options=set())
    scene_properties_expanded: bpy.props.BoolProperty(default=True, options=set())

    asset_editor_active: bpy.props.BoolProperty(default=True, options=set())
    asset_editor_pinned: bpy.props.BoolProperty(options=set())
    output_tags_expanded: bpy.props.BoolProperty(default=True, options=set())
    asset_editor_expanded: bpy.props.BoolProperty(default=True, options=set())
    # model_overrides_expanded: bpy.props.BoolProperty(default=False, options=set())
    scenario_expanded: bpy.props.BoolProperty(default=False, options=set())
    lighting_expanded: bpy.props.BoolProperty(default=False, options=set())
    # zone_sets_expanded: bpy.props.BoolProperty(default=False, options=set())
    objects_expanded: bpy.props.BoolProperty(default=False, options=set())
    prefabs_expanded: bpy.props.BoolProperty(default=False, options=set())
    model_expanded: bpy.props.BoolProperty(default=True, options=set())
    render_model_expanded: bpy.props.BoolProperty(default=False, options=set())
    collision_model_expanded: bpy.props.BoolProperty(default=False, options=set())
    animation_graph_expanded: bpy.props.BoolProperty(default=False, options=set())
    physics_model_expanded: bpy.props.BoolProperty(default=False, options=set())
    crate_expanded: bpy.props.BoolProperty(default=False, options=set())
    scenery_expanded: bpy.props.BoolProperty(default=False, options=set())
    effect_scenery_expanded: bpy.props.BoolProperty(default=False, options=set())
    device_control_expanded: bpy.props.BoolProperty(default=False, options=set())
    device_machine_expanded: bpy.props.BoolProperty(default=False, options=set())
    device_terminal_expanded: bpy.props.BoolProperty(default=False, options=set())
    device_dispenser_expanded: bpy.props.BoolProperty(default=False, options=set())
    biped_expanded: bpy.props.BoolProperty(default=False, options=set())
    creature_expanded: bpy.props.BoolProperty(default=False, options=set())
    giant_expanded: bpy.props.BoolProperty(default=False, options=set())
    vehicle_expanded: bpy.props.BoolProperty(default=False, options=set())
    weapon_expanded: bpy.props.BoolProperty(default=False, options=set())
    equipment_expanded: bpy.props.BoolProperty(default=False, options=set())
    
    model_rig_expanded: bpy.props.BoolProperty(default=True, options=set())
    rig_controls_expanded: bpy.props.BoolProperty(default=False, options=set())
    rig_object_controls_expanded: bpy.props.BoolProperty(default=False, options=set())
    rig_usages_expanded: bpy.props.BoolProperty(default=False, options=set())
    ik_chains_expanded: bpy.props.BoolProperty(default=False, options=set())
    animation_copies_expanded: bpy.props.BoolProperty(default=False, options=set())
    # animation_composites_expanded: bpy.props.BoolProperty(default=False, options=set())
    
    child_assets_expanded: bpy.props.BoolProperty(default=False, options=set())
    
    asset_shaders_expanded: bpy.props.BoolProperty(default=True, options=set())
    importer_expanded: bpy.props.BoolProperty(default=True, options=set())
    camera_sync_expanded: bpy.props.BoolProperty(default=True, options=set())
    rig_tools_expanded: bpy.props.BoolProperty(default=True, options=set())
    animation_tools_expanded: bpy.props.BoolProperty(default=True, options=set())
    game_animation_copy_settings_expanded: bpy.props.BoolProperty(default=True, options=set())
    bsp_tools_expanded: bpy.props.BoolProperty(default=True, options=set())
    scenario_tools_expanded: bpy.props.BoolProperty(default=True, options=set())
    cache_tools_expanded: bpy.props.BoolProperty(default=True, options=set())
    
    regions_table_expanded: bpy.props.BoolProperty(default=True, options=set())
    permutations_table_expanded: bpy.props.BoolProperty(default=True, options=set())
    object_visibility_expanded: bpy.props.BoolProperty(default=True, options=set())

    mesh_properties_expanded: bpy.props.BoolProperty(default=True, options=set())
    material_attributes_expanded: bpy.props.BoolProperty(default=True, options=set())
    instance_proxies_expanded: bpy.props.BoolProperty(default=True, options=set())
    
    image_properties_expanded: bpy.props.BoolProperty(default=True, options=set())

    sets_manager_active: bpy.props.BoolProperty(options=set())
    sets_manager_pinned: bpy.props.BoolProperty(options=set())
    sets_manager_expanded: bpy.props.BoolProperty(default=True, options=set())

    tools_active : bpy.props.BoolProperty(options=set())
    tools_pinned: bpy.props.BoolProperty(options=set())
    tools_expanded : bpy.props.BoolProperty(default=True, options=set())

    help_active : bpy.props.BoolProperty(options=set())
    help_pinned: bpy.props.BoolProperty(options=set())
    help_expanded : bpy.props.BoolProperty(default=True, options=set())

    settings_active : bpy.props.BoolProperty(options=set())
    settings_pinned: bpy.props.BoolProperty(options=set())
    settings_expanded : bpy.props.BoolProperty(default=True, options=set())

    toolbar_expanded : bpy.props.BoolProperty(
        name="Toggle Foundry Toolbar",
        default=True,
        options=set(),
    )

    def render_clean_tag_path(self, context):
        self["template_render_model"] = utils.clean_tag_path(self["template_render_model"],
            "render_model"
        ).strip('"')
    def collision_clean_tag_path(self, context):
        self["template_collision_model"] = utils.clean_tag_path(
            self["template_collision_model"],
            "collision_model"
        ).strip('"')
    def physics_clean_tag_path(self, context):
        self["template_physics_model"] = utils.clean_tag_path(
            self["template_physics_model"],
            "physics_model"
        ).strip('"')
    def animation_clean_tag_path(self, context):
        self["template_model_animation_graph"] = utils.clean_tag_path(
            self["template_model_animation_graph"],
            "model_animation_graph"
        ).strip('"')
    def render_model_clean_tag_path(self, context):
        self["render_model_path"] = utils.clean_tag_path(
            self["render_model_path"],
            "render_model"
        ).strip('"')

    # render_model_from_blend : bpy.props.BoolProperty(name="Render Model built from Blend", default=True)
    template_render_model : bpy.props.StringProperty(
        name="Render Model Template",
        description="Path to an existing render model tag. If a render model does not already exist for this asset, the specified tag will be copied over prior to export",
        update=render_clean_tag_path,
        options=set(),
        )
    
    # collision_model_from_blend : bpy.props.BoolProperty(name="Collision Model built from Blend", default=True)
    template_collision_model : bpy.props.StringProperty(
        name="Collision Model Template",
        description="Path to an existing collision model tag. If a collison model does not already exist for this asset, the specified tag will be copied over prior to export",
        update=collision_clean_tag_path,
        options=set(),
        )
    
    # physics_model_from_blend : bpy.props.BoolProperty(name="Physics Model built from Blend", default=True)
    template_physics_model : bpy.props.StringProperty(
        name="Physics Model Template",
        description="Path to an existing physics model tag. If a physics model does not already exist for this asset, the specified tag will be copied over prior to export",
        update=physics_clean_tag_path,
        options=set(),
        )
    
    # animation_graph_from_blend : bpy.props.BoolProperty(name="Animation Graph built from Blend", default=True)
    template_model_animation_graph : bpy.props.StringProperty(
        name="Animation Graph Template",
        description="Path to an existing model animation graph tag. If an animation graph does not already exist for this asset, the specified tag will be copied over prior to export. This also ensures that the imported node order for your render model (and collision/physics) matches that of the nodes in the given graph",
        update=animation_clean_tag_path,
        options=set(),
        )
    
    render_model_path : bpy.props.StringProperty(
        name="Render Model Path",
        description="Path to the render model used by this animation. Ensures bone order matches the specified model",
        update=render_model_clean_tag_path,
        options=set(),
        )
    
    instance_proxy_running : bpy.props.BoolProperty(options=set())

    # shader_sync_active : bpy.props.BoolProperty(
    #     name="Shader Sync",
    #     description="Sync's the active material with the corresponding Halo Shader/Material tag. Only active when the material has been marked as linked to game",
    #     options=set()
    # )
    
    # material_sync_rate : bpy.props.FloatProperty(
    #     name="Sync Rate",
    #     description="How often Halo Material Sync should refresh",
    #     min=0.001,
    #     default=0.01,
    #     max=3,
    #     subtype='TIME_ABSOLUTE',
    #     options=set(),
    # )
    
    # light_sync_active : bpy.props.BoolProperty(
    #     name="Light Sync",
    #     description="",
    #     options=set()
    # )
    
    # light_sync_rate : bpy.props.FloatProperty(
    #     name="Sync Rate",
    #     description="How often Light Sync should refresh",
    #     min=0.001,
    #     default=0.1,
    #     max=3,
    #     subtype='TIME_ABSOLUTE',
    #     options=set(),
    # )
    
    lights_export_on_save : bpy.props.BoolProperty(
        name="Export Lights on Blender Save",
        description="Exports all lights from Blender whenever the Blend file is saved",
    )
    
    prefabs_export_on_save : bpy.props.BoolProperty(
        name="Export Prefabs on Blender Save",
        description="Exports all prefabs from Blender whenever the Blend file is saved",
    )
    
    # object_sync_active : bpy.props.BoolProperty(
    #     name="Object Sync",
    #     description="",
    #     options=set()
    # )
    
    # object_sync_rate : bpy.props.FloatProperty(
    #     name="Sync Rate",
    #     description="How often Object Sync should refresh",
    #     min=0.001,
    #     default=0.01,
    #     max=3,
    #     subtype='TIME_ABSOLUTE',
    #     options=set(),
    # )
    
    camera_sync_active : bpy.props.BoolProperty(
        name="Camera Sync",
        description="",
        options=set()
    )

    scene_project : bpy.props.StringProperty(
        name="Project",
        options=set(),
    )
    
    storage_only: bpy.props.BoolProperty(options=set())

    # TABLES

    regions_table: bpy.props.CollectionProperty(type=NWO_Regions_ListItems, options=set())
    regions_table_active_index: bpy.props.IntProperty(options=set())
    permutations_table: bpy.props.CollectionProperty(type=NWO_Permutations_ListItems, options=set())
    permutations_table_active_index: bpy.props.IntProperty(options=set())
    bsp_table: bpy.props.CollectionProperty(type=NWO_BSP_ListItems, options=set())
    bsp_active_index: bpy.props.IntProperty(options=set())
    global_material_table: bpy.props.CollectionProperty(type=NWO_GlobalMaterial_ListItems, options=set())
    global_material_active_index: bpy.props.IntProperty(options=set())
    
    # Rig Validation
    
    armature_has_parent: bpy.props.BoolProperty(options=set())
    armature_bad_transforms: bpy.props.BoolProperty(options=set())
    multiple_root_bones: bpy.props.BoolProperty(options=set())
    invalid_root_bone: bpy.props.BoolProperty(options=set())
    # needs_pose_bones: bpy.props.BoolProperty(options=set())
    too_many_bones: bpy.props.BoolProperty(options=set())
    bone_names_too_long: bpy.props.BoolProperty(options=set())
    pose_bones_bad_transforms: bpy.props.BoolProperty(options=set())
    
    # RIG PROPS
    main_armature: bpy.props.PointerProperty(
        name="Main Armature",
        description="",
        type=bpy.types.Object,
        poll=poll_armature,
        options=set(),
    )
    # support_armature_a: bpy.props.PointerProperty(
    #     name="Support Armature",
    #     description="",
    #     type=bpy.types.Object,
    #     poll=poll_armature,
    #     options=set(),
    # )
    # support_armature_a_parent_bone : bpy.props.StringProperty(name='Parent Bone', description='Specify the bone from the main armature which the root bone of this support armature should join to at export', options=set())

    
    # support_armature_b: bpy.props.PointerProperty(
    #     name="Support Armature",
    #     description="",
    #     type=bpy.types.Object,
    #     poll=poll_armature,
    #     options=set(),
    # )
    # support_armature_b_parent_bone : bpy.props.StringProperty(name='Parent Bone', description='Specify the bone from the main armature which the root bone of this support armature should join to at export', options=set())

    
    # support_armature_c: bpy.props.PointerProperty(
    #     name="Support Armature",
    #     description="",
    #     type=bpy.types.Object,
    #     poll=poll_armature,
    #     options=set(),
    # )
    # support_armature_c_parent_bone : bpy.props.StringProperty(name='Parent Bone', description='Specify the bone from the main armature which the root bone of this support armature should join to at export', options=set())
    
    node_usage_physics_control : bpy.props.StringProperty(name="Physics Control", options=set())
    node_usage_camera_control : bpy.props.StringProperty(name="Camera Control", options=set())
    node_usage_origin_marker : bpy.props.StringProperty(name="Origin Marker", options=set())
    node_usage_left_clavicle : bpy.props.StringProperty(name="Left Clavicle", options=set())
    node_usage_left_upperarm : bpy.props.StringProperty(name="Left Upperarm", options=set())
    node_usage_pose_blend_pitch : bpy.props.StringProperty(name="Pose Blend Pitch", options=set())
    node_usage_pose_blend_yaw : bpy.props.StringProperty(name="Pose Blend Yaw", options=set())
    node_usage_pedestal : bpy.props.StringProperty(name="Pedestal", options=set())
    node_usage_pelvis : bpy.props.StringProperty(name="Pelvis", options=set())
    node_usage_left_foot : bpy.props.StringProperty(name="Left Foot", options=set())
    node_usage_right_foot : bpy.props.StringProperty(name="Right Foot", options=set())
    node_usage_damage_root_gut : bpy.props.StringProperty(name="Damage Root Gut", options=set())
    node_usage_damage_root_chest : bpy.props.StringProperty(name="Damage Root Chest", options=set())
    node_usage_damage_root_head : bpy.props.StringProperty(name="Damage Root Head", options=set())
    node_usage_damage_root_left_shoulder : bpy.props.StringProperty(name="Damage Root Left Shoulder", options=set())
    node_usage_damage_root_left_arm : bpy.props.StringProperty(name="Damage Root Left Arm", options=set())
    node_usage_damage_root_left_leg : bpy.props.StringProperty(name="Damage Root Left Leg", options=set())
    node_usage_damage_root_left_foot : bpy.props.StringProperty(name="Damage Root Left Foot", options=set())
    node_usage_damage_root_right_shoulder : bpy.props.StringProperty(name="Damage Root Right Shoulder", options=set())
    node_usage_damage_root_right_arm : bpy.props.StringProperty(name="Damage Root Right Arm", options=set())
    node_usage_damage_root_right_leg : bpy.props.StringProperty(name="Damage Root Right Leg", options=set())
    node_usage_damage_root_right_foot : bpy.props.StringProperty(name="Damage Root Right Foot", options=set())
    node_usage_left_hand : bpy.props.StringProperty(name="Left Hand", options=set())
    node_usage_right_hand : bpy.props.StringProperty(name="Right Hand", options=set())
    node_usage_weapon_ik : bpy.props.StringProperty(name="Weapon IK", options=set())
    
    control_aim: bpy.props.StringProperty(name='Aim Control', options=set())
    
    # Scale
    def scale_update(self, context):
        scene_scale = 1
        world_units = self.scale_display == 'world_units'
        match self.scale:
            case 'blender':
                scene_scale = 1 / 3.048 if world_units else 1
                factor = 0.03048
            case 'max':
                scene_scale = 0.01 if world_units else 0.03048
                factor = 1 / 0.03048
        scale_val = self.get("scale")
        if scale_val is not None and scale_val != self.old_scale:
            self.old_scale = self["scale"]
            for workspace in bpy.data.workspaces:
                for screen in workspace.screens:
                    for area in screen.areas:
                        if area.type == "VIEW_3D":
                            for space in area.spaces:
                                if space.type == "VIEW_3D":
                                    space.clip_start *= factor
                                    space.clip_end *= factor
        
        
        if self.scale_display == 'world_units':
            context.scene.unit_settings.system = 'METRIC'
            context.scene.unit_settings.length_unit = 'METERS'
        context.scene.unit_settings.scale_length = scene_scale
    
    def scale_items(self, context):
        items = []
        items.append(('blender', 'Blender Scale', "For working at a Blender friendly scale. Scene will be appropriately scaled at export to account for Halo's scale", 'BLENDER', 0))
        items.append(('max', 'Halo Scale', "Scene is exported without scaling. Use this if you're working with imported 3DS Max Files, or legacy assets such as JMS/ASS files which have not been scaled down for Blender", get_icon_id("halo_scale"), 1))
        return items
    
    def scale_display_items(self, context):
        items = []
        unit_length: str = context.scene.unit_settings.length_unit
        items.append(('meters', unit_length, "Meters displayed in Blender are equal to 0.328 in game world units", 'DRIVER_DISTANCE', 0))
        items.append(('world_units', 'World Units'.upper(), "Meters displayed in Blender are equal to in game world units i.e. 1 Meter = 1 World Unit. Use this when you want the units displayed in blender to match the units shown in Sapien", get_icon_id('wu_scale'), 1))
        return items
    
    scale: bpy.props.EnumProperty(
        name="Scale",
        default=0,
        options=set(),
        description="Select the scaling for this asset. Scale is applied at export to ensure units displayed in Blender match with in game units",
        items=scale_items,
        update=scale_update,
    )
    
    old_scale: bpy.props.IntProperty(options={'HIDDEN'})
    
    scale_display: bpy.props.EnumProperty(
        name="Scale Display",
        options=set(),
        description="Select whether to display scale as meters or world units. This has no affect on the scale of the exported asset",
        items=scale_display_items,
        update=scale_update,
    )
    
    maintain_marker_axis: bpy.props.BoolProperty(
        name="Maintain Marker Axis",
        options=set(),
        default=True,
        description="Maintains the forward direction of markers when the scene coordinate system is transformed. Use this if you're working with mesh markers and want their orientation in Blender to match their in game orientation",
    )
    
    export_in_progress: bpy.props.BoolProperty(options=set())
    transforming: bpy.props.BoolProperty(options=set())
        
    def poll_camera_track_camera(self, object: bpy.types.Object):
        return object.type == 'CAMERA'
    
    camera_track_camera: bpy.props.PointerProperty(type=bpy.types.Object, poll=poll_camera_track_camera, options=set())
    
    ik_chains: bpy.props.CollectionProperty(
        type=NWO_IKChain,
    )
    
    ik_chains_active_index: bpy.props.IntProperty(options=set())
    
    object_controls: bpy.props.CollectionProperty(
        type=NWO_ControlObjects,
        options=set(),
    )
    
    object_controls_active_index: bpy.props.IntProperty(options=set())
    
    keyframe_sync_active: bpy.props.BoolProperty(options=set())
    
    default_animation_compression: bpy.props.EnumProperty(
        name="Default Animation Compression",
        description="The default animation the game applies to animations",
        options=set(),
        items=[
            ("Automatic", "Automatic", "Compression is determined by the game during animation import"),
            ("Uncompressed", "Uncompressed", "No compression"),
            ("Medium", "Medium", "Medium compression"),
            ("Rough", "Rough", "Highest level of compression"),
        ]
    )
    
    # def get_parent_animation_graph(self):
    #     asset_graph = get_asset_animation_graph()
    #     if asset_graph:
    #         with AnimationTag(path=asset_graph) as animation:
    #             parent_graph = animation.get_parent_graph()
    #             if parent_graph:
    #                 return parent_graph
    #             else:
    #                 return self.parent_animation_graph_helper
    #     else:
    #         return self.parent_animation_graph_helper
                
    # def set_parent_animation_graph(self, value):
    #     asset_graph = get_asset_animation_graph()
    #     if asset_graph and Path(asset_graph).exists():
    #         with AnimationTag(path=asset_graph) as animation:
    #             animation.set_parent_graph(value)
        
    def parent_animation_clean_tag_path(self, context):
        self["parent_animation_graph"] = utils.clean_tag_path(
            self["parent_animation_graph"],
            "model_animation_graph"
        ).strip('"')
        self.parent_animation_graph_helper = self["parent_animation_graph"]
    
    parent_animation_graph: bpy.props.StringProperty(
        name="Parent Animation Graph",
        description="The parent graph of the animations exported from this scene. Allows your animation graph to use and override animations from the parent",
        update=parent_animation_clean_tag_path,
        # get=get_parent_animation_graph,
        # set=set_parent_animation_graph,
        options=set(),
    )
    
    parent_animation_graph_helper: bpy.props.StringProperty(options=set())
    
    scenario_type: bpy.props.EnumProperty( # this is only used at asset creation
        name="Scenario Type",
        description="Select whether this is a Solo, Multiplayer, or Main Menu scenario",
        options=set(),
        items=[
            ("solo", "Singleplayer", "For campaign levels, but also valid for Firefight & Spartan Ops scenarios"),
            ("multiplayer", "Multiplayer", "For multiplayer maps"),
            ("main menu", "Main Menu", "For main menu maps"),
        ]
    )
    
    def update_connected_geometry_mesh_type_default_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_default')
    def update_connected_geometry_mesh_type_collision_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_collision')
    def update_connected_geometry_mesh_type_physics_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_physics')
    def update_connected_geometry_mesh_type_object_instance_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_object_instance')
    def update_connected_geometry_mesh_type_structure_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_structure')
    def update_connected_geometry_mesh_type_seam_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_seam')
    def update_connected_geometry_mesh_type_portal_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_portal')
    def update_connected_geometry_mesh_type_water_surface_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_water_surface')
    def update_connected_geometry_mesh_type_poop_vertical_rain_sheet_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_poop_vertical_rain_sheet')
    def update_connected_geometry_mesh_type_planar_fog_volume_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_planar_fog_volume')
    def update_connected_geometry_mesh_type_lightmap_region_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_lightmap_region')
    def update_connected_geometry_mesh_type_boundary_surface_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_boundary_surface')
    def update_connected_geometry_mesh_type_obb_volume_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_obb_volume')
    def update_connected_geometry_mesh_type_cookie_cutter_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_cookie_cutter')
    def update_connected_geometry_mesh_type_poop_rain_blocker_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_mesh_type_poop_rain_blocker')
    
    def update_connected_geometry_marker_type_model_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_model')
    def update_connected_geometry_marker_type_effects_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_effects')
    def update_connected_geometry_marker_type_garbage_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_garbage')
    def update_connected_geometry_marker_type_hint_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_hint')
    def update_connected_geometry_marker_type_pathfinding_sphere_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_pathfinding_sphere')
    def update_connected_geometry_marker_type_physics_constraint_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_physics_constraint')
    def update_connected_geometry_marker_type_target_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_target')
    def update_connected_geometry_marker_type_game_instance_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_game_instance')
    def update_connected_geometry_marker_type_airprobe_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_airprobe')
    def update_connected_geometry_marker_type_envfx_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_envfx')
    def update_connected_geometry_marker_type_lightCone_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_marker_type_lightCone')

    def update_connected_geometry_object_type_frame_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_object_type_frame')
    def update_connected_geometry_object_type_light_visible(self, context): bpy.ops.nwo.hide_object_type(object_type = '_connected_geometry_object_type_light')
    
    connected_geometry_mesh_type_default_visible: bpy.props.BoolProperty(default=True, options=set(), name="Default", update=update_connected_geometry_mesh_type_default_visible)
    connected_geometry_mesh_type_collision_visible: bpy.props.BoolProperty(default=True, options=set(), name="Collision", update=update_connected_geometry_mesh_type_collision_visible)
    connected_geometry_mesh_type_physics_visible: bpy.props.BoolProperty(default=True, options=set(), name="Physics", update=update_connected_geometry_mesh_type_physics_visible)
    connected_geometry_mesh_type_object_instance_visible: bpy.props.BoolProperty(default=True, options=set(), name="Object Instance", update=update_connected_geometry_mesh_type_object_instance_visible)
    connected_geometry_mesh_type_structure_visible: bpy.props.BoolProperty(default=True, options=set(), name="Structure", update=update_connected_geometry_mesh_type_structure_visible)
    connected_geometry_mesh_type_seam_visible: bpy.props.BoolProperty(default=True, options=set(), name="Seam", update=update_connected_geometry_mesh_type_seam_visible)
    connected_geometry_mesh_type_portal_visible: bpy.props.BoolProperty(default=True, options=set(), name="Portal", update=update_connected_geometry_mesh_type_portal_visible)
    connected_geometry_mesh_type_water_surface_visible: bpy.props.BoolProperty(default=True, options=set(), name="Water Surface", update=update_connected_geometry_mesh_type_water_surface_visible)
    connected_geometry_mesh_type_poop_vertical_rain_sheet_visible: bpy.props.BoolProperty(default=True, options=set(), name="Rain Sheet", update=update_connected_geometry_mesh_type_poop_vertical_rain_sheet_visible)
    connected_geometry_mesh_type_planar_fog_volume_visible: bpy.props.BoolProperty(default=True, options=set(), name="Fog", update=update_connected_geometry_mesh_type_planar_fog_volume_visible)
    connected_geometry_mesh_type_lightmap_region_visible: bpy.props.BoolProperty(default=True, options=set(), name="Lightmap Region", update=update_connected_geometry_mesh_type_lightmap_region_visible)
    connected_geometry_mesh_type_boundary_surface_visible: bpy.props.BoolProperty(default=True, options=set(), name="Soft Ceiling", update=update_connected_geometry_mesh_type_boundary_surface_visible)
    connected_geometry_mesh_type_obb_volume_visible: bpy.props.BoolProperty(default=True, options=set(), name="Lightmap Exclusion Volume", update=update_connected_geometry_mesh_type_obb_volume_visible)
    connected_geometry_mesh_type_cookie_cutter_visible: bpy.props.BoolProperty(default=True, options=set(), name="Cookie Cutter", update=update_connected_geometry_mesh_type_cookie_cutter_visible)
    connected_geometry_mesh_type_poop_rain_blocker_visible: bpy.props.BoolProperty(default=True, options=set(), name="Rain Blocker", update=update_connected_geometry_mesh_type_poop_rain_blocker_visible)
    
    connected_geometry_marker_type_model_visible: bpy.props.BoolProperty(default=True, options=set(), name="Model Marker", update=update_connected_geometry_marker_type_model_visible)
    connected_geometry_marker_type_effects_visible: bpy.props.BoolProperty(default=True, options=set(), name="Effects", update=update_connected_geometry_marker_type_effects_visible)
    connected_geometry_marker_type_garbage_visible: bpy.props.BoolProperty(default=True, options=set(), name="Garbage", update=update_connected_geometry_marker_type_garbage_visible)
    connected_geometry_marker_type_hint_visible: bpy.props.BoolProperty(default=True, options=set(), name="Hint", update=update_connected_geometry_marker_type_hint_visible)
    connected_geometry_marker_type_pathfinding_sphere_visible: bpy.props.BoolProperty(default=True, options=set(), name="Pathfinding Sphere", update=update_connected_geometry_marker_type_pathfinding_sphere_visible)
    connected_geometry_marker_type_physics_constraint_visible: bpy.props.BoolProperty(default=True, options=set(), name="Physics Constraint", update=update_connected_geometry_marker_type_physics_constraint_visible)
    connected_geometry_marker_type_target_visible: bpy.props.BoolProperty(default=True, options=set(), name="Target", update=update_connected_geometry_marker_type_target_visible)
    connected_geometry_marker_type_game_instance_visible: bpy.props.BoolProperty(default=True, options=set(), name="Game Object", update=update_connected_geometry_marker_type_game_instance_visible)
    connected_geometry_marker_type_airprobe_visible: bpy.props.BoolProperty(default=True, options=set(), name="Airpobe", update=update_connected_geometry_marker_type_airprobe_visible)
    connected_geometry_marker_type_envfx_visible: bpy.props.BoolProperty(default=True, options=set(), name="Environment Effect", update=update_connected_geometry_marker_type_envfx_visible)
    connected_geometry_marker_type_lightCone_visible: bpy.props.BoolProperty(default=True, options=set(), name="Lightcone", update=update_connected_geometry_marker_type_lightCone_visible)
    
    connected_geometry_object_type_frame_visible: bpy.props.BoolProperty(default=True, options=set(), name="Frame", update=update_connected_geometry_object_type_frame_visible)
    connected_geometry_object_type_light_visible: bpy.props.BoolProperty(default=True, options=set(), name="Light", update=update_connected_geometry_object_type_light_visible)

    sidecar_path: bpy.props.StringProperty()
    
    def get_asset_name(self):
        if not self.sidecar_path.strip(): return ""
        return Path(self.sidecar_path).parent.name

    asset_name: bpy.props.StringProperty(
        get=get_asset_name,
    )
    
    def get_asset_directory(self):
        if not self.sidecar_path.strip(): return ""
        return str(Path(self.sidecar_path).parent)
    
    asset_directory: bpy.props.StringProperty(
        get=get_asset_directory,
    )
    
    def get_is_valid_asset(self):
        if not bpy.data.filepath:
            return False
        project = utils.get_project(self.scene_project)
        return project and bool(self.sidecar_path.strip())
    
    is_valid_asset: bpy.props.BoolProperty(
        get=get_is_valid_asset,
    )
    
    particle_uses_custom_points: bpy.props.BoolProperty(
        name="Has Custom Emitter Shape",
        description="Generates a particle_emitter_custom_points tag for this particle model. This can be referenced in an effect tag as a custom emitter shape",
    )
    
    # Animation command stuff
    
    animation_cmd_object_type: bpy.props.EnumProperty(
        name="Object Type",
        options=set(),
        items=[
            ('player', "Player", ""),
            ('unit', "Unit", ""),
            ('scenery', "Scenery", ""),
        ]
    )
    
    animation_cmd_loop: bpy.props.BoolProperty(
        name="Loop Animation",
        options=set(),
    )
    
    def animation_cmd_path_clean_tag_path(self, context):
        self["animation_cmd_path"] = utils.clean_tag_path(self["animation_cmd_path"], "model_animation_graph").strip('"')
    
    animation_cmd_path: bpy.props.StringProperty(
        name="Animation Graph Path",
        description="Path to the animation graph to get animations from. If left empty, defaults to the expected animation graph from this asset",
        update=animation_cmd_path_clean_tag_path,
        options=set(),
    )
    
    animation_cmd_name: bpy.props.StringProperty(
        name="Animation Name",
    )
    
    animation_cmd_expression: bpy.props.StringProperty(
        name="Object Expression",
        description="A halo script expression which evaluates to the object you wish to animate. This might be the object name directly in the scenario or something like (player_get 2)",
    )
    
    debug_composites: bpy.props.BoolProperty(
        name="Debug Composites",
        description="Does not overwrite existing composite files with the information set in Blender"
    )
    
    sun_size: bpy.props.FloatProperty(
        name="Sun Size",
        default=1.0,
        min=0.0,
        options=set(),
    )
    
    sun_as_vmf_light: bpy.props.BoolProperty(
        name="Sun as VMF Light",
        description="When true, the sun acts like another skylight and will not provide pre-lightmapping ambient map lighting",
        options=set(),
    )
    
    sun_bounce_scale: bpy.props.FloatProperty(
        name="Sunlight Bounce Scale",
        default=1.0,
        min=0,
        options=set(),
    )
    
    skylight_bounce_scale: bpy.props.FloatProperty(
        name="Skylight Bounce Scale",
        default=1.0,
        min=0,
        options=set(),
    )
    
    show_water_direction: bpy.props.BoolProperty(options={'HIDDEN'})
    
    animation_events: bpy.props.CollectionProperty(
        type=NWO_Animation_ListItems,
    )

    active_animation_event_index: bpy.props.IntProperty(
        name="Index for Animation Event",
        default=0,
        min=0,
        options=set(),
    )
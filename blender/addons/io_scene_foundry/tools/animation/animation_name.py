from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import bpy
from ... import utils
from ...managed_blam.object import ObjectTag

SPECIAL = [
    ('any', "any", "No restrictions on use, however this is lower priorty than exact matches"),
    ('custom', "custom", "Allows you set your own value"),
    ]

MODES_DEVICE = [
    ('device', "device", "Used by devices as their default mode")
]
MODES_VEHICLE = [
    ('vehicle', "vehicle", "Used by vehicles as their default mode")
]
MODES_UNIT = [
    ('combat', "combat", "The default mode for units")
]
MODES_BIPED = [
    ('crouch', "crouch", "Active when a biped is crouching"),
    ('sprint', "sprint", "Active when a biped is sprinting"),
]

MODES = {
    'device': "Used by devices as their default mode",
    'vehicle': "Used by vehicles as their default mode",
    'combat': "The default mode for bipeds",
    'crouch': "Active when a biped is crouching",
    'sprint': "Active when a biped is sprinting",
}

SETS = {
    'sync_actions': "Used when an object is executing a sync action, such as assassinations"
}

MODES_DEVICE = {'device'}
MODES_VEHICLE = {'vehicle', 'combat'}
MODES_UNIT = {'combat'}
MODES_BIPED = {'crouch'}
MODES_CHARACTER = {''}

USEFUL_TAG_EXTS = ".biped", ".vehicle", ".weapon"

info_cache = None

@dataclass
class ExternalGraphInfo:
    driver_seats = defaultdict(set)
    gunner_seats = defaultdict(set)
    boarding_seats = defaultdict(set)
    passenger_seats = defaultdict(set)
    
    weapon_classes = defaultdict(set)
    weapon_types = defaultdict(set)

def _get_external_graph_info():
    
    global info_cache
    if info_cache is not None:
        return info_cache
    
    useful_tags = utils.paths_in_dir(utils.get_tags_path(), USEFUL_TAG_EXTS)
    
    info_cache = ExternalGraphInfo()
    
    for path in useful_tags:
        match Path(path).suffix.lower():
            case '.biped' | '.vehicle':
                with ObjectTag(path=path) as unit:
                    rel_path = unit.tag_path.RelativePathWithExtension
                    for element in unit.tag.SelectField("Struct:unit[0]/Block:seats").Elements:
                        label = element.SelectField("label").GetStringData()
                        if not label:
                            continue
                        flags = element.SelectField("flags")
                        if flags.TestBit("driver"):
                            info_cache.driver_seats[label].add(rel_path)
                        elif flags.TestBit("gunner"):
                            info_cache.gunner_seats[label].add(rel_path)
                        elif flags.TestBit("boarding seat"):
                            info_cache.boarding_seats[label].add(rel_path)
                        else:
                            info_cache.passenger_seats[label].add(rel_path)
            case '.weapon':
                with ObjectTag(path=path) as weapon:
                    rel_path = weapon.tag_path.RelativePathWithExtension
                    weapon_class = weapon.tag.SelectField("weapon class").GetStringData()
                    weapon_type = weapon.tag.SelectField("weapon name").GetStringData()
                    
                    if weapon_class:
                        info_cache.weapon_classes[weapon_class].add(rel_path)
                    if weapon_type:
                        info_cache.weapon_types[weapon_type].add(rel_path)
                        
    return info_cache
            
class NWO_OT_SetAnimationName(bpy.types.Operator):
    bl_idname = "nwo.set_animation_name"
    bl_label = "Set Animation Name"
    bl_description = "Creates a valid animation name"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return True
    
    state_type: bpy.props.EnumProperty(
        name="State Type",
        options=set(),
        items=[
            ("action", "Action / Overlay", ""),
            ("transition", "Transition", ""),
            ("damage", "Death & Damage", ""),
            ("pose", "Pose", "Defines the default pose of an object that is not a unit"),
            ("custom", "Custom", ""),
        ],
    )
    
    def get_modes(self):
        items = []
        items.extend()

    mode: bpy.props.EnumProperty(
        name="Mode",
        options=set(),
        description="""The mode the object must be in to use this animation. Use 'any' for all modes. Other valid
        inputs include but are not limited to: 'crouch' when a unit is crouching, 
        'combat' when a unit is in combat. Modes can also refer
        to vehicle seats. For example an animation for a unit driving a warthog would use 'warthog_d'. For more
        information refer to existing model_animation_graph tags. Can be empty""",
    )

    weapon_class: bpy.props.EnumProperty(
        name="Weapon Class",
        options=set(),
        description="""The weapon class this unit must be holding to use this animation. Weapon class is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty""",
    )
    weapon_type: bpy.props.EnumProperty(
        name="Weapon Name",
        options=set(),
        description="""The weapon type this unit must be holding to use this animation.  Weapon name is defined
        per weapon in .weapon tags (under Group WEAPON > weapon labels). Can be empty""",
    )
    set: bpy.props.EnumProperty(
        name="Set", description="The set this animtion is a part of. Can be empty", options=set(),
    )
    state: bpy.props.EnumProperty(
        name="State",
        options=set(),
        description="""The state this animation plays in. States can refer to hardcoded properties or be entirely
        custom. You should refer to existing model_animation_graph tags for more information. Examples include: 'idle' for 
        animations that should play when the object is inactive, 'move-left', 'move-front' for moving. 'put-away' for
        an animation that should play when putting away a weapon. Must not be empty""",
    )

    destination_mode: bpy.props.EnumProperty(
        name="Destination Mode",
        options=set(),
        description="The mode to put this object in when it finishes this animation. Can be empty",
    )
    destination_state: bpy.props.EnumProperty(
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

    def execute(self, context):
        info = _get_external_graph_info()
        return {"FINISHED"}
    
    def invoke(self, context, _):
        info = _get_external_graph_info()
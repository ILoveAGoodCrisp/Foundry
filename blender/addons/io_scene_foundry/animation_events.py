"""Shared frame-event names, independent of tag enum ordering."""
from functools import lru_cache


# H1 stores single events in scalar slots rather than a frame-event block.
# Keyframes are zero-based; foot slots reserve zero and are one-based.
HALO1_FRAME_EVENT_SLOTS = {
    'primary keyframe': ('key frame index', 0),
    'secondary keyframe': ('second key frame index', 0),
    'left foot': ('left foot frame index', 1),
    'right foot': ('right foot frame index', 1),
}


def canonical_frame_event(value: str) -> str:
    """Resolve tag spelling and pre-Reach transitions to stable Blender IDs."""
    key = value.partition('{')[0].strip().replace('_', ' ').casefold()
    if key in {'transition a', 'transition b', 'transition c', 'transition d'}:
        return 'match ' + key[-1]
    return key


# Numeric IDs are persisted in .blend files. Append entries; never reorder them.
FRAME_EVENT_ITEMS = [
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
    ("left back foot", "Left Back Foot", "Halo 3 / ODST back-foot event; no confirmed equivalent among Reach foot lock/unlock events"),
    ("right back foot", "Right Back Foot", "Halo 3 / ODST back-foot event; no confirmed equivalent among Reach foot lock/unlock events"),
    ("jetpack closed", "Jetpack Closed", "Jetpack has closed"),
    ("jetpack open", "Jetpack Open", "Jetpack has opened"),
    ("sound event", "Sound Event", "Frame sound-event marker"),
    ("effect event", "Effect Event", "Frame effect-event marker"),
]

# Retain callback strings for Blender and explicit IDs across game labels.
FRAME_EVENT_ITEMS = [(*item, index) for index, item in enumerate(FRAME_EVENT_ITEMS)]
CLASSIC_FRAME_EVENT_ITEMS = [
    (identifier, 'Transition ' + identifier[-1].upper(),
     description.replace('Match ', 'Transition '), number)
    if identifier in {'match a', 'match b', 'match c', 'match d'}
    else (identifier, label, description, number)
    for identifier, label, description, number in FRAME_EVENT_ITEMS
]


@lru_cache(maxsize=7)
def frame_event_items_for_game(game: str):
    from .game_capabilities import frame_event_names
    items = CLASSIC_FRAME_EVENT_ITEMS if game in {'halo2', 'halo3', 'halo3odst'} else FRAME_EVENT_ITEMS
    allowed = frame_event_names(game)
    return [item for item in items if item[0] in allowed]

def set_animation_enum(owner, prop, value):
    """Preserve imported enum IDs even when the current game's UI filters them."""
    try:
        setattr(owner, prop, value)
    except TypeError:
        from .game_capabilities import ANIMATION_TYPE_ITEMS, ANIMATION_EVENT_ITEMS, EVENT_DATA_ITEMS
        catalogs = {'frame_name': FRAME_EVENT_ITEMS, 'animation_type': ANIMATION_TYPE_ITEMS,
            'event_type': ANIMATION_EVENT_ITEMS, 'data_type': EVENT_DATA_ITEMS,
            'animation_movement_data': [('none','','',0),('xy','','',1),('xyyaw','','',2),('xyzyaw','','',3),('full','','',4)],
            'animation_space': [('object','','',0),('local','','',1)],
            'multi_frame': [('single','','',0),('range','','',1)]}
        number = next((item[-1] for item in catalogs.get(prop, ()) if item[0] == value), None)
        if number is None:
            raise
        owner[prop] = number

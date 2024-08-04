"""Foundry Bone properties. Not sure if they really do much"""

import bpy

class NWO_BonePropertiesGroup(bpy.types.PropertyGroup):
    object_space_node: bpy.props.BoolProperty(
        name="Object Space Offset Node",
        description="",
        default=False,
        options=set(),
    )
    replacement_correction_node: bpy.props.BoolProperty(
        name="Replacement Correction Node",
        description="",
        default=False,
        options=set(),
    )
    fik_anchor_node: bpy.props.BoolProperty(
        name="Forward IK Anchor Node",
        description="",
        default=False,
        options=set(),
    )
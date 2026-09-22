"""Reach-style skeleton and animation conversion for native legacy imports."""
import bpy
from mathutils import Matrix

from ... import import_transform, utils
from .automate_pose_overlay import BlendScreen, PoseBuilder


def prepare_reach_skeleton(armature):
    names = {}
    for bone in armature.data.bones:
        names.setdefault(utils.remove_node_prefix(bone.name).lower(), bone.name)
    required = ('pedestal', 'aim_yaw', 'aim_pitch')
    if not all(name in names for name in required):
        utils.set_object_mode(bpy.context)
        utils.deselect_all_objects()
        armature.select_set(True)
        utils.set_active_object(armature)
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bones = armature.data.edit_bones
            roots = [bone for bone in bones if bone.parent is None and bone.use_deform]
            for name in required:
                if name in names:
                    continue
                bone = bones.new(name)
                bone.tail = (0, max(import_transform.scale_factor(), 0.001), 0)
                bone.matrix = import_transform.rotation_matrix()
                names[name] = bone.name
                if name != 'pedestal':
                    bone.parent = bones[names['pedestal']]
            pedestal = bones[names['pedestal']]
            for root in roots:
                if root != pedestal and root.name not in (names['aim_yaw'], names['aim_pitch']):
                    root.use_connect = False
                    root.parent = pedestal
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

    scene_nwo = utils.get_scene_props()
    scene_nwo.node_usage_pedestal = names['pedestal']
    scene_nwo.node_usage_pose_blend_yaw = names['aim_yaw']
    scene_nwo.node_usage_pose_blend_pitch = names['aim_pitch']
    for name in required:
        armature.pose.bones[names[name]].rotation_mode = 'QUATERNION'
    return names


def split_root_movement(moved, unmoved, pedestal_rest):
    """Factor movement onto the pedestal without changing the resulting root pose.

    Both root matrices are in imported armature space. The returned old-root
    matrix is local to the pedestal; their product reproduces the original pose.
    """
    return moved @ unmoved.inverted_safe() @ pedestal_rest, pedestal_rest.inverted_safe() @ unmoved


def convert_blend_screen(armature, animation, action, slot, record, names):
    screen = BlendScreen()
    screen.from_record(record)
    screen.compute_transforms()
    armature.animation_data.action = action
    armature.animation_data.action_slot = slot
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    builder = PoseBuilder(
        armature.pose.bones[names['pedestal']],
        armature.pose.bones[names['aim_pitch']],
        armature.pose.bones[names['aim_yaw']],
    )
    animation.pose_overlay = True
    wrap_events = not ('vehicle' in animation.name or 'pain' in animation.name)
    with utils.ArmatureDeformMute():
        animation.frame_end = builder.build_from_blend_screen(
            bpy.context.scene, animation, action, wrap_events, screen, slot)
    action.frame_end = animation.frame_end

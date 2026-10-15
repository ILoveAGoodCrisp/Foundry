"""Aim-control guides for the fixed sample grids used by classic games."""

from math import degrees

import bpy
from mathutils import Matrix

from ... import utils
from ...game_capabilities import LEGACY_GAMES
from .automate_pose_overlay import BlendScreen


def classic_blend_screen(screen):
    """Scene screen angles use radians; the shared legacy sampler uses degrees."""
    result = BlendScreen()
    for field in ('right_yaw_per_frame', 'left_yaw_per_frame',
                  'down_pitch_per_frame', 'up_pitch_per_frame'):
        setattr(result, field, degrees(getattr(screen, field)))
    for field in ('right_frame_count', 'left_frame_count',
                  'down_pitch_frame_count', 'up_pitch_frame_count'):
        setattr(result, field, getattr(screen, field))
    result.compute_transforms(wrap_yaw_limit=None)
    return result


def key_blend_screen_control(action, slot, control, screen, frame_start):
    """Replace only control rotations in this slot, retaining every grid sample.

    A Foundry aim control uses local +X as forward, +Z yaw and +Y pitch.
    Its parent already supplies the pedestal's orientation. The initial neutral
    frame is the additive reference, not a sample in the blend screen.
    """
    fcurves = utils.get_fcurves(action, slot)
    if fcurves is None:
        raise ValueError(f'Action [{action.name}] has no usable armature slot')

    rotations = [Matrix.Identity(4)]
    rotations.extend(yaw @ pitch for yaw, pitch, _ in screen.transforms)
    mode = control.rotation_mode
    values = []
    previous = None
    for rotation in rotations:
        if mode == 'QUATERNION':
            value = rotation.to_quaternion()
            if previous is not None:
                value.make_compatible(previous)
        elif mode == 'AXIS_ANGLE':
            axis, angle = rotation.to_quaternion().to_axis_angle()
            value = (angle, *axis)
        else:
            value = rotation.to_euler(mode, previous) if previous is not None else rotation.to_euler(mode)
        values.append(tuple(value))
        previous = value

    rotation_paths = {control.path_from_id(prop) for prop in (
        'rotation_quaternion', 'rotation_euler', 'rotation_axis_angle')}
    for curve in list(fcurves):
        if curve.data_path in rotation_paths:
            fcurves.remove(curve)

    prop = ('rotation_quaternion' if mode == 'QUATERNION' else
            'rotation_axis_angle' if mode == 'AXIS_ANGLE' else 'rotation_euler')
    for index in range(len(values[0])):
        curve = fcurves.new(control.path_from_id(prop), index=index, group_name=control.name)
        curve.keyframe_points.add(len(values))
        for offset, (point, value) in enumerate(zip(curve.keyframe_points, values)):
            point.co = (frame_start + offset, value[index])
            point.interpolation = 'CONSTANT'
        curve.update()
    action.update_tag()
    return frame_start + len(values) - 1


class NWO_OT_GenerateBlendScreenPoses(bpy.types.Operator):
    bl_idname = 'nwo.generate_blend_screen_poses'
    bl_label = 'Generate Blend Screen Poses'
    bl_description = ('Animate the aim control to show the direction expected on each frame '
                      'by the assigned blend screen. Then pose the model for each direction')
    bl_options = {'REGISTER', 'UNDO'}

    aim_control: bpy.props.StringProperty(
        name='Aim Control Bone',
        description='Control to animate as a direction guide; aim yaw and pitch bones are not required',
    )

    @classmethod
    def poll(cls, context):
        nwo = utils.get_scene_props()
        if utils.get_game(use_external=False) not in LEGACY_GAMES:
            return False
        if context.mode not in {'OBJECT', 'POSE'} or not 0 <= nwo.active_animation_index < len(nwo.animations):
            return False
        animation = nwo.animations[nwo.active_animation_index]
        return animation.animation_type == 'overlay' and not animation.external

    def execute(self, context):
        nwo = utils.get_scene_props()
        if not self.poll(context):
            self.report({'WARNING'}, 'Select a local overlay animation in a pre-Reach project')
            return {'CANCELLED'}
        animation = nwo.animations[nwo.active_animation_index]
        screen = nwo.blend_screens.get(animation.blend_screen)
        if screen is None:
            self.report({'WARNING'}, 'Assign a blend screen to this animation first')
            return {'CANCELLED'}
        armature = utils.get_rig_prioritize_active(context)
        if armature is None:
            self.report({'WARNING'}, 'No armature in scene')
            return {'CANCELLED'}
        control = armature.pose.bones.get(self.aim_control or armature.nwo.control_aim)
        if control is None:
            self.report({'WARNING'}, 'Choose an aim control bone to animate')
            return {'CANCELLED'}
        if armature.nwo.invert_control_aim and control.name == armature.nwo.control_aim:
            self.report({'WARNING'}, 'Turn off Aim Control Toggle so the aim control can drive its own rotation')
            return {'CANCELLED'}
        track = next((track for track in animation.action_tracks
                      if track.object == armature and track.action and not track.is_shape_key_action), None)
        if track is None:
            self.report({'WARNING'}, 'Add an action track for this armature to the selected animation')
            return {'CANCELLED'}
        action = track.action
        slot = utils.get_slot_from_id(action, armature)
        object_slots = [item for item in action.slots if item.target_id_type == 'OBJECT']
        if slot is None and len(object_slots) == 1:
            slot = object_slots[0]
        if (slot is None and action.slots) or (slot is not None and slot.target_id_type != 'OBJECT'):
            self.report({'WARNING'}, 'Assign the armature to its action slot before generating poses')
            return {'CANCELLED'}

        samples = classic_blend_screen(screen)
        if slot is None:
            slot = action.slots.new(id_type='OBJECT', name=armature.name)
        animation.frame_end = key_blend_screen_control(
            action, slot, control, samples, animation.frame_start)
        if armature.animation_data and armature.animation_data.action == action:
            armature.animation_data.action_slot = slot
        armature.nwo.control_aim = control.name
        scene = context.scene
        scene.frame_start = animation.frame_start
        scene.frame_end = animation.frame_end
        scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)
        self.report({'INFO'}, f'Generated {len(samples.transforms)} directions plus a neutral reference frame')
        return {'FINISHED'}

    def invoke(self, context, event):
        armature = utils.get_rig_prioritize_active(context)
        if armature is None:
            return self.execute(context)
        self.aim_control = armature.nwo.control_aim
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        nwo = utils.get_scene_props()
        animation = nwo.animations[nwo.active_animation_index]
        screen = nwo.blend_screens.get(animation.blend_screen)
        layout = self.layout
        layout.use_property_split = True
        armature = utils.get_rig_prioritize_active(context)
        if armature is not None:
            layout.prop_search(self, 'aim_control', armature.pose, 'bones')
        if screen is None:
            layout.label(text='Assign a blend screen to this animation first', icon='ERROR')
            return
        count = (screen.right_frame_count + screen.left_frame_count + 1) * (
            screen.down_pitch_frame_count + screen.up_pitch_frame_count + 1)
        layout.label(text=f'Blend Screen: {screen.name}')
        layout.label(text=f'Neutral reference: frame {animation.frame_start}')
        layout.label(text=f'{count} directions: frames {animation.frame_start + 1}–{animation.frame_start + count}')
        layout.label(text='Replaces the aim control’s rotation keys')

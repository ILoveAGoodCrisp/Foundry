

import bpy
from math import radians
from mathutils import Matrix

class NWO_AddAimAnimation(bpy.types.Operator):
    bl_idname = 'nwo.add_aim_animation'
    bl_label = 'Aim Animation'
    bl_description = 'Animates the aim bones (or aim control if it exists) based on the chosen option'
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        scene_nwo = context.scene.nwo
        arm = scene_nwo.main_armature
        if not arm: return False
        return context.object and context.object == arm and scene_nwo.node_usage_pose_blend_yaw and scene_nwo.node_usage_pose_blend_pitch
    
    aim_animation: bpy.props.EnumProperty(
        name='Animation',
        items=[
            ("steering", "Steering", "Uses the yaw bone only. Steers left and right\nFrames:\nrest\nleft\nmiddle\nright"),
            ("aiming", "Aiming / Flight", "Animates the yaw and pitch bones from left to right\nFrames:\nrest\nleft up\nleft\left down\nmiddle up\nmiddle\nmiddle down\nright up\nright\nright down"),
            ("pitch_and_turn", "Pitch & Turn", "Animates the yaw and pitch bones from left to right in line with 'pitch_and_turn' overlays in earlier Halo games\nFrames:\nrest\nright down\nmiddle down\nleft down\nright forward\nmiddle forward\nleft forward\nright up\nmiddle up\nleft up"),
            ("aiming_360", "360 Aiming / Acceleration", "Aiming for a turret that can rotate 360 degrees. Uses the yaw bone initially, then the pitch (90 degrees down then up)\nFrames:\nrest\nyaw anti-clockwise 360 for 7 frames\nrest\npitch down\npitch up"),
            ]
        )
    
    max_yaw: bpy.props.FloatProperty(
        name='Max Steering Yaw',
        subtype='ANGLE',
        default=radians(45),
        min=radians(1),
        max=radians(89.99),
    )
    
    max_pitch: bpy.props.FloatProperty(
        name='Max Steering Pitch',
        subtype='ANGLE',
        default=radians(45),
        min=radians(1),
        max=radians(89.99),
    )
    
    def setup_steering(self, yaw, aim, start):
        if aim is None:
            yaw.matrix_basis = Matrix()
            yaw.rotation_mode = 'XYZ'
            yaw.keyframe_insert(data_path='rotation_euler', frame=start)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            yaw.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 3)
        else:
            aim.matrix_basis = Matrix()
            aim.rotation_mode = 'XYZ'
            aim.keyframe_insert(data_path='rotation_euler', frame=start)
            aim.rotation_euler = [0, 0, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            aim.rotation_euler = [0, 0, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            aim.rotation_euler = [0, 0, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            
        return start + 3
        
    def setup_aiming(self, yaw, pitch, aim, start):
        if aim is None:
            yaw.matrix_basis = Matrix()
            pitch.matrix_basis = Matrix()
            yaw.rotation_mode = 'XYZ'
            pitch.rotation_mode = 'XYZ'
            yaw.keyframe_insert(data_path='rotation_euler', frame=start)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 9)
        else:
            aim.matrix_basis = Matrix()
            aim.rotation_mode = 'XYZ'
            aim.keyframe_insert(data_path='rotation_euler', frame=start)
            aim.rotation_euler = [0, -self.max_pitch, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            aim.rotation_euler = [0, 0, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            aim.rotation_euler = [0, self.max_pitch, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            aim.rotation_euler = [0, -self.max_pitch, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            aim.rotation_euler = [0, 0, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            aim.rotation_euler = [0, self.max_pitch, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            aim.rotation_euler = [0, -self.max_pitch, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            aim.rotation_euler = [0, 0, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            aim.rotation_euler = [0, self.max_pitch, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 9)
        return start + 9
    
    def setup_pitch_and_turn(self, yaw, pitch, aim, start):
        if aim is None:
            yaw.matrix_basis = Matrix()
            pitch.matrix_basis = Matrix()
            yaw.rotation_mode = 'XYZ'
            pitch.rotation_mode = 'XYZ'
            yaw.keyframe_insert(data_path='rotation_euler', frame=start)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            yaw.rotation_euler = [0, 0, -self.max_yaw]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            yaw.rotation_euler = [0, 0, 0]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            yaw.rotation_euler = [0, 0, self.max_yaw]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 9)
        else:
            aim.matrix_basis = Matrix()
            aim.rotation_mode = 'XYZ'
            aim.keyframe_insert(data_path='rotation_euler', frame=start)
            aim.rotation_euler = [0, self.max_pitch, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            aim.rotation_euler = [0, self.max_pitch, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            aim.rotation_euler = [0, self.max_pitch, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            aim.rotation_euler = [0, 0, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            aim.rotation_euler = [0, 0, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            aim.rotation_euler = [0, 0, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            aim.rotation_euler = [0, -self.max_pitch, -self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            aim.rotation_euler = [0, -self.max_pitch, 0]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            aim.rotation_euler = [0, -self.max_pitch, self.max_yaw]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            
        return start + 9
    
    def setup_aiming_360(self, yaw, pitch, aim, start):
        if aim is None:
            yaw.matrix_basis = Matrix()
            pitch.matrix_basis = Matrix()
            yaw.rotation_mode = 'XYZ'
            pitch.rotation_mode = 'XYZ'
            yaw.keyframe_insert(data_path='rotation_euler', frame=start)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start)
            yaw.rotation_euler = [0, 0, radians(45)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            yaw.rotation_euler = [0, 0, radians(90)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            yaw.rotation_euler = [0, 0, radians(135)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            yaw.rotation_euler = [0, 0, radians(180)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            yaw.rotation_euler = [0, 0, radians(225)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            yaw.rotation_euler = [0, 0, radians(270)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            yaw.rotation_euler = [0, 0, radians(315)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            yaw.rotation_euler = [0, 0, radians(360)]
            pitch.rotation_euler = [0, 0, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            yaw.rotation_euler = [0, 0, radians(360)]
            pitch.rotation_euler = [0, self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            yaw.rotation_euler = [0, 0, radians(360)]
            pitch.rotation_euler = [0, -self.max_pitch, 0]
            yaw.keyframe_insert(data_path='rotation_euler', frame=start + 10)
            pitch.keyframe_insert(data_path='rotation_euler', frame=start + 10)
        else:
            aim.matrix_basis = Matrix()
            aim.rotation_mode = 'XYZ'
            aim.keyframe_insert(data_path='rotation_euler', frame=start)
            aim.rotation_euler = [0, 0, radians(45)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 1)
            aim.rotation_euler = [0, 0, radians(90)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 2)
            aim.rotation_euler = [0, 0, radians(135)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 3)
            aim.rotation_euler = [0, 0, radians(180)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 4)
            aim.rotation_euler = [0, 0, radians(225)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 5)
            aim.rotation_euler = [0, 0, radians(270)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 6)
            aim.rotation_euler = [0, 0, radians(315)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 7)
            aim.rotation_euler = [0, 0, radians(360)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 8)
            aim.rotation_euler = [0, self.max_pitch, radians(360)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 9)
            aim.rotation_euler = [0, -self.max_pitch, radians(360)]
            aim.keyframe_insert(data_path='rotation_euler', frame=start + 10)
            
        return start + 10
    
    def execute(self, context):
        scene_nwo = context.scene.nwo
        arm = scene_nwo.main_armature
        if not arm.animation_data:
            arm.animation_data_create()
        yaw_name = scene_nwo.node_usage_pose_blend_yaw
        pitch_name = scene_nwo.node_usage_pose_blend_pitch
        aim_name = scene_nwo.control_aim
        yaw = arm.pose.bones.get(yaw_name)
        if yaw is None:
            scene_nwo.node_usage_pose_blend_yaw = ''
            self.report({'WARNING'}, f"Pitch bone {pitch_name} does not exist in {arm.name}. Removed from Node Usages")
            return {'CANCELLED'}
        pitch = arm.pose.bones.get(pitch_name)
        if pitch is None:
            scene_nwo.node_usage_pose_blend_pitch = ''
            self.report({'WARNING'}, f"Pitch bone {pitch_name} does not exist in {arm.name}. Removed from Node Usages")
            return {'CANCELLED'}
        if aim_name:
            aim = arm.pose.bones.get(aim_name)
            if aim is None:
                scene_nwo.control_aim = ''
                self.report({'WARNING'}, f"Aim bone {aim_name} does not exist in {arm.name}. Removed from Node Usages")
                return {'CANCELLED'}
        else:
            aim = None
        start = int(arm.animation_data.action.frame_start)
        scene = context.scene
        current = int(scene.frame_current)
        already_in_pose_mode = False
        if context.mode == 'POSE':
            already_in_pose_mode = True
        else:
            bpy.ops.object.posemode_toggle()
            
        scene.frame_current = start
        action = arm.animation_data.action
        fcurves_for_destruction = set()
        for fc in action.fcurves:
            if fc.data_path.startswith(f'pose.bones["{pitch_name}"].') or fc.data_path.startswith(f'pose.bones["{yaw_name}"].') or fc.data_path.startswith(f'pose.bones["{aim_name}"].'):
                fcurves_for_destruction.add(fc)
        [action.fcurves.remove(fc) for fc in fcurves_for_destruction]
        
        if self.aim_animation == 'steering':
            action.frame_end = self.setup_steering(yaw, aim, start)
        elif self.aim_animation == 'aiming':
            action.frame_end = self.setup_aiming(yaw, pitch, aim, start)
        elif self.aim_animation == 'pitch_and_turn':
            action.frame_end = self.setup_pitch_and_turn(yaw, pitch, aim, start)
        elif self.aim_animation == 'aiming_360':
            action.frame_end = self.setup_aiming_360(yaw, pitch, aim, start)
        if not already_in_pose_mode:
            bpy.ops.object.posemode_toggle()
            
        scene.frame_current = current
        return {'FINISHED'}
    
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'aim_animation', text='Animation')
        if self.aim_animation in ('steering', 'aiming', 'pitch_and_turn'):
            layout.prop(self, 'max_yaw', text='Max Yaw Angle')
        if self.aim_animation in ('aiming', 'pitch_and_turn', 'aiming_360'):
            layout.prop(self, 'max_pitch', text='Max Pitch Angle')
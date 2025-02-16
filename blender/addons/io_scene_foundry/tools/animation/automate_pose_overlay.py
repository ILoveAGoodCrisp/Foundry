

import bpy
from math import degrees, radians
from mathutils import Matrix

from ... import utils
from ...managed_blam.animation import AnimationTag

class BlendScreen:
    def __init__(self):
        self.label = ""
        self.right_yaw_per_frame = 90.0
        self.left_yaw_per_frame = 90.0
        self.right_frame_count = 1
        self.left_frame_count = 1
        self.down_pitch_per_frame = 90.0
        self.up_pitch_per_frame = 90.0
        self.down_pitch_frame_count = 1
        self.up_pitch_frame_count = 1
        
        self.transforms = []
        
    def from_element(self, element):
        self.label = element.Fields[0].GetStringData()
        self.right_yaw_per_frame = element.Fields[1].Data
        self.left_yaw_per_frame = element.Fields[2].Data
        self.right_frame_count = element.Fields[3].Data
        self.left_frame_count = element.Fields[4].Data
        self.down_pitch_per_frame = element.Fields[5].Data
        self.up_pitch_per_frame = element.Fields[6].Data
        self.down_pitch_frame_count = element.Fields[7].Data
        self.up_pitch_frame_count = element.Fields[8].Data
        
    def compute_transforms(self):
        """Computes the transform a blend screen expects"""
        self.transforms.clear()
        yaw_transforms = []
        # Right
        for i in reversed(range(self.right_frame_count + 1)):
            yaw_transforms.append(self.right_yaw_per_frame * -i)
            
        # Left
        for i in range(1, self.left_frame_count + 1):
            yaw_transforms.append(self.left_yaw_per_frame * i)
        
        pitch_transforms = []
        # Down
        for i in reversed(range(self.down_pitch_frame_count + 1)):
            pitch_transforms.append(self.down_pitch_per_frame * i)
            
        # Up
        for i in range(1, self.up_pitch_frame_count + 1):
            pitch_transforms.append(self.up_pitch_per_frame * -i)
            
        for p in pitch_transforms:
            for y in yaw_transforms:
                yaw_matrix = Matrix.Rotation(radians(y), 4, 'Z')
                pitch_matrix = Matrix.Rotation(radians(p), 4, 'Y')
                self.transforms.append((tuple((yaw_matrix, pitch_matrix))))
        
        
def blend_screens_from_tag(filepath: str) -> dict[str: BlendScreen]:
    """Returns a dict of keys= animation name value=blend screen"""
    data = {}
    blend_screens = []
    with AnimationTag(path=filepath) as animation:
        for element in animation.tag.SelectField("Struct:definitions[0]/Block:blend screens").Elements:
            bscreen = BlendScreen()
            bscreen.from_element(element)
            bscreen.compute_transforms()
            blend_screens.append(bscreen)
            
        for element in animation.block_animations.Elements:
            index = element.SelectField("blend screen").Value
            if index == -1:
                continue
            data[element.Fields[0].GetStringData()] = blend_screens[index]
            
    return data

preset_steering_transforms = [
    (),
]

preset_aim_transforms = [
    (),
    (),
    (),
    (),
    (),
]

class PoseBuilder:
    def __init__(self, pedestal: bpy.types.PoseBone, pitch: bpy.types.PoseBone, yaw: bpy.types.PoseBone, control: bpy.types.PoseBone | None=None):
        self.pedestal = pedestal
        self.pitch = pitch
        self.yaw = yaw
        self.control = control
        self.uses_control = control is not None
        
    def _pre_build(self, scene: bpy.types.Scene, frame_start: int,  action: bpy.types.Action):
        # Clear any existing keyframe data on aim bones
        fcurves = action.fcurves
        if self.uses_control:
            for fc in fcurves:
                if fc.data_path.startswith(f'pose.bones["{self.pitch.name}"].') or fc.data_path.startswith(f'pose.bones["{self.yaw.name}"].') or fc.data_path.startswith(f'pose.bones["{self.control.name}"].'):
                    fcurves.remove(fc)
        else:
            for fc in fcurves:
                if fc.data_path.startswith(f'pose.bones["{self.pitch.name}"].') or fc.data_path.startswith(f'pose.bones["{self.yaw.name}"].'):
                    fcurves.remove(fc)
                    
        # Set the current frame to the first frame of animation and ensure transform matches pedestal
        scene.frame_set(frame_start)
        if self.uses_control:
            self.control.matrix_basis = self.pedestal.matrix_basis
        else:
            self.yaw.matrix_basis = self.pedestal.matrix_basis
            self.pitch.matrix_basis = self.pedestal.matrix_basis
            
        # Keyframe this as the base pose
        if self.uses_control:
            self.control.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
        else:
            self.yaw.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
            self.pitch.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
            
    def _build_poses(self, scene: bpy.types.Scene, frame_start: int, transforms: list):
        # Loop through transforms and apply them
        if self.uses_control:
            for idx, (yaw, pitch) in enumerate(transforms):
                scene.frame_set(frame_start + idx + 1)
                self.control.matrix_basis = self.pedestal.matrix_basis @ yaw @ pitch
                self.control.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
        else:
            for idx, (yaw, pitch) in enumerate(transforms):
                scene.frame_set(frame_start + idx + 1)
                self.yaw.matrix = self.pedestal.matrix @ yaw
                self.pitch.matrix = self.pedestal.matrix @ pitch
                self.yaw.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
                self.pitch.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
        
    def build_from_preset(self, scene: bpy.types.Scene, frame_start: int,  action: bpy.types.Action, preset: str) -> int:
        """Keyframes a pose overlay based on the input preset. Returns the last frame keyframed"""
        self._pre_build(scene, frame_start, action)
        self._build_poses(scene, frame_start, preset_transforms[preset])

    
    def build_from_blend_screen(self, scene: bpy.types.Scene, frame_start: int,  action: bpy.types.Action, blend_screen: BlendScreen) -> int:
        """Keyframes a pose overlay based on the input blend screen. Returns the last frame keyframed"""
        self._pre_build(scene, frame_start, action)
        self._build_poses(scene, frame_start, blend_screen.transforms)
                
        return scene.frame_current
    
class NWO_OT_GeneratePoses(bpy.types.Operator):
    bl_idname = 'nwo.generate_poses'
    bl_label = 'Generate Poses'
    bl_description = 'Animates the aim bones (or aim control if it exists) based on the chosen option'
    bl_options = {'REGISTER', 'UNDO'}
    
    pose_type: bpy.props.EnumProperty(
        name="Type",
        description="Type of poses to generate",
        items=[
            ("legacy", "Legacy Blend Screen", "Computes poses from the data used by legacy blend screens"),
            ("aim", "Aim", "Computes poses typically used for aiming animations like aim_still_up"),
            ("acc", "Acceleration", "Computes poses typically used acceraltion animations like vehicle:acceleration"),
        ]
    )
    
    right_yaw_per_frame: bpy.props.FloatProperty(
        name="Right Yaw Per Frame",
        subtype='ANGLE',
        unit='ROTATION',
        default=radians(90),
        min=0,
        max=radians(360),
    )
    
    left_yaw_per_frame: bpy.props.FloatProperty(
        name="Left Yaw Per Frame",
        subtype='ANGLE',
        unit='ROTATION',
        default=radians(90),
        min=0,
        max=radians(360),
    )
    
    down_pitch_per_frame: bpy.props.FloatProperty(
        name="Down Pitch Per Frame",
        subtype='ANGLE',
        unit='ROTATION',
        default=radians(90),
        min=0,
        max=radians(360),
    )
    
    up_pitch_per_frame: bpy.props.FloatProperty(
        name="Up Pitch Per Frame",
        subtype='ANGLE',
        unit='ROTATION',
        default=radians(90),
        min=0,
        max=radians(360),
    )
    
    right_frame_count: bpy.props.IntProperty(
        name="Right Frame Count",
        min=0,
        max=4,
        default=1,
    )
    
    left_frame_count: bpy.props.IntProperty(
        name="Left Frame Count",
        min=0,
        max=4,
        default=1,
    )
    
    down_pitch_frame_count: bpy.props.IntProperty(
        name="Down Frame Count",
        min=0,
        max=4,
        default=1,
    )
    
    up_pitch_frame_count: bpy.props.IntProperty(
        name="Up Frame Count",
        min=0,
        max=4,
        default=1,
    )
    
    max_yaw: bpy.props.FloatProperty(
        name='Max Yaw',
        subtype='ANGLE',
        unit='ROTATION',
        default=radians(45),
        min=0,
        max=radians(90),
    )
    
    max_pitch: bpy.props.FloatProperty(
        name='Max Pitch',
        subtype='ANGLE',
        unit='ROTATION',
        default=radians(45),
        min=0,
        max=radians(90),
    )
    
    def execute(self, context):
        scene = context.scene
        nwo = scene.nwo
        armature = utils.get_rig_prioritize_active()
        if not armature:
            self.report({'WARNING'}, "No armature in scene")
            return ['CANCELLED']
        
        if not nwo.animations:
            self.report({'WARNING'}, "Scene has no animations. Ensure at least one exists in the Foundry animation panel")
            
        if nwo.active_animation_index == -1:
            self.report({'WARNING'}, "No active animation. Ensure desired animation is selected in the Foundry animation panel")

        animation = nwo.animations[nwo.active_animation_index]
        if not armature.animation_data:
            armature.animation_data_create()
        
        all_bone_names = {b.name for b in armature.pose.bones}
        
        pedestal_name = nwo.node_usage_pedestal
        if not pedestal_name:
            for name in all_bone_names:
                if utils.remove_node_prefix(name).lower() == "pedestal":
                    pedestal_name = name
                    nwo.node_usage_pedestal = name
            
        yaw_name = nwo.node_usage_pose_blend_yaw
        if not yaw_name:
            for name in all_bone_names:
                if utils.remove_node_prefix(name).lower() == "aim_yaw":
                    yaw_name = name
                    nwo.node_usage_pose_blend_yaw = name
        
        
        pitch_name = nwo.node_usage_pose_blend_pitch
        if not pitch_name:
            for name in all_bone_names:
                if utils.remove_node_prefix(name).lower() == "aim_pitch":
                    pitch_name = name
                    nwo.node_usage_pose_blend_pitch = name
                    
        aim_name = nwo.control_aim
        aim = None
        
        pedestal = armature.pose.bones.get(yaw_name)
        if pedestal is None:
            self.report({'WARNING'}, f"Pedestal bone {pedestal_name} does not exist in {armature.name}")
        yaw = armature.pose.bones.get(yaw_name)
        if yaw is None:
            self.report({'WARNING'}, f"Pitch bone {pitch_name} does not exist in {armature.name}")
        pitch = armature.pose.bones.get(pitch_name)
        if pitch is None:
            self.report({'WARNING'}, f"Pitch bone {pitch_name} does not exist in {armature.name}")
        if aim_name:
            aim = armature.pose.bones.get(aim_name)
            if aim is None:
                self.report({'WARNING'}, f"Aim bone {aim_name} does not exist in {armature.name}")
                
        if not aim and (not yaw and not pitch):
            self.report({'WARNING'}, f"Armature {armature.name} does not have aim bones. Cannot build poses")
            return {'CANCELLED'}
        
        current_frame = scene.frame_current
        
        use_blend_screen_info = self.pose_type == 'legacy'
        if use_blend_screen_info:
            blend_screen = BlendScreen()
            blend_screen.right_yaw_per_frame = degrees(self.right_yaw_per_frame)
            blend_screen.left_yaw_per_frame = degrees(self.left_yaw_per_frame)
            blend_screen.right_frame_count = self.right_frame_count
            blend_screen.left_frame_count = self.left_frame_count
            blend_screen.down_pitch_per_frame = degrees(self.down_pitch_per_frame)
            blend_screen.up_pitch_per_frame = degrees(self.up_pitch_per_frame)
            blend_screen.down_pitch_frame_count = self.down_pitch_frame_count
            blend_screen.up_pitch_frame_count = self.up_pitch_frame_count
            blend_screen.compute_transforms()
        
        builder = PoseBuilder(pedestal, pitch, yaw, aim)
        with utils.ArmatureDeformMute():
            for track in animation.action_tracks:
                if track.object == armature and track.action:
                    if use_blend_screen_info:
                        animation.frame_end = builder.build_from_blend_screen(scene, animation.frame_start, track.action, blend_screen)
                    else:
                        pass
                    break
            
        scene.frame_current = current_frame
        
        return {'FINISHED'}
    
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self, width=330)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "pose_type")
        layout.separator()
        match self.pose_type:
            case 'legacy':
                layout.prop(self, "right_yaw_per_frame")
                layout.prop(self, "left_yaw_per_frame")
                layout.prop(self, "right_frame_count")
                layout.prop(self, "left_frame_count")
                layout.separator()
                layout.prop(self, "down_pitch_per_frame")
                layout.prop(self, "up_pitch_per_frame")
                layout.prop(self, "down_pitch_frame_count")
                layout.prop(self, "up_pitch_frame_count")
            case 'aim':
                layout.prop(self, "max_yaw")
                layout.prop(self, "max_pitch")
            case 'acc':
                layout.prop(self, "max_pitch")
            

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
        if not scene_nwo.animations: return False
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
        animation = scene_nwo.animations[scene_nwo.active_animation_index]
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
        start = animation.frame_start
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
            
        animation.frame_end = int(action.frame_end)
            
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
            
class NWO_OT_AddAimAnimationBatch(NWO_AddAimAnimation):
    bl_idname = 'nwo.add_aim_animation_batch'
    bl_label = 'Batch Add Aim Animations'
    bl_description = 'Animates the aim bones (or aim control if it exists) based on the chosen option for all pose overlay animations'
    bl_options = {'REGISTER', 'UNDO'}
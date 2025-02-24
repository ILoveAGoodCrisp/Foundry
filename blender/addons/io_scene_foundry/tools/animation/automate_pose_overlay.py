

import os
from pathlib import Path
import time
import bpy
from math import degrees, radians
from mathutils import Matrix

from ... import utils
from ...managed_blam.animation import AnimationTag
import xml.etree.cElementTree as ET

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
        
    def from_xml_element(self, element: ET.Element):
        def solve_xml_value(field: ET.Element):
            value = field.attrib.get("value")
            if value is None:
                value = field.text
            return value
        
        for field in element.findall("field"):
            match field.attrib["name"]:
                case "label":
                    self.label = solve_xml_value(field)
                case "right yaw per frame":
                    self.right_yaw_per_frame = float(solve_xml_value(field))
                case "left yaw per frame":
                    self.left_yaw_per_frame = float(solve_xml_value(field))
                case "right frame count":
                    self.right_frame_count = int(solve_xml_value(field))
                case "left frame count":
                    self.left_frame_count = int(solve_xml_value(field))
                case "down pitch per frame":
                    self.down_pitch_per_frame = float(solve_xml_value(field))
                case "up pitch per frame":
                    self.up_pitch_per_frame = float(solve_xml_value(field))
                case "down pitch frame count":
                    self.down_pitch_frame_count = int(solve_xml_value(field))
                case "up pitch frame count":
                    self.up_pitch_frame_count = int(solve_xml_value(field))
        
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
        wraps = []
        # Right
        for i in reversed(range(self.right_frame_count + 1)):
            yaw = self.right_yaw_per_frame * -i
            yaw_transforms.append(yaw)
            if abs(yaw) > 180:
                if yaw > 0:
                    wraps.append("Wrapped Left")
                else:
                    wraps.append("Wrapped Right")
            else:
                wraps.append("")
            
        # Left
        for i in range(1, self.left_frame_count + 1):
            yaw = self.left_yaw_per_frame * i
            yaw_transforms.append(yaw)
            if abs(yaw) > 180:
                if yaw > 0:
                    wraps.append("Wrapped Left")
                else:
                    wraps.append("Wrapped Right")
            else:
                wraps.append("")
        
        pitch_transforms = []
        # Down
        for i in reversed(range(self.down_pitch_frame_count + 1)):
            pitch_transforms.append(self.down_pitch_per_frame * i)
            
        # Up
        for i in range(1, self.up_pitch_frame_count + 1):
            pitch_transforms.append(self.up_pitch_per_frame * -i)
            
        for p in pitch_transforms:
            for y, w in zip(yaw_transforms, wraps):
                yaw_matrix = Matrix.Rotation(radians(y), 4, 'Z')
                pitch_matrix = Matrix.Rotation(radians(p), 4, 'Y')
                self.transforms.append((tuple((yaw_matrix, pitch_matrix, w))))
        
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
    (Matrix.Rotation(radians(45), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(-45), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
]

preset_look_transforms = [
    (Matrix.Rotation(radians(-90), 4, 'Z'), Matrix.Rotation(radians(22.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-60), 4, 'Z'), Matrix.Rotation(radians(22.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-30), 4, 'Z'), Matrix.Rotation(radians(22.6), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(22.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(30), 4, 'Z'), Matrix.Rotation(radians(22.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(60), 4, 'Z'), Matrix.Rotation(radians(22.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(radians(22.6), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(-90), 4, 'Z'), Matrix.Rotation(radians(0.4), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-60), 4, 'Z'), Matrix.Rotation(radians(0.4), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-30), 4, 'Z'), Matrix.Rotation(radians(0.4), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(0.4), 4, 'Y'), ""),
    (Matrix.Rotation(radians(30), 4, 'Z'), Matrix.Rotation(radians(0.4), 4, 'Y'), ""),
    (Matrix.Rotation(radians(60), 4, 'Z'), Matrix.Rotation(radians(0.4), 4, 'Y'), ""),
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(radians(0.4), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(radians(-21.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(60), 4, 'Z'), Matrix.Rotation(radians(-21.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(30), 4, 'Z'), Matrix.Rotation(radians(-21.6), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-21.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-30), 4, 'Z'), Matrix.Rotation(radians(-21.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-60), 4, 'Z'), Matrix.Rotation(radians(-21.6), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-90), 4, 'Z'), Matrix.Rotation(radians(-21.6), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(-90), 4, 'Z'), Matrix.Rotation(radians(-37), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-60), 4, 'Z'), Matrix.Rotation(radians(-37), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-30), 4, 'Z'), Matrix.Rotation(radians(-37), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-37), 4, 'Y'), ""),
    (Matrix.Rotation(radians(30), 4, 'Z'), Matrix.Rotation(radians(-37), 4, 'Y'), ""),
    (Matrix.Rotation(radians(60), 4, 'Z'), Matrix.Rotation(radians(-37), 4, 'Y'), ""),
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(radians(-37), 4, 'Y'), ""),
]

preset_aim_transforms = [
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(-55), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-55), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-55), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(-55), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-55), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(73.5), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(73.5), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(73.5), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(73.5), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(73.5), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
]

preset_aim_turn_left_transforms = [
    (Matrix.Rotation(radians(-73.5), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-73.5), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-73.5), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(-73.5), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-73.5), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(15.5), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(15.5), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(15.5), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(15.5), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(15.5), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(75.5), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(75.5), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(75.5), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(75.5), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(75.5), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(-141), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-141), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-141), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(-141), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-141), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
]

preset_aim_turn_right_transforms = [
    (Matrix.Rotation(radians(55), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(55), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(55), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(55), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(55), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(-34), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-34), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-34), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(-34), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-34), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(-97.3), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-97.3), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-97.3), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(-97.3), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(-97.3), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(125), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(125), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(125), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(125), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(125), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
]

preset_biped_acc_transforms = [
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(-90), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    
    (Matrix.Rotation(radians(180), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(-1), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
]

preset_vehicle_acc_transforms = [
    (Matrix.Rotation(radians(45), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(135), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(180), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(225), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(270), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(315), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(360), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(360), 4, 'Z'), Matrix.Rotation(radians(90), 4, 'Y'), ""),
    (Matrix.Rotation(radians(360), 4, 'Z'), Matrix.Rotation(radians(-90), 4, 'Y'), ""),
]

preset_pain_transforms = [
    (Matrix.Rotation(radians(45), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(135), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(180), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(225), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(270), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(315), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    (Matrix.Rotation(radians(359), 4, 'Z'), Matrix.Rotation(0, 4, 'Y'), ""),
    
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(45), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(135), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(180), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(225), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(270), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(315), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(359), 4, 'Z'), Matrix.Rotation(radians(45), 4, 'Y'), ""),
    
    (Matrix.Rotation(0, 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(45), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(90), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(135), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(180), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(225), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(270), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(315), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
    (Matrix.Rotation(radians(359), 4, 'Z'), Matrix.Rotation(radians(-45), 4, 'Y'), ""),
]

preset_transforms = {
    "look": preset_look_transforms,
    "aim": preset_aim_transforms,
    "aim_turn_left": preset_aim_turn_left_transforms,
    "aim_turn_right": preset_aim_turn_right_transforms,
    "biped_acc": preset_biped_acc_transforms,
    "steering": preset_steering_transforms,
    "vehicle_acc": preset_vehicle_acc_transforms,
    "pain": preset_pain_transforms,
}

class PoseBuilder:
    def __init__(self, pedestal: bpy.types.PoseBone, pitch: bpy.types.PoseBone, yaw: bpy.types.PoseBone, control: bpy.types.PoseBone | None=None):
        self.pedestal = pedestal
        self.pitch = pitch
        self.yaw = yaw
        self.control = control
        self.uses_control = control is not None
        self.uses_pitch = pitch is not None
        self.uses_yaw = yaw is not None
        
    def _pre_build(self, scene: bpy.types.Scene, frame_start: int,  action: bpy.types.Action):
        # Clear any existing keyframe data on aim bones
        fcurves = action.fcurves
        fc_bone_names = []
        if self.uses_control:
            fc_bone_names.append(f'pose.bones["{self.control.name}"].')
        if self.uses_pitch:
            fc_bone_names.append(f'pose.bones["{self.pitch.name}"].')
        if self.uses_yaw:
            fc_bone_names.append(f'pose.bones["{self.yaw.name}"].')
            
        fc_bone_names = tuple(fc_bone_names)

        for fc in fcurves:
            if fc.data_path.startswith(fc_bone_names):
                fcurves.remove(fc)
                    
        # Set the current frame to the first frame of animation and ensure transform matches pedestal
        scene.frame_set(frame_start)
        if self.uses_control:
            self.control.matrix_basis = self.pedestal.matrix_basis
        if self.uses_pitch:
            self.pitch.matrix_basis = self.pedestal.matrix_basis
        if self.uses_yaw:
            self.yaw.matrix_basis = self.pedestal.matrix_basis
            
        # Keyframe this as the base pose
        if self.uses_control:
            self.control.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
        else:
            if self.uses_pitch:
                self.pitch.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
            if self.uses_yaw:
                self.yaw.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
            
    def _add_wrap_event(self, frame: int, animation, wrap_type: str):
        event = animation.animation_events.add()
        event.event_type = '_connected_geometry_animation_event_type_import'
        event.frame_frame = frame
        event.import_name = wrap_type
        event.name = f"{wrap_type} [{frame}]"
            
    def _build_poses(self, scene: bpy.types.Scene, animation, wrap_events: bool, transforms: list):
        # Loop through transforms and apply them
        if self.uses_control:
            for idx, (yaw, pitch, wrap) in enumerate(transforms):
                scene.frame_set(animation.frame_start + idx + 1)
                self.control.matrix_basis =  yaw @ pitch @ self.pedestal.matrix_basis
                self.control.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
                if wrap_events and wrap:
                    self._add_wrap_event(scene.frame_current, animation, wrap)
        else:
            for idx, (yaw, pitch, wrap) in enumerate(transforms):
                scene.frame_set(animation.frame_start + idx + 1)
                if self.uses_yaw:
                    self.yaw.matrix = self.pedestal.matrix @ yaw
                    self.yaw.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
                if self.uses_pitch:
                    self.pitch.matrix = self.pedestal.matrix @ pitch
                    self.pitch.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
                if wrap_events and wrap:
                    self._add_wrap_event(scene.frame_current, animation, wrap)
        
    def build_from_preset(self, scene: bpy.types.Scene, animation, action: bpy.types.Action, wrap_events: bool, preset: str) -> int:
        """Keyframes a pose overlay based on the input preset. Returns the last frame keyframed"""
        self._clear_wrap_events(animation)
        self._pre_build(scene, animation.frame_start, action)
        self._build_poses(scene, animation, wrap_events, preset_transforms[preset])
        return scene.frame_current
    
    def build_from_blend_screen(self, scene: bpy.types.Scene, animation, action: bpy.types.Action, wrap_events: bool, blend_screen: BlendScreen) -> int:
        """Keyframes a pose overlay based on the input blend screen. Returns the last frame keyframed"""
        self._clear_wrap_events(animation)
        self._pre_build(scene, animation.frame_start, action)
        self._build_poses(scene, animation, wrap_events, blend_screen.transforms)
        return scene.frame_current
    
    def _clear_wrap_events(self, animation):
        to_remove_indexes = []
        for idx, event in enumerate(animation.animation_events):
            if event.event_type == '_connected_geometry_animation_event_type_import':
                to_remove_indexes.append(idx)
                
        for idx in reversed(to_remove_indexes):
            animation.events.remove(idx)
            
def pose_overlay_armature_validate(armature: bpy.types.Object, nwo, report):
    if not armature.animation_data:
        armature.animation_data_create()
        
    pedestal_name = nwo.node_usage_pedestal
    if not pedestal_name:
        p = utils.get_pose_bone(armature, "b_pedestal")
        if p is not None:
            pedestal_name = p.name
            nwo.node_usage_pedestal = p.name
        
    yaw_name = nwo.node_usage_pose_blend_yaw
    if not yaw_name:
        y = utils.get_pose_bone(armature, "b_aim_yaw")
        if y is not None:
            yaw_name = y.name
            nwo.node_usage_pose_blend_yaw = y.name

    pitch_name = nwo.node_usage_pose_blend_pitch
    if not pitch_name:
        pi = utils.get_pose_bone(armature, "b_aim_pitch")
        if pi is not None:
            pitch_name = pi.name
            nwo.node_usage_pose_blend_pitch = pi.name
                
    aim_name = nwo.control_aim
    aim = None
    
    pedestal = armature.pose.bones.get(pedestal_name)
    if pedestal is None:
        report({'WARNING'}, f"Pedestal bone {pedestal_name} does not exist in {armature.name}")
    yaw = armature.pose.bones.get(yaw_name)
    if yaw is None:
        report({'WARNING'}, f"Pitch bone {pitch_name} does not exist in {armature.name}")
    pitch = armature.pose.bones.get(pitch_name)
    if pitch is None:
        report({'WARNING'}, f"Pitch bone {pitch_name} does not exist in {armature.name}")
    if aim_name:
        aim = armature.pose.bones.get(aim_name)
        if aim is None:
            report({'WARNING'}, f"Aim bone {aim_name} does not exist in {armature.name}")
            
    return pedestal, pitch, yaw, aim
    
class NWO_OT_GeneratePoses(bpy.types.Operator):
    bl_idname = 'nwo.generate_poses'
    bl_label = 'Generate Poses'
    bl_description = 'Animates the aim bones (or aim control if it exists) based on the chosen option. You should then animate your model as desired for each frame in the generated pose'
    bl_options = {'REGISTER', 'UNDO'}
    
    pose_type: bpy.props.EnumProperty(
        name="Type",
        description="Type of poses to generate",
        items=[
            ("preset", "Preset", "Choose from a list of preset poses"),
            ("legacy", "Blend Screen", "Computes poses from the data used by legacy blend screens"),
        ]
    )
    
    biped_preset: bpy.props.EnumProperty(
        name="Preset",
        items=[
            ("aim", "Aim", "Poses typically used for aiming animations like combat:aim_still_up. Assumes character is right handed as allows for greater turning to the right"),
            ("aim_turn_left", "Aim Turn Left", "Poses typically used for aiming animations during biped turning"),
            ("aim_turn_right", "Aim Turn right", "Poses typically used for aiming animations during biped turning"),
            ("look", "Look", "Poses typically used for steering animations like any:look"),
            ("biped_acc", "Acceleration", "Poses for a biped being effected by vehicle acceleration"),
            ('pain', "Pain", "Poses for a pain overlay, used to to determine reaction to damage dependent on direction")
        ]
    )
    
    vehicle_preset: bpy.props.EnumProperty(
        name="Preset",
        items=[
            ("steering", "Steering", "Poses typically used for steering animations like vehicle:steering"),
            ("vehicle_acc", "Acceleration / 360 Aiming", "Poses typically used for acceleration animations like vehicle:acceleration and 360 turret aiming like vehicle:aiming"),
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
    
    add_wrap_events: bpy.props.BoolProperty(
        name="Add Wrap Events",
        description="Adds pose overlay wrap animation events where appropriate. Enable this if you want to keep the pose overlay from becoming 3D",
        default=True,
    )
    
    unit_type: bpy.props.EnumProperty(
        name="Unit Type",
        description="Whether to generate poses from a vehicle or biped. This changes the presets available and if vehicle is selected, will automatically disable wrap events",
        items=[
            ("biped", "Biped", "Poses are for a biped e.g. weapon aiming"),
            ("vehicle", "Vehicle", "Poses are for a biped e.g. steering"),
        ]
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
        
        pedestal, pitch, yaw, aim = pose_overlay_armature_validate(armature, nwo, self.report)
        
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
        for_biped = self.unit_type == 'biped'
        with utils.ArmatureDeformMute():
            for track in animation.action_tracks:
                if track.object == armature and track.action:
                    if use_blend_screen_info:
                        animation.frame_end = builder.build_from_blend_screen(scene, animation, track.action, self.add_wrap_events and for_biped, blend_screen)
                    else:
                        animation.frame_end = builder.build_from_preset(scene, animation, track.action, self.add_wrap_events and for_biped, self.biped_preset if for_biped else self.vehicle_preset)
                    break

        scene.frame_start = animation.frame_start
        scene.frame_end = animation.frame_end
        scene.frame_current = current_frame
        
        return {'FINISHED'}
    
    def invoke(self, context: bpy.types.Context, _):
        return context.window_manager.invoke_props_dialog(self, width=330)
    
    def draw(self, context):
        for_biped = self.unit_type == 'biped'
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "unit_type", expand=True)
        layout.prop(self, "pose_type", expand=True)
        layout.separator()
        if self.pose_type == 'legacy':
            layout.prop(self, "right_yaw_per_frame")
            layout.prop(self, "left_yaw_per_frame")
            layout.prop(self, "right_frame_count")
            layout.prop(self, "left_frame_count")
            layout.prop(self, "down_pitch_per_frame")
            layout.prop(self, "up_pitch_per_frame")
            layout.prop(self, "down_pitch_frame_count")
            layout.prop(self, "up_pitch_frame_count")
        else:
            if for_biped:
                layout.prop(self, "biped_preset")
            else:
                layout.prop(self, "vehicle_preset")
                
        if for_biped:
            layout.prop(self, "add_wrap_events")
            
def parse_xml_for_blend_screens(xml_path: Path) -> dict | None:
    data = {}
    # These exported XMLs can't be parsed by default because they contain data, so clear these out
    xml_string = ""
    with open(xml_path, "r", errors="replace") as f:
        for line in f.readlines():
            if "<" in line and not "<!" in line and not "]]>" in line:
                xml_string += line
                
    xml_string = xml_string.strip("\n")
    
    # with open(xml_path, "w") as f:
    #     f.write(xml_string)
        
    # try:
    header = ET.fromstring(xml_string)
    # Check if this is an H1 animation tag file
    group = header.attrib.get("group")
    if group is None:
        return utils.print_warning("XML does not declare tag group")
    if group == "model_animations": # H1
        units_block = None
        vehicles_block = None
        animations_block = None
        animation_names = []
        for element in header.findall("block"):
            block_name = element.attrib["name"]
            match block_name:
                case 'UNITS':
                    units_block = element
                case 'VEHICLES':
                    vehicles_block = element
                case 'animations':
                    animations_block = element
                    
        if animations_block is None or (units_block is None and vehicles_block is None):
            return
        
        for element in animations_block.findall("element"):
            name_field = element.find("field")
            animation_names.append(name_field.text)
                
        if units_block is not None:
            for bs_element in units_block.findall("element"):
                blend_screen = BlendScreen()
                blend_screen.from_xml_element(bs_element)
                blend_screen.compute_transforms()
                
                for bs_block in bs_element.findall("block"):
                    bs_block_name = bs_block.attrib["name"]
                    if bs_block_name == "animations":
                        for anim_element in bs_block.findall("element"):
                            block_index_element = anim_element.find("block_index")
                            anim_index = int(block_index_element.attrib["index"])
                            if anim_index == -1:
                                continue
                            anim_name = animation_names[anim_index]
                            data[anim_name.strip().replace(" ", ":").lower()] = blend_screen
                    elif bs_block_name == "weapons":
                        for as_element in bs_block.findall("element"):
                            blend_screen = BlendScreen()
                            blend_screen.from_xml_element(bs_element)
                            blend_screen.compute_transforms()
                            for as_block in as_element.findall("block"):
                                as_block_name = as_block.attrib["name"]
                                if as_block_name == "animations":
                                    for anim_element in as_block.findall("element"):
                                        block_index_element = anim_element.find("block_index")
                                        anim_index = int(block_index_element.attrib["index"])
                                        if anim_index == -1:
                                            continue
                                        anim_name = animation_names[anim_index]
                                        data[anim_name.strip().replace(" ", ":").lower()] = blend_screen
                                break
                        break
                                        
        if vehicles_block is not None:
            for bs_element in units_block.findall("element"):
                blend_screen = BlendScreen()
                blend_screen.from_xml_element(bs_element)
                blend_screen.compute_transforms()
                
                for bs_block in bs_element.findall("block"):
                    bs_block_name = bs_block.attrib["name"]
                    if bs_block_name == "animations":
                        for anim_element in bs_block.findall("element"):
                            block_index_element = anim_element.find("block_index")
                            anim_index = int(block_index_element.attrib["index"])
                            if anim_index == -1:
                                continue
                            anim_name = animation_names[anim_index]
                            data[anim_name.strip().replace(" ", ":").lower()] = blend_screen
                        break
                    
    else: # H2+
        blend_screens = []
        found_blend_screens = False
        found_animations = False
        for element in header.findall("block"):
            block_name = element.attrib["name"]
            if block_name == "blend screens":
                for bs_element in element.findall("element"):
                    blend_screen = BlendScreen()
                    blend_screen.from_xml_element(bs_element)
                    blend_screen.compute_transforms()
                    blend_screens.append(blend_screen)
                found_blend_screens = True
            elif block_name == "animations":
                if not found_blend_screens:
                    return
                for a_element in element.findall("element"):
                    bs_index_element = a_element.find("block_index")
                    if bs_index_element is None:
                        for field in a_element.findall("field"):
                            if field.attrib["name"] == "blend screen":
                                bs_index = int(field.attrib["value"][1:])
                                break
                    else:
                        bs_index = int(bs_index_element.attrib["index"])

                    if bs_index == -1:
                        continue
                    
                    anim_name_field = a_element.find("field")
                    anim_name = anim_name_field.attrib.get("value")
                    if anim_name is None:
                        anim_name = anim_name_field.text
                    
                    data[anim_name] = blend_screens[bs_index]
                found_animations = True
                
            if found_blend_screens and found_animations:
                break

    return data
    
def convert_legacy_pose_overlays(armature: bpy.types.Object, scene: bpy.types.Scene, builder: PoseBuilder, data: dict):
    animations = {a.name.strip().replace(" ", ":").lower(): a for a in scene.nwo.animations}
    animation_indexes = {a: idx for idx, a in enumerate(list(animations.values()))}
    with utils.ArmatureDeformMute():
        for animation_name, blend_screen in data.items():
            animation = animations.get(animation_name)
            if animation is None:
                continue
            print(f"--- Converting {animation_name}")
            add_wrap_events = not ("vehicle" in animation_name or "pain" in animation_name)
            scene.nwo.active_animation_index = animation_indexes[animation]
            for track in animation.action_tracks:
                if track.object == armature and track.action:
                    animation.frame_end = builder.build_from_blend_screen(scene, animation, track.action, add_wrap_events, blend_screen)
                    break
            
class NWO_OT_ConvertLegacyPoseOverlays(bpy.types.Operator):
    bl_idname = 'nwo.convert_legacy_pose_overlays'
    bl_label = 'Convert'
    bl_description = 'Converts legacy pose overlay animations (those used in H1 - ODST) to the new format'
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(
        name='Filepath',
        subtype='FILE_PATH',
        options={"HIDDEN"},
    )
    
    filter_glob: bpy.props.StringProperty(
        default="*.m*_a*_*graph;*.m*_animations;*xml;",
        options={"HIDDEN", "SKIP_SAVE"},
        maxlen=1024,
    )
    
    def execute(self, context):
        scene = context.scene
        nwo = scene.nwo
        if not scene.nwo.animations:
            self.report({'WARNING'}, "No animations in Scene")
            return {'CANCELLED'}
        
        armature = utils.get_rig_prioritize_active(context)
        if armature is None:
            self.report({'WARNING'}, "No Armature in Scene")
            return {'CANCELLED'}
        
        pedestal, pitch, yaw, aim = pose_overlay_armature_validate(armature, nwo, self.report)
        
        if not aim and (not yaw and not pitch):
            self.report({'WARNING'}, f"Armature {armature.name} does not have aim bones. Cannot build poses")
            return {'CANCELLED'}
        
        os.system("cls")
        start = time.perf_counter()
        user_cancelled = False
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            context.scene.nwo_export.show_output = False
            
        export_title = f"►►► LEGACY POSE OVERLAY CONVERTER ◄◄◄\n"
        print(export_title)
        
        if self.filepath.endswith(".xml"):
            xml_path = Path(self.filepath)
        else:
            print(f"--- Converting {self.filepath} to XML")
            xml_path = utils.tag_to_xml(self.filepath)
            if xml_path is None:
                self.report({'WARNING'}, f"Failed to export {self.filepath} to xml")
                return {'CANCELLED'}
        
        print(f"--- Reading blend screen data from {xml_path}")
        
        blend_screen_info = parse_xml_for_blend_screens(xml_path)
        if not blend_screen_info:
            self.report({'WARNING'}, f"{self.filepath} contains no blend sceen information")
            return {'CANCELLED'}
        
        current_frame = scene.frame_current
        current_animation_index = nwo.active_animation_index
        convert_legacy_pose_overlays(armature, scene, PoseBuilder(pedestal, pitch, yaw, aim), blend_screen_info)
        nwo.active_animation_index = current_animation_index
        scene.frame_current = current_frame
        
        print("\n-----------------------------------------------------------------------")
        print(f"Completed in {utils.human_time(time.perf_counter() - start, True)}")
        print("-----------------------------------------------------------------------\n")

        return {'FINISHED'}
    
    def invoke(self, context, _):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def draw(self, context):
        self.layout.label(text="Select the animation tag file")
        self.layout.label(text="containing the blend screens")
        self.layout.label(text="you wish to use for conversion")
    
    
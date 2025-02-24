

import math
import os
import time
import bpy
from mathutils import Euler, Matrix, Quaternion
from ... import utils

list_source_bones = []
list_root_bones = []

class NWO_OT_MovementDataToPedestal(bpy.types.Operator):
    bl_idname = "nwo.movement_data_transfer"
    bl_label = "Movement Data Transfer"
    bl_description = "Transfers the movement data of the source bone to the given root bone for the current or all animations. The type of movement transfered depends on the animation movement type"
    bl_options = {"UNDO", "REGISTER"}
    
    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations
    
    def items_list_source_bones(self, context):
        return list_source_bones
    
    def items_list_root_bones(self, context):
        return list_root_bones
    
    source_bone: bpy.props.EnumProperty(
        name="Source Bone",
        description="The source bone that holds the movement to transfer. In the case of a legacy halo character animation this is usually the pelvis",
        items=items_list_source_bones,
    )
    
    root_bone: bpy.props.EnumProperty(
        name="Root Bone",
        description="The root bone that movement data should be transferred to. This will be the pedestal bone",
        items=items_list_root_bones,
    )
    
    all_animations: bpy.props.BoolProperty(
        name="All Animations",
        description="This operator will run on all animations instead of the currently active one"
    )
    
    def find_armature_ob(self, context):
        if getattr(self, "ob", None) is None:
            ob = None
            if context.object and context.object.type == "ARMATURE":
                ob = context.object
            else:
                ob = utils.get_rig(context)
                
            if ob is None:
                self.report({'WARNING'}, "No armature in scene")
                return {'CANCELLED'}
            
            
            global list_root_bones
            list_root_bones = []
            for bone in ob.pose.bones:
                if not bone.parent:
                    list_root_bones.append((bone.name, bone.name, ""))
                    
            global list_source_bones
            list_source_bones = []
            for bone in ob.pose.bones:
                if bone.parent:
                    list_source_bones.append((bone.name, bone.name, ""))
                    
            self.ob = ob
    
    def invoke(self, context, event):
        self.find_armature_ob(context)
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "source_bone")
        layout.prop(self, "root_bone")
        layout.prop(self, "all_animations")
    
    def execute(self, context):
        if not context.scene.nwo.animations:
            self.report({'WARNING'}, "No animations in scene")
            return {'CANCELLED'}
        
        if not self.all_animations and context.scene.nwo.active_animation_index == -1:
            self.report({'WARNING'}, "No active animation")
            return {'CANCELLED'}
        
        self.find_armature_ob(context)
        
        current_frame = context.scene.frame_current
        current_animation_index = context.scene.nwo.active_animation_index
        current_animation = context.scene.nwo.animations[context.scene.nwo.active_animation_index]
        current_pose = self.ob.data.pose_position
        
        if not self.all_animations and (current_animation.animation_type != "base" or current_animation.animation_movement_data == "none"):
            self.report({'WARNING'}, "Active animation has no movement data")
            return {'CANCELLED'}
        
        
        self.ob.data.pose_position = 'REST'
        context.view_layer.update()
        source_rest_matrix = self.ob.pose.bones[self.source_bone].matrix
        root_rest_matrix = self.ob.pose.bones[self.root_bone].matrix
        self.ob.data.pose_position = 'POSE'
        context.view_layer.update()
        
        os.system("cls")
        start = time.perf_counter()
        if context.scene.nwo_export.show_output:
            bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
            context.scene.nwo_export.show_output = False
            
        export_title = f"►►► MOVEMENT DATA TRANSFER ◄◄◄\n"
        print(export_title)
        
        if self.all_animations:
            print("Converting All Movement Animations")
            for idx, animation in enumerate(context.scene.nwo.animations):
                if animation.animation_type == "base" and animation.animation_movement_data != "none":
                    print(f"--- {animation.name}")
                    transfer_movement(context, animation, idx, self.ob, self.source_bone, self.root_bone, source_rest_matrix, root_rest_matrix)
        else:
            print(f"Converting {current_animation.name}")
            transfer_movement(context, current_animation, current_animation_index, self.ob, self.source_bone, self.root_bone, source_rest_matrix, root_rest_matrix)
            
        
        self.ob.data.pose_position = current_pose
        context.scene.nwo.active_animation_index = current_animation_index
        context.scene.frame_set(current_frame)
        
        print("\n-----------------------------------------------------------------------")
        print(f"Completed in {utils.human_time(time.perf_counter() - start, True)}")
        print("-----------------------------------------------------------------------\n")
        
        return {'FINISHED'}
            
def transfer_movement(context: bpy.types.Context, animation, animation_index: int, ob: bpy.types.Object, source_bone_name: str, root_bone_name: str, source_rest_matrix: Matrix, root_rest_matrix: Matrix):
    context.scene.nwo.active_animation_index = animation_index
    scene = context.scene
    movement = animation.animation_movement_data
    horizontal = "xy" in movement
    vertical = "z" in movement
    yaw = "yaw" in movement
    full = movement == "full"
    
    root_bone = ob.pose.bones[root_bone_name]
    root_bone: bpy.types.PoseBone
    source_bone = ob.pose.bones[source_bone_name]
    source_bone: bpy.types.PoseBone
    
    # Neutralise source movement and save offets
    source_rest_loc = source_rest_matrix.to_translation()
    source_rest_rot = source_rest_matrix.to_euler('XYZ')
    scene.frame_set(animation.frame_start)
    offsets = []
    rot_negative = False
    previous_yaw = None
    direction_found = False
    for i in range(animation.frame_start, animation.frame_end + 1):
        scene.frame_set(i)
        frame_offsets = [0, 0, 0, 0, 0, 0] # LOC XYZ, ROT XYZ
        loc, rot, sca = source_bone.matrix.decompose()
        rot = rot.to_euler('XYZ')
        if horizontal or vertical or full:
            x_offset = source_rest_loc.x - loc.x
            y_offset = source_rest_loc.y - loc.y
            frame_offsets[0] = x_offset
            frame_offsets[1] = y_offset
            if vertical or full:
                z_offset = source_rest_loc.z - loc.z
                frame_offsets[2] = z_offset
                
            loc.x += x_offset
            loc.y += y_offset
            if vertical or full:
                loc.z += z_offset
                
        if yaw or full:
            z_rot = rot.z
            if full:
                x_rot_offset = source_rest_rot.x - rot.x
                y_rot_offset = source_rest_rot.y - rot.y
                frame_offsets[3] = x_rot_offset
                frame_offsets[4] = y_rot_offset
            
            if direction_found:
                if rot_negative:
                    while z_rot > previous_yaw:
                        z_rot -= math.radians(180)
                else:
                    while z_rot < previous_yaw:
                        z_rot += math.radians(180)
            elif previous_yaw is not None:
                if z_rot > previous_yaw:
                    direction_found = True
                elif z_rot < previous_yaw:
                    direction_found = True
                    rot_negative = True
                
            z_rot_offset = source_rest_rot.z - z_rot
            previous_yaw = z_rot
            frame_offsets[5] = z_rot_offset
            
            
            if full:
                rot.x += x_rot_offset
                rot.y += y_rot_offset
            rot.z += z_rot_offset
            
        if abs(frame_offsets[5]) > 180:
            frame_offsets[5] = -((360 - abs(frame_offsets[5])) * (1 if frame_offsets[5] > 0 else -1))

        offsets.append(frame_offsets)

        source_bone.matrix = Matrix.LocRotScale(loc, rot, sca)
        
        if horizontal or vertical or full:
            source_bone.keyframe_insert(data_path='location', frame=scene.frame_current)
        if yaw or full:
            source_bone.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)
    
    # Apply offsets to root
    for idx, i in enumerate(range(animation.frame_start, animation.frame_end + 1)):
        scene.frame_set(i)
        frame_offsets = offsets[idx]
        loc, rot, sca = root_bone.matrix.decompose()
        rot = rot.to_euler('XYZ')
        if idx == 0:
            if horizontal or vertical or full:
                loc.x -= frame_offsets[0]
                loc.y -= frame_offsets[1]
                if vertical or full:
                    loc.z -= frame_offsets[2]
                    
            if yaw or full:
                if full:
                    rot.x -= frame_offsets[3]
                    rot.y -= frame_offsets[4]
                rot.z -= frame_offsets[5]
        else:
            if horizontal or vertical or full:
                loc.x -= (frame_offsets[0] - offsets[idx - 1][0])
                loc.y -= (frame_offsets[1] - offsets[idx - 1][1])
                if vertical or full:
                    loc.z -= (frame_offsets[2] - offsets[idx - 1][2])
                    
            if yaw or full:
                if full:
                    rot.x -= (frame_offsets[3] - offsets[idx - 1][3])
                    rot.y -= (frame_offsets[4] - offsets[idx - 1][4])
                rot.z -= (frame_offsets[5] - offsets[idx - 1][5])
        
        root_bone.matrix = Matrix.LocRotScale(loc, rot, sca)
        if horizontal or vertical or full:
            root_bone.keyframe_insert(data_path='location', frame=scene.frame_current)
        if yaw or full:
            root_bone.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current)

        
    
    # Step 1: Add pedestal movement via constraints
    # scene.frame_set(animation.frame_start)
    # using_copy_loc = False
    # using_copy_rot = False
    # if horizontal or vertical or full:
    #     con_copy_loc = root_bone.constraints.new(type="COPY_LOCATION")
    #     con_copy_loc.target = ob
    #     con_copy_loc.subtarget = source_bone_name
    #     if horizontal and not vertical and not full:
    #         con_copy_loc.use_z = False
            
    #     con_copy_loc.target_space = 'LOCAL_OWNER_ORIENT'
    #     con_copy_loc.owner_space = 'LOCAL'
            
    #     using_copy_loc = True
            
    # if yaw or full:
    #     con_copy_rot = root_bone.constraints.new(type="COPY_ROTATION")
    #     con_copy_rot.target = ob
    #     con_copy_rot.subtarget = source_bone_name
        
    #     con_copy_rot.use_z = True
    #     con_copy_rot.use_y = True
    #     con_copy_rot.use_x = True
            
    #     con_copy_rot.target_space = 'LOCAL_OWNER_ORIENT'
    #     con_copy_rot.owner_space = 'LOCAL'
        
    #     using_copy_rot = True
        
    # # Step 2: Bake pedestal movement
    # while scene.frame_current < animation.frame_end:
    #     scene.frame_set(scene.frame_current + 1)
    #     if using_copy_loc:
    #         root_bone.keyframe_insert(data_path='location', frame=scene.frame_current, options={'INSERTKEY_VISUAL'})
    #     if using_copy_rot:
    #         root_bone.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current, options={'INSERTKEY_VISUAL'})
        
    # scene.frame_set(animation.frame_start)
    # if using_copy_loc:
    #     root_bone.constraints.remove(con_copy_loc)
    # if using_copy_rot:
    #     root_bone.constraints.remove(con_copy_rot)
    
    # # Step 3: Fix source movement via contraints
    
    # con_child_of = source_bone.constraints.new(type='CHILD_OF')
    # con_child_of.target = ob
    # con_child_of.subtarget = root_bone_name
    
    # # if using_copy_loc:
    # #     con_limit_loc = source_bone.constraints.new(type="LIMIT_LOCATION")
    # #     if horizontal or full:
    # #         con_limit_loc.use_min_x = True
    # #         con_limit_loc.use_min_y = True
    # #         con_limit_loc.use_max_x = True
    # #         con_limit_loc.use_max_y = True
    # #     if vertical or full:
    # #         con_limit_loc.use_min_z = True
    # #         con_limit_loc.use_max_z = True

    # # Step 4: Bake new source movement
    # while scene.frame_current < animation.frame_end:
    #     scene.frame_set(scene.frame_current + 1)
    #     parent_matrix = root_bone.matrix.copy()
    #     source_bone.matrix = parent_matrix.inverted() @ source_bone.matrix
    #     if using_copy_loc:
    #         source_bone.keyframe_insert(data_path='location', frame=scene.frame_current, options={'INSERTKEY_VISUAL'})
    #     if using_copy_rot:
    #         source_bone.keyframe_insert(data_path='rotation_quaternion', frame=scene.frame_current, options={'INSERTKEY_VISUAL'})
            
            
    # scene.frame_set(animation.frame_start)
    # source_bone.constraints.remove(con_child_of)
    # if using_copy_loc:
    #     source_bone.constraints.remove(con_limit_loc)
            
            
    
class FCurveTransfer:
    source_fcurve: bpy.types.FCurve
    target_fcurve: bpy.types.FCurve
    
    def __init__(self, action: bpy.types.Action, source_bone: str, target_bone: str, source_channel: str, target_channel: str) -> None:
        source_channel_array_index, source_channel_name = source_channel.split(':')
        target_channel_array_index, target_channel_name = target_channel.split(':')
        self.action = action
        self.source_bone = source_bone
        self.target_bone = target_bone
        self.source_channel = source_channel_name
        self.source_channel_index = int(source_channel_array_index)
        self.target_channel_index = int(target_channel_array_index)
        self.target_channel = target_channel_name
        self.source_fcurve = None
        self.target_fcurve = None
    
    def get_fcurves(self):
        source_data_path = f'pose.bones["{self.source_bone}"].{self.source_channel}'
        target_data_path = f'pose.bones["{self.target_bone}"].{self.target_channel}'
        for fc in self.action.fcurves:
            fc: bpy.types.FCurve
            if fc.data_path == source_data_path and fc.array_index == self.source_channel_index:
                self.source_fcurve = fc
            elif fc.data_path == target_data_path and fc.array_index == self.target_channel_index:
                self.target_fcurve = fc
                
        if not self.source_fcurve:
            return
        
        if not self.target_fcurve:
            self.target_fcurve = self.action.fcurves.new(data_path=f'pose.bones["{self.target_bone}"].{self.target_channel}', index=self.target_channel_index)
            
    def transfer_data(self):
        source_coordinates = []
        for kfp in self.source_fcurve.keyframe_points:
            source_coordinates.append(kfp.co_ui[1])
            
        target_kfps = self.target_fcurve.keyframe_points
        for index, coordinates in enumerate(source_coordinates):
            target_kfps.insert(index, coordinates, options={'REPLACE'})
            
    def remove_source_fcurve(self):
        self.action.fcurves.remove(self.source_fcurve)
            
class NWO_OT_FcurveTransfer(bpy.types.Operator):
    bl_idname = "nwo.fcurve_transfer"
    bl_label = "Motion Transfer"
    bl_description = "Transfers animation keyframes from one channel to another. For example transferring all motion on the Z location channel of bone A to the X location channel of bone B"
    bl_options = {"UNDO", "REGISTER"}
    
    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == 'ARMATURE'
    
    all_animations: bpy.props.BoolProperty(
        name="All Animations",
        description="Run this operator on all actions in the blend file. Disable to only run on the active animation",
    )
    
    remove_source_data: bpy.props.BoolProperty(
        name="Remove Source Channel",
        description="Removes all data from the source channel after transfer",
        default=True,
    )
    
    def list_bones(self, context):
        items = []
        arm = context.object
        for bone in arm.pose.bones:
            items.append((bone.name, bone.name, ""))
            
        return items
            
    def list_channels(self, context):
        items = [
            ("0:location", "X Location", ""),
            ("1:location", "Y Location", ""),
            ("2:location", "Z Location", ""),
            ("0:rotation_euler", "X Euler", ""),
            ("1:rotation_euler", "Y Euler", ""),
            ("2:rotation_euler", "Z Euler", ""),
            ("0:rotation_quaternion", "W Quarternion", ""),
            ("1:rotation_quaternion", "X Quaternion", ""),
            ("2:rotation_quaternion", "Y Quaternion", ""),
            ("3:rotation_quaternion", "Z Quaternion", ""),
            ("0:scale", "X Scale", ""),
            ("1:scale", "Y Scale", ""),
            ("2:scale", "Z Scale", ""),
        ]
        
        return items
    
    source_bone: bpy.props.EnumProperty(
        name="Source Bone",
        description="The bone to transfer data from",
        items=list_bones,
    )
    
    source_channel: bpy.props.EnumProperty(
        name="Source Channel",
        description="The name of the channel containing data. This data must exist",
        items=list_channels,
    )
    
    target_bone: bpy.props.EnumProperty(
        name="Target Bone",
        description="The bone to transfer data to",
        items=list_bones,
    )
    
    target_channel: bpy.props.EnumProperty(
        name="Target Channel",
        description="The name of the channel to receive data. This can be empty",
        items=list_channels,
    )

    def execute(self, context):
        active_animation_index = context.scene.nwo.active_animation_index
        animation = context.scene.nwo.animations[active_animation_index]
        actions = []
        if self.all_animations:
            actions = set(bpy.data.actions)
        else:
            actions = {track.action for track in animation.action_tracks}
            
        utils.clear_animation(animation)
        for action in actions:
            fcurve_transfer = FCurveTransfer(action, self.source_bone, self.target_bone, self.source_channel, self.target_channel)
            fcurve_transfer.get_fcurves()
            if fcurve_transfer.source_fcurve:
                fcurve_transfer.transfer_data()
                if self.remove_source_data:
                    fcurve_transfer.remove_source_fcurve()
            else:
                self.report({'WARNING'}, f"Failed to find source fcurve on action {action.name}")
        
        context.scene.nwo.active_animation_index = active_animation_index
        return {"FINISHED"}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "source_bone")
        layout.prop(self, "source_channel")
        layout.separator()
        layout.prop(self, "target_bone")
        layout.prop(self, "target_channel")
        layout.separator()
        layout.prop(self, "all_animations")
        layout.prop(self, "remove_source_data")



import math
import os
import time
from typing import cast
import bpy
from mathutils import Euler, Matrix, Quaternion
from ... import utils

list_source_bones = []
list_root_bones = []

turn_rots = {
    "turn_left": (0, 90),
    "turn_left_slow": (0, 45),
    "turn_left_fast": (0, 360),
    "turn_right": (0, -90),
    "turn_right_slow": (0, -45),
    "turn_right_fast": (0, -360),
}

last_source_bone = ""
last_root_bone = ""

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
        options={'SKIP_SAVE'},
        description="The source bone that holds the movement to transfer. In the case of a legacy halo character animation this is usually the pelvis",
        items=items_list_source_bones,
    )
    
    root_bone: bpy.props.EnumProperty(
        name="Root Bone",
        options={'SKIP_SAVE'},
        description="The root bone that movement data should be transferred to. This will be the pedestal bone",
        items=items_list_root_bones,
    )
    
    all_animations: bpy.props.BoolProperty(
        name="All Animations",
        description="This operator will run on all animations instead of the currently active one"
    )
    
    include_no_movement: bpy.props.BoolProperty(
        name="Include All Base Animations",
        default=False,
        description="Transfers movement data for no movement base animations. These will be treated as if they have XY yaw movement by default; this will be overridden if the movement data type is set to manual"
    )
    
    movement_type: bpy.props.EnumProperty(
        name="Movement Type",
        description="Determines what transforms are moved from the source bone to the root bone",
        items=[
            ('AUTOMATIC', "Automatic", "Movement type used accounts for the animation movement data type"),
            ('MANUAL', "Manual", "Define the exact type of transforms to move"),
            ('POSE', "Pose", "Uses the root bones current transform and updates keyframes such that the visual animation of the source bone is unchanged"),
            ('ANIMATION', "Animation", "Uses the root bones transform at either the start or end of the specified animation and updates keyframes such that the visual animation of the source bone is unchanged"),
            ('RESET', "Reset", "Resets the root bone to its rest position and updates keyframes such that the visual animation of the source bone is unchanged")
        ]
    )
    
    animation: bpy.props.StringProperty(
        name="Animation",
    )
    
    start_end: bpy.props.EnumProperty(
        name="Frame",
        items=[
            ('START', "Start", "Get root position from start frame"),
            ('END', "End", "Get root position from end frame")
        ]
    )
    
    use_x_loc: bpy.props.BoolProperty(
        name="Forward",
        default=True,
        description=""
    )
    use_y_loc: bpy.props.BoolProperty(
        name="Side to Side",
        default=True,
        description=""
    )
    use_z_loc: bpy.props.BoolProperty(
        name="Vertical",
        description=""
    )
    use_x_rot: bpy.props.BoolProperty(
        name="X Rotation",
        description=""
    )
    use_y_rot: bpy.props.BoolProperty(
        name="Y Rotation",
        description=""
    )
    use_z_rot: bpy.props.BoolProperty(
        name="Z Rotation",
        default=True,
        description=""
    )
    
    def find_armature_ob(self, context):
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
                
        list_source_bones.sort(key=lambda x: "aim" in x[0]) # so aim pitch / aim_yaw don't get sorted first
                
        self.ob = ob
    
    def invoke(self, context, event):
        self.find_armature_ob(context)
        for bone in self.ob.pose.bones:
            if bone.name == last_source_bone:
                self.source_bone = last_source_bone
            elif bone.name == last_root_bone:
                self.root_bone = last_root_bone
                
        return context.window_manager.invoke_props_dialog(self, width=600)
    
    def draw(self, context):
        layout = cast(bpy.types.UILayout, self.layout)
        layout.use_property_split = True
        layout.prop(self, "source_bone")
        layout.prop(self, "root_bone")
        layout.prop(self, "all_animations")
        layout.prop(self, "movement_type", expand=True)
        if self.movement_type == 'MANUAL':
            layout.prop(self, "use_x_loc")
            layout.prop(self, "use_y_loc")
            layout.prop(self, "use_z_loc")
            layout.prop(self, "use_x_rot")
            layout.prop(self, "use_y_rot")
            layout.prop(self, "use_z_rot")
        elif self.movement_type == 'ANIMATION':
            layout.prop_search(self, "animation", context.scene.nwo, "animations", icon='ANIM')
            layout.prop(self, "start_end", expand=True)
        elif self.movement_type == 'AUTOMATIC':
            layout.prop(self, "include_no_movement")
        
    def has_movement_data(self, animation) -> bool:
        if animation.animation_type not in {'base', 'world'}:
            return False
        none_movement = animation.animation_movement_data == "none"
        if none_movement:
            if not self.include_no_movement:
                return False
            state = utils.space_partition(animation.name.replace(":", " "), True).lower()
            return state not in {'idle', 'takeoff'}
        
        return True
    
    def execute(self, context):
        global last_source_bone
        global last_root_bone
        last_source_bone = self.source_bone
        last_root_bone = self.root_bone
        
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
        current_object = context.object
        current_mode = context.mode
        
        settings_dict = {}
        root_matrix = None
        if self.movement_type == 'MANUAL':
            settings_dict["use_x_loc"] = self.use_x_loc
            settings_dict["use_y_loc"] = self.use_y_loc
            settings_dict["use_z_loc"] = self.use_z_loc
            settings_dict["use_x_rot"] = self.use_x_rot
            settings_dict["use_y_rot"] = self.use_y_rot
            settings_dict["use_z_rot"] = self.use_z_rot
        elif self.movement_type == 'POSE':
            root_matrix = self.ob.pose.bones[self.root_bone].matrix.copy()
        elif self.movement_type == 'RESET':
            root_matrix = Matrix.Identity(4)
        elif self.movement_type == 'ANIMATION':
            if not self.animation:
                self.report({'WARNING'}, "No animation specified")
                return {'CANCELLED'}
            for idx, animation in enumerate(context.scene.nwo.animations):
                if animation.name == self.animation:
                    context.scene.nwo.active_animation_index = idx
                    if self.start_end == 'START':
                        context.scene.frame_set(animation.frame_start)
                    else:
                        context.scene.frame_set(animation.frame_end)
                    break
                
            root_matrix = self.ob.pose.bones[self.root_bone].matrix.copy()
                
            context.scene.nwo.active_animation_index = current_animation_index
            context.scene.frame_set(current_frame)
        
        if not self.all_animations and not self.has_movement_data(current_animation) and not settings_dict and root_matrix is None:
            self.report({'WARNING'}, "Active animation has no movement data")
            return {'CANCELLED'}

        utils.set_object_mode(context)
        utils.set_active_object(self.ob)
        
        
        if self.all_animations:
            os.system("cls")
            start = time.perf_counter()
            if context.scene.nwo_export.show_output:
                bpy.ops.wm.console_toggle()  # toggle the console so users can see progress of export
                context.scene.nwo_export.show_output = False
                
            export_title = f"►►► MOVEMENT DATA TRANSFER ◄◄◄\n"
            print(export_title)
        
        source_bone_anim_matrices = {}
        source_bone = self.ob.pose.bones[self.source_bone]
        if self.all_animations:
            print("Getting existing source bone poses")
            for i in range(len(context.scene.nwo.animations)):
                animation = context.scene.nwo.animations[idx]
                print(f"--- {animation.name}")
                source_bone_anim_matrices[i] = get_source_bone_matrices(context, i, animation, source_bone)
        else:
            print(f"Getting existing source bone poses for {current_animation.name}")
            source_bone_anim_matrices[current_animation_index] = get_source_bone_matrices(context, current_animation_index, current_animation, source_bone)
        
        self.ob.data.pose_position = 'REST'
        context.view_layer.update()
        root_rest_matrix = self.ob.pose.bones[self.root_bone].matrix.copy()
        bpy.ops.object.editmode_toggle()
        self.ob.data.edit_bones[self.source_bone].parent = None
        bpy.ops.object.editmode_toggle()
        self.ob.data.pose_position = 'POSE'
        context.view_layer.update()
        
        if self.movement_type == 'RESET':
            root_matrix = root_rest_matrix

        if self.all_animations:
            print("Calculating new root movement for all animations")
            for idx, animation in enumerate(context.scene.nwo.animations):
                if root_matrix is not None or settings_dict or self.has_movement_data(animation):
                    print(f"--- {animation.name}")
                    transfer_movement(context, animation, idx, self.ob, self.source_bone, self.root_bone, root_rest_matrix, root_matrix, settings_dict)
        else:
            print(f"Calculating new root movement for {current_animation.name}")
            transfer_movement(context, current_animation, current_animation_index, self.ob, self.source_bone, self.root_bone, root_rest_matrix, root_matrix, settings_dict)
            
        bpy.ops.object.editmode_toggle()
        self.ob.data.edit_bones[self.source_bone].parent = self.ob.data.edit_bones[self.root_bone]
        bpy.ops.object.editmode_toggle()
        
        print(f"\nSetting new source bone keyframes")
        for idx, source_bone_matrices in source_bone_anim_matrices.items():
            animation = context.scene.nwo.animations[idx]
            print(f"--- {animation.name}")
            fix_source_movement(context, animation, idx, self.ob, self.source_bone, source_bone_matrices)
        
        self.ob.data.pose_position = current_pose
        context.scene.nwo.active_animation_index = current_animation_index
        context.scene.frame_set(current_frame)
        context.view_layer.objects.active = current_object
        utils.restore_mode(current_mode)
        
        if self.all_animations:
            print("\n-----------------------------------------------------------------------")
            print(f"Completed in {utils.human_time(time.perf_counter() - start, True)}")
            print("-----------------------------------------------------------------------\n")
        
        return {'FINISHED'}
    
def get_source_bone_matrices(context: bpy.types.Context, animation_index: int, animation, source_bone: bpy.types.PoseBone):
    context.scene.nwo.active_animation_index = animation_index
    scene = context.scene
    source_bone_matrices = []
    for i in range(animation.frame_start, animation.frame_end + 1):
        scene.frame_set(i)
        source_bone_matrices.append(source_bone.matrix.copy())
        
    return source_bone_matrices
    
def fix_source_movement(context: bpy.types.Context, animation, animation_index: int, ob: bpy.types.Object, source_bone_name: str, source_bone_matrices: list[Matrix]):
    context.scene.nwo.active_animation_index = animation_index
    source_bone = ob.pose.bones[source_bone_name]
    for idx, i in enumerate(range(animation.frame_start, animation.frame_end + 1)):
        context.scene.frame_set(i)
        source_bone.matrix = source_bone_matrices[idx]
        context.view_layer.update()
        source_bone.keyframe_insert(data_path='location', frame=i, options={'INSERTKEY_VISUAL'})
        source_bone.keyframe_insert(data_path='rotation_quaternion', frame=i, options={'INSERTKEY_VISUAL'})
        
def transfer_movement(context: bpy.types.Context, animation, animation_index: int, ob: bpy.types.Object, source_bone_name: str, root_bone_name: str, root_rest_matrix: Matrix, root_matrix: Matrix, custom_settings: dict = {}):
    context.scene.nwo.active_animation_index = animation_index
    scene = context.scene
    horizontal = False
    vertical = False
    yaw = False
    full = False
    special_turn = False
    use_root_transform = root_matrix is not None
    if not custom_settings and not use_root_transform:
        movement = animation.animation_movement_data
        if animation.animation_type == 'world':
            full = True
        elif movement == "none":
            horizontal = True
            yaw = True
        else:
            horizontal = "xy" in movement
            vertical = "z" in movement
            yaw = "yaw" in movement
            full = movement == "full"
            
            # special turn
            final_token = animation.name.rpartition(" ")[2].lower()
            if yaw and turn_rots.get(final_token) is not None:
                special_turn = True
                yaw = False
    
    source_bone_matrices = []
    
    # Reach TURN
    # turn_left 6.66 -> 120
    # turn_left_slow 1.92 -> 86.7
    # turn_left_fast 12.1 -> 360
    # turn_right
    # turn_right_slow
    # turn_right_fast
    
    root_bone = ob.pose.bones[root_bone_name]
    root_bone: bpy.types.PoseBone
       
    con_rot = None
    con_loc = None
    con_limit_rot = None
    con_limit_loc = None
    
    # Add constraints if rotation
    if custom_settings:
        con_rot = root_bone.constraints.new(type='COPY_ROTATION')
        con_rot.target = ob
        con_rot.subtarget = source_bone_name
        con_rot.target_space = 'LOCAL_OWNER_ORIENT'
        con_rot.owner_space = 'LOCAL'
        
        con_loc = root_bone.constraints.new(type='COPY_LOCATION')
        con_loc.target = ob
        con_loc.subtarget = source_bone_name
        con_loc.target_space = 'LOCAL_OWNER_ORIENT'
        con_loc.owner_space = 'LOCAL'
        
        con_limit_rot = root_bone.constraints.new(type='LIMIT_ROTATION')
        con_limit_rot.use_limit_x = not custom_settings.get("use_x_rot")
        con_limit_rot.use_limit_y = not custom_settings.get("use_y_rot")
        con_limit_rot.use_limit_z = not custom_settings.get("use_z_rot")
        con_limit_rot.owner_space = 'LOCAL'
        
        con_limit_loc = root_bone.constraints.new(type='LIMIT_LOCATION')
        con_limit_loc.use_min_x = not custom_settings.get("use_x_loc")
        con_limit_loc.use_max_x = not custom_settings.get("use_x_loc")
        con_limit_loc.use_min_y = not custom_settings.get("use_y_loc")
        con_limit_loc.use_max_y = not custom_settings.get("use_y_loc")
        con_limit_loc.use_min_z = not custom_settings.get("use_z_loc")
        con_limit_loc.use_max_z = not custom_settings.get("use_z_loc")
        con_limit_loc.owner_space = 'LOCAL'  
    elif not use_root_transform:
        if yaw or full:
            con_rot = root_bone.constraints.new(type='COPY_ROTATION')
            con_rot.target = ob
            con_rot.subtarget = source_bone_name
            con_rot.target_space = 'LOCAL_OWNER_ORIENT'
            con_rot.owner_space = 'LOCAL'
            
            if not full:
                con_limit_rot = root_bone.constraints.new(type='LIMIT_ROTATION')
                con_limit_rot.use_limit_x = True
                con_limit_rot.use_limit_y = True
                con_limit_rot.owner_space = 'LOCAL'
        
        if horizontal or vertical or full:
            con_loc = root_bone.constraints.new(type='COPY_LOCATION')
            con_loc.target = ob
            con_loc.subtarget = source_bone_name
            con_loc.target_space = 'LOCAL_OWNER_ORIENT'
            con_loc.owner_space = 'LOCAL'
            
            if not (vertical or full):
                con_limit_loc = root_bone.constraints.new(type='LIMIT_LOCATION')
                con_limit_loc.use_min_z = True
                con_limit_loc.use_max_z = True
                con_limit_loc.owner_space = 'LOCAL'
    
    # Neutralise source movement and save offets
    # source_rest_loc = source_rest_matrix.to_translation()
    # Apply offsets to root
    if not custom_settings and not use_root_transform and special_turn:
        root_rest_rot = root_rest_matrix.to_euler()
        turn_start, turn_end = turn_rots.get(final_token)
        scene.frame_set(animation.frame_start)
        euler_rot = Euler((0, 0, math.radians(turn_start)))
        euler_rot.rotate(root_rest_rot)
        loc, _, sca = root_bone.matrix.decompose()
        root_bone.matrix = Matrix.LocRotScale(loc, euler_rot, sca)
        root_bone.keyframe_insert(data_path='rotation_quaternion', frame=animation.frame_start, options={'INSERTKEY_VISUAL'})
        scene.frame_set(animation.frame_end)
        euler_rot = Euler((0, 0, math.radians(turn_end)))
        euler_rot.rotate(root_rest_rot)
        loc, _, sca = root_bone.matrix.decompose()
        root_bone.matrix = Matrix.LocRotScale(loc, euler_rot, sca)
        root_bone.keyframe_insert(data_path='rotation_quaternion', frame=animation.frame_end, options={'INSERTKEY_VISUAL'})
            
        for i in range(animation.frame_start, animation.frame_end + 1):
            scene.frame_set(i)
            root_bone.keyframe_insert(data_path='rotation_quaternion', frame=i, options={'INSERTKEY_VISUAL'})
            
    elif use_root_transform:
        for i in range(animation.frame_start, animation.frame_end + 1):
            scene.frame_set(i)
            root_bone.matrix = root_matrix
            context.view_layer.update()
            root_bone.keyframe_insert(data_path='location', frame=i, options={'INSERTKEY_VISUAL'})
            root_bone.keyframe_insert(data_path='rotation_quaternion', frame=i, options={'INSERTKEY_VISUAL'})
            root_bone.keyframe_insert(data_path='scale', frame=i, options={'INSERTKEY_VISUAL'})
    elif custom_settings:
        for i in range(animation.frame_start, animation.frame_end + 1):
            scene.frame_set(i)
            root_bone.keyframe_insert(data_path='location', frame=i, options={'INSERTKEY_VISUAL'})
            root_bone.keyframe_insert(data_path='rotation_quaternion', frame=i, options={'INSERTKEY_VISUAL'})
    else:
        for i in range(animation.frame_start, animation.frame_end + 1):
            scene.frame_set(i)
            if horizontal or vertical or full:
                root_bone.keyframe_insert(data_path='location', frame=i, options={'INSERTKEY_VISUAL'})
            if yaw or full:
                root_bone.keyframe_insert(data_path='rotation_quaternion', frame=i, options={'INSERTKEY_VISUAL'})
                
    if con_loc is not None:
        root_bone.constraints.remove(con_loc)
        if con_limit_loc is not None:
            root_bone.constraints.remove(con_limit_loc)
    if con_rot is not None:
        root_bone.constraints.remove(con_rot)
        if con_limit_rot is not None:
            root_bone.constraints.remove(con_limit_rot)

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
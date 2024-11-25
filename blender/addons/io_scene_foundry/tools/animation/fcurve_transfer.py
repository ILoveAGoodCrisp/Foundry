

import bpy
from ... import utils
    
class FCurveTransfer:
    source_fcurve: bpy.types.FCurve
    target_fcurve: bpy.types.FCurve
    
    def __init__(self, action: bpy.types.Action, source_bone: str, target_bone: str, source_channel: str, target_channel: str) -> None:
        source_channel_array_index, source_channel_name = source_channel.split(':')
        target_channel_array_index, target_channel_name = target_channel.split(':')
        print(source_channel_array_index, target_channel_array_index)
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
            print(self.target_fcurve.array_index)
            
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

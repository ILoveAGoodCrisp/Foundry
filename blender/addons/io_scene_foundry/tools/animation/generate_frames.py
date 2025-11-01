"""Generates the final frame for import based and replacement animations, and the first frame of replacement animations"""

import bpy

from ... import utils

from ...props.scene import NWO_AnimationPropertiesGroup

movement_states = (
    "move",
    "jog",
    "run",
    "walk",
    "turn",
    "locomote",
)

need_final_frame = (
    "base",
    "replacement",
    "world",
)

class FrameGenerator:
    def __init__(self):
        self.animations = {anim: utils.AnimationName(anim.name) for anim in bpy.context.scene.nwo.animations if anim.export_this}
        
    def generate(self):
        for animation, name in self.animations.items():
            if animation.animation_type in need_final_frame:
                self._apply_final_frame(animation, name)
            if animation.animation_type == 'replacement':
                self._apply_first_frame()
        
    def _apply_final_frame(self, animation: NWO_AnimationPropertiesGroup, name: utils.AnimationName):
        if name.type == utils.AnimationStateType.TRANSITION:
            self._complete_transition(animation, name)
        
        elif any(name.state in s for s in movement_states):
            self._continue_root_movement(animation)
        else:
            self._complete_loop(animation)
            

    def _complete_loop(self, animation: NWO_AnimationPropertiesGroup):
        """Copies the first frame to the new final frame"""
        pass

    def _continue_root_movement(self, animation: NWO_AnimationPropertiesGroup):
        """Continues the movement of the root bone based on the delta between the 2nd last and last frame"""
        pass

    def _complete_transition(self, animation: NWO_AnimationPropertiesGroup, name: utils.AnimationName):
        """Finds the final frame from the first frame of the animation this transition leads to"""
        destination_animation = None
        for dest_anim, dest_name in self.animations.items():
            if name.destination_mode == dest_name.destination_mode and name.destination_state == dest_name.destination_state:
                destination_animation = dest_anim
                
        if destination_animation is None:
            return print(f"Found no destination animation for {animation.name}")
        
        
        
        

    def _apply_first_frame(self, animation: NWO_AnimationPropertiesGroup):
        pass
    


class NWO_OT_GenerateFrames(bpy.types.Operator):
    bl_idname = "nwo.generate_frames"
    bl_label = "My Class Name"
    bl_description = "Description that shows in blender tooltips"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        
        return {"FINISHED"}

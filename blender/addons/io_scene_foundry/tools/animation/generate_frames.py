"""Generates the final frame for import based and replacement animations, and the first frame of replacement animations"""

import bpy
from mathutils import Euler, Quaternion, Vector

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

soft_transition = (
    "juke",
    "enter",
    "exit",
    "ping",
    "open",
    "close",
    "brace",
    "jump",
    "land",
    "put_away",
    "ready",
    "ejection",
)

need_final_frame = (
    "base",
    "replacement",
    "world",
)

loopers = (
    "idle",
    "melee",
    "go_berserk",
    "evade",
    "airborne",
    "dive",
    "evade",
    "grip",
    "fire_",
    "point",
    "shakefist",
    "smash",
    "surprise",
    "taunt",
    "throw_grenade",
    "warn",
    "advance",
)

class FrameGenerator:
    def __init__(self):
        self.animations = {anim: utils.AnimationName(anim.name) for anim in bpy.context.scene.nwo.animations if anim.export_this}
        
        for k, v in self.animations.items():
            print(k.name, v)
        
    def generate(self):
        print("Generating Missing Frames for Base and Replacement animations")
        replacements = {}
        for animation, name in self.animations.items():
            if animation.animation_type in need_final_frame:
                self._apply_final_frame(animation, name)
            if animation.animation_type == 'replacement':
                replacements[animation] = name
                
        for animation, name in replacements.items():
            self._apply_first_frame(animation, name)
        
    def _apply_final_frame(self, animation: NWO_AnimationPropertiesGroup, name: utils.AnimationName):
        if name.type == utils.AnimationStateType.TRANSITION:
            self._complete_transition(animation, name)
        elif any(s in name.state for s in soft_transition):
            self._complete_soft_transition(animation, name)
        else:
            looper = name.state.startswith(loopers)
            movement = name.state.startswith(movement_states)
            if looper or movement:
                self._copy_frame(animation, ignore_root=True, assume_movement=movement)
    
    def _copy_frame(self, target_animation: NWO_AnimationPropertiesGroup, source_animation: NWO_AnimationPropertiesGroup = None, target_frame=None, source_frame=None, ignore_root=False, assume_movement=False, shift_frames_by_one=False):
        
        if assume_movement:
            ignore_root = True
        
        target_fcurves, target_fcurves_no_root, target_fcurves_root_only = self._get_animation_fcurves(target_animation, ignore_root)
        if source_animation is None:
            source_fcurves = target_fcurves
            source_fcurves_no_root = target_fcurves_no_root
        else:
            source_fcurves, source_fcurves_no_root, source_fcurves_root_only = self._get_animation_fcurves(source_animation, ignore_root)
            
        if not source_fcurves:
            return
        
        target_animation.frame_end += 1
        
        if target_frame is None:
            target_frame = target_animation.frame_end
        
        if source_frame is None:
            if source_animation is None:
                source_frame = target_animation.frame_start
            else:
                source_frame = source_animation.frame_start
        
        if source_animation is None:
            source_animation = target_animation
            
        if shift_frames_by_one:
            for fcurve in target_fcurves.values():
                for kp in fcurve.keyframe_points:
                    kp.co.x += 1
        
        if ignore_root:
            for key, source_fc in source_fcurves_no_root.items():
                first_key = next((kp for kp in source_fc.keyframe_points if int(kp.co.x) == source_frame), None)
                if not first_key:
                    continue

                target_fcurves[key].keyframe_points.insert(target_frame, first_key.co.y, options={'FAST'})
        else:
            for key, source_fc in source_fcurves.items():
                first_key = next((kp for kp in source_fc.keyframe_points if int(kp.co.x) == source_frame), None)
                if not first_key:
                    continue

                target_fcurves[key].keyframe_points.insert(target_frame, first_key.co.y, options={'FAST'})
            
        if assume_movement:
            
            third_last_frame = target_frame - 2
            second_last_frame = target_frame - 1
            
            third_last = {(utils.dot_partition(fc.data_path, True), fc.array_index): kp.co.y for fc in target_fcurves_root_only.values() for kp in fc.keyframe_points if int(kp.co.x) == third_last_frame}
            second_last = {(utils.dot_partition(fc.data_path, True), fc.array_index): kp.co.y for fc in target_fcurves_root_only.values() for kp in fc.keyframe_points if int(kp.co.x) == second_last_frame}
            
            if not third_last or not second_last:
                return print(f"--- Added final frame for [{target_animation.name}] from first frame of [{source_animation.name}]")
            
            transforms_1 = {
                "location": [0.0, 0.0, 0.0],
                "rotation_euler": [0.0, 0.0, 0.0],
                "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            }
            transforms_2 = {
                "location": [0.0, 0.0, 0.0],
                "rotation_euler": [0.0, 0.0, 0.0],
                "rotation_quaternion": [1.0, 0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            }

            for (transform, index), value in third_last.items():
                if transform in transforms_1 and index < len(transforms_1[transform]):
                    transforms_1[transform][index] = value

            for (transform, index), value in second_last.items():
                if transform in transforms_2 and index < len(transforms_2[transform]):
                    transforms_2[transform][index] = value
            
            last = {}
            
            for i in range(3):
                last["location", i] = transforms_2["location"][i] + (transforms_2["location"][i] - transforms_1["location"][i])
                last["scale", i] = transforms_2["scale"][i] + (transforms_2["scale"][i] - transforms_1["scale"][i])

            e1 = Euler(transforms_1["rotation_euler"])
            e2 = Euler(transforms_2["rotation_euler"])
            delta = Euler((e2.x - e1.x, e2.y - e1.y, e2.z - e1.z), e2.order)
            next_euler = Euler((e2.x + delta.x, e2.y + delta.y, e2.z + delta.z), e2.order)
            next_euler.make_compatible(e2)
            for i, v in enumerate(next_euler):
                last["rotation_euler", i] = v

            q1 = Quaternion(transforms_1["rotation_quaternion"])
            q2 = Quaternion(transforms_2["rotation_quaternion"])
            delta_q = q2 @ q1.inverted()
            q3 = delta_q @ q2
            q3.normalize()
            for i, v in enumerate(q3):
                last["rotation_quaternion", i] = v
                    
            
            for fcurve in target_fcurves_root_only.values():
                if fcurve.data_path.endswith(".location"):
                    loc = last.get(("location", fcurve.array_index))
                    if loc is not None:
                        fcurve.keyframe_points.insert(target_frame, loc, options={'FAST'})
                elif fcurve.data_path.endswith(".rotation_quaternion"):
                    rot_q = last.get(("rotation_quaternion", fcurve.array_index))
                    if rot_q is not None:
                        fcurve.keyframe_points.insert(target_frame, rot_q, options={'FAST'})
                elif fcurve.data_path.endswith(".rotation_euler"):
                    rot_e = last.get(("rotation_euler", fcurve.array_index))
                    if rot_e is not None:
                        fcurve.keyframe_points.insert(target_frame, rot_e, options={'FAST'})
                elif fcurve.data_path.endswith(".scale"):
                    scale = last.get(("scale", fcurve.array_index))
                    if scale is not None:
                        fcurve.keyframe_points.insert(target_frame, scale, options={'FAST'})

                
            print(f"--- Generated new root bone frame for [{target_animation.name}]")
            
        print(f"--- Added final frame for [{target_animation.name}] from first frame of [{source_animation.name}]")

    def _complete_transition(self, animation: NWO_AnimationPropertiesGroup, name: utils.AnimationName):
        """Finds the final frame from the first frame of the animation this transition leads to"""
        destination_animation = None
        dest_name = name.copy()
        dest_name.mode = name.destination_mode
        dest_name.state = name.destination_state
        destination_animation = self._seek_best_matching_animation(animation, dest_name)
                
        if destination_animation is None:
            return utils.print_warning(f"Found no destination animation for {animation.name}")
        
        self._copy_frame(animation, destination_animation, ignore_root=True, assume_movement=dest_name.state.startswith(movement_states))
        
    def _seek_best_matching_animation(self, animation: NWO_AnimationPropertiesGroup, name: utils.AnimationName):
        animations = {}
        for next_animation, next_name in self.animations.items():
            if next_animation == animation:
                continue
            if next_name.state != name.state:
                continue
            if next_name.type != utils.AnimationStateType.ACTION:
                continue
            matches = 0
            matches += (int(name.mode == next_name.mode) * 1000)
            matches += (int(name.weapon_class == next_name.weapon_class) * 100)
            matches += (int(name.weapon_type == next_name.weapon_type) * 10)
            matches += int(name.set == next_name.set)
            animations[next_animation] = matches
        
        if not animations:
            return
        
        priority_animations = sorted(animations, key=animations.get, reverse=True)
        
        return priority_animations[0]
        
    def _complete_soft_transition(self, animation: NWO_AnimationPropertiesGroup, name: utils.AnimationName):
        """For built in transition animations like vehicle enters and exits"""
        next_animation = None
        ignore_root = False
        assume_movement = False
        
        if name.mode == "bunker":
            if name.state == "open": # to bunker open idle from closed
                idle_name = name.copy()
                idle_name.state = "idle"
                if name.set.endswith("_closed"):
                    idle_name.set = name.set.replace("_closed", "_open")
                    next_animation = self._seek_best_matching_animation(animation, idle_name)
                    
            elif name.state == "close": # to bunker closed idle from open
                idle_name = name.copy()
                idle_name.state = "idle"
                if name.set.endswith("_open"):
                    idle_name.set = name.set.replace("_open", "_closed")
                    next_animation = self._seek_best_matching_animation(animation, idle_name)
                    
            elif name.state == "enter": # entering either a closed or open bunker
                idle_name = name.copy()
                idle_name.state = "idle"
                next_animation = self._seek_best_matching_animation(animation, idle_name)
                
            elif name.state == "exit": # exiting either a closed or open bunker to a mode idle
                idle_name = name.copy()
                idle_name.state = "idle"
                idle_name.mode = "combat"
                next_animation = self._seek_best_matching_animation(animation, idle_name)
        
        elif name.state.startswith("juke_anticipation_"): # anticipation is going from moving to the first frame of juke
            juke_name = name.copy()
            juke_name.state = name.state.replace("_anticipation", "")
            next_animation = self._seek_best_matching_animation(animation, juke_name)
            assume_movement = True
                
        elif name.state.startswith("juke_"): # from anticipation to move
            assume_movement = True
            juke_direction = name.state.replace("juke_", "")
            juke_name = name.copy()
            juke_name.state = f"locomote_run_{juke_direction}"
            next_animation = self._seek_best_matching_animation(animation, juke_name)
            if next_animation is None:
                juke_name.state = f"move_{juke_direction}"
                next_animation = self._seek_best_matching_animation(animation, juke_name)
                
        elif name.state.endswith("_ping"): # ping animation that returns to the mode idle
            idle_name = name.copy()
            idle_name.state = "idle"
            next_animation = self._seek_best_matching_animation(animation, idle_name)
        
        elif "enter" in name.state: # mode/state enter from combat idle 
            idle_name = name.copy()
            idle_name.state = "idle"
            next_animation = self._seek_best_matching_animation(animation, idle_name)
            if next_animation is None:
                if "_b_" in idle_name.mode:
                    boarding_name = idle_name.copy()
                    boarding_name.mode = idle_name.mode.replace("_b_", "_")
                    next_animation = self._seek_best_matching_animation(animation, boarding_name)
                    
        elif "ejection" in name.state: # vehicle ejection
            next_animation = animation
            assume_movement = True
                
        elif "exit" in name.state: # mode/state exit to idle
            if name.mode.endswith(("_b", "_d", "_p")):
                next_animation = animation # vehicles don't seem to exit to a particular animation
            else:
                idle_name = name.copy()
                idle_name.state = "idle"
                next_animation = self._seek_best_matching_animation(animation, idle_name)
            assume_movement = True
            
        elif "put_away" in name.state: # weapon put away to idle
            ready_name = name.copy()
            ready_name.state = "ready"
            next_animation = self._seek_best_matching_animation(animation, ready_name)
            ignore_root = True
            
        elif "ready" in name.state: # weapon ready to idle
            put_away_name = name.copy()
            put_away_name.state = "put_away"
            next_animation = self._seek_best_matching_animation(animation, put_away_name)
            ignore_root = True
            
        else: # Generic to idle
            idle_name = name.copy()
            idle_name.state = "idle"
            next_animation = self._seek_best_matching_animation(animation, idle_name)
            ignore_root = True
                
                
        if next_animation is not None:
            self._copy_frame(animation, next_animation, ignore_root=ignore_root, assume_movement=assume_movement)

    def _apply_first_frame(self, animation: NWO_AnimationPropertiesGroup, name: utils.AnimationName):
        idle_name = name.copy()
        idle_name.state = "idle"
        next_animation = self._seek_best_matching_animation(animation, idle_name)
        if next_animation is not None:
            self._copy_frame(animation, next_animation, target_frame=animation.frame_start, source_frame=next_animation.frame_start, shift_frames_by_one=True)
        
    
    def _get_animation_fcurves(self, animation: NWO_AnimationPropertiesGroup, ignore_root=False):
        fcurves = {}
        fcurves_no_root = {}
        fcurves_root_only = {}
        root_bone_name = ""
        for track in animation.action_tracks:
            action = track.action
            ob = track.object
            if action is None or ob is None:
                continue
            if ignore_root and ob.type == 'ARMATURE':
                root_bone = next((b for b in ob.data.bones if b.use_deform and b.parent is None), None)
                if root_bone is not None:
                    root_bone_name = root_bone.name

            fcurves = {(fc.data_path, fc.array_index): fc for fc in utils.get_fcurves(action, ob)}
            if ignore_root:
                fcurves_no_root = {k: v for k, v in fcurves.items() if not f'["{root_bone_name}"]' in k[0]}
                fcurves_root_only = {k: v for k, v in fcurves.items() if f'["{root_bone_name}"]' in k[0]}
            
        return fcurves, fcurves_no_root, fcurves_root_only
    


class NWO_OT_GenerateFrames(bpy.types.Operator):
    bl_idname = "nwo.generate_frames"
    bl_label = "Generation Animation Frames"
    bl_description = "Generates frames where possible for tag imported animations. This is needed because base and replacement animations are missing a final frame which would have been present in their source file"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.scene.nwo.animations

    def execute(self, context):
        generator = FrameGenerator()
        generator.generate()
        return {"FINISHED"}

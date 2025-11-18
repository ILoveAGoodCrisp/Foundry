

from collections import defaultdict
from enum import Enum
from math import radians
from pathlib import Path
from typing import cast
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from ..managed_blam.frame_event_list import AnimationEvent, DialogueEvent, EffectEvent, FrameEventListTag, Reference, SoundEvent

from .Tags import TagFieldBlock, TagFieldBlockElement, TagFieldElement

from ..managed_blam.render_model import RenderModelTag
from ..managed_blam import Tag
from ..legacy.jma import Node
from .. import utils

tolerance = 1e-6

damage_states = "h_ping", "s_ping", "h_kill", "s_kill"
directions = "front", "left", "right", "back"
regions = "gut", "chest", "head", "l_arm", "l_hand", "l_leg", "l_foot", "r_arm", "r_hand", "r_leg", "r_foot"

class AnimationType(Enum):
    none = 0
    base = 1
    overlay = 2
    replacement = 3
    
class FrameInfoType(Enum):
    none = 0
    dx_dy = 1
    dx_dy_dyaw = 2
    dx_dy_dz_dyaw = 3
    dx_dy_dz_dangle_axis = 4
    
class Compression(Enum):
    medium_compression = 0
    rough_compression = 1
    uncompressed = 2
    old_codec = 3

class Animation:
    def __init__(self):
        self.name = ""
        self.index = -1
        self.parent_animation: Animation = None
        self.next_animation: Animation = None
        self.frame_count = 0
        self.animation_type = AnimationType.none
        self.frame_info_type = FrameInfoType.none
        self.compression = Compression.medium_compression
        self.resource_group = -1
        self.resource_group_member = -1
        self.element: TagFieldBlockElement = None
        self.state_types = set()
        
    def from_element(self, element: TagFieldBlockElement):
        self.name = element.Fields[0].GetStringData()
        self.index = element.ElementIndex
        self.frame_count = element.SelectField("Block:shared animation data[0]/ShortInteger:frame count").Data
        
    def __repr__(self):
        return self.name
        

class AnimationTag(Tag):
    tag_ext = 'model_animation_graph'

    def _read_fields(self):
        self.block_animations = self.tag.SelectField("Struct:definitions[0]/Block:animations")
        self.block_skeleton_nodes = self.tag.SelectField("definitions[0]/Block:skeleton nodes")
        self.block_node_usages = self.tag.SelectField("definitions[0]/Block:node usage")
        self.block_modes = self.tag.SelectField("Struct:content[0]/Block:modes")
        self.block_ik_chains = self.tag.SelectField('Struct:definitions[0]/Block:ik chains')
        self.block_blend_screens = self.tag.SelectField('Struct:definitions[0]/Block:NEW blend screens')
        self.block_additional_node_dat = self.tag.SelectField("Block:additional node data")
        self.block_sound_references = self.tag.SelectField("Struct:definitions[0]/Block:sound references")
        self.block_effect_references = self.tag.SelectField("Struct:definitions[0]/Block:effect references")
        
    def get_frame_event_list(self) -> str:
        '''Returns the animation graph's frame event list filepath'''
        file = self.tag.SelectField("Struct:definitions[0]/Reference:imported events").Path
        if not file:
            return ""
        
        return file.Filename
        
        
    def get_animation_names(self, filter="") -> list[str]:
        """Returns a list of all animation names"""
        if filter:
            return [element.Fields[0].GetStringData() for element in self.block_animations.Elements if filter in element.Fields[0].GetStringData()]
        else:
            return [element.Fields[0].GetStringData() for element in self.block_animations.Elements]
        
    def get_animations(self, filter="") -> list[str]:
        """Returns a list of all animation"""
        def make_animation(element):
            anim = Animation()
            anim.from_element(element)
            return anim
        
        if filter:
            return [make_animation(element) for element in self.block_animations.Elements if filter in element.Fields[0].GetStringData()]
        else:
            return [make_animation(element) for element in self.block_animations.Elements]
        
    def _initialize_tag(self):
        self.tag.SelectField('Struct:definitions[0]/ShortInteger:animation codec pack').Data = 6
        
    def _node_index_list(self, bones):
        # Have to set up the skeleton nodes block. If we end up with any node usages that point to non-existant nodes, the importer will crash
        node_index_list = [b for b in bones.keys()]
        if self._needs_skeleton_update(node_index_list):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in node_index_list:
                new_node = self.block_skeleton_nodes.AddElement()
                new_node.SelectField('name').SetStringData(n)
                
        return node_index_list
    
    def _node_index_list_granny(self, bones):
        # Have to set up the skeleton nodes block. If we end up with any node usages that point to non-existant nodes, the importer will crash
        node_index_list = [b.name for b in bones]
        if self._needs_skeleton_update(node_index_list):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in node_index_list:
                new_node = self.block_skeleton_nodes.AddElement()
                new_node.SelectField('name').SetStringData(n)
                
        return node_index_list
                
    def _needs_skeleton_update(self, node_index_list):
        graph_nodes = [e.SelectField('name').GetStringData() for e in self.block_skeleton_nodes.Elements]
        return set(node_index_list) != set(graph_nodes)
    
    def _node_index_dict(self):
        return {element.Fields[0].Data: element.ElementIndex for element in self.block_skeleton_nodes.Elements}
    
    def set_node_usages(self, bones, granny: bool = False):
        def _node_usage_dict(nwo):
            node_usage_dict = defaultdict(list)
            if nwo.node_usage_pedestal:
                node_usage_dict[nwo.node_usage_pedestal].append("pedestal")
            if nwo.node_usage_physics_control:
                node_usage_dict[nwo.node_usage_physics_control].append("physics control")
            if nwo.node_usage_camera_control:
                node_usage_dict[nwo.node_usage_camera_control].append("camera control")
            if nwo.node_usage_origin_marker:
                node_usage_dict[nwo.node_usage_origin_marker].append("origin marker")
            if nwo.node_usage_left_clavicle:
                node_usage_dict[nwo.node_usage_left_clavicle].append("left clavicle")
            if nwo.node_usage_left_upperarm:
                node_usage_dict[nwo.node_usage_left_upperarm].append("left upperarm")
            if nwo.node_usage_pose_blend_pitch:
                node_usage_dict[nwo.node_usage_pose_blend_pitch].append("pose blend pitch")
            if nwo.node_usage_pose_blend_yaw:
                node_usage_dict[nwo.node_usage_pose_blend_yaw].append("pose blend yaw")
            if nwo.node_usage_pelvis:
                node_usage_dict[nwo.node_usage_pelvis].append("pelvis")
            if nwo.node_usage_left_foot:
                node_usage_dict[nwo.node_usage_left_foot].append("left foot")
            if nwo.node_usage_right_foot:
                node_usage_dict[nwo.node_usage_right_foot].append("right foot")
            if nwo.node_usage_damage_root_gut:
                node_usage_dict[nwo.node_usage_damage_root_gut].append("damage root gut")
            if nwo.node_usage_damage_root_chest:
                node_usage_dict[nwo.node_usage_damage_root_chest].append("damage root chest")
            if nwo.node_usage_damage_root_head:
                node_usage_dict[nwo.node_usage_damage_root_head].append("damage root head")
            if nwo.node_usage_damage_root_left_shoulder:
                node_usage_dict[nwo.node_usage_damage_root_left_shoulder].append("damage root left shoulder")
            if nwo.node_usage_damage_root_left_arm:
                node_usage_dict[nwo.node_usage_damage_root_left_arm].append("damage root left arm")
            if nwo.node_usage_damage_root_left_leg:
                node_usage_dict[nwo.node_usage_damage_root_left_leg].append("damage root left leg")
            if nwo.node_usage_damage_root_left_foot:
                node_usage_dict[nwo.node_usage_damage_root_left_foot].append("damage root left foot")
            if nwo.node_usage_damage_root_right_shoulder:
                node_usage_dict[nwo.node_usage_damage_root_right_shoulder].append("damage root right shoulder")
            if nwo.node_usage_damage_root_right_arm:
                node_usage_dict[nwo.node_usage_damage_root_right_arm].append("damage root right arm")
            if nwo.node_usage_damage_root_right_leg:
                node_usage_dict[nwo.node_usage_damage_root_right_leg].append("damage root right leg")
            if nwo.node_usage_damage_root_right_foot:
                node_usage_dict[nwo.node_usage_damage_root_right_foot].append("damage root right foot")
            if self.corinth:
                if nwo.node_usage_left_hand:
                    node_usage_dict[nwo.node_usage_left_hand].append("left hand")
                if nwo.node_usage_right_hand:
                    node_usage_dict[nwo.node_usage_right_hand].append("right hand")
                if nwo.node_usage_weapon_ik:
                    node_usage_dict[nwo.node_usage_weapon_ik].append("weapon ik")

            return node_usage_dict
        
        if self.block_skeleton_nodes.Elements.Count != len(bones):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in [b.name for b in bones]:
                self.block_skeleton_nodes.AddElement().Fields[0].SetStringData(n)
                
        node_usage_dict = _node_usage_dict(self.context.scene.nwo)
        skeleton_nodes = self._node_index_dict()
        self.block_node_usages.RemoveAllElements()
        node_targets = [n for n in skeleton_nodes.keys() if n in node_usage_dict.keys()]
        for node in node_targets:
            usages = node_usage_dict[node]
            for usage in usages:
                new_element = self.block_node_usages.AddElement()
                usage_field = new_element.SelectField("usage")
                node_field = new_element.SelectField("node to use")
                items = [i.EnumName for i in usage_field.Items]
                usage_field.Value = items.index(usage)
                node_field.Value = skeleton_nodes[node]
        if node_targets:
            self.tag_has_changes = True
    
    def set_world_animations(self, world_animations):
        """Sets the given animations to world animations"""
        target_elements = [e for e in self.block_animations.Elements if e.SelectField('name').GetStringData() in world_animations]
        for e in target_elements:
            flags = e.SelectField('shared animation data[0]/internal flags')
            flags.SetBit('world relative', True)
        if target_elements:
            self.tag_has_changes = True
            
    def get_nodes(self):
        return [e.SelectField('name').GetStringData() for e in self.block_skeleton_nodes.Elements]
    
    def read_all_modes(self):
        print(self.tag.Path.RelativePath)
        print('-'*100)
        for e in self.block_modes.Elements:
            print(e.SelectField('label').GetStringData())
        print('\n\n\n')
        
    def write_ik_chains(self, ik_chains: list, bones: list, granny: bool = False):
        
        if self.block_skeleton_nodes.Elements.Count != len(bones):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in [b.name for b in bones]:
                self.block_skeleton_nodes.AddElement().Fields[0].SetStringData(n)
        
        skeleton_nodes = self._node_index_dict()
        valid_ik_chains = [chain for chain in ik_chains if chain.start_node in skeleton_nodes and chain.effector_node in skeleton_nodes]
        
        if self.block_ik_chains.Elements.Count:
            self.block_ik_chains.RemoveAllElements()
    
        for chain in valid_ik_chains:
            element = self.block_ik_chains.AddElement()
            element.SelectField('name').SetStringData(chain.name)
            element.SelectField('start node').Value = skeleton_nodes[chain.start_node]
            element.SelectField('effector node').Value = skeleton_nodes[chain.effector_node]
            
        self.tag_has_changes = True
        
    def validate_compression(self, animations, default_compression: str):
        # medium = 0
        # rough = 1
        # uncompressed = 2
        game_animations = {animation.name.replace(' ', ':'): animation.compression for animation in animations}
        
        for element in self.block_animations.Elements:
            name = element.Fields[0].GetStringData()
            if element.Fields[0].GetStringData() not in game_animations.keys() or not element.SelectField("shared animation data").Elements.Count:
                continue
            compression = game_animations.get(name)
            if compression == 'Default':
                continue
            compression_enum = 0 # medium
            match compression:
                case "Rough":
                    compression_enum = 1
                case "Uncompressed":
                    compression_enum = 2
                    
            compression_field = element.SelectField("Block:shared animation data[0]/CharEnum:desired compression")
            if compression_field.Value != compression_enum:
                compression_field.Value = compression_enum
                self.tag_has_changes = True
                
    def set_parent_graph(self, parent_graph_path):
        parent_field = self.tag.SelectField("Struct:definitions[0]/Reference:parent animation graph")
        if not parent_graph_path and parent_field.Path:
            parent_field.Path = None
            self.tag_has_changes = True
            return
        parent_path = str(Path(utils.relative_path(parent_graph_path)).with_suffix(".model_animation_graph"))
        full_path = Path(self.tags_dir, parent_path)
        if not full_path.exists():
            print(f"Parent graph does not exist: {full_path}")
        new_tag_path = self._TagPath_from_string(parent_path)
        if parent_field.Path != new_tag_path:
            parent_field.Path = self._TagPath_from_string(parent_path)
            self.tag_has_changes = True
        
    def get_parent_graph(self):
        path = self.tag.SelectField("Struct:definitions[0]/Reference:parent animation graph").Path
        if path:
            return path.RelativePathWithExtension
        
    def _get_animation_name_from_index(self, index):
        if index > self.block_animations.Elements.Count - 1:
            return ""
        element = self.block_animations.Elements[index]
        return element.SelectField("name").GetStringData()
    
    def _get_animation_index_from_name(self, name):
        for element in self.block_animations.Elements:
            if element.SelectField("name").GetStringData() == name:
                return element.ElementIndex
        
        return -1
        
    def setup_blend_screens(self, animation_names: set):
        sorted_animations  = sorted(animation_names)
        blend_screens_to_remove = []
        tag_animation_names = [name.replace(" ", ":") for name in sorted_animations]
        for element in self.block_blend_screens.Elements:
            index = element.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value
            if index > -1:
                animation_name = self._get_animation_name_from_index(index)
                if animation_name and animation_name in tag_animation_names:
                    tag_animation_names.remove(animation_name)
            else:
                blend_screens_to_remove.append(element.ElementIndex)
        
        for screen_index in reversed(blend_screens_to_remove):
            self.block_blend_screens.RemoveElement(screen_index)
            self.tag_has_changes = True
        
        for name in tag_animation_names:
            animation_index = self._get_animation_index_from_name(name)
            if animation_index > -1:
                element = self.block_blend_screens.AddElement()
                element.SelectField("name").SetStringData(name)
                element.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value = animation_index
                state = name.split(":")[-1]
                yaw_source_value = "none"
                pitch_source_value = "none"
                weight_source_value = "none"
                interpolation_rate = "0"
                flag_weapon_down = False
                flag_blending = False
                flag_parent_adjust = False
                if "aim" in state:
                    yaw_source_value = "aim yaw"
                    pitch_source_value = "aim pitch"
                elif "look" in state:
                    yaw_source_value = "look yaw"
                    pitch_source_value = "look pitch"
                    flag_parent_adjust = True
                elif "steer" in state:
                    yaw_source_value = "steering"
                    pitch_source_value = "steering"
                elif "acc" in state:
                    yaw_source_value = "acceleration yaw"
                    pitch_source_value = "acceleration pitch"
                    weight_source_value = "acceleration magnitude"
                    interpolation_rate = "0.333"
                elif "pitch" in state and "turn" in state:
                    yaw_source_value = "first person turn"
                    pitch_source_value = "first person pitch"
                elif "defense" in state:
                    yaw_source_value = "defense yaw"
                    pitch_source_value = "defense pitch"
                    weight_source_value = "defense"
                    interpolation_rate = "0.25"
                    
                if state.endswith("_down"):
                    flag_weapon_down = True
                elif state == "aiming":
                    flag_blending = True
                    
                element.SelectField("yaw source").SetValue(yaw_source_value)
                element.SelectField("pitch source").SetValue(pitch_source_value)
                element.SelectField("weight source").SetValue(weight_source_value)
                element.SelectField("interpolation rate").SetStringData(interpolation_rate)
                
                flags = element.SelectField("flags")
                
                if flag_weapon_down:
                    flags.SetBit("active only when weapon down", True)
                    
                if flag_blending:
                    flags.SetBit("attempt piece-wise blending", True)
                
                if flag_parent_adjust:
                    flags.SetBit("allow parent adjustment", True)
                
                self.tag_has_changes = True
                
    def to_blender(self, render_model: str, armature, filter: str):
        # Prepare exporter
        print()
        # print(self.resource_info())
        actions = []
        bone_base_matrices = {}
        for bone in armature.pose.bones:
            if bone.parent:
                bone_base_matrices[bone] = bone.parent.matrix.inverted_safe() @ bone.matrix
            else:
                bone_base_matrices[bone] = bone.matrix
        if self.block_animations.Elements.Count < 1: 
            return print("No animations found in graph")
        
        graph = self.to_dict()
        
        animation_nodes = None
        with RenderModelTag(path=render_model) as model:
            exporter = self._AnimationExporter()
            # exporter.LoadTags(self.tag_path, model.tag_path)
            ready = exporter.UseTags(self.tag, model.tag)
            if not ready:
                return print(f"Failed to use tags: {self.tag_path.RelativePath} & {render_model.tag_path.RelativePath}")
            
            nodes_count = exporter.GetGraphNodeCount()
            import clr
            clr.AddReference('System')
            from System import Array # type: ignore
            animation_nodes = [self._GameAnimationNode() for _ in range(nodes_count)]
            animation_nodes = Array[self._GameAnimationNodeType()](animation_nodes)
            
            if armature.animation_data is None:
                armature.animation_data_create()
                
            all_animations = self.get_animation_names()
            all_animations = {n: idx for idx, n in enumerate(all_animations)}
            
            for element in self.block_animations.Elements:
                name = element.SelectField("name").GetStringData()
                if filter and filter not in name:
                    continue
                index = element.ElementIndex
                shared_data = element.SelectField("Block:shared animation data")
                anim_type = shared_data.Elements[0].SelectField("animation type").Value
                frame_info = shared_data.Elements[0].SelectField("frame info type").Value
                overlay = anim_type == 2
                if overlay:
                    utils.print_warning(f"{name} is an overlay, rotations will not be imported")
                    # continue
                elif anim_type == 1 and frame_info > 0: # base and has movement
                    utils.print_warning(f"{name} has movement data that won't be imported")
                    # continue
                frame_count = exporter.GetAnimationFrameCount(index)
                new_name = name.replace(":", " ")
                action = bpy.data.actions.new(new_name)
                slot = action.slots.new('OBJECT', armature.name)
                armature.animation_data.last_slot_identifier = slot.identifier
                armature.animation_data.action = action
                print(f"--- {action.name}")
                animation = self.context.scene.nwo.animations.add()
                animation.name = new_name
                # action.use_fake_user = True
                action.use_frame_range = True
                animation.frame_start = 1
                animation.frame_end = frame_count
                
                if self.corinth and element.SelectField("ShortBlockIndex:composite").Value > -1:
                    animation.animation_type = 'composite'
                    self._import_composite(animation, element.SelectField("ShortBlockIndex:composite").Value)
                    continue
                
                match anim_type:
                    case 0 | 1:
                        if shared_data.Elements[0].SelectField("internal flags").TestBit("world relative"):
                            animation.animation_type = 'world'
                        else:
                            animation.animation_type = 'base'
                        match shared_data.Elements[0].SelectField("frame info type").Value:
                            case 0:
                                animation.animation_movement_data = 'none'
                            case 1:
                                animation.animation_movement_data = 'xy'
                            case 2:
                                animation.animation_movement_data = 'xyyaw'
                            case 3:
                                animation.animation_movement_data = 'xyzyaw'
                            case 4:
                                animation.animation_movement_data = 'full'
                    case 2:
                        animation.animation_type = 'overlay'
                    case 3:
                        animation.animation_type = 'replacement'

                track = animation.action_tracks.add()
                track.object = armature
                track.action = action
                if exporter.GetRenderModelBasePose(animation_nodes, nodes_count):
                    nodes = [Node(n.Name, n.ParentIndex) for n in animation_nodes]
                    for node in nodes:
                        if node.parent_index > -1:
                            node.parent = nodes[node.parent_index]
                            
                    node_base_matrices = {}
                    self._get_base_pose(animation_nodes, nodes, node_base_matrices)
                    transforms = {}
                    base_transforms = {}
                    nodes_with_animations = set()
                    for frame in range(frame_count):
                        if exporter.GetAnimationFrame(index, frame, animation_nodes, nodes_count):
                            nodes_with_animations.update(self._add_transforms(animation_nodes, nodes, frame + 1, overlay, node_base_matrices, transforms))
                       
                    if anim_type == 3: # replacement
                        tokens = name.split(":")
                        if tokens[-1].startswith("var"):
                            tokens.pop(-1)
                            
                        tokens[-1] = "idle"

                        replacement_base_animations = self.find_animation(graph, tokens, ["actions"])
                        if replacement_base_animations:
                            
                            for frame in range(frame_count):
                                if exporter.GetAnimationFrame(replacement_base_animations[0].index, frame, animation_nodes, nodes_count):
                                    self._add_base_transforms(animation_nodes, nodes, frame + 1, node_base_matrices, base_transforms)
                            
                    self._to_armature_action(transforms, armature, action, nodes, base_transforms, nodes_with_animations)
                    actions.append(action)
                    action.frame_end = frame_count
        
        return actions
    
    def _to_armature_action(self, transforms, armature: bpy.types.Object, action: bpy.types.Action, nodes: list[Node], base_transforms: dict, nodes_with_animations):
        fcurves = utils.get_fcurves(action, armature.animation_data.last_slot_identifier)
        fcurves.clear()
        
        armature_bone_names = {utils.remove_node_prefix(bone.name): bone for bone in armature.pose.bones}
        valid_nodes = []
        
        for node in nodes:
            node.pose_bone = armature_bone_names.get(utils.remove_node_prefix(node.name))
            if node.pose_bone is None:
                continue
            node.fc_loc_x = fcurves.new(data_path=f'pose.bones["{node.name}"].location', index=0)
            node.fc_loc_y = fcurves.new(data_path=f'pose.bones["{node.name}"].location', index=1)
            node.fc_loc_z = fcurves.new(data_path=f'pose.bones["{node.name}"].location', index=2)
            node.fc_rot_w = fcurves.new(data_path=f'pose.bones["{node.name}"].rotation_quaternion', index=0)
            node.fc_rot_x = fcurves.new(data_path=f'pose.bones["{node.name}"].rotation_quaternion', index=1)
            node.fc_rot_y = fcurves.new(data_path=f'pose.bones["{node.name}"].rotation_quaternion', index=2)
            node.fc_rot_z = fcurves.new(data_path=f'pose.bones["{node.name}"].rotation_quaternion', index=3)
            node.fc_sca_x = fcurves.new(data_path=f'pose.bones["{node.name}"].scale', index=0)
            node.fc_sca_y = fcurves.new(data_path=f'pose.bones["{node.name}"].scale', index=1)
            node.fc_sca_z = fcurves.new(data_path=f'pose.bones["{node.name}"].scale', index=2)
            valid_nodes.append(node)
            
        bone_dict = {}
        bones_ordered = [node.pose_bone for node in valid_nodes]
        for bone in bones_ordered:
            if bone.parent:
                bone_dict[bone] = bone_dict[bone.parent] + 1
            else:
                bone_dict[bone] = 0
                
        bones_ordered.sort(key=lambda x: bone_dict[x])
        
        bone_base_matrices = {}
        for bone in bones_ordered:
            if bone.parent:
                bone_base_matrices[bone] = bone.parent.matrix.inverted_safe() @ bone.matrix
            else:
                bone_base_matrices[bone] = bone.matrix
        
        base_repeats = 0
        
        for frame_idx, nodes_transforms in transforms.items():
            for node in valid_nodes:
                bind_inv = bone_base_matrices[node.pose_bone].inverted_safe()
                repl_matrix = nodes_transforms[node]
                transform_matrix = bind_inv @ repl_matrix
                base_matrix = Matrix.Identity(4)
                if base_transforms:
                    base_frame_idx = frame_idx - (len(base_transforms) * base_repeats)
                    if base_frame_idx > len(base_transforms):
                        base_repeats += 1
                        base_frame_idx = frame_idx - (len(base_transforms) * base_repeats)
                    base_nodes_transforms = base_transforms[base_frame_idx]
                    if base_nodes_transforms is not None:
                        if node not in nodes_with_animations:
                            base_matrix = base_nodes_transforms[node]
                            
                            delta_base = bind_inv @ base_matrix

                            transform_matrix = delta_base @ transform_matrix

                # decompose the orthogonal result
                loc, rot, sca = transform_matrix.decompose()

                node.fc_loc_x.keyframe_points.insert(frame_idx, loc.x, options={'FAST', 'NEEDED'})
                node.fc_loc_y.keyframe_points.insert(frame_idx, loc.y, options={'FAST', 'NEEDED'})
                node.fc_loc_z.keyframe_points.insert(frame_idx, loc.z, options={'FAST', 'NEEDED'})
                
                node.fc_rot_w.keyframe_points.insert(frame_idx, rot.w, options={'FAST', 'NEEDED'})
                node.fc_rot_x.keyframe_points.insert(frame_idx, rot.x, options={'FAST', 'NEEDED'})
                node.fc_rot_y.keyframe_points.insert(frame_idx, rot.y, options={'FAST', 'NEEDED'})
                node.fc_rot_z.keyframe_points.insert(frame_idx, rot.z, options={'FAST', 'NEEDED'})
                
                node.fc_sca_x.keyframe_points.insert(frame_idx, sca.x, options={'FAST', 'NEEDED'})
                node.fc_sca_y.keyframe_points.insert(frame_idx, sca.y, options={'FAST', 'NEEDED'})
                node.fc_sca_z.keyframe_points.insert(frame_idx, sca.z, options={'FAST', 'NEEDED'})

    def _get_base_pose(self, animation_nodes, nodes, node_base_matrices: dict):
        for idx, (an, node) in enumerate(zip(animation_nodes, nodes)):
            translation = Vector((an.Translation.X, an.Translation.Y, an.Translation.Z)) * 100
            rotation = Quaternion((an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
            scale = an.Scale
            matrix = Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale))
            node_base_matrices[node] = matrix

    def _add_transforms(self, animation_nodes, nodes, frame, overlay: bool, node_base_matrices: dict, transforms: dict):
        frame_data = {}
        nodes_with_animations = set()
        for idx, (an, node) in enumerate(zip(animation_nodes, nodes)):
            translation = Vector((an.Translation.X, an.Translation.Y, an.Translation.Z)) * 100
            rotation = Quaternion((an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
            scale = an.Scale
            
            if any((an.Translation.X, an.Translation.Y, an.Translation.Z, an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z)) or scale != 1.0:
                nodes_with_animations.add(node)
                
            base_matrix = cast(Matrix, node_base_matrices[node])
            overlay_keyed = False
            translation_keyed = False
            rotation_keyed = False
            base_translation, base_rotation, base_scale = base_matrix.decompose()
            if translation.magnitude < tolerance:
                translation = base_translation
            else:
                overlay_keyed = True
                translation_keyed = True
                
            rot_is_zero = all(abs(c) < tolerance for c in (an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
                
            if rot_is_zero:
                rotation = base_rotation
            else:
                overlay_keyed = True
                rotation_keyed = True

            if overlay:
                if overlay_keyed:
                    overlay_translation = (translation + base_translation) if translation_keyed else base_translation
                    overlay_rotation = base_rotation.rotate(rotation) if rotation_keyed else base_rotation
                    matrix = Matrix.LocRotScale(overlay_translation, overlay_rotation, Vector.Fill(3, scale))
                else:
                    matrix = base_matrix
            else:
                matrix = Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale))
                
            frame_data[node] = matrix
        
        transforms[frame] = frame_data
        
        return nodes_with_animations
                    
    def _add_base_transforms(self, animation_nodes, nodes, frame, node_base_matrices: dict, base_transforms: dict):
        frame_data = {}
        for idx, (an, node) in enumerate(zip(animation_nodes, nodes)):
            translation = Vector((an.Translation.X, an.Translation.Y, an.Translation.Z)) * 100
            rotation = Quaternion((an.Rotation.W, an.Rotation.V.X, an.Rotation.V.Y, an.Rotation.V.Z))
            scale = an.Scale
            base_matrix = cast(Matrix, node_base_matrices[node])
            base_translation, base_rotation, base_scale = base_matrix.decompose()
            if translation.magnitude < tolerance:
                translation = base_translation
            if rotation.magnitude < tolerance:
                rotation = base_rotation

            matrix = Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale))
                
            frame_data[node] = matrix
        
        base_transforms[frame] = frame_data
        
    def _import_composite(self, blender_animation, composite_index: int):
        return # TODO
        composites_block = self.tag.SelectField("Struct:definitions[0]/Block:composites")
        if composites_block.Elements.Count == 0 or composite_index >= composites_block.Elements.Count:
            return
        
        composite = composites_block.Elements[composite_index]

        name = composite.SelectField("StringId:name").GetStringData()
        state = utils.space_partition(name, True)
        axis_1 = composite.SelectField("Block:axes[0]")
        axis_2 = composite.SelectField("Block:axes[1]")
        
        use_groups = state == "locomote"
        
        if axis_1 is None:
            return
        
        blend_axis_1 = blender_animation.blend_axes.add()
        blend_axis_1.name = axis_1.SelectField("name")
        blend_axis_1.animation_source_bounds_manual = True
        blend_axis_1.animation_source_bounds = (*axis_1.SelectField("animation bounds").Data,)
        blend_axis_1.runtime_source_bounds_manual = True
        blend_axis_1.runtime_source_bounds = (*axis_1.SelectField("input bounds").Data,)
        blend_axis_1.runtime_source_clamped = axis_1.SelectField("flags").TestBit("clamped")
        blend_axis_1.animation_source_limit = axis_1.SelectField("blend limit").Data
        
        for dead_zone in axis_1.SelectField("Block:dead zones").Elements:
            blender_dead_zone = blend_axis_1.dead_zones.add()
            blender_dead_zone.bounds = (*dead_zone.SelectField("RealBounds:bounds").Data,)
            blender_dead_zone.rate = 360 / dead_zone.SelectField("Real:rate").Data
            
        if use_groups:
            blender_group = blend_axis_1.groups.add()
        
            
    def get_play_text(self, animation, loop: bool, unit: bool, game_object: str = "(player_get 0)") -> str:
        hs_func = "custom_animation_loop" if loop else "custom_animation"
        return f"{hs_func} {game_object} {self.tag_path.RelativePath} {animation.name.replace(' ', ':')} FALSE"
    
    def resource_info(self):
        resource_group = self.tag.SelectField("tag resource groups")
        for element in resource_group.Elements:
            resource = element.SelectField("tag_resource")
            group = element.SelectField("group_members")
            print(group)
            
    def ik_chains_to_blender(self, armature: bpy.types.Object):
        node_names = self.get_nodes()
        
        node_bone_dict = {}
        
        for bone in armature.pose.bones:
            for node in node_names:
                if utils.remove_node_prefix(bone.name) == utils.remove_node_prefix(node):
                    node_bone_dict[node] = bone
        
        for element in self.block_ik_chains.Elements:
            name = element.SelectField("name").GetStringData()
            start_node_index = element.SelectField("start node").Value
            effector_node_index = element.SelectField("effector node").Value
            start_node = node_names[start_node_index] if start_node_index > -1 else None
            effector_node = node_names[effector_node_index] if effector_node_index > -1 else None
            
            start_bone = node_bone_dict[start_node] if start_node is not None else ""
            effector_bone = node_bone_dict[effector_node] if effector_node is not None else ""
            
            blender_ik_chains = bpy.context.scene.nwo.ik_chains
            
            chain = blender_ik_chains.get(name)
            if chain is None:
                chain = blender_ik_chains.add()
                
            chain.name = name
            chain.start_node = start_bone.name
            chain.effector_node = effector_bone.name
            
        print(f"Added / Updated {self.block_ik_chains.Elements.Count} IK Chains")
        
            
    def generate_renames(self, filter=""):
        '''Reads current blender animation names and then parses in the mode n state graph to set up renames in blender'''
        # dict with keys as blender animations and values as sets of renames
        real_animations = {anim.name.replace(" ", ":"): anim for anim in bpy.context.scene.nwo.animations}
        if filter:
            real_animations = {k: v for k, v in real_animations.items() if filter in k}

        graph_dict = self.to_dict()
        renames = detect_renames(graph_dict)
        # renames, copies = detect_copies_from_graph(graph_dict, renames)
        copies = []
        
        for src, dst in renames:
            print(f'renamed "{src}" ==> "{dst}"')

        for src, dst in copies:
            print(f'copied all "{src}" to "{dst}"')
        
        animations_with_renames_count = 0
        renames_count = 0
        
        # add renames to animations
        for src, dst in renames:
            blender_animation = real_animations.get(src)
            if blender_animation is None:
                continue
            
            animations_with_renames_count += 1
            if dst not in {r.name for r in blender_animation.animation_renames}:
                blender_animation.animation_renames.add().name = dst.replace(":", " ")
                
                
        # Add copies
        for src, dst in copies:
            for copy in self.context.scene.nwo.animation_copies:
                if copy.source_name.replace(":", " ") == src.replace(":", " ") and copy.name.replace(":", " ") == dst.replace(":", " "):
                    break
                
            else:
                new_copy = self.context.scene.nwo.animation_copies.add()
                new_copy.source_name = src.replace(":", " ")
                new_copy.name = dst.replace(":", " ")
                
                    
                    
        print(f"\Generated {len(renames)} renames from tag and applied these to {animations_with_renames_count} blender animations\nCreated {len(copies)} animation copies")
        
    def _animation_from_index(self, index, state_type="") -> Animation:
        element = self.block_animations.Elements[index]
        animation = Animation()
        animation.from_element(element)
        if state_type:
            animation.state_types.add(state_type)
        return animation
        
    
    def to_dict(self) -> dict:
        '''Parses the mode n state graph and turns it into a dict'''
        graph = {}
        for mode in self.block_modes.Elements:
            mode_label = mode.Fields[0].GetStringData()
            graph[mode_label] = {}
            
            for weapon_class in mode.Fields[4].Elements:
                weapon_class_label = weapon_class.Fields[0].GetStringData()
                graph[mode_label][weapon_class_label] = {}
                
                for weapon_type in weapon_class.Fields[3].Elements:
                    weapon_type_label = weapon_type.Fields[0].GetStringData()
                    graph[mode_label][weapon_class_label][weapon_type_label] = {}
                    
                    for set in weapon_type.Fields[3].Elements:
                        set_label = set.Fields[0].GetStringData()
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label] = {}
                        
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["actions"] = {action.Fields[0].GetStringData(): self._animation_from_index(action.Fields[3].Elements[0].Fields[1].Value, "action") for action in set.Fields[4].Elements if action.Fields[3].Elements[0].Fields[1].Value > -1}
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["overlay_animations"] = {overlay.Fields[0].GetStringData(): self._animation_from_index(overlay.Fields[3].Elements[0].Fields[1].Value, "overlay") for overlay in set.Fields[5].Elements if overlay.Fields[3].Elements[0].Fields[1].Value > -1}
                        
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"] = {}
                        for death_and_damage in set.Fields[6].Elements:
                            death_and_damage_label = death_and_damage.Fields[0].GetStringData()
                            graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"][death_and_damage_label] = {}
                            for direction in death_and_damage.Fields[1].Elements:
                                direction_label = directions[direction.ElementIndex]
                                graph[mode_label][weapon_class_label][weapon_type_label][set_label]["death_and_damage"][death_and_damage_label][direction_label] = {regions[region.ElementIndex]: self._animation_from_index(region.Fields[0].Elements[0].Fields[1].Value, "death and damage") for region in direction.Fields[0].Elements if region.Fields[0].Elements[0].Fields[1].Value > -1}
                                
                            
                        graph[mode_label][weapon_class_label][weapon_type_label][set_label]["transitions"] = {}
                        
                        for transition in set.Fields[7].Elements:
                            transition_state = transition.Fields[0].GetStringData()
                            graph[mode_label][weapon_class_label][weapon_type_label][set_label]["transitions"][transition_state] = {f"2:{destination.Fields[0].GetStringData()}:{destination.Fields[1].GetStringData()}": self._animation_from_index(destination.Fields[2].Elements[0].Fields[1].Value, "transition") for destination in transition.Fields[1].Elements if destination.Fields[2].Elements[0].Fields[1].Value > -1}
                            
                            
        return graph
    
    def find_animation(self, graph: dict, tokens: list | str, categories: list[str] | None = None):
        '''Finds animations given tokens'''
        if isinstance(tokens, str):
            if ":2:" in tokens:
                p1, p2 = tokens.split(":2:")
                tokens = p1.replace(" ", ":").split(":") + [p2]
            else:
                tokens = tokens.replace(" ", ":").split(":")

        *path_tokens, state_token = tokens

        def walk_tree(level, remaining_tokens, depth=0):
            if not remaining_tokens:
                if any(isinstance(v, dict) for v in level.values()) and not all(
                    k in ("actions", "overlay_animations", "death_and_damage", "transitions") for k in level.keys()
                ):
                    results = []
                    for sublevel in level.values():
                        if isinstance(sublevel, dict):
                            results += walk_tree(sublevel, [], depth + 1)
                    return results

                results = []
                search_categories = categories or ("actions", "overlay_animations", "death_and_damage", "transitions")

                for category in search_categories:
                    cat_data = level.get(category)
                    if not cat_data:
                        continue

                    if category in ("actions", "overlay_animations"):
                        anim = cat_data.get(state_token)
                        if anim:
                            results.append(anim)

                    elif category == "death_and_damage":
                        damage_group = cat_data.get(state_token)
                        if damage_group:
                            for direction in damage_group.values():
                                for animation in direction.values():
                                    results.append(animation)

                    elif category == "transitions":
                        trans_group = cat_data.get(state_token)
                        if trans_group:
                            results.extend(trans_group.values())

                return results

            token = remaining_tokens[0]
            next_tokens = remaining_tokens[1:]

            exact_matches = []
            fallback_matches = []

            if token == "any":
                fallback_matches = [v for v in level.values() if isinstance(v, dict)]
            else:
                if token in level:
                    exact_matches.append(level[token])
                if "any" in level:
                    fallback_matches.append(level["any"])

            results = []
            for branch in exact_matches:
                results += walk_tree(branch, next_tokens, depth + 1)

            if not results:
                for branch in fallback_matches:
                    results += walk_tree(branch, next_tokens, depth + 1)

            return results


        return walk_tree(graph, path_tokens)

    def test_find_animation(self, tokens: list | str, categories=[], graph_dict={}):
        if not graph_dict:
            graph_dict = self.to_dict()
        print("")
        for animation in self.find_animation(graph_dict, tokens):
            print(animation.name, sorted(list(animation.state_types)))
        print("+++++++++++++++++++++++++++++++")
        
    def events_from_blender(self):
        frame_event_list_path = Path(self.tag_path.RelativePath).with_suffix(".frame_event_list")
        with FrameEventListTag(path=frame_event_list_path) as events:
            events.from_blender(self.get_animations())
            
            event_list_tag_ref = self.tag.SelectField("Struct:definitions[0]/Reference:imported events")
            if event_list_tag_ref.Path.RelativePathWithExtension != events.tag_path.RelativePathWithExtension:
                event_list_tag_ref.Path = events.tag_path
                self.tag_has_changes = True
        
    def events_to_blender(self) -> int:
        '''Create AnimationEvents from legacy graph events'''
        event_list_events = {}
        frame_event_list_path = self.get_frame_event_list()
        if not frame_event_list_path:
            utils.print_warning(f"Animation graph contains no reference to a frame event list")
        elif not Path(frame_event_list_path).exists():
            utils.print_warning(f"Frame events list tag does not exist: {frame_event_list_path}")
        else:
            with FrameEventListTag(path=frame_event_list_path) as events:
                event_list_events = events.collect_events()
                
        unique_sounds = []
        for element in self.block_sound_references.Elements:
            ref = Reference()
            ref.from_element(element, self.corinth)
            unique_sounds.append(ref)
            
        unique_effects = []
        for element in self.block_effect_references.Elements:
            ref = Reference()
            ref.from_element(element, self.corinth)
            unique_effects.append(ref)
        
        blender_animations = self.context.scene.nwo.animations
        blender_markers = {ob.nwo.marker_model_group: ob for ob in bpy.data.objects if ob.type == 'EMPTY'}
        event_count = 0
        
        for animation in self.block_animations.Elements:
            name = animation.SelectField("StringId:name").GetStringData()
            name_with_spaces = name.replace(":", " ")
            blender_animation = blender_animations.get(name_with_spaces)
            if blender_animation is None:
                blender_animation = blender_animations.get(name)
                if not blender_animation:
                    # utils.print_warning(f"--- Animation graph contains animation {name_with_spaces} but Blender does not")
                    continue
                
            print(f"--- Getting events for {blender_animation.name}")
            
            animation_events: list[AnimationEvent] = []
            
            for element in animation.SelectField("Block:shared animation data[0]/Block:frame events").Elements:
                event = AnimationEvent()
                event.from_element(element, True)
                animation_events.append(event)
                
            none_event = None
            
            def make_none_event():
                none_event = AnimationEvent()
                animation_events.append(none_event)
                return none_event
            
            for element in animation.SelectField("Block:shared animation data[0]/Block:sound events").Elements:
                if element.SelectField("ShortBlockIndex:sound").Value > -1:
                    sound_event = SoundEvent()
                    sound_event.from_element(element, unique_sounds, True)
                    
                    if sound_event.sound_reference is None:
                        continue
                    
                    if none_event is None:
                        none_event = make_none_event()
                        
                    none_event.sound_events.append(sound_event)
                    
            for element in animation.SelectField("Block:shared animation data[0]/Block:effect events").Elements:
                if element.SelectField("ShortBlockIndex:effect").Value > -1:
                    effect_event = EffectEvent()
                    effect_event.from_element(element, unique_effects, True)
                    
                    if effect_event.effect_reference is None:
                        continue
                    
                    if none_event is None:
                        none_event = make_none_event()
                        
                    none_event.effect_events.append(effect_event)
                        
            for element in animation.SelectField("Block:shared animation data[0]/Block:dialogue events").Elements:
                dialogue_event = DialogueEvent()
                dialogue_event.from_element(element, True)
                
                if none_event is None:
                    none_event = make_none_event()
                    
                none_event.dialogue_events.append(dialogue_event)
                    
            # See if we can make any ranged frame events
            def collapse_events(aes):
                aes.sort(key=lambda x: x.frame, reverse=True)
                result = []
                group_end_frame = aes[0].frame
                
                for curr, next in zip(aes, aes[1:] + [None]):
                    if next:
                        if next.frame == curr.frame - 1 and curr.type == next.type and not (curr.sound_events or curr.effect_events or curr.dialogue_events):
                            continue

                    # Finalize current group
                    curr.end_frame = group_end_frame
                    group_end_frame = next.frame if next else 0
                    result.append(curr)
                        
                return result

            if len(animation_events) > 1:
                animation_events = collapse_events(animation_events)
                    
            # Apply to blender
            def apply_flags(blender_data_event, reference: Reference):
                blender_data_event.flag_allow_on_player = reference.allow_on_player
                blender_data_event.flag_left_arm_only = reference.left_arm_only
                blender_data_event.flag_right_arm_only = reference.right_arm_only
                blender_data_event.flag_first_person_only = reference.first_person_only
                blender_data_event.flag_third_person_only = reference.third_person_only
                blender_data_event.flag_forward_only = reference.forward_only
                blender_data_event.flag_reverse_only = reference.reverse_only
                blender_data_event.flag_fp_no_aged_weapons = reference.fp_no_aged_weapons
                
            # Merge with event list events, frame event list gets priority
            list_events = event_list_events.get(name)
            if list_events is not None:
                graph_events = animation_events
                if not graph_events:
                    animation_events = list_events
                else:
                    valid_graph_events = []
                    for g_event in animation_events:
                        for f_event in list_events:
                            if f_event == g_event:
                                break
                        else:
                            valid_graph_events.append(g_event)
                        
                    animation_events = list_events + valid_graph_events
            
            if animation_events:
                blender_animation.animation_events.clear()     
                for event in sorted(animation_events, key=lambda x: x.frame):
                    blender_event = blender_animation.animation_events.add()
                    blender_event.name = event.name
                    blender_event.frame_frame = blender_animation.frame_start + event.frame
                    if event.end_frame > event.frame:
                        blender_event.multi_frame = 'range'
                        blender_event.frame_range = blender_animation.frame_start + event.end_frame
                    blender_event.frame_name = event.type
                    blender_event.event_id = event.unique_id
                    
                    data_events = event.sound_events + event.effect_events + event.dialogue_events
                    data_events.sort(key=lambda x: x.frame_offset)
                    
                    for data_event in data_events:
                        blender_data_event = blender_event.event_data.add()
                        blender_data_event.frame_offset = data_event.frame_offset
                        if isinstance(data_event, SoundEvent):
                            blender_data_event.data_type = 'SOUND'
                            blender_data_event.frame_offset = data_event.frame_offset
                            blender_data_event.marker = blender_markers.get(data_event.marker_name)
                            blender_data_event.event_sound_tag = data_event.sound_reference.tag
                            apply_flags(blender_data_event, data_event.sound_reference)
                        elif isinstance(data_event, EffectEvent):
                            blender_data_event.data_type = 'EFFECT'
                            blender_data_event.marker = blender_markers.get(data_event.marker_name)
                            blender_data_event.event_effect_tag = data_event.effect_reference.tag
                            apply_flags(blender_data_event, data_event.effect_reference)
                            blender_data_event.damage_effect_reporting_type = data_event.damage_effect_reporting_type
                        else:
                            blender_data_event.data_type = 'DIALOGUE'
                            blender_data_event.dialogue_event = data_event.dialogue_type
                    
                event_count += len(animation_events)
            
        return event_count

def detect_renames(graph):
    name_to_paths = defaultdict(list)

    def walk(path_tokens, node):
        # Categories that hold Animation objects
        for cat in ("actions", "overlay_animations", "transitions", "death_and_damage"):
            if cat not in node:
                continue

            if cat in ("actions", "overlay_animations"):
                for state, anim in node[cat].items():
                    name_to_paths[anim.name].append(":".join(path_tokens + [state]))

            elif cat == "transitions":
                for state, dests in node[cat].items():
                    for key, anim in dests.items():
                        name_to_paths[anim.name].append(":".join(path_tokens + [state, key]))

            elif cat == "death_and_damage":
                for dmg_state, dirs in node[cat].items():
                    for dir_label, regions in dirs.items():
                        for reg_label, anim in regions.items():
                            name_to_paths[anim.name].append(
                                ":".join(path_tokens + [dmg_state, dir_label, reg_label])
                            )

        # Recurse into structural layers
        for k, sub in node.items():
            if isinstance(sub, dict) and k not in (
                "actions",
                "overlay_animations",
                "transitions",
                "death_and_damage",
            ):
                walk(path_tokens + [k], sub)

    walk([], graph)

    renames = []
    for anim_name, paths in name_to_paths.items():
        if len(paths) < 2:
            continue  # unique ⇒ no rename
        canonical_src = ":".join(minimal_path(anim_name.split(":")))
        for p in paths:
            short_p = ":".join(minimal_path(p.split(":")))
            if short_p != canonical_src:
                renames.append((anim_name, short_p))
    return renames


def _strip_trailing_any(toks):
    while toks and toks[-1] == "any":
        toks.pop()
    return toks

def minimal_path(toks):

    # Strip variant markers (…:varX)
    toks = [t for t in toks if not (t.startswith("var") and t[3:].isdigit())]

    # Transition pattern …:state:2:mode:new_state
    if len(toks) >= 5 and toks[-3] == "2":
        base, tail = toks[:-4], toks[-4:]
        return _strip_trailing_any(base) + tail

    # Death & damage …:h_ping:back:gut
    if (
        len(toks) >= 5
        and toks[-3] in damage_states
        and toks[-2] in directions
        and toks[-1] in regions
    ):
        base, tail = toks[:-3], toks[-3:]
        return _strip_trailing_any(base) + tail

    # Normal action / overlay
    head, state = toks[:-1], [toks[-1]]
    return _strip_trailing_any(head) + state
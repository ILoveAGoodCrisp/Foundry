# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2024 Crisp
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ##### END MIT LICENSE BLOCK #####

from math import radians
from pathlib import Path
import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from .Tags import TagFieldBlock, TagFieldElement

from ..managed_blam.render_model import RenderModelTag
from ..managed_blam import Tag
from .. import utils

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
        
    def _initialize_tag(self):
        self.tag.SelectField('Struct:definitions[0]/ShortInteger:animation codec pack').SetStringData('6')
        
    def _node_index_list(self, bones):
        # Have to set up the skeleton nodes block. If we end up with any node usages that point to non-existant nodes, the importer will crash
        node_index_list = [b for b in bones.keys()]
        if self._needs_skeleton_update(node_index_list):
            self.block_skeleton_nodes.RemoveAllElements()
            for n in node_index_list:
                new_node = self.block_skeleton_nodes.AddElement()
                new_node.SelectField('name').SetStringData(n)
                
        return node_index_list
                
    def _needs_skeleton_update(self, node_index_list):
        graph_nodes = [e.SelectField('name').GetStringData() for e in self.block_skeleton_nodes.Elements]
        return node_index_list != graph_nodes
    
    def set_node_usages(self, bones):
        def _node_usage_dict(nwo):
            node_usage_dict = {}
            if nwo.node_usage_pedestal:
                node_usage_dict[nwo.node_usage_pedestal] = "pedestal"
            if nwo.node_usage_physics_control:
                node_usage_dict[nwo.node_usage_physics_control] = "physics control"
            if nwo.node_usage_camera_control:
                node_usage_dict[nwo.node_usage_camera_control] = "camera control"
            if nwo.node_usage_origin_marker:
                node_usage_dict[nwo.node_usage_origin_marker] = "origin marker"
            if nwo.node_usage_left_clavicle:
                node_usage_dict[nwo.node_usage_left_clavicle] = "left clavicle"
            if nwo.node_usage_left_upperarm:
                node_usage_dict[nwo.node_usage_left_upperarm] = "left upperarm"
            if nwo.node_usage_pose_blend_pitch:
                node_usage_dict[nwo.node_usage_pose_blend_pitch] = "pose blend pitch"
            if nwo.node_usage_pose_blend_yaw:
                node_usage_dict[nwo.node_usage_pose_blend_yaw] = "pose blend yaw"
            if nwo.node_usage_pelvis:
                node_usage_dict[nwo.node_usage_pelvis] = "pelvis"
            if nwo.node_usage_left_foot:
                node_usage_dict[nwo.node_usage_left_foot] = "left foot"
            if nwo.node_usage_right_foot:
                node_usage_dict[nwo.node_usage_right_foot] = "right foot"
            if nwo.node_usage_damage_root_gut:
                node_usage_dict[nwo.node_usage_damage_root_gut] = "damage root gut"
            if nwo.node_usage_damage_root_chest:
                node_usage_dict[nwo.node_usage_damage_root_chest] = "damage root chest"
            if nwo.node_usage_damage_root_head:
                node_usage_dict[nwo.node_usage_damage_root_head] = "damage root head"
            if nwo.node_usage_damage_root_left_shoulder:
                node_usage_dict[nwo.node_usage_damage_root_left_shoulder] = "damage root left shoulder"
            if nwo.node_usage_damage_root_left_arm:
                node_usage_dict[nwo.node_usage_damage_root_left_arm] = "damage root left arm"
            if nwo.node_usage_damage_root_left_leg:
                node_usage_dict[nwo.node_usage_damage_root_left_leg] = "damage root left leg"
            if nwo.node_usage_damage_root_left_foot:
                node_usage_dict[nwo.node_usage_damage_root_left_foot] = "damage root left foot"
            if nwo.node_usage_damage_root_right_shoulder:
                node_usage_dict[nwo.node_usage_damage_root_right_shoulder] = "damage root right shoulder"
            if nwo.node_usage_damage_root_right_arm:
                node_usage_dict[nwo.node_usage_damage_root_right_arm] = "damage root right arm"
            if nwo.node_usage_damage_root_right_leg:
                node_usage_dict[nwo.node_usage_damage_root_right_leg] = "damage root right leg"
            if nwo.node_usage_damage_root_right_foot:
                node_usage_dict[nwo.node_usage_damage_root_right_foot] = "damage root right foot"
            if self.corinth:
                if nwo.node_usage_left_hand:
                    node_usage_dict[nwo.node_usage_left_hand] = "left hand"
                if nwo.node_usage_right_hand:
                    node_usage_dict[nwo.node_usage_right_hand] = "right hand"
                if nwo.node_usage_weapon_ik:
                    node_usage_dict[nwo.node_usage_weapon_ik] = "weapon ik"

            return node_usage_dict
        
        # Establish a list of node indexes. These are needed when we write the node usage data
        node_index_list = self._node_index_list(bones)
        node_usage_dict = _node_usage_dict(self.context.scene.nwo)
        self.block_node_usages.RemoveAllElements()
        node_targets = [n for n in node_index_list if n in node_usage_dict.keys()]
        for node in node_targets:
            usage = node_usage_dict[node]
            new_element = self.block_node_usages.AddElement()
            usage_field = new_element.SelectField("usage")
            node_field = new_element.SelectField("node to use")
            items = [i.EnumName for i in usage_field.Items]
            usage_field.Value = items.index(usage)
            node_field.Value = node_index_list.index(node)
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
        
    def write_ik_chains(self, ik_chains: list, bones: list):
        skeleton_nodes = self._node_index_list(bones)
        valid_ik_chains = [chain for chain in ik_chains if chain.start_node in skeleton_nodes and chain.effector_node in skeleton_nodes]
        # Check if we need to write to the block
        chain_names = [chain.name for chain in valid_ik_chains]
        [e.SelectField('name').GetStringData() for e in self.block_skeleton_nodes.Elements]
        if self.block_ik_chains.Elements.Count == len(valid_ik_chains):
            for idx, element in enumerate(self.block_ik_chains.Elements):
                name = element.SelectField('name').GetStringData()
                if name != chain_names[idx]:
                    break
                test_chain = valid_ik_chains[idx]
                start_bone = test_chain.start_node
                effector_bone = test_chain.effector_node
                start_node_index = element.SelectField('start node').Value
                effector_node_index = element.SelectField('effector node').Value
                if start_node_index < 0 or effector_node_index < 0:
                    break
                start_node = skeleton_nodes[start_node_index]
                effector_node = skeleton_nodes[effector_node_index]
                if start_node != start_bone or effector_node != effector_bone:
                    break
                
            else:
                return
        
        if self.block_ik_chains.Elements.Count:
            self.block_ik_chains.RemoveAllElements()
    
        for chain in valid_ik_chains:
            element = self.block_ik_chains.AddElement()
            element.SelectField('name').SetStringData(chain.name)
            element.SelectField('start node').Value = skeleton_nodes.index(chain.start_node)
            element.SelectField('effector node').Value = skeleton_nodes.index(chain.effector_node)
            
        self.tag_has_changes = True
        
    def validate_compression(self, actions: bpy.types.Action, default_compression: str):
        # medium = 0
        # rough = 1
        # uncompressed = 2
        game_animations = {action.nwo.name_override.replace(' ', ':'): action.nwo.compression for action in actions}
        
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
                
    def to_blender(self, render_model: str, armature):
        # Prepare exporter
        print()
        actions = []
        if self.block_animations.Elements.Count < 1: 
            return print("No animations found in graph")
        
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
            first_node = animation_nodes[0]
            animation_count = exporter.GetAnimationCount()
            if not armature.animation_data:
                armature.animation_data_create()
            
            for element in self.block_animations.Elements:
                name = element.SelectField("name").Data
                index = element.ElementIndex
                shared_data = element.SelectField("Block:shared animation data")
                overlay = shared_data.Elements[0].SelectField("animation type").Value > 1
                frame_count = exporter.GetAnimationFrameCount(index)
                action = bpy.data.actions.new(name.replace(":", " "))
                action.use_fake_user = True
                action.use_frame_range = True
                armature.animation_data.action = action
                print(f"--- {action.name}")
                self.jma_data = []
                for frame in range(frame_count):
                    self.jma_bit = []
                    # result = exporter.GetRenderModelBasePose(animation_nodes, nodes_count)
                    result = exporter.GetAnimationFrame(index, frame, animation_nodes, nodes_count)
                    actions.append(self._apply_frames(animation_nodes, armature, frame, action, overlay))
                    self.jma_data.append(self.jma_bit)
                
                action.frame_end = frame_count
                #export(frame_count, animation_nodes, self.jma_data)
                #break
                    
        
        return actions

    def _apply_frames(self, animation_nodes, armature, frame, action: bpy.types.Action, overlay: bool):
        nodes_bones = {bone: node for bone in armature.pose.bones for node in animation_nodes if bone.name == node.Name}
        for idx, (bone, node) in enumerate(nodes_bones.items()):
            default_rotation = utils.ijkw_to_wxyz(self.block_additional_node_dat.Elements[idx].SelectField("default rotation").Data)
            default_translation = Vector([n for n in self.block_additional_node_dat.Elements[idx].SelectField("default translation").Data])
            default_scale = self.block_additional_node_dat.Elements[idx].SelectField("default scale").Data
            translation = Vector((node.Translation.X, node.Translation.Y, node.Translation.Z)) * 100
            rotation = Quaternion((node.Rotation.W, node.Rotation.V.X, node.Rotation.V.Y, node.Rotation.V.Z))
            scale = node.Scale * default_scale
            # print(node.Name, bone.name, armature.animation_data.action.name, frame, translation, rotation)
            default_matrix = Matrix.LocRotScale(default_translation, default_rotation, Vector.Fill(3, default_scale))
            matrix = Matrix.LocRotScale(translation, rotation, Vector.Fill(3, scale))
            final_matrix = default_matrix @ matrix
            bone: bpy.types.PoseBone
            bone.location = translation
            bone.rotation_quaternion = rotation
            bone.scale = Vector.Fill(3, scale)
            # print(frame, node.Translation.ToString())
            # bone.matrix_basis = default_matrix @ matrix
            translation *= 100

        for bone in nodes_bones.keys():
            bone.keyframe_insert(data_path='location', frame=frame)
            bone.keyframe_insert(data_path='rotation_quaternion', frame=frame)
            bone.keyframe_insert(data_path='scale', frame=frame) 
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

from pathlib import Path
import bpy
from io_scene_foundry.utils.nwo_utils import relative_path
from io_scene_foundry.managed_blam import Tag

class AnimationTag(Tag):
    tag_ext = 'model_animation_graph'

    def _read_fields(self):
        self.block_animations = self.tag.SelectField("definitions[0]/Block:animations")
        self.block_skeleton_nodes = self.tag.SelectField("definitions[0]/Block:skeleton nodes")
        self.block_node_usages = self.tag.SelectField("definitions[0]/Block:node usage")
        self.block_modes = self.tag.SelectField("Struct:content[0]/Block:modes")
        self.block_ik_chains = self.tag.SelectField('Struct:definitions[0]/Block:ik chains')
        self.block_blend_screens = self.tag.SelectField('Struct:definitions[0]/Block:NEW blend screens')
        
    def _initialize_tag(self):
        self.tag.SelectField('Struct:definitions[0]/ShortInteger:animation codec pack').SetStringData('6')
        
    def _node_index_list(self, bones):
        # Have to set up the skeleton nodes block. If we end up with any node usages that point to non-existant nodes, the importer will crash
        node_index_list = [b for b in bones.keys()][1:]
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
        parent_path = str(Path(relative_path(parent_graph_path)).with_suffix(".model_animation_graph"))
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
        
    def setup_blend_screens(self, animation_name_list):
        blend_screens_to_remove = []
        tag_animation_names = [name.replace(" ", ":") for name in animation_name_list]
        for element in self.block_blend_screens.Elements:
            if element.SelectField("Struct:animation[0]/ShortBlockIndex:animation").Value > -1:
                animation_name = self._get_animation_name_from_index(element.ElementIndex)
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
                if "aim" in state:
                    yaw_source_value = "aim yaw"
                    pitch_source_value = "aim pitch"
                elif "look" in state:
                    yaw_source_value = "look yaw"
                    pitch_source_value = "look pitch"
                elif "steer" in state:
                    yaw_source_value = "steering"
                    pitch_source_value = "steering"
                elif "acc" in state:
                    yaw_source_value = "acceleration yaw"
                    pitch_source_value = "acceleration pitch"
                elif "pitch" in state and "turn" in state:
                    yaw_source_value = "first person turn"
                    pitch_source_value = "first person pitch"
                    
                element.SelectField("yaw source").SetValue(yaw_source_value)
                element.SelectField("pitch source").SetValue(pitch_source_value)
                
                self.tag_has_changes = True
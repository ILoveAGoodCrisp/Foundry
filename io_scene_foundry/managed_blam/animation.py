# ##### BEGIN MIT LICENSE BLOCK #####
#
# MIT License
#
# Copyright (c) 2023 Crisp
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

from io_scene_foundry.managed_blam import Tag

class AnimationTag(Tag):
    tag_ext = 'model_animation_graph'

    def _read_fields(self):
        self.block_animations = self.tag.SelectField("definitions[0]/Block:animations")
        self.block_skeleton_nodes = self.tag.SelectField("definitions[0]/Block:skeleton nodes")
        self.block_node_usages = self.tag.SelectField("definitions[0]/Block:node usage")
        self.block_modes = self.tag.SelectField("Struct:content[0]/Block:modes")
        
    def _initialize_tag(self):
        self.tag.SelectField('Struct:definitions[0]/ShortInteger:animation codec pack').SetStringData('6')
    
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
        def _node_index_list(block_skeleton_nodes, bones):
            # Have to set up the skeleton nodes block. If we end up with any node usages that point to non-existant nodes, the importer will crash
            node_index_list = [b for b in bones.keys()][1:]
            if _needs_skeleton_update(block_skeleton_nodes, node_index_list):
                self.block_skeleton_nodes.RemoveAllElements()
                for n in node_index_list:
                    new_node = block_skeleton_nodes.AddElement()
                    new_node.SelectField('name').SetStringData(n)
                    
            return node_index_list
                    
        def _needs_skeleton_update(block_skeleton_nodes, node_index_list):
            graph_nodes = [e.SelectField('name').GetStringData() for e in block_skeleton_nodes.Elements]
            return node_index_list != graph_nodes
        
        # Establish a list of node indexes. These are needed when we write the node usage data
        node_index_list = _node_index_list(self.block_skeleton_nodes, bones)
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
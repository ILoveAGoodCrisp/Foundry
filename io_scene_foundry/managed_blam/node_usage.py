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

import os
from io_scene_foundry.utils.nwo_utils import get_asset_path
from . import ManagedBlam

class ManagedBlamNodeUsage(ManagedBlam):
    def __init__(self, armature, bones):
      super().__init__()
      self.node_usage_dict = self.get_node_usage_dict(armature)
      self.bones = bones
      self.tag_helper()

    def get_node_usage_dict(self, armature):
      node_usage_dict = {}
      nwo = armature.nwo
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

    def get_path(self):
      asset_path = get_asset_path()
      asset_name = asset_path.rpartition(os.sep)[2]
      graph_path = os.path.join(asset_path, asset_name + ".model_animation_graph")
      return graph_path
    
    def get_node_index_list(self, bones, definition_block, skeleton_nodes):
      # Have to set up the skeleton nodes block. If we end up with any node usages that point to non-existant nodes, the importer will crash
      node_index_list = [b for b in bones.keys()][1:]
      if self.needs_skeleton_update(skeleton_nodes, node_index_list):
         self.clear_block(definition_block, 'skeleton nodes')
         for n in node_index_list:
            new_node = self.block_new_element(definition_block, 'skeleton nodes')
            self.Element_set_field_value(new_node, 'name', n)

      return node_index_list
    
    def needs_skeleton_update(self, skeleton_nodes, node_index_list):
       elements = skeleton_nodes.Elements
       graph_nodes = [self.Element_get_field_value(e, 'name') for e in elements]
       return node_index_list != graph_nodes

    def tag_edit(self, tag):
      definitions = tag.SelectField("Struct:definitions")
      definition_block = definitions.Elements[0]
      # Establish a list of node indexes. These are needed when we write the node usage data
      node_usages = definition_block.SelectField("Block:node usage")
      skeleton_nodes = definition_block.SelectField("Block:skeleton nodes")
      node_index_list = self.get_node_index_list(self.bones, definition_block, skeleton_nodes)
      node_usages.RemoveAllElements()
      for node in node_index_list:
         if node in self.node_usage_dict.keys():
            usage = self.node_usage_dict[node]
            new_element = node_usages.AddElement()
            usage_field = new_element.SelectField("usage")
            node_field = new_element.SelectField("node to use")
            items = [i.EnumName for i in usage_field.Items]
            usage_field.Value = items.index(usage)
            node_field.Value = node_index_list.index(node)
                


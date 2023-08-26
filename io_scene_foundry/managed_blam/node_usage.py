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
    def __init__(self, armature):
      super().__init__()
      self.node_usage_dict = self.get_node_usage_dict(armature)
      self.tag_helper()

    def get_node_usage_dict(self, armature):
      node_usage_dict = {}
      nwo = armature.nwo
      if nwo.node_usage_physics_control:
         node_usage_dict["physics control"] = nwo.node_usage_physics_control
      if nwo.node_usage_camera_control:
         node_usage_dict["camera control"] = nwo.node_usage_camera_control
      if nwo.node_usage_origin_marker:
         node_usage_dict["origin marker"] = nwo.node_usage_origin_marker
      if nwo.node_usage_left_clavicle:
         node_usage_dict["left clavicle"] = nwo.node_usage_left_clavicle
      if nwo.node_usage_left_upperarm:
         node_usage_dict["left upperarm"] = nwo.node_usage_left_upperarm
      if nwo.node_usage_pose_blend_pitch:
         node_usage_dict["pose blend pitch"] = nwo.node_usage_pose_blend_pitch
      if nwo.node_usage_pose_blend_yaw:
         node_usage_dict["pose blend yaw"] = nwo.node_usage_pose_blend_yaw
      if nwo.node_usage_pedestal:
         node_usage_dict["pedestal"] = nwo.node_usage_pedestal
      if nwo.node_usage_pelvis:
         node_usage_dict["pelvis"] = nwo.node_usage_pelvis
      if nwo.node_usage_left_foot:
         node_usage_dict["left foot"] = nwo.node_usage_left_foot
      if nwo.node_usage_right_foot:
         node_usage_dict["right foot"] = nwo.node_usage_right_foot
      if nwo.node_usage_damage_root_gut:
         node_usage_dict["damage root gut"] = nwo.node_usage_damage_root_gut
      if nwo.node_usage_damage_root_chest:
         node_usage_dict["damage root chest"] = nwo.node_usage_damage_root_chest
      if nwo.node_usage_damage_root_head:
         node_usage_dict["damage root head"] = nwo.node_usage_damage_root_head
      if nwo.node_usage_damage_root_left_shoulder:
         node_usage_dict["damage root left shoulder"] = nwo.node_usage_damage_root_left_shoulder
      if nwo.node_usage_damage_root_left_arm:
         node_usage_dict["damage root left arm"] = nwo.node_usage_damage_root_left_arm
      if nwo.node_usage_damage_root_left_leg:
         node_usage_dict["damage root left leg"] = nwo.node_usage_damage_root_left_leg
      if nwo.node_usage_damage_root_left_foot:
         node_usage_dict["damage root left foot"] = nwo.node_usage_damage_root_left_foot
      if nwo.node_usage_damage_root_right_shoulder:
         node_usage_dict["damage root right shoulder"] = nwo.node_usage_damage_root_right_shoulder
      if nwo.node_usage_damage_root_right_arm:
         node_usage_dict["damage root right arm"] = nwo.node_usage_damage_root_right_arm
      if nwo.node_usage_damage_root_right_leg:
         node_usage_dict["damage root right leg"] = nwo.node_usage_damage_root_right_leg
      if nwo.node_usage_damage_root_right_foot:
         node_usage_dict["damage root right foot"] = nwo.node_usage_damage_root_right_foot
      if self.corinth:
         if nwo.node_usage_left_hand:
            node_usage_dict["left hand"] = nwo.node_usage_left_hand
         if nwo.node_usage_right_hand:
            node_usage_dict["right hand"] = nwo.node_usage_right_hand
         if nwo.node_usage_weapon_ik:
            node_usage_dict["weapon ik"] = nwo.node_usage_weapon_ik

      return node_usage_dict

    def get_path(self):
      asset_path = get_asset_path()
      asset_name = asset_path.rpartition(os.sep)[2]
      graph_path = os.path.join(asset_path, asset_name + ".model_animation_graph")
      return graph_path
    
    def get_node_index_list(self, definition_block):
      """Loops through each element in the skeleton nodes block and returns a list of bone names"""
      node_index_list = []
      block = definition_block.SelectField("Block:skeleton nodes")
      for element in block:
         field = element.SelectField("name")
         node_index_list.append(field.GetStringData())

      return node_index_list

    def tag_edit(self, tag):
      definitions = tag.SelectField("Struct:definitions")
      definition_block = definitions.Elements[0]
      # Establish a list of node indexes. These are needed when we write the node usage data
      node_index_list = self.get_node_index_list(definition_block)
      node_usages = definition_block.SelectField("Block:node usage")
      # loop through existing blocks, applying node indexes
      # for element in block:
      #     e_count += 1
      #     usage = element.SelectField("usage")
      #     node = element.SelectField("node to use")
      #     items = [i.EnumName for i in usage.Items]
      #     for i in items:
      #         for k, v in self.node_usage_dict.items():
      #             if i == k:
      #                 if v in node_index_list:
      #                     print(k, v)
      #                     node.Value = node_index_list.index(v)
      #                     print(node.Value)
      #                 self.node_usage_dict.pop(k)
      #                 break

      # If items remain in node_usage_dict, then we need to add new elements
      node_usages.RemoveAllElements()
      for k, v in self.node_usage_dict.items():
         if v in node_index_list:
               new_element = node_usages.AddElement()
               usage = new_element.SelectField("usage")
               node = new_element.SelectField("node to use")
               items = [i.EnumName for i in usage.Items]
               usage.Value = items.index(k)
               node.Value = node_index_list.index(v)
                


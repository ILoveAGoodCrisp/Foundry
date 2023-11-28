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

class ManagedBlamReachWorldAnimations(ManagedBlam):
    def __init__(self, reach_world_animations):
      super().__init__()
      self.reach_world_animations = reach_world_animations
      self.tag_helper()

    def get_path(self):
      asset_path = get_asset_path()
      asset_name = asset_path.rpartition(os.sep)[2]
      graph_path = os.path.join(asset_path, asset_name + ".model_animation_graph")
      return graph_path

    def tag_edit(self, tag):
      definitions = tag.SelectField("Struct:definitions")
      definition_block = definitions.Elements[0]
      animations = definition_block.SelectField('animations')
      for element in animations.Elements:
          if self.Element_get_field_value(element, 'name') in self.reach_world_animations:
              data_block = element.SelectField('shared animation data')
              animation_data = data_block.Elements[0]
              flags = animation_data.SelectField('internal flags')
              flags.SetBit('world relative', True)
      


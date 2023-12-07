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
import os
from io_scene_foundry.utils import nwo_utils

class ScenarioTag(Tag):
        
    def _get_path(self):
        return os.path.join(self.asset_dir, self.asset_name + '.scenario')
        
    def _read_blocks(self):
        self.block_skies = self.tag.SelectField("Block:skies")
        self.block_object_names = self.tag.SelectField("Block:object names")
    
    def get_skies_mapping(self):
        """Reads the scenario skies block and returns a list of skies"""
        skies = []
        for element in self.block_skies.Elements:
            sky_name = ""
            # Check if we can retrieve the name from the object names block
            object_names_block_index = self.Element_get_field_value(element, "name")
            if object_names_block_index:
                object_names_element = self.block_object_names.Elements[object_names_block_index]
                object_name = self.Element_get_field_value(object_names_element, "name")
                if object_name:
                    sky_name = object_name
            
            # If we haven't yet found the name, just take the tag name
            if not sky_name:
                sky_tag_path = self.Element_get_field_value(element, "sky")
                if not sky_tag_path: continue
                sky_name = nwo_utils.dot_partition(os.path.basename(sky_tag_path.ToString()))
                
            skies.append(sky_name)
            
        return skies
    
    def add_new_sky(self, path):
        """Appends a new entry to the scenario skies block, adding a reference to the given sky scenery tag path"""
        new_sky_element = self.block_skies.AddElement()
        self.Element_set_field_value(new_sky_element, "sky", self.TagPath_from_string(path))
        new_object_name_element = self.block_object_names.AddElement()
        sky_name = nwo_utils.dot_partition(os.path.basename(path))
        self.Element_set_field_value(new_object_name_element, "name", sky_name)
        self.Element_set_field_value(new_sky_element, "name", new_object_name_element.ElementIndex)
        
        return sky_name, new_sky_element.ElementIndex
                
            
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
        self.block_bsps = self.tag.SelectField("Block:structure bsps")
        
    def _get_bsp_from_name(self, bsp_name: str):
        for element in self.block_bsps.Elements:
            bsp_reference = self.Element_get_field_value(element, "structure bsp")
            full_bsp_name = nwo_utils.dot_partition(os.path.basename(bsp_reference.ToString()))
            short_bsp_name = full_bsp_name.split(self.asset_name + '_')[1]
            if short_bsp_name == bsp_name:
                return element
        else:
            return print("BSP not found in Scenario Tag, perhaps you need to export the scene")
        
    def _sky_name_from_element(self, element):
        # Check if we can retrieve the name from the object names block
        object_names_block_index = self.Element_get_field_value(element, "name")
        if object_names_block_index:
            object_names_element = self.block_object_names.Elements[object_names_block_index]
            object_name = self.Element_get_field_value(object_names_element, "name")
            if object_name:
                return object_name
        
        # If we haven't yet found the name, just take the tag name
        sky_tag_path = self.Element_get_field_value(element, "sky")
        if not sky_tag_path: return
        return nwo_utils.dot_partition(os.path.basename(sky_tag_path.ToString()))
    
    def get_skies_mapping(self) -> list:
        """Reads the scenario skies block and returns a list of skies"""
        skies = []
        for element in self.block_skies.Elements:
            sky_name = self._sky_name_from_element(element)
            if sky_name is None: continue  
            skies.append(sky_name)
            
        return skies
    
    def add_new_sky(self, path: str) -> tuple[str, int]:
        """Appends a new entry to the scenario skies block, adding a reference to the given sky scenery tag path"""
        new_sky_element = self.block_skies.AddElement()
        self.Element_set_field_value(new_sky_element, "sky", self.TagPath_from_string(path))
        new_object_name_element = self.block_object_names.AddElement()
        sky_name = nwo_utils.dot_partition(os.path.basename(path))
        self.Element_set_field_value(new_object_name_element, "name", sky_name)
        self.Element_set_field_value(new_sky_element, "name", new_object_name_element.ElementIndex)
        
        return sky_name, new_sky_element.ElementIndex
    
    def set_bsp_default_sky(self, bsp_name: str, sky_index: int):
        """Sets the default sky of the given bsp"""
        # Get the bsp we want from the list
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return
        # Check current sky to see if we need to update it
        sky_block_index = self.Element_get_field_value(bsp_element, "default sky")
        if sky_block_index == sky_index:
            print("Default sky already set to this")
        else:
            self.Element_set_field_value(bsp_element, "default sky", sky_index)
        
        return self._sky_name_from_element(self.block_skies.Elements[sky_index])
        
    def set_bsp_lightmap_res(self, bsp_name: str, size_class: int, refinement_class: int) -> bool:
        """Sets the lightmap resolution and refinement class for this bsp"""
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return False
        bsp_element.SelectField('size class').Value = size_class
        if self.corinth:
            bsp_element.SelectField('refinement size class').Value = refinement_class
            
        return True
        
        
    def get_bsp_info(self, bsp_name: str) -> dict:
        """Returns interesting information about this BSP in a dict"""
        bsp_info_dict = {}
        bsp_element = self._get_bsp_from_name(bsp_name)
        if bsp_element is None: return
        bsp_info_dict["Lightmapper Size Class"] = self.Element_get_enum_as_string(bsp_element, "size class")
        if self.corinth:
            bsp_info_dict["Lightmapper Refinement Class"] = self.Element_get_enum_as_string(bsp_element, "refinement size class")
        sky_index = self.Element_get_field_value(bsp_element, "default sky")
        if sky_index == -1:
            bsp_info_dict["Default Sky"] = "None"
        else:
            bsp_info_dict["Default Sky"] = self._sky_name_from_element(self.block_skies.Elements[sky_index])
        
        return bsp_info_dict
        
        
                
        
        
                
            